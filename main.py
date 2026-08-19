import os
import json
import asyncio
import random
import pytz
from datetime import datetime

# === PATCH ANTI CRASH DISCORD GATEWAY ===
import discord.state
original_parse_ready_supplemental = discord.state.ConnectionState.parse_ready_supplemental

def patched_parse_ready_supplemental(self, data):
    if data and data.get('pending_payments') is None:
        data['pending_payments'] = []
    try:
        original_parse_ready_supplemental(self, data)
    except Exception:
        pass

discord.state.ConnectionState.parse_ready_supplemental = patched_parse_ready_supplemental
# ========================================

from discord.ext import tasks, commands
from discord import Message

DATA_DIR = "/data" if os.path.exists("/data") else "."
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

def load_config():
    default_config = {
        "gm_time": "07:00",
        "gn_time": "19:00",
        "target_channels": []
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return default_config

def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)
    except Exception:
        pass

config = load_config()

DISCORD_USER_TOKEN = os.getenv("DISCORD_USER_TOKEN", "")
MONITOR_CHANNEL_ID = int(os.getenv("MONITOR_CHANNEL_ID", "0"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Jakarta")

client = commands.Bot(command_prefix="!", self_bot=True)

last_sent_gm_date = None
last_sent_gn_date = None

GM_WEIGHTED_MESSAGES = [
    ("gm", 40),
    ("gm guys", 25),
    ("gm frens", 20),
    ("gm all", 15),
    ("good morning", 10),
    ("gm ser", 6),
    ("morning all", 6),
    ("gm fam", 5),
    ("gm world", 4),
    ("gm everyone", 2),
    ("gm! time to grind", 2),
    ("gm! have a good one", 1)
]

GN_WEIGHTED_MESSAGES = [
    ("gn", 40),
    ("gn guys", 25),
    ("gn frens", 20),
    ("gn all", 15),
    ("good night", 10),
    ("gn ser", 6),
    ("night all", 6),
    ("gn fam", 5),
    ("gn sleep well", 4),
    ("gn world", 2),
    ("gn sleep tight", 2),
    ("gn everyone", 1)
]

def get_random_message(weighted_list):
    messages, weights = zip(*weighted_list)
    return random.choices(messages, weights=weights, k=1)[0]

def get_menu_text():
    return (
        "🤖 **BOT GM/GN ON**\n"
        "───────────────────────────────\n"
        "📌 **MENU PERINTAH:**\n"
        "• `!set <id1> <id2>` : Tambah target channel\n"
        "• `!time gm:07.00, gn:19.00` : Atur jam GM/GN\n"
        "• `!list` : Lihat daftar target & jadwal\n"
        "• `!stop <id>` : Hapus channel dari target\n"
        "• `!test gm` atau `!test gn` : Tes kirim manual\n"
        "• `!menu` : Tampilkan menu bantuan\n"
        "───────────────────────────────"
    )

async def send_log(message_text: str):
    print(message_text)
    if MONITOR_CHANNEL_ID != 0:
        try:
            channel = client.get_channel(MONITOR_CHANNEL_ID) or await client.fetch_channel(MONITOR_CHANNEL_ID)
            if channel:
                await channel.send(message_text)
        except Exception:
            pass

@client.event
async def on_ready():
    print(f"[✅] Login sebagai {client.user}")
    await send_log(get_menu_text())
    if not gm_gn_scheduler.is_running():
        gm_gn_scheduler.start()

@client.event
async def on_message(message: Message):
    if message.author.id != client.user.id:
        return
    if MONITOR_CHANNEL_ID != 0 and message.channel.id != MONITOR_CHANNEL_ID:
        return

    ctx = await client.get_context(message)
    if ctx.valid:
        await client.invoke(ctx)

@client.command(name="menu")
async def show_menu(ctx):
    await ctx.send(get_menu_text())

@client.command(name="set")
async def set_channel(ctx, *channel_ids: str):
    if not channel_ids:
        await ctx.send("❌ Masukkan ID channel. Contoh: `!set 123456789`")
        return
    added, exist, invalid = [], [], []
    for cid in channel_ids:
        if not cid.isdigit():
            invalid.append(cid)
            continue
        cid_int = int(cid)
        if cid_int not in config["target_channels"]:
            config["target_channels"].append(cid_int)
            added.append(str(cid_int))
        else:
            exist.append(str(cid_int))
    save_config(config)
    res = "✅ **Update Target:**\n"
    if added: res += f"• Ditambahkan: {', '.join(added)}\n"
    if exist: res += f"• Sudah ada: {', '.join(exist)}\n"
    if invalid: res += f"• Tidak valid: {', '.join(invalid)}\n"
    await ctx.send(res)

@client.command(name="time")
async def set_time(ctx, *, time_str: str = None):
    if not time_str:
        await ctx.send("❌ Contoh format: `!time gm:07.00, gn:19.00`")
        return
    try:
        clean_str = time_str.replace('.', ':').lower()
        parts = [p.strip() for p in clean_str.split(',')]
        for part in parts:
            if part.startswith("gm:"):
                t = part.replace("gm:", "").strip()
                datetime.strptime(t, "%H:%M")
                config["gm_time"] = t
            elif part.startswith("gn:"):
                t = part.replace("gn:", "").strip()
                datetime.strptime(t, "%H:%M")
                config["gn_time"] = t
        save_config(config)
        await ctx.send(f"⏰ **Jadwal Diperbarui:** GM `{config['gm_time']}` | GN `{config['gn_time']}`")
    except Exception:
        await ctx.send("❌ Format jam salah. Gunakan format 24 Jam (`HH:MM`).")

@client.command(name="list")
async def list_channels(ctx):
    channels = config.get("target_channels", [])
    msg = f"📋 **Konfigurasi:**\n• GM: `{config.get('gm_time')}`\n• GN: `{config.get('gn_time')}`\n• Total Target: `{len(channels)}`\n"
    if channels:
        msg += "\n**Daftar ID:**\n" + "\n".join(f"- `{c}`" for c in channels)
    await ctx.send(msg)

@client.command(name="stop")
async def stop_channel(ctx, channel_id: str = None):
    if not channel_id or not channel_id.isdigit():
        await ctx.send("❌ Masukkan ID valid. Contoh: `!stop 123456789`")
        return
    cid_int = int(channel_id)
    if cid_int in config["target_channels"]:
        config["target_channels"].remove(cid_int)
        save_config(config)
        await ctx.send(f"🗑️ Channel `{channel_id}` dihapus.")
    else:
        await ctx.send(f"⚠️ Channel `{channel_id}` tidak ditemukan.")

@client.command(name="test")
async def test_broadcast(ctx, mode: str = None):
    if not mode or mode.lower() not in ["gm", "gn"]:
        await ctx.send("❌ Format salah. Gunakan: `!test gm` atau `!test gn`")
        return
    
    label = mode.upper()
    messages = GM_WEIGHTED_MESSAGES if label == "GM" else GN_WEIGHTED_MESSAGES
    await ctx.send(f"🧪 **[TES MANUAL]** Mengirimkan {label} ke target channel...")
    await broadcast(messages, f"TEST-{label}")

async def broadcast(w_list, label):
    for cid in config.get("target_channels", []):
        try:
            ch = client.get_channel(cid) or await client.fetch_channel(cid)
            if ch:
                await asyncio.sleep(random.randint(2, 6))
                msg = get_random_message(w_list)
                await ch.send(msg)
        except Exception:
            pass

@tasks.loop(seconds=10)
async def gm_gn_scheduler():
    global last_sent_gm_date, last_sent_gn_date
    try:
        tz = pytz.timezone(TIMEZONE)
    except Exception:
        tz = pytz.timezone("Asia/Jakarta")
    
    now = datetime.now(tz)
    current_time_str = now.strftime("%H:%M")
    current_date_str = now.strftime("%Y-%m-%d")
    
    channels = config.get("target_channels", [])
    if not channels:
        return

    target_gm = config.get("gm_time")
    target_gn = config.get("gn_time")

    if target_gm and current_time_str >= target_gm and last_sent_gm_date != current_date_str:
        gm_hour, gm_min = map(int, target_gm.split(":"))
        if now.hour == gm_hour and (now.minute - gm_min) <= 5:
            last_sent_gm_date = current_date_str
            await broadcast(GM_WEIGHTED_MESSAGES, "GM")

    if target_gn and current_time_str >= target_gn and last_sent_gn_date != current_date_str:
        gn_hour, gn_min = map(int, target_gn.split(":"))
        if now.hour == gn_hour and (now.minute - gn_min) <= 5:
            last_sent_gn_date = current_date_str
            await broadcast(GN_WEIGHTED_MESSAGES, "GN")

if __name__ == "__main__":
    if DISCORD_USER_TOKEN:
        client.run(DISCORD_USER_TOKEN)
