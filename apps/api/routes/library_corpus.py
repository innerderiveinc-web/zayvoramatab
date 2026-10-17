"""Grand Classical Library & Corpus REST API Routes."""

from typing import Dict, Any, Tuple
import sqlite3
from apps.api.domains.library_corpus import LibraryCorpusService

def handle_corpus_terms(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    query = req.get("query_params", {}).get("q", "")
    limit = int(req.get("query_params", {}).get("limit", 50))
    terms = LibraryCorpusService.search_standard_terms(conn, query, limit)
    return 200, {"terms": terms, "total": len(terms)}

def handle_corpus_mufradat(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    query = req.get("query_params", {}).get("q", "")
    limit = int(req.get("query_params", {}).get("limit", 50))
    mufradat = LibraryCorpusService.search_mufradat(conn, query, limit)
    return 200, {"mufradat": mufradat, "total": len(mufradat)}

def handle_corpus_sources(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    sources = LibraryCorpusService.list_classical_sources(conn)
    return 200, sources

def handle_corpus_mufrad_detail(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    herb_id = req.get("path_params", {}).get("herb_id", "")
    detail = LibraryCorpusService.get_mufrad_detail(conn, herb_id)
    if not detail:
        return 404, {"ok": False, "error": f"Mufrad '{herb_id}' not found in canonical pharmacopoeia"}
    return 200, {"ok": True, "monograph": detail}

