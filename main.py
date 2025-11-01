import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# إعداد المتغيرات
TOKEN = os.getenv("BOT_TOKEN")
RAILWAY_URL = os.getenv("RAILWAY_URL")  # مثال: https://yourapp-production.up.railway.app

app = Flask(__name__)
application = Application.builder().token(TOKEN).build()


# ====== أوامر البوت الأساسية ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 مرحبًا بك في المستشار القانوني الذكي.\n"
        "أنا هنا لمساعدتك في استشاراتك القانونية باحترافية ودقة عالية."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # منع الإساءات
    bad_words = ["لعن", "قذف", "سب", "شت", "حقير", "سخيف"]
    if any(word in text for word in bad_words):
        await update.message.reply_text(
            "⚠️ تنبيه: يُرجى الالتزام بالاحترام. تكرار المخالفة سيؤدي إلى الحظر."
        )
        return

    # الرد الذكي المؤقت
    response = f"📘 تم استلام سؤالك القانوني:\n\n«{text}»\n\nسيتم تحليله وإعطاؤك الرد المناسب."
    await update.message.reply_text(response)


# إضافة المعالجات
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))


# ====== إعداد Flask للـ Webhook ======
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    """تستقبل التحديثات من Telegram"""
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok", 200


@app.route("/")
def set_webhook():
    """ضبط Webhook تلقائيًا عند تشغيل السيرفر"""
    webhook_url = f"{RAILWAY_URL}/{TOKEN}"
    application.bot.set_webhook(url=webhook_url)
    return f"✅ Webhook set to {webhook_url}", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
