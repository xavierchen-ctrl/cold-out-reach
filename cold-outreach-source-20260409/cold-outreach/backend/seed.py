"""
Run once to create the default admin account.
Usage: python seed.py
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

from database import engine, SessionLocal, Base
from models import User, UserRole
from auth import hash_password
import models  # ensure all models are registered

ADMIN_EMAIL = "joelou989@gmail.com"
ADMIN_PASSWORD = "Ajo0114#"
ADMIN_NAME = "Joe Lou"


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if existing:
            print(f"Admin {ADMIN_EMAIL} already exists, skipping.")
            return
        admin = User(
            email=ADMIN_EMAIL,
            name=ADMIN_NAME,
            hashed_password=hash_password(ADMIN_PASSWORD),
            role=UserRole.admin,
        )
        db.add(admin)
        db.commit()
        print(f"✅ Admin created: {ADMIN_EMAIL}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
