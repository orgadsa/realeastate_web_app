from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from scraper.models import Listing

CSV_HEADERS = [
    "מקור", "כתובת", "עיר", "שכונה", "רחוב", "מחיר",
    "חדרים", "שטח (מ\"ר)", "קומה", "סה\"כ קומות", "סוג נכס", "תאריך כניסה",
    "חניה", "מעלית", "מרפסת", "ממ\"ד", "מיזוג", "מרוהט",
    "שם איש קשר", "טלפון", "תיאור", "מספר תמונות", "לינק למודעה",
]


def export_json(listing: Listing, path: str | Path | None = None) -> str:
    """Export a listing to a JSON file. Returns the path written to."""
    data = listing.model_dump(exclude_none=True)
    content = json.dumps(data, ensure_ascii=False, indent=2)

    if path is None:
        safe_name = (
            listing.address or listing.url.split("/")[-1] or "listing"
        )
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in safe_name)
        safe_name = safe_name.strip()[:80]
        path = Path("output") / f"{safe_name}.json"

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def export_json_batch(listings: list[Listing], path: str | Path = "output/listings.json") -> str:
    """Export multiple listings into a single JSON file."""
    data = [l.model_dump(exclude_none=True) for l in listings]
    content = json.dumps(data, ensure_ascii=False, indent=2)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def _listing_to_csv_row(listing: Listing) -> list[str]:
    contact_name = ""
    contact_phone = ""
    if listing.contacts:
        contact_name = listing.contacts[0].name or ""
        contact_phone = listing.contacts[0].phone or ""

    return [
        listing.source or "",
        listing.address or "",
        listing.city or "",
        listing.neighborhood or "",
        listing.street or "",
        listing.price or "",
        listing.rooms or "",
        listing.size_sqm or "",
        listing.floor or "",
        listing.total_floors or "",
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
        listing.url,
    ]


def export_csv(listings: list[Listing], path: str | Path | None = None) -> str:
    """Export listings to a CSV file ready for Google Sheets import."""
    if path is None:
        path = Path("output") / "listings.csv"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # BOM for Excel/Sheets to detect UTF-8 correctly
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)
        for listing in listings:
            writer.writerow(_listing_to_csv_row(listing))

    return str(path)


def json_to_csv(json_path: str, csv_path: str | None = None) -> str:
    """Convert a previously saved JSON file to CSV."""
    raw = json.loads(Path(json_path).read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = [raw]
    listings = [Listing.model_validate(item) for item in raw]
    return export_csv(listings, csv_path)
