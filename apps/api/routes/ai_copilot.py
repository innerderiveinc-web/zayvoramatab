"""Clinical Advisor & Decision Support REST API Routes."""

import os
from typing import Dict, Any, Tuple
import sqlite3
from apps.api.domains.ai_copilot import HakeemAiCopilot

def handle_ai_query(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Process clinical query through Clinical Decision Support Engine (Verified Literature / Classical Reference)."""
    body = req.get("body", {})
    query = body.get("query") or req.get("query_params", {}).get("query", "")
    context = body.get("context", {})
    
    result = HakeemAiCopilot.query_ai(query=query, context=context, conn=conn)
    return 200, result

def handle_ai_status(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Returns status of clinical knowledge reference tiers."""
    gemini_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    return 200, {
        "status": "ONLINE",
        "primary_tier": "Verified Online Medical Literature",
        "gemini_configured": gemini_key,
        "fallback_tier": "Classical Unani Compendia Knowledge Base",
        "safety_firewalls": ["Schedule E(1) Mudabbar", "Herb-Drug Screening", "Colchicine Ceiling"]
    }
