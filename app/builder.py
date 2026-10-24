"""Guided wizard — helps users create Skills, Workflows, and Agents for CodeMitra.

Flow
----
1. User types /create
2. Wizard asks: Skill / Workflow / Agent
3. Series of plain-English Q&A questions (multiple-choice + freeform)
4. LLM generates the artifact from the collected answers
5. Preview → Approve / Regenerate / Edit / Cancel
6. Save to the right location

Skills   → skills/<slug>/SKILL.md            (auto-discovered by /skills)
Workflows → .codemitra/workflows/<slug>/WORKFLOW.md
Agents   → app/agents/<slug>.py + wiring instructions
"""
from __future__ import annotations

import pathlib
import re
import textwrap
from dataclasses import dataclass, field

# ── Build types ───────────────────────────────────────────────────────────────

BUILD_TYPES: list[tuple[str, str]] = [
    ("skill",    "Skill    — Teach CodeMitra a reusable capability playbook  (beginner-friendly)"),
    ("workflow", "Workflow — Save a step-by-step task automation              (intermediate)"),
    ("agent",    "Agent    — Add an AI sub-agent with custom tools            (advanced / developer)"),
]


# ── Question model ────────────────────────────────────────────────────────────

@dataclass
class BuilderQuestion:
    key: str
    prompt: str
    kind: str = "free"                            # "free" | "choice"
    choices: list[tuple[str, str]] = field(default_factory=list)
    optional: bool = False
    depends_on: tuple[str, str] | None = None    # (key, value) — show only when key==value


# ── Question banks ────────────────────────────────────────────────────────────

SKILL_QUESTIONS: list[BuilderQuestion] = [
    BuilderQuestion(
        key="name",
        prompt="What should this skill be called?\n"
               "  (use a short, descriptive slug: e.g. 'django-model-creator', 'api-doc-writer')",
        kind="free",
    ),
    BuilderQuestion(
        key="goal",
        prompt="In 1–2 sentences, what does this skill do?\n"
               "  (be specific — this becomes the skill's match description)",
        kind="free",
    ),
    BuilderQuestion(
        key="trigger",
        prompt="When should CodeMitra automatically use this skill?\n"
               "  (Describe the situation: keywords, file types, user intent)",
        kind="free",
    ),
    BuilderQuestion(
        key="stack",
        prompt="What technology stack or domain does this skill apply to?",
        kind="choice",
        choices=[
            ("any",    "Any language / stack"),
            ("python", "Python"),
            ("js",     "JavaScript / TypeScript"),
            ("web",    "Web (HTML, CSS, frontend frameworks)"),
            ("sql",    "SQL / databases"),
            ("devops", "DevOps / CI-CD / Docker / Kubernetes"),
            ("custom", "Other — I'll describe it →"),
        ],
    ),
    BuilderQuestion(
        key="stack_detail",
        prompt="Describe your specific stack, framework, or domain:",
        kind="free",
        optional=True,
        depends_on=("stack", "custom"),
    ),
    BuilderQuestion(
        key="rules",
        prompt="List any rules, constraints, or style guidelines this skill must follow.\n"
               "  (One per line — press Enter twice when done. Leave blank to let the AI decide)",
        kind="free",
        optional=True,
    ),
    BuilderQuestion(
        key="workflow_hint",
        prompt="Describe the steps this skill should perform, one per line.\n"
               "  (Leave blank and the AI will generate appropriate steps from your description)",
        kind="free",
        optional=True,
    ),
    BuilderQuestion(
        key="output_format",
        prompt="What should the skill produce or deliver?",
        kind="choice",
        choices=[
            ("code",   "Code files (create / modify source files)"),
            ("docs",   "Documentation or Markdown reports"),
            ("tests",  "Test files"),
            ("plan",   "A plan or checklist"),
            ("mixed",  "A combination of the above"),
        ],
    ),
]

