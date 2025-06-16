import os
import json
import time
import random
import asyncio
import aiohttp
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path

# Загрузка переменных окружения
load_dotenv()

# Конфигурация из .env
TOKEN = os.getenv('USER_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
RESPONSES_FILE = os.getenv('RESPONSES_FILE', 'responses_realistic.json')

# Константы для антиспама
MIN_DELAY = 15  # минимальная задержка в секундах
MAX_DELAY = 600  # максимальная задержка в секундах (10 минут)
USER_COOLDOWN = 180  # задержка между ответами одному пользователю (3 минуты)
CHANNEL_COOLDOWN = 60  # задержка между сообщениями в канале (1 минута)
FILE_CHECK_INTERVAL = 60  # интервал проверки файла ответов (1 минута)

# Константы для имитации печати
TYPING_SPEED = 0.1  # секунд на символ
TYPING_VARIANCE = 0.05  # случайное отклонение скорости печати
MIN_TYPING_TIME = 1  # минимальное время печати
MAX_TYPING_TIME = 5  # максимальное время печати

class DiscordResponder:
    def __init__(self):
        self.headers = {
            'Authorization': TOKEN,
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Антиспам
        self.last_user_response = {}  # {user_id: timestamp}
        self.last_channel_response = 0  # timestamp
        self.responded_messages = set()  # set of message IDs
        
        # Загрузка ответов
        self.responses = self.load_responses()
        self.last_file_check = time.time()
        
    def load_responses(self):
        """Загрузка ответов из JSON файла"""
        try:
            with open(RESPONSES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading responses: {e}")
            return {}
            
    def check_file_update(self):
        """Проверка обновления файла ответов"""
        current_time = time.time()
        if current_time - self.last_file_check >= FILE_CHECK_INTERVAL:
            self.last_file_check = current_time
            new_responses = self.load_responses()
            if new_responses != self.responses:
                print("Responses file updated, reloading...")
                self.responses = new_responses
                
    def is_working_hours(self):
        """Проверка рабочего времени (08:00 - 22:00)"""
        current_hour = datetime.now().hour
        return 8 <= current_hour < 22
        
    def can_respond_to_user(self, user_id):
        """Проверка возможности ответа пользователю"""
        if user_id not in self.last_user_response:
            return True
        time_since_last = time.time() - self.last_user_response[user_id]
        return time_since_last >= USER_COOLDOWN
        
    def can_respond_to_channel(self):
        """Проверка возможности ответа в канал"""
        time_since_last = time.time() - self.last_channel_response
        return time_since_last >= CHANNEL_COOLDOWN
        
    def find_matching_response(self, content):
        """Поиск подходящего ответа в сообщении"""
        content = content.lower().strip()
        
        # Игнорируем сообщения, которые являются ответами на другие сообщения
        if content.startswith('>'):
            return None
            
        # Проверяем на эмодзи и специальные символы
        if any(char in content for char in ['😂', '😊', '😅', '🤣', '😆']):
            return random.choice(self.responses.get('laugh', [
                "Haha, that's funny! 😄",
                "Lol, good one! 😂",
                "That made me laugh! 😆",
                "Haha, nice! 😅",
                "That's hilarious! 🤣"
            ]))
            
        # Проверяем на вопросы
        if content.endswith('?'):
            if 'why' in content:
                return random.choice(self.responses.get('why', [
                    "That's a good question! Let me think...",
                    "Well, there are a few reasons...",
                    "I think it's because...",
                    "There could be several reasons...",
                    "Let me explain why..."
                ]))
            elif 'how' in content:
                return random.choice(self.responses.get('how', [
                    "Let me explain how...",
                    "Here's how it works...",
                    "I'll tell you how...",
                    "Let me show you how...",
                    "Here's the process..."
                ]))
            elif 'what' in content:
                return random.choice(self.responses.get('what', [
                    "Let me tell you what...",
                    "Here's what I think...",
                    "What I know is...",
                    "Let me explain what...",
                    "Here's what happened..."
                ]))
            else:
                return random.choice(self.responses.get('question', [
                    "That's an interesting question!",
                    "Let me think about that...",
                    "Good question!",
                    "I'll try to answer that...",
                    "Let me explain..."
                ]))
        
        # Проверяем на приветствия
        if any(greeting in content for greeting in ['hi', 'hello', 'hey', 'sup', 'yo']):
            return random.choice(self.responses.get('hi', []))
            
        # Проверяем на прощания
        if any(farewell in content for farewell in ['bye', 'goodbye', 'see you', 'later']):
            return random.choice(self.responses.get('bye', []))
            
        # Проверяем на благодарности
        if any(thanks in content for thanks in ['thanks', 'thank you', 'thx']):
            return random.choice(self.responses.get('thanks', []))
            
        # Проверяем на согласие
        if any(yes in content for yes in ['yes', 'yeah', 'yep', 'sure', 'okay']):
            return random.choice(self.responses.get('yes', []))
            
        # Проверяем на несогласие
        if any(no in content for no in ['no', 'nope', 'nah', 'not really']):
            return random.choice(self.responses.get('no', []))
            
        # Проверяем на неопределенность
        if any(maybe in content for maybe in ['maybe', 'perhaps', 'possibly']):
            return random.choice(self.responses.get('maybe', []))
            
        # Проверяем на эмоции
        if any(emotion in content for emotion in ['happy', 'glad', 'excited']):
            return random.choice(self.responses.get('good', []))
        elif any(emotion in content for emotion in ['sad', 'upset', 'angry']):
            return random.choice(self.responses.get('bad', []))
            
        # Если не нашли подходящего ответа, возвращаем None
        return None

    async def get_user_info(self):
        """Получение информации о пользователе"""
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get('https://discord.com/api/v9/users/@me') as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Failed to get user info: {response.status}")

    async def start_typing(self, channel_id):
        """Начать имитацию печати"""
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.post(f'https://discord.com/api/v9/channels/{channel_id}/typing') as response:
                if response.status != 204:
                    print(f"Failed to start typing: {response.status}")

    async def simulate_typing(self, message_length):
        """Имитация времени печати"""
        # Базовое время печати
        base_time = message_length * TYPING_SPEED
        
        # Добавляем случайное отклонение
        variance = random.uniform(-TYPING_VARIANCE, TYPING_VARIANCE)
        typing_time = base_time * (1 + variance)
        
        # Ограничиваем время печати
        typing_time = max(MIN_TYPING_TIME, min(MAX_TYPING_TIME, typing_time))
        
        return typing_time

    async def send_message(self, channel_id, content, reply_to_message=None):
        """Отправка сообщения с имитацией печати и возможностью ответа на конкретное сообщение"""
        # Начинаем имитацию печати
        await self.start_typing(channel_id)
        
        # Имитируем время печати
        typing_time = await self.simulate_typing(len(content))
        await asyncio.sleep(typing_time)
        
        # Отправляем сообщение
        async with aiohttp.ClientSession(headers=self.headers) as session:
            data = {'content': content}
            
            # Если есть сообщение для ответа, добавляем reference
            if reply_to_message:
                data['message_reference'] = {
                    'message_id': reply_to_message['id'],
                    'channel_id': channel_id,
                    'guild_id': reply_to_message.get('guild_id')
                }
            
            async with session.post(f'https://discord.com/api/v9/channels/{channel_id}/messages', json=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Failed to send message: {response.status} - {error_text}")

    async def process_message(self, message):
        """Обработка входящего сообщения"""
        # Проверяем канал
        if message['channel_id'] != str(CHANNEL_ID):
            return
            
        # Проверяем рабочее время
        if not self.is_working_hours():
            return
            
        # Проверяем антиспам
        if not self.can_respond_to_user(message['author']['id']):
            return
            
        if not self.can_respond_to_channel():
            return
            
        if message['id'] in self.responded_messages:
            return
            
        # Проверяем обновление файла ответов
        self.check_file_update()
        
        # Ищем подходящий ответ
        response = self.find_matching_response(message['content'])
        if not response:
            return
            
        # Генерируем задержку
        delay = random.randint(MIN_DELAY, MAX_DELAY)
        
        # Логируем действие
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
        print(f"User: {message['author']['username']} (ID: {message['author']['id']})")
        print(f"Message: {message['content']}")
        print(f"Matched response: {response}")
        print(f"Delay: {delay} seconds")
        
        # Ждем и отправляем ответ
        await asyncio.sleep(delay)
        await self.send_message(CHANNEL_ID, response, reply_to_message=message)
        
        # Обновляем антиспам
        self.last_user_response[message['author']['id']] = time.time()
        self.last_channel_response = time.time()
        self.responded_messages.add(message['id'])
        
        # Очищаем старые записи
        current_time = time.time()
        self.last_user_response = {k: v for k, v in self.last_user_response.items() 
                                 if current_time - v < USER_COOLDOWN}
        self.responded_messages = {msg_id for msg_id in self.responded_messages 
                                 if current_time - self.last_channel_response < CHANNEL_COOLDOWN}

    async def start(self):
        """Запуск бота"""
        try:
            # Получаем информацию о пользователе
            user_info = await self.get_user_info()
            print(f'Logged in as {user_info["username"]}#{user_info["discriminator"]}')
            print('------')
            
            # Основной цикл
            async with aiohttp.ClientSession(headers=self.headers) as session:
                last_message_id = None
                while True:
                    try:
                        # Получаем последние сообщения
                        async with session.get(f'https://discord.com/api/v9/channels/{CHANNEL_ID}/messages?limit=10') as response:
                            if response.status == 200:
                                messages = await response.json()
                                if messages:
                                    # Обрабатываем только новые сообщения
                                    for message in reversed(messages):
                                        if last_message_id is None:
                                            last_message_id = message['id']
                                            continue
                                            
                                        if message['id'] == last_message_id:
                                            break
                                            
                                        # Игнорируем собственные сообщения
                                        if message['author']['id'] == user_info['id']:
                                            continue
                                            
                                        await self.process_message(message)
                                        
                                    if messages:
                                        last_message_id = messages[0]['id']
                    except Exception as e:
                        print(f"Error processing message: {e}")
                    
                    # Ждем перед следующей проверкой
                    await asyncio.sleep(1)
                    
        except Exception as e:
            print(f"Error: {e}")

async def main():
    bot = DiscordResponder()
    await bot.start()

if __name__ == "__main__":
    asyncio.run(main()) 