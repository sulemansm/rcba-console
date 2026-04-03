"""
dashboard.py — Role-specific dashboard views for RCBA Event Reporter.

Roles handled:
  secretariat → full table, filters, approve/reject/late-mark, download
  editor      → full table, read-only + download, can submit
  director    → own reports only, stats summary
"""

import os
import io
import json
import re
import time
import pandas as pd
import streamlit as st
from datetime import datetime

from report_handler import (
    load_reports, update_report, update_report_by_id,
    filter_reports, get_my_reports, compute_stats,
    is_late, get_status,
)
from auth import can_approve_reject, can_view_all_reports, can_mark_late

# ── Badge helpers ─────────────────────────────────────────────────────────────

def _row_class(status: str) -> str:
    if status == "Approved":
        return "approved"
    if status == "Rejected":
        return "changes"
    return "pending"


# ── Stats bar ─────────────────────────────────────────────────────────────────

def render_stats_bar(stats: dict, show_late: bool = True) -> None:
    """Uses native st.metric columns — works in all Streamlit versions."""
    cols = st.columns(5 if show_late else 4)
    cols[0].metric("Total",    stats["total"])
    cols[1].metric("Approved", stats["approved"])
    cols[2].metric("Rejected", stats["rejected"])
    cols[3].metric("Pending",  stats["pending"])
    if show_late:
        cols[4].metric("Late", stats["late"])
    st.markdown("<div style='margin-bottom:0.6rem;'></div>", unsafe_allow_html=True)


# ── Filter bar ────────────────────────────────────────────────────────────────

def render_filter_bar(reports: list, prefix: str = "") -> dict:
    """Renders filter controls and returns the active filter values."""
    all_submitters = sorted(set(
        r.get("submitted_by_name") or r.get("submitted_by_email", "Unknown")
        for r in reports
    ))

    with st.expander("🔍  Filters & Search", expanded=False):
        fc1, fc2, fc3 = st.columns([2, 2, 3])
        with fc1:
            status_filter = st.selectbox(
                "Status", ["All", "Pending", "Approved", "Rejected"],
                key=f"{prefix}_filter_status"
            )
        with fc2:
            submitter_filter = st.selectbox(
                "Submitted by", ["All"] + all_submitters,
                key=f"{prefix}_filter_submitter"
            )
        with fc3:
            search_q = st.text_input(
                "Search (title / member / avenue)",
                placeholder="Type to search...",
                key=f"{prefix}_filter_search"
            )

    return {
        "status":       status_filter,
        "submitted_by": submitter_filter,
        "search":       search_q,
    }


# ── Status/late text helpers (plain text, no HTML) ────────────────────────────

def _status_text(status: str) -> str:
    return {"Approved": "✅ Approved", "Rejected": "❌ Rejected"}.get(status, "🕐 Pending")

def _late_text(report: dict) -> str:
    return "🔴 Late" if is_late(report) else "🟢 On Time"


# ── Single report row ─────────────────────────────────────────────────────────

