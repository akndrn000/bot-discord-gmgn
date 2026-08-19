import os
import json
import asyncio
import random
import discord
from discord.ext import commands
from datetime import datetime
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ==========================================
# ⚙️ KONFIGURASI VARIABEL UTAMA & KATA
# ==========================================

CONFIG_FILE = 'config.json'
TIMEZONE_STR = "Asia/Jakarta"
COMMAND_PREFIX = "!"

# Variasi GM (Bahasa Inggris) dengan Sistem Rarity (Bobot Kemunculan)
GM_VARIATIONS = [
    # Kata Sering Muncul (Common)
    "gm", "gm", "gm", "gm", "gm", "gm", "gm", "gm", "gm", "gm",
    "morning", "morning", "morning", "morning", "morning",
    # Kata Variasi Jarang (Rare)
    "gm guys",
    "gm everyone",
    "good morning!",
    "morning y'all",
    "gm gm",
    "gm chat",
    "rise and grind",
    "top of the morning"
]

# Variasi GN (Bahasa Inggris) dengan Sistem Rarity (Bobot Kemunculan)
GN_VARIATIONS = [
    # Kata Sering Muncul (Common)
    "gn", "gn", "gn", "gn", "gn", "gn", "gn", "gn", "gn", "gn",
    "night", "night", "night", "night", "night",
    # Kata Variasi Jarang (Rare)
    "gn guys",
    "gn everyone",
    "good night!",
    "sleep well",
    "gn chat",
    "gn y'all",
    "off to sleep",
    "sweet dreams"
]

TXT_BOT_ONLINE = "🟢 **SELFBOT GM/GN AUTOMATION AKTIF!**\nBerhasil login menggunakan akun:"

HELP_MENU_BOX = """
```text
=====================================================
        🤖 MENU BANTUAN SELFBOT GM / GN
=====================================================
!set <id1> <id2>   : Tambah target channel (1 / banyak)
!time gm:07.00, gn:19.00 : Atur jadwal kirim GM & GN
!monitor <id>      : Set channel pemantau log / bukti
!list              : Lihat konfigurasi & target aktif
!stop <id>         : Hapus 1 ID target dari daftar
=====================================================
```"""

# ==========================================
# 🛠️ LOGIK SISTEM & ENGINE SELFBOT
# ==========================================

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        "gm_time": "07:00",
        "gn_time": "19:00",
        "monitor_channel_id": None,
        "target_channels": []
    }

def save_config(config_data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=4)

config = load_config()

# Menggunakan self_bot=True khusus untuk token akun F12
bot = commands.Bot(command_prefix=COMMAND_PREFIX, self_bot=True)
scheduler = AsyncIOScheduler(timezone=pytz.timezone(TIMEZONE_STR))

async def log_to_monitor(content):
    """Mengirim log bukti pengiriman ke channel pemantau."""
    monitor_id = config.get("monitor_channel_id")
    if monitor_id:
        try:
            channel = bot.get_channel(int(monitor_id)) or await bot.fetch_channel(int(monitor_id))
            if channel:
                await channel.send(content)
        except Exception as e:
            print(f"[ERROR MONITOR] Gagal mengirim log: {e}")

async def send_daily_message(message_type):
    """Fungsi pengiriman pesan otomatis dengan sistem rarity variasi teks."""
    targets = config.get("target_channels", [])
    if not targets:
        await log_to_monitor(f"⚠️ **[{message_type}]** Jadwal terpicu, namun belum ada target channel yang diset.")
        return

    if message_type == "GM":
        text_to_send = random.choice(GM_VARIATIONS)
    else:
        text_to_send = random.choice(GN_VARIATIONS)

    timestamp = datetime.now(pytz.timezone(TIMEZONE_STR)).strftime("%Y-%m-%d %H:%M:%S")
    await log_to_monitor(f"🚀 **[{message_type}]** Mengirim teks: *\"{text_to_send}\"* pada `{timestamp}` ke {len(targets)} channel...")

    success_count = 0
    fail_count = 0

    for ch_id in targets:
        try:
            channel = bot.get_channel(int(ch_id)) or await bot.fetch_channel(int(ch_id))
            if channel:
                await channel.send(text_to_send)
                success_count += 1
                server_name = channel.guild.name if hasattr(channel, 'guild') else 'DM'
                await log_to_monitor(f"✅ **BUKTI TERKIRIM [{message_type}]** -> Server: `{server_name}` | Channel: `{channel.name}` (`{ch_id}`) | Teks: *\"{text_to_send}\"*")
                await asyncio.sleep(3)  # Delay 3 detik aman dari rate limit
        except Exception as e:
            fail_count += 1
            await log_to_monitor(f"❌ **GAGAL [{message_type}]** -> Channel ID `{ch_id}` | Error: `{e}`")

    await log_to_monitor(f"📊 **LAPORAN [{message_type}] SELESAI** | Berhasil: {success_count} | Gagal: {fail_count}")

