# -*- coding: utf-8 -*-
"""
AI 对话（智能体）：服务器保存的多轮对话、工具调用、流式输出、创建/修改任务与课程的提案。

POST /ai/conversations/{id}/chat 返回 SSE（text/event-stream），事件：
  status    {"text"}                         阶段提示
  reasoning {"delta"}                        思考过程片段（思考模式）
  text      {"delta"}                        回复正文片段
  tool      {"id","name","label","status","summary"}  工具调用 running / done
  proposal  {"proposal","replaces"}          提案卡片（tasks / courses / changes / ask）
  error     {"message"}                      出错（之后仍会发送 done）
  done      {"message", "user_message", "conversation"}  最终保存的助手消息
"""

import json
import logging
import re

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.ai import agent
from app.api.deps import DB, CurrentUser
from app.core import timeutil
from app.core.database import SessionLocal
from app.core.errors import ApiError, ok
from app.models import ChatConversation, ChatMessage, User
from app.schemas import AgentChatIn, ConversationImportIn, ConversationIn, ConversationUpdateIn, ProposalApplyIn
from app.services import gamification
from app.services.tasks import plan_to_dict

logger = logging.getLogger("study_planner.agent")

# 不设 prefix：本模块内的路径写完整（如 /ai/chat/...），由 main.py 统一注册
router = APIRouter(tags=["AI 对话"])

MAX_CONVERSATIONS = 200
DEFAULT_TITLE = "新对话"


# ---------------------------------------------------------------- 序列化
def _load(text):
    try:
        value = json.loads(text) if text else None
        return value if isinstance(value, dict) else None
    except (TypeError, ValueError):
        return None


def message_to_dict(message: ChatMessage) -> dict:
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "role": message.role,
        "content": message.content or "",
        "meta": agent.load_meta(message),
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def conversation_to_dict(db, conversation: ChatConversation) -> dict:
    last = (db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation.id)
            .order_by(ChatMessage.id.desc()).first())
    count = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation.id).count()
    preview = re.sub(r"\s+", " ", (last.content or "") if last else "").strip()[:60]
    return {
        "id": conversation.id,
        "title": conversation.title or DEFAULT_TITLE,
        "archived": bool(conversation.archived),
        "message_count": count,
        "preview": preview,
        "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
        "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
    }


def _owned(db, user: User, conversation_id: int) -> ChatConversation:
    conversation = (db.query(ChatConversation)
                    .filter(ChatConversation.id == conversation_id, ChatConversation.user_id == user.id).first())
    if conversation is None:
        raise ApiError(404, "对话不存在或已被删除")
    return conversation


def _auto_title(text: str) -> str:
    title = re.sub(r"\s+", " ", text).strip()
    return (title[:18] + "…") if len(title) > 18 else (title or DEFAULT_TITLE)


# ---------------------------------------------------------------- 会话 CRUD
@router.get("/ai/conversations", summary="我的 AI 对话列表（最近更新的在前）")
def list_conversations(user: CurrentUser, db: DB):
    items = (db.query(ChatConversation)
             .filter(ChatConversation.user_id == user.id, ChatConversation.archived.isnot(True))
             .order_by(ChatConversation.updated_at.desc(), ChatConversation.id.desc()).limit(MAX_CONVERSATIONS).all())
    return ok({"items": [conversation_to_dict(db, c) for c in items], "total": len(items)})


@router.post("/ai/conversations", summary="新建对话")
def create_conversation(payload: ConversationIn, user: CurrentUser, db: DB):
    conversation = ChatConversation(user_id=user.id, title=(payload.title or DEFAULT_TITLE)[:100])
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return ok(conversation_to_dict(db, conversation), "已新建对话")


