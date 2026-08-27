from starlette import status


class AppError(Exception):
    """Domain error that the API layer maps to an HTTP response."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    message = "Internal Server Error"

    def __init__(self, message: str | None = None):
        self.message = message or type(self).message
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    message = "Resource not found"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    message = "Forbidden"