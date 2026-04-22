import requests
import time
import json
import os
from flask import Flask, jsonify
from threading import Thread
import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime

# ======================= KONFİGÜRASYON =======================
SEEDLOAF_EMAIL = "yigittr1922@gmail.com"  # SeedLoaf emailin
SEEDLOAF_PASSWORD = "201421yt"             # SeedLoaf şifren
SERVER_ID = "dbacbfe3-fdae-4c96-aab0-39a7f8610e80"  # Sunucu ID'n

DISCORD_BOT_TOKEN = ""      # Discord Bot Token
DISCORD_CHANNEL_ID = 1469371305017999421       # Bildirim gönderilecek kanal ID

# ======================= GLOBAL DEĞİŞKENLER =======================
session = requests.Session()
auth_token = None
server_status = "Bilinmiyor"
bot_start_time = datetime.now()

# ======================= FLASK WEB SUNUCU =======================
app = Flask(__name__)

@app.route('/')
def home():
    uptime = datetime.now() - bot_start_time
    return f"""
    <html>
    <head><title>MineBot</title></head>
    <body>
    <h1>✅ Bot Çalışıyor!</h1>
    <p>Sunucu: {SERVER_ID[:20]}...</p>
    <p>Durum: {server_status}</p>
    <p>Çalışma Süresi: {str(uptime).split('.')[0]}</p>
    <p>Son Kontrol: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </body>
    </html>
    """

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# ======================= SEEDLOAF API =======================
def seedloaf_login():
    """SeedLoaf'a email/şifre ile giriş yap"""
    global auth_token, session
    
    print(f"[{datetime.now()}] SeedLoaf'a giriş yapılıyor...")
    
    # Clerk auth endpoint'leri
    login_url = "https://api.clerk.com/v1/client/sign_ins"
    
    # Önce Clerk token al
    clerk_data = {
        "identifier": SEEDLOAF_EMAIL,
        "password": SEEDLOAF_PASSWORD,
        "strategy": "password"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
        "Origin": "https://seedloaf.com",
        "Referer": "https://seedloaf.com/"
    }
    
    try:
        # SeedLoaf'ın kendi auth endpoint'ini dene
        response = session.post(
            "https://seedloaf.com/api/auth/sign-in",
            json=clerk_data,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            auth_token = data.get('token') or data.get('session_token')
            print(f"✅ Giriş başarılı! Token alındı.")
            return True
            
    except Exception as e:
        print(f"Giriş denemesi başarısız: {e}")
    
    # Alternatif: Direkt token varsa kullan
    return False

def get_server_status():
    """Sunucu durumunu kontrol et"""
    global server_status
    
    if not auth_token:
        seedloaf_login()
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = session.get(
            f"https://seedloaf.com/api/server/{SERVER_ID}/status",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            server_status = data.get('status', 'unknown')
            return server_status
        elif response.status_code == 401:
            # Token süresi dolmuş, tekrar giriş yap
            seedloaf_login()
            return get_server_status()
            
    except Exception as e:
        print(f"Durum kontrol hatası: {e}")
    
    return "error"

def start_server():
    """Sunucuyu başlat"""
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = session.post(
            f"https://seedloaf.com/api/server/{SERVER_ID}/start",
            headers=headers
        )
        return response.status_code == 200
    except:
        return False

# ======================= DİSCORD BOT =======================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Discord bot {bot.user} olarak giriş yaptı!')
    check_server_loop.start()
    await send_discord_message("🟢 **Bot Başlatıldı!** Sunucu takibi başladı.")

@tasks.loop(minutes=1)  # Her dakika kontrol et
async def check_server_loop():
    """Her dakika sunucuyu kontrol et ve kapandıysa başlat"""
    global server_status
    
    status = get_server_status()
    print(f"[{datetime.now()}] Sunucu durumu: {status}")
    
    if status == "offline" or status == "stopped":
        await send_discord_message("🟡 **Sunucu Kapalı!** Başlatılıyor...")
        print("Sunucu başlatılıyor...")
        
        if start_server():
            await send_discord_message("✅ **Sunucu Başlatıldı!** 1-2 dakika içinde açılacaktır.")
        else:
            await send_discord_message("❌ **Sunucu Başlatılamadı!** Lütfen manuel kontrol edin.")
            
    elif status == "online" or status == "running":
        pass  # Her şey normal
        
    elif status == "error":
        await send_discord_message("⚠️ **API Hatası!** Token yenileniyor...")
        seedloaf_login()

@check_server_loop.before_loop
async def before_check():
    await bot.wait_until_ready()

async def send_discord_message(message):
    """Discord kanalına mesaj gönder"""
    try:
        channel = bot.get_channel(DISCORD_CHANNEL_ID)
        if channel:
            await channel.send(message)
    except Exception as e:
        print(f"Discord mesaj hatası: {e}")

# Discord komutları
@bot.command()
async def durum(ctx):
    """Sunucu durumunu göster"""
    status = get_server_status()
    status_text = {
        "online": "🟢 Çalışıyor",
        "offline": "🔴 Kapalı",
        "running": "🟢 Çalışıyor",
        "stopped": "🔴 Kapalı",
        "error": "⚠️ Hata"
    }
    await ctx.send(f"**Sunucu Durumu:** {status_text.get(status, '❓ Bilinmiyor')}")

@bot.command()
async def baslat(ctx):
    """Sunucuyu başlat"""
    await ctx.send("🔄 Sunucu başlatılıyor...")
    if start_server():
        await ctx.send("✅ Sunucu başlatma komutu gönderildi!")
    else:
        await ctx.send("❌ Başlatılamadı!")

@bot.command()
async def yardim(ctx):
    """Yardım menüsü"""
    help_text = """
    **🤖 Bot Komutları**
    `!durum` - Sunucu durumunu göster
    `!baslat` - Sunucuyu başlat
    `!yardim` - Bu menüyü göster
    
    **Özellikler**
    - Her dakika otomatik kontrol
    - Sunucu kapanınca otomatik başlatma
    - Discord üzerinden bildirim
    """
    await ctx.send(help_text)

# ======================= ANA ÇALIŞTIRICI =======================
def run_bot():
    """Discord bot'u başlat"""
    bot.run(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════╗
    ║     🚀 SEEDLOAF OTOMATİK BAŞLATICI    ║
    ║     Discord + Web + Auto-Restart     ║
    ╚══════════════════════════════════════╝
    """)
    
    # Önce giriş yap
    seedloaf_login()
    
    # Flask'ı ayrı thread'de başlat
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Discord bot'u başlat
    run_bot()
