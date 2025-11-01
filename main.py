import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# بيانات البيئة (توكن البوت)
TOKEN = os.getenv("BOT_TOKEN")

# يمكنك وضع ID الأدمن مباشرة أو من environment variable
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))  # ضع رقمك هنا

# القوائم لحفظ المستخدمين مؤقتًا
pending_users = {}
approved_users = set()


# 🟢 أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    if chat_id in approved_users:
        await update.message.reply_text("مرحباً بك مجددًا ✅")
        return

    # إرسال إشعار للأدمن
    keyboard = [
        [
            InlineKeyboardButton("✅ قبول", callback_data=f"accept_{chat_id}"),
            InlineKeyboardButton("❌ رفض", callback_data=f"reject_{chat_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"طلب جديد من المستخدم:\n"
             f"👤 الاسم: {user.first_name}\n"
             f"🆔 ID: {chat_id}",
        reply_markup=reply_markup
    )

    pending_users[chat_id] = user.first_name
    await update.message.reply_text("🔒 تم إرسال طلبك للإدارة، الرجاء الانتظار حتى يتم قبولك.")


# 🔘 التعامل مع القبول / الرفض
async def handle_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if not data.startswith(("accept_", "reject_")):
        return

    target_id = int(data.split("_")[1])

    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ ليس لديك صلاحية لهذا الإجراء.")
        return

    if data.startswith("accept_"):
        approved_users.add(target_id)
        pending_users.pop(target_id, None)
        await context.bot.send_message(
            chat_id=target_id,
            text="✅ تم قبولك! يمكنك الآن استخدام البوت بحرية."
        )
        await query.edit_message_text("✅ تم قبول المستخدم بنجاح.")
    else:
        pending_users.pop(target_id, None)
        await context.bot.send_message(
            chat_id=target_id,
            text="❌ تم رفض طلبك. يمكنك المحاولة لاحقًا."
        )
        await query.edit_message_text("🚫 تم رفض المستخدم.")


# 📩 استقبال الرسائل بعد القبول
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in approved_users:
        await update.message.reply_text("❗ أنت غير مقبول بعد. أرسل /start لتقديم طلب.")
        return

    text = update.message.text
    await update.message.reply_text(f"📨 رسالتك تم استلامها: {text}")


# 🚀 تشغيل التطبيق
def main():
    if not TOKEN:
        print("❌ خطأ: BOT_TOKEN غير موجود في المتغيرات.")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_decision))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 البوت يعمل الآن ...")
    app.run_polling()


if __name__ == "__main__":
    main()
