"""
KnowledgeAgent - RAG 知识检索与推理 Agent
提供分层 LLM 检索，失败时回退到旧版关键词检索。
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI

from evaluation.utils import parse_json_response

try:
    from rag.agent import PageIndexRAGAgent
except Exception:
    PageIndexRAGAgent = None


logger = logging.getLogger(__name__)

EVIDENCE_BATCH_SIZE = 2
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_TIMEOUT_SECONDS = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "180"))
DEEPSEEK_MAX_RETRIES = int(os.getenv("DEEPSEEK_MAX_RETRIES", "2"))
DEEPSEEK_RETRY_DELAY_SECONDS = float(os.getenv("DEEPSEEK_RETRY_DELAY_SECONDS", "2"))
LLM_TEMPERATURE_OVERRIDE = os.getenv("LLM_TEMPERATURE_OVERRIDE", "").strip()


class KnowledgeAgent:
    """知识检索与推理 Agent - 封装分层 RAG 功能"""

    def __init__(self, rag_agent: PageIndexRAGAgent):
        self.rag = rag_agent
        self.cache: Dict[str, Dict[str, Any]] = {}
        self._client: Optional[OpenAI] = None

    def retrieve(self, query: str, top_k: int = 3, use_cache: bool = True) -> Dict[str, Any]:
        """
        基础检索方法。
        仅用于兜底场景或显式 query 查询。
        """
        cache_key = f"keyword::{query}_{top_k}"
        if use_cache and cache_key in self.cache:
            return self.cache[cache_key]

        try:
            result = self.rag.build_context(query, top_k=top_k)
            payload = {
                "query": query,
                "hits": result.get("hits", []),
                "context": result.get("context", ""),
                "retrieval_mode": "keyword_direct",
            }
            if use_cache:
                self.cache[cache_key] = payload
            return payload
        except Exception as e:
            logger.warning("RAG 检索失败: %s", e)
            return {
                "query": query,
                "hits": [],
                "context": "",
                "retrieval_mode": "keyword_direct",
            }

    def retrieve_comprehensive(
        self,
        profile: Any,
        status_result: Dict,
        risk_result: Dict,
        factor_result: Dict,
        top_k: int = 3,
    ) -> Dict[str, Any]:
        """
        综合知识检索（优先使用分层 LLM 路由，失败时回退到关键词检索）。
        """
        retrieval_brief = self._build_retrieval_brief(profile, status_result, risk_result, factor_result)
        cache_key = f"hier::{json.dumps(retrieval_brief, ensure_ascii=False, sort_keys=True)}::{top_k}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            result = self._retrieve_hierarchical(retrieval_brief, top_k=top_k)
            self.cache[cache_key] = result
            return result
        except Exception as e:
            logger.warning("分层检索失败，回退关键词检索: %s", e)
            fallback = self._retrieve_comprehensive_keyword_fallback(
                profile,
                status_result,
                risk_result,
                factor_result,
                top_k=top_k,
            )
            fallback["retrieval_brief"] = retrieval_brief
            fallback["retrieval_mode"] = "fallback_keyword"
            fallback["retrieval_trace"] = {
                "fallback_reason": str(e),
                "document_selection": {"selected_docs": []},
                "node_selection": {"selected_nodes": []},
                "evidence_extraction": {"evidence_cards": []},
            }
            self.cache[cache_key] = fallback
            return fallback

    def retrieve_for_action_plan(
        self,
        profile: Any,
        action_category: str,
        specific_need: str = "",
        top_k: int = 2,
    ) -> Dict[str, Any]:
        """
        针对行动计划的关键词检索兜底接口。
        """
        age = int(profile.age) if getattr(profile, "age", None) else 0
        query_parts = [
            f"{age}岁老人",
            action_category,
            specific_need,
            "具体方法 实施步骤",
        ]
        query = " ".join([p for p in query_parts if p])
        result = self.retrieve(query, top_k=top_k)
        result["category"] = action_category
        result["methods"] = self._extract_methods(result.get("hits", []))
        return result

    def _call_llm_json(self, prompt: str, max_tokens: int = 4096) -> Dict[str, Any]:
        response = self._call_llm(prompt, max_tokens=max_tokens)
        parsed = parse_json_response(response)
        if isinstance(parsed, list):
            return {"items": parsed, "_raw_response": response}
        if isinstance(parsed, dict):
            parsed["_raw_response"] = response
            return parsed
        raise ValueError("LLM 未返回 JSON 对象或数组")

    def _get_client(self) -> OpenAI:
        if self._client is None:
            for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
                os.environ.pop(key, None)
            self._client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        return self._client

    def _call_llm(
        self,
        prompt: str,
        system_prompt: str = "你是一个严谨的知识路由助手，请按照指令精确完成任务。",
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        client = self._get_client()
        total_attempts = DEEPSEEK_MAX_RETRIES + 1
        if LLM_TEMPERATURE_OVERRIDE:
            try:
                temperature = float(LLM_TEMPERATURE_OVERRIDE)
            except ValueError:
                pass

        for attempt in range(1, total_attempts + 1):
            started_at = time.monotonic()
            try:
                logger.info(
                    "[knowledge] LLM call attempt=%s/%s prompt_chars=%s max_tokens=%s temperature=%.2f",
                    attempt,
                    total_attempts,
                    len(prompt),
                    max_tokens,
                    temperature,
                )
                response = client.chat.completions.create(
                    model=DEEPSEEK_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=DEEPSEEK_TIMEOUT_SECONDS,
                )
                logger.info(
                    "[knowledge] LLM call finished attempt=%s/%s duration=%.2fs",
                    attempt,
                    total_attempts,
                    time.monotonic() - started_at,
                )
                return response.choices[0].message.content.strip()
            except Exception as error:
                logger.warning(
                    "[knowledge] LLM call failed attempt=%s/%s duration=%.2fs error=%s",
                    attempt,
                    total_attempts,
                    time.monotonic() - started_at,
                    error,
                )
                if attempt >= total_attempts:
                    raise
                sleep_seconds = max(DEEPSEEK_RETRY_DELAY_SECONDS, 0.0) * attempt
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)

    def _build_retrieval_brief(
        self,
        profile: Any,
        status_result: Dict[str, Any],
        risk_result: Dict[str, Any],
        factor_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        diseases = self._extract_diseases(profile)
        short_risks = [
            item.get("risk", "")
            for item in (risk_result.get("short_term_risks", []) or [])
            if item.get("risk")
        ]
        medium_risks = [
            item.get("risk", "")
            for item in (risk_result.get("medium_term_risks", []) or [])
            if item.get("risk")
        ]
        problems = []
        for item in factor_result.get("main_problems", []) or []:
            if isinstance(item, str):
                if item.strip():
                    problems.append(item.strip())
            elif isinstance(item, dict):
                for key in ("problem", "impact"):
                    value = str(item.get(key) or "").strip()
                    if value:
                        problems.append(value)

        focus_needs: List[str] = []
        focus_needs.extend(short_risks[:3])
        focus_needs.extend(medium_risks[:2])
        focus_needs.extend(problems[:3])
        focus_needs.extend(diseases[:3])

        brief = {
            "profile": {
                "age": getattr(profile, "age", None),
                "sex": getattr(profile, "sex", None),
                "residence": getattr(profile, "residence", None),
                "living_arrangement": getattr(profile, "living_arrangement", None),
                "caregiver": getattr(profile, "caregiver", None),
                "medical_insurance": getattr(profile, "medical_insurance", None),
            },
            "status": {
                "status_name": status_result.get("status_name"),
                "status_description": status_result.get("status_description"),
                "badl_details": status_result.get("badl_details", []),
                "iadl_details": status_result.get("iadl_details", []),
            },
            "risks": {
                "overall_risk_level": risk_result.get("overall_risk_level"),
                "short_term": short_risks[:4],
                "medium_term": medium_risks[:4],
            },
            "factors": {
                "main_problems": problems[:6],
                "changeable_factors": factor_result.get("changeable_factors", [])[:6],
            },
            "diseases": diseases[:6],
            "focus_needs": self._dedupe(focus_needs),
        }
        brief["text"] = self._format_retrieval_brief_text(brief)
        return brief

    def _format_retrieval_brief_text(self, brief: Dict[str, Any]) -> str:
        profile = brief["profile"]
        status = brief["status"]
        risks = brief["risks"]
        factors = brief["factors"]
        lines = [
            f"老人画像：{profile.get('age', '未知')}岁，{profile.get('sex', '未知')}，居住地={profile.get('residence') or '未知'}，居住方式={profile.get('living_arrangement') or '未知'}。",
            f"功能状态：{status.get('status_name') or '未知'}；{status.get('status_description') or '暂无补充说明'}。",
            f"短期风险：{'；'.join(risks.get('short_term') or []) or '暂无'}。",
            f"中期风险：{'；'.join(risks.get('medium_term') or []) or '暂无'}。",
            f"主要问题：{'；'.join(factors.get('main_problems') or []) or '暂无'}。",
            f"慢性病：{'；'.join(brief.get('diseases') or []) or '暂无明确慢病'}。",
            f"本轮最需要检索的照护需求：{'；'.join(brief.get('focus_needs') or []) or '通用老年照护建议'}。",
        ]
        return "\n".join(lines)

    def _retrieve_hierarchical(self, retrieval_brief: Dict[str, Any], top_k: int = 3) -> Dict[str, Any]:
        document_catalog = self.rag.get_document_catalog()
        if not document_catalog:
            raise ValueError("索引中缺少文档目录")

        doc_selection = self._select_documents(retrieval_brief, document_catalog, max_docs=max(2, min(top_k + 1, 4)))
        selected_docs = doc_selection.get("selected_docs", [])
        if not selected_docs:
            raise ValueError("文档路由未选中文档")

        node_catalog = self.rag.get_node_catalog(
            doc_ids=[item["doc_id"] for item in selected_docs],
            max_level=3,
            limit_per_doc=40,
        )
        if not node_catalog:
            raise ValueError("所选文档没有可用节点目录")

        node_selection = self._select_nodes(
            retrieval_brief,
            selected_docs,
            node_catalog,
            max_nodes=max(4, min(top_k * 2, 8)),
        )
        selected_nodes = node_selection.get("selected_nodes", [])
        if not selected_nodes:
            raise ValueError("节点路由未选中内容")

        full_nodes = self.rag.get_nodes_by_ids([item["node_id"] for item in selected_nodes])
        if not full_nodes:
            raise ValueError("无法从索引中加载选中节点全文")

        merged_nodes = self._merge_selected_nodes(selected_nodes, full_nodes)
        evidence_result = self._extract_evidence_cards(
            retrieval_brief,
            merged_nodes,
            max_cards=max(4, min(top_k * 2, 8)),
        )
        evidence_cards = evidence_result.get("evidence_cards", [])

        combined_context = self._combine_evidence_cards(evidence_cards, merged_nodes)
        return {
            "enabled": True,
            "retrieval_mode": "hierarchical_llm",
            "retrieval_brief": retrieval_brief,
            "selected_docs": selected_docs,
            "selected_nodes": merged_nodes,
            "evidence_cards": evidence_cards,
            "combined_context": combined_context,
            "total_hits": len(merged_nodes),
            "retrieval_trace": {
                "document_selection": doc_selection,
                "node_selection": node_selection,
                "evidence_extraction": evidence_result,
            },
            "risk_prevention": {"hits": [], "context": ""},
            "disease_management": {"hits": [], "context": ""},
            "functional_training": {"hits": [], "context": ""},
        }

    def _select_documents(
        self,
        retrieval_brief: Dict[str, Any],
        document_catalog: List[Dict[str, Any]],
        max_docs: int,
    ) -> Dict[str, Any]:
        doc_lines = []
        for item in document_catalog:
            outline_titles = "；".join(
                node.get("title", "") for node in item.get("outline_nodes", [])[:5] if node.get("title")
            )
            doc_lines.append(
                "\n".join(
                    [
                        f"- doc_id: {item.get('doc_id')}",
                        f"  doc_name: {item.get('doc_name')}",
                        f"  doc_summary: {item.get('doc_summary') or '无'}",
                        f"  outline: {outline_titles or '无'}",
                    ]
                )
            )

        prompt = f"""你是老年照护知识库的文档路由器。请根据病例检索摘要，从候选文档中选出最值得继续查看详细索引的文档。

