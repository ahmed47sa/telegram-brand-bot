import os
import re
import logging
from groq import Groq
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)

# ===== الإعدادات =====
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID", "")

client = Groq(api_key=GROQ_API_KEY)

# ===== شخصية البوت المطورة =====
SYSTEM_PROMPT = """
أنت "مساعد مبيعات ذكي" لمتجر "براندي" للملابس في مصر. 
هدفك الأساسي: مساعدة العميل وإتمام عملية البيع بنجاح.

أسلوبك: مصري، ودود جداً، عملي، ومحترف.

🛍️ كتالوج المنتجات:
- تيشيرتات قطن: 150-250 ج
- جينز: 350-550 ج
- هوديز: 400-650 ج
(التوصيل 60 ج ومجاني لأي أوردر فوق 500 ج).

التعامل مع المحادثة:
1. لو العميل سلم عليك، رد عليه بترحيب حار واسأله محتاج إيه (تيشيرت، جينز، ولا هوديز؟).
2. لو العميل اختار منتج، قوله السعر ومميزاته واسأله: "تحب نأكد الحجز دلوقتي؟".
3. لو العميل قال "أيوة، تمام، اوك، كمل" أو أظهر أي رغبة في الشراء: 
   - اطلب منه فوراً (الاسم، رقم التليفون، المحافظة).
4. بمجرد ما يبعت البيانات، قوله "تم تسجيل طلبك يا فندم، فريقنا هيكلمك فوراً" ولازم تنهي ردك بالكود ده:
   [[ORDER: name=الاسم, phone=الرقم, city=المحافظة, product=المنتج]]

⚠️ ممنوع تعيد الترحيب لو العميل كمل كلامه، خليك دايماً فاكر هو كان بيقول إيه قبل كدة.
"""

# ذاكرة المحادثات
conversations_history = {}

async def ask_groq(user_id: int, user_message: str) -> str:
    # إنشاء ذاكرة للمستخدم لو مش موجودة
    if user_id not in conversations_history:
        conversations_history[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # إضافة رسالة المستخدم للذاكرة
    conversations_history[user_id].append({"role": "user", "content": user_message})
    
    # الحفاظ على آخر 10 رسائل فقط عشان الذاكرة متتقلش
    if len(conversations_history[user_id]) > 12:
        conversations_history[user_id] = [conversations_history[user_id][0]] + conversations_history[user_id][-10:]

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=conversations_history[user_id],
            temperature=0.7,
        )
        reply = completion.choices[0].message.content
        
        # إضافة رد البوت للذاكرة
        conversations_history[user_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logging.error(f"Groq Error: {e}")
        return "معلش يا فندم، حصل ضغط بسيط. ممكن تبعت رسالتك تاني؟"

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
    
    user_id = update.effective_user.id
    user_text = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    reply = await ask_groq(user_id, user_text)
    order = extract_order(reply)
    display_msg = clean_reply(reply)

    await update.message.reply_text(display_msg)

    if order and OWNER_CHAT_ID:
        msg = (f"🛍️ *طلب جديد وصل!*\n\n👤 العميل: {order['name']}\n📱 التليفون: `{order['phone']}`\n"
               f"📍 المحافظة: {order['city']}\n🎁 المنتج: {order['product']}")
        await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=msg, parse_mode="Markdown")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 البوت المطور شغال الآن...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
