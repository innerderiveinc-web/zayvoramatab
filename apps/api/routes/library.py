"""Medical Library & Compendia API Route Handlers.
Compatible with ApiRouter dispatch: handle_xxx(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]].
"""

from typing import Dict, Any, Tuple, Optional
import sqlite3

from apps.api.domains.library import MedicalLibraryService
from apps.api.core.permissions import require_permission
from apps.api.core.errors import ValidationError, NotFoundError, ForbiddenError


def _get_service(req: Dict[str, Any] = None) -> MedicalLibraryService:
    db_path = req.get("db_path") if req else None
    return MedicalLibraryService(db_path=db_path)


def handle_library_stats(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/library/stats"""
    svc = _get_service(req)
    stats = svc.get_library_stats()
    return 200, stats


def handle_library_books_list(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/library/books"""
    params = req.get("query_params", {})
    query = params.get("q", "")
    category = params.get("category", "")
    language = params.get("language", "")
    try:
        limit = int(params.get("limit", 50))
    except (ValueError, TypeError):
        limit = 50
    try:
        offset = int(params.get("offset", 0))
    except (ValueError, TypeError):
        offset = 0

    if limit > 200:
        limit = 200

    svc = _get_service(req)
    result = svc.search_books(
        query=query,
        category=category,
        language=language,
        limit=limit,
        offset=offset
    )
    return 200, result


def handle_library_book_detail(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/library/books/{book_id}"""
    book_id = req.get("path_params", {}).get("book_id") or req.get("params", {}).get("book_id", "")
    svc = _get_service(req)
    book = svc.get_book_by_id(book_id)
    return 200, {"book": book}


def handle_library_reindex(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/library/reindex"""
    user = req.get("user")
    if not user or user.get("role") not in ("ADMIN", "ORG_ADMIN", "HAKEEM", "TABIB", "PRACTITIONER"):
        raise ForbiddenError("Only authorized clinical staff or administrators can reindex library sources.")

    svc = _get_service(req)
    res = svc.index_downloaded_books()
    return 200, res


def handle_library_book_view(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, str], bytes]:
    """GET /api/v1/library/books/{book_id}/view
    Streams or renders the requested medical compendium PDF/book file with HTTP Range support.
    """
    import os
    import re

    book_id = req.get("path_params", {}).get("book_id") or req.get("query_params", {}).get("book_id", "")
    if not book_id:
        raise ValidationError("Missing book_id parameter.")

    svc = _get_service(req)
    book = svc.get_book_by_id(book_id)
    filename = book.get("filename", "")

    # Multi-environment path resolution for portable live server deployment:
    from apps.api.config import config, BASE_DIR
    configured_dir = getattr(config, "books_dir", None) or os.getenv("MATAB_BOOKS_DIR")
    candidates = []
    if configured_dir:
        candidates.append(os.path.join(configured_dir, filename))
    candidates.append(os.path.join(str(BASE_DIR), "data", "medical_books", filename))
    candidates.append(os.path.join(str(BASE_DIR), "medical_books", filename))
    if book.get("file_path"):
        candidates.append(book["file_path"])
    candidates.append(os.path.join("/Users/irfanashraf/Downloads/medical books", filename))

    fpath = None
    for cand in candidates:
        if cand and os.path.exists(cand):
            fpath = cand
            break

    if not fpath:
        raise NotFoundError(
            f"Medical compendium file '{filename}' was not found on server storage. "
            f"Ensure books are uploaded to '{configured_dir or './data/medical_books'}' or set MATAB_BOOKS_DIR in .env."
        )

    file_size = os.path.getsize(fpath)
    ext = os.path.splitext(fpath)[1].lower()

    raw_fname = os.path.basename(fpath)
    import urllib.parse
    clean_ascii_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', raw_fname).strip('_')
    base_no_ext = os.path.splitext(clean_ascii_name)[0].strip('_.')
    if not base_no_ext:
        code_slug = re.sub(r'[^a-zA-Z0-9_\-]', '_', book.get("code") or book_id).strip('_')
        clean_ascii_name = f"{code_slug}{ext}"
    encoded_utf8_name = urllib.parse.quote(raw_fname)

    if ext == ".pdf":
        content_type = "application/pdf"
        disp_kind = "inline"
    elif ext in [".rar", ".zip", ".tar", ".gz", ".7z"]:
        content_type = "application/octet-stream"
        disp_kind = "attachment"
    elif ext in [".txt", ".md"]:
        content_type = "text/plain; charset=utf-8"
        disp_kind = "inline"
    else:
        content_type = "application/octet-stream"
        disp_kind = "inline"

    disposition = f'{disp_kind}; filename="{clean_ascii_name}"; filename*=UTF-8\'\'{encoded_utf8_name}'

    # Handle HTTP Range requests for smooth PDF streaming and low memory footprint
    range_header = req.get("headers", {}).get("range") or req.get("headers", {}).get("Range")
    if range_header:
        range_match = re.match(r"^bytes=(\d+)-(\d*)$", range_header.strip())
        if range_match:
            start = int(range_match.group(1))
            end_str = range_match.group(2)
            end = int(end_str) if end_str else file_size - 1
            if end >= file_size:
                end = file_size - 1

            if start <= end and start < file_size:
                chunk_len = end - start + 1
                with open(fpath, "rb") as f:
                    f.seek(start)
                    chunk = f.read(chunk_len)

                headers = {
                    "Content-Type": content_type,
                    "Content-Disposition": disposition,
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(len(chunk)),
                    "Accept-Ranges": "bytes",
                    "Cache-Control": "public, max-age=86400",
                    "X-Frame-Options": "SAMEORIGIN"
                }
                return 206, headers, chunk

    with open(fpath, "rb") as f:
        data = f.read()

    headers = {
        "Content-Type": content_type,
        "Content-Disposition": disposition,
        "Content-Length": str(len(data)),
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=86400",
        "X-Frame-Options": "SAMEORIGIN"
    }
    return 200, headers, data

