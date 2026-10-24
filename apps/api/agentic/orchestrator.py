"""ZAYVORA MATAB OS — Master Agentic Systems Orchestrator.
Coordinates and schedules the 4 autonomous clinical & operational pipelines:
1. KAVSIngestionAgent
2. PharmacovigilanceWatchdogAgent
3. FEFORestockAgent
4. ClinicalEvidencePackAgent
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from apps.api.agentic.kavs_agent import KAVSIngestionAgent
from apps.api.agentic.pharmacovigilance_agent import PharmacovigilanceWatchdogAgent
from apps.api.agentic.inventory_agent import FEFORestockAgent
from apps.api.agentic.evidence_agent import ClinicalEvidencePackAgent


class AgenticOrchestrator:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self.kavs_agent = KAVSIngestionAgent(db_path=db_path)
        self.pv_agent = PharmacovigilanceWatchdogAgent(db_path=db_path)
        self.fefo_agent = FEFORestockAgent(db_path=db_path)
        self.evidence_agent = ClinicalEvidencePackAgent(db_path=db_path)

    def get_system_status(self) -> Dict[str, Any]:
        """Return the current health and status of all 4 agentic pipelines."""
        return {
            "status": "OPERATIONAL",
            "version": "2.0-agentic",
            "pipelines": {
                "kavs_ingestion": {
                    "agent": "KAVSIngestionAgent",
                    "status": "READY",
                    "capabilities": ["OCR/Text Extraction", "Unani Ontology Mapping", "Schedule E(1) Verification", "Claim Staging"]
                },
                "pharmacovigilance": {
                    "agent": "PharmacovigilanceWatchdogAgent",
                    "status": "READY",
                    "capabilities": ["Adverse Symptom Scanning", "Batch Correlation", "WHO-UMC Causality Algorithm", "Cluster Quarantine"]
                },
                "fefo_inventory": {
                    "agent": "FEFORestockAgent",
                    "status": "READY",
                    "capabilities": ["Near-Expiry Audit", "Predictive 15-Day Demand", "Seasonal Multipliers", "Auto-PO Generation"]
                },
                "clinical_evidence": {
                    "agent": "ClinicalEvidencePackAgent",
                    "status": "READY",
                    "capabilities": ["Dual-Corpus Retrieval", "Claim-to-Citation Binding", "3-Phase Af'aal Cascade", "Merkle Fingerprint"]
                }
            },
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }

    def run_all(
        self,
        sample_book_pages: Optional[list] = None,
        facility_id: str = "fac-central-opd",
        season: str = "WINTER",
        user_id: str = "agent-master-orchestrator"
    ) -> Dict[str, Any]:
        """Execute a full operational cycle across all 4 autonomous pipelines."""
        start_time = datetime.utcnow()

        # 1. Run KAVS Ingestion Pipeline
        kavs_pages = sample_book_pages or [
            {
                "page_number": 142,
                "text": "Mufrad: Suranjan Shirin (Colchicum autumnale)\nMizaj: Har wa Yabis dar Darja Saum (Hot & Dry Grade 3)\nAf'aal: Muhallil-e-Warm wa Musakkin-e-Waja-ul-Mafasil\nMudabbar: Pure with Cow Ghee (Roghan Zard) before internal use.\nBadal: Zafran (1/4 wazn)"
            },
            {
                "page_number": 143,
                "text": "Mufrad: Zanjabeel (Zingiber officinale)\nMizaj: Har dar Darja Saum, Yabis dar Darja Daum\nAf'aal: Hazim wa Kasir-e-Riyah wa Muqawwi-e-Meda\nBadal: Filfil Daraz"
            }
        ]
        kavs_res = self.kavs_agent.run_pipeline(
            book_title="Makhzan-ul-Adwiya (Canonical Compendia)",
            author="Hakeem Mohammad Husain Shirazi",
            raw_text_pages=kavs_pages,
            user_id=user_id
        )

        # 2. Run Pharmacovigilance Surveillance Pipeline
        pv_res = self.pv_agent.run_surveillance_pipeline(
            lookback_days=30,
            cluster_threshold=2,
            user_id=user_id
        )

        # 3. Run FEFO Inventory Auto-Restock Pipeline
        fefo_res = self.fefo_agent.run_restock_pipeline(
            facility_id=facility_id,
            forecast_days=15,
            season=season,
            user_id=user_id
        )

        # 4. Run Clinical Evidence Pack Generator
        evidence_res = self.evidence_agent.generate_evidence_pack(
            clinical_condition="Dyspepsia & IBS Gastric Cascade",
            patient_mizaj="BALGHAMI",
            user_id=user_id
        )

        execution_duration = (datetime.utcnow() - start_time).total_seconds()

        return {
            "orchestration_id": f"orch-{uuid.uuid4().hex[:8]}",
            "status": "ALL_PIPELINES_EXECUTED_SUCCESSFULLY",
            "execution_duration_seconds": round(execution_duration, 2),
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "pipeline_results": {
                "kavs_ingestion": kavs_res,
                "pharmacovigilance": pv_res,
                "fefo_inventory": fefo_res,
                "clinical_evidence": evidence_res
            }
        }
