from __future__ import annotations

import json
import re
from dataclasses import fields
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple

from multi_agent_system_v2 import UserProfile


BADL_MAP = {
    0: "不需要帮助",
    1: "需要别人搭把手",
    2: "大部分要靠别人帮忙",
    3: "大部分要靠别人帮忙",
}

IADL_MAP = {
    0: "能自己做",
    1: "做起来有点困难",
    2: "现在做不了",
    3: "现在做不了",
}

GENDER_MAP = {
    "male": "男",
    "female": "女",
}

RESIDENCE_MAP = {
    "city": "城市",
    "urban": "城市",
    "rural": "农村",
}

LIVING_MAP = {
    "alone": "独居",
    "with_spouse": "和老伴",
    "with_children": "和子女",
    "nursing_home": "住养老院",
}

LIFESTYLE_MAP = {
    "smoking": {
        "never": "从不",
        "former": "已戒",
        "current": "每天",
    },
    "drinking": {
        "never": "从不",
        "occasional": "偶尔",
        "regular": "每天",
    },
    "exercise": {
        "none": "从不",
        "occasional": "有时",
        "regular": "经常",
    },
    "sleep": {
        "good": "好",
        "fair": "一般",
        "poor": "差",
    },
}

MOOD_MAP = {
    "normal": "从不",
    "depression": "有时",
    "anxiety": "有时",
    "both": "经常",
}

COGNITION_MAP = {
    "normal": "正确",
    "mild_impairment": "错误",
    "moderate_impairment": "错误",
    "severe_impairment": "不知道",
}

VISION_HEARING_MAP = {
    "good": "好",
    "fair": "一般",
    "poor": "差",
}

CHRONIC_FIELDS = {
    "hypertension": "hypertension",
    "diabetes": "diabetes",
    "heart_disease": "coronary_heart_disease",
    "stroke": "stroke",
    "cancer": "cancer",
    "arthritis": "arthritis",
}


def _to_int(value: Any) -> Any:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        return value


def _to_float(value: Any) -> Any:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return value


def _map_score(value: Any, mapping: Dict[int, str]) -> Any:
    if value in (None, ""):
        return None
    try:
        score = int(value)
        return mapping.get(score, None)
    except Exception:
        text = str(value).strip()
        return text if text else None


def _get_by_path(obj: Dict[str, Any], path: Tuple[str, ...], default: Any = None) -> Any:
    current: Any = obj
    for part in path:
        if not isinstance(current, dict):
            return default
        current = current.get(part)
        if current is None:
            return default
    return current


def _as_backend_direct(raw: Dict[str, Any]) -> UserProfile:
    valid = {f.name for f in fields(UserProfile)}
    payload = {k: v for k, v in raw.items() if k in valid}
    return UserProfile(**payload)


