#!/usr/bin/env python3
"""⚽ ЧМ 2026 Ставки — Telegram Bot"""

import logging
import os
import random
from datetime import datetime, timedelta, time as dt_time, timezone

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import db
import sync as syncer

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set in .env")

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# ── CONSTANTS ──────────────────────────────────────────────────────────────

TRASH = [
    "Ставку не сделал — значит проиграл! 😈",
    "Все уже поставили, а ты спишь? 😴",
    "Не ставишь — не выигрываешь! 🤷",
    "Слабак не поставил — ждёт чужих побед 😂",
    "Эй, матч уже скоро, а ставки нет! ⏰",
]

TRASH_MORNING = [
    "😴 {names} дрыхнут и ставки не делают! Позор!",
    "🤡 {names} — что, кишка тонка поставить?",
    "🦥 {names} ленятся. Давайте уже, матчи сами себя не угадают!",
    "⚠️ {names} ещё не поставили. Проспите турнир!",
    "😂 {names} — последние как всегда. Ставки сами себя не делают!",
]

TRASH_REVEAL = [
    "💀 Слились и не поставили: *{names}*",
    "🤡 *{names}* — испугались? Ставок нет!",
    "😴 *{names}* проспали ставку. Позорники!",
    "🦥 *{names}* — где ставки? Трусы!",
]

MOTIVATE = [
    "Отличный выбор! 🎯",
    "Посмотрим, угадаешь ли... 😏",
    "Уверен в себе? 🔥",
    "Смелая ставка! 💪",
    "Оракул в деле! 🔮",
    "Ставка принята, удачи! 🍀",
]

FLAGS = {
    # Group A
    "Mexico": "🇲🇽", "South Korea": "🇰🇷", "Czechia": "🇨🇿", "South Africa": "🇿🇦",
    # Group B
    "Canada": "🇨🇦", "Qatar": "🇶🇦", "Switzerland": "🇨🇭", "Bosnia": "🇧🇦",
    # Group C
    "Brazil": "🇧🇷", "Morocco": "🇲🇦", "Haiti": "🇭🇹", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    # Group D
    "USA": "🇺🇸", "Turkey": "🇹🇷", "Australia": "🇦🇺", "Paraguay": "🇵🇾",
    # Group E
    "Germany": "🇩🇪", "Netherlands": "🇳🇱", "Ivory Coast": "🇨🇮",
    "Ecuador": "🇪🇨", "Curaçao": "🇨🇼",
    # Group F
    "Sweden": "🇸🇪", "Japan": "🇯🇵", "Tunisia": "🇹🇳",
    # Group G
    "Belgium": "🇧🇪", "Iran": "🇮🇷", "Egypt": "🇪🇬", "New Zealand": "🇳🇿",
    # Group H
    "Spain": "🇪🇸", "Saudi Arabia": "🇸🇦", "Uruguay": "🇺🇾", "Cape Verde": "🇨🇻",
    # Group I
    "France": "🇫🇷", "Norway": "🇳🇴", "Senegal": "🇸🇳", "Iraq": "🇮🇶",
    # Group J
    "Argentina": "🇦🇷", "Austria": "🇦🇹", "Algeria": "🇩🇿", "Jordan": "🇯🇴",
    # Group K
    "Portugal": "🇵🇹", "Colombia": "🇨🇴", "DR Congo": "🇨🇩", "Uzbekistan": "🇺🇿",
    # Group L
    "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Croatia": "🇭🇷", "Ghana": "🇬🇭", "Panama": "🇵🇦",
    # Extras
    "Italy": "🇮🇹", "Poland": "🇵🇱", "Denmark": "🇩🇰", "Serbia": "🇷🇸",
    "Nigeria": "🇳🇬", "Chile": "🇨🇱", "Wales": "🏴󠁧󠁢󠁷󠁬󠁳󠁿", "Ukraine": "🇺🇦",
}


MAIN_KB = ReplyKeyboardMarkup(
    [
        ["⚽ Матчи",       "🎯 Ставка"],
        ["📋 Мои ставки",  "👥 Ставки"],
        ["🏆 Лидеры",      "📊 Результаты"],
        ["❓ Помощь"],
    ],
    resize_keyboard=True,
    is_persistent=True,
)


def flag(team: str) -> str:
    return FLAGS.get(team, "⚽")


def fmt_match(m) -> str:
    dt = datetime.strptime(m["mtime"], "%Y-%m-%d %H:%M")
    return (
        f"{flag(m['home'])} {m['home']} vs {m['away']} {flag(m['away'])}\n"
        f"📅 {dt.strftime('%d.%m  %H:%M')} | {m['stage']}"
    )


