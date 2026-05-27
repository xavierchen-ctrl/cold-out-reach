import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/cold_outreach")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=3,           # 每個 instance 最多 3 個連線
    max_overflow=2,        # 超過 pool_size 最多再開 2 個
    pool_timeout=30,
    pool_recycle=1800,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
