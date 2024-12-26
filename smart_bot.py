# |==========================================================< SMART BOT >==========================================================|
import openai
import telebot
import os
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
from keras.models import Sequential
from keras.layers import Dense, Dropout
from keras.optimizers import Adam
from googletrans import Translator
from googlesearch import search
import html
from collections import deque
from telebot import types
from collections import defaultdict
from telebot.types import Message
import time
from datetime import datetime
import threading
import schedule
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Download NLTK resources for tokenization
nltk.download('punkt')

# Initialize pymorphy2
morph = pymorphy2.MorphAnalyzer()

API_KEY_GPT =  os.environ.get('API_KEY_GPT').strip("'")

# Loading the intents Data
with open('intents.json', encoding='utf-8') as file:
    data = json.load(file)

authorized_usernames = ['RandomGor', 'ximozka_nnr']

# Temporary storage for user IDs
pending_accounts = {}

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

# ----------------------------< Making Bag of Words for Training >-------------------------------

def making_bag_of_words_and_training(bot):
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

    model.add(Dense(256, input_dim=len(training[0]), activation='relu'))  
    model.add(Dropout(0.5))  

    model.add(Dense(128, activation='relu')) 
    model.add(Dropout(0.5))

    model.add(Dense(64, activation='relu'))  
    model.add(Dropout(0.5))

    model.add(Dense(len(output[0]), activation='softmax')) 

    model.compile(loss='categorical_crossentropy', 
                optimizer=Adam(learning_rate=0.0005), 
                metrics=['accuracy'])


    from keras.models import load_model

    try:
        print("Attempting to load the model...")
        model = load_model('TelegramChatBot.keras')
        print("\n"*10)
        print("="*50)
        print("\t\tModel loaded successfully!")
        print("="*50,"\n")
    except Exception as e:
        print(f"Failed to load the model. Error: {e}")
        
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
        
        print("Training the model...")
        model.fit(training, output, epochs=500, batch_size=8, verbose=2)  
        
        # Save the trained model
        print("Saving the trained model...")
        model.save('TelegramChatBot.keras')
        print("\n"*10)
        print("="*100)
        print("\tModel saved successfully!")
        print("="*100,"\n")

    def extract_quoted_text(text):
        pattern = re.compile(r'["\'](.*?)["\']')
        matches = re.findall(pattern, text)
        return matches[0] if matches else ""

    def remove_bot_mention(text, bot_username):
        pattern = re.compile(rf'{bot_username}', re.IGNORECASE)
        cleaned_text = re.sub(pattern, '', text)
        return cleaned_text

    def convert_to_html_bold(text):
        text = html.escape(text) 
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'\*(.*?)\*', r'<b>\1</b>', text)
        return text

    # ----------------------------< CHAT GBT >-------------------------------
    

    chat_history = defaultdict(list)

    def track_message(message):
        chat_id = message.chat.id

        content = ""

        if message.reply_to_message:
            replied_user = (
                f"@{message.reply_to_message.from_user.username}"
                if message.reply_to_message.from_user and message.reply_to_message.from_user.username
                else "неизвестный пользователь"
            )

            if message.reply_to_message.text:
                replied_content = f"текстовое сообщение"
            elif message.reply_to_message.photo:
                replied_content = "картинку"
            elif message.reply_to_message.video:
                replied_content = "видео"
            elif message.reply_to_message.voice:
                replied_content = "голосовое сообщение"
            elif message.reply_to_message.video_note:
                replied_content = "видеосообщение"
            elif message.reply_to_message.sticker:
                replied_content = "стикер"
            else:
                replied_content = "сообщение неизвестного типа"


            if message.text:
                content = f"Сообщение от @{message.from_user.username} в ответ @{replied_user} {replied_content}: {message.text}"
            elif message.photo:
                content = f"@{message.from_user.username} кинул(а) картинку в чат в ответ на @{replied_user} {replied_content}"
            elif message.video:
                content = f"@{message.from_user.username} кинул(а) видео в чат в ответ на @{replied_user} {replied_content}"
            elif message.voice:
                content = f"@{message.from_user.username} кинул(а) голосовое сообщение в ответ на @{replied_user} {replied_content}"
            elif message.video_note:
                content = f"@{message.from_user.username} кинул(а) видеосообщение в ответ на @{replied_user} {replied_content}"
            elif message.sticker:
                content = f"@{message.from_user.username} отправил(а) стикер в ответ на @{replied_user} {replied_content}"
            else:
                content = f"@{message.from_user.username} отправил(а) сообщение неизвестного типа в ответ на @{replied_user} {replied_content}"
        else:
            if message.text:
                content = f"Сообщение от @{message.from_user.username}: {message.text}"
            elif message.photo:
                content = f"@{message.from_user.username} кинул(а) картинку в чат"
            elif message.video:
                content = f"@{message.from_user.username} кинул(а) видео в чат"
            elif message.voice:
                content = f"@{message.from_user.username} кинул(а) голосовое сообщение"
            elif message.video_note:
                content = f"@{message.from_user.username} кинул(а) видеосообщение"
            elif message.sticker:
                content = f"@{message.from_user.username} отправил(а) стикер"
            else:
                content = f"@{message.from_user.username} отправил(а) сообщение неизвестного типа"

        chat_history[chat_id].append({'role': 'user', 'content': content})

        chat_history[chat_id] = chat_history[chat_id][-20:]

    def fetch_chat_history(chat_id):
        return chat_history.get(chat_id, [])

    def get_response_gpt_with_history(message, user_message, chat_id):
        try:
            # Fetch stored chat history
            chat_messages = fetch_chat_history(chat_id)

            # Append the new user message to the history
            full_context = chat_messages 

            sys_prmpt =  '''Пожалуйста, давайте немного краткие ответы чтобы они поместились в сообщение для телеграмма. И на русском. 
                        Помни твое имя Амлет и ты находишся в телеграм группе игроков майнкрафт, кросплатформленный сервер.
                        У нас есть личный сервер Amlet_House (это и имя нашей группы телеграм). Админ Группы
                        Гор, и создатель телеграм бота на котором ты работаешь сейчас, твой код написан Гором, его
                        юзернейм в телеграм @RandomGor. И еще помни что Гор любит девушку Вику, вот ее юзернейм @ximozka_nnr.
                        И всегда пиши КРАСИВО используй емодзи, используй '\n', тоесть новые строки для красивого ответа, ну и если хочешь текст какой то сделать широким
                        (bold) используй **жирный текст** такой способ чтобы сделать текст bold. И еще если кому то конкретно надо ответить или ему/ей что то сказать
                        НЕ ЗАБУДЬ УПОМЯНУТЬ юзернейм пользователя, например @ximozka_nnr чтобы они увидели что ты написал когда упоменал их.
                        
                        И еще тебе будет представлено чат история (максимум 20 сообщений), будут они в таком формате 'Сообщени от <юзернейм>: <Сообщение>' ну или
                        это может быть не сообщение а какое то голосовое сообщение или жидео сообщение и так далее, ты все будешь видеть, даже и твои ответы на предыдущие вопросы.
                        И если в сообщениях юзеров есть слово 'Амлет' это значит звали тебя чтобы ответить, ПОСЛЕДНЕЕ сообщение где будет присуствовать 'Амлет'
                        это значит что ты ДОЛЖЕН БУДЕШЬ ОТВЕТИЬ НА ЭТО ПОСЛЕДНЕЕ СООБЩЕНИЕ, учитывая весь контекст переписки чата ЕСЛИ НУЖНО. У тебя есть их 
                        юзернеймы, можешь ВОСПОЛЬЗОВАТСЯ ими чтобы кого то что то сказать или передать. Тебя могут спрашивать вопросы что зависимо от контекста
                        будь внимателен над такими вопросами и отвечай на них всегда ИРОНИЧНО, с юмором когда надо и СЕРЕЗНО КОГДА НАДОБНО :)

                        И НЕ используй форму ответа типо - "Ответ Амлет: <твой ответ>", просто пиши твой ответ без "Ответ Амлет", окей?

                        И когда спрашивают вопросы не о контексте чата а просто познавательный вопрос, хотят чтобы ты давал им информацию, то не используй юмор,
                        тут уже отвечай СЕРЕЗНО.

                        Все, желаю тебе удачи, ты наш асистент в группе Amlet_House отвечай на любые вопросы.
                        '''

            openai.api_key = API_KEY_GPT

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {'role': 'system', 'content': sys_prmpt}
                ] + full_context
            )
            gpt_response = response['choices'][0]['message']['content']

            return gpt_response

        except Exception as e:
            print(f"Error preparing GPT request: {str(e)}")
            return "Ошибка какая то, взгляни в логи @RandomGor але."


    @bot.message_handler(func=lambda message: "гбт" in message.text.lower().split(maxsplit=2)[0])
    def handle_gpt(message):
        chat_id = message.chat.id

        track_message(message)

        thinking_message = bot.reply_to(message, "Думаю... 🔄")

        try:
            prompt = message.text.replace("гбт", "Амлет").strip()
            prompt = message.text.replace("Гбт", "Амлет").strip()
            prompt = message.text.replace("ГБТ", "Амлет").strip()

            response = get_response_gpt_with_history(message, prompt, chat_id)

            bot.delete_message(chat_id, thinking_message.message_id)

            chat_history[chat_id].append({
                'role': 'assistant',
                'content': f"Ответ Амлет: {response}"
            })

            response = re.sub("Ответ Амлет:", '', response)
            response = convert_to_html_bold(response)

            # Send the GPT response
            bot.send_message(chat_id, response, parse_mode="HTML")
        except Exception as e:
            # Handle errors gracefully
            bot.delete_message(chat_id, thinking_message.message_id)
            bot.reply_to(message, "Произошла ошибка при обработке запроса 😔")
            print(f"Error in handle_gpt: {str(e)}")



    # ----------------------------< OMLET PART >-------------------------------

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

    #bot_username = bot.get_me().username
    bot_username = "амлет"

    # Define a new function to handle messages mentioning the bot
    @bot.message_handler(func=lambda message: bot_username.lower() in message.text.lower().split(maxsplit=2)[0])
    def handle_mention(message):
        # Get the text message from the user
        user_message = remove_bot_mention(message.text,bot_username)
        other_response = False
        other_response_tags = ["translate","search","kiss","kick","kickToBalls","chapalax","DoMinet","DoKuni","DoFuck","Hugging",
                               "silent","probability","question"]

        # Process the user's message and generate a response
        input_lemmatized = [morph.parse(word)[0].normal_form for word in word_tokenize(user_message)]
        results = model.predict([bag_of_words(' '.join(input_lemmatized), words)])[0]
        result_index = np.argmax(results)
        tag = labels[result_index]

        if tag not in other_response_tags:
            if results[result_index] > 0.8:
                for tg in data['intents']:
                    if tg['tag'] == tag:
                        responses = tg['responses']
                        break

                response = random.choice(responses)
            else:
                #response = [get_response_gpt_with_history(message, user_message,message.chat.id)]
                response = ["Я не понял, попробуйте еще раз, в этот раз без ошибок. Либо этот функционал у меня отсуствует 🤷‍♂️"]
        else:
            if tag == 'translate':
                ext = extract_quoted_text(user_message)
                if ext != "":
                    tr = translate(ext)
                    response = [f"Вот ваш перевод '{tr}'. Всегда словарь у тебя под рукой 😉"]
                else: response = ["Пишите то что хотите переводить в скобках ('то что хотите переводить')"]
            elif tag == 'search':
                ext = extract_quoted_text(user_message)
                if ext != "":
                    search_result = google_search(ext)
                    if search_result:
                        response = [f"Вот ваши результаты поиска\n {search_result} \n\nВсегда поисковик у тебя под рукой 😉"]
                    else:
                        response = ["Сори нечо не смог найти в гугле по этому запросу 🤷‍♂️"]                
                else: response = ["Пишите то что хотите поискать в скобках ('то что хотите погуглить')"]
            else:

                if tag == "silent":
                    bot.reply_to(message.reply_to_message, "🤐")
                    response = ["ну лан"]
                if tag == "probability":
                    p = round(random.random(),2) * 100
                    response = [f"Вероятность этому премерно {p}% думаю 🧐"]
                if tag == "question":
                    answer = random.choice([
                                            "Хмммм, кажется да 🤔",  
                                            "Ну, какбы да, очевидно же 😊",  
                                            "Однозначно верно! ✅",  
                                            "Конечно нет! ❌",  
                                            "Нууу хз, хз 🤷‍♂️",  
                                            "Затрудняюсь что то ответить 😅",  
                                            "Не знаю как ответить на это 🙈",  
                                            "Чо за вопрос ваще! 🤨",  
                                            "Ну и вопросы конечно у вас 🙃",  
                                            "Знать не могу, простите 😔", 
                                            "Эх, если бы я знал... 🥺", 
                                            "Ну нееет! 😤",  
                                            "Неа, не думаю так 🤔",  
                                            "Не в коем случае 🚫"
                                        ])
                    response = [answer]


                if message.reply_to_message:
                    replied_user = message.reply_to_message.from_user

                    if tag == 'kiss':
                        if replied_user.username:
                            method = ['sticker', 'emodzi']
                            if random.choice(method) == 'sticker':
                                chat_id = message.chat.id
                                sticker_id = random.choice(["CAACAgEAAxkBAAEvNBBnKzf3TxPpP-bq5CV48lksYcP9dQACmgUAAqisYUQyRqEyInPYRjYE",
                                                            "CAACAgEAAxkBAAEvNBRnKzgpZBxLlCNxfZrR1U0fZhQfGAACfQQAAoVgYUQkdUo9bX4GJDYE",
                                                            "CAACAgEAAxkBAAEvNBpnKzhQg8ehBQxq4BJx7M93lQjjlQACaAMAAqWXWEQXoYiREuOWFjYE",
                                                            "CAACAgEAAxkBAAEvNBxnKzhsUwOKfdUbu_G4dVsP-plYHQACYQMAAs8SYUQgvZ0xQxpHSjYE",
                                                            "CAACAgEAAxkBAAEvNCBnKziVu8fFSZKkiG65dIS-MG4LAgACMQQAAi58YUTvz8Hng0cYdDYE",
                                                            "CAACAgEAAxkBAAEvNKZnK0ZtDkJGm-Mswptp7IaRV4wtBgACmwUAAm2wYUR8o9G3jd2f6jYE",
                                                            "CAACAgIAAxkBAAEvNcNnK4ODPz4qZ1sAAbay6SJ2JbzRQMAAAm0fAAIUKDFJsEjjFuNR4qM2BA",
                                                            "CAACAgIAAxkBAAEvNcdnK4OX7Ghf1czzot6wyCoGxLjongACsxsAAmJCMEmfRoKt88PKTzYE",
                                                            "CAACAgIAAxkBAAEvNctnK4OxeCjlR0kztu7TUm9jU_GRTAAC1BoAAr3LMUljfYDbOMDS-jYE",
                                                            "CAACAgIAAxkBAAEvNc1nK4PEU0lCZaB-bFD4MbKv7d432AAC7iIAAvCRMUqRN1zRlI7JWzYE",
                                                            "CAACAgIAAxkBAAEvNdVnK4Sa37fWGA8c9mtioHoEa-5e0QAC5CIAAhA2uUnxWCHIqqbaRDYE"])
                                bot.send_sticker(chat_id, sticker_id)
                            else:
                                bot.reply_to(message.reply_to_message, "😘")
                            response = [f"<b>{message.from_user.first_name}</b> целует @{replied_user.username}! 💋"]
                        else:
                            response = [f"<b>{message.from_user.first_name}</b> целует {replied_user.first_name}! 💋"]

                    if tag == 'kick':
                        if replied_user.username:
                            bot.reply_to(message.reply_to_message, "👊")
                            response = [f"<b>{message.from_user.first_name}</b> ударяет @{replied_user.username}! 🥊"]
                        else:
                            response = [f"<b>{message.from_user.first_name}</b> ударяет {replied_user.first_name}! 🥊"]

                    if tag == 'kickToBalls':
                        if replied_user.username:
                            bot.reply_to(message.reply_to_message, "🍳")
                            response = [f"<b>{message.from_user.first_name}</b> ударяет по яйцам @{replied_user.username}! 🍒🥊"]
                        else:
                            response = [f"<b>{message.from_user.first_name}</b> ударяет по яйцам{replied_user.first_name}! 🍒🥊"]

                    if tag == 'chapalax':
                        if replied_user.username:
                            bot.reply_to(message.reply_to_message, "🫲")
                            response = [f"<b>{message.from_user.first_name}</b> дает подщечину @{replied_user.username}! что аж мало не показалось 🥴👋"]
                        else:
                            response = [f"<b>{message.from_user.first_name}</b> ударяет по яйцам{replied_user.first_name}! что аж мало не показалось 🥴👋"]

                    if tag == 'DoMinet':
                        if replied_user.username:
                            sticker_id = random.choice(["CAACAgEAAxkBAAEvNalnK4DdN4dvS5vZOtRJW7fveUTRMAACgwQAAoh-YUT1nH5RAwqh5DYE",
                                                        "CAACAgIAAxkBAAEvNatnK4Hkl0cIn_rE5Gazqg6-jqfLHAACXjcAAjT-wUpDITD2j3CJCTYE",
                                                        "CAACAgIAAxkBAAEvNa1nK4IBJw4O6rUKT9pRJlANdnBgHQACXDQAAis4yEoXQcySva1yMjYE",
                                                        "CAACAgIAAxkBAAEvNa9nK4ITU6whp9kIJcOs2bYUJF1A1gAC9jgAAjPZwUrJl6_dfPdhAjYE",
                                                        "CAACAgIAAxkBAAEvNbVnK4JpOmJ9GCcTQxvEW4iwhLafUwACox0AApmDMEkAASEIi73cq442BA",
                                                        "CAACAgIAAxkBAAEvNbtnK4LdFZsOmXM0zw4uEFekGvFgFgACxwsAAuw1GEiGRLoPpRha8zYE"])
                            chat_id = message.chat.id
                            bot.send_sticker(chat_id, sticker_id)
                            response = [f"<b>{message.from_user.first_name}</b> смачно отсасывает у @{replied_user.username}! 👄"]
                        else:
                            response = [f"<b>{message.from_user.first_name}</b> смачно отсасывает у {replied_user.first_name}! 👄"]

                    if tag == 'DoFuck':
                        if replied_user.username:
                            sticker_id = random.choice(["CAACAgEAAxkBAAEvM_hnKy-pdG-ZofVCb5PbfKsbGAizswAC8gIAAn7keUSaV0X-hOuuGDYE",
                                                        "CAACAgEAAxkBAAEvNCZnKzmDthV4XOx9j6rJmstGaYls7gAC3AMAAuUrYER-mSqilQa8BTYE",
                                                        "CAACAgEAAxkBAAEvNCxnKzms5WJYIwNnlu6vrxgsAn8O8AACmAQAAkJtYUSli1mJBkty2TYE",
                                                        "CAACAgEAAxkBAAEvNC5nKznaepF_UIAB9FtvFLOHdWsfUwACqgQAAld1YUToOQRaLUEVyDYE",
                                                        "CAACAgEAAxkBAAEvNJRnK0WVCHYDkxv3CxAfRNbWKgdUbgACwAQAAoZEWETfRJbwKoBSjjYE",
                                                        "CAACAgEAAxkBAAEvM_hnKy-pdG-ZofVCb5PbfKsbGAizswAC8gIAAn7keUSaV0X-hOuuGDYE",
                                                        "CAACAgIAAxkBAAEvNdNnK4QGSB0tX6iLOqDH37VXcD7DTwACpRsAAggQKUl_E_sT8BQBVzYE"])
                            chat_id = message.chat.id
                            bot.send_sticker(chat_id, sticker_id)
                            response = [f"<b>{message.from_user.first_name}</b> жоска трахает @{replied_user.username}! 👌🏻👈"]
                        else:
                            response = [f"<b>{message.from_user.first_name}</b> жоска трахает {replied_user.first_name}! 👌🏻👈"]

                    if tag == 'DoKuni':
                        if replied_user.username:
                            bot.reply_to(message.reply_to_message, "👅")
                            response = [f"<b>{message.from_user.first_name}</b> вкусно делает куни @{replied_user.username}! ✌️👅"]
                        else:
                            response = [f"<b>{message.from_user.first_name}</b> вкусно делает куни {replied_user.first_name}! ✌️👅"]

                    if tag == 'Hugging':
                        if replied_user.username:
                            sticker_id = random.choice(["CAACAgEAAxkBAAEvNJZnK0XDi3DNPUiAlnmpLmu6UkMncwACxQQAAscWWUQ8jRk51L9qOzYE",
                                                        "CAACAgEAAxkBAAEvNJhnK0X1c93nFpLWxLrtg6TSP9xSoQACgAUAAtseYUS25KZgdtJ4QDYE",
                                                        "CAACAgEAAxkBAAEvNJpnK0YJznEAAfZd0_JNvVIQcpv2oskAAj4FAAL8WmFEwUdv6CKsAAH3NgQ",
                                                        "CAACAgEAAxkBAAEvNJxnK0Yc9i_z6HVO9k03S2ieCxE5rQACKwUAAmC2YESqauMD7n01yzYE",
                                                        "CAACAgEAAxkBAAEvNKJnK0Y04gJ1TMEDqZNo0Ibp52FDtAACAwUAAn3AYUSZVUi_cpl0HzYE"])
                            chat_id = message.chat.id
                            bot.send_sticker(chat_id, sticker_id)
                            response = [f"<b>{message.from_user.first_name}</b> крепко обнимает @{replied_user.username}! 🤗"]
                        else:
                            response = [f"<b>{message.from_user.first_name}</b> крепко обнимает {replied_user.first_name}! 🤗"]
                


        # Reply to the user with the generated response
        bot.reply_to(message, response, parse_mode="HTML")
        print(f"[{tag}] tag was used.")
    
    CLOTHES_SEQUENCE = ["футболку", "штаны", "носки", "трусы"]

    user_clothing = defaultdict(lambda: CLOTHES_SEQUENCE.copy())

    @bot.message_handler(func=lambda message: "сними" in message.text.lower().split(maxsplit=2)[0])
    def handle_snyat(message):
        if not message.reply_to_message:
            bot.reply_to(message, "⚠️ Команду нужно использовать в ответ на сообщение пользователя.")
            return

        replied_user = message.reply_to_message.from_user
        user_id = replied_user.id
        chat_id = message.chat.id

        # Get the next clothing item to remove
        if not user_clothing[user_id]:
            bot.send_message(chat_id, f"😏 {replied_user.first_name} уже полностью раздет.")
            return

        next_cloth = user_clothing[user_id].pop(0)  # Remove the first item from the list

        bot.send_message(chat_id, f"👕 <b>{message.from_user.first_name}</b> снял {next_cloth} с <b>{replied_user.first_name}</b>.",parse_mode="HTML")

        # If there are still clothes left, schedule the next item removal after some time
        if user_clothing[user_id]:
            threading.Thread(target=schedule_next_removal, args=(chat_id, replied_user, message)).start()

    # Function to schedule the next clothing item removal
    def schedule_next_removal(chat_id, replied_user, message):
        time.sleep(10)  # Wait 10 seconds before removing the next item
        user_id = replied_user.id

        if user_clothing[user_id]:
            next_cloth = user_clothing[user_id].pop(0)
            bot.send_message(chat_id, f"👕 <b>{message.from_user.first_name}</b> снял {next_cloth} с <b>{replied_user.first_name}</b>.",parse_mode="HTML")
        else:
            bot.send_message(chat_id, f"😏 {replied_user.first_name} уже полностью раздет.")




    # ----------------------------< Other commands >-------------------------------

    bots_chat_history = defaultdict(list)

    @bot.message_handler(commands=['clear'])
    def clear_ads(message: Message):
        global authorized_usernames  
        if message.from_user.username not in authorized_usernames:
            bot.reply_to(message, "⚠️ У вас нет разрешения на выполнение этой команды.")
            return

        chat_id = message.chat.id
        message_ids = bots_chat_history.get(chat_id, [])
        print(message_ids)
        
        for msg_id in message_ids:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception as e:
                print(f"⚠️ Ошибка при удалении сообщения {msg_id}: {str(e)}")
        
        bots_chat_history[chat_id] = []
        bot.reply_to(message, "✅ Сообщения ботов очищены (последние 10)!")
        time.sleep(2)
        bot.delete_message(chat_id, message.message_id)
    

    # ================< DAILY ACTIVITY >=================

    
    # Define file paths for storage
    DAILY_STATS_FILE = "daily_activity_stats.json"
    MESSAGE_COUNT_FILE = "user_message_count.json"
    COIN_FILE = "amlet_coins.txt"  # Change to amlet_coins.txt

    # Define message thresholds and rewards
    MESSAGE_THRESHOLDS = [
        (50, 10),  # 50 messages = 10 coins
        (100, 20),  # 100 messages = 20 coins
        (200, 40),  # 200 messages = 40 coins
        (400, 80),  # 400 messages = 80 coins
        (500, 100)  # 500 messages = 100 coins
    ]

    # Read message counts from a JSON file
    def read_file_as_dict(file_path, key_type=int, value_type=str):
        if not os.path.exists(file_path):
            return {}
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading file '{file_path}': {e}")
            return {}

    # Write dictionary data to a JSON file
    def write_dict_to_file(data, file_path):
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error writing to file '{file_path}': {e}")

    # Read balances (AmletCoins) from the amlet_coins.txt file
    def read_balances():
        balances = {}
        if os.path.exists(COIN_FILE):
            try:
                with open(COIN_FILE, 'r') as f:
                    for line in f:
                        user_id, balance = line.strip().split(',')
                        balances[str(user_id)] = float(balance)
            except Exception as e:
                print(f"Error reading coins file '{COIN_FILE}': {e}")
        return balances

    # Write balances to the amlet_coins.txt file
    def write_balances(balances):
        try:
            with open(COIN_FILE, 'w') as f:
                for user_id, balance in balances.items():
                    f.write(f"{user_id},{balance:.2f}\n")
        except Exception as e:
            print(f"Error writing coins to file '{COIN_FILE}': {e}")

    # Read user daily activity (messages and coins for the day)
    def read_daily_activity():
        return read_file_as_dict(DAILY_STATS_FILE, key_type=int, value_type=dict)

    # Write user daily activity (messages, coins, and last milestone) to the file
    def write_daily_activity(daily_activity):
        write_dict_to_file(daily_activity, DAILY_STATS_FILE)

    def daily_activity_function(message):
        user_id = f"{message.from_user.id}"
        user_name = message.from_user.first_name or "Юзер"
        
        # Read the data (message counts and daily activity)
        message_counts = read_file_as_dict(MESSAGE_COUNT_FILE, key_type=str, value_type=int)  # Ensure correct types
        daily_activity = read_daily_activity()
        balances = read_balances()

        # Increment message count for the day
        current_count = message_counts.get(user_id, 0) + 1  # Increment count by 1 for each message
        message_counts[user_id] = current_count  # Save updated count in the dictionary

        # Ensure the message count is saved to the file after incrementing
        write_dict_to_file(message_counts, MESSAGE_COUNT_FILE)

        # If user doesn't have daily activity record, initialize it
        if user_id not in daily_activity:
            daily_activity[user_id] = {'messages': 0, 'coins': 0, 'last_milestone': 0}

        # Update daily messages count (separate from the total message count)
        daily_activity[user_id]['messages'] += 1

        # Get the last milestone the user reached
        last_milestone = daily_activity[user_id]['last_milestone']

        # Calculate the new milestone the user has reached
        new_milestone = 0
        for threshold, _ in MESSAGE_THRESHOLDS:
            if current_count >= threshold:
                new_milestone = threshold
            else:
                break

        # If the user has reached a new milestone, reward them
        if new_milestone > last_milestone:
            # Calculate the coins to award based on the threshold
            coins_to_award = dict(MESSAGE_THRESHOLDS).get(new_milestone, 0)
            
            # Update the daily activity and balance
            daily_activity[user_id]['coins'] += coins_to_award
            balances[user_id] = balances.get(user_id, 0) + coins_to_award
            daily_activity[user_id]['last_milestone'] = new_milestone

            # Send a notification to the user
            bot.reply_to(
                message,
                f"🎉 {user_name}, вы отправили {current_count} сообщений!\n"
                f"Вы достигли нового порога и получили {coins_to_award} AmletCoins 💰 за ваше активное участие!"
            )

        # Save updated daily activity and balances
        write_daily_activity(daily_activity)
        write_balances(balances)


    # Function to reset the daily stats at midnight
    def reset_daily_activity():
        write_daily_activity({})  # Reset all users' daily stats
        write_dict_to_file({}, MESSAGE_COUNT_FILE)
        print("📅 Статистика за день была сброшена!")

    # Reset the daily case file
    def reset_daily_case():
        write_dict_to_file({}, DAILY_CASE_FILE)

    # Scheduler to reset the daily stats at midnight
    def schedule_daily_reset():
        schedule.every().day.at("00:00").do(reset_daily_activity)
        schedule.every().day.at("00:00").do(reset_daily_case)
        while True:
            schedule.run_pending()
            time.sleep(60)

    # Start the scheduler in a separate thread
    def start_daily_reset_scheduler():
        reset_thread = threading.Thread(target=schedule_daily_reset)
        reset_thread.daemon = True
        reset_thread.start()

    # Command to reset daily stats (for admin only)
    @bot.message_handler(commands=['reset_daily'])
    def reset_daily_stats(message):
        authorized_usernames = ['RandomGor']  # Replace with actual admin usernames
        if message.from_user.username not in authorized_usernames:
            bot.reply_to(message, "⚠️ У вас нет разрешения на выполнение этой команды.")
            return
        reset_daily_activity()
        bot.reply_to(message, "📅 Статистика за день была сброшена!")

    # Start the scheduler
    start_daily_reset_scheduler()

    # Command for user daily stats
    @bot.message_handler(func=lambda message: "моя стата" in message.text.lower())
    def handle_user_daily_stats(message):
        user_id = f"{message.from_user.id}"
        user_name = message.from_user.first_name or "Юзер"

        daily_activity = read_daily_activity()

        # Get today's stats for the user
        user_stats = daily_activity.get(user_id, {'messages': 0, 'coins': 0})

        # Display only today's stats
        bot.reply_to(
            message,
            f"<b>📊 {user_name}, ваша статистика за сегодня:</b>\n"
            f"Сообщений отправлено (сегодня): {user_stats['messages']}\n"
            f"Заработано AmletCoins (сегодня): {user_stats['coins']} 💰",
            parse_mode="HTML"
        )

    # Command for overall daily stats (for admin)
    @bot.message_handler(func=lambda message: "общ стата" in message.text.lower())
    def handle_overall_daily_stats(message):
        daily_activity = read_daily_activity()

        if not daily_activity:
            bot.reply_to(message, "📊 Общая статистика пуста. Сегодня ещё нет активности.")
            return

        stats_summary = "📊 Общая статистика за сегодня:\n"

        # Display stats for all users, showing usernames instead of user IDs
        for user_id, activity in daily_activity.items():
              # Retrieve the username

            stats_summary = "📊 Статистика по общительным пользователям за сутки\n\n"
            sorted_users = sorted(daily_activity.items(), key=lambda x: x[1]['messages'], reverse=True)

            for i, (user_id, activity) in enumerate(sorted_users, 1):
                user_name = bot.get_chat(user_id).first_name
                stats_summary += (
                    f"<b>{i}.</b> {user_name} — {activity['messages']}\n"
                )

            total_messages = sum(activity['messages'] for activity in daily_activity.values())
            stats_summary += f"\n<b>Всего сообщений:</b> 💬 {total_messages}"

        bot.reply_to(message, stats_summary, parse_mode="HTML")

    @bot.message_handler(func=lambda message: "дарить" in message.text.lower().split(maxsplit=2)[0])
    def grant_amlet_coins(message):
        # Check if the message is a reply to another user
        if not message.reply_to_message:
            bot.reply_to(message, "⚠️ Вы должны ответить на сообщение пользователя, которому хотите выдать монеты.")
            return
        
        # Check if the issuing user is authorized
        authorized_usernames = ['RandomGor']  # Replace with the usernames of admins
        if message.from_user.username not in authorized_usernames:
            bot.reply_to(message, "⚠️ У вас нет разрешения на выполнение этой команды.")
            return
        
        # Parse the command to get the amount
        try:
            # Extract the amount from the command
            amount = float(message.text.split()[1])
            if amount <= 0:
                raise ValueError
        except (IndexError, ValueError):
            bot.reply_to(message, "⚠️ Пожалуйста, укажите корректное количество монет. Пример: дарить 10")
            return
        
        # Get the user ID of the replied-to user
        replied_user_id = f"{message.reply_to_message.from_user.id}"
        replied_user_name = message.reply_to_message.from_user.first_name or "Юзер"
        user_name = message.from_user.first_name
        
        # Read the balances from the file
        balances = read_balances()
        
        # Grant the coins
        balances[replied_user_id] = balances.get(replied_user_id, 0) + amount
        
        # Save the updated balances
        write_balances(balances)

        
        # Notify both the issuer and the recipient
        bot.reply_to(
            message, 
            f"✅ Вы выдали {amount:.2f} AmletCoins 💰 пользователю {replied_user_name}."
        )
        try:
            bot.send_message(
                replied_user_id,
                f"🎉 Вы получили {amount:.2f} AmletCoins 💰 от {user_name}!"
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "bot can't initiate conversation" in str(e):
                print(f"Bot cannot message user {replied_user_id}. They need to start a chat first.")


    @bot.message_handler(func=lambda message: "отобрать" in message.text.lower().split(maxsplit=2)[0])
    def grant_amlet_coins(message):
        # Check if the message is a reply to another user
        if not message.reply_to_message:
            bot.reply_to(message, "⚠️ Вы должны ответить на сообщение пользователя, из которого хотите отобрать монеты.")
            return
        
        # Check if the issuing user is authorized
        authorized_usernames = ['RandomGor']  # Replace with the usernames of admins
        if message.from_user.username not in authorized_usernames:
            bot.reply_to(message, "⚠️ У вас нет разрешения на выполнение этой команды.")
            return
        
        # Parse the command to get the amount
        try:
            # Extract the amount from the command
            amount = float(message.text.split()[1])
            if amount <= 0:
                raise ValueError
        except (IndexError, ValueError):
            bot.reply_to(message, "⚠️ Пожалуйста, укажите корректное количество монет. Пример: отобрать 10")
            return
        
        # Get the user ID of the replied-to user
        replied_user_id = f"{message.reply_to_message.from_user.id}"
        replied_user_name = message.reply_to_message.from_user.first_name or "Юзер"
        user_name = message.from_user.first_name
        
        # Read the balances from the file
        balances = read_balances()
        
        balances[replied_user_id] = balances.get(replied_user_id, 0) - amount
        
        # Save the updated balances
        write_balances(balances)
        
        # Notify both the issuer and the recipient
        bot.reply_to(
            message, 
            f"✅ Вы отняли {amount:.2f} AmletCoins 💰 из пользователя {replied_user_name}."
        )
        try:
            bot.send_message(
                replied_user_id,
                f"🎉 Вы получили {amount:.2f} AmletCoins 💰 от {user_name}!"
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "bot can't initiate conversation" in str(e):
                print(f"Bot cannot message user {replied_user_id}. They need to start a chat first.")


    @bot.message_handler(func=lambda message: "дать" in message.text.lower().split(maxsplit=2)[0])
    def grant_amlet_coins(message):
        # Check if the message is a reply to another user
        if not message.reply_to_message:
            bot.reply_to(message, "⚠️ Вы должны ответить на сообщение пользователя, которому хотите выдать монеты.")
            return
        
        
        try:
            # Extract the amount from the command
            amount = float(message.text.split()[1])
            if amount <= 0:
                raise ValueError
        except (IndexError, ValueError):
            bot.reply_to(message, "⚠️ Пожалуйста, укажите корректное количество монет. Пример: дать 10")
            return
        
        # Get the user ID of the replied-to user
        replied_user_id = f"{message.reply_to_message.from_user.id}"
        user_id = f"{message.from_user.id}"
        replied_user_name = message.reply_to_message.from_user.first_name or "Юзер"
        user_name = message.from_user.first_name or "Юзер"
        
        # Read the balances from the file
        balances = read_balances()
        
        # Grant the coins
        if balances[user_id] - amount >= 0:
            balances[replied_user_id] = balances.get(replied_user_id, 0) + amount
            balances[user_id] = balances.get(user_id, 0) - amount
        else:
            bot.reply_to(message, f"⚠️ У вас недостаточно Амлет Коинов, ваш баланс: {balances[user_id]} 💰")
            return

        # Save the updated balances
        write_balances(balances)
        
        # Notify both the issuer and the recipient
        bot.reply_to(
            message, 
            f"✅ Вы выдали {amount:.2f} AmletCoins 💰 пользователю {replied_user_name}."
        )
        try:
            bot.send_message(
                replied_user_id,
                f"🎉 Вы получили {amount:.2f} AmletCoins 💰 от {user_name}!"
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "bot can't initiate conversation" in str(e):
                print(f"Bot cannot message user {replied_user_id}. They need to start a chat first.")

    @bot.message_handler(func=lambda message: "топ5" in message.text.lower().split(maxsplit=2)[0])
    def haldle_top5(message):
        balances = read_balances()

        top_5_balances = sorted(balances.items(), key=lambda x: x[1], reverse=True)[:5]

        result_message = "🏆 <b>Топ 5</b> пользователей по балансу:\n"
        for i, (user_id, balance) in enumerate(top_5_balances, start=1):
            try:
                chat = bot.get_chat(user_id)
                username = chat.username or chat.first_name or "Неопознанный"
            except Exception as e:
                username = "Неопознанный"
            result_message += f"{i}. <b>{username}</b>: {balance:.2f} AmletCoins 💰\n"

        bot.reply_to(message, result_message,parse_mode="HTML")


    @bot.message_handler(func=lambda message: "топ10" in message.text.lower().split(maxsplit=2)[0])
    def handle_top10(message):
        balances = read_balances()

        # Sort and limit to top 10
        top_10_balances = sorted(balances.items(), key=lambda x: x[1], reverse=True)[:10]

        result_message = "🏆 <b>Топ 10</b> пользователей по балансу:\n"
        for i, (user_id, balance) in enumerate(top_10_balances, start=1):
            try:
                chat = bot.get_chat(user_id)
                username = chat.username or chat.first_name or "Неопознанный"
            except Exception as e:
                username = "Неопознанный"
            
            result_message += f"{i}. <b>{username}</b>: {balance:.2f} AmletCoins 💰\n"

        bot.reply_to(message, result_message, parse_mode="HTML")



    # ========================< AMLET CASES >========================

    DAILY_CASE_FILE = "daily_case.json"
    COIN_FILE = "amlet_coins.txt"

    # Load or initialize the daily case file
    def load_daily_case():
        return read_file_as_dict(DAILY_CASE_FILE, key_type=str, value_type=dict)

    def save_daily_case(case_data):
        write_dict_to_file(case_data, DAILY_CASE_FILE)

    # Reward probabilities (adjust to your needs)
    REWARDS = {
        10: 0.4,   # 40% chance to win 10 coins
        15: 0.25,  # 25% chance to win 15 coins
        20: 0.15,  # 15% chance to win 20 coins
        30: 0.1,   # 10% chance to win 30 coins
        40: 0.05,  # 5% chance to win 40 coins
        60: 0.03,  # 3% chance to win 60 coins
        80: 0.015, # 1.5% chance to win 80 coins
        100: 0.005 # 0.5% chance to win 100 coins
    }

    PAID_CASE_REWARDS = [30, 40, 50, 60, 70]  # Rewards with equal probability

    # Choose reward based on probabilities
    def choose_reward():
        rewards, probabilities = zip(*REWARDS.items())
        return random.choices(rewards, probabilities)[0]

    def open_daily_case(user_id):
        daily_case = load_daily_case()
        balances = read_balances()

        # Check if the user has already opened the case today
        today_date = time.strftime("%Y-%m-%d")  # Current date in YYYY-MM-DD
        if str(user_id) in daily_case and daily_case[str(user_id)] == today_date:
            return "<b>Вы уже открыли свой ежедневный кейс сегодня! Возвращайтесь завтра.</b>"

        # Check if the user has opened the case from a linked account
        for user_id_2 in daily_case.keys():
            if are_accounts_linked(int(user_id), int(user_id_2)):
                if daily_case[str(user_id_2)] == today_date:
                    return "<b>Вы уже открыли свой кейс с другого аккаунта!</b>"

        # Generate a reward
        reward = choose_reward()
        balances[str(user_id)] = balances.get(str(user_id), 0) + reward

        # Save updated balance
        write_balances(balances)

        # Update daily case
        daily_case[str(user_id)] = today_date
        save_daily_case(daily_case)

        return f"<b>Поздравляем!</b> Вы получили <b>{reward} Амлет Коинов</b>. Ваш новый баланс: <b>{balances[str(user_id)]:.2f}</b> Амлет Коинов."


    # Open the paid case
    def open_paid_case(user_id):
        balances = read_balances()

        # Check if the user has enough coins
        current_balance = balances.get(str(user_id), 0)
        if current_balance < 50:
            return ""

        # Deduct 50 coins
        balances[str(user_id)] -= 50

        # Generate a reward (equal probability for all options)
        reward = random.choice(PAID_CASE_REWARDS)
        balances[str(user_id)] += reward

        # Save updated balance
        write_balances(balances)

        username = bot.get_chat(user_id).username

        if reward >= 50:
            return (
                f"<b>Поздравляем! @{username}</b> Вы получили <b>{reward}</b> Амлет Коинов. "
                f"Ваш новый баланс: {balances[str(user_id)]:.2f} <b>+{reward-50}</b> Амлет Коинов."
            )
        else:
            return (
                f"<b>Повезет в другой раз @{username}</b> Вы получили <b>{reward}</b> Амлет Коинов. "
                f"Ваш новый баланс: {balances[str(user_id)]:.2f} <b>-{50-reward}</b> Амлет Коинов."
            )

    # Telegram bot command for /case
    @bot.message_handler(commands=["case"])
    def handle_case_command(message):
        user_id = message.from_user.id

        # Create an inline keyboard with buttons for daily and paid cases
        markup = InlineKeyboardMarkup()
        daily_button = InlineKeyboardButton("🎁 Ежедневный кейс (дает 10-100)", callback_data="daily_case")
        paid_button = InlineKeyboardButton("💰 Платный кейс стоит 50 (дает 30-70)", callback_data="paid_case")
        
        # Add buttons in separate rows
        markup.add(daily_button)
        markup.add(paid_button)

        bot.send_message(
            chat_id=message.chat.id,
            text="<b>Выберите кейс для открытия:</b>",
            reply_markup=markup,
            parse_mode="HTML"
        )

    # Telegram bot callback for case buttons
    @bot.callback_query_handler(func=lambda call: call.data in ["daily_case", "paid_case"])
    def handle_case_callback(call):
        user_id = call.from_user.id

        if call.data == "daily_case":
            response = open_daily_case(user_id)
            if response == "":
                bot.answer_callback_query(call.id, "❌ Вы уже открыли ваш ежедневный кейс сегодня! Возвращайтесь завтра.")
                return

        elif call.data == "paid_case":
            response = open_paid_case(user_id)
            if response == "":
                bot.answer_callback_query(call.id, "❌ У вас недостаточно Амлет Коинов для открытия этого кейса! Нужно 50 коинов.")
                return

        bot.answer_callback_query(call.id)  # Acknowledge the callback
        sent_message = bot.send_message(chat_id=call.message.chat.id, text=response, parse_mode="HTML")

        def delete_bot_message():
            time.sleep(5)  # Wait before deletion
            try:
                bot.delete_message(chat_id=sent_message.chat.id, message_id=sent_message.message_id)
            except Exception as e:
                print(f"Error deleting bot's message: {e}")

        # Start deletion in another thread
        threading.Thread(target=delete_bot_message).start()


    # -------------< Linking accounts >----------

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

    # Save linked accounts
    def save_linked_accounts(data):
        with open(LINKED_ACCOUNTS_PATH, "w") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    # Add accounts to a group
    def add_accounts_to_group(user_id_1, user_id_2):
        data = load_linked_accounts()
        groups = data["groups"]

        # Find all groups containing user_id_1 or user_id_2
        groups_to_merge = []
        for group in groups:
            if user_id_1 in group or user_id_2 in group:
                groups_to_merge.append(group)

        if groups_to_merge:
            # Merge all relevant groups into one and add the new IDs
            merged_group = set()
            for group in groups_to_merge:
                merged_group.update(group)
                groups.remove(group)  # Remove old groups

            # Add the new IDs
            merged_group.update([user_id_1, user_id_2])
            groups.append(list(merged_group))  # Add the merged group back
        else:
            # Create a new group with the two IDs
            groups.append([user_id_1, user_id_2])

        save_linked_accounts(data)

    # Check if accounts are already linked
    def are_accounts_linked(user_id_1, user_id_2):
        data = load_linked_accounts()
        for group in data["groups"]:
            if user_id_1 in group and user_id_2 in group:
                return True
        return False

    # Telegram bot handler for /same_acc
    @bot.message_handler(commands=["same_acc"])
    def handle_same_acc_command(message):
        authorized_usernames = ['RandomGor']  # Replace with the usernames of admins
        if message.from_user.username not in authorized_usernames:
            bot.reply_to(message, "⚠️ У вас нет разрешения на выполнение этой команды.")
            return

        global pending_accounts
        user_id = message.from_user.id


        # Check if the user is replying to someone
        if not message.reply_to_message:
            bot.reply_to(message, "⚠️ Пожалуйста, используйте эту команду, отвечая на сообщение пользователя, которого хотите связать.")
            return

        # Get the ID of the replied user
        replied_user_id = message.reply_to_message.from_user.id

        if user_id in pending_accounts:
            # Second step: Link the accounts
            first_user_id = pending_accounts[user_id]
            second_user_id = replied_user_id

            if are_accounts_linked(first_user_id, second_user_id):
                bot.reply_to(message, "⚠️ Эти аккаунты уже связаны.")
            else:
                add_accounts_to_group(first_user_id, second_user_id)
                bot.reply_to(message, f"✅ Аккаунты успешно связаны: {first_user_id} и {second_user_id}")

            # Clear the pending state
            del pending_accounts[user_id]
        else:
            # First step: Save the first user ID
            pending_accounts[user_id] = replied_user_id
            bot.reply_to(message, "✅ Теперь укажите другой аккаунт, с которым хотите связать этот.")


    # ========================< CHAT MANAGEMENT >========================

    user_last_message = {}
    user_mute_status = {}
    user_message_timestamps = defaultdict(list)

    def mute_user(chat_id, user_id, mute_duration=60):
        try:
            # Check if the user is the owner or an admin
            chat_member = bot.get_chat_member(chat_id, user_id)

            # Skip muting if the user is the owner or an admin
            if chat_member.status in ['administrator', 'creator']:
                bot.send_message(chat_id, f"⚠️ {chat_member.user.first_name} Я понемаю что ты администратор или владелец, и я не могу тебя дать мут, но прошу не писать в чат слишком быстро, ты же должен привести порядок а не бардак!")
                return

            # Mute the user for the specified duration
            bot.restrict_chat_member(
                chat_id,
                user_id,
                can_send_messages=False,  # Mute user (disables message sending)
                until_date=time.time() + mute_duration  # Mute for the specified duration
            )
            bot.send_message(chat_id, f"⚠️ {chat_member.user.first_name} был заблокирован за отправку слишком большого количества сообщений.")

        except Exception as e:
            print(f"Error muting user: {e}")


    # Configurable rate-limiting settings
    TIME_WINDOW = 5  # Time window in seconds (e.g., 5 seconds)
    MAX_MESSAGES = 10  # Maximum number of messages allowed within the time window
    MESSAGE_FREQUENCY_LIMIT = 0.5  # Time in seconds (minimum time between messages from the same user)

    # ALWAYS AT THE BOTTOM
    @bot.message_handler(func=lambda message: True)
    def handle_all_bot_messages(message: types.Message):
        user_id = message.from_user.id
        current_time = time.time()
        chat_id = message.chat.id

        # Track the time of the message for rate-limiting
        if user_id not in user_message_timestamps:
            user_message_timestamps[user_id] = []

        user_message_timestamps[user_id].append(current_time)

        # Keep only timestamps from the last TIME_WINDOW seconds
        user_message_timestamps[user_id] = [
            ts for ts in user_message_timestamps[user_id] if current_time - ts <= TIME_WINDOW
        ]

        # If the user sends more than MAX_MESSAGES in TIME_WINDOW seconds, mute them for 60 seconds
        if len(user_message_timestamps[user_id]) > MAX_MESSAGES:
            mute_user(chat_id, user_id, mute_duration=60)
            user_message_timestamps[user_id] = []  # Reset the user's timestamps to prevent further triggering
            return

        # Check if the user is sending messages too frequently (less than MESSAGE_FREQUENCY_LIMIT seconds)
        if user_id in user_last_message and (current_time - user_last_message[user_id] < MESSAGE_FREQUENCY_LIMIT):  
            bot_reply = bot.reply_to(message, "⚠️ Вы слишком часто отправляете сообщения.")

            try:
                bot.delete_message(chat_id=chat_id, message_id=message.message_id)
            except Exception as e:
                print(f"Error deleting user message: {e}")

            # Delete the bot's own reply after 2 seconds
            def delete_bot_message():
                time.sleep(2)
                try:
                    bot.delete_message(chat_id=chat_id, message_id=bot_reply.message_id)
                except Exception as e:
                    print(f"Error deleting bot's message: {e}")

            threading.Thread(target=delete_bot_message).start()
            return

        user_last_message[user_id] = current_time  # Update the last message timestamp

        # Track other functionalities such as daily activity or other checks
        track_message(message)

        # Handle user interaction with the bot (can be extended)
        daily_activity_function(message)

        # Track bots' messages (if not the bot itself)
        if message.from_user:  
            if message.from_user.id != bot.get_me().id:  
                if message.from_user.is_bot:  
                    bots_chat_history[chat_id].append(message.message_id)
                    print(f"Bot message detected: {message.text}")  
                    bots_chat_history[chat_id] = bots_chat_history[chat_id][-10:]
        else:
            print("No from_user field in message. Possibly a service message.")
