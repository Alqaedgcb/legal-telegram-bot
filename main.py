import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ⚠️ تأكد من تعيين هذه المتغيرات في Render
BOT_TOKEN = os.getenv('BOT_TOKEN')
MANAGER_CHAT_ID = os.getenv('MANAGER_CHAT_ID')

# قاعدة بيانات مؤقتة في الذاكرة
users_db = {}
pending_approvals = {}
user_warnings = {}

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        user_id = user.id
        
        logger.info(f"User {user_id} started the bot")
        
        # التحقق إذا كان محظوراً
        if users_db.get(user_id, {}).get('banned'):
            await update.message.reply_text("❌ تم حظرك من استخدام البوت.")
            return
            
        # إذا لم يكن معتمداً بعد
        if user_id not in users_db or not users_db[user_id].get('approved'):
            # إنشاء أزرار الموافقة
            keyboard = [
                [
                    InlineKeyboardButton("✅ قبول المستخدم", callback_data=f"approve_{user_id}"),
                    InlineKeyboardButton("❌ رفض المستخدم", callback_data=f"reject_{user_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # إرسال طلب للمدير
            await context.bot.send_message(
                chat_id=MANAGER_CHAT_ID,
                text=f"🆕 طلب انضمام جديد:\n\n"
                     f"👤 المستخدم: {user.first_name}\n"
                     f"📛 username: @{user.username or 'غير متوفر'}\n"
                     f"🆔 ID: {user_id}\n\n"
                     f"اختر الإجراء المناسب:",
                reply_markup=reply_markup
            )
            
            # حفظ بيانات المستخدم
            users_db[user_id] = {
                'first_name': user.first_name,
                'username': user.username,
                'status': 'pending'
            }
            
            await update.message.reply_text(
                "⏳ تم إرسال طلب الانضمام للإدارة.\n"
                "سيتم إعلامك عند الموافقة على طلبك."
            )
            
        else:
            # إذا كان معتمداً، عرض القائمة
            await show_main_menu(update, context)
            
    except Exception as e:
        logger.error(f"Error in start: {e}")
        await update.message.reply_text("❌ حدث خطأ، يرجى المحاولة لاحقاً.")

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض القائمة الرئيسية"""
    keyboard = [
        [InlineKeyboardButton("📞 استشارة قانونية فورية", callback_data="consultation")],
        [InlineKeyboardButton("⚖️ أنواع الخدمات القانونية", callback_data="services")],
        [InlineKeyboardButton("🏢 عن المكتب والمحامين", callback_data="about")],
        [InlineKeyboardButton("📝 حجز موعد استشارة", callback_data="appointment")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = """
👋 أهلاً وسهلاً بك في البوت القانوني المتخصص

اختر الخدمة التي تناسب احتياجك:
"""
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة طلبات الموافقة"""
    try:
        query = update.callback_query
        await query.answer()
        
        data = query.data
        action, user_id = data.split('_')
        user_id = int(user_id)
        
        if action == "approve":
            # قبول المستخدم
            users_db[user_id] = {
                'approved': True,
                'warnings': 0,
                'first_name': users_db.get(user_id, {}).get('first_name', ''),
                'username': users_db.get(user_id, {}).get('username', '')
            }
            
            # إرسال رسالة للمستخدم
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="🎉 تم قبول طلب انضمامك!\n\n"
                         "يمكنك الآن استخدام كافة خدمات البوت القانوني.\n"
                         "اكتب /start لرؤية القائمة الرئيسية."
                )
            except Exception as e:
                logger.error(f"Could not send approval message to user {user_id}: {e}")
            
            await query.edit_message_text(f"✅ تم قبول المستخدم {user_id}")
            
        elif action == "reject":
            # رفض المستخدم
            users_db[user_id] = {'banned': True}
            
            # إرسال رسالة للمستخدم
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ نأسف، تم رفض طلب انضمامك للبوت القانوني."
                )
            except Exception as e:
                logger.error(f"Could not send rejection message to user {user_id}: {e}")
            
            await query.edit_message_text(f"❌ تم رفض المستخدم {user_id}")
            
    except Exception as e:
        logger.error(f"Error in handle_approval: {e}")

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة اختيارات القائمة"""
    try:
        query = update.callback_query
        await query.answer()
        
        choice = query.data
        
        if choice == "consultation":
            await query.edit_message_text(
                "📞 الاستشارة القانونية الفورية:\n\n"
                "يمكنك الآن وصف مشكلتك القانونية بالتفصيل، وسيقوم أحد محامينا المتخصصين بالرد عليك في أقرب وقت.\n\n"
                "⬇️ اكتب رسالتك الآن..."
            )
        
        elif choice == "services":
            await query.edit_message_text(
                "⚖️ خدماتنا القانونية المتكاملة:\n\n"
                "• 📝 صياغة العقود والاتفاقيات\n"
                "• 🏛️ المرافعات والدفوع القضائية\n"
                "• 💼 الاستشارات القانونية المتخصصة\n"
                "• 📄 التوثيق والتصديق القانوني\n"
                "• ⚔️ القضايا والمنازعات القانونية\n"
                "• 🏠 قضايا العقارات والأملاك\n"
                "• 👨‍👩‍👧‍👦 قضايا الأحوال الشخصية\n"
                "• 💰 القضايا التجارية والمالية\n\n"
                "اختر 'استشارة فورية' لبدء الخدمة المناسبة لك."
            )
        
        elif choice == "about":
            await query.edit_message_text(
                "🏢 مكتب المحاماة المتخصص:\n\n"
                "نحن فريق من المحامين المتخصصين في مختلف المجالات القانونية، نقدم خدماتنا باحترافية وشفافية.\n\n"
                "📞 للتواصل المباشر:\n"
                "الهاتف: +966123456789\n"
                "البريد الإلكتروني: info@lawfirm.com\n\n"
                "🕐 أوقات العمل:\n"
                "من الأحد إلى الخميس\n"
                "8:00 ص - 6:00 م"
            )
        
        elif choice == "appointment":
            await query.edit_message_text(
                "📝 حجز موعد استشارة:\n\n"
                "لحجز موعد مع محامٍ متخصص، يرجى:\n\n"
                "📞 الاتصال على: +966123456789\n"
                "📧 المراسلة على: appointments@lawfirm.com\n\n"
                "أو يمكنك إرسال:\n"
                "• الاسم الكامل\n"
                "• نوع الاستشارة\n"
                "• التاريخ والوقت المناسب\n"
                "وسنتواصل معك لتأكيد الموعد."
            )
            
    except Exception as e:
        logger.error(f"Error in handle_menu: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية"""
    try:
        user_id = update.effective_user.id
        message_text = update.message.text
        
        logger.info(f"Message from user {user_id}: {message_text}")
        
        # التحقق من صلاحية المستخدم
        if user_id not in users_db or not users_db[user_id].get('approved'):
            await update.message.reply_text("⏳ لا يمكنك استخدام البوت حتى يتم الموافقة على طلبك.")
            return
        
        # فحص المحتوى المحظور
        forbidden_words = ["http://", "https://", ".com", ".org", "سب", "شتم", "قذف", "شتيمة"]
        for word in forbidden_words:
            if word in message_text.lower():
                # زيادة التحذيرات
                if user_id not in user_warnings:
                    user_warnings[user_id] = 0
                user_warnings[user_id] += 1
                
                warnings = user_warnings[user_id]
                
                if warnings >= 3:
                    # حظر المستخدم
                    users_db[user_id]['banned'] = True
                    await update.message.reply_text("❌ تم حظرك من البوت due to repeated violations.")
                    
                    # إشعار المدير
                    await context.bot.send_message(
                        chat_id=MANAGER_CHAT_ID,
                        text=f"🚨 تم حظر المستخدم {user_id}\nالسبب: repeated violations\nآخر رسالة: {message_text[:100]}..."
                    )
                    return
                else:
                    await update.message.reply_text(
                        f"⚠️ تحذير ({warnings}/3): يمنع مشاركة روابط أو كلمات غير لائقة.\n"
                        f"التكرار يؤدي إلى الحظر الدائم."
                    )
                    
                    # إشعار المدير
                    await context.bot.send_message(
                        chat_id=MANAGER_CHAT_ID,
                        text=f"⚠️ مخالفة من المستخدم {user_id}\nالتحذيرات: {warnings}/3\nالرسالة: {message_text[:200]}..."
                    )
                    return
        
        # إذا كانت الرسالة نظيفة
        await update.message.reply_text(
            "✅ تم استلام رسالتك بنجاح.\n\n"
            "سيقوم أحد محامينا المتخصصين بالرد عليك في أقرب وقت ممكن.\n\n"
            "شكراً لثقتك بمكتبنا القانوني."
        )
        
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر حظر المستخدم (للمدير فقط)"""
    try:
        if str(update.effective_user.id) != MANAGER_CHAT_ID:
            await update.message.reply_text("❌ ليس لديك صلاحية لهذا الأمر.")
            return
        
        if not context.args:
            await update.message.reply_text("❌ يرجى تقديم معرف المستخدم. مثال: /ban 123456789")
            return
        
        user_id = int(context.args[0])
        users_db[user_id] = {'banned': True}
        
        await update.message.reply_text(f"✅ تم حظر المستخدم {user_id}")
        
        # إرسال إشعار للمستخدم
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ تم حظرك من استخدام البوت بقرار من الإدارة."
            )
        except Exception as e:
            logger.error(f"Could not send ban notification to user {user_id}: {e}")
            
    except ValueError:
        await update.message.reply_text("❌ معرف المستخدم يجب أن يكون رقماً.")
    except Exception as e:
        logger.error(f"Error in ban_command: {e}")

def main():
    """الدالة الرئيسية - بدون asyncio.run"""
    try:
        # التحقق من إعدادات البيئة
        if not BOT_TOKEN:
            logger.error("❌ BOT_TOKEN غير مضبوط. يرجى تعيينه في متغيرات البيئة.")
            return
            
        if not MANAGER_CHAT_ID:
            logger.error("❌ MANAGER_CHAT_ID غير مضبوط. يرجى تعيينه في متغيرات البيئة.")
            return
        
        logger.info("🚀 بدء تشغيل البوت القانوني...")
        logger.info(f"المدير: {MANAGER_CHAT_ID}")
        
        # إنشاء التطبيق
        application = Application.builder().token(BOT_TOKEN).build()
        
        # إضافة المعالجات
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("ban", ban_command))
        application.add_handler(CallbackQueryHandler(handle_approval, pattern="^(approve|reject)_"))
        application.add_handler(CallbackQueryHandler(handle_menu, pattern="^(consultation|services|about|appointment)$"))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        # التشغيل المباشر - بدون asyncio.run
        logger.info("✅ البوت جاهز للتشغيل...")
        application.run_polling()
        
    except Exception as e:
        logger.error(f"❌ فشل في تشغيل البوت: {e}")

if __name__ == "__main__":
    main()
