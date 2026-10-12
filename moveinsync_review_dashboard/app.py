
import os
import json
import time
import sqlite3
import hashlib
from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from google_play_scraper import Sort, reviews

load_dotenv()

# =========================================================
# CONFIGURATION
# =========================================================

APP_ID = os.getenv("PLAY_STORE_APP_ID", "com.moveinsync.ets")
COUNTRY = os.getenv("PLAY_STORE_COUNTRY", "in")
LANGUAGE = os.getenv("PLAY_STORE_LANGUAGE", "en")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

DB_PATH = os.getenv("DATABASE_PATH", "reviews.db")

st.set_page_config(
    page_title="MoveInSync Review Intelligence",
    page_icon="📊",
    layout="wide",
)

# =========================================================
# DATABASE
# =========================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                review_id TEXT PRIMARY KEY,
                content TEXT,
                score INTEGER,
                thumbs_up_count INTEGER DEFAULT 0,
                app_version TEXT,
                review_date TEXT,
                fetched_at TEXT,
                sentiment TEXT,
                category TEXT,
                summary TEXT,
                analyzed_at TEXT
            )
        """)
        conn.commit()


def save_reviews(review_list):
    """Insert only new reviews; existing review IDs are ignored."""
    inserted = 0

    with get_connection() as conn:
        for review in review_list:
            content = str(review.get("content") or "").strip()
            if not content:
                continue

            review_id = str(
                review.get("reviewId")
                or hashlib.sha256(
                    (
                        content
                        + str(review.get("at"))
                        + str(review.get("score"))
                    ).encode("utf-8")
                ).hexdigest()
            )

            cursor = conn.execute("""
                INSERT OR IGNORE INTO reviews (
                    review_id, content, score, thumbs_up_count,
                    app_version, review_date, fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                review_id,
                content,
                review.get("score"),
                review.get("thumbsUpCount", 0),
                review.get("reviewCreatedVersion"),
                (
                    review.get("at").isoformat()
                    if review.get("at")
                    else None
                ),
                datetime.now(timezone.utc).isoformat(),
            ))

            inserted += cursor.rowcount

        conn.commit()

    return inserted


def load_reviews():
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT * FROM reviews ORDER BY review_date DESC",
            conn,
        )


def get_unanalyzed_reviews(limit=100):
    with get_connection() as conn:
        return conn.execute("""
            SELECT review_id, content, score
            FROM reviews
            WHERE analyzed_at IS NULL
            ORDER BY review_date DESC
            LIMIT ?
        """, (limit,)).fetchall()


def update_analysis(review_id, sentiment, category, summary):
    with get_connection() as conn:
        conn.execute("""
            UPDATE reviews
            SET sentiment = ?,
                category = ?,
                summary = ?,
                analyzed_at = ?
            WHERE review_id = ?
        """, (
            sentiment,
            category,
            summary,
            datetime.now(timezone.utc).isoformat(),
            review_id,
        ))
        conn.commit()


init_db()

# =========================================================
# GOOGLE PLAY REVIEW COLLECTION
# =========================================================

def fetch_play_store_reviews(count=100):
    """Fetch recent public reviews from Google Play."""
    collected = []
    continuation_token = None

    # Fetch in manageable pages.
    while len(collected) < count:
        page_size = min(100, count - len(collected))

        result, continuation_token = reviews(
            APP_ID,
            lang=LANGUAGE,
            country=COUNTRY,
            sort=Sort.NEWEST,
            count=page_size,
            continuation_token=continuation_token,
        )

        if not result:
            break

        collected.extend(result)

        if continuation_token is None:
            break

    return collected


# =========================================================
# GROQ AI CLASSIFICATION
# =========================================================

def get_groq_client():
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY is missing. Add it to your .env file."
        )
    return Groq(api_key=GROQ_API_KEY)


def extract_json(text):
    """Extract a JSON array/object even if the model adds code fences."""
    text = text.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Recover a JSON array or object from surrounding text.
    starts = [
        pos for pos in (
            text.find("["),
            text.find("{"),
        ) if pos >= 0
    ]

    if not starts:
        raise ValueError("The AI response did not contain JSON.")

    start = min(starts)
    end = max(text.rfind("]"), text.rfind("}"))

    if end < start:
        raise ValueError("The AI returned incomplete JSON.")

    return json.loads(text[start:end + 1])


