# 🤖 Master News Bot — Termux Edition

Bot Telegram otomatis yang memantau **30+ sumber berita** dari seluruh dunia dan mempostingnya ke channel Telegram secara real-time.

---

## 📡 Kategori Berita

| Kategori | Sumber |
|---|---|
| 🌍 Internasional | Reuters, CNBC, MarketWatch, FT, Nikkei |
| 📈 Saham & Equities | Seeking Alpha, Benzinga, Yahoo Finance |
| 💱 Forex & Rates | ForexLive, FXStreet, DailyFX |
| 🪙 Crypto & Blockchain | CoinDesk, CoinTelegraph, Decrypt |
| 🌐 Makro & Ekonomi | IMF, World Bank, The Fed, ECB |
| ⚔️ Geopolitik & Energi | Al Jazeera, AP News, Politico |
| 🇮🇩 Indonesia | CNBC Indonesia, Bisnis.com, Kontan |

---

## ⚙️ Fitur

- ✅ **Anti-duplikat** — cek URL + kesamaan judul antar sumber
- ⏱️ **Filter waktu** — hanya kirim berita dalam N jam terakhir (default: 3 jam)
- 🔍 **Filter keyword** — hanya berita yang relevan dengan pasar keuangan
- 🌅 **Morning Briefing** otomatis jam 06:00 WIB
- 🌙 **Closing Summary** otomatis jam 18:00 WIB
- 📊 **Laporan siklus** setiap kali bot selesai fetch

---

## 🚀 Cara Install & Jalankan di Termux

### 1. Install dependensi Termux
```bash
pkg update && pkg upgrade -y
pkg install python git -y
pip install feedparser requests schedule python-dotenv
```

### 2. Clone repository
```bash
git clone https://github.com/USERNAME/REPO_NAME.git
cd REPO_NAME
```

### 3. Buat file `.env`
```bash
cp .env.example .env
nano .env
```
Isi dengan token dan channel ID Telegram kamu:
```
TELEGRAM_BOT_TOKEN=token_bot_kamu
TELEGRAM_CHANNEL_ID=@channel_kamu
```

### 4. Jalankan bot
```bash
python news_bot.py
```

### 5. Jalankan di background (opsional)
```bash
nohup python news_bot.py > /dev/null 2>&1 &
```
Untuk menghentikannya:
```bash
kill $(pgrep -f news_bot.py)
```

---

## 🔧 Konfigurasi

Edit bagian ini di `news_bot.py` sesuai kebutuhan:

```python
MAX_AGE_HOURS      = 3    # Hanya berita dalam 3 jam terakhir
FETCH_INTERVAL_MIN = 3    # Fetch setiap 3 menit
MAX_PER_SOURCE     = 15   # Maks artikel per sumber per siklus
```

---

## 📁 Struktur File

```
.
├── news_bot.py          # Script utama
├── .env                 # Token & config (JANGAN di-push ke GitHub!)
├── .env.example         # Template .env
├── .gitignore           # File yang diabaikan Git
├── seen_articles.json   # Cache artikel (auto-generated)
└── news_bot.log         # Log runtime (auto-generated)
```

---

## ⚠️ Penting

> **Jangan pernah upload file `.env` ke GitHub!**  
> File `.gitignore` sudah dikonfigurasi untuk mengabaikannya secara otomatis.

---

## 📄 Lisensi

MIT License — bebas digunakan dan dimodifikasi.
