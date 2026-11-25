# ==========================================
# PBL Assignment - automated tests for ALL routes of the Student Management API
# The API must be running (uvicorn, docker run or docker compose).
#
# Run:  python automationTesting.py                       (default http://localhost:8000)
#       API_BASE_URL=http://localhost:8080 python automationTesting.py
# Also works with pytest:  pytest automationTesting.py -v
# ==========================================

import os
import sys
import time
import uuid

import requests

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")

# A unique email for every run, so the tests also pass against a database that already has data
UNIQUE = uuid.uuid4().hex[:8]
STUDENT = {"name": "Aarav", "email": f"aarav.{UNIQUE}@example.com", "course": "Backend Development"}


def url(path):
    return f"{BASE_URL}{path}"


def wait_for_api(timeout_seconds=30):
    """Wait until /health answers (useful right after the container starts)."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            if requests.get(url("/health"), timeout=2).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError(f"API at {BASE_URL} did not become healthy in {timeout_seconds}s")


# ---------- Tests (one function per route / behaviour) ----------
def test_root():
    response = requests.get(url("/"), timeout=5)
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health():
    response = requests.get(url("/health"), timeout=5)
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_full_crud_flow():
    # CREATE
    created = requests.post(url("/students"), json=STUDENT, timeout=5)
    assert created.status_code == 201, created.text
    student = created.json()
    student_id = student["id"]
    assert student["email"] == STUDENT["email"]

    # READ one
    one = requests.get(url(f"/students/{student_id}"), timeout=5)
    assert one.status_code == 200
    assert one.json()["name"] == "Aarav"

    # READ all (+ filter)
    all_students = requests.get(url("/students"), timeout=5)
    assert all_students.status_code == 200
    assert any(s["id"] == student_id for s in all_students.json())
    filtered = requests.get(url("/students"), params={"course": "Backend Development"}, timeout=5)
    assert all(s["course"] == "Backend Development" for s in filtered.json())

    # UPDATE
    updated = requests.put(url(f"/students/{student_id}"),
                           json={**STUDENT, "course": "Cloud Computing"}, timeout=5)
    assert updated.status_code == 200
    assert updated.json()["course"] == "Cloud Computing"

    # DELETE
    deleted = requests.delete(url(f"/students/{student_id}"), timeout=5)
    assert deleted.status_code == 204
    assert requests.get(url(f"/students/{student_id}"), timeout=5).status_code == 404


def test_duplicate_email_returns_409():
    email = f"dup.{uuid.uuid4().hex[:8]}@example.com"
    first = requests.post(url("/students"), json={**STUDENT, "email": email}, timeout=5)
    second = requests.post(url("/students"), json={**STUDENT, "email": email}, timeout=5)
    assert first.status_code == 201
    assert second.status_code == 409
    requests.delete(url(f"/students/{first.json()['id']}"), timeout=5)   # clean up


def test_invalid_data_returns_422():
    bad = requests.post(url("/students"), json={"name": "", "email": "not-an-email", "course": "X"}, timeout=5)
    assert bad.status_code == 422


def test_missing_student_returns_404():
    assert requests.get(url("/students/999999"), timeout=5).status_code == 404
    assert requests.put(url("/students/999999"), json=STUDENT, timeout=5).status_code == 404
    assert requests.delete(url("/students/999999"), timeout=5).status_code == 404


TESTS = [test_root, test_health, test_full_crud_flow, test_duplicate_email_returns_409,
         test_invalid_data_returns_422, test_missing_student_returns_404]


if __name__ == "__main__":
    print(f"Testing {BASE_URL}")
    wait_for_api()
    failed = 0
    for test in TESTS:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except Exception as error:          # assertion or connection error
            failed += 1
            print(f"FAIL  {test.__name__}: {error}")
    print(f"\n{len(TESTS) - failed}/{len(TESTS)} tests passed")
    sys.exit(1 if failed else 0)            # non-zero exit code makes GitHub Actions fail
