#!/usr/bin/env python3

from invoice_generator import run_from_command_line


if __name__ == "__main__":
    run_from_command_line(
        calendar_env_var="CALENDAR_ID",
        location="Vancouver",
        file_prefix="sbg_vancouver_invoice",
        script_name="generate_and_send_invoice_vancouver.py",
    )