def setup_scheduler():
    scheduler.remove_all_jobs()
    gm_h, gm_m = config["gm_time"].split(":")
    gn_h, gn_m = config["gn_time"].split(":")

    scheduler.add_job(send_daily_message, 'cron', hour=int(gm_h), minute=int(gm_m), args=["GM"])
    scheduler.add_job(send_daily_message, 'cron', hour=int(gn_h), minute=int(gn_m), args=["GN"])

@bot.event
async def on_ready():
    print(f"SELFBOT AKTIF sebagai {bot.user.name} ({bot.user.id})")
    setup_scheduler()
    if not scheduler.running:
        scheduler.start()
        
    status_msg = f"{TXT_BOT_ONLINE} `{bot.user.name}`\n{HELP_MENU_BOX}"
    await log_to_monitor(status_msg)

# ==========================================
# 📌 DAFTAR PERINTAH (COMMANDS)
# ==========================================

@bot.command()
async def set(ctx, *channel_ids: str):
    """Menambahkan 1 atau banyak ID channel target sekaligus."""
    if not channel_ids:
        await ctx.send("❌ Harap sertakan ID channel. Contoh: `!set 123456789 987654321`")
        return

    added = []
    already = []
    for cid in channel_ids:
        if cid.isdigit():
            if int(cid) not in config["target_channels"]:
                config["target_channels"].append(int(cid))
                added.append(cid)
            else:
                already.append(cid)

    save_config(config)
    res = f"✅ Berhasil menambahkan `{len(added)}` channel target."
    if already:
        res += f"\n⚠️ Channel sudah ada sebelumnya: `{', '.join(already)}`"
    
    await ctx.send(res)
    await log_to_monitor(f"📝 **[UPDATE TARGET]** Channel ditambahkan: `{', '.join(added)}` oleh `{ctx.author.name}`")

@bot.command()
async def monitor(ctx, channel_id: str):
    """Mengatur channel pemantau log bukti."""
    if not channel_id.isdigit():
        await ctx.send("❌ ID Channel harus berupa angka.")
        return

    config["monitor_channel_id"] = int(channel_id)
    save_config(config)
    await ctx.send(f"✅ Channel pemantau berhasil diatur ke ID: `{channel_id}`")
    
    status_msg = f"📢 **CHANNEL PEMANTAU DITETAPKAN**\n{HELP_MENU_BOX}"
    await log_to_monitor(status_msg)

@bot.command()
async def time(ctx, *, args: str):
    """Mengatur waktu GM dan GN. Format: !time gm:07.00, gn:19.00"""
    try:
        parts = args.split(',')
        gm_part = None
        gn_part = None

        for p in parts:
            p = p.strip().lower()
            if p.startswith("gm:"):
                gm_part = p.replace("gm:", "").strip().replace(".", ":")
            elif p.startswith("gn:"):
                gn_part = p.replace("gn:", "").strip().replace(".", ":")

        if gm_part and gn_part:
            config["gm_time"] = gm_part
            config["gn_time"] = gn_part
            save_config(config)
            setup_scheduler()
            await ctx.send(f"✅ Waktu berhasil diubah!\n☀️ **GM:** `{gm_part}` WIB\n🌙 **GN:** `{gn_part}` WIB")
            await log_to_monitor(f"⏰ **[UPDATE WAKTU]** GM diatur ke `{gm_part}`, GN diatur ke `{gn_part}`")
        else:
            await ctx.send("❌ Format salah! Gunakan: `!time gm:07.00, gn:19.00`")
    except Exception as e:
        await ctx.send(f"❌ Gagal memproses format waktu: {e}")

@bot.command()
async def list(ctx):
    """Menampilkan daftar konfigurasi dan target channel."""
    targets = config.get("target_channels", [])
    monitor_id = config.get("monitor_channel_id", "Belum di-set")
    
    msg = "**📋 PENGATURAN & TARGET CHANNEL AKTIF**\n"
    msg += f"• **Waktu GM:** `{config['gm_time']}` WIB\n"
    msg += f"• **Waktu GN:** `{config['gn_time']}` WIB\n"
    msg += f"• **Channel Pemantau:** `{monitor_id}`\n"
    msg += f"• **Total Target Channel:** `{len(targets)}`\n\n"
    
    if targets:
        msg += "**List Channel ID:**\n"
        for idx, cid in enumerate(targets, 1):
            msg += f"{idx}. `{cid}`\n"
    else:
        msg += "⚠️ *Belum ada channel target yang terdaftar.*"

    await ctx.send(msg)

@bot.command()
async def stop(ctx, channel_id: str):
    """Menghapus 1 ID channel target."""
    if not channel_id.isdigit():
        await ctx.send("❌ ID Channel harus berupa angka.")
        return

    cid = int(channel_id)
    if cid in config["target_channels"]:
        config["target_channels"].remove(cid)
        save_config(config)
        await ctx.send(f"✅ Channel ID `{channel_id}` berhasil dihapus dari target.")
        await log_to_monitor(f"🗑️ **[REMOVE TARGET]** ID Channel `{channel_id}` dihapus dari daftar.")
    else:
        await ctx.send(f"❌ ID Channel `{channel_id}` tidak ditemukan dalam daftar.")

if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        print("ERROR: Environment variable DISCORD_TOKEN belum diisi!")
    else:
        bot.run(TOKEN)
