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
            time.sleep(240)  # كل 4 دقائق
    
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
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>البوت القانوني</title>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .success { color: green; }
            .error { color: red; }
        </style>
    </head>
    <body>
        <h1 class="success">✅ البوت القانوني يعمل!</h1>
        <p><strong>🕒 الوقت:</strong> {}</p>
        <p><strong>🔗 الروابط:</strong></p>
        <ul>
            <li><a href="/status">حالة النظام</a></li>
            <li><a href="/set_webhook">تعيين Webhook</a></li>
            <li><a href="/test">اختبار الإرسال</a></li>
        </ul>
        <p><strong>📊 الإحصائيات:</strong></p>
        <ul>
            <li>👥 المستخدمون: {}</li>
            <li>⏳ بانتظار الموافقة: {}</li>
        </ul>
    </body>
    </html>
    """.format(
        time.strftime('%Y-%m-%d %H:%M:%S'),
        len(users_db),
        sum(1 for u in users_db.values() if u.get('status') == 'pending')
    )

@app.route('/status')
def status():
    """حالة النظام - مبسط"""
    try:
        status_info = {
            "status": "✅ يعمل",
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
    """تعيين webhook - مبسط"""
    try:
        webhook_url = f"{APP_URL}/webhook"
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        
        response = requests.post(url, json={'url': webhook_url})
        
        if response.status_code == 200:
            return f"""
            <h1 class="success">✅ تم تعيين Webhook!</h1>
            <p><strong>الرابط:</strong> {webhook_url}</p>
            <p><strong>الرد:</strong> {response.text}</p>
            <a href="/">← العودة</a>
            """
        else:
            return f"""
            <h1 class="error">❌ فشل تعيين Webhook</h1>
            <p><strong>الخطأ:</strong> {response.text}</p>
            <a href="/">← العودة</a>
            """
    except Exception as e:
        return f"""
        <h1 class="error">❌ خطأ</h1>
        <p><strong>التفاصيل:</strong> {str(e)}</p>
        <a href="/">← العودة</a>
        """

@app.route('/test')
def test():
    """اختبار إرسال رسالة"""
    try:
        if MANAGER_CHAT_ID:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            response = requests.post(url, json={
                'chat_id': MANAGER_CHAT_ID,
                'text': '🧪 اختبار: البوت يعمل بنجاح!'
            })
            
            if response.status_code == 200:
                return "<h1 class='success'>✅ تم إرسال رسالة الاختبار</h1><a href='/'>← العودة</a>"
            else:
                return f"<h1 class='error'>❌ فشل الإرسال: {response.text}</h1><a href='/'>← العودة</a>"
        else:
            return "<h1 class='error'>❌ MANAGER_CHAT_ID غير مضبوط</h1><a href='/'>← العودة</a>"
    except Exception as e:
        return f"<h1 class='error'>❌ خطأ: {str(e)}</h1><a href='/'>← العودة</a>"

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    """Webhook للتليجرام"""
    if request.method == 'GET':
        return "🟢 Webhook جاهز - POST فقط لبيانات التليجرام"
    
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
    elif text and not text.startswith('/'):
        handle_user_text(user_id, chat_id, text)

def handle_start_command(user, chat_id):
    """معالجة أمر /start"""
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
        
        send_telegram_message(
            MANAGER_CHAT_ID,
            f"🆕 طلب انضمام جديد:\n👤 {user['first_name']}\n🆔 {user_id}",
            keyboard
        )
        
        users_db[user_id] = {
            'first_name': user['first_name'],
            'username': user.get('username'),
            'status': 'pending',
            'chat_id': chat_id
        }
        
        send_telegram_message(chat_id, "⏳ تم إرسال طلبك للمدير. انتظر الموافقة.")
        
    else:
        show_main_menu(chat_id)

def show_main_menu(chat_id):
    """عرض القائمة الرئيسية المحسنة"""
    keyboard = {
        'inline_keyboard': [
            # الصف الأول: الخدمات الأساسية
            [
                {'text': '📞 استشارة فورية', 'callback_data': 'consult'},
                {'text': '⚖️ خدمات قانونية', 'callback_data': 'services'}
            ],
            # الصف الثاني: معلومات وإجراءات
            [
                {'text': '❓ الأسئلة الشائعة', 'callback_data': 'faq'},
                {'text': '💰 التكاليف', 'callback_data': 'pricing'}
            ],
            # الصف الثالث: معلومات الاتصال
            [
                {'text': '🏢 عن المكتب', 'callback_data': 'about'},
                {'text': '📞 اتصل بنا', 'callback_data': 'contact'}
            ],
            # الصف الرابع: إضافات مهمة
            [
                {'text': '📝 حجز موعد', 'callback_data': 'appointment'},
                {'text': '🔒 الخصوصية', 'callback_data': 'privacy'}
            ],
            # الصف الخامس: المساعدة
            [
                {'text': '🆘 مساعدة عاجلة', 'callback_data': 'emergency'},
                {'text': '📋 الشروط', 'callback_data': 'terms'}
            ]
        ]
    }
    
    message_text = """
