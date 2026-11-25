
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import User
from app.security import hash_pw

load_dotenv(".env")

email = os.getenv("ADMIN_EMAIL", "").strip().lower()
password = os.getenv("ADMIN_PASSWORD", "")

if not email or not password:
    raise SystemExit("Set ADMIN_EMAIL and ADMIN_PASSWORD in .env first.")

engine = create_engine("sqlite:///./mobihub_local.db")
Session = sessionmaker(bind=engine)

with Session() as db:
    admins = db.query(User).filter_by(role="super").all()

    if not admins:
        raise SystemExit("No super-admin account found.")

    admin = admins[0]
    admin.email = email
    admin.password_hash = hash_pw(password)

    db.commit()
    print("Administrator email and password updated successfully.")
