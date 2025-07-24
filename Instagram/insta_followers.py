import os
import time
import pandas as pd
from datetime import datetime
import instaloader

# Configuration - Edit these values
INSTAGRAM_USERNAME = "your_username"  # Replace with your actual username
INSTAGRAM_PASSWORD = "your_password"  # Replace with your actual password
TARGET_PROFILES = ["id_name"]  # Add profiles to analyze

def login_instaloader(): 
    """Login to Instagrm using Instaloader"""
    L = instaloader.Instaloader()
    try:
        L.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        print("✅ Logge in successfully")
        return L
    except Exception as e:
        print(f"❌ Login failed: {e}")
        exit()

def get_profile_data(L, username):
    """Get profile metadata including followers and post count"""
    try:
        profile = instaloader.Profile.from_username(L.context, username)
        return {
            "username": username,
            "full_name": profile.full_name,
            "followers": profile.followers,
            "following": profile.followees,
            "posts": profile.mediacount,
            "is_private": profile.is_private,
            "is_verified": profile.is_verified,
            "biography": profile.biography,
            "external_url": profile.external_url,
            "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        print(f"❌ Failed to get profile data for @{username}: {e}")
        return None

def save_to_csv(data, filename_prefix):
    """Save data to CSV with timestamp"""
    today = datetime.now().strftime("%Y_%m_%d")
    filename = f"{filename_prefix}_{today}.csv"
    
    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)
    print(f"✅ Saved to {filename}")
    return filename

def main():
    L = login_instaloader()
    
    # Collect profile metadata
    profiles_data = []
    for username in TARGET_PROFILES:
        print(f"\nProcessing @{username}...")
        profile_data = get_profile_data(L, username)
        if profile_data:
            profiles_data.append(profile_data)
            time.sleep(5)  # Rate limiting between profiles
    
    if profiles_data:
        save_to_csv(profiles_data, "instagram_profiles")
    

if __name__ == "__main__":
    main()