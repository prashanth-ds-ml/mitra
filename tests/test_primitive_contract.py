from app.agents import filesystem, reader, shell


def test_reader_surface_is_read_only():
    names = {tool.name for tool in reader._ALL_TOOLS}
    assert names == {"get_file_tree", "read_file", "read_document", "search_in_files", "find_definition", "grep_symbol"}

    forbidden = {"create_file", "edit_file", "delete_file", "move_file", "run_command", "git_status", "git_diff"}
    assert names.isdisjoint(forbidden)


def test_filesystem_surface_contains_mutation_and_execution_tools():
    names = {tool.name for tool in filesystem._ALL_TOOLS}
    expected = {
        "create_folder",
        "create_file",
        "edit_file",
        "read_file",
        "list_directory",
        "search_text",
        "delete_file",
        "delete_folder",
        "move_file",
        "create_venv",
        "install_packages",
        "run_command",
        "git_status",
        "git_diff",
        "git_commit",
        "create_markdown_file",
        "update_markdown_file",
    }
    assert expected.issubset(names)


def test_shell_surface_exposes_command_execution():
    assert shell.run_shell.name == "run_shell"
    assert callable(shell.run_shell.invoke)

    routed = shell.make_routing_tool(llm=object())
    assert routed.name == "run_command"
