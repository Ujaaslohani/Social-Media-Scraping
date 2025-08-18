# 🚀 Social Media Scraping Toolkit

A comprehensive Python-based toolkit for scraping data from various social media platforms including YouTube, Instagram, Twitter, WhatsApp, and more. This project provides automated data collection capabilities with database integration and Excel export functionality.

## 📋 Table of Contents
- [Features](#features)
- [Supported Platforms](#supported-platforms)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)
- [Database Schema](#database-schema)
- [Contributing](#contributing)
- [License](#license)

## ✨ Features

- **Multi-Platform Support**: Scrapes data from YouTube, Instagram, Twitter, WhatsApp, and more
- **Database Integration**: MySQL database support with SQLAlchemy ORM
- **Excel Export**: Automated data export to Excel with date-based folder organization
- **Rate Limiting**: Built-in delays and error handling to respect API limits
- **Environment Configuration**: Secure credential management using .env files
- **Logging**: Comprehensive logging for debugging and monitoring
- **Modular Design**: Clean, reusable code structure for easy extension

## 🔧 Supported Platforms

### 📺 YouTube
- Channel video scraping
- Video metadata extraction (title, description, views, likes)
- Daily video collection from specified channels
- YouTube API v3 integration

### 📸 Instagram
- Profile post/reel scraping
- Automated scrolling and link collection
- Headless browser support
- Excel export functionality

### 🐦 Twitter
- User tweet collection
- Tweet metadata extraction (likes, retweets, replies)
- Twikit library integration
- Authentication handling

### 💬 WhatsApp
- Follower tracking
- Post engagement monitoring
- Video content analysis

## 🚀 Installation

### Prerequisites
- Python 3.7+
- MySQL Server
- Chrome Browser (for Instagram scraping)

### Setup Steps

1. **Clone the repository**
```bash
git clone https://github.com/Ujaaslohani/Social-Media-Scraping.git
cd Social-Media-Scraping
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
Create a `.env` file in the root directory:
```env
# Database Configuration
DB_HOST=localhost
DB_NAME=social_media_db
DB_USER=your_username
DB_PASSWORD=your_password

# API Keys
API_KEY=your_youtube_api_key

# Instagram Credentials (for automation)
INSTAGRAM_USERNAME=your_username
INSTAGRAM_PASSWORD=your_password

# Twitter Credentials
TWITTER_USERNAME=your_username
TWITTER_EMAIL=your_email
TWITTER_PASSWORD=your_password
```

5. **Create database**
```sql
CREATE DATABASE social_media_db;
```

## ⚙️ Configuration

### Database Setup
The project uses MySQL with the following tables:
- `daily_videos`: YouTube video data
- `instagram_posts`: Instagram post data
- `twitter_tweets`: Twitter tweet data
- `whatsapp_data`: WhatsApp engagement data

### Channel/Profile Configuration
Update the respective configuration files with your target channels/profiles:

**YouTube Channels** (in `youtube_id_finder.py`):
```python
CHANNELS = [
    {"id": "UC...", "name": "Channel Name"},
    # Add more channels...
]
```

**Instagram Profiles** (in `insta_main.py`):
```python
target_profiles = ["profile1", "profile2", "profile3"]
```

## 🎯 Usage

### YouTube Data Collection
```bash
python Youtube/youtube_id_finder.py
```

### Instagram Scraping
```bash
python Instagram/insta_main.py
```

### Twitter Data Collection
```bash
python Twitter/twitter_scraping.py
```

### WhatsApp Analysis
```bash
python Whatsapp/Followers/main_new.py
python Whatsapp/Posts/main_vid_new.py
```

## 📁 Project Structure

```
Social-Media-Scraping/
├── 📁 Youtube/
│   ├── youtube_id_finder.py          # YouTube channel video scraper
│   └── youtube video/
│       └── youtube_video_data.py     # Individual video data extraction
├── 📁 Instagram/
│   ├── insta_main.py                 # Main Instagram scraper
│   ├── insta_data.py                 # Data processing utilities
│   ├── insta_followers.py            # Follower tracking
│   └── insta_final.py                # Final data compilation
├── 📁 Twitter/
│   └── twitter_scraping.py           # Twitter tweet collector
├── 📁 Whatsapp/
│   ├── 📁 Followers/
│   │   └── main_new.py               # WhatsApp follower analysis
│   └── 📁 Posts/
│       └── main_vid_new.py           # WhatsApp post engagement
├── 📄 requirements.txt               # Python dependencies
├── 📄 .env.example                   # Environment variables template
├── 📄 README.md                      # This file
└── 📄 LICENSE                        # Project license
```

## 🔌 API Reference

### YouTube API v3
- **Endpoint**: `https://www.googleapis.com/youtube/v3/`
- **Methods**: `activities`, `videos`, `channels`
- **Rate Limit**: 10,000 units/day

### Instagram (Web Scraping)
- **Method**: Selenium WebDriver
- **Features**: Headless browsing, human-like interaction
- **Rate Limiting**: Built-in delays

### Twitter API
- **Library**: Twikit
- **Authentication**: Username/Email/Password
- **Features**: Tweet collection, user data

## 🗄️ Database Schema

### daily_videos (YouTube)
```sql
CREATE TABLE daily_videos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    channel_id VARCHAR(50),
    video_id VARCHAR(50) UNIQUE,
    published_at DATE,
    channel_name VARCHAR(100),
    datetime DATETIME
);
```

### instagram_posts
```sql
CREATE TABLE instagram_posts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    profile_name VARCHAR(100),
    post_url VARCHAR(500) UNIQUE,
    scraped_at DATETIME
);
```

## 🛠️ Development

### Adding New Platforms
1. Create a new directory for the platform
2. Implement scraping logic following existing patterns
3. Add configuration to `.env` file
4. Update requirements.txt if new dependencies needed

### Error Handling
All modules include comprehensive error handling:
- Network timeouts
- API rate limits
- Database connection issues
- Authentication failures

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This tool is for educational and research purposes only. Users are responsible for complying with each platform's Terms of Service and rate limits. The developers are not responsible for any misuse of this software.

## 📞 Support

For issues and questions:
- Open an [Issue](https://github.com/Ujaaslohani/Social-Media-Scraping/issues)
- Check existing [Discussions](https://github.com/Ujaaslohani/Social-Media-Scraping/discussions)

## 🔄 Changelog

### v1.0.0 (Current)
- Initial release with YouTube, Instagram, Twitter, and WhatsApp support
- MySQL database integration
- Excel export functionality
- Environment-based configuration
