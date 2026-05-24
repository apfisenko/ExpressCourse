import base64

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
from src.llm_client import LlmAuthError, LlmProviderError


class AudioClient:
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
        self._model = self._config.audio_model

    async def analyze(
        self,
        system_prompt: str,
        audio_bytes: bytes,
        audio_format: str,
    ) -> str:
        encoded = base64.b64encode(audio_bytes).decode("ascii")
        content: list[dict[str, object]] = [
            {"type": "text", "text": "Обработай голосовое сообщение пользователя."},
            {
                "type": "input_audio",
                "input_audio": {"data": encoded, "format": audio_format},
            },
        ]
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ]

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
