"""
医生端派生总览辅助函数。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


CHRONIC_FIELD_LABELS = {
    "hypertension": "高血压",
    "diabetes": "糖尿病",
    "coronary_heart_disease": "冠心病",
    "stroke": "卒中/中风",
    "cancer": "肿瘤",
    "arthritis": "关节问题",
}

RISK_TAG_PATTERNS = {
    "fall": ["跌倒", "步态", "平衡", "起身", "如厕"],
    "disability": ["失能", "活动能力", "功能下降", "转移", "穿衣", "洗澡", "进食"],
    "cognitive": ["认知", "记忆", "重复提问", "定向", "计算"],
    "mood": ["抑郁", "情绪", "焦虑", "孤独", "睡眠"],
    "chronic": ["高血压", "糖尿病", "心脏", "卒中", "慢病"],
    "medication": ["用药", "药物", "服药", "依从性"],
    "social_support": ["独居", "照护", "支持", "陪护", "家属"],
}


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _extract_latest_payload(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not reports:
        return {}
    content = reports[0].get("content")
    return content if isinstance(content, dict) else {}


def _level_rank(level: str) -> int:
    mapping = {"unknown": -1, "low": 0, "medium": 1, "high": 2}
    return mapping.get(level, -1)


def _merge_level(current: str, candidate: str) -> str:
    return candidate if _level_rank(candidate) > _level_rank(current) else current


def _normalize_level(value: Any) -> str:
    text = _safe_text(value).lower()
    if "high" in text or "高" in text:
        return "high"
    if "medium" in text or "中" in text:
        return "medium"
    if "low" in text or "低" in text:
        return "low"
    return "unknown"


def _get_profile_text(profile: Dict[str, Any], *keys: str) -> str:
    values = [_safe_text(profile.get(key)) for key in keys]
    return " ".join([value for value in values if value])


def _list_text_items(value: Any) -> List[str]:
    return [str(item).strip() for item in _safe_list(value) if str(item).strip()]


def derive_chronic_conditions(profile: Dict[str, Any]) -> List[str]:
    conditions: List[str] = []
    for field, label in CHRONIC_FIELD_LABELS.items():
        value = _safe_text(profile.get(field))
        if value in {"是", "有", "阳性"}:
            conditions.append(label)
    return conditions


def derive_functional_status(profile: Dict[str, Any], latest_payload: Dict[str, Any]) -> Dict[str, Any]:
    badl_keys = [
        "badl_bathing",
        "badl_dressing",
        "badl_toileting",
        "badl_transferring",
        "badl_continence",
        "badl_eating",
    ]
    iadl_keys = [
        "iadl_visiting",
        "iadl_shopping",
        "iadl_cooking",
        "iadl_laundry",
        "iadl_walking",
        "iadl_carrying",
        "iadl_crouching",
        "iadl_transport",
    ]
    badl_deps = sum(1 for key in badl_keys if _safe_text(profile.get(key)) not in {"", "不需要帮助"})
    iadl_deps = sum(1 for key in iadl_keys if _safe_text(profile.get(key)) not in {"", "能自己做"})
    if badl_deps >= 3 or iadl_deps >= 5:
        level = "high"
    elif badl_deps >= 1 or iadl_deps >= 2:
        level = "medium"
    elif badl_deps == 0 and iadl_deps == 0 and any(_safe_text(profile.get(key)) for key in badl_keys + iadl_keys):
        level = "low"
    else:
        level = "unknown"

    report_data = latest_payload.get("report_data") if isinstance(latest_payload, dict) else {}
    portrait = report_data.get("healthPortrait") if isinstance(report_data, dict) else {}
    description = _safe_text((portrait or {}).get("functionalStatus")) or "暂无功能状态描述"
    if level == "unknown":
        lowered = description.lower()
        if any(token in description for token in ["部分协助", "需要协助", "活动能力下降", "功能下降"]) or "assist" in lowered:
            level = "medium"
        elif any(token in description for token in ["失能", "严重依赖", "重度"]) or "dependent" in lowered:
            level = "high"
        elif any(token in description for token in ["独立", "良好", "稳定"]) or "independent" in lowered:
            level = "low"
    return {
        "level": level,
        "description": description,
        "badl_dependency_count": badl_deps,
        "iadl_dependency_count": iadl_deps,
    }


def derive_current_risk_level(latest_payload: Dict[str, Any]) -> str:
    raw_results = latest_payload.get("raw_results") if isinstance(latest_payload, dict) else {}
    risk = raw_results.get("risk") if isinstance(raw_results, dict) else {}
    direct_level = _normalize_level((risk or {}).get("overall_risk_level"))
    if direct_level != "unknown":
        return direct_level

    report_data = latest_payload.get("report_data") if isinstance(latest_payload, dict) else {}
    risk_factors = report_data.get("riskFactors") if isinstance(report_data, dict) else {}
    level = "unknown"
    for item in _safe_list((risk_factors or {}).get("shortTerm")) + _safe_list((risk_factors or {}).get("midTerm")):
        if isinstance(item, dict):
            level = _merge_level(level, _normalize_level(item.get("level")))
    return level


def derive_main_problems(latest_payload: Dict[str, Any]) -> List[str]:
    report_data = latest_payload.get("report_data") if isinstance(latest_payload, dict) else {}
    portrait = report_data.get("healthPortrait") if isinstance(report_data, dict) else {}
    problems = [str(item).strip() for item in _safe_list((portrait or {}).get("problems")) if str(item).strip()]
    return problems[:5]


def derive_high_risk_reasons(latest_payload: Dict[str, Any]) -> List[str]:
    report_data = latest_payload.get("report_data") if isinstance(latest_payload, dict) else {}
    risk_factors = report_data.get("riskFactors") if isinstance(report_data, dict) else {}
    reasons: List[str] = []
    for item in _safe_list((risk_factors or {}).get("shortTerm")) + _safe_list((risk_factors or {}).get("midTerm")):
        if not isinstance(item, dict):
            continue
        if _normalize_level(item.get("level")) != "high":
            continue
        text = _safe_text(item.get("description")) or _safe_text(item.get("name"))
        if text and text not in reasons:
            reasons.append(text)
    return reasons[:3]


def derive_risk_tags(profile: Dict[str, Any], latest_payload: Dict[str, Any]) -> Dict[str, str]:
    tags = {key: "unknown" for key in RISK_TAG_PATTERNS}

    report_data = latest_payload.get("report_data") if isinstance(latest_payload, dict) else {}
    risk_factors = report_data.get("riskFactors") if isinstance(report_data, dict) else {}
    text_bucket: List[str] = []
    for item in _safe_list((risk_factors or {}).get("shortTerm")) + _safe_list((risk_factors or {}).get("midTerm")):
        if isinstance(item, dict):
            text_bucket.append(_safe_text(item.get("name")))
            text_bucket.append(_safe_text(item.get("description")))
    text_bucket.extend(derive_main_problems(latest_payload))
    joined_text = " ".join([item for item in text_bucket if item])

    for key, patterns in RISK_TAG_PATTERNS.items():
        for pattern in patterns:
            if pattern and pattern in joined_text:
                tags[key] = "medium"
                break

    if any(pattern in joined_text for pattern in RISK_TAG_PATTERNS["fall"]):
        tags["fall"] = _merge_level(tags["fall"], derive_current_risk_level(latest_payload))
    if any(pattern in joined_text for pattern in RISK_TAG_PATTERNS["cognitive"]):
        tags["cognitive"] = _merge_level(tags["cognitive"], derive_current_risk_level(latest_payload))
    if any(pattern in joined_text for pattern in RISK_TAG_PATTERNS["mood"]):
        tags["mood"] = _merge_level(tags["mood"], derive_current_risk_level(latest_payload))

    chronic_conditions = derive_chronic_conditions(profile)
    if len(chronic_conditions) >= 2:
        tags["chronic"] = "medium"
    elif chronic_conditions:
        tags["chronic"] = "low"

    if _safe_text(profile.get("living_arrangement")) == "独居" or not _safe_text(profile.get("caregiver")):
        tags["social_support"] = _merge_level(tags["social_support"], "medium")
    if _safe_text(profile.get("depression")) not in {"", "从不"} or _safe_text(profile.get("anxiety")) not in {"", "从不"}:
        tags["mood"] = _merge_level(tags["mood"], "medium")
    cognition_values = [_safe_text(profile.get("cognition_time")), _safe_text(profile.get("cognition_month")), _safe_text(profile.get("cognition_season")), _safe_text(profile.get("cognition_place"))]
    calc_values = [str(item).strip() for item in _safe_list(profile.get("cognition_calc")) if str(item).strip()]
    if any(value in {"错误", "不知道"} for value in cognition_values) or any(value in {"错误", "不知道"} for value in calc_values):
        tags["cognitive"] = _merge_level(tags["cognitive"], "medium")

    functional = derive_functional_status(profile, latest_payload)
    tags["disability"] = _merge_level(tags["disability"], functional["level"])
    return tags


def derive_recent_change(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    if len(reports) < 2:
        return {
            "status": "unknown",
            "summary": "暂无足够历史评估数据判断近 1 个月变化",
        }

    latest = _extract_latest_payload(reports[:1])
    previous = _extract_latest_payload(reports[1:2])
    latest_summary = _safe_text((latest.get("report_data") or {}).get("summary"))
    previous_summary = _safe_text((previous.get("report_data") or {}).get("summary"))
    latest_problems = derive_main_problems(latest)
    previous_problems = derive_main_problems(previous)
    if latest_summary != previous_summary or latest_problems != previous_problems:
        return {
            "status": "changed",
            "summary": "与上一次评估相比，风险摘要或主要问题发生变化",
        }

    return {
        "status": "stable",
        "summary": "与上一次评估相比暂无明显变化",
    }


def derive_recommended_actions(latest_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    report_data = _safe_dict(latest_payload.get("report_data"))
    recommendations = _safe_dict(report_data.get("recommendations"))
    priority_labels = {
        "priority1": "A",
        "priority2": "B",
        "priority3": "C",
    }
    actions: List[Dict[str, Any]] = []
    for key, priority in priority_labels.items():
        for item in _safe_list(recommendations.get(key)):
            if not isinstance(item, dict):
                continue
            title = _safe_text(item.get("title"))
            description = _safe_text(item.get("description"))
            if not title and not description:
                continue
            actions.append(
                {
                    "priority": priority,
                    "id": _safe_text(item.get("id")),
                    "title": title,
                    "category": _safe_text(item.get("category")),
                    "description": description,
                }
            )
    return actions[:6]


def derive_report_review(latest_payload: Dict[str, Any]) -> Dict[str, Any]:
    raw_results = _safe_dict(latest_payload.get("raw_results"))
    review = _safe_dict(raw_results.get("review"))
    consistency = _safe_dict(review.get("consistency_check"))
    safety = _safe_dict(review.get("safety_check"))
    executability = _safe_dict(review.get("executability_check"))
    completeness = _safe_dict(review.get("completeness_check"))

    consistency_issues = _list_text_items(consistency.get("issues"))
    summary = "暂无复核结果"
    if consistency.get("passed") is False and consistency_issues:
        summary = f"存在 {len(consistency_issues)} 条一致性提示"
    elif safety.get("urgent") is True:
        summary = "存在需要尽快处理的安全提示"
    elif review.get("approved") is True:
        summary = "报告复核通过"

    return {
        "summary": summary,
        "overall_quality": _safe_text(review.get("overall_quality")) or "unknown",
        "approved": review.get("approved") if isinstance(review.get("approved"), bool) else None,
        "consistency": {
            "passed": consistency.get("passed") if isinstance(consistency.get("passed"), bool) else None,
            "issues": consistency_issues,
        },
        "safety": {
            "urgent": safety.get("urgent") if isinstance(safety.get("urgent"), bool) else None,
            "urgent_reason": _safe_text(safety.get("urgent_reason")),
        },
        "executability": {
            "passed": executability.get("passed")
            if isinstance(executability.get("passed"), bool)
            else None,
            "issues": _list_text_items(executability.get("issues")),
        },
        "completeness": {
            "passed": completeness.get("passed")
            if isinstance(completeness.get("passed"), bool)
            else None,
            "missing": _list_text_items(completeness.get("missing")),
        },
        "suggestions": _list_text_items(review.get("suggestions")),
    }


def build_doctor_overview(
    elderly_id: str,
    profile: Dict[str, Any],
    reports: List[Dict[str, Any]],
    management: Dict[str, Any],
    latest_followup: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    latest_payload = _extract_latest_payload(reports)
    chronic_conditions = derive_chronic_conditions(profile)
    functional = derive_functional_status(profile, latest_payload)
    risk_level = derive_current_risk_level(latest_payload)
    main_problems = derive_main_problems(latest_payload)
    high_risk_reasons = derive_high_risk_reasons(latest_payload)
    report_data = latest_payload.get("report_data") if isinstance(latest_payload, dict) else {}

    return {
        "elderly_id": elderly_id,
        "age": profile.get("age"),
        "sex": profile.get("sex"),
        "residence": profile.get("residence"),
        "living_arrangement": profile.get("living_arrangement"),
        "marital_status": profile.get("marital_status"),
        "chronic_conditions": chronic_conditions,
        "chronic_summary": "、".join(chronic_conditions) if chronic_conditions else "暂无明确慢病记录",
        "current_risk_level": risk_level,
        "functional_status_level": functional["level"],
        "functional_status_text": functional["description"],
        "risk_tags": derive_risk_tags(profile, latest_payload),
        "recent_change": derive_recent_change(reports),
        "last_assessment_at": reports[0].get("created_at") if reports else None,
        "main_problems": main_problems,
        "high_risk_reasons": high_risk_reasons,
        "summary": _safe_text((report_data or {}).get("summary")) or "暂无报告总结",
        "recommended_actions": derive_recommended_actions(latest_payload),
        "latest_report_review": derive_report_review(latest_payload),
        "doctor_management": management,
        "latest_followup": latest_followup,
    }
