from __future__ import annotations

import json
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

_EMPTY_PREFS = {
    "autopost": {},
    "schedule": {"pipeline": [], "posting": []},
    "brand": {},
    "api_keys": {},
}


class User(db.Model):
    __tablename__ = "users"

    id           = db.Column(db.Integer, primary_key=True)
    username     = db.Column(db.String(80),  unique=True, nullable=False)
    email        = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=True)   # None for Google-only accounts
    google_id    = db.Column(db.String(256), unique=True, nullable=True)
    avatar       = db.Column(db.String(500), nullable=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    last_login   = db.Column(db.DateTime, nullable=True)

    # All per-user settings stored as a single JSON blob for flexibility
    _prefs = db.Column("preferences", db.Text, default="{}")

    # ── password helpers ──────────────────────────────────────────────────────

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    # ── preferences property ──────────────────────────────────────────────────

    @property
    def prefs(self) -> dict:
        try:
            return json.loads(self._prefs or "{}")
        except Exception:
            return {}

    @prefs.setter
    def prefs(self, value: dict) -> None:
        self._prefs = json.dumps(value)

    def get_pref(self, key: str, default=None):
        return self.prefs.get(key, default if default is not None else {})

    def set_pref(self, key: str, value) -> None:
        p = self.prefs
        p[key] = value
        self.prefs = p

    def get_settings(self) -> dict:
        """Return full settings dict (same shape as the old .dashboard_settings.json)."""
        p = self.prefs
        return {
            "autopost": p.get("autopost", {}),
            "schedule": p.get("schedule", {"pipeline": [], "posting": []}),
            "brand":    p.get("brand", {}),
        }

    def save_settings(self, settings: dict) -> None:
        p = self.prefs
        p.update(settings)
        self.prefs = p

    # ── per-user API keys ─────────────────────────────────────────────────────

    def get_api_key(self, name: str) -> str:
        return self.prefs.get("api_keys", {}).get(name, "")

    def set_api_key(self, name: str, value: str) -> None:
        p = self.prefs
        p.setdefault("api_keys", {})[name] = value
        self.prefs = p

    # ── convenience ───────────────────────────────────────────────────────────

    @property
    def display_name(self) -> str:
        return self.username

    @property
    def initials(self) -> str:
        parts = self.username.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return self.username[:2].upper()

    def __repr__(self) -> str:
        return f"<User {self.username!r}>"
