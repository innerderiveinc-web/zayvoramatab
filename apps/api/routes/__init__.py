"""REST API Route handlers."""

from apps.api.routes import (
    health, auth, tenancy, admin, audit, capabilities, patients, encounters,
    formulations, prescriptions, unani_assessment, organ_axis, care_plans,
    modern_assessment, clinical_rules, knowledge, safety_firewall,
    consultation_orchestrator, care_continuity, clinic_operations, enterprise_admin,
    hospital_interop, pilot_launch
)

__all__ = [
    "health",
    "auth",
    "tenancy",
    "admin",
    "audit",
    "capabilities",
    "patients",
    "encounters",
    "formulations",
    "prescriptions",
    "unani_assessment",
    "organ_axis",
    "care_plans",
    "modern_assessment",
    "clinical_rules",
    "knowledge",
    "safety_firewall",
    "consultation_orchestrator",
    "care_continuity",
    "clinic_operations",
    "enterprise_admin",
    "hospital_interop",
    "pilot_launch",
]
