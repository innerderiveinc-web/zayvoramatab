"""Master Clinical System Domain Engine.
ZAYVORA MATAB OS — Classical Unani & Modern Systems Medicine.

Enforces:
1. 12-Axis Diagnostic Matrix & 0-5 Patient Scoring.
2. 21 Master Clinical Protocols (P-01 to P-21) with 3-Phase Afaal Cascade.
3. 21 Bundled Protocol Kits (K-01 to K-21).
4. 8 Master Parhez & Lifestyle Prescriptions.
5. Real-Time Herb-Drug Safety Screening & Contraindications.
"""

import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import sqlite3

from apps.api.database.connection import DatabaseConnection
from apps.api.core.errors import NotFoundError, ValidationError, ForbiddenError


class MasterClinicalService:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_connection(self):
        return DatabaseConnection(self.db_path).get_connection()

    def get_organ_axes(self) -> List[Dict[str, Any]]:
        """Retrieve all 12 Organ Axes with classical-to-modern mapping."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, arabic_name, body_system, governing_power, key_diseases, primary_products, regulatory_track, description
                FROM master_organ_axes
                ORDER BY id ASC;
            """)
            axes = []
            for r in cur.fetchall():
                axes.append({
                    "id": r["id"],
                    "arabic_name": r["arabic_name"],
                    "body_system": r["body_system"],
                    "governing_power": r["governing_power"],
                    "key_diseases": r["key_diseases"],
                    "primary_products": r["primary_products"],
                    "regulatory_track": r["regulatory_track"],
                    "description": r["description"]
                })
            return axes
        finally:
            conn.close()

    def score_axes(self, scores: Dict[str, int]) -> Dict[str, Any]:
        """Score patient across all 12 axes (0-5 scale).
        Calculates Primary Axis (highest score) and Secondary Axis (2nd highest).
        Recommends clinical protocols and kit matches.
        """
        # Validate scores
        valid_scores = {}
        for axis_id, val in scores.items():
            try:
                v = int(val)
                if 0 <= v <= 5:
                    valid_scores[axis_id] = v
            except (ValueError, TypeError):
                continue

        if not valid_scores:
            raise ValidationError("At least one axis score (0-5) must be provided.")

        sorted_axes = sorted(valid_scores.items(), key=lambda x: x[1], reverse=True)
        primary_axis = sorted_axes[0][0] if len(sorted_axes) > 0 else None
        primary_score = sorted_axes[0][1] if len(sorted_axes) > 0 else 0

        secondary_axis = sorted_axes[1][0] if len(sorted_axes) > 1 and sorted_axes[1][1] > 0 else None
        secondary_score = sorted_axes[1][1] if len(sorted_axes) > 1 else 0

        # Find matching protocols for primary axis
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id, name, category, organ_axis, phase1, phase2, phase3, product_stack, lab_monitoring, clinical_warnings FROM master_protocols;")
            all_protocols = cur.fetchall()

            matched_protocols = []
            for p in all_protocols:
                p_axis = p["organ_axis"] or ""
                # Match primary or secondary
                if primary_axis and primary_axis.lower() in p_axis.lower():
                    matched_protocols.append({
                        "id": p["id"],
                        "name": p["name"],
                        "category": p["category"],
                        "organ_axis": p["organ_axis"],
                        "match_type": "PRIMARY",
                        "phase1": p["phase1"],
                        "phase2": p["phase2"],
                        "phase3": p["phase3"],
                        "product_stack": p["product_stack"],
                        "lab_monitoring": p["lab_monitoring"],
                        "clinical_warnings": p["clinical_warnings"]
                    })
                elif secondary_axis and secondary_axis.lower() in p_axis.lower():
                    matched_protocols.append({
                        "id": p["id"],
                        "name": p["name"],
                        "category": p["category"],
                        "organ_axis": p["organ_axis"],
                        "match_type": "SECONDARY",
                        "phase1": p["phase1"],
                        "phase2": p["phase2"],
                        "phase3": p["phase3"],
                        "product_stack": p["product_stack"],
                        "lab_monitoring": p["lab_monitoring"],
                        "clinical_warnings": p["clinical_warnings"]
                    })

            # Fetch matching kit
            cur.execute("SELECT kit_code, name, products_included, indication, price_min_inr, price_max_inr, regulatory_track FROM protocol_kits;")
            all_kits = [dict(r) for r in cur.fetchall()]

            return {
                "scored_axes": valid_scores,
                "ranking": [{"axis": a, "score": s} for a, s in sorted_axes],
                "primary_axis": primary_axis,
                "primary_score": primary_score,
                "secondary_axis": secondary_axis,
                "secondary_score": secondary_score,
                "recommended_protocols": matched_protocols,
                "all_kits": all_kits,
                "clinical_rule": "Always treat PRIMARY AXIS first. Add SECONDARY AXIS support in Phase 2. Cover both in Phase 3 maintenance."
            }
        finally:
            conn.close()

    def get_protocols(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all 21 Master Clinical Protocols."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            query = "SELECT id, name, category, organ_axis, icd11_code, primary_humor, phase1, phase2, phase3, product_stack, lab_monitoring, clinical_warnings FROM master_protocols"
            params = []
            if category:
                query += " WHERE category = ?"
                params.append(category)
            query += " ORDER BY id ASC;"

            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_protocol_by_id(self, protocol_id: str) -> Dict[str, Any]:
        """Fetch complete clinical protocol by ID (e.g. P-01 to P-21)."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM master_protocols WHERE id = ?;", (protocol_id,))
            r = cur.fetchone()
            if not r:
                raise NotFoundError(f"Protocol not found: {protocol_id}")
            return dict(r)
        finally:
            conn.close()

    def get_protocol_kits(self) -> List[Dict[str, Any]]:
        """List all 21 Protocol Kits (K-01 to K-21)."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM protocol_kits ORDER BY kit_code ASC;")
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_parhez_protocols(self) -> List[Dict[str, Any]]:
        """List all 8 master Parhez & lifestyle protocols."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT code, name, classical_principle, target_axes, duration_days, rules FROM master_parhez ORDER BY code ASC;")
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_parhez_by_code(self, code: str) -> Dict[str, Any]:
        """Fetch single Parhez protocol by code (e.g. MF-01, PC-01, TM-01)."""
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM master_parhez WHERE code = ?;", (code,))
            r = cur.fetchone()
            if not r:
                raise NotFoundError(f"Parhez protocol not found: {code}")
            return dict(r)
        finally:
            conn.close()

    def check_herb_drug_safety(self, herbs: List[str], prescription_drugs: List[str]) -> List[Dict[str, Any]]:
        """Check proposed herbs against patient's current prescription drugs for real-time safety alerts."""
        if not herbs or not prescription_drugs:
            return []

        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM herb_drug_interactions;")
            all_rules = cur.fetchall()

            alerts = []
            for rule in all_rules:
                r_herb = rule["herb_name"].lower()
                r_drugs = rule["specific_drugs"].lower()
                r_class = rule["drug_class"].lower()

                # Check if herb matches
                herb_matched = any(h.strip().lower() in r_herb or r_herb in h.strip().lower() for h in herbs if h)
                if not herb_matched:
                    continue

                # Clinical drug class mapping
                ANTIHYPERTENSIVES = {"amlodipine", "losartan", "telmisartan", "metoprolol", "atenolol", "enalapril", "ramipril", "nifedipine", "hydrochlorothiazide"}
                ANTICOAGULANTS = {"warfarin", "aspirin", "clopidogrel", "rivaroxaban", "apixaban", "heparin"}
                ANTIDEPRESSANTS = {"fluoxetine", "sertraline", "escitalopram", "paroxetine", "citalopram", "duloxetine", "venlafaxine"}
                SEDATIVES = {"diazepam", "alprazolam", "zolpidem", "clonazepam", "lorazepam"}
                THYROID = {"levothyroxine", "thyroxine", "eltroxin", "carbimazole"}

                # Check if drug matches
                drug_matched = False
                matched_drug_name = ""
                for med in prescription_drugs:
                    med_l = med.strip().lower()
                    if (med_l in r_drugs or med_l in r_class or 
                        any(d.strip() in med_l for d in r_drugs.split(",") if len(d.strip()) > 2) or
                        ("antihypertensive" in r_class and any(ah in med_l for ah in ANTIHYPERTENSIVES)) or
                        ("anticoagulant" in r_class and any(ac in med_l for ac in ANTICOAGULANTS)) or
                        ("antidepressant" in r_class and any(ad in med_l for ad in ANTIDEPRESSANTS)) or
                        ("sedative" in r_class and any(sd in med_l for sd in SEDATIVES)) or
                        ("thyroid" in r_class and any(th in med_l for th in THYROID))):
                        drug_matched = True
                        matched_drug_name = med
                        break

                if herb_matched and drug_matched:
                    alerts.append({
                        "herb": rule["herb_name"],
                        "drug_class": rule["drug_class"],
                        "matched_medication": matched_drug_name,
                        "interaction": rule["interaction_description"],
                        "severity": rule["severity"],
                        "management_protocol": rule["management_protocol"]
                    })

            return alerts
        finally:
            conn.close()
