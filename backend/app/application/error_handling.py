from loguru import logger


SANITIZED_ERROR_MESSAGE = "An unexpected error occurred. Please try again."


def sanitize_error_message(error: Exception) -> str:
    """Sanitize error message for client display.

    Logs the full error detail server-side and returns a generic
    message that doesn't expose internal implementation details.

    Args:
        error: The exception to sanitize.

    Returns:
        A generic, user-safe error message.
    """
    error_type = type(error).__name__
    error_msg = str(error) if str(error) else "(no message)"

    if hasattr(error, "request"):
        try:
            request = error.request
            error_msg = f"{error_msg} (URL: {request.url})"
        except RuntimeError:
            pass

    logger.error(f"API error: {error_type}: {error_msg}")

    return SANITIZED_ERROR_MESSAGE
