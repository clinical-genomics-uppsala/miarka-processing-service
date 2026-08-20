# pylint: disable=W0107
# Intentionally disabling unnecessary-pass to allow for otherwise empty exception classes.
"""
Custom exceptions for miarka-processing-service.
"""


class ProcessingBaseException(Exception):
    """
    Base exception class for miarka-processing-service.
    """
    pass


class ConfigurationError(ProcessingBaseException):
    """
    Exception in case required configuration key cannot be retrieved.
    """
    pass


class UnableToStopJob(ProcessingBaseException):
    """
    Exception in case job cannot be stopped because it does not exist on a cancellable state.
    """
    pass


class CreateDirectoryError(ProcessingBaseException):
    """
    Exception thrown when there is a problem with creating a directory on miarka.
    """
    pass
