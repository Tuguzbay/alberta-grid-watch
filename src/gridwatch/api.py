import pandas as pd
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from gridwatch import db, health, page, rag

app = FastAPI(title="Alberta Grid & Data Centre Watch")


@app.get("/health")
def liveness() -> dict:
    return {"status": "ok"}


def load_summary() -> dict:
    with db.connect() as conn:
        fc = db.forecast_frame(conn)
        last = conn.execute("SELECT max(ts_utc) FROM hourly WHERE pool_price IS NOT NULL")
        last_actual = pd.Timestamp(last.fetchone()[0])
    return health.summary(fc, last_actual, pd.Timestamp.now(tz="UTC"))


@app.get("/api/health")
def model_health() -> dict:
    return load_summary()


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return page.render(load_summary())


class Question(BaseModel):
    q: str = Field(min_length=3, max_length=500)


@app.post("/api/ask")
def ask(body: Question) -> dict:
    """Extracted passages from AESO/AUC/GoA documents with sources, or an abstention."""
    with db.connect() as conn:
        return rag.ask(conn, body.q)
