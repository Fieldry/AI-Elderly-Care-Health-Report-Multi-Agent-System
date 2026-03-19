"""
老人本人视角的受保护接口。
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request

from report_utils import list_reports_for_user, load_report_payload, resolve_report_owner
from schemas import ReportData
from security import require_elderly_actor, require_state


elderly_router = APIRouter(prefix="/elderly")


@elderly_router.get("/me/profile")
async def get_my_profile(request: Request):
    """获取老人自己的画像。"""
    actor = require_elderly_actor(request)
    conversation_manager = require_state(request, "conversation_manager", "对话管理器未初始化")
    profile = conversation_manager.store.get_profile(actor.subject_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="未找到老人画像")
    return {
        "elderly_id": actor.subject_id,
        "profile": asdict(profile),
    }


@elderly_router.get("/me/reports")
async def list_my_reports(request: Request):
    """获取老人自己的报告列表。"""
    actor = require_elderly_actor(request)
    workspace_manager = require_state(request, "workspace_manager", "工作区管理器未初始化")
    return {"data": list_reports_for_user(workspace_manager, actor.subject_id)}


@elderly_router.get("/me/reports/{report_id}")
async def get_my_report(request: Request, report_id: str) -> ReportData:
    """获取老人自己的指定报告。"""
    actor = require_elderly_actor(request)
    workspace_manager = require_state(request, "workspace_manager", "工作区管理器未初始化")
    payload = load_report_payload(report_id, require_state(request, "reports_dir", "报告目录未初始化"), workspace_manager)
    if payload is None:
        raise HTTPException(status_code=404, detail="报告不存在")
    owner_id = resolve_report_owner(payload, workspace_manager)
    if owner_id != actor.subject_id:
        raise HTTPException(status_code=403, detail="无权访问该报告")
    report_data = payload.get("report_data")
    if not isinstance(report_data, dict):
        raise HTTPException(status_code=404, detail="报告不存在")
    return ReportData(**report_data)
