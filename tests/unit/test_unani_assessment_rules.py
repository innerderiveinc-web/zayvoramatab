"""Unit Tests: Unani Assessment Rules, Semantic States, Provenance, and Care Plan Lifecycles."""

import unittest
from apps.api.domains.unani_assessment import (
    VALID_DOMINANT_MIZAJ,
    VALID_MIZAJ_UNCERTAINTY,
    VALID_SEMANTIC_STATES,
    VALID_PROVENANCES,
    VALID_CERTAINTIES
)
from apps.api.domains.organ_axis import (
    VALID_RELATIONSHIPS,
    VALID_EVIDENCE_LEVELS,
    VALID_MAPPING_STATUSES
)
from apps.api.domains.care_plans import (
    VALID_CARE_PLAN_STATUSES,
    ALLOWED_CARE_PLAN_TRANSITIONS,
    VALID_OUTCOME_STATUSES
)

class TestUnaniAssessmentRules(unittest.TestCase):
    def test_mizaj_taxonomy_validation(self):
        """Mizaj vocabulary must strictly allow recognized temperaments plus honest uncertainty states."""
        self.assertIn("DAMAWWI", VALID_DOMINANT_MIZAJ)
        self.assertIn("BALGHAMI", VALID_DOMINANT_MIZAJ)
        self.assertIn("SAFRAWI", VALID_DOMINANT_MIZAJ)
        self.assertIn("SAUDAWI", VALID_DOMINANT_MIZAJ)
        self.assertIn("MOTADIL", VALID_DOMINANT_MIZAJ)
        self.assertIn("NOT_ASSESSED", VALID_DOMINANT_MIZAJ)
        self.assertIn("UNCERTAIN", VALID_DOMINANT_MIZAJ)
        self.assertIn("MIXED", VALID_DOMINANT_MIZAJ)

        # Arbitrary classifications must not be present
        self.assertNotIn("FIRE", VALID_DOMINANT_MIZAJ)
        self.assertNotIn("WATERY", VALID_DOMINANT_MIZAJ)
        self.assertNotIn("PITA", VALID_DOMINANT_MIZAJ)

    def test_mizaj_uncertainty_vocabulary(self):
        """Uncertainty states must support calibrated clinical confidence levels."""
        self.assertIn("HIGH_CONFIDENCE", VALID_MIZAJ_UNCERTAINTY)
        self.assertIn("MODERATE_CONFIDENCE", VALID_MIZAJ_UNCERTAINTY)
        self.assertIn("UNCERTAIN", VALID_MIZAJ_UNCERTAINTY)
        self.assertIn("PROVISIONAL", VALID_MIZAJ_UNCERTAINTY)
        self.assertIn("NOT_ASSESSED", VALID_MIZAJ_UNCERTAINTY)

    def test_semantic_states_and_provenance(self):
        """Observations must distinguish data from interpretation and record explicit unknown states."""
        self.assertIn("OBSERVED", VALID_SEMANTIC_STATES)
        self.assertIn("NORMAL", VALID_SEMANTIC_STATES)
        self.assertIn("IMPAIRED", VALID_SEMANTIC_STATES)
        self.assertIn("UNKNOWN", VALID_SEMANTIC_STATES)
        self.assertIn("NOT_ASKED", VALID_SEMANTIC_STATES)
        self.assertIn("NOT_ASSESSED", VALID_SEMANTIC_STATES)
        self.assertIn("NOT_APPLICABLE", VALID_SEMANTIC_STATES)

        self.assertIn("PATIENT_REPORTED", VALID_PROVENANCES)
        self.assertIn("CLINICIAN_OBSERVED", VALID_PROVENANCES)
        self.assertIn("MEASURED", VALID_PROVENANCES)
        self.assertIn("IMPORTED", VALID_PROVENANCES)
        self.assertIn("AI_DRAFTED", VALID_PROVENANCES)

    def test_organ_axis_relationship_semantics(self):
        """Organ-Axis relationships must not assert direct medical causation without explicit review."""
        self.assertIn("ASSOCIATED_WITH", VALID_RELATIONSHIPS)
        self.assertIn("TRADITIONALLY_RELATED_TO", VALID_RELATIONSHIPS)
        self.assertIn("MAY_PROMPT_REVIEW_OF", VALID_RELATIONSHIPS)
        self.assertIn("NOT_EQUIVALENT_TO", VALID_RELATIONSHIPS)
        # Unqualified causal claim is strictly prohibited
        self.assertNotIn("CAUSES", VALID_RELATIONSHIPS)

        self.assertIn("REVIEWED", VALID_EVIDENCE_LEVELS)
        self.assertIn("HISTORICAL_BENCHMARK", VALID_EVIDENCE_LEVELS)
        self.assertIn("UNREVIEWED", VALID_EVIDENCE_LEVELS)

    def test_care_plan_lifecycle_transitions(self):
        """Care plans must transition only through allowed states and cannot mutate once completed."""
        # DRAFT transitions
        self.assertIn("ACTIVE", ALLOWED_CARE_PLAN_TRANSITIONS["DRAFT"])
        self.assertIn("PROPOSED", ALLOWED_CARE_PLAN_TRANSITIONS["DRAFT"])
        self.assertIn("DISCONTINUED", ALLOWED_CARE_PLAN_TRANSITIONS["DRAFT"])

        # ACTIVE transitions
        self.assertIn("COMPLETED", ALLOWED_CARE_PLAN_TRANSITIONS["ACTIVE"])
        self.assertIn("DISCONTINUED", ALLOWED_CARE_PLAN_TRANSITIONS["ACTIVE"])
        self.assertIn("SUPERSEDED", ALLOWED_CARE_PLAN_TRANSITIONS["ACTIVE"])

        # COMPLETED is terminal
        self.assertEqual(len(ALLOWED_CARE_PLAN_TRANSITIONS["COMPLETED"]), 0)

        # Outcomes vocabulary
        self.assertIn("ACHIEVED", VALID_OUTCOME_STATUSES)
        self.assertIn("PARTIALLY_ACHIEVED", VALID_OUTCOME_STATUSES)
        self.assertIn("NOT_ACHIEVED", VALID_OUTCOME_STATUSES)
        self.assertIn("ADVERSE_REACTION", VALID_OUTCOME_STATUSES)

if __name__ == "__main__":
    unittest.main()
