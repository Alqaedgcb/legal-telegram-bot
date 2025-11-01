import os
import logging
import requests
import json
import re
from datetime import datetime
from flask import Flask, request, jsonify
import threading
import time

# تكوين السجلات
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# المتغيرات البيئية
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
MANAGER_CHAT_ID = os.getenv('MANAGER_CHAT_ID', '')
N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', '')
APP_URL = os.getenv('RAILWAY_STATIC_URL', '') or os.getenv('APP_URL', '')
PORT = os.getenv('PORT', '5000')

# تخزين البيانات
user_warnings = {}
pending_approvals = {}

def set_telegram_webhook():
    """تعيين webhook لـ Telegram"""
    try:
        if not TELEGRAM_TOKEN or not APP_URL:
            logger.warning("⚠️ لا يمكن تعيين webhook - رمز أو عنوان مفقود")
            return False
            
        webhook_url = f"{APP_URL}/webhook"
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
        payload = {
            'url': webhook_url,
            'drop_pending_updates': True,
            'allowed_updates': ['message', 'callback_query']
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info(f"✅ تم تعيين webhook: {webhook_url}")
            return True
        else:
            logger.error(f"❌ فشل تعيين webhook: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ خطأ في تعيين webhook: {e}")
        return False

def send_telegram_message(chat_id, text, parse_mode='HTML', reply_markup=None):
    """إرسال رسالة إلى Telegram"""
    try:
        if not TELEGRAM_TOKEN or not chat_id or not text:
            return False
            
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': str(text)[:4000],
            'parse_mode': parse_mode
        }
        
        if reply_markup:
            payload['reply_markup'] = reply_markup
        
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
        
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال الرسالة: {e}")
        return False

def answer_callback_query(callback_id, text=None):
    """الرد على callback query"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
        payload = {
            'callback_query_id': callback_id
        }
        if text:
            payload['text'] = text
            
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ خطأ في answer_callback_query: {e}")
        return False

def edit_message_reply_markup(chat_id, message_id):
    """تعديل الرسالة لإزالة الأزرار"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageReplyMarkup"
        payload = {
            'chat_id': chat_id,
            'message_id': message_id,
            'reply_markup': {'inline_keyboard': []}
        }
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ خطأ في تعديل الرسالة: {e}")
        return False

def create_approval_buttons(user_id):
    """إنشاء أزرار الموافقة والرفض"""
    return {
        'inline_keyboard': [
            [
                {
                    'text': '✅ قبول',
                    'callback_data': f'approve_{user_id}'
                },
                {
                    'text': '❌ رفض', 
                    'callback_data': f'reject_{user_id}'
                }
            ]
        ]
    }

def send_approval_request(user_id, user_name, chat_id):
    """إرسال طلب موافقة للمدير"""
    try:
        if not MANAGER_CHAT_ID:
            logger.error("❌ معرف مدير غير موجود")
            return False
            
        buttons = create_approval_buttons(user_id)
        
        message_text = f"""
👤 طلب انضمام جديد

🆔 المعرف: {user_id}
📛 الاسم: {user_name}
💬 الدردشة: {chat_id}

يرجى الموافقة أو الرفض:
        """
        
        # حفظ بيانات الانتظار للموافقة
        pending_approvals[str(user_id)] = {
            'user_name': user_name,
            'chat_id': chat_id,
            'timestamp': datetime.now().isoformat()
        }
        
        success = send_telegram_message(MANAGER_CHAT_ID, message_text, reply_markup=buttons)
        if success:
            logger.info(f"✅ تم إرسال طلب موافقة للمدير للمستخدم {user_id}")
        return success
        
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال طلب الموافقة: {e}")
        return False

def handle_user_approval(user_id, chat_id, message_id):
    """معالجة قبول المستخدم"""
    try:
        user_id_str = str(user_id)
        
        # تحديث حالة المستخدم
        user_warnings[user_id_str] = 0
        
        # إرسال رسالة تأكيد للمدير
        send_telegram_message(
            chat_id,
            f"✅ تم قبول المستخدم {user_id_str} بنجاح"
        )
        
        # إرسال رسالة ترحيب للمستخدم
        user_data = pending_approvals.get(user_id_str, {})
        user_chat_id = user_data.get('chat_id')
        if user_chat_id:
            send_telegram_message(
                user_chat_id,
                "🎉 تم قبول طلب انضمامك! يمكنك الآن استخدام البوت.\n\nأرسل رسالتك وسأقوم بالرد عليك."
            )
        
        # تعديل الرسالة الأصلية لإزالة الأزرار
        edit_message_reply_markup(chat_id, message_id)
        
        # إزالة من قائمة الانتظار
        if user_id_str in pending_approvals:
            del pending_approvals[user_id_str]
        
        logger.info(f"✅ تم قبول المستخدم {user_id_str}")
        return True
        
    except Exception as e:
        logger.error(f"❌ خطأ في قبول المستخدم: {e}")
        return False

