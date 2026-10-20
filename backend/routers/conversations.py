from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from core.deps import get_current_user
from database import get_db
from models import User
from schemas.messages import (ContactsOut, ConversationListOut, MessageOut, SendIn, StartIn, StartOut, ThreadOut)
from services import messages

router = APIRouter(prefix="/api/v1/conversations", tags=["Messages"])


@router.get("", response_model=ConversationListOut)
def list_conversations(q: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"conversations": messages.list_for(db, user, (q or "").strip() or None)}


@router.get("/contacts", response_model=ContactsOut)
def list_contacts(q: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"contacts": messages.contacts(db, user, (q or "").strip() or None)}


@router.post("", response_model=StartOut, status_code=status.HTTP_201_CREATED)
def start_conversation(body: StartIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"id": messages.start(db, user, body.recipient_ids, body.text, body.title)}


@router.get("/{conversation_id}/messages", response_model=ThreadOut)
def get_messages(conversation_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return messages.thread(db, user, conversation_id)


@router.post("/{conversation_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def send_message(conversation_id: int, body: SendIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return messages.send(db, user, conversation_id, body.text)
