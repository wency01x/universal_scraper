#db models
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from .connection import Base

class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    #structured metadata
    id = Column(Integer, primary_key=True, index=True)
    target_url = Column(String, nullable=False)
    status = Column(String, default="pending") # states: pending, in_progress, completed, failed

    #unstructured data payload 
    #this JSONB column can hold 5 fields for amazon, or 50 fields for a real estate site
    extracted_data = Column(JSONB, nullable=True)

    #timestamps for tracking performance
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
