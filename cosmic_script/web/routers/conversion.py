"""Text-to-screenplay conversion routes."""

from __future__ import annotations

import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse
from cosmic_script.web.schemas import (
    ConvertRequest,
    ScreenplayResponse,
    SceneResponse,
    ElementResponse,
    ErrorResponse,
)
from cosmic_script.web.streaming import ProgressEvent, ProgressTracker
from cosmic_script.conversion.pipeline import convert
from cosmic_script.conversion.model_router import get_router
from cosmic_script.models import Screenplay

router = APIRouter(tags=["conversion"])

# Thread executor for LLM calls (avoid blocking event loop)
_executor = ThreadPoolExecutor(max_workers=2)

# 5 minute timeout for LLM calls
LLM_TIMEOUT = 300


def _screenplay_to_response(screenplay: Screenplay) -> ScreenplayResponse:
    """Convert internal Screenplay model to API response."""
    return ScreenplayResponse(
        title=screenplay.title,
        author=screenplay.author,
        scenes=[SceneResponse(heading=s.heading, content=s.content) for s in screenplay.scenes],
        elements=[ElementResponse(type=e.element_type, text=e.text) for e in screenplay.elements],
    )


def _mock_conversion(request: ConvertRequest) -> ScreenplayResponse:
    """Generate a mock screenplay for demo/testing when API is unavailable."""
    lines = request.text.strip().split("\n")[:10]
    text_preview = "\n".join(lines)

    return ScreenplayResponse(
        title=request.title or "Demo Screenplay",
        author=request.author or "Demo Mode",
        scenes=[
            SceneResponse(
                heading="INT. DEMO SCENE - DAY",
                content=f"This is a demo conversion. The LLM API is currently unavailable.\n\nOriginal text preview:\n{text_preview}",
            )
        ],
        elements=[
            ElementResponse(type="scene_heading", text="INT. DEMO SCENE - DAY"),
            ElementResponse(type="action", text="This is a demo conversion."),
            ElementResponse(type="character", text="NARRATOR"),
            ElementResponse(
                type="dialogue", text="The LLM API quota has been exceeded. Please try again later."
            ),
            ElementResponse(
                type="action", text=f"Original text had {len(request.text.split())} words."
            ),
        ],
    )


@router.post(
    "/convert",
    response_model=ScreenplayResponse,
    responses={400: {"model": ErrorResponse}, 504: {"model": ErrorResponse}},
)
async def convert_to_screenplay(request: ConvertRequest):
    """Convert text to screenplay format using LLM with automatic model fallback.

    Models are chosen automatically. The router tries Gemini Flash first,
    then falls back through free OpenRouter models on rate limit or error.
    Set model="demo" for mock conversion without API.
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text content is required")

    # Determine effective model
    demo_mode = os.environ.get("DEMO_MODE", "false").lower() == "true"
    if request.model == "demo" or demo_mode:
        return _mock_conversion(request)

    # Auto: let the router pick the best available model
    effective_model = request.model or "auto"

    try:
        # Run conversion in thread pool with timeout
        loop = asyncio.get_event_loop()
        screenplay = await asyncio.wait_for(
            loop.run_in_executor(
                _executor,
                lambda: convert(
                    text=request.text,
                    model=effective_model,
                    api_key=os.environ.get("GEMINI_API_KEY"),
                    title=request.title or "Untitled",
                    author=request.author or "Unknown",
                    genre=request.genre,
                ),
            ),
            timeout=LLM_TIMEOUT,
        )
        return _screenplay_to_response(screenplay)

    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Conversion timed out after {LLM_TIMEOUT}s. Try with shorter text.",
        )
    except Exception as e:
        # Auto-fallback to demo on API errors
        error_msg = str(e)
        if any(
            code in error_msg
            for code in [
                "429",
                "503",
                "500",
                "UNAVAILABLE",
                "RESOURCE_EXHAUSTED",
                "quota",
                "All models failed",
            ]
        ):
            return _mock_conversion(request)
        raise HTTPException(status_code=500, detail=f"Conversion failed: {error_msg}")


@router.get("/convert/models")
async def list_models():
    """List available LLM models with their status."""
    router = get_router()
    models = router.get_available_models()

    # Add demo mode
    models.append(
        {
            "id": "demo",
            "name": "Demo Mode (No API)",
            "available": True,
            "priority": 99,
        }
    )

    return {"models": models}


@router.post(
    "/convert/stream",
    responses={400: {"model": ErrorResponse}, 504: {"model": ErrorResponse}},
)
async def convert_to_screenplay_stream(request: ConvertRequest):
    """Convert text with SSE progress streaming.

    Returns Server-Sent Events for real-time progress updates.
    Each event contains: type, chapter, total_chapters, message.
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text content is required")

    demo_mode = os.environ.get("DEMO_MODE", "false").lower() == "true"
    if request.model == "demo" or demo_mode:
        # For demo mode, emit mock progress events then return screenplay
        tracker = ProgressTracker()
        tracker.emit(
            ProgressEvent(
                event_type="chapter_start",
                chapter=1,
                total_chapters=1,
                message="Converting chapter 1/1",
            )
        )
        tracker.emit(
            ProgressEvent(
                event_type="chapter_complete",
                chapter=1,
                total_chapters=1,
                message="Chapter 1 complete",
            )
        )
        tracker.emit(
            ProgressEvent(
                event_type="conversion_complete", total_chapters=1, message="All chapters converted"
            )
        )
        events = tracker.get_events()
        sse_data = "".join(e.to_sse() for e in events)
        return StreamingResponse(
            iter([sse_data]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    effective_model = request.model or "auto"
    tracker = ProgressTracker()

    def on_progress(event_type, chapter, total, message):
        tracker.emit(
            ProgressEvent(
                event_type=event_type,
                chapter=chapter,
                total_chapters=total,
                message=message,
            )
        )

    def run_conversion():
        try:
            convert(
                text=request.text,
                model=effective_model,
                api_key=os.environ.get("GEMINI_API_KEY"),
                title=request.title or "Untitled",
                author=request.author or "Unknown",
                genre=request.genre,
                progress_callback=on_progress,
            )
        except Exception:
            tracker.emit(ProgressEvent(event_type="error", message="Conversion failed"))

    thread = threading.Thread(target=run_conversion, daemon=True)
    thread.start()
    thread.join(timeout=LLM_TIMEOUT)

    events = tracker.get_events()
    sse_data = "".join(e.to_sse() for e in events)

    return StreamingResponse(
        iter([sse_data]),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
