# main.py
from fastapi import FastAPI
from api.routes import router
from database.connection import engine, Base

# This automatically creates the tables in PostgreSQL if they don't exist!
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Universal Scraper API")

# Register our routes
app.include_router(router)