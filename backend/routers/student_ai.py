from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from core.deps import get_current_student
from database import get_db
from models import Student
from schemas.ai import (AiContextOut, AskIn, CreateThreadOut, FlagIn, FlagOut, RatingIn, ReplyOut, ThreadDetailOut,
                        ThreadListOut)
from services import ai
from services.ai import context, threads

router = APIRouter(prefix="/api/v1/students/me/ai", tags=["AI advisor"])


@router.get("/context", response_model=AiContextOut)
def get_context(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    return context.student_context(db, student)


@router.get("/threads", response_model=ThreadListOut)
def list_threads(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    return {"threads": threads.list_threads(db, student)}


@router.delete("/threads", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_threads(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    threads.delete_all(db, student)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/threads", response_model=CreateThreadOut, status_code=status.HTTP_201_CREATED)
def create_thread(body: AskIn, student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    thread, question, reply = ai.ask(db, student, body.text)
    return {"thread": threads.thread_out(thread),
            "messages": [threads.message_out(question), threads.message_out(reply)]}


@router.get("/threads/{thread_id}", response_model=ThreadDetailOut)
def get_thread(thread_id: int, student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    return threads.thread_detail(db, student, thread_id)


@router.post("/threads/{thread_id}/messages", response_model=ReplyOut)
def ask_in_thread(thread_id: int, body: AskIn, student: Student = Depends(get_current_student),
                  db: Session = Depends(get_db)):
    _, question, reply = ai.ask(db, student, body.text, thread_id)
    return {"user_message": threads.message_out(question), "reply": threads.message_out(reply)}


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(thread_id: int, student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    threads.delete_thread(db, student, thread_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/messages/{message_id}/rating", status_code=status.HTTP_204_NO_CONTENT)
def rate_message(message_id: int, body: RatingIn, student: Student = Depends(get_current_student),
                 db: Session = Depends(get_db)):
    threads.rate(db, student, message_id, body.helpful)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/messages/{message_id}/flag", response_model=FlagOut, status_code=status.HTTP_201_CREATED)
def flag_message(message_id: int, body: FlagIn, student: Student = Depends(get_current_student),
                 db: Session = Depends(get_db)):
    return {"id": threads.flag(db, student, message_id, body.issue)}
