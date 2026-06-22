from agent_loop import MODEL, agent_loop, client, extract_text
from compact import CompactState
from hook import (
    pre_tool_compact_hook,
    pre_tool_permission_hook,
    register_hook,
    trigger_hooks,
    user_prompt_submit_hook,
)
from logger import CYAN, RESET, log_agent
from permission import MODES, PermissionManager

if __name__ == "__main__":
    print("Permission modes: default, plan, auto")
    mode_input = input("Mode(default): ").strip().lower() or "default"
    if mode_input not in MODES:
        mode_input = "default"
    perms = PermissionManager(mode=mode_input)
    compact_state = CompactState()
    register_hook("PreToolUse", pre_tool_permission_hook(perms))
    register_hook("PreToolUse", pre_tool_compact_hook(client, MODEL, compact_state))
    register_hook("UserPromptSubmit", user_prompt_submit_hook(perms))
    print(f"[Permission mode: {mode_input}]")
    history = []
    while True:
        try:
            query = input(f"{CYAN}👨 >> {RESET}")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        if trigger_hooks("UserPromptSubmit", query):
            continue
        history.append({"role": "user", "content": query})
        agent_loop(history, compact_state, perms)
        final_text = extract_text(history[-1]["content"])
        if final_text:
            log_agent(final_text)
