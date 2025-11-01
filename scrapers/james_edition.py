import json
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests


class JamesEditionScraper:
    """Client for scraping James Edition listings via its Apify actor."""

    DEFAULT_ACTOR_URL = "https://api.apify.com/v2/acts/parseforge~james-edition-real-estate-scraper/runs"
    RUN_STATUS_URL_TEMPLATE = "https://api.apify.com/v2/actor-runs/{run_id}?token={token}"
    DATASET_URL_TEMPLATE = "https://api.apify.com/v2/datasets/{dataset_id}/items?token={token}"
    DEFAULT_POLL_INTERVAL_SECONDS = 5

    def __init__(self, api_key: str, actor_url: Optional[str] = None):
        self.api_key = api_key
        self.actor_url = actor_url or self.DEFAULT_ACTOR_URL
        self.logger = logging.getLogger(__name__)

    def validate_url(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False

            if not parsed.netloc.endswith("jamesedition.com"):
                return False

            path = parsed.path.lower()
            return path.startswith("/real_estate/") or path.startswith("/real-estate/")

        except Exception as exc:
            self.logger.warning("URL validation error for %s: %s", url, exc)
            return False

    def scrape(self, url: str, *, max_items: int = 1) -> List[Dict[str, Any]]:
        if not self.validate_url(url):
            raise ValueError("Invalid James Edition property URL.")

        run_id = self._start_actor_run(url, max_items=max_items)
        dataset_id = self._wait_for_completion(run_id)
        return self._fetch_results(dataset_id)

    def _start_actor_run(self, start_url: str, *, max_items: int = 1) -> str:
        payload = {
            "startUrl": start_url,
            "maxItems": max_items,
        }

        response = requests.post(
            f"{self.actor_url}?token={self.api_key}",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )

        if response.status_code != 201:
            error_msg = (
                f"Failed to start James Edition scraper: "
                f"{response.status_code} - {response.text}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

        try:
            data = response.json()
            return data["data"]["id"]
        except (KeyError, json.JSONDecodeError) as exc:
            error_msg = f"Unexpected response format from Apify API: {exc}"
            self.logger.error("%s. Response: %s", error_msg, response.text)
            raise RuntimeError(error_msg) from exc

    def _wait_for_completion(
        self,
        run_id: str,
        *,
        poll_interval: int = DEFAULT_POLL_INTERVAL_SECONDS,
    ) -> str:
        status_url = self.RUN_STATUS_URL_TEMPLATE.format(run_id=run_id, token=self.api_key)

        while True:
            response = requests.get(status_url, timeout=30)
            if response.status_code != 200:
                error_msg = f"Error checking James Edition run status: {response.text}"
                self.logger.error(error_msg)
                raise RuntimeError(error_msg)

            try:
                payload = response.json()
                data = payload.get("data", {})
                status = data.get("status")
                dataset_id = data.get("defaultDatasetId")
            except json.JSONDecodeError as exc:
                error_msg = f"Invalid JSON while checking run status: {exc}"
                self.logger.error("%s. Response: %s", error_msg, response.text)
                raise RuntimeError(error_msg) from exc

            if status == "SUCCEEDED" and dataset_id:
                return dataset_id

            if status in {"FAILED", "TIMED-OUT"}:
                error_msg = f"James Edition scraper run ended with status {status}"
                self.logger.error(error_msg)
                raise RuntimeError(error_msg)

            self.logger.debug("Waiting for James Edition run %s to complete...", run_id)
            time.sleep(poll_interval)

    def _fetch_results(self, dataset_id: str) -> List[Dict[str, Any]]:
        dataset_url = self.DATASET_URL_TEMPLATE.format(
            dataset_id=dataset_id,
            token=self.api_key,
        )

        response = requests.get(dataset_url, timeout=60)
        if response.status_code != 200:
            error_msg = f"Error fetching James Edition dataset: {response.text}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

        try:
            return response.json()
        except json.JSONDecodeError as exc:
            error_msg = f"Invalid JSON returned for dataset {dataset_id}: {exc}"
            self.logger.error("%s. Response: %s", error_msg, response.text)
            raise RuntimeError(error_msg) from exc
