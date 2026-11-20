"""FastAPI entry point for the retrieval service. Endpoints beyond /healthz are not implemented yet."""

from fastapi import FastAPI

app = FastAPI(title="neet-retrieval")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "retrieval"}
