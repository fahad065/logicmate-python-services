"""
Shared configuration — loaded once, used everywhere.
All pipelines import from here.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── NestJS backend ────────────────────────────────────────────
NESTJS_URL       = os.getenv("NESTJS_URL", "http://localhost:4000/api/v1")
NESTJS_TOKEN     = os.getenv("NESTJS_SERVICE_TOKEN", "")
ADMIN_EMAIL      = os.getenv("ADMIN_EMAIL", "")
ADMIN_PASSWORD   = os.getenv("ADMIN_PASSWORD", "")

# ── AI APIs ───────────────────────────────────────────────────
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
ATLAS_API_KEY    = os.getenv("ATLAS_API_KEY", "")

# ── Output storage ────────────────────────────────────────────
OUTPUT_BASE      = os.getenv("OUTPUT_BASE_DIR", "/tmp/nexagent/output")

# ── Email ─────────────────────────────────────────────────────
GMAIL_USER       = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASS   = os.getenv("GMAIL_APP_PASSWORD", "")

# ── Defaults ──────────────────────────────────────────────────
DEFAULT_NICHE    = os.getenv("NICHE", "dark psychology and human behavior")
NUM_CLIPS        = int(os.getenv("NUM_CLIPS", "12"))
CLIP_DURATION    = int(os.getenv("CLIP_DURATION", "5"))
TARGET_DURATION  = int(os.getenv("TARGET_DURATION", "420"))
NUM_SHORTS       = int(os.getenv("NUM_SHORTS", "3"))

# ── Platform detection (macOS vs Linux/Railway) ───────────────
import platform
IS_MACOS         = platform.system() == "Darwin"
IS_LINUX         = platform.system() == "Linux"