👋 أهلاً وسهلاً بك في *البوت القانوني المتخصص*

🎯 *اختر من القائمة أدناه:*

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

*اختر الخدمة التي تناسب احتياجك:*
"""
    
    send_telegram_message(chat_id, message_text, keyboard)

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
            send_telegram_message(user_chat_id, "🎉 تم قبولك! اكتب /start")
            edit_message_text(chat_id, message_id, f"✅ تم قبول {target_user_id}")
            
        elif data.startswith('reject_'):
            target_user_id = int(data.split('_')[1])
            users_db[target_user_id] = {'banned': True}
            
            user_chat_id = users_db.get(target_user_id, {}).get('chat_id', target_user_id)
            send_telegram_message(user_chat_id, "❌ تم رفض طلبك")
            edit_message_text(chat_id, message_id, f"❌ تم رفض {target_user_id}")
            
        elif data == "consult":
            edit_message_text(
                chat_id,
                message_id,
                "📞 *الاستشارة الفورية*\n\nيمكنك الآن وصف مشكلتك القانونية بالتفصيل، وسيقوم أحد محامينا المتخصصين بالرد عليك في أقرب وقت.\n\nيرجى تضمين:\n• نوع القضية أو المشكلة\n• الأطراف المتضمنة\n• التسلسل الزمني للأحداث\n• أي مستندات متوفرة لديك\n\n⬇️ *اكتب رسالتك الآن...*"
            )
            
        elif data == "services":
            edit_message_text(
                chat_id,
                message_id,
                "⚖️ *خدماتنا القانونية المتكاملة*\n\n*📝 صياغة العقود:*\n• عقود العمل والخدمات\n• عقود الشركات والمشاريع\n• عقود البيع والشراء\n• عقود الإيجار والتمويل\n\n*🏛️ المرافعات القضائية:*\n• الدفاع في القضايا الجنائية\n• القضايا التجارية والمالية\n• قضايا الأحوال الشخصية\n• المنازعات العقارية\n\n*💼 الاستشارات المتخصصة:*\n• استشارات شركات وأعمال\n• استشارات عقارية\n• استشارات ضريبية وجمركية\n• استشارات ملكية فكرية\n\n*📄 التوثيق والتصديق:*\n• توثيق العقود والاتفاقيات\n• تصديق المستندات الرسمية\n• التوثيق لدى الجهات الحكومية\n\nاختر '📞 استشارة فورية' لبدء الخدمة المناسبة لك."
            )
            
        elif data == "about":
            edit_message_text(
                chat_id,
                message_id,
                "🏢 *عن المكتب والمحامين*\n\nنحن فريق من المحامين المتخصصين في مختلف المجالات القانونية، نقدم خدماتنا باحترافية وشفافية.\n\n*رؤيتنا:* أن نكون الخيار الأول للخدمات القانونية.\n\n*رسالتنا:* تقديم حلول قانونية مبتكرة تلبي احتياجات عملائنا.\n\n*فريقنا:*\n• محامون متخصصون في كافة المجالات\n• خبرة تزيد عن 15 عاماً\n• متابعة مستمرة للقضايا\n\n📞 للتواصل المباشر:\nالهاتف: +966123456789\nالبريد: info@lawfirm.com\n\n🕐 أوقات العمل:\nمن الأحد إلى الخميس\n8:00 ص - 6:00 م"
            )
            
        elif data == "appointment":
            edit_message_text(
                chat_id,
                message_id,
                "📝 *حجز موعد استشارة*\n\nلحجز موعد مع محامٍ متخصص، يرجى:\n\n📞 *الاتصال على:* +966123456789\n📧 *المراسلة على:* appointments@lawfirm.com\n\n*أو يمكنك إرسال:*\n• الاسم الكامل\n• نوع الاستشارة\n• التاريخ والوقت المناسب\n• طريقة التواصل المفضلة\n\n*بعد الحجز:*\n• سنرسل لك تأكيد الحجز\n• تذكير قبل الموعد بيوم\n• مرونة في تغيير الموعد\n\n*المواعيد المتاحة:*\n• الأحد - الخميس: 8:00 ص - 6:00 م\n• الجلسات عن بُعد متاحة\n\nوسنتواصل معك لتأكيد الموعد."
            )
            
        elif data == "faq":
            handle_faq(chat_id, message_id)
            
        elif data == "pricing":
            handle_pricing(chat_id, message_id)
            
        elif data == "contact":
            handle_contact(chat_id, message_id)
            
        elif data == "emergency":
            handle_emergency(chat_id, message_id)
            
        elif data == "privacy":
            handle_privacy(chat_id, message_id)
            
        elif data == "terms":
            handle_terms(chat_id, message_id)
            
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الزر: {e}")

def handle_faq(chat_id, message_id):
    """عرض الأسئلة الشائعة"""
    faq_text = """
