"""报告评测模块 - 实现分源 grounding、画像覆盖与分层检索指标。"""

from evaluation.metrics import (
    DocRoutingRelevanceMetric,
    EvidenceCoverageMetric,
    NodeEvidenceRelevanceMetric,
    ProfileCoverageMetric,
    ReportGroundingMetric,
)
from evaluation.evaluator import ReportEvaluator, EvaluationResult

__all__ = [
    "ReportGroundingMetric",
    "ProfileCoverageMetric",
    "DocRoutingRelevanceMetric",
    "NodeEvidenceRelevanceMetric",
    "EvidenceCoverageMetric",
    "ReportEvaluator",
    "EvaluationResult",
]
