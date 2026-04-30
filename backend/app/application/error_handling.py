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
            error_msg = f"{error_msg} (path: {request.url.path})"
        except RuntimeError:
            pass

    logger.error(f"API error: {error_type}: {error_msg}")

    # Log additional detail for OpenAI API status errors
    status_code = getattr(error, "status_code", None)
    if status_code is not None:
        body = getattr(error, "body", None)
        response = getattr(error, "response", None)
        headers = dict(response.headers) if response else None
        logger.debug(
            "API error detail: status={status}, headers={headers}, body={body}",
            status=status_code,
            headers=headers,
            body=body,
        )

    return SANITIZED_ERROR_MESSAGE