❓ *الأسئلة الشائعة*

*Q1: ما هي مدة الاستشارة؟*
• الاستشارة الأولية تستغرق عادة 15-30 دقيقة

*Q2: كيف يتم تحديد التكلفة؟*
• حسب نوع الخدمة وتعقيد القضية

*Q3: هل الاستشارة الأولية مجانية؟*
• نعم، الاستشارة الأولية مجانية

*Q4: ما هي أوقات العمل؟*
• الأحد - الخميس: 8:00 ص - 6:00 م

*Q5: كيف أستلم المستندات؟*
• يتم إرسالها عبر البريد الإلكتروني أو الواتساب

*Q6: هل تتعاملون مع القضايا العاجلة؟*
• نعم، لدينا خدمة الطوارئ للقضايا العاجلة

للاستفسارات الأخرى، اختر '📞 استشارة فورية'
"""
    edit_message_text(chat_id, message_id, faq_text)

def handle_pricing(chat_id, message_id):
    """عرض التكاليف والرسوم"""
    pricing_text = """
💰 *التكاليف والرسوم*

*الاستشارات:*
• 📞 استشارة أولية: *مجانية*
• 💼 استشارة مفصلة: 200 - 500 ريال
• 🏛️ استشارة متخصصة: 500 - 1000 ريال

*صياغة المستندات:*
• 📝 عقد بسيط: 300 - 800 ريال
• 📄 عقد متقدم: 800 - 2000 ريال
• 🏠 عقود عقارية: 1000 - 3000 ريال

*المرافعات:*
• ⚖️ قضية بسيطة: 2000 - 5000 ريال
• 🔥 قضية متوسطة: 5000 - 15000 ريال
• 🚨 قضية معقدة: 15000+ ريال

*ملاحظة:* 
- الأسعار تختلف حسب تعقيد القضية
- الدفع بعد الاتفاق على الخدمة
- تقسيط متاح للقضايا الكبيرة

للحصول على سعر دقيق، اختر '📞 استشارة فورية'
"""
    edit_message_text(chat_id, message_id, pricing_text)

def handle_contact(chat_id, message_id):
    """عرض معلومات الاتصال"""
    contact_text = """
📞 *طرق التواصل معنا*

*للتواصل المباشر:*
• 📞 الهاتف: `+966 12 345 6789`
• 📧 البريد: `info@lawfirm.com`
• 🌐 الموقع: `www.lawfirm.com`

*وسائل التواصل الاجتماعي:*
• 📱 واتساب: `+966 12 345 6789`
• 💼 لينكد إن: `LawFirmKSA`
• 📸 إنستغرام: `@LawFirmKSA`

*العنوان:*
• 🏢 المملكة العربية السعودية
• 📍 الرياض - حي العليا
• 🗺️ شارع الملك فهد

*أوقات العمل:*
• ⏰ الأحد - الخميس: 8:00 ص - 6:00 م
• 🕛 الجمعة - السبت: إجازة

*للحالات الطارئة خارج أوقات العمل:*
• 🆘 هاتف الطوارئ: `+966 50 123 4567`

نحن هنا لخدمتك على مدار الساعة!
"""
    edit_message_text(chat_id, message_id, contact_text)

def handle_emergency(chat_id, message_id):
    """عرض مساعدة الطوارئ"""
    emergency_text = """
🆘 *مساعدة عاجلة*

*للحالات الطارئة:*

📞 *اتصل فوراً على:*
• هاتف الطوارئ: `+966 50 123 4567`
• الهاتف الرئيسي: `+966 12 345 6789`

*الحالات التي نتعامل معها عاجلاً:*
• 🚨 اعتقال أو توقيف
• ⚖️ قضايا جنائية عاجلة
• 🏠 إخلاء أو طرد
• 💼 تجميد أموال أو حسابات
• 📄 استدعاء قضائي مفاجئ

*ما يجب فعله في الحالات الطارئة:*
1. ✅ احتفظ بجميع المستندات
2. ✅ سجل جميع التفاصيل
3. ✅ لا توقع على أي أوراق قبل استشارتنا
4. ✅ تواصل معنا فوراً

*خدمة 24/7:*
نقدم خدمة الطوارئ على مدار الساعة طوال أيام الأسبوع للحالات العاجلة.

