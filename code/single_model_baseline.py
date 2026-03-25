"""
单模型基线生成模块。

目标：
1. 从现有多 Agent system prompt 中移除角色扮演前缀；
2. 组合为一个单模型总 prompt；
3. 在共享输入条件下生成与多 Agent 类似的最终报告；
4. 输出基础对比摘要，便于比较两类报告差异。
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from multi_agent_system_v2 import (
    ActionPlanAgentV3,
    BaseAgent,
    FactorAgentV3,
    PriorityAgentV3,
    ReportAgentV2,
    ReviewAgentV3,
    RiskAgentV3,
    StatusAgentV3,
    UserProfile,
)


@dataclass(frozen=True)
class StagePrompt:
    key: str
    label: str
    source_agent: str
    original_prompt: str
    stripped_prompt: str


STAGE_AGENT_SPECS: Sequence[Tuple[str, str, type]] = (
    ("status", "Stage 1: 状态判定", StatusAgentV3),
    ("risk", "Stage 2: 风险预测", RiskAgentV3),
    ("factors", "Stage 3: 因素分析", FactorAgentV3),
    ("actions", "Stage 4: 行动计划", ActionPlanAgentV3),
    ("priority", "Stage 5: 优先级排序", PriorityAgentV3),
    ("review", "Stage 6: 反思校验", ReviewAgentV3),
    ("report", "Stage 7: 报告生成", ReportAgentV2),
)


REPORT_SECTION_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "report_notice": ("## 0. 报告说明", "报告说明"),
    "summary": ("## 1. 健康报告总结", "健康报告总结"),
    "portrait": ("## 2. 您的健康画像", "健康画像"),
    "risk": ("## 3. 风险因素", "风险因素"),
    "actions": ("## 4. 健康建议", "健康建议"),
    "closing": ("## 5. 温馨寄语", "温馨寄语"),
}


ROLE_PREFIX_PATTERNS = (
    re.compile(r"^你是[^，。！？\n]+[，,]\s*"),
    re.compile(r"^你是[^。！？\n]+[。！？]\s*"),
)


def strip_role_playing(prompt: str) -> str:
    """移除 prompt 首行中的角色扮演前缀，尽量保留原意。"""
    lines = prompt.splitlines()
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not stripped:
            continue

        updated = stripped
        for pattern in ROLE_PREFIX_PATTERNS:
            if pattern.match(updated):
                updated = pattern.sub("", updated, count=1).lstrip()
                break

        if updated != stripped:
            indent = line[: len(line) - len(stripped)]
            lines[index] = f"{indent}{updated}"
        break

    return "\n".join(lines).strip()


def collect_stage_prompts() -> List[StagePrompt]:
    """从多 Agent 定义中提取各阶段 prompt，并移除角色扮演前缀。"""
    stage_prompts: List[StagePrompt] = []
    for key, label, factory in STAGE_AGENT_SPECS:
        agent = factory()
        original_prompt = agent.system_prompt.strip()
        stage_prompts.append(
            StagePrompt(
                key=key,
                label=label,
                source_agent=agent.name,
                original_prompt=original_prompt,
                stripped_prompt=strip_role_playing(original_prompt),
            )
        )
    return stage_prompts


def build_single_model_system_prompt(stage_prompts: Optional[Sequence[StagePrompt]] = None) -> str:
    """组合单模型基线的总 system prompt。"""
    prompts = list(stage_prompts or collect_stage_prompts())
    stage_blocks = [
        f"【{stage.label}｜来源 {stage.source_agent}】\n{stage.stripped_prompt}"
        for stage in prompts
    ]
    preamble = """你将一次性完成原多 Agent 报告流程，但不进行角色扮演。

