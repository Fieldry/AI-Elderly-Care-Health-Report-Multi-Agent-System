from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR / "api"))

from counseling_service import CounselingService  # noqa: E402


class CounselingServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self._temp_dir.name)
        self.db_path = self.temp_path / "users.db"
        self.workspace_dir = self.temp_path / "workspace"
        self.workspace_dir.mkdir()
        self.service = CounselingService(
            db_path=str(self.db_path),
            workspace_dir=str(self.workspace_dir),
        )

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _execute(self, statement: str, params: tuple = ()) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(statement, params)

    def _create_users_table(self) -> None:
        self._execute(
            """
            CREATE TABLE users (
                user_id TEXT PRIMARY KEY,
                profile TEXT NOT NULL
            )
            """
        )

    def _create_sessions_table(self) -> None:
        self._execute(
            """
            CREATE TABLE sessions (
                session_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    def test_build_llm_messages_includes_profile_from_users_table(self):
        self._create_users_table()
        self._execute(
            "INSERT INTO users (user_id, profile) VALUES (?, ?)",
            (
                "elderly-1",
                json.dumps(
                    {
                        "age": 82,
                        "sex": "女",
                        "loneliness": "经常",
                        "sleep_quality": "",
                        "placeholder": "99",
                    },
                    ensure_ascii=False,
                ),
            ),
        )

        session = self.service.create_session("elderly-1")
        messages = self.service._build_llm_messages(
            session["session_id"],
            self.service._load_messages(session["session_id"]),
            "最近睡不好",
        )

        system_messages = [item["content"] for item in messages if item["role"] == "system"]
        self.assertTrue(any("age：82" in item for item in system_messages))
        self.assertTrue(any("loneliness：经常" in item for item in system_messages))
        self.assertFalse(any("sleep_quality" in item for item in system_messages))
        self.assertFalse(any("placeholder" in item for item in system_messages))

    def test_build_llm_messages_uses_latest_workspace_profile_as_fallback(self):
        self._create_sessions_table()
        self._execute(
            "INSERT INTO sessions (session_id, user_id, updated_at) VALUES (?, ?, ?)",
            ("session-latest", "elderly-2", "2026-03-25T10:00:00"),
        )

        session_dir = self.workspace_dir / "session-latest"
        session_dir.mkdir()
        (session_dir / "user_profile.json").write_text(
            json.dumps({"hypertension": "是", "hearing": "一般"}, ensure_ascii=False),
            encoding="utf-8",
        )

        counseling_session = self.service.create_session("elderly-2")
        messages = self.service._build_llm_messages(
            counseling_session["session_id"],
            self.service._load_messages(counseling_session["session_id"]),
            "总觉得心里不踏实",
        )

        system_messages = [item["content"] for item in messages if item["role"] == "system"]
        self.assertTrue(any("hypertension：是" in item for item in system_messages))
        self.assertTrue(any("hearing：一般" in item for item in system_messages))

    def test_build_llm_messages_without_profile_does_not_raise(self):
        session = self.service.create_session("elderly-3")
        messages = self.service._build_llm_messages(
            session["session_id"],
            self.service._load_messages(session["session_id"]),
            "你好",
        )

        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[-1], {"role": "user", "content": "你好"})
        self.assertEqual(len(messages), 2)


if __name__ == "__main__":
    unittest.main()
