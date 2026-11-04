from fastapi import FastAPI
from routers import students, research_predictions

app = FastAPI(title="Acadmate API")

app.include_router(students.router)
app.include_router(research_predictions.router)

@app.get("/")
def home():
    return {"message": "Acadmate Backend API is running"}

from risk_mvp.router import router as database_research_router
app.include_router(database_research_router)
