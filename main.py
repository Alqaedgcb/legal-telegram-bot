import os
import logging
import requests
import json
import re
from datetime import datetime
from flask import Flask, request, jsonify
import threading
import time

# تكوين السجلات المبسط
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# المتغيرات البيئية الأساسية
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
MANAGER_CHAT_ID = os.getenv('MANAGER_CHAT_ID', '')
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', '')
APP_URL = os.getenv('APP_URL', '')

# تخزين بسيط في الذاكرة
user_warnings = {}

def send_telegram_message(chat_id, text):
    """إرسال رسالة إلى Telegram"""
    try:
        if not TELEGRAM_TOKEN or not chat_id or not text:
            return False
            
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': str(text)[:4000],
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
        
    except Exception as e:
        logger.error(f"خطأ في إرسال الرسالة: {e}")
        return False

def send_to_fasl_ai(user_id, chat_id, text, user_name=""):
    """إرسال الرسالة إلى Fasl AI"""
    try:
        if not N8N_WEBHOOK_URL:
            logger.error("عنوان webhook لـ n8n غير موجود")
            return False
        
        # تنظيف البيانات الأساسي
        clean_text = re.sub(r'[^\w\s\u0600-\u06FF@\.\-_]', '', str(text)) if text else ""
        
        if not clean_text:
            return False
        
        payload = {
            'user_id': str(user_id),
            'chat_id': str(chat_id),
            'text': clean_text,
            'timestamp': datetime.now().isoformat(),
            'user_info': {
                'id': str(user_id),
                'first_name': str(user_name).split(' ')[0] if user_name else '',
                'last_name': ' '.join(str(user_name).split(' ')[1:]) if user_name and ' ' in user_name else ''
            }
        }
        
        headers = {
            'Content-Type': 'application/json',
            'X-Telegram-Token': os.getenv('TELEGRAM_WEBHOOK_SECRET', 'default-secret')
        }
        
        response = requests.post(N8N_WEBHOOK_URL, json=payload, headers=headers, timeout=15)
        
        if response.status_code == 200:
            logger.info(f"تم إرسال الرسالة إلى Fasl AI للمستخدم {user_id}")
            return True
        else:
            logger.error(f"فشل إرسال الرسالة إلى Fasl AI: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"خطأ في إرسال الرسالة إلى Fasl AI: {e}")
        return False

def detect_violations(text):
    """الكشف عن المخالفات الأساسية"""
    if not text:
        return False
        
    text_lower = str(text).lower()
    violations = [
        'http://', 'https://', 'www.', 't.me/', 
        'telegram.me', 'spam', 'بريد مزعج'
    ]
    
    for violation in violations:
        if violation in text_lower:
            return True
    return False

def handle_violation(user_id, chat_id, text):
    """معالجة المخالفات بشكل مبسط"""
    try:
        user_id_str = str(user_id)
        
        if user_id_str not in user_warnings:
            user_warnings[user_id_str] = 0
            
        user_warnings[user_id_str] += 1
        warnings = user_warnings[user_id_str]
        
        if warnings >= 3:
            # حظر المستخدم
            send_telegram_message(chat_id, "❌ تم حظرك من البوت due to repeated violations.")
            
            # إشعار المدير
            if MANAGER_CHAT_ID:
                send_telegram_message(
                    MANAGER_CHAT_ID,
                    f"🚨 تم حظر المستخدم {user_id}"
                )
            return True
        else:
            # إرسال تحذير
            send_telegram_message(
                chat_id,
                f"⚠️ تحذير ({warnings}/3): يمنع مشاركة روابط أو كلمات غير لائقة."
            )
            return False
            
    except Exception as e:
        logger.error(f"خطأ في معالجة المخالفة: {e}")
        return False

def keep_alive():
    """الحفاظ على نشاط التطبيق بشكل مبسط"""
    def run():
        while True:
            try:
                if APP_URL:
                    requests.get(f"{APP_URL}/", timeout=5)
                time.sleep(300)
            except:
                time.sleep(300)
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    logger.info("بدأ نظام keep-alive")

@app.route('/webhook', methods=['POST'])
def webhook():
    """معالجة webhook من Telegram بشكل مبسط"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'status': 'no data'}), 400
        
        message = data.get('message', {})
        if not message:
            return jsonify({'status': 'no message'}), 200
        
        user_info = message.get('from', {})
        user_id = user_info.get('id')
        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '').strip()
        user_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
        
        if not user_id or not chat_id:
            return jsonify({'status': 'missing user_id or chat_id'}), 400
        
        # تجاهل الرسائل الفارغة
        if not text:
            send_telegram_message(chat_id, "⚠️ يرجى إرسال نص صالح.")
            return jsonify({'status': 'empty message'}), 200
        
        # الكشف عن المخالفات
        if detect_violations(text):
            handle_violation(user_id, chat_id, text)
            return jsonify({'status': 'violation detected'}), 200
        
        # إرسال إلى Fasl AI
        ai_success = send_to_fasl_ai(user_id, chat_id, text, user_name)
        
        if ai_success:
            send_telegram_message(chat_id, "✅ تم استلام استفسارك وسيتم الرد قريباً.")
        else:
            send_telegram_message(chat_id, "⚠️ عذراً، حدث خطأ في معالجة طلبك.")
        
        return jsonify({'status': 'processed'}), 200
        
    except Exception as e:
        logger.error(f"خطأ في webhook: {e}")
        return jsonify({'status': 'error'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """فحص الصحة الأساسي"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/')
def home():
    """الصفحة الرئيسية"""
    return jsonify({
        'message': 'Legal Telegram Bot is running!',
        'status': 'active'
    })

if __name__ == '__main__':
    # بدء نظام keep-alive
    keep_alive()
    
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"بدء تشغيل البوت على المنفذ {port}")
    
    # تشغيل التطبيق بدون خصائص معقدة
    app.run(host='0.0.0.0', port=port)
