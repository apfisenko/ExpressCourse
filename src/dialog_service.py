import logging

from src.config import Config
from src.llm_client import LlmAuthError, LlmClient, LlmProviderError


class DialogService:
    def __init__(self, llm: LlmClient, config: Config) -> None:
        self._llm = llm
        self._config = config
        self._system_prompt = config.system_prompt
        self._max_pairs = config.dialog_max_pairs
        self._history: dict[int, list[dict[str, str]]] = {}

    def reload_settings(self) -> None:
        self._llm.reload_settings()
        self._system_prompt = self._config.system_prompt
        self._max_pairs = self._config.dialog_max_pairs
        logging.info(
            "LLM settings reloaded: model=%s, key_len=%d",
            self._config.model,
            len(self._config.open_api_key),
        )

    async def reply(self, user_id: int, user_message: str) -> str:
        self.reload_settings()

        messages = self._history.setdefault(user_id, [])
        messages.append({"role": "user", "content": user_message})
        self._trim(messages)

        messages_for_llm = [
            {"role": "system", "content": self._system_prompt},
            *messages,
        ]

        for attempt in range(2):
            try:
                reply = await self._llm.chat(messages_for_llm)
                break
            except (LlmAuthError, LlmProviderError):
                if attempt == 0:
                    self.reload_settings()
                    logging.info("LLM error, settings reloaded, retrying request")
                    continue
                messages.pop()
                raise
            except Exception:
                messages.pop()
                raise

        messages.append({"role": "assistant", "content": reply})
        self._trim(messages)
        return reply

    def _trim(self, messages: list[dict[str, str]]) -> None:
        max_messages = self._max_pairs * 2
        if len(messages) > max_messages:
            del messages[:-max_messages]
