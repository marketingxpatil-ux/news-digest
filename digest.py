import feedparser
import os
import json
from datetime import datetime, timezone, timedelta
import google.generativeai as genai

# ── Gemini setup ──────────────────────────────────────────────────────────────
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")

# ── RSS Feeds per industry ────────────────────────────────────────────────────
FEEDS = {
    "Healthcare": [
        "https://www.statnews.com/feed/",
        "https://www.who.int/rss-feeds/news-english.xml",
        "https://www.fiercehealthcare.com/rss/xml",
        "https://kffhealthnews.org/feed/",
    ],
    "Pharma": [
        "https://www.fiercepharma.com/rss/xml",
        "https://endpts.com/feed/",
        "https://www.biopharmadive.com/feeds/news/",
        "https://www.pharmaceutical-technology.com/feed/",
    ],
    "Artificial Intelligence": [
        "https://www.technologyreview.com/feed/",
        "https://venturebeat.com/category/ai/feed/",
        "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
        "https://feeds.feedburner.com/AIWeekly",
    ],
    "Venture Capital": [
        "https://techcrunch.com/category/venture/feed/",
        "https://news.crunchbase.com/feed/",
        "https://pitchbook.com/news/rss",
        "https://www.axios.com/feeds/feed.rss",
    ],
}

ICONS = {
    "Healthcare": "🏥",
    "Pharma": "💊",
    "Artificial Intelligence": "🤖",
    "Venture Capital": "💰",
}


# ── Fetch articles from RSS ───────────────────────────────────────────────────
def fetch_articles(feed_urls, hours=24):
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    except Exception:
                        pass

                if published is None or published > cutoff:
                    summary = getattr(entry, "summary", "") or ""
                    # Strip HTML tags roughly
                    import re
                    summary = re.sub(r"<[^>]+>", "", summary)[:600]
                    articles.append({
                        "title": entry.get("title", "").strip(),
                        "summary": summary.strip(),
                        "link": entry.get("link", ""),
                        "source": feed.feed.get("title", url),
                    })
        except Exception as e:
            print(f"  ⚠ Could not fetch {url}: {e}")

    return articles


# ── Ask Gemini for top 5 ──────────────────────────────────────────────────────
def get_top5(industry, articles):
    if not articles:
        return []

    article_text = "\n\n---\n\n".join([
        f"Title: {a['title']}\nSource: {a['source']}\nSummary: {a['summary']}\nURL: {a['link']}"
        for a in articles[:35]
    ])

    prompt = f"""You are a sharp industry analyst tracking the {industry} sector.

Below are today's news articles. Select the TOP 5 most important and impactful developments.

{article_text}

For each of the 5 stories, provide:
- headline: A punchy, clear headline (rewrite the original if needed, max 12 words)
- why_it_matters: Exactly 2 sentences — what happened, and why it matters to someone following this industry
- source: The publication name
- url: The original article URL

Respond ONLY with a valid JSON array of 5 objects. No markdown, no backticks, no preamble."""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        # Strip code fences if Gemini wraps in them
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                try:
                    return json.loads(part)
                except Exception:
                    continue
        return json.loads(text)
    except Exception as e:
        print(f"  ⚠ Gemini parse error for {industry}: {e}")
        return []


