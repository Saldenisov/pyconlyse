"""Plain-data exception diagnostics, without importing a driver or clearing errors.

An SDK exception's signed I32 ``error_code`` is metadata, not a reconstructed
LabVIEW error cluster. Diagnostic inspection must never mask the exception
being handled, including when its metadata or string conversion raises.
"""


MESSAGE_LIMIT = 2048


def describe_driver_exception(error):
    """Return bounded JSON data while leaving the supplied exception untouched.

    Only an exact signed I32 ``exception.error_code`` is accepted. Boolean,
    coerced, unsigned, string and enum representations are deliberately absent.
    Metadata access and string conversion are guarded independently so an
    unavailable message does not discard an otherwise available numeric code.
    """
    try:
        error_type = type(error).__name__
        if type(error_type) is not str:
            error_type = "Exception"
    except BaseException:
        error_type = "Exception"
    try:
        message = str(error)
        # __str__ may return a str subclass; retain no custom metadata objects.
        if type(message) is not str:
            message = str.__str__(message)
    except BaseException:
        message = "<exception message unavailable>"
    truncated = len(message) > MESSAGE_LIMIT
    message = message[:MESSAGE_LIMIT]
    try:
        code = error.error_code
    except BaseException:
        code = None
    available = type(code) is int and -2147483648 <= code <= 2147483647
    return {
        "error_type": error_type,
        "message": message,
        "message_truncated": truncated,
        "error_code": code if available else None,
        "error_code_available": available,
        "error_code_origin": "exception.error_code" if available else None,
        "native_error_cluster_inferred": False,
    }
