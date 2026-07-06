#!/usr/bin/env python3
"""
Add Round of 16 (1/16 финала) matches.
EDIT the R16 list below with actual teams and times before running!
Safe to run multiple times — skips matches already in DB.
"""
import sqlite3, os, sys
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "wc2026.db")
MSK = timedelta(hours=3)

PLACEHOLDER = "TBD"


def msk(utc: str) -> str:
    """Convert UTC time string to MSK (+3)."""
    return (datetime.strptime(utc, "%Y-%m-%d %H:%M") + MSK).strftime("%Y-%m-%d %H:%M")


# ── EDIT THIS LIST WITH REAL TEAMS AND UTC TIMES ─────────────────────────────
# Format: (home_team, away_team, msk(utc_time), stage)
# Example: ("Portugal", "Spain", msk("2026-07-06 19:00"), "1/16 финала")
# Times are in UTC — msk() converts to Moscow time automatically.
R16 = [
    # July 6
    ("Portugal",    "Spain",       msk("2026-07-06 19:00"), "1/16 финала"),
    (PLACEHOLDER,   PLACEHOLDER,   msk("2026-07-06 22:30"), "1/16 финала"),
    # July 7
    (PLACEHOLDER,   PLACEHOLDER,   msk("2026-07-07 19:00"), "1/16 финала"),
    (PLACEHOLDER,   PLACEHOLDER,   msk("2026-07-07 22:30"), "1/16 финала"),
    # July 8
    (PLACEHOLDER,   PLACEHOLDER,   msk("2026-07-08 19:00"), "1/16 финала"),
    (PLACEHOLDER,   PLACEHOLDER,   msk("2026-07-08 22:30"), "1/16 финала"),
    # July 9
    (PLACEHOLDER,   PLACEHOLDER,   msk("2026-07-09 19:00"), "1/16 финала"),
    (PLACEHOLDER,   PLACEHOLDER,   msk("2026-07-09 22:30"), "1/16 финала"),
]
# ─────────────────────────────────────────────────────────────────────────────


def main():
    placeholders = [(h, a, t, s) for h, a, t, s in R16 if h == PLACEHOLDER or a == PLACEHOLDER]
    if placeholders:
        print(f"⚠️  {len(placeholders)} матчей с TBD — заполни команды в R16 перед запуском!")
        print("Добавляю только готовые матчи...\n")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    existing = {(r[0], r[1]) for r in c.execute("SELECT home, away FROM matches").fetchall()}

    added = 0
    for home, away, mtime, stage in R16:
        if home == PLACEHOLDER or away == PLACEHOLDER:
            continue
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