WORKFLOW_QUESTIONS: list[BuilderQuestion] = [
    BuilderQuestion(
        key="name",
        prompt="What is the name of this workflow?\n"
               "  (e.g. 'deploy-feature', 'code-review-checklist', 'pr-prep')",
        kind="free",
    ),
    BuilderQuestion(
        key="goal",
        prompt="What does this workflow accomplish? Describe the end result.",
        kind="free",
    ),
    BuilderQuestion(
        key="trigger",
        prompt="When would you run this workflow? What situation or event triggers it?",
        kind="free",
    ),
    BuilderQuestion(
        key="steps_raw",
        prompt="Describe each step of the workflow, one per line.\n"
               "  You can use CodeMitra commands (/review, /fix <cmd>), shell commands, or plain English.\n"
               "  (Leave blank to let the AI generate the steps from your description)",
        kind="free",
        optional=True,
    ),
    BuilderQuestion(
        key="cadence",
        prompt="How often is this workflow run?",
        kind="choice",
        choices=[
            ("ad-hoc",  "On demand — whenever needed"),
            ("daily",   "Daily routine"),
            ("per-pr",  "Once per pull request / feature branch"),
            ("release", "At release / deployment time"),
            ("weekly",  "Weekly"),
        ],
    ),
    BuilderQuestion(
        key="notes",
        prompt="Any tips, warnings, or edge cases to include? (optional)",
        kind="free",
        optional=True,
    ),
]

AGENT_QUESTIONS: list[BuilderQuestion] = [
    BuilderQuestion(
        key="name",
        prompt="What should this agent be called?\n"
               "  (e.g. 'database-agent', 'api-tester', 'dependency-checker')",
        kind="free",
    ),
    BuilderQuestion(
        key="goal",
        prompt="In 2–3 sentences, what does this agent do?\n"
               "  (What problem does it solve? What actions can it take?)",
        kind="free",
    ),
    BuilderQuestion(
        key="tools",
        prompt="What tools should this agent have access to?\n"
               "  (One per line — e.g. 'read files', 'run shell commands', 'search the web', 'query a database')",
        kind="free",
    ),
    BuilderQuestion(
        key="trigger",
        prompt="What kind of user request should activate this agent?\n"
               "  (Describe the keywords or intent — e.g. 'when user asks about database migrations')",
        kind="free",
    ),
    BuilderQuestion(
        key="language",
        prompt="What primary programming language does this agent work with?",
        kind="choice",
        choices=[
            ("python",  "Python"),
            ("js",      "JavaScript / TypeScript"),
            ("any",     "Language-agnostic"),
            ("other",   "Other — I'll describe it"),
        ],
    ),
    BuilderQuestion(
        key="output",
        prompt="What does this agent produce or return to the user?",
        kind="free",
    ),
]


# ── LLM generation prompts ────────────────────────────────────────────────────

_SKILL_GEN_PROMPT = """\
You are a technical writer helping create a CodeMitra skill file.

A CodeMitra skill is a Markdown file with YAML frontmatter that teaches the AI a \
reusable engineering playbook. The skill file is auto-discovered and injected into \
the system prompt when the user's request matches the description.

The user provided these answers:
  Name:              {name}
  What it does:      {goal}
  When to use it:    {trigger}
  Tech stack:        {stack}
  Rules/constraints: {rules}
  Workflow hints:    {workflow_hint}
  Output type:       {output_format}

Generate a complete, ready-to-use SKILL.md file following EXACTLY this format \
(output the markdown code block and nothing else):

```markdown
---
name: {slug}
description: <ONE precise sentence (max 200 chars) that clearly describes when to use this skill>
---

# <Skill Title in Title Case>

## When to use

<2–3 sentences describing the exact situation that triggers this skill. Be specific.>

## Rules

- <concrete, actionable rule 1>
- <concrete, actionable rule 2>
- <add more rules as appropriate>

## Workflow

1. <specific step 1>
2. <specific step 2>
3. <continue — be thorough>

## Output

- <what the skill produces or delivers>
- <format, location, or quality bar>
```

Requirements:
- description must be one precise, standalone sentence used for automatic skill matching
- Rules must be concrete and actionable, not vague
- Workflow steps must be numbered and specific to the "{stack}" stack
- Do NOT output anything outside the ```markdown code block
"""

