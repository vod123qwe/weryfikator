# WERYFIKATOR — Portal Informacyjny z AI Fact-Checkingiem

Portal agreguje newsy z 9 źródeł RSS, grupuje tematy, weryfikuje fakty przez Wikipedia API i 2 fact-checkery (AFP, Demagog), a następnie generuje syntetyczne artykuły po polsku przy użyciu Groq API (LLaMA 3). Każdy artykuł posiada wskaźnik wiarygodności (0–100%) i flagę FAKE NEWS jeśli wykryto dezinformację. Koszt działania: **$0/miesiąc**.

## Architektura

```
┌─────────────────────────────────────────────────────┐
│                   GITHUB ACTIONS                    │
│   cron: co 30 minut                                 │
│                                                     │
│  RSS Feeds (9x) ──► fetch_and_generate.py           │
│  AFP / Demagog  ──► grupowanie tematów              │
│  Wikipedia API  ──► weryfikacja kontekstu           │
│  Groq (LLaMA3)  ──► generowanie artykułów (JSON)   │
│                          │                          │
│                          ▼                          │
│               data/articles.json                    │
│               git commit + push                     │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│                  GITHUB PAGES                       │
│                                                     │
│   index.html + assets/app.js + assets/style.css     │
│   fetch('./data/articles.json') co 5 minut          │
│   Filtrowanie, modal, trust badge, fake news alert  │
└─────────────────────────────────────────────────────┘
```

## Instalacja (5 kroków)

1. **Fork / push repozytorium na GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Init WERYFIKATOR"
   git remote add origin https://github.com/{username}/{repo}.git
   git push -u origin main
   ```

2. **Włącz GitHub Pages:**
   Settings → Pages → Source: `Deploy from branch` → `main` → `/ (root)` → Save

3. **Zdobądź darmowy klucz Groq API:**
   Zarejestruj się na [console.groq.com](https://console.groq.com) (darmowy tier, brak karty)

4. **Dodaj Secret:**
   Settings → Secrets and variables → Actions → New repository secret
   - Name: `GROQ_API_KEY`
   - Value: klucz z Groq Console

5. **Pierwsze uruchomienie:**
   Actions → "Aktualizacja newsow" → Run workflow
   Po ~2 min portal będzie dostępny pod: `https://{username}.github.io/{repo}/`

## Tabela kosztów

| Komponent        | Plan        | Koszt/mies. |
|------------------|-------------|-------------|
| GitHub Pages     | Free        | $0          |
| GitHub Actions   | Free (2000 min/mies.) | $0 |
| Groq API         | Free tier   | $0          |
| Wikipedia API    | Public      | $0          |
| RSS Feeds        | Public      | $0          |
| **RAZEM**        |             | **$0**      |

## Dostosowywanie

**Źródła RSS** — edytuj listę `RSS_FEEDS` w `scripts/fetch_and_generate.py`:
```python
{"name": "Nowe Źródło", "url": "https://example.com/rss.xml", "category": "Polska"},
```

**Częstotliwość aktualizacji** — edytuj cron w `.github/workflows/update_news.yml`:
```yaml
- cron: '*/30 * * * *'   # co 30 min (domyślnie)
- cron: '0 * * * *'      # co godzinę
- cron: '0 */6 * * *'    # co 6 godzin
```

**Model AI** — zmień stałą w `scripts/fetch_and_generate.py`:
```python
GROQ_MODEL = "llama3-8b-8192"      # szybki, darmowy (domyślnie)
GROQ_MODEL = "llama3-70b-8192"     # dokładniejszy (większy limit tokenów)
GROQ_MODEL = "mixtral-8x7b-32768"  # długi kontekst
```

## Struktura plików

```
weryfikator/
├── index.html                    # Portal (HTML5, brak frameworków JS)
├── assets/
│   ├── style.css                 # Bloomberg dark theme, IBM Plex fonts
│   └── app.js                    # Logika frontendu (vanilla JS)
├── data/
│   └── articles.json             # Auto-generowany przez Actions
├── scripts/
│   └── fetch_and_generate.py     # Agregacja RSS + Groq AI
├── .github/
│   └── workflows/
│       └── update_news.yml       # GitHub Actions cron
└── README.md
```
