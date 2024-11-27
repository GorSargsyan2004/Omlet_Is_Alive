import telebot
import re
import os
from telebot.types import Message
import random
import time

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

# |========================================< SMART BOT >========================================|

from smart_bot import making_bag_of_words_and_training
making_bag_of_words_and_training(bot)

# ------------------------------< MEME SCRAPING >---------------------------------

from memes import register_memes
register_memes(bot)


def main():
    while True:
        try:
            bot.infinity_polling(none_stop=True,timeout=60)
            break
        except (ConnectionError, ReadTimeout) as e:
            print(f"Connection error: {e}")
            print("Retrying in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    main()
    
    





