"""Durable local relationship vault used by the relationship-map plugin.

This is a deliberately small SQLite implementation for the installable
package. It stores relationship assets outside Hermes sessions and preserves
an append-only timeline. A future hosted Node Engine service can implement the
same business contract with PostgreSQL without changing the Skill or tool API.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4


SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def safe_owner_id() -> str:
    """Return the runtime-derived owner scope, never a model supplied value."""
    return os.environ.get("RELATIONSHIP_MAP_OWNER_ID", "local-default").strip() or "local-default"


def vault_root() -> Path:
    home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    root = home / "data" / "relationship-map"
    root.mkdir(parents=True, exist_ok=True)
    return root


def database_path() -> Path:
    explicit = os.environ.get("RELATIONSHIP_MAP_DATABASE_PATH", "").strip()
    if explicit:
        path = Path(explicit).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    return vault_root() / "relationship-map.db"


def backup_dir() -> Path:
    path = vault_root() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(database_path())
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("PRAGMA busy_timeout = 5000")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialise() -> None:
    with connection() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS contacts (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                name TEXT NOT NULL,
                organization TEXT,
                city TEXT,
                role TEXT,
                notes TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                archived_at TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_owner_name_org
              ON contacts(owner_id, name, COALESCE(organization, ''));
            CREATE INDEX IF NOT EXISTS idx_contacts_owner_name
              ON contacts(owner_id, name);
            CREATE TABLE IF NOT EXISTS tags (
                contact_id TEXT NOT NULL REFERENCES contacts(id),
                tag TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL,
                PRIMARY KEY(contact_id, tag)
            );
            CREATE TABLE IF NOT EXISTS interactions (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                contact_id TEXT REFERENCES contacts(id),
                occurred_at TEXT NOT NULL,
                interaction_type TEXT NOT NULL,
                summary TEXT NOT NULL,
                source_kind TEXT NOT NULL DEFAULT 'user_statement',
                certainty TEXT NOT NULL DEFAULT 'confirmed',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_interactions_owner_contact_time
              ON interactions(owner_id, contact_id, occurred_at DESC);
            CREATE TABLE IF NOT EXISTS commitments (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                contact_id TEXT REFERENCES contacts(id),
                description TEXT NOT NULL,
                due_at TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                certainty TEXT NOT NULL DEFAULT 'confirmed',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS followups (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                contact_id TEXT REFERENCES contacts(id),
                title TEXT NOT NULL,
                due_at TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                details_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        db.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, utc_now()),
        )


def create_backup(reason: str) -> Path:
    """Create a point-in-time SQLite copy before a destructive operation."""
    initialise()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = backup_dir() / f"relationship-map-{stamp}-{reason}.db"
    with connection() as source:
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
        finally:
            destination.close()
    return target


def _audit(db: sqlite3.Connection, owner_id: str, action: str, entity_type: str, entity_id: str, details: dict[str, Any]) -> None:
    db.execute(
        "INSERT INTO audit_events(id, owner_id, action, entity_type, entity_id, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid4()), owner_id, action, entity_type, entity_id, json.dumps(details, ensure_ascii=False, sort_keys=True), utc_now()),
    )


def _row_to_contact(db: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    contact_id = row["id"]
    tags = [r["tag"] for r in db.execute("SELECT tag FROM tags WHERE contact_id = ? ORDER BY tag", (contact_id,))]
    latest = db.execute(
        "SELECT occurred_at, summary FROM interactions WHERE contact_id = ? ORDER BY occurred_at DESC, created_at DESC LIMIT 1",
        (contact_id,),
    ).fetchone()
    followup = db.execute(
        "SELECT title, due_at FROM followups WHERE contact_id = ? AND status = 'open' ORDER BY COALESCE(due_at, '9999') LIMIT 1",
        (contact_id,),
    ).fetchone()
    return {
        "id": contact_id,
        "name": row["name"],
        "organization": row["organization"],
        "city": row["city"],
        "role": row["role"],
        "notes": row["notes"],
        "tags": tags,
        "latest_interaction": dict(latest) if latest else None,
        "next_followup": dict(followup) if followup else None,
        "status": row["status"],
        "updated_at": row["updated_at"],
    }


def find_contacts(query: str, limit: int = 20) -> list[dict[str, Any]]:
    initialise()
    owner_id = safe_owner_id()
    needle = f"%{query.strip()}%"
    with connection() as db:
        rows = db.execute(
            """SELECT DISTINCT c.* FROM contacts c
               LEFT JOIN tags t ON t.contact_id = c.id
               WHERE c.owner_id = ? AND c.status = 'active'
                 AND (c.name LIKE ? OR COALESCE(c.organization, '') LIKE ? OR COALESCE(c.city, '') LIKE ? OR COALESCE(c.role, '') LIKE ? OR COALESCE(t.tag, '') LIKE ?)
               ORDER BY c.updated_at DESC LIMIT ?""",
            (owner_id, needle, needle, needle, needle, needle, max(1, min(int(limit), 50))),
        ).fetchall()
        return [_row_to_contact(db, row) for row in rows]


def get_contact(name: str) -> dict[str, Any] | None:
    matches = find_contacts(name, limit=2)
    exact = next((item for item in matches if item["name"] == name), None)
    return exact or (matches[0] if len(matches) == 1 else None)


def _resolve_or_create_contact(db: sqlite3.Connection, owner_id: str, name: str, organization: str | None = None, city: str | None = None, role: str | None = None) -> tuple[str, bool]:
    if organization:
        row = db.execute(
            "SELECT id FROM contacts WHERE owner_id = ? AND name = ? AND COALESCE(organization, '') = ? AND status = 'active'",
            (owner_id, name, organization),
        ).fetchone()
    else:
        row = db.execute(
            "SELECT id FROM contacts WHERE owner_id = ? AND name = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
            (owner_id, name),
        ).fetchone()
    if row:
        contact_id = row["id"]
        updates = {"organization": organization, "city": city, "role": role}
        sets, values = [], []
        for column, value in updates.items():
            if value:
                sets.append(f"{column} = COALESCE(?, {column})")
                values.append(value)
        if sets:
            values.extend([utc_now(), contact_id, owner_id])
            db.execute(f"UPDATE contacts SET {', '.join(sets)}, updated_at = ? WHERE id = ? AND owner_id = ?", values)
        return contact_id, False
    contact_id = str(uuid4())
    now = utc_now()
    db.execute(
        "INSERT INTO contacts(id, owner_id, name, organization, city, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (contact_id, owner_id, name, organization, city, role, now, now),
    )
    _audit(db, owner_id, "create", "contact", contact_id, {"name": name})
    return contact_id, True


def record_interaction(name: str, summary: str, occurred_at: str, interaction_type: str = "沟通", organization: str | None = None, city: str | None = None, role: str | None = None, certainty: str = "confirmed") -> dict[str, Any]:
    if not name.strip() or not summary.strip():
        raise ValueError("联系人姓名和互动摘要不能为空。")
    initialise()
    owner_id = safe_owner_id()
    with connection() as db:
        contact_id, created = _resolve_or_create_contact(db, owner_id, name.strip(), organization, city, role)
        interaction_id = str(uuid4())
        db.execute(
            "INSERT INTO interactions(id, owner_id, contact_id, occurred_at, interaction_type, summary, certainty, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (interaction_id, owner_id, contact_id, occurred_at, interaction_type, summary.strip(), certainty, utc_now()),
        )
        _audit(db, owner_id, "append", "interaction", interaction_id, {"contact_id": contact_id, "certainty": certainty})
    return {"contact_created": created, "contact_name": name.strip(), "interaction_id": interaction_id}


def record_commitment(name: str, description: str, due_at: str | None = None, certainty: str = "confirmed") -> dict[str, Any]:
    if not name.strip() or not description.strip():
        raise ValueError("联系人姓名和承诺内容不能为空。")
    initialise()
    owner_id = safe_owner_id()
    with connection() as db:
        contact_id, created = _resolve_or_create_contact(db, owner_id, name.strip())
        commitment_id = str(uuid4())
        now = utc_now()
        db.execute(
            "INSERT INTO commitments(id, owner_id, contact_id, description, due_at, certainty, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (commitment_id, owner_id, contact_id, description.strip(), due_at, certainty, now, now),
        )
        _audit(db, owner_id, "append", "commitment", commitment_id, {"contact_id": contact_id, "certainty": certainty})
    return {"contact_created": created, "contact_name": name.strip(), "commitment_id": commitment_id}


def create_followup(name: str, title: str, due_at: str | None = None) -> dict[str, Any]:
    if not name.strip() or not title.strip():
        raise ValueError("联系人姓名和待跟进事项不能为空。")
    initialise()
    owner_id = safe_owner_id()
    with connection() as db:
        contact_id, created = _resolve_or_create_contact(db, owner_id, name.strip())
        followup_id = str(uuid4())
        now = utc_now()
        db.execute(
            "INSERT INTO followups(id, owner_id, contact_id, title, due_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (followup_id, owner_id, contact_id, title.strip(), due_at, now, now),
        )
        _audit(db, owner_id, "append", "followup", followup_id, {"contact_id": contact_id})
    return {"contact_created": created, "contact_name": name.strip(), "followup_id": followup_id}


def meeting_context(name: str) -> dict[str, Any] | None:
    initialise()
    owner_id = safe_owner_id()
    with connection() as db:
        row = db.execute(
            "SELECT * FROM contacts WHERE owner_id = ? AND name = ? AND status = 'active' ORDER BY updated_at DESC LIMIT 1",
            (owner_id, name.strip()),
        ).fetchone()
        if not row:
            return None
        contact = _row_to_contact(db, row)
        interactions = [dict(r) for r in db.execute(
            "SELECT occurred_at, interaction_type, summary, certainty FROM interactions WHERE owner_id = ? AND contact_id = ? ORDER BY occurred_at DESC, created_at DESC LIMIT 5",
            (owner_id, row["id"]),
        )]
        commitments = [dict(r) for r in db.execute(
            "SELECT description, due_at, status, certainty FROM commitments WHERE owner_id = ? AND contact_id = ? AND status = 'open' ORDER BY COALESCE(due_at, '9999') LIMIT 10",
            (owner_id, row["id"]),
        )]
        contact["recent_interactions"] = interactions
        contact["open_commitments"] = commitments
        return contact


def vault_status() -> dict[str, Any]:
    initialise()
    owner_id = safe_owner_id()
    with connection() as db:
        contacts = db.execute("SELECT COUNT(*) AS n FROM contacts WHERE owner_id = ? AND status = 'active'", (owner_id,)).fetchone()["n"]
        interactions = db.execute("SELECT COUNT(*) AS n FROM interactions WHERE owner_id = ?", (owner_id,)).fetchone()["n"]
    return {"schema_version": SCHEMA_VERSION, "owner_scope": owner_id, "contacts": contacts, "interactions": interactions, "database_path": str(database_path())}