请严格遵守以下总要求：
1. 内部按 Stage 1 到 Stage 7 的顺序完成分析、规划、排序、复核与成文。
2. 尽量保持原多 Agent prompt 的判断标准、字段约束、输出结构和语言风格不变。
3. 不要输出中间 JSON、不要展示中间推理过程、不要自称某个专家或 Agent。
4. 如不同阶段要求存在冲突，以“严格依据输入事实、不编造、保证安全、保证可执行、最终报告可读”为最高优先级。
5. 最终只输出一份 Markdown 格式的《健康评估与照护行动计划》正文。"""
    return "\n\n".join([preamble, *stage_blocks])


def _build_bmi_text(profile: UserProfile) -> str:
    if not profile.weight or not profile.height:
        return "BMI: 暂无法计算"

    try:
        weight = float(profile.weight)
        height = float(profile.height) / 100
        bmi = weight / (height ** 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return "BMI: 暂无法计算"

    if bmi < 18.5:
        label = "偏瘦，营养不足风险"
    elif bmi < 24:
        label = "正常"
    elif bmi < 28:
        label = "超重"
    else:
        label = "肥胖"
    return f"BMI: {bmi:.1f}（{label}）"


def build_single_model_user_prompt(
    profile: UserProfile,
    knowledge_context: str = "",
) -> str:
    """构造单模型基线的 user prompt。"""
    profile_dict = asdict(profile)
    thematic_context = f"""
【基本信息】
- 年龄: {profile.age}岁
- 性别: {profile.sex}
- 居住地: {profile.residence}
- 教育年限: {profile.education_years}年
- 婚姻状况: {profile.marital_status}
- 用户类型: {profile.user_type}

【健康限制】
- 过去6个月是否因健康问题限制了活动: {profile.health_limitation}

【BADL（基本日常生活活动）】
- 洗澡: {profile.badl_bathing}
- 穿衣: {profile.badl_dressing}
- 上厕所: {profile.badl_toileting}
- 室内活动: {profile.badl_transferring}
- 大小便控制: {profile.badl_continence}
- 吃饭: {profile.badl_eating}

【IADL（工具性日常生活活动）】
- 串门: {profile.iadl_visiting}
- 购物: {profile.iadl_shopping}
- 做饭: {profile.iadl_cooking}
- 洗衣: {profile.iadl_laundry}
- 步行1km: {profile.iadl_walking}
- 提重物: {profile.iadl_carrying}
- 蹲起: {profile.iadl_crouching}
- 公共交通: {profile.iadl_transport}

【慢性病情况】
- 慢性病总问: {profile.chronic_disease_any}
- 心脑血管: 高血压={profile.hypertension}, 冠心病={profile.coronary_heart_disease}, 心衰={profile.heart_failure}, 心律失常={profile.arrhythmia}, 中风/脑血管病={profile.stroke}
- 代谢内分泌: 糖尿病={profile.diabetes}, 高血脂={profile.hyperlipidemia}, 甲状腺病={profile.thyroid_disease}
- 呼吸: 慢性肺病={profile.chronic_lung_disease}, 肺结核={profile.tuberculosis}
- 消化肝胆肾: 溃疡={profile.peptic_ulcer}, 胆囊炎/结石={profile.cholecystitis_gallstones}, 慢性肾病={profile.chronic_kidney_disease}, 肝炎={profile.hepatitis}, 慢性肝病={profile.chronic_liver_disease}
- 感官: 白内障={profile.cataract}, 青光眼={profile.glaucoma}, 听力障碍(诊断)={profile.hearing_impairment}
- 神经认知: 帕金森={profile.parkinsons_disease}, 痴呆/AD={profile.dementia}, 癫痫={profile.epilepsy}
- 骨关节: 关节炎={profile.arthritis}, 风湿/类风湿={profile.rheumatism_rheumatoid}, 骨质疏松={profile.osteoporosis}
- 其他: 褥疮={profile.pressure_ulcer}, 癌症={profile.cancer}(类型:{profile.cancer_type}), 衰弱={profile.frailty}, 跌倒史={profile.fall_history}, 失能={profile.disability}, 营养不良={profile.malnutrition}, 其他慢病补充={profile.other_chronic_note}
- 性别相关: 前列腺={profile.prostate_disease}, 乳腺={profile.breast_disease}, 子宫肌瘤={profile.uterine_fibroids}

【认知功能】
- 时间定向: {profile.cognition_time}
- 月份定向: {profile.cognition_month}
- 季节定向: {profile.cognition_season}
- 地点定向: {profile.cognition_place}
- 计算能力: {profile.cognition_calc}

【心理状态】
- 抑郁感: {profile.depression}
- 焦虑感: {profile.anxiety}
- 孤独感: {profile.loneliness}

【生活方式】
- 吸烟: {profile.smoking}
- 饮酒: {profile.drinking}
- 锻炼: {profile.exercise}
- 睡眠质量: {profile.sleep_quality}

