"""Seed the database with a demo health worker + a rich starter cohort.

Creates real rows through the same services the app uses at runtime, then runs
real inference + fusion on every screening. Uses the shared provisioning
service so it stays in lockstep with the per-account starter data.

Run:  python backend/seed.py            (adds demo data if the DB is empty)
      python backend/seed.py --reset    (wipes and reseeds)

Login after seeding:  asha@cardiosense.demo  /  demo-pass-2026
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.db import SessionLocal, engine
from app.core.security import hash_password
from app.models.base import Base
from app.models.entities import User, UserRole
from app.services.demo_data import provision_demo_cohort

DEMO_EMAIL = "asha@cardiosense.demo"
DEMO_PASSWORD = "demo-pass-2026"


def seed(reset: bool = False) -> None:
    if reset:
        print("Resetting database…")
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if existing and not reset:
            print(f"Demo user already exists ({DEMO_EMAIL}). Use --reset to reseed.")
            return

        worker = User(
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            full_name="Asha Devi",
            role=UserRole.health_worker,
        )
        db.add(worker)
        db.flush()

        n = provision_demo_cohort(db, worker, count=18, seed=2026)
        db.commit()

        print("Seed complete:")
        print(f"  health worker : {DEMO_EMAIL}  /  {DEMO_PASSWORD}")
        print(f"  screenings    : {n}")
    finally:
        db.close()


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
