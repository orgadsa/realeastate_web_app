"""
Google Sheets export for scraped listings.

Setup (one-time):
1. Go to https://console.cloud.google.com/apis/credentials
2. Create a Service Account → download the JSON key file
3. Save it as `credentials.json` in the project root (or set GOOGLE_CREDENTIALS_FILE env var)
4. Share your Google Sheet with the service account email (the one ending in @...iam.gserviceaccount.com)
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

from scraper.models import Listing

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADER_ROW = [
    "תאריך הוספה",
    "מקור",
    "כתובת",
    "עיר",
    "שכונה",
    "רחוב",
    "מחיר",
    "חדרים",
    "שטח (מ\"ר)",
    "קומה",
    "סה\"כ קומות",
    "סוג נכס",
    "תאריך כניסה",
    "חניה",
    "מעלית",
    "מרפסת",
    "ממ\"ד",
    "מיזוג",
    "מרוהט",
    "שם איש קשר",
    "טלפון",
    "תיאור",
    "מספר תמונות",
    "לינק תמונה ראשונה",
    "לינק למודעה",
]


def _get_credentials() -> Credentials:
    creds_path = os.environ.get(
        "GOOGLE_CREDENTIALS_FILE",
        str(Path(__file__).parent.parent / "credentials.json"),
    )
    if not Path(creds_path).exists():
        raise FileNotFoundError(
            f"Google credentials file not found at: {creds_path}\n"
            "Please create a service account and save the JSON key.\n"
            "See: https://console.cloud.google.com/apis/credentials"
        )
    return Credentials.from_service_account_file(creds_path, scopes=SCOPES)


def _get_client() -> gspread.Client:
    creds = _get_credentials()
    return gspread.authorize(creds)


def _listing_to_row(listing: Listing) -> list[str]:
    """Convert a Listing into a flat row of strings for the sheet."""
    contact_name = ""
    contact_phone = ""
    if listing.contacts:
        contact_name = listing.contacts[0].name or ""
        contact_phone = listing.contacts[0].phone or ""

    floor_str = listing.floor or ""
    total_floors_str = listing.total_floors or ""

    return [
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        listing.source or "",
        listing.address or "",
        listing.city or "",
        listing.neighborhood or "",
        listing.street or "",
        listing.price or "",
        listing.rooms or "",
        listing.size_sqm or "",
        floor_str,
        total_floors_str,
        listing.property_type or "",
        listing.entry_date or "",
        "V" if listing.has_parking else "",
        "V" if listing.has_elevator else "",
        "V" if listing.has_balcony else "",
        "V" if listing.has_mamad else "",
        "V" if listing.has_air_conditioning else "",
        "V" if listing.is_furnished else "",
        contact_name,
        contact_phone,
        (listing.description or "")[:500],
        str(len(listing.images)),
        listing.images[0] if listing.images else "",
        listing.url,
    ]


def export_to_sheet(
    listings: list[Listing],
    sheet_url: str | None = None,
    sheet_name: str | None = None,
) -> str:
    """
    Append listings to a Google Sheet.

    If *sheet_url* is given, opens that sheet and appends rows.
    Otherwise creates a new spreadsheet named *sheet_name*
    (default: "נדלן - מודעות").

    Returns the URL of the spreadsheet.
    """
    client = _get_client()

    if sheet_url:
        spreadsheet = client.open_by_url(sheet_url)
    else:
        title = sheet_name or "נדלן - מודעות"
        spreadsheet = client.create(title)

    try:
        worksheet = spreadsheet.worksheet("מודעות")
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.sheet1
        worksheet.update_title("מודעות")

    existing = worksheet.get_all_values()
    if not existing:
        worksheet.append_row(HEADER_ROW, value_input_option="USER_ENTERED")
        _apply_header_format(worksheet)

    rows = [_listing_to_row(listing) for listing in listings]
    worksheet.append_rows(rows, value_input_option="USER_ENTERED")

    return spreadsheet.url


def _apply_header_format(worksheet) -> None:
    """Bold + freeze the header row."""
    try:
        worksheet.format("1:1", {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.9, "green": 0.93, "blue": 1.0},
        })
        worksheet.freeze(rows=1)

        worksheet.update_sheet_properties(
            worksheet.id,
            {"sheetProperties": {"rightToLeft": True}},
        )
    except Exception:
        pass
