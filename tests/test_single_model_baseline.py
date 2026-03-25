from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR / "code"))

from single_model_baseline import (  # noqa: E402
    build_report_comparison,
    build_single_model_system_prompt,
    collect_stage_prompts,
    strip_role_playing,
)


class SingleModelBaselineTestCase(unittest.TestCase):
    def test_strip_role_playing_keeps_instruction_body(self):
        prompt = "你是健康评估专家，负责检查报告的一致性。\n\n【规则】\n1. 检查字段。"
        stripped = strip_role_playing(prompt)

        self.assertTrue(stripped.startswith("负责检查报告的一致性。"))
        self.assertIn("【规则】", stripped)
        self.assertNotIn("你是健康评估专家", stripped)

    def test_collect_stage_prompts_removes_leading_role_prefix(self):
        stage_prompts = collect_stage_prompts()

        self.assertEqual(len(stage_prompts), 7)
        self.assertFalse(stage_prompts[0].stripped_prompt.startswith("你是"))
        self.assertIn("【输出格式】JSON", stage_prompts[0].stripped_prompt)
        self.assertIn("【报告结构】", stage_prompts[-1].stripped_prompt)

    def test_build_single_model_system_prompt_contains_all_stage_blocks(self):
        system_prompt = build_single_model_system_prompt()

        self.assertIn("Stage 1: 状态判定", system_prompt)
        self.assertIn("Stage 7: 报告生成", system_prompt)
        self.assertIn("最终只输出一份 Markdown 格式", system_prompt)
        self.assertNotIn("你是失能状态判定专家", system_prompt)

    def test_build_report_comparison_tracks_structure_deltas(self):
        multi_report = """# 健康评估与照护行动计划

## 0. 报告说明
说明

## 1. 健康报告总结
总结
"""
        single_report = """# 健康评估与照护行动计划

## 1. 健康报告总结
总结

## 4. 健康建议
建议
"""
        comparison = build_report_comparison(multi_report, single_report)

        self.assertIn("similarity_ratio", comparison)
        self.assertFalse(comparison["section_presence_delta"]["report_notice"]["single_model"])
        self.assertTrue(comparison["section_presence_delta"]["actions"]["single_model"])
        self.assertTrue(any("single_model_report.md" in line for line in comparison["diff_excerpt"]))


if __name__ == "__main__":
    unittest.main()