def handle_user_rejection(user_id, chat_id, message_id):
    """معالجة رفض المستخدم"""
    try:
        user_id_str = str(user_id)
        
        # تحديث حالة المستخدم (حظر)
        user_warnings[user_id_str] = 3
        
        # إرسال رسالة تأكيد للمدير
        send_telegram_message(
            chat_id,
            f"❌ تم رفض المستخدم {user_id_str}"
        )
        
        # إرسال رسالة رفض للمستخدم
        user_data = pending_approvals.get(user_id_str, {})
        user_chat_id = user_data.get('chat_id')
        if user_chat_id:
            send_telegram_message(
                user_chat_id,
                "❌ تم رفض طلب انضمامك. لا يمكنك استخدام هذا البوت."
            )
        
        # تعديل الرسالة الأصلية لإزالة الأزرار
        edit_message_reply_markup(chat_id, message_id)
        
        # إزالة من قائمة الانتظار
        if user_id_str in pending_approvals:
            del pending_approvals[user_id_str]
        
        logger.info(f"❌ تم رفض المستخدم {user_id_str}")
        return True
        
    except Exception as e:
        logger.error(f"❌ خطأ في رفض المستخدم: {e}")
        return False

def handle_callback_query(callback_query):
    """معالجة ضغط المستخدم على الأزرار"""
    try:
        callback_id = callback_query.get('id')
        user_id = callback_query.get('from', {}).get('id')
        data = callback_query.get('data')
        message = callback_query.get('message', {})
        message_id = message.get('message_id')
        chat_id = message.get('chat', {}).get('id')

        logger.info(f"🔄 معالجة callback: {data} من المستخدم {user_id}")

        # الرد على callback query (مهم لإزالة حالة التحميل)
        answer_callback_query(callback_id, "جارِ المعالجة...")

        # معالجة الإجراءات المختلفة
        if data.startswith('approve_'):
            user_to_approve = data.replace('approve_', '')
            success = handle_user_approval(user_to_approve, chat_id, message_id)
            if success:
                answer_callback_query(callback_id, "✅ تم القبول")
            return jsonify({'status': 'user_approved'}), 200
            
        elif data.startswith('reject_'):
            user_to_reject = data.replace('reject_', '')
            success = handle_user_rejection(user_to_reject, chat_id, message_id)
            if success:
                answer_callback_query(callback_id, "❌ تم الرفض")
            return jsonify({'status': 'user_rejected'}), 200
        
        answer_callback_query(callback_id, "⚠️ إجراء غير معروف")
        return jsonify({'status': 'unknown_action'}), 200
        
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة callback: {e}")
        return jsonify({'status': 'error'}), 500

def detect_violations(text):
    """الكشف عن المخالفات الأساسية"""
    if not text:
        return False
        
    text_lower = str(text).lower()
    violations = [
        'http://', 'https://', 'www.', 't.me/', 
        'telegram.me', '.com', '.org', '.net'
    ]
    
    for violation in violations:
        if violation in text_lower:
            return True
    return False

def handle_violation(user_id, chat_id, text):
    """معالجة المخالفات"""
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
                    f"🚨 تم حظر المستخدم {user_id_str} بسبب المخالفات المتكررة"
                )
            return True
        else:
            # إرسال تحذير
            send_telegram_message(
                chat_id,
                f"⚠️ تحذير ({warnings}/3): يمنع مشاركة روابط أو محتوى غير لائق."
            )
            return False
            
    except Exception as e:
        logger.error(f"❌ خطأ في معالجة المخالفة: {e}")
        return False

def send_to_fasl_ai(user_id, chat_id, text, user_name=""):
    """إرسال الرسالة إلى Fasl AI"""
    try:
        if not N8N_WEBHOOK_URL:
            logger.error("❌ عنوان webhook لـ n8n غير موجود")
            return False
        
        # تنظيف البيانات الأساسي
        clean_text = re.sub(r'[^\w\s\u0600-\u06FF@\.\-_\?\!]', '', str(text)) if text else ""
        
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
            logger.info(f"✅ تم إرسال الرسالة إلى Fasl AI للمستخدم {user_id}")
            return True
        else:
            logger.error(f"❌ فشل إرسال الرسالة إلى Fasl AI: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ خطأ في إرسال الرسالة إلى Fasl AI: {e}")
        return False

