# worker/tasks.py
from celery import Celery
from database.connection import SessionLocal
from database.models import ScrapeJob, PriceHistory, TrackedProduct
from extractors.quotes_ext import QuotesExtractor
from extractors.amazon_ext import AmazonExtractor
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import func as sql_func
from datetime import datetime, timezone

celery_app = Celery(
    "scraper_worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

@celery_app.task
def run_scrape_job(job_id: int):
    db = SessionLocal()
    
    # 1. FIND THE JOB
    job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
    
    if not job:
        db.close()
        return

    # 2. FIX THE URL (Amazon-specific)
    target_url = job.target_url
    if "amazon.com" in target_url and "currency=" not in target_url:
        separator = "&" if "?" in target_url else "?"
        target_url = f"{target_url}{separator}language=en_US&currency=USD"
        print(f"[Worker] Auto-fixing Amazon URL: {target_url}")

    # 3. UPDATE STATUS
    job.status = "running"
    db.commit()

    try:
        # 4. ROUTE TO CORRECT EXTRACTOR
        if "quotes.toscrape.com" in target_url:
            scraper = QuotesExtractor(target_url)
        elif "amazon.com" in target_url:
            scraper = AmazonExtractor(target_url)
        else:
            raise Exception("No extractor found for this domain!")

        print(f"[Worker] Launching {scraper.__class__.__name__}...")
        real_data = scraper.run()

        # 5. SAVE EXTRACTED DATA
        job.extracted_data = real_data
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        flag_modified(job, "extracted_data")

        # ══════════════════════════════════════════════════════════
        # 6. INSERT PRICE HISTORY RECORD (Data Pipeline: Store)
        # ══════════════════════════════════════════════════════════
        if real_data.get("status") == "Success" and real_data.get("price", "N/A") != "N/A":
            try:
                price_val = float(real_data["price"])
                history = PriceHistory(
                    url=job.target_url,
                    title=real_data.get("title", ""),
                    price=price_val,
                    currency=real_data.get("currency", "USD")
                )
                db.add(history)
                print(f"[Worker] ✓ Price history recorded: ${price_val} for {job.target_url[:50]}")
            except (ValueError, TypeError) as e:
                print(f"[Worker] ⚠ Could not record price history: {e}")

        # 7. UPDATE TRACKED PRODUCT (if this URL is being tracked)
        tracked = db.query(TrackedProduct).filter(TrackedProduct.url == job.target_url).first()
        if tracked and real_data.get("price", "N/A") != "N/A":
            try:
                tracked.last_price = float(real_data["price"])
                tracked.last_scraped_at = datetime.now(timezone.utc)
            except (ValueError, TypeError):
                pass

    except Exception as e:
        print(f"[Worker] Error: {str(e)}")
        job.status = "failed"
        job.extracted_data = {"error": str(e)}
        flag_modified(job, "extracted_data")
        
    finally:
        db.commit()
        db.close()


@celery_app.task
def run_scheduled_scrapes():
    """
    Celery Beat task: Re-scrape all active tracked products that are due.
    Called periodically by the scheduler.
    """
    db = SessionLocal()
    try:
        tracked_products = db.query(TrackedProduct).filter(TrackedProduct.is_active == True).all()
        print(f"[Scheduler] Found {len(tracked_products)} active tracked products")

        for product in tracked_products:
            # Check if enough time has passed since last scrape
            if product.last_scraped_at:
                from datetime import timedelta
                next_scrape = product.last_scraped_at + timedelta(hours=product.schedule_hours)
                if datetime.now(timezone.utc) < next_scrape:
                    continue  # Not due yet

            # Create a new scrape job for this tracked product
            new_job = ScrapeJob(target_url=product.url, status="pending")
            db.add(new_job)
            db.commit()
            db.refresh(new_job)
            
            # Queue the job
            run_scrape_job.delay(new_job.id)
            print(f"[Scheduler] ✓ Queued scrape for: {product.label or product.url[:50]}")

    except Exception as e:
        print(f"[Scheduler] Error: {e}")
    finally:
        db.close()