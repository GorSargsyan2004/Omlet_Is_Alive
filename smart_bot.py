# |==========================================================< SMART BOT >==========================================================|
import openai
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

# Download NLTK resources for tokenization
nltk.download('punkt')

# Initialize pymorphy2
morph = pymorphy2.MorphAnalyzer()

API_KEY_GPT =  os.environ.get('API_KEY_GPT').strip("'")

# Loading the intents Data
with open('intents.json', encoding='utf-8') as file:
    data = json.load(file)


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
        print("\t\t\t\tModel loaded successfully!")
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
        return text

    

    # Global dictionary to store chat history
    chat_history = defaultdict(list)

    def track_message(message):
        """Track all non-bot messages and store the last 40 in memory."""
        chat_id = message.chat.id

        msg = message.text.replace("гбт", "ЧатГПТ").strip()

        # Only store messages from users (not bots)
        if not message.from_user.is_bot and message.text:
            chat_history[chat_id].append({  'role': 'user', 
                                            'content': f"Сообщение от {message.from_user.username}: {msg}"})

            # Keep only the last 40 messages
            chat_history[chat_id] = chat_history[chat_id][-40:]

    def fetch_chat_history(chat_id):
        """Retrieve the last 40 messages for a given chat."""
        return chat_history.get(chat_id, [])

    def get_response_gpt_with_history(message, user_message, chat_id):
        """Prepare GPT request with chat history."""
        try:
            # Fetch stored chat history
            chat_messages = fetch_chat_history(chat_id)

            # Append the new user message to the history
            full_context = chat_messages 

            sys_prmpt =  '''Пожалуйста, давайте немного краткие ответы чтобы они поместились в сообщение для телеграм. И на русском. 
                        Помни что ты находишся в телеграм группе игроков майнкрафт, кросплатформленный сервер.
                        У нас есть личный сервер Amlet_House (это и имя нашей группы телеграм). Админ Группы
                        Гор, и создатель телеграм бота на котором ты работаешь сейчас, твой код написан Гором, его
                        юзернейм в телеграм @RandomGor. И еще помни что Гор любит девушку Вику, вот ее юзернейм @ximozka_nnr,
                        будь на чеку я могу тебя сказать делать разные вещи с ней, например успокоить ее когда она расстроена
                        или разозлилась, могу сказать тебе делать ей комплимент и так далее, когда я прошу тебя делать такие вещи 
                        не забудь при ответе (responce) упомянуть ее имя и юзернейм @ximozka_nnr, окей?
                        И всегда пиши красиво используй емодзи, используй '\\n', тоесть с новой строки, ну и если хочешь текст какой то сделать широким
                        (bold) используй **жирный текст** такой способ чтобы сделать текст bold.
                        
                        И еще тебе будет представлено чат история (максимум 40 сообщений), будут они в таком формате 'Сообщени от <юзернейм>: <Сообщение>'
                        И если в этих сообщениях есть слово 'ЧатГПТ' это значит звали тебя чтобы ответить, последнее сообщение где будет присуствовать 'ЧатГБТ'
                        это значит что ты должен будешь ответить на это последнее сообщение и учитывая весь контекст переписки чата если нужно. У тебя есть их 
                        юзернеймы, можешь воспользоватся ими чтобы кого то что то сказать или передать, тебя могут спрашивать вопросы что зависимо от контекста
                        будь внимателен над такими вопросами и отвечай на них всегда иронично :)

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
            return "Error: Could not prepare the request."


    @bot.message_handler(func=lambda message: "гбт" in message.text.lower())
    def handle_gpt(message):
        chat_id = message.chat.id

        # Track the incoming message
        track_message(message)

        # Send a "Thinking..." message
        thinking_message = bot.reply_to(message, "Думаю... 🔄")

        try:
            # Prepare the user prompt
            prompt = message.text.replace("гбт", "ЧатГПТ").strip()

            # Get GPT response using the chat history
            response = get_response_gpt_with_history(message, prompt, chat_id)

            # Delete the "Thinking..." message
            bot.delete_message(chat_id, thinking_message.message_id)

            response = convert_to_html_bold(response)

            # Send the GPT response
            bot.send_message(chat_id, response, parse_mode="HTML")
        except Exception as e:
            # Handle errors gracefully
            bot.delete_message(chat_id, thinking_message.message_id)
            bot.reply_to(message, "Произошла ошибка при обработке запроса 😔")
            print(f"Error in handle_gpt: {str(e)}")








    #bot_username = bot.get_me().username
    bot_username = "амлет"

    # Define a new function to handle messages mentioning the bot
    @bot.message_handler(func=lambda message: bot_username.lower() in message.text.lower())
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
    
    @bot.message_handler(func=lambda message: True)
    def handle_all_messages(message):
        """Track all messages and store them in memory."""
        track_message(message)




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
