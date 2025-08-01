import os
import re
import time
import pandas as pd
from datetime import datetime
import threading

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from webdriver_manager.chrome import ChromeDriverManager


def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--ignore-ssl-errors')
    
    # Disable images to improve performance
    prefs = {"profile.managed_default_content_settings.images": 2}
    chrome_options.add_experimental_option("prefs", prefs)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    print("[DEBUG] Chrome driver initialized")
    return driver


def get_reaction_count(post):
    try:
        reaction_elements = post.find_elements(By.XPATH, './/button[contains(@aria-label, "in total")]')

        if not reaction_elements:
            reaction_elements = post.find_elements(By.XPATH, './/span[contains(@aria-label, "in total")]')

        if not reaction_elements:
            reaction_elements = post.find_elements(By.XPATH, './/*[contains(@aria-label, "reactions")]')

        for element in reaction_elements:
            aria_label = element.get_attribute('aria-label')
            if aria_label:
                patterns = [
                    r'([\d,]+)\s+in total',
                    r'([\d,]+)\s+reactions',
                    r'([\d,]+)\s+reaction',
                    r'([\d,.]+)K?\s+in total',
                ]

                for pattern in patterns:
                    match = re.search(pattern, aria_label)
                    if match:
                        count_str = match.group(1).replace(',', '')
                        if 'K' in count_str:
                            return int(float(count_str.replace('K', '')) * 1000)
                        return int(count_str)

        return 0
    except Exception as e:
        print(f"[ERROR] Error getting reaction count: {e}")
        return 0


def extract_links(text):
    return ', '.join(re.findall(r'(https?://\S+)', str(text)))


def scrape_channel(driver, channel_name, channel_language, output_folder):
    print(f"[INFO] Scraping channel: {channel_name}")

    try:
        channels_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'div[title="Channels"]'))
        )
        channels_button.click()
        print("[DEBUG] Clicked on Channels button successfully")
    except TimeoutException:
        print("[WARNING] Channels button not clickable. Trying to proceed anyway.")
    except Exception as e:
        print(f"[ERROR] Unexpected error clicking Channels button: {e}")

    try:
        # Try both XPaths for search box
        try:
            search_box = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"][@data-tab="3"]'))
            )
        except TimeoutException:
            search_box = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="app"]/div/div[3]/div/div[2]/div[1]/span/div/span/div/div/div[1]/div/div/div[2]/div/div/div[1]'))
            )
            
        search_box.clear()
        search_box.send_keys(channel_name)
        print(f"[DEBUG] Entered '{channel_name}' in search box")
        time.sleep(6)  # Wait for search results to load
        
        # Try to clear search if needed
        try:
            clear_button = WebDriverWait(driver, 2).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="app"]/div/div[3]/div/div[2]/div[1]/span/div/span/div/div/div[1]/div/div/div[2]/button/div/span'))
            )
            clear_button.click()
            print("[DEBUG] Cleared search box")
        except:
            pass
            
    except TimeoutException:
        print(f"[ERROR] Search box not found for channel {channel_name}")
        return []
    except Exception as e:
        print(f"[ERROR] Unexpected error with search box: {e}")
        return []

    try:
        channel_elements = WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.XPATH, f'//span[contains(@title, "{channel_name}")]'))
        )
        print(f"[DEBUG] Found {len(channel_elements)} potential matches for '{channel_name}'")

        if len(channel_elements) > 0:
            for element in channel_elements:
                if channel_name.lower() in element.get_attribute('title').lower():
                    element.click()
                    print(f"[DEBUG] Clicked on the match for '{channel_name}'")
                    break
            else:
                channel_elements[0].click()
                print(f"[DEBUG] Clicked on the first partial match for '{channel_name}'")
        else:
            print(f"[WARNING] No matches found for '{channel_name}'")
            return []
    except TimeoutException:
        print(f"[ERROR] Channel {channel_name} not found in search results")
        return []
    except Exception as e:
        print(f"[ERROR] Unexpected error finding or clicking channel: {e}")
        return []

    time.sleep(5)  # Wait for messages to load
    print(f"[DEBUG] Waiting completed after clicking '{channel_name}'")






    # Scroll up to load more messages
    for i in range(25):
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.PAGE_UP)
        time.sleep(2)
        print(f"[DEBUG] Scrolled up {i + 1} times")

    try:
        posts = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, '//div[contains(@class, "message-in")]'))
        )
        print(f"[DEBUG] Found {len(posts)} posts for '{channel_name}'")
    except TimeoutException:
        print(f"[WARNING] No posts found for '{channel_name}'")
        return []

    channel_data = []

    for index, post in enumerate(posts):
        try:
            content = ''
            try:
                content_element = WebDriverWait(post, 5).until(
                    EC.presence_of_element_located((By.XPATH, './/div[contains(@class, "copyable-text")]'))
                )
                content = content_element.text
            except:
                try:
                    content_element = post.find_element(By.XPATH, './/div[contains(@class, "video-caption")]')
                    content = content_element.text
                except:
                    content = "[Media Content]"

            timestamp = WebDriverWait(post, 5).until(
                EC.presence_of_element_located((By.XPATH, './/div[contains(@data-pre-plain-text, "[")]'))
            ).get_attribute('data-pre-plain-text')

            reaction_count = get_reaction_count(post)

            post_type = "Text"
            if post.find_elements(By.XPATH, './/video'):
                post_type = "Video"
            elif post.find_elements(By.XPATH, './/img[contains(@src, "blob")]'):
                post_type = "GIF/Image"

            links = extract_links(content)

            if timestamp:
                channel_data.append({
                    'Channel_Name': channel_name,
                    'Channel_Language': channel_language,
                    'Post_Content': content,
                    'Post_Type': post_type,
                    'Timestamp': timestamp,
                    'Post_Reaction': reaction_count,
                    'Links': links,
                    'Poll': 'No'
                })
                print(f"[INFO] Processed {post_type} post {index + 1} for '{channel_name}' with {reaction_count} reactions")

        except Exception as e:
            print(f"[ERROR] Error processing post {index + 1} for '{channel_name}': {e}")
            continue

    print(f"[INFO] Finished processing {len(channel_data)} posts for '{channel_name}'")
    
    # Save data for this channel to a separate file
    if channel_data:
        df = pd.DataFrame(channel_data)
        file_path = os.path.join(output_folder, f"Whatsapp_Final_Data_{channel_name}_{datetime.now().date()}.xlsx")
        df.to_excel(file_path, index=False)
        print(f"[INFO] Data saved to {file_path}")
    
    return channel_data


