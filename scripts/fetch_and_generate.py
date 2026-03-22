#!/usr/bin/env python3
"""
WERYFIKATOR — Skrypt agregacji RSS + generowanie artykułów przez Groq AI.
Wymaga: pip install feedparser requests
"""

import argparse
import os
import json
import time
import re
import hashlib
import datetime
import feedparser
import requests

# ─── KONFIGURACJA ────────────────────────────────────────────────────────────

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama3-8b-8192"
MAX_ARTICLES = 10
OUTPUT_PATH  = os.path.join(os.path.dirname(__file__), "..", "data", "articles.json")

RSS_FEEDS = [
    # POLSKA
    {"name": "PAP",         "url": "https://www.pap.pl/rss.xml",               "category": "Polska"},
    {"name": "TVN24",       "url": "https://tvn24.pl/najnowsze.xml",            "category": "Polska"},
    {"name": "Polsat News", "url": "https://www.polsatnews.pl/rss/polska.xml",  "category": "Polska"},
    {"name": "Onet",        "url": "https://wiadomosci.onet.pl/.feed",          "category": "Polska"},

    # SWIAT
    {"name": "BBC World",   "url": "https://feeds.bbci.co.uk/news/world/rss.xml",  "category": "Swiat"},
    {"name": "Reuters",     "url": "https://feeds.reuters.com/reuters/topNews",    "category": "Swiat"},
    {"name": "AP News",     "url": "https://rsshub.app/apnews/topics/apf-topnews", "category": "Swiat"},

    # EUROPA
    {"name": "Euronews PL", "url": "https://pl.euronews.com/rss",               "category": "Europa"},
    {"name": "DW Polska",   "url": "https://rss.dw.com/xml/rss-pol-all",        "category": "Europa"},

    # FACT-CHECKERS (tylko weryfikacja)
    {"name": "AFP FactCheck","url": "https://factcheck.afp.com/list/all/feed",  "category": "_factcheck"},
    {"name": "Demagog",     "url": "https://demagog.org.pl/feed/",              "category": "_factcheck"},
]

# ─── KROK 1: POBIERANIE RSS ───────────────────────────────────────────────────

def extract_image(entry):
    """Wyciągnij URL obrazu z wpisu RSS."""
    # media_content
    if hasattr(entry, "media_content") and entry.media_content:
        url = entry.media_content[0].get("url")
        if url:
            return url
    # enclosures
    if hasattr(entry, "enclosures") and entry.enclosures:
        href = entry.enclosures[0].get("href")
        if href and href.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            return href
    # img src w summary
    summary = getattr(entry, "summary", "") or ""
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary)
    if match:
        return match.group(1)
    return None

def clean_text(text, max_len=400):
    """Usuń HTML tagi i przytnij tekst."""
    text = re.sub(r'<[^>]+>', '', text or '')
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_len]

def fetch_all_feeds():
    """Pobierz wpisy ze wszystkich feedów."""
    news_items = []
    factcheck_items = []

    for feed_def in RSS_FEEDS:
        try:
            print(f"  Pobieranie: {feed_def['name']} ...", end="", flush=True)
            parsed = feedparser.parse(feed_def["url"])
            entries = parsed.entries[:5]

            for entry in entries:
                item = {
                    "source_name": feed_def["name"],
                    "category":    feed_def["category"],
                    "title":       clean_text(getattr(entry, "title", ""), 200),
                    "summary":     clean_text(getattr(entry, "summary", ""), 400),
                    "link":        getattr(entry, "link", ""),
                    "published":   getattr(entry, "published", ""),
                    "image_url":   extract_image(entry),
                }
                if feed_def["category"] == "_factcheck":
                    factcheck_items.append(item)
                else:
                    news_items.append(item)

            print(f" {len(entries)} wpisów")
        except Exception as e:
            print(f" BŁĄD: {e}")

        time.sleep(0.3)

    return news_items, factcheck_items

# ─── KROK 2: GRUPOWANIE TEMATÓW ──────────────────────────────────────────────

def tokenize(title):
    """Tokenizuj tytuł — słowa dłuższe niż 3 znaki."""
    words = re.findall(r'\b\w{4,}\b', title.lower())
    return set(words)

def group_articles(items):
    """Grupuj artykuły według podobieństwa tytułów."""
    clusters = []
    used = set()

    for i, item in enumerate(items):
        if i in used:
            continue
        cluster = [item]
        tokens_i = tokenize(item["title"])
        for j, other in enumerate(items):
            if j <= i or j in used:
                continue
            tokens_j = tokenize(other["title"])
            if len(tokens_i & tokens_j) >= 2:
                cluster.append(other)
                used.add(j)
        used.add(i)
        clusters.append(cluster)

    # Posortuj klastry po liczności (malejąco)
    clusters.sort(key=lambda c: len(c), reverse=True)

    # Fallback: jeśli za mało klastrów, wróć do pojedynczych artykułów
    if len(clusters) < 4:
        clusters = [[item] for item in items]

    return clusters[:MAX_ARTICLES]

