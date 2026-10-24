from app import plugins


def test_discover_loads_plugin_command(tmp_path):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "hello.py").write_text(
        "def hello(raw, context):\n"
        "    return f'hello from {context.workspace}'\n\n"
        "SLASH_COMMANDS = [\n"
        "    {'name': '/hello', 'description': 'Greet the workspace', 'handler': hello},\n"
        "]\n",
        encoding="utf-8",
    )

    registry = plugins.discover(str(tmp_path), ["plugins"])
    command = plugins.find_command(registry, "/hello")

    assert command is not None
    result = plugins.execute(
        command,
        "/hello",
        plugins.PluginContext(workspace=str(tmp_path), config={}),
    )
    assert "hello from" in result


def test_build_registry_reply_mentions_load_issues(tmp_path):
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    (plugin_dir / "broken.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")

    registry = plugins.discover(str(tmp_path), ["plugins"])
    reply = plugins.build_registry_reply(registry)

    assert "Load issues" in reply
    assert "broken.py" in reply
