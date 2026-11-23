
import os
import re
import sqlite3
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

TOKEN = os.environ["BOT_TOKEN"]

db = sqlite3.connect("recap.db", check_same_thread=False)
db.execute("PRAGMA journal_mode=WAL")

db.executescript("""
CREATE TABLE IF NOT EXISTS players (
    chat_id INTEGER,
    user_id INTEGER,
    name TEXT,
    side TEXT,
    amount INTEGER,
    PRIMARY KEY (chat_id, user_id, side)
);

CREATE TABLE IF NOT EXISTS profiles (
    chat_id INTEGER,
    name TEXT,
    registered INTEGER DEFAULT 0,
    PRIMARY KEY (chat_id, name)
);

CREATE TABLE IF NOT EXISTS settings (
    chat_id INTEGER PRIMARY KEY,
    active INTEGER DEFAULT 0
);
""")
db.commit()


def save_profile(chat_id, name, registered=0):
    name = name.strip()
    if not name:
        return

    db.execute("""
        INSERT INTO profiles (chat_id, name, registered)
        VALUES (?, ?, ?)
        ON CONFLICT(chat_id, name)
        DO UPDATE SET registered =
            MAX(registered, excluded.registered)
    """, (chat_id, name, registered))
    db.commit()


def detect_names(chat_id, text):
    for line in text.splitlines():
        line = line.strip()

        match = re.fullmatch(
            r"(.+?)\s+[KB]\s*\d+\s*\.?",
            line,
            re.IGNORECASE
        )

        if match:
            save_profile(chat_id, match.group(1))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "RECAP BOT AKTIF!\nKetik .cmd untuk melihat perintah."
    )


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    chat_id = update.effective_chat.id
    text = (msg.text or "").strip()

    if not user:
        return

    if text == ".ping":
        await msg.reply_text("PONG! Bot aktif.")
        return

    if text == ".on":
        db.execute("""
            INSERT INTO settings VALUES (?, 1)
            ON CONFLICT(chat_id) DO UPDATE SET active=1
        """, (chat_id,))
        db.commit()
        await msg.reply_text("✅ Pencatatan aktif.")
        return

    if text == ".off":
        db.execute("""
            INSERT INTO settings VALUES (?, 0)
            ON CONFLICT(chat_id) DO UPDATE SET active=0
        """, (chat_id,))
        db.commit()
        await msg.reply_text("Pencatatan dimatikan.")
        return

    if text.startswith(".sv "):
        name = text[4:].strip()
        if not name:
            await msg.reply_text("Format: .sv Nama")
            return

        save_profile(chat_id, name, 1)
        await msg.reply_text(
            f"✅ Profil {name} berhasil didaftarkan."
        )
        return

    if text == ".list":
        rows = db.execute("""
            SELECT name, registered
            FROM profiles
            WHERE chat_id=?
            ORDER BY name
        """, (chat_id,)).fetchall()

        result = ["📋 DAFTAR PROFIL\n"]

        if rows:
            for name, registered in rows:
                result.append(
                    f"{name} {'P' if registered else '.'}"
                )
        else:
            result.append("Belum ada nama.")

        for side in ("K", "B"):
            result.append(f"\n{side}:")
            amounts = db.execute("""
                SELECT name, amount
                FROM players
                WHERE chat_id=? AND side=?
                ORDER BY name
            """, (chat_id, side)).fetchall()

            if amounts:
                for name, amount in amounts:
                    result.append(f"{name} {amount}")
            else:
                result.append("- Kosong")

        await msg.reply_text("\n".join(result))
        return

    if text == ".rk":
        totals = {}

        for side in ("K", "B"):
            row = db.execute("""
                SELECT COALESCE(SUM(amount), 0)
                FROM players
                WHERE chat_id=? AND side=?
            """, (chat_id, side)).fetchone()

            totals[side] = row[0]

        await msg.reply_text(
            "📊 REKAP TOTAL\n\n"
            f"⭐ K: {totals['K']}\n"
            f"⭐ B: {totals['B']}\n\n"
            f"💰 Total: {totals['K'] + totals['B']}"
        )
        return

    if text == ".rs":
        db.execute(
            "DELETE FROM players WHERE chat_id=?", (chat_id,)
        )
        db.execute(
            "DELETE FROM profiles WHERE chat_id=?", (chat_id,)
        )
        db.commit()
        await msg.reply_text("✅ List berhasil direset.")
        return

    if text == ".cmd":
        await msg.reply_text(
            "📖 DAFTAR PERINTAH\n\n"
            ".ping - Cek bot\n"
            ".on - Aktifkan pencatatan\n"
            ".off - Matikan pencatatan\n"
            ".sv Nama - Daftarkan profil\n"
            ".list - Lihat daftar\n"
            ".rk - Rekap total\n"
            ".rs - Reset list\n\n"
            "Format pencatatan:\nK 50\nB 20"
        )
        return

    detect_names(chat_id, text)

    active = db.execute(
        "SELECT active FROM settings WHERE chat_id=?",
        (chat_id,)
    ).fetchone()

    if not active or not active[0]:
        return

    parts = text.split()
    if len(parts) != 2:
        return

    side = parts[0].upper()
    if side not in ("K", "B"):
        return

    try:
        amount = int(parts[1])
        if amount <= 0:
            return
    except ValueError:
        return

    name = user.full_name or str(user.id)

    db.execute("""
        INSERT INTO players
        (chat_id, user_id, name, side, amount)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(chat_id, user_id, side)
        DO UPDATE SET
            amount=amount+excluded.amount,
            name=excluded.name
    """, (chat_id, user.id, name, side, amount))

    save_profile(chat_id, name)
    db.commit()

    await msg.reply_text(f"✅ Pik: {side} {amount} {name}")


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle)
    )

    print("RECAP BOT BERJALAN!")
    app.run_polling()


if __name__ == "__main__":
    main()
