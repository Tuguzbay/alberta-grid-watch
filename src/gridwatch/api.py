from fastapi import FastAPI

app = FastAPI(title="Alberta Grid & Data Centre Watch")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
