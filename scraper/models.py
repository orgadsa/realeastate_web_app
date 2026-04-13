from __future__ import annotations

from pydantic import BaseModel


class Contact(BaseModel):
    name: str | None = None
    phone: str | None = None
    contact_type: str | None = None  # e.g. "private", "agent", "developer"


class Listing(BaseModel):
    url: str
    source: str  # "yad2" | "madlan"
    address: str | None = None
    city: str | None = None
    neighborhood: str | None = None
    street: str | None = None
    price: str | None = None
    rooms: str | None = None
    floor: str | None = None
    total_floors: str | None = None
    size_sqm: str | None = None
    property_type: str | None = None  # apartment, house, penthouse, etc.
    entry_date: str | None = None
    description: str | None = None
    is_furnished: bool | None = None
    has_parking: bool | None = None
    has_elevator: bool | None = None
    has_balcony: bool | None = None
    has_mamad: bool | None = None  # safe room
    has_air_conditioning: bool | None = None
    contacts: list[Contact] = []
    images: list[str] = []
    raw_features: list[str] = []

    def summary(self) -> str:
        parts = []
        if self.address:
            parts.append(f"כתובת: {self.address}")
        if self.price:
            parts.append(f"מחיר: {self.price}")
        if self.rooms:
            parts.append(f"חדרים: {self.rooms}")
        if self.size_sqm:
            parts.append(f"שטח: {self.size_sqm} מ\"ר")
        if self.floor:
            floor_str = self.floor
            if self.total_floors:
                floor_str += f"/{self.total_floors}"
            parts.append(f"קומה: {floor_str}")
        if self.contacts:
            for c in self.contacts:
                contact_parts = []
                if c.name:
                    contact_parts.append(c.name)
                if c.phone:
                    contact_parts.append(c.phone)
                if contact_parts:
                    parts.append(f"איש קשר: {', '.join(contact_parts)}")
        if self.images:
            parts.append(f"תמונות: {len(self.images)}")
        return "\n".join(parts)
