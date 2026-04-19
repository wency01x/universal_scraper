import io
import csv
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func
from database.connection import get_db
from database.models import ScrapeJob, PriceHistory, TrackedProduct
from .schemas import (
    JobCreate, JobResponse,
    BulkJobCreate, BulkJobResponse,
    PriceHistoryResponse, TrackedProductCreate, TrackedProductResponse,
    DashboardResponse
)
from worker.tasks import run_scrape_job


router = APIRouter()


# ══════════════════════════════════════════════════════════════════
# EXISTING ENDPOINTS
# ══════════════════════════════════════════════════════════════════

@router.get("/")
def read_root():
    return {"message": "Universal Scraper Engine is online. Go to /docs to test the API."}


@router.post("/jobs/", response_model=JobResponse)
def create_job(job: JobCreate, db: Session = Depends(get_db)):
    new_job = ScrapeJob(target_url=str(job.url), status="pending")
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    run_scrape_job.delay(new_job.id)
    return new_job


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job_status(job_id: int, db: Session = Depends(get_db)):
    job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ══════════════════════════════════════════════════════════════════
# BULK JOB SUBMISSION — Automation at Scale
# ══════════════════════════════════════════════════════════════════

@router.post("/jobs/bulk", response_model=BulkJobResponse, summary="Submit multiple URLs at once")
def create_bulk_jobs(payload: BulkJobCreate, db: Session = Depends(get_db)):
    """Submit a batch of URLs for scraping. Each URL creates a separate background job."""
    job_ids = []
    for url in payload.urls:
        new_job = ScrapeJob(target_url=str(url), status="pending")
        db.add(new_job)
        db.commit()
        db.refresh(new_job)
        run_scrape_job.delay(new_job.id)
        job_ids.append(new_job.id)

    return BulkJobResponse(
        total=len(job_ids),
        job_ids=job_ids,
        message=f"Successfully queued {len(job_ids)} scrape jobs"
    )


@router.get("/jobs/bulk/status", summary="Check status of multiple jobs")
def get_bulk_status(ids: str = Query(..., description="Comma-separated job IDs"), db: Session = Depends(get_db)):
    """Check the status of multiple jobs at once. Pass IDs as comma-separated string."""
    try:
        id_list = [int(x.strip()) for x in ids.split(",")]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format. Use comma-separated integers.")

    jobs = db.query(ScrapeJob).filter(ScrapeJob.id.in_(id_list)).all()
    return [
        {
            "id": job.id,
            "target_url": job.target_url,
            "status": job.status,
            "extracted_data": job.extracted_data
        }
        for job in jobs
    ]


# ══════════════════════════════════════════════════════════════════
# CSV EXPORT
# ══════════════════════════════════════════════════════════════════

