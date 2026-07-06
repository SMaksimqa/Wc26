#!/usr/bin/env python3
"""Add Round of 16 (1/16 финала) matches. Safe to run multiple times."""
import sqlite3, os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "wc2026.db")
MSK = timedelta(hours=3)


def msk(utc: str) -> str:
    return (datetime.strptime(utc, "%Y-%m-%d %H:%M") + MSK).strftime("%Y-%m-%d %H:%M")


# Round of 16 — данные из API (26worldcup.github.io)
# Времена UTC → MSK (+3)
R16 = [
    ("Canada",      "Morocco",     msk("2026-07-04 17:00"), "1/16 финала"),
    ("Paraguay",    "France",      msk("2026-07-04 21:00"), "1/16 финала"),
    ("Brazil",      "Norway",      msk("2026-07-05 20:00"), "1/16 финала"),
    ("Mexico",      "England",     msk("2026-07-06 01:00"), "1/16 финала"),
    ("Portugal",    "Spain",       msk("2026-07-06 19:00"), "1/16 финала"),
    ("USA",         "Belgium",     msk("2026-07-07 00:00"), "1/16 финала"),
    ("Argentina",   "Egypt",       msk("2026-07-07 16:00"), "1/16 финала"),
    ("Switzerland", "Colombia",    msk("2026-07-07 20:00"), "1/16 финала"),
]


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    existing = {(r[0], r[1]) for r in c.execute("SELECT home, away FROM matches").fetchall()}

    added = 0
    for home, away, mtime, stage in R16:
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
    print(f"\nГотово! Добавлено {added} матчей.")
    if added:
        print("Перезапусти бота: systemctl restart wc26bot")


if __name__ == "__main__":
    main()