def scrape_channel_category(driver, channels, category_name, output_folder):
    print(f"[INFO] Starting WhatsApp channels scrape for category: {category_name}")
    
    try:
        driver.get("https://web.whatsapp.com/")
        print(f"[DEBUG] Navigated to WhatsApp Web: {driver.current_url}")
    except Exception as e:
        print(f"[ERROR] Failed to navigate to WhatsApp Web: {e}")
        return []

    print(f"Please scan the QR code to log in to WhatsApp Web for {category_name}.")
    try:
        WebDriverWait(driver, 300).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[title="Channels"]'))
        )
        print(f"[INFO] Logged in and Channels button found for {category_name}.")
    except TimeoutException:
        print(f"[ERROR] Timeout waiting for WhatsApp Web login or Channels button for {category_name}.")
        return []
    time.sleep(5)
    for channel in channels:
        print(f"\n[INFO] Scraping channel: {channel} in {category_name}")
        scrape_channel(driver, channel, category_name, output_folder)
        time.sleep(5)  # small pause between channels


def main():
    # Define channel lists by language/category
    channels_by_category = {
        "News": {  # Combined Hindi and English news channels
            "Hindi": [
                'Aaj Tak', 'India TV', 'ABP News', 'News18 India', 'Zee News',
                'Republic Bharat', 'Times Now Navbharat', 'Good News Today',
                'TV9 Bharatvarsh', 'NDTV India', 'News - Dainik Bhaskar Hindi - India, Rajasthan, Madhya Pradesh, MP, CG, UP, Bihar, Delhi',
                'The Lallantop'
            ],
            "English": [
                'India Today', 'The Times of India', 'CNN News18',
                'NDTV', 'Republic', 'Times Now', 'Firstpost'
            ]
        },
        "Business": [  # Business channels as separate thread
            'Business Today', 'Market Today', 'Money Today', 'Tech Today',
            'Business Today Subscriptions', 'Mint',
            'Money9', 'ET NOW', 'Republic Business', 'moneycontrol',
            'Financial Express', 'CNBC-TV18', 'NDTV Profit'
        ]
    }

    # Create output folder based on today's date
    output_folder = f"Whatsapp_Final_Data_{datetime.now().date()}"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    print(f"[INFO] Output folder created/exists: {output_folder}")

    # Create drivers for each thread
    driver1 = setup_driver()  # For News (Hindi + English)
    driver2 = setup_driver()  # For Business
    
    # Create and start threads
    threads = []
    
    # Thread 1: News channels (Hindi and English)
    news_thread = threading.Thread(
        target=lambda: [
            scrape_channel_category(driver1, channels_by_category["News"]["Hindi"], "Hindi", output_folder),
            scrape_channel_category(driver1, channels_by_category["News"]["English"], "English", output_folder)
        ]
    )
    threads.append(news_thread)
    news_thread.start()
    time.sleep(10)  # Stagger thread starts
    
    # Thread 2: Business channels
    business_thread = threading.Thread(
        target=scrape_channel_category,
        args=(driver2, channels_by_category["Business"], "Business", output_folder)
    )
    threads.append(business_thread)
    business_thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # Close all drivers
    driver1.quit()
    driver2.quit()
    print("[INFO] All Chrome drivers closed.")


if __name__ == "__main__":
    main()
    
    
    
    
    
    
    
    
    
    
    
    # channels_by_category = {
    #     "News": {  # Combined Hindi and English news channels
    #         "Hindi": [
    #             'Aaj Tak', 'India TV', 'ABP News', 'News18 India', 'Zee News',
    #             'Republic Bharat', 'Times Now Navbharat', 'Good News Today',
    #             'TV9 Bharatvarsh', 'NDTV India', 'News - Dainik Bhaskar Hindi - India, Rajasthan, Madhya Pradesh, MP, CG, UP, Bihar, Delhi',
    #             'The Lallantop'
    #         ],
    #         "English": [
    #             'India Today', 'The Times of India', 'CNN News18',
    #             'NDTV', 'Republic', 'Times Now', 'Firstpost'
    #         ]
    #     },
    #     "Business": [  # Business channels as separate thread
    #         'Business Today', 'Market Today', 'Money Today', 'Tech Today',
    #         'Business Today Subscriptions', 'Mint', 'The Economic Times',
    #         'Money9', 'ET NOW', 'Republic Business', 'moneycontrol',
    #         'Financial Express', 'CNBC-TV18', 'NDTV Profit'
    #     ]
    # }