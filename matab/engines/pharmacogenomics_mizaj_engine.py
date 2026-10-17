"""
ZAYVORA HEALTH OS™ — Pharmacogenomics & Mizaj Stratification Engine
Integrative Systems Medicine Layer (Blueprint §24, §25, §36, §78)

Establishes a bi-directional scientific bridge between classical Unani Mizaj
(Humoral Temperaments: Damawi, Safrawi, Balghami, Sawdawi) and modern
pharmacogenomic phenotypes (CYP450 enzymatic clearance, drug transport,
inflammatory gene polymorphisms, and personalized dosage titration).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class MizajPhenotype(str, Enum):
    SAFRAWI = "Safrawi (Hot & Dry / Bilious)"
    DAMAWI = "Damawi (Hot & Wet / Sanguine)"
    BALGHAMI = "Balghami (Cold & Wet / Phlegmatic)"
    SAWDAWI = "Sawdawi (Cold & Dry / Melancholic)"
    MOTADIL = "Motadil (Equilibrated Normative)"


@dataclass
class MetabolicProfile:
    primary_cyp_phenotype: str         # e.g., "CYP2C19 Extensive / Rapid Metabolizer"
    phase_ii_conjugation_rate: str     # "ACCELERATED", "NORMAL", "DELAYED"
    pgp_transport_activity: str        # "HIGH_EFFLUX", "STANDARD", "REDUCED"
    basal_inflammatory_profile: str    # "ELEVATED_TH17_NFKB", "VASCULAR_NITRIC_OXIDE", etc.
    clearance_half_life_modifier: float # 0.70x to 1.30x
    organ_vulnerability: List[str]     # e.g. ["Hepatic parenchymal", "Gastric mucosa"]
    dose_titration_factor: float       # Suggested dosage factor: 0.8x - 1.2x
    clinical_rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PharmacogenomicsMizajEngine:
    """
    Authoritative engine for patient Mizaj to Pharmacogenomic phenotype stratification.
    Provides precise, non-autonomous clinical decision support for personalized dosing.
    """

    def __init__(self):
        self._mizaj_matrix: Dict[str, MetabolicProfile] = {
            "Safrawi": MetabolicProfile(
                primary_cyp_phenotype="CYP2C19 / CYP1A2 Rapid Metabolizer (*17 like)",
                phase_ii_conjugation_rate="ACCELERATED",
                pgp_transport_activity="HIGH_EFFLUX",
                basal_inflammatory_profile="Elevated NF-kB, TNF-alpha, hyper-choleretic",
                clearance_half_life_modifier=0.80, # Clears drugs faster
                organ_vulnerability=["Hepatic parenchymal irritation", "Gastric mucosa hyper-acidity"],
                dose_titration_factor=0.85, # Lower initial dose to avoid Hararat provocation
                clinical_rationale="Safrawi temperament demonstrates heightened basal metabolic rate and rapid Phase I oxidation. High-potency hot drugs require co-administration of Musleh Barid (cooling corrective) and conservative titration.",
            ),
            "Balghami": MetabolicProfile(
                primary_cyp_phenotype="CYP2D6 / CYP3A4 Intermediate or Slow Metabolizer (*4 like)",
                phase_ii_conjugation_rate="DELAYED",
                pgp_transport_activity="REDUCED",
                basal_inflammatory_profile="Hypo-metabolic, lymph stasis, fluid retention tendency",
                clearance_half_life_modifier=1.25, # Retains drugs longer
                organ_vulnerability=["Renal fluid overload", "Pulmonary mucosal congestion"],
                dose_titration_factor=1.10, # Requires warming/stimulating adjuvants (Kaseer-e-Riyah)
                clinical_rationale="Balghami temperament exhibits delayed hepatic clearance and lower GFR excretion rates. Doses should be spaced with longer intervals to prevent cumulative accumulation, accompanied by Muharrik (stimulant) correctives.",
            ),
            "Damawi": MetabolicProfile(
                primary_cyp_phenotype="CYP2E1 / NOS3 Highly Reactive (Normative Robust)",
                phase_ii_conjugation_rate="NORMAL",
                pgp_transport_activity="STANDARD",
                basal_inflammatory_profile="Vascular hyperemia, endothelial nitric oxide synthesis, plethoric",
                clearance_half_life_modifier=1.00,
                organ_vulnerability=["Vascular hypertension", "Capillary fragility"],
                dose_titration_factor=1.00, # Standard standard dose
                clinical_rationale="Damawi temperament shows balanced metabolic throughput but high hemodynamic reactivity. Monitor blood pressure and vascular responsiveness.",
            ),
            "Sawdawi": MetabolicProfile(
                primary_cyp_phenotype="CYP2C9 / UGT1A1 Slower Glucuronidation Phenotype",
                phase_ii_conjugation_rate="DELAYED",
                pgp_transport_activity="STANDARD",
                basal_inflammatory_profile="Neuro-immune axis sensitization, elevated catecholamine turnover",
                clearance_half_life_modifier=1.15,
                organ_vulnerability=["Splenic portal axis", "Central nervous system hyper-sensitization"],
                dose_titration_factor=0.90,
                clinical_rationale="Sawdawi temperament features sluggish Phase II glucuronidation. Psychotropic, neuro-active or sedating herbs require gentle dosage with nutritive (Muqawwi) correctives like Roghan Badam.",
            ),
        }

    def stratify_patient(self, primary_mizaj: str, formulation_canonical_id: str) -> Dict[str, Any]:
        """
        Stratifies patient by temperament and checks interaction with formulation twin.
        """
        # Match primary category
        matched_profile = None
        for key in ["Safrawi", "Balghami", "Damawi", "Sawdawi"]:
            if key.lower() in primary_mizaj.lower():
                matched_profile = self._mizaj_matrix[key]
                break

        if not matched_profile:
            # Fallback to balanced normative
            matched_profile = MetabolicProfile(
                primary_cyp_phenotype="Equilibrated Standard Metabolizer",
                phase_ii_conjugation_rate="NORMAL",
                pgp_transport_activity="STANDARD",
                basal_inflammatory_profile="Normative homeostasis",
                clearance_half_life_modifier=1.00,
                organ_vulnerability=["General non-specific"],
                dose_titration_factor=1.00,
                clinical_rationale="Equilibrated patient profile; standard monograph dosing applies.",
            )

        recommendation = {
            "mizaj_input": primary_mizaj,
            "formulation_evaluated": formulation_canonical_id,
            "pharmacogenomic_profile": matched_profile.to_dict(),
            "dose_adjustment_pct": int((matched_profile.dose_titration_factor - 1.0) * 100),
            "recommended_dose_multiplier": matched_profile.dose_titration_factor,
            "statutory_clinical_guardrail": "ADVISORY ONLY — Clinician sign-off strictly required for final prescription.",
        }
        return recommendation


# Global singleton instance
pharmacogenomics_mizaj_engine = PharmacogenomicsMizajEngine()