要求：
- 只选择与当前病例直接相关、能支持后续生成具体照护建议的文档
- 优先选择能覆盖“高优先级风险 / 主要问题 / 照护动作”的文档
- 返回 1 到 {max_docs} 份文档
- 不要因为文档很长或很常见就默认选择

病例检索摘要：
{retrieval_brief['text']}

候选文档目录：
{chr(10).join(doc_lines)}

请只输出 JSON：
{{
  "selected_docs": [
    {{
      "doc_id": "文档ID",
      "reason": "为什么需要看这份文档",
      "relevance_to_case": "这份文档对应病例的哪个关键需求"
    }}
  ]
}}"""

        payload = self._call_llm_json(prompt, max_tokens=3072)
        selected = []
        for item in payload.get("selected_docs", []) or payload.get("items", []):
            if not isinstance(item, dict):
                continue
            doc_id = str(item.get("doc_id") or "").strip()
            matched = next((doc for doc in document_catalog if doc.get("doc_id") == doc_id), None)
            if matched is None:
                continue
            selected.append(
                {
                    "doc_id": doc_id,
                    "doc_name": matched.get("doc_name"),
                    "doc_summary": matched.get("doc_summary"),
                    "reason": str(item.get("reason") or "").strip(),
                    "relevance_to_case": str(item.get("relevance_to_case") or "").strip(),
                    "outline_nodes": matched.get("outline_nodes", []),
                }
            )
        payload["selected_docs"] = self._dedupe_dicts(selected, "doc_id")[:max_docs]
        return payload

    def _select_nodes(
        self,
        retrieval_brief: Dict[str, Any],
        selected_docs: List[Dict[str, Any]],
        node_catalog: List[Dict[str, Any]],
        max_nodes: int,
    ) -> Dict[str, Any]:
        doc_lookup = {item["doc_id"]: item for item in selected_docs}
        node_lines = []
        for node in node_catalog:
            doc_name = doc_lookup.get(node.get("doc_id"), {}).get("doc_name") or node.get("doc_name")
            node_lines.append(
                "\n".join(
                    [
                        f"- node_id: {node.get('node_id')}",
                        f"  doc_name: {doc_name}",
                        f"  path: {node.get('path')}",
                        f"  summary: {node.get('summary') or '无'}",
                        f"  level: {node.get('level')}",
                    ]
                )
            )

        prompt = f"""你是老年照护知识库的节点路由器。你已经拿到了候选文档，现在要从这些文档的详细索引中选出最值得读取全文的节点。

