# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A Python learning project that implements a Claude Code–style AI coding agent. It demonstrates core concepts: tool-calling loops, subagents, context compaction, skill loading, todo-based session planning, and a multi-layer permission system.

## Commands

```bash
# Run the interactive agent REPL
uv run python src/main.py

# Run any individual module directly
uv run python src/agent_loop.py
```

There is no test suite or linting setup yet.

## Architecture

### Entry point and agent loop

[src/main.py](src/main.py) runs an interactive REPL: reads user input, appends it to `history`, and calls `agent_loop()`.

[src/agent_loop.py](src/agent_loop.py) contains the core `agent_loop(messages, compact_state)`:
1. **Micro-compact** older tool results to save context.
2. **Auto-compact** if `estimate_context_size()` exceeds `CONTEXT_LIMIT` (50,000 chars) — summarizes conversation via an LLM call (saves transcript to `.transcripts/`, replaces history with a single summary message).
3. Calls Anthropic Messages API with `PARENT_TOOLS` (which includes the `task` subagent tool).
4. If `stop_reason == "tool_use"`, dispatches each tool block:
   - `compact` → manual compact (LLM summarizes with a user-provided focus).
   - `task` → spawns a `subagent_loop()` with `CHILD_TOOLS` (no nested subagents).
   - All others → dispatched via `TOOL_HANDLERS` dict.
5. After tool results are collected, checks if a **todo reminder** is needed (injected as text into results if the plan hasn't been updated for ≥3 rounds).
6. Appends tool results as a `user` message and loops.

### Tool system ([src/tools.py](src/tools.py))

- **`TOOL_HANDLERS`** — dict mapping tool name → handler function. Each handler receives tool input as kwargs and returns a string result.
- **`CHILD_TOOLS`** — tool definitions for subagents (bash, read_file, write_file, edit_file, todo, load_skill, compact). Subagents share filesystem but not conversation history.
- **`PARENT_TOOLS`** — `CHILD_TOOLS` + `task` (subagent spawner). The main agent can spawn subagents; subagents cannot nest further.
- **`safe_path()`** — resolves paths relative to `WORKDIR` and rejects any path that escapes the workspace via `..` traversal.
- **`decode_output()`** — tries UTF-8 → GBK → CP936 for subprocess output decoding (handles Windows GBK encoding issues).
- Tool results are truncated to 50,000 chars (bash) or 50,000 chars (read_file).

### Todo / session plan ([src/todo.py](src/todo.py))

`TodoManager` wraps a `PlanningState` dataclass:
- `update(items)` — validates (max 12 items, exactly one `in_progress`), resets round counter, returns rendered plan.
- `note_round_without_update()` — increments counter each agent turn without a todo update.
- `reminder()` — returns a `<reminder>` string after `PLAN_REMINDER_INTERVAL` (3) consecutive rounds without update.

### Compact / context management ([src/compact.py](src/compact.py))

Two levels of compaction:
- **Micro-compact** (`micro_compact()`): keeps only the last `KEEP_RECENT_TOOL_RESULTS` (3) tool results intact; older results >120 chars are replaced with a placeholder message.
- **Full compact** (`compact_history()`): triggered automatically when context exceeds `CONTEXT_LIMIT` (50,000 chars), or manually via the `compact` tool. Saves full transcript to `.transcripts/`, calls an LLM summary, replaces entire history with one summary message.

`CompactState` tracks: whether compaction has occurred, the last summary, and recently accessed files.

### Subagent ([src/subagent.py](src/subagent.py))

`subagent_loop(client, model, prompt)` runs a subagent with `CHILD_TOOLS` for up to 30 turns. Shares the filesystem but starts with fresh context (only the given prompt). Used by the `task` tool in the parent loop. `AgentTemplate` parses agent definitions from markdown frontmatter (mirrors Claude Code's `.claude/agents/*.md` format).

### Skill system ([src/skill.py](src/skill.py))

`SkillRegistry` scans `skills/*/SKILL.md` at startup. Each skill file has YAML frontmatter (`name`, `description`) followed by a markdown body. The registry provides:
- `describe_available()` — a formatted list for the system prompt.
- `load_full_text(name)` — returns the full skill body wrapped in `<skill>` tags (used by the `load_skill` tool).

### Permission system ([src/permission.py](src/permission.py))

Multi-layer permission checking, designed as a teaching-oriented implementation:
1. `BashSecurityValidator` — regex-based dangerous command detection (metacharacters, `runas`, recursive delete, PowerShell, encoded commands, download+execute chains).
2. Deny rules (always checked first, cannot be bypassed by allow rules).
3. Mode-based decisions: `plan` mode blocks all writes; `auto` mode auto-approves read-only tools.
4. Allow rules with fnmatch-based path and content matching.
5. Fallback to `ask` — interactive user prompt with consecutive-denial tracking.

### Logger ([src/logger.py](src/logger.py))

ANSI-styled terminal output with tool-specific icons and colors. Formats agent responses, tool calls (`icon + name → brief`), and subagent task start/end.

## Key conventions

- **Windows PowerShell is the execution environment.** The system prompt explicitly forbids Linux commands (head, tail, ls, cat, grep, sed, awk). Use `read_file` instead of `cat`, PowerShell or Python for directory listing, etc.
- **Encoding**: some files may be GBK-encoded. `decode_output()` handles this; write files as UTF-8.
- **Python ≥ 3.12** required. Package manager is `uv`.
- **API**: Uses Anthropic Messages API via the `anthropic` SDK, configured through `.env` (`ANTHROPIC_BASE_URL`, `MODEL_ID`).
- Import style: modules under `src/` import each other directly by filename (e.g., `from compact import CompactState`), relying on `sys.path` or running from `src/` as cwd.