# ─── KROK 3: WERYFIKACJA ZEWNĘTRZNA ──────────────────────────────────────────

def get_wikipedia_context(title):
    """Pobierz streszczenie z Wikipedia dla głównego słowa kluczowego."""
    words = re.findall(r'\b\w{5,}\b', title)
    if not words:
        return "brak"
    keyword = words[0]
    try:
        url = f"https://pl.wikipedia.org/api/rest_v1/page/summary/{keyword}"
        resp = requests.get(url, timeout=5,
                            headers={"User-Agent": "Weryfikator/1.0 (bot@weryfikator.pl)"})
        if resp.status_code == 200:
            data = resp.json()
            extract = data.get("extract", "")[:300]
            if extract:
                return extract
    except Exception:
        pass
    return "brak"

def check_factcheckers(cluster_titles, factcheck_items):
    """Sprawdź czy temat klastra jest flagowany przez fact-checkerów."""
    warnings = []
    cluster_words = set()
    for title in cluster_titles:
        cluster_words.update(tokenize(title))

    for fc in factcheck_items:
        fc_words = tokenize(fc["title"])
        if len(cluster_words & fc_words) >= 2:
            warnings.append(f"[{fc['source_name']}] {fc['title']}")

    return "\n".join(warnings) if warnings else "brak ostrzeżeń"

# ─── KROK 4: GENEROWANIE PRZEZ GROQ ─────────────────────────────────────────

SYSTEM_PROMPT = """Jestes redaktorem naczelnym polskiego portalu informacyjnego WERYFIKATOR.
Piszesz rzetelne, obiektywne artykuly w jezyku polskim.
Wskazujesz rozbieznosci miedzy zrodlami.
Wykrywasz potencjalne fake newsy na podstawie ostrzezen fact-checkerow.
Odpowiadasz WYLACZNIE w formacie JSON bez zadnych komentarzy ani markdown."""

def build_user_prompt(cluster, wiki_context, fc_warnings):
    """Zbuduj prompt dla Groq."""
    sources_text = "\n".join(
        f"[{item['source_name']}]: {item['title']} — {item['summary'][:200]}"
        for item in cluster
    )
    return f"""Na podstawie ponizszych doniesien napisz zweryfikowany artykul po polsku.

ZRODLA:
{sources_text}

KONTEKST WIKIPEDIA:
{wiki_context}

OSTRZEZENIA FACT-CHECKERS:
{fc_warnings}

Zwroc dokladnie ten JSON (bez markdown, bez komentarzy):
{{
  "title": "tytul max 90 znakow",
  "category": "Swiat|Polska|Europa|Biznes|Technologia",
  "excerpt": "streszczenie 1-2 zdania",
  "content": "akapit1\\n\\nakapit2\\n\\nakapit3\\n\\nakapit4",
  "trust_score": 0-100,
  "is_fake": true/false,
  "fake_reason": "opis lub null",
  "discrepancies": "opis rozbieznosci lub pusty string",
  "reasoning": "uzasadnienie oceny wiarygodnosci",
  "checks": [
    {{"label": "...", "status": "pass|warn|fail"}},
    {{"label": "...", "status": "pass|warn|fail"}},
    {{"label": "...", "status": "pass|warn|fail"}},
    {{"label": "...", "status": "pass|warn|fail"}},
    {{"label": "...", "status": "pass|warn|fail"}},
    {{"label": "...", "status": "pass|warn|fail"}}
  ]
}}"""

def call_groq(cluster, wiki_context, fc_warnings):
    """Wywołaj Groq API i zwróć sparsowany JSON."""
    if not GROQ_API_KEY:
        raise ValueError("Brak GROQ_API_KEY w zmiennych środowiskowych.")

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": build_user_prompt(cluster, wiki_context, fc_warnings)},
        ],
        "max_tokens":  1500,
        "temperature": 0.4,
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type":  "application/json",
    }
    resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()

    content = resp.json()["choices"][0]["message"]["content"].strip()
    # Usuń ewentualne bloki markdown
    content = re.sub(r'^```json\s*', '', content)
    content = re.sub(r'^```\s*', '', content)
    content = re.sub(r'\s*```$', '', content)
    return json.loads(content)

# ─── KROK 5: ZAPIS ───────────────────────────────────────────────────────────