要求：
- 只选择后续生成照护建议真正需要的节点
- 返回 3 到 {max_nodes} 个节点
- 同一文档最多选择 3 个节点
- 优先选择包含“做法、适用对象、风险预防、功能训练、居家管理”信息的节点

病例检索摘要：
{retrieval_brief['text']}

已选文档：
{json.dumps([{k: v for k, v in item.items() if k != 'outline_nodes'} for item in selected_docs], ensure_ascii=False, indent=2)}

详细索引：
{chr(10).join(node_lines)}

请只输出 JSON：
{{
  "selected_nodes": [
    {{
      "node_id": "节点ID",
      "reason": "为什么要看这个节点",
      "need": "这个节点要解决的病例需求"
    }}
  ]
}}"""

        payload = self._call_llm_json(prompt, max_tokens=4096)
        selected: List[Dict[str, Any]] = []
        per_doc_counts: Dict[str, int] = {}
        node_lookup = {item["node_id"]: item for item in node_catalog}
        for item in payload.get("selected_nodes", []) or payload.get("items", []):
            if not isinstance(item, dict):
                continue
            node_id = str(item.get("node_id") or "").strip()
            matched = node_lookup.get(node_id)
            if matched is None:
                continue
            doc_id = str(matched.get("doc_id") or "")
            if per_doc_counts.get(doc_id, 0) >= 3:
                continue
            per_doc_counts[doc_id] = per_doc_counts.get(doc_id, 0) + 1
            selected.append(
                {
                    "node_id": node_id,
                    "doc_id": doc_id,
                    "doc_name": matched.get("doc_name"),
                    "path": matched.get("path"),
                    "summary": matched.get("summary"),
                    "reason": str(item.get("reason") or "").strip(),
                    "need": str(item.get("need") or "").strip(),
                }
            )
        payload["selected_nodes"] = self._dedupe_dicts(selected, "node_id")[:max_nodes]
        return payload

    def _merge_selected_nodes(
        self,
        selected_nodes: List[Dict[str, Any]],
        full_nodes: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        selected_lookup = {item["node_id"]: item for item in selected_nodes}
        merged = []
        for node in full_nodes:
            routed = selected_lookup.get(node.get("node_id"), {})
            merged.append(
                {
                    "node_id": node.get("node_id"),
                    "doc_id": node.get("doc_id"),
                    "doc_name": node.get("doc_name"),
                    "path": node.get("path"),
                    "title": node.get("title"),
                    "summary": node.get("summary"),
                    "text": node.get("text", ""),
                    "excerpt": node.get("text", "")[:320],
                    "reason": routed.get("reason", ""),
                    "need": routed.get("need", ""),
                    "line_num": node.get("line_num"),
                    "start_index": node.get("start_index"),
                    "end_index": node.get("end_index"),
                    "source_path": node.get("source_path"),
                    "source_type": node.get("source_type"),
                }
            )
        return merged

    def _extract_evidence_cards(
        self,
        retrieval_brief: Dict[str, Any],
        selected_nodes: List[Dict[str, Any]],
        max_cards: int,
    ) -> Dict[str, Any]:
        batches = self._chunk_selected_nodes(selected_nodes, batch_size=EVIDENCE_BATCH_SIZE)
        logger.info(
            "Evidence extraction batches=%s selected_nodes=%s batch_size=%s",
            len(batches),
            len(selected_nodes),
            EVIDENCE_BATCH_SIZE,
        )
        node_lookup = {item["node_id"]: item for item in selected_nodes}
        all_cards: List[Dict[str, Any]] = []
        raw_batches: List[Dict[str, Any]] = []

        for batch_index, batch_nodes in enumerate(batches, start=1):
            node_blocks = []
            for node in batch_nodes:
                node_blocks.append(
                    "\n".join(
                        [
                            f"[node_id] {node.get('node_id')}",
                            f"[doc_name] {node.get('doc_name')}",
                            f"[path] {node.get('path')}",
                            f"[selected_need] {node.get('need') or '未填写'}",
                            f"[selected_reason] {node.get('reason') or '未填写'}",
                            f"[text]\n{self._truncate_node_text(node.get('text', ''))}",
                        ]
                    )
                )

            prompt = f"""你是老年照护知识提炼助手。请根据病例摘要和选中的知识节点，提炼可直接支持报告生成的结构化证据卡。