def outcome_text(h: int, a: int, home: str, away: str) -> str:
    if h > a:
        return f"победа {home}"
    if h < a:
        return f"победа {away}"
    return "ничья"


# ── SCORE KEYBOARDS ────────────────────────────────────────────────────────

def _score_row(prefix: str, mid: int, extra: str = "") -> list:
    row = []
    for i in range(6):
        cd = f"{prefix}_{mid}_{i}" if not extra else f"{prefix}_{mid}_{extra}_{i}"
        row.append(InlineKeyboardButton(str(i), callback_data=cd))
    return row


def kb_home(mid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        _score_row("bh", mid),
        [InlineKeyboardButton("❌ Отмена", callback_data="bx")],
    ])


def kb_away(mid: int, h: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        _score_row("ba", mid, str(h)),
        [InlineKeyboardButton("❌ Отмена", callback_data="bx")],
    ])


def kb_confirm(mid: int, h: int, a: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"bc_{mid}_{h}_{a}"),
        InlineKeyboardButton("🔄 Изменить",    callback_data=f"bm_{mid}"),
    ], [
        InlineKeyboardButton("❌ Отмена", callback_data="bx"),
    ]])


# ── HELPERS ────────────────────────────────────────────────────────────────

async def _send_all(bot, text: str, exclude_id: int | None = None):
    for u in db.all_users():
        if exclude_id and u["id"] == exclude_id:
            continue
        try:
            await bot.send_message(u["id"], text, parse_mode="Markdown")
        except Exception as e:
            log.warning("send_all failed for %s: %s", u["id"], e)


