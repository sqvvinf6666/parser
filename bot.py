import random
import re
import requests
from bs4 import BeautifulSoup
import telebot
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Токен бота
TOKEN = '8458501671:AAE7wRSsi_F8EKDAW7ajOJCFypqTGaBELMU'  # Ваш токен
bot = telebot.TeleBot(TOKEN, threaded=False)

# Список NFT подарунків
GIFTS = [
    "BDayCandle", "EternalRose", "SharpTongue",
    "SpicedWine", "SnowGlobe", "SantaHat",
    "JellyBunny", "SpyAgaric", "DeskCalendar",
    "LunarSnake", "MagicPotion", "Tamagadget",
    "BerryBox", "JesterHat", "LightSword",
    "BunnyMuffin", "CandyCane", "MiniNotepad",
    "SnakeBox", "VintageCigar"
]

# Кеш для зберігання результатів
cache = {}
CACHE_EXPIRE = 300  # 5 хвилин

def clean_text(text):
    """Экранирование символов для MarkdownV2"""
    if not text:
        return ""
    return re.sub(r'([_*!\[\]()~`>#+\-=|{}\\.\\|])', r'\\\1', text)

def extract_owner_name(soup):
    """Извлечение имени владельца из таблицы характеристик NFT"""
    try:
        owner_label = soup.find(string=re.compile(r'Владелец|Owner', re.IGNORECASE))
        if owner_label:
            owner_name = owner_label.find_next(string=True)
            if owner_name:
                return clean_text(owner_name.strip())

        owner_div = soup.find('div', class_='tgme_page_extra')
        if owner_div:
            return clean_text(owner_div.get_text(strip=True).split('@')[0].strip())

    except Exception as e:
        print(f"Ошибка при парсинге имени владельца: {e}")

    return "Нет имени"

def get_nft_info(gift, nft_id):
    """Получение информации о NFT"""
    url = f"https://t.me/nft/{gift}-{nft_id}"

    if url in cache and time.time() - cache[url]['time'] < CACHE_EXPIRE:
        return cache[url]['data']

    try:
        with requests.Session() as session:
            response = session.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
            })
            soup = BeautifulSoup(response.text, 'html.parser')

            username = None
            profile_link = soup.find('a', href=re.compile(r't.me/(?!nft/)[a-zA-Z0-9_]+$'))
            if profile_link:
                username = profile_link['href'].split('/')[-1]

            owner_name = extract_owner_name(soup)
            gift_escaped = clean_text(gift)
            gift_with_link = f"[{gift_escaped}]({url})"

            data = {
                'gift_with_link': gift_with_link,
                'username': username if username else "N/A",
                'owner_name': owner_name
            }
            cache[url] = {'data': data, 'time': time.time()}
            return data

    except Exception as e:
        print(f"Ошибка парсинга {url}: {str(e)}")
        return None

@bot.message_handler(commands=['start'])
def start(message):
    """Обработчик команды /start"""
    bot.reply_to(message,
                 "👋 *Парсер владельцев NFT* — находим владельцев NFT\n"
                 "🔍 Используйте /parse для поиска",
                 parse_mode='MarkdownV2')

@bot.message_handler(commands=['parse'])
def parse(message):
    """Обработчик команды /parse"""
    progress_msg = bot.send_message(message.chat.id, "🔍 Поиск владельцев NFT...")

    found = []
    attempts = 0
    MAX_ATTEMPTS = 150

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []
        while len(found) < 15 and attempts < MAX_ATTEMPTS:
            attempts += 1
            gift = random.choice(GIFTS)
            nft_id = random.randint(30000, 80000)
            futures.append(executor.submit(get_nft_info, gift, nft_id))

            if attempts % 5 == 0:
                completed = [f.result() for f in as_completed(futures) if f.result() is not None]
                for data in completed:
                    if data['username'] != "N/A" and data not in found:
                        found.append(data)

                bot.edit_message_text(
                    f"⏳ Найдено: {len(found)}/15\n"
                    f"🔎 Проверено: {attempts} NFT",
                    message.chat.id,
                    progress_msg.message_id
                )

    if found:
        result = "👤 *Найденные владельцы NFT:*\n\n"
        for i, item in enumerate(found[:15], 1):
            result += f"{i} {item['gift_with_link']} \| @{clean_text(item['username'])} \| {item['owner_name']}\n"

        bot.send_message(
            message.chat.id,
            result,
            parse_mode='MarkdownV2',
            disable_web_page_preview=True
        )
        bot.delete_message(message.chat.id, progress_msg.message_id)
    else:
        bot.edit_message_text(
            "😕 Не удалось найти активные NFT",
            message.chat.id,
            progress_msg.message_id
        )

if __name__ == '__main__':
    print("🟢 Парсер запущен!")
    bot.infinity_polling()
