import os
import logging
import datetime
import gspread
from google.oauth2.service_account import Credentials
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from threading import Thread

# ========== إعدادات البوت ==========
BOT_TOKEN = "YOUR_TOKEN"
BOT_NAME = "فَصْل | Fasl"
BOT_LOGO = "⚖️"
MANAGER_CHAT_ID = 123456789  # 👈 ضع هنا رقم حساب المدير (بدون @)

# قاعدة بيانات داخلية مؤقتة
users_db = {}
user_warnings = {}

# ========== إعداد السجلات ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== إعداد Flask ==========
app = Flask(__name__)

@app.route('/')
def home():
    return f"{BOT_NAME} Bot is running ✅"

# ========== Google Sheets ==========
GOOGLE_SHEET_NAME = "Fasl_Chat_Logs"

def setup_google_sheets():
    """تجهيز الاتصال مع Google Sheets"""
    creds = Credentials.from_service_account_file(
        "credentials.json",
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    client = gspread.authorize(creds)
    sheet = client.open(GOOGLE_SHEET_NAME).sheet1
    # إعداد الأعمدة إذا كانت جديدة
    if not sheet.row_values(1):
        sheet.append_row(["User ID", "Name", "Message", "Bot Reply", "Timestamp"])
    return sheet

sheet = setup_google_sheets()

def log_to_sheet(user_id, name, message, bot_reply):
    """تسجيل الرسائل في Google Sheets"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        sheet.append_row([user_id, name, message, bot_reply, timestamp])
        logger.info(f"🧾 Logged message for user {user_id}")
    except Exception as e:
        logger.error(f"❌ Error writing to Google Sheet: {e}")

# ========== أدوات المساعدة ==========
async def send_telegram_message(context, chat_id, text):
    try:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"❌ خطأ أثناء إرسال الرسالة: {e}")

# ========== الأوامر ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    # إذا المستخدم جديد
    if user.id not in users_db:
        users_db[user.id] = {"approved": False, "banned": False, "name": user.full_name}

        keyboard = [
            [
                InlineKeyboardButton("✅ قبول", callback_data=f"approve_user:{user.id}"),
                InlineKeyboardButton("❌ رفض", callback_data=f"reject_user:{user.id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # إرسال إخطار للمدير فقط
        await context.bot.send_message(
            chat_id=MANAGER_CHAT_ID,
            text=f"👤 مستخدم جديد انضم:\n\nالاسم: *{user.full_name}*\nID: `{user.id}`\n\nهل ترغب بقبوله؟",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

        await update.message.reply_text("⏳ تم إرسال طلبك للإدارة للموافقة عليه.")
    else:
        if users_db[user.id]["approved"]:
            await update.message.reply_text("👋 مرحبًا مجددًا، يمكنك استخدام النظام بحرية.")
        else:
            await update.message.reply_text("⏳ طلبك قيد المراجعة.")

# ========== الأزرار ==========
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("approve_user:"):
        user_id = int(data.split(":")[1])
        users_db[user_id] = {"approved": True, "banned": False}

        await query.edit_message_text(f"✅ تم قبول المستخدم {user_id} بنجاح.")
        await context.bot.send_message(chat_id=user_id, text="🎉 تم قبولك بنجاح! يمكنك الآن استخدام البوت.")
        logger.info(f"✅ Approved user {user_id}")

    elif data.startswith("reject_user:"):
        user_id = int(data.split(":")[1])
        users_db[user_id] = {"approved": False, "banned": True}

        await query.edit_message_text(f"🚫 تم رفض المستخدم {user_id}.")
        await context.bot.send_message(chat_id=user_id, text="❌ تم رفض طلبك للانضمام إلى النظام.")
        logger.info(f"🚫 Rejected user {user_id}")

# ========== معالجة الرسائل ==========
async def handle_user_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_name = update.effective_user.full_name
    text = update.message.text.strip()

    # التحقق من الموافقة
    if user_id not in users_db or not users_db[user_id].get("approved"):
        await send_telegram_message(context, chat_id, "⏳ لا يمكنك استخدام البوت حتى يتم الموافقة على طلبك.")
        return

    # التحقق من الحظر
    if users_db[user_id].get("banned"):
        await send_telegram_message(context, chat_id, "🚫 تم حظرك من استخدام البوت.")
        return

    # فحص الألفاظ المسيئة
    forbidden_words = ["سب", "شتم", "قذف", "شتيمة"]
    for word in forbidden_words:
        if word in text.lower():
            user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
            if user_warnings[user_id] >= 3:
                users_db[user_id]["banned"] = True
                await send_telegram_message(context, chat_id, "❌ تم حظرك بسبب تكرار المخالفات.")
                await send_telegram_message(context, MANAGER_CHAT_ID, f"🚨 تم حظر المستخدم {user_id}")
                return
            else:
                await send_telegram_message(context, chat_id, f"⚠️ تحذير ({user_warnings[user_id]}/3): يمنع استخدام الألفاظ غير اللائقة.")
                return

    # الرد الذكي الافتراضي
    reply_text = f"""
{BOT_LOGO}
✅ *تم استلام رسالتك بنجاح*

📨 *تفاصيل الرسالة:*
{text[:200]}...

⚖️ *الحالة:* سيقوم أحد محامينا المتخصصين بالرد عليك قريبًا.

🤝 *شكرًا لثقتك بـ {BOT_NAME}*
    """

    await send_telegram_message(context, chat_id, reply_text)
    log_to_sheet(user_id, user_name, text, reply_text)

# ========== التشغيل ==========
def main():
    app_telegram = Application.builder().token(BOT_TOKEN).build()
    app_telegram.add_handler(CommandHandler("start", start))
    app_telegram.add_handler(CallbackQueryHandler(handle_callback))
    app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_text))
    app_telegram.run_polling()

if __name__ == "__main__":
    Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))).start()
    main()
