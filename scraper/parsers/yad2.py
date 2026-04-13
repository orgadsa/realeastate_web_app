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
    r"0[2-9]\d[-–\s]?\d{7}|05\d[-–\s]?\d{7}|"
    r"0[2-9][-–\s]?\d{3}[-–\s]?\d{4}|"
    r"05\d[-–\s]?\d{3}[-–\s]?\d{4}"
)


class Yad2Parser(BaseParser):
    source = "yad2"

    async def parse(self, page: Page, url: str) -> Listing:
        from scraper.browser import load_page

        await load_page(page, url, wait_selector="[class*='listing']")

        body_text = await page.evaluate("() => document.body.innerText.substring(0, 500)")
        if "אין לנו עמוד כזה" in body_text or "העמוד שחיפשת הוסר" in body_text:
            raise ValueError("המודעה הוסרה או שהלינק לא תקין")

        listing = Listing(url=url, source=self.source)

        listing = await self._try_extract_from_json(page, listing)
        listing = await self._smart_extract(page, listing)
        listing.images = await self._extract_images(page)
        listing.contacts = await self._extract_contacts(page, listing)

        listing.raw_features = list(dict.fromkeys(listing.raw_features))

        return listing

    async def _try_extract_from_json(self, page: Page, listing: Listing) -> Listing:
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
                    "Product", "RealEstateListing", "Residence", "Apartment",
                ):
                    if "name" in data:
                        listing.address = listing.address or data["name"]
                    if "description" in data:
                        listing.description = listing.description or data["description"]
                    offers = data.get("offers", {})
                    if isinstance(offers, dict) and "price" in offers:
                        listing.price = listing.price or str(offers["price"])
        except Exception:
            pass

        return listing

    def _parse_next_data(self, data: dict, listing: Listing) -> Listing:
        try:
            props = data.get("props", {}).get("pageProps", {})

            # Deep-walk to find the listing object
            item = self._find_listing_object(props)
            if not item:
                return listing

            listing.price = listing.price or _str(
                item.get("price") or item.get("Price")
            )
            listing.rooms = listing.rooms or _str(
                item.get("rooms") or item.get("Rooms") or item.get("rooms_text")
            )
            listing.size_sqm = listing.size_sqm or _str(
                item.get("square_meters") or item.get("SquareMeter")
                or item.get("squaremeter") or item.get("size")
            )
            listing.floor = listing.floor or _str(
                item.get("floor") or item.get("Floor")
            )
            listing.total_floors = listing.total_floors or _str(
                item.get("TotalFloor_text") or item.get("total_floor")
            )
            listing.description = listing.description or _str(
                item.get("info_text") or item.get("description") or item.get("Description")
            )
            listing.property_type = listing.property_type or _str(
                item.get("property_type") or item.get("PropertyType") or item.get("catId_text")
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
                    for img in images if isinstance(img, (dict, str))
                ]

            contact_name = _str(item.get("contact_name") or item.get("ContactName"))
            contact_phone = _str(item.get("contact_phone") or item.get("ContactPhone"))
            if contact_name or contact_phone:
                listing.contacts.append(Contact(name=contact_name, phone=contact_phone))

        except Exception:
            pass
        return listing

    def _find_listing_object(self, obj: dict, depth: int = 0) -> dict | None:
        """Recursively find the actual listing data object in __NEXT_DATA__."""
        if depth > 5:
            return None

        for key in ("item", "listing", "feedItem", "data", "listingData", "ad"):
            if key in obj and isinstance(obj[key], dict):
                candidate = obj[key]
                if any(k in candidate for k in ("price", "rooms", "address", "Price", "Rooms")):
                    return candidate

        for v in obj.values():
            if isinstance(v, dict):
                if any(k in v for k in ("price", "rooms", "address", "Price", "Rooms", "square_meters")):
                    return v
                found = self._find_listing_object(v, depth + 1)
                if found:
                    return found

        return None

    async def _smart_extract(self, page: Page, listing: Listing) -> Listing:
        """
        Extract listing data from the Yad2 DOM using targeted selectors
        based on Yad2's actual component structure.
        """

        data = await page.evaluate("""() => {
            const result = {};

            // --- Price ---
            const priceEl = document.querySelector('[data-testid="price"]');
            if (priceEl) result.price = priceEl.textContent.trim();

            // --- Street address (from floating header) ---
            const addrEl = document.querySelector('[class*="floating-property-details_address"]')
                        || document.querySelector('[class*="address"]');
            if (addrEl) result.street = addrEl.textContent.trim();

            // --- Title (h1) - usually "street name" ---
            const h1 = document.querySelector('h1');
            if (h1) result.h1 = h1.textContent.trim();

            // --- Property type + location subtitle (h2 with data-testid="address") ---
            const subEl = document.querySelector('h2[data-testid="address"]')
                       || document.querySelector('[class*="address_address"]')
                       || document.querySelector('[class*="item-title_subTitle"]');
            if (subEl) result.subtitle = subEl.textContent.trim();

            // --- Key stats (rooms / floor / sqm) from building-details ---
            const detailItems = document.querySelectorAll('[data-testid="property-detail-item"]');
            for (const item of detailItems) {
                const fullText = item.textContent.trim();
                const valueEl = item.querySelector('[data-testid="building-text"]');
                const labelEl = item.querySelector('[class*="itemValue"]');
                const value = valueEl ? valueEl.textContent.trim() : '';
                const label = labelEl ? labelEl.textContent.trim() : fullText;

                if (label.includes('חדרים') && value) {
                    result.rooms = value;
                } else if (label.includes('מ') && (label.includes('ר') || label.includes('\u05F4')) && value) {
                    result.sqm = value;
                } else if (label.includes('קרקע') || label.includes('קומה')) {
                    result.floor = value || label;
                }
            }

            // Fallback: parse the combined text of building-details
            if (!result.rooms || !result.sqm) {
                const bd = document.querySelector('[data-testid="building-details"]');
                if (bd) {
                    const text = bd.textContent;
                    if (!result.rooms) {
                        const m = text.match(/([\d.]+)\s*חדרים/);
                        if (m) result.rooms = m[1];
                    }
                    if (!result.sqm) {
                        const m = text.match(/([\d,]+)\s*מ/);
                        if (m) result.sqm = m[1].replace(',', '');
                    }
                }
            }

            // --- Description ---
            const descEl = document.querySelector('[class*="description"], [class*="Description"], [class*="info_text"]');
            if (descEl) result.description = descEl.textContent.trim();

            return result;
        }""")

        if not data:
            return listing

        if not listing.price and data.get("price"):
            listing.price = data["price"]

        if not listing.rooms and data.get("rooms"):
            listing.rooms = data["rooms"]

        if not listing.size_sqm and data.get("sqm"):
            listing.size_sqm = data["sqm"]

        if not listing.floor and data.get("floor"):
            listing.floor = data["floor"]

        if not listing.description and data.get("description"):
            listing.description = data["description"]

        # Street address from the floating header (most accurate)
        street_from_dom = data.get("street") or data.get("h1")
        if street_from_dom and not listing.street:
            listing.street = street_from_dom

        # Subtitle: "property_type, neighborhood, city"
        subtitle = data.get("subtitle", "")
        if subtitle:
            parts = [p.strip() for p in subtitle.split(",")]
            if len(parts) >= 3:
                listing.property_type = listing.property_type or parts[0]
                listing.neighborhood = listing.neighborhood or parts[1]
                listing.city = listing.city or parts[2]
            elif len(parts) == 2:
                listing.neighborhood = listing.neighborhood or parts[0]
                listing.city = listing.city or parts[1]

        # Build full address
        if listing.street and listing.city:
            listing.address = f"{listing.street}, {listing.neighborhood}, {listing.city}" if listing.neighborhood else f"{listing.street}, {listing.city}"
        elif not listing.address:
            listing.address = data.get("h1", "")

        # --- Parse address into components if structured ---
        if listing.address and not listing.city:
            listing = _parse_address_string(listing)

        # --- Features from description ---
        if listing.description:
            for keyword, attr in FEATURES_MAP.items():
                if keyword in listing.description:
                    setattr(listing, attr, True)

        # --- Features from DOM tags ---
        feature_elements = await page.query_selector_all(
            "[class*='ameniti'], [class*='feature'], [class*='tag'], "
            "[data-testid*='amenit'], [data-testid*='feature']"
        )
        for el in feature_elements:
            txt = ((await el.text_content()) or "").strip()
            if txt and len(txt) < 50:
                listing.raw_features.append(txt)
                for keyword, attr in FEATURES_MAP.items():
                    if keyword in txt:
                        setattr(listing, attr, True)

        return listing

    async def _extract_images(self, page: Page) -> list[str]:
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

        # Extract phone from tel: links first (most reliable)
        phone = None
        tel_links = await page.query_selector_all("a[href^='tel:']")
        for link in tel_links:
            href = await link.get_attribute("href") or ""
            number = href.replace("tel:", "").strip()
            if number and len(number) >= 9:
                phone = number
                break

        name = await _text(page, [
            "[data-testid*='contact-name']",
            "[class*='contact-name']",
            "[class*='seller-name']",
            "[class*='ContactName']",
            "[class*='agent-name']",
        ])

        # Extract phone from description as fallback
        if not phone and listing.description:
            desc_clean = listing.description.replace("מספר", " ").replace("פלאפון", " ")
            m = PHONE_RE.search(desc_clean)
            if m:
                phone = m.group(0).replace(" ", "").replace("–", "-")

        if phone or name:
            contacts.append(Contact(name=name, phone=phone))

        return contacts


