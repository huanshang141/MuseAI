"""Logging configuration module using loguru.

Provides:
- Async logging for high concurrency
- JSON structured format
- Per-module log files
- Time-based rotation with 7-day retention
"""

import sys
from pathlib import Path

from loguru import logger

from app.config.settings import Settings


def _get_log_file(log_dir: Path, module: str) -> Path:
    """Get log file path for a module."""
    return log_dir / f"{module}.log"


def _json_format(record: dict) -> str:
    """Format log record as JSON string for custom output."""
    import json

    log_entry = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
    }

    # Add extra fields if present
    if record.get("extra"):
        log_entry["extra"] = record["extra"]

    # Add exception info if present
    if record["exception"]:
        log_entry["exception"] = {
            "type": record["exception"].type.__name__ if record["exception"].type else None,
            "value": str(record["exception"].value) if record["exception"].value else None,
            "traceback": record["exception"].traceback if record["exception"].traceback else None,
        }

    return json.dumps(log_entry, ensure_ascii=False)


def _text_format(record: dict) -> str:
    """Format log record as human-readable text."""
    timestamp = record["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    level = record["level"].name
    module = record["module"]
    function = record["function"]
    line = record["line"]
    message = record["message"]

    base = f"{timestamp} | {level: <8} | {module}:{function}:{line} - {message}"
    if record["exception"]:
        base += f"\n{record['exception']}"
    return base


def setup_logging(settings: Settings) -> None:
    """Configure loguru logging based on settings.

    Args:
        settings: Application settings containing log configuration
    """
    # Remove default handler
    logger.remove()

    # Create log directory
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Determine format based on settings
    is_json = settings.LOG_FORMAT.lower() == "json"
    log_level = settings.LOG_LEVEL.upper()

    # Console handler - always text for readability, use string format to avoid colorization issues
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{module}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    logger.add(
        sys.stdout,
        format=console_format,
        level=log_level,
        colorize=True,
    )

    # Module-specific file handlers
    modules = ["app", "auth", "chat", "document", "infra"]

    for module in modules:
        log_file = _get_log_file(log_dir, module)

        if is_json:
            # JSON format with serialization
            logger.add(
                str(log_file),
                format="{message}",
                filter=lambda record, m=module: _should_log_to_module(record, m),
                rotation="00:00",  # Daily rotation at midnight
                retention="7 days",
                level=log_level,
                serialize=True,  # Built-in JSON serialization
                enqueue=True,  # Async writes for high concurrency
            )
        else:
            # Text format
            logger.add(
                str(log_file),
                format=_text_format,
                filter=lambda record, m=module: _should_log_to_module(record, m),
                rotation="00:00",
                retention="7 days",
                level=log_level,
                enqueue=True,
            )

    logger.info("Logging system initialized", extra={"log_dir": str(log_dir), "log_level": log_level})


def _should_log_to_module(record: dict, module: str) -> bool:
    """Determine if a log record should go to a specific module file.

    Routes logs based on the module field in the log record:
    - app: main.py, lifespan, startup/shutdown
    - auth: auth.py, auth_service.py, jwt, password
    - chat: chat.py, chat_service.py, rag
    - document: documents.py, document_service.py, ingestion
    - infra: elasticsearch, redis, llm, embeddings, providers
    """
    record_module = record.get("module", "")
    record_name = record.get("name", "")
    record_path = record.get("file", "")
    if hasattr(record_path, "path"):
        record_path = str(record_path.path)
    else:
        record_path = str(record_path)

    # Map modules to their source files
    module_mappings = {
        "app": ["main", "config"],
        "auth": ["auth", "auth_service", "jwt_handler", "password"],
        "chat": ["chat", "chat_service", "rag", "multi_turn", "query_transform"],
        "document": ["document", "document_service", "ingestion", "chunking"],
        "infra": [
            "elasticsearch",
            "redis",
            "llm",
            "embedding",
            "embeddings",
            "retrievers",
            "agents",
            "database",
            "models",
        ],
    }

    target_modules = module_mappings.get(module, [])

    # Check if record's module matches any target
    for target in target_modules:
        if target.lower() in record_module.lower() or target.lower() in record_name.lower():
            return True
        if target.lower() in record_path.lower():
            return True

    # Default: only log to 'app' if no specific module matched
    return module == "app"


def get_logger(module_name: str) -> "logger":
    """Get a logger bound to a specific module.

    Args:
        module_name: Name of the module for log routing

    Returns:
        Logger instance bound to the module
    """
    return logger.bind(module=module_name)