# ── USER COMMANDS ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    first = db.register(u.id, u.username or "", u.first_name)
    admin_note = "\n\n👑 Ты первый — ты *АДМИНИСТРАТОР!*" if first else ""
    await update.message.reply_text(
        f"⚽ Привет, *{u.first_name}*! Добро пожаловать в *ЧМ 2026 Ставки*!\n\n"
        f"Используй кнопки внизу 👇{admin_note}",
        parse_mode="Markdown",
        reply_markup=MAIN_KB,
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = (
        "⚽ *ЧМ 2026 Ставки — Помощь*\n\n"
        "🎯 *Очки:*\n"
        "• Угадал победителя / ничью → *2 очка*\n"
        "• Угадал точный счёт → *5 очков*\n\n"
        "📌 *Команды:*\n"
        "/matches — ближайшие матчи\n"
        "/bet — сделать ставку\n"
        "/mybets — мои ставки\n"
        "/leaderboard — таблица лидеров\n"
        "/results — последние результаты\n"
        "/myid — получить свой Telegram ID\n"
    )
    if db.is_admin(uid):
        text += (
            "\n👑 *Админ-команды:*\n"
            "/addmatch `<Кто> <Кто> <ГГГГ-ММ-ДД> <ЧЧ:ММ> [Этап]`\n"
            "/setresult `<id_матча> <счёт>` _(пример: 2\\-1)_\n"
            "/allbets `<id_матча>` — все ставки на матч\n"
            "/broadcast `<текст>` — написать всем\n"
            "/promote `<user_id>` — сделать админом\n"
        )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_myid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(f"🆔 Твой Telegram ID: `{uid}`", parse_mode="Markdown")


async def cmd_matches(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    matches = db.upcoming(15)
    if not matches:
        await update.message.reply_text("😴 Нет предстоящих матчей")
        return

    lines = ["⚽ *Ближайшие матчи:*\n"]
    for m in matches:
        bets = db.match_bets(m["id"])
        my = next((b for b in bets if b["user_id"] == uid), None)
        bet_line = f"  ✅ Ставка: {my['bet_h']}–{my['bet_a']}" if my else "  ⬜ Не поставил"
        lines.append(f"*#{m['id']}* {fmt_match(m)}\n{bet_line}\n")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_bet(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not db.get_user(uid):
        await update.message.reply_text("Сначала напиши /start!")
        return

    matches = db.upcoming(12)
    if not matches:
        await update.message.reply_text("😴 Нет матчей для ставок")
        return

    bets_all = {b["user_id"]: b for m in matches for b in db.match_bets(m["id"]) if b["user_id"] == uid}

    kb = []
    for m in matches:
        bets = db.match_bets(m["id"])
        my = next((b for b in bets if b["user_id"] == uid), None)
        dt = datetime.strptime(m["mtime"], "%Y-%m-%d %H:%M")
        label = (
            f"{'✅' if my else '⬜'} #{m['id']} "
            f"{m['home']} vs {m['away']} "
            f"({dt.strftime('%d.%m %H:%M')})"
        )
        kb.append([InlineKeyboardButton(label, callback_data=f"bm_{m['id']}")])

    kb.append([InlineKeyboardButton("❌ Закрыть", callback_data="bx")])
    await update.message.reply_text(
        "⚽ Выбери матч:\n_(✅ = уже поставил, можно изменить)_",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


async def cmd_mybets(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bets = db.my_bets(uid)
    if not bets:
        await update.message.reply_text("📭 Ставок пока нет\n\nДелай /bet!")
        return

    lines = ["🎯 *Твои ставки:*\n"]
    for b in bets:
        dt = datetime.strptime(b["mtime"], "%Y-%m-%d %H:%M")
        if b["done"]:
            if b["pts"] == 5:
                status = "🔮 Точный счёт! +5 очков"
            elif b["pts"] == 2:
                status = "✅ Исход угадал +2 очка"
            else:
                status = f"❌ Мимо (итог: {b['rh']}–{b['ra']})"
        else:
            status = "⏳ Ждём результата"

        lines.append(
            f"{flag(b['home'])} *{b['home']}* vs *{b['away']}* {flag(b['away'])}\n"
            f"📅 {dt.strftime('%d.%m %H:%M')} | {b['stage']}\n"
            f"🎯 Ставка: {b['bet_h']}–{b['bet_a']}  {status}\n"
        )

    total = sum(b["pts"] for b in bets if b["settled"])
    lines.append(f"💰 *Итого очков: {total}*")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_show_bets(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show all friends' bets on upcoming matches."""
    matches = db.upcoming(10)
    all_users = db.all_users()
    if not matches:
        await update.message.reply_text("😴 Нет предстоящих матчей")
        return

    lines = ["👥 *Ставки на предстоящие матчи:*\n"]
    for m in matches[:6]:
        dt = datetime.strptime(m["mtime"], "%Y-%m-%d %H:%M")
        bets = db.match_bets(m["id"])
        bet_map = {b["user_id"]: b for b in bets}

        lines.append(
            f"⚽ {flag(m['home'])} *{m['home']}* vs *{m['away']}* {flag(m['away'])}\n"
            f"🕐 {dt.strftime('%d.%m %H:%M')} | {m['stage']}"
        )
        for u in all_users:
            b = bet_map.get(u["id"])
            if b:
                lines.append(f"  ✅ {u['name']}: {b['bet_h']}–{b['bet_a']}")
            else:
                lines.append(f"  ❓ {u['name']}: не поставил")
        lines.append("")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = db.leaderboard()
    if not rows:
        await update.message.reply_text("📭 Пока никого нет — зови друзей!")
        return

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]
    lines = ["🏆 *Таблица лидеров ЧМ 2026:*\n"]
    for i, r in enumerate(rows):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        name = r["name"] or r["username"] or "Аноним"
        lines.append(
            f"{medal} *{name}* — {r['points']} очков\n"
            f"   📊 {r['bets'] or 0} ставок  "
            f"✅ {r['wins'] or 0} верных  "
            f"🔮 {r['exact'] or 0} точных\n"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_results(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        matches = db.recent(5)
    except Exception as e:
        log.exception("cmd_results: db.recent failed: %s", e)
        await update.message.reply_text("⚠️ Ошибка загрузки результатов")
        return

    if not matches:
        await update.message.reply_text("😴 Завершённых матчей пока нет")
        return

    lines = ["📊 *Последние результаты:*\n"]
    for m in matches:
        try:
            bets = db.match_bets(m["id"])
            exact = [b for b in bets if b["bet_h"] == m["home_score"] and b["bet_a"] == m["away_score"]]
            outcome_ok = [b for b in bets if b["pts"] == 2]
            miss = db.missing_bettors(m["id"])

            lines.append(
                f"{flag(m['home'])} {m['home']} *{m['home_score']}–{m['away_score']}* "
                f"{m['away']} {flag(m['away'])} | {m['stage']}\n"
            )
            if exact:
                lines.append(f"  🔮 Точный счёт: {', '.join(b['name'] for b in exact)} (+5)\n")
            if outcome_ok:
                lines.append(f"  ✅ Исход: {', '.join(b['name'] for b in outcome_ok)} (+2)\n")
            if miss:
                lines.append(f"  😴 Не ставили: {', '.join(u['name'] for u in miss)}\n")
            lines.append("")
        except Exception as e:
            log.exception("cmd_results: match #%s error: %s", m["id"], e)
            continue

    try:
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        log.exception("cmd_results: send failed: %s", e)
        # Try sending without Markdown if formatting failed
        plain = "\n".join(lines).replace("*", "").replace("_", "").replace("\\", "")
        await update.message.reply_text(plain)


# ── ADMIN COMMANDS ─────────────────────────────────────────────────────────

async def cmd_addmatch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not db.is_admin(uid):
        await update.message.reply_text("⛔ Только для администраторов")
        return

    args = ctx.args
    if len(args) < 4:
        await update.message.reply_text(
            "Формат:\n`/addmatch Испания Германия 2026-06-21 21:00 Группа`",
            parse_mode="Markdown",
        )
        return

    home, away = args[0], args[1]
    mtime = f"{args[2]} {args[3]}"
    stage = " ".join(args[4:]) if len(args) > 4 else "Группа"

    try:
        datetime.strptime(mtime, "%Y-%m-%d %H:%M")
    except ValueError:
        await update.message.reply_text("❌ Неверная дата. Формат: `2026-06-21 21:00`", parse_mode="Markdown")
        return

    db.add_match(home, away, mtime, stage)
    await update.message.reply_text(
        f"✅ Матч добавлен!\n{flag(home)} {home} vs {away} {flag(away)}\n📅 {mtime} | {stage}"
    )


async def cmd_setresult(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not db.is_admin(uid):
        await update.message.reply_text("⛔ Только для администраторов")
        return

    if len(ctx.args) < 2:
        await update.message.reply_text(
            "Формат: `/setresult <id> <счёт>`\nПример: `/setresult 1 2-1`",
            parse_mode="Markdown",
        )
        return

    try:
        mid = int(ctx.args[0])
        hs, as_ = map(int, ctx.args[1].split("-"))
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Неверный формат. Пример: `/setresult 1 2-1`", parse_mode="Markdown")
        return

    m = db.get_match(mid)
    if not m:
        await update.message.reply_text(f"❌ Матч #{mid} не найден")
        return
    if m["done"]:
        await update.message.reply_text(f"⚠️ Результат матча #{mid} уже установлен!")
        return

    results = db.set_result(mid, hs, as_)

    text = (
        f"⚽ *ФИНАЛЬНЫЙ СВИСТОК!*\n\n"
        f"{flag(m['home'])} *{m['home']} {hs}–{as_} {m['away']}* {flag(m['away'])}\n"
        f"_{m['stage']}_\n\n"
        f"📊 *Итоги ставок:*\n"
    )

    if not results:
        text += "_(никто не поставил на этот матч)_"
    else:
        for r in results:
            if r["pts"] == 5:
                text += f"🔮 *{r['name']}* — точный счёт! +5 очков\n"
            elif r["pts"] == 2:
                text += f"✅ *{r['name']}* — исход угадал +2 очка\n"
            else:
                text += f"❌ {r['name']} — мимо (ставил {r['bet_h']}–{r['bet_a']})\n"

    await update.message.reply_text(text, parse_mode="Markdown")
    await _send_all(ctx.bot, text, exclude_id=uid)


async def cmd_allbets(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not db.is_admin(uid):
        await update.message.reply_text("⛔ Только для администраторов")
        return

    # Without argument → show match picker
    if not ctx.args:
        matches = db.upcoming(20)
        finished = db.recent(10)
        all_matches = list(matches) + [m for m in finished if m not in matches]

        if not all_matches:
            await update.message.reply_text("Матчей нет")
            return

        kb = []
        for m in all_matches:
            bets = db.match_bets(m["id"])
            dt = datetime.strptime(m["mtime"], "%Y-%m-%d %H:%M")
            status = "✅" if m["done"] else ("⏳" if bets else "⬜")
            label = f"{status} #{m['id']} {m['home']} vs {m['away']} ({len(bets)} ставок)"
            kb.append([InlineKeyboardButton(label, callback_data=f"admin_bets_{m['id']}")])

        await update.message.reply_text(
            "👑 *Обзор ставок — выбери матч:*\n_(✅ завершён | ⏳ есть ставки | ⬜ нет ставок)_",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown",
        )
        return

    # With argument → show bets for specific match
    try:
        mid = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный id")
        return

    await _show_match_bets(update.message.reply_text, mid)


async def _show_match_bets(reply_fn, mid: int):
    m = db.get_match(mid)
    if not m:
        await reply_fn(f"❌ Матч #{mid} не найден")
        return

    bets = db.match_bets(mid)
    miss = db.missing_bettors(mid)
    dt = datetime.strptime(m["mtime"], "%Y-%m-%d %H:%M")

    result_line = ""
    if m["done"]:
        result_line = f"🏁 Итог: *{m['home_score']}–{m['away_score']}*\n"

    lines = [
        f"⚽ *Матч #{mid}*\n"
        f"{flag(m['home'])} {m['home']} vs {m['away']} {flag(m['away'])}\n"
        f"📅 {dt.strftime('%d.%m %H:%M')} | {m['stage']}\n"
        f"{result_line}"
    ]

    if bets:
        lines.append(f"✅ *Поставили ({len(bets)}):*")
        for b in bets:
            pts = f" → +{b['pts']}pts" if m["done"] else ""
            lines.append(f"  • *{b['name']}*: {b['bet_h']}–{b['bet_a']}{pts}")
    else:
        lines.append("😴 *Никто не поставил*")

    if miss and not m["done"]:
        lines.append(f"\n⚠️ *Не поставили ({len(miss)}):*")
        for u in miss:
            lines.append(f"  • {u['name']}")

    await reply_fn("\n".join(lines), parse_mode="Markdown")


async def cmd_resetscores(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not db.is_admin(uid):
        await update.message.reply_text("⛔ Только для администраторов")
        return

    args = ctx.args
    if not args or args[0] != "confirm":
        await update.message.reply_text(
            "⚠️ Это сбросит *все очки* всем участникам!\n\n"
            "Для подтверждения: `/resetscores confirm`",
            parse_mode="Markdown",
        )
        return

    db.reset_scores()
    await update.message.reply_text("✅ Все очки сброшены до нуля!")
    await _send_all(ctx.bot, "🔄 *Администратор сбросил таблицу лидеров.* Начинаем заново!", exclude_id=uid)


async def cmd_rebroadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not db.is_admin(uid):
        await update.message.reply_text("⛔ Только для администраторов")
        return

    if not ctx.args:
        # Show list of recently finished matches
        matches = db.recent(10)
        if not matches:
            await update.message.reply_text("Нет завершённых матчей")
            return
        lines = ["Выбери матч для повторной рассылки:\n"]
        for m in matches:
            lines.append(f"  /rebroadcast {m['id']} — {m['home']} {m['home_score']}–{m['away_score']} {m['away']}")
        await update.message.reply_text("\n".join(lines))
        return

    try:
        mid = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный id")
        return

    m = db.get_match(mid)
    if not m:
        await update.message.reply_text(f"❌ Матч #{mid} не найден")
        return
    if not m["done"]:
        await update.message.reply_text("❌ Матч ещё не завершён")
        return

    results = db.match_bets(mid)
    settled = [r for r in results if r["pts"] is not None]

    h, a = m["home"], m["away"]
    hs, as_ = m["home_score"], m["away_score"]

    text = (
        f"⚽ *ФИНАЛЬНЫЙ СВИСТОК!*\n\n"
        f"{flag(h)} *{h} {hs}–{as_} {a}* {flag(a)}\n"
        f"_{m['stage']}_\n\n"
    )
    if settled:
        text += "📊 *Итоги ставок:*\n"
        for b in settled:
            bet = f"{b['bet_h']}–{b['bet_a']}"
            if b["pts"] == 5:
                text += f"🔮 ОРАКУЛ! — *{b['name']}* ставил {bet} +5 очков\n"
            elif b["pts"] == 2:
                text += f"✅ Исход угадал — *{b['name']}* ставил {bet} +2 очка\n"
            else:
                text += f"❌ Мимо — {b['name']} ставил {bet}\n"
    else:
        text += "_(никто не поставил на этот матч)_"

    sent = 0
    for u in db.all_users():
        try:
            await ctx.bot.send_message(u["id"], text, parse_mode="Markdown")
            sent += 1
        except Exception as e:
            log.warning("rebroadcast: failed to send to %s: %s", u["id"], e)
    await update.message.reply_text(f"✅ Разослано {sent} пользователям!")


async def cmd_forcesync(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not db.is_admin(uid):
        await update.message.reply_text("⛔ Только для администраторов")
        return
    await update.message.reply_text("🔄 Запускаю синхронизацию результатов...")
    try:
        settled, added = await syncer.check_results(ctx.bot)
        if settled or added:
            await update.message.reply_text(
                f"✅ Зачтено результатов: *{settled}*\n"
                f"➕ Добавлено новых матчей: *{added}*",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text("😴 Новых завершённых матчей не найдено")
    except Exception as e:
        log.exception("forcesync error: %s", e)
        await update.message.reply_text(f"❌ Ошибка синхронизации: {e}")


async def cmd_dbstatus(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not db.is_admin(uid):
        await update.message.reply_text("⛔ Только для администраторов")
        return
    finished = db.recent(20)
    upcoming = db.upcoming(10)
    lines = [
        f"📊 *Статус БД:*\n",
        f"✅ Завершённых матчей: *{len(finished)}*",
        f"⏳ Предстоящих матчей: *{len(upcoming)}*\n",
    ]
    if finished:
        lines.append("*Последние результаты:*")
        for m in finished[:5]:
            lines.append(f"  #{m['id']} {m['home']} {m['home_score']}–{m['away_score']} {m['away']}")
    if upcoming:
        lines.append("\n*Ближайшие матчи:*")
        for m in upcoming[:5]:
            lines.append(f"  #{m['id']} {m['home']} vs {m['away']} ({m['mtime']})")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not db.is_admin(uid):
        await update.message.reply_text("⛔ Только для администраторов")
        return

    if not ctx.args:
        await update.message.reply_text("Формат: `/broadcast <текст>`", parse_mode="Markdown")
        return

    msg = "📢 " + " ".join(ctx.args)
    users = db.all_users()
    sent = 0
    for u in users:
        try:
            await ctx.bot.send_message(u["id"], msg)
            sent += 1
        except Exception as e:
            log.warning("broadcast failed %s: %s", u["id"], e)

    await update.message.reply_text(f"✅ Отправлено {sent}/{len(users)}")


async def cmd_promote(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not db.is_admin(uid):
        await update.message.reply_text("⛔ Только для администраторов")
        return

    if not ctx.args:
        await update.message.reply_text("Формат: `/promote <user_id>`", parse_mode="Markdown")
        return

    try:
        target = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный user_id")
        return

    db.promote(target)
    await update.message.reply_text(f"✅ Пользователь `{target}` теперь администратор", parse_mode="Markdown")


# ── REPLY KEYBOARD HANDLER ────────────────────────────────────────────────

_BUTTON_MAP = {
    "⚽ Матчи":      cmd_matches,
    "🎯 Ставка":     cmd_bet,
    "📋 Мои ставки": cmd_mybets,
    "👥 Ставки":     cmd_show_bets,
    "🏆 Лидеры":     cmd_leaderboard,
    "📊 Результаты": cmd_results,
    "❓ Помощь":     cmd_help,
}


async def handle_kb_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    handler = _BUTTON_MAP.get(update.message.text)
    if handler:
        await handler(update, ctx)


# ── CALLBACK HANDLER ───────────────────────────────────────────────────────

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = q.from_user.id

    if data == "bx":
        await q.edit_message_text("❌ Отменено")
        return

    # Admin: show bets for selected match
    if data.startswith("admin_bets_"):
        if not db.is_admin(uid):
            await q.answer("⛔ Только для администраторов", show_alert=True)
            return
        mid = int(data.split("_")[2])
        try:
            await _show_match_bets(q.edit_message_text, mid)
        except Exception as e:
            log.exception("admin_bets callback error for match #%s: %s", mid, e)
            await q.answer(f"Ошибка: {e}", show_alert=True)
        return

    # Match selected → ask home score
    if data.startswith("bm_"):
        mid = int(data[3:])
        m = db.get_match(mid)
        if not m:
            await q.edit_message_text("❌ Матч не найден")
            return
        mt = datetime.strptime(m["mtime"], "%Y-%m-%d %H:%M")
        now_msk = datetime.utcnow() + timedelta(hours=3)
        if now_msk >= mt:
            await q.edit_message_text(f"⏱️ Ставки закрыты!\n{m['home']} vs {m['away']}")
            return

        bets = db.match_bets(mid)
        my = next((b for b in bets if b["user_id"] == uid), None)
        note = (
            f"\n_Текущая ставка: {my['bet_h']}–{my['bet_a']} (можно изменить)_"
            if my else ""
        )
        await q.edit_message_text(
            f"⚽ {flag(m['home'])} *{m['home']}* vs *{m['away']}* {flag(m['away'])}\n"
            f"📅 {mt.strftime('%d.%m %H:%M')} | {m['stage']}{note}\n\n"
            f"Выбери счёт *{m['home']}* (хозяев):",
            reply_markup=kb_home(mid),
            parse_mode="Markdown",
        )
        return

    # Home score selected → ask away score
    if data.startswith("bh_"):
        _, mid_s, h_s = data.split("_")
        mid, h = int(mid_s), int(h_s)
        m = db.get_match(mid)
        await q.edit_message_text(
            f"⚽ {flag(m['home'])} *{m['home']}* {h} — ? *{m['away']}* {flag(m['away'])}\n\n"
            f"Выбери счёт *{m['away']}* (гостей):",
            reply_markup=kb_away(mid, h),
            parse_mode="Markdown",
        )
        return

    # Away score selected → confirm
    if data.startswith("ba_"):
        parts = data.split("_")
        mid, h, a = int(parts[1]), int(parts[2]), int(parts[3])
        m = db.get_match(mid)
        await q.edit_message_text(
            f"⚽ *Подтвердить ставку?*\n\n"
            f"{flag(m['home'])} {m['home']} *{h}–{a}* {m['away']} {flag(m['away'])}\n"
            f"📊 Прогноз: {outcome_text(h, a, m['home'], m['away'])}\n\n"
            f"💰 Точный счёт → 5 очков\n"
            f"💰 Верный исход → 2 очка",
            reply_markup=kb_confirm(mid, h, a),
            parse_mode="Markdown",
        )
        return

    # Bet confirmed
    if data.startswith("bc_"):
        parts = data.split("_")
        mid, h, a = int(parts[1]), int(parts[2]), int(parts[3])
        ok, msg = db.place_bet(uid, mid, h, a)
        m = db.get_match(mid)
        if ok:
            await q.edit_message_text(
                f"✅ *Ставка принята!*\n\n"
                f"{flag(m['home'])} {m['home']} *{h}–{a}* {m['away']} {flag(m['away'])}\n\n"
                f"{random.choice(MOTIVATE)}",
                parse_mode="Markdown",
            )
        else:
            await q.edit_message_text(f"❌ {msg}")
        return


# ── REMINDERS (JobQueue) ───────────────────────────────────────────────────

async def _remind(ctx: ContextTypes.DEFAULT_TYPE):
    mid = ctx.job.data["mid"]
    m = db.get_match(mid)
    if not m or m["done"]:
        return
    missing = db.missing_bettors(mid)
    for u in missing:
        try:
            await ctx.bot.send_message(
                u["id"],
                f"⏰ *Последний шанс!*\n\n"
                f"⚽ Через час: {flag(m['home'])} {m['home']} vs {m['away']} {flag(m['away'])}\n"
                f"_{random.choice(TRASH)}_\n\n"
                f"Успей поставить → /bet",
                parse_mode="Markdown",
            )
        except Exception as e:
            log.warning("reminder failed %s: %s", u["id"], e)


async def _reveal_bets(ctx: ContextTypes.DEFAULT_TYPE):
    """Broadcast everyone's bets 5 minutes before kickoff."""
    mid = ctx.job.data["mid"]
    m = db.get_match(mid)
    if not m or m["done"]:
        return

    bets = db.match_bets(mid)
    miss = db.missing_bettors(mid)
    h, a = m["home"], m["away"]

    lines = [
        f"👀 *Ставки раскрыты!*\n",
        f"{flag(h)} *{h}* vs *{a}* {flag(a)}",
        f"⏰ Матч через 5 минут!\n",
    ]

    if bets:
        lines.append("🎯 *Кто на что поставил:*")
        for b in bets:
            oc = outcome_text(b["bet_h"], b["bet_a"], h, a)
            lines.append(f"  • *{b['name']}*: {b['bet_h']}–{b['bet_a']}  _({oc})_")
    else:
        lines.append("😶 Никто не поставил на этот матч!")

    if miss:
        names = ", ".join(u["name"] for u in miss)
        lines.append("\n" + random.choice(TRASH_REVEAL).format(names=names))

    text = "\n".join(lines)
    for u in db.all_users():
        try:
            await ctx.bot.send_message(u["id"], text, parse_mode="Markdown")
        except Exception as e:
            log.warning("reveal_bets failed %s: %s", u["id"], e)


async def _morning_digest(ctx: ContextTypes.DEFAULT_TYPE):
    """9:00 MSK daily: show today's matches and shame those who haven't bet."""
    now = datetime.utcnow() + timedelta(hours=3)  # MSK
    today_str = now.strftime("%Y-%m-%d")

    matches = db.upcoming(20)
    today = [m for m in matches if m["mtime"].startswith(today_str)]
    if not today:
        return

    all_users = db.all_users()
    no_bets = {u["id"]: u["name"] for u in all_users}

    lines = [f"☀️ *Матчи на сегодня — {now.strftime('%d.%m')}:*\n"]
    for m in today:
        dt = datetime.strptime(m["mtime"], "%Y-%m-%d %H:%M")
        bets = db.match_bets(m["id"])
        for b in bets:
            no_bets.pop(b["user_id"], None)
        lines.append(
            f"⚽ {flag(m['home'])} *{m['home']}* vs *{m['away']}* {flag(m['away'])}\n"
            f"   🕐 {dt.strftime('%H:%M')} МСК  |  {len(bets)} ставок\n"
        )

    if no_bets:
        names = ", ".join(no_bets.values())
        lines.append(random.choice(TRASH_MORNING).format(names=names))
        lines.append("👉 /bet")
    else:
        lines.append("✅ Все поставили — красавчики!")

    text = "\n".join(lines)
    for u in all_users:
        try:
            await ctx.bot.send_message(u["id"], text, parse_mode="Markdown")
        except Exception as e:
            log.warning("morning_digest failed %s: %s", u["id"], e)


async def _sync_job(ctx: ContextTypes.DEFAULT_TYPE):
    settled, added = await syncer.check_results(ctx.bot)
    if settled:
        log.info("auto-sync: settled %d new match(es)", settled)
    if added:
        log.info("auto-sync: added %d new match(es) — rescheduling reminders", added)
        _schedule_reminders(ctx.application)


def _schedule_reminders(app: Application):
    matches = db.upcoming(50)
    now = datetime.utcnow() + timedelta(hours=3)  # current MSK time
    for m in matches:
        mt = datetime.strptime(m["mtime"], "%Y-%m-%d %H:%M")

        remind_delay = (mt - timedelta(hours=1) - now).total_seconds()
        if remind_delay > 0 and not app.job_queue.get_jobs_by_name(f"remind_{m['id']}"):
            app.job_queue.run_once(
                _remind,
                when=remind_delay,
                data={"mid": m["id"]},
                name=f"remind_{m['id']}",
            )
            log.info("Scheduled reminder for match #%s in %.0fs", m["id"], remind_delay)

        reveal_delay = (mt - timedelta(minutes=5) - now).total_seconds()
        if reveal_delay > 0 and not app.job_queue.get_jobs_by_name(f"reveal_{m['id']}"):
            app.job_queue.run_once(
                _reveal_bets,
                when=reveal_delay,
                data={"mid": m["id"]},
                name=f"reveal_{m['id']}",
            )
            log.info("Scheduled reveal for match #%s in %.0fs", m["id"], reveal_delay)


# ── MAIN ───────────────────────────────────────────────────────────────────

def main():
    db.init()
    db.seed()

    app = Application.builder().token(BOT_TOKEN).build()

    # User
    app.add_handler(CommandHandler("start",       cmd_start))
    app.add_handler(CommandHandler("help",        cmd_help))
    app.add_handler(CommandHandler("myid",        cmd_myid))
    app.add_handler(CommandHandler("matches",     cmd_matches))
    app.add_handler(CommandHandler("schedule",    cmd_matches))
    app.add_handler(CommandHandler("bet",         cmd_bet))
    app.add_handler(CommandHandler("mybets",      cmd_mybets))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("lb",          cmd_leaderboard))
    app.add_handler(CommandHandler("results",     cmd_results))
    app.add_handler(CommandHandler("bets",        cmd_show_bets))

    # Admin
    app.add_handler(CommandHandler("addmatch",   cmd_addmatch))
    app.add_handler(CommandHandler("setresult",  cmd_setresult))
    app.add_handler(CommandHandler("allbets",    cmd_allbets))
    app.add_handler(CommandHandler("broadcast",  cmd_broadcast))
    app.add_handler(CommandHandler("promote",      cmd_promote))
    app.add_handler(CommandHandler("resetscores",  cmd_resetscores))
    app.add_handler(CommandHandler("forcesync",    cmd_forcesync))
    app.add_handler(CommandHandler("rebroadcast",  cmd_rebroadcast))
    app.add_handler(CommandHandler("dbstatus",     cmd_dbstatus))

    # Reply keyboard buttons
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_kb_button))

    # Callbacks
    app.add_handler(CallbackQueryHandler(on_callback))

    _schedule_reminders(app)

    # Auto-sync results every 10 minutes (first run after 60 sec)
    app.job_queue.run_repeating(_sync_job, interval=600, first=60,
                                name="auto_sync")

    # Morning digest at 09:00 MSK = 06:00 UTC
    app.job_queue.run_daily(
        _morning_digest,
        time=dt_time(6, 0, tzinfo=timezone.utc),
        name="morning_digest",
    )

    log.info("⚽ WC 2026 Bot started! Auto-sync every 10 min.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
