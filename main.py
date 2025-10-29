import os
import logging
from flask import Flask, request, jsonify
import requests
import json

# الإعدادات
BOT_TOKEN = os.getenv('BOT_TOKEN')
MANAGER_CHAT_ID = os.getenv('MANAGER_CHAT_ID')
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)

# تخزين البيانات
users_db = {}
user_warnings = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def send_telegram_message(chat_id, text, reply_markup=None):
    """إرسال رسالة عبر Telegram API مباشرة"""
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text
    }
    
    if reply_markup:
        payload['reply_markup'] = json.dumps(reply_markup)
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        return False

def edit_telegram_message(chat_id, message_id, text):
    """تعديل رسالة موجودة"""
    url = f"{TELEGRAM_API}/editMessageText"
    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to edit message: {e}")
        return False

def answer_callback_query(callback_query_id):
    """الرد على callback query"""
    url = f"{TELEGRAM_API}/answerCallbackQuery"
    payload = {
        'callback_query_id': callback_query_id
    }
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to answer callback: {e}")
        return False

@app.route('/')
def index():
    return "✅ البوت القانوني يعمل بنظام Webhook المباشر!"

@app.route('/webhook', methods=['POST'])
def webhook():
    """معالجة webhook من التليجرام"""
    try:
        data = request.get_json()
        logger.info(f"Received update: {data}")
        
        if 'message' in data:
            handle_message(data['message'])
        elif 'callback_query' in data:
            handle_callback(data['callback_query'])
            
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
    
    return 'OK'

def handle_message(message):
    """معالجة الرسائل النصية"""
    chat_id = message['chat']['id']
    text = message.get('text', '')
    user = message['from']
    user_id = user['id']
    
    logger.info(f"Message from {user_id}: {text}")
    
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
                {
                    'text': '✅ قبول المستخدم',
                    'callback_data': f'approve_{user_id}'
                },
                {
                    'text': '❌ رفض المستخدم', 
                    'callback_data': f'reject_{user_id}'
                }
            ]]
        }
        
        # إرسال طلب للمدير
        send_telegram_message(
            MANAGER_CHAT_ID,
            f"🆕 طلب انضمام جديد:\n\n"
            f"👤 المستخدم: {user['first_name']}\n"
            f"📛 username: @{user.get('username', 'غير متوفر')}\n"
            f"🆔 ID: {user_id}\n\n"
            f"اختر الإجراء المناسب:",
            keyboard
        )
        
        # حفظ بيانات المستخدم
        users_db[user_id] = {
            'first_name': user['first_name'],
            'username': user.get('username'),
            'status': 'pending',
            'chat_id': chat_id
        }
        
        send_telegram_message(chat_id, "⏳ تم إرسال طلب الانضمام للإدارة.\nسيتم إعلامك عند الموافقة.")
        
    else:
        # إذا كان معتمداً، عرض القائمة
        show_main_menu(chat_id)

def show_main_menu(chat_id):
    """عرض القائمة الرئيسية"""
    keyboard = {
        'inline_keyboard': [
            [{'text': '📞 استشارة فورية', 'callback_data': 'consult'}],
            [{'text': '⚖️ خدمات قانونية', 'callback_data': 'services'}],
            [{'text': 'ℹ️ معلومات', 'callback_data': 'about'}],
            [{'text': '📝 حجز موعد', 'callback_data': 'appointment'}]
        ]
    }
    
    send_telegram_message(
        chat_id,
        "👋 أهلاً وسهلاً بك في البوت القانوني المتخصص\n\nاختر الخدمة التي تناسب احتياجك:",
        keyboard
    )

