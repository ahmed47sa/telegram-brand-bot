import os
import re
import logging
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# إعداد الـ Logging لمتابعة الأخطاء في Railway
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ===== جلب البيانات من Variables =====
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID", "")

# ===== إعداد Gemini بالمكتبة الرسمية =====
genai.configure(api_key=GEMINI_API_KEY)
# نستخدم الموديل 1.5 فلاش مباشرة
model = genai.GenerativeModel('gemini-1.5-flash')

# ===== شخصية البوت =====
SYSTEM_PROMPT = """
أنت مساعد متجر ملابس "براندي" المصري. ردودك دايماً بالعربية، ودودة، وقصيرة وواضحة.

🛍️ منتجاتنا وأسعارها:
- تيشيرتات قطن 100%: 150 - 250 جنيه
- بناطيل جينز: 350 - 550 جنيه
- هوديز: 400 - 650 جنيه
- الألوان المتاحة: أبيض، أسود، كحلي، رمادي، بيج

📦 سياسات المتجر:
- التوصيل لكل محافظات مصر خلال 3-5 أيام
- رسوم التوصيل: 60 جنيه (مجاني فوق 500 جنيه)
- الإرجاع والاستبدال خلال 14 يوم

🎯 مهمتك:
1. رد على أي سؤال عن المنتجات أو الأسعار أو التوصيل
2. لو العميل أبدى رغبة في الشراء أو طلب التوصيل:
   - اطلب منه: الاسم الكامل، رقم الهاتف، المحافظة، والمنتج المطلوب
   - بعد ما يبعتهم، قوله: "شكراً! سيتواصل معك فريقنا خلال ساعات قليلة 🎉"
   - وضيف في آخر ردك هذا التنسيق بالضبط:
     [[ORDER: name=الاسم, phone=الرقم, city=المحافظة, product=المنتج]]

ملاحظة: لو العميل بعت بيانات ناقصة، اطلب المعلومة الناقصة بس.
"""

# ذاكرة المحادثات
chat_sessions = {}

async def ask_gemini(user_id: int, user_message: str) -> str:
    # لو المستخدم جديد، بنبدأ له محادثة جديدة مع البرومبت الأساسي
    if user_id not in chat_sessions:
        chat_sessions[user_id] = model.start_chat(history=[])
        prompt = f"{SYSTEM_PROMPT}\n\nالعميل يقول: {user_message}"
    else:
        prompt = user_message

    try:
        # إرسال الرسالة للموديل بشكل غير متزامن
        response = await chat_sessions[user_id].send_message_async(prompt)
        return response.text
    except Exception as e:
        logging.error(f"Gemini Error: {e}")
        return "⚠️ عذراً، حدث خطأ مؤقت في الاتصال بالذكاء الاصطناعي. حاول مرة أخرى."

def extract_order(text: str) -> dict or None:
    # نمط استخراج البيانات (Regex) المعدل
    pattern = r'\[\[ORDER:\s*name=(.+?),\s*phone=(.+?),\s*city=(.+?),\s*product=(.+?)\]\]'
    match = re.search(pattern, text)
    if match:
        return {
            "name": match.group(1).strip(),
            "phone": match.group(2).strip(),
            "city": match.group(3).strip(),
            "product": match.group(4).strip()
        }
    return None

def clean_reply(text: str) -> str:
    # مسح كود الطلب من الرسالة اللي بتظهر للعميل
    return re.sub(r'\[\[ORDER:.*?\]\]', '', text, flags=re.DOTALL).strip()

async def notify_owner(context: ContextTypes.DEFAULT_TYPE, order: dict, customer_id: int):
    if not OWNER_CHAT_ID:
        return
    
    msg = (f"🛍️ *طلب جديد!*\n\n"
           f"👤 *العميل:* {order['name']}\n"
           f"📱 *الهاتف:* `{order['phone']}`\n"
           f"📍 *المحافظة:* {order['city']}\n"
           f"🎁 *المنتج:* {order['product']}\n\n"
           f"🆔 Telegram ID: `{customer_id}`")
    
    try:
        await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=msg, parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Notify Owner Error: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    user_text = update.message.text

    # إظهار "Typing..." في تليجرام
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # الحصول على رد Gemini
    reply = await ask_gemini(user_id, user_text)
    
    # معالجة الرد (تنظيفه واستخراج الطلب)
    order = extract_order(reply)
    display_msg = clean_reply(reply)

    await update.message.reply_text(display_msg)

    # إرسال إشعار لصاحب البوت لو فيه طلب
    if order:
        await notify_owner(context, order, user_id)

def main():
    if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
        print("❌ خطأ: لم يتم العثور على المفاتيح في Variables!")
        return

    # بناء البوت
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # معالجة الرسائل النصية فقط
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 البوت شغال الآن باستخدام المكتبة الرسمية...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