def normalize_results(data, expected_count):
    """Normalize either a JSON list or a dictionary response."""
    if isinstance(data, dict):
        data = data.get(
            "reviews",
            data.get("results", data.get("items", [data]))
        )

    if not isinstance(data, list):
        raise ValueError("Expected a JSON list of review analyses.")

    normalized = []

    for item in data[:expected_count]:
        if not isinstance(item, dict):
            continue

        sentiment = str(item.get("sentiment", "Neutral")).title()
        if sentiment not in {"Positive", "Neutral", "Negative"}:
            sentiment = "Neutral"

        category = str(item.get("category", "Other")).strip()
        summary = str(
            item.get("summary", "No summary available.")
        ).strip()

        normalized.append({
            "sentiment": sentiment,
            "category": category[:100] or "Other",
            "summary": summary[:500] or "No summary available.",
        })

    return normalized


def classify_batch(batch):
    """Classify a small batch with retry handling for rate limits."""
    client = get_groq_client()

    review_text = [
        {
            "index": i,
            "rating": row["score"],
            "review": row["content"][:1200],
        }
        for i, row in enumerate(batch)
    ]

    prompt = f"""
You analyze customer reviews for the MoveInSync transportation app.

Classify each review independently. Do not invent facts.

Allowed sentiment values:
Positive, Neutral, Negative.

Choose a short category that best matches the review, such as:
App Stability, Login/Access, Pickup/Transport, Driver Experience,
Trip Scheduling, Customer Support, Payments, Feature Request, Other.

Return ONLY a valid JSON array. Do not use Markdown or extra text.
Return exactly one object per input review, in the same order.

Each object must contain:
{{
  "sentiment": "Positive | Neutral | Negative",
  "category": "short category",
  "summary": "brief summary of the user's feedback"
}}

Reviews:
{json.dumps(review_text, ensure_ascii=False)}
"""

    last_error = None

    for attempt in range(4):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a careful review analyst. "
                            "Return only valid JSON."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=1200,
            )

            choice = response.choices[0]

            if choice.finish_reason == "length":
                raise ValueError(
                    "AI response was truncated. Reduce the batch size."
                )

            content = choice.message.content or ""
            data = extract_json(content)
            results = normalize_results(data, len(batch))

            if len(results) != len(batch):
                raise ValueError(
                    "AI returned an unexpected number of results."
                )

            return results

        except Exception as exc:
            last_error = exc
            message = str(exc).lower()

            # Retry rate limits and temporary server errors.
            retryable = any(term in message for term in [
                "429", "rate limit", "rate_limit",
                "503", "502", "500", "timeout",
                "temporarily unavailable",
            ])

            if not retryable or attempt == 3:
                break

            time.sleep(min(2 ** attempt * 2, 20))

    raise RuntimeError(f"Groq analysis failed: {last_error}")


def analyze_pending_reviews(batch_size=3, max_reviews=30):
    """Analyze unclassified reviews in small batches."""
    pending = get_unanalyzed_reviews(limit=max_reviews)

    if not pending:
        return 0, 0

    successful = 0
    failed = 0

    for start in range(0, len(pending), batch_size):
        batch = pending[start:start + batch_size]

        try:
            results = classify_batch(batch)

            for row, result in zip(batch, results):
                update_analysis(
                    row["review_id"],
                    result["sentiment"],
                    result["category"],
                    result["summary"],
                )
                successful += 1

        except Exception as exc:
            failed += len(batch)
            st.warning(
                f"Could not analyze a batch of reviews: {exc}"
            )

    return successful, failed


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.title("⚙️ Dashboard Settings")

analysis_days = st.sidebar.selectbox(
    "Analysis window",
    options=[7, 30, 90, 180, 365],
    index=1,
    format_func=lambda n: f"Last {n} days",
)

reviews_per_fetch = st.sidebar.slider(
    "Reviews per fetch",
    min_value=10,
    max_value=200,
    value=50,
    step=10,
)

refresh_minutes = st.sidebar.selectbox(
    "Refresh interval",
    options=[5, 10, 15, 30, 60],
    index=2,
    format_func=lambda n: f"Every {n} minutes",
)

st.sidebar.caption(
    "Periodic collection operates while this dashboard and its "
    "refresh mechanism are running."
)

if st.sidebar.button("🔄 Fetch and analyze now", use_container_width=True):
    st.session_state["manual_refresh"] = True

# =========================================================
# PERIODIC REFRESH
# =========================================================

try:
    from streamlit_autorefresh import st_autorefresh

    st_autorefresh(
        interval=refresh_minutes * 60 * 1000,
        key="review_dashboard_refresh",
    )
    periodic_refresh_available = True

except ImportError:
    periodic_refresh_available = False
    st.sidebar.warning(
        "For automatic periodic refresh, install "
        "`streamlit-autorefresh`."
    )

