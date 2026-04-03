"""
report_handler.py - Complete handler for Supabase + JSON fallback
Manages report persistence, retrieval, and filtering
"""
import os
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict

# Try Supabase first, fallback to JSON
try:
    from supabase_handler import (
        save_report_to_db, load_reports_from_db, get_report_by_id,
        update_report_status as update_report_status_db, SUPABASE_ENABLED
    )
    USE_SUPABASE = SUPABASE_ENABLED
except Exception as e:
    USE_SUPABASE = False
    print(f"[report_handler] Supabase init failed, using JSON: {str(e)}")

REPORTS_FILE = os.path.join(os.path.dirname(__file__), "reports_store.json")
os.makedirs(os.path.dirname(REPORTS_FILE), exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# JSON FALLBACK FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _load_json() -> List[Dict]:
    """Load from JSON"""
    if not os.path.exists(REPORTS_FILE):
        return []
    try:
        with open(REPORTS_FILE) as f:
            return json.load(f)
    except:
        return []


def _save_json(reports: List[Dict]) -> None:
    """Save to JSON"""
    try:
        with open(REPORTS_FILE, "w") as f:
            json.dump(reports, f, indent=2, default=str)
    except Exception as e:
        print(f"[report_handler] JSON save failed: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def save_report(record: dict, docx_binary: Optional[bytes] = None) -> Dict:
    """Save report - uses Supabase if available, else JSON"""
    
    # Ensure required fields
    record.setdefault("report_id", str(uuid.uuid4())[:8].upper())
    record.setdefault("status", "submitted")
    record.setdefault("submission_timestamp", str(datetime.now()))
    
    if USE_SUPABASE:
        try:
            # Prepare for Supabase
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
                "member_names": record.get("selected_members", []),
                "guest_count": record.get("guest_count", 0),
                "guest_names": record.get("guest_names", ""),
                "district_count": record.get("district_count", 0),
                "district_names": record.get("district_names", ""),
                "ambassadorial_count": record.get("ambassadorial_count", 0),
                "ambassadorial_names": record.get("ambassadorial_names", ""),
                "avenue_chairs": record.get("avenue_chairs", []),
                "submitted_by_email": record.get("submitted_by_email", ""),
                "submitted_by_name": record.get("submitted_by_name", ""),
            }
            result = save_report_to_db(supabase_data, docx_binary=docx_binary)
            if result.get("success"):
                print(f"[report_handler] [OK] Supabase save successful")
                return result
        except Exception as e:
            print(f"[report_handler] Supabase save failed: {str(e)}, falling back to JSON")
    
    # Fallback to JSON
    reports = _load_json()
    reports.append(record)
    _save_json(reports)
    print(f"[report_handler] [OK] JSON save successful")
    return {"success": True, "report_id": record.get("report_id")}


def load_reports(email: Optional[str] = None, role: Optional[str] = None) -> List[Dict]:
    """Load reports - Supabase first, then JSON"""
    if USE_SUPABASE:
        try:
            reports = load_reports_from_db(email=email, role=role)
            if reports:
                print(f"[report_handler] [OK] Loaded {len(reports)} reports from Supabase")
                return reports
        except Exception as e:
            print(f"[report_handler] Supabase load failed: {str(e)}, trying JSON")
    
    # Fallback to JSON
    reports = _load_json()
    if role == "director" and email:
        reports = [r for r in reports if r.get("submitted_by_email", "").lower() == email.lower()]
    elif role not in ("secretariat", "admin", "editor"):
        reports = []
    
    print(f"[report_handler] [OK] Loaded {len(reports)} reports from JSON")
    return sorted(reports, key=lambda r: r.get("submission_timestamp", ""), reverse=True)


def update_report(idx: int, fields: dict) -> None:
    """Update report by index (legacy)"""
    reports = _load_json()
    if 0 <= idx < len(reports):
        reports[idx].update(fields)
        _save_json(reports)


def update_report_by_id(report_id: str, fields: dict) -> bool:
    """Update report by ID"""
    reports = _load_json()
    for r in reports:
        if r.get("report_id") == report_id:
            r.update(fields)
            _save_json(reports)
            return True
    return False


def update_report_status(report_id_or_int, status: str, approved_by: str = "", comments: str = "") -> bool:
    """Update status - Supabase or JSON"""
    if USE_SUPABASE:
        try:
            report_id_int = int(report_id_or_int) if not isinstance(report_id_or_int, int) else report_id_or_int
            result = update_report_status_db(report_id_int, status, approved_by=approved_by, comments=comments)
            if result:
                print(f"[report_handler] [OK] Supabase status update successful")
                return result
        except Exception as e:
            print(f"[report_handler] Supabase update failed: {str(e)}, trying JSON")
    
    # Fallback to JSON
    return update_report_by_id(str(report_id_or_int), {
        "status": status,
        "approved_by": approved_by,
        "approval_comments": comments,
        "approved_at": str(datetime.now()) if approved_by else "",
    })


def get_status(report: dict) -> str:
    """Get normalized status"""
    raw = report.get("status") or report.get("approval_status", "submitted")
    mapping = {
        "submitted": "Pending",
        "pending": "Pending",
        "approved": "Approved",
        "rejected": "Rejected",
    }
    return mapping.get(str(raw).lower().strip(), "Pending")


def is_late(event_date_str: str, submitted_at_str: str) -> bool:
    """Check if submission is late (>7 days)"""
    try:
        from datetime import datetime
        ev = datetime.strptime(str(event_date_str)[:10], "%Y-%m-%d").date()
        sub = datetime.strptime(str(submitted_at_str)[:10], "%Y-%m-%d").date()
        return (sub - ev).days > 7
    except:
        return False


def filter_reports(
    reports: List[dict],
    status: Optional[str] = None,
    submitted_by: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
) -> List[dict]:
    """Filter reports"""
    out = reports
    
    if status and status != "All":
        out = [r for r in out if get_status(r) == status]
    
    if submitted_by and submitted_by != "All":
        out = [r for r in out if 
               r.get("submitted_by_email", "").lower() == submitted_by.lower() or
               r.get("submitted_by_name", "").lower() == submitted_by.lower()]
    
    if date_from:
        out = [r for r in out if
               (r.get("event_date") or r.get("event_start_date", ""))[:10] >= date_from]
    
    if date_to:
        out = [r for r in out if
               (r.get("event_date") or r.get("event_start_date", ""))[:10] <= date_to]
    
    if search:
        q = search.lower()
        out = [r for r in out if
               q in r.get("event_title", "").lower() or
               q in r.get("submitted_by_name", "").lower()]
    
    return out


def get_my_reports(reports: List[dict], email: str) -> List[dict]:
    """Get user's reports"""
    return [r for r in reports if r.get("submitted_by_email", "").lower() == email.lower()]


def compute_stats(reports: List[dict]) -> dict:
    """Compute statistics"""
    total = len(reports)
    approved = sum(1 for r in reports if get_status(r) == "Approved")
    rejected = sum(1 for r in reports if get_status(r) == "Rejected")
    pending = total - approved - rejected
    
    return {
        "total": total,
        "approved": approved,
        "rejected": rejected,
        "pending": pending,
        "late": sum(1 for r in reports if is_late(
            r.get("event_date") or r.get("event_start_date", ""),
            r.get("submitted_at") or r.get("submission_timestamp", "")
        )),
    }
