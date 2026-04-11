#!/usr/bin/env python3
"""
job_scraper.py — Job scraper for Halalisani Ngema
Uses Adzuna API (free) + CareerJunction HTML scraping.

Setup:
  1. Register FREE at https://developer.adzuna.com/
  2. Add your app_id and app_key to social_config.json
  3. Run: python3 job_scraper.py --once

Usage:
  python3 job_scraper.py --once        # run once and exit
  python3 job_scraper.py               # run every 3 hours
  python3 job_scraper.py --interval 6  # run every 6 hours

Requirements: pip3 install requests beautifulsoup4 schedule
"""

import json, re, time, hashlib, argparse, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
    import schedule
except ImportError:
    print("Run:  pip3 install requests beautifulsoup4 schedule")
    exit(1)

# ── Config ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "social_config.json"
SEEN_FILE   = BASE_DIR / ".seen_jobs.json"

config = {}
if CONFIG_FILE.exists():
    with open(CONFIG_FILE) as f:
        config = json.load(f)

BOT_TOKEN    = config.get("telegram_bot_token", "")
CHAT_ID      = config.get("telegram_chat_id", "")
ADZUNA_ID    = config.get("adzuna_app_id", "")
ADZUNA_KEY   = config.get("adzuna_app_key", "")

# ── Search terms ───────────────────────────────────────────────────────────────
SEARCHES = [
    "HR administrator",
    "HR benefits consultant",
    "payroll administrator",
    "banking customer service",
    "banking consultant",
    "administration clerk",
    "HR officer",
    "call centre agent",
    "teller",
    "HR generalist",
]

KEYWORDS_INCLUDE = [
    "hr", "human resources", "benefits", "payroll", "banking",
    "teller", "customer service", "administration", "admin",
    "financial services", "contact centre", "call centre",
    "clerk", "officer", "consultant", "people",
]

