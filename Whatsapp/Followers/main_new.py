from playwright.sync_api import sync_playwright
import time
import re
import pandas as pd
from datetime import datetime
import threading
import traceback
import os
from pathlib import Path

# Configuration
CONFIG = {
    'headless': False,
    'slow_mo': 50,
    'timeout': 120000,  # 2 minutes timeout per channel
    'state_path': 'whatsapp_auth_state.json',
    'login_wait_time': 90,  # seconds to wait for manual login if needed
    'max_retries': 2,  # max retries per channel
}

# XPATH Definitions (using your provided XPaths)
XPATHS = {
    'search_box': '//*[@id="app"]/div/div[3]/div/div[2]/div[1]/span/div/span/div/div/div[1]/div/div/div[2]/div/div/div[1]',
    'clear_search': '//*[@id="app"]/div/div[3]/div/div[2]/div[1]/span/div/span/div/div/div[1]/div/div/div[2]/button/div/span',
    'channel_header': '//*[@id="main"]/header',
    'channel_info_name': '//*[@id="app"]/div/div[3]/div/div[5]/span/div/span/div/div/section/div[1]/div[1]/div[2]/div/div/div/div/span/span',
    'channel_info_followers': '//*[@id="app"]/div/div[3]/div/div[5]/span/div/span/div/div/section/div[1]/div[1]/div[3]/span/div',
    'conversation_list': 'div[data-testid="conversation-list"]',
}

# Start time tracking
start_time = time.time()

def load_excel_data(path):
    """Load and prepare data from Excel file"""
    try:
        df = pd.read_excel(path)
        return {
            'channel_names': list(df['Channel Name']),
            'group_names': list(df['GroupName']),
            'links': list(df['Link/URL']),
        }
    except Exception as e:
        print(f"Error loading Excel file: {e}")
        raise

# Load Excel data
try:
    data = load_excel_data("new whatsapp followers tracking.xlsx")
    channel_names = data['channel_names']
    group_names = data['group_names']
    links = data['links']
except Exception as e:
    print(f"Failed to load data: {e}")
    exit(1)

# Thread-safe results collection
results_lock = threading.Lock()
results = {
    'channel_names': [],
    'follower_counts': [],
    'processed_indices': set(),
}

def save_state(context, path=CONFIG['state_path']):
    """Save authentication state"""
    storage = context.storage_state()
    with open(path, "w") as f:
        f.write(storage)

def load_state(browser, path=CONFIG['state_path']):
    """Load authentication state if exists"""
    if os.path.exists(path):
        context = browser.new_context(storage_state=path)
        print("Loaded existing authentication state")
        return context
    return None

def clean_follower_text(text):
    """Extract follower count from text"""
    if not text:
        return "N/A"
    
    # Handle different formats
    match = re.search(r'(\d{1,3}(?:,\d{1,3})*)\s*(followers|सदस्य)', text)
    if match:
        return match.group(1)
    return "N/A"

def process_channel(page, channel_name, thread_id):
    """Process a single channel to get follower count"""
    start_time = time.time()
    retry_count = 0
    
    while retry_count < CONFIG['max_retries']:
        try:
            print(f"[Thread {thread_id}] Attempt {retry_count + 1} for '{channel_name}'")
            
            # Click on search box using your XPath
            search_box = page.locator(f'xpath={XPATHS["search_box"]}')
            search_box.click()
            time.sleep(1)
            
            # Clear search box
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            time.sleep(1)
            
            # Type channel name
            search_box.type(channel_name, delay=100)
            time.sleep(2)  # Wait for results
            
            # Try to find and click the channel (using your logic for special cases)
            if channel_names.index(channel_name) in [6, 12, 72, 74, 88, 109, 120, 143, 193, 215, 191, 213, 141, 71]:
                channel_locator = page.locator(f'span[title="{channel_name}"]')
            else:
                channel_locator = page.locator('span[class="matched-text _ao3e"]').nth(0)
            
            if channel_locator.count() > 0:
                channel_locator.click()
            else:
                print(f"[Thread {thread_id}] Channel not found: '{channel_name}'")
                return None
            
            time.sleep(2)
            
            # Open channel info using your XPath
            page.locator(f'xpath={XPATHS["channel_header"]}').click()
            time.sleep(2)
            
            # Get follower count using your XPath
            follower_element = page.locator(f'xpath={XPATHS["channel_info_followers"]}')
            if follower_element.count() == 0:
                print(f"[Thread {thread_id}] No follower element found for '{channel_name}'")
                return None
                
            followers_text = follower_element.text_content()
            followers_clean = clean_follower_text(followers_text)
            
            # Get actual channel name using your XPath
            channel_name_element = page.locator(f'xpath={XPATHS["channel_info_name"]}')
            actual_channel_name = channel_name_element.text_content() if channel_name_element.count() > 0 else channel_name
            
            print(f"[Thread {thread_id}] ✅ Fetched followers for '{actual_channel_name}': {followers_clean}")
            
            # Clear search using your XPath
            page.locator(f'xpath={XPATHS["clear_search"]}').click()
            time.sleep(1)
            
            return (actual_channel_name, followers_clean)
            
        except Exception as e:
            print(f"[Thread {thread_id}] Attempt {retry_count + 1} failed for '{channel_name}': {str(e)}")
            retry_count += 1
            time.sleep(2)
            
            # Check if we're stuck on the same channel for too long
            if time.time() - start_time > CONFIG['timeout'] / 1000:
                print(f"[Thread {thread_id}] Timeout processing '{channel_name}', skipping...")
                return None
    
    return None

