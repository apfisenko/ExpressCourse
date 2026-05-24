import asyncio
import logging
import re

from src.audio_client import AudioClient
from src.audio_converter import AudioConverter
from src.config import Config
from src.image_client import ImageClient
from src.llm_client import LlmAuthError, LlmProviderError, ModalityNotSupportedError

_PROFILE_FIELDS = {
    "goals": re.compile(
        r"(?i)(?:^|\n)\s*(?:моя\s+)?цел[ья]\s*[:\-—]\s*(.+?)(?:\n|$)"
    ),
    "restrictions": re.compile(
        r"(?i)(?:^|\n)\s*ограничени[яе]\s*[:\-—]\s*(.+?)(?:\n|$)"
    ),
    "allergies": re.compile(
        r"(?i)(?:^|\n)\s*аллерги[яи]\s*[:\-—]\s*(.+?)(?:\n|$)"
    ),
    "preferences": re.compile(
        r"(?i)(?:^|\n)\s*предпочтени[яе]\s*[:\-—]\s*(.+?)(?:\n|$)"
    ),
}

_PROFILE_LABELS = {
    "goals": "Цели",
    "restrictions": "Ограничения",
    "allergies": "Аллергии",
    "preferences": "Предпочтения",
}


class DialogService:
    def __init__(
        self, llm: LlmClient, image: ImageClient, audio: AudioClient, config: Config
    ) -> None:
        self._llm = llm
        self._image = image
        self._audio = audio
        self._config = config
        self._system_prompt = config.system_prompt
        self._image_prompt = config.image_prompt
        self._audio_prompt = config.audio_prompt
        self._max_pairs = config.dialog_max_pairs
        self._history: dict[int, list[dict[str, str]]] = {}
        self._profiles: dict[int, dict[str, str]] = {}

    def reload_settings(self) -> None:
        self._llm.reload_settings()
        self._image.reload_settings()
        self._audio.reload_settings()
        self._system_prompt = self._config.system_prompt
        self._image_prompt = self._config.image_prompt
        self._audio_prompt = self._config.audio_prompt
        self._max_pairs = self._config.dialog_max_pairs
        logging.info(
            "LLM settings reloaded: model=%s, vision=%s, audio=%s, local=%s, key_len=%d",
            self._config.model,
            self._config.vision_model,
            self._config.audio_model,
            self._config.is_local_provider,
            len(self._config.open_api_key),
        )

    async def reply(self, user_id: int, user_message: str) -> str:
        self.reload_settings()
        self._try_update_profile(user_id, user_message)

        messages = self._history.setdefault(user_id, [])
        messages.append({"role": "user", "content": user_message})
        self._trim(messages)

        messages_for_llm = [
            {"role": "system", "content": self._build_system_content(user_id)},
            *messages,
        ]

        reply = await self._call_with_retry(
            lambda: self._llm.chat(messages_for_llm),
            on_retry=lambda: self._refresh_system_message(messages_for_llm, user_id),
            on_failure=lambda: messages.pop(),
        )

        messages.append({"role": "assistant", "content": reply})
        self._trim(messages)
        return reply

    async def reply_photo(
        self,
        user_id: int,
        image_bytes: bytes,
        mime_type: str,
        caption: str = "",
    ) -> str:
        self.reload_settings()
        if caption:
            self._try_update_profile(user_id, caption)

        history_label = f"[Фото] {caption.strip()}" if caption.strip() else "[Фото]"
        messages = self._history.setdefault(user_id, [])
        messages.append({"role": "user", "content": history_label})
        self._trim(messages)

        user_text = caption.strip() or "Проанализируй фото и дай рекомендации по питанию."
        system_content = {"value": self._build_image_system_content(user_id)}

        reply = await self._call_with_retry(
            lambda: self._image.analyze(
                system_content["value"], image_bytes, mime_type, user_text
            ),
            on_retry=lambda: system_content.update(
                value=self._build_image_system_content(user_id)
            ),
            on_failure=lambda: messages.pop(),
        )

        messages.append({"role": "assistant", "content": reply})
        self._trim(messages)
        return reply

    async def reply_voice(self, user_id: int, ogg_bytes: bytes) -> str:
        self.reload_settings()

        if self._config.is_local_provider:
            audio_bytes = await asyncio.to_thread(
                AudioConverter.telegram_voice_to_wav, ogg_bytes
            )
            audio_format = "wav"
        else:
            audio_bytes = await asyncio.to_thread(
                AudioConverter.telegram_voice_to_mp3, ogg_bytes
            )
            audio_format = "mp3"

        messages = self._history.setdefault(user_id, [])
        messages.append({"role": "user", "content": "[Голосовое сообщение]"})
        self._trim(messages)

        system_content = {"value": self._build_audio_system_content(user_id)}

        reply = await self._call_with_retry(
            lambda: self._audio.analyze(
                system_content["value"], audio_bytes, audio_format
            ),
            on_retry=lambda: system_content.update(
                value=self._build_audio_system_content(user_id)
            ),
            on_failure=lambda: messages.pop(),
        )

        self._try_update_profile(user_id, reply)
        messages.append({"role": "assistant", "content": reply})
        self._trim(messages)
        return reply

    async def _call_with_retry(self, call, on_retry, on_failure) -> str:
        for attempt in range(2):
            try:
                return await call()
            except ModalityNotSupportedError:
                on_failure()
                raise
            except (LlmAuthError, LlmProviderError):
                if attempt == 0:
                    self.reload_settings()
                    on_retry()
                    logging.info("LLM error, settings reloaded, retrying request")
                    continue
                on_failure()
                raise
            except Exception:
                on_failure()
                raise
        raise RuntimeError("unreachable")

    def _refresh_system_message(
        self, messages_for_llm: list[dict[str, str]], user_id: int
    ) -> None:
        messages_for_llm[0]["content"] = self._build_system_content(user_id)

    def _build_system_content(self, user_id: int) -> str:
        return self._append_profile(self._system_prompt, user_id)

    def _build_image_system_content(self, user_id: int) -> str:
        return self._append_profile(self._image_prompt, user_id)

    def _build_audio_system_content(self, user_id: int) -> str:
        return self._append_profile(self._audio_prompt, user_id)

    def _append_profile(self, base_prompt: str, user_id: int) -> str:
        profile_block = self._format_profile(user_id)
        if not profile_block:
            return base_prompt
        return f"{base_prompt}\n\n{profile_block}"

    def _format_profile(self, user_id: int) -> str:
        profile = self._profiles.get(user_id)
        if not profile:
            return ""

        lines = [
            f"{_PROFILE_LABELS[key]}: {profile[key]}"
            for key in _PROFILE_LABELS
            if profile.get(key)
        ]
        if not lines:
            return ""
        return (
            "Известный профиль пользователя (учитывай при рекомендациях):\n"
            + "\n".join(lines)
        )

    def _try_update_profile(self, user_id: int, text: str) -> None:
        profile = self._profiles.setdefault(user_id, {})
        for field, pattern in _PROFILE_FIELDS.items():
            match = pattern.search(text)
            if match:
                profile[field] = match.group(1).strip()

    def _trim(self, messages: list[dict[str, str]]) -> None:
        max_messages = self._max_pairs * 2
        if len(messages) > max_messages:
            del messages[:-max_messages]
