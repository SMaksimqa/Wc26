#!/usr/bin/env python3
"""Replace placeholder matches with real WC 2026 schedule."""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "wc2026.db")

# (home, away, mtime, stage, home_score, away_score, done)
MATCHES = [
    # ── Round 1  (Jun 11-17) ── all finished ──────────────────────
    ("Mexico",       "South Africa", "2026-06-11 19:00", "Group A",  2, 0, 1),
    ("South Korea",  "Czechia",      "2026-06-12 02:00", "Group A",  2, 1, 1),
    ("Canada",       "Bosnia",       "2026-06-12 19:00", "Group B",  1, 1, 1),
    ("Qatar",        "Switzerland",  "2026-06-13 19:00", "Group B",  1, 1, 1),
    ("Brazil",       "Morocco",      "2026-06-13 22:00", "Group C",  1, 1, 1),
    ("Haiti",        "Scotland",     "2026-06-14 01:00", "Group C",  0, 1, 1),
    ("USA",          "Paraguay",     "2026-06-14 01:00", "Group D",  4, 1, 1),
    ("Australia",    "Turkey",       "2026-06-14 04:00", "Group D",  2, 0, 1),
    ("Germany",      "Curaçao",      "2026-06-14 17:00", "Group E",  7, 1, 1),
    ("Ivory Coast",  "Ecuador",      "2026-06-14 23:00", "Group E",  1, 0, 1),
    ("Netherlands",  "Japan",        "2026-06-14 20:00", "Group F",  2, 2, 1),
    ("Sweden",       "Tunisia",      "2026-06-15 02:00", "Group F",  5, 1, 1),
    ("Belgium",      "Egypt",        "2026-06-15 19:00", "Group G",  1, 1, 1),
    ("Iran",         "New Zealand",  "2026-06-16 01:00", "Group G",  2, 2, 1),
    ("Spain",        "Cape Verde",   "2026-06-15 16:00", "Group H",  0, 0, 1),
    ("Saudi Arabia", "Uruguay",      "2026-06-15 22:00", "Group H",  1, 1, 1),
    ("France",       "Senegal",      "2026-06-16 19:00", "Group I",  3, 1, 1),
    ("Iraq",         "Norway",       "2026-06-16 22:00", "Group I",  1, 4, 1),
    ("Argentina",    "Algeria",      "2026-06-17 01:00", "Group J",  3, 0, 1),
    ("Austria",      "Jordan",       "2026-06-17 04:00", "Group J",  3, 1, 1),
    ("Portugal",     "DR Congo",     "2026-06-17 17:00", "Group K",  1, 1, 1),
    ("Uzbekistan",   "Colombia",     "2026-06-18 02:00", "Group K",  1, 3, 1),
    ("England",      "Croatia",      "2026-06-17 20:00", "Group L",  4, 2, 1),
    ("Ghana",        "Panama",       "2026-06-17 23:00", "Group L",  1, 0, 1),
    # ── Round 2  (Jun 18-20) ── all finished ──────────────────────
    ("Czechia",      "South Africa", "2026-06-18 16:00", "Group A",  1, 1, 1),
    ("Mexico",       "South Korea",  "2026-06-19 01:00", "Group A",  1, 0, 1),
    ("Switzerland",  "Bosnia",       "2026-06-18 19:00", "Group B",  4, 1, 1),
    ("Canada",       "Qatar",        "2026-06-18 22:00", "Group B",  6, 0, 1),
    ("Scotland",     "Morocco",      "2026-06-19 22:00", "Group C",  0, 1, 1),
    ("Brazil",       "Haiti",        "2026-06-20 00:30", "Group C",  3, 0, 1),
    ("USA",          "Australia",    "2026-06-19 19:00", "Group D",  2, 0, 1),
    ("Turkey",       "Paraguay",     "2026-06-20 03:00", "Group D",  0, 1, 1),
    ("Netherlands",  "Sweden",       "2026-06-20 17:00", "Group F",  5, 1, 1),
    # Match 33 — Germany vs Ivory Coast — live/tonight, leave open
    ("Germany",      "Ivory Coast",  "2026-06-20 20:00", "Group E",  None, None, 0),
    # ── Round 2 cont. ─────────────────────────────────────────────
    ("Ecuador",      "Curaçao",      "2026-06-21 00:00", "Group E",  None, None, 0),
    ("Tunisia",      "Japan",        "2026-06-21 04:00", "Group F",  None, None, 0),
    ("Spain",        "Saudi Arabia", "2026-06-21 16:00", "Group H",  None, None, 0),
    ("Belgium",      "Iran",         "2026-06-21 19:00", "Group G",  None, None, 0),
    ("Uruguay",      "Cape Verde",   "2026-06-21 22:00", "Group H",  None, None, 0),
    ("New Zealand",  "Egypt",        "2026-06-22 01:00", "Group G",  None, None, 0),
    ("Argentina",    "Austria",      "2026-06-22 17:00", "Group J",  None, None, 0),
    ("France",       "Iraq",         "2026-06-22 21:00", "Group I",  None, None, 0),
    ("Norway",       "Senegal",      "2026-06-23 00:00", "Group I",  None, None, 0),
    ("Jordan",       "Algeria",      "2026-06-23 03:00", "Group J",  None, None, 0),
    ("Portugal",     "Uzbekistan",   "2026-06-23 17:00", "Group K",  None, None, 0),
    ("England",      "Ghana",        "2026-06-23 20:00", "Group L",  None, None, 0),
    ("Panama",       "Croatia",      "2026-06-23 23:00", "Group L",  None, None, 0),
    ("Colombia",     "DR Congo",     "2026-06-24 02:00", "Group K",  None, None, 0),
    # ── Round 3  (Jun 24-28) ──────────────────────────────────────
    ("Switzerland",  "Canada",       "2026-06-24 19:00", "Group B",  None, None, 0),
    ("Bosnia",       "Qatar",        "2026-06-24 19:00", "Group B",  None, None, 0),
    ("Scotland",     "Brazil",       "2026-06-24 22:00", "Group C",  None, None, 0),
    ("Morocco",      "Haiti",        "2026-06-24 22:00", "Group C",  None, None, 0),
    ("Czechia",      "Mexico",       "2026-06-25 01:00", "Group A",  None, None, 0),
    ("South Africa", "South Korea",  "2026-06-25 01:00", "Group A",  None, None, 0),
    ("Curaçao",      "Ivory Coast",  "2026-06-25 20:00", "Group E",  None, None, 0),
    ("Ecuador",      "Germany",      "2026-06-25 20:00", "Group E",  None, None, 0),
    ("Japan",        "Sweden",       "2026-06-25 23:00", "Group F",  None, None, 0),
    ("Tunisia",      "Netherlands",  "2026-06-25 23:00", "Group F",  None, None, 0),
    ("Turkey",       "USA",          "2026-06-26 02:00", "Group D",  None, None, 0),
    ("Paraguay",     "Australia",    "2026-06-26 02:00", "Group D",  None, None, 0),
    ("Norway",       "France",       "2026-06-26 19:00", "Group I",  None, None, 0),
    ("Senegal",      "Iraq",         "2026-06-26 19:00", "Group I",  None, None, 0),
    ("Cape Verde",   "Saudi Arabia", "2026-06-27 00:00", "Group H",  None, None, 0),
    ("Uruguay",      "Spain",        "2026-06-27 00:00", "Group H",  None, None, 0),
    ("Egypt",        "Iran",         "2026-06-27 03:00", "Group G",  None, None, 0),
    ("New Zealand",  "Belgium",      "2026-06-27 03:00", "Group G",  None, None, 0),
    ("Colombia",     "Portugal",     "2026-06-27 23:30", "Group K",  None, None, 0),
    ("DR Congo",     "Uzbekistan",   "2026-06-27 23:30", "Group K",  None, None, 0),
    ("Panama",       "England",      "2026-06-27 21:00", "Group L",  None, None, 0),
    ("Croatia",      "Ghana",        "2026-06-27 21:00", "Group L",  None, None, 0),
    ("Algeria",      "Austria",      "2026-06-28 02:00", "Group J",  None, None, 0),
    ("Jordan",       "Argentina",    "2026-06-28 02:00", "Group J",  None, None, 0),
]


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    print("Clearing old placeholder matches and bets...")
    c.execute("DELETE FROM bets")
    c.execute("DELETE FROM matches")
    c.execute("UPDATE users SET points = 0")
    try:
        c.execute("DELETE FROM sqlite_sequence WHERE name='matches'")
    except Exception:
        pass

    print(f"Inserting {len(MATCHES)} real WC 2026 matches...")
    for home, away, mtime, stage, hs, as_, done in MATCHES:
        c.execute(
            "INSERT INTO matches(home, away, mtime, stage, home_score, away_score, done) "
            "VALUES (?,?,?,?,?,?,?)",
            (home, away, mtime, stage, hs, as_, done),
        )

    conn.commit()
    conn.close()
    print(f"Done! {len(MATCHES)} matches loaded.")
    print("Restart bot: systemctl restart wc26bot")


if __name__ == "__main__":
    main()