@router.post("/ai/conversations/import", summary="迁移旧版保存在浏览器本地的对话（成为一条新的服务器对话）")
def import_conversation(payload: ConversationImportIn, user: CurrentUser, db: DB):
    conversation = ChatConversation(user_id=user.id, title=payload.title[:100])
    db.add(conversation)
    db.flush()
    for turn in payload.messages:
        if turn.content.strip():
            db.add(ChatMessage(conversation_id=conversation.id, user_id=user.id, role=turn.role,
                               content=turn.content.strip()[:4000],
                               meta=json.dumps({"legacy": True}, ensure_ascii=False)))
    db.commit()
    db.refresh(conversation)
    return ok(conversation_to_dict(db, conversation), "已迁移之前的对话")


@router.get("/ai/conversations/{conversation_id}", summary="对话详情")
def get_conversation(conversation_id: int, user: CurrentUser, db: DB):
    return ok(conversation_to_dict(db, _owned(db, user, conversation_id)))


@router.patch("/ai/conversations/{conversation_id}", summary="重命名 / 归档对话")
def update_conversation(conversation_id: int, payload: ConversationUpdateIn, user: CurrentUser, db: DB):
    conversation = _owned(db, user, conversation_id)
    if payload.title is not None:
        conversation.title = payload.title
    if payload.archived is not None:
        conversation.archived = payload.archived
    db.commit()
    db.refresh(conversation)
    return ok(conversation_to_dict(db, conversation), "已保存")


@router.delete("/ai/conversations/{conversation_id}", summary="删除对话（已导入的任务和课程不受影响）")
def delete_conversation(conversation_id: int, user: CurrentUser, db: DB):
    conversation = _owned(db, user, conversation_id)
    db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation.id).delete()
    db.delete(conversation)
    db.commit()
    return ok({"id": conversation_id}, "对话已删除")


@router.get("/ai/conversations/{conversation_id}/messages", summary="对话消息（最近 200 条）")
def list_messages(conversation_id: int, user: CurrentUser, db: DB):
    conversation = _owned(db, user, conversation_id)
    rows = (db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation.id, ChatMessage.user_id == user.id)
            .order_by(ChatMessage.id.desc()).limit(200).all())
    return ok({"conversation": conversation_to_dict(db, conversation),
               "items": [message_to_dict(m) for m in reversed(rows)]})


# ---------------------------------------------------------------- 对话
def _save_user_message(db, user: User, conversation: ChatConversation, text: str) -> ChatMessage:
    first = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation.id).count() == 0
    message = ChatMessage(conversation_id=conversation.id, user_id=user.id, role="user", content=text.strip())
    db.add(message)
    if first and (conversation.title or DEFAULT_TITLE) == DEFAULT_TITLE:
        conversation.title = _auto_title(text)
    conversation.updated_at = timeutil.now()
    db.commit()
    db.refresh(message)
    return message


def _save_assistant(db, user_id: int, conversation_id: int, state: agent.TurnState, interrupted: bool = False) -> ChatMessage:
    meta = state.meta()
    if interrupted:
        meta["interrupted"] = True
    content = state.content.strip()
    if not content and state.error:
        content = f"抱歉，{state.error}"
    message = ChatMessage(conversation_id=conversation_id, user_id=user_id, role="assistant", content=content,
                          meta=json.dumps(meta, ensure_ascii=False, default=str))
    db.add(message)
    conversation = db.get(ChatConversation, conversation_id)
    if conversation is not None:
        conversation.updated_at = timeutil.now()
        if state.memory:
            conversation.memory = json.dumps(state.memory, ensure_ascii=False)
    db.commit()
    db.refresh(message)
    return message


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _new_state(conversation: ChatConversation) -> agent.TurnState:
    state = agent.TurnState()
    state.memory = _load(conversation.memory)
    return state


@router.post("/ai/conversations/{conversation_id}/chat",
             summary="发送消息（SSE 流式）：status / reasoning / text / tool / proposal / error / done")