# =========================================================
# HEADER
# =========================================================

st.title("📊 MoveInSync Review Intelligence")
st.markdown(
    "Monitor customer feedback, identify recurring issues, "
    "and turn public Play Store reviews into actionable insights."
)

st.caption(
    f"Last dashboard update: "
    f"{datetime.now().strftime('%d %b %Y, %I:%M:%S %p')}"
)

# =========================================================
# FETCH AND ANALYZE
# =========================================================

should_refresh = (
    st.session_state.pop("manual_refresh", False)
    or (
        periodic_refresh_available
        and st.session_state.get("last_auto_fetch") is None
    )
)

if periodic_refresh_available:
    # The autorefresh counter changes on each scheduled rerun.
    refresh_counter = st.session_state.get(
        "review_dashboard_refresh", 0
    )
    last_counter = st.session_state.get("last_processed_counter")

    if last_counter != refresh_counter:
        should_refresh = True
        st.session_state["last_processed_counter"] = refresh_counter

if should_refresh:
    try:
        with st.spinner("Fetching the latest Play Store reviews..."):
            fetched = fetch_play_store_reviews(reviews_per_fetch)
            inserted = save_reviews(fetched)

        st.session_state["last_auto_fetch"] = datetime.now().isoformat()

        st.success(
            f"Fetched {len(fetched)} reviews; "
            f"added {inserted} new reviews to the database."
        )

        if GROQ_API_KEY:
            with st.spinner("Analyzing new reviews with AI..."):
                successful, failed = analyze_pending_reviews(
                    batch_size=3,
                    max_reviews=150,
                )

            st.info(
                f"AI analysis completed for {successful} reviews. "
                f"Failed or deferred: {failed}."
            )
        else:
            st.warning(
                "Reviews were saved, but AI analysis was skipped. "
                "Configure GROQ_API_KEY in .env."
            )

    except Exception as exc:
        st.error(f"Refresh failed: {exc}")

# =========================================================
# LOAD AND FILTER DATA
# =========================================================

df = load_reviews()

if df.empty:
    st.info(
        "No reviews have been collected yet. "
        "Click **Fetch and analyze now** to get started."
    )
    st.stop()

df["review_date"] = pd.to_datetime(
    df["review_date"], errors="coerce", utc=True
)

cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(
    days=analysis_days
)

filtered = df[df["review_date"] >= cutoff].copy()
filtered = filtered.dropna(subset=["score"])
filtered["score"] = pd.to_numeric(
    filtered["score"], errors="coerce"
)
filtered = filtered.dropna(subset=["score"])

if filtered.empty:
    st.warning(
        "No reviews were found in this analysis window. "
        "Try a longer period or fetch more reviews."
    )
    st.stop()

filtered["score"] = filtered["score"].astype(int)
filtered["category"] = (
    filtered["category"].fillna("Unclassified")
)
filtered["sentiment"] = (
    filtered["sentiment"].fillna("Unclassified")
)
filtered["summary"] = filtered["summary"].fillna("")

# =========================================================
# KPI METRICS
# =========================================================

total_reviews = len(filtered)
average_rating = filtered["score"].mean()
negative_reviews = filtered[
    filtered["sentiment"] == "Negative"
]
low_rating_count = len(filtered[filtered["score"] <= 2])

analyzed_count = len(
    filtered[filtered["sentiment"] != "Unclassified"]
)

col1, col2, col3, col4 = st.columns(4)

col1.metric("Reviews", f"{total_reviews:,}")
col2.metric("Average rating", f"{average_rating:.2f} / 5")
col3.metric("Low ratings (1–2★)", f"{low_rating_count:,}")
col4.metric(
    "AI analyzed",
    f"{analyzed_count:,} / {total_reviews:,}",
)

st.divider()

# =========================================================
# CHARTS
# =========================================================

left, right = st.columns(2)

with left:
    st.subheader("Rating distribution")

    rating_counts = (
        filtered["score"]
        .value_counts()
        .reindex([1, 2, 3, 4, 5], fill_value=0)
        .rename_axis("Rating")
        .reset_index(name="Reviews")
    )

    fig = px.bar(
        rating_counts,
        x="Rating",
        y="Reviews",
        text="Reviews",
        title="Number of reviews by star rating",
    )
    fig.update_layout(xaxis=dict(dtick=1))
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Sentiment distribution")

    sentiment_counts = (
        filtered["sentiment"]
        .value_counts()
        .rename_axis("Sentiment")
        .reset_index(name="Reviews")
    )

    fig = px.pie(
        sentiment_counts,
        names="Sentiment",
        values="Reviews",
        title="AI-classified customer sentiment",
        hole=0.35,
    )
    st.plotly_chart(fig, use_container_width=True)

