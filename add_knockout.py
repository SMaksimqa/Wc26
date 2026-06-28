#!/usr/bin/env python3
"""Add Round of 32 (knockout) matches to the DB. Safe to run multiple times."""
import sqlite3, os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "wc2026.db")
MSK = timedelta(hours=3)

def msk(utc: str) -> str:
    return (datetime.strptime(utc, "%Y-%m-%d %H:%M") + MSK).strftime("%Y-%m-%d %H:%M")

# Round of 32 — times converted from local US/MX zones to UTC then to MSK
R32 = [
    ("South Africa", "Canada",      msk("2026-06-28 19:00"), "1/32 финала"),
    ("Brazil",       "Japan",       msk("2026-06-29 17:00"), "1/32 финала"),
    ("Germany",      "Paraguay",    msk("2026-06-29 20:30"), "1/32 финала"),
    ("Netherlands",  "Morocco",     msk("2026-06-30 01:00"), "1/32 финала"),
    ("Ivory Coast",  "Norway",      msk("2026-06-30 17:00"), "1/32 финала"),
    ("France",       "Sweden",      msk("2026-06-30 21:00"), "1/32 финала"),
    ("Mexico",       "Ecuador",     msk("2026-07-01 01:00"), "1/32 финала"),
    ("England",      "DR Congo",    msk("2026-07-01 16:00"), "1/32 финала"),
    ("Belgium",      "Senegal",     msk("2026-07-01 20:00"), "1/32 финала"),
    ("USA",          "Bosnia",      msk("2026-07-02 00:00"), "1/32 финала"),
    ("Spain",        "Austria",     msk("2026-07-02 19:00"), "1/32 финала"),
    ("Portugal",     "Croatia",     msk("2026-07-02 23:00"), "1/32 финала"),
    ("Switzerland",  "Algeria",     msk("2026-07-03 03:00"), "1/32 финала"),
    ("Australia",    "Egypt",       msk("2026-07-03 18:00"), "1/32 финала"),
    ("Argentina",    "Cape Verde",  msk("2026-07-03 22:00"), "1/32 финала"),
    ("Colombia",     "Ghana",       msk("2026-07-04 01:30"), "1/32 финала"),
]

def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    existing = {(r[0], r[1]) for r in c.execute("SELECT home, away FROM matches").fetchall()}

    added = 0
    for home, away, mtime, stage in R32:
        if (home, away) not in existing:
            c.execute(
                "INSERT INTO matches(home, away, mtime, stage) VALUES (?,?,?,?)",
                (home, away, mtime, stage),
            )
            added += 1
            print(f"  + {home} vs {away}  {mtime}")
        else:
            print(f"  = {home} vs {away} (уже есть)")

    conn.commit()
    conn.close()
    print(f"\nГотово! Добавлено {added} матчей. Перезапусти бота: systemctl restart wc26bot")

if __name__ == "__main__":
    main()
