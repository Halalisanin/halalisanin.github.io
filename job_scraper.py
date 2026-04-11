#!/usr/bin/env python3
"""
job_scraper.py — South African job scraper for Halalisani Ngema
Searches PNet, CareerJunction, and Indeed ZA for matching roles.
Sends matches to your Telegram jobs bot.

Usage:  python3 job_scraper.py
        python3 job_scraper.py --once       # run once and exit
        python3 job_scraper.py --interval 3 # run every 3 hours (default)

Requirements:  pip3 install requests beautifulsoup4 schedule
"""

import json, re, time, hashlib, argparse, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
    import schedule
except ImportError:
    print("Missing dependencies. Run:  pip3 install requests beautifulsoup4 schedule")
    exit(1)

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_FILE = Path(__file__).parent / "social_config.json"
SEEN_FILE   = Path(__file__).parent / ".seen_jobs.json"

config = {}
if CONFIG_FILE.exists():
    with open(CONFIG_FILE) as f:
        config = json.load(f)

BOT_TOKEN = config.get("telegram_bot_token", "")
CHAT_ID   = config.get("telegram_chat_id", "")

# ── Job search criteria ───────────────────────────────────────────────────────
SEARCH_QUERIES = [
    "HR administrator Johannesburg",
    "HR benefits consultant Johannesburg",
    "payroll administrator Johannesburg",
    "customer service banking Johannesburg",
    "banking consultant Johannesburg",
    "administration clerk Johannesburg",
    "HR officer Gauteng",
    "call centre agent Johannesburg",
    "teller Johannesburg",
]

KEYWORDS_INCLUDE = [
    "hr", "human resources", "benefits", "payroll", "banking",
    "teller", "customer service", "administration", "admin",
    "nedbank", "fnb", "standard bank", "absa", "capitec",
    "financial services", "contact centre", "call centre",
]

