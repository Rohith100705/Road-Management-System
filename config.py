from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Centralized configuration loaded from the project .env file."""

    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_DB = os.getenv("MONGO_DB")
    MONGO_COLLECTION = os.getenv("MONGO_COLLECTION")
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "8050"))
    HIGH_MODEL_PATH = os.getenv("HIGH_MODEL_PATH")
    LOW_MODEL_PATH = os.getenv("LOW_MODEL_PATH")
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
    IGNORE_TOP_PERCENTAGE = float(os.getenv("IGNORE_TOP_PERCENTAGE", "0.3"))
    MIN_BBOX_AREA_RATIO = float(os.getenv("MIN_BBOX_AREA_RATIO", "0.001"))
    MAX_BBOX_AREA_RATIO = float(os.getenv("MAX_BBOX_AREA_RATIO", "0.5"))
    MAX_ASPECT_RATIO = float(os.getenv("MAX_ASPECT_RATIO", "1.2"))
    DEBUG_MODE = bool(os.getenv("DEBUG_MODE", "False") == "True")
    DETECTION_INTERVAL = int(os.getenv("DETECTION_INTERVAL", "10"))
    STATIC_IMAGE_DIR = BASE_DIR / "static" / "images"
    TEST_IMAGE_PATH = BASE_DIR / "Test" / "1.png"
    TEST_VIDEO_PATH = BASE_DIR / "Test" / "Pothole Exp1.mp4"

    @classmethod
    def validate(cls) -> None:
        """Raise a clear error if required environment variables are missing."""
        required = [
            "MONGO_URI",
            "MONGO_DB",
            "MONGO_COLLECTION",
            "GOOGLE_MAPS_API_KEY",
            "FLASK_SECRET_KEY",
            "HIGH_MODEL_PATH",
            "LOW_MODEL_PATH",
        ]
        missing = [name for name in required if not getattr(cls, name)]
        if missing:
            missing_str = ", ".join(missing)
            raise RuntimeError(f"Missing required environment variables in .env: {missing_str}")

        cls.STATIC_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


Config.validate()
try:
    print("✅ Config loaded successfully")
except UnicodeEncodeError:
    print("Config loaded successfully")
