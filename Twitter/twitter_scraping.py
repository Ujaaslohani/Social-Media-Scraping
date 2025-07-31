import asyncio
from twikit import Client

USERNAME = 'example_user'
EMAIL = 'email@example.com'
PASSWORD = 'password0000'

client = Client('en-US')

async def main():
    await client.login(
        auth_info_1=USERNAME,
        auth_info_2=EMAIL,
        password=PASSWORD,
        cookies_file='cookies.json'
    )

    screen_name = 'username'
    user = await client.get_user_by_screen_name(screen_name)
    user_id = user.id

    tweets = await client.get_user_tweets(user_id, 'Tweets', count=20)
    for tweet in tweets:
        print(f"\nTweet ID: {tweet.id}")
        print(f"Text: {tweet.full_text}")
        print(f"Likes: {tweet.favorite_count}")
        print(f"Retweets: {tweet.retweet_count}")
        print(f"Replies: {tweet.reply_count}")
        print(f"Quote Tweets: {tweet.quote_count}")
        print(f"Posted At: {tweet.created_at}")

asyncio.run(main())
