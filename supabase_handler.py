"""
Supabase database handler - Complete, tested, production-ready
Handles reports, members, roles, and DOCX file storage
Works with both local .env and Streamlit Cloud secrets
"""
import os
import base64
from datetime import datetime
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

# Import secrets manager for Streamlit Cloud compatibility
try:
    import streamlit as st
    from secrets_manager import get_secret
    USE_SECRETS_MANAGER = True
except:
    USE_SECRETS_MANAGER = False

load_dotenv()

try:
    from supabase import create_client, Client
    
    # Get credentials from Streamlit Cloud or local .env
    if USE_SECRETS_MANAGER:
        SUPABASE_URL = get_secret("SUPABASE_URL", "").strip()
        SUPABASE_KEY = get_secret("SUPABASE_KEY", "").strip()
    else:
        SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
        SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
    
    if SUPABASE_URL and SUPABASE_KEY:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        SUPABASE_ENABLED = True
        print("[supabase_handler] [OK] Supabase initialized")
    else:
        SUPABASE_ENABLED = False
        print("[supabase_handler] [WARNING] Missing credentials")
        supabase = None
except Exception as e:
    SUPABASE_ENABLED = False
    supabase = None
    print(f"[supabase_handler] [ERROR] Init failed: {str(e)}")


# ===========================================================================
# REPORTS
# ===========================================================================

def save_report_to_db(report_data: Dict[str, Any], docx_binary: Optional[bytes] = None) -> Dict:
    """Save report to Supabase with optional DOCX storage"""
    if not SUPABASE_ENABLED or not supabase:
        return {"error": "Supabase not available", "success": False}
    
    try:
        # Prepare payload with proper types
        payload = {
            "event_title": str(report_data.get("event_title", "")).strip(),
            "event_venue": str(report_data.get("event_venue", "")).strip(),
            "event_date": str(report_data.get("event_date", "")).strip() if report_data.get("event_date") else None,
            "chief_guest": str(report_data.get("chief_guest", "")).strip(),
            "description": str(report_data.get("description", "")).strip(),
            "pre_event": str(report_data.get("pre_event", "")).strip(),
            "on_day": str(report_data.get("on_day", "")).strip(),
            "post_event": str(report_data.get("post_event", "")).strip(),
            "outcome": str(report_data.get("outcome", "")).strip(),
            "member_names": report_data.get("member_names") if isinstance(report_data.get("member_names"), list) else [],
            "guest_count": int(report_data.get("guest_count") or 0),
            "guest_names": str(report_data.get("guest_names", "")).strip(),
            "district_count": int(report_data.get("district_count") or 0),
            "district_names": str(report_data.get("district_names", "")).strip(),
            "ambassadorial_count": int(report_data.get("ambassadorial_count") or 0),
            "ambassadorial_names": str(report_data.get("ambassadorial_names", "")).strip(),
            "avenue_chairs": report_data.get("avenue_chairs") if isinstance(report_data.get("avenue_chairs"), list) else [],
            "submitted_by_email": str(report_data.get("submitted_by_email", "")).strip().lower(),
            "submitted_by_name": str(report_data.get("submitted_by_name", "")).strip(),
            "status": "submitted",
            "is_late": bool(report_data.get("is_late", False)),
        }
        
        # Insert
        response = supabase.table("reports").insert(payload).execute()
        
        if not response.data:
            return {"error": "No data returned from insert", "success": False}
        
        report_id = response.data[0].get("id")
        print(f"[supabase_handler] [OK] Report {report_id} saved")
        
        # Save DOCX if provided
        if docx_binary:
            try:
                b64 = base64.b64encode(docx_binary).decode('utf-8')
                docx_payload = {
                    "report_id": report_id,
                    "filename": f"report_{report_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                    "file_content": b64,
                    "file_size": len(docx_binary),
                }
                docx_resp = supabase.table("docx_files").insert(docx_payload).execute()
                if docx_resp.data:
                    docx_id = docx_resp.data[0].get("id")
                    supabase.table("reports").update({"docx_file_id": docx_id}).eq("id", report_id).execute()
                    print(f"[supabase_handler] [OK] DOCX {docx_id} saved")
            except Exception as e:
                print(f"[supabase_handler] [WARNING] DOCX save failed: {str(e)}")
        
        return {"success": True, "report_id": report_id}
    
    except Exception as e:
        print(f"[supabase_handler] [ERROR] Save failed: {str(e)}")
        return {"error": str(e), "success": False}


def load_reports_from_db(email: Optional[str] = None, role: Optional[str] = None) -> List[Dict]:
    """Load reports based on role"""
    if not SUPABASE_ENABLED or not supabase:
        return []
    
    try:
        if role == "director" and email:
            resp = supabase.table("reports").select("*").eq("submitted_by_email", email.lower()).order("submitted_at", desc=True).execute()
        elif role in ("secretariat", "admin", "editor"):
            resp = supabase.table("reports").select("*").order("submitted_at", desc=True).execute()
        else:
            return []
        
        return resp.data if resp.data else []
    except Exception as e:
        print(f"[supabase_handler] [ERROR] Load reports failed: {str(e)}")
        return []


