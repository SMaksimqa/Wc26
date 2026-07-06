"""Auto-sync WC 2026 results from 26worldcup.github.io (updates every 15 min from FIFA API)."""
import logging
import random
import aiohttp
from datetime import datetime, timedelta
import db

log = logging.getLogger(__name__)

MATCHES_URL = (
    "https://raw.githubusercontent.com/26worldcup/26worldcup.github.io"
    "/main/public/data/matches.json"
)

# FIFA 3-letter code → our DB team name
CODE = {
    "MEX": "Mexico",       "RSA": "South Africa", "KOR": "South Korea",
    "CZE": "Czechia",      "CAN": "Canada",        "BIH": "Bosnia",
    "QAT": "Qatar",        "SUI": "Switzerland",   "BRA": "Brazil",
    "MAR": "Morocco",      "HAI": "Haiti",          "SCO": "Scotland",
    "USA": "USA",          "PAR": "Paraguay",       "AUS": "Australia",
    "TUR": "Turkey",       "GER": "Germany",        "CUW": "Curaçao",
    "NED": "Netherlands",  "JPN": "Japan",           "SWE": "Sweden",
    "TUN": "Tunisia",      "BEL": "Belgium",         "EGY": "Egypt",
    "IRN": "Iran",         "NZL": "New Zealand",     "ESP": "Spain",
    "CPV": "Cape Verde",   "KSA": "Saudi Arabia",   "URU": "Uruguay",
    "FRA": "France",       "SEN": "Senegal",         "IRQ": "Iraq",
    "NOR": "Norway",       "ARG": "Argentina",       "ALG": "Algeria",
    "AUT": "Austria",      "JOR": "Jordan",          "POR": "Portugal",
    "COD": "DR Congo",     "UZB": "Uzbekistan",      "COL": "Colombia",
    "ENG": "England",      "CRO": "Croatia",         "GHA": "Ghana",
    "PAN": "Panama",       "CIV": "Ivory Coast",     "ECU": "Ecuador",
}

STAGE_NAMES = {
    "group":        lambda g: f"Group {g}" if g else "Группа",
    "round_of_32":  lambda g: "1/32 финала",
    "r32":          lambda g: "1/32 финала",
    "round_of_16":  lambda g: "1/16 финала",
    "r16":          lambda g: "1/16 финала",
    "quarter_final": lambda g: "Четвертьфинал",
    "qf":           lambda g: "Четвертьфинал",
    "semi_final":   lambda g: "Полуфинал",
    "sf":           lambda g: "Полуфинал",
    "final":        lambda g: "Финал",
    "f":            lambda g: "Финал",
}

FLAGS = {
    "Mexico": "🇲🇽", "South Africa": "🇿🇦", "South Korea": "🇰🇷",
    "Czechia": "🇨🇿", "Canada": "🇨🇦", "Bosnia": "🇧🇦",
    "Qatar": "🇶🇦", "Switzerland": "🇨🇭", "Brazil": "🇧🇷",
    "Morocco": "🇲🇦", "Haiti": "🇭🇹", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    "USA": "🇺🇸", "Paraguay": "🇵🇾", "Australia": "🇦🇺",
    "Turkey": "🇹🇷", "Germany": "🇩🇪", "Curaçao": "🇨🇼",
    "Netherlands": "🇳🇱", "Japan": "🇯🇵", "Sweden": "🇸🇪",
    "Tunisia": "🇹🇳", "Belgium": "🇧🇪", "Egypt": "🇪🇬",
    "Iran": "🇮🇷", "New Zealand": "🇳🇿", "Spain": "🇪🇸",
    "Cape Verde": "🇨🇻", "Saudi Arabia": "🇸🇦", "Uruguay": "🇺🇾",
    "France": "🇫🇷", "Senegal": "🇸🇳", "Iraq": "🇮🇶",
    "Norway": "🇳🇴", "Argentina": "🇦🇷", "Algeria": "🇩🇿",
    "Austria": "🇦🇹", "Jordan": "🇯🇴", "Portugal": "🇵🇹",
    "DR Congo": "🇨🇩", "Uzbekistan": "🇺🇿", "Colombia": "🇨🇴",
    "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Croatia": "🇭🇷", "Ghana": "🇬🇭",
    "Panama": "🇵🇦", "Ivory Coast": "🇨🇮", "Ecuador": "🇪🇨",
}

WIN_EXACT = ["🔮 ОРАКУЛ! Точный счёт!", "🧠 МОЗГ! Угадал точно!", "🎯 СНАЙПЕР!"]
WIN_OUT   = ["✅ Исход угадал", "👍 Верное направление", "✅ Победителя поймал"]
LOSE      = ["❌ Мимо", "💀 Эх, не угадал", "❌ Попробуй в следующий раз"]


def _flag(team: str) -> str:
    return FLAGS.get(team, "⚽")


def _get_score(team_data: dict):
    """Extract score safely — handles 0 goals correctly."""
    for field in ("score", "goals", "ft_score"):
        val = team_data.get(field)
        if val is not None:
            return int(val)
    return None


def _parse_msk_time(date_str: str) -> str:
    """Convert ISO UTC timestamp to MSK (UTC+3) string."""
    dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
    return (dt + timedelta(hours=3)).strftime("%Y-%m-%d %H:%M")


