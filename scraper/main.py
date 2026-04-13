"""
Real Estate Listing Scraper
============================
Extracts structured data from Israeli real-estate listing pages.

Usage:
    python -m scraper <url> [<url> ...]
    python -m scraper --file urls.txt
    python -m scraper <url> --sheet
    python -m scraper <url> --sheet-url "https://docs.google.com/spreadsheets/d/..."
    python -m scraper --upload output/listing.json --sheet
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from scraper.browser import get_browser, get_page
from scraper.export import export_csv, export_json, export_json_batch, json_to_csv
from scraper.models import Listing
from scraper.parsers import get_parser_for_url

console = Console()


def load_listings_from_json(path: str) -> list[Listing]:
    """Load listings from a previously saved JSON file."""
    file_path = Path(path)
    if not file_path.exists():
        console.print(f"[bold red]File not found: {path}[/]")
        sys.exit(1)

    raw = json.loads(file_path.read_text(encoding="utf-8"))

    if isinstance(raw, list):
        return [Listing.model_validate(item) for item in raw]
    if isinstance(raw, dict):
        return [Listing.model_validate(raw)]

    console.print(f"[bold red]Unexpected JSON format in {path}[/]")
    sys.exit(1)


async def scrape_url(url: str) -> Listing:
    """Scrape a single listing URL and return the parsed Listing."""
    parser = get_parser_for_url(url)
    console.print(f"[bold blue]⏳ Scraping[/] {url} [dim]({parser.source})[/]")

    async with get_browser() as browser:
        async with get_page(browser) as page:
            listing = await parser.parse(page, url)

    return listing


async def scrape_urls(urls: list[str]) -> list[Listing]:
    """Scrape multiple URLs sequentially."""
    listings: list[Listing] = []
    for url in urls:
        try:
            listing = await scrape_url(url)
            listings.append(listing)
            _print_listing(listing)
        except Exception as exc:
            console.print(f"[bold red]✗ Error scraping {url}:[/] {exc}")
    return listings


def _export_to_sheets(listings: list[Listing], sheet_url: str | None) -> None:
    from scraper.sheets import export_to_sheet

    console.print("\n[bold blue]⏳ Exporting to Google Sheets...[/]")
    try:
        url = export_to_sheet(listings, sheet_url=sheet_url)
        console.print(f"[bold green]✓ Google Sheet:[/] {url}")
    except FileNotFoundError as exc:
        console.print(f"[bold red]✗ {exc}[/]")
        sys.exit(1)
    except Exception as exc:
        console.print(f"[bold red]✗ Google Sheets error:[/] {exc}")
        sys.exit(1)


def _print_listing(listing: Listing) -> None:
    """Pretty-print a listing to the console."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="bold cyan", min_width=15)
    table.add_column("Value")

    fields = [
        ("מקור", listing.source),
        ("כתובת", listing.address),
        ("עיר", listing.city),
        ("שכונה", listing.neighborhood),
        ("מחיר", listing.price),
        ("חדרים", listing.rooms),
        ("שטח (מ\"ר)", listing.size_sqm),
        ("קומה", f"{listing.floor}/{listing.total_floors}" if listing.total_floors else listing.floor),
        ("סוג נכס", listing.property_type),
        ("תאריך כניסה", listing.entry_date),
    ]
    for label, value in fields:
        if value:
            table.add_row(label, str(value))

    booleans = [
        ("חניה", listing.has_parking),
        ("מעלית", listing.has_elevator),
        ("מרפסת", listing.has_balcony),
        ("ממ\"ד", listing.has_mamad),
        ("מיזוג", listing.has_air_conditioning),
        ("מרוהט", listing.is_furnished),
    ]
    active = [label for label, val in booleans if val]
    if active:
        table.add_row("מאפיינים", ", ".join(active))

    if listing.raw_features:
        table.add_row("תגיות נוספות", ", ".join(listing.raw_features[:10]))

    if listing.contacts:
        for c in listing.contacts:
            parts = []
            if c.name:
                parts.append(c.name)
            if c.phone:
                parts.append(c.phone)
            table.add_row("איש קשר", " | ".join(parts))

    table.add_row("תמונות", f"{len(listing.images)} תמונות")

    if listing.description:
        desc = listing.description[:200]
        if len(listing.description) > 200:
            desc += "..."
        table.add_row("תיאור", desc)

    console.print(Panel(table, title=f"[bold green]✓ {listing.address or listing.url}[/]", border_style="green"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Israeli real-estate listings (Yad2, Madlan)"
    )
    parser.add_argument("urls", nargs="*", help="One or more listing URLs")
    parser.add_argument(
        "--file", "-f", type=str, help="Text file with one URL per line"
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Output JSON file path (default: output/<address>.json)"
    )
    parser.add_argument(
        "--sheet", "-s", action="store_true",
        help="Export to Google Sheets (creates a new spreadsheet)"
    )
    parser.add_argument(
        "--sheet-url", type=str, default=None,
        help="Google Sheets URL to append rows to (implies --sheet)"
    )
    parser.add_argument(
        "--upload", "-u", type=str, default=None,
        help="Upload an existing JSON file to Google Sheets (no scraping)"
    )
    parser.add_argument(
        "--csv", action="store_true",
        help="Also export a CSV file (for manual Google Sheets import)"
    )
    parser.add_argument(
        "--to-csv", type=str, default=None,
        help="Convert an existing JSON file to CSV (no scraping). Example: --to-csv output/listing.json"
    )
    args = parser.parse_args()

    # --- Convert mode: JSON → CSV, no scraping ---
    if args.to_csv:
        csv_out = json_to_csv(args.to_csv)
        console.print(f"[bold green]✓ CSV saved to {csv_out}[/]")
        console.print("[dim]Import to Google Sheets: File → Import → Upload → select the CSV[/]")
        return

    # --- Upload mode: JSON → Google Sheets, no scraping ---
    if args.upload:
        listings = load_listings_from_json(args.upload)
        console.print(f"[bold blue]Loaded {len(listings)} listing(s) from {args.upload}[/]")
        for listing in listings:
            _print_listing(listing)
        _export_to_sheets(listings, sheet_url=args.sheet_url)
        return

    # --- Scrape mode ---
    urls: list[str] = list(args.urls or [])

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            console.print(f"[bold red]File not found: {args.file}[/]")
            sys.exit(1)
        urls.extend(
            line.strip()
            for line in file_path.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        )

    if not urls:
        console.print("[bold yellow]No URLs provided.[/] Use: python -m scraper <url>")
        parser.print_help()
        sys.exit(1)

    listings = asyncio.run(scrape_urls(urls))

    if not listings:
        console.print("[bold red]No listings were scraped successfully.[/]")
        sys.exit(1)

    # --- Google Sheets export ---
    use_sheets = args.sheet or args.sheet_url
    if use_sheets:
        _export_to_sheets(listings, sheet_url=args.sheet_url)

    # --- JSON export (always, as backup) ---
    if len(listings) == 1:
        out = export_json(listings[0], args.output)
    else:
        out = export_json_batch(listings, args.output or "output/listings.json")
    console.print(f"[bold green]✓ JSON saved to {out}[/]")

    # --- CSV export ---
    if args.csv:
        csv_out = export_csv(listings)
        console.print(f"[bold green]✓ CSV saved to {csv_out}[/]")
        console.print("[dim]Import to Google Sheets: File → Import → Upload → select the CSV[/]")


if __name__ == "__main__":
    main()
