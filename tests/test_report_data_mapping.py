from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from dataclasses import dataclass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR / "code"))
sys.path.insert(0, str(BACKEND_DIR / "api"))

stub_module = types.ModuleType("multi_agent_system_v2")


@dataclass
class UserProfile:
    pass


stub_module.UserProfile = UserProfile
sys.modules["multi_agent_system_v2"] = stub_module

from mappers import to_frontend_report_data  # noqa: E402
from report_utils import load_report_payload  # noqa: E402


FULL_MARKDOWN_REPORT = """# 健康评估与照护行动计划

## 0. 报告说明
本报告基于当前信息生成，仅供参考。

## 1. 健康报告总结
1. 近期主要风险是夜间跌倒。
2. 需要开始规律活动，延缓功能下降。
3. 家属支持较好，适合逐步落实照护计划。

## 4. 健康建议

### A. 第一优先级（最紧急、最重要的事）
**1）降低夜间跌倒风险**
* **怎么做**：
  * 清理从床边到卫生间的杂物。
  * 安装小夜灯，保证夜间照明。
* **完成标准**：夜间通道明亮、无障碍。

### B. 第二优先级（重要但没那么急的事）
**1）开始规律下肢训练**
* **怎么做**：
  * 每周做三次坐站练习。
* **完成标准**：连续坚持两周。

### C. 第三优先级（长期保持的事）
**1）优化日常饮食**
* **怎么做**：少盐少油，控制零食。
* **完成标准**：家属每周一起复盘一次。

## 5. 温馨寄语
请一步一步来，先把安全和活动落实好。
"""


class ReportDataMappingTestCase(unittest.TestCase):
    def test_to_frontend_report_data_parses_markdown_recommendations_and_warm_message(self):
        report_data = to_frontend_report_data(
            {
                "status": {"status_description": "需要部分协助"},
                "risk": {"short_term_risks": [], "medium_term_risks": []},
                "factors": {
                    "functional_status": {"description": "步态变慢，需要家属协助。"},
                    "strengths": ["家属支持较好"],
                    "main_problems": ["夜间起身不稳"],
                },
                "report": FULL_MARKDOWN_REPORT,
            },
            "2026-03-25T04:44:02.871284",
        )

        self.assertEqual(report_data["generatedAt"], "2026-03-25T04:44:02.871284")
        self.assertEqual(report_data["warmMessage"], "请一步一步来，先把安全和活动落实好。")
        self.assertEqual(report_data["recommendations"]["priority1"][0]["title"], "降低夜间跌倒风险")
        self.assertIn("怎么做：清理从床边到卫生间的杂物", report_data["recommendations"]["priority1"][0]["description"])
        self.assertIn("完成标准：夜间通道明亮、无障碍。", report_data["recommendations"]["priority1"][0]["description"])
        self.assertEqual(report_data["recommendations"]["priority2"][0]["title"], "开始规律下肢训练")
        self.assertEqual(report_data["recommendations"]["priority3"][0]["title"], "优化日常饮食")

    def test_to_frontend_report_data_falls_back_to_actions_raw_payload(self):
        report_data = to_frontend_report_data(
            {
                "status": {"status_description": "需要部分协助"},
                "risk": {"short_term_risks": [], "medium_term_risks": []},
                "factors": {"functional_status": {"description": "步态变慢，需要家属协助。"}},
                "actions": {
                    "error": "JSON解析失败",
                    "raw": json.dumps(
                        {
                            "actions": [
                                {
                                    "action_id": "A1",
                                    "title": "整理居家环境",
                                    "subtitle": "移除绊倒风险",
                                    "completion_criteria": "本周内完成环境整理",
                                    "category": "安全管理",
                                }
                            ]
                        },
                        ensure_ascii=False,
                    ),
                },
                "priority": {
                    "priority_a": [{"action_id": "A1", "reason": "先降低近期跌倒风险"}],
                    "priority_b": [],
                    "priority_c": [],
                },
                "report": "# 健康评估与照护行动计划\n\n## 1. 健康报告总结\n1. 需要优先降低跌倒风险。\n",
            }
        )

        self.assertEqual(report_data["recommendations"]["priority1"][0]["title"], "整理居家环境")
        self.assertIn("移除绊倒风险", report_data["recommendations"]["priority1"][0]["description"])
        self.assertIn("先降低近期跌倒风险", report_data["recommendations"]["priority1"][0]["description"])

    def test_load_report_payload_rebuilds_incomplete_report_data(self):
        with tempfile.TemporaryDirectory() as tempdir:
            reports_dir = Path(tempdir)
            date_dir = reports_dir / "202603"
            date_dir.mkdir(parents=True, exist_ok=True)

            payload = {
                "report_id": "sample_report",
                "generated_at": "2026-03-25T04:44:02.871284",
                "raw_results": {
                    "status": {"status_description": "需要部分协助"},
                    "risk": {"short_term_risks": [], "medium_term_risks": []},
                    "factors": {"functional_status": {"description": "步态变慢，需要家属协助。"}},
                    "actions": {"error": "JSON解析失败", "raw": "{}"},
                    "priority": {"priority_a": [], "priority_b": [], "priority_c": []},
                    "report": FULL_MARKDOWN_REPORT,
                },
                "report_data": {
                    "summary": "旧版只解析到了前三段。",
                    "healthPortrait": {},
                    "riskFactors": {"shortTerm": [], "midTerm": []},
                    "recommendations": {"priority1": [], "priority2": [], "priority3": []},
                    "generatedAt": "2026-03-25T04:44:02.871284",
                },
            }

            report_file = date_dir / "report_sample_report_75岁男.json"
            report_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            loaded = load_report_payload("sample_report", reports_dir)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["report_data"]["generatedAt"], "2026-03-25T04:44:02.871284")
        self.assertEqual(loaded["report_data"]["warmMessage"], "请一步一步来，先把安全和活动落实好。")
        self.assertEqual(loaded["report_data"]["recommendations"]["priority1"][0]["title"], "降低夜间跌倒风险")


if __name__ == "__main__":
    unittest.main()
