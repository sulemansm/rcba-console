"""
report_handler.py — Report persistence, metadata management, and late detection.
Extends the existing reports_store.json approach with richer fields.
"""

import os
import json
import uuid
from datetime import datetime, date
from typing import List, Optional, Dict

REPORTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports_store.json")
UPLOADS_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")

os.makedirs(UPLOADS_DIR, exist_ok=True)


# ── Core I/O ─────────────────────────────────────────────────────────────────

def load_reports() -> List[dict]:
    if not os.path.exists(REPORTS_FILE):
        return []
    with open(REPORTS_FILE) as f:
        try:
            return json.load(f)
        except Exception:
            return []


def _save_all(reports: List[dict]) -> None:
    with open(REPORTS_FILE, "w") as f:
        json.dump(reports, f, indent=2, default=str)


def save_report(record: dict) -> None:
    """Append a new report record."""
    # Back-fill required fields if missing
    record.setdefault("report_id",           str(uuid.uuid4())[:8].upper())
    record.setdefault("status",              record.pop("approval_status", "Pending"))
    record.setdefault("submission_timestamp", record.get("submitted_at", str(datetime.now())))
    record.setdefault("last_updated",         str(datetime.now()))
    record.setdefault("is_late",              _calc_is_late(
        record.get("event_start_date", ""), record.get("submission_timestamp", "")))
    record.setdefault("rejection_message",   "")
    record.setdefault("file_path",           "")
    record.setdefault("role",                "")

    reports = load_reports()
    reports.append(record)
    _save_all(reports)


def update_report(idx: int, fields: dict) -> None:
    """Patch fields on a report by list index (legacy compat)."""
    reports = load_reports()
    if 0 <= idx < len(reports):
        # Normalise status field
        if "approval_status" in fields and "status" not in fields:
            fields["status"] = _normalise_status(fields.pop("approval_status"))
        fields["last_updated"] = str(datetime.now())
        reports[idx].update(fields)
        _save_all(reports)


def update_report_by_id(report_id: str, fields: dict) -> bool:
    """Patch fields on a report by its report_id."""
    reports = load_reports()
    for r in reports:
        if r.get("report_id") == report_id:
            if "approval_status" in fields and "status" not in fields:
                fields["status"] = _normalise_status(fields.pop("approval_status"))
            fields["last_updated"] = str(datetime.now())
            r.update(fields)
            _save_all(reports)
            return True
    return False


# ── Status normalisation ─────────────────────────────────────────────────────

def _normalise_status(raw: str) -> str:
    mapping = {
        "approved":  "Approved",
        "approve":   "Approved",
        "rejected":  "Rejected",
        "reject":    "Rejected",
        "changes":   "Rejected",
        "pending":   "Pending",
    }
    return mapping.get(raw.lower().strip(), raw)


def get_status(report: dict) -> str:
    """Unified status getter (handles both old and new field names)."""
    raw = report.get("status") or report.get("approval_status", "Pending")
    return _normalise_status(raw)


# ── Late detection ────────────────────────────────────────────────────────────

def _calc_is_late(event_date_str: str, submitted_at_str: str) -> bool:
    try:
        ev  = datetime.strptime(str(event_date_str)[:10], "%Y-%m-%d").date()
        sub = datetime.strptime(str(submitted_at_str)[:10], "%Y-%m-%d").date()
        return (sub - ev).days > 7
    except Exception:
        return False


def is_late(report: dict) -> bool:
    """Check if a report was submitted late (>7 days after event start)."""
    # Manual override takes precedence
    if "is_late" in report and isinstance(report["is_late"], bool):
        return report["is_late"]
    return _calc_is_late(
        report.get("event_start_date", ""),
        report.get("submission_timestamp") or report.get("submitted_at", "")
    )


# ── File storage ──────────────────────────────────────────────────────────────

def save_uploaded_file(file_bytes: bytes, filename: str) -> str:
    """Save uploaded DOCX bytes to the uploads directory. Returns file path."""
    safe_name = filename.replace(" ", "_")
    dest = os.path.join(UPLOADS_DIR, safe_name)
    with open(dest, "wb") as f:
        f.write(file_bytes)
    return dest


# ── Filters ───────────────────────────────────────────────────────────────────

def filter_reports(
    reports: List[dict],
    status: Optional[str] = None,
    submitted_by: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
) -> List[dict]:
    out = reports

    if status and status != "All":
        out = [r for r in out if get_status(r) == status]

    if submitted_by and submitted_by != "All":
        out = [r for r in out if
               r.get("submitted_by_email", "").lower() == submitted_by.lower() or
               r.get("submitted_by_name", "").lower() == submitted_by.lower()]

    if date_from:
        out = [r for r in out if
               (r.get("event_start_date") or r.get("submitted_at", ""))[:10] >= date_from]

    if date_to:
        out = [r for r in out if
               (r.get("event_start_date") or r.get("submitted_at", ""))[:10] <= date_to]

    if search:
        q = search.lower()
        out = [r for r in out if
               q in r.get("event_title", "").lower() or
               q in r.get("submitted_by_name", "").lower() or
               q in r.get("avenue", "").lower()]

    return out


def get_my_reports(reports: List[dict], email: str) -> List[dict]:
    return [r for r in reports if r.get("submitted_by_email", "").lower() == email.lower()]


# ── Stats ─────────────────────────────────────────────────────────────────────

def compute_stats(reports: List[dict]) -> dict:
    total    = len(reports)
    approved = sum(1 for r in reports if get_status(r) == "Approved")
    rejected = sum(1 for r in reports if get_status(r) == "Rejected")
    pending  = total - approved - rejected
    late_ct  = sum(1 for r in reports if is_late(r))
    return {
        "total": total, "approved": approved,
        "rejected": rejected, "pending": pending, "late": late_ct,
    }
