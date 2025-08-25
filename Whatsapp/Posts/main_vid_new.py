from playwright.sync_api import sync_playwright
import pandas as pd
import time, re, os, traceback, threading
from datetime import datetime

CONFIG = {
    'headless': False,
    'slow_mo': 50,
    'timeout': 120000,
    'state_path': 'whatsapp_auth_state.json',
    'login_wait_time': 30,
    'scroll_pause': 1,   # wait after each scroll
    'scroll_count': 120,  # max scrolls in case date not found
    'max_retries': 2,

    # --- New Date Filters ---
    'from_date': "10/08/2025",   # stop when reaching this date (discard it)
    'to_date': "19/08/2025",     # remove posts >= this date before saving
}

XPATHS = {
    'search_box': '//*[@id="app"]/div/div[3]/div/div[2]/div[1]/span/div/span/div/div/div[1]/div/div/div[2]/div/div/div[1]',
    'clear_search': '//*[@id="app"]/div/div[3]/div/div[2]/div[1]/span/div/span/div/div/div[1]/div/div/div[2]/button/div/span',
    'channel_header': '//*[@id="main"]/header',
    'conversation_list': 'div[data-testid="conversation-list"]',
    'posts_container': '//*[@id="main"]/div[2]/div/div[2]',
    'post_item': './/div[contains(@class, "message-in") or contains(@class, "message-out")]',
    'copyable_text': './/div[contains(@class, "copyable-text")]',
    'reaction_count': './/div[contains(@class,"reactions")]//span',
}

