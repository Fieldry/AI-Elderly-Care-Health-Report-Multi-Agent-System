"""
报告生成与存储辅助函数。
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from multi_agent_system_v2 import UserProfile


def profile_to_dict(profile: UserProfile) -> Dict[str, Any]:
    """将 UserProfile 转为可持久化字典。"""
    payload = asdict(profile)
    payload.pop("user_type", None)
    return payload


def save_report_bundle(
    reports_dir: Path,
    workspace_manager,
    profile: Dict[str, Any],
    results: Dict[str, Any],
    report_data: Dict[str, Any],
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    保存报告到传统目录与工作区，返回完整 JSON 载荷。
    """
    timestamp = datetime.now()
    report_id = timestamp.strftime("%Y%m%d_%H%M%S_%f")

    age = profile.get("age", "未知")
    sex = profile.get("sex", "未知")

    date_dir = reports_dir / timestamp.strftime("%Y%m")
    date_dir.mkdir(parents=True, exist_ok=True)

    base_filename = f"report_{report_id}_{age}岁{sex}"
    payload = {
        "report_id": report_id,
        "session_id": session_id,
        "user_id": user_id,
        "generated_at": timestamp.isoformat(),
        "profile": profile,
        "raw_results": results,
        "report_data": report_data,
    }

    json_file = date_dir / f"{base_filename}.json"
    with open(json_file, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)

    markdown_file = date_dir / f"{base_filename}.md"
    markdown_content = generate_markdown_report(profile, results, report_data, timestamp)
    with open(markdown_file, "w", encoding="utf-8") as file_obj:
        file_obj.write(markdown_content)

    if session_id and workspace_manager is not None:
        workspace_manager.save_report(session_id, payload, "json")
        workspace_manager.save_report(session_id, markdown_content, "md")
        workspace_manager.update_metadata(session_id, {"has_report": True})

    return payload


def generate_markdown_report(
    profile: Dict[str, Any],
    results: Dict[str, Any],
    report_data: Dict[str, Any],
    timestamp: datetime,
) -> str:
    """生成 Markdown 格式的健康报告。"""
    status = results.get("status", {})
    risk = results.get("risk", {})
    raw_report = results.get("report", "")

    md_lines = [
        "# 养老健康评估报告",
        "",
        "## 报告信息",
        "",
        f"- **生成时间**: {timestamp.strftime('%Y年%m月%d日 %H:%M')}",
        f"- **年龄**: {profile.get('age', '未知')}岁",
        f"- **性别**: {profile.get('sex', '未知')}",
        "",
        "## 1. 健康报告总结",
        "",
    ]

    if raw_report:
        summary_match = re.search(r"##\s*1\.\s*健康报告总结\s*(.+?)(?:\n##\s|\Z)", raw_report, re.S)
        if summary_match:
            md_lines.append(summary_match.group(1).strip())
        else:
            md_lines.append(report_data.get("summary", "暂无总结"))
    else:
        md_lines.append(report_data.get("summary", "暂无总结"))
    md_lines.append("")

    md_lines.extend(
        [
            "## 2. 功能状态评估",
            "",
            f"**状态描述**: {status.get('status_description', '无')}",
            "",
        ]
    )

    health_portrait = report_data.get("healthPortrait", {})
    if health_portrait:
        md_lines.extend(
            [
                "### 健康画像",
                "",
                f"**功能状态**: {health_portrait.get('functionalStatus', '无描述')}",
                "",
            ]
        )

        strengths = health_portrait.get("strengths", [])
        if strengths:
            md_lines.append("**优势**:")
            md_lines.extend([f"- {item}" for item in strengths])
            md_lines.append("")

        problems = health_portrait.get("problems", [])
        if problems:
            md_lines.append("**需要关注的问题**:")
            md_lines.extend([f"- {item}" for item in problems])
            md_lines.append("")

    md_lines.extend(["## 3. 风险预测分析", ""])
    risk_factors = report_data.get("riskFactors", {})
    for label, items in [("短期风险（1-4周）", risk_factors.get("shortTerm", [])), ("中期风险（1-6月）", risk_factors.get("midTerm", []))]:
        if not items:
            continue
        md_lines.extend([f"### {label}", ""])
        for item in items:
            md_lines.extend(
                [
                    f"#### {item['name']}",
                    f"- **风险等级**: {item['level']}",
                    f"- **时间范围**: {item['timeframe']}",
                    f"- **描述**: {item['description']}",
                    "",
                ]
            )

    if risk:
        md_lines.extend(
            [
                "**风险总结**:",
                f"- 短期风险数: {len(risk_factors.get('shortTerm', []))}项",
                f"- 中期风险数: {len(risk_factors.get('midTerm', []))}项",
                f"- 风险概况: {risk.get('risk_summary', '无')}",
                "",
            ]
        )

    md_lines.extend(["## 4. 行动建议", ""])
    recommendations = report_data.get("recommendations", {})
    for section_title, items in [
        ("优先级 A - 立即执行", recommendations.get("priority1", [])),
        ("优先级 B - 本周完成", recommendations.get("priority2", [])),
        ("优先级 C - 后续跟进", recommendations.get("priority3", [])),
    ]:
        if not items:
            continue
        md_lines.extend([f"### {section_title}", ""])
        for item in items:
            md_lines.extend(
                [
                    f"#### {item['title']}",
                    f"- **类别**: {item['category']}",
                    f"- **描述**: {item['description']}",
                    "",
                ]
            )

    if raw_report:
        md_lines.extend(["## 5. 完整评估报告", "", raw_report, ""])

    md_lines.extend(
        [
            "---",
            "",
            "*本报告由 AI 养老健康助手自动生成，仅供参考。请结合专业医生的诊断和建议。*",
        ]
    )
    return "\n".join(md_lines)


