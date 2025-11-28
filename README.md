# firline---poc
# 🔥 Fireline: Autonomous SRE Incident Commander

Fireline is an event-driven AI agent that acts as a virtual Site Reliability Engineer (SRE). It monitors alerts, autonomously investigates logs, searches internal runbooks (RAG), and proposes fixes—all managed by a durable Temporal workflow with a Human-in-the-Loop approval gate.

## 🏗 Architecture
- **API Gateway:** FastAPI (Python)
- **Orchestration:** Temporal.io
- **AI Engine:** Google Gemini Pro (`gemini-pro-latest`)
- **Knowledge Base:** PostgreSQL 17 + `pgvector`
- **Dashboard:** Streamlit

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.10+
- Homebrew (for Postgres & Temporal)
- Google AI Studio API Key

### 2. Environment Setup
```bash
# Clone the repo
git clone [https://github.com/Ayush1Deshmukh/FIRLINE_POC.git](https://github.com/Ayush1Deshmukh/FIRLINE_POC.git)
cd FIRLINE_POC

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
