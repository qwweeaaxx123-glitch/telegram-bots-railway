import os
import threading
import telebot
from flask import Flask, request

app = Flask(__name__)

# Bot 1 - Currency
from bot import bot as currency_bot

# Bot 2 - Download
from bot2 import bot as download_bot

RAILWAY_URL = os.environ.get("RAILWAY_PUBLIC_DOMAIN")

# Set webhooks if on Railway
if RAILWAY_URL:
    WEBHOOK_URL_1 = f"https://{RAILWAY_URL}/bot1"
    WEBHOOK_URL_2 = f"https://{RAILWAY_URL}/bot2"

    try:
        currency_bot.remove_webhook()
        currency_bot.set_webhook(url=WEBHOOK_URL_1)
        print("Bot 1 webhook set")
    except Exception as e:
        print(f"Bot 1 webhook error: {e}")

    try:
        download_bot.remove_webhook()
        download_bot.set_webhook(url=WEBHOOK_URL_2)
        print("Bot 2 webhook set")
    except Exception as e:
        print(f"Bot 2 webhook error: {e}")

@app.route('/')
def home():
    return "Telegram Bots Running!"

@app.route('/bot1', methods=['POST'])
def webhook_bot1():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        currency_bot.process_new_updates([update])
        return 'OK', 200
    return 'Bad Request', 400

@app.route('/bot2', methods=['POST'])
def webhook_bot2():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        download_bot.process_new_updates([update])
        return 'OK', 200
    return 'Bad Request', 400

def run_polling():
    """Fallback polling if not on Railway"""
    if not RAILWAY_URL:
        def run_bot1():
            print("Starting Bot 1 (Currency)...")
            currency_bot.polling(none_stop=True, interval=1)
        def run_bot2():
            print("Starting Bot 2 (Download)...")
            download_bot.polling(none_stop=True, interval=1)

        t1 = threading.Thread(target=run_bot1, daemon=True)
        t2 = threading.Thread(target=run_bot2, daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

if __name__ == '__main__':
    if RAILWAY_URL:
        # Railway mode - use webhook via Flask
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
    else:
        # Local/Replit mode - use polling
        run_polling()