KEYWORDS_EXCLUDE = [
    "senior manager", "head of", "director", "executive",
    "10 years", "15 years", "degree required", "honours",
    "masters", "phd",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# ─────────────────────────────────────────────────────────────────────────────
def load_seen() -> set:
    if SEEN_FILE.exists():
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def job_hash(title: str, url: str) -> str:
    return hashlib.md5(f"{title}{url}".encode()).hexdigest()[:12]

def is_relevant(title: str, description: str = "") -> bool:
    text = (title + " " + description).lower()
    if not any(kw in text for kw in KEYWORDS_INCLUDE):
        return False
    if any(kw in text for kw in KEYWORDS_EXCLUDE):
        return False
    return True

# ── Scrapers ──────────────────────────────────────────────────────────────────
def scrape_pnet(query: str) -> list[dict]:
    jobs = []
    try:
        q = urllib.parse.quote(query)
        url = f"https://www.pnet.co.za/jobs/{q.replace('+', '-').replace('%20', '-').lower()}/"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select("article.job-card, div.job-card, [data-job-id]")[:15]:
            title_el = card.select_one("h2, h3, .job-title, [class*='title']")
            link_el  = card.select_one("a[href]")
            comp_el  = card.select_one("[class*='company'], [class*='employer']")
            if not title_el or not link_el:
                continue
            title = title_el.get_text(strip=True)
            href  = link_el["href"]
            if not href.startswith("http"):
                href = "https://www.pnet.co.za" + href
            company = comp_el.get_text(strip=True) if comp_el else "Unknown"
            if is_relevant(title):
                jobs.append({"title": title, "company": company, "url": href, "source": "PNet"})
    except Exception as e:
        print(f"  PNet error: {e}")
    return jobs

def scrape_careerjunction(query: str) -> list[dict]:
    jobs = []
    try:
        q = urllib.parse.quote_plus(query)
        url = f"https://www.careerjunction.co.za/jobs/results?keywords={q}&location=Gauteng"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select(".job-card, article, [class*='job-item'], [class*='JobCard']")[:15]:
            title_el = card.select_one("h2, h3, [class*='title'], [class*='Title']")
            link_el  = card.select_one("a[href]")
            comp_el  = card.select_one("[class*='company'], [class*='Company'], [class*='employer']")
            if not title_el or not link_el:
                continue
            title = title_el.get_text(strip=True)
            href  = link_el["href"]
            if not href.startswith("http"):
                href = "https://www.careerjunction.co.za" + href
            company = comp_el.get_text(strip=True) if comp_el else "Unknown"
            if is_relevant(title):
                jobs.append({"title": title, "company": company, "url": href, "source": "CareerJunction"})
    except Exception as e:
        print(f"  CareerJunction error: {e}")
    return jobs

def scrape_indeed(query: str) -> list[dict]:
    jobs = []
    try:
        q = urllib.parse.quote_plus(query)
        url = f"https://za.indeed.com/jobs?q={q}&l=Johannesburg&sort=date"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select(".job_seen_beacon, .jobsearch-SerpJobCard, [class*='job_']")[:15]:
            title_el = card.select_one("h2.jobTitle, h2, [class*='jobTitle']")
            link_el  = card.select_one("a[href]")
            comp_el  = card.select_one("[class*='companyName'], [class*='company']")
            if not title_el or not link_el:
                continue
            title = title_el.get_text(strip=True)
            href  = link_el["href"]
            if not href.startswith("http"):
                href = "https://za.indeed.com" + href
            company = comp_el.get_text(strip=True) if comp_el else "Unknown"
            if is_relevant(title):
                jobs.append({"title": title, "company": company, "url": href, "source": "Indeed ZA"})
    except Exception as e:
        print(f"  Indeed error: {e}")
    return jobs

def scrape_jobmail(query: str) -> list[dict]:
    jobs = []
    try:
        q = urllib.parse.quote_plus(query)
        url = f"https://www.jobmail.co.za/jobs?keyword={q}&location=Johannesburg"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select("[class*='job-ad'], [class*='jobAd'], article")[:10]:
            title_el = card.select_one("h2, h3, [class*='title']")
            link_el  = card.select_one("a[href]")
            comp_el  = card.select_one("[class*='company'], [class*='employer']")
            if not title_el or not link_el:
                continue
            title = title_el.get_text(strip=True)
            href  = link_el["href"]
            if not href.startswith("http"):
                href = "https://www.jobmail.co.za" + href
            company = comp_el.get_text(strip=True) if comp_el else "Unknown"
            if is_relevant(title):
                jobs.append({"title": title, "company": company, "url": href, "source": "JobMail"})
    except Exception as e:
        print(f"  JobMail error: {e}")
    return jobs

# ── Telegram sender ───────────────────────────────────────────────────────────
def send_telegram(message: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print("  ⚠  Telegram not configured. Edit social_config.json")
        return False
    try:
        data = urllib.parse.urlencode({
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": "false"
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data=data
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"  Telegram error: {e}")
        return False

def format_job_message(job: dict) -> str:
    return (
        f"💼 *New Job Match!*\n\n"
        f"*{job['title']}*\n"
        f"🏢 {job['company']}\n"
        f"📍 Johannesburg / Gauteng\n"
        f"🔗 [{job['source']}]({job['url']})"
    )

# ── Main scrape loop ──────────────────────────────────────────────────────────
def run_scrape():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Scraping jobs…")
    seen   = load_seen()
    found  = 0
    all_jobs = []

    for query in SEARCH_QUERIES:
        print(f"  Searching: {query}")
        all_jobs += scrape_pnet(query)
        all_jobs += scrape_careerjunction(query)
        all_jobs += scrape_indeed(query)
        all_jobs += scrape_jobmail(query)
        time.sleep(1)  # polite delay

    # Deduplicate by hash
    unique = {}
    for job in all_jobs:
        h = job_hash(job["title"], job["url"])
        if h not in seen and h not in unique:
            unique[h] = job

    print(f"  Found {len(unique)} new matching jobs")

    for h, job in unique.items():
        msg = format_job_message(job)
        ok  = send_telegram(msg)
        if ok:
            print(f"  → Sent: {job['title']} ({job['source']})")
            found += 1
            seen.add(h)
        time.sleep(0.5)

    save_seen(seen)
    if found == 0:
        print("  No new jobs this round.")
    else:
        print(f"  ✓ Sent {found} new jobs to Telegram")

# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job scraper for Halalisani Ngema")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, default=3, help="Hours between runs (default: 3)")
    args = parser.parse_args()

    print("Job Scraper — halalisanin.github.io")
    print(f"Bot token: {'configured ✓' if BOT_TOKEN else 'NOT SET ✗'}")
    print(f"Chat ID:   {'configured ✓' if CHAT_ID else 'NOT SET ✗'}")

    if not BOT_TOKEN or not CHAT_ID:
        print("\nPlease fill in telegram_bot_token and telegram_chat_id in social_config.json")

    run_scrape()

    if not args.once:
        print(f"\nRunning every {args.interval} hours. Press Ctrl+C to stop.")
        schedule.every(args.interval).hours.do(run_scrape)
        while True:
            schedule.run_pending()
            time.sleep(60)
