<div align="center">

# 🐱 Adly
### LLM-Powered Marketing Analytics

*Ask your campaign data anything. Get instant, data-backed answers.*

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Groq](https://img.shields.io/badge/Groq-Primary_LLM-F55036?style=for-the-badge)](https://groq.com)
[![Status](https://img.shields.io/badge/Status-Active_Development-brightgreen?style=for-the-badge)]()

</div>

---

## What is Adly?

Adly is a natural language analytics tool built for marketing agencies. Instead of writing SQL or building dashboards, you ask business questions and get instant insights backed by your actual campaign data.

> *"Which campaign should I pause today?"*
> *"What's giving me a false sense of security?"*
> *"Show me my RFM segmentation."*

Built for a real client (marketing agency, Bogotá). Connects CRM data → Google Sheets → analytics engine → natural language interface.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🧠 **Natural Language Queries** | Ask business questions in plain Spanish or English |
| 🔍 **CSV-Agnostic Engine** | Semantic + statistical column detection — no hardcoded schema |
| 🔄 **Schema Drift Detection** | Alerts when data structure changes between loads |
| 🤖 **Multi-Provider LLM** | Groq → Anthropic → Gemini → OpenAI fallback chain |
| ⚡ **Token Efficiency** | 74% system prompt reduction (1,670 → 431 tokens) |
| 📊 **Full Analytics Suite** | ROAS, CPL, CPA, RFM, Cohorts, MQL→SQL conversion, Outliers |
| 🛡️ **Data Integrity Footer** | Freshness alerts with severity levels on every response |

---

## 🏗️ Architecture

```
Adly/
├── src/
│   ├── ai/                  # LLM engine, multi-provider Strategy pattern
│   ├── api/                 # FastAPI routes, state management
│   ├── ingestion/           # CSV/Sheets ingestion, schema detection, normalization
│   └── processing/          # Data quality, value mapping, semantic inference
├── interfaces/
│   └── cli/                 # Rich terminal interface
└── .env.example             # Environment variables template
```

**Data flow:** `CSV / Google Sheets → Ingestion → Schema Detection → LLM Engine → Natural Language Response`

---

## 🛠️ Tech Stack

- **Backend:** Python, FastAPI, Pandas
- **LLM Layer:** Groq (llama-3.3-70b), Anthropic Claude, Gemini, OpenAI
- **Data:** Google Sheets API, n8n automation, CSV
- **Frontend:** Vite + vanilla JS
- **Terminal UI:** Rich

---

## 🚀 Setup

```bash
# 1. Clone and install
git clone https://github.com/CNicolas1996/Adly.git
cd Adly
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Add your API keys to .env

# 3. Run
python scripts/cli.py       # CLI mode
# or start FastAPI backend + Vite frontend separately
```

---

## 📈 Supported Analytics Commands

| Command | Description |
|---|---|
| `/rfm` | RFM segmentation (Recency, Frequency, Monetary) |
| `/cohorts` | Cohort retention analysis |
| `/rentabilidad` | ROAS, CPL, CPA by campaign/adset |
| `/velocidad` | MQL → SQL → Sale conversion speed |
| `/outliers` | Statistical anomaly detection |
| `/correlacion` | Metric correlation analysis |
| `/embudo` | Full funnel visualization |
| `/limpiar_duplicados` | Data integrity cleanup |

---

## 🔐 Security

- API keys managed via `.env` (never committed)
- `.env.example` provided as template
- Multi-provider fallback avoids single point of failure

---

<div align="center">

Built by [Carlos Nicolás López](https://linkedin.com/in/carlosnicolaslopez) · Bogotá, Colombia

</div>
