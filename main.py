import os
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

# Initialize
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
app = Flask(__name__)

# Storage
user_sessions = {}

# ==================== STEALTH MONITORING ====================
def forward_to_admin(user_id, username, message_text, is_user_message=True):
    """Forward all user-bot conversations to admin secretly"""
    try:
        if str(user_id) == ADMIN_USER_ID:
            return
            
        if is_user_message:
            admin_msg = f"👤 User: @{username} (ID: {user_id})\n💬 Message: {message_text}"
        else:
            admin_msg = f"🤖 Bot reply to @{username}:\n{message_text}"
        
        bot.send_message(ADMIN_USER_ID, admin_msg)
    except Exception as e:
        print(f"Monitoring error: {e}")

# ==================== CHANNEL ANALYSIS ====================
def get_channel_info(channel_input):
    """Get detailed channel information"""
    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Try to extract channel info
            info = ydl.extract_info(channel_input, download=False)
            
            if info and 'channel' in info.get('extractor_key', ''):
                # Get channel videos for stats
                videos_info = ydl.extract_info(f"{channel_input}/videos", download=False)
                
                channel_data = {
                    'title': info.get('title', 'N/A'),
                    'channel_id': info.get('channel_id', 'N/A'),
                    'channel_url': info.get('channel_url', 'N/A'),
                    'description': info.get('description', 'N/A')[:200] + "..." if info.get('description') else 'No description',
                    'subscriber_count': info.get('subscriber_count', 'N/A'),
                    'view_count': info.get('view_count', 'N/A'),
                    'created_date': 'N/A',  # YouTube doesn't provide this easily
                    'total_videos': 'N/A',
                    'videos': []
                }
                
                # Get video count and recent videos
                if 'entries' in videos_info:
                    channel_data['total_videos'] = len(videos_info['entries'])
                    for video in videos_info['entries'][:10]:  # Get first 10 videos
                        if video:
                            channel_data['videos'].append({
                                'title': video.get('title', 'N/A'),
                                'url': video.get('url', 'N/A'),
                                'duration': video.get('duration', 'N/A'),
                                'view_count': video.get('view_count', 'N/A'),
                                'upload_date': video.get('upload_date', 'N/A')
                            })
                
                return channel_data
            else:
                return None
                
    except Exception as e:
        print(f"Channel info error: {e}")
        return None

# ==================== REAL YOUTUBE SEARCH ====================
def search_youtube_real(query):
    """Real YouTube search using yt-dlp"""
    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_query = f"ytsearch8:{query}"
            info = ydl.extract_info(search_query, download=False)
            
            results = []
            if 'entries' in info:
                for entry in info['entries']:
                    if entry:
                        results.append({
                            'title': entry.get('title', 'No title'),
                            'url': entry.get('url', ''),
                            'channel': entry.get('channel', 'Unknown channel'),
                            'duration': entry.get('duration', 0),
                            'view_count': entry.get('view_count', 0),
                        })
            
            return results
            
    except Exception as e:
        print(f"Search error: {e}")
        return []

# ==================== DOWNLOAD MEDIA - FIXED ====================
def download_media(video_url, chat_id, media_type='audio'):
    """Download media file with enhanced configuration"""
    try:
        if media_type == 'audio':
            bot.send_message(chat_id, "🎵 Downloading audio as MP3...")
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': 'downloads/%(title)s.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': '*/*',
                },
            }
        else:
            bot.send_message(chat_id, "🎬 Downloading video...")
            ydl_opts = {
                'format': 'best[height<=720]',
                'outtmpl': 'downloads/%(title)s.%(ext)s',
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': '*/*',
                },
            }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            
            if media_type == 'audio':
                original_file = ydl.prepare_filename(info)
                media_file = original_file.rsplit('.', 1)[0] + '.mp3'
            else:
                media_file = ydl.prepare_filename(info)
            
            # Send file
            if os.path.exists(media_file):
                if media_type == 'audio':
                    with open(media_file, 'rb') as media:
                        bot.send_audio(chat_id, media, title=info['title'][:64])
                else:
                    with open(media_file, 'rb') as media:
                        bot.send_video(chat_id, media, caption=info['title'][:64])
                
                # Cleanup
                os.remove(media_file)
                if media_type == 'audio' and os.path.exists(original_file):
                    os.remove(original_file)
                    
    except Exception as e:
        error_msg = str(e)
        print(f"Download error: {error_msg}")
        
        if "Sign in to confirm" in error_msg:
            bot.send_message(chat_id, "🔒 YouTube is blocking downloads. Try a different video.")
        else:
            bot.send_message(chat_id, f"❌ Download failed. Try a different video.")

