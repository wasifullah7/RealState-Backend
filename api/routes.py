
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import asyncio

from api.models import ScrapeRequest, ScrapeAndMatchRequest, MatchRequest
from api.scrapers_service import ScraperService
from matching_engine.engine import MatchingEngine


router = APIRouter()

scraper_service: ScraperService = None
matching_engine: MatchingEngine = None


def init_services(scraper_svc: ScraperService, engine: MatchingEngine):
    global scraper_service, matching_engine
    scraper_service = scraper_svc
    matching_engine = engine


@router.get("/health")
def health_check():
    return {
        "status": "ok", 
        "message": "FastAPI backend is running",
        "scrapers_configured": bool(scraper_service and scraper_service.apify_api_key),
    }


@router.post("/scrape", response_model=Dict[str, Any])
async def scrape_listing(payload: ScrapeRequest):

    provider, results, normalized = await asyncio.to_thread(
        scraper_service.scrape_url, payload.post_url
    )
    return {
        "status": "success", 
        "provider": provider, 
        "data": results, 
        "normalized": normalized
    }


@router.post("/match", response_model=Dict[str, Any])
async def match_listing(request_body: MatchRequest):

    data = MatchRequest.ensure_payload(request_body)
    
    if not data.sale_listing:
        raise HTTPException(
            status_code=400,
            detail="This endpoint requires 'sale_listing' data. To scrape a URL, use /scrape_and_match endpoint."
        )
    
    sale_listing_data = data.sale_listing.dict()
    sale_listing_data.setdefault("platform", "Provided Listing")
    
    try:
        matches = await asyncio.to_thread(
            matching_engine.match_sale_to_rentals, 
            sale_listing_data, 
            top_k=5
        )
        print(f" Found {len(matches)} matches for {sale_listing_data.get('title')}.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Matching engine error: {e}")
    
    return {
        "sale_listing": sale_listing_data, 
        "matches": matches
    }


@router.post("/scrape_and_match", response_model=Dict[str, Any])
async def scrape_and_match(payload: ScrapeAndMatchRequest):

    provider, results, normalized = await asyncio.to_thread(
        scraper_service.scrape_url, payload.post_url
    )
    
    if not normalized:
        raise HTTPException(
            status_code=500,
            detail="Scraper returned no normalized listings to match.",
        )
    
    primary_listing = normalized[0]
    
    try:
        matches = await asyncio.to_thread(
            matching_engine.match_sale_to_rentals, 
            primary_listing, 
            top_k=10
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Matching engine error: {exc}")
    
    return {
        "status": "success",
        "provider": provider,
        "data": results,
        "normalized": normalized,
        "sale_listing": primary_listing,
        "matches": matches,
    }
