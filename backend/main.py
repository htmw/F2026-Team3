from fastapi import FastAPI
from routers import students

app = FastAPI(title="Acadmate API")

app.include_router(students.router)

@app.get("/")
def home():
    return {"message": "Acadmate Backend API is running"}
