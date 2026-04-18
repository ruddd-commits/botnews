"""
╔══════════════════════════════════════════════════════════════╗
║         MASTER NEWS BOT — SAHAM • FOREX • CRYPTO • MAKRO     ║
║         Telegram Channel Auto-Poster  |  Termux Edition      ║
╚══════════════════════════════════════════════════════════════╝
"""

import feedparser
import requests
import schedule
import time
import hashlib
import json
import os
import re
import sys
import logging
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
#  KONFIGURASI
# ─────────────────────────────────────────────
BOT_TOKEN            = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHANNEL_ID           = os.getenv("TELEGRAM_CHANNEL_ID", "")
SEEN_FILE            = "seen_articles.json"
MAX_PER_SOURCE       = 15
FETCH_INTERVAL_MIN   = 3
REQUEST_TIMEOUT      = 10
DELAY_BETWEEN_SEND   = 2
MAX_AGE_HOURS        = 3

# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("news_bot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def validate_config():
    if not BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN belum diisi di .env!")
        sys.exit(1)
    if not CHANNEL_ID:
        log.error("TELEGRAM_CHANNEL_ID belum diisi di .env!")
        sys.exit(1)
    log.info(f"Config OK — Channel: {CHANNEL_ID}")


# ─────────────────────────────────────────────
#  MASTER SOURCE LIST
# ─────────────────────────────────────────────
SOURCES = {
    "🌍 INTERNASIONAL": [
        {"name": "Reuters",        "url": "https://feeds.reuters.com/reuters/topNews"},
        {"name": "Reuters Bisnis", "url": "https://feeds.reuters.com/reuters/businessNews"},
        {"name": "CNBC",           "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html"},
        {"name": "CNBC World",     "url": "https://www.cnbc.com/id/100727362/device/rss/rss.html"},
        {"name": "MarketWatch",    "url": "https://feeds.marketwatch.com/marketwatch/topstories/"},
        {"name": "Nikkei Asia",    "url": "https://asia.nikkei.com/rss/feed/nar"},
        {"name": "FT Markets",     "url": "https://www.ft.com/markets?format=rss"},
    ],
    "📈 SAHAM & EQUITIES": [
        {"name": "Seeking Alpha",  "url": "https://seekingalpha.com/feed.xml"},
        {"name": "Benzinga",       "url": "https://www.benzinga.com/feed"},
        {"name": "Investor's Biz", "url": "https://www.investors.com/feed/"},
        {"name": "Motley Fool",    "url": "https://www.fool.com/a/feeds/foolwatch?format=rss&id=foolwatch&apikey=foolwatch"},
        {"name": "Yahoo Finance",  "url": "https://finance.yahoo.com/rss/topfinstories"},
    ],
    "💱 FOREX & RATES": [
        {"name": "ForexLive",         "url": "https://www.forexlive.com/feed/news"},
        {"name": "FXStreet",          "url": "https://www.fxstreet.com/rss/news"},
        {"name": "DailyFX",           "url": "https://www.dailyfx.com/feeds/all"},
        {"name": "Investing.com",     "url": "https://www.investing.com/rss/news_301.rss"},
        {"name": "Trading Economics", "url": "https://tradingeconomics.com/rss/news.aspx"},
    ],
    "🪙 CRYPTO & BLOCKCHAIN": [
        {"name": "CoinDesk",      "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
        {"name": "CoinTelegraph", "url": "https://cointelegraph.com/rss"},
        {"name": "The Block",     "url": "https://www.theblock.co/rss.xml"},
        {"name": "Decrypt",       "url": "https://decrypt.co/feed"},
        {"name": "CryptoSlate",   "url": "https://cryptoslate.com/feed/"},
    ],
    "🌐 MAKRO & EKONOMI": [
        {"name": "IMF",             "url": "https://www.imf.org/en/News/rss?language=ENG"},
        {"name": "World Bank",      "url": "https://blogs.worldbank.org/rss.xml"},
        {"name": "Federal Reserve", "url": "https://www.federalreserve.gov/feeds/press_all.xml"},
        {"name": "ECB",             "url": "https://www.ecb.europa.eu/rss/press.html"},
        {"name": "Bank of England", "url": "https://www.bankofengland.co.uk/rss/news"},
    ],
    "🌍 GEOPOLITIK & ENERGI": [
        {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
        {"name": "AP News",    "url": "https://rsshub.app/apnews/topics/apf-topnews"},
        {"name": "Politico",   "url": "https://rss.politico.com/politics-news.xml"},
    ],
    "🇮🇩 INDONESIA": [
        {"name": "CNBC Indonesia", "url": "https://www.cnbcindonesia.com/rss"},
        {"name": "Bisnis.com",     "url": "https://rss.bisnis.com/topnews.rss"},
        {"name": "Kontan",         "url": "https://rss.kontan.co.id/kontan/investasi.rss"},
        {"name": "Investor.id",    "url": "https://investor.id/feed"},
    ],
}

TOTAL_SOURCES = sum(len(v) for v in SOURCES.values())

# Emoji kategori untuk header pesan
KATEGORI_ICON = {
    "🌍 INTERNASIONAL":    "🌍",
    "📈 SAHAM & EQUITIES": "📈",
    "💱 FOREX & RATES":    "💱",
    "🪙 CRYPTO & BLOCKCHAIN": "🪙",
    "🌐 MAKRO & EKONOMI":  "🌐",
    "🌍 GEOPOLITIK & ENERGI": "⚔️",
    "🇮🇩 INDONESIA":       "🇮🇩",
}


# ─────────────────────────────────────────────
#  KEYWORD FILTER
# ─────────────────────────────────────────────
KEYWORDS = [
    "market","stock","shares","index","equity","trading","rally","crash",
    "earnings","revenue","profit","loss","forecast","outlook","guidance",
    "dollar","euro","yen","pound","rate","fed","fomc","interest",
    "inflation","cpi","ppi","gdp","nonfarm","payroll","unemployment",
    "treasury","yield","bond","bitcoin","btc","ethereum","eth","crypto",
    "blockchain","token","defi","nft","etf","altcoin","halving","whale",
    "recession","imf","world bank","central bank","monetary","fiscal",
    "tariff","trade war","sanction","opec","oil","gold","commodity",
    "war","conflict","geopolit","china","russia","ukraine","taiwan",
    "nato","election","president","minister","policy","deal",
    "indonesia","rupiah","idr","ihsg","bi rate","ojk","bps","saham",
    "bursa","idx","obligasi","sbn","sri mulyani","prabowo","apbn",
]


def is_relevant(text: str) -> bool:
    return any(kw in text.lower() for kw in KEYWORDS)


# ─────────────────────────────────────────────
#  FILTER WAKTU
# ─────────────────────────────────────────────
def parse_published(entry) -> datetime | None:
    for field in ("published", "updated", "created"):
        raw = getattr(entry, field, None)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                pass
    for field in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, field, None)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def is_recent(entry) -> bool:
    dt = parse_published(entry)
    if dt is None:
        log.debug("Tanggal tidak ditemukan, entri dilewati.")
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    return dt >= cutoff


# ─────────────────────────────────────────────
#  SEEN CACHE
# ─────────────────────────────────────────────
def load_seen() -> set:
    try:
        if os.path.exists(SEEN_FILE):
            with open(SEEN_FILE, "r") as f:
                return set(json.load(f))
    except Exception:
        pass
    return set()


def save_seen(seen: set):
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen)[-5000:], f)
    except Exception as e:
        log.error(f"Gagal simpan cache: {e}")


