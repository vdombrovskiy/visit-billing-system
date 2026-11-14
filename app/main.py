from fastapi import FastAPI

app = FastAPI(title="Visit Billing System")


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": "Welcome to the Visit Billing System!"
    }
