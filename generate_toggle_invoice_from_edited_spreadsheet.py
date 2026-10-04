#!/usr/bin/env python3
"""Generate (and optionally send) an invoice from an already-processed spreadsheet.

Expected columns: Date_or_date_range, Hours_worked, Project, Comments.
Hours are used as-is; no Toggl duration calculations are performed.
"""

import argparse
import csv
import os
from datetime import datetime, date

from generate_toggl_invoice import (
    DEFAULT_PROJECT,
    R_WORKING_DIR,
    get_credentials,
    parse_service_period,
    run_r_invoice,
    send_email_with_attachment,
)

DATE_FORMAT = "%d %B, %Y"


def read_spreadsheet_entries(csv_path: str, project: str | None = None):
    entries = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if project is None or row.get("Project", "").strip() == project:
                entries.append(row)
    if not entries:
        if project is None:
            raise ValueError(f"No entries found in {csv_path}")
        raise ValueError(f"No entries for project {project!r} found in {csv_path}")
    return entries


def parse_entry_date(entry) -> date:
    return datetime.strptime(entry["Date_or_date_range"].strip(), DATE_FORMAT).date()


def build_invoice_csv(entries, csv_path: str):
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Date_or_date_range", "Hours_worked", "Comments"])
        for entry in entries:
            hours = float(entry["Hours_worked"])
            comments = entry.get("Comments", "").strip() or "Session"
            writer.writerow([entry["Date_or_date_range"].strip(), f"{hours:.2f}", comments])


def invoice_month_from_entries(entries) -> date:
    earliest = min(parse_entry_date(entry) for entry in entries)
    return date(earliest.year, earliest.month, 1)


def main(
    spreadsheet_csv_path: str,
    send_email: bool = True,
    project: str | None = DEFAULT_PROJECT,
    service_period: date | None = None,
):
    entries = read_spreadsheet_entries(spreadsheet_csv_path, project=project)
    invoice_date = invoice_month_from_entries(entries)
    month_name = invoice_date.strftime("%b").lower()
    base_name = f"ufi_invoice_{invoice_date.day}_{month_name}_{invoice_date.year}"

    csv_path = os.path.join(R_WORKING_DIR, f"{base_name}.csv")
    pdf_path = os.path.join(R_WORKING_DIR, f"{base_name}.pdf")

    build_invoice_csv(entries, csv_path)
    run_r_invoice(csv_path, invoice_date, pdf_path, service_period=service_period)

    print(f"Generated invoice: {pdf_path}")

    if send_email:
        creds = get_credentials()
        subject = f"UFI Invoice for {invoice_date.strftime('%B %Y')}"
        body = f"Attached is your UFI invoice for {invoice_date.strftime('%B %Y')}."
        send_email_with_attachment(creds, pdf_path, subject, body)
        print("Emailed invoice.")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Generate (and optionally send) an invoice from an edited spreadsheet CSV whose hours are already calculated",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_toggle_invoice_from_edited_spreadsheet.py ufi_invoice_1_sep_2026_amended_processed.csv
  python generate_toggle_invoice_from_edited_spreadsheet.py ufi_invoice_1_sep_2026_amended_processed.csv --no-email
  python generate_toggle_invoice_from_edited_spreadsheet.py ufi_invoice_1_sep_2026_amended_processed.csv --service-period 2026-09
        """,
    )
    parser.add_argument("spreadsheet_csv", help="Path to the edited spreadsheet CSV")
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Generate the invoice PDF but don't send it via email",
    )
    parser.add_argument(
        "--project",
        default=DEFAULT_PROJECT,
        help=f"Only include rows whose Project exactly matches this value (default: {DEFAULT_PROJECT})",
    )
    parser.add_argument(
        "--service-period",
        type=parse_service_period,
        metavar="YYYY-MM",
        help="Month shown in the PDF Service Period section (defaults to the current month)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    main(
        args.spreadsheet_csv,
        send_email=not args.no_email,
        project=args.project,
        service_period=args.service_period,
    )
