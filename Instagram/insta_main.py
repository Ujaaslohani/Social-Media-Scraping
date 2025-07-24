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

# Suppress all warnings
warnings.filterwarnings("ignore")
os.environ['WDM_LOG_LEVEL'] = '0'
os.environ['WDM_PRINT_FIRST_LINE'] = 'False'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

def human_type(element, text, delay=(0.1, 0.3)):
    """Simulate human typing with random delays"""
    for character in text:
        element.send_keys(character)
        time.sleep(random.uniform(*delay))

def get_credentials():
    """Hardcoded Instagram credentials"""
    print("\nInstagram Login Required")
    username = "your_username"
    password = "your_password"
    return username, password

def login_to_instagram(driver, username, password):
    """Login to Instagram with human-like behavior"""
    print("Logging in to Instagram...")
    driver.get("https://www.instagram.com/accounts/login/")
    time.sleep(2)

    # Accept cookies
    try:
        cookie_button = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Allow essential and optional cookies')]")))
        cookie_button.click()
        time.sleep(1)
    except:
        pass

    # Fill login form with simulated typing
    username_field = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "username")))
    human_type(username_field, username)
    
    password_field = driver.find_element(By.NAME, "password")
    human_type(password_field, password)
    
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    time.sleep(5)

    # Dismiss save login info
    try:
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Not Now')]"))).click()
        time.sleep(1)
    except:
        pass

    # Dismiss notifications
    try:
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Not Now')]"))).click()
        time.sleep(1)
    except:
        pass
    
    time.sleep(2)
    print("Login successful!\n")

def collect_links_with_scroll(driver, username, max_time=60):
    """Collect post/reel URLs with automated scrolling"""
    print(f"Automatically scrolling through @{username}'s profile for {max_time} seconds")
    print("The script will collect all visible post links during this time...\n")
    
    driver.get(f"https://www.instagram.com/{username}/")
    time.sleep(3)
    
    post_reel_links = set()
    start_time = time.time()
    last_update = 0
    
    # Get the page body for scrolling
    body = driver.find_element(By.TAG_NAME, 'body')
    
    while time.time() - start_time < max_time:
        try:
            # Scroll down
            body.send_keys(Keys.PAGE_DOWN)
            time.sleep(random.uniform(0.5, 1.5))  # Random delay between scrolls
            
            # Get fresh references to elements each iteration
            links = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.TAG_NAME, "a")))
            
            for link in links:
                try:
                    href = link.get_attribute("href")
                    if href and ("/p/" in href or "/reel/" in href):
                        post_reel_links.add(href)
                except:
                    continue  # Skip if element becomes stale during iteration
            
            # Update user on progress
            elapsed = int(time.time() - start_time)
            remaining = max_time - elapsed
            if elapsed - last_update >= 10:  # Update every 10 seconds
                print(f"Time remaining: {remaining} seconds | Links collected: {len(post_reel_links)}")
                last_update = elapsed
            
        except Exception as e:
            time.sleep(1)
            continue
    
    print(f"\nCollection complete for @{username}")
    print(f"Total links collected: {len(post_reel_links)}\n")
    return list(post_reel_links)

def save_to_excel(profile, links):
    """Save links to Excel in a dated folder"""
    date_str = datetime.now().strftime("%d_%m_%Y")
    folder_name = f"instagram_{date_str}"
    os.makedirs(folder_name, exist_ok=True)

    filename = os.path.join(folder_name, f"instagram_{profile}_{date_str}.xlsx")
    df = pd.DataFrame(links, columns=["URL"])
    df.to_excel(filename, index=False)
    print(f"Saved to {filename}\n")

def main():
    # Setup browser to run in headless mode without warnings
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1200,800")
    options.add_argument("--log-level=3")  # Suppress Chrome logging
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    # Suppress WebDriver manager output
    os.environ['WDM_LOG'] = str(0)
    os.environ['WDM_LOG_LEVEL'] = str(0)
    
    # Create service with no window
    service = Service(ChromeDriverManager().install())
    service.creationflags = 0x08000000  # CREATE_NO_WINDOW flag

    driver = webdriver.Chrome(service=service, options=options)

    try:
        username, password = get_credentials()
        login_to_instagram(driver, username, password)

        # List of profiles to scrape
        target_profiles = ["id_name"]  # Replace with your own list

        for profile in target_profiles:
            links = collect_links_with_scroll(driver, profile, max_time=60)
            if links:
                save_to_excel(profile, links)
            time.sleep(2)  # Small delay between profiles

    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        driver.quit()
        print("Scraping complete.")

if __name__ == "__main__":
    main()