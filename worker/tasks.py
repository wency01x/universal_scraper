# worker/tasks.py
from celery import Celery
from database.connection import SessionLocal
from database.models import ScrapeJob
import time

# Connect Celery to your local Redis server
celery_app = Celery(
    "scraper_worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

@celery_app.task
def run_scrape_job(job_id: int):
    # 1. Open a database session
    db = SessionLocal()
    
    # 2. Find the job we need to process
    job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
    if not job:
        db.close()
        return

    # 3. Mark the job as running
    job.status = "running"
    db.commit()

    try:
        # 4. ---------------------------------------------------------
        # THIS IS WHERE THE REAL SCRAPING HAPPENS LATER.
        # For now, we will simulate a 3-second scrape to test the system.
        print(f"Scraping {job.target_url}...")
        time.sleep(3) 
        
        # Here is that dynamic dictionary we talked about!
        simulated_scraped_data = {
            "message": "Success!",
            "raw_html_length": 5042,
            "emails_found": ["contact@example.com"]
        }
        # -------------------------------------------------------------

        # 5. Save the data to that JSONB column and mark it complete
        job.extracted_data = simulated_scraped_data
        job.status = "completed"
        
    except Exception as e:
        # If the scraper crashes (e.g., website blocks us), catch it cleanly
        job.status = "failed"
        job.extracted_data = {"error": str(e)}
        
    finally:
        db.commit()
        db.close()