*اتصل بنا الآن للاستشارة العاجلة!*
"""
    edit_message_text(chat_id, message_id, emergency_text)

def handle_privacy(chat_id, message_id):
    """عرض سياسة الخصوصية"""
    privacy_text = """
🔒 *سياسة الخصوصية والأمان*

*حماية بياناتك:*
• 🔐 جميع محادثاتك مشفرة وآمنة
• 📁 ملفاتك محفوظة بسرية تامة
• 👥 لا نشارك بياناتك مع أي طرف ثالث

*مبدأ السرية:*
• جميع المحامين ملتزمون بمبدأ السرية المهنية
• معلوماتك محمية بموجب النظام
• نلتزم بأعلى معايير الأمان

*حقوقك:*
•你有权利 الاطلاع على بياناتك
• لك الحق في طلب حذف بياناتك
• يمكنك سحب الموافقة في أي وقت

*التخزين:*
• يتم تخزين البيانات على خوادم آمنة
• فترة الاحتفاظ: 5 سنوات حسب النظام
• يتم التدمير الآمن بعد انتهاء المدة

نحن نحرص على حماية خصوصيتك وأمان بياناتك.
"""
    edit_message_text(chat_id, message_id, privacy_text)

def handle_terms(chat_id, message_id):
    """عرض الشروط والأحكام"""
    terms_text = """
📋 *الشروط والأحكام*

*شروط استخدام الخدمة:*
• ✅ يجب أن تكون المعلومات المقدمة صحيحة
• ✅ الالتزام بمواعيد الجلسات
• ✅ دفع الرسوم المتفق عليها

*التزاماتنا:*
• نقدم الاستشارات بدقة واحترافية
• نحافظ على سرية معلوماتك
• نلتزم بالمواعيد المتفق عليها

*مسؤوليات العميل:*
• تقديم المعلومات الصحيحة والكاملة
• الالتزام بالدفعات المتفق عليها
• إبلاغنا بأي تغييرات مهمة

*إخلاء المسؤولية:*
• الاستشارات لا تغني عن المراجعة الكاملة
• النتائج تختلف حسب ظروف كل قضية
• نعمل ضمن الإطار القانوني

*الدفع والمقابل:*
• الدفع بعد الاتفاق على الخدمة
• تقسيط متاح للقضايا الكبيرة
• لا استرداد للرسوم بعد تقديم الخدمة

بالاستمرار في استخدام الخدمة، فإنك توافق على هذه الشروط.
"""
    edit_message_text(chat_id, message_id, terms_text)

def handle_user_text(user_id, chat_id, text):
    """معالجة الرسائل النصية من المستخدمين"""
    # التحقق من صلاحية المستخدم
    if user_id not in users_db or not users_db[user_id].get('approved'):
        send_telegram_message(chat_id, "⏳ لا يمكنك استخدام البوت حتى يتم الموافقة على طلبك.")
        return
    
    # فحص المحتوى المحظور
    forbidden_words = ["http://", "https://", ".com", ".org", "سب", "شتم", "قذف", "شتيمة"]
    for word in forbidden_words:
        if word in text.lower():
            # زيادة التحذيرات
            if user_id not in user_warnings:
                user_warnings[user_id] = 0
            user_warnings[user_id] += 1
            
            warnings = user_warnings[user_id]
            
            if warnings >= 3:
                # حظر المستخدم
                users_db[user_id]['banned'] = True
                send_telegram_message(chat_id, "❌ تم حظرك من البوت due to repeated violations.")
                
                # إشعار المدير
                send_telegram_message(
                    MANAGER_CHAT_ID,
                    f"🚨 تم حظر المستخدم {user_id}\nالسبب: repeated violations\nآخر رسالة: {text[:100]}..."
                )
                return
            else:
                send_telegram_message(
                    chat_id,
                    f"⚠️ تحذير ({warnings}/3): يمنع مشاركة روابط أو كلمات غير لائقة.\nالتكرار يؤدي إلى الحظر الدائم."
                )
                
                # إشعار المدير
                send_telegram_message(
                    MANAGER_CHAT_ID,
                    f"⚠️ مخالفة من المستخدم {user_id}\nالتحذيرات: {warnings}/3\nالرسالة: {text[:200]}..."
                )
                return
    
    # إذا كانت الرسالة نظيفة
    send_telegram_message(
        chat_id,
        "✅ تم استلام رسالتك بنجاح.\n\nسيقوم أحد محامينا المتخصصين بالرد عليك في أقرب وقت ممكن.\n\nشكراً لثقتك بمكتبنا القانوني."
    )

if __name__ == '__main__':
    # بدء نظام keep-alive
    keep_alive()
    
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 بدء تشغيل البوت على المنفذ {port}")
    logger.info(f"🌐 عنوان التطبيق: {APP_URL}")
    app.run(host='0.0.0.0', port=port, debug=False)
