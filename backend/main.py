from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def root():
    return {"message": "Acadmate backEnd is running!"}