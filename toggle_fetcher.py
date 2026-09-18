#!/usr/bin/env python3
"""Download a detailed time entries report from Toggl Track as a CSV file."""

import argparse
import base64
import os
from calendar import monthrange
from datetime import date

import requests
from dotenv import load_dotenv

load_dotenv()

# ================== CONFIG ==================

TOGGL_API_TOKEN = os.getenv("TOGGL_API_TOKEN")
TOGGL_WORKSPACE_ID = os.getenv("TOGGL_WORKSPACE_ID")

REPORTS_API_URL = "https://api.track.toggl.com/reports/api/v3/workspace/{workspace_id}/search/time_entries.csv"

OUTPUT_DIR = "/Users/markfisher/knitr_invoice_generator/"

# ==================================================


def default_date_range() -> tuple[date, date]:
    """Return the start and end date of the current month."""
    today = date.today()
    start = date(today.year, today.month, 1)
    end = date(today.year, today.month, monthrange(today.year, today.month)[1])
    return start, end


def fetch_toggl_csv(start_date: date, end_date: date) -> bytes:
    if not TOGGL_API_TOKEN:
        raise ValueError("TOGGL_API_TOKEN environment variable is required")
    if not TOGGL_WORKSPACE_ID:
        raise ValueError("TOGGL_WORKSPACE_ID environment variable is required")

    auth_token = base64.b64encode(f"{TOGGL_API_TOKEN}:api_token".encode()).decode()
    url = REPORTS_API_URL.format(workspace_id=TOGGL_WORKSPACE_ID)
    payload = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
    response = requests.post(
        url,
        json=payload,
        headers={
            "Authorization": f"Basic {auth_token}",
            "Content-Type": "application/json",
        },
    )
    response.raise_for_status()
    return response.content


def save_toggl_csv(start_date: date, end_date: date, output_dir: str = OUTPUT_DIR) -> str:
    csv_bytes = fetch_toggl_csv(start_date, end_date)
    month_name = start_date.strftime("%b").lower()
    csv_name = f"toggl_export_{start_date.day}_{month_name}_{start_date.year}.csv"
    csv_path = os.path.join(output_dir, csv_name)
    with open(csv_path, "wb") as f:
        f.write(csv_bytes)
    return csv_path


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Download a detailed Toggl Track time entries report as a CSV file"
    )
    parser.add_argument("--start", help="Start date (YYYY-MM-DD), defaults to start of current month")
    parser.add_argument("--end", help="End date (YYYY-MM-DD), defaults to end of current month")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    if args.start and args.end:
        range_start = date.fromisoformat(args.start)
        range_end = date.fromisoformat(args.end)
    else:
        range_start, range_end = default_date_range()

    # Path to the downloaded Toggl CSV export
    toggl_csv_path = save_toggl_csv(range_start, range_end)

    print(f"Saved Toggl export to: {toggl_csv_path}")
