import os
import logging
import datetime
import gspread
from google.oauth2.service_account import Credentials
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from threading import Thread

# ========== إعدادات البوت ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN") or "YOUR_TOKEN"
BOT_NAME = "فَصْل | Fasl"
BOT_LOGO = "⚖️"
# ⬇️ تأكد أن هذا الرقم صحيح وبدون @
MANAGER_CHAT_ID = int(os.environ.get("MANAGER_CHAT_ID") or 123456789)

# قاعدة بيانات داخلية مؤقتة
users_db = {}
user_warnings = {}

# ========== إعداد السجلات ==========
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)

# ========== إعداد Flask ==========
app = Flask(__name__)

@app.route('/')
def home():
    return f"{BOT_NAME} Bot is running ✅"

# ========== Google Sheets (إذا تستخدمها) ==========
# ضع إعداد Google Sheets هنا إذا سبق وفعّلته؛ إذا لم يكن مطلوبًا، تجاهل الأقسام الخاصة به.

# ========== أدوات المساعدة ==========
async def safe_send(bot, chat_id, text, reply_markup=None, parse_mode="Markdown"):
    """إرسال رسالة مع تتبّع الأخطاء وإرجاع True/False"""
    try:
        if reply_markup:
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        logger.info(f"📤 Sent message to {chat_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send message to {chat_id}: {e}")
        return False

