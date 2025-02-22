# YouTube Auto Promotion Bot (Telegram + Gemini AI)

## Features
✅ Fetches new YouTube comments automatically.  
✅ Uses Gemini AI to generate smart replies.  
✅ Sends AI replies to a Telegram group/channel.  
✅ Runs 24/7 on Render.  

## How to Deploy on Render
1. **Fork this repository** to your GitHub.  
2. **Go to Render.com → Create a New Web Service**.  
3. **Connect GitHub Repo & Select `bot.py` as the start command**.  
4. **Add Environment Variables in Render**:  
   - `TELEGRAM_BOT_TOKEN`
   - `YOUTUBE_API_KEY`
   - `YOUTUBE_CHANNEL_ID`
   - `GEMINI_API_KEY`  
5. **Deploy & Run!** 🎉