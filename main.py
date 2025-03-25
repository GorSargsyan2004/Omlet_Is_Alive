import telebot
import re
import os
import random
import time
from telebot.types import Message

# Fix missing imports
from requests.exceptions import ConnectionError, ReadTimeout  

# Load environment variables
def load_env():
    with open('.env', 'r') as file:
        for line in file:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

load_env()

tg_token = os.environ.get('TELEGRAM_API_TOKEN').strip("'")

bot = telebot.TeleBot(tg_token)

# ---------------< Essential commands for monitoring minecraft >---------------
from commands import register_commands
register_commands(bot)

# ------------------------------< MEME SCRAPING >---------------------------------
from memes import register_memes
register_memes(bot)

# |========================================< SMART BOT >========================================|
from smart_bot import making_bag_of_words_and_training
making_bag_of_words_and_training(bot)

# Initialize logging
from daily_logger import DailyLogger
# logger = DailyLogger()

def main():
    while True:
        try:
            bot.infinity_polling(
                none_stop=True, 
                timeout=60, 
                allowed_updates=[
                    "message", "edited_message", "channel_post",
                    "edited_channel_post", "callback_query", 
                    "inline_query", "chosen_inline_result", 
                    "poll", "my_chat_member", "chat_member", 
                    "chat_join_request"
                ]
            )
            break  # If polling succeeds, break the loop
        except (ConnectionError, ReadTimeout) as e:
            print(f"Connection error: {e}")
            print("Retrying in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    main()
