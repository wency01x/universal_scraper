#api/schemas.py
from typing import Optional, Dict, Any
from pydantic import BaseModel, HttpUrl

# this ensures the user actually sends a valid URL when requesting a scrape
class JobCreate(BaseModel):
    url: HttpUrl

# this defines what the API returns when we ask for a job's status
class JobResponse(BaseModel):
    id: int
    target_url: str
    status: str

    extracted_data: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