def art_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


# ─────────────────────────────────────────────
#  ANTI-DUPLIKAT JUDUL
# ─────────────────────────────────────────────
def normalize_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    stopwords = {
        "the","a","an","is","are","in","on","at","to","of","for",
        "and","or","with","by","from","as","that","this","it","be",
        "has","have","was","were","will","can","its","their","says",
        "said","new","says",
    }
    words = [w for w in t.split() if w not in stopwords]
    return " ".join(words[:8])


def title_hash(title: str) -> str:
    return hashlib.md5(normalize_title(title).encode()).hexdigest()


# ─────────────────────────────────────────────
#  TELEGRAM
# ─────────────────────────────────────────────
def send_telegram(text: str) -> bool:
    api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(api, json={
            "chat_id": CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return True
    except requests.exceptions.ConnectionError:
        log.warning("Tidak ada koneksi internet.")
        return False
    except Exception as e:
        log.error(f"Telegram error: {e}")
        return False


# ─────────────────────────────────────────────
#  FORMAT PESAN — PROFESIONAL & MUDAH DIBACA
# ─────────────────────────────────────────────
def bersihkan(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;|&gt;|&nbsp;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def buat_hashtag(sumber: str, kategori: str) -> str:
    """Buat hashtag dari sumber dan kategori."""
    tag_sumber   = "#" + re.sub(r"[^a-zA-Z0-9]", "", sumber)
    # Ambil kata pertama dari kategori (tanpa emoji)
    kata_kategori = re.sub(r"[^a-zA-Z]", "", kategori.split()[-1])
    tag_kategori  = f"#{kata_kategori}" if kata_kategori else ""
    return f"{tag_sumber} {tag_kategori}".strip()


def format_pesan(kategori, sumber, judul, ringkasan, link, pub_time=None) -> str:
    judul     = bersihkan(judul)
    ringkasan = bersihkan(ringkasan)

    # Potong ringkasan agar tidak terlalu panjang
    if len(ringkasan) > 280:
        ringkasan = ringkasan[:280].rsplit(" ", 1)[0] + "…"

    # Waktu WIB sekarang
    wib_offset = timezone(timedelta(hours=7))
    now_wib    = datetime.now(wib_offset).strftime("%d %b %Y • %H:%M WIB")

    # Waktu publikasi asli
    pub_str = ""
    if pub_time:
        pt = pub_time.astimezone(wib_offset)
        pub_str = pt.strftime("%d %b %Y %H:%M WIB")

    # Icon kategori
    icon = KATEGORI_ICON.get(kategori, "📰")

    # Hashtag
    hashtag = buat_hashtag(sumber, kategori)

    # ── Bangun pesan ────────────────────────────────────────
    baris = []

    # Header kategori
    baris.append(f"┌{'─'*30}┐")
    baris.append(f"  {icon}  <b>{esc(kategori.split(' ', 1)[-1])}</b>")
    baris.append(f"└{'─'*30}┘")
    baris.append("")

    # Judul
    baris.append(f"📰 <b>{esc(judul)}</b>")
    baris.append("")

    # Ringkasan (hanya tampil jika ada isi)
    if ringkasan:
        baris.append(f"<i>{esc(ringkasan)}</i>")
        baris.append("")

    # Metadata
    baris.append(f"{'─'*32}")
    baris.append(f"🏢 <b>Sumber :</b> {esc(sumber)}")
    if pub_str:
        baris.append(f"📅 <b>Terbit  :</b> {pub_str}")
    baris.append(f"🕐 <b>Diposting:</b> {now_wib}")
    baris.append(f"{'─'*32}")
    baris.append("")

    # Tombol link & hashtag
    baris.append(f"🔗 <a href='{link}'><b>» Baca Artikel Lengkap</b></a>")
    baris.append("")
    baris.append(f"<i>{hashtag} #MarketNews #NewsBot</i>")

    return "\n".join(baris)


# ─────────────────────────────────────────────
#  FETCH & KIRIM
# ─────────────────────────────────────────────
def fetch_and_send():
    log.info("=" * 50)
    log.info(f"Mulai fetch berita (max {MAX_AGE_HOURS} jam terakhir)...")
    seen            = load_seen()
    seen_titles     = set()
    total_sent      = 0
    total_skip_old  = 0
    total_skip_dupl = 0

    for kategori, feeds in SOURCES.items():
        for feed_info in feeds:
            nama = feed_info["name"]
            url  = feed_info["url"]
            try:
                feed    = feedparser.parse(url)
                entries = feed.entries[:MAX_PER_SOURCE]
                for entry in entries:
                    link      = getattr(entry, "link", "")
                    judul     = getattr(entry, "title", "").strip()
                    ringkasan = getattr(entry, "summary", "")
                    if not link or not judul:
                        continue

                    # 1. Cek duplikat URL
                    aid = art_id(link)
                    if aid in seen:
                        continue

                    # 2. Cek umur berita
                    pub_time = parse_published(entry)
                    if not is_recent(entry):
                        seen.add(aid)
                        total_skip_old += 1
                        log.debug(f"Skip (terlalu lama): [{nama}] {judul[:50]}")
                        continue

                    # 3. Cek duplikat judul
                    th = title_hash(judul)
                    if th in seen_titles:
                        seen.add(aid)
                        total_skip_dupl += 1
                        log.info(f"Skip (duplikat judul): [{nama}] {judul[:60]}")
                        continue
                    seen_titles.add(th)

                    # 4. Filter keyword relevansi
                    if not is_relevant(judul + " " + ringkasan):
                        seen.add(aid)
                        continue

                    # 5. Kirim ke Telegram
                    pesan = format_pesan(kategori, nama, judul, ringkasan, link, pub_time)
                    if send_telegram(pesan):
                        seen.add(aid)
                        total_sent += 1
                        log.info(f"✅ [{nama}] {judul[:60]}...")
                        time.sleep(DELAY_BETWEEN_SEND)

            except Exception as e:
                log.error(f"Error [{nama}]: {e}")

    save_seen(seen)

    log.info(
        f"Selesai — Terkirim: {total_sent} | "
        f"Skip lama: {total_skip_old} | "
        f"Skip duplikat: {total_skip_dupl}"
    )

    # Laporan ringkas setiap siklus
    if total_sent > 0:
        send_telegram(
            f"┌{'─'*30}┐\n"
            f"  📊  <b>LAPORAN SIKLUS BOT</b>\n"
            f"└{'─'*30}┘\n\n"
            f"✅  Berita terkirim   : <b>{total_sent}</b>\n"
            f"⏱️  Filter waktu      : <b>{MAX_AGE_HOURS} jam</b> terakhir\n"
            f"🚫  Dilewati (lama)   : {total_skip_old}\n"
            f"🔁  Dilewati (duplikat): {total_skip_dupl}\n\n"
            f"{'─'*32}\n"
            f"🕐 {datetime.now().strftime('%d %b %Y  %H:%M WIB')}\n"
            f"<i>#BotUpdate #NewsBot</i>"
        )
    else:
        log.info("Tidak ada berita baru.")


# ─────────────────────────────────────────────
#  BRIEFING TERJADWAL
# ─────────────────────────────────────────────
def morning_briefing():
    now  = datetime.now()
    hari = ["Senin","Selasa","Rabu","Kamis","Jumat","Sabtu","Minggu"][now.weekday()]
    send_telegram(
        f"┌{'━'*30}┐\n"
        f"  🌅  <b>MORNING MARKET BRIEFING</b>\n"
        f"└{'━'*30}┘\n\n"
        f"📅 <b>{hari}, {now.strftime('%d %B %Y')}</b>\n\n"
        f"<b>🔍 Yang Perlu Dipantau Hari Ini:</b>\n"
        f"  • 📊 Pembukaan IHSG, Nikkei, HSI\n"
        f"  • 📰 Rilis data ekonomi terbaru\n"
        f"  • 🇺🇸 Sentimen Wall Street semalam\n"
        f"  • 🪙 Update Crypto &amp; on-chain data\n"
        f"  • 💱 Pergerakan USD/IDR\n\n"
        f"{'─'*32}\n"
        f"📡 Memantau <b>{TOTAL_SOURCES} sumber</b> aktif\n"
        f"⏱️ Filter: hanya berita <b>{MAX_AGE_HOURS} jam</b> terakhir\n\n"
        f"<i>💡 Stay informed. Trade wisely.</i>\n"
        f"<i>#MorningBriefing #MarketOpen #IHSG</i>"
    )
    log.info("Morning briefing terkirim.")


def closing_summary():
    now = datetime.now()
    send_telegram(
        f"┌{'━'*30}┐\n"
        f"  🌙  <b>MARKET CLOSING SUMMARY</b>\n"
        f"└{'━'*30}┘\n\n"
        f"🕔 <b>{now.strftime('%d %B %Y  •  %H:%M WIB')}</b>\n\n"
        f"<b>📌 Status Sesi:</b>\n"
        f"  • 🌏 Sesi Asia       : <b>Tutup</b>\n"
        f"  • 🇪🇺 Sesi Eropa     : <b>Tutup</b>\n"
        f"  • 🇺🇸 Sesi New York  : <b>Berlangsung</b>\n"
        f"  • 🪙 Crypto Market   : <b>Aktif 24/7</b>\n\n"
        f"{'─'*32}\n"
        f"<b>⏰ Jadwal Selanjutnya:</b>\n"
        f"  • Morning Briefing  : 06:00 WIB\n"
        f"  • Bot tetap aktif memantau berita\n\n"
        f"<i>#ClosingSummary #IHSG #MarketWrap</i>"
    )
    log.info("Closing summary terkirim.")


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    validate_config()

    print("\n" + "="*50)
    print("  MASTER NEWS BOT — TERMUX EDITION")
    print("="*50)
    print(f"  Channel     : {CHANNEL_ID}")
    print(f"  Total sumber: {TOTAL_SOURCES}")
    print(f"  Interval    : {FETCH_INTERVAL_MIN} menit")
    print(f"  Filter waktu: {MAX_AGE_HOURS} jam terakhir")
    print("="*50 + "\n")

    send_telegram(
        f"┌{'━'*30}┐\n"
        f"  🤖  <b>MASTER NEWS BOT — ONLINE</b>\n"
        f"└{'━'*30}┘\n\n"
        f"<b>📡 Memantau {TOTAL_SOURCES} Sumber Berita:</b>\n\n"
        f"  🌍 Internasional   📈 Saham &amp; Equities\n"
        f"  💱 Forex &amp; Rates  🪙 Crypto &amp; Blockchain\n"
        f"  🌐 Makro &amp; Ekonomi  ⚔️ Geopolitik\n"
        f"  🇮🇩 Indonesia\n\n"
        f"{'─'*32}\n"
        f"⚙️  <b>Konfigurasi:</b>\n"
        f"  • Interval fetch  : setiap <b>{FETCH_INTERVAL_MIN} menit</b>\n"
        f"  • Filter berita   : <b>{MAX_AGE_HOURS} jam</b> terakhir\n"
        f"  • Anti-duplikat   : URL + Judul ✅\n\n"
        f"🕐 Aktif sejak: {datetime.now().strftime('%d %b %Y  %H:%M WIB')}\n"
        f"<i>#BotOnline #NewsBot</i>"
    )

    schedule.every(FETCH_INTERVAL_MIN).minutes.do(fetch_and_send)
    schedule.every().day.at("06:00").do(morning_briefing)
    schedule.every().day.at("18:00").do(closing_summary)

    fetch_and_send()  # langsung fetch saat start

    log.info("Loop utama berjalan. Ctrl+C untuk berhenti.")
    while True:
        try:
            schedule.run_pending()
            time.sleep(30)
        except KeyboardInterrupt:
            log.info("Bot dihentikan.")
            send_telegram(
                f"🛑 <b>Bot Dihentikan</b>\n\n"
                f"Bot telah dimatikan secara manual.\n"
                f"🕐 {datetime.now().strftime('%d %b %Y  %H:%M WIB')}\n"
                f"<i>#BotOffline</i>"
            )
            break
        except Exception as e:
            log.error(f"Loop error: {e} — retry 60 detik...")
            time.sleep(60)


if __name__ == "__main__":
    main()