def build_report_list_item(payload: Dict[str, Any], fallback_id: str) -> Dict[str, Any]:
    """构造列表场景使用的报告摘要对象。"""
    report_data = payload.get("report_data") if isinstance(payload, dict) else {}
    title = "健康评估报告"
    if isinstance(report_data, dict):
        title = report_data.get("summary") or title

    return {
        "id": payload.get("report_id", fallback_id),
        "title": title,
        "created_at": payload.get("generated_at") or "",
        "content": payload,
    }


def list_reports_for_user(workspace_manager, user_id: str) -> List[Dict[str, Any]]:
    """按用户归属聚合工作区中的报告。"""
    reports: List[Dict[str, Any]] = []
    for metadata in workspace_manager.find_sessions_by_user(user_id):
        session_id = metadata.get("session_id")
        if not session_id:
            continue

        for report_file in workspace_manager.get_report_files(session_id):
            with open(report_file, "r", encoding="utf-8") as file_obj:
                payload = json.load(file_obj)

            item = build_report_list_item(payload, report_file.stem)
            if not item["created_at"]:
                item["created_at"] = datetime.fromtimestamp(report_file.stat().st_mtime).isoformat()
            reports.append(item)

    reports.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return reports


def load_report_payload(
    report_id: str,
    reports_dir: Path,
    workspace_manager=None,
) -> Optional[Dict[str, Any]]:
    """根据 report_id 从传统目录和工作区查找报告。"""
    for report_file in reports_dir.rglob("*.json"):
        with open(report_file, "r", encoding="utf-8") as file_obj:
            payload = json.load(file_obj)
        if payload.get("report_id") == report_id:
            return payload

    if workspace_manager is None:
        return None

    for session_id in workspace_manager.list_sessions():
        for report_file in workspace_manager.get_report_files(session_id):
            with open(report_file, "r", encoding="utf-8") as file_obj:
                payload = json.load(file_obj)
            if payload.get("report_id") == report_id:
                return payload
    return None


def resolve_report_owner(payload: Dict[str, Any], workspace_manager=None) -> Optional[str]:
    """从报告 payload 或工作区元数据反查报告所属老年人。"""
    if not isinstance(payload, dict):
        return None

    user_id = payload.get("user_id")
    if user_id:
        return str(user_id)

    session_id = payload.get("session_id")
    if not session_id or workspace_manager is None:
        return None

    metadata = workspace_manager.get_session_metadata(str(session_id))
    owner_id = metadata.get("user_id") if metadata else None
    return str(owner_id) if owner_id else None
