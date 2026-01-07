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
TIMEZONE_OFFSET = 7  # WIB

print(r'''
 🌅 DAILY BOT - BROADCAST EDITION
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
        if os.path.exists(DB_FILE):
            try:
                with open(DB_FILE, "r") as f: return json.load(f)
            except: return {}
        return {}

    def save_data(self):
        with open(DB_FILE, "w") as f:
            json.dump(self.daily_data, f, indent=4)

    async def send_log(self, message):
        if not LOG_CHANNEL_ID: return
        try:
            if not self.log_channel:
                self.log_channel = await self.fetch_channel(int(LOG_CHANNEL_ID))
            await self.log_channel.send(message)
        except: pass

    async def on_ready(self):
        print(f"[✅] Login sebagai {self.user}")
        
        menu = (
            "✅ **SYSTEM ONLINE**\n"
            "------------------------------------------\n"
            "💡 **DAFTAR PERINTAH:**\n"
            "1. `!add_daily [ID]... [PesanPagi] | [PesanMalam]`\n"
            "2. `!send_now [pagi/malam]` : 🚀 Kirim Manual SEKARANG\n"
            "3. `!remove_daily [ID]`     : 🗑️ Hapus Jadwal\n"
            "4. `!list_daily`            : 📋 Cek List\n"
            "5. `!time`                  : ⏰ Cek Waktu\n"
            "------------------------------------------"
        )
        await self.send_log(menu)

        if not self.scheduler_task.is_running():
            self.scheduler_task.start()

    async def on_message(self, message):
        if message.author.id != self.user.id: return
        content = message.content.strip()
        cmd = content.split(" ")[0].lower()

        # === 1. KIRIM MANUAL SEKARANG (FITUR BARU) ===
        if cmd == "!send_now":
            # Cek argumen: maunya pagi atau malam?
            args = content[len("!send_now"):].strip().lower()
            
            if "pagi" in args or "gm" in args:
                await message.reply("🚀 **Memulai Broadcast Manual (Pesan PAGI)...**")
                # Parameter "am" mengambil pesan pagi dari database
                await self.run_batch("MANUAL BROADCAST (PAGI)", "am")
                
            elif "malam" in args or "gn" in args:
                await message.reply("🚀 **Memulai Broadcast Manual (Pesan MALAM)...**")
                # Parameter "pm" mengambil pesan malam dari database
                await self.run_batch("MANUAL BROADCAST (MALAM)", "pm")
                
            else:
                await message.reply("❌ **Format Salah!**\nGunakan:\n`!send_now pagi` (Kirim pesan GM)\n`!send_now malam` (Kirim pesan GN)")

        # === 2. ADD JADWAL ===
        elif cmd == "!add_daily":
            try:
                if "|" not in content:
                    await message.reply("❌ Error: Pisahkan pesan dengan `|`")
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
                    await message.reply("❌ Tidak ada ID Channel.")
                    return

                msg_loading = await message.reply("⏳ **Memverifikasi...**")
                
                success_lines = []
                failed_lines = []
                
                for cid in target_ids:
                    try:
                        chan = await self.fetch_channel(int(cid))
                        if hasattr(chan, 'guild'): server = chan.guild.name
                        elif hasattr(chan, 'recipient'): server = f"DM: {chan.recipient.name}"
                        else: server = "Group DM"
                            
                        self.daily_data[cid] = {"am": msg_pagi, "pm": msg_malam}
                        success_lines.append(f"✅ **{server}** | `#{chan.name}`")
                    except:
                        failed_lines.append(f"❌ ID `{cid}` (Gagal Akses)")

                self.save_data()

                report = "📝 **LAPORAN INPUT:**\n\n"
                if success_lines: report += "**BERHASIL:**\n" + "\n".join(success_lines) + "\n"
                if failed_lines: report += "\n**GAGAL:**\n" + "\n".join(failed_lines) + "\n"
                
                report += f"\n⚙️ **Pesan:**\n☀️ `{msg_pagi}`\n🌙 `{msg_malam}`"
                if len(report) > 1900: report = report[:1900] + "\n...(Terpotong)"
                
                await msg_loading.edit(content=report)
                await self.send_log(f"📝 Added {len(success_lines)} channels.")

            except Exception as e:
                await message.reply(f"❌ Error: {e}")

        # === 3. REMOVE ===
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

        # === 4. LIST ===
        elif cmd == "!list_daily":
            if not self.daily_data: await message.reply("📭 Database Kosong.")
            else:
                chunks = ["**📅 LIST JADWAL:**\n"]
                curr = chunks[0]
                for cid, m in self.daily_data.items():
                    line = f"• <#{cid}> : `{m['am']}` | `{m['pm']}`\n"
                    if len(curr) + len(line) > 1900: 
                        chunks.append(line); curr = line
                    else: curr += line; chunks[-1] = curr
                for c in chunks: await message.reply(c)

        # === 5. TIME ===
        elif cmd == "!time":
            now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
            await message.reply(f"⏰ `{now.strftime('%H:%M:%S')}`")

    # === CORE: EKSEKUSI PESAN ===
    async def run_batch(self, type_name, key):
        """Fungsi ini dipanggil oleh Manual Command ATAU Otomatis Schedule"""
        total = len(self.daily_data)
        success = 0
        failed = 0
        failed_details = []

        await self.send_log(f"⏳ **MEMULAI BATCH: {type_name}**\nTarget: {total} Channel")

        for cid, data in self.daily_data.items():
            try:
                channel = await self.fetch_channel(int(cid))
                await channel.send(data[key]) # key = 'am' atau 'pm'
                success += 1
                await asyncio.sleep(2) # Delay aman
            except Exception as e:
                failed += 1
                err_msg = str(e)
                if "Forbidden" in err_msg: reason = "No Permission"
                elif "NotFound" in err_msg: reason = "Channel Hilang"
                else: reason = "Error"
                failed_details.append(f"❌ <#{cid}> -> {reason}")
        
        report = (
            f"✅ **BATCH SELESAI: {type_name}**\n"
            f"📊 **Statistik:**\n"
            f"✅ Sukses : {success}\n"
            f"❌ Gagal  : {failed}\n"
            f"--------------------------"
        )

        if failed_details:
            report += "\n\n⚠️ **GAGAL:**\n" + "\n".join(failed_details)

        # Kirim laporan akhir (potong jika kepanjangan)
        if len(report) > 1900:
            await self.send_log(report[:1900] + "\n...(Report Terpotong)")
        else:
            await self.send_log(report)

    # === SCHEDULE OTOMATIS ===
    @tasks.loop(seconds=60) 
    async def scheduler_task(self):
        now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
        current_time = now.strftime("%H:%M")

        # JAM 07:00 (Otomatis)
        if current_time == "07:00":
            if not self.sent_today_am: 
                await self.run_batch("☀️ AUTO SCHEDULE (PAGI)", "am")
                self.sent_today_am = True; self.sent_today_pm = False 

        # JAM 19:00 (Otomatis)
        elif current_time == "19:00":
            if not self.sent_today_pm:
                await self.run_batch("🌙 AUTO SCHEDULE (MALAM)", "pm")
                self.sent_today_pm = True; self.sent_today_am = False 

        # Reset flag harian
        else:
            if current_time == "07:01": self.sent_today_am = True
            if current_time == "19:01": self.sent_today_pm = True

if __name__ == "__main__":
    if DISCORD_USER_TOKEN:
        client = DailyBot()
        client.run(DISCORD_USER_TOKEN)
    else:
        print("❌ Token Discord Belum Diisi")
