"""Tests for app/policy.py."""

import tempfile
import pathlib

from app.policy import Policy, Rule, Action, Scope, load_policy, save_policy, DEFAULT_POLICY_YAML


class TestPolicyEngine:
    def test_default_policy_loads(self):
        policy = load_policy()
        assert policy.default_action == Action.ASK
        assert len(policy.rules) > 0

    def test_tool_allow_rule(self):
        policy = load_policy()
        result = policy.evaluate(Scope.TOOL, "read_file")
        assert result == Action.ALLOW

    def test_tool_ask_rule(self):
        policy = load_policy()
        result = policy.evaluate(Scope.TOOL, "create_file")
        assert result == Action.ASK

    def test_tool_ask_rule_delete(self):
        policy = load_policy()
        result = policy.evaluate(Scope.TOOL, "delete_file")
        assert result == Action.ASK

        result = policy.evaluate(Scope.TOOL, "delete_folder")
        assert result == Action.ASK

        result = policy.evaluate(Scope.TOOL, "run_command")
        assert result == Action.ASK

    def test_command_allow_rule(self):
        policy = load_policy()
        result = policy.evaluate(Scope.COMMAND, "python")
        assert result == Action.ALLOW

        result = policy.evaluate(Scope.COMMAND, "python3")
        assert result == Action.ALLOW

        result = policy.evaluate(Scope.COMMAND, "pytest")
        assert result == Action.ALLOW

    def test_command_deny_fallback(self):
        policy = load_policy()
        result = policy.evaluate(Scope.COMMAND, "rm -rf /")
        assert result == Action.DENY

    def test_path_allow_default(self):
        policy = load_policy()
        result = policy.evaluate(Scope.PATH, "src/main.py")
        assert result == Action.ALLOW

    def test_priority_ordering(self):
        policy = Policy(rules=[
            Rule(Action.ALLOW, Scope.TOOL, "create_file", priority=10),
            Rule(Action.DENY, Scope.TOOL, "create_file", priority=20),
        ], default_action=Action.ASK)
        result = policy.evaluate(Scope.TOOL, "create_file")
        assert result == Action.DENY

    def test_custom_policy_file(self, tmp_path):
        custom_yaml = """
version: 1
default_action: deny
rules:
  - action: allow
    scope: tool
    pattern: "read_file"
    priority: 10
"""
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(custom_yaml)
        policy = load_policy(str(policy_file))
        assert policy.default_action == Action.DENY
        assert policy.evaluate(Scope.TOOL, "read_file") == Action.ALLOW
        assert policy.evaluate(Scope.TOOL, "create_file") == Action.DENY

    def test_save_policy(self, tmp_path):
        policy = Policy(rules=[
            Rule(Action.ALLOW, Scope.TOOL, "test_tool", priority=5),
        ], default_action=Action.ASK)
        policy_file = tmp_path / "policy.yaml"
        save_policy(policy, str(policy_file))

        loaded = load_policy(str(policy_file))
        assert loaded.default_action == Action.ASK
        assert len(loaded.rules) == 1
        assert loaded.rules[0].pattern == "test_tool"
        assert loaded.rules[0].action == Action.ALLOW


class TestRuleMatching:
    def test_glob_pattern_matching(self):
        rule = Rule(Action.ALLOW, Scope.COMMAND, "python*")
        assert rule.matches("python")
        assert rule.matches("python3")
        assert rule.matches("python3.10")
        assert not rule.matches("pip")

    def test_exact_match(self):
        rule = Rule(Action.ALLOW, Scope.TOOL, "read_file")
        assert rule.matches("read_file")
        assert not rule.matches("read_files")

    def test_path_glob_matching(self):
        rule = Rule(Action.ALLOW, Scope.PATH, "src/**")
        assert rule.matches("src/main.py")
        assert rule.matches("src/utils/helper.py")
        assert not rule.matches("tests/test_main.py")