# ── Build the HTML page ───────────────────────────────────────────────────────
def build_html(digests):
    date_str = datetime.now().strftime("%A, %B %d, %Y")
    ist_time = (datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)).strftime("%I:%M %p IST")

    sections = ""
    for industry, items in digests.items():
        icon = ICONS.get(industry, "📰")
        if not items:
            stories_html = '<p class="empty">No stories found for today.</p>'
        else:
            stories_html = ""
            for i, item in enumerate(items, 1):
                stories_html += f"""
                <article class="story">
                    <div class="story-num">{i:02d}</div>
                    <div class="story-body">
                        <h3 class="story-headline">{item.get('headline', 'Untitled')}</h3>
                        <p class="story-why">{item.get('why_it_matters', '')}</p>
                        <footer class="story-foot">
                            <span class="story-src">{item.get('source', '')}</span>
                            <a class="story-link" href="{item.get('url','#')}" target="_blank" rel="noopener">Read full story ↗</a>
                        </footer>
                    </div>
                </article>"""

        sections += f"""
        <section class="industry">
            <div class="industry-label">
                <span class="industry-icon">{icon}</span>
                <h2 class="industry-title">{industry}</h2>
            </div>
            <div class="stories">{stories_html}</div>
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daily Digest · {date_str}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,900;1,700&family=Source+Serif+4:ital,opsz,wght@0,8..60,300;0,8..60,400;1,8..60,300&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --bg:        #0c0c0f;
    --surface:   #141418;
    --border:    #242430;
    --accent:    #c9a84c;
    --accent2:   #7b9cdc;
    --text:      #e8e4d9;
    --muted:     #7a7870;
    --dim:       #3a3830;
  }}

  html {{ scroll-behavior: smooth; }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Source Serif 4', Georgia, serif;
    font-size: 17px;
    line-height: 1.7;
    min-height: 100vh;
  }}

  /* ── Header ── */
  header {{
    border-bottom: 1px solid var(--border);
    padding: 48px 0 32px;
    text-align: center;
    background: linear-gradient(180deg, #0a0a0d 0%, var(--bg) 100%);
  }}

  .header-eyebrow {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.2em;
    color: var(--accent);
    text-transform: uppercase;
    margin-bottom: 16px;
  }}

  .site-title {{
    font-family: 'Playfair Display', Georgia, serif;
    font-size: clamp(42px, 7vw, 80px);
    font-weight: 900;
    letter-spacing: -0.02em;
    line-height: 1;
    background: linear-gradient(135deg, #e8e4d9 30%, var(--accent) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }}

  .site-subtitle {{
    margin-top: 10px;
    font-size: 15px;
    color: var(--muted);
    font-style: italic;
    font-weight: 300;
  }}

  .header-meta {{
    margin-top: 28px;
    display: flex;
    justify-content: center;
    gap: 32px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--muted);
    letter-spacing: 0.08em;
  }}

  .header-meta span {{ display: flex; align-items: center; gap: 6px; }}
  .header-meta span::before {{ content: '—'; color: var(--dim); }}

  /* ── Nav pills ── */
  nav {{
    display: flex;
    justify-content: center;
    gap: 8px;
    padding: 24px 16px;
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
  }}

  nav a {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    text-decoration: none;
    color: var(--muted);
    border: 1px solid var(--border);
    padding: 6px 14px;
    border-radius: 2px;
    transition: all 0.2s;
  }}

  nav a:hover {{
    color: var(--accent);
    border-color: var(--accent);
    background: rgba(201,168,76,0.05);
  }}

  /* ── Main content ── */
  main {{
    max-width: 860px;
    margin: 0 auto;
    padding: 0 24px 80px;
  }}

  /* ── Industry section ── */
  .industry {{
    margin-top: 64px;
  }}

  .industry-label {{
    display: flex;
    align-items: center;
    gap: 14px;
    padding-bottom: 16px;
    border-bottom: 2px solid var(--accent);
    margin-bottom: 32px;
  }}

  .industry-icon {{
    font-size: 22px;
  }}

  .industry-title {{
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 26px;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--text);
  }}

  /* ── Story card ── */
  .story {{
    display: grid;
    grid-template-columns: 40px 1fr;
    gap: 20px;
    padding: 24px 0;
    border-bottom: 1px solid var(--border);
  }}

  .story:last-child {{ border-bottom: none; }}

  .story-num {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--accent);
    letter-spacing: 0.05em;
    padding-top: 5px;
    font-weight: 500;
  }}

  .story-headline {{
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 19px;
    font-weight: 700;
    line-height: 1.35;
    color: var(--text);
    margin-bottom: 10px;
    letter-spacing: -0.01em;
  }}

  .story-why {{
    font-size: 15px;
    color: #b5b0a5;
    line-height: 1.65;
    font-weight: 300;
    margin-bottom: 14px;
  }}

  .story-foot {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }}

  .story-src {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--muted);
  }}

  .story-link {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--accent2);
    text-decoration: none;
    letter-spacing: 0.05em;
    transition: color 0.2s;
  }}

  .story-link:hover {{ color: var(--accent); }}

  .empty {{
    color: var(--muted);
    font-style: italic;
    font-size: 15px;
    padding: 24px 0;
  }}

  /* ── Footer ── */
  footer {{
    text-align: center;
    padding: 40px 24px;
    border-top: 1px solid var(--border);
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--dim);
    letter-spacing: 0.08em;
  }}

  footer strong {{ color: var(--muted); }}
</style>
</head>
<body>

<header>
  <p class="header-eyebrow">Your daily intelligence briefing</p>
  <h1 class="site-title">The Digest</h1>
  <p class="site-subtitle">Healthcare · Pharma · AI · Venture Capital</p>
  <div class="header-meta">
    <span>{date_str}</span>
    <span>Updated {ist_time}</span>
    <span>Top 5 per sector</span>
  </div>
</header>

<nav>
  <a href="#healthcare">🏥 Healthcare</a>
  <a href="#pharma">💊 Pharma</a>
  <a href="#ai">🤖 AI</a>
  <a href="#vc">💰 Venture Capital</a>
</nav>

<main>
  <div id="healthcare"></div>
  <div id="pharma"></div>
  <div id="ai"></div>
  <div id="vc"></div>
  {sections}
</main>

<footer>
  <p>Generated daily by <strong>Gemini Flash</strong> · Powered by RSS · Hosted on <strong>GitHub Pages</strong></p>
  <p style="margin-top:8px">Built for signal, not noise.</p>
</footer>

</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🗞  Starting daily digest generation...\n")
    digests = {}

    for industry, feed_urls in FEEDS.items():
        print(f"📡 Fetching: {industry}")
        articles = fetch_articles(feed_urls)
        print(f"   Found {len(articles)} articles")

        print(f"🤖 Asking Gemini for top 5...")
        top5 = get_top5(industry, articles)
        print(f"   Got {len(top5)} stories\n")
        digests[industry] = top5

    print("🎨 Building HTML page...")
    html = build_html(digests)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("✅ index.html written successfully.")
