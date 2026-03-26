#!/usr/bin/env python3
"""
从样本 JSON 直接生成健康报告。

默认读取 data/output_selected_cases/sample_*.json，
并将 result_*.json / report_*.md 写回同一目录。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data"
DEFAULT_INPUT_DIR = DATA_DIR / "output_selected_cases"
DEFAULT_INDEX = DATA_DIR / "rag_indexes" / "guidelines_all_index.json"
DEFAULT_DOTENV = SCRIPT_DIR.parent / ".env"


def configure_runtime(
    rag_index: Path,
    rag_top_k: int,
    dotenv_path: Path,
    llm_config: str,
    temperature: float,
    model_override: str | None,
) -> None:
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


def extract_label(sample_path: Path, payload: dict[str, Any]) -> str:
    match = re.match(r"sample_\d+_(.+)$", sample_path.stem)
    if match:
        return match.group(1)

    label = payload.get("label")
    if isinstance(label, str) and label.strip():
        return label.strip()

    return sample_path.stem


def normalize_profile_dict(profile_data: dict[str, Any], valid_fields: set[str]) -> dict[str, Any]:
    alias_map = {
        "heart_disease": "coronary_heart_disease",
    }

    normalized: dict[str, Any] = {}
    for key, value in profile_data.items():
        mapped_key = alias_map.get(key, key)
        if mapped_key in valid_fields:
            normalized[mapped_key] = value
    return normalized


def load_profile_from_sample_json(sample_path: Path):
    sys.path.insert(0, str(SCRIPT_DIR))
    from multi_agent_system_v2 import UserProfile

    with open(sample_path, "r", encoding="utf-8") as file:
        payload = json.load(file)

    profile_data = payload.get("profile") or payload.get("user_profile") or payload
    if not isinstance(profile_data, dict):
        raise ValueError(f"无效样本格式: {sample_path}")

    valid_fields = {item.name for item in fields(UserProfile)}
    normalized = normalize_profile_dict(profile_data, valid_fields)
    profile = UserProfile(**normalized)
    label = extract_label(sample_path, payload)
    return profile, label, payload


def save_result(
    output_dir: Path,
    label: str,
    profile,
    results: dict[str, Any],
    sample_path: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"result_{label}.json"
    report_path = output_dir / f"report_{label}.md"

    result_payload = results.copy()
    result_payload["profile"] = asdict(profile)
    result_payload["label"] = label
    result_payload["source_sample"] = str(sample_path)

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(result_payload, file, ensure_ascii=False, indent=2)

    with open(report_path, "w", encoding="utf-8") as file:
        file.write(f"<!-- 数据来源：{sample_path.name} -->\n\n")
        file.write(results["report"])

    return json_path, report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="基于样本 JSON 生成健康报告")
    parser.add_argument(
        "--input-dir",
        type=str,
        default=str(DEFAULT_INPUT_DIR),
        help=f"样本 JSON 目录（默认: {DEFAULT_INPUT_DIR}）",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="输出目录（默认与 input-dir 相同）",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="sample_*.json",
        help="样本文件匹配模式（默认: sample_*.json）",
    )
    parser.add_argument(
        "--index",
        type=str,
        default=str(DEFAULT_INDEX),
        help=f"RAG 索引文件（默认: {DEFAULT_INDEX.name}）",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="RAG 检索 Top-K（默认: 5）",
    )
    parser.add_argument(
        "--dotenv",
        type=str,
        default=str(DEFAULT_DOTENV),
        help=f".env 路径（默认: {DEFAULT_DOTENV}）",
    )
    parser.add_argument(
        "--llm-config",
        choices=("deepseek", "openai"),
        default="openai",
        help="模型配置（默认: openai）",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5",
        help="模型名覆盖（默认: gpt-5）",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=1.0,
        help="统一覆盖整条链路 temperature（默认: 1.0）",
    )

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output) if args.output else input_dir
    rag_index = Path(args.index)
    dotenv_path = Path(args.dotenv)

    if not input_dir.exists():
        print(f"❌ 样本目录不存在: {input_dir}")
        return 1
    if not rag_index.exists():
        print(f"❌ RAG 索引不存在: {rag_index}")
        return 1

    sample_files = sorted(input_dir.glob(args.pattern))
    if not sample_files:
        print(f"❌ 未找到样本文件: {input_dir / args.pattern}")
        return 1

    configure_runtime(
        rag_index=rag_index,
        rag_top_k=args.top_k,
        dotenv_path=dotenv_path,
        llm_config=args.llm_config,
        temperature=args.temperature,
        model_override=args.model,
    )

    sys.path.insert(0, str(SCRIPT_DIR))
    from multi_agent_system_v2 import OrchestratorAgentV2

    print("=" * 60)
    print("  样本 JSON 报告生成")
    print("=" * 60)
    print(f"  输入目录: {input_dir}")
    print(f"  输出目录: {output_dir}")
    print(f"  样本数量: {len(sample_files)}")
    print(f"  模型配置: {args.llm_config}")
    print(f"  基座模型: {os.getenv('DEEPSEEK_MODEL', '')}")
    print(f"  temperature: {os.getenv('LLM_TEMPERATURE_OVERRIDE', '')}")

    orchestrator = OrchestratorAgentV2()
    failed = False

    for index, sample_path in enumerate(sample_files, start=1):
        print(f"\n{'=' * 60}")
        print(f"  处理样本 {index}/{len(sample_files)}: {sample_path.name}")
        print(f"{'=' * 60}")

        try:
            profile, label, _payload = load_profile_from_sample_json(sample_path)
            print(f"  标签: {label}")
            print(f"  画像: {profile.age}岁 {profile.sex}")

            results = orchestrator.run(profile, verbose=True)
            json_path, report_path = save_result(output_dir, label, profile, results, sample_path)

            print(f"\n✅ 已保存：")
            print(f"   - JSON: {json_path}")
            print(f"   - 报告: {report_path}")
        except Exception as exc:
            failed = True
            print(f"\n❌ 处理失败: {sample_path.name}")
            print(f"   错误: {exc}")

    print(f"\n{'=' * 60}")
    if failed:
        print("  ⚠️ 部分样本失败")
        print(f"  输出目录: {output_dir}")
        print(f"{'=' * 60}")
        return 1

    print("  ✅ 全部完成")
    print(f"  输出目录: {output_dir}")
    print(f"{'=' * 60}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
