# movinsync-review-analyzer
# MoveInSync Review Intelligence Dashboard

An AI-powered dashboard that analyzes public Google Play Store reviews of the MoveInSync application to identify customer complaints, understand user sentiment, track recurring issues, and generate actionable recommendations to improve user ratings and experience.

## Overview

Customer reviews contain valuable feedback about app stability, employee transportation, driver experience, pickup reliability, and customer support. Manually analyzing large numbers of reviews is time-consuming.

This project automates the process by periodically collecting public Play Store reviews, storing new reviews, classifying feedback using a Large Language Model (LLM), and visualizing important trends through an interactive Streamlit dashboard.

## Key Features

- **Automated Review Collection:** Fetches public MoveInSync reviews from the Google Play Store.
- **Periodic Refresh:** Rechecks for new reviews at a configurable interval while the Streamlit application is running.
- **Duplicate Prevention:** Uses SQLite to store reviews and avoid processing the same review repeatedly.
- **AI-Powered Review Analysis:** Uses the Groq API to classify reviews, summarize complaints, and identify recurring themes.
- **Rating Analysis:** Tracks review ratings and identifies low-rated feedback.
- **Issue Detection:** Highlights recurring complaints and potential areas for improvement.
- **Interactive Visualizations:** Displays review trends and issue distributions using Plotly.
- **Actionable Recommendations:** Converts review patterns into practical recommendations for product and operations teams.
- **Persistent Storage:** Maintains collected reviews and analysis data in a local SQLite database.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application and data processing |
| Streamlit | Interactive dashboard and user interface |
| Google Play Scraper | Collects publicly available Play Store reviews |
| pandas | Data cleaning, filtering, and analysis |
| Groq API | AI-based review classification and summarization |
| SQLite | Persistent storage and duplicate prevention |
| Plotly | Interactive charts and visualizations |
| python-dotenv | Loads API keys and configuration from environment variables |

## System Workflow

1. **Periodic Collection:** The application fetches recent public reviews from Google Play at the configured refresh interval.
2. **Data Cleaning:** Python and pandas normalize and filter the collected data.
3. **Deduplication:** Unique review identifiers help prevent duplicate records from being stored and analyzed.
4. **Database Storage:** New reviews are saved in SQLite.
5. **AI Analysis:** New or unclassified reviews are sent to the Groq API for classification and summarization.
6. **Trend Analysis:** Review ratings, complaints, and recurring themes are aggregated.
7. **Dashboard Visualization:** Streamlit and Plotly present the findings in charts and tables.
8. **Recommendations:** The analysis helps prioritize issues that may require investigation and corrective action.

## Periodic Data Collection

The dashboard supports periodic refreshes so that it can check for newly available reviews without requiring the user to manually restart the analysis each time.

The refresh interval and number of reviews fetched can be configured from the dashboard. Newly discovered reviews are stored in SQLite, and previously collected reviews are deduplicated to reduce unnecessary processing and API usage.

**Important:** Periodic collection through the running Streamlit application works only while the application and its refresh mechanism remain active. For unattended collection when the dashboard is closed, a separate background worker or scheduled job should be configured.

Google Play may limit the number of reviews returned or change the availability of review fields. Collection frequency and review volume therefore depend on the scraper and source availability.

## Project Structure

A typical project structure is shown below. Adjust filenames to match your actual repository.

```text
moveinsync-review-dashboard/
├── app.py                 # Streamlit dashboard and application logic
├── .env                   # Private API keys and configuration
├── .gitignore             # Files excluded from version control
├── requirements.txt       # Python dependencies
├── README.md              # Project documentation
└── reviews.db             # SQLite database (created at runtime)
```

## Prerequisites

- Python 3.10 or a compatible version supported by your dependencies
- A Groq API key
- Internet access to retrieve public Play Store reviews and call the Groq API

## Installation and Setup

### 1. Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd moveinsync-review-dashboard
```

Alternatively, download the repository and open its directory in your terminal.

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

On Linux or macOS:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

If you do not already have a `requirements.txt`, install the packages used by your application:

```bash
pip install streamlit pandas plotly google-play-scraper groq python-dotenv
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b
PLAY_STORE_APP_ID=com.moveinsync.ets
```

Replace `your_groq_api_key` with your actual Groq API key. Use a model currently available to your Groq account if the configured model is unavailable.

Keep the `.env` file private and never commit API keys to GitHub.

### 5. Run the dashboard

```bash
streamlit run app.py
```

Open the local URL displayed in your terminal, usually:

```text
http://localhost:8501
```

## Dashboard Configuration

The dashboard provides user-facing controls for:

- **Analysis Window:** Select the period of reviews to analyze.
- **Reviews Per Fetch:** Set the number of reviews to request per collection cycle.
- **Refresh Interval:** Configure how frequently the application checks for new reviews.

The Play Store app ID, country, language, and Groq model can be managed internally through application configuration rather than exposed as dashboard controls.

## How AI Analysis Works

The application uses an LLM through the Groq API to analyze review text and produce structured findings.

The analysis can help with:

- Categorizing feedback into issue themes.
- Summarizing repeated complaints.
- Identifying negative feedback that may need attention.
- Highlighting patterns across reviews.
- Generating recommendations based on observed feedback.

AI-generated findings should be treated as decision-support information rather than definitive proof of a technical or operational problem.

## Recommendations for Improving User Ratings

The dashboard can help teams investigate and prioritize the following areas when supported by the collected reviews:

1. **App Stability:** Investigate reports of crashes, login failures, slow loading, and other usability problems.
2. **Transportation Reliability:** Review complaints about pickup delays, trip scheduling, and transport availability.
3. **Driver and Trip Experience:** Examine feedback about driver behavior, communication, and trip quality.
4. **Customer Support:** Identify recurring reports of unresolved issues or delayed responses.
5. **Continuous Monitoring:** Track whether complaint frequency and ratings improve after corrective actions.

These are areas to investigate, not conclusions that the application has confirmed each problem. Validate review-based findings using relevant operational data, application logs, and support records.

## Limitations

- Only publicly accessible reviews available through the scraper can be analyzed.
- Review collection may be affected by source limitations or changes to Google Play.
- AI classification can make mistakes or misunderstand context.
- Groq API rate limits may require smaller batches, retries, or reduced request frequency.
- Periodic refreshes stop when the running application or its refresh mechanism stops.
- Review sentiment alone cannot establish the root cause of a customer complaint.

## Future Enhancements

- Run a separate background scheduler for collection when the dashboard is closed.
- Add automatic retries and exponential backoff for API rate limits.
- Implement more detailed sentiment and issue classification.
- Track trends across multiple time periods.
- Add email or messaging alerts for sudden increases in negative reviews.
- Compare review trends before and after product improvements.
- Deploy the dashboard to a cloud hosting platform with persistent database storage.

## Security

- Store API credentials in environment variables or a secure secrets manager.
- Add `.env`, database files, virtual environments, and cache files to `.gitignore` as appropriate.
- Avoid exposing API keys in logs, screenshots, or public repositories.
- Apply suitable access controls before deploying the dashboard for team-wide use.

## Conclusion

The MoveInSync Review Intelligence Dashboard transforms public customer reviews into structured feedback and actionable insights. By combining periodic data collection, persistent storage, AI-based analysis, and interactive visualization, it helps teams identify recurring concerns and make more informed decisions about improving the user experience.

**Note:** The dashboard supports evidence-based prioritization; improvements in app ratings depend on validating the findings, implementing effective changes, and measuring subsequent results.

## License

Add the license applicable to your project before distributing it publicly.
