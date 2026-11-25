# ==========================================
# PBL Assignment - Student Management API (FastAPI + SQLite)
# Containerized with Docker, run with docker compose, tested by automationTesting.py,
# built and pushed to Docker Hub by GitHub Actions.
# Run locally:  pip install -r requirements.txt  →  uvicorn main:app --reload
# ==========================================

import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

# ---------- Configuration from environment variables ----------
DATABASE_PATH = os.getenv("DATABASE_PATH", "students.db")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

# ---------- Structured request logging (monitoring) ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("student-api")

app = FastAPI(title="Student Management API", version=APP_VERSION)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info("method=%s path=%s status=%s duration_ms=%.2f",
                request.method, request.url.path, response.status_code, duration_ms)
    return response


# ---------- Database (SQLite from the Python standard library) ----------
@contextmanager
def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row          # rows behave like dictionaries
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    folder = os.path.dirname(DATABASE_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                name   TEXT NOT NULL,
                email  TEXT NOT NULL UNIQUE,
                course TEXT NOT NULL
            )
        """)


init_db()


# ---------- Schemas ----------
class StudentIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, examples=["Aarav"])
    email: EmailStr = Field(..., examples=["aarav@example.com"])
    course: str = Field(..., min_length=2, max_length=100, examples=["Backend Development"])


class Student(StudentIn):
    id: int


def find_student(conn, student_id: int) -> dict:
    row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return dict(row)


# ---------- Routes ----------
@app.get("/")
def root():
    return {"application": "Student Management API", "framework": "FastAPI",
            "version": APP_VERSION, "status": "running"}


@app.get("/health")
def health():
    # also checks that the database can be reached
    with get_connection() as conn:
        conn.execute("SELECT 1")
    return {"status": "healthy"}


@app.get("/students", response_model=List[Student])
def list_students(course: Optional[str] = None):
    with get_connection() as conn:
        if course:
            rows = conn.execute("SELECT * FROM students WHERE course = ? ORDER BY id", (course,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM students ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.get("/students/{student_id}", response_model=Student)
def get_student(student_id: int):
    with get_connection() as conn:
        return find_student(conn, student_id)


@app.post("/students", response_model=Student, status_code=201)
def create_student(data: StudentIn):
    with get_connection() as conn:
        try:
            cursor = conn.execute("INSERT INTO students (name, email, course) VALUES (?, ?, ?)",
                                  (data.name, data.email, data.course))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Email already registered")
        return find_student(conn, cursor.lastrowid)


@app.put("/students/{student_id}", response_model=Student)
def update_student(student_id: int, data: StudentIn):
    with get_connection() as conn:
        find_student(conn, student_id)
        try:
            conn.execute("UPDATE students SET name = ?, email = ?, course = ? WHERE id = ?",
                         (data.name, data.email, data.course, student_id))
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Email already registered")
        return find_student(conn, student_id)


@app.delete("/students/{student_id}", status_code=204)
def delete_student(student_id: int):
    with get_connection() as conn:
        find_student(conn, student_id)
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    return Response(status_code=204)
