import streamlit as st
import json
import os
import io
from report_generator import generate_report
from docx_builder import build_docx
from report_handler import save_report as save_report_handler
from datetime import datetime

# Try to use Supabase for members, fallback to JSON
try:
    from supabase_handler import get_all_members, SUPABASE_ENABLED
    USE_SUPABASE = SUPABASE_ENABLED
except:
    USE_SUPABASE = False

# Page header with helpful info
st.title("📝 Create Event Report")
st.markdown("💡 **Tip:** Club members for attendance selection are managed in the **Manage Club Members** page (available for admins/secretariat)")

# Load members for dropdown with short cache TTL to enable real-time updates
@st.cache_data(ttl=30)
def load_members():
    """Load members from Supabase or JSON fallback - cached for 30 seconds"""
    if USE_SUPABASE:
        try:
            db_members = get_all_members()
            return db_members if db_members else []
        except Exception as e:
            print(f"[1_create_report] Supabase load failed: {str(e)}, using JSON")
    
    # Fallback to JSON
    members_file = os.path.join(os.path.dirname(__file__), "..", "members.json")
    if os.path.exists(members_file):
        try:
            with open(members_file) as f:
                return json.load(f)
        except:
            return []
    return []

members = load_members()
member_names = [m.get("name", "") for m in members]

# Show member count in sidebar
if members:
    st.sidebar.info(f"📌 {len(members)} club members available")

# Event Details Section
st.subheader("📋 Event Details")
col1, col2 = st.columns(2)
with col1:
    event_title = st.text_input("Event Title *", key="event_title")
    event_venue = st.text_input("Venue", key="venue")

with col2:
    event_start_date = st.date_input("Event Start Date", key="event_start_date")
    chief_guest = st.text_input("Chief Guest", key="chief_guest")

description = st.text_area("Event Description", key="description", height=80)

# Event Work Section
st.subheader("🔧 Event Work")
col1, col2, col3 = st.columns(3)
with col1:
    pre_event = st.text_area("Pre Event Work", key="pre_event", height=80)
with col2:
    on_day = st.text_area("On Day Work", key="on_day", height=80)
with col3:
    post_event = st.text_area("Post Event Work", key="post_event", height=80)

outcome = st.text_area("Outcome", key="outcome", height=80)

# Attendance Section
st.subheader("👥 Attendance")
st.info("**Member Names** field is mandatory. Other fields are optional.")

col1, col2 = st.columns([2, 1])
with col1:
    # Member attendance with dropdown
    selected_members = st.multiselect(
        "Select Member Names *",
        options=member_names,
        key="member_attendance_list",
        help="Select members who attended the event"
    )
    member_attendance_count = len(selected_members)

with col2:
    st.metric("Member Count", member_attendance_count)

# Additional Attendance Fields
col1, col2 = st.columns(2)
with col1:
    guest_attendance_count = st.number_input(
        "Guest Attendance Count",
        value=0,
        min_value=0,
        key="guest_count",
        help="Number of guests who attended"
    )
    if guest_attendance_count > 0:
        guest_names = st.text_area(
            "Guest Names (comma-separated)",
            key="guest_names",
            height=70,
            help="Enter guest names separated by commas"
        )
    else:
        guest_names = ""

with col2:
    district_attendance_count = st.number_input(
        "District Attendance Count",
        value=0,
        min_value=0,
        key="district_count",
        help="Number of district members who attended"
    )
    if district_attendance_count > 0:
        district_names = st.text_area(
            "District Member Names (comma-separated)",
            key="district_names",
            height=70,
            help="Enter district member names separated by commas"
        )
    else:
        district_names = ""

col1, col2 = st.columns(2)
with col1:
    ambassadorial_attendance_count = st.number_input(
        "Ambassadorial Attendance Count",
        value=0,
        min_value=0,
        key="ambassador_count",
        help="Number of ambassadors (clubs) who attended"
    )
    if ambassadorial_attendance_count > 0:
        ambassadorial_club_names = st.text_area(
            "Club Names (comma-separated)",
            key="club_names",
            height=70,
            help="Enter club names separated by commas"
        )
    else:
        ambassadorial_club_names = ""

with col2:
    # Total attendance auto-calculated
    total_attendance = member_attendance_count + guest_attendance_count + district_attendance_count + ambassadorial_attendance_count
    st.metric("Total Attendance Count", total_attendance)

# Project Details Section
st.subheader("💰 Project Details")
col1, col2, col3, col4 = st.columns(4)
with col1:
    income = st.number_input("Income (₹)", value=0, min_value=0, key="income")
with col2:
    expenditure = st.number_input("Expenditure (₹)", value=0, min_value=0, key="expenditure")
with col3:
    profit_loss = income - expenditure
    st.metric("Profit/Loss", f"₹ {profit_loss}")
with col4:
    st.empty()

# Additional Details Section
st.subheader("📌 Additional Details")
col1, col2 = st.columns(2)
with col1:
    # Select Avenue Chair(s) from members dropdown
    avenue_chairs = st.multiselect(
        "Avenue Chair(s) *",
        options=member_names,
        key="avenue_chair",
        help="Select one or more avenue chairs for this event"
    )
    
    avenue = st.text_input("Avenue/Department", key="avenue", help="e.g., Community Service, Professional Development")
    
    drive_link = st.text_input("Drive Link", key="drive_link", help="Link to the shared drive folder for this event")

