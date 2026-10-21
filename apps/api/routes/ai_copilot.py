"""Clinical Advisor & Decision Support REST API Routes."""

import os
from typing import Dict, Any, Tuple
import sqlite3
from apps.api.domains.ai_copilot import HakeemAiCopilot
from apps.api.core.errors import AuthenticationError, ForbiddenError

def handle_ai_query(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Process clinical query through Governed Clinical Decision Support Engine."""
    user = req.get("user")
    if not user:
        raise AuthenticationError("Authentication required to access Clinical Decision Support.")

    roles = set(user.get("roles") or ([user.get("role")] if user.get("role") else []))
    is_clinical = bool(roles.intersection({"HAKEEM", "DOCTOR", "PRACTITIONER", "TABIB", "ADMIN", "SUPER_ADMIN", "ORG_ADMIN"}))
    if not is_clinical:
        raise ForbiddenError("Only registered clinicians may query the clinical decision support engine.")

    body = req.get("body", {})
    query = body.get("query") or req.get("query_params", {}).get("query", "")
    context = body.get("context", {})
    
    result = HakeemAiCopilot.query_ai(query=query, context=context, conn=conn)
    return 200, result

def handle_ai_status(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Returns status of clinical knowledge reference tiers with truthful readiness indicators."""
    user = req.get("user")
    if not user:
        raise AuthenticationError("Authentication required to view system status.")

    gemini_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    status_label = "READY_HYBRID (Cloud Reference & Classical Corpus Active)" if gemini_key else "READY_DETERMINISTIC (Offline Classical Compendia Active)"
    return 200, {
        "status": status_label,
        "gemini_configured": gemini_key,
        "primary_tier": "Governed Clinical RAG / LLM Reference" if gemini_key else "Governed Classical Unani Compendia",
        "fallback_tier": "Classical Unani Compendia Knowledge Base (Al-Qanun, Al-Hawi, NFUM)",
        "safety_firewalls": ["Schedule E(1) Mudabbar", "Herb-Drug Screening", "Colchicine Ceiling", "Zero Autonomous Prescribing Policy"]
    }
