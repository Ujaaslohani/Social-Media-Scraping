import os
import time
import pandas as pd
from datetime import datetime
from pathlib import Path
import instaloader

# Configuration - Edit these values
INSTAGRAM_USERNAME = "your_username"  # Replace with your actual username
INSTAGRAM_PASSWORD = "your_pasword"  # Replace with your actual password

# Login to Instagram using Instaloader
def login_instaloader():
    L = instaloader.Instaloader()
    try:
        L.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        print("✅ Logged in successfully.\n")
    except Exception as e:
        print(f"❌ Login failed: {e}")
        exit()
    return L

# Get latest 'instagram_dd_mm_yyyy' folder
def get_latest_folder():
    folders = [f for f in Path.cwd().iterdir() if f.is_dir() and f.name.startswith("instagram_")]
    if not folders:
        raise FileNotFoundError("No folder found.")
    return max(folders, key=os.path.getmtime)

# Collect URLs from Excel files in the folder and track their source files
def collect_links(folder_path):
    file_links = {}
    for file in folder_path.glob("*.xlsx"):
        df = pd.read_excel(file)
        if "URL" in df.columns:
            links = df["URL"].dropna().unique().tolist()
            if links:
                file_links[file.name] = links
    return file_links

# Scrape post info using Instaloader
def scrape_post(L, url):
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

def main():
    L = login_instaloader()
    folder = get_latest_folder()
    print(f"📁 Using folder: {folder}")
    
    file_links = collect_links(folder)
    total_links = sum(len(links) for links in file_links.values())
    print(f"🔗 Found {total_links} unique links across {len(file_links)} files\n")

    today_date = datetime.now().strftime("%d_%m_%Y")
    
    for filename, links in file_links.items():
        # Extract profile name from original filename
        try:
            # Expected format: instagram_{profilename}_{date}.xlsx
            parts = filename.split('_')
            profilename = parts[1] if len(parts) > 2 else "data"
        except:
            profilename = "data"
            
        output_filename = f"instagram_post_data_{profilename}_{today_date}.xlsx"
        output_path = folder / output_filename
        
        scraped = []
        print(f"\nProcessing {len(links)} links from {filename}")
        
        for idx, link in enumerate(links, 1):
            print(f"[{idx}/{len(links)}] Scraping: {link}")
            data = scrape_post(L, link)
            if data:
                scraped.append(data)
            time.sleep(5)  # delay between requests

        if scraped:
            df = pd.DataFrame(scraped)
            df.to_excel(output_path, index=False)
            print(f"✅ Data saved to {output_path}")
        else:
            print("⚠️ No posts were successfully scraped from this file.")

if __name__ == "__main__":
    main()