import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager  # Added for managing ChromeDriver
import time

class Scrapper:
    def __init__(self):
        self.filename = 'media_links.txt'

    def scrape_memes(self):
        url = "https://www.memozg.ru/popular"

        # Set up Selenium WebDriver with headless options
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--remote-debugging-port=9222")  # Debugging port
        chrome_options.binary_location = "/snap/bin/chromium"  # Correct binary

        # Use webdriver-manager to automatically handle ChromeDriver installation
        service = Service(ChromeDriverManager().install())  # Automatically manage the correct driver

        print("Launching Selenium WebDriver...")
        driver = webdriver.Chrome(service=service, options=chrome_options)  # Use the service from webdriver-manager
        print("WebDriver launched successfully.")

        try:
            # Load the page
            driver.get(url)
            time.sleep(5)  # Allow time for the page to fully load

            # Locate all image elements
            images = driver.find_elements(By.TAG_NAME, "img")

            # Extract 'src' attributes of images
            meme_urls = [img.get_attribute("src") for img in images if img.get_attribute("src")]
            return meme_urls

        except Exception as e:
            print(f"An error occurred: {e}")
            return []

        finally:
            # Close the WebDriver
            driver.quit()

    def store_links_in_file(self, video_urls, image_urls):
        with open(self.filename, 'w') as file:
            file.write("Video URLs:\n")
            for url in video_urls:
                file.write(url + '\n')
            file.write("\nImage URLs:\n")
            for url in image_urls:
                file.write(url + '\n')

    def scrape_all_video_urls(self):
        url = "https://pikabu.ru/tag/%D0%9A%D0%BE%D1%82,%D0%9C%D0%B5%D0%BC%D1%8B,%D0%A2%D1%80%D0%B5%D0%BD%D0%B4"  

        response = requests.get(url)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            video_urls = []
            video_divs = soup.find_all('div', class_='player')
            
            for div in video_divs:
                av1_url = div.get('data-av1')
                if av1_url:
                    video_urls.append(av1_url)
                
                mp4_url = div.get('data-source')  
                if mp4_url and mp4_url not in video_urls:
                    video_urls.append(mp4_url)

            if video_urls:
                video_urls = [url + ".mp4" for url in video_urls]
                return video_urls
            else:
                print("No video URLs found")
                return []
        else:
            print(f"Failed to retrieve page. Status code: {response.status_code}")
            return []

    def scrape_all_image_urls(self):
        url = "https://pikabu.ru/tag/%D0%9A%D0%BE%D1%82,%D0%9C%D0%B5%D0%BC%D1%8B,%D0%A2%D1%80%D0%B5%D0%BD%D0%B4"  
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            image_divs = soup.find_all('div', class_='story-image__content')
            image_urls = [img_tag.get('data-large-image') or img_tag.get('src') for div in image_divs if (img_tag := div.find('img'))]
            return image_urls
        else:
            print(f"Failed to retrieve page. Status code: {response.status_code}")
            return []

def scrape_and_store():
    scrapper = Scrapper()
    video_urls = scrapper.scrape_all_video_urls()
    #image_urls = scrapper.scrape_all_image_urls() + scrapper.scrape_memes()
    image_urls = scrapper.scrape_all_image_urls()
    scrapper.store_links_in_file(video_urls, image_urls)

if __name__ == '__main__':
    scrapper = Scrapper()
    image_urls = scrapper.scrape_memes()
    print(image_urls)
