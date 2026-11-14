from fastapi import FastAPI

from app.modules.visits.api.router import router as visits_router

app = FastAPI(title="Visit Billing System")

app.include_router(visits_router)

@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": "Welcome to the Visit Billing System!"
    }
