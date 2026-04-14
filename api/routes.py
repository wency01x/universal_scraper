from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import ScrapeJob
from .schemas import JobCreate, JobResponse
from worker.tasks import run_scrape_job


router = APIRouter()

@router.get("/")
def read_root():
    return {"message": "Universal Scraper Engine is online. Go to /docs to test the API."}

@router.post("/jobs/", response_model=JobResponse)
def create_job(job: JobCreate, db: Session = Depends(get_db)):
    #create a new job record in db
    new_job = ScrapeJob(target_url=str(job.url), status="pending")
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    run_scrape_job.delay(new_job.id)

    # 2. (Future Step) Here is where we will tell Redis to start the Celery worker
    # send_task_to_queue.delay(new_job.id)

    return new_job

@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_status(job_id: int, db: Session = Depends(get_db)):
    # Fetch the job from the database
    job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return job