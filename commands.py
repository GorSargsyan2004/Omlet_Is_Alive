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

server_ip = os.environ.get('MINECRAFT_SERVER_IP').strip("'")
server_port = int(os.environ.get('MINECRAFT_SERVER_PORT', 25565))  # Default to 25565
rcon_password = os.environ.get('RCON_PASSWORD').strip("'")  # RCON password
rcon_port = int(os.environ.get('RCON_PORT', 25575))  # RCON port, default 25575
OPENWEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY').strip("'")


# Global variable to control the tracking thread
tracking_active = False
tracking_thread = None

tracking_joins_active = False
tracking_joins_thread = None

authorized_usernames = ['RandomGor', 'ximozka_nnr']

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
    executor = ProcessPoolExecutor(max_workers=1)


    @bot.message_handler(commands=['say'])
    def handle_say_command(message: Message):
        command_text = message.text.split(maxsplit=1)

        if len(command_text) < 2:
            bot.reply_to(message, "⚠️ Пожалуйста, укажите что хотите написать в чате сервера.")
            return

        msg = command_text[1]
        sender_username = message.from_user.username

        authorized_usernames = ['RandomGor', 'ximozka_nnr']


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

    # Command to retrieve and send the last 5 messages to the bot
    @bot.message_handler(commands=['last'])
    def handle_last_1_message(message: Message):
        messages = get_last_x_messages(1)
        
        if messages:
            response = "\n".join(messages)
            bot.reply_to(message, f"📝 Последнее сообщение:\n{response}", parse_mode="HTML")
        else:
            bot.reply_to(message, "⚠️ Не удалось найти сообщения игроков.")

    # Command to retrieve and send the last 5 messages to the bot
    @bot.message_handler(commands=['last10'])
    def handle_last_10_messages(message: Message):
        messages = get_last_x_messages(10)
        
        if messages:
            response = "\n".join(messages)
            bot.reply_to(message, f"📝 Последние 10 сообщений игроков:\n{response}", parse_mode="HTML")
        else:
            bot.reply_to(message, "⚠️ Не удалось найти сообщения игроков.")

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

    @bot.message_handler(commands=['serverStatus'])
    def handle_server_status(message):
        status = server.status()
        try:
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
            response = f"❌ <b>Сервер статус:</b> Оффлайн\n⚠️ <b>Ошибка:</b> {str(e)}"
        
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
        status = server.status()
        try:
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
            "• /privileges [привилегия] - Посмотреть информацию о правах и задачах каждой привилегии.\n\n"
            
            "📦 <b>Мемы и развлечения:</b>\n"
            "• /scrape - Получить мемы из интернета и сохранить их (доступно только некоторым пользователям).\n"
            "• /meme - Показать фото-мемы, полученные с интернета.\n"
            "• /memev - Показать видео-мемы, полученные с интернета.\n\n"
            
            "💬 <b>Чат-команды:</b>\n"
            "• /say - Чтобы послать сообщение в сервер (доступно всем).\n"
            "• /cmd - Ввести команды для консоли сервера (доступно только некоторым пользователям).\n"
            "• /chat [текст]- Чтобы поискать в чате конкретное слово или вырожение (доступно только некоторым пользователям).\n"
            "• /track - Чтобы следить за чатом сервера в реальном времени (доступно только некоторым пользователям).\n"
            "• /stoptrack - Закончить следить за чатом (доступно только некоторым пользователям).\n"
            "• /trackJoin - Следить за тем кто заходит и выходит с сервера (доступно только некоторым пользователям).\n"
            "• /stoptrackJoin - Закончить следить за тем кто заходит и выходит с сервера (доступно только некоторым пользователям).\n"
            "• /last, /last5, /last10 - Показать последние 1, 5 или 10 сообщений игроков на сервере.\n\n"
            
            "🔹 <b>Дополнительные действия:</b>\n"
            "Бот также умеет:\n"
            "• Ударять 🤜\n"
            "• Дать пощёчину 🖐️\n"
            "• Целовать 💋\n"
            "• Обнять 🤗\n"
            "• Делать м**ет 🫦\n"
            "• Т**нуть 😉\n"
            "• Делать к**и 👅\n\n"
            
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

    