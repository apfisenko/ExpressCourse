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


class ImageClient:
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
        self._model = self._config.vision_model

    async def analyze(
        self,
        system_prompt: str,
        image_bytes: bytes,
        mime_type: str,
        user_text: str,
    ) -> str:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        image_url = f"data:{mime_type};base64,{encoded}"

        content: list[dict[str, object]] = [
            {"type": "text", "text": user_text},
            {"type": "image_url", "image_url": {"url": image_url}},
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
