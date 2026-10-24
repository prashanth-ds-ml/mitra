from app.agents import registry


def test_get_agent_roles_exposes_phase4_roles():
    roles = registry.get_agent_roles()

    assert [role.key for role in roles] == [
        "planner",
        "prd",
        "task",
        "coder",
        "tester",
        "reviewer",
        "docs",
        "decision",
    ]
    assert roles[0].workflows == ("PlanWorkflow", "NextWorkflow")


def test_resolve_agent_models_prefers_configured_overrides():
    resolved = registry.resolve_agent_models(
        {
            "agent_models": {
                "planner": "custom-planner",
                "coder": "custom-coder",
            }
        },
        chat_model="chat-local",
        codegen_model="cloud-codegen",
        cloud_codegen_enabled=True,
    )

    assert resolved["planner"] == "custom-planner"
    assert resolved["coder"] == "custom-coder"
    assert resolved["reviewer"] == registry.default_agent_models()["reviewer"]


def test_summarize_agent_models_groups_roles():
    summary = registry.summarize_agent_models(
        {
            "planner": "a",
            "prd": "a",
            "task": "a",
            "reviewer": "b",
            "decision": "b",
            "coder": "c",
            "tester": "d",
            "docs": "d",
        }
    )

    assert "planner `a`" in summary
    assert "reviewer `b`" in summary
    assert "coder `c`" in summary
    assert "docs `d`" in summary
