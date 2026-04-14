# worker/tasks.py
from celery import Celery
from database.connection import SessionLocal
from database.models import ScrapeJob
from extractors.quotes_ext import QuotesExtractor
from sqlalchemy.orm.attributes import flag_modified # <-- NEW IMPORT!

celery_app = Celery(
    "scraper_worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

@celery_app.task
def run_scrape_job(job_id: int):
    db = SessionLocal()
    job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
    if not job:
        db.close()
        return

    job.status = "running"
    db.commit()

    try:
        print(f"[Worker] Launching Extractor for {job.target_url}...")
        
        scraper = QuotesExtractor(job.target_url)
        real_data = scraper.run()

        job.extracted_data = real_data
        job.status = "completed"
        
        # <-- NEW COMMAND: Force the database to notice the JSON change
        flag_modified(job, "extracted_data") 
        
    except Exception as e:
        job.status = "failed"
        job.extracted_data = {"error": str(e)}
        flag_modified(job, "extracted_data") # Flag it here too, just in case of an error
        
    finally:
        db.commit() # Now it will actually save the data!
        db.close()