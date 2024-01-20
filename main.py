import telebot
import sqlite3
import threading
import os
from telebot import types
import time
from telebot.types import Message

admin="RandomGor"

# Function to load environment variables from .env file
def load_env():
    with open('.env', 'r') as file:
        for line in file:
            # Ignore comments and empty lines
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

# Load environment variables
load_env()

# Access environment variables
tg_token = os.environ.get('TELEGRAM_API_TOKEN').strip("'")

# Use threading.local() to create a separate connection and cursor for each thread
local_data = threading.local()

def get_connection():
    # Create a new connection if it doesn't exist for the current thread
    if not hasattr(local_data, 'connection'):
        local_data.connection = sqlite3.connect('server_data.db', check_same_thread=False)
    return local_data.connection

def get_cursor():
    # Create a new cursor if it doesn't exist for the current thread
    if not hasattr(local_data, 'cursor'):
        local_data.cursor = get_connection().cursor()
    return local_data.cursor

# Create a table to store server data if it doesn't exist
with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            telegram_username TEXT,
            server_name TEXT,
            num_players INTEGER
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS xbox_usernames (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_username TEXT UNIQUE,
            xbox_username TEXT
        )
    ''')
    conn.commit()


bot = telebot.TeleBot(tg_token)

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


# Dictionary to store user data temporarily
user_data = {}

@bot.message_handler(commands=['start'])
def handle_start(message):
    start_text = (
        "👋 Привет!\n\n"
        "Я телеграм бот 🤖, созданный 'Стариком-Гором-Котом-Куртом (как бы вы меня не называли)'.\n"
        "**Моя цель** - помочь вам играть в ваш любимый майнкрафт с друзьями и провести отличное время. 🎮\n\n"
        "Давайте начнем! Используйте команду /help, чтобы узнать как пользоватся мной и как призвать к тебе играть в Minecraft. 🌐"
    )

    bot.reply_to(message, start_text, parse_mode="Markdown")


@bot.message_handler(commands=['help'])
def show_help(message):
    help_text = (
        "🤖 **Bot Commands** 🤖\n\n"
        "/start - Инициирует разговор с ботом.\n"
        "/host - Начать процесс создания сервера Minecraft.\n"
        "/stophost - Завершить хостинг сервера.\n"
        "/register - Зарегистрировать Xbox username.\n"
        "/xbox - Показать зарегистрированные Xbox usernames.\n"
        "/delete_xbox - Удалить Xbox username из регистрации.\n"
        "/hosts - Показать список активных серверов.\n"
        "/help - Показать это сообщение с командами.\n\n"
        "🎮 **Инструкции:**\n"
        "1. Используйте /host, чтобы начать создание сервера.\n"
        "2. Используйте /stophost, чтобы завершить хостинг сервера.\n"
        "3. Используйте /register, чтобы зарегистрировать Xbox username.\n"
        "4. Используйте /xbox, чтобы посмотреть зарегистрированные Xbox usernames.\n"
        "5. Используйте /delete_xbox, чтобы удалить Xbox username из регистрации.\n"
        "6. Используйте /hosts, чтобы посмотреть активные сервера.\n"
        "7. Используйте /help, чтобы посмотреть это сообщение с командами.\n\n"
        "📚 **Помощь:**\n"
        "Если у вас есть вопросы или нужна дополнительная помощь, я умный🧠 бот, обратитесь ко мне списовая мой ник (@OmletIsAliveBot) и задавая ваш вопрос, буду рад вам помочь. Могу помочь с моими коммандами и просто пообщятся (но предупрейдаю что мои знания ограничены). А также могу делать поиски в Google\nЕсли и я не смог помочь обращяйтесь к моему создателю - @RandomGor"
    )

    bot.reply_to(message, help_text, parse_mode="Markdown")


@bot.message_handler(commands=['host'])
def start_hosting(message):
    try:
        # Retrieve the Telegram username from the message
        telegram_username = message.from_user.username

        # Check if the user is already hosting
        cursor = get_cursor()
        cursor.execute("SELECT COUNT(*) FROM servers WHERE user_id = ?", (message.chat.id,))
        hosting_count = cursor.fetchone()[0]

        if hosting_count > 0:
            bot.reply_to(message, "Вы уже являетесь хостом. Вы не можете создать больше одного сервера.")
        else:
            # Save the username in user_data
            user_data[message.chat.id] = {'telegram_username': telegram_username}

            # Ask for the name of the server
            msg = bot.reply_to(message, "Пишите имя вашего сервера")
            bot.register_next_step_handler(msg, process_server_name_step)

    except Exception as e:
        bot.reply_to(message, 'Что-то пошло не так при получении вашего Telegram юзернейма.')


def process_server_name_step(message):
    try:
        # Save the server name in user_data
        user_data[message.chat.id]['server_name'] = message.text

        # Ask for the number of players
        question = "Сколько людей могут зайти к вам на сервер? (пишите только цифру)"
        msg = bot.send_message(message.chat.id, question, reply_markup=types.ForceReply(selective=True))

        # Register the next step handler
        bot.register_next_step_handler(msg, process_players_step)

    except Exception as e:
        bot.reply_to(message, 'Отвечайте мне на сообщение пожалуйста.')

def process_players_step(message):
    try:
        # Save the number of players in user_data
        user_data[message.chat.id]['num_players'] = int(message.text)

        # Commit the user_data to the database
        commit_to_database(message)

        # Display the gathered information
        telegram_username = user_data[message.chat.id]['telegram_username']
        server_name = user_data[message.chat.id]['server_name']
        num_players = user_data[message.chat.id]['num_players']

        # Format the reply message
        reply = (
            f"🎮 Создан хост сервера!\n\n"
            f"👤 <b>Хост:</b> @{telegram_username}\n"
            f"🌐 <b>Имя Сервера:</b> {server_name}\n"
            f"👥 <b>Число Игроков:</b> {num_players}\n\n"
            f"✨ <b>Приходите почилим :)</b>"
        )

        # Mention everyone in the group
        bot.send_message(message.chat.id, reply, parse_mode="HTML", disable_notification=True)

    except ValueError as ve:
        bot.reply_to(message, f'Ошибка: {ve}. Прошу писать только число игроков.')

    except Exception as e:
        bot.reply_to(message, f'Упс, что-то пошло не так: {e}.')

    finally:
        # Clear user_data to avoid looping
        user_data.pop(message.chat.id, None)

def commit_to_database(message):
    try:
        # Retrieve data from user_data
        telegram_username = user_data[message.chat.id]['telegram_username']
        server_name = user_data[message.chat.id]['server_name']
        num_players = user_data[message.chat.id]['num_players']

        # Save the data to SQLite database
        user_id = message.chat.id
        cursor = get_cursor()
        cursor.execute("INSERT INTO servers (user_id, telegram_username, server_name, num_players) VALUES (?, ?, ?, ?)",
                       (user_id, telegram_username, server_name, num_players))
        get_connection().commit()

    except Exception as e:
        bot.reply_to(message, f'Упс, что-то пошло не так при сохранении данных в базу данных: {e}.')


@bot.message_handler(commands=['stophost'])
def stop_hosting(message):
    try:
        # Retrieve the Telegram username from the message
        telegram_username = message.from_user.username

        # Specify the allowed username(s) that can stop hosting
        allowed_usernames = [telegram_username, admin]

        # Check if the user has the permission to stop hosting
        if telegram_username not in allowed_usernames:
            bot.reply_to(message, "У вас нет прав на остановку хостинга.")
            return

        # Retrieve the Telegram user ID
        user_id = message.chat.id

        # Use a context manager for the cursor
        with get_connection() as conn:
            # Check if the user is currently hosting
            cursor = conn.cursor()
            cursor.execute("SELECT server_name FROM servers WHERE user_id = ? LIMIT 1", (user_id,))
            hosting_info = cursor.fetchone()

            if not hosting_info:
                bot.reply_to(message, "Вы не являетесь текущим хостом.")
            else:
                server_name = hosting_info[0]

                # Stop hosting by removing the server entry
                cursor.execute("DELETE FROM servers WHERE user_id = ?", (user_id,))
                conn.commit()

                reply = f"Хостинг для сервера '{server_name}' был успешно остановлен."
                bot.reply_to(message, reply)

    except Exception as e:
        bot.reply_to(message, f'Упс, что-то пошло не так: {e}.')



@bot.message_handler(commands=['hosts'])
def show_hosts(message):
    try:
        # Retrieve the list of hosts from the database
        cursor = get_cursor()
        cursor.execute("SELECT s.telegram_username, s.server_name, s.num_players, x.xbox_username FROM servers s LEFT JOIN xbox_usernames x ON s.telegram_username = x.telegram_username")
        hosts = cursor.fetchall()

        if not hosts:
            bot.reply_to(message, "На данный момент нет активных хостов.")
        else:
            # Create a styled message for each host
            host_messages = []

            for host in hosts:
                username, server_name, num_players, xbox_username = host
                host_text = f"👤 @{username}\n🌐 {server_name}\n👥 Игроков: {num_players}\n🎮 Xbox: {xbox_username}"
                host_messages.append(host_text)

            # Combine all host messages into one reply
            reply = "\n\n".join(host_messages)

            # Send the reply without inline buttons
            bot.reply_to(message, reply)

    except Exception as e:
        bot.reply_to(message, f'Упс, что-то пошло не так: {e}.')


@bot.message_handler(commands=['register'])
def register_xbox_username(message):
    try:
        # Ask the user for their Xbox username
        question = "Введите ваш Xbox username"
        msg = bot.send_message(message.chat.id, question, reply_markup=telebot.types.ForceReply(selective=True))

        # Register the next step handler
        bot.register_next_step_handler(msg, process_xbox_username_step)

    except Exception as e:
        bot.reply_to(message, 'Что-то пошло не так при регистрации Xbox юзернейма.')

def process_xbox_username_step(message):
    try:
        # Retrieve the Xbox username from the message
        xbox_username = message.text

        # Retrieve the Telegram username from the message
        telegram_username = message.from_user.username

        # Save the data to the Xbox_usernames table
        cursor = get_cursor()
        cursor.execute("INSERT OR REPLACE INTO xbox_usernames (telegram_username, xbox_username) VALUES (?, ?)",
                       (telegram_username, xbox_username))
        get_connection().commit()

        reply = f"Ваш Xbox username ({xbox_username}) зарегистрирован.🌐"
        bot.reply_to(message, reply)

    except sqlite3.IntegrityError:
        bot.reply_to(message, 'Этот Telegram username уже связан с другим Xbox username. Используйте другой Telegram username для регистрации.')
    except Exception as e:
        bot.reply_to(message, f'Упс, что-то пошло не так: {e}.')

@bot.message_handler(commands=['xbox'])
def show_xbox_usernames(message):
    try:
        # Retrieve Xbox usernames from the database
        cursor = get_cursor()
        cursor.execute("SELECT telegram_username, xbox_username FROM xbox_usernames")
        xbox_data = cursor.fetchall()

        if not xbox_data:
            bot.reply_to(message, "На данный момент нет зарегистрированных Xbox usernames.")
        else:
            # Create a formatted message with monospace formatting for Xbox usernames
            xbox_list = "\n".join(f"🎮 <b>@{telegram_username}</b>: <code>{xbox_username}</code>" for telegram_username, xbox_username in xbox_data)
            reply = f"Зарегистрированные Xbox usernames:\n{xbox_list}"
            bot.reply_to(message, reply, parse_mode="HTML")

    except telebot.apihelper.ApiException as e:
        # Handle the error by accessing the error message using str(e)
        bot.reply_to(message, f'Упс, что-то пошло не так: {str(e)}')

    except Exception as e:
        bot.reply_to(message, f'Упс, что-то пошло не так: {str(e)}.')




@bot.message_handler(commands=['deletexbox'])
def delete_xbox_username(message):
    try:
        # Retrieve the Telegram username from the message
        telegram_username = message.from_user.username

        # Specify the allowed username(s) that can delete from the database
        allowed_usernames = [telegram_username,admin]

        # Check if the user has the permission to delete Xbox usernames
        if telegram_username not in allowed_usernames:
            bot.reply_to(message, "У вас нет прав на удаление Xbox username.")
            return

        # Check if the user has a registered Xbox username
        cursor = get_cursor()
        cursor.execute("SELECT xbox_username FROM xbox_usernames WHERE telegram_username = ?", (telegram_username,))
        xbox_username = cursor.fetchone()

        if not xbox_username:
            bot.reply_to(message, "У вас нет зарегистрированного Xbox username.")
        else:
            # Delete the Xbox username from the database
            cursor.execute("DELETE FROM xbox_usernames WHERE telegram_username = ?", (telegram_username,))
            get_connection().commit()

            bot.reply_to(message, f"Ваш Xbox username ({xbox_username[0]}) успешно удален.")

    except Exception as e:
        bot.reply_to(message, f'Упс, что-то пошло не так: {e}.')


# |=============================================================< SMART BOT >=============================================================|

import nltk
from nltk.tokenize import word_tokenize
import pymorphy2
import numpy as np
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout
import random
import json
import pickle
from requests.exceptions import ConnectionError, ReadTimeout
import re
from googletrans import Translator
from googlesearch import search

# Download NLTK resources for tokenization
nltk.download('punkt')

# Initialize pymorphy2
morph = pymorphy2.MorphAnalyzer()

# Loading the intents Data
with open('intents.json', encoding='utf-8') as file:
    data = json.load(file)

# ----------------------------< Making Bag of Words for Training >-------------------------------

try:
    with open('data.pickle', 'rb') as f:
        words, labels, training, output = pickle.load(f)
except FileNotFoundError:
    words = []
    labels = []
    docs_x = []
    docs_y = []

    for intent in data['intents']:
        for pattern in intent['patterns']:
            wrds = word_tokenize(pattern)
            wrds = [morph.parse(word)[0].normal_form for word in wrds]
            words.extend(wrds)
            docs_x.append(wrds)
            docs_y.append(intent['tag'])

        if intent['tag'] not in labels:
            labels.append(intent['tag'])

    words = sorted(list(set(words)))

    labels = sorted(labels)

    training = []
    output = []

    out_empty = [0 for _ in range(len(labels))]

    for x, doc in enumerate(docs_x):
        bag = []

        wrds = [morph.parse(word)[0].normal_form for word in doc]

        for w in words:
            if w in wrds:
                bag.append(1)
            else:
                bag.append(0)

        output_row = out_empty[:]
        output_row[labels.index(docs_y[x])] = 1

        training.append(bag)
        output.append(output_row)

    with open('data.pickle', 'wb') as f:
        pickle.dump((words, labels, training, output), f)

training = np.array(training)
output = np.array(output)

# ----------------------------< Training the Model >-------------------------------

model = Sequential()
model.add(Dense(128, input_dim=len(training[0]), activation='relu'))
model.add(Dropout(0.5))
model.add(Dense(64, activation='relu'))
model.add(Dropout(0.5))
model.add(Dense(len(output[0]), activation='softmax'))

# Compile the model
model.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy'])

# Import necessary libraries
from keras.models import load_model

# < Fitting then Saving the Model >
try:
    print("Attempting to load the model...")
    model = load_model('TelegramChatBot.keras')
    print("\n"*10)
    print("="*100)
    print("\t\t\t\tModel loaded successfully!")
    print("="*100,"\n")
except Exception as e:
    print(f"Failed to load the model. Error: {e}")
    
    # Suppress TensorFlow warning messages
    import os
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
    
    # Train the model with less verbose output
    print("Training the model...")
    model.fit(training, output, epochs=250, batch_size=5, verbose=1)
    
    # Save the trained model
    print("Saving the trained model...")
    model.save('TelegramChatBot.keras')
    print("\n"*10)
    print("="*100)
    print("\t\t\t\tModel saved successfully!")
    print("="*100,"\n")



# ----------------------------< Making Predictions >-------------------------------

def bag_of_words(s, words):
    bag = [0 for _ in range(len(words))]

    s_words = word_tokenize(s)
    s_words = [morph.parse(word)[0].normal_form for word in s_words]

    for se in s_words:
        for i, w in enumerate(words):
            if w == se:
                bag[i] = 1

    # Reshape the bag to match the expected input shape
    return np.array(bag).reshape(1, len(words))

bot_username = bot.get_me().username

def remove_bot_mention(text):
    pattern = re.compile(r'@OmletIsAliveBot', re.IGNORECASE)
    cleaned_text = re.sub(pattern, '', text)
    return cleaned_text

def extract_quoted_text(text):
    pattern = re.compile(r'["\'](.*?)["\']')
    matches = re.findall(pattern, text)
    return matches[0] if matches else ""


# ----------------------------< Other Responses Functions >-------------------------------

def translate(text):
    if not text:
        return ""
    translator = Translator()
    translation = translator.translate(text, dest='hy')
    return translation.text


def google_search(query, num_results=1):
    try:
        search_results = list(search(query, num_results=num_results))
        return search_results[0] if search_results else None
    except Exception as e:
        print(f"Ошибка слушай! --> {e}")
        return None

# Define a new function to handle messages mentioning the bot
@bot.message_handler(func=lambda message: bot_username.lower() in message.text.lower())
def handle_mention(message):
    # Get the text message from the user
    user_message = remove_bot_mention(message.text)
    other_response = False
    other_response_tags = ["translate","search"]

    # Process the user's message and generate a response
    input_lemmatized = [morph.parse(word)[0].normal_form for word in word_tokenize(user_message)]
    results = model.predict([bag_of_words(' '.join(input_lemmatized), words)])[0]
    result_index = np.argmax(results)
    tag = labels[result_index]

    if tag not in other_response_tags:
        if results[result_index] > 0.6:
            for tg in data['intents']:
                if tg['tag'] == tag:
                    responses = tg['responses']
                    break

            response = random.choice(responses)
        else:
            response = "Я не понял, попробуйте еще раз, в этот раз без ошибок. Либо этот функционал у меня отсуствует 🤷‍♂️"
    else:
        if tag == 'translate':
            ext = extract_quoted_text(user_message)
            if ext != "":
                tr = translate(ext)
                response = [f"Вот ваш перевод '{tr}'. Всегда словарь у тебя под рукой 😉"]
            else: response = ["Пишите то что хотите переводить в скобках ('то что хотите переводить')"]
        if tag == 'search':
            ext = extract_quoted_text(user_message)
            if ext != "":
                search_result = google_search(ext)
                if search_result:
                    response = [f"Вот ваши результаты поиска\n {search_result} \n\nВсегда поисковик у тебя под рукой 😉"]
                else:
                    response = ["Сори нечо не смог найти в гугле по этому запросу 🤷‍♂️"]                
            else: response = ["Пишите то что хотите поискать в скобках ('то что хотите погуглить')"]
        
    # Reply to the user with the generated response
    bot.reply_to(message, response)
    print(f"[{tag}] tag was used.")

def main():
    while True:
        try:
            bot.polling(none_stop=True,timeout=60)
            break
        except (ConnectionError, ReadTimeout) as e:
            print(f"Connection error: {e}")
            print("Retrying in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    main()
    
    





