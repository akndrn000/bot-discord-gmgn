# 🤖 Discord Automated GM/GN Self-Bot

Self-bot Discord otomatis untuk mengirimkan pesan *Good Morning* (GM) dan *Good Night* (GN) secara berkala ke daftar target *channel* dengan sistem variasi bobot (*rarity*). Dilengkapi dengan panel kontrol berbasis perintah teks yang hanya bisa diakses melalui *channel* pemantau khusus.

---

## 📌 Fitur Utama

* **Sistem Rarity Pesan:** Pesan singkat yang natural (`gm` / `gn`) diatur agar muncul lebih sering, sementara variasi kalimat lain muncul secara acak sebagai selingan.
* **Multi-Channel Target:** Mendukung pengiriman ke banyak *channel* sekaligus dengan jeda waktu acak (*human-like delay*) untuk mencegah deteksi spam.
* **Manajemen Perintah Praktis:** Mengontrol penambahan, penghapusan, dan pengecekan jadwal langsung dari *channel* pemantau.
* **Railway Volume Support:** Konfigurasi tersimpan secara aman menggunakan penyimpanan persisten (`/data/config.json`) sehingga tidak hilang saat bot direstart atau *re-deploy*.
* **Strict Monitoring Channel:** Perintah admin terkunci secara ketat dan hanya merespons di *channel* pemantau yang telah ditentukan.

---

## 🛠️ Daftar Perintah (`!`)

Ketik perintah berikut **hanya di dalam *channel* pemantau**:

| Perintah | Deskripsi | Contoh Penggunaan |
| :--- | :--- | :--- |
| `!menu` | Menampilkan panduan menu bantuan. | `!menu` |
| `!set` | Menambahkan satu atau banyak ID *channel* target. | `!set 1234567890 0987654321` |
| `!time` | Mengatur jam pengiriman otomatis GM dan GN. | `!time gm:07.00, gn:19.00` |
| `!list` | Menampilkan konfigurasi aktif dan daftar ID target. | `!list` |
| `!stop` | Menghapus ID *channel* dari daftar target. | `!stop 1234567890` |

---

## ⚙️ Environment Variables (Railway)

Sebelum menjalankan bot, pastikan kamu telah mengatur variabel lingkungan berikut di dashboard Railway:

| Nama Variabel | Contoh Nilai | Keterangan |
| :--- | :--- | :--- |
| `DISCORD_USER_TOKEN` | `MTI3...` | Token akun Discord pribadi (ambil dari tab Network F12 browser). |
| `MONITOR_CHANNEL_ID` | `123456789012345678` | ID *channel* tempat bot mengirim status aktif dan menerima perintah. |
| `TIMEZONE` | `Asia/Jakarta` | Zona waktu patokan jadwal (`Asia/Jakarta`, `Asia/Makassar`, dll). |

---

## 🚀 Panduan Instalasi & Deployment (Railway)

1. Buat direktori proyek baru di komputer Anda, lalu masukkan file-file utama:
   * `src/gmgn_bot/` (kode bot)
   * `requirements.txt`
   * `Dockerfile`
   * `Procfile`
2. Buat repositori baru di GitHub dan *push* seluruh file tersebut ke dalam repositori Anda.
3. Buka [Railway](https://railway.app/), buat proyek baru, lalu pilih **Deploy from GitHub repo** dan hubungkan ke repositori bot Anda.
4. Masuk ke menu **Variables** di proyek Railway Anda, lalu tambahkan variabel lingkungan (`DISCORD_USER_TOKEN`, `MONITOR_CHANNEL_ID`, dan `TIMEZONE`).
5. Bot akan otomatis melakukan *build* dan berjalan secara stabil.

---

## 📦 Struktur Berkas Proyek

```text
├── src/gmgn_bot/        # Kode bot (logika per modul)
│   ├── __init__.py      # Ekspor publik paket
│   ├── __main__.py      # Titik masuk: python -m gmgn_bot
│   ├── settings.py      # Baca dan validasi env var (satu tempat)
│   ├── storage.py       # Baca/tulis config.json (skema sama persis)
│   ├── messages.py      # Kumpulan pesan + pemilihan rarity
│   ├── scheduler.py     # Logika jadwal dan pengiriman berkala
│   ├── commands.py      # Parser dan handler perintah !menu/!set/!time/!list/!stop
│   ├── client.py        # Pembuatan client Discord dan event handler tipis
│   └── logging_setup.py # Konfigurasi logging
├── tests/               # Tes perilaku (pytest)
├── .env.example         # Contoh variabel lingkungan (tanpa token asli)
├── pyproject.toml       # Konfigurasi ruff dan pytest
├── requirements.txt     # Daftar dependensi runtime (versi disematkan)
├── requirements-dev.txt # Dependensi development (pytest, ruff)
├── Dockerfile           # Konfigurasi container untuk Docker/Railway
└── Procfile             # Perintah eksekusi worker
```

---

## 💻 Cara Menjalankan Lokal

```bash
pip install -r requirements.txt
pip install -e .
set DISCORD_USER_TOKEN=token_anda & set MONITOR_CHANNEL_ID=123 & set TIMEZONE=Asia/Jakarta
python -m gmgn_bot
```

## ✅ Cara Menjalankan Tes & Lint

```bash
pip install -r requirements-dev.txt
pytest
ruff check .
ruff format --check .
```
