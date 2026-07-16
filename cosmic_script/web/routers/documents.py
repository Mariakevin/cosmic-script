"""Document upload / management routes."""

from __future__ import annotations

import tempfile
import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from cosmic_script.web.schemas import UploadResponse, ErrorResponse
from cosmic_script.ingestion.loader import load_document

router = APIRouter(tags=["documents"])

# Max upload size: 50MB
MAX_UPLOAD_SIZE = 50 * 1024 * 1024
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".epub"}


@router.post(
    "/upload",
    response_model=UploadResponse,
    responses={422: {"model": ErrorResponse}, 413: {"model": ErrorResponse}},
)
async def upload_document(file: UploadFile = File(...)):
    """Upload a document for screenplay conversion.

    Accepts .txt, .md, .pdf, .epub files up to 50MB.
    Returns extracted text with metadata.
    """
    # Validate extension
    filename = file.filename or "unknown.txt"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Read and check size
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {MAX_UPLOAD_SIZE // (1024 * 1024)}MB",
        )

    # Save to temp file and process
    tmp_dir = tempfile.mkdtemp(prefix="cosmic_")
    tmp_path = Path(tmp_dir) / filename
    try:
        tmp_path.write_bytes(content)
        text = load_document(str(tmp_path))

        # Calculate stats
        word_count = len(text.split())
        char_count = len(text)
        char_count_no_spaces = len(text.replace(" ", "").replace("\n", "").replace("\t", ""))

        return UploadResponse(
            filename=filename,
            text=text,
            word_count=word_count,
            char_count=char_count,
            char_count_no_spaces=char_count_no_spaces,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        # Cleanup temp files
        shutil.rmtree(tmp_dir, ignore_errors=True)
