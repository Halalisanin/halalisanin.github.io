#!/usr/bin/env python3
"""
new_post.py — Blog post creator for halalisanin.github.io
Usage:  python3 new_post.py

Creates a markdown post, updates posts/index.json,
optionally pushes to GitHub and posts to Telegram / social media.
"""

import os, sys, json, re, subprocess, tempfile, datetime, textwrap
from pathlib import Path

POSTS_DIR  = Path(__file__).parent / "posts"
INDEX_FILE = POSTS_DIR / "index.json"
EDITOR     = os.environ.get("EDITOR", "nano")

# ── Load social config (optional) ────────────────────────────────────────────
CONFIG_FILE = Path(__file__).parent / "social_config.json"
config = {}
if CONFIG_FILE.exists():
    with open(CONFIG_FILE) as f:
        config = json.load(f)

# ─────────────────────────────────────────────────────────────────────────────
def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_-]+", "-", text)

def prompt(label: str, default: str = "") -> str:
    val = input(f"  {label}{f' [{default}]' if default else ''}: ").strip()
    return val or default

def run(cmd: str) -> bool:
    result = subprocess.run(cmd, shell=True, cwd=Path(__file__).parent)
    return result.returncode == 0

# ─────────────────────────────────────────────────────────────────────────────
def write_post(title, date, tags, excerpt, content):
    slug   = slugify(title)
    post_id = f"{date}-{slug}"
    filename = POSTS_DIR / f"{post_id}.md"

    frontmatter = textwrap.dedent(f"""\
        ---
        title: {title}
        date: {date}
        tags: {', '.join(tags)}
        excerpt: {excerpt}
        ---

        """)

    with open(filename, "w") as f:
        f.write(frontmatter + content)

    print(f"\n  ✓ Saved: posts/{post_id}.md")
    return post_id, filename

def update_index(post_id, title, date, tags, excerpt):
    posts = []
    if INDEX_FILE.exists():
        with open(INDEX_FILE) as f:
            posts = json.load(f)

    # Remove existing entry with same id (re-publish / update)
    posts = [p for p in posts if p["id"] != post_id]
    posts.insert(0, {
        "id":      post_id,
        "title":   title,
        "date":    date,
        "tags":    tags,
        "excerpt": excerpt,
    })

    with open(INDEX_FILE, "w") as f:
        json.dump(posts, f, indent=2)
    print("  ✓ Updated posts/index.json")

def push_to_github(post_id):
    print("\n  Pushing to GitHub…")
    token = config.get("github_token", "")
    if token:
        run(f"git remote set-url origin https://{token}@github.com/Halalisanin/halalisanin.github.io.git")
    ok = run(f'git add . && git commit -m "Add blog post: {post_id}" && git push origin main')
    if ok:
        print("  ✓ Pushed! Live in ~60 seconds at https://halalisanin.github.io/post.html?id=" + post_id)
    else:
        print("  ✗ Push failed. Run manually: git add . && git commit -m 'post' && git push")

def post_to_telegram(title, excerpt, post_id):
    try:
        import urllib.request, urllib.parse
        bot_token = config.get("telegram_bot_token", "")
        chat_id   = config.get("telegram_chat_id", "")
        if not bot_token or not chat_id:
            print("  ⚠ Telegram not configured. Add telegram_bot_token and telegram_chat_id to social_config.json")
            return
        url   = f"https://halalisanin.github.io/post.html?id={post_id}"
        msg   = f"📝 New blog post!\n\n*{title}*\n\n{excerpt}\n\n[Read it here]({url})"
        data  = urllib.parse.urlencode({"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}).encode()
        req   = urllib.request.Request(f"https://api.telegram.org/bot{bot_token}/sendMessage", data=data)
        urllib.request.urlopen(req, timeout=10)
        print("  ✓ Posted to Telegram")
    except Exception as e:
        print(f"  ✗ Telegram error: {e}")

def post_to_twitter(title, excerpt, post_id):
    try:
        import tweepy
        keys = config.get("twitter", {})
        if not all(keys.get(k) for k in ["api_key","api_secret","access_token","access_token_secret"]):
            print("  ⚠ Twitter not configured in social_config.json")
            return
        client = tweepy.Client(
            consumer_key=keys["api_key"], consumer_secret=keys["api_secret"],
            access_token=keys["access_token"], access_token_secret=keys["access_token_secret"]
        )
        url  = f"https://halalisanin.github.io/post.html?id={post_id}"
        text = f"{title}\n\n{excerpt[:180]}…\n\n{url}"
        client.create_tweet(text=text[:280])
        print("  ✓ Posted to Twitter/X")
    except ImportError:
        print("  ⚠ tweepy not installed. Run: pip3 install tweepy")
    except Exception as e:
        print(f"  ✗ Twitter error: {e}")

# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("\n" + "─"*50)
    print("  New Blog Post — halalisanin.github.io")
    print("─"*50 + "\n")

    today  = datetime.date.today().isoformat()
    title  = prompt("Post title")
    if not title:
        print("  Title required. Exiting.")
        sys.exit(1)

    date   = prompt("Date (YYYY-MM-DD)", today)
    tags   = [t.strip() for t in prompt("Tags (comma-separated)", "career").split(",") if t.strip()]
    excerpt = prompt("Short excerpt (1–2 sentences)")
    if not excerpt:
        excerpt = f"A new post by Halalisani Ngema about {tags[0] if tags else 'career and AI'}."

    print(f"\n  Opening {EDITOR} for content. Save and close when done.\n")
    input("  Press Enter to open editor…")

    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as tmp:
        tmp.write(f"# {title}\n\nWrite your post here…\n")
        tmp_path = tmp.name

    subprocess.call([EDITOR, tmp_path])

    with open(tmp_path) as f:
        content = f.read()
    os.unlink(tmp_path)

    if content.strip() == f"# {title}\n\nWrite your post here…":
        print("\n  Content unchanged. Aborting.")
        sys.exit(0)

    print("\n" + "─"*50)
    post_id, _ = write_post(title, date, tags, excerpt, content)
    update_index(post_id, title, date, tags, excerpt)

    # GitHub push?
    push = prompt("\n  Push to GitHub now? (y/n)", "y").lower()
    if push == "y":
        push_to_github(post_id)

    # Socials
    tg = prompt("  Post to Telegram? (y/n)", "y").lower()
    if tg == "y":
        post_to_telegram(title, excerpt, post_id)

    tw = prompt("  Post to Twitter/X? (y/n)", "n").lower()
    if tw == "y":
        post_to_twitter(title, excerpt, post_id)

    print("\n  Done! ✓\n")

if __name__ == "__main__":
    main()