# =========================================================
# RATING TREND
# =========================================================

st.subheader("Rating trend over time")

trend_data = filtered.dropna(subset=["review_date"]).copy()

if not trend_data.empty:
    trend_data["Date"] = (
        trend_data["review_date"].dt.date.astype(str)
    )

    daily_trend = (
        trend_data.groupby("Date", as_index=False)
        .agg(
            Average_Rating=("score", "mean"),
            Review_Count=("review_id", "count"),
        )
    )

    fig = px.line(
        daily_trend,
        x="Date",
        y="Average_Rating",
        markers=True,
        title="Daily average star rating",
        hover_data=["Review_Count"],
    )
    fig.update_yaxes(range=[0, 5])
    st.plotly_chart(fig, use_container_width=True)

# =========================================================
# ISSUE ANALYSIS
# =========================================================

st.subheader("Recurring customer issues")

classified = filtered[
    filtered["sentiment"] != "Unclassified"
].copy()

if not classified.empty:
    issue_counts = (
        classified.groupby("category", as_index=False)
        .agg(
            Reviews=("review_id", "count"),
            Average_Rating=("score", "mean"),
        )
        .sort_values("Reviews", ascending=False)
    )

    fig = px.bar(
        issue_counts,
        x="Reviews",
        y="category",
        orientation="h",
        color="Average_Rating",
        title="Review volume by issue category",
        labels={"category": "Issue category"},
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        issue_counts.round(2),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info(
        "AI classifications are not available yet. "
        "Configure Groq and run a refresh to analyze reviews."
    )

# =========================================================
# NEGATIVE REVIEWS
# =========================================================

st.subheader("Negative customer feedback")

negative = filtered[
    (filtered["sentiment"] == "Negative")
    | (filtered["score"] <= 2)
].copy()

if not negative.empty:
    display_columns = [
        "review_date",
        "score",
        "category",
        "summary",
        "content",
    ]

    negative["review_date"] = (
        negative["review_date"].astype(str)
    )

    st.dataframe(
        negative[display_columns].sort_values(
            "score", ascending=True
        ),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info(
        "No low-rated or AI-classified negative reviews "
        "were found in this period."
    )

# =========================================================
# RECOMMENDATIONS
# =========================================================

st.subheader("Recommended actions")

if not negative.empty:
    if not classified.empty:
        negative_categories = classified[
            (classified["sentiment"] == "Negative")
            | (classified["score"] <= 2)
        ]

        category_counts = (
            negative_categories["category"]
            .value_counts()
        )
    else:
        category_counts = pd.Series(dtype=int)

    if not category_counts.empty:
        top_category = category_counts.index[0]
        top_count = int(category_counts.iloc[0])

        st.markdown(
            f"**1. Investigate the leading complaint:** "
            f"`{top_category}` appears in "
            f"{top_count} negative or low-rated reviews."
        )
    else:
        st.markdown(
            "**1. Investigate low-rated reviews:** "
            "Review the 1–2 star feedback to identify "
            "the main customer pain points."
        )

    st.markdown(
        "**2. Validate the cause:** Compare review findings "
        "with application logs, transport operations, and "
        "customer-support records."
    )
    st.markdown(
        "**3. Prioritize fixes:** Assign owners and deadlines "
        "to the most frequent, severe, and actionable issues."
    )
    st.markdown(
        "**4. Measure improvement:** Compare ratings and "
        "complaint frequency before and after each fix."
    )
else:
    st.markdown(
        "Continue collecting reviews and monitor rating trends. "
        "Use emerging complaints to prioritize investigations."
    )

st.caption(
    "Recommendations are based on available review data. "
    "Reviews indicate reported experiences and do not, by "
    "themselves, prove the underlying cause of a problem."
)

# =========================================================
# EXPORT
# =========================================================

st.subheader("Export review data")

csv_data = filtered.to_csv(index=False).encode("utf-8")

st.download_button(
    label="⬇️ Download filtered reviews as CSV",
    data=csv_data,
    file_name="moveinsync_reviews.csv",
    mime="text/csv",
)

with st.expander("Database and collection information"):
    st.write(f"Total stored reviews: {len(df):,}")
    st.write(f"Reviews in selected window: {len(filtered):,}")
    st.write(f"Application ID: {APP_ID}")
    st.write(f"Country: {COUNTRY}")
    st.write(f"Language: {LANGUAGE}")
    st.write(f"AI model: {GROQ_MODEL}")
