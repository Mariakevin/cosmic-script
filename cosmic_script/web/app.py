"""FastAPI application factory and main app instance."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Cosmic Script API",
    description="Convert free-form text stories into proper screenplay format",
    version="0.1.0",
)

# CORS for local dev (Vite default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


# Include routers
from cosmic_script.web.routers import characters, chapters, conversion, documents, export, analysis

app.include_router(characters.router, prefix="/api")
app.include_router(chapters.router, prefix="/api")
app.include_router(conversion.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
