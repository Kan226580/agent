from fastapi import FastAPI

app = FastAPI(title="Harness Agent")


@app.get("/health/live")
def health() -> dict[str, str]:
    return {"status": "ok"}
