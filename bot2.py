import os
import re
import time
import telebot
from telebot import types
import yt_dlp
import tempfile
import requests
import instaloader

BOT2_TOKEN = os.environ.get("BOT2_TOKEN")
bot = telebot.TeleBot(BOT2_TOKEN)

SUPPORTED = ["youtube.com", "youtu.be", "tiktok.com", "twitter.com", "x.com", "facebook.com"]

def is_supported_non_ig(url):
    return any(site in url.lower() for site in SUPPORTED)

def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("تحميل فيديو 🎬"),
        types.KeyboardButton("تحميل صوت فقط 🎵"),
        types.KeyboardButton("معلومات حساب انستغرام 📊")
    )
    return markup

user_temp_data = {}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        "أهلاً! 👋\nأنا بوت تحميل الفيديوهات.\n\n"
        "أقدر أحمّل من:\n"
        "🎬 YouTube\n🎵 TikTok\n🐦 Twitter / X\n📘 Facebook\n"
        "ومعلومات حسابات إنستغرام 👤\n\n"
        "اختر من الأزرار 👇",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda m: m.text in ["تحميل فيديو 🎬", "تحميل صوت فقط 🎵"])
def ask_for_link(message):
    mode = "video" if "فيديو" in message.text else "audio"
    bot.send_message(message.chat.id, "أرسل الرابط 👇", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, lambda m: handle_download(m, mode))

