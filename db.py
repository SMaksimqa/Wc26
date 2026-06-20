import sqlite3
import contextlib
from datetime import datetime

DB_PATH = "wc2026.db"


@contextlib.contextmanager
def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def init():
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY,
                username   TEXT,
                name       TEXT,
                points     INTEGER DEFAULT 0,
                is_admin   INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS matches (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                home       TEXT NOT NULL,
                away       TEXT NOT NULL,
                mtime      TEXT NOT NULL,
                stage      TEXT DEFAULT 'Группа',
                home_score INTEGER,
                away_score INTEGER,
                done       INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS bets (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  INTEGER NOT NULL,
                match_id INTEGER NOT NULL,
                bet_h    INTEGER NOT NULL,
                bet_a    INTEGER NOT NULL,
                pts      INTEGER DEFAULT 0,
                settled  INTEGER DEFAULT 0,
                UNIQUE(user_id, match_id),
                FOREIGN KEY(user_id)  REFERENCES users(id),
                FOREIGN KEY(match_id) REFERENCES matches(id)
            );
        """)


def seed():
    with _conn() as c:
        if c.execute("SELECT COUNT(*) FROM matches").fetchone()[0]:
            return
        c.executemany(
            "INSERT INTO matches(home, away, mtime, stage) VALUES (?,?,?,?)",
            [
                # Группа — ближайшие матчи
                ("Аргентина",  "Бразилия",    "2026-06-21 21:00", "Группа"),
                ("Испания",    "Германия",    "2026-06-22 18:00", "Группа"),
                ("Франция",    "Англия",      "2026-06-22 21:00", "Группа"),
                ("Португалия", "Нидерланды",  "2026-06-23 18:00", "Группа"),
                ("Бельгия",    "Италия",      "2026-06-23 21:00", "Группа"),
                ("Хорватия",   "Мексика",     "2026-06-24 18:00", "Группа"),
                ("Япония",     "Марокко",     "2026-06-24 21:00", "Группа"),
                ("США",        "Польша",      "2026-06-25 18:00", "Группа"),
                ("Австралия",  "Сенегал",     "2026-06-25 21:00", "Группа"),
                ("Уругвай",    "Колумбия",    "2026-06-26 21:00", "Группа"),
                # Плей-офф
                ("Германия",   "Франция",     "2026-07-02 21:00", "1/8 финала"),
                ("Аргентина",  "Испания",     "2026-07-03 21:00", "1/8 финала"),
                ("Бразилия",   "Португалия",  "2026-07-04 21:00", "1/8 финала"),
                ("Англия",     "Хорватия",    "2026-07-05 21:00", "1/8 финала"),
                ("Финал",      "Финал",       "2026-07-19 21:00", "Финал"),
            ],
        )


# ── USERS ──────────────────────────────────────────────────────────────────

def register(uid: int, username: str, name: str) -> bool:
    """Register user. Returns True if this is the first user (becomes admin)."""
    with _conn() as c:
        first = c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        c.execute(
            "INSERT OR IGNORE INTO users(id, username, name, is_admin) VALUES(?,?,?,?)",
            (uid, username, name, 1 if first else 0),
        )
    return first


def get_user(uid: int):
    with _conn() as c:
        return c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()


def is_admin(uid: int) -> bool:
    u = get_user(uid)
    return bool(u and u["is_admin"])


def all_users():
    with _conn() as c:
        return c.execute("SELECT * FROM users").fetchall()


def promote(uid: int):
    with _conn() as c:
        c.execute("UPDATE users SET is_admin=1 WHERE id=?", (uid,))


def leaderboard():
    with _conn() as c:
        return c.execute("""
            SELECT u.id, u.name, u.username, u.points,
                   COUNT(b.id)                                AS bets,
                   SUM(CASE WHEN b.pts > 0 THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN b.pts = 5 THEN 1 ELSE 0 END) AS exact
            FROM users u
            LEFT JOIN bets b ON u.id = b.user_id AND b.settled = 1
            GROUP BY u.id
            ORDER BY u.points DESC
        """).fetchall()


# ── MATCHES ────────────────────────────────────────────────────────────────

def upcoming(limit: int = 15):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    with _conn() as c:
        return c.execute(
            "SELECT * FROM matches WHERE mtime > ? AND done = 0 ORDER BY mtime LIMIT ?",
            (now, limit),
        ).fetchall()


def get_match(mid: int):
    with _conn() as c:
        return c.execute("SELECT * FROM matches WHERE id=?", (mid,)).fetchone()


def recent(limit: int = 5):
    with _conn() as c:
        return c.execute(
            "SELECT * FROM matches WHERE done=1 ORDER BY mtime DESC LIMIT ?",
            (limit,),
        ).fetchall()


def add_match(home: str, away: str, mtime: str, stage: str = "Группа"):
    with _conn() as c:
        c.execute(
            "INSERT INTO matches(home, away, mtime, stage) VALUES(?,?,?,?)",
            (home, away, mtime, stage),
        )


def set_result(mid: int, hs: int, as_: int) -> list:
    """
    Set final score. Returns list of dicts:
    {uid, name, bet_h, bet_a, pts}
    """
    with _conn() as c:
        c.execute(
            "UPDATE matches SET home_score=?, away_score=?, done=1 WHERE id=?",
            (hs, as_, mid),
        )
        bets = c.execute(
            """SELECT b.id, b.user_id, b.bet_h, b.bet_a, u.name
               FROM bets b JOIN users u ON b.user_id = u.id
               WHERE b.match_id = ? AND b.settled = 0""",
            (mid,),
        ).fetchall()

        results = []
        for b in bets:
            exact = b["bet_h"] == hs and b["bet_a"] == as_
            correct_outcome = (
                (b["bet_h"] > b["bet_a"]) == (hs > as_)
                and (b["bet_h"] == b["bet_a"]) == (hs == as_)
            )
            pts = 5 if exact else (2 if correct_outcome else 0)

            c.execute("UPDATE bets SET pts=?, settled=1 WHERE id=?", (pts, b["id"]))
            if pts:
                c.execute(
                    "UPDATE users SET points = points + ? WHERE id=?",
                    (pts, b["user_id"]),
                )
            results.append(
                {"uid": b["user_id"], "name": b["name"],
                 "bet_h": b["bet_h"], "bet_a": b["bet_a"], "pts": pts}
            )
    return results


# ── BETS ───────────────────────────────────────────────────────────────────

def place_bet(uid: int, mid: int, h: int, a: int) -> tuple[bool, str]:
    m = get_match(mid)
    if not m:
        return False, "Матч не найден"
    mt = datetime.strptime(m["mtime"], "%Y-%m-%d %H:%M")
    if datetime.now() >= mt:
        return False, "Ставки закрыты — матч уже начался ⏱️"
    if m["done"]:
        return False, "Матч уже завершён!"
    with _conn() as c:
        c.execute(
            """INSERT INTO bets(user_id, match_id, bet_h, bet_a) VALUES(?,?,?,?)
               ON CONFLICT(user_id, match_id)
               DO UPDATE SET bet_h=excluded.bet_h, bet_a=excluded.bet_a, settled=0, pts=0""",
            (uid, mid, h, a),
        )
    return True, "ok"


def my_bets(uid: int):
    with _conn() as c:
        return c.execute(
            """SELECT b.bet_h, b.bet_a, b.pts, b.settled,
                      m.id AS match_id, m.home, m.away, m.mtime, m.stage,
                      m.home_score AS rh, m.away_score AS ra, m.done
               FROM bets b JOIN matches m ON b.match_id = m.id
               WHERE b.user_id = ?
               ORDER BY m.mtime DESC""",
            (uid,),
        ).fetchall()


def match_bets(mid: int):
    with _conn() as c:
        return c.execute(
            """SELECT b.bet_h, b.bet_a, b.pts, b.user_id, u.name, u.username
               FROM bets b JOIN users u ON b.user_id = u.id
               WHERE b.match_id = ?""",
            (mid,),
        ).fetchall()


def missing_bettors(mid: int):
    with _conn() as c:
        return c.execute(
            """SELECT id, name FROM users
               WHERE id NOT IN (SELECT user_id FROM bets WHERE match_id=?)""",
            (mid,),
        ).fetchall()
