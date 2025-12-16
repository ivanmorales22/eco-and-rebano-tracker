# 📊 GDL Insight: Eco & Rebaño Tracker
 **An autonomous and intelligent Dashboard + an AI agent to keep you up to date**
 * Connecting my passions: Sustainability + Club Deportivo Guadalajara

![Environment View](images/streamlit-chivas.png)
---
![Chivas View](images/streamlit-environment.png)
---

# Problem Statement
Living in guadalajara is amazing, going into some news sites and scrolling trough all of the clickbait to read the concise information at the end of it, is not, at the same time, monitoring local sustainability metrics like the level of Chapala Lake requires digging trough unfriendly government websites, this only creates friction for one to stay informed efficiently about two topics that I am passionate about, Chivas and Sustainability.

The solution comes with a bot that gathers the info, and displays it on a Streamlit Dashboard sending you a brief email every day to wake up informed.

---

# Main features
### 1. Environmental Dashboard
* **Dynamic Map**, showing ZMG's 13 IMECA monitoring stations
* **Critical KPIs**, such as Chapala Lake level and IMECA concentrations
* **Environmental feed**, 5 selected articles about the environment in the ZMG (AI Powered)

### 2. Chivas Analytics
* **Anti-Clickbait filter**, a gemini model goes trough the news and clean the content
* **Chivas feed**, 5 selected articles about the current status about the club (AI Powered)

### 3. AI Agent
* **No friction**, no action needed, everything is up and ready
* **GitHub Actions CRON**, a Script is executed every day at 8:00AM
* **Morning briefing**, wake up informed with a minimalist email

# Tech Stack
This project combines data engineering with AI implementation

* **AI Core**, 
    * google-generativeai, 2.5-flash & 2.5-flash-lite
    * cursor (free) and gemini (pro) for coding and depuration
* **Frontend**, Streamlit, friendly and efficient user interface
* **Backend**, Python, Pandas, Numpy
* **Data Ingestion**, 
    * Beautifulsoup4 & Requests for scrapping
    * Feedparser for news ingestion from Google RSS
* **Visualization**, Plotly
* **Automation**, GitHub Actions (serverless CRON jobs) + smtplib (emailing)

# Installation and Use instructions (using bash is suggested)
1. Cloning the Repo:

    git clone [https://github.com/ivanmorales22/eco-and-rebano-tracker.git](https://github.com/ivanmorales22/eco-and-rebano-tracker.git)

    cd eco-and-rebano-tracker

2. Create the virtual env and install dependencies

    python -m venv venv

    source venv/Scripts/activate

    pip install -r requirements.txt

3. Set Environment Variables (.env)

**NOTE: DO NOT COMMIT THIS FILE**

Gitignore file should already be ignoring it but be sure.

    GEMINI_API_KEY = "..."
    EMAIL_USER = "..."
    EMAIL_PASS = "..."
    EMAIL_RECEIVER = "..."

4. Dashboard Execution

    streamlit run app.py

5. Emaling test

    python daily_briefing.py


## Architecture

```mermaid
graph TD
    A[Data Sources - Google] -->|RSS & Scraping| B(Python Scripts )
    B -->|Raw Text| C{Gemini AI Flash 2.5}
    C -->|Cleaning & Summarizing| D[Structured Data]
    D --> E["Streamlit Dashboard (PULL)"]
    D --> F["GitHub Actions (PUSH)"]
    F -->|8:00 AM Daily| G[Email Briefing]
```

```text
eco-and-rebano-tracker/
├── .devcontainer/          # Configuration for Codespaces/Docker
│   └── devcontainer.json   # Virtual environment rules & extensions
├── .github/
│   └── workflows/
│       └── daily_agent.yml # Daily email automation (8:00 AM)
├── chivas/                 # Module: Chivas
│   ├── __init__.py
│   └── data.py             # Chivas news logic + AI Filter
├── environment/            # Module: ZMG Environment
│   ├── __init__.py
│   └── data.py             # Scraping (IMECA/Chapala) + Env News
├── images/                 # Screenshots for the README
│   ├── streamlit-chivas.png
│   └── streamlit-environment.png
├── .gitignore              # Ignored files (Cache JSONs, .env, venv)
├── app.py                  # Main Frontend (Streamlit Dashboard)
├── daily_briefing.py       # Autonomous Agent Script (Email sender)
├── README.md               # Project documentation
├── requirements.txt        # Python libraries
└── utils.py                # Cache manager (Save/Read JSONs)
```