import os
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Config:
    def __init__(self) -> None:
        load_dotenv(_ENV_FILE)
        self.telegram_bot_token = self._require("TELEGRAM_BOT_TOKEN")
        self.reload_llm_settings()

    def reload_llm_settings(self) -> None:
        load_dotenv(_ENV_FILE, override=True)
        self.open_api_key = self._require("OPEN_API_KEY")
        self.open_base_url = os.getenv("OPEN_BASE_URL", "https://openrouter.ai/api/v1").strip()
        self.model = (os.getenv("MODEL") or os.getenv(
            "LLM_MODEL", "nvidia/nemotron-3-nano-30b-a3b:free"
        )).strip()
        self.system_prompt = self._read_system_prompt()
        self.dialog_max_pairs = self._read_int("DIALOG_MAX_PAIRS", 20)

    def _read_int(self, name: str, default: int) -> int:
        raw = os.getenv(name, str(default)).strip()
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(f"{name} must be an integer") from exc
        if value < 1:
            raise ValueError(f"{name} must be >= 1")
        return value

    def _read_system_prompt(self) -> str:
        path = os.getenv("SYSTEM_PROMPT_FILE", "system.txt").strip()
        prompt_path = Path(path)
        if not prompt_path.is_absolute():
            prompt_path = _PROJECT_ROOT / prompt_path
        with open(prompt_path, encoding="utf-8") as file:
            content = file.read().strip()
        if not content:
            raise ValueError(f"{prompt_path} is empty")
        return content

    def _require(self, name: str) -> str:
        value = os.getenv(name)
        if not value:
            raise ValueError(f"{name} is required")
        return value.strip()
