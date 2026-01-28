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

# Fallback file location
if not os.path.exists("/app/data"):
    DB_FILE = "daily_list.json"

# === SETUP SELF-BOT ===
# Self-bot tidak pakai Intents yang sama dengan Bot biasa
# Kita matikan verifikasi intents
bot = commands.Bot(command_prefix="!", self_bot=True, help_command=None)

def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_data(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

async def send_log(message):
    print(f"[LOG] {message}")
    if not LOG_CHANNEL_ID: return
    try:
        # Self-bot harus kirim pesan sebagai user
        channel = bot.get_channel(int(LOG_CHANNEL_ID))
        if channel: await channel.send(message)
    except Exception as e:
        print(f"Gagal kirim log: {e}")

@bot.event
async def on_ready():
    print(f"✅ LOGIN SUKSES SEBAGAI USER: {bot.user}")
    if not scheduler_task.is_running():
        scheduler_task.start()
    await send_log("✅ **SELF-BOT ONLINE** (Railway)")

# === COMMANDS ===
@bot.command(name="daftar")
async def menu_cmd(ctx):
    # Self-bot merespon command dirinya sendiri
    if ctx.author.id != bot.user.id: return
    
    text = (
        "✅ **MENU SELF-BOT**\n"
        "`!add_daily ID1 ID2 Pagi | Malam`\n"
        "`!send_now pagi/malam`\n"
        "`!remove_daily ID`\n"
        "`!list_daily`\n"
        "`!time`"
    )
    await ctx.reply(text)

@bot.command(name="add_daily")
async def add_daily(ctx, *, args=None):
    if ctx.author.id != bot.user.id: return
    
    if not args or "|" not in args:
        return await ctx.reply("❌ Format: ID1 ID2 Pagi | Malam")

    try:
        left, msg_pm = args.split("|", 1)
        target_ids = [x for x in left.split() if x.isdigit()]
        msg_am = " ".join([x for x in left.split() if not x.isdigit()])

        data = load_data()
        for cid in target_ids:
            data[cid] = {"am": msg_am, "pm": msg_pm.strip()}
        save_data(data)
        await ctx.reply(f"✅ Saved for {len(target_ids)} channels.")
    except:
        await ctx.reply("❌ Error parsing.")

@bot.command(name="list_daily")
async def list_daily(ctx):
    if ctx.author.id != bot.user.id: return
    data = load_data()
    if not data: return await ctx.reply("📭 Kosong.")
    
    txt = "📋 **LIST**\n"
    for cid, m in data.items():
        txt += f"{cid} | {m['am'][:10]}.. | {m['pm'][:10]}..\n"
    await ctx.reply(txt)

@bot.command(name="send_now")
async def send_now(ctx, mode: str):
    if ctx.author.id != bot.user.id: return
    if "pagi" in mode: await run_batch("MANUAL", "am")
    elif "malam" in mode: await run_batch("MANUAL", "pm")

@bot.command(name="time")
async def time_cmd(ctx):
    if ctx.author.id != bot.user.id: return
    now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
    await ctx.reply(f"⏰ {now.strftime('%H:%M:%S')}")

async def run_batch(name, key):
    data = load_data()
    count = 0
    for cid, content in data.items():
        try:
            channel = bot.get_channel(int(cid))
            if not channel: channel = await bot.fetch_channel(int(cid))
            await channel.send(content[key])
            count += 1
            await asyncio.sleep(2) # Wajib delay biar gak kena ban
        except Exception as e:
            print(f"Error {cid}: {e}")
    await send_log(f"✅ Batch {name}: {count} terkirim.")

@tasks.loop(seconds=60)
async def scheduler_task():
    now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
    t = now.strftime("%H:%M")
    if t == "07:00": await run_batch("AUTO", "am")
    elif t == "19:00": await run_batch("AUTO", "pm")

@scheduler_task.before_loop
async def before_scheduler():
    await bot.wait_until_ready()

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Token kosong")
