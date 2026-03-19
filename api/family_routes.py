"""
家属端 API 路由。
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request

from report_utils import list_reports_for_user
from security import (
    require_family_actor,
    require_family_elderly_access,
    require_family_session_access,
    require_state,
)


family_router = APIRouter(prefix="/family")


@family_router.post("/session/start/{elderly_id}")
async def start_family_session(request: Request, elderly_id: str):
    """为已绑定老人启动家属端评估会话。"""
    require_family_elderly_access(request, elderly_id)
    family_manager = require_state(request, "family_manager", "家属管理器未初始化")

    try:
        session_id = family_manager.new_family_session(elderly_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"启动会话失败: {exc}") from exc

    greeting = (
        "您好👋 感谢您来帮助我们更好地了解老人的情况。\n\n"
        "作为老人的家属，您对他/她的日常生活最了解。"
        "我会通过一些问题来收集您的观察和建议，"
        "这样我们就能为老人提供更贴心的照护建议。\n\n"
        "请按照您的真实情况回答，没有标准答案。"
        "如果有些问题记不清，也没关系，大概说一下就可以。"
    )

    return {
        "session_id": session_id,
        "elderly_id": elderly_id,
        "greeting": greeting,
        "state": "GREETING",
    }


@family_router.post("/session/{session_id}/message")
async def send_family_message(request: Request, session_id: str, message: Dict[str, str]):
    """发送家属消息。"""
    require_family_session_access(request, session_id)
    family_manager = require_state(request, "family_manager", "家属管理器未初始化")

    content = str(message.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="消息不能为空")

    try:
        return family_manager.chat(session_id, content)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"处理消息失败: {exc}") from exc


@family_router.get("/session/{session_id}/info")
async def get_family_session_info(request: Request, session_id: str):
    """获取家属会话信息。"""
    require_family_session_access(request, session_id)
    family_manager = require_state(request, "family_manager", "家属管理器未初始化")

    try:
        return family_manager.get_session_info(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取会话信息失败: {exc}") from exc


@family_router.get("/elderly-list")
async def get_elderly_list(request: Request):
    """获取当前家属已绑定的老人列表。"""
    actor = require_family_actor(request)
    auth_service = require_state(request, "auth_service", "认证服务未初始化")
    conversation_manager = require_state(request, "conversation_manager", "对话管理器未初始化")
    store = conversation_manager.store

    relations = auth_service.list_family_relations(actor.subject_id)
    if not relations:
        return {"data": []}

    try:
        conn = sqlite3.connect(store.db_path)
        conn.row_factory = sqlite3.Row
        elderly_list = []
        for relation in relations:
            elderly_id = relation["elderly_user_id"]
            row = conn.execute(
                "SELECT profile, created_at, updated_at FROM users WHERE user_id = ?",
                (elderly_id,),
            ).fetchone()
            if row is None:
                continue
            profile = json.loads(row["profile"]) if row["profile"] else {}
            elderly_list.append(
                {
                    "elderly_id": elderly_id,
                    "name": profile.get("name", "未命名"),
                    "relation": relation.get("relation") or "家庭成员",
                    "completion_rate": store.get_completion_rate(elderly_id),
                    "created_at": row["created_at"] or row["updated_at"] or datetime.now().isoformat(),
                }
            )
        conn.close()
        return {"data": elderly_list}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取列表失败: {exc}") from exc


@family_router.get("/elderly/{elderly_id}")
async def get_elderly_detail(request: Request, elderly_id: str):
    """获取已绑定老年人详细信息。"""
    require_family_elderly_access(request, elderly_id)
    conversation_manager = require_state(request, "conversation_manager", "对话管理器未初始化")
    profile = conversation_manager.store.get_profile(elderly_id)
    if not profile:
        raise HTTPException(status_code=404, detail="老年人不存在")

    return {
        "elderly_id": elderly_id,
        "profile": asdict(profile),
    }


@family_router.put("/elderly/{elderly_id}")
async def update_elderly_info(request: Request, elderly_id: str, updates: Dict[str, Any]):
    """更新已绑定老人的画像。"""
    require_family_elderly_access(request, elderly_id)
    conversation_manager = require_state(request, "conversation_manager", "对话管理器未初始化")
    workspace_manager = require_state(request, "workspace_manager", "工作区管理器未初始化")
    store = conversation_manager.store

    if not store.user_exists(elderly_id):
        raise HTTPException(status_code=404, detail="老年人不存在")

    try:
        store.update_profile(elderly_id, updates)
        latest_session = store.get_latest_session(elderly_id)
        if latest_session is not None:
            workspace_manager.save_user_profile(
                latest_session["session_id"],
                asdict(store.get_profile(elderly_id)),
            )
            workspace_manager.update_metadata(latest_session["session_id"], {"has_profile": True})
        return {"success": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"更新失败: {exc}") from exc


@family_router.get("/reports/{elderly_id}")
async def get_elderly_reports(request: Request, elderly_id: str):
    """获取当前家属可见的某位老人的所有报告。"""
    require_family_elderly_access(request, elderly_id)
    conversation_manager = require_state(request, "conversation_manager", "对话管理器未初始化")
    workspace_manager = require_state(request, "workspace_manager", "工作区管理器未初始化")

    if not conversation_manager.store.user_exists(elderly_id):
        raise HTTPException(status_code=404, detail="老年人不存在")

    try:
        return {"data": list_reports_for_user(workspace_manager, elderly_id)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取报告失败: {exc}") from exc