def handle_callback(callback_query):
    """معالجة ضغطات الأزرار"""
    data = callback_query['data']
    user_id = callback_query['from']['id']
    message_id = callback_query['message']['message_id']
    chat_id = callback_query['message']['chat']['id']
    
    # الرد على callback (إزالة حالة التحميل)
    answer_callback_query(callback_query['id'])
    
    try:
        if data.startswith('approve_'):
            target_user_id = int(data.split('_')[1])
            users_db[target_user_id] = {
                'approved': True,
                'warnings': 0,
                'first_name': users_db.get(target_user_id, {}).get('first_name', ''),
                'username': users_db.get(target_user_id, {}).get('username', '')
            }
            
            # إرسال رسالة للمستخدم
            user_chat_id = users_db.get(target_user_id, {}).get('chat_id', target_user_id)
            send_telegram_message(
                user_chat_id,
                "🎉 تم قبول طلب انضمامك!\n\nيمكنك الآن استخدام كافة خدمات البوت القانوني.\nاكتب /start لرؤية القائمة الرئيسية."
            )
            
            # تحديث رسالة المدير
            edit_telegram_message(
                chat_id,
                message_id,
                f"✅ تم قبول المستخدم {target_user_id}"
            )
            
        elif data.startswith('reject_'):
            target_user_id = int(data.split('_')[1])
            users_db[target_user_id] = {'banned': True}
            
            # إرسال رسالة للمستخدم
            user_chat_id = users_db.get(target_user_id, {}).get('chat_id', target_user_id)
            send_telegram_message(user_chat_id, "❌ نأسف، تم رفض طلب انضمامك للبوت القانوني.")
            
            # تحديث رسالة المدير
            edit_telegram_message(
                chat_id,
                message_id,
                f"❌ تم رفض المستخدم {target_user_id}"
            )
            
        elif data == "consult":
            edit_telegram_message(
                chat_id,
                message_id,
                "📞 الاستشارة القانونية الفورية:\n\nيمكنك الآن وصف مشكلتك القانونية بالتفصيل، وسيقوم أحد محامينا المتخصصين بالرد عليك في أقرب وقت.\n\n⬇️ اكتب رسالتك الآن..."
            )
            
        elif data == "services":
            edit_telegram_message(
                chat_id,
                message_id,
                "⚖️ خدماتنا القانونية المتكاملة:\n\n• 📝 صياغة العقود والاتفاقيات\n• 🏛️ المرافعات والدفوع القضائية\n• 💼 الاستشارات القانونية المتخصصة\n• 📄 التوثيق والتصديق القانوني\n• ⚔️ القضايا والمنازعات القانونية\n• 🏠 قضايا العقارات والأملاك\n• 👨‍👩‍👧‍👦 قضايا الأحوال الشخصية\n• 💰 القضايا التجارية والمالية\n\nاختر 'استشارة فورية' لبدء الخدمة المناسبة لك."
            )
            
        elif data == "about":
            edit_telegram_message(
                chat_id,
                message_id,
                "🏢 مكتب المحاماة المتخصص:\n\nنحن فريق من المحامين المتخصصين في مختلف المجالات القانونية، نقدم خدماتنا باحترافية وشفافية.\n\n📞 للتواصل المباشر:\nالهاتف: +966123456789\nالبريد الإلكتروني: info@lawfirm.com\n\n🕐 أوقات العمل:\nمن الأحد إلى الخميس\n8:00 ص - 6:00 م"
            )
            
        elif data == "appointment":
            edit_telegram_message(
                chat_id,
                message_id,
                "📝 حجز موعد استشارة:\n\nلحجز موعد مع محامٍ متخصص، يرجى:\n\n📞 الاتصال على: +966123456789\n📧 المراسلة على: appointments@lawfirm.com\n\nأو يمكنك إرسال:\n• الاسم الكامل\n• نوع الاستشارة\n• التاريخ والوقت المناسب\nوسنتواصل معك لتأكيد الموعد."
            )
            
    except Exception as e:
        logger.error(f"خطأ في معالجة الزر: {e}")

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

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """تعيين webhook"""
    try:
        webhook_url = f"https://{app.name}.onrender.com/webhook"
        url = f"{TELEGRAM_API}/setWebhook"
        payload = {
            'url': webhook_url
        }
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            return f"✅ تم تعيين webhook: {webhook_url}"
        else:
            return f"❌ فشل تعيين webhook: {response.text}"
    except Exception as e:
        return f"❌ خطأ: {e}"

@app.route('/delete_webhook', methods=['GET'])
def delete_webhook():
    """حذف webhook"""
    try:
        url = f"{TELEGRAM_API}/deleteWebhook"
        response = requests.post(url)
        
        if response.status_code == 200:
            return "✅ تم حذف webhook"
        else:
            return f"❌ فشل حذف webhook: {response.text}"
    except Exception as e:
        return f"❌ خطأ: {e}"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