def _format_stage(api_stage: str, group: str) -> str:
    fn = STAGE_NAMES.get(api_stage.lower())
    if fn:
        return fn(group)
    return api_stage.replace("_", " ").title()


async def check_results(bot) -> tuple[int, int]:
    """
    Fetch latest data, add new matches, settle finished ones, broadcast results.
    Returns (settled, added) counts.
    """
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(MATCHES_URL, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    log.warning("sync: HTTP %s", r.status)
                    return 0, 0
                payload = await r.json(content_type=None)
                api_matches = payload.get("matches", payload)
    except Exception as e:
        log.warning("sync: fetch error: %s", e)
        return 0, 0

    settled = 0
    added = 0

    for m_api in api_matches:
        h_code = "?"
        a_code = "?"
        try:
            if not m_api:
                continue
            if not m_api.get("home") or not m_api.get("away"):
                continue  # TBD matches (SF/Final placeholders)

            h_code = m_api["home"].get("code", "")
            a_code = m_api["away"].get("code", "")

            home = CODE.get(h_code)
            away = CODE.get(a_code)
            if not home or not away:
                log.debug("sync: unknown code %s/%s", h_code, a_code)
                continue

            api_stage = m_api.get("stage", "group")
            group = m_api.get("group", "")
            stage = _format_stage(api_stage, group)

            # Auto-add new matches not yet in DB
            if not db.match_exists(home, away):
                mtime = _parse_msk_time(m_api["date"])
                db.add_match(home, away, mtime, stage)
                log.info("sync: added %s vs %s at %s [%s]", home, away, mtime, stage)
                added += 1

            if m_api.get("status") != "finished":
                continue

            h_score = _get_score(m_api["home"])
            a_score = _get_score(m_api["away"])

            if h_score is None or a_score is None:
                log.warning("sync: finished %s/%s has no score", h_code, a_code)
                continue

            match = db.find_match_by_teams(home, away)
            if not match:
                log.debug("sync: %s vs %s already settled or not in DB", home, away)
                continue

            log.info("sync: settling #%d %s %d–%d %s", match["id"], home, h_score, a_score, away)
            results = db.set_result(match["id"], h_score, a_score)
            settled += 1

            try:
                await _broadcast_result(bot, match, h_score, a_score, results)
                log.info("sync: broadcast sent for #%d %s vs %s", match["id"], home, away)
            except Exception as e:
                log.exception("sync: broadcast FAILED for #%d %s vs %s: %s", match["id"], home, away, e)

        except Exception as e:
            log.exception("sync: unhandled error on %s/%s: %s", h_code, a_code, e)

    if settled:
        log.info("sync: settled %d match(es)", settled)
        if settled >= 2:
            await _broadcast_standings(bot)
    if added:
        log.info("sync: added %d new match(es)", added)

    return settled, added


async def _broadcast_standings(bot):
    """Send updated leaderboard after a batch of results."""
    rows = db.leaderboard()
    if not rows:
        return

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]
    lines = ["🏆 *Таблица лидеров — актуально:*\n"]
    for i, r in enumerate(rows):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        name = r["name"] or r["username"] or "Аноним"
        lines.append(
            f"{medal} *{name}* — {r['points']} очков  "
            f"_(🔮{r['exact'] or 0} точных)_"
        )

    if len(rows) > 1:
        last = rows[-1]
        last_name = last["name"] or "Аноним"
        roasts = [
            f"\n😂 *{last_name}* — последнее место. Позорище!",
            f"\n💀 *{last_name}* — на дне. Пора завязывать с футболом!",
            f"\n🤡 *{last_name}* — аутсайдер тура. Без комментариев!",
        ]
        lines.append(random.choice(roasts))

    text = "\n".join(lines)
    for u in db.all_users():
        try:
            await bot.send_message(u["id"], text, parse_mode="Markdown")
        except Exception as e:
            log.warning("standings: send to %s failed: %s", u["id"], e)


async def _broadcast_result(bot, match, hs: int, as_: int, results: list):
    h, a = match["home"], match["away"]

    text = (
        f"⚽ *ФИНАЛЬНЫЙ СВИСТОК!*\n\n"
        f"{_flag(h)} *{h} {hs}–{as_} {a}* {_flag(a)}\n"
        f"_{match['stage']}_\n\n"
    )

    if results:
        text += "📊 *Итоги ставок:*\n"
        for r in results:
            bet = f"{r['bet_h']}–{r['bet_a']}"
            if r["pts"] == 5:
                text += f"{random.choice(WIN_EXACT)} — *{r['name']}* ставил {bet} +5 очков\n"
            elif r["pts"] == 2:
                text += f"{random.choice(WIN_OUT)} — *{r['name']}* ставил {bet} +2 очка\n"
            else:
                text += f"{random.choice(LOSE)} — {r['name']} ставил {bet}\n"
    else:
        text += "_(никто не поставил на этот матч)_"

    import asyncio
    for u in db.all_users():
        for attempt in range(3):
            try:
                await bot.send_message(u["id"], text, parse_mode="Markdown")
                break
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                else:
                    log.warning("sync: send to %s failed after 3 attempts: %s", u["id"], e)
