
import os
import sys
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from api.scrapers_service import ScraperService
from api.routes import router, init_services
from matching_engine.engine import MatchingEngine
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Real Estate Matching Engine",
    description="API for scraping and matching real estate listings",
    version="1.0.0"
)

# CORS origins - support both local development and production
origins = [
    "http://localhost:5173",  
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Add production frontend URL from environment variable
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    origins.append(frontend_url)
    # Also support https if http is provided
    if frontend_url.startswith("http://"):
        origins.append(frontend_url.replace("http://", "https://"))
    elif frontend_url.startswith("https://"):
        origins.append(frontend_url.replace("https://", "http://"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    global scraper_service, engine
    logger.info("Starting Real Estate Matching Engine API...")
    
    apify_api_key = os.getenv("APIFY_API_KEY")
    if not apify_api_key:
        logger.warning("APIFY_API_KEY not configured. Scraping endpoints will be limited.")
    
    scraper_service = ScraperService(apify_api_key=apify_api_key)
    
    try:
        engine = MatchingEngine()
        logger.info(" MatchingEngine loaded successfully.")
    except Exception as e:
        logger.error(f" Error loading MatchingEngine: {e}")
        logger.error("Please ensure you have run 'python -m matching_engine.build_indexes' first.")
        sys.exit(1)
    
    init_services(scraper_service, engine)
    
    logger.info(" API startup complete!")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Real Estate Matching Engine API...")


app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
