"""End-to-end screening flow, validation, RBAC and graceful degradation.

These tests assert the behaviours the product actually promises, not just that
endpoints return 200. In particular: that a missing modality produces a valid
full-weight result, and that clinical input outside physiological range is
rejected before it can reach the model.
"""

from __future__ import annotations

from app.core.config import settings

API = settings.api_v1_prefix


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _create_patient(client, headers, name="Test Patient") -> str:
    res = client.post(
        f"{API}/patients",
        headers=headers,
        json={"full_name": name, "sex": "male", "age_years": 55, "village_or_area": "Rampur"},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_screening(client, headers, patient_id) -> str:
    res = client.post(f"{API}/screenings", headers=headers, json={"patient_id": patient_id})
    assert res.status_code == 201, res.text
    return res.json()["id"]


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
def test_health_endpoint(client):
    assert client.get("/health").json()["status"] == "ok"


def test_unauthenticated_requests_are_rejected(client):
    assert client.get(f"{API}/patients").status_code == 401
    assert client.get(f"{API}/dashboard/queue").status_code == 401


def test_duplicate_registration_is_rejected(client):
    body = {
        "email": "dup@example.org",
        "password": "Correct-Horse-9!",
        "full_name": "Dup",
        "role": "health_worker",
    }
    assert client.post(f"{API}/auth/register", json=body).status_code == 201
    assert client.post(f"{API}/auth/register", json=body).status_code == 409


def test_weak_password_is_rejected(client):
    res = client.post(
        f"{API}/auth/register",
        json={
            "email": "weak@example.org",
            "password": "short",
            "full_name": "Weak",
            "role": "health_worker",
        },
    )
    assert res.status_code == 422


def test_login_failure_does_not_reveal_whether_email_exists(client, auth_headers):
    unknown = client.post(
        f"{API}/auth/login",
        json={"email": "nobody@example.org", "password": "Correct-Horse-9!"},
    )
    wrong_pw = client.post(
        f"{API}/auth/login",
        json={"email": "asha.worker@example.org", "password": "Wrong-Password-1!"},
    )
    assert unknown.status_code == wrong_pw.status_code == 401
    assert unknown.json()["detail"] == wrong_pw.json()["detail"]


def test_me_returns_current_user(client, auth_headers):
    res = client.get(f"{API}/auth/me", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["email"] == "asha.worker@example.org"
    assert "password_hash" not in res.json()


# --------------------------------------------------------------------------
# Clinical input validation
# --------------------------------------------------------------------------
def test_out_of_range_vitals_are_rejected(client, auth_headers, normal_vitals):
    patient_id = _create_patient(client, auth_headers)
    screening_id = _create_screening(client, auth_headers, patient_id)

    bad = {**normal_vitals, "trestbps": 1200}  # transcription slip
    res = client.post(
        f"{API}/screenings/{screening_id}/clinical", headers=auth_headers, json=bad
    )
    assert res.status_code == 422, res.text


def test_unknown_extra_field_is_rejected(client, auth_headers, normal_vitals):
    patient_id = _create_patient(client, auth_headers)
    screening_id = _create_screening(client, auth_headers, patient_id)

    res = client.post(
        f"{API}/screenings/{screening_id}/clinical",
        headers=auth_headers,
        json={**normal_vitals, "smoker": 1},
    )
    assert res.status_code == 422


def test_analyze_without_clinical_data_is_refused(client, auth_headers):
    patient_id = _create_patient(client, auth_headers)
    screening_id = _create_screening(client, auth_headers, patient_id)

    res = client.post(f"{API}/screenings/{screening_id}/analyze", headers=auth_headers)
    assert res.status_code == 409


# --------------------------------------------------------------------------
# The core vertical slice
# --------------------------------------------------------------------------
def test_clinical_only_screening_produces_a_full_result(
    client, auth_headers, concerning_vitals
):
    patient_id = _create_patient(client, auth_headers)
    screening_id = _create_screening(client, auth_headers, patient_id)

    assert (
        client.post(
            f"{API}/screenings/{screening_id}/clinical",
            headers=auth_headers,
            json=concerning_vitals,
        ).status_code
        == 200
    )

    res = client.post(f"{API}/screenings/{screening_id}/analyze", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()

    # A calibrated probability, a band, and a confidence figure — not a bare label.
    assert 0.0 <= body["final_score"] <= 1.0
    assert body["risk_band"] in {"low", "moderate", "high"}
    assert 0.0 <= body["confidence"] <= 1.0

    # Graceful degradation: clinical alone runs at full renormalised weight.
    assert body["modalities_used"] == ["clinical"]
    assert body["weights"] == {"clinical": 1.0}

    # Honesty requirements.
    assert "not a diagnosis" in body["disclaimer"].lower()
    assert body["uncertainty_note"]
    assert "1 of 3" in body["uncertainty_note"]
    assert "pcg" in body["uncertainty_note"] and "ecg" in body["uncertainty_note"]
    assert body["recommendation"]

    # SHAP explanation is present and uses clinician-facing labels, not raw
    # feature names or one-hot column names.
    clinical = next(p for p in body["per_modality"] if p["modality"] == "clinical")
    explanation = clinical["explanation"]
    assert explanation is not None
    assert explanation["method"] == "shap"
    assert len(explanation["top_factors"]) >= 3
    for factor in explanation["top_factors"]:
        assert factor["direction"] in {"increases_risk", "decreases_risk"}
        assert factor["magnitude"] >= 0
        assert factor["label"] and factor["label"] != factor["feature"]
        assert "_" not in factor["label"]
        assert factor["display_value"]


def test_result_is_retrievable_after_analysis(client, auth_headers, normal_vitals):
    patient_id = _create_patient(client, auth_headers)
    screening_id = _create_screening(client, auth_headers, patient_id)
    client.post(
        f"{API}/screenings/{screening_id}/clinical",
        headers=auth_headers,
        json=normal_vitals,
    )
    analyzed = client.post(
        f"{API}/screenings/{screening_id}/analyze", headers=auth_headers
    ).json()
    fetched = client.get(
        f"{API}/screenings/{screening_id}/result", headers=auth_headers
    ).json()
    assert fetched["final_score"] == analyzed["final_score"]
    assert fetched["risk_band"] == analyzed["risk_band"]


def test_result_before_analysis_is_a_conflict_not_an_empty_result(
    client, auth_headers, normal_vitals
):
    """An unanalysed screening must not return a zero-risk-looking payload."""
    patient_id = _create_patient(client, auth_headers)
    screening_id = _create_screening(client, auth_headers, patient_id)
    client.post(
        f"{API}/screenings/{screening_id}/clinical",
        headers=auth_headers,
        json=normal_vitals,
    )
    assert (
        client.get(f"{API}/screenings/{screening_id}/result", headers=auth_headers).status_code
        == 409
    )


def test_resubmitting_clinical_data_invalidates_the_previous_result(
    client, auth_headers, normal_vitals, concerning_vitals
):
    """Stale results must not survive an input change."""
    patient_id = _create_patient(client, auth_headers)
    screening_id = _create_screening(client, auth_headers, patient_id)

    client.post(
        f"{API}/screenings/{screening_id}/clinical",
        headers=auth_headers,
        json=normal_vitals,
    )
    client.post(f"{API}/screenings/{screening_id}/analyze", headers=auth_headers)

    client.post(
        f"{API}/screenings/{screening_id}/clinical",
        headers=auth_headers,
        json=concerning_vitals,
    )
    # Previous fusion result is gone rather than shown against new inputs.
    assert (
        client.get(f"{API}/screenings/{screening_id}/result", headers=auth_headers).status_code
        == 409
    )


def test_higher_risk_inputs_score_higher_than_lower_risk_inputs(
    client, auth_headers, normal_vitals, concerning_vitals
):
    """A directional sanity check on the model, not a metric assertion."""
    scores = {}
    for label, vitals in (("normal", normal_vitals), ("concerning", concerning_vitals)):
        patient_id = _create_patient(client, auth_headers, name=f"Patient {label}")
        screening_id = _create_screening(client, auth_headers, patient_id)
        client.post(
            f"{API}/screenings/{screening_id}/clinical", headers=auth_headers, json=vitals
        )
        scores[label] = client.post(
            f"{API}/screenings/{screening_id}/analyze", headers=auth_headers
        ).json()["final_score"]

    assert scores["concerning"] > scores["normal"], scores


# --------------------------------------------------------------------------
# Dashboard, history, referrals
# --------------------------------------------------------------------------
def test_dashboard_queue_sorts_high_risk_first(
    client, auth_headers, normal_vitals, concerning_vitals
):
    for label, vitals in (("low", normal_vitals), ("high", concerning_vitals)):
        patient_id = _create_patient(client, auth_headers, name=f"Queue {label}")
        screening_id = _create_screening(client, auth_headers, patient_id)
        client.post(
            f"{API}/screenings/{screening_id}/clinical", headers=auth_headers, json=vitals
        )
        client.post(f"{API}/screenings/{screening_id}/analyze", headers=auth_headers)

    body = client.get(f"{API}/dashboard/queue", headers=auth_headers).json()
    assert body["stats"]["total_patients"] == 2
    assert body["stats"]["total_screenings"] == 2

    bands = [row["latest_risk_band"] for row in body["queue"]]
    rank = {"high": 0, "moderate": 1, "low": 2, None: 3}
    assert [rank[b] for b in bands] == sorted(rank[b] for b in bands)


def test_patient_history_includes_screenings(client, auth_headers, normal_vitals):
    patient_id = _create_patient(client, auth_headers)
    screening_id = _create_screening(client, auth_headers, patient_id)
    client.post(
        f"{API}/screenings/{screening_id}/clinical",
        headers=auth_headers,
        json=normal_vitals,
    )
    client.post(f"{API}/screenings/{screening_id}/analyze", headers=auth_headers)

    body = client.get(f"{API}/patients/{patient_id}", headers=auth_headers).json()
    assert len(body["screenings"]) == 1
    assert body["screenings"][0]["risk_band"] in {"low", "moderate", "high"}
    assert body["screenings"][0]["modalities_used"] == ["clinical"]


def test_referral_workflow(client, auth_headers, concerning_vitals):
    patient_id = _create_patient(client, auth_headers)
    screening_id = _create_screening(client, auth_headers, patient_id)
    client.post(
        f"{API}/screenings/{screening_id}/clinical",
        headers=auth_headers,
        json=concerning_vitals,
    )
    client.post(f"{API}/screenings/{screening_id}/analyze", headers=auth_headers)

    res = client.post(
        f"{API}/referrals",
        headers=auth_headers,
        json={
            "screening_id": screening_id,
            "refer_to": "District Hospital",
            "note": "Raised risk; needs clinical assessment.",
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "pending"
    assert len(client.get(f"{API}/referrals", headers=auth_headers).json()) == 1


def test_review_marks_screening_reviewed(client, auth_headers, normal_vitals):
    patient_id = _create_patient(client, auth_headers)
    screening_id = _create_screening(client, auth_headers, patient_id)
    client.post(
        f"{API}/screenings/{screening_id}/clinical",
        headers=auth_headers,
        json=normal_vitals,
    )
    client.post(f"{API}/screenings/{screening_id}/analyze", headers=auth_headers)
    res = client.post(f"{API}/screenings/{screening_id}/review", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "reviewed"


# --------------------------------------------------------------------------
# Row-level access control
# --------------------------------------------------------------------------
def test_health_worker_cannot_see_another_workers_patient(client, auth_headers):
    patient_id = _create_patient(client, auth_headers, name="Private Patient")

    client.post(
        f"{API}/auth/register",
        json={
            "email": "other.worker@example.org",
            "password": "Another-Horse-7!",
            "full_name": "Other Worker",
            "role": "health_worker",
        },
    )
    token = client.post(
        f"{API}/auth/login",
        json={"email": "other.worker@example.org", "password": "Another-Horse-7!"},
    ).json()["access_token"]
    other = {"Authorization": f"Bearer {token}"}

    # 404, not 403 — confirming existence would itself leak information.
    assert client.get(f"{API}/patients/{patient_id}", headers=other).status_code == 404
    assert client.get(f"{API}/patients", headers=other).json() == []


def test_patient_role_cannot_create_patients(client):
    client.post(
        f"{API}/auth/register",
        json={
            "email": "patient.user@example.org",
            "password": "Patient-Horse-3!",
            "full_name": "Patient User",
            "role": "patient",
        },
    )
    token = client.post(
        f"{API}/auth/login",
        json={"email": "patient.user@example.org", "password": "Patient-Horse-3!"},
    ).json()["access_token"]

    res = client.post(
        f"{API}/patients",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Someone Else"},
    )
    assert res.status_code == 403


# --------------------------------------------------------------------------
# Capability transparency
# --------------------------------------------------------------------------
def test_system_models_endpoint_reports_modality_availability(client):
    body = client.get(f"{API}/system/models").json()
    assert body["modalities"]["clinical"]["available"] is True
    # Clinical is always active; every modality reports its signal pipeline and,
    # when unavailable, a reason (never silently defaulted to available).
    assert "clinical" in body["active_modalities"]
    for modality in ("pcg", "ecg"):
        m = body["modalities"][modality]
        assert m["signal_pipeline"] is True
        if not m["available"]:
            assert m["reason"]
    assert "not a diagnosis" in body["disclaimer"].lower()
