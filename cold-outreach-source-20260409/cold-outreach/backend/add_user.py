import os
from dotenv import load_dotenv

load_dotenv()

from database import engine, SessionLocal
from models import User, UserRole
from auth import hash_password

def add_user():
    db = SessionLocal()
    try:
        email = "xavier.chen@wavenet.com.tw".lower()
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            existing.hashed_password = hash_password("ting0212")
            print(f"User {email} updated password.")
        else:
            new_user = User(
                email=email,
                name="Xavier Chen",
                hashed_password=hash_password("ting0212"),
                role=UserRole.admin,
            )
            db.add(new_user)
            print(f"User {email} created.")
        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    add_user()
