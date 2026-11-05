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
    assert resolved["reviewer"] == "chat-local"  # no override: the picked model (E-015)


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


def test_no_role_defaults_to_a_model_the_user_may_not_have():
    """E-015: roles defaulted to qwen3:14b / qwen2.5-coder:14b; a bare /run then hit a 404 from Ollama."""
    resolved = registry.resolve_agent_models({}, chat_model="qwen3.5:4b", codegen_model="", cloud_codegen_enabled=False)

    assert set(resolved.values()) == {"qwen3.5:4b"}
