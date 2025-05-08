# pylint: disable=W0107
# Intentionally disabling unnecessary-pass to allow for otherwise empty exception classes.
"""
Custom exceptions for sequencing-report-service.
"""


class SequencingReportBaseException(Exception):
    """
    Base exception class for sequencing-report-service.
    """
    pass


class ConfigurationError(SequencingReportBaseException):
    """
    Exception in case required configuration key cannot be retrieved.
    """
    pass


class RunfolderNotFound(SequencingReportBaseException):
    """
    Exception in case specified runfolder does not exist.
    """
    pass


class UnableToStopJob(SequencingReportBaseException):
    """
    Exception in case job cannot be stopped because it does not exist on a cancellable state.
    """
    pass


class NextflowConfigError(ConfigurationError):
    """
    Exception thrown when there is a problem with the configuration of the nextflow job.
    """
    pass
