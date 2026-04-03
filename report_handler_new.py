"""
report_handler.py — Report persistence with Supabase (primary) and JSON fallback
"""

import os
import json
import uuid
from datetime import datetime, date
from typing import List, Optional, Dict

# Try to use Supabase, fallback to JSON
try:
    from supabase_handler import (
        save_report_to_db, load_reports_from_db, get_report_by_id,
        update_report_status, SUPABASE_ENABLED
    )
    USE_SUPABASE = SUPABASE_ENABLED
except:
    USE_SUPABASE = False

REPORTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports_store.json")
UPLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")

os.makedirs(UPLOADS_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# JSON FALLBACK (for local development)
# ═══════════════════════════════════════════════════════════════════════════════

def load_reports_json() -> List[dict]:
    """Load reports from JSON file (local fallback)"""
    if not os.path.exists(REPORTS_FILE):
        return []
    with open(REPORTS_FILE) as f:
        try:
            return json.load(f)
        except Exception:
            return []


def _save_all_json(reports: List[dict]) -> None:
    """Save reports to JSON file"""
    with open(REPORTS_FILE, "w") as f:
        json.dump(reports, f, indent=2, default=str)


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API (uses Supabase if available, falls back to JSON)
# ═══════════════════════════════════════════════════════════════════════════════

def load_reports(email: Optional[str] = None, role: Optional[str] = None) -> List[dict]:
    """Load reports - uses Supabase if available, else JSON"""
    if USE_SUPABASE:
        return load_reports_from_db(email=email, role=role)
    else:
        # Fallback: load all from JSON
        reports = load_reports_json()
        
        # Filter by role locally
        if role == "director" and email:
            reports = [r for r in reports if r.get("submitted_by_email") == email]
        elif role not in ("secretariat", "admin", "editor"):
            reports = []
        
        # Sort by date descending
        return sorted(reports, key=lambda r: r.get("submission_timestamp", ""), reverse=True)


def save_report(record: dict, docx_binary: Optional[bytes] = None) -> Dict:
    """Save report - uses Supabase if available, else JSON"""
    
    # Standardize fields
    record.setdefault("report_id", str(uuid.uuid4())[:8].upper())
    record.setdefault("status", "submitted")
    record.setdefault("submission_timestamp", str(datetime.now()))
    record.setdefault("last_updated", str(datetime.now()))
    record.setdefault("is_late", _calc_is_late(
        record.get("event_start_date", ""), 
        record.get("submission_timestamp", "")
    ))
    record.setdefault("rejection_message", "")
    record.setdefault("file_path", "")
    
    if USE_SUPABASE:
        # Prepare Supabase payload
        supabase_data = {
            "event_title": record.get("event_title", ""),
            "event_venue": record.get("event_venue", ""),
            "event_date": record.get("event_start_date", ""),
            "chief_guest": record.get("chief_guest", ""),
            "description": record.get("description", ""),
            "pre_event": record.get("pre_event", ""),
            "on_day": record.get("on_day", ""),
            "post_event": record.get("post_event", ""),
            "outcome": record.get("outcome", ""),
            
            # Attendance
            "member_names": record.get("selected_members", []),
            "guest_count": record.get("guest_count", 0),
            "guest_names": record.get("guest_names", ""),
            "district_count": record.get("district_count", 0),
            "district_names": record.get("district_names", ""),
            "ambassadorial_count": record.get("ambassadorial_count", 0),
            "ambassadorial_names": record.get("ambassadorial_names", ""),
            
            # Avenue chairs
            "avenue_chairs": record.get("avenue_chairs", []),
            
            # Metadata
            "submitted_by_email": record.get("submitted_by_email", ""),
            "submitted_by_name": record.get("submitted_by_name", ""),
        }
        
        return save_report_to_db(supabase_data, docx_binary=docx_binary)
    else:
        # Fallback: save to JSON
        reports = load_reports_json()
        reports.append(record)
        _save_all_json(reports)
        return {"success": True, "report_id": record.get("report_id")}


def update_report_status(report_id: str, status: str, approved_by: str = "", comments: str = "") -> bool:
    """Update report status - uses Supabase if available"""
    if USE_SUPABASE:
        # Try to get report_id as integer
        try:
            report_id_int = int(report_id)
        except:
            report_id_int = None
        
        if report_id_int:
            return update_report_status(report_id_int, status, approved_by=approved_by, comments=comments)
        return False
    else:
        # Fallback: update JSON
        return update_report_by_id(report_id, {
            "status": status,
            "approved_by": approved_by,
            "approval_comments": comments,
            "approved_at": str(datetime.now()) if approved_by else "",
        })


def update_report_by_id(report_id: str, fields: dict) -> bool:
    """Update report by ID - JSON fallback"""
    reports = load_reports_json()
    for r in reports:
        if r.get("report_id") == report_id:
            fields["last_updated"] = str(datetime.now())
            r.update(fields)
            _save_all_json(reports)
            return True
    return False


def get_status(report: dict) -> str:
    """Get normalized status from report"""
    raw = report.get("status") or report.get("approval_status", "submitted")
    mapping = {
        "approved": "Approved",
        "approve": "Approved",
        "rejected": "Rejected",
        "reject": "Rejected",
        "submitted": "Pending",
        "pending": "Pending",
    }
    return mapping.get(str(raw).lower().strip(), raw)


def is_late(event_date_str: str, submitted_at_str: str) -> bool:
    """Check if submission is late (>7 days after event)"""
    try:
        ev = datetime.strptime(event_date_str[:10], "%Y-%m-%d").date()
        sub = datetime.strptime(submitted_at_str[:10], "%Y-%m-%d").date()
        return (sub - ev).days > 7
    except:
        return False


def _calc_is_late(event_date: str, submission_date: str) -> bool:
    """Calculate if submission is late"""
    return is_late(event_date, submission_date)
