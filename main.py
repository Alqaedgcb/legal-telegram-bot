# ===========================
# 🤖 Legal Consultation Bot (v2.1)
# متوافق مع python-telegram-bot 21.3 و Render
# ===========================

import os
import logging
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ⚠️ ضع بياناتك
BOT_TOKEN = "ضع_توكن_البوت_هنا"
MANAGER_CHAT_ID = "ضع_معرفك_هنا"  # معرف المدير (رقم ID)

# 🗂️ قواعد البيانات البسيطة
users_db = {}
pending_approvals = {}
user_warnings = {}

# إعدادات اللوج
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===========================
# 🧭 أوامر البوت الأساسية
# ===========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    # التحقق من الحظر
    if user_id in users_db and users_db[user_id].get("banned"):
        await update.message.reply_text("❌ تم حظرك من استخدام البوت.")
        return

    # التحقق من الموافقة
    if user_id not in users_db or not users_db[user_id].get("approved"):
        keyboard = [
            [
                InlineKeyboardButton("✅ قبول المستخدم", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton("❌ رفض المستخدم", callback_data=f"reject_{user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await context.bot.send_message(
                chat_id=MANAGER_CHAT_ID,
                text=f"🆕 طلب انضمام جديد:\n\n"
                     f"👤 {user.first_name} {user.last_name or ''}\n"
                     f"📛 @{user.username or 'غير متوفر'}\n"
                     f"🆔 {user_id}\n\n"
                     f"اختر الإجراء:",
                reply_markup=reply_markup
            )

            pending_approvals[user_id] = {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username
            }

            await update.message.reply_text(
                "⏳ تم إرسال طلب الانضمام إلى الإدارة.\n"
                "سيتم إعلامك عند الموافقة على طلبك."
            )

        except Exception as e:
            await update.message.reply_text("❌ حدث خطأ في الإعدادات.")
            logger.error(f"Error in start: {e}")
    else:
        await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📞 استشارة قانونية فورية", callback_data="consultation")],
        [InlineKeyboardButton("⚖️ أنواع الخدمات القانونية", callback_data="services")],
        [InlineKeyboardButton("🏢 عن المكتب والمحامين", callback_data="about")],
        [InlineKeyboardButton("📝 حجز موعد استشارة", callback_data="appointment")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "👋 أهلاً وسهلاً بك في البوت القانوني المتخصص.\n\n"
        "اختر الخدمة التي تناسب احتياجك:"
    )

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, user_id = query.data.split("_")
    user_id = int(user_id)

    if action == "approve":
        users_db[user_id] = {"approved": True, "warnings": 0}
        pending_approvals.pop(user_id, None)

        await context.bot.send_message(
            chat_id=user_id,
            text="🎉 تم قبول طلبك! يمكنك الآن استخدام جميع خدمات البوت.\nاكتب /start للبدء."
        )
        await query.edit_message_text(f"✅ تم قبول المستخدم {user_id}")

    elif action == "reject":
        pending_approvals.pop(user_id, None)
        await context.bot.send_message(chat_id=user_id, text="❌ تم رفض طلبك.")
        await query.edit_message_text(f"❌ تم رفض المستخدم {user_id}")

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "consultation":
        await query.edit_message_text(
            "📞 أرسل مشكلتك القانونية بالتفصيل.\n"
            "سيقوم أحد المحامين بالرد عليك قريباً."
        )

    elif choice == "services":
        await query.edit_message_text(
            "⚖️ خدماتنا القانونية:\n\n"
            "• 📝 صياغة العقود\n"
            "• 🏛️ المرافعات القضائية\n"
            "• 💼 الاستشارات القانونية\n"
            "• 📄 التوثيق القانوني\n"
            "• ⚔️ القضايا التجارية والعقارية"
        )

    elif choice == "about":
        await query.edit_message_text(
            "🏢 مكتب المحاماة المتخصص:\n\n"
            "نحن فريق من المحامين المعتمدين بخبرة طويلة.\n\n"
            "📞  +966123456789\n"
            "📧  info@lawfirm.com"
        )

    elif choice == "appointment":
        await query.edit_message_text(
            "📝 لحجز موعد، أرسل اسمك ونوع القضية والتاريخ المطلوب."
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.lower()

    if user_id not in users_db or not users_db[user_id].get("approved"):
        await update.message.reply_text("⏳ لا يمكنك استخدام البوت حتى تتم الموافقة عليك.")
        return

    forbidden = ["http://", "https://", ".com", ".org", "سب", "شتم", "قذف"]
    for bad in forbidden:
        if bad in text:
            user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
            count = user_warnings[user_id]
            if count >= 3:
                users_db[user_id]["banned"] = True
                await update.message.reply_text("❌ تم حظرك بسبب مخالفات متكررة.")
                await context.bot.send_message(chat_id=MANAGER_CHAT_ID, text=f"🚨 تم حظر المستخدم {user_id}")
                return
            else:
                await update.message.reply_text(f"⚠️ تحذير ({count}/3): يمنع نشر روابط أو كلمات مسيئة.")
                await context.bot.send_message(chat_id=MANAGER_CHAT_ID, text=f"⚠️ مخالفة من المستخدم {user_id}")
                return

    await update.message.reply_text("✅ تم استلام رسالتك، وسيتم الرد عليك قريباً.")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != MANAGER_CHAT_ID:
        return
    if context.args:
        try:
            uid = int(context.args[0])
            users_db[uid] = {"banned": True}
            await update.message.reply_text(f"✅ تم حظر المستخدم {uid}")
        except:
            await update.message.reply_text("❌ رقم غير صالح.")

# ===========================
# 🚀 تشغيل البوت والسيرفر معاً
# ===========================

def main():
    async def run_bot():
        app = (
            Application.builder()
            .token(BOT_TOKEN)
            .build()
        )

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("ban", ban_command))
        app.add_handler(CallbackQueryHandler(handle_approval, pattern=r"^(approve|reject)_"))
        app.add_handler(CallbackQueryHandler(handle_menu, pattern=r"^(consultation|services|about|appointment)$"))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        print("🤖 البوت القانوني يعمل الآن...")
        await app.run_polling()

    asyncio.run(run_bot())


# ===========================
# 🌐 Fake web server for Render
# ===========================

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ Legal Consultation Bot is Running!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=10000)

if __name__ == "__main__":
    Thread(target=run_flask).start()
    main()
