import os
import json
import logging
from typing import Dict, Any, Optional, List, Union
from urllib.parse import urlparse, urlunparse
import requests

class IdealistaScraper:

    STANDBY_URL = "https://dz-omar--idealista-scraper-api.apify.actor/"
    RUN_SYNC_URL = "https://api.apify.com/v2/acts/dz_omar~idealista-scraper-api/run-sync-get-dataset-items"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)
        
    def validate_url(self, url: str) -> bool:
        normalized = self._normalize_url(url)
        return any(domain in (normalized or "") for domain in ["idealista.com", "idealista.pt", "idealista.it"])
        
    def prepare_payload(
        self,
        url: str,
        proxy_config: Optional[Dict[str, Any]] = None,
        max_retries: int = 2,
        timeout: int = 30,
        save_map_images: bool = True,
        include_gallery: bool = True,
        extract_contact_info: bool = True,
    ) -> Dict[str, Any]:

        payload: Dict[str, Any] = {
            "Url": url,
            "proxyConfig": proxy_config
            or {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
            },
            "maxRetries": max_retries,
            "timeout": timeout,
            "saveMapImages": save_map_images,
            "includeGallery": include_gallery,
            "extractContactInfo": extract_contact_info,
        }

        return payload

    def scrape(
        self, 
        url: str, 
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        normalized_url = self._normalize_url(url)

        if not self.validate_url(normalized_url):
            self.logger.error(f"Invalid Idealista URL: {url}")
            return None

        try:
            payload = self.prepare_payload(url=normalized_url, **kwargs)

            self.logger.info(
                "Calling Idealista API for %s with payload: %s",
                normalized_url,
                json.dumps({k: v for k, v in payload.items() if k != "proxyConfig"}, indent=2),
            )

            try:
                raw_result = self._call_standby(payload)
            except Exception as standby_error:
                self.logger.warning(
                    "Standby endpoint failed (%s). Falling back to run-sync endpoint.",
                    standby_error,
                    exc_info=True,
                )
                raw_result = self._call_run_sync(payload)

            if not raw_result:
                self.logger.warning("Idealista scraper returned empty response for %s", url)
                return None

            processed = self._process_result(raw_result)
            return processed

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error while scraping Idealista: {str(e)}", exc_info=True)
            return None
        except Exception as e:
            self.logger.error(f"Error scraping Idealista: {str(e)}", exc_info=True)
            return None

    def _process_result(self, result: Dict[str, Any]) -> Dict[str, Any]:

        raw = dict(result)

        price_raw = raw.get("price") or ""
        amount = None
        currency = None
        if price_raw:
            parts = price_raw.replace(",", "").split()
            if parts:
                potential_currency = parts[-1]
                if potential_currency.replace(".", "").isalpha() or len(potential_currency) <= 3:
                    currency = potential_currency
                    numeric_part = "".join(parts[:-1])
                else:
                    numeric_part = "".join(parts)
                num_filtered = "".join(ch for ch in numeric_part if ch.isdigit() or ch == ".")
                if num_filtered:
                    try:
                        amount = float(num_filtered)
                    except ValueError:
                        amount = None

        location_value = raw.get("location")
        if isinstance(location_value, dict):
            location = {
                "address": location_value.get("address"),
                "city": location_value.get("city"),
                "state": location_value.get("region"),
                "country": location_value.get("country"),
                "coordinates": location_value.get("coordinates"),
            }
        else:
            location = {
                "address": raw.get("address"),
                "city": location_value if isinstance(location_value, str) else raw.get("city"),
                "state": raw.get("province"),
                "country": raw.get("country"),
                "coordinates": raw.get("coordinates"),
            }

        property_specs = raw.get("propertySpecs", {}) or {}
        living_area_value = property_specs.get("constructedArea") or property_specs.get("livingArea")
        living_area = None
        if living_area_value:
            living_area = {"value": living_area_value, "unit": "m²"}

        features: List[str] = []
        if isinstance(raw.get("characteristics"), list):
            features.extend(raw["characteristics"])
        if isinstance(raw.get("building"), list):
            features.extend(raw["building"])

        gallery = raw.get("gallery") or []
        image_urls = [img.get("url") for img in gallery if isinstance(img, dict) and img.get("url")]
        if not image_urls and raw.get("MainImage"):
            image_urls = [raw["MainImage"]]

        contact_info = raw.get("contactInfo") or {}
        office = {
            "name": contact_info.get("professionalName") or contact_info.get("name"),
            "phone": contact_info.get("phones"),
            "email": contact_info.get("email"),
            "logo": contact_info.get("logo"),
            "url": contact_info.get("agencyWebsite"),
        }

        processed: Dict[str, Any] = dict(raw)
        processed["source"] = "idealista"
        processed["listingUrl"] = processed.get("Url") or processed.get("listingUrl") or processed.get("url")
        processed["primaryImageUrl"] = processed.get("MainImage") or (image_urls[0] if image_urls else None)
        processed["imageUrls"] = image_urls
        processed["featureList"] = features
        processed["locationInfo"] = location
        processed["livingAreaInfo"] = living_area or {"value": None, "unit": "m²"}
        processed["priceInfo"] = {
            "amount": amount,
            "currency": currency,
            "formatted": price_raw or "Price on request",
        }
        processed["bedroomCount"] = property_specs.get("rooms")
        processed["bathroomCount"] = property_specs.get("bathrooms")
        processed["office"] = office

        return processed

    def _normalize_url(self, url: Optional[str]) -> Optional[str]:
        if not url:
            return url

        candidate = url.strip()

        if not candidate:
            return None

        parsed = urlparse(candidate if "//" in candidate else f"https://{candidate.lstrip('/')}")
        netloc = parsed.netloc.lower()

        if netloc.startswith("www.www."):
            while netloc.startswith("www.www."):
                netloc = netloc.replace("www.", "", 1)
            netloc = f"www.{netloc}" if not netloc.startswith("www.") else netloc

        if not netloc and parsed.path:
            netloc = parsed.path
            path = ""
        else:
            path = parsed.path

        path = path or ""

        if netloc.endswith("idealista.com"):
            lower_path = path.lower()
            if lower_path.startswith("/inmueble/") and not lower_path.startswith("/en/inmueble/"):
                path = f"/en{path}"

        normalized = urlunparse(
            (
                parsed.scheme or "https",
                netloc,
                path,
                parsed.params,
                parsed.query,
                parsed.fragment,
            )
        )

        return normalized.rstrip("?&")

    def _call_standby(self, payload: Dict[str, Any]) -> Dict[str, Any]:

        response = requests.post(
            self.STANDBY_URL,
            json=payload,
            headers=self._auth_headers(),
            timeout=payload.get("timeout", 30) + 5,
        )
        response.raise_for_status()
        data = response.json()

        if isinstance(data, dict) and data.get("status") == "failed":
            raise ValueError(data.get("error", "Idealista standby run failed"))

        return data

    def _call_run_sync(self, payload: Dict[str, Any]) -> Dict[str, Any]:

        response = requests.post(
            f"{self.RUN_SYNC_URL}?token={self.api_key}",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=300,
        )
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list):
            if not data:
                raise ValueError("Idealista run-sync returned an empty dataset")
            return data[0]

        if isinstance(data, dict) and "items" in data and data["items"]:
            return data["items"][0]

        raise ValueError("Unexpected response format from Idealista run-sync endpoint")

    def _auth_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }