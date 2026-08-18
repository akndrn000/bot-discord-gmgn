import os
import json
import asyncio
import random
import pytz
from datetime import datetime
from discord.ext import tasks, commands
from discord import Message

# === Jalur Penyimpanan Config (Mendukung Railway Volume di /data) ===
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
        except Exception as e:
            print(f"[⚠️] Gagal membaca {CONFIG_FILE}: {e}")
    return default_config

def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"[❌] Gagal menyimpan {CONFIG_FILE}: {e}")

# Memuat konfigurasi awal
config = load_config()

# === Konfigurasi Environment Variables ===
DISCORD_USER_TOKEN = os.getenv("DISCORD_USER_TOKEN", "")
MONITOR_CHANNEL_ID = int(os.getenv("MONITOR_CHANNEL_ID", "0"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Jakarta")

# Inisialisasi Self-Bot Client
client = commands.Bot(command_prefix="!", self_bot=True)

# State penanda tanggal terakhir pesan dikirim (Mencegah pengiriman ganda)
last_sent_gm_date = None
last_sent_gn_date = None

# Variasi Pesan Otomatis
GM_MESSAGES = [
    "gm", 
    "gm guys", 
    "gm frens", 
    "gm all", 
    "good morning", 
    "gm! hope u all have a great day"
]

GN_MESSAGES = [
    "gn", 
    "gn guys", 
    "gn frens", 
    "gn all", 
    "good night", 
    "gn! sleep well everyone"
]

def get_menu_text():
    return (
        "🤖 **BOT GM/GN ON**\n"
        "───────────────────────────────\n"
        "📌 **MENU PERINTAH:**\n"
        "• `!set <id1> <id2>` : Tambah 1 atau banyak target channel sekaligus\n"
        "• `!time gm:07.00, gn:19.00` : Atur jam kirim GM dan GN\n"
        "• `!list` : Lihat daftar target channel & jadwal aktif\n"
        "• `!stop <id>` : Hapus 1 ID channel dari target\n"
        "• `!menu` : Tampilkan menu bantuan ini\n"
        "───────────────────────────────"
    )

async def send_log(message_text: str):
    """Mengirim pesan log/notifikasi ke channel pemantau."""
    print(message_text)
    if MONITOR_CHANNEL_ID != 0:
        try:
            channel = client.get_channel(MONITOR_CHANNEL_ID) or await client.fetch_channel(MONITOR_CHANNEL_ID)
            if channel:
                await channel.send(message_text)
        except Exception as e:
            print(f"[❌] Gagal kirim pesan ke channel pemantau ({MONITOR_CHANNEL_ID}): {e}")

@client.event
async def on_ready():
    print(f"[✅] Login sebagai {client.user}")
    # Kirim status ON beserta Menu saat pertama kali bot terhubung
    await send_log(get_menu_text())
    
    if not gm_gn_scheduler.is_running():
        gm_gn_scheduler.start()

@client.event
async def on_message(message: Message):
    # Hanya tanggapi perintah dari akun sendiri
    if message.author.id != client.user.id:
        return

    # Batasi perintah hanya jika dikirim di channel pemantau
    if MONITOR_CHANNEL_ID != 0 and message.channel.id != MONITOR_CHANNEL_ID:
        return

    ctx = await client.get_context(message)
    if ctx.valid:
        await client.invoke(ctx)

# === Command: !menu ===
@client.command(name="menu")
async def show_menu(ctx):
    await ctx.send(get_menu_text())

# === Command: !set ===
@client.command(name="set")
async def set_channel(ctx, *channel_ids: str):
    if not channel_ids:
        await ctx.send("❌ Harap masukkan setidaknya satu ID channel.\n*Contoh:* `!set 123456789 987654321`")
        return

    added, already_exist, invalid = [], [], []

    for cid in channel_ids:
        if not cid.isdigit():
            invalid.append(cid)
            continue
        
        cid_int = int(cid)
        if cid_int not in config["target_channels"]:
            config["target_channels"].append(cid_int)
            added.append(str(cid_int))
        else:
            already_exist.append(str(cid_int))

    save_config(config)

    res = "✅ **Pembaruan Channel Target:**\n"
    if added:
        res += f"• **Ditambahkan:** {', '.join(added)}\n"
    if already_exist:
        res += f"• **Sudah Ada:** {', '.join(already_exist)}\n"
    if invalid:
        res += f"• **Format Tidak Valid:** {', '.join(invalid)}\n"

    await ctx.send(res)

# === Command: !time ===
@client.command(name="time")
async def set_time(ctx, *, time_str: str = None):
    if not time_str:
        await ctx.send("❌ Format salah.\n*Contoh:* `!time gm:07.00, gn:19.00` atau `!time gm:07:00, gn:19:00`")
        return

    try:
        clean_str = time_str.replace('.', ':').lower()
        parts = [p.strip() for p in clean_str.split(',')]
        
        new_gm, new_gn = None, None

        for part in parts:
            if part.startswith("gm:"):
                new_gm = part.replace("gm:", "").strip()
            elif part.startswith("gn:"):
                new_gn = part.replace("gn:", "").strip()

        if new_gm:
            datetime.strptime(new_gm, "%H:%M")
            config["gm_time"] = new_gm
        if new_gn:
            datetime.strptime(new_gn, "%H:%M")
            config["gn_time"] = new_gn

        save_config(config)
        await ctx.send(f"⏰ **Jadwal Diperbarui:**\n• **GM:** `{config['gm_time']}` | **GN:** `{config['gn_time']}`")

    except ValueError:
        await ctx.send("❌ Format jam tidak valid. Gunakan format 24 Jam (`HH:MM`).")
    except Exception as e:
        await ctx.send(f"❌ Terjadi kesalahan: {e}")

# === Command: !list ===
@client.command(name="list")
async def list_channels(ctx):
    channels = config.get("target_channels", [])
    gm_t = config.get("gm_time", "Belum diatur")
    gn_t = config.get("gn_time", "Belum diatur")

    msg = f"📋 **Status Konfigurasi Saat Ini:**\n"
    msg += f"• **GM Time:** `{gm_t}`\n"
    msg += f"• **GN Time:** `{gn_t}`\n"
    msg += f"• **Total Target Channel:** `{len(channels)}`\n\n"

    if channels:
        msg += "**Daftar Channel ID Target:**\n"
        for idx, cid in enumerate(channels, 1):
            msg += f"{idx}. `{cid}`\n"
    else:
        msg += "*Belum ada target channel. Gunakan `!set <channel_id>`.*"

    await ctx.send(msg)

# === Command: !stop ===
@client.command(name="stop")
async def stop_channel(ctx, channel_id: str = None):
    if not channel_id or not channel_id.isdigit():
        await ctx.send("❌ Masukkan ID channel yang valid. *Contoh:* `!stop 123456789`")
        return

    cid_int = int(channel_id)
    if cid_int in config["target_channels"]:
        config["target_channels"].remove(cid_int)
        save_config(config)
        await ctx.send(f"🗑️ Berhasil menghapus channel `{channel_id}` dari target.")
    else:
        await ctx.send(f"⚠️ Channel ID `{channel_id}` tidak ditemukan di daftar.")

# === Task Scheduler GM/GN ===
@tasks.loop(seconds=30)
async def gm_gn_scheduler():
    global last_sent_gm_date, last_sent_gn_date

    try:
        tz = pytz.timezone(TIMEZONE)
    except Exception:
        tz = pytz.timezone("Asia/Jakarta")

    now = datetime.now(tz)
    current_time_str = now.strftime("%H:%M")
    current_date_str = now.strftime("%Y-%m-%d")

    target_gm = config.get("gm_time")
    target_gn = config.get("gn_time")
    channels = config.get("target_channels", [])

    if not channels:
        return

    # Pengecekan Jam GM
    if current_time_str == target_gm and last_sent_gm_date != current_date_str:
        last_sent_gm_date = current_date_str
        await broadcast_message(GM_MESSAGES, "GM")

    # Pengecekan Jam GN
    elif current_time_str == target_gn and last_sent_gn_date != current_date_str:
        last_sent_gn_date = current_date_str
        await broadcast_message(GN_MESSAGES, "GN")

async def broadcast_message(messages_list, mode_label):
    channels = config.get("target_channels", [])
    await send_log(f"🚀 Memulai pengiriman **{mode_label}** ke {len(channels)} channel...")

    for cid in channels:
        try:
            channel = client.get_channel(cid) or await client.fetch_channel(cid)
            if channel:
                # Jeda acak 2–6 detik antar channel agar alami
                await asyncio.sleep(random.randint(2, 6))
                
                msg_content = random.choice(messages_list)
                await channel.send(msg_content)
                await send_log(f"✅ [{mode_label}] Terkirim ke `{cid}`: *\"{msg_content}\"*")
        except Exception as e:
            await send_log(f"❌ [{mode_label}] Gagal kirim ke `{cid}`: {e}")

if __name__ == "__main__":
    if not DISCORD_USER_TOKEN:
        print("[❌] ERROR: Variable DISCORD_USER_TOKEN belum diisi di Environment Variables Railway!")
    else:
        client.run(DISCORD_USER_TOKEN)
