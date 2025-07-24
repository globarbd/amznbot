import asyncio
import nest_asyncio
import re
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

nest_asyncio.apply()

BOT_TOKEN = '7058999572:AAGBoKSDGWIotM6ymcmK9idZLwFm5bHAcEg'
API_BASE = 'https://web.amznvip.com/api'

HEADERS_TEMPLATE = {
    'content-type': 'application/x-www-form-urlencoded',
    'origin': 'https://web.amznvip.com',
    'referer': 'https://web.amznvip.com/',
    'user-agent': 'Mozilla/5.0'
}

user_tokens = {}  # user_id -> latest token
user_last_phone = {}  # user_id -> last phone used (optional)

UUID_REGEX = r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}"
PHONE_REGEX = r"(\S*%3D%3D)\s+(\d{10,15})"

# Command: /start or /login
async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔐 দয়া করে টোকেন পাঠান...\nযেমন:\n`2c314829-12e9-4b86-99f7-224e2043b178`", parse_mode='Markdown')

# Auto-detect token or phone number
async def detect_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # 1. Check if it's a token
    token_match = re.match(UUID_REGEX, text)
    if token_match:
        token = token_match.group()
        user_tokens[user_id] = token
        await update.message.reply_text(f"✅ টোকেন সংরক্ষিত হয়েছে।\nএখন নাম্বার পাঠান।\nযেমন:\n`CPAUI1lDEt2QB%2BBSQAqH4w%3D%3D 12898165220`", parse_mode='Markdown')
        return

    # 2. Check if it's a phone pair
    phone_match = re.match(PHONE_REGEX, text)
    if phone_match:
        if user_id not in user_tokens:
            await update.message.reply_text("⚠️ আগে টোকেন দিন (Login করুন)।")
            return

        encoded, decoded = phone_match.groups()
        token = user_tokens[user_id]
        headers = HEADERS_TEMPLATE.copy()
        headers["token"] = token

        # Step 1: Send code
        requests.post(f"{API_BASE}/task/send_code", headers=headers, data=f"phone={encoded}")

        # Step 2: Try to get code
        code = None
        for _ in range(6):
            await asyncio.sleep(5)
            get_res = requests.post(f"{API_BASE}/task/get_code", headers=headers, data=f"is_agree=1&phone={decoded}")
            res_data = get_res.json().get("data", {})
            code = res_data.get("code")
            if code:
                break

        if code:
            # Save last phone in case needed later
            user_last_phone[user_id] = decoded
            keyboard = [[InlineKeyboardButton("✅ Confirm", callback_data="confirm_bind")]]
            await update.message.reply_text(f"📨 কোড: `{code}`", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("❌ কোড পাওয়া যায়নি। পরে আবার চেষ্টা করুন।")
        return

    # Not token or phone
    await update.message.reply_text("⚠️ টোকেন বা নাম্বার সঠিক ফরম্যাটে দিন।")

# Confirm bind button handler
async def confirm_bind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    token = user_tokens.get(user_id)

    if not token:
        await query.edit_message_text("⚠️ প্রথমে টোকেন দিন (/login)।")
        return

    headers = HEADERS_TEMPLATE.copy()
    headers["token"] = token
    res = requests.post(f"{API_BASE}/task/phone_list", headers=headers)
    phones = res.json().get("data", [])

    if phones:
        p = phones[0]
        msg = f"📱 নাম্বার: `{p['phone']}`\n🔗 Bind Status: ✅\n🕓 সময়: {p['last_time_text']}"
        await query.edit_message_text(msg, parse_mode='Markdown')
    else:
        await query.edit_message_text("❌ Bind হয়নি।")

# Main function
async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("start", login))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, detect_input))
    app.add_handler(CallbackQueryHandler(confirm_bind, pattern="confirm_bind"))

    await app.bot.set_my_commands([
        BotCommand("login", "লগইন করুন টোকেন দিয়ে"),
    ])

    print("🤖 Bot চলছে...")
    await app.run_polling()

# Run bot
asyncio.run(main())