# ========== الأوامر ==========
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /start للمستخدمين والمدير"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    logger.info(f"/start from user {user.id} - {user.full_name}")

    # تأكد أن المدير عمل /start للبوت على الأقل مرة
    if user.id == MANAGER_CHAT_ID:
        await safe_send(context.bot, chat_id, "أهلاً بك مدير النظام. تم تسجيل دخولك.")
        return

    if user.id not in users_db:
        users_db[user.id] = {"approved": False, "banned": False, "name": user.full_name}
        # بناء لوحة الموافقة
        keyboard = [
            [
                InlineKeyboardButton("✅ قبول", callback_data=f"approve_user:{user.id}"),
                InlineKeyboardButton("❌ رفض", callback_data=f"reject_user:{user.id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # أرسل للمدير مع فحص النتيجة
        sent = await safe_send(
            context.bot,
            MANAGER_CHAT_ID,
            f"👤 مستخدم جديد انضم:\n\nالاسم: *{user.full_name}*\nID: `{user.id}`\n\nهل ترغب بقبوله؟",
            reply_markup=reply_markup
        )
        if not sent:
            # احتمال أن المدير لم يبدأ المحادثة مع البوت
            await safe_send(context.bot, chat_id,
                "⚠️ تم إرسال طلب الانضمام للمدير لكن لم يتم تسليمه.\n"
                "تأكد أن المدير بدأ المحادثة مع البوت (`/start`)."
            )
            logger.warning(f"Manager ({MANAGER_CHAT_ID}) did not receive the approval request. Ask manager to /start the bot.")
        else:
            await safe_send(context.bot, chat_id, "⏳ تم إرسال طلبك للإدارة للموافقة عليه.")
    else:
        state = users_db[user.id]
        if state.get("banned"):
            await safe_send(context.bot, chat_id, "🚫 تم حظرك من استخدام البوت.")
        elif state.get("approved"):
            await safe_send(context.bot, chat_id, "👋 مرحبًا مجددًا! أنت معتمد الآن.")
        else:
            await safe_send(context.bot, chat_id, "⏳ طلبك قيد المراجعة من الإدارة.")

# ========== التعامل مع callback queries ==========
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # سجّل كامل المحتوى لمتابعة الأخطاء
    logger.info(f"CallbackQuery received from {query.from_user.id}: data={query.data!r}, message_id={getattr(query.message,'message_id',None)}")
    await query.answer()  # مؤكد للـTelegram

    data = query.data or ""
    try:
        if data.startswith("approve_user:"):
            user_id = int(data.split(":", 1)[1])
            # تحقق من وجود المستخدم
            if user_id not in users_db:
                users_db[user_id] = {"approved": True, "banned": False, "name": ""}
            else:
                users_db[user_id]["approved"] = True
                users_db[user_id]["banned"] = False

            # تعديل رسالة المدير لتأكيد الإجراء (إذا ممكن)
            try:
                await query.edit_message_text(f"✅ تم قبول المستخدم {user_id} بنجاح.")
            except Exception as e:
                logger.warning(f"Could not edit manager message: {e}")

            # إرسال إشعار للمستخدم
            ok = await safe_send(context.bot, user_id, "🎉 تم قبولك بنجاح! يمكنك الآن استخدام البوت.")
            if not ok:
                # إذا لم يستطع إرسال للمستخدم — سجّل التحذير
                logger.warning(f"Could not notify user {user_id} after approval. User may not have started the bot.")

            logger.info(f"User {user_id} approved by admin {query.from_user.id}")

        elif data.startswith("reject_user:"):
            user_id = int(data.split(":", 1)[1])
            users_db[user_id] = {"approved": False, "banned": True, "name": users_db.get(user_id,{}).get("name","")}
            try:
                await query.edit_message_text(f"🚫 تم رفض المستخدم {user_id}.")
            except Exception as e:
                logger.warning(f"Could not edit manager message: {e}")

            ok = await safe_send(context.bot, user_id, "❌ تم رفض طلبك للانضمام إلى النظام.")
            if not ok:
                logger.warning(f"Could not notify user {user_id} after rejection.")

            logger.info(f"User {user_id} rejected by admin {query.from_user.id}")

        else:
            logger.warning(f"Unhandled callback data: {data}")

    except Exception as ex:
        logger.exception(f"Exception handling callback: {ex}")
        # اعطِ ردًا واضحًا للمدير
        try:
            await query.edit_message_text("❌ حدث خطأ أثناء معالجة طلب الانضمام. الرجاء المحاولة لاحقًا.")
        except:
            pass

# ========== معالجة رسائل المستخدمين ==========
async def handle_user_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    logger.info(f"Message from {user_id}: {text[:120]!r}")

    # تحقق الموافقة
    if user_id not in users_db or not users_db[user_id].get("approved"):
        await safe_send(context.bot, chat_id, "⏳ لا يمكنك استخدام البوت حتى تتم الموافقة على طلبك.")
        return

    if users_db[user_id].get("banned"):
        await safe_send(context.bot, chat_id, "🚫 تم حظرك من استخدام البوت.")
        return

    # فلترة كلمات مسيئة
    forbidden = ["سب", "شتم", "قذف", "شتيمة", "http://", "https://", ".com"]
    for w in forbidden:
        if w in text.lower():
            user_warnings[user_id] = user_warnings.get(user_id, 0) + 1
            if user_warnings[user_id] >= 3:
                users_db[user_id]["banned"] = True
                await safe_send(context.bot, chat_id, "❌ تم حظرك بسبب تكرار المخالفات.")
                await safe_send(context.bot, MANAGER_CHAT_ID, f"🚨 تم حظر المستخدم {user_id} لأسباب سلوكية.")
                return
            else:
                await safe_send(context.bot, chat_id, f"⚠️ تحذير ({user_warnings[user_id]}/3): يمنع استخدام الألفاظ غير اللائقة.")
                await safe_send(context.bot, MANAGER_CHAT_ID, f"⚠️ مخالفة من المستخدم {user_id} ({user_warnings[user_id]}/3).")
                return

    # الرد الواثق
    reply = f"{BOT_LOGO} ✅ تم استلام رسالتك، سيتم الرد عليك قريباً."
    await safe_send(context.bot, chat_id, reply)
    # هنا يمكنك استدعاء log_to_sheet(...) إن كانت مهيأة

# ========== التشغيل ==========
def main():
    app_telegram = Application.builder().token(BOT_TOKEN).build()
    app_telegram.add_handler(CommandHandler("start", start_cmd))
    # نستخدم CallbackQueryHandler بدون pattern ليغطي كل الـcallback
    app_telegram.add_handler(CallbackQueryHandler(handle_callback))
    app_telegram.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_text))

    logger.info("Starting Telegram polling...")
    app_telegram.run_polling()

if __name__ == "__main__":
    # شغّل Flask في Thread منفصل للحفاظ على endpoint صحي (لـFly/Render)
    Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))).start()
    main()
