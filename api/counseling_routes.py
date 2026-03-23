"""
心理咨询（情感陪伴）路由。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from schemas import (
    CounselingMessageRequest,
    CounselingMessageResponse,
    CounselingSessionCreateResponse,
    CounselingSessionInfo,
)
from security import (
    require_authenticated_actor,
    require_elderly_actor,
    require_state,
)
from auth_service import DOCTOR_ROLE, ELDERLY_ROLE, FAMILY_ROLE

logger = logging.getLogger(__name__)

counseling_router = APIRouter(prefix="/counseling")


# ── 辅助函数 ─────────────────────────────────────────────


def _get_counseling_service(request: Request):
    return require_state(request, "counseling_service", "心理咨询服务未初始化")


def _require_session_owner(request: Request, session_id: str):
    """确认当前 elderly 用户拥有该咨询会话。"""
    actor = require_elderly_actor(request)
    service = _get_counseling_service(request)
    session = service.get_session(session_id)
    if session is None or session["user_id"] != actor.subject_id:
        raise HTTPException(status_code=404, detail="咨询会话不存在")
    return actor, session


def _can_view_counseling_sessions(request: Request, target_user_id: str) -> bool:
    """检查当前 actor 是否有权查看目标用户的咨询会话。"""
    actor = require_authenticated_actor(request)
    if actor.role == DOCTOR_ROLE:
        return True
    if actor.role == ELDERLY_ROLE:
        return actor.subject_id == target_user_id
    if actor.role == FAMILY_ROLE:
        auth_service = require_state(request, "auth_service", "认证服务未初始化")
        return auth_service.check_family_access(actor.subject_id, target_user_id)
    return False


# ── 端点 ─────────────────────────────────────────────────


@counseling_router.post("/sessions", response_model=CounselingSessionCreateResponse)
async def create_counseling_session(request: Request) -> CounselingSessionCreateResponse:
    """创建新的心理咨询会话。"""
    actor = require_elderly_actor(request)
    service = _get_counseling_service(request)
    result = service.create_session(actor.subject_id)
    return CounselingSessionCreateResponse(
        sessionId=result["session_id"],
        createdAt=result["created_at"],
    )


@counseling_router.post(
    "/sessions/{session_id}/message",
    response_model=CounselingMessageResponse,
)
async def send_counseling_message(
    request: Request,
    session_id: str,
    payload: CounselingMessageRequest,
) -> CounselingMessageResponse:
    """发送咨询消息（非流式）。"""
    _require_session_owner(request, session_id)
    service = _get_counseling_service(request)

    try:
        result = await asyncio.to_thread(service.send_message, session_id, payload.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return CounselingMessageResponse(
        messageId=result["message_id"],
        role=result["role"],
        content=result["content"],
        createdAt=result["created_at"],
    )


@counseling_router.get("/sessions/{session_id}/stream")
async def stream_counseling_message(
    request: Request,
    session_id: str,
    message: str,
):
    """SSE 流式咨询对话。"""
    _require_session_owner(request, session_id)
    service = _get_counseling_service(request)

    async def event_generator() -> AsyncGenerator[str, None]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def _produce():
            try:
                for chunk in service.send_message_stream(session_id, message):
                    loop.call_soon_threadsafe(
                        queue.put_nowait,
                        f"data: {json.dumps({'content': chunk})}\n\n",
                    )
                loop.call_soon_threadsafe(queue.put_nowait, "data: [DONE]\n\n")
            except Exception as exc:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    f"data: {json.dumps({'error': str(exc)})}\n\n",
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        asyncio.get_running_loop().run_in_executor(None, _produce)

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@counseling_router.get("/sessions/{session_id}/history")
async def get_counseling_history(request: Request, session_id: str):
    """获取咨询对话历史。"""
    actor = require_authenticated_actor(request)
    service = _get_counseling_service(request)
    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="咨询会话不存在")

    if not _can_view_counseling_sessions(request, session["user_id"]):
        raise HTTPException(status_code=403, detail="无权访问该咨询会话")

    history = service.get_session_history(session_id)
    return {"messages": history}


@counseling_router.get("/sessions", response_model=List[CounselingSessionInfo])
async def list_counseling_sessions(
    request: Request,
    userId: str | None = None,
):
    """列出咨询会话。elderly 只能看自己的，family 看绑定老人的，doctor 看全部。"""
    actor = require_authenticated_actor(request)
    service = _get_counseling_service(request)

    if actor.role == DOCTOR_ROLE:
        if userId:
            sessions = service.list_sessions(userId)
        else:
            sessions = service.list_all_sessions()
    elif actor.role == ELDERLY_ROLE:
        sessions = service.list_sessions(actor.subject_id)
    elif actor.role == FAMILY_ROLE:
        if userId:
            if not _can_view_counseling_sessions(request, userId):
                raise HTTPException(status_code=403, detail="无权访问该老年人数据")
            sessions = service.list_sessions(userId)
        else:
            auth_service = require_state(request, "auth_service", "认证服务未初始化")
            elderly_ids = auth_service.list_family_elderly_ids(actor.subject_id)
            sessions = []
            for eid in elderly_ids:
                sessions.extend(service.list_sessions(eid))
            sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    else:
        sessions = []

    return [
        CounselingSessionInfo(
            sessionId=s["session_id"],
            userId=s["user_id"],
            title=s["title"],
            status=s["status"],
            createdAt=s["created_at"],
            updatedAt=s["updated_at"],
        )
        for s in sessions
    ]


@counseling_router.post("/sessions/{session_id}/end")
async def end_counseling_session(request: Request, session_id: str):
    """结束咨询会话。"""
    _require_session_owner(request, session_id)
    service = _get_counseling_service(request)
    ok = service.end_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="咨询会话不存在")
    return {"success": True}
