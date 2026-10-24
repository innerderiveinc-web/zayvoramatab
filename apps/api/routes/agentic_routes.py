"""ZAYVORA MATAB OS — Agentic Systems API Route Handlers.
Exposes endpoints for the 4 autonomous clinical & operational pipelines.
Protected with strict session authentication and RBAC.
"""

from typing import Dict, Any, Tuple
import sqlite3
import json

from apps.api.agentic.orchestrator import AgenticOrchestrator
from apps.api.agentic.kavs_agent import KAVSIngestionAgent
from apps.api.agentic.pharmacovigilance_agent import PharmacovigilanceWatchdogAgent
from apps.api.agentic.inventory_agent import FEFORestockAgent
from apps.api.agentic.evidence_agent import ClinicalEvidencePackAgent
from apps.api.core.errors import ValidationError


def handle_get_agentic_status(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """GET /api/v1/agents/status — Returns status of all 4 autonomous pipelines."""
    orchestrator = AgenticOrchestrator(db_path=req.get("db_path"))
    status = orchestrator.get_system_status()
    return 200, status


def handle_run_all_agents(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/agents/run-all — Triggers end-to-end execution across all 4 pipelines."""
    body = req.get("body") or {}
    orchestrator = AgenticOrchestrator(db_path=req.get("db_path"))
    result = orchestrator.run_all(
        facility_id=body.get("facility_id", "fac-central-opd"),
        season=body.get("season", "WINTER"),
        user_id=req.get("user", {}).get("username", "agent-runner")
    )
    return 200, result


def handle_run_kavs_agent(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/agents/kavs/ingest — Executes KAVS book parsing and claim staging."""
    body = req.get("body") or {}
    book_title = body.get("book_title", "Canonical Tibb Compendia")
    author = body.get("author", "Classical Scholar")
    pages = body.get("pages") or [
        {
            "page_number": 1,
            "text": "Mufrad: Suranjan (Colchicum autumnale)\nMizaj: Har wa Yabis dar Darja Saum\nAf'aal: Muhallil-e-Warm\nMudabbar: With Roghan Zard\nBadal: Zafran"
        }
    ]
    agent = KAVSIngestionAgent(db_path=req.get("db_path"))
    res = agent.run_pipeline(
        book_title=book_title,
        author=author,
        raw_text_pages=pages,
        user_id=req.get("user", {}).get("username", "kavs-runner")
    )
    return 200, res


def handle_run_pharmacovigilance_agent(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/agents/pharmacovigilance/scan — Executes safety surveillance watchdog."""
    body = req.get("body") or {}
    agent = PharmacovigilanceWatchdogAgent(db_path=req.get("db_path"))
    res = agent.run_surveillance_pipeline(
        lookback_days=body.get("lookback_days", 30),
        cluster_threshold=body.get("cluster_threshold", 2),
        user_id=req.get("user", {}).get("username", "pv-runner")
    )
    return 200, res


def handle_run_inventory_agent(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/agents/inventory/restock-plan — Executes predictive FEFO restock pipeline."""
    body = req.get("body") or {}
    agent = FEFORestockAgent(db_path=req.get("db_path"))
    res = agent.run_restock_pipeline(
        facility_id=body.get("facility_id", "fac-central-opd"),
        forecast_days=body.get("forecast_days", 15),
        season=body.get("season", "WINTER"),
        user_id=req.get("user", {}).get("username", "inventory-runner")
    )
    return 200, res


def handle_run_evidence_agent(conn: sqlite3.Connection, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/v1/agents/evidence/generate — Synthesizes dual-corpus Clinical Evidence Pack."""
    body = req.get("body") or {}
    condition = body.get("condition") or body.get("diagnosis", "Dyspepsia")
    mizaj = body.get("mizaj", "BALGHAMI")
    agent = ClinicalEvidencePackAgent(db_path=req.get("db_path"))
    res = agent.generate_evidence_pack(
        clinical_condition=condition,
        patient_mizaj=mizaj,
        user_id=req.get("user", {}).get("username", "evidence-runner")
    )
    return 200, res
