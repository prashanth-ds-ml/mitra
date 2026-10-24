"""Tests for app.builder — guided artifact creation wizard (pure logic only)."""
from __future__ import annotations

import pathlib
import types

import pytest

from app import builder


# ── Fixtures ──────────────────────────────────────────────────────────────────

SKILL_ANSWERS = {
    "name": "Django Model Creator",
    "goal": "Generates Django model classes from a plain-English description.",
    "trigger": "When the user asks to create a Django model or database table.",
    "stack": "python",
    "rules": "- Always add __str__\n- Use verbose_name\n- Add docstring",
    "workflow_hint": "",
    "output_format": "code",
}

WORKFLOW_ANSWERS = {
    "name": "PR Prep Checklist",
    "goal": "Ensure the code is clean, tested, and documented before opening a PR.",
    "trigger": "Before opening a pull request or merging a feature branch.",
    "steps_raw": "/review\n/fix pytest\nUpdate CHANGELOG\nVerify docs",
    "cadence": "per-pr",
    "notes": "Run on a feature branch, never on main.",
}

AGENT_ANSWERS = {
    "name": "Database Inspector",
    "goal": "Queries the database schema and returns table/column information.",
    "tools": "run SQL queries\nread schema files",
    "trigger": "When the user asks about database tables, columns, or schema.",
    "language": "python",
    "output": "Schema summary as Markdown table.",
}


# ── slugify ───────────────────────────────────────────────────────────────────

class TestSlugify:
    def test_simple(self):
        assert builder.slugify("My Skill") == "my-skill"

    def test_already_slug(self):
        assert builder.slugify("test-generator") == "test-generator"

    def test_special_chars_stripped(self):
        assert builder.slugify("API (v2) Writer!") == "api-v2-writer"

    def test_underscores_to_dashes(self):
        assert builder.slugify("my_new_skill") == "my-new-skill"

    def test_empty_fallback(self):
        assert builder.slugify("") == "my-skill"

    def test_multiple_spaces(self):
        assert builder.slugify("  lots   of   spaces  ") == "lots-of-spaces"

    def test_uppercase(self):
        assert builder.slugify("Django Model Creator") == "django-model-creator"


# ── extract_content ───────────────────────────────────────────────────────────

class TestExtractContent:
    def test_markdown_fence(self):
        raw = "Here is your skill:\n```markdown\n---\nname: x\n---\n# Title\n```\nDone."
        assert builder.extract_content(raw) == "---\nname: x\n---\n# Title"

    def test_python_fence(self):
        raw = "```python\ndef hello():\n    pass\n```"
        assert builder.extract_content(raw) == "def hello():\n    pass"

    def test_bare_fence(self):
        raw = "```\ncontent here\n```"
        assert builder.extract_content(raw) == "content here"

    def test_no_fence_returns_raw(self):
        raw = "Just plain text, no fences."
        assert builder.extract_content(raw) == raw.strip()

    def test_strips_whitespace(self):
        raw = "```markdown\n\n  padded  \n\n```"
        assert builder.extract_content(raw) == "padded"


# ── extract_wiring_instructions ───────────────────────────────────────────────

class TestExtractWiringInstructions:
    def test_finds_section(self):
        raw = "```python\ncode\n```\n\n## 📋 Wiring instructions\n1. Import it\n2. Add route\n"
        result = builder.extract_wiring_instructions(raw)
        assert "Import it" in result

    def test_case_insensitive(self):
        raw = "## WIRING INSTRUCTIONS\nDo this."
        assert "Do this" in builder.extract_wiring_instructions(raw)

    def test_missing_returns_empty(self):
        raw = "No wiring section here."
        assert builder.extract_wiring_instructions(raw) == ""


# ── get_questions ─────────────────────────────────────────────────────────────

class TestGetQuestions:
    def test_skill_questions_nonempty(self):
        qs = builder.get_questions("skill")
        assert len(qs) >= 6
        keys = [q.key for q in qs]
        assert "name" in keys
        assert "goal" in keys
        assert "trigger" in keys

    def test_workflow_questions_nonempty(self):
        qs = builder.get_questions("workflow")
        assert len(qs) >= 5
        keys = [q.key for q in qs]
        assert "name" in keys
        assert "steps_raw" in keys

    def test_agent_questions_nonempty(self):
        qs = builder.get_questions("agent")
        assert len(qs) >= 5
        keys = [q.key for q in qs]
        assert "name" in keys
        assert "tools" in keys

    def test_unknown_type_returns_empty(self):
        assert builder.get_questions("unknown") == []


# ── should_ask ────────────────────────────────────────────────────────────────

class TestShouldAsk:
    def test_no_dependency_always_shown(self):
        q = builder.BuilderQuestion(key="x", prompt="X?", kind="free")
        assert builder.should_ask(q, {}) is True

    def test_dependency_met(self):
        q = builder.BuilderQuestion(key="detail", prompt="Detail?", depends_on=("stack", "custom"))
        assert builder.should_ask(q, {"stack": "custom"}) is True

    def test_dependency_not_met(self):
        q = builder.BuilderQuestion(key="detail", prompt="Detail?", depends_on=("stack", "custom"))
        assert builder.should_ask(q, {"stack": "python"}) is False

    def test_dependency_key_missing(self):
        q = builder.BuilderQuestion(key="detail", prompt="Detail?", depends_on=("stack", "custom"))
        assert builder.should_ask(q, {}) is False


