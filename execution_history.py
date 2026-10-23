"""Local execution ledger. Connections never cross threads; SQL is parameterized."""
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from operational_preferences import atomic_json, profile_dir


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def known_secrets(settings_dir):
    """Read only known credential values for masking; never persist keys or values."""
    key_pattern = re.compile(r"password|passwd|token|secret|api.?key", re.I)
    values = [value for key, value in os.environ.items() if key_pattern.search(key)]
    try:
        for line in (Path(settings_dir) / ".env").read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and not key.lstrip().startswith("#") and key_pattern.search(key):
                values.append(value.strip().strip("\"'"))
    except (OSError, UnicodeError):
        pass
    return values


class LogPolicy:
    def __init__(self, settings, secrets=()):
        self.mode = settings.get("log_mode", "summary")
        self.limit = int(settings.get("max_log_chars", 64000))
        self.secrets = sorted({str(x) for x in secrets if x and len(str(x)) >= 4}, key=len, reverse=True)
        self.used = 0

    def clean(self, text):
        for secret in self.secrets:
            text = text.replace(secret, "[OSCURATO]")
        text = re.sub(r"(?i)(bearer\s+)\S+", r"\1[OSCURATO]", text)
        text = re.sub(r"(?i)((?:password|passwd|token|secret|api[_-]?key|authorization)\s*[=:]\s*)[^\s,;]+",
                      r"\1[OSCURATO]", text)
        text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
        text = re.sub(r"(?i)(https?://)[^\s/@]+:[^\s/@]+@", r"\1[OSCURATO]@", text)
        return text

    def capture(self, text, diagnostic=False):
        if not diagnostic and self.mode != "redacted":
            return ""
        available = max(0, self.limit - self.used)
        value = self.clean(text)[:available]
        self.used += len(value)
        return value


class HistoryStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else profile_dir() / "history.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.path.with_name("history_settings.json")
        self.settings = {"schema_version": 1, "retention_days": 90,
                         "log_mode": "summary", "max_log_chars": 64000}
        if self.settings_path.exists():
            try:
                data = json.loads(self.settings_path.read_text(encoding="utf-8"))
                if data.get("schema_version") == 1:
                    self.settings.update({key: data[key] for key in self.settings if key in data})
            except (ValueError, OSError, AttributeError):
                pass  # Preserve unreadable settings, use conservative defaults.
        else:
            atomic_json(self.settings_path, self.settings)
        try:
            self.settings["retention_days"] = max(1, min(3650, int(self.settings["retention_days"])))
            self.settings["max_log_chars"] = max(1000, min(1000000, int(self.settings["max_log_chars"])))
        except (TypeError, ValueError):
            self.settings.update(retention_days=90, max_log_chars=64000)
        with self.connect() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 2:
                raise RuntimeError("Versione storico più recente dell'applicazione")
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, activity_id TEXT NOT NULL, activity_name TEXT NOT NULL,
                started_at TEXT NOT NULL, ended_at TEXT, duration REAL,
                outcome TEXT NOT NULL, exit_code INTEGER, log TEXT NOT NULL DEFAULT '',
                workflow_run_id TEXT, step_index INTEGER)""")
            db.execute("CREATE INDEX IF NOT EXISTS runs_date ON runs(started_at DESC)")
            db.execute("""CREATE TABLE IF NOT EXISTS workflow_runs (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, started_at TEXT NOT NULL,
                ended_at TEXT, outcome TEXT NOT NULL, steps_json TEXT NOT NULL,
                current_index INTEGER NOT NULL DEFAULT 0)""")
            db.execute("PRAGMA user_version=2")
        self.prune()

    @contextmanager
    def connect(self):
        # isolation via short-lived connections, bounded busy timeout.
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def recover(self):
        # Called only by the application that owns the profile execution lock.
        with self.connect() as db:
            db.execute("""UPDATE runs SET ended_at=NULL, duration=NULL,
                       outcome='interrotto', log=log || ? WHERE outcome='in_esecuzione'""",
                       ("\nSessione terminata senza esito: esecuzione interrotta, nessuna ripresa automatica. "
                        "Data di conclusione e durata effettiva sconosciute.\n",))
            db.execute("UPDATE workflow_runs SET ended_at=NULL,outcome='interrotto' WHERE outcome='in_esecuzione'")

    def start_workflow(self, run_id, name, steps):
        with self.connect() as db:
            db.execute("INSERT INTO workflow_runs(id,name,started_at,outcome,steps_json) VALUES(?,?,?,?,?)",
                       (run_id, name, utc_now(), "in_esecuzione", json.dumps(steps)))

    def update_workflow(self, run_id, index, outcome="in_esecuzione"):
        with self.connect() as db:
            db.execute("UPDATE workflow_runs SET current_index=?,outcome=?,ended_at=? WHERE id=?",
                       (index, outcome, None if outcome == "in_esecuzione" else utc_now(), run_id))

    def workflows(self, limit=20):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM workflow_runs ORDER BY started_at DESC LIMIT ?", (limit,))]

    def start(self, activity, workflow_run_id=None, step_index=None):
        run_id = uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO runs(id,activity_id,activity_name,started_at,outcome,workflow_run_id,step_index) VALUES(?,?,?,?,?,?,?)",
                       (run_id, activity.activity_id, activity.title, utc_now(), "in_esecuzione", workflow_run_id, step_index))
        return run_id

    def append(self, run_id, text):
        if text:
            with self.connect() as db:
                db.execute("UPDATE runs SET log=log || ? WHERE id=?", (text, run_id))

    def finish(self, run_id, outcome, exit_code, duration):
        with self.connect() as db:
            db.execute("UPDATE runs SET ended_at=?,duration=?,outcome=?,exit_code=? WHERE id=?",
                       (utc_now(), max(0, duration), outcome, exit_code, run_id))
        self.prune()

    def prune(self):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.settings["retention_days"])).isoformat()
        with self.connect() as db:
            db.execute("DELETE FROM runs WHERE started_at < ? AND outcome != 'in_esecuzione'", (cutoff,))
            db.execute("DELETE FROM workflow_runs WHERE started_at < ? AND outcome != 'in_esecuzione'", (cutoff,))

    def clear(self):
        with self.connect() as db:
            db.execute("PRAGMA secure_delete=ON")
            db.execute("DELETE FROM runs WHERE outcome != 'in_esecuzione'")
            db.execute("DELETE FROM workflow_runs WHERE outcome != 'in_esecuzione'")
        with self.connect() as db:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            db.execute("VACUUM")

    def rows(self, activity_id=None, outcome=None, limit=500, offset=0, newest_first=True):
        clauses, args = [], []
        for column, value in (("activity_id", activity_id), ("outcome", outcome)):
            if value:
                clauses.append(f"{column}=?")
                args.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        order = "DESC" if newest_first else "ASC"
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT id,activity_id,activity_name,started_at,ended_at,duration,outcome,exit_code,workflow_run_id,step_index FROM runs"
                + where + f" ORDER BY started_at {order},id {order} LIMIT ? OFFSET ?", args + [limit, offset])]

    def detail(self, run_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            return dict(row) if row else None

    def statistics(self):
        with self.connect() as db:
            counts = {row[0]: row[1] for row in db.execute("SELECT outcome,COUNT(*) FROM runs GROUP BY outcome")}
            frequent = [dict(row) for row in db.execute("""SELECT activity_id,MAX(activity_name) AS activity_name,
                COUNT(*) AS count FROM runs GROUP BY activity_id ORDER BY count DESC LIMIT 5""")]
        return {"counts": counts, "frequent": frequent, "recent": self.rows(limit=5)}