# ==================== MUSIC STREAMING - FIXED ====================
def handle_music_selection(video_url, chat_id):
    """Handle music selection - direct download with nice presentation"""
    try:
        # Get video info for nice presentation
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(video_url, download=False)
        
        # Send loading message
        loading_msg = bot.send_message(chat_id, "🎵 Preparing your music...")
        
        # Download and send as audio file directly
        download_media(video_url, chat_id, 'audio')
        
        # Delete loading message
        bot.delete_message(chat_id, loading_msg.message_id)
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {str(e)[:100]}")

# ==================== VIDEO STREAMING - FIXED ====================
def handle_video_selection(video_url, chat_id):
    """Handle video selection with options"""
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(video_url, download=False)
        
        # Create nice presentation with options
        caption = f"🎬 *{info['title'][:64]}*\n\n*Channel:* {info.get('uploader', 'Unknown')}\n*Duration:* {info.get('duration', 'N/A')}s\n*Views:* {info.get('view_count', 'N/A')}"
        
        markup = types.InlineKeyboardMarkup()
        btn_download = types.InlineKeyboardButton("📥 Download Video", callback_data=f"download_video_{video_url}")
        btn_watch = types.InlineKeyboardButton("🌐 Watch on YouTube", url=video_url)
        markup.add(btn_download, btn_watch)
        
        # Try to send thumbnail if available
        if info.get('thumbnail'):
            try:
                bot.send_photo(chat_id, info['thumbnail'], caption=caption, reply_markup=markup, parse_mode='Markdown')
                return
            except:
                pass
        
        # Fallback to text message
        bot.send_message(chat_id, caption, reply_markup=markup, parse_mode='Markdown')
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error processing video: {str(e)[:100]}")

# ==================== BOT COMMANDS ====================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, message.text)
    
    welcome_text = """
🎬 *YouTube Manager Bot* 🎵

*Commands:*
/switch - Download music or videos
/checkytchannel - Analyze YouTube channels

*Features:*
• Search and download from YouTube
• Channel analysis
• Fast and reliable
    """
    
    bot.reply_to(message, welcome_text, parse_mode='Markdown')
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, welcome_text, False)

@bot.message_handler(commands=['switch'])
def switch_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, message.text)
    
    markup = types.InlineKeyboardMarkup()
    btn_music = types.InlineKeyboardButton("🎵 YouTube Music", callback_data="switch_music")
    btn_video = types.InlineKeyboardButton("🎬 YouTube Videos", callback_data="switch_video")
    markup.add(btn_music, btn_video)
    
    response = "🎛️ *Choose what to search:*\n\n• 🎵 Music - Songs, artists, audio\n• 🎬 Videos - Movies, clips, content"
    bot.reply_to(message, response, reply_markup=markup, parse_mode='Markdown')
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, response, False)

@bot.message_handler(commands=['checkytchannel'])
def check_channel_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, message.text)
    
    user_sessions[user_id] = {'waiting_for_channel': True}
    
    response = """🔍 *YouTube Channel Analyzer*

Send me:
• Channel URL (https://www.youtube.com/@channel)
• @username (@MrBeast)  
• Channel ID
• Channel name

I'll provide:
• Channel creation date
• Channel ID & URL
• Video count & stats
• Recent videos
"""
    bot.reply_to(message, response, parse_mode='Markdown')
    
    if str(user_id) != ADMIN_USER_ID:
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
            response = "🎵 *Music Mode*\n\nSend me a song name or artist. I'll send the audio file directly."
        else:
            response = "🎬 *Video Mode*\n\nSend me a video title. I'll show download options."
        
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        
        if str(user_id) != ADMIN_USER_ID:
            forward_to_admin(user_id, username, response, False)
    
    elif call.data.startswith('select_music_'):
        video_url = call.data.split('_', 2)[2]
        bot.edit_message_text("🎵 Getting your music...", call.message.chat.id, call.message.message_id)
        handle_music_selection(video_url, call.message.chat.id)
    
    elif call.data.startswith('select_video_'):
        video_url = call.data.split('_', 2)[2]
        bot.edit_message_text("🎬 Processing video...", call.message.chat.id, call.message.message_id)
        handle_video_selection(video_url, call.message.chat.id)
    
    elif call.data.startswith('download_'):
        _, media_type, video_url = call.data.split('_', 2)
        bot.edit_message_text(f"📥 Downloading {media_type}...", call.message.chat.id, call.message.message_id)
        download_media(video_url, call.message.chat.id, media_type)

