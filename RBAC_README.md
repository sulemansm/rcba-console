# RCBA Event Reporter — Role-Based Access Control Upgrade

## Architecture

```
rcba-operations-website-master/
├── app.py                ← Main entry point (router + UI + AI + DOCX + email)
├── auth.py               ← NEW: Role resolution (secretariat / editor / director)
├── report_handler.py     ← NEW: Report CRUD, filtering, stats, file storage
├── dashboard.py          ← NEW: Role-specific dashboard views
├── roles.json            ← UPDATED: 3 role lists
├── reports_store.json    ← Persistent report store (JSON)
├── uploads/              ← AUTO-CREATED: Saved DOCX files
├── .env                  ← Secrets (not committed)
└── ...existing files...
```

---

## Roles

| Role | Badge Colour | Dashboard | Submit | Approve/Reject | Download | Mark Late |
|---|---|---|---|---|---|---|
| **Secretariat** | Purple | All reports + filters | ✅ | ✅ | ✅ | ✅ |
| **Editor** | Gold | All reports + filters | ✅ | ❌ | ✅ | ❌ |
| **Director** | Teal | Own reports only | ✅ | ❌ | Own only | ❌ |

---

## Setup

### 1. Add emails to `roles.json`

```json
{
  "secretariat_emails": ["secretary@example.com"],
  "editor_emails":      ["editor1@example.com"],
  "director_emails":    [],
  "admin_emails":       ["secretary@example.com"]
}
```

> **Note:** All whitelisted emails not in secretariat/editor lists default to **Director**.
> `admin_emails` is kept for backwards compatibility — maps to secretariat.

### 2. Update `.env`

```env
GROQ_API_KEY=your_groq_key
SENDER_EMAIL=your@gmail.com
SENDER_PASSWORD=abcdabcdabcdabcd   # 16-char Gmail App Password, no spaces
SECRETARY_EMAIL=secretary@example.com
OAUTH_REDIRECT_URI=http://localhost:8501/
WHITELISTED_EMAILS=alice@gmail.com,bob@gmail.com,carol@gmail.com
GOOGLE_CREDENTIALS_FILE=google_credentials.json
```

### 3. Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

## Data Model

Each report in `reports_store.json` now carries:

```json
{
  "report_id":             "A1B2C3D4",
  "event_title":           "Shukriya Night 2025",
  "avenue":                "Club Service",
  "event_start_date":      "2025-03-01",
  "submitted_by_name":     "Riya Shah",
  "submitted_by_email":    "riya@gmail.com",
  "submitted_at":          "2025-03-05 14:30:00",
  "submission_timestamp":  "2025-03-05 14:30:00",
  "status":                "Pending",
  "approval_status":       "pending",
  "role":                  "director",
  "file_path":             "uploads/RCBA_Report_Shukriya_Night_20250305143000.docx",
  "rejection_message":     "",
  "review_comment":        "",
  "reviewed_by":           "",
  "reviewed_at":           "",
  "is_late":               false,
  "last_updated":          "2025-03-05 14:30:00"
}
```

**Backwards compatible** — old records without new fields work fine.

---

## Email Flows

| Trigger | Recipient | Content |
|---|---|---|
| Report submitted (Step 5) | Secretary | DOCX attachment + summary |
| Secretariat approves | Submitter | Approval notice + optional comments |
| Secretariat rejects | Submitter | Rejection reason (required) |

---

## AI Report Generation

**Fully intact.** Uses Groq (llama-3.3-70b-versatile → llama-3.1-8b-instant fallback).
Steps 1–5 in New Report page are unchanged.
The only addition: the generated DOCX is now saved to `uploads/` and registered in `reports_store.json` with `status = Pending`.

---

## Existing Functionality Preserved

- ✅ Google OAuth login
- ✅ Whitelist-based access
- ✅ AI report generation (Groq)
- ✅ DOCX builder (full formatting)
- ✅ Email to secretary on submission
- ✅ All CSS / UI design
- ✅ Profile page
- ✅ Word counters
- ✅ All existing report records in `reports_store.json`
