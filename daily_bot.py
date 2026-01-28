import os
import discord
import asyncio
import json
from datetime import datetime, timedelta
from discord.ext import tasks

# === KONFIGURASI ===
DISCORD_USER_TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
TIMEZONE_OFFSET = 7  # WIB (UTC+7)
DB_FILE = "daily_list.json"

print(r'''
 🌅 DAILY BOT - LEGACY VERSION (NO INTENTS)
''')

class DailyBot(discord.Client):
    def __init__(self):
        # === PERBAIKAN DI SINI (LEGACY MODE) ===
        # Kita menghapus intents karena library Anda versi lama
        super().__init__()
        
        self.daily_data = self.load_data()
        self.sent_today_am = False 
        self.sent_today_pm = False
        self.log_channel = None 

    # === DATABASE ===
    def load_data(self):
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r") as f: return json.load(f)
            except: return {}
        return {}

    def save_data(self):
        with open(DB_FILE, "w") as f:
            json.dump(self.daily_data, f, indent=4)

    # === LOG SYSTEM ===
    async def send_log(self, message):
        if not LOG_CHANNEL_ID: return
        try:
            if not self.log_channel:
                # fetch_channel mungkin tidak ada di versi sangat lama, kita pakai get_channel dulu
                self.log_channel = self.get_channel(int(LOG_CHANNEL_ID))
                if not self.log_channel:
                    self.log_channel = await self.fetch_channel(int(LOG_CHANNEL_ID))
            await self.log_channel.send(message)
        except: pass

    # === MENU TAMPILAN ===
    def get_menu_text(self):
        return (
            "✅ **SYSTEM ONLINE (LEGACY MODE)**\n"
            "```asciidoc\n"
            "= DAFTAR PERINTAH =\n"
            "!add_daily [ID]...    :: ➕ Tambah/Update Jadwal\n"
            "   └ Format: !add_daily ID Pagi | Malam\n"
            "!send_now [opsi]      :: 🚀 Kirim Instan (pagi/malam)\n"
            "!remove_daily [ID]    :: 🗑️ Hapus Jadwal\n"
            "!break                :: 🧹 Hapus 30 Pesan (Cleaner)\n"
            "!list_daily           :: 📋 Cek List Channel\n"
            "!time                 :: ⏰ Cek Waktu Server\n"
            "!daftar               :: 📜 Tampilkan Menu Ini\n"
            "```"
        )

    # === STARTUP ===
    async def on_ready(self):
        print(f"[✅] Login sebagai {self.user}")
        
        startup_msg = (
            "✅ **BOT AKTIF (Versi Legacy)**\n"
            "👉 Ketik `!daftar` untuk menampilkan menu."
        )
        await self.send_log(startup_msg)

        if not self.scheduler_task.is_running():
            self.scheduler_task.start()

    # === COMMAND HANDLER ===
    async def on_message(self, message):
        if message.author.id != self.user.id: return
        content = message.content.strip()
        cmd = content.split(" ")[0].lower()

        # 1. MENU
        if cmd == "!daftar":
            await message.channel.send(self.get_menu_text()) # Menggunakan send biasa untuk kompatibilitas

        # 2. CLEANER / BREAK
        elif cmd == "!break":
            msg_load = await message.channel.send("🧹 **Membersihkan...**")
            await asyncio.sleep(1) 

            deleted_count = 0
            # History mungkin berbeda cara kerjanya di versi lama, kita coba blok try-except
            try:
                async for msg in message.channel.history(limit=30):
                    if msg.id != msg_load.id:
                        await msg.delete()
                        deleted_count += 1
                        await asyncio.sleep(1.0) 
            except: pass
            
            await msg_load.edit(content=f"🧹 **SELESAI**: Menghapus {deleted_count} pesan.")
            await asyncio.sleep(3)
            await msg_load.delete()

        # 3. KIRIM MANUAL
        elif cmd == "!send_now":
            args = content[len("!send_now"):].strip().lower()
            
            if "pagi" in args or "gm" in args:
                await message.channel.send("🚀 **Mengirim Pesan PAGI...**")
                await self.run_batch("MANUAL (PAGI)", "am", delay=0)
                
            elif "malam" in args or "gn" in args:
                await message.channel.send("🚀 **Mengirim Pesan MALAM...**")
                await self.run_batch("MANUAL (MALAM)", "pm", delay=0)
                
            else:
                await message.channel.send("❌ Format: `!send_now pagi` atau `!send_now malam`")

        # 4. ADD DAILY
        elif cmd == "!add_daily":
            try:
                if "|" not in content:
                    await message.channel.send("❌ Error: Pisahkan pesan pagi dan malam dengan tanda `|`")
                    return

                raw_args = content[len("!add_daily"):].strip()
                left_part, msg_malam = raw_args.split("|", 1)
                msg_malam = msg_malam.strip()
                
                left_words = left_part.strip().split()
                target_ids = []
                msg_pagi_words = []
                
                found_text = False
                for word in left_words:
                    if word.isdigit() and len(word) > 15 and not found_text:
                        target_ids.append(word)
                    else:
                        found_text = True
                        msg_pagi_words.append(word)
                
                msg_pagi = " ".join(msg_pagi_words)

                if not target_ids:
                    await message.channel.send("❌ Tidak ada ID Channel.")
                    return

                msg_loading = await message.channel.send("⏳ **Memproses...**")
                
                success_lines = []
                failed_lines = []
                
                for cid in target_ids:
                    try:
                        # Coba get_channel dulu (cache)
                        chan = self.get_channel(int(cid))
                        if not chan:
                            chan = await self.fetch_channel(int(cid))
                        
                        self.daily_data[cid] = {"am": msg_pagi, "pm": msg_malam}
                        success_lines.append(f"Channel : {chan.name} ({cid})")
                    except:
                        failed_lines.append(f"ID      : {cid} (Error/Invalid)")

                self.save_data()

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
                await message.channel.send(f"❌ Error: {e}")

        # 5. REMOVE DAILY
        elif cmd == "!remove_daily":
            try:
                raw_ids = content[len("!remove_daily"):].strip().split()
                deleted = []
                for cid in raw_ids:
                    if cid in self.daily_data:
                        del self.daily_data[cid]
                        deleted.append(cid)
                self.save_data()
                await message.channel.send(f"🗑️ Menghapus {len(deleted)} jadwal.")
            except: pass

        # 6. LIST DAILY
        elif cmd == "!list_daily":
            if not self.daily_data: 
                await message.channel.send("📭 Database Kosong.")
            else:
                chunks = ["📋 **LIST JADWAL AKTIF**"]
                current_chunk = "```yaml\n"
                i = 1
                msg_wait = await message.channel.send("⏳ **Sedang memuat...**")

                for cid, m in self.daily_data.items():
                    try:
                        chan = self.get_channel(int(cid))
                        if not chan: chan = await self.fetch_channel(int(cid))
                        c_name = chan.name
                    except:
                        c_name = "⚠️ Unknown"

                    entry = (
                        f"#{i} Channel : {c_name}\n"
                        f"   ID      : {cid}\n"
                        f"   AM      : \"{m['am'][:30]}...\"\n"
                        f"   PM      : \"{m['pm'][:30]}...\"\n\n"
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
                await msg_wait.delete()
                for c in chunks: await message.channel.send(c)

        # 7. TIME
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
            await message.channel.send(msg)

    # === BATCH SENDER ===
    async def run_batch(self, type_name, key, delay=2):
        total = len(self.daily_data)
        success = 0
        failed = 0
        failed_details = []

        await self.send_log(f"⏳ **MEMULAI BATCH: {type_name}**")

        for cid, data in self.daily_data.items():
            try:
                channel = self.get_channel(int(cid))
                if not channel:
                    channel = await self.fetch_channel(int(cid))
                
                await channel.send(data[key]) 
                success += 1
                if delay > 0: await asyncio.sleep(delay)
            except Exception as e:
                failed += 1
                failed_details.append(f"- ID {cid} : {str(e)}")
        
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

    # === SCHEDULER ===
    @tasks.loop(seconds=60) 
    async def scheduler_task(self):
        now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
        current_time = now.strftime("%H:%M")

        if current_time == "07:00":
            if not self.sent_today_am: 
                await self.run_batch("AUTO (PAGI)", "am", delay=2)
                self.sent_today_am = True
                self.sent_today_pm = False 

        elif current_time == "19:00":
            if not self.sent_today_pm:
                await self.run_batch("AUTO (MALAM)", "pm", delay=2)
                self.sent_today_pm = True
                self.sent_today_am = False 
        else:
            if current_time == "07:01": self.sent_today_am = True
            if current_time == "19:01": self.sent_today_pm = True

if __name__ == "__main__":
    if DISCORD_USER_TOKEN:
        client = DailyBot()
        client.run(DISCORD_USER_TOKEN)
    else:
        print("❌ Token Discord Belum Diisi di Environment Variable!")
