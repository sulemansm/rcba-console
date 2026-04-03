import smtplib
from email.message import EmailMessage
import streamlit as st

SENDER_EMAIL = st.secrets["email"]["sender"]
SENDER_PASSWORD = st.secrets["email"]["password"]
SECRETARY_EMAIL = st.secrets["email"]["secretary"]


def send_email(event_title, docx_bytes):

    msg = EmailMessage()

    msg["Subject"] = f"Event Report — {event_title}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = SECRETARY_EMAIL

    msg.set_content(
        f"Please find attached the report for event: {event_title}"
    )

    msg.add_attachment(
        docx_bytes,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"{event_title}.docx"
    )

    with smtplib.SMTP("smtp.gmail.com",587) as server:

        server.starttls()

        server.login(SENDER_EMAIL,SENDER_PASSWORD)

        server.send_message(msg)