要求：
- 返回 4 到 {max_cards} 条 evidence_cards
- recommendation 必须是贴合病例的“推荐内容”，不是泛泛摘要
- evidence_quote 必须原样摘自材料，长度控制在 30-120 字
- applicability 要说清楚为什么适用于当前病例
- 只可使用给定节点中的内容，不要补充外部常识

病例检索摘要：
{retrieval_brief['text']}

选中节点全文：
{chr(10).join(node_blocks)}

请只输出 JSON：
{{
  "evidence_cards": [
    {{
      "need": "对应的病例需求",
      "recommendation": "可供后续行动计划吸收的推荐内容",
      "evidence_quote": "材料中的原文依据",
      "doc_name": "来源文档名",
      "node_id": "来源节点ID",
      "path": "来源章节路径",
      "applicability": "为什么适用于当前病例"
    }}
  ]
}}"""
            logger.info(
                "Evidence extraction batch=%s/%s prompt_chars=%s node_count=%s",
                batch_index,
                len(batches),
                len(prompt),
                len(batch_nodes),
            )
            payload = self._call_llm_json(prompt, max_tokens=4096)
            raw_batches.append(
                {
                    "batch_index": batch_index,
                    "node_ids": [node.get("node_id") for node in batch_nodes],
                    "prompt_chars": len(prompt),
                    "response": payload.get("_raw_response", ""),
                }
            )
            for item in payload.get("evidence_cards", []) or payload.get("items", []):
                if not isinstance(item, dict):
                    continue
                node_id = str(item.get("node_id") or "").strip()
                node = node_lookup.get(node_id)
                if node is None:
                    continue
                all_cards.append(
                    {
                        "need": str(item.get("need") or node.get("need") or "").strip(),
                        "recommendation": str(item.get("recommendation") or "").strip(),
                        "evidence_quote": str(item.get("evidence_quote") or "").strip(),
                        "doc_name": node.get("doc_name"),
                        "node_id": node_id,
                        "path": node.get("path"),
                        "applicability": str(item.get("applicability") or "").strip(),
                    }
                )

        return {
            "evidence_cards": self._dedupe_cards(all_cards)[:max_cards],
            "batches": raw_batches,
        }

    def _combine_evidence_cards(
        self,
        evidence_cards: List[Dict[str, Any]],
        selected_nodes: List[Dict[str, Any]],
    ) -> str:
        if evidence_cards:
            parts = ["【结构化知识证据】"]
            for idx, card in enumerate(evidence_cards, start=1):
                parts.append(
                    "\n".join(
                        [
                            f"[证据{idx}] 需求：{card.get('need') or '未标注'}",
                            f"推荐内容：{card.get('recommendation') or '未提炼'}",
                            f"证据原文：{card.get('evidence_quote') or '未提取'}",
                            f"来源：{card.get('doc_name')} / {card.get('path')}",
                            f"适用原因：{card.get('applicability') or '未说明'}",
                        ]
                    )
                )
            return "\n\n".join(parts)

        fallback_parts = ["【选中知识节点】"]
        for idx, node in enumerate(selected_nodes, start=1):
            fallback_parts.append(
                "\n".join(
                    [
                        f"[节点{idx}] {node.get('doc_name')} / {node.get('path')}",
                        f"用途：{node.get('need') or node.get('reason') or '未标注'}",
                        f"摘要：{self._truncate_node_text(node.get('text', ''), limit=240)}",
                    ]
                )
            )
        return "\n\n".join(fallback_parts)

    def _truncate_node_text(self, text: str, limit: int = 1800) -> str:
        text = str(text or "").strip()
        if len(text) <= limit:
            return text
        return f"{text[: limit - 3].rstrip()}..."

    @staticmethod
    def _chunk_selected_nodes(selected_nodes: List[Dict[str, Any]], batch_size: int) -> List[List[Dict[str, Any]]]:
        if batch_size <= 0:
            return [selected_nodes]
        return [
            selected_nodes[idx: idx + batch_size]
            for idx in range(0, len(selected_nodes), batch_size)
            if selected_nodes[idx: idx + batch_size]
        ]

    def _retrieve_comprehensive_keyword_fallback(
        self,
        profile: Any,
        status_result: Dict,
        risk_result: Dict,
        factor_result: Dict,
        top_k: int = 3,
    ) -> Dict[str, Any]:
        risk_knowledge = self.retrieve_for_risk_prevention(
            profile,
            risk_result.get("short_term_risks", []),
            top_k=top_k,
        )
        disease_knowledge = self.retrieve_for_disease_management(
            profile,
            top_k=top_k,
        )
        training_knowledge = self.retrieve_for_functional_training(
            status_result,
            top_k=top_k,
        )

        combined_context = self._combine_contexts(
            [
                risk_knowledge.get("context", ""),
                disease_knowledge.get("context", ""),
                training_knowledge.get("context", ""),
            ]
        )
        return {
            "enabled": True,
            "risk_prevention": risk_knowledge,
            "disease_management": disease_knowledge,
            "functional_training": training_knowledge,
            "combined_context": combined_context,
            "total_hits": (
                len(risk_knowledge.get("hits", []))
                + len(disease_knowledge.get("hits", []))
                + len(training_knowledge.get("hits", []))
            ),
            "selected_docs": [],
            "selected_nodes": [],
            "evidence_cards": [],
        }

    def retrieve_for_risk_prevention(
        self,
        profile: Any,
        risks: List[Dict],
        top_k: int = 2,
    ) -> Dict[str, Any]:
        if not risks:
            return {"enabled": False, "hits": [], "context": ""}

        high_risks = [r for r in risks if r.get("severity") == "高"]
        target_risks = high_risks[:2] if high_risks else risks[:2]
        risk_names = [r.get("risk", "") for r in target_risks]
        age = int(profile.age) if getattr(profile, "age", None) else 0
        query = f"{age}岁 {profile.sex} {' '.join(risk_names)} 预防措施 照护要点"

        result = self.retrieve(query, top_k=top_k)
        return {
            "enabled": True,
            "query": query,
            "target_risks": risk_names,
            "hits": result["hits"],
            "context": result["context"],
            "recommendations": self._extract_recommendations(result["hits"]),
        }

    def retrieve_for_disease_management(
        self,
        profile: Any,
        top_k: int = 2,
    ) -> Dict[str, Any]:
        diseases = self._extract_diseases(profile)
        if not diseases:
            return {"enabled": False, "diseases": [], "hits": [], "context": ""}

        query = f"老年人 {' '.join(diseases[:3])} 日常管理 注意事项 健康标准"
        result = self.retrieve(query, top_k=top_k)
        return {
            "enabled": True,
            "query": query,
            "diseases": diseases,
            "hits": result["hits"],
            "context": result["context"],
            "management_tips": self._extract_management_tips(result["hits"]),
        }

    def retrieve_for_functional_training(
        self,
        status_result: Dict,
        top_k: int = 2,
    ) -> Dict[str, Any]:
        status_name = status_result.get("status_name", "")
        badl_details = status_result.get("badl_details", [])
        iadl_details = status_result.get("iadl_details", [])
        if not status_name:
            return {"enabled": False, "hits": [], "context": ""}

        limitations = []
        if badl_details:
            limitations.extend(badl_details[:2])
        if iadl_details:
            limitations.extend(iadl_details[:2])

        query = f"{status_name} {' '.join(limitations)} 功能训练 康复方法 改善"
        result = self.retrieve(query, top_k=top_k)
        return {
            "enabled": True,
            "query": query,
            "status": status_name,
            "limitations": limitations,
            "hits": result["hits"],
            "context": result["context"],
            "training_methods": self._extract_training_methods(result["hits"]),
        }

    def _extract_diseases(self, profile: Any) -> List[str]:
        diseases = []
        disease_map = {
            "hypertension": "高血压",
            "diabetes": "糖尿病",
            "coronary_heart_disease": "冠心病",
            "heart_failure": "心力衰竭",
            "arrhythmia": "心律失常",
            "stroke": "中风",
            "arthritis": "关节炎",
            "cancer": "肿瘤",
            "hearing_impairment": "听力障碍",
        }
        for field, name in disease_map.items():
            value = str(getattr(profile, field, "")).strip()
            if value in {"是", "有", "患有", "1", "true", "True"}:
                diseases.append(name)
        return diseases

    def _extract_recommendations(self, hits: List[Dict]) -> List[str]:
        return self._extract_by_keywords(hits, ["建议", "应", "需要", "可以", "推荐", "宜"])

    def _extract_management_tips(self, hits: List[Dict]) -> List[str]:
        return self._extract_by_keywords(hits, ["管理", "控制", "监测", "注意", "定期", "检查"])

    def _extract_training_methods(self, hits: List[Dict]) -> List[str]:
        return self._extract_by_keywords(hits, ["训练", "锻炼", "康复", "运动", "练习", "改善"])

    def _extract_methods(self, hits: List[Dict]) -> List[str]:
        return self._extract_by_keywords(hits, ["方法", "步骤", "措施", "做法", "可以", "通过"])

    def _extract_by_keywords(self, hits: List[Dict], keywords: List[str]) -> List[str]:
        items = []
        for hit in hits:
            excerpt = hit.get("excerpt", "")
            for keyword in keywords:
                if keyword in excerpt:
                    for sentence in excerpt.split("。"):
                        if keyword in sentence and len(sentence) > 10:
                            items.append(sentence.strip()[:120])
                            break
                    break
        return self._dedupe(items)[:5]

    def _combine_contexts(self, contexts: List[str]) -> str:
        valid_contexts = [c.strip() for c in contexts if c and c.strip()]
        if not valid_contexts:
            return ""
        labels = ["【风险预防知识】", "【慢性病管理指南】", "【功能训练建议】"]
        combined = []
        for idx, context in enumerate(valid_contexts):
            prefix = labels[idx] if idx < len(labels) else "【知识片段】"
            combined.append(f"{prefix}\n{context}")
        return "\n\n".join(combined)

    @staticmethod
    def _dedupe(items: List[str]) -> List[str]:
        seen = set()
        output = []
        for item in items:
            normalized = str(item or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            output.append(normalized)
        return output

    @staticmethod
    def _dedupe_dicts(items: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
        seen = set()
        output = []
        for item in items:
            marker = item.get(key)
            if not marker or marker in seen:
                continue
            seen.add(marker)
            output.append(item)
        return output

    @staticmethod
    def _dedupe_cards(cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        output = []
        for card in cards:
            recommendation = str(card.get("recommendation") or "").strip()
            marker = (card.get("node_id"), recommendation)
            if not recommendation or marker in seen:
                continue
            seen.add(marker)
            output.append(card)
        return output

    def clear_cache(self):
        self.cache.clear()
