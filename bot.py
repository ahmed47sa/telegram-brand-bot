import os
import re
import logging
from groq import Groq
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# إعداد الـ Logging
logging.basicConfig(level=logging.INFO)

# ===== الإعدادات =====
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID", "")

# إعداد عميل Groq
client = Groq(api_key=GROQ_API_KEY)

# ===== شخصية البوت =====
SYSTEM_PROMPT = """
أنت مساعد متجر ملابس "براندي" المصري. ردودك دايماً بالعربية، ودودة، وقصيرة وواضحة.
🛍️ منتجاتنا: تيشيرتات (150-250ج)، جينز (350-550ج)، هوديز (400-650ج).
📦 التوصيل: 60ج ومجاني فوق 500ج لجميع المحافظات.
🎯 لو العميل طلب شراء اطلب منه: (الاسم، الهاتف، المحافظة، المنتج).
بمجرد استلامهم، أضف هذا الكود في نهاية ردك:
[[ORDER: name=الاسم, phone=الرقم, city=المحافظة, product=المنتج]]
"""

async def ask_groq(user_message: str) -> str:
    try:
        # بنستخدم موديل Llama 3 السريع جداً
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"Groq Error: {e}")
        return "⚠️ عذراً، حدث خطأ بسيط. جرب تبعت رسالتك تاني."

def extract_order(text: str):
    pattern = r'\[\[ORDER:\s*name=(.+?),\s*phone=(.+?),\s*city=(.+?),\s*product=(.+?)\]\]'
    match = re.search(pattern, text)
    if match:
        return {"name": match.group(1), "phone": match.group(2), "city": match.group(3), "product": match.group(4)}
    return None

def clean_reply(text: str):
    return re.sub(r'\[\[ORDER:.*?\]\]', '', text, flags=re.DOTALL).strip()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # الحصول على الرد من Groq
    reply = await ask_groq(user_text)
    order = extract_order(reply)
    display_msg = clean_reply(reply)

    await update.message.reply_text(display_msg)

    # إشعار لصاحب البوت
    if order and OWNER_CHAT_ID:
        msg = (f"🛍️ *طلب جديد!*\n👤 العميل: {order['name']}\n📱 الهاتف: `{order['phone']}`\n"
               f"📍 المحافظة: {order['city']}\n🎁 المنتج: {order['product']}")
        await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=msg, parse_mode="Markdown")

def main():
    if not TELEGRAM_BOT_TOKEN or not GROQ_API_KEY:
        print("❌ تأكد من إضافة Tokens في Railway Variables")
        return
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 البوت شغال الآن بـ Groq...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