def chat_stream(conversation_id: int, payload: AgentChatIn, user: CurrentUser, db: DB):
    conversation = _owned(db, user, conversation_id)
    user_message = _save_user_message(db, user, conversation, payload.message)
    user_id, user_payload = user.id, message_to_dict(user_message)

    def events():
        # 流式响应在请求依赖关闭之后才开始迭代，这里用独立的数据库会话
        session = SessionLocal()
        state = None
        saved = False
        try:
            owner = session.get(User, user_id)
            conv = session.get(ChatConversation, conversation_id)
            state = _new_state(conv)
            yield _sse("status", {"text": "已收到"})
            for item in agent.run_turn(session, owner, conversation_id, state):
                yield _sse(item["event"], item["data"])
            reply = _save_assistant(session, user_id, conversation_id, state)
            saved = True
            yield _sse("done", {"message": message_to_dict(reply), "user_message": user_payload,
                                "conversation": conversation_to_dict(session, session.get(ChatConversation, conversation_id))})
        except GeneratorExit:
            # 客户端中途断开：保存已生成的部分
            if state is not None and not saved and (state.content or state.proposals):
                session.rollback()
                _save_assistant(session, user_id, conversation_id, state, interrupted=True)
            raise
        except Exception as error:  # noqa: BLE001
            logger.exception("AI 对话失败：%s", error)
            session.rollback()
            message = error.message if isinstance(error, ApiError) else "AI 服务暂时不可用，请稍后重试"
            yield _sse("error", {"message": message})
            if state is not None and not saved:
                state.error = state.error or message
                reply = _save_assistant(session, user_id, conversation_id, state)
                yield _sse("done", {"message": message_to_dict(reply), "user_message": user_payload,
                                    "conversation": None})
        finally:
            session.close()

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


@router.post("/ai/conversations/{conversation_id}/chat/sync", summary="发送消息（非流式兜底）：一次返回完整回复")
def chat_sync(conversation_id: int, payload: AgentChatIn, user: CurrentUser, db: DB):
    conversation = _owned(db, user, conversation_id)
    user_message = _save_user_message(db, user, conversation, payload.message)
    state = _new_state(conversation)
    events = []
    try:
        for item in agent.run_turn(db, user, conversation_id, state):
            if item["event"] in ("tool", "proposal", "error"):
                events.append(item)
    except Exception as error:  # noqa: BLE001
        logger.exception("AI 对话失败：%s", error)
        db.rollback()
        state.error = error.message if isinstance(error, ApiError) else "AI 服务暂时不可用，请稍后重试"
    reply = _save_assistant(db, user.id, conversation_id, state)
    return ok({"message": message_to_dict(reply), "user_message": message_to_dict(user_message),
               "conversation": conversation_to_dict(db, _owned(db, user, conversation_id)), "events": events})


# ---------------------------------------------------------------- 提案确认
@router.post("/ai/proposals/apply", summary="导入提案（用户编辑、勾选后的条目）：逐条应用，返回每条成功 / 失败原因")
def apply_proposal(payload: ProposalApplyIn, user: CurrentUser, db: DB):
    tracker = gamification.RewardTracker(db, user)
    outcome = agent.apply_proposal(db, user, payload.kind, payload.items, title=payload.title, goal=payload.goal,
                                   plan_id=payload.plan_id)
    results = outcome["results"]
    plan = outcome["plan"]
    agent.record_results(db, user, payload.message_id, payload.proposal_id, payload.items, results,
                         plan.id if plan is not None else payload.plan_id)
    reward = tracker.finish()
    db.commit()
    if plan is not None:
        db.refresh(plan)
    done = sum(1 for r in results if r["ok"])
    failed = len(results) - done
    unit = {"tasks": "个任务", "courses": "门课程", "changes": "处修改"}[payload.kind]
    if done and not failed:
        message = f"已导入 {done} {unit}"
    elif done:
        message = f"已导入 {done} {unit}，{failed} 条未导入"
    else:
        message = "全部未能导入，请查看每条的原因"
    return ok({"results": results, "ok_count": done, "fail_count": failed,
               "plan": plan_to_dict(plan) if plan is not None else None, "reward": reward}, message)
