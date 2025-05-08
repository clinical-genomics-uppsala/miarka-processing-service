"""
The ReportsRepository finds and presents reports.
"""
import os
from pathlib import Path
import logging
from queue import Queue
import dataclasses


from miarka_processing_service.exceptions import RunfolderNotFound


log = logging.getLogger(__name__)


class ReportsRepository:
    """
    The ReportsRepository finds and presents reports.
    There can be multiple reports associated with a single runfolder, these are denoted v1, v2, etc.
    There should be a link in the reports base directory which indicates which is the current report
    (normally this should be the most recent one).
    """

    def __init__(self, reports_dir):
        """
        Instantiate a ReportsRepository
        :param reports_dir: the base paths were runfolders/reports can be found.
        """
        self._reports_dir = reports_dir

    @staticmethod
    def _bf_search(search_for, root, max_depth):
        """
        Search a directory for a directory with a `search_for` breath from `root` to a
        maximum recursion depth of `max_depth`
        """

        # pylint: disable=R0903
        @dataclasses.dataclass
        class PathLevel():
            """
            Representation of a path and the level they were found at compared to the root
            """
            path: Path
            level: int

        queue = Queue()
        queue.put(PathLevel(path=Path(root), level=0))
        while True:
            if queue.empty():
                return None

            elem = queue.get()

            if elem.level > max_depth:
                return None

            if elem.path.name == search_for:
                return elem.path

            dirs = [x for x in elem.path.iterdir() if x.is_dir()]
            for directory in dirs:
                queue.put(PathLevel(path=directory, level=elem.level + 1))

    def _find_runfolder_dir(self, runfolder):
        result = self._bf_search(runfolder, self._reports_dir, 3)
        if not result:
            raise RunfolderNotFound(
                f"Could not identify a runfolder with the name: "
                f"{runfolder} in any of the monitored directories.")
        return result

    def get_report_with_version(self, runfolder, version):
        """
        The path to the report for the specified version
        :param runfolder:
        :param version:
        :return: a Path to the report or None if there was no report
        :raises: RunfolderNotFound if there was no such runfolder
        """
        runfolder_dir = self._find_runfolder_dir(runfolder)
        return runfolder_dir / 'reports' / version / 'multiqc_report.html'

    def get_current_report_for_runfolder(self, runfolder):
        """
        Get the current report for the runfolder.
        :param runfolder:
        :return: the path to the report or None
        :raises: RunfolderNotFound if there was no such runfolder
        """
        return self.get_report_with_version(runfolder, 'current')

    def get_all_report_versions_for_runfolder(self, runfolder):
        """
        Find all the report versions for the specified runfolder
        :param runfolder:
        :return: a generator of available version, e.g. v1, v2, current
        """

        runfolder_dir = self._find_runfolder_dir(runfolder)
        for report_dir in os.listdir(runfolder_dir / 'reports'):
            if (runfolder_dir / 'reports' / report_dir).is_dir():
                yield report_dir