PROPERTY_TYPES = {
    "דירה", "דירת גן", "גג/פנטהאוז", "פנטהאוז", "דופלקס", "טריפלקס",
    "בית פרטי", "בית פרטי/ קוטג'", "קוטג'", "מגרש", "דו משפחתי",
    "מיני פנטהאוז", "סטודיו", "יחידת דיור", "משק חקלאי", "נחלה",
}


def _parse_address_string(listing: Listing) -> Listing:
    """
    Parse a Yad2 address/title string like "דירה, לב תל אביב, לב העיר צפון, תל אביב יפו"
    into property_type, neighborhood, city, and a cleaner address.
    """
    addr = listing.address or ""
    parts = [p.strip() for p in addr.split(",")]

    if len(parts) < 2:
        return listing

    first = parts[0]
    is_type = first in PROPERTY_TYPES or any(first.startswith(t) for t in PROPERTY_TYPES)

    if is_type:
        listing.property_type = listing.property_type or first
        rest = parts[1:]
    else:
        rest = parts

    if len(rest) >= 2:
        listing.city = listing.city or rest[-1].strip()
        listing.neighborhood = listing.neighborhood or rest[0].strip()
        listing.address = ", ".join(rest)
        if not listing.street and len(rest) >= 3:
            listing.street = rest[0].strip()
    elif len(rest) == 1:
        listing.city = listing.city or rest[0].strip()

    return listing


def _is_listing_image(url: str) -> bool:
    skip_patterns = ["logo", "icon", "avatar", "pixel", "tracking", "1x1", "svg", "play.png"]
    url_lower = url.lower()
    return not any(p in url_lower for p in skip_patterns)


def _normalize_image_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(query=""))


def _dedupe_images(images: list[str]) -> list[str]:
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
