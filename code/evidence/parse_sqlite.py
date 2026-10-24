"""Parser for SQLite database snapshots."""

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, Set


class SqliteSnapshotParser:
    def __init__(self, sql_path: Path):
        self.sql_path = sql_path
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        with open(sql_path, "r", encoding="utf-8") as f:
            script = f.read()
        self.conn.executescript(script)

    def get_tables(self) -> List[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return [row[0] for row in cur.fetchall()]

    def search_records_by_identifiers(
        self, identifiers: Set[str]
    ) -> List[Dict[str, Any]]:
        """Searches all tables for any row matching any of the given identifiers."""
        matches: List[Dict[str, Any]] = []
        if not identifiers:
            return matches

        tables = self.get_tables()
        cur = self.conn.cursor()

        for table in tables:
            cur.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cur.fetchall()]

            cur.execute(f"SELECT * FROM {table}")
            rows = cur.fetchall()
            for row in rows:
                row_dict = dict(row)
                row_values_lower = {
                    str(v).strip().lower() for v in row_dict.values() if v is not None
                }
                # Check if any identifier matches any column value
                for ident in identifiers:
                    if ident.lower() in row_values_lower:
                        matches.append(
                            {
                                "table": table,
                                "matched_identifier": ident,
                                "record": row_dict,
                            }
                        )
                        break
        return matches

    def close(self):
        self.conn.close()
