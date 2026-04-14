#db connection
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "postgresql+psycopg2://postgres:password@127.0.0.1:5432/scraper_db"

# create engine
engine = create_engine(DATABASE_URL)

# create session 
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# base class for mdels
Base = declarative_base()

# dependeny to get db session in api routs
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()