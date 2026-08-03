import requests
from bs4 import BeautifulSoup
import telebot
import os
import random
import openai
import feedparser
import json
from datetime import datetime

# گرفتن اطلاعات از محیط (Secrets)
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

bot = telebot.TeleBot(BOT_TOKEN)
openai.api_key = OPENAI_API_KEY

# فایل برای ذخیره رسیپی‌های قبلی
HISTORY_FILE = 'sent_recipes.json'

def load_history():
    """بارگذاری تاریخچه رسیپی‌های ارسال شده"""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return []

def save_history(history):
    """ذخیره تاریخچه رسیپی‌های ارسال شده"""
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)

def get_recipe_from_web():
    """گرفتن رسیپی از یک سایت معروف (مثال: Tasty)"""
    try:
        # استفاده از RSS feed سایت Tasty
        url = "https://tasty.co/feed"
        feed = feedparser.parse(url)
        
        # انتخاب یک رسیپی تصادفی
        entries = feed.entries
        random_entry = random.choice(entries)
        
        # استخراج اطلاعات
        title = random_entry.title
        link = random_entry.link
        
        # گرفتن جزئیات از صفحه
        response = requests.get(link)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # پیدا کردن مواد اولیه
        ingredients = []
        ingredient_items = soup.find_all('li', class_='ingredient-item')
        for item in ingredient_items[:10]:  # حداکثر 10 ماده
            ingredient = item.get_text(strip=True)
            if ingredient:
                ingredients.append(ingredient)
        
        # پیدا کردن دستورالعمل‌ها
        instructions = []
        instruction_steps = soup.find_all('li', class_='instruction-item')
        for step in instruction_steps[:8]:  # حداکثر 8 مرحله
            instruction = step.get_text(strip=True)
            if instruction:
                instructions.append(instruction)
        
        # پیدا کردن عکس
        image_url = None
        image_tag = soup.find('meta', property='og:image')
        if image_tag:
            image_url = image_tag.get('content')
        
        return {
            'title': title,
            'link': link,
            'ingredients': ingredients,
            'instructions': instructions,
            'image_url': image_url
        }
    except Exception as e:
        print(f"خطا در گرفتن رسیپی: {e}")
        return None

def translate_to_persian(text):
    """ترجمه متن به فارسی با استفاده از OpenAI"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a translator. Translate the following text to Persian (Farsi) accurately."},
                {"role": "user", "content": text}
            ],
            max_tokens=500,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"خطا در ترجمه: {e}")
        return text

def rewrite_recipe(recipe_data):
    """بازنویسی رسیپی با هوش مصنوعی به صورت جذاب"""
    try:
        prompt = f"""
        یک دستور پخت جذاب و حرفه‌ای برای غذا زیر بنویس به فارسی:
        
        عنوان: {recipe_data['title']}
        
        مواد اولیه:
        {', '.join(recipe_data['ingredients'])}
        
        دستورالعمل:
        {' '.join(recipe_data['instructions'])}
        
        لطفاً به صورت زیر بنویس:
        - یک مقدمه جذاب
        - مواد لازم به صورت لیست
        - طرز تهیه مرحله‌به‌مرحله
        - نکات طلایی
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a professional chef and food writer. Write in Persian."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=800,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"خطا در بازنویسی: {e}")
        return None

def download_image(image_url):
    """دانلود عکس و ذخیره موقت"""
    if not image_url:
        return None
    
    try:
        response = requests.get(image_url, timeout=10)
        if response.status_code == 200:
            image_path = f"recipe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            with open(image_path, 'wb') as f:
                f.write(response.content)
            return image_path
    except Exception as e:
        print(f"خطا در دانلود عکس: {e}")
    return None

def send_to_telegram(message, image_path=None):
    """ارسال به کانال تلگرام"""
    try:
        if image_path and os.path.exists(image_path):
            # ارسال با عکس
            with open(image_path, 'rb') as photo:
                bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=photo,
                    caption=message,
                    parse_mode='HTML'
                )
            os.remove(image_path)  # پاک کردن فایل موقت
        else:
            # ارسال فقط متن
            bot.send_message(
                chat_id=CHANNEL_ID,
                text=message,
                parse_mode='HTML'
            )
        return True
    except Exception as e:
        print(f"خطا در ارسال به تلگرام: {e}")
        return False

def main():
    print(f"شروع اجرا در: {datetime.now()}")
    
    # بارگذاری تاریخچه
    history = load_history()
    
    # تلاش برای گرفتن رسیپی جدید
    max_attempts = 5
    for attempt in range(max_attempts):
        recipe = get_recipe_from_web()
        
        if not recipe:
            print(f"تلاش {attempt + 1} ناموفق بود")
            continue
        
        # بررسی تکراری نبودن
        if recipe['title'] in history:
            print("این رسیپی قبلاً ارسال شده، تلاش مجدد...")
            continue
        
        # ترجمه و بازنویسی
        print("در حال بازنویسی رسیپی...")
        persian_recipe = rewrite_recipe(recipe)
        
        if not persian_recipe:
            # اگر بازنویسی ناموفق بود، از ترجمه ساده استفاده کن
            print("بازنویسی ناموفق، استفاده از ترجمه ساده...")
            translated_title = translate_to_persian(recipe['title'])
            persian_recipe = f"🍳 {translated_title}\n\n"
            persian_recipe += "مواد لازم:\n"
            for ing in recipe['ingredients']:
                persian_recipe += f"• {ing}\n"
            persian_recipe += "\nطرز تهیه:\n"
            for i, step in enumerate(recipe['instructions'], 1):
                persian_recipe += f"{i}. {step}\n"
        
        # اضافه کردن منبع
        persian_recipe += f"\n\n📎 منبع: {recipe['link']}"
        
        # دانلود عکس
        print("در حال دانلود عکس...")
        image_path = download_image(recipe['image_url'])
        
        # ارسال به تلگرام
        print("در حال ارسال به تلگرام...")
        success = send_to_telegram(persian_recipe, image_path)
        
        if success:
            # ذخیره در تاریخچه
            history.append(recipe['title'])
            save_history(history)
            print("✅ رسیپی با موفقیت ارسال شد!")
            break
        else:
            print("❌ ارسال ناموفق بود")
    
    print(f"پایان اجرا در: {datetime.now()}")

if __name__ == "__main__":
    main()
