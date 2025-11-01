
from typing import List, Dict, Any, Optional
import re


def _ensure_list_of_strings(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


def _first_non_empty(*values):
    """Return first non-empty value from arguments"""
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if value not in (None, "", [], {}):
            return value
    return None


def normalize_scraped_listing(provider: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize scraped listing data to a common format
    
    Args:
        provider: Scraper provider name (idealista, immobiliare, james_edition)
        raw: Raw scraped data
        
    Returns:
        Normalized listing dictionary
    """
    if not raw:
        return {}

    # Extract and parse price
    price_block = raw.get("price") or raw.get("priceInfo") or {}
    if isinstance(price_block, dict):
        price_value = _first_non_empty(
            price_block.get("parsed"),
            price_block.get("amount"),
            price_block.get("dataPrice"),
            price_block.get("value"),
        )
        if price_value is None or price_value == 0:
            formatted_price = price_block.get("formatted")
            if formatted_price and isinstance(formatted_price, str):
                cleaned = re.sub(r'[^\d,.]', '', formatted_price)
                if '.' in cleaned and ',' in cleaned:
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                elif cleaned.count('.') > 1:  
                    cleaned = cleaned.replace('.', '')
                try:
                    price_value = float(cleaned)
                except (ValueError, TypeError):
                    pass
    else:
        price_value = price_block

    try:
        price_value = float(price_value) if price_value is not None else 0.0
    except (TypeError, ValueError):
        price_value = 0.0

    # Extract location
    location_block = (
        raw.get("location")
        or raw.get("locationInfo")
        or raw.get("address")
        or {}
    )
    if isinstance(location_block, dict):
        location_str = ", ".join(
            [
                str(part).strip()
                for part in [
                    location_block.get("city"),
                    location_block.get("state") or location_block.get("region"),
                    location_block.get("country"),
                ]
                if part
            ]
        )
    else:
        location_str = str(location_block)

    # Extract images
    image_candidates = (
        _ensure_list_of_strings(raw.get("photos"))        # Immobiliare 
        or _ensure_list_of_strings(raw.get("imageUrls"))  # Idealista
        or _ensure_list_of_strings(raw.get("images"))     # Generic
        or _ensure_list_of_strings(raw.get("gallery"))    # JamesEdition
    )
    if not image_candidates:
        primary_image = raw.get("primaryImageUrl") or raw.get("image")
        if primary_image:
            image_candidates = _ensure_list_of_strings(primary_image)

    # Extract description
    description = _first_non_empty(
        raw.get("description"),
        " ".join(_ensure_list_of_strings(raw.get("features"))),
        raw.get("summary"),
        raw.get("propertyType"),
    ) or "Description not provided."

    # Extract rooms
    rooms_value = _first_non_empty(
        raw.get("rooms"),
        raw.get("bedrooms"),
        raw.get("bedroomCount"),
        raw.get("roomCount"),
    )
    try:
        rooms_value = int(rooms_value) if rooms_value is not None else 0
    except (TypeError, ValueError):
        rooms_value = 0

    normalized = {
        "id": _first_non_empty(
            raw.get("id"),
            (raw.get("dataAttributes") or {}).get("id"),
            hash(raw.get("listingUrl") or raw.get("url") or provider) % (10**6),
        ),
        "url": _first_non_empty(raw.get("listingUrl"), raw.get("url")),
        "title": _first_non_empty(raw.get("title"), raw.get("name"), "Untitled Listing"),
        "desc": description,
        "price": price_value,
        "rooms": rooms_value,
        "location": location_str or "Location not provided",
        "images": image_candidates[:3] if image_candidates else [
            "https://via.placeholder.com/400x250?text=Image+Not+Available"
        ],
    }

    return normalized
