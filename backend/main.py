from fastapi import FastAPI, HTTPException
from database import SessionLocal
from models import Student

app = FastAPI()


@app.get("/")
def root():
    return {"message": "Acadmate backend is running!"}


@app.get("/api/v1/students/{student_id}")
def get_student(student_id: int):
    db = SessionLocal()

    try:
        student = (
            db.query(Student)
            .filter(Student.student_id == student_id)
            .first()
        )

        if student is None:
            raise HTTPException(
                status_code=404,
                detail="Student not found"
            )

        return {
            "student_id": student.student_id,
            "user_id": student.user_id,
            "name": student.name,
            "email": student.email,
            "program_id": student.program_id
        }

    finally:
        db.close()