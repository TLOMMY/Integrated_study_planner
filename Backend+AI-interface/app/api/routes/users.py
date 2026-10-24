# -*- coding: utf-8 -*-
from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.core.errors import ApiError, ok
from app.core.security import hash_password, token_payload, verify_password
from app.models import AiProvider, FocusRecord, ImportLog, StudyPlan, StudyTask, Timetable, User, UserAchievement, XpEvent
from app.schemas import EmailChangeIn, PasswordConfirmIn, PasswordIn, PhoneChangeIn, StudyPrefsIn, UserUpdateIn
from app.services import prefs
from app.services.accounts import user_to_dict

router = APIRouter(prefix="/users", tags=["用户"])


def _check_password(user: User, password: str) -> None:
    if not verify_password(password, user.hashed_password):
        raise ApiError(400, "密码不正确")


def _no_demo(user: User, action: str) -> None:
    if user.is_demo:
        raise ApiError(403, f"演示账号不支持{action}，请注册自己的账号")


@router.get("/me", summary="当前用户信息")
def get_me(user: CurrentUser):
    return ok(user_to_dict(user))


@router.put("/me", summary="修改昵称 / 头像 / 每日目标")
def update_me(payload: UserUpdateIn, user: CurrentUser, db: DB):
    for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return ok(user_to_dict(user), "资料已更新")


@router.put("/me/password", summary="修改密码（其他设备上的登录随即失效）")
def change_password(payload: PasswordIn, user: CurrentUser, db: DB):
    _no_demo(user, "修改密码")
    if not verify_password(payload.old_password, user.hashed_password):
        raise ApiError(400, "原密码不正确")
    if payload.old_password == payload.new_password:
        raise ApiError(400, "新密码不能与原密码相同")
    user.hashed_password = hash_password(payload.new_password)
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    # 当前设备换发新凭证，继续保持登录
    return ok(token_payload(user), "密码已修改，其他设备需要重新登录")


@router.put("/me/email", summary="换绑邮箱（需验证密码）")
def change_email(payload: EmailChangeIn, user: CurrentUser, db: DB):
    _no_demo(user, "换绑邮箱")
    _check_password(user, payload.password)
    email = payload.email.lower()
    if email == (user.email or "").lower():
        raise ApiError(400, "新邮箱与当前邮箱相同")
    if db.query(User.id).filter(User.email == email, User.id != user.id).first():
        raise ApiError(400, "该邮箱已被其他账号使用")
    # 用户名默认就是注册邮箱：跟着换，避免旧邮箱仍能作为用户名登录
    if user.username == user.email and not db.query(User.id).filter(User.username == email).first():
        user.username = email
    user.email = email
    db.commit()
    db.refresh(user)
    return ok(user_to_dict(user), "邮箱已更新，下次可用新邮箱登录")


@router.put("/me/phone", summary="绑定 / 解绑手机号（需验证密码；暂不发送短信验证码）")
def change_phone(payload: PhoneChangeIn, user: CurrentUser, db: DB):
    _no_demo(user, "绑定手机号")
    _check_password(user, payload.password)
    if payload.phone and db.query(User.id).filter(User.phone == payload.phone, User.id != user.id).first():
        raise ApiError(400, "该手机号已绑定其他账号")
    user.phone = payload.phone
    db.commit()
    db.refresh(user)
    return ok(user_to_dict(user), "手机号已绑定" if payload.phone else "已解绑手机号")


@router.post("/me/logout-all", summary="退出所有设备（所有旧凭证失效，当前设备换发新凭证）")
def logout_all(user: CurrentUser, db: DB):
    user.token_version = int(user.token_version or 0) + 1
    db.commit()
    return ok(token_payload(user), "已退出其他所有设备")


@router.get("/me/study-prefs", summary="学习时段偏好 + 专注习惯统计（AI 排程会读取）")
def get_study_prefs(user: CurrentUser, db: DB):
    return ok(prefs.to_dict(db, user))


@router.put("/me/study-prefs", summary="保存学习时段偏好")
def save_study_prefs(payload: StudyPrefsIn, user: CurrentUser, db: DB):
    prefs.save(user, payload.model_dump())
    db.commit()
    return ok(prefs.to_dict(db, user), "学习偏好已保存，AI 排程会按此安排")


@router.get("/me/export", summary="导出我的全部数据（JSON）")
def export_data(user: CurrentUser, db: DB):
    def rows(model, *order):
        query = db.query(model).filter(model.user_id == user.id)
        return [
            {c.name: (v.isoformat() if hasattr(v, "isoformat") else v) for c in model.__table__.columns
             for v in [getattr(item, c.name)] if c.name not in {"api_key_enc"}}
            for item in query.order_by(*order).all()
        ]

    return ok({
        "user": {**user_to_dict(user), "study_prefs": prefs.load(user)},
        "timetables": rows(Timetable, Timetable.id),
        "study_plans": rows(StudyPlan, StudyPlan.id),
        "study_tasks": rows(StudyTask, StudyTask.id),
        "focus_records": rows(FocusRecord, FocusRecord.id),
        "xp_events": rows(XpEvent, XpEvent.id),
        "achievements": rows(UserAchievement, UserAchievement.id),
        "ai_providers": rows(AiProvider, AiProvider.id),
        "import_logs": rows(ImportLog, ImportLog.id),
    }, "数据已导出")


@router.delete("/me", summary="注销账号（删除全部数据，不可恢复）")
def delete_account(payload: PasswordConfirmIn, user: CurrentUser, db: DB):
    _no_demo(user, "注销")
    _check_password(user, payload.password)
    for model in (FocusRecord, StudyTask, StudyPlan, Timetable, XpEvent, UserAchievement, AiProvider, ImportLog):
        db.query(model).filter(model.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()
    return ok(None, "账号已注销，所有数据已删除")
