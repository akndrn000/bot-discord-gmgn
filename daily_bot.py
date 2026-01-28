import os
import discord
import asyncio
import json
import datetime
from datetime import datetime, timedelta
from discord.ext import commands, tasks

# === KONFIGURASI ===
TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
TIMEZONE_OFFSET = 7  # WIB
DB_FILE = "/app/data/daily_list.json"

# Fallback file location (jika dijalankan di PC lokal)
if not os.path.exists("/app/data"):
    DB_FILE = "daily_list.json"

# === SETUP SELF-BOT ===
bot = commands.Bot(command_prefix="!", self_bot=True, help_command=None)

# === DATA MANAGER ===
def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_data(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

# === HELPER: LOGGING CANTIK (KOTAK) ===
async def send_log(title, details):
    print(f"[LOG] {title}")
    if not LOG_CHANNEL_ID: return
    try:
        # Format Kotak menggunakan Markdown YAML
        log_box = (
            f"```yaml\n"
            f"{title}\n"
            f"{'-'*30}\n"
            f"{details}\n"
            f"{'-'*30}\n"
            f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}\n"
            f"```"
        )
        
        channel = bot.get_channel(int(LOG_CHANNEL_ID))
        if not channel: channel = await bot.fetch_channel(int(LOG_CHANNEL_ID))
        if channel: await channel.send(log_box)
    except Exception as e:
        print(f"Gagal kirim log: {e}")

# === EVENT: ON READY ===
@bot.event
async def on_ready():
    print(f"✅ LOGIN: {bot.user}")
    
    if not scheduler_task.is_running():
        scheduler_task.start()
    
    # Pesan pembuka saat bot restart/nyala
    startup_msg = (
        "✅ **SYSTEM ONLINE**\n"
        "👉 Ketik `!daftar` untuk melihat menu."
    )
    
    # Kirim ke log channel
    if LOG_CHANNEL_ID:
        try:
            channel = bot.get_channel(int(LOG_CHANNEL_ID)) or await bot.fetch_channel(int(LOG_CHANNEL_ID))
            await channel.send(startup_msg)
        except: pass

# === COMMAND: MENU RAPI (ALIGNMENT) ===
@bot.command(name="daftar")
async def menu_cmd(ctx):
    if ctx.author.id != bot.user.id: return
    
    # Tampilan Menu dengan Spasi yang dihitung agar lurus
    menu_box = (
        "```yaml\n"
        "🤖 CONTROL PANEL\n"
        "!add_daily       : Tambah / Update Jadwal [Format: ID1 ID2 Pagi | Malam]\n"
        "!send_now        : Kirim Pesan Manual [Opsi: pagi / malam]\n"
        "!remove_daily    : Hapus Jadwal Channel [Format: !remove_daily ID]\n"
        "!list_daily      : Cek Database List\n"
        "!time            : Cek Waktu Server\n"
        "```"
    )
    await ctx.reply(menu_box)

# === COMMAND: ADD ===
@bot.command(name="add_daily")
async def add_daily(ctx, *, args=None):
    if ctx.author.id != bot.user.id: return
    
    if not args or "|" not in args:
        return await ctx.reply("❌ Format Salah. Gunakan:\n`!add_daily ID1 ID2 Pesan Pagi | Pesan Malam`")

    try:
        left, msg_pm = args.split("|", 1)
        
        # Memisahkan ID (Angka) dan Text
        parts = left.split()
        target_ids = []
        msg_am_parts = []
        
        for p in parts:
            if p.isdigit() and len(p) > 10: target_ids.append(p)
            else: msg_am_parts.append(p)
            
        msg_am = " ".join(msg_am_parts)
        msg_pm = msg_pm.strip()

        if not target_ids: return await ctx.reply("❌ Tidak ada ID Channel.")

        data = load_data()
        for cid in target_ids:
            data[cid] = {"am": msg_am, "pm": msg_pm}
        save_data(data)

        # Laporan Add dalam Kotak
        details = (
            f"Total    : {len(target_ids)} Channel\n"
            f"Pesan AM : {msg_am[:20]}...\n"
            f"Pesan PM : {msg_pm[:20]}..."
        )
        await send_log("📝 DATABASE UPDATED", details)
        await ctx.reply("✅ Data tersimpan.")
        
    except Exception as e:
        await ctx.reply(f"❌ Error: {e}")

# === COMMAND: LIST ===
@bot.command(name="list_daily")
async def list_daily(ctx):
    if ctx.author.id != bot.user.id: return
    data = load_data()
    
    if not data: return await ctx.reply("📭 Database Kosong.")
    
    output = "```yaml\n📋 DATABASE LIST\n"
    for cid, m in data.items():
        output += f"ID: {cid}\n   AM: {m['am'][:15]}..\n   PM: {m['pm'][:15]}..\n"
    output += "```"
    
    await ctx.reply(output)

# === COMMAND: SEND NOW ===
@bot.command(name="send_now")
async def send_now(ctx, mode: str):
    if ctx.author.id != bot.user.id: return
    if "pagi" in mode: await run_batch("MANUAL (PAGI)", "am")
    elif "malam" in mode: await run_batch("MANUAL (MALAM)", "pm")

# === COMMAND: TIME ===
@bot.command(name="time")
async def time_cmd(ctx):
    if ctx.author.id != bot.user.id: return
    now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
    await ctx.reply(f"```yaml\n⏰ WAKTU SERVER: {now.strftime('%H:%M:%S')}\n```")

# === CORE: BATCH SENDER ===
async def run_batch(name, key):
    data = load_data()
    total = len(data)
    if total == 0: return

    success = 0
    failed = 0
    
    # Proses Kirim
    for cid, content in data.items():
        try:
            channel = bot.get_channel(int(cid))
            if not channel: channel = await bot.fetch_channel(int(cid))
            
            await channel.send(content[key])
            success += 1
            await asyncio.sleep(2) # Delay aman untuk Self-Bot
        except:
            failed += 1
    
    # BUKTI TERKIRIM DALAM KOTAK (Log)
    details = (
        f"Status   : Selesai\n"
        f"Total    : {total} Channel\n"
        f"Sukses   : {success}\n"
        f"Gagal    : {failed}"
    )
    await send_log(f"🚀 PENGIRIMAN {name}", details)

# === SCHEDULER ===
@tasks.loop(seconds=60)
async def scheduler_task():
    now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
    t = now.strftime("%H:%M")
    
    if t == "07:00": await run_batch("AUTO (PAGI)", "am")
    elif t == "19:00": await run_batch("AUTO (MALAM)", "pm")

@scheduler_task.before_loop
async def before_scheduler():
    await bot.wait_until_ready()

# === RUN ===
if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ Token belum diisi di Railway Variable")
