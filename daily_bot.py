import os
import discord
import asyncio
import json
from datetime import datetime, timedelta
from discord.ext import tasks

# === 1. KONFIGURASI ===
# Token & Channel ID diambil dari Environment Variable
DISCORD_USER_TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
TIMEZONE_OFFSET = 7  # WIB (UTC+7)
DB_FILE = "daily_list.json"

print(r'''
 🌅 DAILY BOT - FINAL VERSION (INTENTS FIXED)
''')

class DailyBot(discord.Client):
    def __init__(self):
        # === BAGIAN PENTING (FIX ERROR INTENTS) ===
        # Kita harus mendefinisikan intents agar bot diizinkan membaca pesan
        intents = discord.Intents.default()
        intents.message_content = True  # Wajib True agar bisa baca command !daftar, dll
        
        # Kirim intents ke sistem Discord (Ini yang memperbaiki error sebelumnya)
        super().__init__(intents=intents)
        
        # Load Database
        self.daily_data = self.load_data()
        
        # Status Pengiriman Harian
        self.sent_today_am = False 
        self.sent_today_pm = False
        self.log_channel = None 

    # === 2. SISTEM DATABASE ===
    def load_data(self):
        """Memuat data dari file JSON"""
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r") as f: return json.load(f)
            except: return {}
        return {}

    def save_data(self):
        """Menyimpan data ke file JSON"""
        with open(DB_FILE, "w") as f:
            json.dump(self.daily_data, f, indent=4)

    # === 3. SISTEM LOGGING ===
    async def send_log(self, message):
        """Mengirim pesan log ke channel khusus"""
        if not LOG_CHANNEL_ID: return
        try:
            if not self.log_channel:
                self.log_channel = await self.fetch_channel(int(LOG_CHANNEL_ID))
            await self.log_channel.send(message)
        except: pass

    # === 4. TAMPILAN MENU ===
    def get_menu_text(self):
        return (
            "✅ **SYSTEM ONLINE**\n"
            "```asciidoc\n"
            "= DAFTAR PERINTAH =\n"
            "!add_daily [ID]...    :: ➕ Tambah/Update Jadwal\n"
            "   └ Format: !add_daily ID Pagi | Malam\n"
            "!send_now [opsi]      :: 🚀 Kirim Instan (pagi/malam)\n"
            "!remove_daily [ID]    :: 🗑️ Hapus Jadwal\n"
            "!break                :: 🧹 Hapus 30 Pesan (Cleaner)\n"
            "!list_daily           :: 📋 Cek List Channel (+Nama)\n"
            "!time                 :: ⏰ Cek Waktu Server\n"
            "!daftar               :: 📜 Tampilkan Menu Ini\n"
            "```"
        )

    # === 5. SAAT BOT MENYALA ===
    async def on_ready(self):
        print(f"[✅] Login sukses sebagai {self.user}")
        
        # Kirim notifikasi bot hidup ke log
        startup_msg = (
            "✅ **BOT AKTIF (Versi 2.0 Fixed)**\n"
            "👉 Ketik `!daftar` untuk menampilkan menu."
        )
        await self.send_log(startup_msg)

        # Jalankan loop waktu otomatis jika belum jalan
        if not self.scheduler_task.is_running():
            self.scheduler_task.start()

    # === 6. HANDLER PERINTAH (COMMANDS) ===
    async def on_message(self, message):
        # Bot hanya merespon dirinya sendiri (Self-Bot behavior)
        if message.author.id != self.user.id: return
        
        content = message.content.strip()
        cmd = content.split(" ")[0].lower()

        # --- A. MENU ---
        if cmd == "!daftar":
            await message.reply(self.get_menu_text())

        # --- B. CLEANER / BREAK ---
        elif cmd == "!break":
            msg_load = await message.reply("🧹 **Membersihkan...**")
            await asyncio.sleep(1) 
            deleted_count = 0
            try:
                # Menghapus 30 pesan terakhir
                async for msg in message.channel.history(limit=30):
                    if msg.id != msg_load.id:
                        await msg.delete()
                        deleted_count += 1
                        await asyncio.sleep(0.5) 
            except: pass
            
            await msg_load.edit(content=f"🧹 **SELESAI**: Menghapus {deleted_count} pesan.")
            await asyncio.sleep(3)
            await msg_load.delete()

        # --- C. KIRIM MANUAL ---
        elif cmd == "!send_now":
            args = content[len("!send_now"):].strip().lower()
            if "pagi" in args or "gm" in args:
                await message.reply("🚀 **Mengirim Pesan PAGI...**")
                await self.run_batch("MANUAL (PAGI)", "am", delay=0)
            elif "malam" in args or "gn" in args:
                await message.reply("🚀 **Mengirim Pesan MALAM...**")
                await self.run_batch("MANUAL (MALAM)", "pm", delay=0)
            else:
                await message.reply("❌ Format: `!send_now pagi` atau `!send_now malam`")

        # --- D. ADD JADWAL ---
        elif cmd == "!add_daily":
            try:
                if "|" not in content:
                    await message.reply("❌ Pisahkan pesan pagi dan malam dengan tanda `|`")
                    return

                # Parsing Input
                raw_args = content[len("!add_daily"):].strip()
                left_part, msg_malam = raw_args.split("|", 1)
                msg_malam = msg_malam.strip()
                
                left_words = left_part.strip().split()
                target_ids = []
                msg_pagi_words = []
                
                # Memisahkan ID Channel (angka) dari Pesan Pagi (teks)
                found_text = False
                for word in left_words:
                    if word.isdigit() and len(word) > 15 and not found_text:
                        target_ids.append(word)
                    else:
                        found_text = True
                        msg_pagi_words.append(word)
                
                msg_pagi = " ".join(msg_pagi_words)

                if not target_ids:
                    await message.reply("❌ Tidak ada ID Channel.")
                    return

                msg_loading = await message.reply("⏳ **Memproses...**")
                success_lines = []
                failed_lines = []
                
                # Simpan ke Database
                for cid in target_ids:
                    try:
                        chan = await self.fetch_channel(int(cid))
                        self.daily_data[cid] = {"am": msg_pagi, "pm": msg_malam}
                        success_lines.append(f"Channel : {chan.name} ({cid})")
                    except:
                        failed_lines.append(f"ID      : {cid} (Error/Invalid)")

                self.save_data()

                # Buat Laporan
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
                await message.reply(f"❌ Error: {e}")

        # --- E. HAPUS JADWAL ---
        elif cmd == "!remove_daily":
            try:
                raw_ids = content[len("!remove_daily"):].strip().split()
                deleted = []
                for cid in raw_ids:
                    if cid in self.daily_data:
                        del self.daily_data[cid]
                        deleted.append(cid)
                self.save_data()
                await message.reply(f"🗑️ Menghapus {len(deleted)} jadwal.")
            except: pass

        # --- F. LIHAT LIST ---
        elif cmd == "!list_daily":
            if not self.daily_data: 
                await message.reply("📭 Database Kosong.")
            else:
                chunks = ["📋 **LIST JADWAL AKTIF**"]
                current_chunk = "```yaml\n"
                i = 1
                msg_wait = await message.reply("⏳ **Sedang memuat nama channel...**")

                for cid, m in self.daily_data.items():
                    # Ambil Nama Channel
                    try:
                        chan = self.get_channel(int(cid)) # Cek cache
                        if not chan:
                            chan = await self.fetch_channel(int(cid)) # Cek API
                        c_name = chan.name
                    except:
                        c_name = "⚠️ Unknown/Kick/Deleted"

                    entry = (
                        f"#{i} Channel : {c_name}\n"
                        f"   ID      : {cid}\n"
                        f"   AM      : \"{m['am'][:30]}...\"\n"
                        f"   PM      : \"{m['pm'][:30]}...\"\n\n"
                    )
                    
                    # Potong pesan jika kepanjangan (Batas Discord 2000 char)
                    if len(current_chunk) + len(entry) > 1900:
                        current_chunk += "```"
                        chunks.append(current_chunk)
                        current_chunk = "```yaml\n" + entry
                    else:
                        current_chunk += entry
                    i += 1
                
                current_chunk += "```"
                chunks.append(current_chunk)
                
                await msg_wait.delete()
                for c in chunks: await message.reply(c)

        # --- G. CEK WAKTU ---
        elif cmd == "!time":
            now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
            msg = (
                f"⏰ **WAKTU SERVER**\n"
                f"```yaml\n"
                f"Jam     : {now.strftime('%H:%M:%S')}\n"
                f"Tanggal : {now.strftime('%d-%m-%Y')}\n"
                f"Zone    : WIB (UTC+7)\n"
                f"```"
            )
            await message.reply(msg)

    # === 7. FUNGSI PENGIRIMAN PESAN ===
    async def run_batch(self, type_name, key, delay=2):
        total = len(self.daily_data)
        success = 0
        failed = 0
        failed_details = []

        await self.send_log(f"⏳ **MEMULAI BATCH: {type_name}**")

        for cid, data in self.daily_data.items():
            try:
                # Menggunakan fetch_channel agar lebih reliable
                channel = await self.fetch_channel(int(cid))
                await channel.send(data[key]) 
                success += 1
                if delay > 0: await asyncio.sleep(delay)
                    
            except Exception as e:
                failed += 1
                failed_details.append(f"- ID {cid} : {str(e)}")
        
        # Buat Laporan Batch
        report = (
            f"✅ **BATCH SELESAI**\n"
            f"```yaml\n"
            f"Tipe      : {type_name}\n"
            f"Total     : {total}\n"
            f"Sukses    : {success}\n"
            f"Gagal     : {failed}\n"
        )
        if failed_details:
            report += "\nDETAIL ERROR:\n" + "\n".join(failed_details)
        report += "```"

        if len(report) > 1900:
            await self.send_log(report[:1900] + "...\n```")
        else:
            await self.send_log(report)

    # === 8. JADWAL OTOMATIS (TIMER) ===
    @tasks.loop(seconds=60) 
    async def scheduler_task(self):
        now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
        current_time = now.strftime("%H:%M")

        # Pukul 07:00 Pagi
        if current_time == "07:00":
            if not self.sent_today_am: 
                await self.run_batch("AUTO (PAGI)", "am", delay=2)
                self.sent_today_am = True
                self.sent_today_pm = False 

        # Pukul 19:00 Malam
        elif current_time == "19:00":
            if not self.sent_today_pm:
                await self.run_batch("AUTO (MALAM)", "pm", delay=2)
                self.sent_today_pm = True
                self.sent_today_am = False 
        
        # Reset Logic (jaga-jaga bot mati di tengah jalan)
        else:
            if current_time == "07:01": self.sent_today_am = True
            if current_time == "19:01": self.sent_today_pm = True

# === 9. MAIN PROGRAM ===
if __name__ == "__main__":
    if DISCORD_USER_TOKEN:
        client = DailyBot()
        client.run(DISCORD_USER_TOKEN)
    else:
        print("❌ Token Discord Belum Diisi di Environment Variable!")
