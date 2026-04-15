# worker/tasks.py
from celery import Celery
from database.connection import SessionLocal
from database.models import ScrapeJob
from extractors.quotes_ext import QuotesExtractor
from extractors.amazon_ext import AmazonExtractor # Import your new extractor
from sqlalchemy.orm.attributes import flag_modified

celery_app = Celery(
    "scraper_worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

@celery_app.task
def run_scrape_job(job_id: int):
    db = SessionLocal()
    
    # 1. FIND THE JOB FIRST
    job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
    
    if not job:
        db.close()
        return

    # 2. NOW YOU CAN FIX THE URL
    target_url = job.target_url
    if "amazon.com" in target_url and "currency=" not in target_url:
        separator = "&" if "?" in target_url else "?"
        target_url = f"{target_url}{separator}language=en_US&currency=USD"
        print(f"[Worker] Auto-fixing Amazon URL: {target_url}")

    # 3. UPDATE STATUS
    job.status = "running"
    db.commit()

    try:
        # 4. ROUTING (Use the NEW target_url here!)
        if "quotes.toscrape.com" in target_url:
            scraper = QuotesExtractor(target_url)
        elif "amazon.com" in target_url:
            scraper = AmazonExtractor(target_url)
        else:
            raise Exception("No extractor found for this domain!")

        print(f"[Worker] Launching {scraper.__class__.__name__}...")
        real_data = scraper.run()

        # 5. SAVE DATA
        job.extracted_data = real_data
        job.status = "completed"
        flag_modified(job, "extracted_data") 
        
    except Exception as e:
        print(f"[Worker] Error: {str(e)}")
        job.status = "failed"
        job.extracted_data = {"error": str(e)}
        flag_modified(job, "extracted_data")
        
    finally:
        db.commit()
        db.close()