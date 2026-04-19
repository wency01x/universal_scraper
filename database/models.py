#db models
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, func
from sqlalchemy.dialects.postgresql import JSONB
from .connection import Base


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    #structured metadata
    id = Column(Integer, primary_key=True, index=True)
    target_url = Column(String, nullable=False)
    status = Column(String, default="pending") # states: pending, running, completed, failed

    #unstructured data payload 
    extracted_data = Column(JSONB, nullable=True)

    #timestamps for tracking performance
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class PriceHistory(Base):
    """Stores one price snapshot per scrape — builds a timeline for price tracking."""
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=False, index=True)
    title = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    currency = Column(String, default="USD")
    scraped_at = Column(DateTime(timezone=True), server_default=func.now())


class TrackedProduct(Base):
    """Products that are auto-scraped on a schedule by Celery Beat."""
    __tablename__ = "tracked_products"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, nullable=False, unique=True)
    label = Column(String, nullable=True)  # e.g. "Echo Dot" for easy identification
    schedule_hours = Column(Integer, default=6)  # re-scrape every X hours
    is_active = Column(Boolean, default=True)
    last_scraped_at = Column(DateTime(timezone=True), nullable=True)
    last_price = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
