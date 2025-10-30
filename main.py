import os
import logging
import requests
import json
import re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
import threading
import time
from urllib.parse import urljoin

# تكوين السجلات
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# المتغيرات البيئية مع قيم افتراضية آمنة
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
MANAGER_CHAT_ID = os.getenv('MANAGER_CHAT_ID', '')
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', '')
APP_URL = os.getenv('APP_URL', 'https://legal-telegram-bot-qsvz.onrender.com')
FASL_AI_ENDPOINT = os.getenv('FASL_AI_ENDPOINT', '')

# تخزين مؤقت آمن للمستخدمين
users_db = {}
user_warnings = {}
user_message_history = {}

# أنماط الكشف عن المخالفات
VIOLATION_PATTERNS = [
    r'(?i)(http|https|www\.|t\.me|telegram\.me)',
    r'(?i)(سب|شتيمة| insult)',
    r'(?i)(spam|بريد مزعج)'
]

class UserManager:
    """فئة لإدارة حالة المستخدمين بشكل آمن"""
    
    @staticmethod
    def get_user(user_id):
        """الحصول على بيانات المستخدم بشكل آمن"""
        try:
            return users_db.get(str(user_id), {
                'id': user_id,
                'first_name': '',
                'last_name': '',
                'warnings': 0,
                'banned': False,
                'created_at': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"خطأ في الحصول على بيانات المستخدم {user_id}: {e}")
            return {
                'id': user_id,
                'first_name': '',
                'last_name': '',
                'warnings': 0,
                'banned': False,
                'created_at': datetime.now().isoformat()
            }
    
    @staticmethod
    def update_user(user_id, **updates):
        """تحديث بيانات المستخدم بشكل آمن"""
        try:
            user_id = str(user_id)
            if user_id not in users_db:
                users_db[user_id] = UserManager.get_user(user_id)
            
            users_db[user_id].update(updates)
            users_db[user_id]['updated_at'] = datetime.now().isoformat()
            return True
        except Exception as e:
            logger.error(f"خطأ في تحديث بيانات المستخدم {user_id}: {e}")
            return False
    
    @staticmethod
    def is_user_banned(user_id):
        """التحقق من حظر المستخدم"""
        try:
            user = UserManager.get_user(user_id)
            return user.get('banned', False)
        except Exception as e:
            logger.error(f"خطأ في التحقق من حظر المستخدم {user_id}: {e}")
            return False

class SecurityManager:
    """فئة لإدارة الأمان والكشف عن المخالفات"""
    
    @staticmethod
    def detect_violations(text):
        """الكشف عن المخالفات في النص"""
        if not text or not isinstance(text, str):
            return False, []
        
        violations = []
        text_clean = text.lower().strip()
        
        for pattern in VIOLATION_PATTERNS:
            if re.search(pattern, text_clean):
                violations.append(pattern)
        
        return len(violations) > 0, violations
    
    @staticmethod
    def sanitize_text(text):
        """تنظيف النص من الأحرف الخطرة"""
        if not text:
            return ""
        
        # إزالة الأحرف الخطرة مع الحفاظ على الأحرف العربية
        cleaned = re.sub(r'[^\w\s\u0600-\u06FF@\.\-_]', '', str(text))
        return cleaned.strip()

class MessageHandler:
    """فئة لمعالجة الرسائل بشكل آمن"""
    
    @staticmethod
    def send_telegram_message(chat_id, text, parse_mode='HTML', reply_markup=None):
        """إرسال رسالة إلى Telegram بشكل آمن"""
        try:
            if not TELEGRAM_TOKEN:
                logger.error("❌ رمز Telegram غير موجود")
                return False
            
            if not text or not str(chat_id).strip():
                logger.error("❌ نص الرسالة أو معرف الدردشة غير صالح")
                return False
            
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': text[:4090],  # حدود Telegram
                'parse_mode': parse_mode
            }
            
            if reply_markup:
                payload['reply_markup'] = reply_markup
            
            response = requests.post(url, json=payload, timeout=15)
            
            if response.status_code == 200:
                logger.info(f"✅ تم إرسال الرسالة إلى الدردشة {chat_id}")
                return True
            else:
                logger.error(f"❌ فشل إرسال الرسالة: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error("⏰ انتهت المهلة في إرسال رسالة Telegram")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"🌐 خطأ في الشبكة أثناء إرسال الرسالة: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ خطأ غير متوقع في إرسال الرسالة: {e}")
            return False
    
    @staticmethod
    def send_to_fasl_ai(user_id, chat_id, text, user_name=""):
        """إرسال الرسالة إلى Fasl AI بشكل آمن"""
        try:
            if not N8N_WEBHOOK_URL:
                logger.error("❌ عنوان webhook لـ n8n غير موجود")
                return False
            
            # تنظيف البيانات
            clean_text = SecurityManager.sanitize_text(text)
            clean_user_name = SecurityManager.sanitize_text(user_name)
            
            if not clean_text:
                logger.error("❌ النص غير صالح بعد التنظيف")
                return False
            
            payload = {
                'user_id': str(user_id),
                'chat_id': str(chat_id),
                'text': clean_text,
                'timestamp': datetime.now().isoformat(),
                'user_info': {
                    'id': str(user_id),
                    'first_name': clean_user_name.split(' ')[0] if clean_user_name else '',
                    'last_name': ' '.join(clean_user_name.split(' ')[1:]) if clean_user_name and ' ' in clean_user_name else ''
                }
            }
            
            headers = {
                'Content-Type': 'application/json',
                'X-Telegram-Token': os.getenv('TELEGRAM_WEBHOOK_SECRET', 'default-secret'),
                'User-Agent': 'LegalTelegramBot/1.0'
            }
            
            # إضافة محاولات إعادة
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        N8N_WEBHOOK_URL, 
                        json=payload, 
                        headers=headers,
                        timeout=20
                    )
                    
                    if response.status_code in [200, 201, 202]:
                        logger.info(f"✅ تم إرسال الرسالة إلى Fasl AI للمستخدم {user_id}")
                        return True
                    else:
                        logger.warning(f"⚠️ محاولة {attempt + 1} فشلت مع رمز {response.status_code}")
                        if attempt < max_retries - 1:
                            time.sleep(2)  # انتظار قبل إعادة المحاولة
                        
                except requests.exceptions.Timeout:
                    logger.warning(f"⏰ انتهت المهلة في المحاولة {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                except requests.exceptions.RequestException as e:
                    logger.warning(f"🌐 خطأ شبكة في المحاولة {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
            
            logger.error(f"❌ فشل جميع محاولات الإرسال إلى Fasl AI للمستخدم {user_id}")
            return False
            
        except Exception as e:
            logger.error(f"❌ خطأ غير متوقع في إرسال الرسالة إلى Fasl AI: {e}")
            return False

class ViolationManager:
    """فئة لإدارة المخالفات بشكل مركزي"""
    
    @staticmethod
    def handle_violation(user_id, chat_id, text):
        """معالجة المخالفات بشكل آمن"""
        try:
            user_id_str = str(user_id)
            
            # تحديث التحذيرات
            if user_id_str not in user_warnings:
                user_warnings[user_id_str] = 0
            
            user_warnings[user_id_str] += 1
            warnings = user_warnings[user_id_str]
            
            # تسجيل المخالفة
            violation_data = {
                'user_id': user_id_str,
                'chat_id': str(chat_id),
                'text': SecurityManager.sanitize_text(text)[:500],  # تقليل الطول
                'timestamp': datetime.now().isoformat(),
                'warnings_count': warnings
            }
            
            if warnings >= 3:
                # حظر المستخدم
                UserManager.update_user(user_id_str, banned=True, banned_at=datetime.now().isoformat())
                
                # إرسال رسالة الحظر
                MessageHandler.send_telegram_message(
                    chat_id, 
                    "❌ تم حظرك من البوت due to repeated violations."
                )
                
                # إشعار المدير
                MessageHandler.send_telegram_message(
                    MANAGER_CHAT_ID,
                    f"🚨 تم حظر المستخدم {user_id_str}\n"
                    f"السبب: repeated violations\n"
                    f"عدد التحذيرات: {warnings}\n"
                    f"آخر رسالة: {text[:200]}..."
                )
                return True
            else:
                # إرسال تحذير
                MessageHandler.send_telegram_message(
                    chat_id,
                    f"⚠️ تحذير ({warnings}/3): يمنع مشاركة روابط أو كلمات غير لائقة.\n"
                    f"التكرار يؤدي إلى الحظر الدائم."
                )
                
                # إشعار المدير
                MessageHandler.send_telegram_message(
                    MANAGER_CHAT_ID,
                    f"⚠️ مخالفة من المستخدم {user_id_str}\n"
                    f"التحذيرات: {warnings}/3\n"
                    f"الرسالة: {text[:200]}..."
                )
                return False
                
        except Exception as e:
            logger.error(f"❌ خطأ في معالجة المخالفة: {e}")
            return False

def keep_alive():
    """الحفاظ على نشاط التطبيق"""
    def run():
        while True:
            try:
                # طلب بسيط للحفاظ على النشاط
                if APP_URL:
                    requests.get(f"{APP_URL}/health", timeout=10)
                time.sleep(300)  # كل 5 دقائق
            except Exception as e:
                logger.debug(f"إشعار النشاط: {e}")
                time.sleep(300)
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    logger.info("🚀 بدء نظام keep-alive")

@app.route('/webhook', methods=['POST'])
def webhook():
    """معالجة webhook من Telegram"""
    try:
        data = request.get_json()
        
        if not data:
            logger.warning("⚠️ طلب webhook بدون بيانات")
            return jsonify({'status': 'error', 'message': 'No data received'}), 400
        
        logger.info(f"📥 بيانات مستلمة: {json.dumps(data, ensure_ascii=False)[:500]}")
        
        # استخراج بيانات الرسالة
        message = data.get('message', {})
        if not message:
            logger.info("⚠️ لا توجد رسالة في البيانات")
            return jsonify({'status': 'ignored'}), 200
        
        user_id = message.get('from', {}).get('id')
        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '').strip()
        user_name = f"{message.get('from', {}).get('first_name', '')} {message.get('from', {}).get('last_name', '')}".strip()
        
        if not user_id or not chat_id:
            logger.warning("⚠️ معرف مستخدم أو دردشة مفقود")
            return jsonify({'status': 'error', 'message': 'Missing user_id or chat_id'}), 400
        
        # التحقق من حظر المستخدم
        if UserManager.is_user_banned(user_id):
            logger.info(f"⛔ مستخدم محظور {user_id} حاول إرسال رسالة")
            MessageHandler.send_telegram_message(
                chat_id, 
                "❌ أنت محظور من استخدام هذا البوت."
            )
            return jsonify({'status': 'banned'}), 200
        
        # معالجة الرسالة الفارغة
        if not text:
            MessageHandler.send_telegram_message(
                chat_id,
                "⚠️ يرجى إرسال نص صالح للتحليل."
            )
            return jsonify({'status': 'empty_message'}), 200
        
        # الكشف عن المخالفات
        has_violation, violations = SecurityManager.detect_violations(text)
        
        if has_violation:
            logger.warning(f"🚨 مخالفة обнаружена للمستخدم {user_id}: {violations}")
            ViolationManager.handle_violation(user_id, chat_id, text)
            return jsonify({'status': 'violation_detected'}), 200
        
        # إرسال إلى Fasl AI
        success = MessageHandler.send_to_fasl_ai(user_id, chat_id, text, user_name)
        
        if success:
            MessageHandler.send_telegram_message(
                chat_id,
                "✅ تم استلام استفسارك وسيتم الرد قريباً."
            )
        else:
            MessageHandler.send_telegram_message(
                chat_id,
                "⚠️ عذراً، حدث خطأ في معالجة طلبك. يرجى المحاولة لاحقاً."
            )
        
        return jsonify({'status': 'processed'}), 200
        
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع في webhook: {e}")
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """نقطة فحص صحة التطبيق"""
    try:
        status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '2.0.0',
            'services': {
                'telegram': bool(TELEGRAM_TOKEN),
                'n8n_webhook': bool(N8N_WEBHOOK_URL),
                'manager_chat': bool(MANAGER_CHAT_ID)
            },
            'statistics': {
                'total_users': len(users_db),
                'active_warnings': len(user_warnings)
            }
        }
        return jsonify(status), 200
    except Exception as e:
        logger.error(f"❌ خطأ في health check: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

@app.route('/')
def home():
    """الصفحة الرئيسية"""
    return jsonify({
        'message': 'Legal Telegram Bot is running!',
        'status': 'active',
        'timestamp': datetime.now().isoformat()
    })

@app.errorhandler(404)
def not_found(error):
    """معالجة الأخطاء 404"""
    return jsonify({'status': 'error', 'message': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """معالجة الأخطاء 500"""
    logger.error(f"❌ خطأ داخلي في الخادم: {error}")
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

if __name__ == '__main__':
    # التحقق من المتغيرات البيئية الأساسية
    required_vars = ['TELEGRAM_TOKEN']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"❌ متغيرات بيئية مفقودة: {missing_vars}")
        logger.warning("⚠️ البوت قد لا يعمل بشكل صحيح بدون هذه المتغيرات")
    
    # بدء نظام keep-alive
    keep_alive()
    
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 بدء تشغيل البوت على المنفذ {port}")
    logger.info(f"🌐 عنوان التطبيق: {APP_URL}")
    logger.info(f"📊 عدد المستخدمين المسجلين: {len(users_db)}")
    
    try:
        app.run(
            host='0.0.0.0', 
            port=port, 
            debug=False,
            threaded=True
        )
    except Exception as e:
        logger.error(f"❌ فشل تشغيل التطبيق: {e}")
        raise
