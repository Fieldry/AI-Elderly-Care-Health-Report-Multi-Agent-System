"""
报告评测模块 - 实现 Faithfulness、Profile Coverage、Context Relevance 三个指标。
"""

from evaluation.metrics import (
    FaithfulnessMetric,
    ProfileCoverageMetric,
    ContextRelevanceMetric,
)
from evaluation.evaluator import ReportEvaluator, EvaluationResult

__all__ = [
    "FaithfulnessMetric",
    "ProfileCoverageMetric",
    "ContextRelevanceMetric",
    "ReportEvaluator",
    "EvaluationResult",
]
