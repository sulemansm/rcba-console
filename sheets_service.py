import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
import json
from oauth2client.service_account import ServiceAccountCredentials

SHEET_NAME = "RCBA Reports"

def connect_sheet():

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds_dict = st.secrets["gcp_service_account"]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        creds_dict, scope
    )

    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1

    return sheet

def save_report(row):

    sheet = connect_sheet()

    sheet.append_row(row)


def load_reports():

    sheet = connect_sheet()

    data = sheet.get_all_records()

    return pd.DataFrame(data)