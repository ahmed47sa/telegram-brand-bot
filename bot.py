import os
import re
import httpx
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# ===== إعدادات =====
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID", "")

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

# ===== حفظ المحادثات =====
conversations = {}


async def ask_gemini(user_id: int, user_message: str) -> str:
    if user_id not in conversations:
        conversations[user_id] = []

    conversations[user_id].append({
        "role": "user",
        "parts": [{"text": user_message}]
    })

    if len(conversations[user_id]) > 20:
        conversations[user_id] = conversations[user_id][-20:]

    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": conversations[user_id]
    }

    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
   
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload)
        data = response.json()

        if "error" in data:
            print(f"Gemini Error: {data['error']}")
            return "عذراً، حدث خطأ مؤقت. حاول مرة أخرى 🙏"

        assistant_reply = data["candidates"][0]["content"]["parts"][0]["text"]

        conversations[user_id].append({
            "role": "model",
            "parts": [{"text": assistant_reply}]
        })

        return assistant_reply


def extract_order(text: str) -> dict | None:
    pattern = r'\[\[ORDER:\s*name=([^,]+),\s*phone=([^,]+),\s*city=([^,]+),\s*product=([^\]]+)\]\]'
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
    return re.sub(r'\[\[ORDER:.*?\]\]', '', text, flags=re.DOTALL).strip()


async def notify_owner(app: Application, order: dict, customer_id: int):
    message = f"""🛍️ *طلب جديد!*

👤 *العميل:* {order['name']}
📱 *الهاتف:* `{order['phone']}`
📍 *المحافظة:* {order['city']}
🎁 *المنتج:* {order['product']}

🆔 Telegram ID: `{customer_id}`"""

    await app.bot.send_message(
        chat_id=OWNER_CHAT_ID,
        text=message,
        parse_mode="Markdown"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    gemini_reply = await ask_gemini(user_id, user_message)
    order = extract_order(gemini_reply)
    clean_message = clean_reply(gemini_reply)

    await update.message.reply_text(clean_message)

    if order and OWNER_CHAT_ID:
        await notify_owner(context.application, order, user_id)


def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ البوت شغال مع Gemini!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
