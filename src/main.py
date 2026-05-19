from loop import agent_loop, extract_text

if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms03 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        final_text = extract_text(history[-1]["content"])
        if final_text:
            print(final_text)
        print()
