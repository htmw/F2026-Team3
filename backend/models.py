from sqlalchemy import Column, Integer, String, Numeric, Boolean, Enum, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import ARRAY
from datetime import datetime, timezone

Base = declarative_base()   
class Program(Base):
    __tablename__ = "programs"

    program_id = Column(Integer, primary_key=True)
    program_name = Column(String(100), nullable=False)
    total_required_credits = Column(Numeric, nullable=False)

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role= Column(Enum("student", "advisor", "admin", name="user_role"), nullable=False)  # e.g., 'student', 'advisor', 'admin'
    is_active = Column(Boolean, default=True,nullable=False)

class Student(Base):
    __tablename__ = "students"

    student_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), unique=True, nullable=False)  # Foreign key to User
    name = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    program_id = Column(Integer, ForeignKey("programs.program_id"), nullable=False)  # Foreign key to Program

class Course(Base):
    __tablename__ = "courses"

    course_id = Column(Integer, primary_key=True)
    course_code = Column(String(100), unique=True, nullable=False)
    course_name = Column(String(200), nullable=False)
    credits = Column(Numeric, nullable=False)

class Enrollment(Base):
    __tablename__ = "enrollments"

    enrollment_id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.student_id"), nullable=False)  # Foreign key to Student
    course_id = Column(Integer, ForeignKey("courses.course_id"), nullable=False)  # Foreign key to Course
    term = Column(String(50), nullable=False)  # e.g., 'Fall 2026', 'Spring 2026'
    status = Column(Enum("in_progress", "completed", "failed","withdrawn", name="enrollment_status"), nullable=False)  # e.g., 'inprogress', 'completed', 'failed', 'withdrawn'
    grade = Column(String(5), nullable=True)  # e.g., 'A', 'B+', 'C-', etc. (nullable for in-progress courses)
    grade_points = Column(Numeric, nullable=True)  # e.g., 4.0, 3.5, etc. (nullable for in-progress courses)

class Advisor(Base):
    __tablename__ = "advisors"

    advisor_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), unique=True, nullable=False)  # Foreign key to User

class AdvisorStudentAssignment(Base):
    __tablename__ = "advisor_student_assignments"

    student_id = Column(Integer, ForeignKey("students.student_id"),primary_key=True, nullable=False)  # Foreign key to Student
    advisor_id = Column(Integer, ForeignKey("advisors.advisor_id"), nullable=False)  # Foreign key to Advisor
    updated_at = Column(DateTime(timezone=True), nullable=False,default=lambda: datetime.now(timezone.utc))  # Timestamp of the last update

class ProgramRequirement(Base):
    __tablename__ = "program_requirements"

    requirement_id = Column(Integer, primary_key=True)
    program_id = Column(Integer, ForeignKey("programs.program_id"), nullable=False)  # Foreign key to Program
    group_name = Column(String(100), nullable=False)  # Name of the requirement group (e.g., "Core Courses", "Electives")
    required_credits = Column(Numeric, nullable=False)  # Total credits required for this group
    course_ids = Column(ARRAY(Integer), nullable=True)  # List of course IDs that satisfy this requirement
    eligible_courses_ids = Column(ARRAY(Integer), nullable=False)  # List of eligible course IDs for this requirement

