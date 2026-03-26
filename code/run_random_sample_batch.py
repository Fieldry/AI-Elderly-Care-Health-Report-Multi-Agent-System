#!/usr/bin/env python3
"""
随机抽样批量运行报告生成与评测。

特点：
- 随机抽取指定数量样本；
- 默认使用 run_and_evaluate.py 子进程执行单样本生成+评测；
- 支持从较高并发开始，若出现失败则自动降低并发，直到单线程；
- 运行过程中持续保存 manifest、日志和汇总文件。
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence

import pandas as pd

from run_parallel_batches import RowRunResult, analyze_outputs, latest_match, render_markdown


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
DATA_DIR = BACKEND_ROOT / "data"
DEFAULT_EXCEL = DATA_DIR / "clhls_2018_bilingual_headers-checked.xlsx"
DEFAULT_INDEX = DATA_DIR / "rag_indexes" / "guidelines_all_index.json"
DEFAULT_OUTPUT_ROOT = DATA_DIR / "output_random_batch"
DEFAULT_DOTENV = BACKEND_ROOT / ".env"
DEFAULT_SAMPLE_SIZE = 100
DEFAULT_INITIAL_PARALLEL = 5
DEFAULT_MIN_PARALLEL = 1
DEFAULT_TOP_K = 5
DEFAULT_SEED = 20260326
DEFAULT_METRICS = (
    "input_grounding,guideline_grounding,profile_coverage,"
    "doc_routing_relevance,node_evidence_relevance,evidence_coverage"
)
RETRYABLE_MARKERS = (
    "429",
    "rate limit",
    "timeout",
    "timed out",
    "connection",
    "temporarily unavailable",
    "server disconnected",
    "governor",
    "502",
    "503",
    "504",
)


def sample_rows(excel_path: Path, sample_size: int, seed: int) -> List[int]:
    df = pd.read_excel(excel_path)
    row_count = len(df.iloc[1:].reset_index(drop=True))
    if sample_size > row_count:
        raise ValueError(f"sample_size={sample_size} 超过可用样本数 {row_count}")
    rng = random.Random(seed)
    return rng.sample(list(range(row_count)), sample_size)


def build_command(
    python_bin: Path,
    row: int,
    excel_path: Path,
    rag_index: Path,
    output_dir: Path,
    metrics: str,
    top_k: int,
    dotenv_path: Path,
    llm_config: str,
    temperature: float,
    model_override: str | None,
) -> List[str]:
    cmd = [
        str(python_bin),
        str(SCRIPT_DIR / "run_and_evaluate.py"),
        "--row",
        str(row),
        "--excel",
        str(excel_path),
        "--index",
        str(rag_index),
        "--output",
        str(output_dir),
        "--top-k",
        str(top_k),
        "--metrics",
        metrics,
        "--dotenv",
        str(dotenv_path),
        "--llm-config",
        llm_config,
        "--temperature",
        str(temperature),
    ]
    if model_override:
        cmd.extend(["--model", model_override])
    return cmd


def read_log_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def is_retryable_failure(result: RowRunResult) -> bool:
    if result.error is None:
        return False
    log_text = read_log_text(Path(result.log_path)).lower()
    if any(marker in log_text for marker in RETRYABLE_MARKERS):
        return True
    error_text = str(result.error).lower()
    return any(marker in error_text for marker in RETRYABLE_MARKERS)


def run_batch(
    batch_rows: Sequence[int],
    batch_id: int,
    python_bin: Path,
    excel_path: Path,
    rag_index: Path,
    output_dir: Path,
    logs_dir: Path,
    metrics: str,
    top_k: int,
    dotenv_path: Path,
    llm_config: str,
    temperature: float,
    model_override: str | None,
) -> List[RowRunResult]:
    active: List[Dict[str, Any]] = []
    for row in batch_rows:
        log_path = logs_dir / f"batch_{batch_id:03d}_row_{row:05d}.log"
        cmd = build_command(
            python_bin=python_bin,
            row=row,
            excel_path=excel_path,
            rag_index=rag_index,
            output_dir=output_dir,
            metrics=metrics,
            top_k=top_k,
            dotenv_path=dotenv_path,
            llm_config=llm_config,
            temperature=temperature,
            model_override=model_override,
        )
        log_file = open(log_path, "w", encoding="utf-8")
        started_at = time.time()
        process = subprocess.Popen(
            cmd,
            cwd=str(BACKEND_ROOT),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        active.append(
            {
                "row": row,
                "process": process,
                "log_path": log_path,
                "log_file": log_file,
                "started_at": started_at,
            }
        )

    results: List[RowRunResult] = []
    for item in active:
        process = item["process"]
        returncode = process.wait()
        item["log_file"].close()
        duration = time.time() - item["started_at"]
        row = item["row"]

        result_json = latest_match(output_dir, f"result_row{row}_*.json")
        report_md = latest_match(output_dir, f"report_row{row}_*.md")
        eval_json = latest_match(output_dir, f"eval_result_row{row}_*.json")
        error = None
        if returncode != 0:
            error = f"subprocess exited with code {returncode}"
        elif result_json is None:
            error = "result json not found"
        elif report_md is None:
            error = "report markdown not found"
        elif eval_json is None:
            error = "evaluation result file not found"

        results.append(
            RowRunResult(
                row=row,
                batch_id=batch_id,
                returncode=returncode,
                duration_seconds=round(duration, 2),
                log_path=str(item["log_path"]),
                result_json=str(result_json) if result_json else None,
                report_md=str(report_md) if report_md else None,
                eval_json=str(eval_json) if eval_json else None,
                error=error,
            )
        )

    return sorted(results, key=lambda item: item.row)


def persist_manifest(run_dir: Path, manifest: Dict[str, Any]) -> None:
    with open(run_dir / "run_manifest.json", "w", encoding="utf-8") as file:
        json.dump(manifest, file, ensure_ascii=False, indent=2)


def finalize_summary(run_dir: Path, artifacts_dir: Path, run_results: List[RowRunResult]) -> Dict[str, Any]:
    summary = analyze_outputs(artifacts_dir, run_results)
    with open(run_dir / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)
    with open(run_dir / "summary.md", "w", encoding="utf-8") as file:
        file.write(render_markdown(summary))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="随机抽样批量生成报告并评测")
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE, help="随机抽样数量")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="随机种子")
    parser.add_argument("--initial-parallel", type=int, default=DEFAULT_INITIAL_PARALLEL, help="初始并发数")
    parser.add_argument("--min-parallel", type=int, default=DEFAULT_MIN_PARALLEL, help="最低并发数")
    parser.add_argument("--max-retries", type=int, default=2, help="单个样本最大重试次数")
    parser.add_argument("--excel", type=str, default=str(DEFAULT_EXCEL), help="Excel 路径")
    parser.add_argument("--index", type=str, default=str(DEFAULT_INDEX), help="RAG 索引路径")
    parser.add_argument("--output-root", type=str, default=str(DEFAULT_OUTPUT_ROOT), help="输出根目录")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="RAG top-k")
    parser.add_argument("--metrics", type=str, default=DEFAULT_METRICS, help="评测指标列表")
    parser.add_argument("--dotenv", type=str, default=str(DEFAULT_DOTENV), help=".env 路径")
    parser.add_argument("--llm-config", choices=("deepseek", "openai"), default="openai", help="模型配置来源")
    parser.add_argument("--model", type=str, default=None, help="可选模型名覆盖")
    parser.add_argument("--temperature", type=float, default=1.0, help="整条链路 temperature")
    args = parser.parse_args()

    excel_path = Path(args.excel).resolve()
    rag_index = Path(args.index).resolve()
    output_root = Path(args.output_root).resolve()
    dotenv_path = Path(args.dotenv).resolve()
    venv_python = BACKEND_ROOT / ".venv" / "bin" / "python"
    python_bin = venv_python if venv_python.exists() else Path(sys.executable)

    if not excel_path.exists():
        raise FileNotFoundError(f"excel not found: {excel_path}")
    if not rag_index.exists():
        raise FileNotFoundError(f"rag index not found: {rag_index}")
    if args.initial_parallel < args.min_parallel or args.min_parallel <= 0:
        raise ValueError("parallel 参数不合法")

    sampled_rows = sample_rows(excel_path, args.sample_size, args.seed)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_root / f"run_{timestamp}"
    artifacts_dir = run_dir / "artifacts"
    logs_dir = run_dir / "logs"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    manifest: Dict[str, Any] = {
        "created_at": datetime.now().isoformat(),
        "sample_size": args.sample_size,
        "seed": args.seed,
        "sampled_rows": sampled_rows,
        "initial_parallel": args.initial_parallel,
        "min_parallel": args.min_parallel,
        "max_retries": args.max_retries,
        "excel_path": str(excel_path),
        "rag_index": str(rag_index),
        "dotenv_path": str(dotenv_path),
        "llm_config": args.llm_config,
        "model": args.model,
        "temperature": args.temperature,
        "run_dir": str(run_dir),
        "batches": [],
        "completed_rows": [],
        "failed_rows": [],
    }
    persist_manifest(run_dir, manifest)

    print(f"随机批跑开始: sample_size={args.sample_size} seed={args.seed}")
    print(f"sampled_rows={sampled_rows}")
    print(f"模型配置={args.llm_config} model={args.model or '(from .env)'} temperature={args.temperature}")
    print(f"输出目录: {run_dir}")

    pending_rows = list(sampled_rows)
    attempt_counter: Counter[int] = Counter()
    completed_rows: set[int] = set()
    failed_rows: Dict[int, str] = {}
    run_results: List[RowRunResult] = []
    current_parallel = args.initial_parallel
    batch_id = 1
    overall_started = time.time()

    while pending_rows:
        used_parallel = current_parallel
        batch_rows = pending_rows[:used_parallel]
        pending_rows = pending_rows[used_parallel:]

        print(f"\n=== Batch {batch_id} parallel={used_parallel} rows={batch_rows} ===")
        batch_started = time.time()
        batch_results = run_batch(
            batch_rows=batch_rows,
            batch_id=batch_id,
            python_bin=python_bin,
            excel_path=excel_path,
            rag_index=rag_index,
            output_dir=artifacts_dir,
            logs_dir=logs_dir,
            metrics=args.metrics,
            top_k=args.top_k,
            dotenv_path=dotenv_path,
            llm_config=args.llm_config,
            temperature=args.temperature,
            model_override=args.model,
        )
        batch_duration = round(time.time() - batch_started, 2)

        retry_rows: List[int] = []
        batch_failures = 0
        retryable_failures = 0
        for result in batch_results:
            if result.error is None:
                if result.row not in completed_rows:
                    run_results.append(result)
                    completed_rows.add(result.row)
                continue

            batch_failures += 1
            attempt_counter[result.row] += 1
            can_retry = attempt_counter[result.row] <= args.max_retries
            retryable = can_retry and is_retryable_failure(result)

            if retryable:
                retry_rows.append(result.row)
                retryable_failures += 1
            elif can_retry and current_parallel > args.min_parallel:
                retry_rows.append(result.row)
            else:
                run_results.append(result)
                failed_rows[result.row] = result.error or "unknown error"

        if retry_rows:
            current_parallel = max(current_parallel - 1, args.min_parallel)
            pending_rows = retry_rows + pending_rows

        manifest["batches"].append(
            {
                "batch_id": batch_id,
                "rows": batch_rows,
                "parallel": used_parallel,
                "duration_seconds": batch_duration,
                "results": [asdict(item) for item in batch_results],
                "retry_rows": retry_rows,
                "batch_failures": batch_failures,
                "retryable_failures": retryable_failures,
                "remaining_rows": list(pending_rows),
                "next_parallel": current_parallel,
            }
        )
        manifest["completed_rows"] = sorted(completed_rows)
        manifest["failed_rows"] = [{"row": row, "error": err} for row, err in sorted(failed_rows.items())]
        persist_manifest(run_dir, manifest)

        print(
            f"Batch {batch_id} 完成: success={len(batch_rows) - batch_failures}/{len(batch_rows)} "
            f"retry={len(retry_rows)} duration={batch_duration:.1f}s next_parallel={current_parallel}"
        )
        batch_id += 1

    summary = finalize_summary(run_dir, artifacts_dir, run_results)
    summary["total_duration_seconds"] = round(time.time() - overall_started, 2)
    with open(run_dir / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)

    print("\n=== 全部完成 ===")
    print(f"完成数量: {len(summary['completed_rows'])}/{len(sampled_rows)}")
    print(f"失败数量: {summary['failure_count']}")
    print(f"总耗时: {summary['total_duration_seconds']:.1f}s")
    print(f"汇总文件: {run_dir / 'summary.md'}")
    return 0 if summary["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
