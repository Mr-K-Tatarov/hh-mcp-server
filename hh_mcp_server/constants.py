from pathlib import Path

TOOL_TIMEOUT_SECONDS: float = 90.0
BASE_URL = "https://hh.ru"
PROFILE_DIR = Path.home() / ".hh-mcp" / "profile"
STATE_FILE = PROFILE_DIR / "state.json"

AREA_CODES = {
    "москва": "1",
    "санкт-петербург": "2",
    "екатеринбург": "3",
    "новосибирск": "4",
    "нижний новгород": "66",
    "казань": "88",
    "россия": "113",
}

SCHEDULE_MAP = {
    "remote": "remote",
    "office": "fullDay",
    "hybrid": "flyInFlyOut",
    "flexible": "flexible",
    "shift": "shift",
}

EXPERIENCE_MAP = {
    "no_experience": "noExperience",
    "1-3": "between1And3",
    "3-6": "between3And6",
    "6+": "moreThan6",
}
