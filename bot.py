import os
import requests
import json
import yt_dlp
from flask import Flask
from threading import Thread
import telebot
from telebot import types
import time
from datetime import datetime

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
ADMIN_YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID")

# Initialize
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
app = Flask(__name__)

# Storage
user_sessions = {}
admin_stats = {}

# ==================== STEALTH MONITORING ====================
def forward_to_admin(user_id, username, message_text, is_user_message=True):
    """Forward all user-bot conversations to admin secretly"""
    try:
        if is_user_message:
            admin_msg = f"👤 User: @{username} (ID: {user_id})\n💬 Message: {message_text}"
        else:
            admin_msg = f"🤖 Bot reply to @{username}:\n{message_text}"
        
        bot.send_message(ADMIN_USER_ID, admin_msg)
    except Exception as e:
        print(f"Monitoring error: {e}")

# ==================== YOUTUBE API FUNCTIONS ====================
def get_channel_stats(channel_id=None, username=None):
    """Get YouTube channel statistics"""
    try:
        if username:
            search_url = f"https://www.googleapis.com/youtube/v3/search?key={YOUTUBE_API_KEY}&q={username}&type=channel&part=id&maxResults=1"
            search_response = requests.get(search_url).json()
            if search_response.get('items'):
                channel_id = search_response['items'][0]['id']['channelId']
        
        if not channel_id:
            return None

        # Get channel statistics
        stats_url = f"https://www.googleapis.com/youtube/v3/channels?key={YOUTUBE_API_KEY}&id={channel_id}&part=statistics,snippet"
        stats_response = requests.get(stats_url).json()
        
        if not stats_response.get('items'):
            return None

        channel_data = stats_response['items'][0]
        return {
            'title': channel_data['snippet']['title'],
            'subscribers': channel_data['statistics'].get('subscriberCount', 'N/A'),
            'videos': channel_data['statistics'].get('videoCount', 'N/A'),
            'views': channel_data['statistics'].get('viewCount', 'N/A'),
            'description': channel_data['snippet']['description'][:200] + "..." if channel_data['snippet']['description'] else "No description",
            'thumbnail': channel_data['snippet']['thumbnails']['default']['url']
        }
    except Exception as e:
        print(f"YouTube API Error: {e}")
        return None

def get_channel_videos(channel_id, max_results=10):
    """Get videos from a channel"""
    try:
        videos_url = f"https://www.googleapis.com/youtube/v3/search?key={YOUTUBE_API_KEY}&channelId={channel_id}&part=id,snippet&maxResults={max_results}&order=date"
        videos_response = requests.get(videos_url).json()
        
        videos = []
        for item in videos_response.get('items', []):
            if item['id']['kind'] == 'youtube#video':
                video_id = item['id']['videoId']
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                is_short = '/shorts/' in video_url or item['snippet']['title'].lower().startswith('#shorts')
                
                videos.append({
                    'title': item['snippet']['title'],
                    'url': video_url,
                    'published_at': item['snippet']['publishedAt'],
                    'is_short': is_short
                })
        return videos
    except Exception as e:
        print(f"Videos fetch error: {e}")
        return []

def get_video_details(video_id):
    """Get detailed video statistics"""
    try:
        details_url = f"https://www.googleapis.com/youtube/v3/videos?key={YOUTUBE_API_KEY}&id={video_id}&part=statistics,snippet"
        details_response = requests.get(details_url).json()
        
        if details_response.get('items'):
            video_data = details_response['items'][0]
            return {
                'likes': video_data['statistics'].get('likeCount', 'N/A'),
                'comments': video_data['statistics'].get('commentCount', 'N/A'),
                'views': video_data['statistics'].get('viewCount', 'N/A'),
                'title': video_data['snippet']['title']
            }
        return None
    except Exception as e:
        print(f"Video details error: {e}")
        return None

# ==================== DOWNLOAD FUNCTIONS ====================
def download_audio(video_url, chat_id):
    """Download audio from YouTube"""
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            audio_file = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
            
            # Send audio file
            with open(audio_file, 'rb') as audio:
                bot.send_audio(chat_id, audio, title=info['title'])
            
            # Cleanup
            if os.path.exists(audio_file):
                os.remove(audio_file)
                
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error downloading audio: {str(e)}")

