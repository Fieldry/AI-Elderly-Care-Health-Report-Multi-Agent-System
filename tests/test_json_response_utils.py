from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR / "code"))

from evaluation.utils import call_llm_json  # noqa: E402
from json_response_utils import parse_json_response_loose  # noqa: E402
from multi_agent_system_v2 import BaseAgent  # noqa: E402


class JsonResponseUtilsTestCase(unittest.TestCase):
    def test_parse_json_response_loose_handles_markdown_and_prefix_text(self):
        text = "说明如下：\n```json\n{\"status\": 1, \"items\": [1, 2]}\n```"
        parsed = parse_json_response_loose(text)
        self.assertEqual(parsed["status"], 1)
        self.assertEqual(parsed["items"], [1, 2])

    def test_parse_json_response_loose_handles_python_like_dict(self):
        text = "结果：{'status': 1, 'passed': True, 'items': ['A',],}"
        parsed = parse_json_response_loose(text)
        self.assertEqual(parsed["status"], 1)
        self.assertTrue(parsed["passed"])
        self.assertEqual(parsed["items"], ["A"])

    @patch("evaluation.utils.call_llm")
    def test_call_llm_json_retries_after_parse_failure(self, mock_call_llm):
        mock_call_llm.side_effect = [
            "这不是 JSON",
            '{"ok": true, "value": 3}',
        ]
        parsed = call_llm_json("请输出 JSON", parse_attempts=2)
        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["value"], 3)

    def test_base_agent_call_llm_json_retries(self):
        agent = BaseAgent("TestAgent", "system")
        responses = iter(["不是 JSON", '{"result": "ok"}'])
        agent.call_llm = lambda user_prompt, temperature=0.3, max_tokens=2048: next(responses)  # type: ignore[method-assign]

        parsed = agent.call_llm_json("请输出 JSON", parse_attempts=2)
        self.assertEqual(parsed["result"], "ok")


if __name__ == "__main__":
    unittest.main()
