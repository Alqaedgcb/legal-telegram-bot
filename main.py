import os
import logging
import threading
import time
import requests
from flask import Flask, request, jsonify
import json

# الإعدادات
BOT_TOKEN = os.getenv('BOT_TOKEN')
MANAGER_CHAT_ID = os.getenv('MANAGER_CHAT_ID')
APP_URL = "https://legal-telegram-bot-qsvz.onrender.com"

# الشعار الاحترافي للبوت
BOT_NAME = "المستشار القانوني الذكي"
BOT_LOGO = """
🏛️⚖️🤖 *المستشار القانوني الذكي* 🤖⚖️🏛️
*الذكاء الاصطناعي في خدمة القانون*
──────────────────────────────
"""

app = Flask(__name__)

# تخزين البيانات
users_db = {}
user_warnings = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def keep_alive():
    """إبقاء الخدمة نشطة باستمرار"""
    def ping():
        while True:
            try:
                response = requests.get(f'{APP_URL}/', timeout=10)
                logger.info(f"✅ Keep-alive ping: {response.status_code}")
            except Exception as e:
                logger.error(f"❌ Keep-alive failed: {e}")
            time.sleep(240)
    
    thread = threading.Thread(target=ping)
    thread.daemon = True
    thread.start()
    logger.info("🔄 نظام Keep-alive مفعل")

def send_telegram_message(chat_id, text, reply_markup=None):
    """إرسال رسالة عبر Telegram API مباشرة"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown'
    }
    
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        logger.info(f"📤 Message sent to {chat_id}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ Failed to send message: {e}")
        return False

def edit_message_text(chat_id, message_id, text):
    """تعديل رسالة موجودة"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text,
        'parse_mode': 'Markdown'
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ Failed to edit message: {e}")
        return False

def answer_callback_query(callback_query_id):
    """الرد على callback query"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
    payload = {
        'callback_query_id': callback_query_id
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ Failed to answer callback: {e}")
        return False

@app.route('/')
def home():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{BOT_NAME}</title>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }}
            .logo {{ font-size: 24px; text-align: center; margin: 20px 0; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 15px; color: #333; box-shadow: 0 10px 30px rgba(0,0,0,0.3); }}
            .success {{ color: #28a745; font-weight: bold; }}
            .error {{ color: #dc3545; }}
            .nav {{ margin: 20px 0; }}
            .nav a {{ display: inline-block; margin: 5px; padding: 10px 15px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; }}
            .stats {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">
                <h1>🏛️⚖️🤖</h1>
                <h1>{BOT_NAME}</h1>
                <p><em>الذكاء الاصطناعي في خدمة القانون</em></p>
            </div>
            
            <div class="success">
                <h2>✅ البوت القانوني يعمل!</h2>
            </div>
            
            <p><strong>🕒 الوقت:</strong> {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <div class="nav">
                <strong>🔗 الروابط السريعة:</strong><br>
                <a href="/status">حالة النظام</a>
                <a href="/set_webhook">تعيين Webhook</a>
                <a href="/test">اختبار الإرسال</a>
            </div>
            
            <div class="stats">
                <strong>📊 إحصائيات النظام:</strong>
                <ul>
                    <li>👥 المستخدمون: {len(users_db)}</li>
                    <li>⏳ بانتظار الموافقة: {sum(1 for u in users_db.values() if u.get('status') == 'pending')}</li>
                    <li>✅ مستخدمون نشطون: {sum(1 for u in users_db.values() if u.get('approved'))}</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/status')
def status():
    """حالة النظام"""
    try:
        status_info = {
            "status": "✅ يعمل",
            "bot_name": BOT_NAME,
            "app_url": APP_URL,
            "server_time": time.strftime('%Y-%m-%d %H:%M:%S'),
            "users_count": len(users_db),
            "pending_approvals": sum(1 for u in users_db.values() if u.get('status') == 'pending'),
            "approved_users": sum(1 for u in users_db.values() if u.get('approved')),
            "banned_users": sum(1 for u in users_db.values() if u.get('banned'))
        }
        return jsonify(status_info)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/set_webhook')
def set_webhook():
    """تعيين webhook"""
    try:
        webhook_url = f"{APP_URL}/webhook"
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        
        response = requests.post(url, json={'url': webhook_url})
        
        if response.status_code == 200:
            return f"""
            <div class="container">
                <h1 class="success">✅ تم تعيين Webhook!</h1>
                <p><strong>الرابط:</strong> {webhook_url}</p>
                <p><strong>الرد:</strong> {response.text}</p>
                <div class="nav"><a href="/">← العودة للصفحة الرئيسية</a></div>
            </div>
            """
        else:
            return f"""
            <div class="container">
                <h1 class="error">❌ فشل تعيين Webhook</h1>
                <p><strong>الخطأ:</strong> {response.text}</p>
                <div class="nav"><a href="/">← العودة للصفحة الرئيسية</a></div>
            </div>
            """
    except Exception as e:
        return f"""
        <div class="container">
            <h1 class="error">❌ خطأ</h1>
            <p><strong>التفاصيل:</strong> {str(e)}</p>
            <div class="nav"><a href="/">← العودة للصفحة الرئيسية</a></div>
        </div>
        """

@app.route('/test')
def test():
    """اختبار إرسال رسالة"""
    try:
        if MANAGER_CHAT_ID:
            # إرسال رسالة اختبارية مع الشعار
            test_message = f"""
{BOT_LOGO}
🧪 *اختبار النظام*