【生理指标】
- 体重: {profile.weight}kg
- 身高: {profile.height}cm
- {_build_bmi_text(profile)}
- 视力: {profile.vision}
- 听力: {profile.hearing}
- 腰围: {profile.waist_circumference}cm
- 臀围: {profile.hip_circumference}cm

【社会支持】
- 居住安排: {profile.living_arrangement}
- 经济状况: {profile.financial_status}
- 医保: {profile.medical_insurance}
- 照护者: {profile.caregiver}
""".strip()

    user_prompt = f"""请基于以下老人信息，一次性完成原多 Agent 流程，并直接输出最终报告。

【执行要求】
- 内部按 Stage 1 到 Stage 7 的规则完成状态判定、风险预测、健康画像、行动计划、优先级排序、结果复核和最终成文。
- 尽量保留原多 Agent prompt 的语义与约束，不要重新发明评估框架。
- 严格依据输入与知识库参考，不要编造用户未提供的事实。
- 最终只输出 Markdown 报告正文，不要输出中间 JSON、分析过程、标题外说明。

【按主题整理的老人信息】
{thematic_context}

【结构化画像 JSON】
{json.dumps(profile_dict, ensure_ascii=False, indent=2)}
"""

    if knowledge_context:
        user_prompt += f"""

【知识库参考】
以下内容与多智能体版本使用同一批检索结果，用于尽量保持对比条件一致。仅在与当前老人情况一致时吸收使用，不要逐字照抄，也不要生成与个体情况矛盾的建议。

