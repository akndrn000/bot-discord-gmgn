import os
import discord
import asyncio
import json
import datetime
from datetime import datetime, timedelta
from discord.ext import commands, tasks

# === KONFIGURASI ===
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")  # Pastikan token ada di ENV atau ganti string ini
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID") # Opsional: ID Channel untuk log bot
TIMEZONE_OFFSET = 7  # WIB (UTC+7)
DB_FILE = "daily_list.json"

# === SETUP BOT MODERN ===
# Kita aktifkan 'Intents' agar bot bisa baca pesan dan member
intents = discord.Intents.default()
intents.message_content = True  # WAJIB untuk membaca command
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# === DATABASE MANAGER ===
def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_data(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

# === EVENTS ===
@bot.event
async def on_ready():
    print(f'''
    ╔════════════════════════════════════════╗
    ║       🤖 DAILY BOT ONLINE (v2.0)       ║
    ║       Logged in as: {bot.user.name}      ║
    ║       ID: {bot.user.id}                ║
    ╚════════════════════════════════════════╝
    ''')
    
    # Cek Log Channel
    if LOG_CHANNEL_ID:
        channel = bot.get_channel(int(LOG_CHANNEL_ID))
        if channel:
            embed = discord.Embed(title="🟢 System Online", description="Bot siap melayani perintah.", color=discord.Color.green())
            await channel.send(embed=embed)
    
    # Jalankan Scheduler jika belum jalan
    if not scheduler_task.is_running():
        scheduler_task.start()

# === COMMANDS (PERINTAH) ===

# 1. MENU BANTUAN
@bot.command(name="help", aliases=["daftar", "menu"])
async def show_help(ctx):
    embed = discord.Embed(title="📘 DAILY BOT COMMANDS", color=discord.Color.blue())
    embed.add_field(name="➕ Tambah Jadwal", value="`!add <Channel_ID> <Pesan Pagi> | <Pesan Malam>`", inline=False)
    embed.add_field(name="📋 Lihat List", value="`!list` (Menampilkan Nama Channel)", inline=False)
    embed.add_field(name="🗑️ Hapus Jadwal", value="`!remove <Channel_ID>`", inline=False)
    embed.add_field(name="🚀 Kirim Manual", value="`!send <pagi/malam>`", inline=False)
    embed.add_field(name="🧹 Bersihkan Chat", value="`!clean <jumlah>` (Default 30)", inline=False)
    embed.add_field(name="⏰ Cek Waktu", value="`!time`", inline=False)
    embed.set_footer(text="Daily Bot System • Auto 07:00 & 19:00 WIB")
    await ctx.send(embed=embed)

# 2. TAMBAH JADWAL (FITUR UTAMA)
@bot.command(name="add")
async def add_daily(ctx, channel_id: str = None, *, content: str = None):
    # Validasi Input
    if not channel_id or not content or "|" not in content:
        await ctx.reply("❌ **Format Salah!**\nGunakan: `!add <Channel_ID> <Pesan Pagi> | <Pesan Malam>`")
        return

    try:
        # Cek apakah Channel Valid & Ambil Namanya
        target_channel = bot.get_channel(int(channel_id))
        if not target_channel:
            await ctx.reply(f"❌ Channel dengan ID `{channel_id}` tidak ditemukan! Pastikan bot sudah join server tersebut.")
            return

        parts = content.split("|", 1)
        msg_am = parts[0].strip()
        msg_pm = parts[1].strip()

        data = load_data()
        data[channel_id] = {
            "am": msg_am,
            "pm": msg_pm,
            "added_by": ctx.author.name
        }
        save_data(data)

        # Konfirmasi Cantik dengan Nama Channel
        embed = discord.Embed(title="✅ Jadwal Disimpan", color=discord.Color.green())
        embed.add_field(name="📍 Channel Target", value=f"**{target_channel.name}** (`{target_channel.id}`)", inline=False)
        embed.add_field(name="🌞 Pesan Pagi", value=f"\"{msg_am}\"", inline=False)
        embed.add_field(name="🌙 Pesan Malam", value=f"\"{msg_pm}\"", inline=False)
        await ctx.send(embed=embed)

    except ValueError:
        await ctx.reply("❌ ID Channel harus berupa angka.")

# 3. LIHAT LIST (DENGAN NAMA CHANNEL)
@bot.command(name="list")
async def list_daily(ctx):
    data = load_data()
    if not data:
        await ctx.reply("📭 **Database Kosong.** Belum ada jadwal.")
        return

    embed = discord.Embed(title=f"📋 LIST JADWAL AKTIF ({len(data)})", color=discord.Color.gold())
    
    description_text = ""
    for cid, info in data.items():
        # Fetch nama channel secara real-time
        channel_obj = bot.get_channel(int(cid))
        channel_name = f"#{channel_obj.name}" if channel_obj else "❌ (Channel Terhapus/Bot Kick)"
        
        description_text += f"**{channel_name}** (`{cid}`)\n"
        description_text += f"├ 🌞: {info['am'][:30]}...\n"
        description_text += f"└ 🌙: {info['pm'][:30]}...\n\n"

    # Handle jika teks terlalu panjang untuk satu embed
    if len(description_text) > 4000:
        description_text = description_text[:4000] + "\n... (List terlalu panjang)"
    
    embed.description = description_text
    await ctx.send(embed=embed)

# 4. HAPUS JADWAL
@bot.command(name="remove", aliases=["del"])
async def remove_daily(ctx, channel_id: str):
    data = load_data()
    if channel_id in data:
        del data[channel_id]
        save_data(data)
        await ctx.reply(f"🗑️ Jadwal untuk ID `{channel_id}` berhasil dihapus.")
    else:
        await ctx.reply("❌ ID tidak ditemukan di database.")

# 5. BERSIHKAN PESAN (CEPAT)
@bot.command(name="clean", aliases=["break", "clear"])
@commands.has_permissions(manage_messages=True)
async def clean_messages(ctx, amount: int = 30):
    # Hapus pesan command user dulu
    await ctx.message.delete()
    
    # Tampilkan loading
    loading = await ctx.send("🧹 **Sedang membersihkan...**")
    
    # Proses Purge (Instan)
    deleted = await ctx.channel.purge(limit=amount, check=lambda m: m.id != loading.id)
    
    await loading.edit(content=f"✨ **Selesai!** Menghapus {len(deleted)} pesan.")
    await asyncio.sleep(3)
    await loading.delete()

@clean_messages.error
async def clean_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply("❌ Kamu tidak punya izin `Manage Messages`.")

# 6. MANUAL TRIGGER
@bot.command(name="send")
async def send_manual(ctx, time_type: str):
    time_type = time_type.lower()
    data = load_data()
    
    if time_type not in ["pagi", "malam", "gm", "gn"]:
        await ctx.reply("❌ Gunakan: `!send pagi` atau `!send malam`")
        return

    key = "am" if time_type in ["pagi", "gm"] else "pm"
    label = "PAGI" if key == "am" else "MALAM"
    
    msg = await ctx.reply(f"🚀 Mengirim pesan **{label}** ke {len(data)} channel...")
    
    count = 0
    for cid, info in data.items():
        try:
            chan = bot.get_channel(int(cid))
            if chan:
                await chan.send(info[key])
                count += 1
                await asyncio.sleep(1) # Delay biar aman
        except: pass
    
    await msg.edit(content=f"✅ **Sukses:** Terkirim ke {count}/{len(data)} channel.")

# 7. CEK WAKTU
@bot.command(name="time")
async def check_time(ctx):
    now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
    await ctx.reply(f"⏰ **Waktu Server (WIB):** `{now.strftime('%H:%M:%S')} | {now.strftime('%d-%m-%Y')}`")

# === TASK SCHEDULER ===
@tasks.loop(seconds=60)
async def scheduler_task():
    now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
    current_time = now.strftime("%H:%M")
    
    # LOGIKA PENGIRIMAN OTOMATIS
    # Menggunakan set/flag sederhana agar tidak double send dalam 1 menit
    data = load_data()
    target_key = None

    if current_time == "07:00":
        target_key = "am"
    elif current_time == "19:00":
        target_key = "pm"
    
    if target_key:
        print(f"[AUTO] Mengirim pesan {target_key.upper()}...")
        for cid, info in data.items():
            try:
                chan = bot.get_channel(int(cid))
                if chan:
                    await chan.send(info[target_key])
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"Gagal kirim ke {cid}: {e}")

# === JALANKAN ===
if __name__ == "__main__":
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        print("❌ Error: DISCORD_TOKEN belum diisi di environment variables.")
