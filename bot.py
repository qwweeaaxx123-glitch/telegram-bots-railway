import os
import telebot
from telebot import types
import requests

BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_KEY = os.environ.get("EXCHANGE_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)

user_data = {}

CURRENCIES = ["USD", "IQD", "EUR", "SAR", "KWD", "AED", "GBP", "TRY"]

def get_exchange_rate(base, target):
    try:
        url = f"https://v6.exchangerate-api.com/v6/{API_KEY}/pair/{base}/{target}"
        response = requests.get(url)
        data = response.json()
        if data['result'] == 'success':
            return data['conversion_rate']
    except Exception as e:
        print(f"Error: {e}")
    return None

def currency_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=4)
    buttons = [types.KeyboardButton(c) for c in CURRENCIES]
    markup.add(*buttons)
    return markup

def remove_keyboard():
    return types.ReplyKeyboardRemove()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_data[message.chat.id] = {}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("تحويل عملة 💱"))
    bot.send_message(
        message.chat.id,
        "أهلاً! 👋\nأنا بوت تحويل العملات.\nاضغط الزر أدناه للبدء:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "تحويل عملة 💱")
def start_conversion(message):
    user_data[message.chat.id] = {"step": "base"}
    bot.send_message(
        message.chat.id,
        "اختر العملة اللي عندك 👇",
        reply_markup=currency_keyboard()
    )

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get("step") == "base")
def get_base_currency(message):
    currency = message.text.strip().upper()
    if currency not in CURRENCIES:
        bot.send_message(message.chat.id, "اختر عملة من الأزرار 👇", reply_markup=currency_keyboard())
        return
    user_data[message.chat.id]["base"] = currency
    user_data[message.chat.id]["step"] = "target"
    bot.send_message(
        message.chat.id,
        f"زين ✅\nالآن اختر العملة اللي تريد تحول إليها 👇",
        reply_markup=currency_keyboard()
    )

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get("step") == "target")
def get_target_currency(message):
    currency = message.text.strip().upper()
    if currency not in CURRENCIES:
        bot.send_message(message.chat.id, "اختر عملة من الأزرار 👇", reply_markup=currency_keyboard())
        return
    base = user_data[message.chat.id]["base"]
    if currency == base:
        bot.send_message(message.chat.id, "اختر عملة مختلفة عن الأولى 😅", reply_markup=currency_keyboard())
        return
    user_data[message.chat.id]["target"] = currency
    user_data[message.chat.id]["step"] = "amount"
    bot.send_message(
        message.chat.id,
        f"كم المبلغ بـ {base}؟ اكتبه بالأرقام 👇",
        reply_markup=remove_keyboard()
    )

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get("step") == "amount")
def get_amount(message):
    try:
        amount = float(message.text.strip().replace(",", ""))
    except ValueError:
        bot.send_message(message.chat.id, "الرجاء كتابة رقم صحيح فقط، مثل: 100")
        return

    base = user_data[message.chat.id]["base"]
    target = user_data[message.chat.id]["target"]
    rate = get_exchange_rate(base, target)

    if rate:
        result = amount * rate
        bot.send_message(
            message.chat.id,
            f"💰 {amount:,.2f} {base}\n⬇️\n💵 {result:,.2f} {target}",
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(
                types.KeyboardButton("تحويل عملة 💱")
            )
        )
    else:
        bot.send_message(message.chat.id, "صار خطأ، حاول مرة ثانية.")

    user_data[message.chat.id] = {}

@bot.message_handler(func=lambda m: True)
def fallback(message):
    user_data[message.chat.id] = {}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("تحويل عملة 💱"))
    bot.send_message(message.chat.id, "اضغط الزر للبدء 👇", reply_markup=markup)

print("Currency bot loaded")
