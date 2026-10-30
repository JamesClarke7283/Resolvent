"""Local SQLite worksheets. The database path is configurable for tests/portable use."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from platformdirs import user_data_path

from resolvent.models import Worksheet


class WorksheetStore:
    def __init__(self, path: Path | None = None):
        self.path = path or user_data_path("resolvent", appauthor=False) / "worksheets.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS worksheets (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, cells TEXT NOT NULL, updated_at TEXT NOT NULL
            )""")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def list(self):
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT id, title, updated_at FROM worksheets ORDER BY updated_at DESC LIMIT 200"
                )
            ]

    def get(self, id: str):
        with self.connect() as db:
            row = db.execute("SELECT * FROM worksheets WHERE id=?", (id,)).fetchone()
        if row is None:
            return None
        return {**dict(row), "cells": json.loads(row["cells"])}

    def save(self, worksheet: Worksheet, id: str | None = None):
        id = id or uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        cells = [cell.model_dump() for cell in worksheet.cells]
        with self.connect() as db:
            db.execute(
                """INSERT INTO worksheets VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title, cells=excluded.cells,
                updated_at=excluded.updated_at""",
                (id, worksheet.title, json.dumps(cells), now),
            )
        return {"id": id, "title": worksheet.title, "cells": cells, "updated_at": now}

    def delete(self, id: str):
        with self.connect() as db:
            return db.execute("DELETE FROM worksheets WHERE id=?", (id,)).rowcount > 0
