"""
心理咨询（情感陪伴）服务。

提供多轮对话式心理咨询功能，调用 DeepSeek LLM，
支持同步与流式两种响应模式，对话历史持久化到 SQLite。
"""

from __future__ import annotations

import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

# ── LLM 配置 ─────────────────────────────────────────────

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
LLM_TIMEOUT_SECONDS = max(float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "180")), 1.0)

# 上下文窗口：发送给 LLM 的最大历史消息数（不含 system prompt）
MAX_HISTORY_MESSAGES = 40

# ── 系统提示词（占位，可通过环境变量覆盖）──────────────────

_DEFAULT_SYSTEM_PROMPT = """\
你是一位温暖、耐心的心理咨询师，专门为老年人提供情感陪伴和心理支持。
请用简单易懂的语言，关心老人的情绪和生活状况。
（占位提示词 - 后续替换为正式版本）
"""

COUNSELING_SYSTEM_PROMPT = os.getenv("COUNSELING_SYSTEM_PROMPT", _DEFAULT_SYSTEM_PROMPT)


class CounselingService:
    """心理咨询服务：管理咨询会话、调用 LLM、持久化消息。"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        self._init_db()

    # ── 数据库 ────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS counseling_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id    TEXT NOT NULL,
                    title      TEXT NOT NULL DEFAULT '心理咨询',
                    status     TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_counseling_sessions_user
                ON counseling_sessions(user_id)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS counseling_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role       TEXT NOT NULL,
                    content    TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES counseling_sessions(session_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_counseling_messages_session
                ON counseling_messages(session_id)
                """
            )

    # ── 会话管理 ──────────────────────────────────────────

    def create_session(self, user_id: str) -> Dict[str, Any]:
        """创建新的咨询会话，插入 system 消息。"""
        session_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()

        with self._conn() as conn:
            conn.execute(
                "INSERT INTO counseling_sessions (session_id, user_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, user_id, now, now),
            )
            conn.execute(
                "INSERT INTO counseling_messages (message_id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (uuid.uuid4().hex, session_id, "system", COUNSELING_SYSTEM_PROMPT, now),
            )

        return {"session_id": session_id, "created_at": now}

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话元数据。"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM counseling_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def list_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """列出用户的咨询会话。"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM counseling_sessions WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_all_sessions(self) -> List[Dict[str, Any]]:
        """列出所有咨询会话（医生视角）。"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM counseling_sessions ORDER BY updated_at DESC",
            ).fetchall()
        return [dict(r) for r in rows]

    def end_session(self, session_id: str) -> bool:
        """结束会话。"""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            cursor = conn.execute(
                "UPDATE counseling_sessions SET status = 'ended', updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
        return cursor.rowcount > 0

    # ── 消息历史 ──────────────────────────────────────────

    def _load_messages(self, session_id: str) -> List[Dict[str, str]]:
        """加载会话全部消息（含 system）。"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT role, content FROM counseling_messages WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def _save_message(self, session_id: str, role: str, content: str) -> str:
        """持久化一条消息，返回 message_id。"""
        message_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO counseling_messages (message_id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (message_id, session_id, role, content, now),
            )
            conn.execute(
                "UPDATE counseling_sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
        return message_id

    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """返回消息列表（排除 system），供前端展示。"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT message_id, role, content, created_at FROM counseling_messages "
                "WHERE session_id = ? AND role != 'system' ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── LLM 调用 ─────────────────────────────────────────

    def _build_llm_messages(self, history: List[Dict[str, str]], new_user_message: str) -> List[Dict[str, str]]:
        """构造发送给 LLM 的消息列表，包含窗口截断。"""
        system_msg = {"role": "system", "content": COUNSELING_SYSTEM_PROMPT}

        # 从历史中剔除 system 消息
        non_system = [m for m in history if m["role"] != "system"]

        # 窗口截断：只保留最近 N 条
        if len(non_system) > MAX_HISTORY_MESSAGES:
            non_system = non_system[-MAX_HISTORY_MESSAGES:]

        messages = [system_msg] + non_system + [{"role": "user", "content": new_user_message}]
        return messages

    def send_message(self, session_id: str, content: str) -> Dict[str, Any]:
        """非流式发送消息：调用 LLM 并持久化。"""
        session = self.get_session(session_id)
        if session is None:
            raise ValueError(f"咨询会话不存在: {session_id}")
        if session["status"] != "active":
            raise ValueError("该咨询会话已结束")

        history = self._load_messages(session_id)
        messages = self._build_llm_messages(history, content)

        # 持久化用户消息
        self._save_message(session_id, "user", content)

        # 调用 LLM
        try:
            response = self._client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
                timeout=LLM_TIMEOUT_SECONDS,
            )
            reply = response.choices[0].message.content or ""
        except Exception as exc:
            logger.exception("Counseling LLM call failed for session=%s", session_id)
            raise RuntimeError(f"LLM 调用失败: {exc}") from exc

        # 持久化助手回复
        now = datetime.now(timezone.utc).isoformat()
        message_id = self._save_message(session_id, "assistant", reply)

        return {
            "message_id": message_id,
            "role": "assistant",
            "content": reply,
            "created_at": now,
        }

    def send_message_stream(self, session_id: str, content: str) -> Generator[str, None, None]:
        """流式发送消息：yield 文本片段，完成后持久化完整回复。"""
        session = self.get_session(session_id)
        if session is None:
            raise ValueError(f"咨询会话不存在: {session_id}")
        if session["status"] != "active":
            raise ValueError("该咨询会话已结束")

        history = self._load_messages(session_id)
        messages = self._build_llm_messages(history, content)

        # 持久化用户消息
        self._save_message(session_id, "user", content)

        # 流式调用 LLM
        full_reply_parts: list[str] = []
        try:
            response = self._client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
                stream=True,
                timeout=LLM_TIMEOUT_SECONDS,
            )
            for chunk in response:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    full_reply_parts.append(delta)
                    yield delta
        except Exception as exc:
            logger.exception("Counseling LLM stream failed for session=%s", session_id)
            raise RuntimeError(f"LLM 流式调用失败: {exc}") from exc

        # 持久化完整助手回复
        full_reply = "".join(full_reply_parts)
        if full_reply:
            self._save_message(session_id, "assistant", full_reply)
