# AI-SDLC Pipeline

An end-to-end AI pipeline that takes a Business Requirements Specification (BRS)
document and progressively transforms it into a structured SRS, technical designs,
engineering tasks, tickets, and sprint plans — automating the early SDLC workflow
normally done by a business analyst, architect, and scrum master.

## Pipeline

BRS (doc/PDF) → Ingestion & Summarization → Research Agent → SRS Generator
→ Requirement Classifier → Design Generator (HLD/LLD) → Task Planner
→ Ticket Generator → Sprint Allocator → Dashboard

## Status

🚧 In progress. Currently implemented: BRS ingestion,structured summarization,research Agent and Tech/Non-Tech Classifier77 .

## Stack

- Python
- Google Gemini API (LLM)
- Pydantic (structured outputs)
- python-docx / PyPDF2 (document parsing)

## Setup

\`\`\`bash
git clone https://github.com/<your-username>/ai-sdlc-pipeline.git
cd ai-sdlc-pipeline
python -m venv venv
source venv/bin/activate   # venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env       # then add your GEMINI_API_KEY
\`\`\`

## Usage

\`\`\`bash
python test_summarizer.py
\`\`\`
