import requests
from meme_scrapper import Scrapper, scrape_and_store
import os

scrapper = Scrapper()
filename = scrapper.filename


def register_memes(bot):

    # Function to scrape and store meme links
    @bot.message_handler(commands=['scrape'])
    def scrape_memes(message):
        authorized_usernames = ['RandomGor']

        if message.from_user.username in authorized_usernames:
            scrape_and_store()  
            bot.reply_to(message, "🌐 Мемы успешно загружены с интернета и сохранены! 🎉 Используйте /meme или /memev, чтобы посмотреть их!")
        else:
            bot.reply_to(message, "❌ У вас нет прав для выполнения этой команды.")

    # Function to retrieve and send the first image meme, removing it from the file
    @bot.message_handler(commands=['meme'])
    def get_meme_image(message):
        if not os.path.exists(filename) or os.path.getsize(filename) == 0:
            bot.reply_to(message, "😞 К сожалению, изображения мемов закончились. Используйте команду /scrape, чтобы загрузить новые!")
            return

        with open(filename, 'r') as file:
            lines = file.readlines()

        try:
            image_start = lines.index("Image URLs:\n") + 1
        except ValueError:
            bot.reply_to(message, "⚠️ Ой! Что-то пошло не так с файлом мемов. Попробуйте загрузить их снова.")
            return

        meme_url = None
        if image_start < len(lines) and lines[image_start].strip():
            meme_url = lines[image_start].strip()
            del lines[image_start]
        else:
            bot.reply_to(message, "😢 Изображения мемов закончились! Используйте команду /scrape, чтобы загрузить новые!")
            return

        # Update the file with remaining URLs
        with open(filename, 'w') as file:
            file.writelines(lines)

        # Download and send the image file
        try:
            image_data = requests.get(meme_url).content
            bot.send_photo(message.chat.id, image_data)
        except Exception as e:
            bot.reply_to(message, f"Ошибка при отправке изображения: {e}")

    # Function to retrieve and send the first video meme, removing it from the file
    @bot.message_handler(commands=['memev'])
    def get_meme_video(message):
        if not os.path.exists(filename) or os.path.getsize(filename) == 0:
            bot.reply_to(message, "😞 К сожалению, видео мемов закончились. Используйте команду /scrape, чтобы загрузить новые!")
            return

        with open(filename, 'r') as file:
            lines = file.readlines()

        try:
            video_start = lines.index("Video URLs:\n") + 1
        except ValueError:
            bot.reply_to(message, "⚠️ Ой! Что-то пошло не так с файлом мемов. Попробуйте загрузить их снова.")
            return

        meme_url = None
        if video_start < len(lines) and lines[video_start].strip():
            meme_url = lines[video_start].strip()
            del lines[video_start]
        else:
            bot.reply_to(message, "😢 Видео мемов закончились! Используйте команду /scrape, чтобы загрузить новые!")
            return

        # Update the file with remaining URLs
        with open(filename, 'w') as file:
            file.writelines(lines)

        # Download and send the video file
        try:
            video_data = requests.get(meme_url).content
            bot.send_video(message.chat.id, video_data)
        except Exception as e:
            bot.reply_to(message, f"Ошибка при отправке видео: {e}")