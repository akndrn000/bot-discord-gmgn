<div align="center">

# gmgn-bot

**Self-bot Discord untuk mengirim pesan GM/GN terjadwal ke banyak channel, lengkap dengan panel kontrol lewat perintah teks.**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![discord.py-self](https://img.shields.io/badge/discord.py--self-pinned-5865F2?logo=discord&logoColor=white)
![Deploy](https://img.shields.io/badge/Deploy-Railway-0B0D0E?logo=railway&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![Lint](https://img.shields.io/badge/lint-ruff-D7FF64?logo=ruff&logoColor=black)
![License](https://img.shields.io/badge/license-MIT-green)

</div>

---

## Daftar Isi

- [Ringkasan](#ringkasan)
- [Fitur](#fitur)
- [Cara Kerja](#cara-kerja)
- [Perintah](#perintah)
- [Konfigurasi](#konfigurasi)
- [Deploy ke Railway](#deploy-ke-railway)
- [Menjalankan Secara Lokal](#menjalankan-secara-lokal)
- [Struktur Proyek](#struktur-proyek)
- [Testing dan Lint](#testing-dan-lint)
- [Troubleshooting](#troubleshooting)
- [Keamanan dan Disclaimer](#keamanan-dan-disclaimer)
- [Lisensi](#lisensi)

## Ringkasan

gmgn-bot mengirim pesan *Good Morning* (GM) dan *Good Night* (GN) otomatis pada jam yang kamu tentukan ke satu atau banyak channel Discord. Pesan dipilih secara acak berbobot (*rarity*), sehingga bentuk singkat seperti `gm` dan `gn` paling sering muncul, sementara variasi lain muncul sesekali.

Seluruh pengaturan dilakukan dari Discord sendiri lewat perintah berawalan `!` di sebuah **channel pemantau**, tanpa perlu mengedit file atau melakukan deploy ulang.

## Fitur

- **Pesan berbobot (rarity):** 12 variasi pesan GM dan 12 variasi GN. Pesan `gm` / `gn` memiliki peluang sekitar 29% per pengiriman, variasi lain lebih jarang.
- **Multi-channel:** satu jadwal dikirim ke semua channel target, dengan jeda acak 2–5 detik antar channel.
- **Jadwal fleksibel:** jam GM dan GN diatur terpisah (format 24 jam) dan mengikuti zona waktu pilihanmu.
- **Anti kirim ganda:** setiap jadwal hanya terkirim sekali per hari.
- **Laporan otomatis:** setelah tiap pengiriman, bot mengirim laporan ke channel pemantau berisi jumlah berhasil, pesan yang terkirim, dan channel yang gagal.
- **Konfigurasi persisten:** pengaturan tersimpan di `config.json` (Railway Volume di `/data`), sehingga bertahan saat restart maupun redeploy.
- **Akses terkunci:** perintah hanya diproses dari pesan akun pemilik token, dan hanya di channel pemantau.
- **Siap produksi:** kode modular, ber-tes, dilengkapi `Dockerfile` dan `railway.json` dengan kebijakan restart otomatis.

## Cara Kerja

```mermaid
flowchart LR
    A[Bot aktif] --> B[Kirim menu ke channel pemantau]
    B --> C{Cek jadwal tiap 20 detik}
    C -->|Jam GM/GN tiba, belum terkirim hari ini| D[Pilih pesan acak berbobot]
    D --> E[Kirim ke tiap channel target, jeda 2-5 detik]
    E --> F[Laporan ke channel pemantau]
    F --> C
    C -->|Belum waktunya| C
```

Aturan penjadwalan:

- Bot memeriksa jadwal setiap **20 detik**.
- Pesan dikirim bila waktu sekarang berada dalam jendela **0–15 menit setelah** jam jadwal dan belum terkirim pada tanggal tersebut. Jendela ini membuat jadwal tetap terkirim walau bot baru menyala beberapa menit setelah jamnya.
- Bila tidak ada channel target, tidak ada yang dikirim.
- Zona waktu tidak valid otomatis memakai `Asia/Jakarta`.

Contoh laporan yang muncul di channel pemantau:

```text
📊 LAPORAN BROADCAST: GM (Otomatis)
• Status: Selesai (2/2 berhasil)

📝 Detail Pesan Terkirim:
• #general (`#general`): `gm`
• #chat (`#chat`): `gm frens`
```

## Perintah

Semua perintah diketik **di channel pemantau**, dari akun yang sama dengan token bot.

| Perintah | Fungsi | Contoh |
| --- | --- | --- |
| `!menu` | Menampilkan daftar perintah | `!menu` |
| `!set <id> [<id> ...]` | Menambah satu atau banyak channel target | `!set 1234567890 0987654321` |
| `!stop <id>` | Menghapus satu channel dari target | `!stop 1234567890` |
| `!time gm:<jam>, gn:<jam>` | Mengatur jam GM dan/atau GN (24 jam, pemisah `.` atau `:`) | `!time gm:07.00, gn:19.00` |
| `!list` | Menampilkan jadwal aktif dan daftar ID target | `!list` |
| `!test gm` / `!test gn` | Menjalankan pengiriman manual ke semua target untuk uji coba | `!test gm` |

Catatan:

- `!time` boleh hanya berisi salah satu, misalnya `!time gn:21.30`. Bagian yang tidak diberikan tidak berubah.
- Nilai awal bila belum pernah diatur: GM `07:00`, GN `19:00`, tanpa channel target.
- `!set` dan `!stop` hanya menerima ID berupa angka.

## Konfigurasi

### Environment variable

| Variabel | Wajib | Default | Keterangan |
| --- | --- | --- | --- |
| `DISCORD_USER_TOKEN` | Ya | kosong | Token akun Discord. Bila kosong, bot berhenti tanpa pesan error |
| `MONITOR_CHANNEL_ID` | Disarankan | `0` | ID channel pemantau. Isi `0` agar perintah berlaku di semua channel dan laporan tidak dikirim ke Discord |
| `TIMEZONE` | Tidak | `Asia/Jakarta` | Zona waktu jadwal, misalnya `Asia/Makassar`, `Asia/Jayapura`, `UTC` |

> `MONITOR_CHANNEL_ID` harus berupa angka murni. Nilai berisi huruf atau spasi membuat bot berhenti saat startup.

`.env.example` hanya berfungsi sebagai contoh. Bot **tidak** membaca file `.env` otomatis, jadi nilai harus diisi lewat Railway Variables atau diatur di shell (lihat [Menjalankan Secara Lokal](#menjalankan-secara-lokal)).

### File konfigurasi

Pengaturan dari perintah disimpan ke `config.json`:

```json
{
    "gm_time": "07:00",
    "gn_time": "19:00",
    "target_channels": [1234567890, 987654321]
}
```

Lokasi file: `/data/config.json` bila folder `/data` ada (Railway Volume), jika tidak `./config.json` di direktori kerja.

## Deploy ke Railway

1. Push repositori ini ke GitHub.
2. Di [Railway](https://railway.app/), buat proyek baru dengan **Deploy from GitHub repo** dan pilih repositori ini. Railway otomatis memakai `Dockerfile` dan `railway.json`.
3. Buka tab **Variables**, lalu isi `DISCORD_USER_TOKEN`, `MONITOR_CHANNEL_ID`, dan `TIMEZONE`.
4. Tambahkan **Volume** dan arahkan *mount path* ke `/data` agar jadwal dan daftar channel tidak hilang saat redeploy.
5. Tunggu deployment berstatus **Active**. Bila berhasil, menu bot muncul di channel pemantau.

Perilaku deploy yang sudah diatur di `railway.json`: build dengan Dockerfile, start command `python -m gmgn_bot`, dan restart otomatis saat gagal (maksimal 10 kali).

> Jangan mengisi *Custom Start Command* di dashboard Railway dengan awalan `PYTHONPATH=...`. Railway menjalankannya tanpa shell sehingga muncul error `The executable pythonpath=src could not be found`. Paket sudah terpasang lewat `pip install .` di Dockerfile, jadi tidak diperlukan.

## Menjalankan Secara Lokal

Prasyarat: Python 3.10+ dan Git (dependensi `discord.py-self` diambil dari GitHub).

```bash
git clone https://github.com/akndrn000/gmgn-bot.git
cd gmgn-bot
python -m venv .venv
```

Aktifkan virtual environment, lalu pasang dependensi:

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
pip install -e .
```

Atur variabel lalu jalankan:

```powershell
# Windows (PowerShell)
$env:DISCORD_USER_TOKEN = "token_anda"
$env:MONITOR_CHANNEL_ID = "123456789012345678"
$env:TIMEZONE = "Asia/Jakarta"
python -m gmgn_bot
```

```bash
# Linux / macOS
export DISCORD_USER_TOKEN="token_anda"
export MONITOR_CHANNEL_ID="123456789012345678"
export TIMEZONE="Asia/Jakarta"
python -m gmgn_bot
```

Dengan Docker:

```bash
docker build -t gmgn-bot .
docker run --rm -e DISCORD_USER_TOKEN=... -e MONITOR_CHANNEL_ID=... -e TIMEZONE=Asia/Jakarta gmgn-bot
```

## Struktur Proyek

```text
gmgn-bot/
├── src/gmgn_bot/
│   ├── __main__.py        # Titik masuk: python -m gmgn_bot
│   ├── settings.py        # Membaca environment variable
│   ├── storage.py         # Baca/tulis config.json
│   ├── messages.py        # Daftar pesan GM/GN, bobot rarity, teks menu
│   ├── scheduler.py       # Aturan jadwal dan pengiriman broadcast
│   ├── commands.py        # Handler perintah !menu !set !time !list !stop !test
│   ├── client.py          # Client Discord, event on_ready/on_message, loop jadwal
│   └── logging_setup.py   # Konfigurasi logging
├── tests/                 # Tes pytest
├── .env.example           # Contoh variabel lingkungan
├── Dockerfile             # Image container
├── Procfile               # Perintah worker
├── railway.json           # Konfigurasi build dan deploy Railway
├── pyproject.toml         # Metadata paket, konfigurasi ruff dan pytest
├── requirements.txt       # Dependensi runtime (versi disematkan)
└── requirements-dev.txt   # Dependensi development
```

## Testing dan Lint

```bash
pip install -r requirements-dev.txt
pytest
ruff check .
ruff format --check .
```

Tes mencakup parser perintah, aturan jadwal, pemilihan pesan berbobot, penyimpanan konfigurasi, dan konfigurasi deploy. Tidak ada tes yang terhubung ke Discord.

## Troubleshooting

| Gejala | Kemungkinan penyebab | Solusi |
| --- | --- | --- |
| Deploy gagal: `The executable pythonpath=src could not be found` | Custom Start Command lama di dashboard Railway | Kosongkan atau ganti menjadi `python -m gmgn_bot` di Settings → Deploy |
| Deploy **Active** tetapi tidak ada menu di Discord | Token kosong, salah, atau sudah kedaluwarsa; `MONITOR_CHANNEL_ID` salah; akun tidak punya akses ke channel itu | Periksa Variables dan Deploy Logs, pastikan token masih berlaku |
| Bot langsung berhenti saat start | `MONITOR_CHANNEL_ID` bukan angka | Isi dengan ID channel berupa angka |
| Perintah `!` tidak direspons | Perintah diketik di luar channel pemantau atau dari akun lain | Ketik di channel pemantau memakai akun pemilik token |
| Jadwal tidak terkirim | Belum ada channel target, atau jam sudah lewat lebih dari 15 menit | Cek `!list`, tambahkan target dengan `!set`, uji dengan `!test gm` |
| Jadwal bergeser jamnya | `TIMEZONE` tidak sesuai | Atur `TIMEZONE` yang benar, mis. `Asia/Makassar` |
| Konfigurasi hilang setelah redeploy | Volume belum terpasang di `/data` | Tambahkan Volume dengan mount path `/data` |

## Keamanan dan Disclaimer

- **Self-bot melanggar Terms of Service Discord.** Memakai token akun pengguna untuk otomatisasi dapat berujung pada pembatasan atau penonaktifan akun. Gunakan dengan risiko sendiri, dan sebaiknya bukan pada akun utama yang penting.
- Perlakukan token seperti kata sandi: jangan dibagikan, jangan di-commit ke repositori, dan jangan ditempel di issue atau tangkapan layar. Isi hanya lewat environment variable. Bila token bocor, segera amankan akun dan ganti kata sandi.
- Jaga agar repositori dan log tidak memuat token. `.gitignore` sudah menyiapkan pengecualian umum, tetapi tetap periksa sebelum push.
- Proyek ini tidak berafiliasi dengan, disponsori, atau didukung oleh Discord Inc. maupun Railway Corp. Seluruh nama dan merek dagang adalah milik pemiliknya masing-masing.
- Perangkat lunak disediakan apa adanya, tanpa jaminan apa pun.

## Lisensi

Dirilis di bawah [Lisensi MIT](./LICENSE).
