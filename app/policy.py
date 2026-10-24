"""Policy Engine — deny-first rule engine with allow/ask/deny, path/tool/command scopes, precedence."""
from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import yaml


class Action(Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class Scope(Enum):
    TOOL = "tool"
    COMMAND = "command"
    PATH = "path"


@dataclass(frozen=True)
class Rule:
    action: Action
    scope: Scope
    pattern: str
    description: str = ""
    priority: int = 0

    def matches(self, value: str) -> bool:
        import fnmatch
        return fnmatch.fnmatch(value, self.pattern)


@dataclass
class Policy:
    rules: list[Rule] = field(default_factory=list)
    default_action: Action = Action.ASK

    def evaluate(self, scope: Scope, value: str) -> Action:
        matched_rules = [r for r in self.rules if r.scope == scope and r.matches(value)]
        if not matched_rules:
            return self.default_action
        matched_rules.sort(key=lambda r: r.priority, reverse=True)
        return matched_rules[0].action


DEFAULT_POLICY_YAML = """
# CodeMitra Policy Configuration
# Deny-first rule engine: rules are evaluated in priority order (highest wins)
# Actions: allow, ask, deny
# Scopes: tool, command, path

version: 1
default_action: ask

rules:
  # Tool rules - control which filesystem tools can be used
  - action: allow
    scope: tool
    pattern: "read_file"
    description: "Allow reading files"
    priority: 10

  - action: allow
    scope: tool
    pattern: "list_directory"
    description: "Allow listing directories"
    priority: 10

  - action: allow
    scope: tool
    pattern: "get_file_tree"
    description: "Allow file tree view"
    priority: 10

  - action: allow
    scope: tool
    pattern: "search_in_files"
    description: "Allow searching in files"
    priority: 10

  - action: allow
    scope: tool
    pattern: "find_definition"
    description: "Allow finding definitions"
    priority: 10

  - action: allow
    scope: tool
    pattern: "grep_symbol"
    description: "Allow grepping symbols"
    priority: 10

  - action: ask
    scope: tool
    pattern: "create_file"
    description: "Ask before creating files"
    priority: 20

  - action: ask
    scope: tool
    pattern: "create_folder"
    description: "Ask before creating folders"
    priority: 20

  - action: ask
    scope: tool
    pattern: "move_file"
    description: "Ask before moving/renaming files"
    priority: 20

  - action: ask
    scope: tool
    pattern: "delete_file"
    description: "Ask before deleting files"
    priority: 30

  - action: ask
    scope: tool
    pattern: "delete_folder"
    description: "Ask before deleting folders"
    priority: 30

  - action: ask
    scope: tool
    pattern: "run_command"
    description: "Ask before running commands"
    priority: 30

  # Command rules - control which executables can be run
  - action: allow
    scope: command
    pattern: "python*"
    description: "Allow python commands"
    priority: 10

  - action: allow
    scope: command
    pattern: "pip*"
    description: "Allow pip commands"
    priority: 10

  - action: allow
    scope: command
    pattern: "git*"
    description: "Allow git commands"
    priority: 10

  - action: allow
    scope: command
    pattern: "npm*"
    description: "Allow npm commands"
    priority: 10

  - action: allow
    scope: command
    pattern: "pytest*"
    description: "Allow pytest"
    priority: 10

  - action: allow
    scope: command
    pattern: "ruff*"
    description: "Allow ruff"
    priority: 10

  - action: allow
    scope: command
    pattern: "mypy*"
    description: "Allow mypy"
    priority: 10

  - action: allow
    scope: command
    pattern: "black*"
    description: "Allow black"
    priority: 10

  - action: allow
    scope: command
    pattern: "uvicorn*"
    description: "Allow uvicorn"
    priority: 10

  - action: deny
    scope: command
    pattern: "*"
    description: "Deny all other commands"
    priority: 5

  # Path rules - control which paths can be accessed
  - action: allow
    scope: path
    pattern: "**"
    description: "Allow all paths within workspace by default"
    priority: 5
"""


def load_policy(policy_path: Optional[str] = None) -> Policy:
    if policy_path:
        with open(policy_path, "r") as f:
            data = yaml.safe_load(f)
    else:
        data = yaml.safe_load(DEFAULT_POLICY_YAML)

    rules = []
    for rule_data in data.get("rules", []):
        rules.append(Rule(
            action=Action(rule_data["action"]),
            scope=Scope(rule_data["scope"]),
            pattern=rule_data["pattern"],
            description=rule_data.get("description", ""),
            priority=rule_data.get("priority", 0),
        ))

    default_action = Action(data.get("default_action", "ask"))
    return Policy(rules=rules, default_action=default_action)


def save_policy(policy: Policy, policy_path: str) -> None:
    data = {
        "version": 1,
        "default_action": policy.default_action.value,
        "rules": [
            {
                "action": r.action.value,
                "scope": r.scope.value,
                "pattern": r.pattern,
                "description": r.description,
                "priority": r.priority,
            }
            for r in policy.rules
        ],
    }
    with open(policy_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)