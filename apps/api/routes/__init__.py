"""REST API Route handlers."""

from apps.api.routes import health, auth, tenancy, admin, audit, capabilities, patients, encounters, formulations, prescriptions, unani_assessment, organ_axis, care_plans

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
    "care_plans"
]
