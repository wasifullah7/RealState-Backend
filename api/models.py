
from pydantic import BaseModel
from typing import Optional, Dict, Any


class ScrapeRequest(BaseModel):
    post_url: str


class ScrapeAndMatchRequest(BaseModel):
    post_url: str


class SaleListing(BaseModel):
    id: Optional[int] = None
    url: Optional[str] = None
    title: Optional[str] = None
    desc: Optional[str] = None
    price: Optional[float] = None
    rooms: Optional[int] = None
    location: Optional[str] = None
    images: Optional[list] = None


class MatchRequest(BaseModel):
    sale_url: Optional[str] = None
    sale_listing: Optional[SaleListing] = None

    @staticmethod
    def ensure_payload(data: "MatchRequest"):
        from fastapi import HTTPException
        if not data.sale_url and not data.sale_listing:
            raise HTTPException(
                status_code=400,
                detail="Provide either 'sale_url' in the request body."
            )
        return data
