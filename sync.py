"""Auto-sync WC 2026 results from 26worldcup.github.io (updates every 15 min from FIFA API)."""
import logging
import random
import aiohttp
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


async def check_results(bot) -> int:
    """
    Fetch latest results, settle unsettled matches, broadcast to users.
    Returns number of newly settled matches.
    """
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(MATCHES_URL, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    log.warning("sync: HTTP %s", r.status)
                    return 0
                payload = await r.json(content_type=None)
                api_matches = payload.get("matches", payload)
    except Exception as e:
        log.warning("sync: fetch error: %s", e)
        return 0

    settled = 0
    for m_api in api_matches:
        if m_api.get("status") != "finished":
            continue

        h_code = m_api["home"]["code"]
        a_code = m_api["away"]["code"]
        h_score = m_api["home"].get("score")
        a_score = m_api["away"].get("score")

        if h_score is None or a_score is None:
            continue

        home = CODE.get(h_code)
        away = CODE.get(a_code)
        if not home or not away:
            log.debug("sync: unknown code %s/%s", h_code, a_code)
            continue

        match = db.find_match_by_teams(home, away)
        if not match:
            continue  # already settled or not in our DB

        log.info("sync: settling #%d %s %d–%d %s", match["id"], home, h_score, a_score, away)
        results = db.set_result(match["id"], h_score, a_score)
        settled += 1

        await _broadcast_result(bot, match, h_score, a_score, results)

    if settled:
        log.info("sync: settled %d match(es)", settled)
    return settled


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
            if r["pts"] == 5:
                text += f"{random.choice(WIN_EXACT)} — *{r['name']}* +5 очков\n"
            elif r["pts"] == 2:
                text += f"{random.choice(WIN_OUT)} — *{r['name']}* +2 очка\n"
            else:
                text += f"{random.choice(LOSE)} — {r['name']} (ставил {r['bet_h']}–{r['bet_a']})\n"
    else:
        text += "_(никто не поставил на этот матч)_"

    for u in db.all_users():
        try:
            await bot.send_message(u["id"], text, parse_mode="Markdown")
        except Exception as e:
            log.warning("sync: send to %s failed: %s", u["id"], e)
