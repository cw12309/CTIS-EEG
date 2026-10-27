import json
import os
import sqlite3
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from config import DATA_DIR

DB_PATH = os.path.join(DATA_DIR, "ctis_eeg.db")


@dataclass
class UserProfile:
    user_id: str
    name: str
    age: int
    gender: str
    diagnosis: str = ""          # 如 "MCI", "早期AD"
    created_at: str = ""
    baseline: dict = field(default_factory=dict)


class UserDatabase:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_tables()

    def _init_tables(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    name TEXT,
                    age INTEGER,
                    gender TEXT,
                    diagnosis TEXT,
                    created_at TEXT,
                    baseline TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    session_date TEXT,
                    ct30_score REAL,
                    cognitive_vector TEXT,
                    json_log_path TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            """)

    def add_user(self, profile: UserProfile) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO users VALUES (?,?,?,?,?,?,?)",
                    (
                        profile.user_id,
                        profile.name,
                        profile.age,
                        profile.gender,
                        profile.diagnosis,
                        profile.created_at,
                        json.dumps(profile.baseline, ensure_ascii=False),
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_user(self, user_id: str) -> Optional[UserProfile]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id=?", (user_id,)
            ).fetchone()
        if row:
            return UserProfile(
                user_id=row[0],
                name=row[1],
                age=row[2],
                gender=row[3],
                diagnosis=row[4],
                created_at=row[5],
                baseline=json.loads(row[6]) if row[6] else {},
            )
        return None

    def list_users(self) -> List[UserProfile]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        return [
            UserProfile(
                user_id=r[0], name=r[1], age=r[2], gender=r[3],
                diagnosis=r[4], created_at=r[5],
                baseline=json.loads(r[6]) if r[6] else {},
            )
            for r in rows
        ]
