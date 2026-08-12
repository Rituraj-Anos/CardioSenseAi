"""Starter-cohort provisioning.

Creates a realistic set of patients + analysed screenings owned by a given
health worker, so their workspace is populated from the first login instead of
showing empty states. Every row is a real record run through the real model and
fusion engine — this is genuine pipeline output, seeded, not fabricated numbers.

Used both by the register flow (per-user starter data) and the standalone
seed script.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.entities import (
    Patient,
    PatientPII,
    Referral,
    ReferralStatus,
    Screening,
    ScreeningStatus,
    Sex,
    User,
)
from app.models.schemas import ClinicalInput
from app.services import screenings as screening_service

log = get_logger(__name__)

_NAMES = [
    "Meera Nair", "Rajesh Kumar", "Lakshmi Devi", "Arun Prasad", "Fatima Sheikh",
    "Vijay Reddy", "Anita Bose", "Suresh Iyer", "Kavya Menon", "Ramesh Yadav",
    "Sunita Patil", "Karthik Rao", "Deepa Krishnan", "Mohammed Aslam", "Geeta Sharma",
    "Prakash Jena", "Nandini Gowda", "Imran Khan", "Sarita Das", "Vikram Chauhan",
]
_VILLAGES = ["Rampur", "Chandpur", "Kelwa", "Bishnupur", "Tarapur", "Mahua", "Sunderpal"]

# A spread of plausible clinical profiles → a realistic low/moderate/high mix.
_TEMPLATES = [
    dict(cp=2, fbs=0, restecg=1, exang=0, oldpeak=0.0, slope=2, ca=0, thal=2),
    dict(cp=1, fbs=0, restecg=1, exang=0, oldpeak=0.4, slope=2, ca=0, thal=2),
    dict(cp=2, fbs=0, restecg=0, exang=0, oldpeak=1.0, slope=1, ca=1, thal=2),
    dict(cp=1, fbs=1, restecg=2, exang=1, oldpeak=1.2, slope=1, ca=1, thal=3),
    dict(cp=0, fbs=0, restecg=0, exang=1, oldpeak=2.0, slope=1, ca=2, thal=3),
    dict(cp=0, fbs=1, restecg=2, exang=1, oldpeak=2.6, slope=0, ca=3, thal=3),
]


def _vitals(rng: random.Random, template: dict, age: int, sex: int) -> ClinicalInput:
    trestbps = int(min(230, max(95, rng.gauss(120 + (age - 40) * 0.6 + template["ca"] * 8, 12))))
    chol = int(min(560, max(130, rng.gauss(200 + template["ca"] * 20, 35))))
    thalach = int(min(202, max(80, rng.gauss(200 - age * 0.8 - template["exang"] * 20, 12))))
    return ClinicalInput(
        age=age, sex=sex, cp=template["cp"], trestbps=trestbps, chol=chol,
        fbs=template["fbs"], restecg=template["restecg"], thalach=thalach,
        exang=template["exang"],
        oldpeak=round(min(6.0, max(0.0, template["oldpeak"] + rng.uniform(-0.3, 0.4))), 1),
        slope=template["slope"], ca=template["ca"], thal=template["thal"],
    )


def provision_demo_cohort(
    db: Session, worker: User, *, count: int = 16, seed: int | None = None
) -> int:
    """Create `count` patients with analysed screenings for `worker`.

    Idempotent-ish: intended to run once per fresh account. Returns the number
    of screenings created. Explanations are generated so result pages are
    populated too.
    """
    rng = random.Random(seed if seed is not None else hash(str(worker.id)) & 0xFFFFFFFF)
    now = datetime.now(UTC)
    screening_count = 0

    for i in range(count):
        name = _NAMES[i % len(_NAMES)]
        sex = rng.choice([0, 1])
        age = rng.randint(35, 74)

        pii = PatientPII(
            full_name=name,
            contact=f"+91 9{rng.randint(100000000, 999999999)}",
            dob=now - timedelta(days=age * 365 + rng.randint(0, 364)),
        )
        db.add(pii)
        db.flush()

        patient = Patient(
            pii_ref=pii.id,
            created_by=worker.id,
            sex=Sex.male if sex == 1 else Sex.female,
            age_years=age,
            village_or_area=rng.choice(_VILLAGES),
        )
        db.add(patient)
        db.flush()

        template = _TEMPLATES[i % len(_TEMPLATES)]
        for s in range(rng.choice([1, 1, 2, 2, 3])):
            created = now - timedelta(days=rng.randint(0, 60), hours=rng.randint(0, 23))
            screening = Screening(patient_id=patient.id, created_by=worker.id, created_at=created)
            db.add(screening)
            db.flush()

            screening_service.save_clinical(db, screening, _vitals(rng, template, age, sex))
            result = screening_service.analyze(db, screening)
            screening.created_at = created
            screening_count += 1

            if result.risk_band.value == "high" and rng.random() < 0.6:
                db.add(
                    Referral(
                        screening_id=screening.id,
                        created_by=worker.id,
                        status=rng.choice([ReferralStatus.pending, ReferralStatus.accepted]),
                        refer_to="District Hospital",
                        note="Elevated cardiovascular risk on screening.",
                    )
                )
            if s == 0 and rng.random() < 0.4:
                screening.status = ScreeningStatus.reviewed
                screening.reviewed_by = worker.id
                screening.reviewed_at = created + timedelta(hours=2)

    db.flush()
    log.info("demo_cohort_provisioned", user_id=str(worker.id), screenings=screening_count)
    return screening_count
