"""
医生随访记录与管理状态服务。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


DEFAULT_MANAGEMENT_STATUS = "normal"


class DoctorService:
    """存储医生侧的随访记录和管理状态，不改写老人原始画像。"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS doctor_followups (
                    followup_id TEXT PRIMARY KEY,
                    elderly_user_id TEXT NOT NULL,
                    doctor_id TEXT NOT NULL,
                    visit_type TEXT NOT NULL,
                    findings TEXT NOT NULL,
                    recommendations TEXT NOT NULL,
                    contacted_family INTEGER NOT NULL DEFAULT 0,
                    arranged_revisit INTEGER NOT NULL DEFAULT 0,
                    referred INTEGER NOT NULL DEFAULT 0,
                    next_followup_at TEXT,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (elderly_user_id) REFERENCES users(user_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS doctor_management_state (
                    elderly_user_id TEXT PRIMARY KEY,
                    is_key_case INTEGER NOT NULL DEFAULT 0,
                    management_status TEXT NOT NULL DEFAULT 'normal',
                    contacted_family INTEGER NOT NULL DEFAULT 0,
                    arranged_revisit INTEGER NOT NULL DEFAULT 0,
                    referred INTEGER NOT NULL DEFAULT 0,
                    next_followup_at TEXT,
                    last_followup_at TEXT,
                    last_followup_type TEXT,
                    updated_by TEXT,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (elderly_user_id) REFERENCES users(user_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_doctor_followups_elderly ON doctor_followups(elderly_user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_doctor_followups_created ON doctor_followups(created_at)"
            )

    def _elderly_exists(self, elderly_user_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM users WHERE user_id = ?",
                (elderly_user_id,),
            ).fetchone()
        return row is not None

    def get_management_state(self, elderly_user_id: str) -> Dict[str, Any]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM doctor_management_state
                WHERE elderly_user_id = ?
                """,
                (elderly_user_id,),
            ).fetchone()
        if row is None:
            return self._default_management_state(elderly_user_id)
        return self._normalize_management_state(dict(row))

    def update_management_state(
        self,
        elderly_user_id: str,
        doctor_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not self._elderly_exists(elderly_user_id):
            raise ValueError("老年人不存在")

        current = self.get_management_state(elderly_user_id)
        next_state = {**current}
        field_map = {
            "is_key_case": "is_key_case",
            "management_status": "management_status",
            "contacted_family": "contacted_family",
            "arranged_revisit": "arranged_revisit",
            "referred": "referred",
            "next_followup_at": "next_followup_at",
            "last_followup_at": "last_followup_at",
            "last_followup_type": "last_followup_type",
        }
        for source_key, target_key in field_map.items():
            if source_key in updates and updates[source_key] is not None:
                next_state[target_key] = updates[source_key]

        next_state["updated_by"] = doctor_id
        next_state["updated_at"] = datetime.now(timezone.utc).isoformat()

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO doctor_management_state (
                    elderly_user_id,
                    is_key_case,
                    management_status,
                    contacted_family,
                    arranged_revisit,
                    referred,
                    next_followup_at,
                    last_followup_at,
                    last_followup_type,
                    updated_by,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(elderly_user_id) DO UPDATE SET
                    is_key_case = excluded.is_key_case,
                    management_status = excluded.management_status,
                    contacted_family = excluded.contacted_family,
                    arranged_revisit = excluded.arranged_revisit,
                    referred = excluded.referred,
                    next_followup_at = excluded.next_followup_at,
                    last_followup_at = excluded.last_followup_at,
                    last_followup_type = excluded.last_followup_type,
                    updated_by = excluded.updated_by,
                    updated_at = excluded.updated_at
                """,
                (
                    elderly_user_id,
                    int(bool(next_state["is_key_case"])),
                    str(next_state["management_status"] or DEFAULT_MANAGEMENT_STATUS),
                    int(bool(next_state["contacted_family"])),
                    int(bool(next_state["arranged_revisit"])),
                    int(bool(next_state["referred"])),
                    next_state.get("next_followup_at"),
                    next_state.get("last_followup_at"),
                    next_state.get("last_followup_type"),
                    doctor_id,
                    next_state["updated_at"],
                ),
            )
        return self.get_management_state(elderly_user_id)

    def create_followup(
        self,
        elderly_user_id: str,
        doctor_id: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        if not self._elderly_exists(elderly_user_id):
            raise ValueError("老年人不存在")

        now = datetime.now(timezone.utc).isoformat()
        record = {
            "followup_id": str(uuid.uuid4()),
            "elderly_user_id": elderly_user_id,
            "doctor_id": doctor_id,
            "visit_type": str(payload.get("visit_type") or "").strip(),
            "findings": str(payload.get("findings") or "").strip(),
            "recommendations": [
                str(item).strip()
                for item in (payload.get("recommendations") or [])
                if str(item).strip()
            ],
            "contacted_family": bool(payload.get("contacted_family")),
            "arranged_revisit": bool(payload.get("arranged_revisit")),
            "referred": bool(payload.get("referred")),
            "next_followup_at": payload.get("next_followup_at"),
            "notes": str(payload.get("notes") or "").strip(),
            "created_at": now,
            "updated_at": now,
        }
        if not record["visit_type"]:
            raise ValueError("随访方式不能为空")
        if not record["findings"]:
            raise ValueError("本次发现不能为空")

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO doctor_followups (
                    followup_id,
                    elderly_user_id,
                    doctor_id,
                    visit_type,
                    findings,
                    recommendations,
                    contacted_family,
                    arranged_revisit,
                    referred,
                    next_followup_at,
                    notes,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["followup_id"],
                    elderly_user_id,
                    doctor_id,
                    record["visit_type"],
                    record["findings"],
                    json.dumps(record["recommendations"], ensure_ascii=False),
                    int(record["contacted_family"]),
                    int(record["arranged_revisit"]),
                    int(record["referred"]),
                    record["next_followup_at"],
                    record["notes"],
                    now,
                    now,
                ),
            )

        self.update_management_state(
            elderly_user_id,
            doctor_id,
            {
                "contacted_family": record["contacted_family"],
                "arranged_revisit": record["arranged_revisit"],
                "referred": record["referred"],
                "next_followup_at": record["next_followup_at"],
                "last_followup_at": now,
                "last_followup_type": record["visit_type"],
            },
        )
        return record

    def list_followups(self, elderly_user_id: str) -> list[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM doctor_followups
                WHERE elderly_user_id = ?
                ORDER BY created_at DESC
                """,
                (elderly_user_id,),
            ).fetchall()
        return [self._normalize_followup(dict(row)) for row in rows]

    def get_latest_followup(self, elderly_user_id: str) -> Optional[Dict[str, Any]]:
        followups = self.list_followups(elderly_user_id)
        return followups[0] if followups else None

    def _default_management_state(self, elderly_user_id: str) -> Dict[str, Any]:
        return {
            "elderly_user_id": elderly_user_id,
            "is_key_case": False,
            "management_status": DEFAULT_MANAGEMENT_STATUS,
            "contacted_family": False,
            "arranged_revisit": False,
            "referred": False,
            "next_followup_at": None,
            "last_followup_at": None,
            "last_followup_type": None,
            "updated_by": None,
            "updated_at": None,
        }

    @staticmethod
    def _normalize_followup(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "followup_id": row["followup_id"],
            "elderly_user_id": row["elderly_user_id"],
            "doctor_id": row["doctor_id"],
            "visit_type": row["visit_type"],
            "findings": row["findings"],
            "recommendations": json.loads(row["recommendations"] or "[]"),
            "contacted_family": bool(row["contacted_family"]),
            "arranged_revisit": bool(row["arranged_revisit"]),
            "referred": bool(row["referred"]),
            "next_followup_at": row["next_followup_at"],
            "notes": row["notes"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _normalize_management_state(row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "elderly_user_id": row["elderly_user_id"],
            "is_key_case": bool(row["is_key_case"]),
            "management_status": row["management_status"] or DEFAULT_MANAGEMENT_STATUS,
            "contacted_family": bool(row["contacted_family"]),
            "arranged_revisit": bool(row["arranged_revisit"]),
            "referred": bool(row["referred"]),
            "next_followup_at": row["next_followup_at"],
            "last_followup_at": row["last_followup_at"],
            "last_followup_type": row["last_followup_type"],
            "updated_by": row["updated_by"],
            "updated_at": row["updated_at"],
        }
