#!/usr/bin/env python3

import argparse
import csv
import os
import subprocess
import smtplib
from email.message import EmailMessage
from datetime import datetime, date, timedelta

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ================== CONFIG ==================

R_SCRIPT = "/usr/local/bin/Rscript"  # <-- replace with your actual which Rscript

# Scope for read-only access to calendar
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Load configuration from environment variables
CALENDAR_ID = os.getenv("CALENDAR_ID")
if not CALENDAR_ID:
    raise ValueError("CALENDAR_ID environment variable is required")

# Where your R files live
R_WORKING_DIR = "/Users/markfisher/knitr_invoice_generator/"  # adjust path
WRAPPER_R = os.path.join(R_WORKING_DIR, "wrapper_for_knit.R")

# Email settings
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
FROM_EMAIL = os.getenv("FROM_EMAIL")
TO_EMAIL = os.getenv("TO_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# Validate required environment variables
if not FROM_EMAIL:
    raise ValueError("FROM_EMAIL environment variable is required")
if not TO_EMAIL:
    raise ValueError("TO_EMAIL environment variable is required")
if not GMAIL_APP_PASSWORD:
    raise ValueError("GMAIL_APP_PASSWORD environment variable is required")

# Google OAuth credentials from environment
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

if not GOOGLE_CLIENT_ID:
    raise ValueError("GOOGLE_CLIENT_ID environment variable is required")
if not GOOGLE_PROJECT_ID:
    raise ValueError("GOOGLE_PROJECT_ID environment variable is required")
if not GOOGLE_CLIENT_SECRET:
    raise ValueError("GOOGLE_CLIENT_SECRET environment variable is required")

# ==================================================


def get_credentials(credential_path="credentials.json", token_path="token.json"):
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Failed to refresh credentials: {e}")
                print("Re-authenticating...")
                creds = None  # Force re-authentication
        
        if not creds:
            # Create credentials configuration from environment variables
            client_config = {
                "installed": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "project_id": GOOGLE_PROJECT_ID,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uris": ["http://localhost"]
                }
            }
            
            # First-time auth flow using the dynamically created config
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    return creds


def month_bounds(year: int, month: int):
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def fetch_events_for_month(service, calendar_id: str, year: int, month: int):
    start_date, end_date = month_bounds(year, month)
    time_min = start_date.isoformat() + "T00:00:00Z"
    time_max = end_date.isoformat() + "T00:00:00Z"

    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    events = events_result.get("items", [])
    return events


def event_duration_hours(event) -> float:
    start = event["start"].get("dateTime") or (event["start"].get("date") + "T00:00:00Z")
    end = event["end"].get("dateTime") or (event["end"].get("date") + "T00:00:00Z")

    # Parse RFC3339 timestamps
    def parse_iso(dt_str):
        # Strip timezone if present and treat as naive UTC
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1]
        return datetime.fromisoformat(dt_str)

    start_dt = parse_iso(start)
    end_dt = parse_iso(end)
    delta = end_dt - start_dt
    return round(delta.total_seconds() / 3600.0, 2)


def event_date_string(event) -> str:
    # Use the start date for the invoice's Date_or_date_range column
    start_date = event["start"].get("date")
    if start_date:
        d = datetime.fromisoformat(start_date)
    else:
        start_dt = event["start"]["dateTime"]
        if start_dt.endswith("Z"):
            start_dt = start_dt[:-1]
        d = datetime.fromisoformat(start_dt)
    return d.strftime("%d %B, %Y")  # e.g. "17 September, 2019"


def build_csv_from_events(events, csv_path: str):
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date_or_date_range", "Hours_worked", "Comments"])
        for event in events:
            date_str = event_date_string(event)
            hours = event_duration_hours(event)
            summary = event.get("summary", "").strip()
            description = event.get("description", "").strip()

            # Combine summary + description as comments
            if summary and description:
                comments = f"{summary} — {description}"
            else:
                comments = summary or description or "Session"

            writer.writerow([date_str, f"{hours:.2f}", comments])


def run_r_invoice(csv_path: str, invoice_date: date, output_pdf: str):
    invoice_date_str = invoice_date.isoformat()
    cmd = [
        R_SCRIPT,
        WRAPPER_R,
        csv_path,
        invoice_date_str,
        output_pdf,
    ]
    subprocess.run(cmd, check=True, cwd=R_WORKING_DIR)


def send_email_with_attachment(pdf_path: str, subject: str, body: str):
    msg = EmailMessage()
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL
    msg["Subject"] = subject
    msg.set_content(body)

    with open(pdf_path, "rb") as f:
        data = f.read()

    filename = os.path.basename(pdf_path)
    msg.add_attachment(
        data,
        maintype="application",
        subtype="pdf",
        filename=filename,
    )

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(FROM_EMAIL, GMAIL_APP_PASSWORD)
        server.send_message(msg)


def main(year: int = None, month: int = None):
    today = date.today()
    if year is None or month is None:
        # default to current month
        year = today.year
        month = today.month

    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)

    events = fetch_events_for_month(service, CALENDAR_ID, year, month)
    if not events:
        print("No events found for that month.")
        return

    invoice_date = date(year, month, 1)
    month_name = invoice_date.strftime("%b").lower()
    csv_name = f"sbg_invoice_{invoice_date.day}_{month_name}_{invoice_date.year}.csv"
    pdf_name = f"sbg_invoice_{invoice_date.day}_{month_name}_{invoice_date.year}.pdf"

    csv_path = os.path.join(R_WORKING_DIR, csv_name)
    pdf_path = os.path.join(R_WORKING_DIR, pdf_name)

    build_csv_from_events(events, csv_path)
    run_r_invoice(csv_path, invoice_date, pdf_path)

    subject = f"SBG Invoice for {invoice_date.strftime('%B %Y')}"
    body = f"Attached is your SBG invoice for {invoice_date.strftime('%B %Y')}."
    send_email_with_attachment(pdf_path, subject, body)

    print(f"Generated and emailed invoice: {pdf_path}")


def parse_arguments():
    """Parse command line arguments for month and year."""
    parser = argparse.ArgumentParser(
        description="Generate and send invoice from Google Calendar events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_and_send_invoice.py                    # Current month
  python generate_and_send_invoice.py -m 10              # October of current year
  python generate_and_send_invoice.py -m 10 -y 2024      # October 2024
  python generate_and_send_invoice.py --month 12 --year 2023  # December 2023
        """
    )
    
    parser.add_argument(
        "-m", "--month",
        type=int,
        choices=range(1, 13),
        help="Month (1-12). Defaults to current month if not specified."
    )
    
    parser.add_argument(
        "-y", "--year",
        type=int,
        help="Year (e.g., 2024). Defaults to current year if not specified."
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    
    # Use provided arguments or default to current month/year
    today = date.today()
    year = args.year if args.year is not None else today.year
    month = args.month if args.month is not None else today.month
    
    print(f"Generating invoice for {date(year, month, 1).strftime('%B %Y')}")
    main(year, month)

