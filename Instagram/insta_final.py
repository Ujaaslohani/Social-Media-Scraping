import time
import os
import random
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import warnings
import instaloader
import concurrent.futures
import mysql.connector
from mysql.connector import Error

# Suppress warnings
warnings.filterwarnings("ignore")
os.environ['WDM_LOG_LEVEL'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

# Instagram credentials
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")  # set in env
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")  # set in env

# AWS RDS MySQL credentials
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


# --- Utility Functions ---
def human_type(element, text, delay=(0.1, 0.3)):
    """Simulate human typing with random delays"""
    for character in text:
        element.send_keys(character)
        time.sleep(random.uniform(*delay))


def get_credentials():
    """Return Instagram credentials"""
    return INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD


# --- Database Functions ---
def create_db_connection():
    """Connect to AWS RDS MySQL"""
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            port=3306
        )
        if connection.is_connected():
            print("✅ Connected to AWS RDS MySQL")
        return connection
    except Error as e:
        print(f"❌ Error connecting to RDS: {e}")
        return None


def create_table_if_not_exists(connection):
    """Create table to store Instagram posts"""
    create_table_query = """
    CREATE TABLE IF NOT EXISTS instagram_posts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        profile VARCHAR(255),
        url VARCHAR(500),
        caption TEXT,
        upload_date DATETIME,
        likes INT,
        comments INT,
        is_video BOOLEAN,
        scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """
    cursor = connection.cursor()
    cursor.execute(create_table_query)
    connection.commit()


def save_to_db(data, profile):
    """Save scraped data into MySQL database"""
    connection = create_db_connection()
    if not connection:
        print("⚠️ Database connection failed. Data not saved.")
        return

    create_table_if_not_exists(connection)
    
    insert_query = """
    INSERT INTO instagram_posts
    (profile, url, caption, upload_date, likes, comments, is_video)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    cursor = connection.cursor()
    for post in data:
        cursor.execute(insert_query, (
            profile,
            post.get("url"),
            post.get("caption"),
            post.get("upload_date"),
            post.get("likes"),
            post.get("comments"),
            post.get("is_video")
        ))
    
    connection.commit()
    cursor.close()
    connection.close()
    print(f"✅ {len(data)} posts for @{profile} saved to database\n")


# --- Selenium Functions ---
def login_to_instagram_selenium(driver, username, password):
    """Login to Instagram using Selenium"""
    print("Logging in to Instagram via Selenium...")
    driver.get("https://www.instagram.com/accounts/login/")
    time.sleep(2)

    # Accept cookies if popup exists
    try:
        cookie_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Allow essential and optional cookies')]"))
        )
        cookie_button.click()
        time.sleep(1)
    except:
        pass

    username_field = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "username")))
    human_type(username_field, username)

    password_field = driver.find_element(By.NAME, "password")
    human_type(password_field, password)

    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    time.sleep(5)

    # Dismiss save login info
    try:
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Not Now')]"))
        ).click()
        time.sleep(1)
    except:
        pass

    # Dismiss notifications
    try:
        WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Not Now')]"))
        ).click()
        time.sleep(1)
    except:
        pass

    print("Selenium login successful!\n")


def collect_links_with_scroll(driver, username, max_time=60):
    """Collect post/reel URLs with automated scrolling"""
    print(f"Collecting post links from @{username} for {max_time} seconds...")
    driver.get(f"https://www.instagram.com/{username}/")
    time.sleep(3)

    post_reel_links = set()
    start_time = time.time()
    last_update = 0
    body = driver.find_element(By.TAG_NAME, 'body')

    while time.time() - start_time < max_time:
        try:
            body.send_keys(Keys.PAGE_DOWN)
            time.sleep(random.uniform(0.5, 1.5))

            links = driver.find_elements(By.TAG_NAME, "a")
            for link in links:
                try:
                    href = link.get_attribute("href")
                    if href and ("/p/" in href or "/reel/" in href):
                        post_reel_links.add(href)
                except:
                    continue

            elapsed = int(time.time() - start_time)
            if elapsed - last_update >= 10:
                remaining = max_time - elapsed
                print(f"Time remaining: {remaining}s | Links collected: {len(post_reel_links)}")
                last_update = elapsed

        except:
            time.sleep(1)
            continue

    print(f"Collected {len(post_reel_links)} links for @{username}\n")
    return list(post_reel_links)


# --- Instaloader Functions ---
def login_instaloader():
    """Login via Instaloader"""
    print("Logging in to Instagram via Instaloader...")
    L = instaloader.Instaloader()
    try:
        L.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        print("✅ Instaloader login successful.\n")
    except Exception as e:
        print(f"❌ Instaloader login failed: {e}")
        exit()
    return L


def scrape_post(L, url):
    """Scrape post info using Instaloader"""
    try:
        shortcode = url.strip("/").split("/")[-1]
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        return {
            "url": url,
            "caption": post.caption,
            "upload_date": post.date_utc,
            "likes": post.likes,
            "comments": post.comments,
            "is_video": post.is_video,
        }
    except Exception as e:
        print(f"❌ Failed to scrape {url}: {e}")
        return None


def process_links_parallel(L, links, profile, max_workers=5):
    """Process collected links in parallel and save to DB"""
    scraped = []
    print(f"Processing {len(links)} links from @{profile} with {max_workers} workers...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(scrape_post, L, url): url for url in links}
        for i, future in enumerate(concurrent.futures.as_completed(future_to_url), 1):
            url = future_to_url[future]
            try:
                data = future.result()
                if data:
                    scraped.append(data)
                print(f"[{i}/{len(links)}] Scraped: {url}")
            except Exception as e:
                print(f"❌ Error scraping {url}: {e}")
            time.sleep(0.5)

    if scraped:
        save_to_db(scraped, profile)
    else:
        print("⚠️ No posts scraped successfully.")


# --- Main ---
def main():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1200,800")
    options.add_argument("--log-level=3")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        username, password = get_credentials()
        login_to_instagram_selenium(driver, username, password)

        target_profiles = ["profile1"]  # replace with your target profiles
        all_profile_links = {}

        for profile in target_profiles:
            print(f"\n{'='*50}")
            print(f"Processing profile: @{profile}")
            print(f"{'='*50}")
            links = collect_links_with_scroll(driver, profile, max_time=60)
            all_profile_links[profile] = links
            time.sleep(2)

        L = login_instaloader()

        for profile, links in all_profile_links.items():
            print(f"\n{'='*50}")
            print(f"Scraping detailed data for @{profile}")
            print(f"{'='*50}")
            start_time = time.time()
            process_links_parallel(L, links, profile, max_workers=5)
            elapsed = time.time() - start_time
            print(f"⏱️ Completed in {elapsed:.2f} seconds")

    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        driver.quit()
        print("\nScraping complete.")


if __name__ == "__main__":
    main()