def keep_alive():
    """الحفاظ على نشاط التطبيق"""
    def run():
        while True:
            try:
                if APP_URL:
                    requests.get(f"{APP_URL}/health", timeout=10)
                    logger.debug("🟢 طلب keep-alive تم بنجاح")
                time.sleep(300)  # كل 5 دقائق
            except Exception as e:
                logger.debug(f"🔴 keep-alive فشل: {e}")
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
            return jsonify({'status': 'no_data'}), 400
        
        logger.info(f"📥 بيانات مستلمة: {json.dumps(data, ensure_ascii=False)[:200]}...")
        
        # معالجة callback queries (ضغط على الأزرار)
        if 'callback_query' in data:
            return handle_callback_query(data['callback_query'])
        
        # معالجة الرسائل العادية
        message = data.get('message', {})
        if not message:
            logger.info("⚠️ لا توجد رسالة في البيانات")
            return jsonify({'status': 'no_message'}), 200
        
        user_info = message.get('from', {})
        user_id = user_info.get('id')
        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '').strip()
        user_name = f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()

        if not user_id or not chat_id:
            logger.warning("⚠️ معرف مستخدم أو دردشة مفقود")
            return jsonify({'status': 'missing_ids'}), 400

        logger.info(f"👤 مستخدم {user_id} في دردشة {chat_id}: {text[:50]}...")

        # التحقق من حظر المستخدم
        if str(user_id) in user_warnings and user_warnings[str(user_id)] >= 3:
            logger.info(f"⛔ مستخدم محظور {user_id} حاول إرسال رسالة")
            send_telegram_message(chat_id, "❌ أنت محظور من استخدام هذا البوت.")
            return jsonify({'status': 'banned'}), 200

        # التحقق من المستخدم الجديد
        if str(user_id) not in user_warnings:
            user_warnings[str(user_id)] = 0
            # إرسال طلب موافقة للمدير
            approval_sent = send_approval_request(user_id, user_name, chat_id)
            if approval_sent:
                send_telegram_message(chat_id, "⏳ تم إرسال طلب الانضمام للمدير، يرجى الانتظار للموافقة...")
                return jsonify({'status': 'approval_sent'}), 200
            else:
                send_telegram_message(chat_id, "⚠️ حدث خطأ في إرسال طلب الانضمام. يرجى المحاولة لاحقاً.")
                return jsonify({'status': 'approval_failed'}), 200

        # التحقق من انتظار الموافقة
        if str(user_id) in pending_approvals:
            send_telegram_message(chat_id, "⏳ طلبك لا يزال قيد المراجعة. يرجى الانتظار...")
            return jsonify({'status': 'pending_approval'}), 200

        # تجاهل الرسائل الفارغة
        if not text:
            send_telegram_message(chat_id, "⚠️ يرجى إرسال نص صالح.")
            return jsonify({'status': 'empty_message'}), 200

        # الكشف عن المخالفات
        if detect_violations(text):
            logger.warning(f"🚨 مخالفة обнаружена للمستخدم {user_id}")
            handle_violation(user_id, chat_id, text)
            return jsonify({'status': 'violation_detected'}), 200

        # إرسال إلى Fasl AI
        ai_success = send_to_fasl_ai(user_id, chat_id, text, user_name)
        
        if ai_success:
            send_telegram_message(chat_id, "✅ تم استلام استفسارك وسيتم الرد قريباً.")
        else:
            send_telegram_message(chat_id, "⚠️ عذراً، حدث خطأ في معالجة طلبك. يرجى المحاولة لاحقاً.")

        return jsonify({'status': 'processed'}), 200
        
    except Exception as e:
        logger.error(f"❌ خطأ غير متوقع في webhook: {e}")
        return jsonify({'status': 'error'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """فحص صحة التطبيق"""
    status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'telegram': bool(TELEGRAM_TOKEN),
            'n8n_webhook': bool(N8N_WEBHOOK_URL),
            'manager_chat': bool(MANAGER_CHAT_ID)
        },
        'statistics': {
            'total_users': len(user_warnings),
            'pending_approvals': len(pending_approvals)
        }
    }
    return jsonify(status), 200

@app.route('/set_webhook', methods=['GET'])
def set_webhook_route():
    """تعيين webhook يدوياً"""
    success = set_telegram_webhook()
    if success:
        return jsonify({'status': 'success', 'message': 'Webhook set successfully'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to set webhook'}), 500

@app.route('/')
def home():
    """الصفحة الرئيسية"""
    return jsonify({
        'message': 'Legal Telegram Bot is running!',
        'status': 'active',
        'timestamp': datetime.now().isoformat(),
        'version': '2.0.0'
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'status': 'error', 'message': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"❌ خطأ داخلي في الخادم: {error}")
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

if __name__ == '__main__':
    # التحقق من المتغيرات البيئية الأساسية
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN غير موجود!")
    else:
        logger.info("✅ TELEGRAM_TOKEN موجود")

    if not MANAGER_CHAT_ID:
        logger.warning("⚠️ MANAGER_CHAT_ID غير موجود - إشعارات المدير لن تعمل")

    # تعيين webhook تلقائياً
    set_telegram_webhook()
    
    # بدء نظام keep-alive
    keep_alive()
    
    # تشغيل التطبيق
    logger.info(f"🚀 بدء تشغيل البوت على المنفذ {PORT}")
    logger.info(f"📊 إحصائيات أولية: {len(user_warnings)} مستخدم، {len(pending_approvals)} في انتظار الموافقة")
    
    app.run(host='0.0.0.0', port=int(PORT), debug=False)
