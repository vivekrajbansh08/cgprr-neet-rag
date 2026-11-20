"""FastAPI entry point for the predictor service. Endpoints beyond /healthz are not implemented yet."""

from fastapi import FastAPI

app = FastAPI(title="neet-predictor")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "predictor"}
