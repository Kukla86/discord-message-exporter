import os
import json
import asyncio
import aiohttp
import csv
from datetime import datetime
from dotenv import load_dotenv
from jinja2 import Template
from typing import Optional, List, Dict, Any, Union
from pathlib import Path

# Загрузка переменных окружения
load_dotenv()

# Используем USER_TOKEN вместо DISCORD_TOKEN
token = os.getenv('USER_TOKEN')
if not token:
    raise ValueError("User token not found. Please set USER_TOKEN in .env file")

class DiscordExporter:
    def __init__(self, output_format: str = 'json', output_dir: str = 'exports'):
        self.token = token
        self.output_format = output_format.lower()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.exported_files = []
        self.headers = {
            'Authorization': self.token,  # Используем токен напрямую
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': 'https://discord.com',
            'Referer': 'https://discord.com/channels/@me'
        }

    async def get_user_info(self):
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get('https://discord.com/api/v9/users/@me') as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Failed to get user info: {response.status}")

    async def get_guilds(self):
        async with aiohttp.ClientSession(headers=self.headers) as session:
            async with session.get('https://discord.com/api/v9/users/@me/guilds') as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"Failed to get guilds: {response.status}")

    async def get_channel_messages(self, channel_id: int, limit: int = 100, before: Optional[str] = None, after: Optional[str] = None):
        messages = []
        total_requests = 0
        max_requests = 50  # Максимальное количество запросов (50 * 100 = 5000 сообщений)
        
        async with aiohttp.ClientSession(headers=self.headers) as session:
            while len(messages) < limit and total_requests < max_requests:
                # Каждый запрос получает максимум 100 сообщений
                params = {'limit': 100}  # Discord ограничивает 100 сообщениями за запрос
                if before:
                    params['before'] = before  # Используем ID последнего сообщения для получения более старых сообщений
                if after:
                    params['after'] = after

                url = f'https://discord.com/api/v9/channels/{channel_id}/messages'
                
                try:
                    print(f"\nЗапрос #{total_requests + 1}: Получаем следующие 100 сообщений...")
                    async with session.get(url, params=params) as response:
                        if response.status == 200:
                            new_messages = await response.json()
                            if not new_messages:
                                print("Больше сообщений нет")
                                break
                                
                            messages.extend(new_messages)
                            total_requests += 1
                            print(f"✓ Получено {len(new_messages)} сообщений в этом запросе")
                            print(f"  Всего получено: {len(messages)} из {limit} сообщений")
                            
                            if len(new_messages) < 100:
                                print("Достигнут конец истории сообщений")
                                break
                                
                            before = new_messages[-1]['id']  # Сохраняем ID последнего сообщения для следующего запроса
                            
                            # Добавляем небольшую задержку между запросами
                            await asyncio.sleep(0.5)
                        else:
                            error_text = await response.text()
                            raise Exception(f"Failed to get messages: {response.status} - {error_text}")
                except Exception as e:
                    print(f"Ошибка при получении сообщений: {e}")
                    break
                    
        print(f"\nЭкспорт завершен. Всего получено {len(messages)} сообщений за {total_requests} запросов.")
        return messages

    async def export_channel(self, channel_id: int):
        try:
            print(f"Пытаемся получить доступ к каналу {channel_id}")
            
            # Спрашиваем параметры экспорта
            limit_input = input("Введите лимит сообщений (Enter для максимального количества - 5000): ").strip()
            limit = int(limit_input) if limit_input else 5000  # По умолчанию 5000 сообщений
            
            before = input("Введите дату начала (YYYY-MM-DD, Enter для пропуска): ").strip()
            before = datetime.strptime(before, "%Y-%m-%d").isoformat() if before else None
            
            after = input("Введите дату окончания (YYYY-MM-DD, Enter для пропуска): ").strip()
            after = datetime.strptime(after, "%Y-%m-%d").isoformat() if after else None

            print(f"\nНачинаем экспорт до {limit} сообщений...")
            messages = await self.get_channel_messages(channel_id, limit, before, after)
            print(f"Экспорт завершен. Всего экспортировано {len(messages)} сообщений.")

            # Экспортируем в выбранный формат
            if self.output_format == 'json':
                self._export_json(messages, channel_id)
            elif self.output_format == 'html':
                self._export_html(messages, channel_id)
            elif self.output_format == 'txt':
                self._export_txt(messages, channel_id)
            elif self.output_format == 'csv':
                self._export_csv(messages, channel_id)
            else:
                print(f"Неподдерживаемый формат: {self.output_format}")

        except Exception as e:
            print(f"Ошибка при экспорте: {e}")

    def _export_json(self, messages: List[Dict], channel_id: int):
        output_file = self.output_dir / f'channel_{channel_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
        self.exported_files.append(output_file)
        print(f"Экспорт в JSON завершён: {output_file}")

    def _export_html(self, messages: List[Dict], channel_id: int):
        template = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Discord Chat Export - Channel {{ channel_id }}</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; background: #36393f; color: #dcddde; }
                .message { margin-bottom: 20px; padding: 10px; border-bottom: 1px solid #2f3136; }
                .author { font-weight: bold; color: #7289da; }
                .timestamp { color: #72767d; font-size: 0.8em; }
                .content { margin: 5px 0; }
                .attachment { color: #7289da; }
                .embed { background: #2f3136; border-left: 4px solid #7289da; padding: 10px; margin: 5px 0; }
                .reaction { display: inline-block; margin: 0 5px; }
                .pinned { color: #faa61a; }
            </style>
        </head>
        <body>
            <h1>Экспорт чата: Channel {{ channel_id }}</h1>
            {% for message in messages %}
            <div class="message">
                <div class="author">{{ message.author.username }}</div>
                <div class="timestamp">{{ message.timestamp }}</div>
                {% if message.content %}
                <div class="content">{{ message.content }}</div>
                {% endif %}
                {% if message.attachments %}
                <div class="attachments">
                    {% for attachment in message.attachments %}
                    <div class="attachment">📎 <a href="{{ attachment.url }}">{{ attachment.filename }}</a></div>
                    {% endfor %}
                </div>
                {% endif %}
                {% if message.embeds %}
                <div class="embeds">
                    {% for embed in message.embeds %}
                    <div class="embed">
                        {% if embed.title %}
                        <div class="embed-title">{{ embed.title }}</div>
                        {% endif %}
                        {% if embed.description %}
                        <div class="embed-description">{{ embed.description }}</div>
                        {% endif %}
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
                {% if message.reactions %}
                <div class="reactions">
                    {% for reaction in message.reactions %}
                    <span class="reaction">{{ reaction.emoji.name }} {{ reaction.count }}</span>
                    {% endfor %}
                </div>
                {% endif %}
                {% if message.pinned %}
                <div class="pinned">📌 Закреплено</div>
                {% endif %}
            </div>
            {% endfor %}
        </body>
        </html>
        """
        output_file = self.output_dir / f'channel_{channel_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(Template(template).render(messages=messages, channel_id=channel_id))
        self.exported_files.append(output_file)
        print(f"Экспорт в HTML завершён: {output_file}")

    def _export_txt(self, messages: List[Dict], channel_id: int):
        output_file = self.output_dir / f'channel_{channel_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Экспорт чата: Channel {channel_id}\n")
            f.write("=" * 50 + "\n\n")
            for message in messages:
                f.write(f"[{message['timestamp']}] {message['author']['username']}:\n")
                if message['content']:
                    f.write(f"{message['content']}\n")
                if message['attachments']:
                    for attachment in message['attachments']:
                        f.write(f"[Вложение: {attachment['filename']}]\n")
                if message['embeds']:
                    f.write("[Эмбеды]\n")
                f.write("\n")
        self.exported_files.append(output_file)
        print(f"Экспорт в TXT завершён: {output_file}")

    def _export_csv(self, messages: List[Dict], channel_id: int):
        output_file = self.output_dir / f'channel_{channel_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'Author', 'Content', 'Attachments', 'Embeds', 'Reactions'])
            for message in messages:
                writer.writerow([
                    message['timestamp'],
                    message['author']['username'],
                    message['content'],
                    len(message.get('attachments', [])),
                    len(message.get('embeds', [])),
                    len(message.get('reactions', []))
                ])
        self.exported_files.append(output_file)
        print(f"Экспорт в CSV завершён: {output_file}")

async def main():
    print("Выберите формат экспорта:")
    print("1. JSON")
    print("2. HTML")
    print("3. TXT")
    print("4. CSV")
    format_choice = input("Выберите формат (1-4): ").strip()
    
    format_map = {
        "1": "json",
        "2": "html",
        "3": "txt",
        "4": "csv"
    }
    
    if format_choice not in format_map:
        print("Неверный выбор формата!")
        return
        
    output_format = format_map[format_choice]
    exporter = DiscordExporter(output_format=output_format)
    
    # Получаем информацию о пользователе
    try:
        user_info = await exporter.get_user_info()
        print(f"Вошли как {user_info['username']}#{user_info['discriminator']}")
        print(f"ID пользователя: {user_info['id']}")
        
        # Получаем список серверов
        guilds = await exporter.get_guilds()
        print(f"Доступные серверы: {[guild['name'] for guild in guilds]}")
        
        # Спрашиваем пользователя, что он хочет экспортировать
        print("\nЧто вы хотите экспортировать?")
        print("1. Канал")
        print("2. Категорию")
        print("3. Весь сервер")
        print("4. Личные сообщения")
        choice = input("Выберите опцию (1-4): ").strip()

        if choice == "1":
            channel_id = input("Введите ID канала: ").strip()
            if not channel_id.isdigit():
                print("ID канала должен быть числом!")
                return
            await exporter.export_channel(int(channel_id))
        elif choice == "2":
            category_id = input("Введите ID категории: ").strip()
            if not category_id.isdigit():
                print("ID категории должен быть числом!")
                return
            await exporter.export_category(int(category_id))
        elif choice == "3":
            guild_id = input("Введите ID сервера: ").strip()
            if not guild_id.isdigit():
                print("ID сервера должен быть числом!")
                return
            await exporter.export_guild(int(guild_id))
        elif choice == "4":
            user_id = input("Введите ID пользователя для экспорта личных сообщений: ").strip()
            if not user_id.isdigit():
                print("ID пользователя должен быть числом!")
                return
            await exporter.export_dm(int(user_id))
        else:
            print("Неверный выбор!")
            return
            
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 