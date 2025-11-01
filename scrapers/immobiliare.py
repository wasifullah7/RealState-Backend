import os
import json
import logging
from typing import Any, Dict, List, Optional

import requests


class ImmobiliareScraper:
    """Client for scraping single Immobiliare.it listings via Apify actor."""

    DEFAULT_ACTOR_ID = "p9QZzUdBCGXMDuKad"
    RUN_SYNC_TIMEOUT_SECONDS = 600

    def __init__(self, api_key: str, actor_id: Optional[str] = None) -> None:
        self.api_key = api_key
        self.actor_id = actor_id or os.getenv("IMMOBILIARE_ACTOR_ID", self.DEFAULT_ACTOR_ID)
        self.logger = logging.getLogger(__name__)


    def validate_url(self, url: str) -> bool:
        return "immobiliare.it" in url

    def scrape(self, url: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
        url = self._normalize_url(url)

        if not self.validate_url(url):
            self.logger.error("Invalid Immobiliare URL: %s", url)
            return None

        payload = self.prepare_payload(url=url, **kwargs)

        try:
            self.logger.info(
                "Calling Immobiliare actor for %s with payload: %s",
                url,
                json.dumps(payload, indent=2),
            )

            raw_result = self._call_run_sync(payload)

            if not raw_result:
                self.logger.warning("Immobiliare scraper returned empty response for %s", url)
                return None

            if isinstance(raw_result, list):
                if not raw_result:
                    self.logger.warning("Immobiliare dataset empty for %s", url)
                    return None
                raw_result = raw_result[0]

            processed = self._process_result(raw_result)
            return processed

        except requests.exceptions.RequestException as exc:
            self.logger.error("Request error while scraping Immobiliare: %s", exc, exc_info=True)
            return None
        except Exception as exc:  
            self.logger.error("Error scraping Immobiliare: %s", exc, exc_info=True)
            return None

    def prepare_payload(
        self,
        url: str,
        start_urls: Optional[List[str]] = None,
        max_concurrency: int = 10,
        min_concurrency: int = 1,
        max_request_retries: int = 100,
        proxy_configuration: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "startUrls": start_urls or [url],
            "maxConcurrency": max_concurrency,
            "minConcurrency": min_concurrency,
            "maxRequestRetries": max_request_retries,
            "proxyConfiguration": proxy_configuration
            or {
                "useApifyProxy": True,
            },
        }
        return payload

    def _normalize_url(self, url: str) -> str:
        if not isinstance(url, str):
            return url

        cleaned = url.strip()

        if "immobiliare.it/en/" in cleaned:
            cleaned = cleaned.replace("immobiliare.it/en/", "immobiliare.it/")

        if cleaned.endswith(("?", "&")):
            cleaned = cleaned.rstrip("?&")

        return cleaned

    def _process_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        raw = dict(result)

        if raw.get("dataType") == "agency":
            processed: Dict[str, Any] = dict(raw)
            processed["source"] = "immobiliare"
            processed.setdefault("listingUrl", processed.get("url"))
            return processed

        basic_info = raw.get("basicInfo") or {}

        listing_url = (
            raw.get("url")
            or raw.get("detailUrl")
            or raw.get("canonicalUrl")
            or basic_info.get("analytics", {}).get("shareUrl")
        )

        media = raw.get("media") or basic_info.get("media") or {}
        image_urls: List[str] = []

        def _collect_media_urls(values: Any) -> None:
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, dict):
                        for key in ("url", "src", "hd", "sd"):
                            url_value = value.get(key)
                            if url_value and url_value not in image_urls:
                                image_urls.append(url_value)
                    elif isinstance(value, str) and value not in image_urls:
                        image_urls.append(value)

        for media_key in ("imgs_hd", "imgs_b", "images", "gallery"):
            _collect_media_urls(media.get(media_key))

        placeholder = media.get("placeholder") if isinstance(media, dict) else None
        if placeholder and placeholder not in image_urls:
            image_urls.append(placeholder)

        price_node = (
            raw.get("price")
            or basic_info.get("price")
            or raw.get("infoCosti", [{}])[0]
        )

        formatted_price = None
        amount = None
        currency = None

        if isinstance(price_node, dict):
            formatted_price = (
                price_node.get("formatted")
                or price_node.get("value")
                or price_node.get("text")
                or price_node.get("label")
            )
            raw_amount = (
                price_node.get("amount")
                or price_node.get("raw")
                or price_node.get("value")
            )
            if isinstance(raw_amount, (int, float)):
                amount = raw_amount
            elif isinstance(raw_amount, str) and raw_amount.replace(".", "", 1).isdigit():
                try:
                    amount = float(raw_amount)
                except ValueError:
                    amount = None
            currency = price_node.get("currency") or "€"
        elif isinstance(price_node, (int, float)):
            amount = price_node
            currency = "€"
            formatted_price = f"€ {price_node:,.0f}".replace(",", ".")
        elif isinstance(price_node, str):
            formatted_price = price_node

        analytics = raw.get("analytics") or basic_info.get("analytics") or {}
        geography = basic_info.get("geography") or {}

        def _safe_float(value: Any) -> Optional[float]:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        def _safe_int(value: Any) -> Optional[int]:
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str):
                digits = "".join(ch for ch in value if ch.isdigit())
                if digits:
                    try:
                        return int(digits)
                    except ValueError:
                        return None
            return None

        location_info = {
            "address": raw.get("addr") or geography.get("street"),
            "city": raw.get("c") or geography.get("municipality", {}).get("name"),
            "state": raw.get("region")
            or geography.get("province", {}).get("name"),
            "country": analytics.get("country")
            or geography.get("municipality", {}).get("country"),
            "coordinates": {
                "lat": _safe_float(
                    geography.get("geolocation", {}).get("latitude")
                    or raw.get("lt")
                ),
                "lng": _safe_float(
                    geography.get("geolocation", {}).get("longitude")
                    or raw.get("ln")
                ),
            },
        }

        topology = basic_info.get("topology") or {}

        rooms_source = (
            topology.get("rooms")
            or basic_info.get("rooms")
            or raw.get("rooms")
            or raw.get("s")
        )
        bathrooms_source = (
            topology.get("bathrooms")
            or raw.get("bathrooms")
            or raw.get("bagni")
        )

        feature_list: List[str] = []
        for key in ("otherFeatures",):
            values = analytics.get(key)
            if isinstance(values, list):
                feature_list.extend([str(item) for item in values if item])

        for array_key in ("datiPrincipali", "infoCosti"):
            values = raw.get(array_key)
            if isinstance(values, list):
                for item in values:
                    if isinstance(item, dict):
                        label = item.get("label")
                        value = item.get("value")
                        if label and value:
                            feature_list.append(f"{label}: {value}")

        agency_detail = raw.get("agencyDetail") or basic_info.get("contacts") or {}
        phones = agency_detail.get("phones") or []
        if isinstance(phones, list) and phones and isinstance(phones[0], dict):
            phone_value = phones[0].get("num") or phones[0].get("value")
        else:
            phone_value = agency_detail.get("telefono1") or agency_detail.get("telefono")

        office = {
            "name": agency_detail.get("agencyName")
            or agency_detail.get("nome")
            or agency_detail.get("name"),
            "phone": phone_value,
            "email": agency_detail.get("email"),
            "logo": agency_detail.get("lag")
            or agency_detail.get("logo"),
            "url": agency_detail.get("web")
            or agency_detail.get("website")
            or agency_detail.get("agencyUrl"),
        }

        amenities: List[str] = []
        seen_amenities: set[str] = set()
        for item in feature_list:
            normalized = item.strip()
            if normalized and normalized not in seen_amenities:
                amenities.append(normalized)
                seen_amenities.add(normalized)

        title = (
            raw.get("meta", {}).get("title")
            or basic_info.get("meta", {}).get("title")
            if isinstance(basic_info.get("meta"), dict)
            else None
        )
        if not title:
            title = raw.get("title") or raw.get("t")

        description = raw.get("desc") or basic_info.get("description")

        processed: Dict[str, Any] = {
            "title": title,
            "description": description,
            "price": {
                "formatted": formatted_price,
                "amount": amount,
                "currency": currency,
            },
            "rooms": _safe_int(rooms_source),
            "bathrooms": _safe_int(bathrooms_source),
            "amenities": amenities,
            "location": {
                **location_info,
                "listingUrl": listing_url,
            },
            "photos": image_urls,
        }

        return processed

    def _call_run_sync(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        run_sync_url = f"https://api.apify.com/v2/acts/{self.actor_id}/run-sync-get-dataset-items?token={self.api_key}"
        response = requests.post(
            run_sync_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=(30, self.RUN_SYNC_TIMEOUT_SECONDS),
        )
        response.raise_for_status()
        return response.json()
