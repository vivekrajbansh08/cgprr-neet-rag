"""FastAPI entry point for the answer service. Endpoints beyond /healthz are not implemented yet."""

from fastapi import FastAPI

app = FastAPI(title="neet-answer")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "answer"}
