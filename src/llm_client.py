from openai import (
    APIConnectionError,
    APITimeoutError,
    APIStatusError,
    AsyncOpenAI,
    AuthenticationError,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)

from src.config import Config


class LlmAuthError(Exception):
    pass


class LlmProviderError(Exception):
    pass


class LlmClient:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._apply_settings()

    def reload_settings(self) -> None:
        self._config.reload_llm_settings()
        self._apply_settings()

    def _apply_settings(self) -> None:
        self._client = AsyncOpenAI(
            api_key=self._config.open_api_key,
            base_url=self._config.open_base_url,
        )
        self._model = self._config.model

    async def chat(self, messages: list[dict[str, str]]) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
            )
        except AuthenticationError as exc:
            raise LlmAuthError from exc
        except PermissionDeniedError as exc:
            if exc.status_code == 401:
                raise LlmAuthError from exc
            raise LlmProviderError from exc
        except (
            RateLimitError,
            APIConnectionError,
            APITimeoutError,
            APIStatusError,
            OpenAIError,
        ) as exc:
            raise LlmProviderError from exc

        return response.choices[0].message.content or ""
