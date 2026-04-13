from __future__ import annotations

import json
import re
from urllib.parse import urlparse, urlunparse

from playwright.async_api import Page

from scraper.models import Contact, Listing
from scraper.parsers.base import BaseParser

FEATURES_MAP = {
    "מיזוג אויר": "has_air_conditioning",
    "מיזוג אוויר": "has_air_conditioning",
    "מרפסת": "has_balcony",
    "מעלית": "has_elevator",
    "חניה": "has_parking",
    "חנייה": "has_parking",
    "ממ\"ד": "has_mamad",
    "ממ״ד": "has_mamad",
    "ממד": "has_mamad",
    "מרוהטת": "is_furnished",
    "ריהוט": "is_furnished",
}

PHONE_RE = re.compile(
    r"(?:0[2-9][0-9][-–\s]?[0-9]{7}|05[0-9][-–\s]?[0-9]{7}|"
    r"0[2-9][-–\s]?[0-9]{3}[-–\s]?[0-9]{4}|"
    r"05[0-9][-–\s]?[0-9]{3}[-–\s]?[0-9]{4})"
)


class Yad2Parser(BaseParser):
    source = "yad2"

    async def parse(self, page: Page, url: str) -> Listing:
        from scraper.browser import load_page

        await load_page(page, url, wait_selector="[class*='listing']")

        listing = Listing(url=url, source=self.source)

        listing = await self._try_extract_from_json(page, listing)
        listing = await self._extract_from_dom(page, listing)
        listing.images = await self._extract_images(page)
        listing.contacts = await self._extract_contacts(page, listing)

        # Deduplicate features
        listing.raw_features = list(dict.fromkeys(listing.raw_features))

        return listing

    async def _try_extract_from_json(self, page: Page, listing: Listing) -> Listing:
        """Yad2 often embeds listing data as JSON inside script tags or __NEXT_DATA__."""
        try:
            next_data = await page.evaluate(
                "() => window.__NEXT_DATA__ && JSON.stringify(window.__NEXT_DATA__)"
            )
            if next_data:
                data = json.loads(next_data)
                listing = self._parse_next_data(data, listing)
                return listing
        except Exception:
            pass

        try:
            scripts = await page.query_selector_all('script[type="application/ld+json"]')
            for script in scripts:
                text = await script.text_content()
                if not text:
                    continue
                data = json.loads(text)
                if isinstance(data, dict) and data.get("@type") in (
                    "Product",
                    "RealEstateListing",
                    "Residence",
                    "Apartment",
                ):
                    if "name" in data:
                        listing.address = listing.address or data["name"]
                    if "description" in data:
                        listing.description = listing.description or data["description"]
                    offers = data.get("offers", {})
                    if isinstance(offers, dict) and "price" in offers:
                        listing.price = listing.price or str(offers["price"])
                    images = data.get("image", [])
                    if isinstance(images, list):
                        listing.images = images
        except Exception:
            pass

        return listing

    def _parse_next_data(self, data: dict, listing: Listing) -> Listing:
        """Walk the __NEXT_DATA__ structure to find listing details."""
        try:
            props = data.get("props", {}).get("pageProps", {})
            item = (
                props.get("item")
                or props.get("listing")
                or props.get("feedItem")
                or props.get("data")
                or {}
            )
            if not item:
                for v in props.values():
                    if isinstance(v, dict) and ("price" in v or "address" in v or "rooms" in v):
                        item = v
                        break

            if not item:
                return listing

            listing.price = listing.price or _str(
                item.get("price") or item.get("Price")
            )
            listing.rooms = listing.rooms or _str(
                item.get("rooms") or item.get("Rooms") or item.get("rooms_text")
            )
            listing.size_sqm = listing.size_sqm or _str(
                item.get("square_meters")
                or item.get("SquareMeter")
                or item.get("squaremeter")
                or item.get("size")
            )
            listing.floor = listing.floor or _str(
                item.get("floor") or item.get("Floor")
            )
            listing.total_floors = listing.total_floors or _str(
                item.get("TotalFloor_text") or item.get("total_floor")
            )
            listing.description = listing.description or _str(
                item.get("info_text")
                or item.get("description")
                or item.get("Description")
            )
            listing.property_type = listing.property_type or _str(
                item.get("property_type")
                or item.get("PropertyType")
                or item.get("catId_text")
            )
            listing.entry_date = listing.entry_date or _str(
                item.get("date_of_entry") or item.get("DateOfEntry")
            )

            addr = item.get("address_home", {}) or item.get("address", {})
            if isinstance(addr, dict):
                listing.city = listing.city or _str(
                    addr.get("city", {}).get("text")
                    if isinstance(addr.get("city"), dict)
                    else addr.get("city")
                )
                listing.street = listing.street or _str(
                    addr.get("street", {}).get("text")
                    if isinstance(addr.get("street"), dict)
                    else addr.get("street")
                )
                listing.neighborhood = listing.neighborhood or _str(
                    addr.get("neighborhood", {}).get("text")
                    if isinstance(addr.get("neighborhood"), dict)
                    else addr.get("neighborhood")
                )
                house_num = _str(
                    addr.get("house", {}).get("number")
                    if isinstance(addr.get("house"), dict)
                    else addr.get("house_number")
                )
                if listing.street and house_num:
                    listing.address = f"{listing.street} {house_num}, {listing.city or ''}"
                elif listing.street:
                    listing.address = f"{listing.street}, {listing.city or ''}"
            elif isinstance(addr, str):
                listing.address = addr

            if not listing.address:
                listing.address = _str(
                    item.get("title") or item.get("Title") or item.get("address_text")
                )

            images = item.get("images") or item.get("Images") or []
            if isinstance(images, list) and images:
                listing.images = [
                    img.get("src") or img.get("url") or img
                    for img in images
                    if isinstance(img, (dict, str))
                ]

            contact_name = _str(
                item.get("contact_name") or item.get("ContactName")
            )
            contact_phone = _str(
                item.get("contact_phone") or item.get("ContactPhone")
            )
            if contact_name or contact_phone:
                listing.contacts.append(
                    Contact(name=contact_name, phone=contact_phone)
                )

        except Exception:
            pass
        return listing

    async def _extract_from_dom(self, page: Page, listing: Listing) -> Listing:
        """Extract / fill missing fields from the visible page DOM."""

        if not listing.price:
            listing.price = await _text(page, [
                "[data-testid='price']",
                "[class*='price']",
                "[class*='Price']",
                ".price",
            ])

        if not listing.rooms:
            listing.rooms = await _text(page, [
                "[data-testid='rooms']",
                "[class*='rooms']",
            ])

        if not listing.size_sqm:
            listing.size_sqm = await _text(page, [
                "[data-testid='squaremeter']",
                "[data-testid='square-meter']",
                "[class*='squaremeter']",
                "[class*='square_meter']",
            ])

        if not listing.floor:
            listing.floor = await _text(page, [
                "[data-testid='floor']",
                "[class*='floor']",
            ])

        if not listing.address:
            listing.address = await _text(page, [
                "[data-testid='address']",
                "[class*='address']",
                "[class*='Address']",
                "h1",
                "[class*='title']",
            ])

        if not listing.description:
            listing.description = await _text(page, [
                "[data-testid='description']",
                "[class*='description']",
                "[class*='Description']",
                "[class*='info_text']",
            ])

        # Try extracting key stats from row-based layout common in Yad2
        if not listing.rooms or not listing.size_sqm or not listing.floor:
            listing = await self._extract_key_stats(page, listing)

        # Features / amenities
        feature_elements = await page.query_selector_all(
            "[class*='ameniti'], [class*='feature'], [class*='tag'], "
            "[data-testid*='amenit'], [data-testid*='feature']"
        )
        for el in feature_elements:
            txt = ((await el.text_content()) or "").strip()
            if txt:
                listing.raw_features.append(txt)
                for keyword, attr in FEATURES_MAP.items():
                    if keyword in txt:
                        setattr(listing, attr, True)

        return listing

    async def _extract_key_stats(self, page: Page, listing: Listing) -> Listing:
        """Try to find rooms/size/floor from stat rows or key-value pairs on the page."""
        pairs = await page.evaluate("""() => {
            const results = [];
            // Look for dt/dd pairs, label/value pairs, or rows with key-value structure
            const allElements = document.querySelectorAll(
                '[class*="detail"], [class*="Detail"], [class*="info"], [class*="spec"], '
                + '[class*="param"], [class*="Param"], [class*="stat"], [class*="Stat"], '
                + '[class*="key-val"], [class*="data-row"]'
            );
            for (const el of allElements) {
                const text = el.textContent.trim();
                if (text.length < 100) {
                    results.push(text);
                }
            }
            return results;
        }""")

        for text in (pairs or []):
            text_lower = text.strip()
            if not listing.rooms and re.search(r"חדרים?\s*:?\s*([\d.]+)", text_lower):
                m = re.search(r"חדרים?\s*:?\s*([\d.]+)", text_lower)
                listing.rooms = m.group(1)
            if not listing.size_sqm and re.search(r"(?:מ\"ר|שטח|מטר)\s*:?\s*(\d+)", text_lower):
                m = re.search(r"(?:מ\"ר|שטח|מטר)\s*:?\s*(\d+)", text_lower)
                listing.size_sqm = m.group(1)
            if not listing.floor and re.search(r"קומה\s*:?\s*(\d+)", text_lower):
                m = re.search(r"קומה\s*:?\s*(\d+)", text_lower)
                listing.floor = m.group(1)

        return listing

    async def _extract_images(self, page: Page) -> list[str]:
        """Collect all listing image URLs from the gallery."""
        images: list[str] = []

        img_elements = await page.query_selector_all(
            "[class*='gallery'] img, [class*='Gallery'] img, "
            "[class*='carousel'] img, [class*='slider'] img, "
            "[class*='image-gallery'] img, [data-testid*='image'] img, "
            "[class*='lightbox'] img, picture img"
        )
        for img in img_elements:
            src = await img.get_attribute("src")
            if not src:
                src = await img.get_attribute("data-src")
            if src and src.startswith("http") and _is_listing_image(src):
                images.append(src)

        bg_elements = await page.query_selector_all(
            "[class*='gallery'] [style*='background-image'], "
            "[class*='carousel'] [style*='background-image']"
        )
        for el in bg_elements:
            style = await el.get_attribute("style") or ""
            match = re.search(r'url\(["\']?(https?://[^"\')\s]+)', style)
            if match and _is_listing_image(match.group(1)):
                images.append(match.group(1))

        return _dedupe_images(images)

    async def _extract_contacts(self, page: Page, listing: Listing) -> list[Contact]:
        contacts: list[Contact] = []

        # Try clicking "show phone number" button
        show_phone_btns = await page.query_selector_all(
            "button[class*='phone'], button[class*='Phone'], "
            "[data-testid*='phone'], [class*='show-phone'], "
            "button[class*='contact']"
        )
        for btn in show_phone_btns:
            try:
                await btn.click()
                await page.wait_for_timeout(1500)
                break
            except Exception:
                continue

        phone = await _text(page, [
            "a[href^='tel:']",
            "[data-testid*='phone'] a",
            "[data-testid*='phone']",
            "[class*='phone'] a",
            "[class*='phone-number']",
        ])

        # Validate that "phone" is actually a phone number
        if phone and not PHONE_RE.search(phone.replace("-", "").replace(" ", "")):
            phone = None

        name = await _text(page, [
            "[data-testid*='contact-name']",
            "[class*='contact-name']",
            "[class*='seller-name']",
            "[class*='ContactName']",
        ])

        # tel: link fallback
        if not phone:
            tel_links = await page.query_selector_all("a[href^='tel:']")
            for link in tel_links:
                href = await link.get_attribute("href") or ""
                number = href.replace("tel:", "").strip()
                if number and len(number) >= 9:
                    phone = number
                    break

        # Extract phone from description as last resort
        if not phone and listing.description:
            desc_clean = listing.description.replace("מספר", " ").replace("פלאפון", " ")
            m = PHONE_RE.search(desc_clean)
            if m:
                phone = m.group(0).replace(" ", "").replace("–", "-")

        if phone or name:
            contacts.append(Contact(name=name, phone=phone))

        return contacts


def _is_listing_image(url: str) -> bool:
    """Filter out tiny icons, logos, and tracking pixels."""
    skip_patterns = ["logo", "icon", "avatar", "pixel", "tracking", "1x1", "svg", "play.png"]
    url_lower = url.lower()
    return not any(p in url_lower for p in skip_patterns)


def _normalize_image_url(url: str) -> str:
    """Strip query params for deduplication comparison."""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query=""))


def _dedupe_images(images: list[str]) -> list[str]:
    """Deduplicate images, preferring higher-resolution versions."""
    seen_bases: dict[str, str] = {}
    for img in images:
        base = _normalize_image_url(img)
        if base not in seen_bases:
            seen_bases[base] = img
        else:
            existing = seen_bases[base]
            if len(img) > len(existing):
                seen_bases[base] = img
    return list(seen_bases.values())


def _str(val) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


async def _text(page: Page, selectors: list[str]) -> str | None:
    """Return the text content of the first matching selector, or None."""
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el:
                text = ((await el.text_content()) or "").strip()
                if text:
                    return text
        except Exception:
            continue
    return None
