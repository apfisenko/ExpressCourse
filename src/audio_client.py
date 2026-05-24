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
from src.llm_client import LlmAuthError, LlmProviderError, raise_for_completion_error


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
        user_text = "Обработай голосовое сообщение пользователя."

        if self._config.is_local_provider:
            # Ollama: WAV через image_url (input_audio не поддерживается)
            content: list[dict[str, object]] = [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:audio/wav;base64,{encoded}"},
                },
                {"type": "text", "text": user_text},
            ]
        else:
            content = [
                {"type": "text", "text": user_text},
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
            raise_for_completion_error(
                exc, "audio", self._model, local_provider=self._config.is_local_provider
            )

        return response.choices[0].message.content or ""