KEYWORDS_EXCLUDE = [
    "senior manager", "head of department", "director", "executive",
    "10+ years", "15 years", "honours degree", "masters", "phd",
    "software engineer", "developer", "data scientist",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── Helpers ────────────────────────────────────────────────────────────────────
def load_seen():
    if SEEN_FILE.exists():
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def job_hash(title, url):
    return hashlib.md5((title + url).encode()).hexdigest()[:12]

def is_relevant(title, description=""):
    text = (title + " " + description).lower()
    if not any(kw in text for kw in KEYWORDS_INCLUDE):
        return False
    if any(kw in text for kw in KEYWORDS_EXCLUDE):
        return False
    return True

# ── Adzuna API (free — register at developer.adzuna.com) ──────────────────────
def scrape_adzuna(query):
    if not ADZUNA_ID or not ADZUNA_KEY:
        return []
    jobs = []
    try:
        q   = urllib.parse.quote_plus(query)
        url = (
            f"https://api.adzuna.com/v1/api/jobs/za/search/1"
            f"?app_id={ADZUNA_ID}&app_key={ADZUNA_KEY}"
            f"&what={q}&where=johannesburg"
            f"&results_per_page=20&sort_by=date&full_time=1"
        )
        r    = requests.get(url, headers=HEADERS, timeout=15)
        data = r.json()
        for job in data.get("results", []):
            title   = job.get("title", "")
            company = job.get("company", {}).get("display_name", "Unknown")
            link    = job.get("redirect_url", "")
            desc    = re.sub(r"<[^>]+>", " ", job.get("description", ""))[:200]
            if is_relevant(title, desc):
                jobs.append({
                    "title":   title,
                    "company": company,
                    "url":     link,
                    "source":  "Adzuna",
                    "snippet": desc.strip(),
                })
    except Exception as e:
        print(f"  Adzuna error: {e}")
    return jobs

# ── CareerJunction HTML scrape ─────────────────────────────────────────────────
def scrape_careerjunction(query):
    jobs = []
    try:
        q   = urllib.parse.quote_plus(query)
        url = f"https://www.careerjunction.co.za/jobs/results?keywords={q}&location=Gauteng&sortby=DatePosted"
        r   = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        # Try multiple possible card selectors
        cards = (
            soup.select(".module.job-result") or
            soup.select("[class*='job-result']") or
            soup.select("[class*='JobResult']") or
            soup.select("article")
        )

        for card in cards[:15]:
            title_el = (
                card.select_one("h2 a") or
                card.select_one("h3 a") or
                card.select_one("[class*='title'] a") or
                card.select_one("a[href*='/job/']")
            )
            comp_el = (
                card.select_one("[class*='company']") or
                card.select_one("[class*='employer']")
            )
            if not title_el:
                continue
            title   = title_el.get_text(strip=True)
            href    = title_el.get("href", "")
            if not href.startswith("http"):
                href = "https://www.careerjunction.co.za" + href
            company = comp_el.get_text(strip=True) if comp_el else "See listing"
            if is_relevant(title):
                jobs.append({
                    "title":   title,
                    "company": company,
                    "url":     href,
                    "source":  "CareerJunction",
                    "snippet": "",
                })
    except Exception as e:
        print(f"  CareerJunction error: {e}")
    return jobs

# ── Telegram ───────────────────────────────────────────────────────────────────
def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("  Telegram not configured.")
        return False
    try:
        data = urllib.parse.urlencode({
            "chat_id":                  CHAT_ID,
            "text":                     message,
            "parse_mode":               "Markdown",
            "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data=data
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"  Telegram error: {e}")
        return False

def format_job(job):
    snippet = f"\n_{job['snippet'][:150]}_" if job.get("snippet") else ""
    return (
        f"💼 *New Job Match!*\n\n"
        f"*{job['title']}*\n"
        f"🏢 {job['company']}\n"
        f"📍 Johannesburg / Gauteng{snippet}\n\n"
        f"🔗 [View on {job['source']}]({job['url']})"
    )

# ── Main ───────────────────────────────────────────────────────────────────────
def run_scrape():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Searching for jobs…")

    if not ADZUNA_ID:
        print("\n  ⚠  Adzuna API not configured.")
        print("  Register FREE at: https://developer.adzuna.com/")
        print("  Then add adzuna_app_id and adzuna_app_key to social_config.json\n")

    seen     = load_seen()
    all_jobs = []

    for query in SEARCHES:
        print(f"  → {query}")
        all_jobs += scrape_adzuna(query)
        all_jobs += scrape_careerjunction(query)
        time.sleep(0.5)

    # Deduplicate
    unique = {}
    for job in all_jobs:
        h = job_hash(job["title"], job["url"])
        if h not in seen and h not in unique:
            unique[h] = job

    print(f"\n  Found {len(unique)} new matching jobs")

    sent = 0
    for h, job in unique.items():
        if send_telegram(format_job(job)):
            print(f"  ✓ {job['title']} ({job['source']})")
            seen.add(h)
            sent += 1
            time.sleep(0.5)

    save_seen(seen)

    if sent == 0:
        msg = "🔍 Job search complete — no new matches this round. Will check again later."
        print("  No new jobs this round.")
        send_telegram(msg)
    else:
        print(f"\n  Done! Sent {sent} jobs to Telegram.")

# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once",     action="store_true")
    parser.add_argument("--interval", type=int, default=3)
    args = parser.parse_args()

    print("Job Scraper — @Sani_prof_bot")
    print(f"Telegram: {'ready ✓' if BOT_TOKEN and CHAT_ID else 'NOT configured ✗'}")
    print(f"Adzuna:   {'ready ✓' if ADZUNA_ID else 'NOT configured — register free at developer.adzuna.com'}")

    run_scrape()

    if not args.once:
        print(f"\nChecking every {args.interval} hours. Ctrl+C to stop.")
        schedule.every(args.interval).hours.do(run_scrape)
        while True:
            schedule.run_pending()
            time.sleep(60)