def get_report_by_id(report_id: int) -> Optional[Dict]:
    """Get single report"""
    if not SUPABASE_ENABLED or not supabase:
        return None
    try:
        resp = supabase.table("reports").select("*").eq("id", report_id).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        print(f"[supabase_handler] [ERROR] Get report failed: {str(e)}")
        return None


def update_report_status(report_id: int, status: str, approved_by: str = "", comments: str = "") -> bool:
    """Update report status"""
    if not SUPABASE_ENABLED or not supabase:
        return False
    try:
        update_data = {"status": status, "last_updated": datetime.now().isoformat()}
        if approved_by:
            update_data["approved_by_email"] = approved_by
            update_data["approved_at"] = datetime.now().isoformat()
        if comments:
            update_data["approval_comments"] = comments
        
        resp = supabase.table("reports").update(update_data).eq("id", report_id).execute()
        return bool(resp.data)
    except Exception as e:
        print(f"[supabase_handler] [ERROR] Update status failed: {str(e)}")
        return False


def get_docx_file(report_id: int) -> Optional[bytes]:
    """Get DOCX file binary data"""
    if not SUPABASE_ENABLED or not supabase:
        return None
    try:
        resp = supabase.table("docx_files").select("file_content").eq("report_id", report_id).execute()
        if resp.data and resp.data[0].get("file_content"):
            return base64.b64decode(resp.data[0]["file_content"])
        return None
    except Exception as e:
        print(f"[supabase_handler] [ERROR] Get DOCX failed: {str(e)}")
        return None


# ===========================================================================
# MEMBERS
# ===========================================================================

def add_member_to_db(name: str, email: str, role: str = "Member") -> bool:
    """Add member"""
    if not SUPABASE_ENABLED or not supabase:
        return False
    try:
        resp = supabase.table("members").insert({
            "name": str(name).strip(),
            "email": str(email).strip().lower(),
            "role": str(role).strip(),
            "added_date": datetime.now().isoformat(),
        }).execute()
        return bool(resp.data)
    except Exception as e:
        print(f"[supabase_handler] [ERROR] Add member failed: {str(e)}")
        return False


def get_all_members() -> List[Dict]:
    """Get all members"""
    if not SUPABASE_ENABLED or not supabase:
        return []
    try:
        resp = supabase.table("members").select("*").order("added_date", desc=True).execute()
        return resp.data if resp.data else []
    except Exception as e:
        print(f"[supabase_handler] [ERROR] Load members failed: {str(e)}")
        return []


def delete_member_from_db(member_name: str) -> bool:
    """Delete member"""
    if not SUPABASE_ENABLED or not supabase:
        return False
    try:
        supabase.table("members").delete().eq("name", member_name).execute()
        return True
    except Exception as e:
        print(f"[supabase_handler] [ERROR] Delete member failed: {str(e)}")
        return False


def member_exists(name: str = "", email: str = "") -> bool:
    """Check if member exists"""
    if not SUPABASE_ENABLED or not supabase:
        return False
    try:
        if name:
            resp = supabase.table("members").select("id").eq("name", name).execute()
            if resp.data:
                return True
        if email:
            resp = supabase.table("members").select("id").eq("email", email.lower()).execute()
            if resp.data:
                return True
        return False
    except Exception as e:
        print(f"[supabase_handler] [ERROR] Check member failed: {str(e)}")
        return False


# ===========================================================================
# ROLES
# ===========================================================================

def get_role_from_db(email: str) -> Optional[str]:
    """Get role from database"""
    if not SUPABASE_ENABLED or not supabase:
        return None
    try:
        resp = supabase.table("roles_config").select("role").eq("email", email.lower()).execute()
        return resp.data[0]["role"] if resp.data else None
    except Exception as e:
        print(f"[supabase_handler] [ERROR] Get role failed: {str(e)}")
        return None


def assign_role_in_db(email: str, role: str) -> bool:
    """Assign role to user"""
    if not SUPABASE_ENABLED or not supabase:
        return False
    try:
        existing = supabase.table("roles_config").select("id").eq("email", email.lower()).execute()
        payload = {"email": email.lower(), "role": role, "assigned_at": datetime.now().isoformat()}
        
        if existing.data:
            resp = supabase.table("roles_config").update(payload).eq("email", email.lower()).execute()
        else:
            resp = supabase.table("roles_config").insert(payload).execute()
        
        return bool(resp.data)
    except Exception as e:
        print(f"[supabase_handler] [ERROR] Assign role failed: {str(e)}")
        return False


# ===========================================================================
# UTILITIES
# ===========================================================================

def get_dashboard_stats() -> Dict:
    """Get dashboard statistics"""
    if not SUPABASE_ENABLED or not supabase:
        return {}
    try:
        reports = supabase.table("reports").select("id").execute()
        pending = supabase.table("reports").select("id").eq("status", "submitted").execute()
        members = supabase.table("members").select("id").execute()
        
        return {
            "total_reports": len(reports.data) if reports.data else 0,
            "pending_reports": len(pending.data) if pending.data else 0,
            "total_members": len(members.data) if members.data else 0,
        }
    except Exception as e:
        print(f"[supabase_handler] [ERROR] Stats failed: {str(e)}")
        return {}
