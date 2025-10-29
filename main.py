import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# الإعدادات
BOT_TOKEN = os.getenv('BOT_TOKEN')
MANAGER_CHAT_ID = os.getenv('MANAGER_CHAT_ID')

# تخزين البيانات
users_db = {}
pending_approvals = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if users_db.get(user_id, {}).get('banned'):
        await update.message.reply_text("❌ تم حظرك")
        return
        
    if not users_db.get(user_id, {}).get('approved'):
        keyboard = [
            [InlineKeyboardButton("✅ قبول", callback_data=f"approve_{user_id}"),
             InlineKeyboardButton("❌ رفض", callback_data=f"reject_{user_id}")]
        ]
        
        try:
            await context.bot.send_message(
                MANAGER_CHAT_ID,
                f"📋 طلب جديد:\n👤 {user.first_name}\n🆔 {user_id}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            users_db[user_id] = {'status': 'pending'}
            await update.message.reply_text("⏳ تم إرسال طلبك للمدير")
            
        except Exception as e:
            await update.message.reply_text("❌ حدث خطأ في الإعدادات")
    else:
        await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📞 استشارة فورية", callback_data="consult")],
        [InlineKeyboardButton("⚖️ خدمات قانونية", callback_data="services")],
        [InlineKeyboardButton("ℹ️ معلومات", callback_data="about")]
    ]
    
    await update.message.reply_text(
        "🎯 اختر الخدمة:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith('approve_'):
        user_id = int(data.split('_')[1])
        users_db[user_id] = {'approved': True}
        await context.bot.send_message(user_id, "🎉 تم قبولك! /start")
        await query.edit_message_text(f"✅ تم قبول {user_id}")
        
    elif data.startswith('reject_'):
        user_id = int(data.split('_')[1])
        users_db[user_id] = {'banned': True}
        await context.bot.send_message(user_id, "❌ تم رفض طلبك")
        await query.edit_message_text(f"❌ تم رفض {user_id}")
        
    elif data == "consult":
        await query.edit_message_text("💬 اكتب استشارتك...")
    elif data == "services":
        await query.edit_message_text("📋 الخدمات: عقود - قضايا - استشارات")
    elif data == "about":
        await query.edit_message_text("🏢 محامون متخصصون")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not users_db.get(user_id, {}).get('approved'):
        await update.message.reply_text("⌛ انتظر الموافقة أولاً")
        return
        
    text = update.message.text
    
    if any(word in text for word in ['http', '.com', 'سب', 'شتم']):
        await update.message.reply_text("⚠️ يمنع هذا المحتوى")
        return
        
    await update.message.reply_text("✅ تم الاستلام، سنرد قريباً")

def main():
    try:
        if not BOT_TOKEN:
            logger.error("❌ BOT_TOKEN غير مضبوط")
            return
            
        if not MANAGER_CHAT_ID:
            logger.error("❌ MANAGER_CHAT_ID غير مضبوط")
            return
        
        application = Application.builder().token(BOT_TOKEN).build()
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(handle_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        logger.info("🚀 بدء تشغيل البوت...")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ خطأ في التشغيل: {e}")

if __name__ == "__main__":
    main()
