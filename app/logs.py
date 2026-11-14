from __future__ import annotations

import logging
import pathlib

_LOGGER_NAME = "codemitra"


def setup_logging(workspace: str | None = None) -> logging.Logger:
    """Configure a simple file logger for CLI commands."""
    root = pathlib.Path(workspace).resolve() if workspace else pathlib.Path.cwd().resolve()
    log_dir = root / ".codemitra"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "codemitra.log"

    logger = logging.getLogger(_LOGGER_NAME)
    configured_path = getattr(logger, "_codemitra_log_path", None)
    if configured_path == str(log_path):
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)

    logger._codemitra_log_path = str(log_path)  # type: ignore[attr-defined]
    return logger
