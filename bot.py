import os
import json
import re
import httpx
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# ===== إعدادات - غير القيم دي بس =====
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")
OWNER_CHAT_ID = os.environ.get("OWNER_CHAT_ID", "")  # الـ chat_id بتاعك

# ===== شخصية البوت وبيانات البراند =====
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
2. لو العميل أبدى رغبة في الشراء أو طلب التوصيل أو طلب التواصل:
   - اطلب منه: الاسم الكامل، رقم الهاتف، المحافظة، والمنتج المطلوب
   - بعد ما يبعتهم، قوله: "شكراً! سيتواصل معك فريقنا خلال ساعات قليلة 🎉"
   - وضيف في آخر ردك هذا التنسيق بالضبط (مش هيظهر للعميل):
     [[ORDER: name=الاسم, phone=الرقم, city=المحافظة, product=المنتج]]

ملاحظة: لو العميل بعت بيانات ناقصة، اطلب المعلومة الناقصة بس.
"""

# ===== حفظ محادثات العملاء في الذاكرة =====
conversations = {}


async def ask_claude(user_id: int, user_message: str) -> str:
    """بعت الرسالة لـ Claude وارجع الرد"""
    
    # احفظ سجل المحادثة لكل عميل
    if user_id not in conversations:
        conversations[user_id] = []
    
    conversations[user_id].append({
        "role": "user",
        "content": user_message
    })
    
    # خلي السجل ما يعديش 20 رسالة عشان ما تزيدش التكلفة
    if len(conversations[user_id]) > 20:
        conversations[user_id] = conversations[user_id][-20:]
    
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5-20251001",  # الأرخص والأسرع
                "max_tokens": 500,
                "system": SYSTEM_PROMPT,
                "messages": conversations[user_id]
            }
        )
        
        data = response.json()
        assistant_reply = data["content"][0]["text"]
        
        # احفظ رد Claude في السجل
        conversations[user_id].append({
            "role": "assistant",
            "content": assistant_reply
        })
        
        return assistant_reply


def extract_order(text: str) -> dict | None:
    """استخرج بيانات الطلب من رد Claude لو موجودة"""
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
    """شيل الـ ORDER tag من الرسالة قبل ما تتبعت للعميل"""
    return re.sub(r'\[\[ORDER:.*?\]\]', '', text, flags=re.DOTALL).strip()


async def notify_owner(app: Application, order: dict, customer_name: str, customer_id: int):
    """ابعت إشعار لصاحب المتجر"""
    message = f"""🛍️ *طلب جديد!*

👤 *العميل:* {order['name']}
📱 *الهاتف:* `{order['phone']}`
📍 *المحافظة:* {order['city']}
🎁 *المنتج:* {order['product']}

🆔 Telegram ID: `{customer_id}`
"""
    await app.bot.send_message(
        chat_id=OWNER_CHAT_ID,
        text=message,
        parse_mode="Markdown"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """المعالج الرئيسي لكل رسالة"""
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # أرسل "جاري الكتابة..."
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )
    
    # اسأل Claude
    claude_reply = await ask_claude(user_id, user_message)
    
    # شوف لو في طلب في الرد
    order = extract_order(claude_reply)
    
    # ابعت الرد للعميل (بدون الـ tag)
    clean_message = clean_reply(claude_reply)
    await update.message.reply_text(clean_message)
    
    # لو في طلب، ابعت إشعار لصاحب المتجر
    if order and OWNER_CHAT_ID:
        await notify_owner(context.application, order, update.effective_user.first_name, user_id)


def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ البوت شغال!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
