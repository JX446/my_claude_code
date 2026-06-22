from compact import compact_history
from logger import log_tool_call
from permission import MODES, PermissionManager

HOOKS = {"UserPromptSubmit": [], "PreToolUse": [], "PostToolUse": [], "Stop": []}


def register_hook(event: str, callback) -> None:
    HOOKS[event].append(callback)


def trigger_hooks(event: str, *args):
    for callback in HOOKS[event]:
        result = callback(*args)
        if result is not None:
            return result
    return None


def pre_tool_permission_hook(perms: PermissionManager):
    def check_permission(block, _messages=None):
        if block.name == "compact":
            return None  # 元工具，始终放行
        decision = perms.check(block.name, dict(block.input or {}))
        if decision["behavior"] == "deny":
            output = f"⛔ [Denied] {decision.get('reason', '')}"
            log_tool_call(block.name, output[:100])
            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output,
            }
        elif decision["behavior"] == "ask":
            output = f"⏳ [Ask required] {decision.get('reason', '')}\n(Agent loop non-interactive. Add allow rule or switch mode.)"
            log_tool_call(block.name, output[:100])
            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output,
            }
        # behavior == "allow" → 继续执行
        return None

    return check_permission


def user_prompt_submit_hook(perms: PermissionManager):
    def handle_command(query: str):
        if query.startswith("/mode"):
            parts = query.split()
            if len(parts) == 2 and parts[1] in MODES:
                perms.mode = parts[1]
                print(f"[Switched to {parts[1]} mode]")
            else:
                print(f"Usage: /mode <{'|'.join(MODES)}>")
            return True  # 拦截，不进入 agent
        if query.strip() == "/rules":
            for i, rule in enumerate(perms.rules):
                print(f"  {i}: {rule}")
            return True  # 拦截，不进入 agent
        return None  # 放行

    return handle_command


def pre_tool_compact_hook(client, model, state):
    def handle_compact(block, messages):
        if block.name != "compact":
            return None
        focus = str((block.input or {}).get("focus", ""))
        log_tool_call("compact", "compacting")
        messages[:] = compact_history(client, model, messages, state, focus=focus)
        return "__COMPACTED__"

    return handle_compact
