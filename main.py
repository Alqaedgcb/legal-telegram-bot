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
APP_URL = "https://legal-telegram-bot-qsvz.onrender.com"  # ⚠️ الرابط الصحيح

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
        'text': text
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

@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>البوت القانوني</title>
        <meta charset="utf-8">
    </head>
    <body>
        <h1>✅ البوت القانوني يعمل بنظام Webhook المباشر!</h1>
        <p>🕒 آخر نشاط: {}</p>
        <p>🔗 <a href="/set_webhook">تعيين Webhook</a></p>
        <p>🔗 <a href="/status">حالة النظام</a></p>
        <p>📞 الرابط الصحيح: {}</p>
    </body>
    </html>
    """.format(time.strftime('%Y-%m-%d %H:%M:%S'), APP_URL)

@app.route('/status')
def status():
    """عرض حالة النظام"""
    status_info = {
        'app_url': APP_URL,
        'users_count': len(users_db),
        'pending_approvals': sum(1 for u in users_db.values() if u.get('status') == 'pending'),
        'server_time': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    return jsonify(status_info)

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """تعيين webhook"""
    try:
        webhook_url = f"{APP_URL}/webhook"
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        payload = {
            'url': webhook_url
        }
        
        response = requests.post(url, json=payload)
        logger.info(f"Set webhook response: {response.status_code}")
        
        if response.status_code == 200:
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>تعيين Webhook</title>
                <meta charset="utf-8">
            </head>
            <body>
                <h1>✅ تم تعيين Webhook بنجاح!</h1>
                <p><strong>الرابط الصحيح:</strong> {webhook_url}</p>
                <p><strong>الرد من التليجرام:</strong> {response.text}</p>
                <br>
                <p>🎯 الآن يمكنك اختبار البوت بإرسال /start للبوت</p>
                <p>🔄 <a href="/">العودة للصفحة الرئيسية</a></p>
            </body>
            </html>
            """
        else:
            return f"""
            <h1>❌ فشل تعيين Webhook</h1>
            <p><strong>الخطأ:</strong> {response.text}</p>
            <p><strong>الرابط المستخدم:</strong> {webhook_url}</p>
            <p>تأكد من صحة BOT_TOKEN</p>
            """
    except Exception as e:
        return f"""
        <h1>❌ خطأ في تعيين Webhook</h1>
        <p><strong>التفاصيل:</strong> {str(e)}</p>
        """

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    """معالجة webhook من التليجرام"""
    if request.method == 'GET':
        return "✅ Webhook جاهز لاستقبال البيانات من: " + APP_URL
    
    try:
        data = request.get_json()
        logger.info(f"📩 Received update from Telegram")
        
        if 'message' in data:
            handle_message(data['message'])
        elif 'callback_query' in data:
            handle_callback(data['callback_query'])
            
    except Exception as e:
        logger.error(f"❌ Error in webhook: {e}")
    
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
    
    if users_db.get(user_id, {}).get('banned'):
        send_telegram_message(chat_id, "❌ تم حظرك من استخدام البوت.")
        return
        
    if user_id not in users_db or not users_db[user_id].get('approved'):
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
    """عرض القائمة الرئيسية"""
    keyboard = {
        'inline_keyboard': [
            [{'text': '📞 استشارة فورية', 'callback_data': 'consult'}],
            [{'text': '⚖️ خدمات قانونية', 'callback_data': 'services'}],
            [{'text': 'ℹ️ معلومات', 'callback_data': 'about'}]
        ]
    }
    
    send_telegram_message(chat_id, "🎯 اختر الخدمة:", keyboard)

def handle_callback(callback_query):
    """معالجة ضغطات الأزرار"""
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
            edit_message_text(chat_id, message_id, "💬 اكتب استشارتك...")
        elif data == "services":
            edit_message_text(chat_id, message_id, "📋 الخدمات: عقود - قضايا - استشارات")
        elif data == "about":
            edit_message_text(chat_id, message_id, "🏢 محامون متخصصون")
            
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة الزر: {e}")

def answer_callback_query(callback_query_id):
    """الرد على callback query"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery"
    payload = {'callback_query_id': callback_query_id}
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ Failed to answer callback: {e}")
        return False

def edit_message_text(chat_id, message_id, text):
    """تعديل رسالة موجودة"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"
    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ Failed to edit message: {e}")
        return False

def handle_user_text(user_id, chat_id, text):
    """معالجة الرسائل النصية من المستخدمين"""
    if user_id not in users_db or not users_db[user_id].get('approved'):
        send_telegram_message(chat_id, "⏳ انتظر الموافقة أولاً")
        return
    
    if any(word in text for word in ['http', '.com', 'سب', 'شتم']):
        send_telegram_message(chat_id, "⚠️ يمنع هذا المحتوى")
        return
        
    send_telegram_message(chat_id, "✅ تم الاستلام، سنرد قريباً")

if __name__ == '__main__':
    keep_alive()
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 بدء تشغيل البوت على: {APP_URL}")
    app.run(host='0.0.0.0', port=port, debug=False)