channels_by_category = {
    "News": {
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
    "Business": [
        'Business Today', 'Market Today', 'Money Today', 'Tech Today',
        'Business Today Subscriptions', 'Mint',
        'Money9', 'ET NOW', 'Republic Business', 'moneycontrol',
        'Financial Express', 'CNBC-TV18', 'NDTV Profit'
    ]
}

results_lock = threading.Lock()
results = []

def save_state(context, path=CONFIG['state_path']):
    storage = context.storage_state()
    with open(path, "w") as f:
        f.write(storage)

def load_state(browser, path=CONFIG['state_path']):
    if os.path.exists(path):
        context = browser.new_context(storage_state=path)
        print("Loaded existing authentication state")
        return context
    return None

def extract_links(text):
    if not text:
        return []
    return re.findall(r'(https?://\S+)', text)

def parse_timestamp(ts_str):
    """Convert WhatsApp timestamp '17:42, 18/08/2025' → datetime.date"""
    try:
        return datetime.strptime(ts_str, "%H:%M, %d/%m/%Y")
    except:
        return None

def process_posts(page, channel_name, channel_type):
    posts_data = []
    seen_posts = set()

    # Convert config dates to datetime.date
    from_date = datetime.strptime(CONFIG['from_date'], "%d/%m/%Y").date()

    try:
        posts_container = page.locator(f'xpath={XPATHS["posts_container"]}')
        stop_scraping = False

        for i in range(CONFIG['scroll_count']):
            if stop_scraping:
                break

            try:
                page.set_default_timeout(5000)

                posts = posts_container.locator("xpath=" + XPATHS['post_item']).all()
                for post in posts:
                    try:
                        content = "[Media Content]"
                        if post.locator("xpath=" + XPATHS['copyable_text']).count() > 0:
                            content = post.locator("xpath=" + XPATHS['copyable_text']).nth(0).text_content()

                        timestamp = None
                        if post.locator("xpath=" + XPATHS['copyable_text']).count() > 0:
                            copyable = post.locator("xpath=" + XPATHS['copyable_text']).nth(0)
                            ts_raw = copyable.get_attribute("data-pre-plain-text")
                            if ts_raw:
                                m = re.match(r'\[(.*?)\]', ts_raw.strip())
                                if m:
                                    timestamp = m.group(1)

                        reaction_count = "0"
                        if post.locator("button[aria-label*='Reactions']").count() > 0:
                            aria_label = post.locator("button[aria-label*='Reactions']").nth(0).get_attribute("aria-label")
                            if aria_label:
                                match = re.search(r'(\d+)\s+in total', aria_label)
                                if match:
                                    reaction_count = match.group(1)

                        if post.locator("video").count() > 0:
                            post_type = "Video"
                        elif post.locator("img[src*='blob']").count() > 0:
                            post_type = "GIF/Image"
                        else:
                            post_type = "Text"

                        links = extract_links(content)

                        post_date = None
                        if timestamp:
                            ts_dt = parse_timestamp(timestamp)
                            if ts_dt:
                                post_date = ts_dt.date()
                                # stop if we reach from_date or older
                                if post_date <= from_date:
                                    stop_scraping = True
                                    break

                        post_key = f"{timestamp}-{content[:30]}"
                        if post_key not in seen_posts:
                            seen_posts.add(post_key)
                            posts_data.append({
                                "Channel_Name": channel_name,
                                "Type": channel_type,
                                "Post_Content": content,
                                "Post_Type": post_type,
                                "Timestamp": timestamp,
                                "Post_Reaction": reaction_count,
                                "Links": ", ".join(links) if links else "",
                            })
                    except:
                        continue

                page.evaluate("(el) => el.scrollBy(0, -1000)", posts_container.element_handle())
                time.sleep(CONFIG['scroll_pause'])
                print(f"[{channel_name}] Scroll {i+1}/{CONFIG['scroll_count']} → {len(posts_data)} posts")

            finally:
                page.set_default_timeout(CONFIG['timeout'])

        print(f"[{channel_name}] ✅ Collected posts: {len(posts_data)}")

    except Exception as e:
        print(f"❌ Error processing posts for {channel_name}: {e}")
        traceback.print_exc()

    return posts_data

def process_channel(page, channel_name, channel_type):
    retry = 0
    while retry < CONFIG['max_retries']:
        try:
            search_box = page.locator(f'xpath={XPATHS["search_box"]}')
            search_box.click()
            time.sleep(1)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            search_box.type(channel_name, delay=100)
            time.sleep(2)

            channel_locator = page.locator(f'span[title="{channel_name}"]')
            if channel_locator.count() > 0:
                channel_locator.click()
            else:
                print(f"Channel not found: {channel_name}")
                return []
            time.sleep(3)

            data = process_posts(page, channel_name, channel_type)

            page.locator(f'xpath={XPATHS["clear_search"]}').click()
            return data
        except Exception as e:
            print(f"Error opening channel {channel_name}: {e}")
            retry += 1
            time.sleep(2)
    return []

def worker_thread(channels, lang_or_category, thread_id):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=CONFIG['headless'], slow_mo=CONFIG['slow_mo'])
            context = load_state(browser) or browser.new_context()
            context.set_default_timeout(CONFIG['timeout'])
            page = context.new_page()
            page.goto("https://web.whatsapp.com/")

            try:
                continue_btn = page.locator('xpath=//*[@id="app"]/div[1]/span[2]/div/div/div/div/div/div/div[2]/div/button')
                if continue_btn.count() > 0:
                    print(f"[Thread {thread_id}] Found 'Continue' button, clicking it...")
                    continue_btn.click()
                    time.sleep(3)
            except:
                pass

            if page.locator('text="Use WhatsApp on your computer"').count() > 0:
                print(f"[Thread {thread_id}] Waiting for manual login...")
                page.wait_for_selector(XPATHS['conversation_list'], timeout=CONFIG['login_wait_time'] * 1000)
                save_state(context)
                print(f"[Thread {thread_id}] Logged in and saved state")

            page.click('button[aria-label="Channels"]')
            time.sleep(5)

            for ch in channels:
                print(f"[Thread {thread_id}] Processing channel: {ch}")
                if lang_or_category == "News":
                    if ch in channels_by_category["News"]["Hindi"]:
                        channel_type = "Hindi"
                    else:
                        channel_type = "English"
                else:
                    channel_type = lang_or_category

                data = process_channel(page, ch, channel_type)
                with results_lock:
                    results.extend(data)
                time.sleep(1)
    except Exception as e:
        print(f"[Thread {thread_id}] Error: {e}")
        traceback.print_exc()

def main():
    threads = []
    news_channels = channels_by_category["News"]["Hindi"] + channels_by_category["News"]["English"]
    business_channels = channels_by_category["Business"]

    t1 = threading.Thread(target=worker_thread, args=(news_channels, "News", 1))
    t2 = threading.Thread(target=worker_thread, args=(business_channels, "Business", 2))
    threads.extend([t1, t2])

    for t in threads:
        t.start()
        time.sleep(10)

    for t in threads:
        t.join()

    df = pd.DataFrame(results)

    # Apply to_date filter before saving
    if not df.empty:
        to_date = datetime.strptime(CONFIG['to_date'], "%d/%m/%Y").date()

        def filter_date(ts):
            try:
                ts_dt = datetime.strptime(ts, "%H:%M, %d/%m/%Y")
                return ts_dt.date() < to_date
            except:
                return False

        df = df[df['Timestamp'].apply(filter_date)]

    formatted_date = datetime.now().strftime("%b_%d_%Y")
    filename = f"Whatsapp_Posts_{formatted_date}.xlsx"
    df.to_excel(filename, index=False)
    print(f"\n✅ Data saved to {filename}")

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
    #         'Business Today Subscriptions', 'Mint',
    #         'Money9', 'ET NOW', 'Republic Business', 'moneycontrol',
    #         'Financial Express', 'CNBC-TV18', 'NDTV Profit'
    #     ]
    # }