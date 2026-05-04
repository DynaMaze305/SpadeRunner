import sqlite3
import threading
import time

class TelemetryStore:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, db_path="telemetry.db"):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init(db_path)
        return cls._instance

    def _init(self, db_path):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                ts REAL,
                bot TEXT,
                key TEXT,
                value REAL
            )
        """)
        self.db.commit()

    # -------------------------
    # Store a telemetry sample
    # -------------------------
    def store_sample(self, sample):
        ts = sample["ts"]
        bot = sample["bot"]

        cur = self.db.cursor()
        for key, value in sample["values"].items():
            print((ts, bot, key, value))
            cur.execute(
                "INSERT INTO telemetry (ts, bot, key, value) VALUES (?, ?, ?, ?)",
                (ts, bot, key, value)
            )
        self.db.commit()

    # -------------------------
    # Query analog data
    # -------------------------
    def query_analog(self, minutes=15):
        since = time.time() - minutes * 60
        cur = self.db.cursor()

        cur.execute("""
            SELECT ts, key, value
            FROM telemetry
            WHERE ts >= ?
            AND key LIKE 'analog_%'
            ORDER BY ts ASC
        """, (since,))

        rows = cur.fetchall()

        data = {}
        for ts, key, value in rows:
            if key not in data:
                data[key] = []

            # Normalize timestamp to milliseconds (int)
            data[key].append({
                "ts": int(ts * 1000),
                "value": value
            })

        return data

    # -------------------------
    # Query digital data
    # -------------------------
    def query_digital(self, minutes=15):
        since = time.time() - minutes * 60
        cur = self.db.cursor()

        cur.execute("""
            SELECT ts, key, value
            FROM telemetry
            WHERE ts >= ?
            AND key LIKE 'digital_%'
            ORDER BY ts ASC
        """, (since,))

        rows = cur.fetchall()

        data = {}
        for ts, key, value in rows:
            if key not in data:
                data[key] = []

            data[key].append({
                "ts": int(ts * 1000),  # ms
                "value": value
            })

        return data
