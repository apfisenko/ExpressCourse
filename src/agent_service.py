import json
import logging

from langsmith import traceable

from src.config import Config
from src.llm_client import LlmAuthError, LlmClient, LlmProviderError

_MAX_TOOL_ITERATIONS = 10


class AgentService:
    def __init__(self, llm: LlmClient, config: Config) -> None:
        self._llm = llm
        self._config = config
        self._system_prompt = config.system_prompt
        self._max_pairs = config.dialog_max_pairs
        self._history: dict[int, list[dict]] = {}
        self._tools: list[dict] = []

    def reload_settings(self) -> None:
        self._llm.reload_settings()
        self._system_prompt = self._config.system_prompt
        self._max_pairs = self._config.dialog_max_pairs

    def register_tool(self, definition: dict, handler) -> None:
        """Register a tool definition and its async handler callable."""
        self._tools.append({"definition": definition, "handler": handler})

    @traceable(name="agent_handle_message")
    async def handle_message(self, user_id: int, text: str) -> str:
        self.reload_settings()

        history = self._history.setdefault(user_id, [])
        history.append({"role": "user", "content": text})
        self._trim(history)

        try:
            return await self._run_agent_loop(user_id, history)
        except Exception:
            history.pop()
            raise

    async def _run_agent_loop(self, user_id: int, history: list[dict]) -> str:
        tool_definitions = [t["definition"] for t in self._tools]
        handlers = {t["definition"]["function"]["name"]: t["handler"] for t in self._tools}

        context: list[dict] = [
            {"role": "system", "content": self._system_prompt},
            *history,
        ]

        for _ in range(_MAX_TOOL_ITERATIONS):
            content, tool_calls = await self._chat_with_retry(context, tool_definitions)

            if not tool_calls:
                final = content or ""
                history.append({"role": "assistant", "content": final})
                self._trim(history)
                return final

            # Append assistant message with tool_calls to context
            context.append({
                "role": "assistant",
                "content": content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ],
            })

            for tc in tool_calls:
                result = await self._execute_tool(tc.function.name, tc.function.arguments, handlers)
                context.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        logging.warning("Agent loop reached max iterations for user %d", user_id)
        return content or ""

    async def _execute_tool(self, name: str, arguments_json: str, handlers: dict) -> str:
        handler = handlers.get(name)
        if handler is None:
            logging.warning("Unknown tool called: %s", name)
            return json.dumps({"error": f"Tool '{name}' not found"})
        try:
            args = json.loads(arguments_json)
            result = await handler(**args)
            return json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            logging.exception("Tool '%s' raised an error", name)
            return json.dumps({"error": str(exc)})

    async def _chat_with_retry(self, context: list[dict], tool_definitions: list[dict]):
        for attempt in range(2):
            try:
                return await self._llm.chat(context, tools=tool_definitions or None)
            except (LlmAuthError, LlmProviderError):
                if attempt == 0:
                    self.reload_settings()
                    logging.info("LLM error in agent loop, settings reloaded, retrying")
                    continue
                raise
        raise RuntimeError("unreachable")

    def _trim(self, messages: list[dict]) -> None:
        max_messages = self._max_pairs * 2
        if len(messages) > max_messages:
            del messages[:-max_messages]
