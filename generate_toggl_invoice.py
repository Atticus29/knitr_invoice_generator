#!/usr/bin/env python3

import argparse
import csv
import os
import subprocess
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, date

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ================== CONFIG ==================

R_SCRIPT = "/usr/local/bin/Rscript"  # <-- replace with your actual which Rscript

# Scopes are kept the same as generate_and_send_invoice.py so the existing
# token.json (already authorized for both scopes) can be reused without
# re-triggering the OAuth flow.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

# Where your R files live
R_WORKING_DIR = "/Users/markfisher/knitr_invoice_generator/"  # adjust path
WRAPPER_R = os.path.join(R_WORKING_DIR, "wrapper_for_knit.R")

# Email settings
FROM_EMAIL = os.getenv("FROM_EMAIL")
TO_EMAIL = os.getenv("TO_EMAIL")

# Google OAuth credentials from environment
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

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
            if not GOOGLE_CLIENT_ID:
                raise ValueError("GOOGLE_CLIENT_ID environment variable is required")
            if not GOOGLE_PROJECT_ID:
                raise ValueError("GOOGLE_PROJECT_ID environment variable is required")
            if not GOOGLE_CLIENT_SECRET:
                raise ValueError("GOOGLE_CLIENT_SECRET environment variable is required")

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


def parse_duration_to_hours(duration_str: str) -> float:
    """Convert a Toggl 'H:MM:SS' duration string to decimal hours."""
    hours, minutes, seconds = (int(part) for part in duration_str.split(":"))
    total_hours = hours + minutes / 60.0 + seconds / 3600.0
    return round(total_hours, 2)


def parse_toggl_date(date_str: str) -> date:
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def read_toggl_entries(toggl_csv_path: str):
    entries = []
    with open(toggl_csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(row)
    if not entries:
        raise ValueError(f"No entries found in {toggl_csv_path}")
    return entries


def build_csv_from_toggl_entries(entries, csv_path: str):
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date_or_date_range", "Hours_worked", "Comments"])
        for entry in entries:
            entry_date = parse_toggl_date(entry["Start date"])
            date_str = entry_date.strftime("%d %B, %Y")
            hours = parse_duration_to_hours(entry["Duration"])
            comments = entry.get("Description", "").strip() or "Session"
            writer.writerow([date_str, f"{hours:.2f}", comments])


def invoice_month_from_entries(entries) -> date:
    dates = [parse_toggl_date(entry["Start date"]) for entry in entries]
    earliest = min(dates)
    return date(earliest.year, earliest.month, 1)


def run_r_invoice(csv_path: str, invoice_date: date, output_pdf: str):
    invoice_date_str = invoice_date.isoformat()
    cmd = [
        R_SCRIPT,
        WRAPPER_R,
        csv_path,
        invoice_date_str,
        output_pdf,
        "UFI Software Development Services Invoice",
        "50",
        "Urban Forest Institute",
    ]
    subprocess.run(cmd, check=True, cwd=R_WORKING_DIR)


def send_email_with_attachment(creds, pdf_path: str, subject: str, body: str):
    if not FROM_EMAIL:
        raise ValueError("FROM_EMAIL environment variable is required")
    if not TO_EMAIL:
        raise ValueError("TO_EMAIL environment variable is required")

    msg = MIMEMultipart()
    msg["From"] = FROM_EMAIL
    msg["To"] = TO_EMAIL
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with open(pdf_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f'attachment; filename="{os.path.basename(pdf_path)}"',
    )
    msg.attach(part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    gmail_service = build("gmail", "v1", credentials=creds)
    gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()


def main(toggl_csv_path: str, send_email: bool = True):
    entries = read_toggl_entries(toggl_csv_path)
    invoice_date = invoice_month_from_entries(entries)
    month_name = invoice_date.strftime("%b").lower()
    csv_name = f"ufi_invoice_{invoice_date.day}_{month_name}_{invoice_date.year}.csv"
    pdf_name = f"ufi_invoice_{invoice_date.day}_{month_name}_{invoice_date.year}.pdf"

    csv_path = os.path.join(R_WORKING_DIR, csv_name)
    pdf_path = os.path.join(R_WORKING_DIR, pdf_name)

    build_csv_from_toggl_entries(entries, csv_path)
    run_r_invoice(csv_path, invoice_date, pdf_path)

    print(f"Generated invoice: {pdf_path}")

    if send_email:
        creds = get_credentials()
        subject = f"UFI Invoice for {invoice_date.strftime('%B %Y')}"
        body = f"Attached is your UFI invoice for {invoice_date.strftime('%B %Y')}."
        send_email_with_attachment(creds, pdf_path, subject, body)
        print("Emailed invoice.")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Generate (and optionally send) an invoice from a Toggl Track detailed CSV export",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_toggl_invoice.py toggl_export.csv
  python generate_toggl_invoice.py toggl_export.csv --no-email
        """
    )

    parser.add_argument(
        "toggl_csv",
        help="Path to the Toggl Track detailed report CSV export",
    )

    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Generate the invoice PDF but don't send it via email",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    main(args.toggl_csv, send_email=not args.no_email)
