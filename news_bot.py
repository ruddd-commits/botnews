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
SEEN_TITLES_FILE     = "seen_titles.json"   # ← BARU: cache judul persisten
MAX_PER_SOURCE       = 15
FETCH_INTERVAL_MIN   = 3
REQUEST_TIMEOUT      = 10
DELAY_BETWEEN_SEND   = 2
MAX_AGE_HOURS        = 2

# Threshold kemiripan judul (0.0–1.0). Semakin tinggi = lebih ketat.
# 0.6 berarti 60% kata yang sama dianggap topik yang sama.
TITLE_SIMILARITY_THRESHOLD = 0.6

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
#  SEEN CACHE (URL)
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
        log.error(f"Gagal simpan cache URL: {e}")


def art_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


# ─────────────────────────────────────────────
#  SEEN TITLES CACHE (PERSISTEN ANTAR SIKLUS)
# ─────────────────────────────────────────────
def load_seen_titles() -> dict:
    """
    Mengembalikan dict: { title_key (str) -> published_iso (str) }
    title_key = token set dari judul yang dinormalisasi (disimpan sebagai string join)
    """
    try:
        if os.path.exists(SEEN_TITLES_FILE):
            with open(SEEN_TITLES_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_seen_titles(seen_titles: dict):
    """Simpan max 2000 entri terbaru agar file tidak membengkak."""
    try:
        items = list(seen_titles.items())
        # Trim ke 2000 entri terbaru
        if len(items) > 2000:
            items = items[-2000:]
        with open(SEEN_TITLES_FILE, "w") as f:
            json.dump(dict(items), f)
    except Exception as e:
        log.error(f"Gagal simpan cache judul: {e}")


def cleanup_old_titles(seen_titles: dict) -> dict:
    """Hapus entri judul yang sudah lebih dari MAX_AGE_HOURS * 3 jam (buffer 3x)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS * 3)
    cleaned = {}
    for key, pub_iso in seen_titles.items():
        try:
            pub_dt = datetime.fromisoformat(pub_iso)
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            if pub_dt >= cutoff:
                cleaned[key] = pub_iso
        except Exception:
            pass  # buang entri rusak
    return cleaned


# ─────────────────────────────────────────────
#  ANTI-DUPLIKAT JUDUL (LINTAS SUMBER & SIKLUS)
# ─────────────────────────────────────────────
STOPWORDS = {
    "the","a","an","is","are","in","on","at","to","of","for",
    "and","or","with","by","from","as","that","this","it","be",
    "has","have","was","were","will","can","its","their","says",
    "said","new","says",
}


def normalize_title(title: str) -> str:
    """Normalisasi judul: lowercase, hapus karakter non-alfanumerik, hapus stopword."""
    t = title.lower()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    words = [w for w in t.split() if w not in STOPWORDS]
    return " ".join(words)


def title_tokens(title: str) -> set:
    """Kembalikan set token dari judul yang sudah dinormalisasi."""
    return set(normalize_title(title).split())


def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Hitung Jaccard similarity antara dua set token."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def title_key(title: str) -> str:
    """Buat string key dari token set untuk penyimpanan di JSON."""
    tokens = title_tokens(title)
    return " ".join(sorted(tokens))


def find_similar_title(new_title: str, seen_titles: dict) -> str | None:
    """
    Cari apakah ada judul yang mirip di seen_titles.
    Kembalikan key yang mirip, atau None jika tidak ada.
    """
    new_tokens = title_tokens(new_title)
    if not new_tokens:
        return None
    for existing_key in seen_titles:
        existing_tokens = set(existing_key.split())
        sim = jaccard_similarity(new_tokens, existing_tokens)
        if sim >= TITLE_SIMILARITY_THRESHOLD:
            return existing_key
    return None


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

    # Nama kategori bersih (tanpa emoji di depan)
    nama_kategori = re.sub(r"^[\W\s]+", "", kategori).strip()
    # Fallback: ambil kata setelah spasi pertama jika masih ada emoji
    if not nama_kategori[0].isalpha():
        nama_kategori = kategori.split(" ", 1)[-1].strip()

    # Hashtag
    hashtag = buat_hashtag(sumber, kategori)

    # ── Bangun pesan ────────────────────────────────────────
    baris = []

    # ═══ BREAKING NEWS HEADER ═══
    baris.append(f"🔴 <b>BREAKING NEWS</b>")
    baris.append(f"{'━'*32}")
    baris.append(f"{icon} <b>{esc(nama_kategori)}</b>")
    baris.append(f"{'━'*32}")
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
#  FETCH SEMUA ARTIKEL (TANPA KIRIM)
# ─────────────────────────────────────────────
def fetch_all_candidates(seen: set) -> list[dict]:
    """
    Ambil semua artikel kandidat dari seluruh sumber.
    Return list of dict:
        { kategori, nama, judul, ringkasan, link, pub_time, aid }
    Sudah difilter: bukan URL duplikat, masih baru (dalam MAX_AGE_HOURS),
    dan relevan berdasarkan keyword.
    URL duplikat langsung di-mark ke seen agar tidak muncul lagi.
    """
    candidates = []

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

                    aid = art_id(link)

                    # Sudah pernah dikirim (URL)?
                    if aid in seen:
                        continue

                    # Terlalu lama?
                    pub_time = parse_published(entry)
                    if not pub_time or not is_recent(entry):
                        seen.add(aid)  # jangan proses lagi
                        log.debug(f"Skip (terlalu lama): [{nama}] {judul[:50]}")
                        continue

                    # Relevan?
                    if not is_relevant(judul + " " + ringkasan):
                        seen.add(aid)
                        continue

                    candidates.append({
                        "kategori":  kategori,
                        "nama":      nama,
                        "judul":     judul,
                        "ringkasan": ringkasan,
                        "link":      link,
                        "pub_time":  pub_time,
                        "aid":       aid,
                    })

            except Exception as e:
                log.error(f"Error fetch [{nama}]: {e}")

    return candidates


# ─────────────────────────────────────────────
#  DEDUPLIKASI KONTEN (LINTAS SUMBER)
# ─────────────────────────────────────────────
def deduplicate_candidates(candidates: list[dict]) -> list[dict]:
    """
    Dari semua kandidat artikel, hilangkan yang topiknya sama.
    Jika ada beberapa artikel dengan judul mirip (Jaccard >= threshold),
    HANYA artikel dengan pub_time PALING AWAL yang dipertahankan.
    Artikel lainnya dianggap duplikat dan diabaikan.

    Return: list artikel unik, diurutkan dari yang terlama ke terbaru
            (agar yang paling awal masuk sent_titles lebih dulu).
    """
    # Urutkan dulu dari pub_time terlama → terbaru
    # Dengan begitu ketika kita iterasi, artikel paling awal selalu menang
    sorted_cands = sorted(candidates, key=lambda x: x["pub_time"])

    groups: list[list[dict]] = []   # setiap group = topik yang sama
    group_tokens: list[set]  = []   # token representatif tiap group

    for art in sorted_cands:
        tokens = title_tokens(art["judul"])
        matched_group = None

        for i, g_tokens in enumerate(group_tokens):
            if jaccard_similarity(tokens, g_tokens) >= TITLE_SIMILARITY_THRESHOLD:
                matched_group = i
                break

        if matched_group is not None:
            # Masukkan ke group yang ada
            groups[matched_group].append(art)
        else:
            # Buat group baru
            groups.append([art])
            group_tokens.append(tokens)

    # Ambil hanya artikel pertama (paling awal) dari setiap group
    unique = []
    for group in groups:
        winner = group[0]   # sudah sorted by pub_time, index 0 = paling lama/duluan
        unique.append(winner)
        if len(group) > 1:
            dupes = [f"[{a['nama']}] {a['judul'][:50]}" for a in group[1:]]
            log.info(
                f"Duplikat dibuang ({len(group)-1}): pilih [{winner['nama']}] "
                f"'{winner['judul'][:50]}' | Dibuang: {dupes}"
            )

    return unique


# ─────────────────────────────────────────────
#  FETCH & KIRIM
# ─────────────────────────────────────────────
def fetch_and_send():
    log.info("=" * 50)
    log.info(f"Mulai fetch berita (max {MAX_AGE_HOURS} jam terakhir)...")

    seen        = load_seen()
    seen_titles = load_seen_titles()

    # Bersihkan entri judul yang sudah sangat lama
    seen_titles = cleanup_old_titles(seen_titles)

    total_sent          = 0
    total_skip_old      = 0
    total_skip_dupl_url = 0
    total_skip_dupl_ttl = 0

    # ── Tahap 1: Ambil semua kandidat dari semua sumber ──
    log.info("Tahap 1: Mengumpulkan kandidat dari semua sumber...")
    candidates = fetch_all_candidates(seen)
    log.info(f"Total kandidat sebelum dedup: {len(candidates)}")

    # ── Tahap 2: Deduplikasi antar-sumber (pilih paling duluan publish) ──
    log.info("Tahap 2: Deduplikasi konten lintas sumber...")
    unique_candidates = deduplicate_candidates(candidates)

    # Hitung berapa yang dibuang di tahap ini
    total_skip_dupl_ttl = len(candidates) - len(unique_candidates)
    log.info(f"Setelah dedup konten: {len(unique_candidates)} artikel unik")

    # ── Tahap 3: Filter vs seen_titles persisten & kirim ──
    log.info("Tahap 3: Filter seen_titles persisten & kirim...")
    for art in unique_candidates:
        judul    = art["judul"]
        pub_time = art["pub_time"]
        aid      = art["aid"]

        # Cek apakah sudah ada judul serupa yang pernah dikirim (lintas siklus)
        similar_key = find_similar_title(judul, seen_titles)
        if similar_key is not None:
            seen.add(aid)
            total_skip_dupl_ttl += 1
            log.info(
                f"Skip (duplikat persisten): [{art['nama']}] {judul[:60]}"
            )
            continue

        # Kirim ke Telegram
        pesan = format_pesan(
            art["kategori"], art["nama"], judul,
            art["ringkasan"], art["link"], pub_time
        )
        if send_telegram(pesan):
            seen.add(aid)
            # Simpan ke seen_titles persisten
            tkey = title_key(judul)
            pub_iso = pub_time.isoformat() if pub_time else datetime.now(timezone.utc).isoformat()
            seen_titles[tkey] = pub_iso

            total_sent += 1
            log.info(f"✅ [{art['nama']}] {judul[:60]}...")
            time.sleep(DELAY_BETWEEN_SEND)

    save_seen(seen)
    save_seen_titles(seen_titles)

    log.info(
        f"Selesai — Terkirim: {total_sent} | "
        f"Skip lama: {total_skip_old} | "
        f"Skip duplikat: {total_skip_dupl_ttl}"
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
            f"🔁  Dilewati (duplikat): {total_skip_dupl_ttl}\n\n"
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
    print(f"  Sim. threshold: {TITLE_SIMILARITY_THRESHOLD}")
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
        f"  • Anti-duplikat   : URL + Judul (Jaccard {TITLE_SIMILARITY_THRESHOLD}) ✅\n"
        f"  • Cache judul     : persisten lintas siklus ✅\n\n"
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
