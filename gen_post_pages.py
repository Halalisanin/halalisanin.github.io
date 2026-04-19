#!/usr/bin/env python3
"""
gen_post_pages.py
=================
Generates one lightweight HTML page per blog post.
Each page has STATIC og: meta tags so that Facebook, LinkedIn, and X
correctly show the featured image + title when the URL is shared.
The page immediately redirects to post.html?id=... for actual rendering.

Run after adding posts or changing post metadata:
    python3 gen_post_pages.py

IMPORTANT: og:image is a relative path here.
When you deploy to a real domain, run this one-liner to make it absolute:
    sed -i 's|og:image\" content=\"posts/|og:image" content="https://YOURDOMAIN.com/posts/|g' *.html
"""
import json, os, html as htmllib
from pathlib import Path

PROFILE_DIR = Path(__file__).resolve().parent
INDEX_PATH  = PROFILE_DIR / 'posts' / 'index.json'

posts = json.loads(INDEX_PATH.read_text(encoding='utf-8'))

TMPL = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title_e} &mdash; Halalisani Ngema</title>
  <meta name="description" content="{excerpt_e}" />

  <!-- Open Graph / Facebook
       NOTE: og:image needs an ABSOLUTE URL for Facebook to show the image.
       After deploying replace posts/images/ with https://yourdomain.com/posts/images/
       or run:  sed -i 's|content="posts/|content="https://yourdomain.com/posts/|g' *.html -->
  <meta property="og:type"        content="article" />
  <meta property="og:site_name"   content="Halalisani Ngema" />
  <meta property="og:title"       content="{title_e}" />
  <meta property="og:description" content="{excerpt_e}" />
  <meta property="og:image"       content="{image}" />
  <meta property="og:url"         content="{post_id}.html" />

  <!-- Twitter / X -->
  <meta name="twitter:card"        content="summary_large_image" />
  <meta name="twitter:title"       content="{title_e}" />
  <meta name="twitter:description" content="{excerpt_e}" />
  <meta name="twitter:image"       content="{image}" />

  <!-- Redirect real visitors to the full post renderer -->
  <script>window.location.replace('post.html?id={post_id}');</script>
  <noscript><meta http-equiv="refresh" content="0;url=post.html?id={post_id}" /></noscript>
</head>
<body style="margin:0;background:#080810;font-family:sans-serif;color:#8a8070;display:flex;align-items:center;justify-content:center;min-height:100vh;">
  <p>Loading&hellip; &nbsp;<a href="post.html?id={post_id}" style="color:#c9a84c;">Click here if not redirected</a></p>
</body>
</html>
"""

count = 0
for p in posts:
    pid      = p['id']
    title_e  = htmllib.escape(p.get('title',   ''), quote=True)
    excerpt_e= htmllib.escape(p.get('excerpt', ''), quote=True)
    image    = p.get('image', '')          # e.g. posts/images/foo.webp

    content = TMPL.format(
        post_id  = pid,
        title_e  = title_e,
        excerpt_e= excerpt_e,
        image    = image,
    )
    out = PROFILE_DIR / f'{pid}.html'
    out.write_text(content, encoding='utf-8')
    count += 1

print(f'Generated {count} social-sharing pages.')
print('Share links now look like:  post-ID.html  (e.g. 2026-04-22-job-hunting-strategy.html)')
print('\nTo add absolute URLs for Facebook once deployed, run:')
print('  sed -i \'s|content="posts/|content="https://yourdomain.com/posts/|g\' *.html')
