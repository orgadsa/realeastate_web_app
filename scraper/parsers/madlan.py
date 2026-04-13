from __future__ import annotations

import json
import re

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
    "ממד": "has_mamad",
    "מרוהטת": "is_furnished",
    "ריהוט": "is_furnished",
}


class MadlanParser(BaseParser):
    source = "madlan"

    async def parse(self, page: Page, url: str) -> Listing:
        from scraper.browser import load_page

        await load_page(page, url, wait_selector="[class*='listing'], [class*='Listing']")

        listing = Listing(url=url, source=self.source)

        listing = await self._try_extract_from_json(page, listing)
        listing = await self._extract_from_dom(page, listing)
        listing.images = await self._extract_images(page)
        listing.contacts = await self._extract_contacts(page)

        return listing

    async def _try_extract_from_json(self, page: Page, listing: Listing) -> Listing:
        """Madlan (Next.js based) often has __NEXT_DATA__ or Apollo cache."""

        # __NEXT_DATA__
        try:
            next_data = await page.evaluate(
                "() => window.__NEXT_DATA__ && JSON.stringify(window.__NEXT_DATA__)"
            )
            if next_data:
                data = json.loads(next_data)
                listing = self._parse_next_data(data, listing)
                if listing.price:
                    return listing
        except Exception:
            pass

        # Apollo state (Madlan uses GraphQL)
        try:
            apollo = await page.evaluate(
                "() => window.__APOLLO_STATE__ && JSON.stringify(window.__APOLLO_STATE__)"
            )
            if apollo:
                data = json.loads(apollo)
                listing = self._parse_apollo(data, listing)
        except Exception:
            pass

        # JSON-LD
        try:
            scripts = await page.query_selector_all('script[type="application/ld+json"]')
            for script in scripts:
                text = await script.text_content()
                data = json.loads(text)
                if isinstance(data, dict):
                    listing.address = listing.address or _str(data.get("name"))
                    listing.description = listing.description or _str(
                        data.get("description")
                    )
                    offers = data.get("offers", {})
                    if isinstance(offers, dict):
                        listing.price = listing.price or _str(offers.get("price"))
        except Exception:
            pass

        return listing

    def _parse_next_data(self, data: dict, listing: Listing) -> Listing:
        try:
            props = data.get("props", {}).get("pageProps", {})
            item = props.get("listing") or props.get("item") or props.get("data") or {}

            if not item:
                for v in props.values():
                    if isinstance(v, dict) and (
                        "price" in v or "address" in v or "rooms" in v
                    ):
                        item = v
                        break
            if not item:
                return listing

            listing.price = listing.price or _str(item.get("price"))
            listing.rooms = listing.rooms or _str(item.get("rooms"))
            listing.size_sqm = listing.size_sqm or _str(
                item.get("squareMeter") or item.get("size") or item.get("area")
            )
            listing.floor = listing.floor or _str(item.get("floor"))
            listing.total_floors = listing.total_floors or _str(item.get("totalFloors"))
            listing.description = listing.description or _str(item.get("description"))
            listing.property_type = listing.property_type or _str(
                item.get("propertyType") or item.get("type")
            )
            listing.entry_date = listing.entry_date or _str(item.get("entryDate"))

            addr = item.get("address") or {}
            if isinstance(addr, dict):
                listing.city = listing.city or _str(addr.get("city"))
                listing.street = listing.street or _str(addr.get("street"))
                listing.neighborhood = listing.neighborhood or _str(
                    addr.get("neighborhood")
                )
                house = _str(addr.get("houseNumber"))
                if listing.street:
                    listing.address = listing.street
                    if house:
                        listing.address += f" {house}"
                    if listing.city:
                        listing.address += f", {listing.city}"
            elif isinstance(addr, str):
                listing.address = addr

            images = item.get("images") or item.get("photos") or []
            if images:
                listing.images = [
                    (img.get("url") or img.get("src") or img)
                    for img in images
                    if isinstance(img, (dict, str))
                ]

            contact_name = _str(item.get("contactName") or item.get("agentName"))
            contact_phone = _str(item.get("contactPhone") or item.get("agentPhone"))
            if contact_name or contact_phone:
                listing.contacts.append(
                    Contact(name=contact_name, phone=contact_phone)
                )

        except Exception:
            pass
        return listing

    def _parse_apollo(self, data: dict, listing: Listing) -> Listing:
        """Walk Apollo client cache looking for listing-like objects."""
        try:
            for key, obj in data.items():
                if not isinstance(obj, dict):
                    continue
                typename = obj.get("__typename", "")
                if typename not in (
                    "Listing",
                    "ListingDetails",
                    "Property",
                    "Ad",
                    "PoiListing",
                ):
                    continue

                listing.price = listing.price or _str(obj.get("price"))
                listing.rooms = listing.rooms or _str(obj.get("rooms"))
                listing.size_sqm = listing.size_sqm or _str(
                    obj.get("squareMeter") or obj.get("area")
                )
                listing.floor = listing.floor or _str(obj.get("floor"))
                listing.description = listing.description or _str(
                    obj.get("description")
                )
                listing.address = listing.address or _str(obj.get("address"))
                listing.city = listing.city or _str(obj.get("city"))
                listing.street = listing.street or _str(obj.get("street"))
                listing.neighborhood = listing.neighborhood or _str(
                    obj.get("neighborhood")
                )
                break
        except Exception:
            pass
        return listing

    async def _extract_from_dom(self, page: Page, listing: Listing) -> Listing:
        if not listing.price:
            listing.price = await _text(page, [
                "[data-testid*='price']",
                "[class*='price']",
                "[class*='Price']",
            ])

        if not listing.rooms:
            listing.rooms = await _text(page, [
                "[data-testid*='room']",
                "[class*='rooms']",
            ])

        if not listing.size_sqm:
            listing.size_sqm = await _text(page, [
                "[data-testid*='area']",
                "[data-testid*='size']",
                "[class*='area']",
                "[class*='size']",
                "[class*='sqm']",
            ])

        if not listing.floor:
            listing.floor = await _text(page, [
                "[data-testid*='floor']",
                "[class*='floor']",
            ])

        if not listing.address:
            listing.address = await _text(page, [
                "[data-testid*='address']",
                "[class*='address']",
                "[class*='Address']",
                "h1",
            ])

        if not listing.description:
            listing.description = await _text(page, [
                "[data-testid*='description']",
                "[class*='description']",
                "[class*='Description']",
            ])

        # Features
        feature_els = await page.query_selector_all(
            "[class*='ameniti'], [class*='feature'], [class*='tag'], "
            "[class*='facility'], [data-testid*='feature']"
        )
        for el in feature_els:
            txt = ((await el.text_content()) or "").strip()
            if txt:
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
            "[class*='media'] img, [class*='photo'] img, "
            "[data-testid*='image'] img, picture img"
        )
        for img in img_elements:
            src = await img.get_attribute("src")
            if not src:
                src = await img.get_attribute("data-src")
            if src and src.startswith("http") and _is_listing_image(src):
                images.append(src)

        bg_elements = await page.query_selector_all(
            "[style*='background-image']"
        )
        for el in bg_elements:
            style = await el.get_attribute("style") or ""
            match = re.search(r'url\(["\']?(https?://[^"\')\s]+)', style)
            if match and _is_listing_image(match.group(1)):
                images.append(match.group(1))

        return list(dict.fromkeys(images))

    async def _extract_contacts(self, page: Page) -> list[Contact]:
        contacts: list[Contact] = []

        show_btns = await page.query_selector_all(
            "button[class*='phone'], button[class*='Phone'], "
            "[data-testid*='phone'], [class*='show-phone'], "
            "button[class*='contact'], [class*='call']"
        )
        for btn in show_btns:
            try:
                await btn.click()
                await page.wait_for_timeout(1500)
                break
            except Exception:
                continue

        phone = await _text(page, [
            "[data-testid*='phone'] a",
            "[data-testid*='phone']",
            "[class*='phone'] a",
            "[class*='phone-number']",
            "a[href^='tel:']",
        ])

        name = await _text(page, [
            "[data-testid*='contact-name']",
            "[class*='contact-name']",
            "[class*='agent-name']",
            "[class*='seller-name']",
        ])

        if phone or name:
            contacts.append(Contact(name=name, phone=phone))

        if not phone:
            tel_links = await page.query_selector_all("a[href^='tel:']")
            for link in tel_links:
                href = await link.get_attribute("href") or ""
                number = href.replace("tel:", "").strip()
                if number and len(number) >= 9:
                    contacts.append(Contact(phone=number))
                    break

        return contacts


def _is_listing_image(url: str) -> bool:
    skip_patterns = ["logo", "icon", "avatar", "pixel", "tracking", "1x1", "svg"]
    url_lower = url.lower()
    return not any(p in url_lower for p in skip_patterns)


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