# ── build_llm_prompt ──────────────────────────────────────────────────────────

class TestBuildLlmPrompt:
    def test_skill_prompt_contains_answers(self):
        p = builder.build_llm_prompt("skill", SKILL_ANSWERS)
        assert "Django Model Creator" in p
        assert "Django model" in p
        assert "python" in p.lower()

    def test_skill_prompt_contains_slug(self):
        p = builder.build_llm_prompt("skill", SKILL_ANSWERS)
        assert "django-model-creator" in p

    def test_workflow_prompt_contains_answers(self):
        p = builder.build_llm_prompt("workflow", WORKFLOW_ANSWERS)
        assert "PR Prep Checklist" in p
        assert "/review" in p
        assert "per-pr" in p

    def test_agent_prompt_contains_answers(self):
        p = builder.build_llm_prompt("agent", AGENT_ANSWERS)
        assert "Database Inspector" in p
        assert "database-inspector" in p
        assert "SQL" in p

    def test_agent_prompt_uses_runnable_scaffold(self):
        p = builder.build_llm_prompt("agent", AGENT_ANSWERS)
        assert "NotImplementedError" not in p
        assert "_workspace_hint" in p

    def test_custom_stack_resolved(self):
        answers = {**SKILL_ANSWERS, "stack": "custom", "stack_detail": "Ruby on Rails"}
        p = builder.build_llm_prompt("skill", answers)
        assert "Ruby on Rails" in p

    def test_unknown_type_empty(self):
        assert builder.build_llm_prompt("unknown", {}) == ""


# ── finalize ─────────────────────────────────────────────────────────────────

class TestFinalize:
    def test_skill_result(self):
        llm_output = "```markdown\n---\nname: test\n---\n# Title\n```"
        result = builder.finalize("skill", SKILL_ANSWERS, llm_output)
        assert result.build_type == "skill"
        assert result.slug == "django-model-creator"
        assert "Title" in result.content
        assert result.wiring == ""

    def test_agent_extracts_wiring(self):
        llm_output = (
            "```python\ndef run(): pass\n```\n\n"
            "## 📋 Wiring instructions\n1. Import it\n2. Add route\n"
        )
        result = builder.finalize("agent", AGENT_ANSWERS, llm_output)
        assert result.build_type == "agent"
        assert "run" in result.content
        assert "Import it" in result.wiring

    def test_name_preserved(self):
        result = builder.finalize("skill", SKILL_ANSWERS, "content")
        assert result.name == "Django Model Creator"


# ── save_result ───────────────────────────────────────────────────────────────

class TestSaveResult:
    def test_saves_skill(self, tmp_path):
        result = builder.finalize("skill", SKILL_ANSWERS, "---\nname: x\n---\n# Skill")
        path = builder.save_result(result, str(tmp_path))
        assert path.exists()
        assert path.name == "SKILL.md"
        assert path.parent.name == "django-model-creator"
        assert "# Skill" in path.read_text()

    def test_saves_workflow(self, tmp_path):
        result = builder.finalize("workflow", WORKFLOW_ANSWERS, "# Workflow content")
        path = builder.save_result(result, str(tmp_path))
        assert path.exists()
        assert path.name == "WORKFLOW.md"
        assert "pr-prep-checklist" in str(path)

    def test_saves_agent(self, tmp_path):
        result = builder.finalize("agent", AGENT_ANSWERS, "def run(): pass")
        path = builder.save_result(result, str(tmp_path))
        assert path.exists()
        assert path.suffix == ".py"
        assert "database-inspector" in path.name

    def test_agent_saves_wiring_file(self, tmp_path):
        llm_output = (
            "```python\ndef run(): pass\n```\n\n"
            "## Wiring instructions\n1. Import it\n"
        )
        result = builder.finalize("agent", AGENT_ANSWERS, llm_output)
        builder.save_result(result, str(tmp_path))
        wiring_path = tmp_path / "app" / "agents" / "database-inspector_WIRING.md"
        assert wiring_path.exists()

    def test_skill_creates_dir(self, tmp_path):
        result = builder.finalize("skill", {"name": "brand-new"}, "content")
        path = builder.save_result(result, str(tmp_path))
        assert (tmp_path / "skills" / "brand-new").is_dir()

    def test_unknown_type_raises(self, tmp_path):
        result = builder.BuildResult(build_type="unknown", name="x", slug="x", content="c")
        with pytest.raises(ValueError, match="Unknown build type"):
            builder.save_result(result, str(tmp_path))


# ── save_path_for ─────────────────────────────────────────────────────────────

class TestSavePathFor:
    def test_skill_path(self, tmp_path):
        p = builder.save_path_for("skill", "my-skill", str(tmp_path))
        assert str(p).endswith("skills/my-skill/SKILL.md") or "skills" in str(p)

    def test_workflow_path(self, tmp_path):
        p = builder.save_path_for("workflow", "my-wf", str(tmp_path))
        assert "WORKFLOW.md" in str(p)

    def test_agent_path(self, tmp_path):
        p = builder.save_path_for("agent", "my-agent", str(tmp_path))
        assert p.suffix == ".py"
