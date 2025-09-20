import sqlite3
import csv

DB = "groundwater.db"
CSV = "sample.csv"

schema = """
CREATE TABLE IF NOT EXISTS groundwater (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location TEXT UNIQUE,
    groundwater_level REAL,
    pH REAL,
    TDS INTEGER,
    COD REAL,
    BOD REAL,
    status TEXT,
    last_updated TEXT
);
"""

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.executescript(schema)

with open(CSV, "r") as f:
    dr = csv.DictReader(f)
    for r in dr:
        cur.execute(
            """INSERT OR REPLACE INTO groundwater
            (location, groundwater_level, pH, TDS, COD, BOD, status, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                r["location"],
                float(r["groundwater_level"]),
                float(r["pH"]),
                int(r["TDS"]),
                float(r["COD"]),
                float(r["BOD"]),
                r["status"],
                r["last_updated"],
            ),
        )

conn.commit()
conn.close()
print("Database initialized ->", DB)