@bot.message_handler(func=lambda m: m.text == "معلومات حساب انستغرام 📊")
def ask_ig_username(message):
    bot.send_message(
        message.chat.id,
        "أرسل يوزرنيم الحساب أو رابطه 👇\n"
        "مثال: cristiano\n"
        "أو: https://instagram.com/cristiano\n\n"
        "ملاحظة: الحساب يجب أن يكون عام — الحسابات الخاصة ما تتم العمل معها.",
        reply_markup=types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(message, show_ig_profile)

def get_instaloader():
    L = instaloader.Instaloader(
        download_pictures=True, download_videos=True,
        download_video_thumbnails=False, download_geotags=False,
        download_comments=False, save_metadata=False,
        compress_json=False, quiet=True,
        request_timeout=15
    )
    return L

def fetch_ig_with_login(username, password, target_username):
    """Use instaloader with login to fetch profile info"""
    L = get_instaloader()
    try:
        L.login(username, password)
        time.sleep(3)
        profile = instaloader.Profile.from_username(L.context, target_username)
        return {
            "full_name": profile.full_name or target_username,
            "username": target_username,
            "followers": profile.followers,
            "following": profile.followees,
            "posts": profile.mediacount,
            "biography": profile.biography or "لا يوجد",
            "is_private": profile.is_private,
            "is_verified": profile.is_verified,
            "pic_url": str(profile.profile_pic_url),
        }
    except Exception as e:
        print(f"Login fetch error: {e}")
        return None

def fetch_ig_anonymous(username):
    """Try to fetch profile without login (rarely works from server IPs)"""
    headers = {
        "x-ig-app-id": "936619743392459",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "*/*", "Referer": "https://www.instagram.com/",
    }
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            user = data.get("data", {}).get("user")
            if user:
                return {
                    "full_name": user.get("full_name") or username,
                    "username": username,
                    "followers": user.get("edge_followed_by", {}).get("count", 0),
                    "following": user.get("edge_follow", {}).get("count", 0),
                    "posts": user.get("edge_owner_to_timeline_media", {}).get("count", 0),
                    "biography": user.get("biography") or "لا يوجد",
                    "is_private": user.get("is_private", False),
                    "is_verified": user.get("is_verified", False),
                    "pic_url": user.get("profile_pic_url_hd") or user.get("profile_pic_url", ""),
                }
    except Exception as e:
        print(f"Anonymous fetch error: {e}")
    return None

def show_ig_profile(message):
    text = message.text.strip()
    if "instagram.com/" in text:
        username = text.rstrip("/").split("/")[-1].split("?")[0]
    else:
        username = text.lstrip("@")

    wait_msg = bot.send_message(message.chat.id, "⏳ جاري جلب معلومات الحساب...")

    # Try anonymous first
    user_data = fetch_ig_anonymous(username)

    if not user_data:
        bot.delete_message(message.chat.id, wait_msg.message_id)
        bot.send_message(
            message.chat.id,
            "⚠️ تعذّر جلب معلومات الحساب.\n\n"
            "ذلك بسبب حظر إنستغرام للسيرفرات.\n"
            "إذا عندك حساب إنستغرام ثانوي يمكنني استخدامه للدخول، أرسله بالشكل:\n\n"
            "يوزرنيم الحساب الثانوي: ...\n"
            "باسورد الحساب الثانوي: ...",
            reply_markup=main_menu()
        )
        # Store context for next message
        user_temp_data[message.chat.id] = {"action": "ig_login", "target": username}
        return

    # Build response
    followers = f"{user_data['followers']:,}"
    following = f"{user_data['following']:,}"
    posts = f"{user_data['posts']:,}"
    name = user_data["full_name"]
    bio = user_data["biography"]
    is_private = user_data["is_private"]
    is_verified = user_data["is_verified"]
    pic_url = user_data["pic_url"]

    status = "🔒 خاص" if is_private else "🌍 عام"
    verified = "✅ موثّق" if is_verified else ""

    info_text = (
        f"👤 {name} (@{username}) {verified}\n"
        f"{status}\n\n"
        f"👥 المتابعون: {followers}\n"
        f"➡️ يتابع: {following}\n"
        f"🖼 المنشورات: {posts}\n\n"
        f"📝 البايو:\n{bio}"
    )

    bot.delete_message(message.chat.id, wait_msg.message_id)
    try:
        pic_response = requests.get(pic_url, timeout=10)
        bot.send_photo(message.chat.id, pic_response.content, caption=info_text)
    except:
        bot.send_message(message.chat.id, info_text)

    bot.send_message(message.chat.id, "اختر من الأزرار 👇", reply_markup=main_menu())

@bot.message_handler(func=lambda m: user_temp_data.get(m.chat.id, {}).get("action") == "ig_login")
def handle_ig_login_credentials(message):
    text = message.text.strip()
    parts = text.split(":", 1)
    if len(parts) != 2:
        bot.send_message(
            message.chat.id,
            "❌ الصيغة غير صحيحة.\n"
            "أرسل بالصيغة:\n"
            "يوزرنيم الحساب الثانوي: ...\n"
            "باسورد الحساب الثانوي: ...",
            reply_markup=main_menu()
        )
        return

    username = parts[0].strip()
    password = parts[1].strip()
    target = user_temp_data[message.chat.id]["target"]

    wait_msg = bot.send_message(message.chat.id, f"⏳ جاري الدخول بحساب: {username} وجلب معلومات {target}...")

    user_data = fetch_ig_with_login(username, password, target)

    if not user_data:
        bot.delete_message(message.chat.id, wait_msg.message_id)
        bot.send_message(
            message.chat.id,
            "❌ تعذّر الدخول أو جلب المعلومات.\n"
            "قد يكون السبب:\n"
            "• الباسورد خاطئة\n"
            "• إنستغرام طلب تأكيد على الجوال (checkpoint)\n"
            "• الحساب الثانوي حاص\n\n"
            "احمل تطبيق Instagram وافتح التحقيق إذا ظهر لك، ثم حاول مرة.",
            reply_markup=main_menu()
        )
        del user_temp_data[message.chat.id]
        return

    # Success
    followers = f"{user_data['followers']:,}"
    following = f"{user_data['following']:,}"
    posts = f"{user_data['posts']:,}"
    name = user_data["full_name"]
    bio = user_data["biography"]
    is_private = user_data["is_private"]
    is_verified = user_data["is_verified"]
    pic_url = user_data["pic_url"]

    status = "🔒 خاص" if is_private else "🌍 عام"
    verified = "✅ موثّق" if is_verified else ""

    info_text = (
        f"👤 {name} (@{target}) {verified}\n"
        f"{status}\n\n"
        f"👥 المتابعون: {followers}\n"
        f"➡️ يتابع: {following}\n"
        f"🖼 المنشورات: {posts}\n\n"
        f"📝 البايو:\n{bio}"
    )

    bot.delete_message(message.chat.id, wait_msg.message_id)
    try:
        pic_response = requests.get(pic_url, timeout=10)
        bot.send_photo(message.chat.id, pic_response.content, caption=info_text)
    except:
        bot.send_message(message.chat.id, info_text)

    del user_temp_data[message.chat.id]
    bot.send_message(message.chat.id, "اختر من الأزرار 👇", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text in ["تحميل فيديو 🎬", "تحميل صوت فقط 🎵"])
def ask_for_link_direct(message):
    mode = "video" if "فيديو" in message.text else "audio"
    bot.send_message(message.chat.id, "أرسل الرابط 👇", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, lambda m: handle_download(m, mode))

def handle_download(message, mode):
    url = message.text.strip()

    if not url.startswith("http"):
        bot.send_message(message.chat.id, "الرابط غير صحيح، تأكد منه وحاول.", reply_markup=main_menu())
        return

    wait_msg = bot.send_message(message.chat.id, "⏳ جاري التحميل، انتظر قليلاً...")

    is_instagram = "instagram.com" in url.lower()
    is_tiktok = "tiktok.com" in url.lower()

    # Instagram & TikTok are blocked from this server IP
    if is_instagram or is_tiktok:
        bot.delete_message(message.chat.id, wait_msg.message_id)
        platform = "إنستغرام" if is_instagram else "تيك توك"
        bot.send_message(
            message.chat.id,
            f"⚠️ عذراً، {platform} محظور من السيرفر الحالي.\n\n"
            "المنصات المدعومة الحالية:\n"
            "🎬 YouTube\n"
            "🐦 Twitter / X\n"
            "📘 Facebook\n\n"
            "للحصول على إنستغرام وتيك توك، \n"
            "يلزم استخدام إعداد إضافي (Proxy أو API مدفوع).",
            reply_markup=main_menu()
        )
        return

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            if mode == "audio":
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': f'{tmpdir}/%(title)s.%(ext)s',
                    'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
                    'quiet': True,
                }
            else:
                ydl_opts = {
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    'outtmpl': f'{tmpdir}/%(title)s.%(ext)s',
                    'merge_output_format': 'mp4',
                    'quiet': True,
                }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'ملف')

            files = [f for f in os.listdir(tmpdir) if not f.endswith(('.json', '.txt', '.xz'))]
            if not files:
                raise Exception("لم يتم تحميل أي ملف")

            bot.delete_message(message.chat.id, wait_msg.message_id)

            for filename in sorted(files):
                filepath = os.path.join(tmpdir, filename)
                if os.path.getsize(filepath) > 50 * 1024 * 1024:
                    bot.send_message(message.chat.id, f"⚠️ الملف أكبر من 50MB، تعذّر إرساله.")
                    continue
                ext = filename.rsplit('.', 1)[-1].lower()
                with open(filepath, 'rb') as f:
                    if mode == "audio" and ext == "mp3":
                        bot.send_audio(message.chat.id, f, title=title, reply_markup=main_menu())
                    elif ext in ['jpg', 'jpeg', 'png', 'webp']:
                        bot.send_photo(message.chat.id, f, caption=f"📸 {title}")
                    else:
                        bot.send_video(message.chat.id, f, caption=f"🎬 {title}", reply_markup=main_menu())

            bot.send_message(message.chat.id, "✅ تم!", reply_markup=main_menu())

    except Exception as e:
        err = str(e)
        print(f"Download error: {err}")
        try:
            bot.delete_message(message.chat.id, wait_msg.message_id)
        except:
            pass
        bot.send_message(
            message.chat.id,
            "❌ تعذّر التحميل. تأكد من الرابط وأن المحتوى عام.",
            reply_markup=main_menu()
        )

@bot.message_handler(func=lambda m: True)
def fallback(message):
    bot.send_message(message.chat.id, "اختر من الأزرار 👇", reply_markup=main_menu())

print("Download bot loaded")

if __name__ == "__main__":
    bot.polling()
