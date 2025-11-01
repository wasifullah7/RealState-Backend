"""
Scraper service layer - handles all scraping logic
"""
from typing import List, Dict, Any, Tuple, Callable
from fastapi import HTTPException
import logging
import os

try:
    from scrapers.idealista import IdealistaScraper
    from scrapers.immobiliare import ImmobiliareScraper
    from scrapers.james_edition import JamesEditionScraper
except ImportError as e:
    raise ImportError(f"Failed to import scrapers: {e}")

from api.utils import normalize_scraped_listing

logger = logging.getLogger("property_scraper")


class ScraperService:
    """Service for managing property scrapers"""
    
    def __init__(self, apify_api_key: str = None):
        self.apify_api_key = apify_api_key or os.getenv("APIFY_API_KEY")
        
        self.idealista_scraper = None
        self.immobiliare_scraper = None
        self.james_edition_scraper = None
        
        if self.apify_api_key:
            self.idealista_scraper = IdealistaScraper(api_key=self.apify_api_key)
            self.immobiliare_scraper = ImmobiliareScraper(api_key=self.apify_api_key)
            self.james_edition_scraper = JamesEditionScraper(api_key=self.apify_api_key)
        else:
            logger.warning("APIFY_API_KEY not found; scraping endpoints will return errors.")
        
        self.workflows: List[Tuple[str, Callable[[str], bool], Callable[[str], List[Dict[str, Any]]]]] = []
        self._setup_workflows()
    
    def _setup_workflows(self):
        if self.idealista_scraper:
            self.workflows.append((
                "idealista",
                self.idealista_scraper.validate_url,
                self._scrape_idealista
            ))
        
        if self.immobiliare_scraper:
            self.workflows.append((
                "immobiliare",
                self.immobiliare_scraper.validate_url,
                self._scrape_immobiliare
            ))
        
        if self.james_edition_scraper:
            self.workflows.append((
                "james_edition",
                self.james_edition_scraper.validate_url,
                self._scrape_james_edition
            ))
    
    def _scrape_idealista(self, post_url: str) -> List[Dict[str, Any]]:
        if not self.idealista_scraper:
            raise HTTPException(
                status_code=500, 
                detail="Scraper service not configured. Set APIFY_API_KEY."
            )
        
        if not self.idealista_scraper.validate_url(post_url):
            raise HTTPException(
                status_code=400, 
                detail="Invalid URL. Provide a valid Idealista property URL."
            )
        
        result = self.idealista_scraper.scrape(post_url)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Idealista scraper returned no data. Verify the listing is public.",
            )
        return [result]
    
    def _scrape_immobiliare(self, post_url: str) -> List[Dict[str, Any]]:
        if not self.immobiliare_scraper:
            raise HTTPException(
                status_code=500, 
                detail="Scraper service not configured. Set APIFY_API_KEY."
            )
        
        if not self.immobiliare_scraper.validate_url(post_url):
            raise HTTPException(
                status_code=400, 
                detail="Invalid URL. Provide a valid Immobiliare property URL."
            )
        
        try:
            result = self.immobiliare_scraper.scrape(post_url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail="Immobiliare scraper returned no data. Verify the listing is public.",
            )
        return [result]
    
    def _scrape_james_edition(self, post_url: str) -> List[Dict[str, Any]]:
        if not self.james_edition_scraper:
            raise HTTPException(
                status_code=500, 
                detail="Scraper service not configured. Set APIFY_API_KEY."
            )
        
        try:
            results = self.james_edition_scraper.scrape(post_url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        
        if not results:
            raise HTTPException(
                status_code=404,
                detail="James Edition scraper returned no data. Verify the listing is public.",
            )
        return results
    
    def scrape_url(self, post_url: str) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:

        if not self.apify_api_key:
            raise HTTPException(
                status_code=500,
                detail="Scraper service not configured. Set APIFY_API_KEY in environment.",
            )
        
        matched_provider = None
        scraper_func = None
        
        for provider_name, url_validator, scraper_callable in self.workflows:
            if url_validator(post_url):
                matched_provider = provider_name
                scraper_func = scraper_callable
                logger.info(f"Matched URL to provider: {provider_name}")
                break
        
        if not matched_provider or not scraper_func:
            raise HTTPException(
                status_code=400,
                detail="URL does not match any supported scraper (Idealista, Immobiliare, James Edition).",
            )
        
        logger.info(f"Starting scrape for {post_url} using {matched_provider}")
        results = scraper_func(post_url)
        
        if not results or len(results) == 0:
            logger.error("No valid data returned from scraper.")
            raise HTTPException(
                status_code=404,
                detail="No valid data returned. Check if the URL is correct and the property is available.",
            )
        
        if not any(results[0].values()):
            logger.error("Scraper returned empty data.")
            raise HTTPException(
                status_code=404,
                detail="No valid data returned. Check if the URL is correct and the property is available.",
            )
        
        normalized_results = [
            normalize_scraped_listing(matched_provider, item) 
            for item in results
        ]
        
        return matched_provider, results, normalized_results
