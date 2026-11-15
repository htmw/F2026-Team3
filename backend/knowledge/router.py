"""Read-only authenticated source view for project-help citations."""
from fastapi import APIRouter,Depends
from fastapi.responses import PlainTextResponse
from core.deps import get_current_user
from core.errors import ApiError,not_found
from .project_help import document
router=APIRouter(prefix="/api/v1/help",tags=["Project help"])


@router.get("/documents/{document_id}",response_class=PlainTextResponse)
def source(document_id:str,user=Depends(get_current_user)):
    try:
        entry,text=document(document_id,user.role)
    except LookupError:raise not_found("Project document") from None
    except (ValueError,OSError,KeyError,TypeError):raise ApiError(503,"PROJECT_HELP_UNAVAILABLE","Verified project help unavailable.") from None
    return PlainTextResponse(text,headers={"Cache-Control":"no-store, private","X-Content-Type-Options":"nosniff"})