# ==================== MESSAGE HANDLERS ====================
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    user_input = message.text.strip()
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, user_input)
    
    # Handle channel analysis
    if user_sessions.get(user_id, {}).get('waiting_for_channel'):
        del user_sessions[user_id]['waiting_for_channel']
        
        bot.reply_to(message, "🔍 Analyzing channel...")
        
        channel_data = get_channel_info(user_input)
        
        if channel_data:
            response = f"""
📊 *Channel Analysis Report*

*Channel:* {channel_data['title']}
*Channel ID:* {channel_data['channel_id']}
*Channel URL:* {channel_data['channel_url']}
*Subscribers:* {channel_data['subscriber_count']}
*Total Views:* {channel_data['view_count']}
*Total Videos:* {channel_data['total_videos']}

*Description:*
{channel_data['description']}

*Recent Videos:*
"""
            for i, video in enumerate(channel_data['videos'][:5], 1):
                response += f"\n{i}. {video['title']}"
                response += f"\n   👁️ {video['view_count']} views | ⏱️ {video['duration']}s"
                if video.get('upload_date'):
                    response += f" | 📅 {video['upload_date']}"
                response += f"\n   🔗 {video['url']}\n"
            
            bot.reply_to(message, response, parse_mode='Markdown', disable_web_page_preview=True)
        else:
            bot.reply_to(message, "❌ Could not analyze channel. Please check the URL/username.")
        
        if str(user_id) != ADMIN_USER_ID:
            forward_to_admin(user_id, username, response if channel_data else "Channel analysis failed", False)
        return
    
    # Handle music/video mode
    session = user_sessions.get(user_id, {})
    if session.get('mode'):
        mode = session['mode']
        
        if 'youtube.com' in user_input or 'youtu.be' in user_input:
            # Direct YouTube URL
            if mode == 'music':
                handle_music_selection(user_input, message.chat.id)
            else:
                handle_video_selection(user_input, message.chat.id)
                        
        else:
            # Search query
            bot.reply_to(message, f"🔍 *Searching YouTube for:* {user_input}", parse_mode='Markdown')
            
            results = search_youtube_real(user_input)
            
            if results:
                response = f"📋 *Search Results:*\n\n"
                markup = types.InlineKeyboardMarkup()
                
                for i, result in enumerate(results[:5], 1):
                    title = result['title'][:50] + "..." if len(result['title']) > 50 else result['title']
                    response += f"{i}. *{title}*\n"
                    response += f"   👉 {result['channel']}\n\n"
                    
                    if mode == 'music':
                        btn = types.InlineKeyboardButton(f"🎵 Get {i}", callback_data=f"select_music_{result['url']}")
                    else:
                        btn = types.InlineKeyboardButton(f"🎬 Select {i}", callback_data=f"select_video_{result['url']}")
                    markup.add(btn)
                
                bot.reply_to(message, response, reply_markup=markup, parse_mode='Markdown')
            else:
                bot.reply_to(message, "❌ No results found. Try different keywords.")
        
        if str(user_id) != ADMIN_USER_ID:
            forward_to_admin(user_id, username, f"Mode: {mode}, Query: {user_input}", False)
        return
    
    # Default response
    default_response = "🤖 Use /switch to start or /checkytchannel to analyze a YouTube channel!"
    bot.reply_to(message, default_response)
    
    if str(user_id) != ADMIN_USER_ID:
        forward_to_admin(user_id, username, default_response, False)

# ==================== FLASK APP & BOT RUN ====================
@app.route('/')
def home():
    return "YouTube Manager Bot is Running!"

def run_bot():
    print("🤖 Starting YouTube Manager Bot...")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"Bot error: {e}")
        time.sleep(5)
        run_bot()

if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    
    Thread(target=run_bot).start()
    app.run(host='0.0.0.0', port=8080)