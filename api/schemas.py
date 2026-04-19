#api/schemas.py
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, HttpUrl
from datetime import datetime


# ── Single Job ────────────────────────────────────────────────────
class JobCreate(BaseModel):
    url: HttpUrl

class JobResponse(BaseModel):
    id: int
    target_url: str
    status: str
    extracted_data: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# ── Bulk Jobs ─────────────────────────────────────────────────────
class BulkJobCreate(BaseModel):
    urls: List[HttpUrl]

class BulkJobResponse(BaseModel):
    total: int
    job_ids: List[int]
    message: str


# ── Price History ─────────────────────────────────────────────────
class PriceHistoryResponse(BaseModel):
    id: int
    url: str
    title: Optional[str] = None
    price: Optional[float] = None
    currency: str
    scraped_at: datetime

    class Config:
        from_attributes = True


# ── Tracked Products ──────────────────────────────────────────────
class TrackedProductCreate(BaseModel):
    url: HttpUrl
    label: Optional[str] = None
    schedule_hours: int = 6

class TrackedProductResponse(BaseModel):
    id: int
    url: str
    label: Optional[str] = None
    schedule_hours: int
    is_active: bool
    last_scraped_at: Optional[datetime] = None
    last_price: Optional[float] = None

    class Config:
        from_attributes = True


# ── Analytics ─────────────────────────────────────────────────────
class DashboardResponse(BaseModel):
    total_jobs: int
    completed: int
    failed: int
    success_rate: float
    total_price_records: int
    tracked_products: int
    recent_results: List[Dict[str, Any]]
