from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import builtins

from openreview_cli.prompts.models import Prompt, PromptBinding, PromptVersion
from openreview_cli.slots import VALID_SLOTS


class PromptStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        sql = (
            Path(__file__).parent.parent / "storage" / "migrations" / "004_prompts.sql"
        ).read_text()
        conn = self._conn()
        try:
            conn.executescript(sql)
            conn.commit()
        finally:
            conn.close()

    def create(
        self,
        name: str,
        content: str,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> PromptVersion:
        if len(content.encode("utf-8")) > 16384:
            raise ValueError("Content exceeds 16384 bytes")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT 1 FROM prompt_versions WHERE name = ? LIMIT 1", (name,)
            ).fetchone()
            if existing:
                raise ValueError(f"Prompt '{name}' already exists")
            now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            conn.execute(
                "INSERT INTO prompt_versions (name, version, content, created_at, tags, description) VALUES (?, 1, ?, ?, ?, ?)",
                (name, content, now, json.dumps(tags) if tags else None, description),
            )
            conn.commit()
            return PromptVersion(
                name=name,
                version=1,
                content=content,
                created_at=now,
                tags=tags,
                description=description,
            )
        finally:
            conn.close()

    def update(
        self,
        name: str,
        content: str,
        tags: list[str] | None = None,
        description: str | None = None,
    ) -> PromptVersion:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT MAX(version) FROM prompt_versions WHERE name = ?", (name,)
            ).fetchone()
            if row[0] is None:
                raise ValueError(f"Prompt '{name}' not found")
            next_version = int(row[0]) + 1
            now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            conn.execute(
                "INSERT INTO prompt_versions (name, version, content, created_at, tags, description) VALUES (?, ?, ?, ?, ?, ?)",
                (name, next_version, content, now, json.dumps(tags) if tags else None, description),
            )
            conn.commit()
            return PromptVersion(
                name=name,
                version=next_version,
                content=content,
                created_at=now,
                tags=tags,
                description=description,
            )
        finally:
            conn.close()

    def get(self, name: str, version: int) -> PromptVersion:
        conn = self._conn()
        try:
            exists = conn.execute(
                "SELECT 1 FROM prompt_versions WHERE name = ? LIMIT 1", (name,)
            ).fetchone()
            if exists is None:
                raise ValueError(f"Prompt '{name}' not found")
            row = conn.execute(
                "SELECT * FROM prompt_versions WHERE name = ? AND version = ?", (name, version)
            ).fetchone()
            if row is None:
                raise ValueError(f"Prompt '{name}' version {version} not found")
            return self._row_to_version(row)
        finally:
            conn.close()

    def get_latest(self, name: str) -> PromptVersion:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM prompt_versions WHERE name = ? ORDER BY version DESC LIMIT 1",
                (name,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Prompt '{name}' not found")
            return self._row_to_version(row)
        finally:
            conn.close()

    def list(self, page: int = 1, per_page: int = 25) -> list[Prompt]:
        conn = self._conn()
        try:
            offset = (page - 1) * per_page
            rows = conn.execute(
                "SELECT name, MAX(version) AS latest_version, MIN(created_at) AS created_at "
                "FROM prompt_versions GROUP BY name ORDER BY name LIMIT ? OFFSET ?",
                (per_page, offset),
            ).fetchall()
            return [
                Prompt(
                    name=str(r["name"]),
                    latest_version=int(r["latest_version"]),
                    created_at=str(r["created_at"]),
                )
                for r in rows
            ]
        finally:
            conn.close()

    def delete(self, name: str) -> None:
        conn = self._conn()
        try:
            conn.execute("DELETE FROM prompt_bindings WHERE prompt_name = ?", (name,))
            cursor = conn.execute("DELETE FROM prompt_versions WHERE name = ?", (name,))
            if cursor.rowcount == 0:
                raise ValueError(f"Prompt '{name}' not found")
            conn.commit()
        finally:
            conn.close()

    def bind(self, slot: str, name: str, version: int) -> PromptBinding:
        if slot not in VALID_SLOTS:
            raise ValueError(f"Invalid slot '{slot}'. Valid: {', '.join(sorted(VALID_SLOTS))}")
        conn = self._conn()
        try:
            exists = conn.execute(
                "SELECT 1 FROM prompt_versions WHERE name = ? AND version = ?", (name, version)
            ).fetchone()
            if exists is None:
                raise ValueError(f"Prompt '{name}' version {version} not found")
            now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            conn.execute(
                "INSERT OR REPLACE INTO prompt_bindings (slot, prompt_name, prompt_version, created_at) VALUES (?, ?, ?, ?)",
                (slot, name, version, now),
            )
            conn.commit()
            return PromptBinding(
                slot=slot, prompt_name=name, prompt_version=version, created_at=now
            )
        finally:
            conn.close()

    def unbind(self, slot: str) -> None:
        conn = self._conn()
        try:
            cursor = conn.execute("DELETE FROM prompt_bindings WHERE slot = ?", (slot,))
            if cursor.rowcount == 0:
                raise ValueError(f"No binding exists for slot '{slot}'")
            conn.commit()
        finally:
            conn.close()

    def bindings(self) -> builtins.list[PromptBinding]:
        conn = self._conn()
        try:
            rows = conn.execute("SELECT * FROM prompt_bindings ORDER BY slot").fetchall()
            return [
                PromptBinding(
                    slot=str(r["slot"]),
                    prompt_name=str(r["prompt_name"]),
                    prompt_version=int(r["prompt_version"]),
                    created_at=str(r["created_at"]),
                )
                for r in rows
            ]
        finally:
            conn.close()

    def export(self, name: str | None = None) -> builtins.list[dict[str, Any]] | dict[str, Any]:
        conn = self._conn()
        try:
            if name:
                rows = conn.execute(
                    "SELECT * FROM prompt_versions WHERE name = ? ORDER BY version", (name,)
                ).fetchall()
                if not rows:
                    raise ValueError(f"Prompt '{name}' not found")
                return self._rows_to_export(rows)
            rows = conn.execute(
                "SELECT DISTINCT name FROM prompt_versions ORDER BY name"
            ).fetchall()
            result: builtins.list[dict[str, Any]] = []
            for row in rows:
                versions = conn.execute(
                    "SELECT * FROM prompt_versions WHERE name = ? ORDER BY version",
                    (str(row["name"]),),
                ).fetchall()
                result.append(self._rows_to_export(versions))
            return result
        finally:
            conn.close()

    def import_prompt(self, data: dict[str, Any]) -> None:
        if "name" not in data or "versions" not in data:
            raise ValueError("Import data must contain 'name' and 'versions'")
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT 1 FROM prompt_versions WHERE name = ? LIMIT 1", (data["name"],)
            ).fetchone()
            if existing:
                raise ValueError(f"Prompt '{data['name']}' already exists")
            for v in data["versions"]:
                raw_tags = v.get("tags") or v.get("metadata", {}).get("tags")
                tags_json = json.dumps(raw_tags) if raw_tags else None
                description = v.get("description") or v.get("metadata", {}).get("description")
                conn.execute(
                    "INSERT INTO prompt_versions (name, version, content, created_at, tags, description) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        data["name"],
                        v.get("version", 1),
                        v["content"],
                        v.get("created_at"),
                        tags_json,
                        description,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _rows_to_export(rows: builtins.list[sqlite3.Row]) -> dict[str, Any]:
        name = str(rows[0]["name"])
        versions = []
        for r in rows:
            tags: list[str] | None = None
            if r["tags"]:
                tags = json.loads(str(r["tags"]))
            versions.append(
                {
                    "version": int(r["version"]),
                    "content": str(r["content"]),
                    "created_at": str(r["created_at"]),
                    "metadata": {
                        "tags": tags,
                        "description": str(r["description"]) if r["description"] else None,
                    },
                }
            )
        return {"name": name, "versions": versions}

    def resolve(self, slot_name: str) -> str:
        conn = self._conn()
        binding = conn.execute(
            "SELECT prompt_name, prompt_version FROM prompt_bindings WHERE slot = ?",
            (slot_name,),
        ).fetchone()
        if binding is None:
            conn.close()
            return ""
        row = conn.execute(
            "SELECT content FROM prompt_versions WHERE name = ? AND version = ?",
            (str(binding["prompt_name"]), int(binding["prompt_version"])),
        ).fetchone()
        conn.close()
        return str(row["content"]) if row else ""

    @staticmethod
    def _row_to_version(row: sqlite3.Row) -> PromptVersion:
        tags: list[str] | None = None
        if row["tags"]:
            tags = json.loads(str(row["tags"]))
        return PromptVersion(
            name=str(row["name"]),
            version=int(row["version"]),
            content=str(row["content"]),
            created_at=str(row["created_at"]),
            tags=tags,
            description=str(row["description"]) if row["description"] else None,
        )
