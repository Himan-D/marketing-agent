from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import setup_logging
from app.api.deps import engine, async_session
from app.models.db import Base
from app.api.routes import campaigns, leads, pipeline, emails, webhooks, memory


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Marketing Agent API",
    description="AI-powered marketing agent with Apollo.io, Apify, vLLM, and Twenty CRM",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(campaigns.router)
app.include_router(leads.router)
app.include_router(pipeline.router)
app.include_router(emails.router)
app.include_router(webhooks.router)
app.include_router(memory.router)


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
