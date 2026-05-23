# ── ANSI styling ──────────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"

TOOL_ICON: dict[str, str] = {
    "bash": "⚡",
    "read_file": "📖",
    "write_file": "✍️ ",
    "edit_file": "✏️ ",
    "todo": "📋",
}

TOOL_COLOR: dict[str, str] = {
    "bash": CYAN,
    "read_file": GREEN,
    "write_file": YELLOW,
    "edit_file": BLUE,
    "todo": MAGENTA,
}
# ──────────────────────────────────────────────────────────────
indent = " " * 6


def log_agent(text: str) -> None:
    prefix = f"{MAGENTA}🤖 >> {RESET}"
    formatted = text.replace("\n", "\n" + indent)
    print(prefix + formatted)


def log_task_start(desc: object) -> None:
    print(f"{indent}{MAGENTA}{BOLD}🚀 task{RESET} {DIM}→{RESET} {desc}")


def log_task_end(summary: str) -> None:
    print(f"{indent}{MAGENTA}{DIM}←{RESET}{MAGENTA} {summary}{RESET}")


def log_tool_call(name: str, brief: str) -> None:
    icon = TOOL_ICON.get(name, "⚙️ ")
    color = TOOL_COLOR.get(name, "")
    print(f"{indent}{icon} {color}{BOLD}{name}{RESET} {DIM}→{RESET} {brief}")
