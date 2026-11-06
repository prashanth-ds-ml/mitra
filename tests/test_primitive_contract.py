from app.agents import filesystem




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


