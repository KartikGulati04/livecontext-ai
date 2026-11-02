# Engineering Architecture & Release Guidelines

## 1. System Overview
LiveContext AI is an agentic RAG system connecting live cloud tools (Atlassian Jira, Notion, Google Gmail) with indexed documentation and persistent memory.

## 2. Release Blocker Criteria
- Any issue with priority **Blocker** or **Critical** must be resolved before deployment.
- Current release candidate: **v1.4.0**.
- Jira tracking epic: **PROJ-100**.
- Database migrations must complete within a 5-minute maintenance window.

## 3. Data Retention & Upload Limits
- Maximum upload size: **10 MB** per document.
- Supported formats: **PDF, Markdown (.md), and Plain Text (.txt)**.
- Document chunks are stored with 500 characters and 50 character overlap.
- Retention: Inactive uploaded files are archived after 90 days.
