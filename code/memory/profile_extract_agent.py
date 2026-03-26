"""
用户画像信息提取 Agent
仅用于自由回答题目的字段抽取。
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.questionnaire import FIELD_META


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

for key in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
    if key in os.environ:
        del os.environ[key]

client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


class ProfileExtractAgent:
    """
    从自然语言回答中抽取结构化字段。
    结构化题卡不走这里，只有 chat 类题目会调用。
    """

    SYSTEM_PROMPT = (
        "你是一个专门从中文对话中提取老年健康评估字段的助手。\n\n"
        "你的任务：\n"
        "- 只从用户最新回答中提取当前目标字段\n"
        "- 提取不确定时宁可留空，不要猜测\n"
        "- 返回 JSON，对应字段名到标准值\n\n"
        "标准值要求：\n"
        "- 性别：男 / 女\n"
        "- 居住地：城市 / 农村\n"
        "- 婚姻状况：在婚 / 丧偶 / 离婚 / 未婚 / 其他\n"
        "- 视力/听力：好 / 一般 / 差\n"
        "- 定向类：正确 / 错误 / 不知道\n"
        "- 计算能力 cognition_calc：长度为 3 的数组，元素为 正确 / 错误 / 不知道\n"
        "- 慢病类：是 / 否\n"
        "- 心理状态：从不 / 很少 / 有时 / 经常\n"
        "- 吸烟/饮酒：从不 / 已戒 / 偶尔 / 每天\n"
        "- BADL：不需要帮助 / 需要别人搭把手 / 大部分要靠别人帮忙\n"
        "- IADL：能自己做 / 做起来有点困难 / 现在做不了\n"
        "- 健康限制：完全没有影响 / 有一点影响 / 影响比较明显 / 影响很大\n\n"
        "转换规则：\n"
        "- 小学≈6年，初中≈9年，高中≈12年\n"
        "- 没上过学≈0年\n"
        "- 已戒烟/已戒酒/以前抽现在不抽 -> 已戒\n"
        "- 经常喝酒/每天喝 -> 每天\n"
        "- 偶尔喝/很少喝一点 -> 偶尔\n"
        "- 用户明确说没量过腰围、臀围，不要填值\n"
        "- 用户说不记得、不知道、记不清，定向类填不知道；其他字段不提取\n\n"
        "数值字段：\n"
        "- age、education_years 提取整数\n"
        "- weight、height、waist_circumference、hip_circumference 提取浮点数\n\n"
        "只输出 JSON，不要添加解释。"
    )

    def extract(
        self,
        user_message: str,
        target_fields: List[str],
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        if not user_message.strip() or not target_fields:
            return {}

        field_desc_lines = []
        for field in target_fields:
            meta = FIELD_META.get(field, {})
            zh = meta.get("zh", field)
            hint = meta.get("hint", "")
            field_desc_lines.append(f"- {field}（{zh}）：{hint}")

        context_text = ""
        if conversation_history:
            for message in conversation_history[-6:]:
                role_zh = "用户" if message.get("role") == "user" else "助手"
                context_text += f"{role_zh}：{message.get('content', '')}\n"

        user_prompt = (
            "【需要提取的字段】\n"
            f"{chr(10).join(field_desc_lines)}\n\n"
            "【最近对话】\n"
            f"{context_text or '（无）'}\n\n"
            "【用户最新回答】\n"
            f"{user_message}\n\n"
            "请提取目标字段，返回 JSON；未明确提到的字段不要输出。"
        )

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=700,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()
            extracted = json.loads(raw)
            return {key: value for key, value in extracted.items() if key in target_fields}
        except Exception as exc:
            print(f"[ProfileExtractAgent] 提取失败: {exc}")
            return {}

    def generate_followup(
        self,
        missing_fields: List[str],
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        group_question: Optional[str] = None,
    ) -> str:
        labels = [FIELD_META.get(field, {}).get("zh", field) for field in missing_fields[:6]]
        if not labels:
            return "您继续说就可以。"
        return f"刚才还差这些信息：{'、'.join(labels)}。您方便补充一下吗？"

