import logging
import os

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from assign import extract_assignee, is_completion
from llm import extract_ticket
from sheets import append_ticket, assign_ticket, complete_ticket

load_dotenv()
logging.basicConfig(level=logging.INFO)

IT_GROUP_CHAT_ID = os.environ.get("IT_GROUP_CHAT_ID")
_sheet_id = os.environ.get("GOOGLE_SHEET_ID")
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{_sheet_id}/edit" if _sheet_id else None

# ponytail: in-memory pending tickets / group-message map, single-process only.
# Move to Redis/DB if bot scales beyond one instance.
pending: dict[int, dict] = {}
group_message_ticket: dict[int, str] = {}
ticket_reporter: dict[str, int] = {}

WELCOME = (
    "Halo! Ketik kendala SIMRS atau IT lainnya di sini, contoh:\n"
    '"SIMRS error pas mau input pasien baru, muncul kode 500"\n\n'
    "Nanti aku ringkas jadi tiket sebelum dikirim ke tim IT Support."
)

GROUP_TEMPLATE = (
    "🎫 Tiket {ticket_id}\n"
    "Kategori: {category}\n"
    "Prioritas: {priority}\n"
    "Deskripsi: {description}\n"
    "Pelapor: {requester_name}\n\n"
    'Reply pesan ini "ambil" buat klaim, "@nama kerjain" buat assign ke orang lain, '
    'atau "selesai" kalau udah kelar.'
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME)


async def handle_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    requester = update.effective_user.full_name
    ticket = extract_ticket(update.message.text, requester_name=requester)
    pending[chat_id] = ticket

    summary = (
        f"Kategori: {ticket['category']}\n"
        f"Prioritas: {ticket['priority']}\n"
        f"Deskripsi: {ticket['description']}\n\n"
        "Kirim tiket ini ke IT Support?"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Kirim", callback_data="confirm"),
        InlineKeyboardButton("Batal", callback_data="cancel"),
    ]])
    await update.message.reply_text(summary, reply_markup=keyboard)


async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    ticket = pending.pop(chat_id, None)

    if query.data == "cancel" or ticket is None:
        await query.edit_message_text("Tiket dibatalkan. Kirim ulang laporanmu kalau perlu.")
        return

    ticket_id = append_ticket(ticket)
    ticket_reporter[ticket_id] = chat_id
    confirmation = f"Tiket {ticket_id} terkirim ke IT Support. Terima kasih!"
    if SHEET_URL:
        confirmation += f"\n\nCek progress semua tiket di sini: {SHEET_URL}"
    await query.edit_message_text(confirmation)

    if IT_GROUP_CHAT_ID:
        sent = await context.bot.send_message(
            chat_id=int(IT_GROUP_CHAT_ID),
            text=GROUP_TEMPLATE.format(ticket_id=ticket_id, **ticket),
        )
        group_message_ticket[sent.message_id] = ticket_id


async def handle_group_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    replied = update.message.reply_to_message
    ticket_id = group_message_ticket.get(replied.message_id) if replied else None
    if ticket_id is None:
        return  # reply to something other than a ticket announcement, ignore

    text = update.message.text
    if is_completion(text):
        if complete_ticket(ticket_id):
            await update.message.reply_text(f"Tiket {ticket_id} ditandai selesai.")
            reporter_chat_id = ticket_reporter.pop(ticket_id, None)
            if reporter_chat_id is not None:
                await context.bot.send_message(
                    chat_id=reporter_chat_id,
                    text=f"Tiket {ticket_id} kamu udah selesai dikerjain tim IT. Terima kasih!",
                )
        return

    assignee = extract_assignee(text, update.effective_user.full_name)
    if assign_ticket(ticket_id, assignee):
        await update.message.reply_text(f"Tiket {ticket_id} di-assign ke {assignee}.")


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_report)
    )
    if IT_GROUP_CHAT_ID:
        app.add_handler(
            MessageHandler(
                filters.Chat(chat_id=int(IT_GROUP_CHAT_ID)) & filters.REPLY, handle_group_reply
            )
        )
    app.add_handler(CallbackQueryHandler(handle_confirm))
    app.run_polling()


if __name__ == "__main__":
    main()
