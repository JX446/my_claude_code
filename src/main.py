from agent_loop import agent_loop, extract_text
from compact import CompactState
from logger import CYAN, RESET, log_agent
from permission import MODES, PermissionManager

if __name__ == "__main__":
    print("Permission modes: default, plan, auto")
    mode_input = input("Mode(default): ").strip().lower() or "default"
    if mode_input not in MODES:
        mode_input = "default"
    perms = PermissionManager(mode=mode_input)
    print(f"[Permission mode: {mode_input}]")
    history = []
    compact_state = CompactState()
    while True:
        try:
            query = input(f"{CYAN}👨 >> {RESET}")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break

        # /mode command to switch modes at runtime
        if query.startswith("/mode"):
            parts = query.split()
            if len(parts) == 2 and parts[1] in MODES:
                perms.mode = parts[1]
                print(f"[Switched to {parts[1]} mode]")
            else:
                print(f"Usage: /mode <{'|'.join(MODES)}>")
            continue

        # /rules command to show current rules
        if query.strip() == "/rules":
            for i, rule in enumerate(perms.rules):
                print(f"  {i}: {rule}")
            continue

        history.append({"role": "user", "content": query})
        agent_loop(history, compact_state, perms)
        final_text = extract_text(history[-1]["content"])
        if final_text:
            log_agent(final_text)
