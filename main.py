# main.py
# ===========================
# 🤖 Legal Consultation Bot (Fixed)
# ===========================
import os
import logging
from threading import Thread

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# قراءة المتغيرات من بيئة التشغيل (أمن)
BOT_TOKEN = os.getenv("BOT_TOKEN")
MANAGER_CHAT_ID_RAW = os.getenv("MANAGER_CHAT_ID")

# تحقق من المتغيرات وحول MANAGER_CHAT_ID إلى int
if not BOT_TOKEN:
    raise SystemExit("❌ خطأ: المتغير البيئي BOT_TOKEN غير معرّف. ضع توكن البوت في إعدادات الاستضافة.")
try:
    MANAGER_CHAT_ID = int(MANAGER_CHAT_ID_RAW) if MANAGER_CHAT_ID_RAW is not None else None
except ValueError:
    raise SystemExit("❌ خطأ: المتغير MANAGER_CHAT_ID يجب أن يحتوي رقمًا فقط.")

if MANAGER_CHAT_ID is None:
    raise SystemExit("❌ خطأ: المتغير البيئي MANAGER_CHAT_ID غير معرّف. ضع معرف المدير (رقم) في إعدادات الاستضافة.")

# قواعد البيانات المؤقتة في الذاكرة (يمكن استبدالها لاحقًا بقاعدة بيانات حقيقية)
users_db = {}
pending_approvals = {}
user_warnings = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    # تحقق إذا كان محظورًا
    if user_id in users_db and users_db[user_id].get("banned"):
        await update.message.reply_text("❌ تم حظرك من استخدام البوت.")
        return

    # إذا لم يكن معتمدًا بعد
    if user_id not in users_db or not users_db[user_id].get("approved"):
        keyboard = [
            [
                InlineKeyboardButton("✅ قبول المستخدم", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton("❌ رفض المستخدم", callback_data=f"reject_{user_id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await context.bot.send_message(
                chat_id=MANAGER_CHAT_ID,
                text=(
                    f"🆕 طلب انضمام جديد:\n\n"
                    f"👤 {user.first_name} {user.last_name or ''}\n"
                    f"📛 @{user.username or 'غير متوفر'}\n"
                    f"🆔 {user_id}\n\n"
                    f"اختر الإجراء:"
                ),
                reply_markup=reply_markup,
            )

            pending_approvals[user_id] = {
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
            }
            await update.message.reply_text("⏳ تم إرسال طلبك إلى الإدارة، يرجى انتظار الموافقة.")
        except Exception as e:
            await update.message.reply_text("❌ خطأ في الاتصال بالإدارة.")
            logger.exception("Error sending approval request to manager: %s", e)
    else:
        await show_main_menu(update, context)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📞 استشارة قانونية فورية", callback_data="consultation")],
        [InlineKeyboardButton("⚖️ أنواع الخدمات القانونية", callback_data="services")],
        [InlineKeyboardButton("🏢 عن المكتب والمحامين", callback_data="about")],
        [InlineKeyboardButton("📝 حجز موعد استشارة", callback_data="appointment")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "👋 أهلاً بك في البوت القانوني الذكي.\n\nاختر الخدمة المطلوبة:"

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)


async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if "_" not in data:
        await query.edit_message_text("بيانات غير صحيحة.")
        return
    action, user_id_str = data.split("_", 1)
    try:
        user_id = int(user_id_str)
    except ValueError:
        await query.edit_message_text("معرف المستخدم غير صالح.")
        return

    if action == "approve":
        users_db[user_id] = {"approved": True, "warnings": 0}
        pending_approvals.pop(user_id, None)
        try:
            await context.bot.send_message(chat_id=user_id, text="🎉 تم قبولك! اكتب /start للبدء.")
        except Exception:
            logger.exception("Could not send approval message to user %s", user_id)
        await query.edit_message_text(f"✅ تمت الموافقة على المستخدم {user_id}")

    elif action == "reject":
        pending_approvals.pop(user_id, None)
        try:
            await context.bot.send_message(chat_id=user_id, text="❌ تم رفض طلبك.")
        except Exception:
            logger.exception("Could not send rejection message to user %s", user_id)
        await query.edit_message_text(f"❌ تم رفض المستخدم {user_id}")


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "consultation":
        await query.edit_message_text(
            "📞 أرسل وصف مشكلتك القانونية بالتفصيل وسيتواصل معك أحد المحامين."
        )

    elif data == "services":
        await query.edit_message_text(
            "⚖️ خدماتنا:\n• صياغة العقود\n• المرافعات\n• الاستشارات\n• القضايا التجارية والعقارية"
        )

    elif data == "about":
        await query.edit_message_text(
            "🏢 مكتب المحاماة:\nنحن محامون متخصصون في مختلف القضايا.\n📞 +967776086053\n📧 info@lawfirm.com"
        )

    elif data == "appointment":
        await query.edit_message_text("📝 للحجز، أرسل اسمك ونوع القضية والتاريخ المطلوب.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = (update.message.text or "").lower()

    if user_id not in users_db or not users_db[user_id].get("approved"):
        await update.message.reply_text("⏳ لا يمكنك استخدام البوت حتى يتم الموافقة عليك.")
        return

    forbidden = ["http://", "https://", ".com", "سب", "شتم", "قذف"]
    for bad in forbidden:
        if bad in text:
            user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
            count = user_warnings[user_id]
            if count >= 3:
                users_db[user_id]["banned"] = True
                await update.message.reply_text("❌ تم حظرك بسبب مخالفات متكررة.")
                try:
                    await context.bot.send_message(
                        chat_id=MANAGER_CHAT_ID, text=f"🚨 تم حظر المستخدم {user_id}"
                    )
                except Exception:
                    logger.exception("Could not notify manager about ban for user %s", user_id)
                return
            else:
                await update.message.reply_text(f"⚠️ تحذير ({count}/3): يمنع نشر روابط أو كلمات مسيئة.")
                try:
                    await context.bot.send_message(
                        chat_id=MANAGER_CHAT_ID, text=f"⚠️ مخالفة من المستخدم {user_id}"
                    )
                except Exception:
                    logger.exception("Could not notify manager about infraction for user %s", user_id)
                return

    await update.message.reply_text("✅ تم استلام رسالتك، سيتم الرد عليك قريباً.")


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # أمر الحظر من المدير فقط
    try:
        sender_id = update.effective_user.id
    except Exception:
        return

    if sender_id != MANAGER_CHAT_ID:
        await update.message.reply_text("❌ غير مصرح لك باستخدام هذا الأمر.")
        return

    if context.args:
        try:
            uid = int(context.args[0])
            if uid not in users_db:
                users_db[uid] = {}
            users_db[uid]["banned"] = True
            await update.message.reply_text(f"✅ تم حظر المستخدم {uid}")
        except ValueError:
            await update.message.reply_text("❌ يرجى إدخال رقم معرف صحيح.")


# --- Main function to start the bot ---
def main():
    # يبني تطبيق البوت ويشغّل polling
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CallbackQueryHandler(handle_approval, pattern=r"^(approve|reject)_"))
    application.add_handler(CallbackQueryHandler(handle_menu, pattern=r"^(consultation|services|about|appointment)$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 البوت القانوني يعمل الآن...")
    # تشغيل long polling (آمن للاستخدام على Render مع الخادوم الوهمي)
    application.run_polling()


# -------------------------------
# 🚀 Fake web server for Render (keeps the Web Service alive)
# -------------------------------
from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
    return "Legal Bot is running!"


def run_flask():
    # Render يعطي عدة عناوين؛ نستخدم 10000 كمنفذ بسيط ضمن بيئة Render
    app.run(host="0.0.0.0", port=10000)


if __name__ == "__main__":
    # شغّل السيرفر الوهمي في الخلفية ثم شغّل البوت
    Thread(target=run_flask, daemon=True).start()
    main()
    def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CallbackQueryHandler(handle_approval, pattern=r"^(approve|reject)_"))
    application.add_handler(CallbackQueryHandler(handle_menu, pattern=r"^(consultation|services|about|appointment)$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 البوت القانوني يعمل الآن...")
    application.run_polling()

from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "Legal Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=10000)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    main()
