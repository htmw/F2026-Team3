"""Additive, reviewable risk-data schema. Does not import database.py."""
from sqlalchemy import (Integer,String,Float,Boolean,DateTime,ForeignKey,UniqueConstraint,CheckConstraint)
from sqlalchemy.orm import DeclarativeBase,Mapped,mapped_column
from models import Base as AcademicBase
from datetime import datetime

class Base(DeclarativeBase):pass
# Copy declarations only, not tables/data; existing metadata and source remain untouched.
for table in AcademicBase.metadata.sorted_tables:table.to_metadata(Base.metadata)

class Offering(Base):
    __tablename__='risk_course_offerings'
    id:Mapped[int]=mapped_column(primary_key=True)
    course_id:Mapped[int]=mapped_column(ForeignKey('courses.course_id'))
    term:Mapped[str]=mapped_column(String(50))
    starts_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    ends_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    timezone:Mapped[str]=mapped_column(String(50),default='UTC')
    known_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('course_id','term'),CheckConstraint('ends_at > starts_at'))

class Link(Base):
    __tablename__='risk_enrollment_offerings'
    enrollment_id:Mapped[int]=mapped_column(ForeignKey('enrollments.enrollment_id'),primary_key=True)
    offering_id:Mapped[int]=mapped_column(ForeignKey('risk_course_offerings.id'))
    registered_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    known_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    pattern:Mapped[str]=mapped_column(String(50))

class Assessment(Base):
    __tablename__='risk_assessments'
    id:Mapped[int]=mapped_column(primary_key=True)
    offering_id:Mapped[int]=mapped_column(ForeignKey('risk_course_offerings.id'))
    label:Mapped[str]=mapped_column(String(100))
    kind:Mapped[str]=mapped_column(String(20),default='TMA')

class AssessmentVersion(Base):
    __tablename__='risk_assessment_versions'
    id:Mapped[int]=mapped_column(primary_key=True)
    assessment_id:Mapped[int]=mapped_column(ForeignKey('risk_assessments.id'),index=True)
    version:Mapped[int]=mapped_column()
    due_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    max_score:Mapped[float]=mapped_column()
    known_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)
    __table_args__=(UniqueConstraint('assessment_id','version'),CheckConstraint('max_score > 0'))

class Submission(Base):
    __tablename__='risk_submission_versions'
    id:Mapped[int]=mapped_column(primary_key=True)
    enrollment_id:Mapped[int]=mapped_column(ForeignKey('enrollments.enrollment_id'),index=True)
    assessment_id:Mapped[int]=mapped_column(ForeignKey('risk_assessments.id'))
    version:Mapped[int]=mapped_column()
    submitted_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    known_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)
    grade_available_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    score:Mapped[float|None]=mapped_column(nullable=True)
    status:Mapped[str]=mapped_column(String(20))
    is_banked:Mapped[bool]=mapped_column(default=False)
    __table_args__=(UniqueConstraint('enrollment_id','assessment_id','version'),CheckConstraint('known_at >= submitted_at'),CheckConstraint('score IS NULL OR score >= 0'))

class Activity(Base):
    __tablename__='risk_activity_events'
    id:Mapped[int]=mapped_column(primary_key=True)
    enrollment_id:Mapped[int]=mapped_column(ForeignKey('enrollments.enrollment_id'),index=True)
    source_event_id:Mapped[str]=mapped_column(String(100),unique=True)
    occurred_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),index=True)
    known_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    count:Mapped[int]=mapped_column()
    event_type:Mapped[str]=mapped_column(String(30),default='synthetic_resource_interaction')
    __table_args__=(CheckConstraint('count >= 0'),CheckConstraint('known_at >= occurred_at'))

class Coverage(Base):
    __tablename__='risk_source_coverage'
    id:Mapped[int]=mapped_column(primary_key=True)
    enrollment_id:Mapped[int]=mapped_column(ForeignKey('enrollments.enrollment_id'),index=True)
    source:Mapped[str]=mapped_column(String(20))
    starts_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    through_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    known_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    complete:Mapped[bool]=mapped_column()
    __table_args__=(UniqueConstraint('enrollment_id','source','known_at'),CheckConstraint('through_at >= starts_at'))

class History(Base):
    __tablename__='risk_enrollment_history'
    id:Mapped[int]=mapped_column(primary_key=True)
    enrollment_id:Mapped[int]=mapped_column(ForeignKey('enrollments.enrollment_id'),index=True)
    status:Mapped[str]=mapped_column(String(30))
    grade:Mapped[str|None]=mapped_column(String(5),nullable=True)
    grade_points:Mapped[float|None]=mapped_column(nullable=True)
    effective_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    known_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('enrollment_id','known_at'),)

RISK_TABLES=[t for t in Base.metadata.sorted_tables if t.name.startswith('risk_')]