def worker_thread(start_index, count, thread_id):
    """Worker thread to process a range of channels"""
    thread_results = {
        'channel_names': [],
        'follower_counts': [],
        'processed_indices': set(),
    }
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                channel="chrome",
                headless=CONFIG['headless'],
                slow_mo=CONFIG['slow_mo']
            )
            
            # Try to load existing auth state
            context = load_state(browser) or browser.new_context()
            context.set_default_timeout(CONFIG['timeout'])
            
            page = context.new_page()
            page.goto("https://web.whatsapp.com/")
            
            # Check if we need to login
            if page.locator('text="Use WhatsApp on your computer"').count() > 0:
                print(f"[Thread {thread_id}] Waiting for manual login...")
                page.wait_for_selector(XPATHS['conversation_list'], timeout=CONFIG['login_wait_time'] * 1000)
                save_state(context)
                print(f"[Thread {thread_id}] Logged in and saved auth state")
            
            # Switch to channels view
            page.click('button[aria-label="Channels"]')
            time.sleep(5)
            
            end_index = min(start_index + count, len(channel_names))
            
            for j in range(start_index, end_index):
                if j in results['processed_indices']:
                    continue
                    
                channel_name = channel_names[j]
                print(f"[Thread {thread_id}] Processing index {j}: '{channel_name}'")
                
                result = process_channel(page, channel_name, thread_id)
                if result:
                    actual_name, followers = result
                    thread_results['channel_names'].append(actual_name)
                    thread_results['follower_counts'].append(followers)
                    thread_results['processed_indices'].add(j)
                
                time.sleep(1)
            
            # Save results
            with results_lock:
                results['channel_names'].extend(thread_results['channel_names'])
                results['follower_counts'].extend(thread_results['follower_counts'])
                results['processed_indices'].update(thread_results['processed_indices'])
                
            print(f"[Thread {thread_id}] Finished. Processed {len(thread_results['channel_names'])} channels")
            
    except Exception as e:
        print(f"[Thread {thread_id}] Thread error: {str(e)}")
        traceback.print_exc()

def main():
    """Main execution function"""
    print(f"Total entries in Excel: {len(channel_names)}")
    
    # Calculate thread ranges
    total_entries = len(channel_names)
    mid_point = total_entries // 2
    
    # Create and start threads
    threads = [
        threading.Thread(target=worker_thread, args=(0, mid_point, 1)),
        threading.Thread(target=worker_thread, args=(mid_point, total_entries - mid_point, 2))
    ]
    
    for t in threads:
        t.start()
        time.sleep(10)
    
    for t in threads:
        t.join()
    
    # Prepare final data
    formatted_date = datetime.now().strftime("%b %d %Y")
    
    # Align all lists to the original Excel length
    final_channel_names = []
    final_follower_counts = []
    
    for i in range(len(channel_names)):
        if i in results['processed_indices']:
            idx_in_results = list(results['processed_indices']).index(i)
            final_channel_names.append(results['channel_names'][idx_in_results])
            final_follower_counts.append(results['follower_counts'][idx_in_results])
        else:
            final_channel_names.append("Not processed")
            final_follower_counts.append("N/A")
    
    # Create output DataFrame
    output_data = {
        "GroupName": group_names,
        "Channel Name": final_channel_names,
        "Links/URL": links,
        formatted_date: final_follower_counts,
    }
    
    df_out = pd.DataFrame(output_data)
    
    # Count valid results
    valid_followers = sum(1 for count in final_follower_counts if count != "N/A" and count != "Not processed")
    print(f"\n📊 Total followers fetched: {valid_followers} out of {len(channel_names)} channels")
    
    # Save to Excel
    filename = f'Whatsapp_Followers_Tracking_{formatted_date.replace(" ", "_")}.xlsx'
    df_out.to_excel(filename, index=False)
    print(f"\n✅ Output saved to {filename}")
    
    # Execution time
    end_time = time.time()
    total_seconds = round(end_time - start_time, 2)
    print(f"\n⏱️ Execution Time: {total_seconds} seconds ({total_seconds/60:.1f} minutes)")

if __name__ == "__main__":
    main()