def render_report_row(
    r: dict,
    idx: int,
    real_idx: int,
    role: str,
    reviewer_name: str,
    send_review_email_fn,
    show_submitter: bool = True,
) -> None:
    status  = get_status(r)
    ev_date = r.get("event_start_date", "")
    sub_at  = r.get("submission_timestamp") or r.get("submitted_at", "")
    rid     = r.get("report_id", "")

    # Build a compact single-line summary using native markdown
    title    = r.get("event_title", "—")
    avenue   = r.get("avenue", "—") or "—"
    date_str = ev_date[:10] if ev_date else "—"
    sub_str  = sub_at[:10] if sub_at else "—"
    status_t = _status_text(status)
    late_t   = _late_text(r)

    # Left-border colour via a thin coloured rule above
    border_colour = {"Approved": "#4ECDC4", "Rejected": "#FF6B6B"}.get(status, "#FFB347")

    submitter_line = f"**By:** {r.get('submitted_by_name','—')}  · " if show_submitter else ""

    # Render the card with a coloured top stripe + text metadata
    st.markdown(
        f"<div style='border-left:3px solid {border_colour};"
        f"background:#111827;border-radius:10px;padding:0.75rem 1rem 0.5rem;"
        f"margin-bottom:0.3rem;border:1px solid rgba(255,255,255,0.07);"
        f"border-left:3px solid {border_colour};'>"
        f"<span style='font-family:Syne,sans-serif;font-size:0.95rem;font-weight:700;"
        f"color:#E8EDF5;'>{title}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Metadata row using native st.caption (always renders correctly)
    meta = (
        f"🗂 **{avenue}**  ·  "
        f"📅 {date_str}  ·  "
        f"{submitter_line}"
        f"📤 Submitted {sub_str}  ·  "
        f"{late_t}  ·  {status_t}"
    )
    st.markdown(meta)

    # Rejection/review comment
    rej_msg = r.get("rejection_message") or r.get("review_comment", "")
    if rej_msg:
        rb = r.get("reviewed_by", "")
        ra = (r.get("reviewed_at", "") or "")[:10]
        reviewer_line = f"**{rb}** · {ra} — " if rb else ""
        st.caption(f"💬 {reviewer_line}{rej_msg}")

    # Action expander (secretariat only for approve/reject; all for download)
    file_path = r.get("file_path", "")
    has_file  = file_path and os.path.exists(file_path)

    with st.expander(f"{'Manage' if can_approve_reject(role) else 'Details'} — {r.get('event_title','Report')}", expanded=False):

        # Download button
        if has_file:
            with open(file_path, "rb") as fh:
                file_bytes = fh.read()
            ev_title_safe = r.get("event_title", "report").replace(" ", "_")
            st.download_button(
                label="⬇  Download DOCX",
                data=file_bytes,
                file_name=f"RCBA_Report_{ev_title_safe}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"dl_{rid or real_idx}",
                use_container_width=True,
            )
        else:
            st.caption("No DOCX file attached to this report.")

        if can_approve_reject(role):
            existing_comment = r.get("rejection_message") or r.get("review_comment", "")
            comment_val = st.text_area(
                "Comments / Rejection message",
                value=existing_comment,
                placeholder="Provide feedback or rejection reason (required for rejection)...",
                height=90,
                key=f"comment_{rid or real_idx}",
            )

            col_a, col_r, col_late, _ = st.columns([1, 1, 1, 1])

            with col_a:
                if st.button("✓ Approve", key=f"approve_{rid or real_idx}", type="primary", use_container_width=True):
                    with st.spinner("Saving & emailing…"):
                        try:
                            send_review_email_fn(r, "approve", comment_val, reviewer_name)
                            _patch(rid, real_idx, {
                                "status": "Approved",
                                "approval_status": "approved",
                                "review_comment": comment_val,
                                "rejection_message": "",
                                "reviewed_by": reviewer_name,
                                "reviewed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            })
                            st.success(f"Approved — email sent to {r.get('submitted_by_email', 'member')}.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not send email: {exc}")

            with col_r:
                if st.button("✗ Reject", key=f"reject_{rid or real_idx}", type="secondary", use_container_width=True):
                    if not comment_val.strip():
                        st.warning("Please add a rejection reason before rejecting.")
                    else:
                        with st.spinner("Saving & emailing…"):
                            try:
                                send_review_email_fn(r, "reject", comment_val, reviewer_name)
                                _patch(rid, real_idx, {
                                    "status": "Rejected",
                                    "approval_status": "changes",
                                    "rejection_message": comment_val,
                                    "review_comment": comment_val,
                                    "reviewed_by": reviewer_name,
                                    "reviewed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                })
                                st.success(f"Rejected — email sent to {r.get('submitted_by_email', 'member')}.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Could not send email: {exc}")

            if can_mark_late(role):
                with col_late:
                    current_late = is_late(r)
                    btn_label = "Mark On-Time" if current_late else "Mark Late"
                    if st.button(btn_label, key=f"late_{rid or real_idx}", use_container_width=True):
                        _patch(rid, real_idx, {"is_late": not current_late})
                        st.rerun()


def _patch(rid: str, fallback_idx: int, fields: dict):
    if rid and update_report_by_id(rid, fields):
        return
    update_report(fallback_idx, fields)


# ── Table renderer ────────────────────────────────────────────────────────────

def extract_docx_text(file_path: str) -> str:
    """Extract text content from DOCX file."""
    try:
        from docx import Document
        doc = Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
        return text
    except Exception as e:
        return f"Could not read document: {e}"

def render_report_summary_table(reports: list, show_submitter: bool = True) -> None:
    """Render a styled summary table of reports."""
    if not reports:
        return
    
    # Build table data
    table_data = []
    for r in reversed(reports):
        status = get_status(r)
        ev_date = r.get("event_start_date", "—")[:10] if r.get("event_start_date") else "—"
        sub_at = (r.get("submission_timestamp") or r.get("submitted_at", ""))[:10] if r.get("submission_timestamp") or r.get("submitted_at") else "—"
        
        # Get total attendance (new structure or fallback)
        total_attendance = r.get("total_attendance", r.get("member_attendance_count", 0))
        
        row = {
            "📄 Title": r.get("event_title", "—"),
            "🏢 Avenue": r.get("avenue", "—") or "—",
            "👥 Attendance": str(total_attendance),
            "📅 Event": ev_date,
            "✅ Status": _status_text(status),
            "⏰ Late": _late_text(r),
            "📤 Submitted": sub_at,
        }
        
        if show_submitter:
            row["👤 By"] = r.get("submitted_by_name", "—")
        
        table_data.append(row)
    
    df = pd.DataFrame(table_data)
    
    # Custom styling for the table
    st.markdown("""
    <style>
    .summary-table {
        border-collapse: collapse;
        width: 100%;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        overflow: hidden;
    }
    .summary-table thead {
        background: rgba(0,201,177,0.15);
        border-bottom: 2px solid rgba(0,201,177,0.3);
    }
    .summary-table th {
        padding: 12px 16px;
        text-align: left;
        font-family: 'Syne', sans-serif;
        font-weight: 600;
        color: #00C9B1;
        font-size: 0.85rem;
        letter-spacing: 0.05em;
    }
    .summary-table td {
        padding: 12px 16px;
        border-bottom: 1px solid rgba(255,255,255,0.05);
        color: #E8EDF5;
        font-size: 0.9rem;
    }
    .summary-table tbody tr:hover {
        background: rgba(0,201,177,0.05);
    }
    .summary-table tbody tr:last-child td {
        border-bottom: none;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.dataframe(df, use_container_width=True, hide_index=True)

def render_reports_table(reports: list, role: str, reviewer_name: str, send_review_email_fn, show_submitter: bool = True) -> None:
    """Render all reports in a card format with summary table."""
    if not reports:
        st.markdown("""
        <div style='background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:2rem;text-align:center;'>
            <p style='color:var(--muted);margin:0;'>No reports to display</p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # Render summary table first
    st.markdown("<div style='margin-bottom:1.5rem;'></div>", unsafe_allow_html=True)
    render_report_summary_table(reports, show_submitter=show_submitter)
    
    st.markdown("<div style='margin:2rem 0;border-top:1px solid var(--border);padding-top:2rem;'></div>", unsafe_allow_html=True)
    st.markdown("<p style='color:var(--muted);font-size:0.9rem;margin-bottom:1.5rem;'>Actions & Details</p>", unsafe_allow_html=True)
    
    for idx, r in enumerate(reversed(reports)):
        real_idx = len(reports) - 1 - idx
        rid = r.get("report_id", "")
        file_path = r.get("file_path", "")
        has_file = file_path and os.path.exists(file_path)
        status = get_status(r)
        is_reviewed = status != "Pending"
        
        # Status color indicator

        status_colors = {
            "Approved": "rgba(78,205,196,0.15)",
            "Rejected": "rgba(255,107,107,0.15)",
            "Pending": "rgba(255,179,71,0.15)"
        }
        status_color = status_colors.get(status, "rgba(0,201,177,0.08)")
        
        st.markdown(f"""
        <div style='background:{status_color};border:1px solid rgba(0,201,177,0.25);border-radius:12px;padding:1.2rem;margin-bottom:1rem;'>
            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:0.8rem;'>
                <h4 style='color:#E8EDF5;margin:0;font-size:1rem;'>{r.get('event_title', 'Report')}</h4>
                <span style='color:#00C9B1;font-size:0.75rem;font-weight:600;'>{status}</span>
            </div>
            <p style='color:var(--muted);margin:0;font-size:0.85rem;'>📅 Event: {r.get("event_start_date", "—")[:10]} | 📤 Submitted: {(r.get("submission_timestamp") or r.get("submitted_at", ""))[:10]}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Action buttons
        if has_file:
            col1, col2, col3, col4 = st.columns([0.8, 0.8, 1, 1.4])
        else:
            col1, col2, col3 = st.columns([0.8, 1, 1.4])
            col4 = None
        
        # Helper function for toggle
        def toggle_view(key):
            st.session_state[f"view_expanded_{key}"] = not st.session_state.get(f"view_expanded_{key}", False)
        
        def toggle_review(key):
            st.session_state[f"review_expanded_{key}"] = not st.session_state.get(f"review_expanded_{key}", False)
        
        # View button
        with col1:
            if has_file:
                st.button("👁️", key=f"view_btn_{rid or real_idx}", help="View report content", use_container_width=True, 
                         on_click=toggle_view, args=(f"{rid or real_idx}",))
        
        # Download button
        with col2:
            if has_file:
                with open(file_path, "rb") as fh:
                    file_bytes = fh.read()
                ev_title_safe = r.get("event_title", "report").replace(" ", "_")
                st.download_button(
                    label="💾",
                    data=file_bytes,
                    file_name=f"RCBA_Report_{ev_title_safe}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key=f"dl_{rid or real_idx}",
                    use_container_width=True,
                    help="Download DOCX file"
                )
        
        # Review button for secretariat - using on_click callback
        if can_approve_reject(role):
            with col3:
                if is_reviewed:
                    st.button("✓", key=f"review_done_{rid or real_idx}", use_container_width=True, disabled=True, help="Already reviewed")
                else:
                    st.button("📝", key=f"review_btn_{rid or real_idx}", use_container_width=True, help="Review and approve/reject",
                             on_click=toggle_review, args=(f"{rid or real_idx}",))
        
        # View modal for report content
        if st.session_state.get(f"view_expanded_{rid or real_idx}", False):
            with st.expander("📖 Report Preview", expanded=True):
                if has_file:
                    report_text = extract_docx_text(file_path)
                    st.markdown(f"""
                    <div style='background:var(--surface2);border:1px solid var(--border);border-radius:12px;padding:1.5rem;max-height:600px;overflow-y:auto;'>
                        <p style='color:#E8EDF5;white-space:pre-wrap;line-height:1.6;'>{report_text}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button("Close Preview", key=f"close_view_{rid or real_idx}"):
                        st.session_state[f"view_{rid or real_idx}"] = False
                        st.rerun()
        
        # Attendance Details Section
        if r.get("total_attendance") or r.get("member_attendance"):
            with st.expander("👥 Attendance Details", expanded=False):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Total Attendance", r.get("total_attendance", 0))
                    st.markdown(f"**Avenue Chair:** {r.get('avenue_chair', '—')}")
                    st.markdown(f"**Avenue:** {r.get('avenue', '—')}")
                    st.markdown(f"**Member Attendance:** {r.get('member_attendance_count', 0)}")
                
                with col2:
                    st.markdown(f"**Drive Link:** [{r.get('drive_link', '—')}]({r.get('drive_link', '#')})" if r.get('drive_link') else "**Drive Link:** —")
                    st.markdown(f"**Guest Attendance:** {r.get('guest_attendance_count', 0)}")
                    st.markdown(f"**District Attendance:** {r.get('district_attendance_count', 0)}")
                    st.markdown(f"**Ambassadorial Attendance:** {r.get('ambassadorial_attendance_count', 0)}")
                
                # Detailed attendance info
                if r.get("member_attendance"):
                    st.markdown("**Member Names:**")
                    st.markdown(", ".join(r.get("member_attendance", [])) if isinstance(r.get("member_attendance"), list) else r.get("member_attendance"))
                
                if r.get("guest_names"):
                    st.markdown("**Guest Names:**")
                    st.text(r.get("guest_names"))
                
                if r.get("district_names"):
                    st.markdown("**District Member Names:**")
                    st.text(r.get("district_names"))
                
                if r.get("ambassadorial_club_names"):
                    st.markdown("**Club Names:**")
                    st.text(r.get("ambassadorial_club_names"))
        
        # Review form for secretariat
        if can_approve_reject(role):
            if st.session_state.get(f"review_expanded_{rid or real_idx}", False):
                with st.expander(f"📝 Review: {r.get('event_title', 'Report')}", expanded=True):
                    existing_comment = r.get("rejection_message") or r.get("review_comment", "")
                    comment_val = st.text_area(
                        "Comments / Rejection message",
                        value=existing_comment,
                        placeholder="Provide feedback or rejection reason...",
                        height=80,
                        key=f"comment_{rid or real_idx}",
                    )
                    
                    col_a, col_r, col_late = st.columns(3)
                    
                    with col_a:
                        if st.button("✓ Approve", key=f"approve_{rid or real_idx}", type="primary", use_container_width=True):
                            with st.spinner("Saving & emailing…"):
                                try:
                                    send_review_email_fn(r, "approve", comment_val, reviewer_name)
                                    _patch(rid, real_idx, {
                                        "status": "Approved",
                                        "approval_status": "approved",
                                        "review_comment": comment_val,
                                        "rejection_message": "",
                                        "reviewed_by": reviewer_name,
                                        "reviewed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    })
                                    st.success("Approved — email sent.")
                                    st.session_state[f"review_expanded_{rid or real_idx}"] = False
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Error: {exc}")
                    
                    with col_r:
                        if st.button("✗ Reject", key=f"reject_{rid or real_idx}", type="secondary", use_container_width=True):
                            if not comment_val.strip():
                                st.warning("Please add a rejection reason.")
                            else:
                                with st.spinner("Saving & emailing…"):
                                    try:
                                        send_review_email_fn(r, "reject", comment_val, reviewer_name)
                                        _patch(rid, real_idx, {
                                            "status": "Rejected",
                                            "approval_status": "changes",
                                            "rejection_message": comment_val,
                                            "review_comment": comment_val,
                                            "reviewed_by": reviewer_name,
                                            "reviewed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                        })
                                        st.success("Rejected — email sent.")
                                        st.session_state[f"review_expanded_{rid or real_idx}"] = False
                                        time.sleep(1)
                                        st.rerun()
                                    except Exception as exc:
                                        st.error(f"Error: {exc}")
                    
                    if can_mark_late(role):
                        with col_late:
                            current_late = is_late(r)
                            btn_label = "On-Time" if current_late else "Mark Late"
                            if st.button(btn_label, key=f"late_{rid or real_idx}", use_container_width=True):
                                _patch(rid, real_idx, {"is_late": not current_late})
                                st.rerun()
        
        st.markdown("<div style='border-top:1px solid rgba(255,255,255,0.05);margin:1.5rem 0;'></div>", unsafe_allow_html=True)



def page_dashboard_secretariat(send_review_email_fn) -> None:
    """Full admin view: all reports, filters, approve/reject/late."""
    st.markdown("""
    <div style='margin-bottom:2rem;'>
        <h1 style='color:#E8EDF5;font-size:2rem;margin:0;font-family:Syne,sans-serif;font-weight:700;'>📋 All Submissions</h1>
        <p style='color:var(--muted);font-size:0.95rem;margin:0.5rem 0 0;'>Review and approve submissions from your team members</p>
    </div>
    """, unsafe_allow_html=True)

    all_reports = load_reports()
    stats = compute_stats(all_reports)
    render_stats_bar(stats, show_late=True)

    if not all_reports:
        st.markdown("""
        <div style='background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:2rem;text-align:center;margin:1rem 0;'>
            <h3 style='color:#E8EDF5;margin:0;'>No submissions yet</h3>
            <p style='color:var(--muted);margin:0.5rem 0 0;'>Reports will appear here once members submit them</p>
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown("<div style='margin:1.5rem 0;'></div>", unsafe_allow_html=True)
    filters = render_filter_bar(all_reports, prefix="sec")
    filtered = filter_reports(
        all_reports,
        status=filters["status"],
        submitted_by=filters["submitted_by"],
        search=filters["search"],
    )

    st.markdown(f"""
    <div style='background:rgba(0,201,177,0.08);border-left:3px solid #00C9B1;border-radius:8px;padding:1rem;margin:1rem 0 1.5rem;'>
        <p style='color:#00C9B1;font-weight:600;margin:0;font-size:0.9rem;'>📊 Showing {len(filtered)} of {len(all_reports)} submission(s)</p>
    </div>
    """, unsafe_allow_html=True)

    reviewer_name = st.session_state.get("username", "Secretariat")
    
    render_reports_table(filtered, role="secretariat", reviewer_name=reviewer_name, send_review_email_fn=send_review_email_fn, show_submitter=True)


def page_dashboard_editor(send_review_email_fn) -> None:
    """Editor view: see all reports, download only (no approve/reject)."""
    st.markdown("""
    <div style='margin-bottom:2rem;'>
        <h1 style='color:#E8EDF5;font-size:2rem;margin:0;font-family:Syne,sans-serif;font-weight:700;'>📑 All Reports</h1>
        <p style='color:var(--muted);font-size:0.95rem;margin:0.5rem 0 0;'>View and download all submitted reports from your team</p>
    </div>
    """, unsafe_allow_html=True)

    all_reports = load_reports()
    stats = compute_stats(all_reports)
    render_stats_bar(stats, show_late=False)

    if not all_reports:
        st.markdown("""
        <div style='background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:2rem;text-align:center;margin:1rem 0;'>
            <h3 style='color:#E8EDF5;margin:0;'>No reports yet</h3>
            <p style='color:var(--muted);margin:0.5rem 0 0;'>Reports will appear here once they are submitted</p>
        </div>
        """, unsafe_allow_html=True)
        return

    st.markdown("<div style='margin:1.5rem 0;'></div>", unsafe_allow_html=True)
    filters = render_filter_bar(all_reports, prefix="ed")
    filtered = filter_reports(
        all_reports,
        status=filters["status"],
        submitted_by=filters["submitted_by"],
        search=filters["search"],
    )

    st.markdown(f"""
    <div style='background:rgba(0,201,177,0.08);border-left:3px solid #00C9B1;border-radius:8px;padding:1rem;margin:1rem 0 1.5rem;'>
        <p style='color:#00C9B1;font-weight:600;margin:0;font-size:0.9rem;'>📊 Showing {len(filtered)} of {len(all_reports)} report(s)</p>
    </div>
    """, unsafe_allow_html=True)

    render_reports_table(filtered, role="editor", reviewer_name="", send_review_email_fn=send_review_email_fn, show_submitter=True)


def page_dashboard_director() -> None:
    """Director view: own reports only, with summary stats."""
    email = st.session_state.get("user_email", "")

    st.markdown("""
    <div style='margin-bottom:2rem;'>
        <h1 style='color:#E8EDF5;font-size:2rem;margin:0;font-family:Syne,sans-serif;font-weight:700;'>📊 My Reports</h1>
        <p style='color:var(--muted);font-size:0.95rem;margin:0.5rem 0 0;'>Track the status of your submitted event reports</p>
    </div>
    """, unsafe_allow_html=True)

    all_reports = load_reports()
    my_reports  = get_my_reports(all_reports, email)

    if not my_reports:
        st.markdown("""
        <div style='background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:2rem;text-align:center;margin:1rem 0;'>
            <h3 style='color:#E8EDF5;margin:0;'>No reports yet</h3>
            <p style='color:var(--muted);margin:0.5rem 0 0;'>Submit your first event report via the "New Report" page above</p>
        </div>
        """, unsafe_allow_html=True)
        return

    stats = compute_stats(my_reports)
    render_stats_bar(stats, show_late=True)

    st.markdown("<div style='margin:1.5rem 0;'></div>", unsafe_allow_html=True)

    # Search within own reports
    search_q = st.text_input("🔍 Search reports", placeholder="Search by title or avenue…", key="dir_search")
    filtered = filter_reports(my_reports, search=search_q or None)

    st.markdown(f"""
    <div style='background:rgba(0,201,177,0.08);border-left:3px solid #00C9B1;border-radius:8px;padding:1rem;margin:1rem 0 1.5rem;'>
        <p style='color:#00C9B1;font-weight:600;margin:0;font-size:0.9rem;'>📄 You have {len(filtered)} report(s)</p>
    </div>
    """, unsafe_allow_html=True)

    render_reports_table(filtered, role="director", reviewer_name="", send_review_email_fn=lambda *a, **kw: None, show_submitter=False)


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN PAGE — Member & Role Management
# ══════════════════════════════════════════════════════════════════════════════

def load_roles_file():
    """Load roles.json file."""
    roles_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "roles.json")
    try:
        with open(roles_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "_comment": "Role-based access control.",
            "secretariat_emails": [],
            "director_emails": [],
            "editor_emails": [],
            "admin_emails": [],
            "roles": {}
        }

def save_roles_file(data):
    """Save roles.json file."""
    roles_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "roles.json")
    with open(roles_file, "w") as f:
        json.dump(data, f, indent=2)

def load_env_file():
    """Load .env file as dictionary."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    env_data = {}
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env_data[key.strip()] = val.strip()
    return env_data

def save_env_file(env_data):
    """Save .env file."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    with open(env_path, "w") as f:
        for key, val in env_data.items():
            f.write(f"{key}={val}\n")

def is_valid_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def page_admin():
    """Admin page for managing members and roles."""
    # Access control - only admin can access this page
    if st.session_state.get("role") != "admin":
        st.error("❌ Access Denied - Admin only")
        st.stop()
    
    st.markdown("<p class='rcba-page-title'>Team Management</p>", unsafe_allow_html=True)
    st.markdown("<p class='rcba-page-sub'>Add/remove core/BODs from the whitelist and assign their roles.</p>", unsafe_allow_html=True)
    
    # Load current data
    roles_data = load_roles_file()
    env_data = load_env_file()
    
    # Parse whitelist from env
    whitelist_str = env_data.get("WHITELISTED_EMAILS", "")
    whitelist = [e.strip() for e in whitelist_str.split(",") if e.strip()] if whitelist_str else []
    
    # Get current members with their roles
    secretariat_emails = set(roles_data.get("secretariat_emails", []))
    director_emails = set(roles_data.get("director_emails", []))
    editor_emails = set(roles_data.get("editor_emails", []))
    
    # Create member list with roles
    member_roles = {}
    for email in whitelist:
        if email in secretariat_emails:
            member_roles[email] = "secretariat"
        elif email in editor_emails:
            member_roles[email] = "editor"
        elif email in director_emails:
            member_roles[email] = "director"
        else:
            member_roles[email] = "director"  # default
    
    # Tab 1: Add New Member
    tab1, tab2 = st.tabs(["➕ Add Member", "📋 Current Members"])
    
    with tab1:
        st.markdown("""
        <div style='background:rgba(0,201,177,0.08);border:1px solid rgba(0,201,177,0.25);border-radius:12px;padding:1.2rem;margin-bottom:1.5rem;'>
            <p style='color:#00C9B1;font-weight:600;margin:0;'>Add New Members</p>
            <p style='color:var(--muted);font-size:0.9rem;margin:0.5rem 0 0;'>Separate multiple emails with commas or line breaks</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns([2, 1])
        with col1:
            new_emails = st.text_area(
                "Email Address(es)", 
                placeholder="member@example.com\nor member1@example.com, member2@example.com", 
                height=100, 
                key="new_member_email",
                label_visibility="collapsed"
            )
        with col2:
            new_role = st.selectbox(
                "Role", 
                ["director", "editor", "secretariat"], 
                key="new_member_role",
                label_visibility="visible"
            )
        
        if st.button("+ Add Member(s)", type="primary", use_container_width=True, key="btn_add_members"):
            # Parse emails from input (support both comma-separated and newline-separated)
            email_list = []
            for line in new_emails.split('\n'):
                # Split by comma as well
                for email in line.split(','):
                    email = email.strip().lower()
                    if email:
                        email_list.append(email)
            
            # Initialize message container
            msg_container = st.container()
            
            if not email_list:
                with msg_container:
                    st.error("❌ Please enter at least one email address.")
            else:
                added_emails = []
                invalid_emails = []
                existing_emails = []
                
                for email in email_list:
                    if not is_valid_email(email):
                        invalid_emails.append(email)
                    elif email in whitelist:
                        existing_emails.append(email)
                    else:
                        # Add to whitelist
                        whitelist.append(email)
                        added_emails.append(email)
                        
                        # Update roles
                        if new_role == "secretariat":
                            secretariat_emails.add(email)
                        elif new_role == "editor":
                            editor_emails.add(email)
                        else:
                            director_emails.add(email)
                
                # Display messages
                with msg_container:
                    if added_emails:
                        # Save files
                        env_data["WHITELISTED_EMAILS"] = ", ".join(whitelist)
                        roles_data["secretariat_emails"] = sorted(list(secretariat_emails))
                        roles_data["editor_emails"] = sorted(list(editor_emails))
                        roles_data["director_emails"] = sorted(list(director_emails))
                        
                        save_env_file(env_data)
                        save_roles_file(roles_data)
                        
                        success_msg = f"✅ Successfully added {len(added_emails)} member(s) as {new_role}:\n\n"
                        for e in added_emails:
                            success_msg += f"  • {e}\n"
                        st.success(success_msg, icon="✅")
                        
                        if existing_emails:
                            existing_msg = "⚠️ These emails already exist:\n\n"
                            for e in existing_emails:
                                existing_msg += f"  • {e}\n"
                            st.warning(existing_msg)
                        
                        if invalid_emails:
                            invalid_msg = "❌ These emails are invalid:\n\n"
                            for e in invalid_emails:
                                invalid_msg += f"  • {e}\n"
                            st.error(invalid_msg)
                        
                        # Keep message visible longer
                        import time
                        time.sleep(2)
                        st.rerun()
                    elif existing_emails:
                        msg = "These emails already exist in the system:\n\n"
                        for e in existing_emails:
                            msg += f"  • {e}\n"
                        st.info(msg)
                    elif invalid_emails:
                        msg = "Invalid email format(s):\n\n"
                        for e in invalid_emails:
                            msg += f"  • {e}\n"
                        st.error(msg)
    
    # Tab 2: Current Members
    with tab2:
        st.subheader("Current Members", divider="gray")
        
        if not whitelist:
            st.info("No members added yet.")
        else:
            # Display members table
            member_data = []
            for email in sorted(whitelist):
                role = member_roles.get(email, "director")
                member_data.append({"Email": email, "Role": role})
            
            df_members = pd.DataFrame(member_data)
            st.dataframe(df_members, use_container_width=True, hide_index=True)
            
            # Member actions
            st.markdown("---")
            st.subheader("Update Member", divider="gray")
            
            select_email = st.selectbox("Select Member", sorted(whitelist), key="select_member_to_update")
            if select_email:
                current_role = member_roles.get(select_email, "director")
                new_role_update = st.selectbox("New Role", ["director", "editor", "secretariat"], index=["director", "editor", "secretariat"].index(current_role), key="update_member_role")
                
                col_update, col_delete = st.columns(2)
                
                with col_update:
                    if st.button("Update Role", type="primary", use_container_width=True, key="btn_update_role"):
                        # Remove from old role
                        if select_email in secretariat_emails:
                            secretariat_emails.discard(select_email)
                        elif select_email in editor_emails:
                            editor_emails.discard(select_email)
                        elif select_email in director_emails:
                            director_emails.discard(select_email)
                        
                        # Add to new role
                        if new_role_update == "secretariat":
                            secretariat_emails.add(select_email)
                        elif new_role_update == "editor":
                            editor_emails.add(select_email)
                        else:
                            director_emails.add(select_email)
                        
                        # Save
                        roles_data["secretariat_emails"] = sorted(list(secretariat_emails))
                        roles_data["editor_emails"] = sorted(list(editor_emails))
                        roles_data["director_emails"] = sorted(list(director_emails))
                        save_roles_file(roles_data)
                        
                        st.success(f"✓ {select_email} updated to {new_role_update}.")
                        st.rerun()
                
                with col_delete:
                    if st.button("Remove Member", type="secondary", use_container_width=True, key="btn_delete_member"):
                        # Remove from whitelist
                        whitelist.remove(select_email)
                        env_data["WHITELISTED_EMAILS"] = ", ".join(whitelist)
                        
                        # Remove from all roles
                        secretariat_emails.discard(select_email)
                        editor_emails.discard(select_email)
                        director_emails.discard(select_email)
                        
                        # Save
                        roles_data["secretariat_emails"] = sorted(list(secretariat_emails))
                        roles_data["editor_emails"] = sorted(list(editor_emails))
                        roles_data["director_emails"] = sorted(list(director_emails))
                        
                        save_env_file(env_data)
                        save_roles_file(roles_data)
                        
                        st.success(f"✓ {select_email} removed from whitelist.")
                        st.rerun()


def page_manage_members():
    """Manage club members for attendance and avenue chair selection."""
    # Try to use Supabase
    try:
        from supabase_handler import (
            get_all_members, add_member_to_db, delete_member_from_db, 
            member_exists, SUPABASE_ENABLED
        )
        USE_SUPABASE = SUPABASE_ENABLED
    except:
        USE_SUPABASE = False
    
    # Access control - only admin and secretariat can manage members
    current_role = st.session_state.get("role")
    if current_role not in ("admin", "secretariat"):
        st.error("❌ Access Denied - Admin/Secretariat only")
        st.stop()
    
    st.markdown("<p class='rcba-page-title'>Manage Club Members</p>", unsafe_allow_html=True)
    st.markdown("<p class='rcba-page-sub'>Add, view, and manage club members for attendance and avenue chair roles</p>", unsafe_allow_html=True)
    
    # Load members file (JSON fallback)
    members_file = os.path.join(os.path.dirname(__file__), "members.json")
    
    def load_members_list():
        """Load members from Supabase or JSON file"""
        if USE_SUPABASE:
            try:
                return get_all_members()
            except:
                pass
        
        # Fallback to JSON
        if os.path.exists(members_file):
            try:
                with open(members_file) as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def save_member_db(name, email):
        """Save member to database"""
        if USE_SUPABASE:
            try:
                return add_member_to_db(name, email, "Member")
            except:
                pass
        
        # Fallback to JSON
        members_list = load_members_list()
        new_member = {
            "name": name.strip(),
            "email": email.strip().lower(),
            "role": "Member",
            "added_date": str(datetime.now())
        }
        members_list.append(new_member)
        
        try:
            with open(members_file, "w") as f:
                json.dump(members_list, f, indent=2)
            return True
        except:
            return False
    
    def delete_member_db(name):
        """Delete member from database"""
        if USE_SUPABASE:
            try:
                return delete_member_from_db(name)
            except:
                pass
        
        # Fallback to JSON
        members_list = load_members_list()
        new_list = [m for m in members_list if m.get("name") != name]
        
        try:
            with open(members_file, "w") as f:
                json.dump(new_list, f, indent=2)
            return True
        except:
            return False
    
    def check_member_exists(name="", email=""):
        """Check if member exists"""
        if USE_SUPABASE:
            try:
                return member_exists(name=name, email=email)
            except:
                pass
        
        # Fallback check in JSON
        members_list = load_members_list()
        if name:
            return any(m.get("name", "").lower() == name.lower() for m in members_list)
        if email:
            return any(m.get("email", "").lower() == email.lower() for m in members_list)
        return False
    
    # Load current members
    members_list = load_members_list()
    
    # Create tabs
    tab1, tab2 = st.tabs(["➕ Add Members", "📋 View Members"])
    
    # TAB 1: Add Members
    with tab1:
        st.markdown("""
        <div style='background:rgba(0,201,177,0.08);border:1px solid rgba(0,201,177,0.25);border-radius:12px;padding:1.2rem;margin-bottom:1.5rem;'>
            <p style='color:#00C9B1;font-weight:600;margin:0;'>Add New Club Members</p>
            <p style='color:var(--muted);font-size:0.9rem;margin:0.5rem 0 0;'>Add members who can be selected for attendance and avenue chair roles in event reports</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([2, 1.5, 1.5])
        with col1:
            member_name = st.text_input("Member Name *", placeholder="Full name", key="member_name_pg")
        with col2:
            member_email = st.text_input("Email Address *", placeholder="email@example.com", key="member_email_pg")
        with col3:
            st.markdown("<span style='color:var(--muted);font-size:0.85rem;'>Role: Member</span>", unsafe_allow_html=True)
            st.text_input("Role", value="Member", disabled=True, key="member_role_display_pg")
        
        if st.button("➕ Add Member", type="primary", use_container_width=True, key="btn_add_member_pg"):
            if not member_name.strip():
                st.error("❌ Member name is required.")
            elif not member_email.strip():
                st.error("❌ Email address is required.")
            elif not is_valid_email(member_email):
                st.error("❌ Invalid email format.")
            elif check_member_exists(email=member_email):
                st.error("❌ This email is already registered.")
            elif check_member_exists(name=member_name):
                st.error("❌ This member name already exists.")
            else:
                # Add new member
                if save_member_db(member_name, member_email):
                    st.success(f"✅ {member_name} added successfully to club members!")
                    st.balloons()
                    time.sleep(1.5)
                    st.rerun()
                else:
                    st.error("Failed to add member. Please try again.")
    
    # TAB 2: View & Manage Members
    with tab2:
        if not members_list:
            st.info("📭 No club members added yet. Add members using the 'Add Members' tab above.")
        else:
            # Display statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Members", len(members_list))
            with col2:
                st.metric("Date Added (Latest)", members_list[-1].get("added_date", "—").split(" ")[0])
            with col3:
                st.metric("Status", "Active")
            
            st.markdown("---")
            
            # Display members in a table
            st.subheader("Club Members Directory")
            member_display_data = []
            for idx, m in enumerate(members_list):
                member_display_data.append({
                    "No.": idx + 1,
                    "Name": m.get("name", "—"),
                    "Email": m.get("email", "—"),
                    "Role": m.get("role", "Member"),
                    "Added Date": m.get("added_date", "—").split(" ")[0]
                })
            
            df_members = pd.DataFrame(member_display_data)
            st.dataframe(df_members, use_container_width=True, hide_index=True)
            
            # Export members as CSV
            csv_data = df_members.to_csv(index=False)
            st.download_button(
                label="📥 Download Members as CSV",
                data=csv_data,
                file_name=f"club_members_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            st.markdown("---")
            st.subheader("Remove Member", divider="gray")
            
            # Secretariat can only delete members with "Member" role
            current_role = st.session_state.get("role", "")
            if current_role == "secretariat":
                deletable_members = [m for m in members_list if m.get("role") == "Member"]
                if not deletable_members:
                    st.info("ℹ️ No removable members. (Secretariat can only remove members with 'Member' role)")
                else:
                    member_names_for_removal = [m.get("name", "") for m in deletable_members]
                    selected_member_to_remove = st.selectbox(
                        "Select member to remove",
                        member_names_for_removal,
                        key="select_member_remove_pg",
                        help="Choose a member to remove from the directory"
                    )
                    
                    col1, col2 = st.columns([0.8, 0.2])
                    with col1:
                        st.info(f"⚠️ This will remove **{selected_member_to_remove}** from the members list. They can be re-added later.")
                    
                    with col2:
                        if st.button("🗑️ Remove", type="secondary", use_container_width=True, key="btn_remove_member_pg"):
                            if delete_member_db(selected_member_to_remove):
                                st.success(f"✅ {selected_member_to_remove} removed successfully!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Failed to remove member. Please try again.")
            else:
                # Admin can delete all members
                member_names_for_removal = [m.get("name", "") for m in members_list]
                selected_member_to_remove = st.selectbox(
                    "Select member to remove",
                    member_names_for_removal,
                    key="select_member_remove_pg",
                    help="Choose a member to remove from the directory"
                )
                
                col1, col2 = st.columns([0.8, 0.2])
                with col1:
                    st.info(f"⚠️ This will remove **{selected_member_to_remove}** from the members list. They can be re-added later.")
                
                with col2:
                    if st.button("🗑️ Remove", type="secondary", use_container_width=True, key="btn_remove_member_admin"):
                        if delete_member_db(selected_member_to_remove):
                            st.success(f"✅ {selected_member_to_remove} removed successfully!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Failed to remove member. Please try again.")
