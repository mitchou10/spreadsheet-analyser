from fastapi import FastAPI

app = FastAPI(title="spreadsheet-analyser backend")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
