#!/usr/bin/env python3
"""ZAYVORA MATAB OS — Autonomous Agentic Pipelines CLI Runner.
Executes multi-step clinical and operational workflows:
  python3 scripts/run_agentic_pipeline.py --all
  python3 scripts/run_agentic_pipeline.py --kavs
  python3 scripts/run_agentic_pipeline.py --pv
  python3 scripts/run_agentic_pipeline.py --inventory
  python3 scripts/run_agentic_pipeline.py --evidence "Dyspepsia"
"""

import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apps.api.agentic.orchestrator import AgenticOrchestrator
from apps.api.agentic.kavs_agent import KAVSIngestionAgent
from apps.api.agentic.pharmacovigilance_agent import PharmacovigilanceWatchdogAgent
from apps.api.agentic.inventory_agent import FEFORestockAgent
from apps.api.agentic.evidence_agent import ClinicalEvidencePackAgent


def main():
    parser = argparse.ArgumentParser(description="ZAYVORA MATAB OS Agentic Pipelines Runner")
    parser.add_argument("--all", action="store_true", help="Execute all 4 autonomous pipelines")
    parser.add_argument("--kavs", action="store_true", help="Run KAVS book parsing and extraction agent")
    parser.add_argument("--pv", action="store_true", help="Run Pharmacovigilance adverse event watchdog")
    parser.add_argument("--inventory", action="store_true", help="Run FEFO predictive restock agent")
    parser.add_argument("--evidence", type=str, help="Generate Clinical Evidence Pack for disease")
    parser.add_argument("--status", action="store_true", help="Print agentic systems operational status")

    args = parser.parse_args()
    orchestrator = AgenticOrchestrator()

    if args.status or (not any([args.all, args.kavs, args.pv, args.inventory, args.evidence])):
        print("🌿 ZAYVORA MATAB OS — Agentic System Status:")
        print(json.dumps(orchestrator.get_system_status(), indent=2))
        return

    if args.all:
        print("🚀 Executing Master Orchestrator across all 4 Agentic Pipelines...")
        result = orchestrator.run_all()
        print(json.dumps(result, indent=2))
        return

    if args.kavs:
        print("📚 Running KAVS Book Ingestion Pipeline...")
        agent = KAVSIngestionAgent()
        res = agent.run_pipeline(
            book_title="Makhzan-ul-Adwiya",
            author="Hakeem Mohammad Husain Shirazi",
            raw_text_pages=[
                {
                    "page_number": 88,
                    "text": "Mufrad: Suranjan (Colchicum autumnale)\nMizaj: Har dar Darja Saum, Yabis dar Darja Saum\nAf'aal: Muhallil-e-Warm wa Musakkin-e-Waja\nMudabbar: Shuddha with Cow Ghee (Roghan Zard)\nBadal: Zafran (1/4 wazn)"
                }
            ]
        )
        print(json.dumps(res, indent=2))

    if args.pv:
        print("🛡️ Running Pharmacovigilance Watchdog Agent...")
        agent = PharmacovigilanceWatchdogAgent()
        res = agent.run_surveillance_pipeline(lookback_days=30, cluster_threshold=2)
        print(json.dumps(res, indent=2))

    if args.inventory:
        print("📦 Running FEFO Predictive Restock Agent...")
        agent = FEFORestockAgent()
        res = agent.run_restock_pipeline(season="WINTER")
        print(json.dumps(res, indent=2))

    if args.evidence:
        print(f"🔬 Synthesizing Clinical Evidence Pack for '{args.evidence}'...")
        agent = ClinicalEvidencePackAgent()
        res = agent.generate_evidence_pack(clinical_condition=args.evidence)
        print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
