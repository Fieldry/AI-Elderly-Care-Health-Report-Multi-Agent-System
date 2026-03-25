#!/usr/bin/env python3
"""
报告评测 CLI 工具。

用法:
    # 评测单个报告
    python evaluate_report.py --input report.json

    # 评测目录下所有报告
    python evaluate_report.py --input ./reports/202603/

    # 指定输出文件
    python evaluate_report.py --input report.json --output eval_result.json

    # 启用 RAG 重新检索（当原始报告无 RAG 数据时）
    python evaluate_report.py --input report.json --re-retrieve

    # 只运行部分指标
    python evaluate_report.py --input report.json --metrics input_grounding,profile_coverage
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# 确保 code 目录在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

from evaluation.evaluator import ReportEvaluator

logger = logging.getLogger(__name__)


def normalize_metric_names(raw_metrics: set[str]) -> set[str]:
    alias_map = {
        "faithfulness": {"input_grounding", "guideline_grounding"},
        "coverage": {"profile_coverage"},
        "context_relevance": {"doc_routing_relevance", "node_evidence_relevance", "evidence_coverage"},
        "doc_routing": {"doc_routing_relevance"},
        "node_relevance": {"node_evidence_relevance"},
    }
    normalized: set[str] = set()
    for metric in raw_metrics:
        name = metric.strip()
        normalized.update(alias_map.get(name, {name}))
    return normalized


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def find_report_files(input_path: str) -> List[Path]:
    """查找报告 JSON 文件。"""
    p = Path(input_path)
    if p.is_file() and p.suffix == ".json":
        return [p]
    if p.is_dir():
        files = sorted(p.rglob("*.json"))
        # 过滤掉非报告文件（如索引文件）
        return [f for f in files if "report" in f.name or "result" in f.name]
    print(f"错误: {input_path} 不是有效的文件或目录")
    sys.exit(1)


def init_evaluator(re_retrieve: bool = False) -> ReportEvaluator:
    """初始化评测器，可选加载 RAG agent。"""
    rag_agent = None
    knowledge_agent = None

    if re_retrieve:
        try:
            from rag.agent import PageIndexRAGAgent
            from knowledge_agent import KnowledgeAgent

            rag_index_path = os.getenv(
                "RAG_INDEX_PATH",
                str(Path(__file__).resolve().parent.parent / "data" / "rag_indexes" / "combined_index.json"),
            )
            if Path(rag_index_path).exists():
                rag_agent = PageIndexRAGAgent()
                rag_agent.load_index(rag_index_path)
                knowledge_agent = KnowledgeAgent(rag_agent)
                logger.info("RAG agent 已加载: %s", rag_index_path)
            else:
                logger.warning("RAG 索引文件不存在: %s，将跳过重新检索", rag_index_path)
        except Exception as e:
            logger.warning("无法初始化 RAG agent: %s", e)

    return ReportEvaluator(rag_agent=rag_agent, knowledge_agent=knowledge_agent)


def evaluate_single(
    evaluator: ReportEvaluator,
    json_path: Path,
    re_retrieve: bool,
    metrics: set,
) -> Dict[str, Any]:
    """评测单个报告，返回结果字典。"""
    print(f"\n{'='*60}")
    print(f"评测: {json_path.name}")
    print(f"{'='*60}")

    result = evaluator.evaluate_from_file(
        str(json_path),
        re_retrieve=re_retrieve,
    )

    # 根据指定的 metrics 过滤
    if "input_grounding" not in metrics:
        result.input_grounding = None
    if "guideline_grounding" not in metrics:
        result.guideline_grounding = None
    if "profile_coverage" not in metrics:
        result.profile_coverage = None
    if "doc_routing_relevance" not in metrics:
        result.doc_routing_relevance = None
    if "node_evidence_relevance" not in metrics:
        result.node_evidence_relevance = None
    if "evidence_coverage" not in metrics:
        result.evidence_coverage = None

    # 打印摘要
    summary = result.summary()
    print("\n📊 评测结果:")
    for name, score in summary.items():
        bar = "█" * int(score * 20) + "░" * (20 - int(score * 20))
        print(f"  {name:20s}: {score:.4f} [{bar}]")

    if result.input_grounding:
        print(f"\n  Input Grounding 详情:")
        print(f"    总陈述数: {result.input_grounding.total_statements}")
        print(f"    被支持数: {result.input_grounding.supported_statements}")

    if result.guideline_grounding:
        print(f"\n  Guideline Grounding 详情:")
        print(f"    总陈述数: {result.guideline_grounding.total_statements}")
        print(f"    被支持数: {result.guideline_grounding.supported_statements}")

    if result.profile_coverage:
        print(f"\n  Profile Coverage 详情:")
        print(f"    总要素数: {result.profile_coverage.total_elements}")
        print(f"    被覆盖数: {result.profile_coverage.covered_elements}")
        uncovered = [
            e["element"]
            for e in result.profile_coverage.elements
            if not e["covered"]
        ]
        if uncovered:
            print(f"    未覆盖: {', '.join(uncovered)}")

    if result.doc_routing_relevance:
        print(f"\n  Doc Routing Relevance 详情:")
        print(f"    总文档数: {result.doc_routing_relevance.total_docs}")
        print(f"    相关文档数: {result.doc_routing_relevance.relevant_docs}")

    if result.node_evidence_relevance:
        print(f"\n  Node Evidence Relevance 详情:")
        print(f"    总节点数: {result.node_evidence_relevance.total_nodes}")
        print(f"    产出证据节点数: {result.node_evidence_relevance.covered_nodes}")

    if result.evidence_coverage:
        print(f"\n  Evidence Coverage 详情:")
        print(f"    总需求数: {result.evidence_coverage.total_needs}")
        print(f"    被覆盖需求数: {result.evidence_coverage.covered_needs}")

    return {
        "file": str(json_path),
        "evaluated_at": datetime.now().isoformat(),
        **result.to_dict(),
    }


def main():
    parser = argparse.ArgumentParser(description="健康报告评测工具")
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="报告 JSON 文件路径或包含报告的目录",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="评测结果输出文件路径（默认: 输入文件同目录下的 eval_*.json）",
    )
    parser.add_argument(
        "--re-retrieve",
        action="store_true",
        help="重新运行 RAG 检索（当原始报告无 RAG 数据时使用）",
    )
    parser.add_argument(
        "--metrics", "-m",
        default="input_grounding,guideline_grounding,profile_coverage,doc_routing_relevance,node_evidence_relevance,evidence_coverage",
        help="要运行的指标，逗号分隔",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细日志",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    metrics = normalize_metric_names({m.strip() for m in args.metrics.split(",")})
    report_files = find_report_files(args.input)

    if not report_files:
        print("未找到报告文件")
        sys.exit(1)

    print(f"找到 {len(report_files)} 个报告文件")

    evaluator = init_evaluator(re_retrieve=args.re_retrieve)
    all_results: List[Dict[str, Any]] = []

    for json_path in report_files:
        try:
            result = evaluate_single(evaluator, json_path, args.re_retrieve, metrics)
            all_results.append(result)
        except Exception as e:
            logger.error("评测 %s 失败: %s", json_path.name, e)
            all_results.append({
                "file": str(json_path),
                "error": str(e),
            })

    # 汇总统计
    if len(all_results) > 1:
        print(f"\n{'='*60}")
        print(f"汇总（共 {len(all_results)} 份报告）")
        print(f"{'='*60}")
        for metric_name in [
            "input_grounding",
            "guideline_grounding",
            "profile_coverage",
            "doc_routing_relevance",
            "node_evidence_relevance",
            "evidence_coverage",
        ]:
            scores = [
                r["summary"][metric_name]
                for r in all_results
                if "summary" in r and metric_name in r.get("summary", {})
            ]
            if scores:
                avg = sum(scores) / len(scores)
                min_s = min(scores)
                max_s = max(scores)
                print(f"  {metric_name:20s}: avg={avg:.4f}  min={min_s:.4f}  max={max_s:.4f}")

    # 保存结果
    if args.output:
        output_path = Path(args.output)
    else:
        input_p = Path(args.input)
        if input_p.is_dir():
            output_path = input_p / f"eval_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        else:
            output_path = input_p.parent / f"eval_{input_p.stem}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_data = all_results[0] if len(all_results) == 1 else {"reports": all_results}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 评测结果已保存: {output_path}")


if __name__ == "__main__":
    main()
