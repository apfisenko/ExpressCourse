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
from openai.types.chat import ChatCompletionMessageToolCall

from langsmith import traceable

from src.config import Config


class LlmAuthError(Exception):
    pass


class LlmProviderError(Exception):
    pass


class ModalityNotSupportedError(Exception):
    def __init__(self, modality: str, model: str) -> None:
        self.modality = modality
        self.model = model
        super().__init__(f"{modality} is not supported by {model}")


_MODALITY_UNSUPPORTED_MARKERS = (
    "does not support",
    "not support",
    "unsupported",
    "no endpoints found",
    "input audio",
    "input_audio",
    "multimodal",
    "vision",
    "image input",
    "audio input",
    "cannot process",
)


def raise_for_completion_error(
    exc: Exception,
    modality: str,
    model: str,
    *,
    local_provider: bool = False,
) -> None:
    if isinstance(exc, AuthenticationError):
        raise LlmAuthError from exc
    if isinstance(exc, PermissionDeniedError):
        if exc.status_code == 401:
            raise LlmAuthError from exc
        raise LlmProviderError from exc
    if isinstance(exc, APIStatusError):
        if _is_modality_unsupported(exc) or _is_local_modality_rejection(
            exc, modality, local_provider
        ):
            raise ModalityNotSupportedError(modality, model) from exc
    if isinstance(
        exc,
        (RateLimitError, APIConnectionError, APITimeoutError, APIStatusError, OpenAIError),
    ):
        raise LlmProviderError from exc
    raise exc


def _is_local_modality_rejection(
    exc: APIStatusError, modality: str, local_provider: bool
) -> bool:
    if not local_provider or modality not in ("audio", "image"):
        return False
    return exc.status_code in (400, 404, 422)


def _is_modality_unsupported(exc: APIStatusError) -> bool:
    if exc.status_code not in (400, 404, 422):
        return False
    text = str(exc).lower()
    body = getattr(exc, "body", None)
    if body:
        text = f"{text} {body}".lower()
    return any(marker in text for marker in _MODALITY_UNSUPPORTED_MARKERS)


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

    @traceable(name="llm_chat", run_type="llm")
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> tuple[str | None, list[ChatCompletionMessageToolCall] | None]:
        kwargs: dict = {"model": self._model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        try:
            response = await self._client.chat.completions.create(**kwargs)
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
            raise_for_completion_error(exc, "text", self._model)

        message = response.choices[0].message
        tool_calls = message.tool_calls or None
        content = message.content or None
        return content, tool_calls
