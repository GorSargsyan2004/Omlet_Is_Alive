from telebot.types import Message
import os
from mcstatus import JavaServer  
from mcrcon import MCRcon
from concurrent.futures import ProcessPoolExecutor
from collections import deque
import time
import re
import random
import threading
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import pickle
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from concurrent.futures import TimeoutError
import json
from datetime import timedelta



server_ip = os.environ.get('MINECRAFT_SERVER_IP').strip("'")
server_port = int(os.environ.get('MINECRAFT_SERVER_PORT', 25565))  # Default to 25565
rcon_password = os.environ.get('RCON_PASSWORD').strip("'")  # RCON password
rcon_port = int(os.environ.get('RCON_PORT', 25575))  # RCON port, default 25575
OPENWEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY').strip("'")
API_TOKEN = os.environ.get('TELEGRAM_API_TOKEN').strip("'")


# Global variable to control the tracking thread
tracking_active = False
tracking_thread = None

tracking_joins_active = False
tracking_joins_thread = None

active_playtime = {}  # {player_name: active_time_in_seconds}
lock = threading.Lock()


authorized_usernames = ['RandomGor','otkidon']

# Function to send commands to the Minecraft server via RCON
def send_rcon_command(command):
    try:
        with MCRcon(server_ip, rcon_password, port=rcon_port) as mcr:
            response = mcr.command(command)
            return response
    except Exception as e:
        return f"Ошибка: {str(e)}"