with col2:
    project_level = st.text_input("Project Level", key="project_level", help="e.g., Club, District, International")
    project_hours = st.number_input("Project Hours", value=0, min_value=0, key="project_hours")
    days = st.number_input("Days", value=1, min_value=1, key="days")
    man_hours = days * 24
    st.metric("Man Hours", man_hours)

# Report Generation Section
if st.button("🤖 Generate Draft Report", use_container_width=True, type="secondary"):
    if not event_title:
        st.error("Event Title is mandatory!")
    elif not selected_members:
        st.error("At least one member must be selected for attendance!")
    elif not avenue_chairs:
        st.error("At least one avenue chair must be selected!")
    else:
        with st.spinner("Generating draft report..."):
            report = generate_report({
                "title": event_title,
                "venue": event_venue,
                "chief_guest": chief_guest,
                "description": description,
                "pre_event": pre_event,
                "on_day": on_day,
                "post_event": post_event,
                "outcome": outcome
            })
            st.session_state.report = report
            st.success("✓ Draft generated! Edit below if needed.")

# Report Editing and DOCX Generation
if "report" in st.session_state:
    st.markdown("<hr style='margin: 2rem 0;'>", unsafe_allow_html=True)
    
    st.subheader("✏️ Edit Report Draft")
    edited_report = st.text_area(
        "Report Content",
        value=st.session_state.report,
        height=300,
        key="edited_report"
    )
    
    st.markdown("<hr style='margin: 1rem 0;'>", unsafe_allow_html=True)
    
    if st.button("📄 Generate & Download DOCX", use_container_width=True, type="primary"):
        # Validation
        if not event_title:
            st.error("Event Title is required!")
        elif not selected_members:
            st.error("Member attendance is required!")
        elif not avenue_chairs:
            st.error("At least one avenue chair is required!")
        else:
            with st.spinner("Generating DOCX..."):
                # Format attendance data for DOCX
                attendance_details = {
                    "Member Attendance": f"{member_attendance_count} - {', '.join(selected_members)}" if selected_members else "0",
                    "Guest Attendance": f"{guest_attendance_count} - {guest_names.replace(chr(10), ', ')}" if guest_names else str(guest_attendance_count),
                    "District Attendance": f"{district_attendance_count} - {district_names.replace(chr(10), ', ')}" if district_names else str(district_attendance_count),
                    "Ambassadorial Attendance": f"{ambassadorial_attendance_count} - {ambassadorial_club_names.replace(chr(10), ', ')}" if ambassadorial_club_names else str(ambassadorial_attendance_count),
                    "Total Attendance": total_attendance,
                }
                
                # Create project details dict with all information
                project_details = {
                    "Avenue": avenue or "—",
                    "Avenue Chairs": ", ".join(avenue_chairs) if avenue_chairs else "—",
                    "Drive Link": drive_link or "—",
                    "Project Level": project_level or "—",
                    "Project Hours": project_hours,
                    "Man Hours": man_hours,
                    "Income": f"₹ {income}",
                    "Expenditure": f"₹ {expenditure}",
                    "Profit/Loss": f"₹ {profit_loss}",
                }
                
                # Build DOCX with all data
                docx = build_docx(
                    {
                        "title": event_title,
                        "venue": event_venue,
                        "start_time": str(event_start_date),
                        "end_time": "",
                        "chief_guest": chief_guest
                    },
                    edited_report,
                    attendance_details,
                    project_details
                )
                
                # Convert to bytes if it's file-like object
                if hasattr(docx, 'getvalue'):
                    docx_bytes = docx.getvalue()
                else:
                    docx_bytes = docx
                
                # Prepare filename
                file_name = f"RCBA_Report_{event_title.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
                
                # Create download button
                st.download_button(
                    label="💾 Download DOCX Report",
                    data=docx_bytes,
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
                
                # Prepare report data for database
                report_data = {
                    "event_title": event_title,
                    "event_start_date": str(event_start_date),
                    "event_venue": event_venue,
                    "avenue": avenue,
                    "avenue_chairs": avenue_chairs,
                    "drive_link": drive_link,
                    "chief_guest": chief_guest,
                    "selected_members": selected_members,
                    "member_attendance_count": member_attendance_count,
                    "guest_count": guest_attendance_count,
                    "guest_names": guest_names,
                    "district_count": district_attendance_count,
                    "district_names": district_names,
                    "ambassadorial_count": ambassadorial_attendance_count,
                    "ambassadorial_names": ambassadorial_club_names,
                    "total_attendance": total_attendance,
                    "income": income,
                    "expenditure": expenditure,
                    "profit_loss": profit_loss,
                    "project_level": project_level,
                    "project_hours": project_hours,
                    "days": days,
                    "man_hours": man_hours,
                    "description": edited_report,
                    "submitted_at": str(datetime.now()),
                    "submitted_by_name": st.session_state.get("username", "Unknown"),
                    "submitted_by_email": st.session_state.get("user_email", "unknown@example.com"),
                    "role": st.session_state.get("role", "editor"),
                    "status": "submitted",
                }
                
                # Save to database with DOCX file
                result = save_report_handler(report_data, docx_binary=docx_bytes)
                
                if result.get("success"):
                    st.success(f"✓ Report saved with ID: {result.get('report_id')}")
                    st.balloons()
                else:
                    st.error(f"Failed to save report: {result.get('error', 'Unknown error')}")