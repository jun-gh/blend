#!/usr/bin/env python3
"""Sync non-secret configuration from backend/.env to infra/app.env and Bicep templates.

Run this whenever you change model names or search weights in your local .env,
or let the pre-commit hook run it automatically.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_ENV = ROOT / "backend" / ".env"
FALLBACK_ENV = ROOT / ".env"
APP_ENV = ROOT / "infra" / "app.env"
MAIN_BICEP = ROOT / "infra" / "main.bicep"
CONTAINER_APP_BICEP = ROOT / "infra" / "modules" / "container-app.bicep"

SYNC_KEYS = [
    "GEMINI_CHAT_MODEL",
    "GEMINI_EMBED_MODEL",
    "EMBEDDING_DIMENSIONS",
    "DENSE_WEIGHT",
    "SPARSE_WEIGHT",
    "TOP_K_RETRIEVAL",
    "TOP_K_CONTEXT",
    "SITE_PASSWORD",
    "SESSION_EXPIRY_DAYS",
    "MAX_DOCUMENTS_PER_SESSION",
]


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            data[key] = val
    return data


def sync() -> None:
    env_data = parse_env_file(FALLBACK_ENV)
    env_data.update(parse_env_file(BACKEND_ENV))

    synced: dict[str, str] = {}
    for key in SYNC_KEYS:
        if key in env_data:
            synced[key] = env_data[key]

    if not synced:
        print("[sync_env] No matching keys found in .env files to sync.")
        return

    # 1. Update infra/app.env
    app_env_content = (
        "# Shared and production configuration synced from backend/.env\n"
        "# This file is tracked in git so GitHub Actions deployments preserve your settings.\n"
    )
    for key, val in synced.items():
        app_env_content += f"{key}={val}\n"
    APP_ENV.write_text(app_env_content, encoding="utf-8")
    print(f"[sync_env] Updated {APP_ENV.relative_to(ROOT)}")

    # 2. Update default params in Bicep files
    param_map = {
        "GEMINI_CHAT_MODEL": ("geminiChatModel", "string"),
        "GEMINI_EMBED_MODEL": ("geminiEmbedModel", "string"),
        "EMBEDDING_DIMENSIONS": ("embeddingDimensions", "int"),
        "DENSE_WEIGHT": ("denseWeight", "string"),
        "SPARSE_WEIGHT": ("sparseWeight", "string"),
        "TOP_K_RETRIEVAL": ("topKRetrieval", "string"),
        "TOP_K_CONTEXT": ("topKContext", "string"),
        "SITE_PASSWORD": ("sitePassword", "string"),
        "SESSION_EXPIRY_DAYS": ("sessionExpiryDays", "int"),
        "MAX_DOCUMENTS_PER_SESSION": ("maxDocumentsPerSession", "int"),
    }

    for bicep_file in (MAIN_BICEP, CONTAINER_APP_BICEP):
        if not bicep_file.is_file():
            continue
        content = bicep_file.read_text(encoding="utf-8")
        for env_key, (param_name, param_type) in param_map.items():
            if env_key not in synced:
                continue
            val = synced[env_key]
            if param_type == "string":
                pattern = rf"(param\s+{param_name}\s+string\s*=\s*)'[^']*'"
                replacement = rf"\g<1>'{val}'"
            else:
                pattern = rf"(param\s+{param_name}\s+int\s*=\s*)\d+"
                replacement = rf"\g<1>{val}"
            content = re.sub(pattern, replacement, content)
        bicep_file.write_text(content, encoding="utf-8")
        print(f"[sync_env] Updated defaults in {bicep_file.relative_to(ROOT)}")

    print("[sync_env] Successfully synced settings:")
    for k, v in synced.items():
        print(f"  • {k} = {v}")


if __name__ == "__main__":
    sync()