def build_article(ai_result, cluster):
    """Złóż finalny obiekt artykułu."""
    title = ai_result.get("title", "")
    article_id = abs(int(hashlib.md5(title.encode()).hexdigest(), 16)) % 100000

    # Obraz z pierwszego wpisu w klastrze który ma URL
    image_url = next((item["image_url"] for item in cluster if item.get("image_url")), None)

    sources = [
        {"name": item["source_name"], "headline": item["title"], "url": item["link"]}
        for item in cluster
    ]

    checks = ai_result.get("checks", [])

    return {
        "id":           article_id,
        "title":        title[:90],
        "category":     ai_result.get("category", "Swiat"),
        "excerpt":      ai_result.get("excerpt", ""),
        "content":      ai_result.get("content", ""),
        "image_url":    image_url,
        "published_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trust_score":  int(ai_result.get("trust_score", 50)),
        "is_fake":      bool(ai_result.get("is_fake", False)),
        "fake_reason":  ai_result.get("fake_reason", None),
        "sources":      sources,
        "verification": {
            "checks":        checks,
            "discrepancies": ai_result.get("discrepancies", ""),
            "reasoning":     ai_result.get("reasoning", ""),
        },
    }

# ─── TRYB BEZ AI ─────────────────────────────────────────────────────────────

def build_article_from_rss(item):
    """Zbuduj artykuł bezpośrednio z wpisu RSS, bez wywołania Groq."""
    title = item["title"][:90]
    article_id = abs(int(hashlib.md5(title.encode()).hexdigest(), 16)) % 100000
    return {
        "id":           article_id,
        "title":        title,
        "category":     item["category"],
        "excerpt":      item["summary"][:200] if item["summary"] else "",
        "content":      item["summary"] or "",
        "image_url":    item.get("image_url"),
        "published_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trust_score":  50,
        "is_fake":      False,
        "fake_reason":  None,
        "sources": [{"name": item["source_name"], "headline": item["title"], "url": item["link"]}],
        "verification": {
            "checks": [
                {"label": "Pobrano z RSS", "status": "pass"},
                {"label": "Brak weryfikacji AI", "status": "warn"},
                {"label": "Brak analizy fact-checkerow", "status": "warn"},
            ],
            "discrepancies": "",
            "reasoning": "Artykul pochodzi bezposrednio z RSS bez weryfikacji AI. Uruchom skrypt bez --no-ai aby uzyskac pelna analize.",
        },
    }

# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="WERYFIKATOR — agregacja RSS")
    parser.add_argument("--no-ai", action="store_true",
                        help="Pominij Groq API i uzyj surowych danych RSS (do testow lokalnych)")
    args = parser.parse_args()

    start_time = time.time()
    print("=== WERYFIKATOR — start agregacji ===")

    # Krok 1
    print("\n[1/2] Pobieranie RSS..." if args.no_ai else "\n[1/5] Pobieranie RSS...")
    news_items, factcheck_items = fetch_all_feeds()
    print(f"  Pobrano: {len(news_items)} newsów, {len(factcheck_items)} fact-checków")

    if not news_items:
        print("BŁĄD: Brak danych z RSS. Sprawdź połączenie.")
        return

    articles = []
    fake_count = 0

    if args.no_ai:
        # ── Tryb bez AI: surowe RSS, bez Groq ──
        print(f"\n[2/2] Budowanie artykułów z RSS (bez AI)...")
        candidates = [i for i in news_items][:MAX_ARTICLES]
        for item in candidates:
            article = build_article_from_rss(item)
            articles.append(article)
            print(f"  + {article['title'][:70]}")
    else:
        # ── Tryb pełny: grupowanie + Groq ──
        print("\n[2/5] Grupowanie tematów...")
        clusters = group_articles(news_items)
        print(f"  Klastrów: {len(clusters)}")

        print("\n[3-4/5] Weryfikacja + generowanie artykułów przez Groq...")
        for idx, cluster in enumerate(clusters):
            print(f"  [{idx+1}/{len(clusters)}] Klaster: {cluster[0]['title'][:60]}...")

            wiki_ctx = get_wikipedia_context(cluster[0]["title"])
            fc_warnings = check_factcheckers([item["title"] for item in cluster], factcheck_items)

            try:
                ai_result = call_groq(cluster, wiki_ctx, fc_warnings)
                article = build_article(ai_result, cluster)
                articles.append(article)
                if article["is_fake"]:
                    fake_count += 1
                print(f"     OK — trust: {article['trust_score']}%, fake: {article['is_fake']}")
            except Exception as e:
                print(f"     BŁĄD Groq: {e}")

            time.sleep(0.5)

    step = "3/3" if args.no_ai else "5/5"
    print(f"\n[{step}] Zapis do data/articles.json...")
    output = {
        "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "articles":     articles,
    }
    os.makedirs(os.path.dirname(os.path.abspath(OUTPUT_PATH)), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - start_time
    mode_label = "RSS-only (bez AI)" if args.no_ai else f"{fake_count} fake"
    print(f"\n=== GOTOWE: {len(articles)} artykułów ({mode_label}), czas: {elapsed:.1f}s ===")

if __name__ == "__main__":
    main()
