import os
import discord
import asyncio
import json
import datetime
from datetime import datetime, timedelta
from discord.ext import tasks

# === KONFIGURASI ===
DISCORD_USER_TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
TIMEZONE_OFFSET = 7  # WIB (Indonesia Barat)

print(r'''
 🌅 DAILY BOT - ULTIMATE EDITION
''')

DB_FILE = "daily_list.json"

class DailyBot(discord.Client):
    def __init__(self):
        super().__init__()
        self.daily_data = self.load_data()
        self.sent_today_am = False 
        self.sent_today_pm = False
        self.log_channel = None 

    def load_data(self):
        """Load database agar jadwal tersimpan selamanya"""
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r") as f: return json.load(f)
            except: return {}
        return {}

    def save_data(self):
        with open(DB_FILE, "w") as f:
            json.dump(self.daily_data, f, indent=4)

    async def send_log(self, message):
        """Kirim laporan ke channel pantau"""
        if not LOG_CHANNEL_ID: 
            print(f"[CONSOLE] {message}")
            return
        try:
            if not self.log_channel:
                self.log_channel = await self.fetch_channel(int(LOG_CHANNEL_ID))
            await self.log_channel.send(message)
        except: pass

    async def on_ready(self):
        print(f"[✅] Login sebagai {self.user}")
        
        # === MENU STARTUP ===
        menu_msg = (
            "✅ **SYSTEM ONLINE** - DAILY SCHEDULER\n"
            "------------------------------------------\n"
            "💡 **DAFTAR PERINTAH UTAMA:**\n"
            "1. `!add_daily [ID1] [ID2]... [PesanPagi] | [PesanMalam]`\n"
            "   *(Input sekali, jalan selamanya tiap hari)*\n"
            "2. `!remove_daily [ID]` : 🗑️ Hapus Jadwal\n"
            "3. `!list_daily`        : 📋 Cek Daftar Channel\n"
            "4. `!force_run`         : 🚀 Test Kirim Sekarang (Cek Error)\n"
            "5. `!time`              : ⏰ Cek Waktu Bot\n"
            "------------------------------------------\n"
            f"📅 **Status Database:** {len(self.daily_data)} Channel Aktif"
        )
        await self.send_log(menu_msg)

        if not self.scheduler_task.is_running():
            self.scheduler_task.start()

    async def on_message(self, message):
        if message.author.id != self.user.id: return
        content = message.content.strip()
        cmd = content.split(" ")[0].lower()

        # === 1. ADD JADWAL (VERIFIKASI & BULK) ===
        if cmd == "!add_daily":
            try:
                if "|" not in content:
                    await message.reply("❌ Error: Pisahkan pesan pagi dan malam dengan `|`")
                    return

                # Parsing Input
                raw_args = content[len("!add_daily"):].strip()
                left_part, msg_malam = raw_args.split("|", 1)
                msg_malam = msg_malam.strip()
                
                left_words = left_part.strip().split()
                target_ids = []
                msg_pagi_words = []
                
                # Pisahkan ID (Angka) dengan Kata-kata Pesan
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

                # === PROSES VERIFIKASI ===
                msg_loading = await message.reply("⏳ **Sedang memverifikasi ID Channel...**")
                
                success_list = []
                failed_list = []

                for cid in target_ids:
                    try:
                        # Cek apakah channel valid dan bisa diakses
                        chan = await self.fetch_channel(int(cid))
                        
                        # Ambil nama Server/Grup
                        if hasattr(chan, 'guild'): server_name = chan.guild.name
                        elif hasattr(chan, 'recipient'): server_name = f"DM: {chan.recipient.name}"
                        else: server_name = "Group DM"
                        
                        # Simpan ke Database
                        self.daily_data[cid] = {"am": msg_pagi, "pm": msg_malam}
                        
                        # Tambahkan ke Laporan Sukses
                        success_list.append(f"✅ **{server_name}** | `#{chan.name}`")
                    except:
                        # Jika gagal (ID Salah / Tidak ada akses)
                        failed_list.append(f"❌ ID: `{cid}` (Tidak Ditemukan/No Access)")

                self.save_data()
                
                # === BUAT LAPORAN ===
                report_msg = f"📝 **LAPORAN INPUT JADWAL**\n\n"
                
                if success_list:
                    report_msg += "**BERHASIL:**\n" + "\n".join(success_list)
                
                if failed_list:
                    report_msg += "\n\n**GAGAL:**\n" + "\n".join(failed_list)

                report_msg += f"\n\n⚙️ **Pesan Diset:**\n☀️ `{msg_pagi}`\n🌙 `{msg_malam}`"
                
                # Kirim laporan (potong jika terlalu panjang buat Discord)
                if len(report_msg) > 1900: 
                    report_msg = report_msg[:1900] + "\n...(List terpotong)"
                
                await msg_loading.edit(content=report_msg)
                await self.send_log(f"📝 **Database Update:** {len(success_list)} channel baru ditambahkan.")

            except Exception as e:
                await message.reply(f"❌ Error: {e}")

        # === 2. REMOVE JADWAL ===
        elif cmd == "!remove_daily":
            try:
                raw_ids = content[len("!remove_daily"):].strip().split()
                deleted = []
                for cid in raw_ids:
                    if cid in self.daily_data:
                        del self.daily_data[cid]
                        deleted.append(cid)
                
                self.save_data()
                await message.reply(f"🗑️ Dihapus: {len(deleted)} jadwal.")
            except: pass

        # === 3. LIST JADWAL ===
        elif cmd == "!list_daily":
            if not self.daily_data: 
                await message.reply("📭 Database Kosong.")
            else:
                chunks = ["**📅 DAFTAR JADWAL AKTIF:**\n"]
                curr = chunks[0]
                for cid, m in self.daily_data.items():
                    line = f"<#{cid}> : `{m['am']}` | `{m['pm']}`\n"
                    if len(curr) + len(line) > 1900: 
                        chunks.append(line)
                        curr = line
                    else: 
                        curr += line
                        chunks[-1] = curr
                
                for c in chunks: await message.reply(c)

        # === 4. MANUAL TEST (FORCE RUN) ===
        elif cmd == "!force_run":
             await message.reply("🚀 **Memulai Manual Run (Test)...**")
             await self.run_batch("MANUAL TEST", "am")

        # === 5. CEK WAKTU ===
        elif cmd == "!time":
            now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
            await message.reply(f"⏰ Jam Bot (WIB): `{now.strftime('%H:%M:%S')}`")

    # === FUNGSI EKSEKUTOR BATCH (DENGAN LAPORAN DETIL) ===
    async def run_batch(self, type_name, key):
        total = len(self.daily_data)
        success = 0
        failed = 0
        failed_details = [] # Nampung siapa aja yang gagal
        
        await self.send_log(f"⏳ **MEMULAI BATCH: {type_name}**\nTarget: {total} Channel")

        for cid, data in self.daily_data.items():
            try:
                channel = await self.fetch_channel(int(cid))
                await channel.send(data[key])
                success += 1
                await asyncio.sleep(2) # Delay biar aman
            except Exception as e:
                failed += 1
                # Analisa Error
                err_msg = str(e)
                if "Forbidden" in err_msg: reason = "Tidak ada izin chat"
                elif "NotFound" in err_msg: reason = "Channel Dihapus"
                else: reason = "Error Lain"
                
                failed_details.append(f"❌ <#{cid}> ({cid}) -> {reason}")
                print(f"Gagal {cid}: {e}")
        
        # Buat Laporan Akhir
        report = (
            f"✅ **BATCH SELESAI: {type_name}**\n"
            f"📊 **Statistik:**\n"
            f"✅ Sukses : {success}\n"
            f"❌ Gagal  : {failed}\n"
            f"--------------------------"
        )

        # Lampirkan daftar yang gagal (jika ada)
        if failed_details:
            report += "\n\n⚠️ **DAFTAR KEGAGALAN:**\n"
            chunk_fail = ""
            for line in failed_details:
                if len(report) + len(chunk_fail) + len(line) > 1900:
                    await self.send_log(report + chunk_fail)
                    report = "⚠️ **(Lanjutan Gagal)...**\n"
                    chunk_fail = ""
                chunk_fail += line + "\n"
            report += chunk_fail

        await self.send_log(report)

    @tasks.loop(seconds=60) 
    async def scheduler_task(self):
        now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
        current_time = now.strftime("%H:%M")

        # === JAM 07:00 PAGI ===
        if current_time == "07:00":
            if not self.sent_today_am: 
                await self.run_batch("☀️ GM / PAGI", "am")
                self.sent_today_am = True
                self.sent_today_pm = False 

        # === JAM 19:00 MALAM ===
        elif current_time == "19:00":
            if not self.sent_today_pm:
                await self.run_batch("🌙 GN / MALAM", "pm")
                self.sent_today_pm = True
                self.sent_today_am = False 

        # Reset flag
        else:
            if current_time == "07:01": self.sent_today_am = True
            if current_time == "19:01": self.sent_today_pm = True

if __name__ == "__main__":
    if DISCORD_USER_TOKEN:
        client = DailyBot()
        client.run(DISCORD_USER_TOKEN)
    else:
        print("❌ Token Discord Belum Diisi")