هذه رسالة اختبارية للتأكد من عمل البوت
✅ *الحالة:* النظام يعمل بشكل مثالي
🕒 *الوقت:* {time.strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            response = requests.post(url, json={
                'chat_id': MANAGER_CHAT_ID,
                'text': test_message,
                'parse_mode': 'Markdown'
            })
            
            if response.status_code == 200:
                return """
                <div class="container">
                    <h1 class="success">✅ تم إرسال رسالة الاختبار</h1>
                    <p>تم إرسال رسالة اختبارية للمدير مع شعار البوت</p>
                    <div class="nav"><a href="/">← العودة للصفحة الرئيسية</a></div>
                </div>
                """
            else:
                return f"""
                <div class="container">
                    <h1 class="error">❌ فشل الإرسال</h1>
                    <p><strong>الخطأ:</strong> {response.text}</p>
                    <div class="nav"><a href="/">← العودة للصفحة الرئيسية</a></div>
                </div>
                """
        else:
            return """
            <div class="container">
                <h1 class="error">❌ MANAGER_CHAT_ID غير مضبوط</h1>
                <div class="nav"><a href="/">← العودة للصفحة الرئيسية</a></div>
            </div>
            """
    except Exception as e:
        return f"""
        <div class="container">
            <h1 class="error">❌ خطأ</h1>
            <p><strong>التفاصيل:</strong> {str(e)}</p>
            <div class="nav"><a href="/">← العودة للصفحة الرئيسية</a></div>
        </div>
        """

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    """Webhook للتليجرام"""
    if request.method == 'GET':
        return f"🟢 {BOT_NAME} - Webhook جاهز لاستقبال البيانات"
    
    try:
        data = request.get_json()
        logger.info("📩 بيانات واردة من التليجرام")
        
        if 'message' in data:
            handle_message(data['message'])
        elif 'callback_query' in data:
            handle_callback(data['callback_query'])
            
    except Exception as e:
        logger.error(f"❌ خطأ في webhook: {e}")
    
    return 'OK'

def handle_message(message):
    """معالجة الرسائل النصية"""
    chat_id = message['chat']['id']
    text = message.get('text', '')
    user = message['from']
    user_id = user['id']
    
    logger.info(f"💬 Message from {user_id}: {text}")
    
    if text == '/start':
        handle_start_command(user, chat_id)
    elif text == '/logo':
        # أمر جديد لعرض الشعار
        send_telegram_message(chat_id, BOT_LOGO)
    elif text and not text.startswith('/'):
        handle_user_text(user_id, chat_id, text)

def handle_start_command(user, chat_id):
    """معالجة أمر /start مع الشعار"""
    user_id = user['id']
    
    # التحقق إذا كان محظوراً
    if users_db.get(user_id, {}).get('banned'):
        send_telegram_message(chat_id, "❌ تم حظرك من استخدام البوت.")
        return
        
    # إذا لم يكن معتمداً بعد
    if user_id not in users_db or not users_db[user_id].get('approved'):
        # إنشاء أزرار الموافقة
        keyboard = {
            'inline_keyboard': [[
                {'text': '✅ قبول المستخدم', 'callback_data': f'approve_{user_id}'},
                {'text': '❌ رفض المستخدم', 'callback_data': f'reject_{user_id}'}
            ]]
        }
        
        # إرسال طلب للمدير مع الشعار
        request_message = f"""
{BOT_LOGO}
🆕 *طلب انضمام جديد*

👤 *المستخدم:* {user['first_name']}
📛 *Username:* @{user.get('username', 'غير متوفر')}
🆔 *ID:* {user_id}

⚖️ *اختر الإجراء المناسب:*
        """
        
        send_telegram_message(MANAGER_CHAT_ID, request_message, keyboard)
        
        users_db[user_id] = {
            'first_name': user['first_name'],
            'username': user.get('username'),
            'status': 'pending',
            'chat_id': chat_id
        }
        
        # إرسال رسالة ترحيب للمستخدم مع الشعار
        welcome_message = f"""
{BOT_LOGO}
🎯 *مرحباً بك في {BOT_NAME}*

⏳ *حالة طلبك:* تم إرسال طلب الانضمام للإدارة
✅ *سيتم إعلامك* فور الموافقة على طلبك

⚖️ *نحن هنا لخدمتك قانونياً*
        """
        
        send_telegram_message(chat_id, welcome_message)
        
    else:
        show_main_menu(chat_id)

def show_main_menu(chat_id):
    """عرض القائمة الرئيسية مع الشعار"""
    keyboard = {
        'inline_keyboard': [
            [
                {'text': '📞 استشارة فورية', 'callback_data': 'consult'},
                {'text': '⚖️ خدمات قانونية', 'callback_data': 'services'}
            ],
            [
                {'text': '❓ الأسئلة الشائعة', 'callback_data': 'faq'},
                {'text': '💰 التكاليف', 'callback_data': 'pricing'}
            ],
            [
                {'text': '🏢 عن المكتب', 'callback_data': 'about'},
                {'text': '📞 اتصل بنا', 'callback_data': 'contact'}
            ],
            [
                {'text': '📝 حجز موعد', 'callback_data': 'appointment'},
                {'text': '🔒 الخصوصية', 'callback_data': 'privacy'}
            ],
            [
                {'text': '🆘 مساعدة عاجلة', 'callback_data': 'emergency'},
                {'text': '📋 الشروط', 'callback_data': 'terms'}
            ]
        ]
    }
    
    menu_message = f"""
{BOT_LOGO}
🎯 *مرحباً بك في القائمة الرئيسية*

🤖 *{BOT_NAME}* - الذكاء الاصطناعي في خدمة القانون

📋 *اختر من القائمة أدناه:*

• 📞 *استشارة فورية* - للحصول على إجابة سريعة
• ⚖️ *خدمات قانونية* - تعرف على كافة خدماتنا  
• ❓ *الأسئلة الشائعة* - إجابات على أكثر الاستفسارات شيوعاً
• 💰 *التكاليف* - معرفة الرسوم والتكاليف
• 🏢 *عن المكتب* - تعرف على فريقنا
• 📞 *اتصل بنا* - طرق التواصل المباشر
• 📝 *حجز موعد* - ترتيب جلسة استشارية
• 🔒 *الخصوصية* - سياسة الخصوصية والأمان
• 🆘 *مساعدة عاجلة* - للحالات الطارئة
• 📋 *الشروط* - الشروط والأحكام

⚖️ *اختر الخدمة التي تناسب احتياجك:*
    """
    
    send_telegram_message(chat_id, menu_message, keyboard)

# باقي الدوال (handle_callback, handle_faq, handle_pricing, etc.) تبقى كما هي
# ... [يتبع نفس الدوال السابقة بدون تغيير]

def handle_callback(callback_query):
    """معالجة ضغطات الأزرار المحسنة"""
    data = callback_query['data']
    user_id = callback_query['from']['id']
    message_id = callback_query['message']['message_id']
    chat_id = callback_query['message']['chat']['id']
    
    answer_callback_query(callback_query['id'])
    
    try:
        if data.startswith('approve_'):
            target_user_id = int(data.split('_')[1])
            users_db[target_user_id] = {'approved': True, 'warnings': 0}
            
            user_chat_id = users_db.get(target_user_id, {}).get('chat_id', target_user_id)
            
            # رسالة القبول مع الشعار
            approval_message = f"""
{BOT_LOGO}
🎉 *تهانينا! تم قبول طلبك*

✅ *مرحباً بك رسمياً في {BOT_NAME}*

⚖️ *يمكنك الآن:*
• استخدام كافة خدمات البوت القانوني
• الحصول على استشارات قانونية متخصصة
• التواصل مع محامين متخصصين

🎯 *اكتب /start لرؤية القائمة الرئيسية*
            """
            
            send_telegram_message(user_chat_id, approval_message)
            edit_message_text(chat_id, message_id, f"✅ تم قبول المستخدم {target_user_id}")
            
        elif data.startswith('reject_'):
            target_user_id = int(data.split('_')[1])
            users_db[target_user_id] = {'banned': True}
            
            user_chat_id = users_db.get(target_user_id, {}).get('chat_id', target_user_id)
            send_telegram_message(user_chat_id, "❌ تم رفض طلبك")
            edit_message_text(chat_id, message_id, f"❌ تم رفض المستخدم {target_user_id}")
            
        elif data == "consult":
            consult_message = f"""
{BOT_LOGO}
📞 *الاستشارة القانونية الفورية*

🤖 *{BOT_NAME}* - مستعد لمساعدتك

يمكنك الآن وصف مشكلتك القانونية بالتفصيل، وسيقوم أحد محامينا المتخصصين بالرد عليك في أقرب وقت.

📋 *يرجى تضمين:*
• نوع القضية أو المشكلة
• الأطراف المتضمنة  
• التسلسل الزمني للأحداث
• أي مستندات متوفرة لديك

⚖️ *ملاحظة:* جميع استشاراتك محمية بسرية تامة

⬇️ *اكتب رسالتك الآن...*
            """
            edit_message_text(chat_id, message_id, consult_message)
            
        elif data == "services":
            services_message = f"""
{BOT_LOGO}
⚖️ *خدماتنا القانونية المتكاملة*

🏛️ *{BOT_NAME}* - نقدم لك:

*📝 صياغة العقود:*
• عقود العمل والخدمات
• عقود الشركات والمشاريع
• عقود البيع والشراء
• عقود الإيجار والتمويل

*🏛️ المرافعات القضائية:*
• الدفاع في القضايا الجنائية
• القضايا التجارية والمالية
• قضايا الأحوال الشخصية
• المنازعات العقارية

*💼 الاستشارات المتخصصة:*
• استشارات شركات وأعمال
• استشارات عقارية
• استشارات ضريبية وجمركية
• استشارات ملكية فكرية

*📄 التوثيق والتصديق:*
• توثيق العقود والاتفاقيات
• تصديق المستندات الرسمية
• التوثيق لدى الجهات الحكومية

🎯 *اختر '📞 استشارة فورية' لبدء الخدمة المناسبة لك*
            """
            edit_message_text(chat_id, message_id, services_message)
            
        # ... [بقية الدوال تبقى كما هي]
        elif data == "about":
            handle_about(chat_id, message_id)
        elif data == "faq":
            handle_faq(chat_id, message_id)
        elif data == "pricing":
            handle_pricing(chat_id, message_id)
        elif data == "contact":
            handle_contact(chat_id, message_id)
        elif data == "appointment":
            handle_appointment(chat_id, message_id)
        elif data == "emergency":
            handle_emergency(chat_id, message_id)
        elif data == "privacy":
            handle_privacy(chat_id, message_id)
        elif data == "terms":
            handle_terms(chat_id, message_id)
            
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الزر: {e}")

def handle_about(chat_id, message_id):
    """عرض معلومات عن البوت مع الشعار"""
    about_text = f"""
{BOT_LOGO}
🏢 *عن {BOT_NAME}*

🤖 *رؤيتنا:* أن نكون الخيار الأول للخدمات القانونية الذكية

🎯 *رسالتنا:* تقديم حلول قانونية مبتكرة تلبي احتياجات عملائنا باستخدام أحدث تقنيات الذكاء الاصطناعي

⚖️ *فريقنا:*
• محامون متخصصون في كافة المجالات
• خبرة تزيد عن 15 عاماً
• متابعة مستمرة للقضايا
• استخدام أحدث التقنيات

🏛️ *قيمنا:*
• الاحترافية والشفافية
• السرية والأمان
• الابتكار والتطوير
• خدمة العملاء

📞 للتواصل المباشر:
الهاتف: +966123456789
البريد: info@lawfirm.com

🕐 أوقات العمل:
من الأحد إلى الخميس
8:00 ص - 6:00 م
    """
    edit_message_text(chat_id, message_id, about_text)

# ... [بقية الدوال المساعدة تبقى كما هي]

def handle_user_text(user_id, chat_id, text):
    """معالجة الرسائل النصية من المستخدمين"""
    if user_id not in users_db or not users_db[user_id].get('approved'):
        send_telegram_message(chat_id, "⏳ لا يمكنك استخدام البوت حتى يتم الموافقة على طلبك.")
        return
    
    # فحص المحتوى المحظور
    forbidden_words = ["http://", "https://", ".com", ".org", "سب", "شتم", "قذف", "شتيمة"]
    for word in forbidden_words:
        if word in text.lower():
            if user_id not in user_warnings:
                user_warnings[user_id] = 0
            user_warnings[user_id] += 1
            
            warnings = user_warnings[user_id]
            
            if warnings >= 3:
                users_db[user_id]['banned'] = True
                send_telegram_message(chat_id, "❌ تم حظرك من البوت due to repeated violations.")
                send_telegram_message(MANAGER_CHAT_ID, f"🚨 تم حظر المستخدم {user_id}\nالسبب: repeated violations")
                return
            else:
                send_telegram_message(chat_id, f"⚠️ تحذير ({warnings}/3): يمنع مشاركة روابط أو كلمات غير لائقة")
                send_telegram_message(MANAGER_CHAT_ID, f"⚠️ مخالفة من المستخدم {user_id}\nالتحذيرات: {warnings}/3")
                return
    
    # إذا كانت الرسالة نظيفة
    confirmation_message = f"""
{BOT_LOGO}
✅ *تم استلام رسالتك بنجاح*

📨 *تفاصيل الرسالة:*
{text[:100]}...

⚖️ *الحالة:* سيقوم أحد محامينا المتخصصين بالرد عليك في أقرب وقت ممكن

🕒 *الوقت المتوقع للرد:* 2-4 ساعات عمل

🤝 *شكراً لثقتك بـ {BOT_NAME}*
    """
    
    send_telegram_message(chat_id, confirmation_message)

if __name__ == '__main__':
    keep_alive()
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 بدء تشغيل {BOT_NAME} على المنفذ {port}")
    logger.info(f"🌐 عنوان التطبيق: {APP_URL}")
    app.run(host='0.0.0.0', port=port, debug=False)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = "YOUR_TOKEN"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("قبول ✅", callback_data="accept"),
            InlineKeyboardButton("رفض ❌", callback_data="reject"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("تم انضمام مستخدم جديد، هل تقبله؟", reply_markup=reply_markup)

async def handle_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # ضروري لتأكيد الضغط

    if query.data == "accept":
        await query.edit_message_text("✅ تم قبول المستخدم بنجاح.")
    elif query.data == "reject":
        await query.edit_message_text("❌ تم رفض المستخدم.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_decision))
    app.run_polling()

if __name__ == "__main__":
    main()
