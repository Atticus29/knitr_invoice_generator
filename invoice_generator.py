#!/usr/bin/env python3

import argparse
import base64
import csv
import os
import subprocess
from datetime import date, datetime
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

R_SCRIPT = "/usr/local/bin/Rscript"
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]
R_WORKING_DIR = "/Users/markfisher/knitr_invoice_generator/"
WRAPPER_R = os.path.join(R_WORKING_DIR, "wrapper_for_knit.R")

FROM_EMAIL = os.getenv("FROM_EMAIL")
TO_EMAIL = os.getenv("TO_EMAIL")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

if not FROM_EMAIL:
    raise ValueError("FROM_EMAIL environment variable is required")
if not TO_EMAIL:
    raise ValueError("TO_EMAIL environment variable is required")
if not GOOGLE_CLIENT_ID:
    raise ValueError("GOOGLE_CLIENT_ID environment variable is required")
if not GOOGLE_PROJECT_ID:
    raise ValueError("GOOGLE_PROJECT_ID environment variable is required")
if not GOOGLE_CLIENT_SECRET:
    raise ValueError("GOOGLE_CLIENT_SECRET environment variable is required")


def get_credentials(credential_path="credentials.json", token_path="token.json"):
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as error:
                print(f"Failed to refresh credentials: {error}")
                print("Re-authenticating...")
                creds = None

        if not creds:
            client_config = {
                "installed": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "project_id": GOOGLE_PROJECT_ID,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uris": ["http://localhost"],
                }
            }
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as token:
            token.write(creds.to_json())
    return creds


def month_bounds(year: int, month: int):
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


def fetch_events_for_month(service, calendar_id: str, year: int, month: int):
    start_date, end_date = month_bounds(year, month)
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_date.isoformat() + "T00:00:00Z",
        timeMax=end_date.isoformat() + "T00:00:00Z",
        singleEvents=True,
        orderBy="startTime",
    ).execute()
    return events_result.get("items", [])


def event_duration_hours(event) -> float:
    start = event["start"].get("dateTime") or (event["start"].get("date") + "T00:00:00Z")
    end = event["end"].get("dateTime") or (event["end"].get("date") + "T00:00:00Z")

    def parse_iso(timestamp):
        if timestamp.endswith("Z"):
            timestamp = timestamp[:-1]
        return datetime.fromisoformat(timestamp)

    return round((parse_iso(end) - parse_iso(start)).total_seconds() / 3600.0, 2)


def event_date_string(event) -> str:
    start_date = event["start"].get("date")
    if start_date:
        event_date = datetime.fromisoformat(start_date)
    else:
        timestamp = event["start"]["dateTime"]
        if timestamp.endswith("Z"):
            timestamp = timestamp[:-1]
        event_date = datetime.fromisoformat(timestamp)
    return event_date.strftime("%d %B, %Y")


def build_csv_from_events(events, csv_path: str):
    with open(csv_path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Date_or_date_range", "Hours_worked", "Comments"])
        for event in events:
            summary = event.get("summary", "").strip()
            description = event.get("description", "").strip()
            if summary and description:
                comments = f"{summary} — {description}"
            else:
                comments = summary or description or "Session"
            writer.writerow([
                event_date_string(event),
                f"{event_duration_hours(event):.2f}",
                comments,
            ])


def run_r_invoice(csv_path: str, invoice_date: date, output_pdf: str, location: str):
    command = [
        R_SCRIPT,
        WRAPPER_R,
        csv_path,
        invoice_date.isoformat(),
        output_pdf,
        "BJJ Instruction Services Invoice",
        "21",
        f"Straight Blast Gym {location}",
        invoice_date.isoformat(),
        "Brazilian Jiu Jitsu Instruction",
    ]
    subprocess.run(command, check=True, cwd=R_WORKING_DIR)


def send_email_with_attachment(creds, pdf_path: str, subject: str, body: str):
    message = MIMEMultipart()
    message["From"] = FROM_EMAIL
    message["To"] = TO_EMAIL
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    with open(pdf_path, "rb") as file:
        attachment = MIMEBase("application", "octet-stream")
        attachment.set_payload(file.read())
    encoders.encode_base64(attachment)
    attachment.add_header(
        "Content-Disposition",
        f'attachment; filename="{os.path.basename(pdf_path)}"',
    )
    message.attach(attachment)

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    gmail_service = build("gmail", "v1", credentials=creds)
    gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()


def generate_invoice(calendar_env_var: str, location: str, file_prefix: str, year: int, month: int):
    calendar_id = os.getenv(calendar_env_var)
    if not calendar_id:
        raise ValueError(f"{calendar_env_var} environment variable is required")

    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)
    events = fetch_events_for_month(service, calendar_id, year, month)
    if not events:
        print("No events found for that month.")
        return

    invoice_date = date(year, month, 1)
    month_name = invoice_date.strftime("%b").lower()
    csv_name = f"{file_prefix}_{invoice_date.day}_{month_name}_{invoice_date.year}.csv"
    pdf_name = f"{file_prefix}_{invoice_date.day}_{month_name}_{invoice_date.year}.pdf"
    csv_path = os.path.join(R_WORKING_DIR, csv_name)
    pdf_path = os.path.join(R_WORKING_DIR, pdf_name)

    build_csv_from_events(events, csv_path)
    run_r_invoice(csv_path, invoice_date, pdf_path, location)

    subject = f"SBG Invoice for {invoice_date.strftime('%B %Y')}"
    body = f"Attached is your SBG invoice for {invoice_date.strftime('%B %Y')}."
    send_email_with_attachment(creds, pdf_path, subject, body)
    print(f"Generated and emailed invoice: {pdf_path}")


def parse_arguments(script_name: str):
    parser = argparse.ArgumentParser(
        description="Generate and send invoice from Google Calendar events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  python {script_name}                    # Current month
  python {script_name} -m 10              # October of current year
  python {script_name} -m 10 -y 2024      # October 2024
  python {script_name} --month 12 --year 2023  # December 2023
        """,
    )
    parser.add_argument(
        "-m", "--month",
        type=int,
        choices=range(1, 13),
        help="Month (1-12). Defaults to current month if not specified.",
    )
    parser.add_argument(
        "-y", "--year",
        type=int,
        help="Year (e.g., 2024). Defaults to current year if not specified.",
    )
    return parser.parse_args()


def run_from_command_line(calendar_env_var: str, location: str, file_prefix: str, script_name: str):
    args = parse_arguments(script_name)
    today = date.today()
    year = args.year if args.year is not None else today.year
    month = args.month if args.month is not None else today.month
    print(f"Generating invoice for {date(year, month, 1).strftime('%B %Y')}")
    generate_invoice(calendar_env_var, location, file_prefix, year, month)
