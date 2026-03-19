from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import api.server as server
from workspace_manager import WorkspaceManager


def build_fake_workflow_results() -> dict:
    return {
        "status": {
            "status_description": "需要部分协助",
        },
        "risk": {
            "short_term_risks": [
                {
                    "risk": "跌倒",
                    "severity": "高",
                    "trigger": "步态不稳",
                    "prevention_key": "清理环境并加强陪护",
                    "timeframe": "1-4周",
                }
            ],
            "medium_term_risks": [
                {
                    "risk": "功能继续下降",
                    "severity": "中",
                    "chain": "活动量减少可能进一步削弱下肢力量",
                    "prevention_key": "规律训练和定期复评",
                    "timeframe": "1-6月",
                }
            ],
            "risk_summary": "存在跌倒与活动能力下降风险",
        },
        "factors": {
            "functional_status": {
                "description": "步态变慢，需要部分协助。",
            },
            "strengths": ["家属支持较好"],
            "main_problems": ["步态不稳"],
        },
        "actions": {
            "actions": [
                {
                    "action_id": "act_1",
                    "title": "整理居家环境",
                    "category": "安全管理",
                    "subtitle": "移除地面绊倒风险",
                    "completion_criteria": "本周内完成环境整理",
                }
            ]
        },
        "priority": {
            "priority_a": [
                {
                    "action_id": "act_1",
                    "reason": "先降低近期跌倒风险",
                }
            ],
            "priority_b": [],
            "priority_c": [],
        },
        "report": "## 1. 健康报告总结\n整体情况需要持续观察。\n\n## 2. 详细分析\n建议加强安全管理。",
    }


class APIServerTestCase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)

        self.base_dir = Path(self.tempdir.name)
        self.db_path = self.base_dir / "users.db"
        self.reports_dir = self.base_dir / "reports"
        self.workspace_dir = self.base_dir / "workspace"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        workspace_dir = self.workspace_dir

        class TempWorkspaceManager(WorkspaceManager):
            def __init__(self, base_dir: str = "workspace"):
                super().__init__(base_dir=str(workspace_dir))

        self.patches = [
            patch.object(server, "DB_PATH", str(self.db_path)),
            patch.object(server, "REPORTS_DIR", self.reports_dir),
            patch.object(server, "WorkspaceManager", TempWorkspaceManager),
        ]

        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)

        self.client_context = TestClient(server.app)
        self.client = self.client_context.__enter__()
        self.addCleanup(self.client_context.__exit__, None, None, None)

        self.conversation_manager = self.client.app.state.conversation_manager
        self.workspace_manager = self.client.app.state.workspace_manager

    def test_chat_progress_returns_real_progress_data(self):
        user_id = self.conversation_manager.new_user()
        session_id = self.conversation_manager.new_session(user_id)
        self.conversation_manager.store.update_profile(
            user_id,
            {
                "age": 82,
                "sex": "男",
                "province": "北京",
                "residence": "城市",
                "education_years": 9,
                "marital_status": "已婚",
            },
        )

        response = self.client.get(f"/chat/progress/{session_id}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["state"], "greeting")
        self.assertGreater(body["progress"], 0.0)
        self.assertIn("基本信息", body["completedGroups"])
        self.assertIn("健康限制", body["pendingGroups"])
        self.assertIn("健康限制", body["missingFields"])

    def test_family_reports_filters_by_elderly_id_and_sorts(self):
        elderly_id = self.conversation_manager.new_user()
        other_elderly_id = self.conversation_manager.new_user()
        session_old = self.conversation_manager.new_session(elderly_id)
        session_new = self.conversation_manager.new_session(elderly_id)
        session_other = self.conversation_manager.new_session(other_elderly_id)

        for session_id, user_id in [
            (session_old, elderly_id),
            (session_new, elderly_id),
            (session_other, other_elderly_id),
        ]:
            self.workspace_manager.create_metadata(
                session_id,
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "created_at": "2026-03-19T10:00:00",
                    "status": "active",
                    "title": "评估记录",
                },
            )

        self.workspace_manager.save_report(
            session_old,
            {
                "report_id": "old-report",
                "generated_at": "2026-03-19T10:00:00",
                "report_data": {"summary": "较早报告"},
            },
            "json",
        )
        self.workspace_manager.save_report(
            session_new,
            {
                "report_id": "new-report",
                "generated_at": "2026-03-19T12:00:00",
                "report_data": {"summary": "最新报告"},
            },
            "json",
        )
        self.workspace_manager.save_report(
            session_other,
            {
                "report_id": "other-report",
                "generated_at": "2026-03-19T13:00:00",
                "report_data": {"summary": "其他老人报告"},
            },
            "json",
        )

        response = self.client.get(f"/family/reports/{elderly_id}")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([item["id"] for item in body["data"]], ["new-report", "old-report"])
        self.assertTrue(all(item["content"]["report_id"] != "other-report" for item in body["data"]))

    def test_generate_report_for_elderly_persists_profile_and_workspace_report(self):
        elderly_id = self.conversation_manager.new_user()
        fake_results = build_fake_workflow_results()

        with patch.object(
            server,
            "_run_report_workflow",
            new=AsyncMock(return_value=fake_results),
        ):
            response = self.client.post(
                f"/report/generate/{elderly_id}",
                json={
                    "age": 84,
                    "sex": "男",
                    "residence": "农村",
                    "education_years": 6,
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("reportId", body)
        self.assertIn("sessionId", body)
        self.assertEqual(body["report"]["summary"], "整体情况需要持续观察。")

        stored_profile = self.conversation_manager.store.get_profile(elderly_id)
        self.assertEqual(stored_profile.age, 84)
        self.assertEqual(stored_profile.residence, "农村")

        session_id = body["sessionId"]
        metadata = self.workspace_manager.get_session_metadata(session_id)
        self.assertEqual(metadata["user_id"], elderly_id)
        self.assertTrue(metadata["has_profile"])
        self.assertTrue(metadata["has_report"])
        self.assertEqual(len(self.workspace_manager.get_report_files(session_id)), 1)

    def test_auth_routes_keep_demo_behavior(self):
        invalid_response = self.client.post(
            "/auth/login",
            json={"phone": "", "password": ""},
        )
        self.assertEqual(invalid_response.status_code, 400)

        login_response = self.client.post(
            "/auth/login",
            json={"phone": "13800138000", "password": "123456"},
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.json()["role"], "family")

        logout_response = self.client.post("/auth/logout")
        self.assertEqual(logout_response.status_code, 200)
        self.assertEqual(logout_response.json(), {"success": True})


if __name__ == "__main__":
    unittest.main()
