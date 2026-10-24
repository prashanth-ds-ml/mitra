"""Tests for the routing contract and intent router."""

from app import main as main_module
from app.routing import IntentDecision, IntentRouter


class TestIntentRouter:
    def test_build_intent_for_feature_request(self):
        router = IntentRouter()
        decision = router.classify("Build a snake game in React")

        assert decision.intent == "build"
        assert decision.confidence >= 0.9
        assert "feature" in decision.reason.lower()

    def test_fix_intent_for_error_request(self):
        router = IntentRouter()
        decision = router.classify("Why is this error happening in the API?")

        assert decision.intent == "fix"
        assert decision.workflow_hint == "fix"

    def test_review_intent_for_diff_request(self):
        router = IntentRouter()
        decision = router.classify("Review this diff before I merge it")

        assert decision.intent == "review"
        assert decision.workflow_hint == "review"

    def test_test_intent_for_test_request(self):
        router = IntentRouter()
        decision = router.classify("Run pytest and tell me what fails")

        assert decision.intent == "test"
        assert decision.workflow_hint == "test"

    def test_scaffold_intent_for_project_creation(self):
        router = IntentRouter()
        decision = router.classify("Create a new FastAPI project")

        assert decision.intent == "scaffold"
        assert decision.workflow_hint == "scaffold"

    def test_continue_intent_for_next_step_request(self):
        router = IntentRouter()
        decision = router.classify("Continue with the next step")

        assert decision.intent == "continue"
        assert decision.workflow_hint == "continue"

    def test_to_dict_serializes_decision(self):
        decision = IntentDecision("build", 0.92, "feature implementation request", workflow_hint="build")
        payload = decision.to_dict()

        assert payload["intent"] == "build"
        assert payload["confidence"] == 0.92
        assert payload["workflow_hint"] == "build"


class TestMainIntentCompatibility:
    def test_main_classify_intent_routes_build_requests(self):
        assert main_module._classify_intent("Build a snake game in React") == "build"
