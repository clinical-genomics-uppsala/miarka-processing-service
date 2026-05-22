# pylint: disable=R0903

"""
Module for classes and functions related to the identification of runfolders.
"""

from pathlib import Path

from miarka_processing_service.exceptions import ConfigurationError, RunfolderNotFound


class RunfolderRepository():
    """
    The RunfolderRepository is used to monitor a list of directories and returns paths to runfolders in these.
    """

    def __init__(self, monitored_directories):
        """
        Input a list of monitored directories, for this repository to look at
        """
        self._monitored_dirs = monitored_directories
        if not isinstance(self._monitored_dirs, list) and self._monitored_dirs is not None:
            raise ConfigurationError('"monitored_directories" in the config must be a list!')

    def get_runfolder(self, runfolder):
        """
        Return the path to the specified runfolder if it exists in one of the monitored directories,
         otherwise raise RunfolderNotFound Exception.
        """

        for directory in self._monitored_dirs:
            potential_runfolder = Path(directory) / runfolder
            if potential_runfolder.exists():
                return potential_runfolder
        raise RunfolderNotFound(
            f"Could not identify a runfolder with the name: {runfolder} in any of the monitored directories.")
