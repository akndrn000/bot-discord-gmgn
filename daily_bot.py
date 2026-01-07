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
 🌅 DAILY BOT - TURBO & CLEANER
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
            "✅ **SYSTEM ONLINE** (TURBO + CLEANER)\n"
            "------------------------------------------\n"
            "💡 **DAFTAR PERINTAH:**\n"
            "1. `!add_daily [ID]... [PesanPagi] | [PesanMalam]`\n"
            "2. `!send_now [pagi/malam]` : 🚀 Kirim INSTAN (Turbo)\n"
            "3. `!remove_daily [ID]`     : 🗑️ Hapus Jadwal\n"
            "4. `!clear`                 : 🧹 Hapus 30 Pesan Terakhir\n"
            "5. `!list_daily`            : 📋 Cek List\n"
            "6. `!time`                  : ⏰ Cek Waktu\n"
            "------------------------------------------"
        )
        await self.send_log(menu)

        if not self.scheduler_task.is_running():
            self.scheduler_task.start()

    async def on_message(self, message):
        if message.author.id != self.user.id: return
        content = message.content.strip()
        cmd = content.split(" ")[0].lower()

        # === 1. FITUR CLEAR / PEMBERSIH ===
        if cmd == "!clear":
            # Info awal
            info = await message.reply("🧹 **Membersihkan 30 pesan terakhir...** (Mode Aman)")
            await asyncio.sleep(2) 

            deleted_count = 0
            # Hapus 30 pesan terakhir di channel ini
            async for msg in message.channel.history(limit=30):
                try:
                    await msg.delete()
                    deleted_count += 1
                    # Jeda wajib 1.5 detik agar akun tidak kena ban Discord
                    await asyncio.sleep(1.5) 
                except: 
                    pass
            
            # Lapor ke log (karena pesan di channel target sudah hilang)
            await self.send_log(f"🧹 **Cleaner:** Menghapus {deleted_count} pesan di <#{message.channel.id}>.")

        # === 2. KIRIM MANUAL SEKARANG (MODE NGEBUT) ===
        elif cmd == "!send_now":
            args = content[len("!send_now"):].strip().lower()
            
            if "pagi" in args or "gm" in args:
                await message.reply("🚀 **Mengirim Pesan PAGI (Mode Cepat)...**")
                # delay=0 artinya TIDAK MENUNGGU SAMA SEKALI
                await self.run_batch("MANUAL (PAGI)", "am", delay=0)
                
            elif "malam" in args or "gn" in args:
                await message.reply("🚀 **Mengirim Pesan MALAM (Mode Cepat)...**")
                # delay=0 artinya TIDAK MENUNGGU SAMA SEKALI
                await self.run_batch("MANUAL (MALAM)", "pm", delay=0)
                
            else:
                await message.reply("❌ Format: `!send_now pagi` atau `!send_now malam`")

        # === 3. ADD JADWAL ===
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

                msg_loading = await message.reply("⏳ **Verifikasi...**")
                
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

        # === 4. REMOVE ===
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

        # === 5. LIST ===
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

        # === 6. TIME ===
        elif cmd == "!time":
            now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
            await message.reply(f"⏰ `{now.strftime('%H:%M:%S')}`")

    # === CORE: EKSEKUSI PESAN (DENGAN PENGATUR KECEPATAN) ===
    async def run_batch(self, type_name, key, delay=2):
        """
        delay=2 : Mode Aman (Jadwal Otomatis)
        delay=0 : Mode Turbo (Manual !send_now)
        """
        total = len(self.daily_data)
        success = 0
        failed = 0
        failed_details = []

        await self.send_log(f"⏳ **MEMULAI BATCH: {type_name}**\nTarget: {total} Channel\nKecepatan: {'⚡ INSTAN' if delay==0 else '🐢 AMAN (2s)'}")

        for cid, data in self.daily_data.items():
            try:
                channel = await self.fetch_channel(int(cid))
                await channel.send(data[key]) 
                success += 1
                
                if delay > 0: await asyncio.sleep(delay)
                    
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

        if len(report) > 1900:
            await self.send_log(report[:1900] + "\n...(Report Terpotong)")
        else:
            await self.send_log(report)

    # === SCHEDULE OTOMATIS (TETAP PAKAI DELAY BIAR AMAN) ===
    @tasks.loop(seconds=60) 
    async def scheduler_task(self):
        now = datetime.utcnow() + timedelta(hours=TIMEZONE_OFFSET)
        current_time = now.strftime("%H:%M")

        # JAM 07:00 (Otomatis - Pakai Delay 2 detik)
        if current_time == "07:00":
            if not self.sent_today_am: 
                await self.run_batch("☀️ AUTO SCHEDULE (PAGI)", "am", delay=2)
                self.sent_today_am = True; self.sent_today_pm = False 

        # JAM 19:00 (Otomatis - Pakai Delay 2 detik)
        elif current_time == "19:00":
            if not self.sent_today_pm:
                await self.run_batch("🌙 AUTO SCHEDULE (MALAM)", "pm", delay=2)
                self.sent_today_pm = True; self.sent_today_am = False 

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
