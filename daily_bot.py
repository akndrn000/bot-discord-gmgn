import os
import discord
import asyncio
import json
from datetime import datetime, timedelta
from discord.ext import tasks

# === KONFIGURASI ===
# Pastikan environment variable diset atau ganti manual string di bawah
DISCORD_USER_TOKEN = os.getenv("DISCORD_TOKEN") 
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
TIMEZONE_OFFSET = 7  # WIB
DB_FILE = "daily_list.json"

print(r'''
 🌅 DAILY BOT - FINAL (OPTIMIZED & SECURED)
''')

class DailyBot(discord.Client):
    def __init__(self):
        # === UPDATE 1: WAJIB MENGGUNAKAN INTENTS ===
        intents = discord.Intents.default()
        intents.message_content = True # Agar bot bisa baca isi pesan (!perintah)
        intents.guilds = True
        super().__init__(intents=intents)
        
        self.daily_data = self.load_data()
        self.sent_today_am = False 
        self.sent_today_pm = False
        self.log_channel = None 

    def load_data(self):
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r") as f: return json.load(f)
            except: return {}
        return {}

    def save_data(self):
        try:
            with open(DB_FILE, "w") as f:
                json.dump(self.daily_data, f, indent=4)
        except Exception as e:
            print(f"❌ Gagal menyimpan database: {e}")

    async def send_log(self, message):
        if not LOG_CHANNEL_ID: return
        try:
            if not self.log_channel:
                self.log_channel = await self.fetch_channel(int(LOG_CHANNEL_ID))
            await self.log_channel.send(message)
        except: pass

    # === FUNGSI MENU RAPI ===
    def get_menu_text(self):
        return (
            "✅ **SYSTEM ONLINE**\n"
            "```asciidoc\n"
            "= DAFTAR PERINTAH =\n"
            "!add_daily [ID]...    :: ➕ Tambah/Update Jadwal\n"
            "   └ Format: !add_daily ID_Channel Pesan Pagi | Pesan Malam\n"
            "!send_now [opsi]      :: 🚀 Kirim Instan (pagi/malam)\n"
            "!remove_daily [ID]    :: 🗑️ Hapus Jadwal\n"
            "!break                :: 🧹 Hapus 30 Pesan (Cleaner)\n"
            "!list_daily           :: 📋 Cek List Channel\n"
            "!time                 :: ⏰ Cek Waktu Server\n"
            "!daftar               :: 📜 Tampilkan Menu Ini\n"
            "```"
        )

    async def on_ready(self):
        print(f"[✅] Login berhasil sebagai: {self.user}")
        
        # Pesan Startup
        startup_msg = (
            "✅ **BOT AKTIF**\n"
            "👉 Ketik `!daftar` untuk menampilkan menu."
        )
        await self.send_log(startup_msg)

        # Mulai loop scheduler jika belum jalan
        if not self.scheduler_task.is_running():
            self.scheduler_task.start()

    async def on_message(self, message):
        # Mencegah bot merespon bot lain atau dirinya sendiri (kecuali untuk command sendiri)
        if message.author.id != self.user.id: return
        
        content = message.content.strip()
        if not content: return
        cmd = content.split(" ")[0].lower()

        # === 1. TAMPILKAN DAFTAR MENU ===
        if cmd == "!daftar":
            await message.reply(self.get_menu_text())

        # === 2. FITUR BREAK (CLEANER) ===
        elif cmd == "!break":
            msg_load = await message.reply("🧹 **Membersihkan...**")
            await asyncio.sleep(1) 

            deleted_count = 0
            # History limit
            async for msg in message.channel.history(limit=30):
                try:
                    if msg.id != msg_load.id: 
                        await msg.delete()
                        deleted_count += 1
                        await asyncio.sleep(0.8) # Sedikit delay agar aman
                except: pass

            await msg_load.edit(content=f"🧹 **SELESAI**: Menghapus {deleted_count} pesan.")
            await asyncio.sleep(3)
            await msg_load.delete()

        # === 3. KIRIM MANUAL ===
        elif cmd == "!send_now":
            args = content[len("!send_now"):].strip().lower()

            if "pagi" in args or "gm" in args:
                await message.reply("🚀 **Mengirim Pesan PAGI...**")
                # Delay 1 detik per pesan untuk keamanan rate limit manual
                await self.run_batch("MANUAL (PAGI)", "am", delay=1) 

            elif "malam" in args or "gn" in args:
                await message.reply("🚀 **Mengirim Pesan MALAM...**")
                await self.run_batch("MANUAL (MALAM)", "pm", delay=1)

            else:
                await message.reply("❌ Format: `!send_now pagi` atau `!send_now malam`")

        # === 4. ADD JADWAL ===
        elif cmd == "!add_daily":
            try:
                if "|" not in content:
                    await message.reply("❌ Error: Pisahkan pesan pagi dan malam dengan tanda `|`\nContoh: `!add_daily 123456789 Selamat Pagi | Selamat Malam`")
                    return

                raw_args = content[len("!add_daily"):].strip()
                left_part, msg_malam = raw_args.split("|", 1)
                msg_malam = msg_malam.strip()

                left_words = left_part.strip().split()
                target_ids = []
                msg_pagi_words = []

                found_text = False
                for word in left_words:
                    # Logika deteksi ID: Angka dan panjang > 15 digit
                    if word.isdigit() and len(word) > 15 and not found_text:
                        target_ids.append(word)
                    else:
                        found_text = True
                        msg_pagi_words.append(word)

                msg_pagi = " ".join(msg_pagi_words)

                if not target_ids:
                    await message.reply("❌ Tidak ada ID Channel yang valid terdeteksi.")
                    return

                msg_loading = await message.reply("⏳ **Memproses Database...**")

                success_lines = []
                failed_lines = []

                for cid in target_ids:
                    try:
                        # Validasi apakah bot bisa akses channel tersebut
                        chan = await self.fetch_channel(int(cid))
                        self.daily_data[cid] = {"am": msg_pagi, "pm": msg_malam}
                        success_lines.append(f"Channel : {chan.name}")
                    except discord.Forbidden:
                        failed_lines.append(f"ID {cid}: Bot tidak punya akses")
                    except discord.NotFound:
                        failed_lines.append(f"ID {cid}: Channel tidak ditemukan")
                    except Exception as e:
                        failed_lines.append(f"ID {cid}: Error")

                self.save_data()

                # Buat Laporan Rapi
                report = "📝 **LAPORAN INPUT**\n```yaml\n"
                if success_lines:
                    report += "BERHASIL:\n"
                    for s in success_lines: report += f"- {s}\n"
                if failed_lines:
                    report += "\nGAGAL:\n"
                    for f in failed_lines: report += f"- {f}\n"

                report += f"\nSETTING PESAN:\n"
                report += f"Pagi  : \"{msg_pagi}\"\n"
                report += f"Malam : \"{msg_malam}\"\n"
                report += "```"

                await msg_loading.edit(content=report)
                await self.send_log(f"📝 Database updated: {len(self.daily_data)} channels total.")

            except Exception as e:
                await message.reply(f"❌ Critical Error: {e}")

        # === 5. REMOVE ===
        elif cmd == "!remove_daily":
            try:
                raw_ids = content[len("!remove_daily"):].strip().split()
                deleted = []
                for cid in raw_ids:
                    if cid in self.daily_data:
                        del self.daily_data[cid]
                        deleted.append(cid)
                self.save_data()
                await message.reply(f"🗑️ Berhasil menghapus {len(deleted)} jadwal dari database.")
            except: pass

        # === 6. LIST RAPI ===
        elif cmd == "!list_daily":
            if not self.daily_data: 
                await message.reply("📭 Database Kosong.")
            else:
                chunks = ["📋 **LIST JADWAL AKTIF**"]
                current_chunk = "```yaml\n"

                i = 1
                for cid, m in self.daily_data.items():
                    entry = (
                        f"#{i} ID    : {cid}\n"
                        f"   AM    : \"{m['am'][:30]}...\"\n"
                        f"   PM    : \"{m['pm'][:30]}...\"\n\n"
                    )

                    if len(current_chunk) + len(entry) > 1900:
                        current_chunk += "```"
                        chunks.append(current_chunk)
                        current_chunk = "```yaml\n" + entry
                    else:
                        current_chunk += entry
                    i += 1

                current_chunk += "```"
                chunks.append(current_chunk)

                for c in chunks: await message.reply(c)

        # === 7. TIME RAPI ===
        elif cmd == "!time":
            now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
            time_str = now.strftime('%H:%M:%S')
            date_str = now.strftime('%d-%m-%Y')

            msg = (
                f"⏰ **WAKTU SERVER**\n"
                f"```yaml\n"
                f"Jam     : {time_str}\n"
                f"Tanggal : {date_str}\n"
                f"Zone    : WIB (UTC+7)\n"
                f"```"
            )
            await message.reply(msg)

    # === CORE: EKSEKUSI PESAN ===
    async def run_batch(self, type_name, key, delay=2):
        total = len(self.daily_data)
        success = 0
        failed = 0
        failed_details = []

        await self.send_log(f"⏳ **MEMULAI BATCH: {type_name}**")

        for cid, data in self.daily_data.items():
            try:
                channel = await self.fetch_channel(int(cid))
                await channel.send(data[key]) 
                success += 1
                if delay > 0: await asyncio.sleep(delay)

            except Exception as e:
                failed += 1
                failed_details.append(f"- ID {cid} : {str(e)}")

        # Laporan Akhir Rapi
        report = (
            f"✅ **BATCH SELESAI**\n"
            f"```yaml\n"
            f"Tipe      : {type_name}\n"
            f"Total     : {total}\n"
            f"Sukses    : {success}\n"
            f"Gagal     : {failed}\n"
        )

        if failed_details:
            # Potong jika terlalu panjang
            error_msg = "\nDETAIL ERROR:\n" + "\n".join(failed_details)
            if len(report + error_msg) < 1950:
                report += error_msg
            else:
                report += "\n(Detail error terlalu panjang, cek console)"
                print(error_msg)

        report += "```"

        await self.send_log(report)

    # === SCHEDULE OTOMATIS ===
    @tasks.loop(seconds=60) 
    async def scheduler_task(self):
        now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
        current_time = now.strftime("%H:%M")

        # LOGIKA TRIGGER
        if current_time == "07:00":
            if not self.sent_today_am: 
                await self.run_batch("AUTO (PAGI)", "am", delay=2)
                self.sent_today_am = True
                self.sent_today_pm = False # Reset flag malam

        elif current_time == "19:00":
            if not self.sent_today_pm:
                await self.run_batch("AUTO (MALAM)", "pm", delay=2)
                self.sent_today_pm = True
                self.sent_today_am = False # Reset flag pagi

        # Reset flag manual jika bot restart lewat jam trigger
        # (Opsional, tapi membantu menjaga state)
        if current_time == "07:05": self.sent_today_am = True
        if current_time == "19:05": self.sent_today_pm = True

    @scheduler_task.before_loop
    async def before_scheduler(self):
        # Tunggu sampai bot benar-benar siap sebelum loop jalan
        await self.wait_until_ready()

# === ENTRY POINT YANG DISEMPURNAKAN ===
if __name__ == "__main__":
    if DISCORD_USER_TOKEN:
        try:
            client = DailyBot()
            client.run(DISCORD_USER_TOKEN)
        except discord.errors.LoginFailure:
            print("❌ TOKEN SALAH: Periksa kembali DISCORD_TOKEN anda.")
        except Exception as e:
            print(f"❌ TERJADI ERROR FATAL: {e}")
    else:
        print("❌ CONFIG ERROR: Token tidak ditemukan.")
        print("   Set environment variable 'DISCORD_TOKEN' atau edit file ini.")
