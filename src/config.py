import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"

_OPENROUTER_DEFAULT_MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"
_OPENROUTER_DEFAULT_VISION = "google/gemini-2.0-flash-lite-preview-02-05:free"
_OPENROUTER_DEFAULT_AUDIO = "openai/gpt-audio-mini"
_LOCAL_DEFAULT_MODEL = "llama3.2"


class Config:
    def __init__(self) -> None:
        load_dotenv(_ENV_FILE)
        self.telegram_bot_token = self._require("TELEGRAM_BOT_TOKEN")
        self.langsmith_enabled = os.getenv("LANGSMITH_ENABLED", "false").strip().lower() == "true"
        self.langsmith_api_key = os.getenv("LANGSMITH_API_KEY", "").strip()
        self.langsmith_project = os.getenv("LANGSMITH_PROJECT", "expresscourse").strip()
        self.reload_llm_settings()

    def reload_llm_settings(self) -> None:
        load_dotenv(_ENV_FILE, override=True)
        self.open_base_url = os.getenv(
            "OPEN_BASE_URL", "https://openrouter.ai/api/v1"
        ).strip()
        self.is_local_provider = self._is_local_provider(self.open_base_url)
        self.open_api_key = self._read_api_key(self.open_base_url)
        self.model = self._read_model("MODEL", _LOCAL_DEFAULT_MODEL, _OPENROUTER_DEFAULT_MODEL)
        self.system_prompt = self._read_prompt_file("SYSTEM_PROMPT_FILE", "system.txt")
        self.image_prompt = self._read_prompt_file("IMAGE_PROMPT_FILE", "prompts/image.txt")
        self.audio_prompt = self._read_prompt_file("AUDIO_PROMPT_FILE", "prompts/audio.txt")
        self.vision_model = self._read_model(
            "VISION_MODEL", self.model, _OPENROUTER_DEFAULT_VISION
        )
        self.audio_model = self._read_model(
            "AUDIO_MODEL", self.model, _OPENROUTER_DEFAULT_AUDIO
        )
        self.dialog_max_pairs = self._read_int("DIALOG_MAX_PAIRS", 20)

    def _read_model(
        self, env_name: str, local_default: str, cloud_default: str
    ) -> str:
        value = os.getenv(env_name)
        if value and value.strip():
            name = value.strip()
            if self.is_local_provider and self._looks_like_cloud_model(name):
                return local_default
            return name
        if self.is_local_provider:
            return local_default
        return cloud_default

    @staticmethod
    def _looks_like_cloud_model(name: str) -> bool:
        if "/" not in name:
            return False
        provider = name.split("/", 1)[0].lower()
        return provider not in {"ollama", "local"}

    @staticmethod
    def _is_local_provider(base_url: str) -> bool:
        return "openrouter.ai" not in base_url.lower()

    def _read_int(self, name: str, default: int) -> int:
        raw = os.getenv(name, str(default)).strip()
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(f"{name} must be an integer") from exc
        if value < 1:
            raise ValueError(f"{name} must be >= 1")
        return value

    def _read_prompt_file(self, env_name: str, default_path: str) -> str:
        path = os.getenv(env_name, default_path).strip()
        prompt_path = Path(path)
        if not prompt_path.is_absolute():
            prompt_path = _PROJECT_ROOT / prompt_path
        with open(prompt_path, encoding="utf-8") as file:
            content = file.read().strip()
        if not content:
            raise ValueError(f"{prompt_path} is empty")
        return content

    def _read_api_key(self, base_url: str) -> str:
        for name in ("OPEN_API_KEY", "OPENROUTER_API_KEY"):
            value = os.getenv(name)
            if value and value.strip():
                return value.strip()
        if "openrouter.ai" in base_url.lower():
            raise ValueError("One of OPEN_API_KEY, OPENROUTER_API_KEY is required for OpenRouter")
        return "ollama"

    def _require(self, name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise ValueError(f"{name} is required")
        return value.strip()
