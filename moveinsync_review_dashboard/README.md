# MoveInSync Review Intelligence Dashboard

## What it does
- Fetches public Google Play reviews or imports your CSV.
- Uses Groq to assign issue labels, secondary labels, summaries, evidence phrases, impact, suspected cause, confidence and actionability.
- Tracks rating distributions, sample average rating, low-rating share, issue counts and monthly trends.
- Includes searchable reviews, CSV export, AI-generated findings/recommendations and refresh history.
- Stores records in local SQLite and skips duplicate review IDs.

## Setup
Python 3.10+ recommended.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env`, add your Groq key, and verify the Play Store app ID from the official listing. Never commit `.env`.

```bash
streamlit run app.py
```

Click **Fetch & analyze now**, or import an existing reviews CSV. Expected fields include `reviewId`/`review_id`, `content`/`review_text`, `score`/`rating`, `at`/`review_date`; app version is optional.

## Periodic tracking
Choose a refresh interval in the sidebar. The dashboard checks the interval only while the Streamlit process is alive. For reliable unattended monitoring, run a scheduled worker (cron, GitHub Actions or a persistent service) and store data on persistent storage. Streamlit hosting may sleep/restart; local SQLite may be ephemeral.

## Limitations
- Review scraping is best-effort and can be incomplete or rate-limited.
- Sample average rating is not the official Play Store rating.
- Reviews do not prove actual cab arrival times, booking success, crash rates or internal causes.
- Validate AI labels against real reviews; human-review safety complaints promptly.
