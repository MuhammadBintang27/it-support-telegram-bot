import os
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_sheet = None


def _get_sheet():
    global _sheet
    if _sheet is None:
        creds = Credentials.from_service_account_file(
            os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"], scopes=SCOPES
        )
        client = gspread.authorize(creds)
        _sheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"]).sheet1
    return _sheet


def _next_ticket_id(sheet) -> str:
    today = datetime.now().strftime("%Y%m%d")
    existing_rows = len(sheet.get_all_values()) - 1  # minus header row
    return f"IT-{today}-{max(existing_rows, 0) + 1:03d}"


def append_ticket(ticket: dict) -> str:
    sheet = _get_sheet()
    ticket_id = _next_ticket_id(sheet)
    sheet.append_row([
        ticket_id,
        datetime.now().isoformat(timespec="seconds"),
        ticket["requester_name"],
        ticket["category"],
        ticket["priority"],
        ticket["description"],
        "Open",
        "",  # Assignee, filled in later via assign_ticket
    ])
    return ticket_id


STATUS_COLUMN = 7
ASSIGNEE_COLUMN = 8


def assign_ticket(ticket_id: str, assignee: str) -> bool:
    """Find the ticket's row by ID and set its status/assignee. Returns False if not found."""
    sheet = _get_sheet()
    cell = sheet.find(ticket_id, in_column=1)
    if cell is None:
        return False
    sheet.update_cell(cell.row, STATUS_COLUMN, "In Progress")
    sheet.update_cell(cell.row, ASSIGNEE_COLUMN, assignee)
    return True


def complete_ticket(ticket_id: str) -> bool:
    """Find the ticket's row by ID and mark it Selesai. Returns False if not found."""
    sheet = _get_sheet()
    cell = sheet.find(ticket_id, in_column=1)
    if cell is None:
        return False
    sheet.update_cell(cell.row, STATUS_COLUMN, "Selesai")
    return True