def _jobs_to_csv_stream(jobs: list) -> StreamingResponse:
    """Convert a list of ScrapeJob rows into a downloadable CSV stream."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["job_id", "target_url", "status", "title", "price", "currency", "scrape_status", "debug_raw"])

    for job in jobs:
        data = job.extracted_data or {}
        writer.writerow([
            job.id, job.target_url, job.status,
            data.get("title", ""), data.get("price", ""),
            data.get("currency", ""), data.get("status", ""),
            data.get("debug_raw", ""),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=scrape_results.csv"}
    )


@router.get("/jobs/{job_id}/export", summary="Export a single job result as CSV")
def export_job_csv(job_id: int, db: Session = Depends(get_db)):
    job = db.query(ScrapeJob).filter(ScrapeJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job is not completed yet (status: {job.status})")
    return _jobs_to_csv_stream([job])


@router.get("/jobs/export/all", summary="Export ALL completed jobs as CSV")
def export_all_jobs_csv(
    domain: str = Query(None, description="Filter by domain, e.g. 'amazon.com'"),
    db: Session = Depends(get_db)
):
    """Download all completed scrape jobs as CSV. Optionally filter by domain."""
    query = db.query(ScrapeJob).filter(ScrapeJob.status == "completed")
    if domain:
        query = query.filter(ScrapeJob.target_url.contains(domain))
    jobs = query.all()
    if not jobs:
        raise HTTPException(status_code=404, detail="No completed jobs found")
    return _jobs_to_csv_stream(jobs)


# ══════════════════════════════════════════════════════════════════
# TRACKED PRODUCTS — Scheduled Scraping
# ══════════════════════════════════════════════════════════════════

@router.post("/tracked/", response_model=TrackedProductResponse, summary="Add a product to auto-track")
def add_tracked_product(payload: TrackedProductCreate, db: Session = Depends(get_db)):
    """Add a URL to be automatically re-scraped on a schedule."""
    existing = db.query(TrackedProduct).filter(TrackedProduct.url == str(payload.url)).first()
    if existing:
        raise HTTPException(status_code=409, detail="This URL is already being tracked")

    product = TrackedProduct(
        url=str(payload.url),
        label=payload.label,
        schedule_hours=payload.schedule_hours
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/tracked/", response_model=list[TrackedProductResponse], summary="List all tracked products")
def list_tracked_products(db: Session = Depends(get_db)):
    return db.query(TrackedProduct).all()


@router.delete("/tracked/{product_id}", summary="Stop tracking a product")
def delete_tracked_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(TrackedProduct).filter(TrackedProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Tracked product not found")
    db.delete(product)
    db.commit()
    return {"message": f"Stopped tracking: {product.url}"}


# ══════════════════════════════════════════════════════════════════
# ANALYTICS & DASHBOARD — Data Pipeline Analysis
# ══════════════════════════════════════════════════════════════════

@router.get("/analytics/price-history", response_model=list[PriceHistoryResponse],
            summary="Get price history for a URL")
def get_price_history(
    url: str = Query(..., description="Product URL to get price history for"),
    db: Session = Depends(get_db)
):
    """Returns all recorded prices for a given URL, ordered by date."""
    records = (
        db.query(PriceHistory)
        .filter(PriceHistory.url.contains(url))
        .order_by(PriceHistory.scraped_at.desc())
        .limit(100)
        .all()
    )
    if not records:
        raise HTTPException(status_code=404, detail="No price history found for this URL")
    return records


@router.get("/analytics/dashboard", response_model=DashboardResponse,
            summary="Get overall scraping dashboard stats")
def get_dashboard(db: Session = Depends(get_db)):
    """Returns summary statistics: total jobs, success rate, tracked products, recent results."""
    total = db.query(sql_func.count(ScrapeJob.id)).scalar() or 0
    completed = db.query(sql_func.count(ScrapeJob.id)).filter(ScrapeJob.status == "completed").scalar() or 0
    failed = db.query(sql_func.count(ScrapeJob.id)).filter(ScrapeJob.status == "failed").scalar() or 0
    price_records = db.query(sql_func.count(PriceHistory.id)).scalar() or 0
    tracked = db.query(sql_func.count(TrackedProduct.id)).scalar() or 0

    # Last 10 completed results
    recent_jobs = (
        db.query(ScrapeJob)
        .filter(ScrapeJob.status == "completed")
        .order_by(ScrapeJob.id.desc())
        .limit(10)
        .all()
    )
    recent_results = [
        {
            "id": j.id,
            "url": j.target_url,
            "title": (j.extracted_data or {}).get("title", ""),
            "price": (j.extracted_data or {}).get("price", ""),
            "currency": (j.extracted_data or {}).get("currency", ""),
        }
        for j in recent_jobs
    ]

    return DashboardResponse(
        total_jobs=total,
        completed=completed,
        failed=failed,
        success_rate=round((completed / total * 100) if total > 0 else 0, 1),
        total_price_records=price_records,
        tracked_products=tracked,
        recent_results=recent_results
    )