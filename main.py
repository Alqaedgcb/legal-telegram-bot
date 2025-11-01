import os
import logging
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ========== إعدادات البوت ==========
BOT_TOKEN = "YOUR_TOKEN"
BOT_NAME = "فَصْل | Fasl"
BOT_LOGO = "⚖️"
MANAGER_CHAT_ID = 123456789  # ضع رقم حساب المدير هنا

# قاعدة بيانات داخلية بسيطة
users_db = {}
user_warnings = {}

# إعداد السجلّات
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask لإبقاء السيرفر نشط
app = Flask(__name__)

@app.route('/')
def home():
    return f"{BOT_NAME} Bot is running ✅"


# ========== دوال المساعدة ==========

async def send_telegram_message(context, chat_id, text):
    """إرسال رسالة نصية"""
    try:
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"❌ خطأ أثناء إرسال الرسالة: {e}")


# ========== الأوامر الأساسية ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء المحادثة مع المستخدم"""
    user = update.effective_user
    chat_id = update.effective_chat.id

    # تحقق إذا كان المستخدم جديد
    if user.id not in users_db:
        users_db[user.id] = {"approved": False, "banned": False, "name": user.full_name}

        # إرسال طلب الموافقة للمدير
        keyboard = [
            [
                InlineKeyboardButton("قبول ✅", callback_data=f"accept_{user.id}"),
                InlineKeyboardButton("رفض ❌", callback_data=f"reject_{user.id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=MANAGER_CHAT_ID,
            text=f"👤 مستخدم جديد انضم:\n\nالاسم: *{user.full_name}*\nID: `{user.id}`\n\nهل ترغب بقبوله؟",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        await update.message.reply_text("⏳ تم إرسال طلبك للإدارة للموافقة عليه.")
    else:
        await update.message.reply_text("مرحباً مجددًا 👋")


# ========== معالجة أزرار القبول / الرفض ==========

async def handle_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة أزرار المدير لقبول أو رفض المستخدمين"""
    query = update.callback_query
    await query.answer()

    try:
        action, user_id = query.data.split("_")
        user_id = int(user_id)
    except Exception:
        await query.edit_message_text("❌ حدث خطأ في التعرف على المستخدم.")
        return

    if action == "accept":
        users_db[user_id]["approved"] = True
        await query.edit_message_text(f"✅ تم قبول المستخدم {user_id} بنجاح.")
        await context.bot.send_message(chat_id=user_id, text="🎉 تم قبولك بنجاح! يمكنك الآن استخدام البوت.")
    elif action == "reject":
        users_db[user_id]["banned"] = True
        await query.edit_message_text(f"🚫 تم رفض المستخدم {user_id}.")
        await context.bot.send_message(chat_id=user_id, text="❌ تم رفض طلبك للانضمام إلى النظام.")


# ========== فلترة الرسائل للمستخدمين ==========
async def handle_user_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    if user_id not in users_db or not users_db[user_id].get("approved"):
        await send_telegram_message(context, chat_id, "⏳ لا يمكنك استخدام البوت حتى يتم الموافقة على طلبك.")
        return

    if users_db[user_id].get("banned"):
        await send_telegram_message(context, chat_id, "🚫 تم حظرك من استخدام البوت.")
        return

    # فحص الألفاظ غير اللائقة
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

    # الرد التلقائي للرسائل القانونية
    confirmation_message = f"""
{BOT_LOGO}
✅ *تم استلام رسالتك بنجاح*

📨 *تفاصيل الرسالة:*
{text[:200]}...

⚖️ *الحالة:* سيقوم أحد محامينا بالرد عليك قريبًا.

🤝 *شكرًا لثقتك بـ {BOT_NAME}*
    """
    await send_telegram_message(context, chat_id, confirmation_message)


# ========== تشغيل التطبيق ==========

def main():
    app_telegram = Application.builder().token(BOT_TOKEN).build()
    app_telegram.add_handler(CommandHandler("start", start))
    app_telegram.add_handler(CallbackQueryHandler(handle_decision))
    app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_text))
    app_telegram.run_polling()

if __name__ == "__main__":
    from threading import Thread
    Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))).start()
    main()
