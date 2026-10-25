# -*- coding: utf-8 -*-
"""学习小组排行榜、断签保护卡。（每周学习报告在 /study/weekly-report）"""

from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.core import timeutil
from app.core.errors import ApiError, ok
from app.models import StreakFreeze
from app.schemas import GroupIn, GroupJoinIn
from app.services import gamification, social

# 不设 prefix：本模块内的路径写完整（如 /groups），由 main.py 统一注册
router = APIRouter(tags=["成长社交"])


# ---------------------------------------------------------------- 学习小组
@router.get("/groups", summary="我加入的学习小组（含我在组内的本周排名）")
def list_groups(user: CurrentUser, db: DB):
    return ok(social.my_groups(db, user))


@router.post("/groups", summary="创建学习小组（自动生成邀请码，创建者为组长）")
def create_group(payload: GroupIn, user: CurrentUser, db: DB):
    group = social.create_group(db, user, payload.name)
    db.commit()
    return ok(social.group_to_dict(db, group, user, with_board=True), f"小组已创建，邀请码 {group.invite_code}")


@router.post("/groups/join", summary="用邀请码加入小组")
def join_group(payload: GroupJoinIn, user: CurrentUser, db: DB):
    group = social.join_group(db, user, payload.invite_code)
    db.commit()
    return ok(social.group_to_dict(db, group, user, with_board=True), f"已加入「{group.name}」")


@router.get("/groups/{group_id}", summary="小组详情与组内本周 XP 排行")
def group_detail(group_id: int, user: CurrentUser, db: DB):
    group = social.get_my_group(db, user, group_id)
    return ok(social.group_to_dict(db, group, user, with_board=True))


@router.post("/groups/{group_id}/leave", summary="退出小组（组长退出时自动转让，最后一人退出时解散）")
def leave_group(group_id: int, user: CurrentUser, db: DB):
    group = social.get_my_group(db, user, group_id)
    name = group.name
    result = social.leave_group(db, user, group)
    db.commit()
    return ok({"id": group_id, **result}, f"已退出「{name}」" + ("，小组已解散" if result["dissolved"] else ""))


@router.delete("/groups/{group_id}", summary="解散小组（仅组长）")
def dissolve_group(group_id: int, user: CurrentUser, db: DB):
    group = social.get_my_group(db, user, group_id)
    name = group.name
    social.dissolve_group(db, user, group)
    db.commit()
    return ok({"id": group_id}, f"「{name}」已解散")


@router.post("/groups/{group_id}/invite-code", summary="重新生成邀请码（仅组长，旧邀请码失效）")
def reset_invite_code(group_id: int, user: CurrentUser, db: DB):
    group = social.get_my_group(db, user, group_id)
    if group.owner_id != user.id:
        raise ApiError(403, "只有组长可以重置邀请码")
    group.invite_code = social.new_invite_code(db)
    db.commit()
    return ok(social.group_to_dict(db, group, user), f"新邀请码 {group.invite_code}")


# ---------------------------------------------------------------- 断签保护卡
@router.get("/streak/freezes", summary="断签保护卡：持有数量、获得规则与使用记录")
def streak_freezes(user: CurrentUser, db: DB):
    # 先把推演出的变化落库，保证"使用记录"与连续天数一致
    gamification.settle_freezes(db, user)
    db.commit()
    streak = gamification.streak_info(db, user.id)
    rows = (
        db.query(StreakFreeze)
        .filter(StreakFreeze.user_id == user.id, StreakFreeze.kind.in_(["used", "earned"]))
        .order_by(StreakFreeze.day.desc())
        .limit(30)
        .all()
    )
    return ok({
        "held": streak["freezes"],
        "max": gamification.FREEZE_MAX,
        "every": gamification.FREEZE_EVERY,
        "next_freeze_in": streak["next_freeze_in"],
        "streak": streak["current"],
        "last_protected": streak["last_protected"],
        "history": [
            {"day": r.day, "kind": r.kind, "label": "保住连续记录" if r.kind == "used" else f"连续学习满 {gamification.FREEZE_EVERY} 天获得",
             "weekday": timeutil.weekday_label(timeutil.parse_date(r.day))}
            for r in rows
        ],
    })
