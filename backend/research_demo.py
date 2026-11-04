"""Local database-free host for the same research router registered in main."""
from fastapi import FastAPI
from routers.research_predictions import router

app=FastAPI(title='AcadMate Sprint 2 research demonstration')
app.include_router(router)

from risk_mvp.router import router as database_research_router
app.include_router(database_research_router)