{knowledge_context}
"""

    user_prompt += "\n\n请直接输出最终 Markdown 报告。"
    return user_prompt


def resolve_knowledge_context(knowledge: Optional[Dict[str, Any]]) -> str:
    """优先使用综合检索产物中的 combined_context。"""
    if not knowledge:
        return ""
    for key in ("combined_context", "context"):
        value = str(knowledge.get(key) or "").strip()
        if value:
            return value
    return ""


class SingleModelBaselineAgent(BaseAgent):
    """单模型基线 Agent。"""

    def __init__(self, system_prompt: Optional[str] = None):
        super().__init__(
            name="SingleModelBaselineAgent",
            system_prompt=system_prompt or build_single_model_system_prompt(),
        )

    def generate_report(
        self,
        profile: UserProfile,
        knowledge_context: str = "",
    ) -> Dict[str, Any]:
        user_prompt = build_single_model_user_prompt(profile, knowledge_context=knowledge_context)
        report = self.call_llm(user_prompt=user_prompt, temperature=0.5, max_tokens=8192)
        return {
            "mode": "single_model_baseline",
            "report": report,
            "prompt_artifacts": {
                "system_prompt": self.system_prompt,
                "user_prompt": user_prompt,
                "stage_prompts": [stage.__dict__ for stage in collect_stage_prompts()],
            },
        }


def run_single_model_baseline(
    profile: UserProfile,
    knowledge: Optional[Dict[str, Any]] = None,
    system_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """运行单模型基线并返回可保存的结果字典。"""
    knowledge_payload = knowledge or {
        "enabled": False,
        "combined_context": "",
        "total_hits": 0,
        "retrieval_mode": "disabled",
    }
    generator = SingleModelBaselineAgent(system_prompt=system_prompt)
    result = generator.generate_report(
        profile=profile,
        knowledge_context=resolve_knowledge_context(knowledge_payload),
    )
    result["knowledge"] = knowledge_payload
    return result


def build_user_id(profile: UserProfile, row_index: Optional[int] = None, timestamp: Optional[str] = None) -> str:
    """构建稳定的输出标识。"""
    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    if row_index is not None:
        return f"row{row_index}_{profile.age}岁{profile.sex}_{stamp}"
    return f"{profile.age}岁{profile.sex}_{stamp}"


def save_single_model_results(
    results: Dict[str, Any],
    profile: UserProfile,
    output_dir: str,
    row_index: Optional[int] = None,
    user_id: Optional[str] = None,
) -> Dict[str, str]:
    """保存单模型报告、JSON 结果和 prompt 文件。"""
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    resolved_user_id = user_id or build_user_id(profile, row_index=row_index)

    json_path = target_dir / f"single_model_result_{resolved_user_id}.json"
    report_path = target_dir / f"single_model_report_{resolved_user_id}.md"
    prompt_path = target_dir / f"single_model_prompt_{resolved_user_id}.md"

    payload = dict(results)
    payload["profile"] = asdict(profile)
    if row_index is not None:
        payload["row_index"] = row_index

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    with open(report_path, "w", encoding="utf-8") as file:
        if row_index is not None:
            file.write(f"<!-- 数据来源：第{row_index}行 -->\n\n")
        file.write(results.get("report", ""))

    prompt_artifacts = results.get("prompt_artifacts", {})
    with open(prompt_path, "w", encoding="utf-8") as file:
        file.write("# Single Model Combined Prompt\n\n")
        file.write("## System Prompt\n\n")
        file.write(prompt_artifacts.get("system_prompt", ""))
        file.write("\n\n## User Prompt\n\n")
        file.write(prompt_artifacts.get("user_prompt", ""))

    return {
        "json_path": str(json_path),
        "report_path": str(report_path),
        "prompt_path": str(prompt_path),
    }


def extract_markdown_headings(text: str) -> List[str]:
    """提取 Markdown 标题。"""
    return [match.group(1).strip() for match in re.finditer(r"^\s{0,3}#+\s+(.+?)\s*$", text, re.M)]


def summarize_report_structure(report_text: str) -> Dict[str, Any]:
    """生成报告结构摘要。"""
    headings = extract_markdown_headings(report_text)
    section_presence = {
        name: any(keyword in report_text for keyword in keywords)
        for name, keywords in REPORT_SECTION_KEYWORDS.items()
    }
    return {
        "char_count": len(report_text),
        "line_count": len(report_text.splitlines()),
        "headings": headings,
        "section_presence": section_presence,
    }


def build_report_comparison(multi_agent_report: str, single_model_report: str) -> Dict[str, Any]:
    """输出简洁的文本层面对比摘要。"""
    multi_summary = summarize_report_structure(multi_agent_report)
    single_summary = summarize_report_structure(single_model_report)

    multi_headings = set(multi_summary["headings"])
    single_headings = set(single_summary["headings"])
    diff_lines = list(
        difflib.unified_diff(
            multi_agent_report.splitlines(),
            single_model_report.splitlines(),
            fromfile="multi_agent_report.md",
            tofile="single_model_report.md",
            lineterm="",
        )
    )

    return {
        "similarity_ratio": round(
            difflib.SequenceMatcher(a=multi_agent_report, b=single_model_report).ratio(),
            4,
        ),
        "multi_agent": multi_summary,
        "single_model": single_summary,
        "shared_headings": sorted(multi_headings & single_headings),
        "multi_only_headings": sorted(multi_headings - single_headings),
        "single_only_headings": sorted(single_headings - multi_headings),
        "section_presence_delta": {
            key: {
                "multi_agent": multi_summary["section_presence"][key],
                "single_model": single_summary["section_presence"][key],
            }
            for key in REPORT_SECTION_KEYWORDS
        },
        "diff_excerpt": diff_lines[:200],
    }


def comparison_to_markdown(comparison: Dict[str, Any]) -> str:
    """将对比摘要转成 Markdown。"""
    similarity_ratio = comparison.get("similarity_ratio", 0.0)
    multi_agent = comparison.get("multi_agent", {})
    single_model = comparison.get("single_model", {})
    delta = comparison.get("section_presence_delta", {})
    diff_excerpt = comparison.get("diff_excerpt", [])

    lines = [
        "# 报告对比摘要",
        "",
        f"- 文本相似度（SequenceMatcher）: {similarity_ratio:.4f}",
        f"- 多智能体报告长度: {multi_agent.get('char_count', 0)} 字符 / {multi_agent.get('line_count', 0)} 行",
        f"- 单模型报告长度: {single_model.get('char_count', 0)} 字符 / {single_model.get('line_count', 0)} 行",
        "",
        "## 结构覆盖",
    ]
    for key, value in delta.items():
        lines.append(
            f"- {key}: multi_agent={value.get('multi_agent')} / single_model={value.get('single_model')}"
        )

    lines.extend(
        [
            "",
            "## 标题差异",
            f"- 共同标题: {comparison.get('shared_headings', [])}",
            f"- 多智能体独有标题: {comparison.get('multi_only_headings', [])}",
            f"- 单模型独有标题: {comparison.get('single_only_headings', [])}",
            "",
            "## Diff 片段",
            "```diff",
            *diff_excerpt,
            "```",
        ]
    )
    return "\n".join(lines)
