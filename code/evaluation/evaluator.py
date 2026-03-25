"""
评测编排器 - 协调分源 grounding、画像覆盖和分层检索指标。
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from evaluation.metrics import (
    DocRoutingRelevanceMetric,
    DocRoutingRelevanceResult,
    EvidenceCoverageMetric,
    EvidenceCoverageResult,
    GroundingResult,
    NodeEvidenceRelevanceMetric,
    NodeEvidenceRelevanceResult,
    ProfileCoverageMetric,
    ProfileCoverageResult,
    ReportGroundingMetric,
)
from evaluation.utils import (
    build_input_evidence_text,
    build_retrieval_focus_needs,
    build_retrieved_context_text,
    extract_profile_elements,
)

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    input_grounding: Optional[GroundingResult] = None
    guideline_grounding: Optional[GroundingResult] = None
    profile_coverage: Optional[ProfileCoverageResult] = None
    doc_routing_relevance: Optional[DocRoutingRelevanceResult] = None
    node_evidence_relevance: Optional[NodeEvidenceRelevanceResult] = None
    evidence_coverage: Optional[EvidenceCoverageResult] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        if self.input_grounding:
            result["input_grounding"] = self.input_grounding.score
        if self.guideline_grounding:
            result["guideline_grounding"] = self.guideline_grounding.score
        if self.profile_coverage:
            result["profile_coverage"] = self.profile_coverage.score
        if self.doc_routing_relevance:
            result["doc_routing_relevance"] = self.doc_routing_relevance.score
        if self.node_evidence_relevance:
            result["node_evidence_relevance"] = self.node_evidence_relevance.score
        if self.evidence_coverage:
            result["evidence_coverage"] = self.evidence_coverage.score
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary(),
            "input_grounding": asdict(self.input_grounding) if self.input_grounding else None,
            "guideline_grounding": asdict(self.guideline_grounding) if self.guideline_grounding else None,
            "profile_coverage": asdict(self.profile_coverage) if self.profile_coverage else None,
            "doc_routing_relevance": asdict(self.doc_routing_relevance) if self.doc_routing_relevance else None,
            "node_evidence_relevance": asdict(self.node_evidence_relevance) if self.node_evidence_relevance else None,
            "evidence_coverage": asdict(self.evidence_coverage) if self.evidence_coverage else None,
            "metadata": self.metadata,
        }


class ReportEvaluator:
    """
    报告评测编排器。

    支持两种模式：
    1. 在线评测：传入 results dict 和 profile
    2. 离线评测：从 JSON 文件加载，可选重新运行 RAG 检索
    """

    def __init__(self, rag_agent=None, knowledge_agent=None):
        self.rag_agent = rag_agent
        self.knowledge_agent = knowledge_agent
        self.grounding_metric = ReportGroundingMetric()
        self.coverage_metric = ProfileCoverageMetric()
        self.doc_routing_metric = DocRoutingRelevanceMetric()
        self.node_relevance_metric = NodeEvidenceRelevanceMetric()
        self.evidence_coverage_metric = EvidenceCoverageMetric()

    def evaluate(
        self,
        results: Dict[str, Any],
        profile: Dict[str, Any],
        run_input_grounding: bool = True,
        run_guideline_grounding: bool = True,
        run_coverage: bool = True,
        run_doc_routing: bool = True,
        run_node_relevance: bool = True,
        run_evidence_coverage: bool = True,
    ) -> EvaluationResult:
        report_text = results.get("report", "")
        knowledge = results.get("knowledge", {}) or {}

        input_context = build_input_evidence_text(results, profile)
        guideline_context = build_retrieved_context_text(knowledge, use_full_text=True)
        profile_elements = extract_profile_elements(profile)
        focus_needs = build_retrieval_focus_needs(results, knowledge)

        eval_result = EvaluationResult()

        if run_input_grounding or run_guideline_grounding:
            input_grounding, guideline_grounding = self.grounding_metric.evaluate(
                report_text,
                input_context=input_context,
                guideline_context=guideline_context,
            )
            if run_input_grounding:
                eval_result.input_grounding = input_grounding
            if run_guideline_grounding:
                eval_result.guideline_grounding = guideline_grounding

        if run_coverage:
            eval_result.profile_coverage = self.coverage_metric.evaluate(report_text, profile_elements)

        if run_doc_routing:
            eval_result.doc_routing_relevance = self.doc_routing_metric.evaluate(
                knowledge.get("retrieval_brief", {}),
                knowledge.get("selected_docs", []) or [],
            )

        if run_node_relevance:
            eval_result.node_evidence_relevance = self.node_relevance_metric.evaluate(
                knowledge.get("selected_nodes", []) or [],
                knowledge.get("evidence_cards", []) or [],
            )

        if run_evidence_coverage:
            eval_result.evidence_coverage = self.evidence_coverage_metric.evaluate(
                focus_needs,
                knowledge.get("evidence_cards", []) or [],
            )

        eval_result.metadata = {
            "retrieval_mode": knowledge.get("retrieval_mode", "unknown"),
            "report_length": len(report_text),
            "input_context_length": len(input_context),
            "guideline_context_length": len(guideline_context),
            "profile_elements_count": len(profile_elements),
            "focus_needs_count": len(focus_needs),
            "selected_docs_count": len(knowledge.get("selected_docs", []) or []),
            "selected_nodes_count": len(knowledge.get("selected_nodes", []) or []),
            "evidence_cards_count": len(knowledge.get("evidence_cards", []) or []),
            "has_retrieval_trace": bool(knowledge.get("retrieval_trace")),
        }
        return eval_result

    def evaluate_from_file(
        self,
        json_path: str,
        re_retrieve: bool = False,
    ) -> EvaluationResult:
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"报告文件不存在: {json_path}")

        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        profile = payload.get("profile", {})
        results = payload.get("raw_results", {})
        if not results:
            results = {
                key: value
                for key, value in payload.items()
                if key not in ("profile", "report_id", "session_id", "user_id", "generated_at", "report_data")
            }

        if re_retrieve and self.knowledge_agent is not None:
            logger.info("重新运行分层检索...")
            results["knowledge"] = self._re_retrieve(profile, results)

        return self.evaluate(results, profile)

    def _re_retrieve(self, profile: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
        if self.knowledge_agent is None:
            return {"enabled": False, "combined_context": "", "total_hits": 0, "retrieval_mode": "disabled"}

        try:
            from multi_agent_system_v2 import UserProfile

            profile_copy = {k: v for k, v in profile.items() if k != "user_type"}
            user_profile = UserProfile(**profile_copy)

            knowledge = self.knowledge_agent.retrieve_comprehensive(
                user_profile,
                results.get("status", {}),
                results.get("risk", {}),
                results.get("factors", {}),
            )
            logger.info("重新检索完成，总命中: %d", knowledge.get("total_hits", 0))
            return knowledge
        except Exception as e:
            logger.error("重新检索失败: %s", e)
            return {"enabled": False, "combined_context": "", "total_hits": 0, "retrieval_mode": "disabled"}
