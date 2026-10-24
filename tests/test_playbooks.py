import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app import playbooks as playbook_registry


def test_repository_playbooks_are_discoverable():
    root = pathlib.Path(__file__).resolve().parents[1]
    playbooks = playbook_registry.discover(str(root))
    names = {playbook.name for playbook in playbooks}

    assert {
        "react-demo",
        "simple-game",
        "fastapi-api",
        "rag-app",
        "langgraph-agent",
        "huggingface-demo",
        "docker-service",
        "full-stack-ai-app",
    }.issubset(names)


def test_find_supports_exact_and_partial_matches():
    root = pathlib.Path(__file__).resolve().parents[1]
    playbooks = playbook_registry.discover(str(root))

    exact = playbook_registry.find(playbooks, "simple-game")
    partial = playbook_registry.find(playbooks, "simple")

    assert exact is not None
    assert exact.name == "simple-game"
    assert partial is not None
    assert partial.name == "simple-game"