# Function to register all commands
def register_commands(bot):

    # Initialize the Minecraft server object
    server = JavaServer.lookup(f"{server_ip}:{server_port}")

    # Initialize a process pool for handling RCON commands
    executor = ProcessPoolExecutor(max_workers=10)


    @bot.message_handler(commands=['say'])
    def handle_say_command(message: Message):
        command_text = message.text.split(maxsplit=1)

        if len(command_text) < 2:
            bot.reply_to(message, "⚠️ Пожалуйста, укажите что хотите написать в чате сервера.")
            return

        msg = command_text[1]
        sender_username = message.from_user.username

        global authorized_usernames


        if message.from_user.username in authorized_usernames:
            mc_command =    (
                            f'tellraw @a '
                            f'[{{"text":"[Телграм: ","color":"blue"}},'
                            f'{{"text":"{sender_username}","color":"gold"}},'
                            f'{{"text":"] ","color":"blue"}},'
                            f'{{"text":"{msg}","color":"blue"}}]'
                            )
        else:
            mc_command =    (
                                f'tellraw @a '
                                f'[{{"text":"[Телграм: ","color":"blue"}},'
                                f'{{"text":"{sender_username}","color":"white"}},'
                                f'{{"text":"] ","color":"blue"}},'
                                f'{{"text":"{msg}","color":"blue"}}]'
                            )

        # Submit the RCON command to be executed in a separate process
        future = executor.submit(send_rcon_command, mc_command)
        
        def send_response(f):
            response = f.result()  # Retrieve the result from the future
            if response == "":
                bot.reply_to(message, f"Сообщения Послано: {msg}")
            else:
                bot.reply_to(message, f"📝 Ответ сервера:\n{response}")

        # Add a callback to send the response once the command is complete
        future.add_done_callback(send_response)


    @bot.message_handler(commands=['cmd'])
    def handle_mc_command(message: Message):
        # Check if the message sender is authorized
        global authorized_usernames  # List of authorized usernames
        if message.from_user.username not in authorized_usernames:
            bot.reply_to(message, "⚠️ У вас нет разрешения на выполнение этой команды.")
            return

        command_text = message.text.split(maxsplit=1)
        
        if len(command_text) < 2:
            bot.reply_to(message, "⚠️ Пожалуйста, укажите команду для сервера.")
            return

        mc_command = command_text[1]  # The actual Minecraft command to send
        sender_username = message.from_user.username  # Get the username of the sender

        # Submit the RCON command to be executed in a separate process
        future = executor.submit(send_rcon_command, mc_command)
        
        # Function to handle the response once the command is executed
        def send_response(f):
            response = f.result()  # Retrieve the result from the future
            bot.reply_to(message, f"📝 Ответ сервера:\n{response}")

        # Add a callback to send the response once the command is complete
        future.add_done_callback(send_response)

    # Path to the Minecraft log file (adjust this path as needed)
    log_file_path = '/home/ubuntu/MinecraftServer/logs/latest.log'

    # Function to remove ANSI escape codes
    def remove_ansi_escape_codes(text):
        # Regex to remove ANSI escape codes
        return re.sub(r'\x1b\[[0-9;]*m', '', text)

    # Function to read the last 5 player messages from the log file
    def get_last_x_messages(count):
        messages = deque(maxlen=count)  # Store up to the last 5 messages

        try:
            with open(log_file_path, 'r', encoding='utf-8') as log_file:
                for line in log_file:
                    # Only process lines containing "Async Chat Thread"
                    if "Async Chat Thread" in line:
                        # Remove ANSI escape codes from the line
                        line = remove_ansi_escape_codes(line)
                        
                        # Regex to capture rank, player name, and message content
                        # This pattern assumes ranks might have extra symbols like "o" before the actual rank
                        match = re.search(r'\[Async Chat Thread.*?/INFO\]:.*?\[(.*?)\]\s*([^\s]+(?:\s+[^\s]+)*)(.*)', line)
                        
                        if match:
                            # Extract rank, player, and message
                            rank, player, message = match.groups()

                            # Handle the "o" or other unwanted characters before the rank
                            if player.startswith("o "):
                                player = player[2:]  # Remove the unwanted "o " before the player's name

                            if player.startswith("oo "):
                                player = player[2:]  # Handle "o" prefix
                            
                            # Clean the message by removing unwanted leading "o" characters
                            message = message.lstrip("o")  # Remove any unwanted "o" at the start of the message

                            # Format the message with bold player name using Markdown
                            formatted_message = f"<b>[</b>{rank}<b>]</b> <b>{player}</b>   {message}"
                            messages.append(formatted_message)

        except FileNotFoundError:
            return ["Ошибка: Файл логов не найден."]
        except UnicodeDecodeError:
            return ["Ошибка: Проблема с кодировкой файла логов."]
        except Exception as e:
            return [f"Ошибка при чтении лога: {str(e)}"]

        return list(messages)

    # Command to retrieve and send the last 5 messages to the bot
    @bot.message_handler(commands=['last5'])
    def handle_last_5_messages(message: Message):
        messages = get_last_x_messages(5)
        
        if messages:
            response = "\n".join(messages)
            bot.reply_to(message, f"📝 Последние 5 сообщений игроков:\n{response}", parse_mode="HTML")
        else:
            bot.reply_to(message, "⚠️ Не удалось найти сообщения игроков.")
            time.sleep(2)
            bot.send_message(message.chat.id, "бож")

    # Command to retrieve and send the last 5 messages to the bot
    @bot.message_handler(commands=['last'])
    def handle_last_1_message(message: Message):
        messages = get_last_x_messages(1)
        
        if messages:
            response = "\n".join(messages)
            bot.reply_to(message, f"📝 Последнее сообщение:\n{response}", parse_mode="HTML")
        else:
            bot.reply_to(message, "⚠️ Не удалось найти сообщения игроков.")
            time.sleep(2)
            bot.send_message(message.chat.id, "бож")

    # Command to retrieve and send the last 5 messages to the bot
    @bot.message_handler(commands=['last10'])
    def handle_last_10_messages(message: Message):
        messages = get_last_x_messages(10)
        
        if messages:
            response = "\n".join(messages)
            bot.reply_to(message, f"📝 Последние 10 сообщений игроков:\n{response}", parse_mode="HTML")
        else:
            bot.reply_to(message, "⚠️ Не удалось найти сообщения игроков.")
            time.sleep(2)
            bot.send_message(message.chat.id, "бож")

    # Function to track player messages from the log file in real-time
    def track_chat_messages(bot, chat_id):
        global tracking_active

        with open(log_file_path, 'r', encoding='utf-8') as log_file:
            # Seek to the end of the file
            log_file.seek(0, os.SEEK_END)

            while tracking_active:
                line = log_file.readline()
                if not line:
                    time.sleep(0.1)  # Wait briefly for new log lines
                    continue

                # Process lines containing "Async Chat Thread"
                if "Async Chat Thread" in line:
                    line = remove_ansi_escape_codes(line)
                    
                    # Regex to capture rank, player name, and message content
                    match = re.search(r'\[Async Chat Thread.*?/INFO\]:.*?\[(.*?)\]\s*([^\s]+(?:\s+[^\s]+)*)(.*)', line)
                    
                    if match:
                        rank, player, message = match.groups()
                        if player.startswith("o "):
                            player = player[2:]  # Handle "o" prefix
                        
                        if player.startswith("oo "):
                            player = player[2:]  # Handle "o" prefix

                        message = message.lstrip("o")  # Clean up the message
                        formatted_message = f"<b>[</b>{rank}<b>]</b> <b>{player}</b>   {message}"

                        # Send the formatted message to the chat
                        bot.send_message(chat_id, formatted_message, parse_mode="HTML")

    # Command to start tracking chat messages
    @bot.message_handler(commands=['track'])
    def handle_track_command(message: Message):
        # Check if the message sender is authorized
        global authorized_usernames
        if message.from_user.username not in authorized_usernames:
            bot.reply_to(message, "⚠️ У вас нет разрешения на выполнение этой команды.")
            return

        global tracking_active, tracking_thread

        if tracking_active:
            bot.reply_to(message, "⚠️ Трекинг уже активен!")
            return

        tracking_active = True
        chat_id = message.chat.id

        # Start a new thread for tracking
        tracking_thread = threading.Thread(target=track_chat_messages, args=(bot, chat_id), daemon=True)
        tracking_thread.start()
        bot.reply_to(message, "📡 Начат трекинг чата. Чтобы остановить, используйте /stoptrack.")

    # Command to stop tracking chat messages
    @bot.message_handler(commands=['stoptrack'])
    def handle_stoptrack_command(message: Message):
        # Check if the message sender is authorized
        global authorized_usernames
        if message.from_user.username not in authorized_usernames:
            bot.reply_to(message, "⚠️ У вас нет разрешения на выполнение этой команды.")
            return
        global tracking_active

        if not tracking_active:
            bot.reply_to(message, "⚠️ Трекинг уже остановлен!")
            return

        tracking_active = False
        bot.reply_to(message, "🛑 Трекинг чата остановлен.")

    def track_join_events(bot, chat_id):
        global tracking_joins_active

        with open(log_file_path, 'r', encoding='utf-8') as log_file:
            # Seek to the end of the file
            log_file.seek(0, os.SEEK_END)

            while tracking_joins_active:
                line = log_file.readline()
                if not line:
                    time.sleep(0.1)  # Wait briefly for new log lines
                    continue

                # Check for player join events
                if "joined the game" in line:
                    line = remove_ansi_escape_codes(line)
                    match = re.search(r'\[.*?\]:\s(.*?)\sjoined the game', line)
                    if match:
                        player = match.group(1)  # Extract the player's name
                        notification = f"⚡ Игрок <b>{player}</b> зашёл(а) на сервер!"
                        bot.send_message(chat_id, notification, parse_mode="HTML")

                # Check for player join events
                if "left the game" in line:
                    line = remove_ansi_escape_codes(line)
                    match = re.search(r'\[.*?\]:\s(.*?)\sleft the game', line)
                    if match:
                        player = match.group(1)  # Extract the player's name
                        notification = f"⚡ Игрок <b>{player}</b> вышел(а) из сервера!"
                        bot.send_message(chat_id, notification, parse_mode="HTML")

    @bot.message_handler(commands=['trackJoin'])
    def handle_track_join_command(message: Message):
        # Check if the message sender is authorized
        global authorized_usernames
        if message.from_user.username not in authorized_usernames:
            bot.reply_to(message, "⚠️ У вас нет разрешения на выполнение этой команды.")
            return

        global tracking_joins_active, tracking_joins_thread

        if tracking_joins_active:
            bot.reply_to(message, "⚠️ Трекинг подключений уже активен!")
            return

        tracking_joins_active = True
        chat_id = message.chat.id

        # Start a new thread for join tracking
        tracking_joins_thread = threading.Thread(target=track_join_events, args=(bot, chat_id), daemon=True)
        tracking_joins_thread.start()
        bot.reply_to(message, "📡 Начат трекинг подключений игроков. Чтобы остановить, используйте /stoptrackJoin.")

    @bot.message_handler(commands=['stoptrackJoin'])
    def handle_stop_track_join_command(message: Message):
        # Check if the message sender is authorized
        global authorized_usernames
        if message.from_user.username not in authorized_usernames:
            bot.reply_to(message, "⚠️ У вас нет разрешения на выполнение этой команды.")
            return

        global tracking_joins_active

        if not tracking_joins_active:
            bot.reply_to(message, "⚠️ Трекинг подключений уже остановлен!")
            return

        tracking_joins_active = False
        bot.reply_to(message, "🛑 Трекинг подключений игроков остановлен.")

    def search_in_chat(keyword):
        messages = []

        try:
            with open(log_file_path, 'r', encoding='utf-8') as log_file:
                for line in log_file:
                    # Only process lines containing "Async Chat Thread"
                    if "Async Chat Thread" in line:
                        # Remove ANSI escape codes from the line
                        line = remove_ansi_escape_codes(line)

                        match = re.search(r'\[Async Chat Thread.*?/INFO\]:.*?\[(.*?)\]\s*([^\s]+(?:\s+[^\s]+)*)(.*)', line)

                        if match:
                            # Extract rank, player, and message
                            rank, player, message = match.groups()

                            # Handle the "o" or other unwanted characters before the rank
                            if player.startswith("o "):
                                player = player[2:]  # Remove the unwanted "o " before the player's name

                            if player.startswith("oo "):
                                player = player[2:]  # Handle "oo" prefix

                            # Clean the message by removing unwanted leading "o" characters
                            message = message.lstrip("o")  # Remove any unwanted "o" at the start of the message

                            # Safely split player and message
                            if "  " in player:  # Check if double space exists
                                player_parts = player.split("  ", maxsplit=1)
                                player = player_parts[0]
                                if len(player_parts) > 1:
                                    message = player_parts[1] + message

                            # Check if the keyword is in the message
                            if keyword.lower() in message.lower():
                                # Format the message with bold player name using HTML
                                formatted_message = f"<b>[</b>{rank}<b>]</b> <b>{player}</b> {message}"
                                messages.append(formatted_message)

        except FileNotFoundError:
            return ["Ошибка: Файл логов не найден."]
        except UnicodeDecodeError:
            return ["Ошибка: Проблема с кодировкой файла логов."]
        except Exception as e:
            return [f"Ошибка при чтении лога: {str(e)}"]

        return messages

    @bot.message_handler(commands=['chat'])
    def handle_chat(message: Message):
        global authorized_usernames
        if message.from_user.username not in authorized_usernames:
            bot.reply_to(message, "⚠️ У вас нет разрешения на выполнение этой команды.")
            return

        text = message.text.split(maxsplit=1)
        
        if len(text) < 2:
            bot.reply_to(message, "⚠️ Пожалуйста, укажите что хотите поискать в чате.")
            return

        keyword = text[1] 

        messages = search_in_chat(keyword)
        
        if messages:
            response = "\n".join(messages)
            bot.reply_to(message, f"📝 Все сообщения игроков с ключевым словом <b>{keyword}</b>:\n{response}", parse_mode="HTML")
        else:
            bot.reply_to(message, f"⚠️ Не удалось найти сообщения игроков с ключевым словом <b>{keyword}</b>.", parse_mode="HTML")


    @bot.message_handler(commands=['playing'])
    def handle_playing_command(message: Message):
        # Submit the RCON "list" command to the executor
        future = executor.submit(send_rcon_command, "list")
        
        # Function to process the result of the RCON command
        def send_response(f):
            try:
                response = f.result()  # Retrieve the result from the future
                
                if not response or "Error" in response:
                    bot.reply_to(message, "⚠️ Не удалось получить информацию о игроках. Возможно, сервер недоступен.")
                    return
                
                # Remove Minecraft color codes (e.g., §6, §c)
                cleaned_response = re.sub(r"§[0-9a-fk-or]", "", response)

                # Try matching common formats after cleaning
                match_without_players = re.search(r"There are (\d+) out of maximum \d+ players online\.", cleaned_response)
                match_with_players = re.search(r"There are (\d+) out of maximum \d+ players online\.\s*(.*)", cleaned_response, re.DOTALL)

                if match_with_players:
                    player_count = int(match_with_players.group(1))
                    players_raw = match_with_players.group(2).strip()

                    # Split players by newline and process individually
                    player_lines = players_raw.split("\n")

                    players_cleaned = []
                    for line in player_lines:
                        line = line.strip()
                        if line:  # Skip empty lines
                            # Remove prefixes like "mod:" or "architect:"
                            line = re.sub(r"^\w+:\s*", "", line)
                            players_cleaned.append(line)

                    if player_count == 0 or not players_cleaned:
                        bot.reply_to(message, "⚡ Никто не играет на сервере сейчас.")
                        time.sleep(2)
                        bot.send_message(message.chat.id,"ц")
                    else:
                        players_formatted = "\n".join(f"<b>{p}</b>" for p in players_cleaned)
                        bot.reply_to(message, f"⚡ Сейчас на сервере {player_count} игрок(а/ов):\n{players_formatted}", parse_mode="HTML")

                else:
                    # For debugging: handle unexpected formats
                    bot.reply_to(message, f"⚠️ Не удалось распознать формат ответа от сервера:\n<pre>{cleaned_response}</pre>", parse_mode="HTML")
            
            except Exception as e:
                bot.reply_to(message, f"⚠️ Произошла ошибка: {str(e)}")
        
        # Add the callback to process the response when the command is done
        future.add_done_callback(send_response)

    def get_weather(location):
        try:
            url = f"http://api.openweathermap.org/data/2.5/weather"
            params = {
                'q': location,
                'appid': OPENWEATHER_API_KEY,
                'lang': 'ru', 
                'units': 'metric'  
            }
            response = requests.get(url, params=params)
            print(response)
            data = response.json()

            if response.status_code == 200:
                city = data['name']
                weather_description = data['weather'][0]['description']
                temperature = data['main']['temp']
                feels_like = data['main']['feels_like']
                humidity = data['main']['humidity']
                wind_speed = data['wind']['speed']

                return (
                    f"🌍 Погода в {city}:\n"
                    f"🌤️ {weather_description.capitalize()}\n"
                    f"🌡️ Температура: {temperature}°C (Ощущается как {feels_like}°C)\n"
                    f"💧 Влажность: {humidity}%\n"
                    f"💨 Скорость ветра: {wind_speed} м/с"
                )
            else:
                return f"⚠️ Не удалось найти погоду для '{location}'. Проверьте правильность написания."
        except Exception as e:
            return f"⚠️ Произошла ошибка: {str(e)}"

    @bot.message_handler(commands=['weather'])
    def handle_weather_command(message: Message):
        command_parts = message.text.split(maxsplit=1)
        if len(command_parts) < 2:
            bot.reply_to(message, "⚠️ Укажите название города, например: /weather Москва")
            return
        location = command_parts[1]
        weather_info = get_weather(location)
        bot.reply_to(message, weather_info)

    @bot.message_handler(func=lambda message: "погода в " in message.text.lower())
    def handle_weather_command(message: Message):
        command_parts = message.text.split(maxsplit=2)
        if len(command_parts) < 3:
            bot.reply_to(message, "⚠️ Укажите название города, например: погода в Москва или /weather Москва")
            return
        location = command_parts[2]
        if location[-1] == "е":
            location = location[:-1]
        weather_info = get_weather(location)
        bot.reply_to(message, weather_info)

    @bot.message_handler(commands=['serverStatus'])
    def handle_server_status(message):
        try:
            status = server.status()  # Attempt to get the server status

            response = (
                f"✅ <b>Сервер статус:</b> Онлайн\n"
                f"🎮 <b>Версия:</b> {status.version.name}\n"
                f"👥 <b>Игроки Онлайн:</b> {status.players.online}/{status.players.max}\n"
                """\n<b>Bedrock</b> (Телефонный) v. 1.20.81+
    ———————————————
    <b>ip</b> - guide-bone.gl.at.ply.gg
    <b>порт</b> - 3157

    <b>Java</b> (пк) v. 1.20.4
    ———————————————
    <b>ip</b> - b-griffin.gl.joinmc.link"""
            )
        
        except Exception as e:
            response = (
                "❌ <b>Сервер статус:</b> Оффлайн\n"
                "⚠️ <b>Ошибка:</b> Сервер не отвечает. Попробуйте позже."
            )

        bot.reply_to(message, response, parse_mode="HTML")


    @bot.message_handler(commands=['privileges'])
    def handle_privileges(message):
        try:
            # Define the privileges and their explanations
            privileges = {
                "УЧАСТНИК": [
                    "/tp - Телепортация к другому игроку.",
                    "/sethome - Установить домашнюю точку.",
                    "/home - Телепортироваться домой.",
                    "/delhome - Удалить домашнюю точку.",
                    "/warp - Телепортация на установленную точку.",
                    "/spawn - Телепортация на спаун.",
                    "Роль: Новички на сервере, могут использовать базовые команды для комфортной игры"
                ],
                "ВИП": [
                    "Все возможности Участника.",
                    "/fly - Позволяет летать, что упрощает исследование и строительство.",
                     "Роль: Просто активные и порядочные игроки, которые заслуживают летать. Занемаются геймплеем и если замечают какой то баг или нарушение или неполадок сообщяют высшим рангам, будут за это награждены."
                ],
                "СТРОИТЕЛЬ": [
                    "Все возможности ВИПа.",
                    "/gamemode - Сменить режим игры (например, креативный для строительства).",
                    "/fill - Заполняет область блоками.",
                    "Роль: Занематся строительством сервера, использовать гейммод для благого дела, ну или для собственных нужд, не занимаются правопорядком сервера, концентрация на строительстве. Очень ценные юниты для Архитектора. Являются помощниками Архитекторов.",
                ],
                "ЭЛИТА": [
                    "Все возможности Строителя.",
                    "/give - Дает доступ к ресурсам, включая блоки из креативного режима.",
                    "/kick - Временное исключение игрока за неподобающее поведение.",
                    "/ban - Блокировка нарушителей за серьезные нарушения.",
                    "/unban - Снятие бана с игроков.",
                    "Роль: Следить за правопорядком сервера, за нарушениями игроков, скенцрируются они в основном на Строителей, следят чтоб не злоупотребляли гейммод. Могут кикать или банить нарушителей, либо соощщить о нарушении Админам. Являются помощниками Админов",
                ],
                "АРХИТЕКТОР": [
                    "Все возможности Элиты.",
                    "/lp user &lt;player&gt; promote builder - Повысить игрока до Строителя.",
                    "/lp user &lt;player&gt; demote builder - Понизить игрока, убрав роль Строителя.",
                    "//br - Используется для быстрого построения.",
                    "Роль: Следить за управлению сервером, мониторингу игроков и их потребностями. Контралируют Элит, следят за их делом и за правильных принятий решений. Являются помощниками Супервайзера, слущаются их, за нарушение могут быть пониженными.",
                ],
                "АДМИН": [
                    "Имеет доступ ко всем командам, кроме назначения рангов.",
                    "Роль: Следить за управлению сервером, мониторингу игроков и их потребностями. Контралируют Элит, следят за их делом и за правильных принятий решений. Являются помощниками Супервайзера, слущаются их, за нарушение могут быть пониженными.",
                ],
                "СУПЕРВАЙЗЕР": [
                    "Все возможности Админа.",
                    "/lp user &lt;player&gt; promote admin - Назначить игрока Админом.",
                    "/lp user &lt;player&gt; demote admin - Снять роль Админа.",
                    "Роль: Главный в сервере после Модератора. Должен следить за нарушениями, не правильными поступками Админов. Должен наводить порядок в сервере, принять равновесные и честные решения, слушать все требования и если не может решать - рассказать о проблеме Модератору. Может добавить себя помошников в виде Админов или убрать их.",
                ],
                "МОДЕРАТОР": [
                    "Имеет весь контроль над сервером и занемается програмными чатями сервака, добавлениями плагинов, мини игр, и устраняет неполадки в сервере если они появятся.",
                ]
            }
            
            # Extract the role argument if provided
            args = message.text.split()
            if len(args) > 1:
                role_name = " ".join(args[1:]).upper()
            else:
                role_name = None

            # Build the response string
            if role_name and role_name in privileges:
                response = f"<b>🛠️ Привилегии для роли {role_name}:</b>\n\n"
                response += "\n".join(f"• {cmd}" for cmd in privileges[role_name])
            elif role_name and role_name not in privileges:
                response = f"❌ <b>Ошибка:</b> Роль <b>{role_name}</b> не найдена. Убедитесь в правильности написания."
            else:
                response = "<b>🛠️ Привилегии на сервере:</b>\n\n"
                for role, commands in privileges.items():
                    response += f"<b>{role}:</b>\n"
                    response += "\n".join(f"• {cmd}" for cmd in commands) + "\n\n"

            # Send the response
            bot.reply_to(message, response, parse_mode="HTML")
        
        except Exception as e:
            response = f"❌ <b>Ошибка:</b> Не удалось получить информацию о привилегиях.\n⚠️ <b>Детали:</b> {str(e)}"
            bot.reply_to(message, response, parse_mode="HTML")

    @bot.message_handler(commands=['online'])
    def handle_online(message):
        try:
            status = server.status()
            response = (
                f"👥 **Игроки Онлайн:** {status.players.online}/{status.players.max}\n"
            )
        except Exception as e:
            response = f"❌ **Ошибка:** Не удалось получить число игроковn⚠️ **Details:** {str(e)}"
        
        bot.reply_to(message, response, parse_mode="Markdown")

        if status.players.online == 0:
            time.sleep(2)
            chat_id = message.chat.id 
            bot.send_message(chat_id, "педарасы")

    @bot.message_handler(commands=['help'])
    def handle_help(message):
        help_text = (
            "📚 <b>Доступные команды:</b>\n\n"
            
            "⚙️ <b>Общие команды:</b>\n"
            "• /serverStatus - Проверить статус сервера.\n"
            "• /online - Узнать количество игроков онлайн.\n"
            "• /playing - Узнать количество игроков и их никнеймы, узнать кто играет.\n"
            "• /privileges [привилегия] - Посмотреть информацию о правах и задачах каждой привилегии.\n"
            "• /sync [никнейм] - Синхронизировать ваш Minecraft никнейм с Telegram аккаунтом.\n"
            "• /showsync - Увидеть все синхранизированные Minecraft никнеймы.\n\n"
            
            "💰 <b>Amlet Coins:</b>\n"
            "• /fortune - Испытать удачу и получить от 0.5 до 5.0 Amlet Coins.\n"
            "• /balance - Узнать ваш текущий баланс Amlet Coins.\n"
            "• /топ5 - Узнать топ 5 пользователей с наибольшим количеством Amlet Coins.\n"
            "• /топ10 - Узнать топ 10 пользователей с наибольшим количеством Amlet Coins.\n"
            "• /купить превелегию [название привилегии] - Купить привилегию для вашего Minecraft аккаунта за Amlet Coins.\n\n"
            
            "📦 <b>Мемы и развлечения:</b>\n"
            "• /scrape - Получить мемы из интернета и сохранить их (доступно только некоторым пользователям).\n"
            "• /meme - Показать фото-мемы, полученные с интернета.\n"
            "• /memev - Показать видео-мемы, полученные с интернета.\n\n"
            
            "💬 <b>Чат-команды:</b>\n"
            "• /clear - Чтобы очистить последние 10 сообщений ботов, в основном для рекламы (доступно всем).\n"
            "• /say - Чтобы послать сообщение в сервер (доступно всем).\n"
            "• /cmd - Ввести команды для консоли сервера (доступно только некоторым пользователям).\n"
            "• /chat [текст] - Чтобы поискать в чате конкретное слово или выражение (доступно только некоторым пользователям).\n"
            "• /track - Чтобы следить за чатом сервера в реальном времени (доступно только некоторым пользователям).\n"
            "• /stoptrack - Закончить следить за чатом (доступно только некоторым пользователям).\n"
            "• /trackJoin - Следить за тем, кто заходит и выходит с сервера (доступно только некоторым пользователям).\n"
            "• /stoptrackJoin - Закончить следить за тем, кто заходит и выходит с сервера (доступно только некоторым пользователям).\n"
            "• /last, /last5, /last10 - Показать последние 1, 5 или 10 сообщений игроков на сервере.\n\n"
            
            "🔹 <b>Дополнительные действия:</b>\n"
            "Бот также умеет:\n"
            "• Ударять 🤜\n"
            "• Дать пощёчину 🖐️\n"
            "• Целовать 💋\n"
            "• Обнимать 🤗\n"
            "• Делать м**ет 🫦\n"
            "• Т**нуть 😉\n"
            "• Делать к**и 👅\n\n"

            "Используйте <b>гбт</b> чтобы общятся с более умной версией Амлет Бота, ответит на любой вопрос.\n\n"
            
            "💡 <b>Система начисления Amlet Coins:</b>\n"
            "Бот вознаграждает активных участников группы и игроков на сервере Minecraft:\n\n"
            "<b>В группе:</b>\n"
            "• За каждые 50 сообщений вы получите 10 Coins.\n"
            "• 100 сообщений = 20 Coins.\n"
            "• 200 сообщений = 40 Coins.\n"
            "• 400 сообщений = 80 Coins.\n"
            "• 500 сообщений = 100 Coins.\n\n"
            
            "<b>На сервере Minecraft:</b>\n"
            "• За каждую секунду игры начисляется 0.01 Amlet Coin.\n\n"
            
            "🔄 <i>Бот постоянно обновляется, и в будущем его функционал будет расширяться!</i>"
        )
        bot.reply_to(message, help_text, parse_mode="HTML")

    # Function to greet new members
    @bot.message_handler(func=lambda message: message.new_chat_members is not None and message.text is not None)
    def greet_new_member(message: Message):
        # Get information about the new member
        new_member = message.new_chat_members[0]

        # Construct a friendly greeting message
        greeting_message = (
            f"🌟 Привет, {new_member.mention_markdown()}! Добро пожаловать в наше уютное сообщество! 🤗\n\n"
            "Здесь мы делимся интересами, общаемся, играем в Майнкрафт и чилим вместе. "
            "Чувствуйте себя как в своем чате с друзьями."
            "Рады, что ты с нами! 🎉"
            "Я Омлет🤖, узнай обо мне больше вспомощю /help, и **прочитай закрепленное сообщение**"
        )

        # Send the friendly greeting message to the group
        bot.reply_to(message, greeting_message)

    @bot.message_handler(commands=['start'])
    def handle_start(message):
        start_text = (
            "👋 Привет!\n\n"
            "Я телеграм бот 🤖, созданный 'Стариком-Гором-Котом-Куртом (как бы вы меня не называли)'.\n"
            "<b>Моя цель</b> - помочь вам играть в ваш любимый майнкрафт с друзьями и провести отличное время. 🎮\n\n"
            "Давайте начнем! Используйте команду /help, чтобы узнать как пользоватся мной и как призвать к тебе играть в Minecraft. 🌐"
        )

        bot.reply_to(message, start_text, parse_mode="HTML")


      


    #=============================< AMLET COINS PART >=============================

    TIMESTAMP_FILE = "user_timestamps.txt"
    COIN_FILE = "amlet_coins.txt"

    def read_file_as_dict(file_path, key_type=int, value_type=str):
        if not os.path.exists(file_path):
            return {}
        try:
            with open(file_path, 'r') as f:
                return {
                    key_type(line.split(',')[0]): value_type(line.split(',')[1].strip())
                    for line in f.readlines()
                }
        except Exception as e:
            print(f"Error reading file '{file_path}': {e}")
            return {}

    def write_dict_to_file(data, file_path, value_formatter=str):

        try:
            with open(file_path, 'w') as f:
                for key, value in data.items():
                    f.write(f"{key},{value_formatter(value)}\n")
        except Exception as e:
            print(f"Error writing to file '{file_path}': {e}")

    def read_balances():
        return read_file_as_dict(COIN_FILE, key_type=int, value_type=float)

    def write_balances(balances):
        write_dict_to_file(balances, COIN_FILE, value_formatter=lambda x: f"{x:.2f}") 

    def read_timestamps():
        return read_file_as_dict(TIMESTAMP_FILE, key_type=int, value_type=float)

    def write_timestamps(timestamps):
        write_dict_to_file(timestamps, TIMESTAMP_FILE, value_formatter=str)

    def generate_fortune():
        thresholds = [0.5, 1.5, 3.0, 4.0, 5.0]
        probabilities = [0.6, 0.25, 0.1, 0.04, 0.01]
        return round(random.choices(thresholds, probabilities)[0], 2)


    LINKED_ACCOUNTS_PATH = "linked_accounts.json"

    # Load linked accounts
    def load_linked_accounts():
        if not os.path.exists(LINKED_ACCOUNTS_PATH):
            return {"groups": []}  # Initialize with an empty structure if file doesn't exist
        try:
            with open(LINKED_ACCOUNTS_PATH, "r") as f:
                data = json.load(f)
                # Ensure the structure is correct
                if "groups" not in data or not isinstance(data["groups"], list):
                    raise ValueError("Invalid JSON structure")
                return data
        except (json.JSONDecodeError, ValueError):
            print("⚠️ Error: Could not decode JSON or invalid structure. Starting with an empty structure.")
            return {"groups": []}

    # Check if accounts are already linked
    def are_accounts_linked(user_id_1, user_id_2):
        data = load_linked_accounts()
        for group in data["groups"]:
            if user_id_1 in group and user_id_2 in group:
                return True
        return False

    @bot.message_handler(commands=['fortune'])
    def handle_fortune(message):
        user_id = message.from_user.id
        user_name = message.from_user.first_name or "Юзер"

        balances = read_balances()
        timestamps = read_timestamps()

        current_time = time.time()
        one_hour = 3600

        def delete_user_message():
            time.sleep(5) 
            try:
                bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            except Exception as e:
                print(f"Error deleting user's message: {e}")

        last_timestamp = timestamps.get(user_id, 0)
        if current_time - last_timestamp < one_hour:
            time_left = round(one_hour - (current_time - last_timestamp), 2)
            bot.reply_to(
                message,
                f"⏳ {user_name}, подождите {time_left} секунд, прежде чем получить новую удачу!"
            )
            threading.Thread(target=delete_user_message).start()
            return

        # Check if the user has opened the case from a linked account
        for user_id_2 in timestamps.keys():
            if are_accounts_linked(int(user_id), int(user_id_2)):
                last_timestamp = timestamps.get(user_id_2, 0)
                if current_time - last_timestamp < one_hour:
                    time_left = round(one_hour - (current_time - last_timestamp), 2)
                    bot.reply_to(
                        message,
                        f"⏳ {user_name}, подождите {time_left} секунд, вы уже использовали фортуну в другом аккаунте!"
                    )
                    threading.Thread(target=delete_user_message).start()
                    return

        fortune_amount = generate_fortune()
        balances[user_id] = balances.get(user_id, 0) + fortune_amount
        timestamps[user_id] = current_time

        write_balances(balances)
        write_timestamps(timestamps)

        bot.send_message(message.chat.id,
            f"🍀 {user_name}, удача на вашей стороне!\n"
            f"Вы получили {fortune_amount} AmletCoins 💰!"
        )

        threading.Thread(target=delete_user_message).start()

    @bot.message_handler(commands=['balance'])
    def handle_balance(message):
        user_id = message.from_user.id
        user_name = message.from_user.first_name or "User"

        balances = read_balances()
        user_balance = balances.get(user_id, 0.0)

        bot.send_message(message.chat.id,
            f"💰 {user_name}, ваш баланс AmletCoins: {user_balance:.2f}!"
        )

        def delete_user_message():
            time.sleep(5)  
            try:
                bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            except Exception as e:
                print(f"Error deleting user's message: {e}")

        threading.Thread(target=delete_user_message).start()
    

    #=============================< AMLET MINECRAFT GRANT >=============================

    #------------------------------------------
    # 1. Player Activity and AFK Detection
    #------------------------------------------

    # Store player activity information
    daily_playtime_file = "daily_playtime.json"


    def send_rcon_command_with_timeout(command, timeout=5):
        try:
            # Use executor.submit to run the RCON command with a timeout
            future = executor.submit(send_rcon_command, command)
            response = future.result(timeout=timeout)  # Wait for the result with timeout
            return response
        except TimeoutError:
            return "Error: Command timed out"
        except Exception as e:
            return f"Error: {str(e)}"

    def get_minecraft_players():
        try:
            response = send_rcon_command_with_timeout("list", timeout=5)
            if not response or "Error" in response:
                print(f"⚠️ Не удалось получить информацию о игроках: {response}")
                return []
            
            cleaned_response = re.sub(r"§[0-9a-fk-or]", "", response)
            match_with_players = re.search(r"There are (\d+) out of maximum \d+ players online\.\s*(.*)", cleaned_response, re.DOTALL)
            
            if match_with_players:
                players_raw = match_with_players.group(2).strip()
                player_lines = [line.strip() for line in players_raw.split("\n") if line.strip()]
                players = []
                for line in player_lines:
                    is_afk = "[AFK]" in line

                    nickname_cleaned = line.split(" ", maxsplit=3)[2]

                    players.append({"nickname": nickname_cleaned, "afk": is_afk})
                return players
            else:
                return []
        except Exception as e:
            print(f"⚠️ Произошла ошибка: {str(e)}")
            return []


    #------------------------------------------
    # 2. AmletCoins Reward System
    #------------------------------------------

    AMLET_COINS_PER_MINUTE = 0.6

    def grant_rewards():
        def read_synchronized_users():
            """Reads the synchronized users (user_id, minecraft_nick) from the pickle file."""
            if not os.path.exists("synchronize.pickle"):
                return {}
            with open("synchronize.pickle", 'rb') as f:
                synchronized_users = pickle.load(f)
            return synchronized_users

        def task():
            global active_playtime
            synchronized_users = read_synchronized_users()
            balances = read_balances()

            # Get the list of Minecraft players (including AFK status)
            players = get_minecraft_players()  # This should be implemented in your system.

            # Convert player data to a dictionary of player names with their AFK status
            player_afk_status = {player['nickname']: player['afk'] for player in players}

            # Iterate through active players and grant rewards if they are not AFK
            for player, playtime in active_playtime.items():
                if player_afk_status.get(player, False):  # If player is AFK, skip
                    continue

                if playtime > 0:  # Only grant rewards if the player has playtime and is not AFK
                    earned_coins = AMLET_COINS_PER_MINUTE

                    mc_command = (
                            f'tellraw {player} '
                            f'[{{"text":"[Амлет] ","color":"gold"}},'
                            f'{{"text":"+{earned_coins} 💰","color":"yellow"}}]'
                            )
                            
                    
                    # Submit the RCON command to be executed in a separate process
                    future = executor.submit(send_rcon_command, mc_command)
                    
                    def send_response(f):
                        response = f.result()  
                        if response == "":
                            for user_id, minecraft_nick in synchronized_users.items():
                                if minecraft_nick.lower() == player.lower():
                                    balances[user_id] = balances.get(user_id, 0) + earned_coins
                                    write_balances(balances)
                                    break

                    # Add a callback to send the response once the command is complete
                    future.add_done_callback(send_response)

                    

        threading.Thread(target=task).start()

    #------------------------------------------
    # 3. Periodic Task Scheduler
    #------------------------------------------

    def load_daily_playtime():
        try:
            with open("daily_playtime.json", "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        return data

    def save_daily_playtime(data):
        with open("daily_playtime.json", "w") as f:
            json.dump(data, f, indent=4)

    def reset_daily_playtime():
        current_date = datetime.now().strftime("%Y-%m-%d")
        try:
            with open("playtime_date.txt", "r") as f:
                last_date = f.read().strip()
        except FileNotFoundError:
            last_date = None

        if current_date != last_date:
            with open("playtime_date.txt", "w") as f:
                f.write(current_date)
            save_daily_playtime({})
            print("✅ Daily playtime data reset for a new day.")

    def update_playtime(players):
        global active_playtime

        reset_daily_playtime()

        daily_playtime = load_daily_playtime()
        current_time = time.time()

        with lock:  # Ensure thread safety
            for player in players:
                nickname = player["nickname"]
                is_afk = player["afk"]

                if not is_afk:
                    # Initialize active playtime for the player if not already set
                    if nickname not in active_playtime:
                        active_playtime[nickname] = current_time

                    # Calculate elapsed time
                    elapsed_time = current_time - active_playtime[nickname]

                    # Prevent unrealistic playtime increments
                    if elapsed_time > 3600:  # If more than 1 hour, likely an error
                        print(f"⚠️ Unrealistic playtime detected for {nickname}: {elapsed_time} seconds. Skipping.")
                        elapsed_time = 0

                    # Update daily playtime
                    daily_playtime[nickname] = daily_playtime.get(nickname, 0) + elapsed_time

                    # Update last active time
                    active_playtime[nickname] = current_time
                else:
                    # Remove player from active playtime if they are AFK
                    active_playtime.pop(nickname, None)

        save_daily_playtime(daily_playtime)

    def periodic_update_playtime(interval, get_players_func):
        def wrapper():
            while True:
                players = get_players_func()
                if players:
                    update_playtime(players)
                time.sleep(interval)

        threading.Thread(target=wrapper, daemon=True).start()

    def periodic_grant_rewards():
        while True:
            grant_rewards()
            time.sleep(60)

    # Start the periodic reward system in a background thread

    threading.Thread(target=periodic_grant_rewards, daemon=True).start()
    periodic_update_playtime(interval=5, get_players_func=get_minecraft_players)

    #------------------------------------------
    # 3. Minecraft players activity function
    #------------------------------------------


    # Function to format playtime
    def format_playtime_in_russian(seconds):
        total_minutes = seconds // 60
        hours = total_minutes // 60
        minutes = total_minutes % 60

        if hours > 0:
            return f"{hours} час(ов) и {minutes} минут(ы)"
        else:
            return f"{minutes} минут(ы)"

    # Function to calculate and display playtime
    def display_daily_playtime():
        daily_playtime = load_daily_playtime()

        if not daily_playtime:
            return "⛔️ В данный момент данных об активности в Сервере нет."

        playtime_report = "<b>⏱ Активность игроков в Сервере:</b>\n"
        for player, seconds in daily_playtime.items():
            formatted_time = format_playtime_in_russian(seconds)
            playtime_report += f"👤 <b>{player}</b>: {formatted_time}\n"

        return playtime_report

    # Telegram bot command for майн актив
    @bot.message_handler(func=lambda message: "майн актив" in message.text.lower() )
    def handle_mine_activity_command(message):
        response = display_daily_playtime()
        bot.send_message(chat_id=message.chat.id, text=response, parse_mode="HTML")

    #=============================< AMLET MEME CREATION PART >=============================


    user_requests = {}

    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    @bot.message_handler(func=lambda message: "создать мем" in message.text.lower())
    def create_meme(message: Message):
        user_id = message.from_user.id
        user_name = message.from_user.first_name or "Пользователь"
        
        user_requests[user_id] = {'state': 'waiting_for_photo', 'chat_id': message.chat.id}
        
        bot.reply_to(message, f"Привет, {user_name}! 😊 Для создания мема, отправь мне фото мема!")

    @bot.message_handler(content_types=['photo'])
    def handle_photo(message: Message):
        user_id = message.from_user.id

        # Check if the user is in the 'waiting_for_photo' state
        if user_id not in user_requests or user_requests[user_id]['state'] != 'waiting_for_photo':
            return
        
        # Get the photo file from Telegram
        file_info = bot.get_file(message.photo[-1].file_id)
        photo_url = f"https://api.telegram.org/file/bot{API_TOKEN}/{file_info.file_path}"
        photo_response = requests.get(photo_url)
        photo = Image.open(BytesIO(photo_response.content))

        # Store the photo and change state to 'waiting_for_text'
        user_requests[user_id]['photo'] = photo
        user_requests[user_id]['state'] = 'waiting_for_text'

        bot.reply_to(message, f"Отлично! Теперь напиши текст для мема, {message.from_user.first_name}.")

    def get_scaled_font_size(image, text, font_path, max_font_size=40):
        draw = ImageDraw.Draw(image)
        width, _ = image.size
        font_size = max_font_size
        font = ImageFont.truetype(font_path, font_size)
        
        # Decrease font size until the text fits in the width
        while True:
            bbox = draw.textbbox((0, 0), text, font=font)  # bbox = (left, top, right, bottom)
            text_width = bbox[2] - bbox[0]  # Width of the text
            if text_width <= width - 20:  # Allow a little padding
                break
            font_size -= 1
            font = ImageFont.truetype(font_path, font_size)

        return font

    def wrap_text(draw, text, font, max_width):
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            # Test adding the word to the current line
            test_line = current_line + " " + word if current_line else word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            text_width = bbox[2] - bbox[0]  # Width of the text

            if text_width <= max_width - 20:  # If it fits, add it to the line
                current_line = test_line
            else:
                # Otherwise, start a new line
                lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines

    @bot.message_handler(func=lambda message: user_requests.get(message.from_user.id, {}).get('state') == 'waiting_for_text')
    def handle_text(message: Message):
        user_id = message.from_user.id
        meme_text = message.text
        chat_id = user_requests[user_id]['chat_id']  # Get the chat ID from user request

        # Retrieve the stored photo
        if user_id in user_requests and 'photo' in user_requests[user_id]:
            photo = user_requests[user_id]['photo']
            width, height = photo.size
            
            # Create a draw object for the text overlay
            draw = ImageDraw.Draw(photo)

            # Get a scaled font size that fits the image width
            font = get_scaled_font_size(photo, meme_text, font_path, max_font_size=40)

            # Wrap the text properly to fit within the image width
            wrapped_text = wrap_text(draw, meme_text, font, width)

            # Calculate the total height required for the text
            total_text_height = 0
            for line in wrapped_text:
                bbox = draw.textbbox((0, 0), line, font=font)
                total_text_height += bbox[3] - bbox[1]  # Height of the text line
            total_text_height += 10 * len(wrapped_text)  # Add space between lines

            # Create a new image with extra space for the text
            new_height = height + total_text_height + 10  # Adding extra space for text (10px margin)
            new_image = Image.new('RGB', (width, new_height), (255, 255, 255))  # White background

            # Create a new drawing object for the new image (important!)
            draw = ImageDraw.Draw(new_image)

            # Paste the original photo at the bottom, leaving space at the top for text
            new_image.paste(photo, (0, total_text_height))  # Paste the photo below the new text space

            # Draw the wrapped text on the new image
            y_position = 10  # Starting Y position for text (a bit of margin at the top)
            for line in wrapped_text:
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]  # Width of the text
                x_position = (width - text_width) // 2  # Center the text horizontally
                draw.text((x_position, y_position), line, font=font, fill=(0, 0, 0))  # Black text
                y_position += bbox[3] - bbox[1] + 10  # Move to the next line with a bit of space

            # Save the final image
            meme_path = f'meme_{user_id}.png'
            new_image.save(meme_path)

            # Send the processed meme back to the correct user (chat_id)
            with open(meme_path, 'rb') as photo_file:
                bot.send_photo(chat_id, photo_file, caption="Вот ваш мем! 🤩")

            # Reset the user's request state
            del user_requests[user_id]

    #=============================< AMLET MINECRAFT PLAYER SYNC PART >=============================

    # File to store the user synchronization data
    SYNC_FILE = "synchronize.pickle"

    def read_synchronized_users():
        """Reads the synchronized users (user_id, minecraft_nick) from the pickle file."""
        if not os.path.exists(SYNC_FILE):
            return {}
        with open(SYNC_FILE, 'rb') as f:
            synchronized_users = pickle.load(f)
        return synchronized_users

    def write_synchronized_users(synchronized_users):
        """Writes the synchronized users (user_id, minecraft_nick) to the pickle file."""
        with open(SYNC_FILE, 'wb') as f:
            pickle.dump(synchronized_users, f)

    # Function to synchronize a user with a Minecraft nickname
    @bot.message_handler(commands=['sync'])
    def sync_user(message):
        """Command handler for syncing a user with their Minecraft nickname."""
        user_id = message.from_user.id
        user_name = message.from_user.first_name or "User"
        minecraft_nick = message.text.split(" ")[1] if len(message.text.split()) > 1 else None
        
        if minecraft_nick:
            # Read the current synchronized users
            synchronized_users = read_synchronized_users()

            # Add or update the sync pair (user_id, minecraft_nick)
            synchronized_users[user_id] = minecraft_nick

            # Save the updated synchronized users
            write_synchronized_users(synchronized_users)

            bot.reply_to(message, f"✅ {user_name}, ваш Minecraft ник ({minecraft_nick}) был синхронизирован с вашим Telegram аккаунтом!")
        else:
            bot.reply_to(message, "⚠️ Пожалуйста, укажите ваш Minecraft ник. Используйте: /sync <minecraft_nick>")

    def get_nickname(user_id):
        synchronized_users = read_synchronized_users()
        return synchronized_users.get(user_id, None)

    @bot.message_handler(commands=['showsync'])
    def show_synchronized_users(message):
        """Command handler to show all synchronized users."""
        synchronized_users = read_synchronized_users()

        if synchronized_users:
            sync_list = ""
            for user_id, minecraft_nick in synchronized_users.items():
                # You can fetch the user name directly from the message handler or elsewhere in your bot
                # Since the user_id is already in your system, you don't need get_chat to fetch names
                
                user_name =  bot.get_chat(user_id).first_name or "Пользователь"
                sync_list += f"<b>{user_name}</b>: {minecraft_nick}\n"
            
            bot.reply_to(message, f"📜 <b>Синхронизированные пользователи:</b>\n{sync_list}",parse_mode="HTML")
        else:
            bot.reply_to(message, "❌ <b>Нет синхронизированных пользователей.</b>",parse_mode="HTML")

    #=============================< AMLET PRIVELLAGES PART >=============================

    # Privileges configuration
    PRIVILEGES = {
        "ВИП ♠": {"group": "vip", "cost": 400},
        "СТРОИТЕЛЬ ⚒": {"group": "builder", "cost": 1200},
        "ЭЛИТА 💎": {"group": "elite", "cost": 2400},
        "АРХИТЕКТОР 💡": {"group": "architect", "cost": 4800},
        "АДМИН ★": {"group": "admin", "cost": 8000},
        "СУПЕРВАЙЗЕР ✦": {"group": "supervisor", "cost": 16000},
    }

    # Command to display privileges with buttons
    @bot.message_handler(func=lambda message: "купить привелегию" in message.text.lower())
    def display_privileges(message):
        user_id = message.from_user.id

        # Create an inline keyboard with privileges as buttons
        markup = InlineKeyboardMarkup()
        for privilege_name, details in PRIVILEGES.items():
            button_text = f"{privilege_name} - {details['cost']} Amlet Coins"
            button_callback_data = f"buy:{details['group']}:{details['cost']}"
            markup.add(InlineKeyboardButton(button_text, callback_data=button_callback_data))
        
        # Display the list of privileges
        bot.reply_to(
            message,
            "🛒 Выберите привелегию для покупки:",
            reply_markup=markup
        )

    # Callback query handler for privilege purchase
    @bot.callback_query_handler(func=lambda call: call.data.startswith('buy:'))
    def handle_purchase(call):
        user_id = call.from_user.id
        data = call.data.split(':')
        privilege_group = data[1]
        privilege_cost = int(data[2])

        # Read current balances
        fortunes = read_balances()
        user_coins = fortunes.get(user_id, 0.0)

        if user_coins >= privilege_cost:

            # Get the user's Minecraft nickname
            minecraft_nick = get_nickname(user_id)
            print(minecraft_nick)
            if not minecraft_nick:
                bot.answer_callback_query(call.id, "❌ Вы не синхронизировали свой Minecraft ник. Используйте /sync ваш никнейм.")
                return

            # Execute RCON command to set privilege
            rcon_command = f"/lp user {minecraft_nick} group set {privilege_group}"
            print(rcon_command)

            # Submit the RCON command to the executor
            future = executor.submit(send_rcon_command, rcon_command)

            def send_response(f):
                try:
                    success = f.result()
                    print(success)
                    if success:  # Assuming send_rcon_command returns True/False
                        bot.answer_callback_query(call.id, f"✅ Привелегия '{privilege_group}' успешно выдана!")
                        # Deduct coins
                        fortunes[user_id] = user_coins - privilege_cost
                        write_balances(fortunes)
                    else:
                        bot.answer_callback_query(call.id, "❌ Ошибка при выполнении команды RCON.")
                except Exception as e:
                    bot.answer_callback_query(call.id, f"❌ Произошла ошибка: {str(e)}")

            # Add a callback to handle the response when the command completes
            future.add_done_callback(send_response)
        else:
            bot.answer_callback_query(call.id, f"❌ У вас недостаточно Amlet Coins для покупки этой привелегии. Ваш баланс: {round(user_coins, 2)} 💰")

    # Example placeholder functions for RCON and nickname
    def get_nickname(user_id):
        """Retrieve the Minecraft nickname associated with a user."""
        synchronized_users = read_synchronized_users()  # Assuming this is implemented
        return synchronized_users.get(user_id)

    




