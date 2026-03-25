#!/usr/bin/env python3
"""
单模型报告对照脚本。

流程：
1. 运行现有多智能体流程，生成基准报告；
2. 复用同一份画像和知识检索结果，运行“去角色化 + prompt 合并”的单模型基线；
3. 输出两份报告、单模型 prompt 文件、文本对比摘要；
4. 可选调用现有评测器，对比两类报告的自动化指标。
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
DATA_DIR = BACKEND_DIR / "data"

DEFAULT_EXCEL = DATA_DIR / "clhls_2018_bilingual_headers-checked.xlsx"
DEFAULT_INDEX = DATA_DIR / "rag_indexes" / "guidelines_all_index.json"
DEFAULT_OUTPUT = DATA_DIR / "output_single_model_compare"
DEFAULT_DOTENV = BACKEND_DIR / ".env"


def configure_runtime(
    rag_index: Path,
    rag_top_k: int,
    dotenv_path: Path,
    llm_config: str,
    temperature: float,
    model_override: str | None,
) -> None:
    """在导入主模块前设置运行时环境。"""
    load_dotenv(dotenv_path, override=True)

    if llm_config == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        base_url = os.getenv("OPENAI_BASE_URL", "").strip()
        model = (model_override or os.getenv("OPENAI_MODEL", "")).strip()
        if api_key:
            os.environ["DEEPSEEK_API_KEY"] = api_key
        if base_url:
            os.environ["DEEPSEEK_BASE_URL"] = base_url
        if model:
            os.environ["DEEPSEEK_MODEL"] = model
    elif llm_config == "deepseek" and model_override:
        os.environ["DEEPSEEK_MODEL"] = model_override

    os.environ["RAG_ENABLED"] = "true"
    os.environ["RAG_INDEX_PATH"] = str(rag_index)
    os.environ["RAG_TOP_K"] = str(rag_top_k)
    os.environ["LLM_TEMPERATURE_OVERRIDE"] = str(temperature)

    sys.path.insert(0, str(SCRIPT_DIR))


def summarize_eval_deltas(
    multi_eval: Dict[str, Any],
    single_eval: Dict[str, Any],
) -> Dict[str, Dict[str, float]]:
    """对齐两份评测 summary，计算差值。"""
    multi_summary = multi_eval.get("summary", {})
    single_summary = single_eval.get("summary", {})
    metric_names = sorted(set(multi_summary) | set(single_summary))
    deltas: Dict[str, Dict[str, float]] = {}
    for name in metric_names:
        multi_score = float(multi_summary.get(name, 0.0))
        single_score = float(single_summary.get(name, 0.0))
        deltas[name] = {
            "multi_agent": round(multi_score, 4),
            "single_model": round(single_score, 4),
            "delta_single_minus_multi": round(single_score - multi_score, 4),
        }
    return deltas


def append_evaluation_markdown(base_markdown: str, eval_deltas: Dict[str, Dict[str, float]]) -> str:
    """将评测对比结果拼接进 Markdown 摘要。"""
    lines = [base_markdown, "", "## 自动评测对比"]
    for metric, scores in eval_deltas.items():
        lines.append(
            "- "
            f"{metric}: multi_agent={scores['multi_agent']:.4f}, "
            f"single_model={scores['single_model']:.4f}, "
            f"delta={scores['delta_single_minus_multi']:.4f}"
        )
    return "\n".join(lines)


def save_comparison_artifacts(
    output_dir: Path,
    comparison_payload: Dict[str, Any],
    comparison_markdown: str,
) -> Dict[str, str]:
    """保存比较结果。"""
    json_path = output_dir / "comparison_summary.json"
    md_path = output_dir / "comparison_summary.md"

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(comparison_payload, file, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as file:
        file.write(comparison_markdown)

    return {
        "json_path": str(json_path),
        "markdown_path": str(md_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="比较多智能体报告与单模型基线报告",
    )
    parser.add_argument(
        "--row",
        type=int,
        default=10,
        help="Excel 数据行号，默认 10",
    )
    parser.add_argument(
        "--excel",
        type=Path,
        default=DEFAULT_EXCEL,
        help=f"Excel 数据文件路径，默认 {DEFAULT_EXCEL}",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=DEFAULT_INDEX,
        help=f"RAG 索引路径，默认 {DEFAULT_INDEX}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"输出目录，默认 {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--rag-top-k",
        type=int,
        default=5,
        help="知识检索 top-k，默认 5",
    )
    parser.add_argument(
        "--skip-eval",
        action="store_true",
        help="只生成对照报告，不跑自动评测",
    )
    parser.add_argument(
        "--dotenv",
        type=Path,
        default=DEFAULT_DOTENV,
        help=f".env 路径，默认 {DEFAULT_DOTENV}",
    )
    parser.add_argument(
        "--llm-config",
        choices=("deepseek", "openai"),
        default="deepseek",
        help="运行时使用哪组 .env 模型配置，默认 deepseek",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="可选模型名覆盖；若 llm-config=openai，则覆盖 OPENAI_MODEL",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=1.0,
        help="统一覆盖整条链路的 temperature，默认 1.0",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.excel.exists():
        raise FileNotFoundError(f"Excel 数据文件不存在: {args.excel}")
    if not args.index.exists():
        raise FileNotFoundError(f"RAG 索引文件不存在: {args.index}")

    configure_runtime(
        args.index,
        args.rag_top_k,
        args.dotenv,
        args.llm_config,
        args.temperature,
        args.model,
    )

    from evaluation.evaluator import ReportEvaluator
    from multi_agent_system_v2 import OrchestratorAgentV2, load_user_profile_from_excel, save_results
    from single_model_baseline import (
        build_report_comparison,
        build_user_id,
        comparison_to_markdown,
        run_single_model_baseline,
        save_single_model_results,
    )

    print("=" * 72)
    print("单模型 vs 多智能体 报告对照")
    print("=" * 72)
    print(f"数据文件: {args.excel}")
    print(f"RAG 索引: {args.index}")
    print(f"目标行号: {args.row}")
    print(f"输出目录: {args.output}")
    print(f"模型配置: {args.llm_config}")
    print(f"基座模型: {os.getenv('DEEPSEEK_MODEL', '')}")
    print(f"temperature: {os.getenv('LLM_TEMPERATURE_OVERRIDE', '')}")

    profile = load_user_profile_from_excel(str(args.excel), row_index=args.row)
    run_id = build_user_id(profile, row_index=args.row)
    run_dir = args.output / run_id
    multi_dir = run_dir / "multi_agent"
    single_dir = run_dir / "single_model"
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[1/4] 运行多智能体基准流程...")
    multi_started = time.time()
    orchestrator = OrchestratorAgentV2()
    multi_results = orchestrator.run(profile, verbose=True)
    multi_elapsed = time.time() - multi_started
    multi_json_path, multi_report_path = save_results(
        multi_results,
        profile,
        output_dir=str(multi_dir),
        row_index=args.row,
    )
    print(f"  完成，用时 {multi_elapsed:.1f}s")

    print(f"\n[2/4] 运行单模型基线...")
    single_started = time.time()
    single_results = run_single_model_baseline(
        profile,
        knowledge=multi_results.get("knowledge", {}),
    )
    single_elapsed = time.time() - single_started
    single_paths = save_single_model_results(
        single_results,
        profile,
        output_dir=str(single_dir),
        row_index=args.row,
        user_id=run_id,
    )
    print(f"  完成，用时 {single_elapsed:.1f}s")

    print(f"\n[3/4] 生成文本差异摘要...")
    comparison = build_report_comparison(
        multi_agent_report=multi_results.get("report", ""),
        single_model_report=single_results.get("report", ""),
    )
    comparison_payload: Dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "row_index": args.row,
        "run_id": run_id,
        "multi_agent_artifacts": {
            "json_path": multi_json_path,
            "report_path": multi_report_path,
        },
        "single_model_artifacts": single_paths,
        "comparison": comparison,
    }
    comparison_markdown = comparison_to_markdown(comparison)

    if args.skip_eval:
        print("  跳过自动评测")
    else:
        print(f"\n[4/4] 运行自动评测...")
        eval_started = time.time()
        evaluator = ReportEvaluator()
        multi_eval = evaluator.evaluate(multi_results, asdict(profile)).to_dict()
        single_eval = evaluator.evaluate(single_results, asdict(profile)).to_dict()
        eval_deltas = summarize_eval_deltas(multi_eval, single_eval)
        comparison_payload["evaluation"] = {
            "multi_agent": multi_eval,
            "single_model": single_eval,
            "summary_deltas": eval_deltas,
        }
        comparison_markdown = append_evaluation_markdown(comparison_markdown, eval_deltas)
        print(f"  完成，用时 {time.time() - eval_started:.1f}s")

    artifact_paths = save_comparison_artifacts(
        run_dir,
        comparison_payload=comparison_payload,
        comparison_markdown=comparison_markdown,
    )

    print("\n输出完成：")
    print(f"- 多智能体 JSON: {multi_json_path}")
    print(f"- 多智能体报告: {multi_report_path}")
    print(f"- 单模型 JSON: {single_paths['json_path']}")
    print(f"- 单模型报告: {single_paths['report_path']}")
    print(f"- 单模型 prompt: {single_paths['prompt_path']}")
    print(f"- 对比摘要 JSON: {artifact_paths['json_path']}")
    print(f"- 对比摘要 Markdown: {artifact_paths['markdown_path']}")


if __name__ == "__main__":
    main()