_WORKFLOW_GEN_PROMPT = """\
You are a technical writer creating a CodeMitra workflow file.

A CodeMitra workflow is a saved, replayable step-by-step playbook that guides \
the user through a recurring engineering task. Users can run it with /workflow <name>.

The user provided these answers:
  Name:        {name}
  Goal:        {goal}
  When to run: {trigger}
  Steps given: {steps_raw}
  Cadence:     {cadence}
  Notes:       {notes}

Generate a complete, ready-to-use WORKFLOW.md file following EXACTLY this format \
(output the markdown code block and nothing else):

```markdown
---
name: {slug}
description: <ONE sentence describing what this workflow achieves>
cadence: {cadence}
---

# <Workflow Title in Title Case>

## Goal

<What this workflow achieves and why it matters — 2–3 sentences.>

## When to run

<Describe the situation or event that triggers this workflow.>

## Steps

1. <concrete step — use CodeMitra commands like /review, /fix <cmd>, or clear natural language action>
2. <step>
3. <continue — be thorough, cover the full end-to-end process>

## Verification checklist

- [ ] <thing to check that confirms the workflow succeeded>
- [ ] <another check>

## Notes

<Tips, warnings, edge cases, or troubleshooting hints. Write "None." if nothing specific.>
```

Requirements:
- Steps must be actionable. Prefer CodeMitra slash commands (/review, /fix, /run) where applicable.
- If steps_raw is provided, expand each step with detail.
- Verification checklist should confirm the workflow actually worked, not just ran.
- Do NOT output anything outside the ```markdown code block
"""

_AGENT_GEN_PROMPT = """\
You are a senior Python engineer helping create a new CodeMitra agent module.

CodeMitra agents are LangChain-based tool-calling sub-agents. Each agent is a Python \
module in app/agents/ that defines LangChain @tool functions and an invoke() entry point \
that runs a ReAct-style agent loop.

The user provided:
  Name:        {name}
  Goal:        {goal}
  Tools:       {tools}
  Trigger:     {trigger}
  Language:    {language}
  Output:      {output}

Generate a complete Python skeleton for app/agents/{slug}.py following this pattern:

```python
\"\"\"CodeMitra {title} Agent — {goal}

Activation: {trigger}
\"\"\"
from __future__ import annotations

from langchain_core.messages import SystemMessage, HumanMessage
from pathlib import Path

_SYSTEM_PROMPT = \"\"\"
You are a specialist agent focused on: {goal}

Rules:
- Only perform actions directly related to the user's request.
- Always explain what you are about to do before doing it.
- Report results clearly.
- If workspace context matters, mention the relevant file or folder you inspected.
\"\"\"

def _workspace_hint(workspace: str | None) -> str:
    if not workspace:
        return "Workspace: not provided."
    root = Path(workspace).resolve()
    try:
        entries = sorted(p.name for p in root.iterdir())[:8]
    except OSError:
        entries = []
    listing = ", ".join(entries) if entries else "(workspace not readable)"
    return f"Workspace: {{root}}\\nTop-level entries: {{listing}}"

def run(query: str, llm, *, workspace: str | None = None) -> str:
    \"\"\"Run the {name} agent on the given query.\"\"\"
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT.strip()),
        HumanMessage(content=f"{{_workspace_hint(workspace)}}\\n\\nUser request: {{query}}"),
    ]
    response = llm.invoke(messages)
    return getattr(response, "content", str(response))
```

After the code block, add a section:

## 📋 Wiring instructions

Explain step by step how to wire this agent into app/main.py:
1. Where to import it
2. What slash command to add (suggest /<name>)
3. Where to add the command handler in the _chat() dispatch loop
4. Where to add it to the /help table

Be specific with line-level guidance.

Keep the scaffold runnable as-is; only add concrete tools if they materially help the described agent.
"""


# ── Utilities ─────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """Convert a human name to a filesystem-safe slug."""
    slug = name.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "my-skill"


