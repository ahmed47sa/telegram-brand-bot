import os
import re
import logging
from groq import Groq
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler

logging.basicConfig(level=logging.INFO)

# ===== الإعدادات =====
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID", "")

client = Groq(api_key=GROQ_API_KEY)

# ===== شخصية ندى (Nada Sales) =====
SYSTEM_PROMPT = """
أنتِ "Nada Sales" من متجر "براندي" للملابس. 
أسلوبك: بنت مصرية، ذكية، لبقة جداً، وودودة. 
أول رد ليكي لازم يكون: "مساء الخير، معاكِ ندى من Brandy Sales.. نورتنا يا فندم! 🔥"
وبعدين اسأليه محتاج يشوف تيشيرتات، جينز، ولا هوديز؟

🛍️ المنتجات: تيشيرتات (150-250ج)، جينز (350-550ج)، هوديز (400-650ج).
📦 التوصيل: 60ج (مجاني فوق 500ج).

🎯 مهمتك:
- جمع بيانات الأوردر (الاسم، الموبايل، المحافظة، المنتج).
- إنهاء الطلب بالكود: [[ORDER: name=الاسم, phone=الرقم, city=المحافظة, product=المنتج]]
"""

conversations_history = {}

async def ask_groq(user_id: int, user_message: str) -> str:
    if user_id not in conversations_history:
        conversations_history[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    conversations_history[user_id].append({"role": "user", "content": user_message})
    
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
        return "منورة يا فندم، بس حصل ضغط بسيط.. ممكن تبعتي رسالتك تاني؟"

# دالة الترحيب (لما يضغط Start أو يبعت HELLO)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # مسح الذاكرة القديمة لبدء محادثة جديدة
    conversations_history[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # الرد الترحيبي الأول
    welcome_text = "مساء الخير، معاكِ ندى من Brandy Sales.. نورتنا يا فندم! 🔥\n\nحابب تشوف كوليكشن التيشيرتات ولا الهوديز النهاردة؟"
    
    # إضافة زرار HELLO عشان يظهر للعميل تحت
    keyboard = [['HELLO']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    user_text = update.message.text
    user_id = update.effective_user.id

    # لو العميل بعت HELLO، نعتبرها كأنها Start ونرحب بيه
    if user_text.upper() == "HELLO":
        await start_command(update, context)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    reply = await ask_groq(user_id, user_text)
    
    # استخراج الأوردر لو موجود
    pattern = r'\[\[ORDER:\s*name=(.+?),\s*phone=(.+?),\s*city=(.+?),\s*product=(.+?)\]\]'
    order_match = re.search(pattern, reply)
    display_msg = re.sub(r'\[\[ORDER:.*?\]\]', '', reply, flags=re.DOTALL).strip()

    await update.message.reply_text(display_msg)

    if order_match and OWNER_CHAT_ID:
        order = {"name": order_match.group(1), "phone": order_match.group(2), "city": order_match.group(3), "product": order_match.group(4)}
        msg = f"🛍️ *طلب جديد لندى!*\n👤 {order['name']}\n📱 `{order['phone']}`\n📍 {order['city']}\n🎁 {order['product']}"
        await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=msg, parse_mode="Markdown")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # التعامل مع /start
    app.add_handler(CommandHandler("start", start_command))
    # التعامل مع الرسايل العادية وكلمة HELLO
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 ندى Sales جاهزة للشغل...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
