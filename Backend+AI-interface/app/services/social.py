# -*- coding: utf-8 -*-
"""学习小组：邀请码加入、组内本周 XP 排行。"""

import secrets
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import StudyGroup, StudyGroupMember, User
from app.services import gamification
from app.services.schedule import SHARE_ALPHABET, normalize_share_code

MAX_MEMBERS = 50
MAX_GROUPS_PER_USER = 10
CODE_LENGTH = 6


def new_invite_code(db: Session) -> str:
    code = ""
    for _ in range(20):
        code = "".join(secrets.choice(SHARE_ALPHABET) for _ in range(CODE_LENGTH))
        if not db.query(StudyGroup.id).filter(StudyGroup.invite_code == code).first():
            break
    return code


def member_ids(db: Session, group_id: int) -> List[int]:
    return [uid for (uid,) in db.query(StudyGroupMember.user_id).filter(StudyGroupMember.group_id == group_id).all()]


def get_my_group(db: Session, user: User, group_id: int) -> StudyGroup:
    """只有组员能看到小组；不是组员一律当作不存在。"""
    group = (
        db.query(StudyGroup)
        .join(StudyGroupMember, StudyGroupMember.group_id == StudyGroup.id)
        .filter(StudyGroup.id == group_id, StudyGroupMember.user_id == user.id)
        .first()
    )
    if group is None:
        raise ApiError(404, "小组不存在，或你已不在该小组")
    return group


def group_to_dict(db: Session, group: StudyGroup, user: User, with_board: bool = False) -> dict:
    ids = member_ids(db, group.id)
    board = gamification.group_leaderboard(db, user, ids)
    owner = db.get(User, group.owner_id)
    data = {
        "id": group.id,
        "name": group.name,
        "invite_code": group.invite_code,
        "owner_id": group.owner_id,
        "owner_name": (owner.full_name or owner.username) if owner else "",
        "is_owner": group.owner_id == user.id,
        "member_count": len(ids),
        "max_members": MAX_MEMBERS,
        "my_rank": board["me"]["rank"] if board["me"] else None,
        "my_xp": board["me"]["xp"] if board["me"] else 0,
        "week_start": board["week_start"],
        "created_at": group.created_at.isoformat() if group.created_at else None,
    }
    if with_board:
        data["leaderboard"] = board
    return data


def my_groups(db: Session, user: User) -> List[dict]:
    groups = (
        db.query(StudyGroup)
        .join(StudyGroupMember, StudyGroupMember.group_id == StudyGroup.id)
        .filter(StudyGroupMember.user_id == user.id)
        .order_by(StudyGroupMember.joined_at, StudyGroup.id)
        .all()
    )
    return [group_to_dict(db, g, user) for g in groups]


def create_group(db: Session, user: User, name: str) -> StudyGroup:
    joined = db.query(func.count(StudyGroupMember.id)).filter(StudyGroupMember.user_id == user.id).scalar()
    if joined >= MAX_GROUPS_PER_USER:
        raise ApiError(422, f"最多同时加入 {MAX_GROUPS_PER_USER} 个小组")
    group = StudyGroup(name=name, owner_id=user.id, invite_code=new_invite_code(db))
    db.add(group)
    db.flush()
    db.add(StudyGroupMember(group_id=group.id, user_id=user.id))
    db.flush()
    return group


def join_group(db: Session, user: User, code: str) -> StudyGroup:
    group = db.query(StudyGroup).filter(StudyGroup.invite_code == normalize_share_code(code)).first()
    if group is None:
        raise ApiError(404, "邀请码不存在，请检查是否输入正确")
    exists = db.query(StudyGroupMember.id).filter_by(group_id=group.id, user_id=user.id).first()
    if exists:
        raise ApiError(409, f"你已经在「{group.name}」里了")
    if len(member_ids(db, group.id)) >= MAX_MEMBERS:
        raise ApiError(422, f"小组人数已满（{MAX_MEMBERS} 人）")
    joined = db.query(func.count(StudyGroupMember.id)).filter(StudyGroupMember.user_id == user.id).scalar()
    if joined >= MAX_GROUPS_PER_USER:
        raise ApiError(422, f"最多同时加入 {MAX_GROUPS_PER_USER} 个小组")
    db.add(StudyGroupMember(group_id=group.id, user_id=user.id))
    db.flush()
    return group


def leave_group(db: Session, user: User, group: StudyGroup) -> dict:
    """退出小组。组长退出时组长转给最早加入的组员；最后一人退出时小组解散。"""
    db.query(StudyGroupMember).filter_by(group_id=group.id, user_id=user.id).delete()
    db.flush()
    rest = (
        db.query(StudyGroupMember)
        .filter(StudyGroupMember.group_id == group.id)
        .order_by(StudyGroupMember.joined_at, StudyGroupMember.id)
        .first()
    )
    if rest is None:
        db.delete(group)
        return {"dissolved": True, "new_owner_id": None}
    if group.owner_id == user.id:
        group.owner_id = rest.user_id
        return {"dissolved": False, "new_owner_id": rest.user_id}
    return {"dissolved": False, "new_owner_id": None}


def dissolve_group(db: Session, user: User, group: StudyGroup) -> None:
    if group.owner_id != user.id:
        raise ApiError(403, "只有组长可以解散小组")
    db.query(StudyGroupMember).filter(StudyGroupMember.group_id == group.id).delete()
    db.delete(group)