def _from_frontend_profile(raw: Dict[str, Any]) -> UserProfile:
    demographics = raw.get("demographics", {})
    functional_status = raw.get("functionalStatus", {})
    badl = functional_status.get("badl", {})
    iadl = functional_status.get("iadl", {})
    health = raw.get("healthFactors", {})
    lifestyle = raw.get("lifestyle", {})
    support = raw.get("socialSupport", {})

    diseases = set(health.get("chronicDiseases") or [])

    return UserProfile(
        age=_to_int(demographics.get("age")),
        sex=GENDER_MAP.get(demographics.get("gender"), demographics.get("gender")),
        residence=RESIDENCE_MAP.get(str(demographics.get("livingStatus", "")).lower(), None),
        education_years=demographics.get("education") or None,
        marital_status=demographics.get("maritalStatus") or None,
        health_limitation=None,
        badl_bathing=_map_score(badl.get("bathing"), BADL_MAP),
        badl_dressing=_map_score(badl.get("dressing"), BADL_MAP),
        badl_toileting=_map_score(badl.get("toileting"), BADL_MAP),
        badl_transferring=_map_score(badl.get("transfer"), BADL_MAP),
        badl_continence=_map_score(badl.get("continence"), BADL_MAP),
        badl_eating=_map_score(badl.get("feeding"), BADL_MAP),
        iadl_visiting=_map_score(iadl.get("visiting"), IADL_MAP),
        iadl_shopping=_map_score(iadl.get("shopping"), IADL_MAP),
        iadl_cooking=_map_score(iadl.get("cooking"), IADL_MAP),
        iadl_laundry=_map_score(iadl.get("washing"), IADL_MAP),
        iadl_walking=_map_score(iadl.get("walking"), IADL_MAP),
        iadl_carrying=_map_score(iadl.get("lifting"), IADL_MAP),
        iadl_crouching=_map_score(iadl.get("crouching"), IADL_MAP),
        iadl_transport=_map_score(iadl.get("transport"), IADL_MAP),
        hypertension="是" if "hypertension" in diseases else "否",
        diabetes="是" if "diabetes" in diseases else "否",
        coronary_heart_disease="是" if "heart_disease" in diseases else "否",
        stroke="是" if "stroke" in diseases else "否",
        cataract="否",
        cancer="是" if "cancer" in diseases else "否",
        arthritis="是" if "arthritis" in diseases else "否",
        cognition_time=COGNITION_MAP.get(health.get("cognition"), None),
        cognition_month=COGNITION_MAP.get(health.get("cognition"), None),
        cognition_season=COGNITION_MAP.get(health.get("cognition"), None),
        cognition_place=COGNITION_MAP.get(health.get("cognition"), None),
        cognition_calc=None,
        depression=MOOD_MAP.get(health.get("mood"), None),
        anxiety=MOOD_MAP.get(health.get("mood"), None),
        loneliness=MOOD_MAP.get(health.get("mood"), None),
        smoking=LIFESTYLE_MAP["smoking"].get(lifestyle.get("smoking"), None),
        drinking=LIFESTYLE_MAP["drinking"].get(lifestyle.get("drinking"), None),
        exercise=LIFESTYLE_MAP["exercise"].get(lifestyle.get("exercise"), None),
        sleep_quality=LIFESTYLE_MAP["sleep"].get(lifestyle.get("sleep"), None),
        weight=None,
        height=None,
        vision=VISION_HEARING_MAP.get(health.get("vision"), None),
        hearing=VISION_HEARING_MAP.get(health.get("hearing"), None),
        living_arrangement=LIVING_MAP.get(demographics.get("livingStatus"), None),
        financial_status=None,
        medical_insurance=None,
        caregiver=support.get("primaryCaregiver") or None,
        user_type="elderly",
    )


def to_backend_profile(raw: Dict[str, Any]) -> UserProfile:
    if not isinstance(raw, dict):
        return UserProfile()

    if "demographics" in raw and "functionalStatus" in raw:
        return _from_frontend_profile(raw)

    return _as_backend_direct(raw)


def _severity_to_level(text: Any) -> str:
    value = str(text or "").lower()
    if "高" in value or "high" in value:
        return "high"
    if "低" in value or "low" in value:
        return "low"
    return "medium"


def _extract_summary_from_markdown(report_text: str) -> str:
    if not report_text:
        return ""
    section = _extract_markdown_section(report_text, r"1\.\s*健康报告总结")
    if not section:
        return ""
    content = section
    lines = [line.strip(" -*\t") for line in content.splitlines() if line.strip()]
    return " ".join(lines[:3]).strip()


def _extract_markdown_section(report_text: str, title_pattern: str) -> str:
    if not report_text:
        return ""
    section = re.search(rf"##\s*{title_pattern}\s*(.+?)(?=\n##\s|\n---\s*\n|\Z)", report_text, re.S)
    if not section:
        return ""
    return section.group(1).strip()


