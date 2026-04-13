from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent.parent / "data" / "properties.db"))


def _ensure_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_db():
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE NOT NULL,
                source TEXT,
                address TEXT,
                city TEXT,
                neighborhood TEXT,
                street TEXT,
                price TEXT,
                rooms TEXT,
                floor TEXT,
                total_floors TEXT,
                size_sqm TEXT,
                property_type TEXT,
                entry_date TEXT,
                description TEXT,
                has_parking BOOLEAN DEFAULT 0,
                has_elevator BOOLEAN DEFAULT 0,
                has_balcony BOOLEAN DEFAULT 0,
                has_mamad BOOLEAN DEFAULT 0,
                has_air_conditioning BOOLEAN DEFAULT 0,
                is_furnished BOOLEAN DEFAULT 0,
                contact_name TEXT,
                contact_phone TEXT,
                images TEXT DEFAULT '[]',
                -- User-editable fields
                status TEXT DEFAULT 'חדש',
                rating REAL DEFAULT 0,
                notes TEXT DEFAULT '',
                tasks TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT
            )
        """)


def upsert_property(data: dict) -> int:
    """Insert or update a property. Returns the row id."""
    now = datetime.now().isoformat()

    contact_name = ""
    contact_phone = ""
    contacts = data.get("contacts", [])
    if contacts:
        contact_name = contacts[0].get("name", "") or ""
        contact_phone = contacts[0].get("phone", "") or ""

    images = json.dumps(data.get("images", []), ensure_ascii=False)

    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM properties WHERE url = ?", (data["url"],)
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE properties SET
                    source=?, address=?, city=?, neighborhood=?, street=?,
                    price=?, rooms=?, floor=?, total_floors=?, size_sqm=?,
                    property_type=?, entry_date=?, description=?,
                    has_parking=?, has_elevator=?, has_balcony=?,
                    has_mamad=?, has_air_conditioning=?, is_furnished=?,
                    contact_name=?, contact_phone=?, images=?, updated_at=?
                WHERE id=?
            """, (
                data.get("source"), data.get("address"), data.get("city"),
                data.get("neighborhood"), data.get("street"), data.get("price"),
                data.get("rooms"), data.get("floor"), data.get("total_floors"),
                data.get("size_sqm"), data.get("property_type"), data.get("entry_date"),
                data.get("description"),
                data.get("has_parking", False), data.get("has_elevator", False),
                data.get("has_balcony", False), data.get("has_mamad", False),
                data.get("has_air_conditioning", False), data.get("is_furnished", False),
                contact_name, contact_phone, images, now, existing["id"],
            ))
            return existing["id"]
        else:
            cur = conn.execute("""
                INSERT INTO properties (
                    url, source, address, city, neighborhood, street,
                    price, rooms, floor, total_floors, size_sqm,
                    property_type, entry_date, description,
                    has_parking, has_elevator, has_balcony,
                    has_mamad, has_air_conditioning, is_furnished,
                    contact_name, contact_phone, images,
                    status, rating, notes, tasks, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                data["url"], data.get("source"), data.get("address"), data.get("city"),
                data.get("neighborhood"), data.get("street"), data.get("price"),
                data.get("rooms"), data.get("floor"), data.get("total_floors"),
                data.get("size_sqm"), data.get("property_type"), data.get("entry_date"),
                data.get("description"),
                data.get("has_parking", False), data.get("has_elevator", False),
                data.get("has_balcony", False), data.get("has_mamad", False),
                data.get("has_air_conditioning", False), data.get("is_furnished", False),
                contact_name, contact_phone, images,
                "חדש", 0, "", "", now, now,
            ))
            return cur.lastrowid


def get_all_properties(status_filter: str | None = None) -> list[dict]:
    with get_db() as conn:
        if status_filter and status_filter != "הכל":
            rows = conn.execute(
                "SELECT * FROM properties WHERE status = ? ORDER BY created_at DESC",
                (status_filter,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM properties ORDER BY created_at DESC"
            ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_property(prop_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM properties WHERE id = ?", (prop_id,)).fetchone()
    return _row_to_dict(row) if row else None


def update_property_field(prop_id: int, field: str, value: str) -> bool:
    allowed = {"status", "rating", "notes", "tasks"}
    if field not in allowed:
        return False
    with get_db() as conn:
        conn.execute(
            f"UPDATE properties SET {field} = ?, updated_at = ? WHERE id = ?",
            (value, datetime.now().isoformat(), prop_id),
        )
    return True


def delete_property(prop_id: int) -> bool:
    with get_db() as conn:
        conn.execute("DELETE FROM properties WHERE id = ?", (prop_id,))
    return True


def get_stats() -> dict:
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
        by_status = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM properties GROUP BY status"
        ).fetchall()
    status_map = {row["status"]: row["cnt"] for row in by_status}
    return {
        "total": total,
        "new": status_map.get("חדש", 0),
        "visited": status_map.get("ביקרתי", 0),
        "negotiation": status_map.get("משא ומתן", 0),
        "status_counts": status_map,
    }


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    try:
        d["images"] = json.loads(d.get("images", "[]"))
    except (json.JSONDecodeError, TypeError):
        d["images"] = []
    return d
