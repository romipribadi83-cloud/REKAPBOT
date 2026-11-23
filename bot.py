
import os
import sqlite3
from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters
)

TOKEN = os.environ["BOT_TOKEN"]

db = sqlite3.connect("recap.db", check_same_thread=False)

db.execute("""
CREATE TABLE IF NOT EXISTS players (
    chat_id INTEGER,
    user_id INTEGER,
    name TEXT,
    side TEXT,
    amount INTEGER,
    PRIMARY KEY (chat_id, user_id, side)
)
""")

db.execute("""
CREATE TABLE IF NOT EXISTS settings (
    chat_id INTEGER PRIMARY KEY,
    active INTEGER DEFAULT 0
)
""")
db.commit()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
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

    if text in (".on", ".akses"):
        db.execute(
            "INSERT INTO settings VALUES (?,1) "
            "ON CONFLICT(chat_id) DO UPDATE SET active=1",
            (chat_id,)
        )
        db.commit()
        await msg.reply_text("✅ Pencatatan K/B aktif.")
        return

    if text in (".off", ".delakses"):
        db.execute(
            "INSERT INTO settings VALUES (?,0) "
            "ON CONFLICT(chat_id) DO UPDATE SET active=0",
            (chat_id,)
        )
        db.commit()
        await msg.reply_text("Pencatatan dimatikan.")
        return

    if text == ".list":
        result = ["🎯 RECAP LIST\n"]

        for side in ("K", "B"):
            result.append(side + ":")

            rows = db.execute(
                "SELECT name, amount FROM players "
                "WHERE chat_id=? AND side=? ORDER BY name",
                (chat_id, side)
            ).fetchall()

            if not rows:
                result.append("- Kosong")
            else:
                for name, amount in rows:
                    result.append(f"{name} {amount}")

            result.append("")

        await msg.reply_text("\n".join(result))
        return

    if text == ".rk":
        totals = {}

        for side in ("K", "B"):
            row = db.execute(
                "SELECT COALESCE(SUM(amount),0) "
                "FROM players WHERE chat_id=? AND side=?",
                (chat_id, side)
            ).fetchone()
            totals[side] = row[0]

        k = totals["K"]
        b = totals["B"]

        await msg.reply_text(
            f"📊 REKAP TOTAL\n\n"
            f"K: {k}\n"
            f"B: {b}\n"
            f"Selisih: {abs(k-b)}"
        )
        return

    if text == ".rs":
        db.execute(
            "DELETE FROM players WHERE chat_id=?",
            (chat_id,)
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
            ".list - Lihat daftar K/B\n"
            ".rk - Rekap total\n"
            ".rs - Reset list\n\n"
            "Contoh pik:\n"
            "K 50\n"
            "B 20"
        )
        return

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

    name = user.full_name or user.username or str(user.id)

    db.execute("""
        INSERT INTO players
        (chat_id, user_id, name, side, amount)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(chat_id, user_id, side)
        DO UPDATE SET
        amount=amount+excluded.amount,
        name=excluded.name
    """, (chat_id, user.id, name, side, amount))

    db.commit()

    await msg.reply_text(
        f"✅ Pik: {side} {amount} @{user.username}"
        if user.username else
        f"✅ Pik: {side} {amount} {name}"
    )


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
