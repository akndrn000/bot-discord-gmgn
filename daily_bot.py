import os
import discord
import asyncio
import json
import datetime
from datetime import datetime, timedelta
from discord.ext import commands, tasks

# === KONFIGURASI ===
# Mengambil token dari Environment Variables (Wajib di Railway)
TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
TIMEZONE_OFFSET = 7  # WIB (UTC+7)
DB_FILE = "/app/data/daily_list.json" # Path spesifik agar bisa dimount volume (opsional)

# Jika tidak pakai Volume, fallback ke file lokal biasa
if not os.path.exists("/app/data"):
    DB_FILE = "daily_list.json"

# === SETUP BOT ===
intents = discord.Intents.default()
intents.message_content = True  # WAJIB DI-ON-KAN DI DISCORD DEVELOPER PORTAL
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# === DATA MANAGER ===
def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_data(data):
    # Pastikan data tersimpan
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

# === HELPER: LOGGING ===
async def send_log(message):
    print(f"[LOG SYSTEM] {message}") # Print ke console Railway juga
    if not LOG_CHANNEL_ID: return
    try:
        channel = bot.get_channel(int(LOG_CHANNEL_ID))
        if channel: await channel.send(message)
    except: pass

# === EVENT: ON READY ===
@bot.event
async def on_ready():
    print("------------------------------------------------")
    print(f"✅ LOGIN SUKSES: {bot.user}")
    print(f"✅ ID BOT      : {bot.user.id}")
    print(f"✅ DATABASE    : {DB_FILE}")
    print("------------------------------------------------")
    
    if not scheduler_task.is_running():
        scheduler_task.start()
    
    await send_log("✅ **SYSTEM ONLINE (Railway Deploy)**\nBot siap digunakan.")

# === COMMANDS ===
@bot.command(name="daftar")
async def menu_cmd(ctx):
    text = (
        "✅ **SYSTEM ONLINE**\n"
        "```asciidoc\n"
        "= DAFTAR PERINTAH =\n"
        "!add_daily [ID]...    :: ➕ Tambah/Update Jadwal\n"
        "!send_now [opsi]      :: 🚀 Kirim Instan (pagi/malam)\n"
        "!remove_daily [ID]    :: 🗑️ Hapus Jadwal\n"
        "!list_daily           :: 📋 Cek Database\n"
        "!time                 :: ⏰ Cek Waktu Server\n"
        "```"
    )
    await ctx.reply(text)

@bot.command(name="add_daily")
async def add_daily(ctx, *, args=None):
    if not args or "|" not in args:
        return await ctx.reply("❌ Format: `!add_daily ID1 ID2 Pagi | Malam`")

    try:
        left, msg_pm = args.split("|", 1)
        msg_pm = msg_pm.strip()
        parts = left.strip().split()
        target_ids = [p for p in parts if p.isdigit() and len(p) > 15]
        msg_am = " ".join([p for p in parts if not p.isdigit() or len(p) <= 15])

        if not target_ids: return await ctx.reply("❌ ID Channel tidak valid.")

        data = load_data()
        for cid in target_ids:
            data[cid] = {"am": msg_am, "pm": msg_pm}
        save_data(data)
        
        await ctx.reply(f"✅ Tersimpan untuk {len(target_ids)} channel.")
        await send_log(f"📝 Database updated: {len(data)} entries.")
    except Exception as e:
        await ctx.reply(f"❌ Error: {e}")

@bot.command(name="list_daily")
async def list_daily(ctx):
    data = load_data()
    if not data: return await ctx.reply("📭 Database Kosong.")
    
    # Kirim file text jika list terlalu panjang (agar rapi)
    list_str = ""
    for cid, m in data.items():
        list_str += f"ID: {cid}\nAM: {m['am']}\nPM: {m['pm']}\n{'='*20}\n"
    
    import io
    file = discord.File(io.StringIO(list_str), filename="daily_list.txt")
    await ctx.reply("📋 **Database List**", file=file)

@bot.command(name="remove_daily")
async def remove_daily(ctx, *ids):
    data = load_data()
    deleted = 0
    for cid in ids:
        if cid in data:
            del data[cid]
            deleted += 1
    save_data(data)
    await ctx.reply(f"🗑️ Menghapus {deleted} data.")

@bot.command(name="time")
async def time_cmd(ctx):
    now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
    await ctx.reply(f"⏰ **Waktu Server (WIB):** `{now.strftime('%H:%M:%S')}`")

@bot.command(name="send_now")
async def send_now(ctx, mode: str):
    mode = mode.lower()
    if "pagi" in mode: await run_batch("MANUAL_PAGI", "am")
    elif "malam" in mode: await run_batch("MANUAL_MALAM", "pm")
    else: await ctx.reply("❌ Gunakan `!send_now pagi` atau `!send_now malam`")

# === SCHEDULER & BATCH ===
async def run_batch(name, key):
    data = load_data()
    if not data: return
    
    count = 0
    for cid, content in data.items():
        try:
            chan = bot.get_channel(int(cid)) or await bot.fetch_channel(int(cid))
            if chan:
                await chan.send(content[key])
                count += 1
                await asyncio.sleep(1) # Anti-Spam
        except Exception as e:
            print(f"[ERROR] {cid}: {e}")
    
    await send_log(f"✅ **BATCH {name}**: Terkirim ke {count}/{len(data)} channel.")

@tasks.loop(seconds=60)
async def scheduler_task():
    now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
    t = now.strftime("%H:%M")
    
    if t == "07:00": await run_batch("AUTO_PAGI", "am")
    elif t == "19:00": await run_batch("AUTO_MALAM", "pm")

@scheduler_task.before_loop
async def before_scheduler():
    await bot.wait_until_ready()

# === RUN ===
if __name__ == "__main__":
    if not TOKEN:
        print("❌ FATAL ERROR: Token Discord belum di-set di Railway Variables!")
    else:
        try:
            bot.run(TOKEN)
        except discord.errors.LoginFailure:
            print("\n❌ TOKEN SALAH! Cek tab 'Variables' di Railway. Pastikan Token benar.")
        except discord.errors.PrivilegedIntentsRequired:
            print("\n❌ INTENTS ERROR! Aktifkan 'Message Content Intent' di Discord Developer Portal.")
        except Exception as e:
            print(f"❌ ERROR: {e}")
