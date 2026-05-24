from compact import CompactState
from loop import agent_loop, extract_text
from my_logger import CYAN, RESET, log_agent

if __name__ == "__main__":
    history = []
    compact_state = CompactState()
    while True:
        try:
            query = input(f"{CYAN}👨 >> {RESET}")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history, compact_state)
        final_text = extract_text(history[-1]["content"])
        if final_text:
            log_agent(final_text)