def _clean_markdown_text(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[*_`#>-]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip("：: ").strip()


def _normalize_markdown_lines(lines: List[str]) -> str:
    cleaned_lines: List[str] = []
    for raw_line in lines:
        line = str(raw_line or "").strip()
        if not line:
            continue
        line = re.sub(r"^\s*[*+-]\s*", "", line)
        line = re.sub(r"^\s*\d+[.)、]\s*", "", line)
        line = _clean_markdown_text(line)
        if line:
            cleaned_lines.append(line)
    return "；".join(cleaned_lines)


def _extract_warm_message_from_markdown(report_text: str) -> str:
    section = _extract_markdown_section(report_text, r"5\.\s*温馨寄语")
    if not section:
        return ""
    paragraphs = [_clean_markdown_text(line) for line in section.splitlines() if _clean_markdown_text(line)]
    return "\n".join(paragraphs).strip()


def _problem_to_text(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        problem = item.get("problem", "")
        impact = item.get("impact", "")
        if problem and impact:
            return f"{problem}: {impact}"
        return str(problem or impact or "")
    return str(item)


def _map_short_term_risks(risks: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for risk in risks or []:
        desc_parts = [risk.get("trigger"), risk.get("prevention_key")]
        description = "；".join([p for p in desc_parts if p]) or "暂无描述"
        items.append(
            {
                "name": risk.get("risk", "未命名风险"),
                "level": _severity_to_level(risk.get("severity")),
                "description": description,
                "timeframe": risk.get("timeframe", "1-4周"),
            }
        )
    return items


def _map_mid_term_risks(risks: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for risk in risks or []:
        desc_parts = [risk.get("chain"), risk.get("prevention_key")]
        description = "；".join([p for p in desc_parts if p]) or "暂无描述"
        items.append(
            {
                "name": risk.get("risk", "未命名风险"),
                "level": _severity_to_level(risk.get("severity")),
                "description": description,
                "timeframe": risk.get("timeframe", "1-6月"),
            }
        )
    return items


def _map_recommendation(action: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    action_id = str(action.get("action_id") or action.get("id") or "")
    title = action.get("title") or "未命名建议"
    description = "；".join(
        [
            str(action.get("subtitle") or "").strip(),
            str(action.get("completion_criteria") or "").strip(),
            str(reason or "").strip(),
        ]
    )
    description = "；".join([p for p in description.split("；") if p]) or "请按医护建议执行"

    return {
        "id": action_id or f"rec_{abs(hash(title)) % 100000}",
        "title": title,
        "description": description,
        "category": action.get("category", "健康管理"),
        "completed": False,
    }


def _parse_actions_from_payload(actions_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    action_list = actions_payload.get("actions") if isinstance(actions_payload, dict) else []
    if isinstance(action_list, list):
        return [item for item in action_list if isinstance(item, dict)]

    raw_payload = actions_payload.get("raw") if isinstance(actions_payload, dict) else ""
    if not isinstance(raw_payload, str) or not raw_payload.strip():
        return []

    candidate = raw_payload.strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", candidate, re.S)
        if not match:
            return []
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []

    parsed_actions = parsed.get("actions") if isinstance(parsed, dict) else []
    if not isinstance(parsed_actions, list):
        return []
    return [item for item in parsed_actions if isinstance(item, dict)]


def _extract_recommendations_from_markdown(report_text: str) -> Dict[str, List[Dict[str, Any]]]:
    recommendations = {
        "priority1": [],
        "priority2": [],
        "priority3": [],
    }
    section = _extract_markdown_section(report_text, r"4\.\s*健康建议")
    if not section:
        return recommendations

    priority_map = {
        "A": "priority1",
        "B": "priority2",
        "C": "priority3",
    }
    section_pattern = re.compile(r"###\s*([ABC])\.\s*([^\n]+)\n(.*?)(?=\n###\s*[ABC]\.\s*|\Z)", re.S)
    item_pattern = re.compile(r"\*\*\s*\d+[）\)]\s*(.+?)\s*\*\*\s*\n(.*?)(?=\n\*\*\s*\d+[）\)]|\Z)", re.S)

    for section_match in section_pattern.finditer(section):
        priority_code = section_match.group(1)
        priority_title = re.sub(r"（.*?）", "", section_match.group(2)).strip()
        body = section_match.group(3).strip()
        target_key = priority_map.get(priority_code)
        if not target_key:
            continue

        for index, item_match in enumerate(item_pattern.finditer(body), start=1):
            title = _clean_markdown_text(item_match.group(1))
            item_body = item_match.group(2).strip()
            current_label = ""
            current_lines: List[str] = []
            labelled_blocks: Dict[str, str] = {}
            loose_lines: List[str] = []

            def flush_current_block():
                nonlocal current_label, current_lines
                if not current_label:
                    return
                normalized = _normalize_markdown_lines(current_lines)
                if normalized:
                    labelled_blocks[current_label] = normalized
                current_label = ""
                current_lines = []

            for raw_line in item_body.splitlines():
                line = str(raw_line or "").strip()
                if not line:
                    continue
                line_no_prefix = re.sub(r"^\s*[*+-]\s*", "", line).strip()
                label_match = re.match(r"\*\*(怎么做|完成标准)\*\*[:：]?\s*(.*)$", line_no_prefix)
                if label_match:
                    flush_current_block()
                    current_label = label_match.group(1)
                    current_lines = [label_match.group(2)] if label_match.group(2).strip() else []
                    continue

                if current_label:
                    current_lines.append(line_no_prefix)
                else:
                    loose_lines.append(line_no_prefix)

            flush_current_block()

            description_parts: List[str] = []
            how_to_do = labelled_blocks.get("怎么做")
            completion = labelled_blocks.get("完成标准")
            if how_to_do:
                description_parts.append(f"怎么做：{how_to_do}")
            if completion:
                description_parts.append(f"完成标准：{completion}")
            if not description_parts:
                normalized_loose = _normalize_markdown_lines(loose_lines)
                if normalized_loose:
                    description_parts.append(normalized_loose)

            recommendations[target_key].append(
                {
                    "id": f"{priority_code}{index}",
                    "title": title or f"{priority_title}{index}",
                    "description": "；".join(description_parts) or "请按计划逐步落实。",
                    "category": priority_title or "健康建议",
                    "completed": False,
                }
            )

    return recommendations


def _map_recommendations(results: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    report_text = str(results.get("report") or "")
    markdown_recommendations = _extract_recommendations_from_markdown(report_text)
    if any(markdown_recommendations.values()):
        return markdown_recommendations

    actions_payload = results.get("actions") if isinstance(results.get("actions"), dict) else {}
    action_list = _parse_actions_from_payload(actions_payload)

    action_by_id = {
        str(item.get("action_id")): item
        for item in action_list
        if isinstance(item, dict) and item.get("action_id")
    }

    priority_payload = results.get("priority") if isinstance(results.get("priority"), dict) else {}

    def _collect(priority_key: str) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []
        for item in priority_payload.get(priority_key, []) or []:
            if not isinstance(item, dict):
                continue
            action = action_by_id.get(str(item.get("action_id")))
            if action:
                output.append(_map_recommendation(action, reason=str(item.get("reason") or "")))
        return output

    p1 = _collect("priority_a")
    p2 = _collect("priority_b")
    p3 = _collect("priority_c")

    used_ids = {
        str(item.get("id") or "")
        for group in (p1, p2, p3)
        for item in group
        if isinstance(item, dict)
    }
    remaining_actions = [
        action for action in action_list if str(action.get("action_id") or action.get("id") or "") not in used_ids
    ]
    for action in remaining_actions:
        mapped = _map_recommendation(action)
        if len(p1) < 3:
            p1.append(mapped)
        elif len(p2) < 4:
            p2.append(mapped)
        else:
            p3.append(mapped)

    return {
        "priority1": p1,
        "priority2": p2,
        "priority3": p3,
    }


def to_frontend_report_data(results: Dict[str, Any], generated_at: str | None = None) -> Dict[str, Any]:
    status = results.get("status") if isinstance(results.get("status"), dict) else {}
    risk = results.get("risk") if isinstance(results.get("risk"), dict) else {}
    factors = results.get("factors") if isinstance(results.get("factors"), dict) else {}
    report_text = str(results.get("report") or "")

    summary = _extract_summary_from_markdown(report_text)
    if not summary:
        summary = "；".join(
            [
                str(status.get("status_description") or ""),
                str(risk.get("risk_summary") or ""),
            ]
        )
        summary = "；".join([p for p in summary.split("；") if p]) or "已生成健康评估与照护行动计划。"

    health_portrait = {
        "functionalStatus": str(
            _get_by_path(factors, ("functional_status", "description"), "")
            or status.get("status_description")
            or "暂无功能状态描述"
        ),
        "strengths": factors.get("strengths") if isinstance(factors.get("strengths"), list) else [],
        "problems": [
            _problem_to_text(item)
            for item in (factors.get("main_problems") if isinstance(factors.get("main_problems"), list) else [])
            if _problem_to_text(item)
        ],
    }

    short_term = _map_short_term_risks(risk.get("short_term_risks") if isinstance(risk, dict) else [])
    mid_term = _map_mid_term_risks(risk.get("medium_term_risks") if isinstance(risk, dict) else [])

    return {
        "summary": summary,
        "healthPortrait": health_portrait,
        "riskFactors": {
            "shortTerm": short_term,
            "midTerm": mid_term,
        },
        "recommendations": _map_recommendations(results),
        "warmMessage": _extract_warm_message_from_markdown(report_text),
        "generatedAt": generated_at or datetime.now().isoformat(),
    }