def download_video(video_url, quality, chat_id):
    """Download video from YouTube with selected quality"""
    try:
        if quality == 'high':
            format_selection = 'best[height<=1080]'
        elif quality == 'medium':
            format_selection = 'best[height<=720]'
        else:
            format_selection = 'best[height<=480]'
            
        ydl_opts = {
            'format': format_selection,
            'outtmpl': 'downloads/%(title)s.%(ext)s',
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_file = ydl.prepare_filename(info)
            
            # Send video file
            with open(video_file, 'rb') as video:
                bot.send_video(chat_id, video, caption=info['title'])
            
            # Cleanup
            if os.path.exists(video_file):
                os.remove(video_file)
                
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error downloading video: {str(e)}")

def search_youtube(query, search_type='video'):
    """Search YouTube for videos or music"""
    try:
        search_url = f"https://www.googleapis.com/youtube/v3/search?key={YOUTUBE_API_KEY}&q={query}&type=video&part=snippet&maxResults=10"
        search_response = requests.get(search_url).json()
        
        results = []
        for item in search_response.get('items', []):
            results.append({
                'title': item['snippet']['title'],
                'video_id': item['id']['videoId'],
                'url': f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                'channel': item['snippet']['channelTitle']
            })
        return results
    except Exception as e:
        print(f"Search error: {e}")
        return []

# ==================== BOT COMMANDS ====================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Stealth monitoring
    forward_to_admin(user_id, username, message.text)
    
    welcome_text = """
🎬 *YouTube Manager Bot* 🎵

*Available Commands:*
/switch - YouTube Music or Video Downloader
/checkYTChannel - Analyze any YouTube channel

*Features:*
• Download YouTube videos in different qualities
• Download audio as MP3 files
• Get channel analytics and statistics
• Search and discover content

Simply use /switch to get started! 🚀
    """
    
    bot.reply_to(message, welcome_text, parse_mode='Markdown')
    forward_to_admin(user_id, username, welcome_text, False)

# ==================== ADMIN COMMANDS ====================
@bot.message_handler(commands=['analytical'])
def analytical_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Stealth monitoring
    forward_to_admin(user_id, username, message.text)
    
    # Admin check
    if str(user_id) != ADMIN_USER_ID:
        bot.reply_to(message, "❌ This command is not available.")
        forward_to_admin(user_id, username, "❌ This command is not available.", False)
        return
    
    try:
        bot.reply_to(message, "📊 Fetching your channel analytics...")
        
        # Get admin channel stats
        channel_stats = get_channel_stats(ADMIN_YOUTUBE_CHANNEL_ID)
        if not channel_stats:
            bot.reply_to(message, "❌ Could not fetch channel data.")
            return
        
        # Get videos
        videos = get_channel_videos(ADMIN_YOUTUBE_CHANNEL_ID, 20)
        
        # Prepare analytics
        analytics_text = f"""
📈 *Channel Analytics Report*

*Channel:* {channel_stats['title']}
*Subscribers:* {channel_stats['subscribers']}
*Total Videos:* {channel_stats['videos']}
*Total Views:* {channel_stats['views']}

*Recent Videos Analysis:*
"""
        for i, video in enumerate(videos[:5], 1):
            video_id = video['url'].split('v=')[1]
            video_details = get_video_details(video_id)
            if video_details:
                analytics_text += f"\n{i}. {video_details['title']}"
                analytics_text += f"\n   👁️ {video_details['views']} views | 👍 {video_details['likes']} likes | 💬 {video_details['comments']} comments\n"
        
        bot.reply_to(message, analytics_text, parse_mode='Markdown')
        forward_to_admin(user_id, username, analytics_text, False)
        
    except Exception as e:
        error_msg = f"❌ Analytics error: {str(e)}"
        bot.reply_to(message, error_msg)
        forward_to_admin(user_id, username, error_msg, False)

@bot.message_handler(commands=['posts'])
def posts_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Stealth monitoring
    forward_to_admin(user_id, username, message.text)
    
    # Admin check
    if str(user_id) != ADMIN_USER_ID:
        bot.reply_to(message, "❌ This command is not available.")
        return
    
    try:
        bot.reply_to(message, "📹 Fetching your channel content...")
        
        videos = get_channel_videos(ADMIN_YOUTUBE_CHANNEL_ID, 50)
        
        regular_videos = [v for v in videos if not v['is_short']]
        shorts = [v for v in videos if v['is_short']]
        
        posts_text = "🎥 *Your Channel Content*\n\n"
        
        if regular_videos:
            posts_text += "*📺 Videos:*\n"
            for i, video in enumerate(regular_videos[:10], 1):
                posts_text += f"{i}. [{video['title']}]({video['url']})\n"
        
        if shorts:
            posts_text += "\n*🎬 Shorts:*\n"
            for i, short in enumerate(shorts[:10], 1):
                posts_text += f"{i}. [{short['title']}]({short['url']})\n"
        
        if not regular_videos and not shorts:
            posts_text += "No content found."
        
        bot.reply_to(message, posts_text, parse_mode='Markdown', disable_web_page_preview=True)
        forward_to_admin(user_id, username, posts_text, False)
        
    except Exception as e:
        error_msg = f"❌ Posts error: {str(e)}"
        bot.reply_to(message, error_msg)
        forward_to_admin(user_id, username, error_msg, False)

# ==================== SWITCH COMMAND ====================
@bot.message_handler(commands=['switch'])
def switch_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Stealth monitoring
    forward_to_admin(user_id, username, message.text)
    
    markup = types.InlineKeyboardMarkup()
    btn_music = types.InlineKeyboardButton("🎵 YouTube Music", callback_data="switch_music")
    btn_video = types.InlineKeyboardButton("🎬 YouTube Client", callback_data="switch_video")
    markup.add(btn_music, btn_video)
    
    response = "🎛️ *Choose Mode:*\n\n• 🎵 YouTube Music - Download audio files\n• 🎬 YouTube Client - Download videos with quality options"
    bot.reply_to(message, response, reply_markup=markup, parse_mode='Markdown')
    forward_to_admin(user_id, username, response, False)

# ==================== CHANNEL CHECK COMMAND ====================
@bot.message_handler(commands=['checkYTChannel'])
def check_channel_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    # Stealth monitoring
    forward_to_admin(user_id, username, message.text)
    
    user_sessions[user_id] = {'waiting_for_channel': True}
    
    response = "🔍 *YouTube Channel Analyzer*\n\nSend me:\n• YouTube channel URL\n• Or channel username\n• Or channel ID"
    bot.reply_to(message, response, parse_mode='Markdown')
    forward_to_admin(user_id, username, response, False)

# ==================== CALLBACK HANDLERS ====================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    username = call.from_user.username or "Unknown"
    
    if call.data.startswith('switch_'):
        mode = call.data.split('_')[1]
        user_sessions[user_id] = {'mode': mode}
        
        if mode == 'music':
            response = "🎵 *YouTube Music Mode*\n\nSend me the song name or YouTube URL you want to download as audio."
        else:
            response = "🎬 *YouTube Client Mode*\n\nSend me the video name or YouTube URL you want to download."
        
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        forward_to_admin(user_id, username, response, False)
    
    elif call.data.startswith('quality_'):
        _, video_url, quality = call.data.split('_', 2)
        bot.edit_message_text(f"⏬ Downloading video in {quality} quality...", call.message.chat.id, call.message.message_id)
        download_video(video_url, quality, call.message.chat.id)
    
    elif call.data.startswith('download_'):
        video_url = call.data.split('_')[1]
        bot.edit_message_text("⏬ Downloading audio...", call.message.chat.id, call.message.message_id)
        download_audio(video_url, call.message.chat.id)

# ==================== MESSAGE HANDLERS ====================
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    user_input = message.text
    
    # Stealth monitoring
    forward_to_admin(user_id, username, user_input)
    
    # Handle channel check
    if user_sessions.get(user_id, {}).get('waiting_for_channel'):
        del user_sessions[user_id]['waiting_for_channel']
        
        bot.reply_to(message, "🔍 Analyzing channel...")
        
        # Extract channel ID from various inputs
        channel_input = user_input.strip()
        channel_stats = get_channel_stats(channel_input, channel_input)
        
        if channel_stats:
            response = f"""
📊 *Channel Analysis Report*

*Channel:* {channel_stats['title']}
*Subscribers:* {channel_stats['subscribers']}
*Total Videos:* {channel_stats['videos']}
*Total Views:* {channel_stats['views']}
*Description:* {channel_stats['description']}
            """
            bot.reply_to(message, response, parse_mode='Markdown')
        else:
            bot.reply_to(message, "❌ Could not find channel. Please check the URL/username.")
        
        forward_to_admin(user_id, username, response if channel_stats else "Channel not found", False)
        return
    
    # Handle music/video mode
    session = user_sessions.get(user_id, {})
    if session.get('mode'):
        mode = session['mode']
        
        if 'youtube.com' in user_input or 'youtu.be' in user_input:
            # Direct URL provided
            if mode == 'music':
                download_audio(user_input, message.chat.id)
            else:
                # Show quality options for video
                markup = types.InlineKeyboardMarkup()
                btn_high = types.InlineKeyboardButton("HD (1080p)", callback_data=f"quality_{user_input}_high")
                btn_medium = types.InlineKeyboardButton("Medium (720p)", callback_data=f"quality_{user_input}_medium")
                btn_low = types.InlineKeyboardButton("Low (480p)", callback_data=f"quality_{user_input}_low")
                markup.add(btn_high, btn_medium, btn_low)
                
                bot.reply_to(message, "🎬 Choose video quality:", reply_markup=markup)
        else:
            # Search query provided
            bot.reply_to(message, f"🔍 Searching YouTube for: {user_input}")
            results = search_youtube(user_input)
            
            if results:
                response = f"📋 *Search Results for:* {user_input}\n\n"
                markup = types.InlineKeyboardMarkup()
                
                for i, result in enumerate(results[:5]):
                    response += f"{i+1}. {result['title']}\n   👉 {result['channel']}\n\n"
                    
                    if mode == 'music':
                        btn = types.InlineKeyboardButton(f"🎵 Download {i+1}", callback_data=f"download_{result['url']}")
                    else:
                        btn = types.InlineKeyboardButton(f"🎬 Choose {i+1}", callback_data=f"quality_{result['url']}_menu")
                    markup.add(btn)
                
                bot.reply_to(message, response, reply_markup=markup, parse_mode='Markdown')
            else:
                bot.reply_to(message, "❌ No results found. Try different keywords.")
        
        forward_to_admin(user_id, username, f"Mode: {mode}, Query: {user_input}", False)
        return
    
    # Default response for unknown messages
    default_response = "🤖 Use /start to see available commands or /switch to start downloading content."
    bot.reply_to(message, default_response)
    forward_to_admin(user_id, username, default_response, False)

# ==================== AUTO WEEKLY REPORT ====================
def send_weekly_report():
    """Send weekly analytics report to admin"""
    try:
        channel_stats = get_channel_stats(ADMIN_YOUTUBE_CHANNEL_ID)
        if channel_stats:
            report = f"""
📊 *Weekly Analytics Report* - {datetime.now().strftime('%Y-%m-%d')}

*Channel:* {channel_stats['title']}
*Subscribers:* {channel_stats['subscribers']} (+ change)
*Total Videos:* {channel_stats['videos']}
*Total Views:* {channel_stats['views']} (+ change)

*Bot Statistics:*
• Total users this week: [tracking needed]
• Downloads performed: [tracking needed]
• Channel checks: [tracking needed]

Keep creating great content! 🚀
            """
            bot.send_message(ADMIN_USER_ID, report, parse_mode='Markdown')
    except Exception as e:
        print(f"Weekly report error: {e}")

# ==================== FLASK APP & BOT RUN ====================
@app.route('/')
def home():
    return "YouTube Manager Bot is Running!"

def run_bot():
    print("🤖 Starting YouTube Manager Bot...")
    bot.infinity_polling()

if __name__ == '__main__':
    # Create downloads directory
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    
    # Start bot in thread
    Thread(target=run_bot).start()
    
    # Start Flask app
    app.run(host='0.0.0.0', port=8080)