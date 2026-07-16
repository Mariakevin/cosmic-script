"""Analysis API routes — coverage, logline, page estimation, genre listing.

Reuses existing analysis functions from ``cosmic_script.analysis`` and
defaults to demo mode when LLM calls fail.
"""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Query

from cosmic_script.models import Screenplay, Scene, ScreenplayElement
from cosmic_script.web.schemas import ErrorResponse

router = APIRouter(tags=["analysis"])

# Thread executor for LLM calls (avoid blocking event loop)
_executor = ThreadPoolExecutor(max_workers=2)

# 5 minute timeout for LLM calls
LLM_TIMEOUT = 300


def _text_to_screenplay(text: str) -> Screenplay:
    """Convert raw text to a minimal Screenplay object.

    Wraps the text in a single demo scene so downstream analysis functions
    have something to work with.  For proper analysis, the text should be
    Fountain-formatted.
    """
    return Screenplay(
        title="Analysis",
        author="System",
        scenes=[Scene(heading="INT. SCENE - DAY", content=text)],
    )


@router.post(
    "/coverage",
    responses={400: {"model": ErrorResponse}, 504: {"model": ErrorResponse}},
)
async def generate_coverage(
    text: str,
    model: str = Query("auto", description="LLM model (auto = automatic fallback)"),
):
    """Generate a professional script coverage report.

    Returns a ScriptCoverage JSON with logline, synopsis, strengths,
    weaknesses, rating, and recommendation.
    """
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text content is required")

    from cosmic_script.analysis.coverage import ScriptCoverage, generate_coverage as _gen_cov

    # Check for demo mode
    demo_mode = os.environ.get("DEMO_MODE", "false").lower() == "true"
    effective_model = "demo" if demo_mode else model

    screenplay = _text_to_screenplay(text)

    try:
        loop = asyncio.get_event_loop()
        coverage = await asyncio.wait_for(
            loop.run_in_executor(
                _executor,
                lambda: _gen_cov(
                    screenplay=screenplay,
                    model=effective_model,
                ),
            ),
            timeout=LLM_TIMEOUT,
        )
        return _coverage_to_dict(coverage)

    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Coverage generation timed out after {LLM_TIMEOUT}s",
        )
    except Exception as e:
        # Fallback to demo on failure
        coverage = _gen_cov(screenplay, model="demo")
        return _coverage_to_dict(coverage)


def _coverage_to_dict(coverage) -> dict:
    """Convert ScriptCoverage dataclass to a JSON-serializable dict."""
    return {
        "logline": coverage.logline,
        "synopsis": coverage.synopsis,
        "strengths": list(coverage.strengths),
        "weaknesses": list(coverage.weaknesses),
        "rating": coverage.rating,
        "recommendation": coverage.recommendation,
        "genre": coverage.genre,
        "target_audience": coverage.target_audience,
        "model_used": coverage.model_used,
    }


@router.post(
    "/logline",
    responses={400: {"model": ErrorResponse}, 504: {"model": ErrorResponse}},
)
async def generate_logline(
    text: str,
    model: str = Query("auto", description="LLM model (auto = automatic fallback)"),
):
    """Generate a one-sentence logline for the provided text.

    Returns ``{ logline: string }``.
    """
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text content is required")

    from cosmic_script.analysis.logline import generate_logline as _gen_log

    # Check for demo mode
    demo_mode = os.environ.get("DEMO_MODE", "false").lower() == "true"
    effective_model = "demo" if demo_mode else model

    screenplay = _text_to_screenplay(text)

    try:
        loop = asyncio.get_event_loop()
        logline = await asyncio.wait_for(
            loop.run_in_executor(
                _executor,
                lambda: _gen_log(
                    screenplay=screenplay,
                    model=effective_model,
                ),
            ),
            timeout=LLM_TIMEOUT,
        )
        return {"logline": logline}

    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Logline generation timed out after {LLM_TIMEOUT}s",
        )
    except Exception as e:
        # Fallback to demo on failure
        logline = _gen_log(screenplay, model="demo")
        return {"logline": logline}


@router.get("/estimate")
async def estimate_pages(
    text: str = Query("", description="Screenplay text to estimate"),
):
    """Estimate the page count for a screenplay.

    Returns a PageEstimate JSON with estimated_pages, total_lines,
    breakdown, and confidence.
    """
    if not text.strip():
        return {
            "estimated_pages": 0.0,
            "total_lines": 0,
            "breakdown": {},
            "confidence": "high",
        }

    from cosmic_script.export.page_estimator import estimate_pages as _est

    screenplay = _text_to_screenplay(text)

    try:
        estimate = _est(screenplay)
        return {
            "estimated_pages": estimate.estimated_pages,
            "total_lines": estimate.total_lines,
            "breakdown": estimate.breakdown,
            "confidence": estimate.confidence,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Page estimation failed: {e}",
        )


@router.get("/genres")
async def list_genres():
    """List available genre presets with names and descriptions.

    Returns a list of objects with ``name`` and ``description`` fields.
    """
    from cosmic_script.conversion.genres import list_genres as _list_genres

    return {"genres": _list_genres()}
