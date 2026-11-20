"""Tool definitions supplied to a compatible model service."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required,
                "additionalProperties": False,
            },
        },
    }
    for name, desc, props, required in [
        (
            "write_file",
            "Write a UTF-8 file in /workspace",
            {"path": {"type": "string"}, "content": {"type": "string"}},
            ["path", "content"],
        ),
        ("read_file", "Read a UTF-8 workspace file", {"path": {"type": "string"}}, ["path"]),
        (
            "run_command",
            "Run a shell command in /workspace, timeout 30 seconds; Python is installed",
            {"command": {"type": "string"}},
            ["command"],
        ),
        (
            "browser",
            "Browser actions: open(url), set_content(text), snapshot, click(selector), fill(selector,text). Offline by default: use set_content for HTML.",
            {
                "action": {"type": "string"},
                "url": {"type": "string"},
                "selector": {"type": "string"},
                "text": {"type": "string"},
            },
            ["action"],
        ),
    ]
]
