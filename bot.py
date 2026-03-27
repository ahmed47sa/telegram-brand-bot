import os
import re
import logging
from groq import Groq
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler

# إعداد الـ Logging لمراقبة الأداء في Railway
logging.basicConfig(level=logging.INFO)

# ===== الإعدادات =====
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID", "")

client = Groq(api_key=GROQ_API_KEY)

# ===== شخصية ندى (Nada Sales) لبراند Eilvost =====
SYSTEM_PROMPT = """
أنتِ "Nada Sales" من براند الملابس المصري "Eilvost".
أسلوبك: بنت مصرية شاطرة، ذكية، ولبقة جداً.

قواعد الرد:
1. أول رد ليكي في أي محادثة لازم يبدأ بـ: "مساء الخير، معاكِ ندى من Eilvost Sales.. نورتنا يا فندم! 🔥"
2. وضحي للعميل إننا عندنا: تيشيرتات (150-250ج)، جينز (350-550ج)، وهوديز (400-650ج).
3. التوصيل بـ 60ج ومجاني لأي طلب فوق الـ 500ج.
4. هدفك تاخدي (الاسم، الموبايل، المحافظة، والمنتج) وتنهي الطلب بالكود ده في آخر رسالة:
   [[ORDER: name=الاسم, phone=الرقم, city=المحافظة, product=المنتج]]

⚠️ خليكي دايماً فاكرة كلام العميل وماتكرريش الترحيب لو المحادثة شغالة.
"""

conversations_history = {}

async def ask_ai(user_id: int, user_message: str) -> str:
    if user_id not in conversations_history:
        conversations_history[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    conversations_history[user_id].append({"role": "user", "content": user_message})
    
    # الذاكرة لآخر 10 رسائل
    if len(conversations_history[user_id]) > 12:
        conversations_history[user_id] = [conversations_history[user_id][0]] + conversations_history[user_id][-10:]

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=conversations_history[user_id],
            temperature=0.7,
        )
        reply = completion.choices[0].message.content
        conversations_history[user_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logging.error(f"Groq Error: {e}")
        return "معلش يا فندم، حصل ضغط بسيط.. ممكن تبعت رسالتك تاني؟"

# دالة الرد على /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # تصفير الذاكرة لبدء محادثة جديدة تماماً
    conversations_history[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    welcome_text = "مساء الخير، معاكِ ندى من Eilvost Sales.. نورتنا يا فندم! 🔥\n\nحابب تشوف كوليكشن التيشيرتات ولا الهوديز النهاردة؟"
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    user_id = update.effective_user.id
    user_text = update.message.text

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    reply = await ask_ai(user_id, user_text)
    
    # تنظيف الرد من كود الأوردر قبل عرضه للعميل
    display_msg = re.sub(r'\[\[ORDER:.*?\]\]', '', reply, flags=re.DOTALL).strip()
    await update.message.reply_text(display_msg)

    # استخراج بيانات الأوردر لإرسالها لصاحب البوت
    pattern = r'\[\[ORDER:\s*name=(.+?),\s*phone=(.+?),\s*city=(.+?),\s*product=(.+?)\]\]'
    match = re.search(pattern, reply)
    if match and OWNER_CHAT_ID:
        order_msg = (f"🛍️ *طلب جديد لـ Eilvost!*\n\n"
                     f"👤 العميل: {match.group(1)}\n"
                     f"📱 التليفون: `{match.group(2)}`\n"
                     f"📍 المحافظة: {match.group(3)}\n"
                     f"🎁 المنتج: {match.group(4)}")
        await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=order_msg, parse_mode="Markdown")

def main():
    if not TELEGRAM_BOT_TOKEN or not GROQ_API_KEY:
        print("❌ تأكد من ضبط الـ Variables في Railway!")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 ندى من Eilvost جاهزة للطلبات...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