def extract_content(llm_output: str) -> str:
    """Extract content from ```markdown, ```python, or ``` fences.

    Falls back to the raw output if no fence is found.
    """
    match = re.search(r"```(?:markdown|python|md)?\n(.*?)```", llm_output, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Try bare triple-backtick
    match = re.search(r"```\n(.*?)```", llm_output, re.DOTALL)
    if match:
        return match.group(1).strip()
    return llm_output.strip()


def extract_wiring_instructions(llm_output: str) -> str:
    """Extract the '## Wiring instructions' section from agent output."""
    match = re.search(r"##\s*(?:📋\s*)?Wiring instructions?(.*?)$", llm_output, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def get_questions(build_type: str) -> list[BuilderQuestion]:
    """Return the Q&A question list for a given build type."""
    return {
        "skill":    SKILL_QUESTIONS,
        "workflow": WORKFLOW_QUESTIONS,
        "agent":    AGENT_QUESTIONS,
    }.get(build_type, [])


def should_ask(question: BuilderQuestion, answers: dict[str, str]) -> bool:
    """Return True if this question's dependency condition is met."""
    if question.depends_on is None:
        return True
    dep_key, dep_val = question.depends_on
    return answers.get(dep_key, "") == dep_val


def build_llm_prompt(build_type: str, answers: dict[str, str]) -> str:
    """Build the one-shot LLM generation prompt from collected answers."""
    slug = slugify(answers.get("name", ""))

    stack = answers.get("stack", "any")
    if stack == "custom":
        stack = answers.get("stack_detail", "general purpose")

    if build_type == "skill":
        return _SKILL_GEN_PROMPT.format(
            name=answers.get("name", ""),
            slug=slug,
            goal=answers.get("goal", ""),
            trigger=answers.get("trigger", ""),
            stack=stack,
            rules=answers.get("rules", "Follow best practices for the given stack."),
            workflow_hint=answers.get("workflow_hint", "Generate appropriate steps."),
            output_format=answers.get("output_format", "mixed"),
        )

    if build_type == "workflow":
        return _WORKFLOW_GEN_PROMPT.format(
            name=answers.get("name", ""),
            slug=slug,
            goal=answers.get("goal", ""),
            trigger=answers.get("trigger", ""),
            steps_raw=answers.get("steps_raw", "Generate appropriate steps from the goal."),
            cadence=answers.get("cadence", "ad-hoc"),
            notes=answers.get("notes", "None."),
        )

    if build_type == "agent":
        language = answers.get("language", "any")
        title = " ".join(w.title() for w in answers.get("name", "").replace("-", " ").split())
        return _AGENT_GEN_PROMPT.format(
            name=answers.get("name", ""),
            slug=slug,
            title=title,
            goal=answers.get("goal", ""),
            tools=answers.get("tools", ""),
            trigger=answers.get("trigger", ""),
            language=language,
            output=answers.get("output", ""),
        )

    return ""


# ── Result model ──────────────────────────────────────────────────────────────

@dataclass
class BuildResult:
    build_type: str         # "skill" | "workflow" | "agent"
    name: str
    slug: str
    content: str            # main file content (SKILL.md / WORKFLOW.md / .py)
    wiring: str = ""        # agent wiring instructions (agent only)
    save_path: pathlib.Path | None = None


def finalize(build_type: str, answers: dict[str, str], llm_output: str) -> BuildResult:
    """Parse LLM output into a BuildResult ready for preview and saving."""
    content = extract_content(llm_output)
    wiring = extract_wiring_instructions(llm_output) if build_type == "agent" else ""
    slug = slugify(answers.get("name", "my-artifact"))
    name = answers.get("name", slug)
    return BuildResult(
        build_type=build_type,
        name=name,
        slug=slug,
        content=content,
        wiring=wiring,
    )


def save_result(result: BuildResult, workspace: str) -> pathlib.Path:
    """Write the artifact to disk. Returns the path written."""
    ws = pathlib.Path(workspace)

    if result.build_type == "skill":
        dest_dir = ws / "skills" / result.slug
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / "SKILL.md"
        path.write_text(result.content, encoding="utf-8")

    elif result.build_type == "workflow":
        dest_dir = ws / ".codemitra" / "workflows" / result.slug
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / "WORKFLOW.md"
        path.write_text(result.content, encoding="utf-8")

    elif result.build_type == "agent":
        dest_dir = ws / "app" / "agents"
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / f"{result.slug}.py"
        path.write_text(result.content, encoding="utf-8")
        # Also save wiring instructions as a sibling README
        if result.wiring:
            wire_path = dest_dir / f"{result.slug}_WIRING.md"
            wire_path.write_text(
                f"# Wiring instructions for `{result.slug}` agent\n\n{result.wiring}\n",
                encoding="utf-8",
            )
    else:
        raise ValueError(f"Unknown build type: {result.build_type!r}")

    result.save_path = path
    return path


def save_path_for(build_type: str, slug: str, workspace: str) -> pathlib.Path:
    """Return the expected save path without creating the file."""
    ws = pathlib.Path(workspace)
    if build_type == "skill":
        return ws / "skills" / slug / "SKILL.md"
    if build_type == "workflow":
        return ws / ".codemitra" / "workflows" / slug / "WORKFLOW.md"
    if build_type == "agent":
        return ws / "app" / "agents" / f"{slug}.py"
    raise ValueError(f"Unknown build type: {build_type!r}")
