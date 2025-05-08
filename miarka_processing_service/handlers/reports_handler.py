# pylint: disable=W0223,W0221,W0511, W0201
# W0201 needs to be disabled because this is the way that tornado demands that handlers
#       are setup
# TODO: remove these exceptions, see DEVELOP-440
"""
Handlers to retrieve links to reports, and actual report files.
"""

import re

from tornado.web import StaticFileHandler, HTTPError

from arteria.web.handlers import BaseRestHandler

from miarka_processing_service.handlers import NOT_FOUND
from miarka_processing_service.exceptions import RunfolderNotFound


class ReportsHandler(BaseRestHandler):
    """
    This will return reports corresponding to a specific runfolder, it will return them as links in json on the
    following format:
        {
        "links": [
            "http://localhost:9999/reports/foo_runfolder/v1/",
            "http://localhost:9999/reports/foo_runfolder/current/",
            "http://localhost:9999/reports/foo_runfolder/v2/"
            ]
        }
    """

    def initialize(self, reports_repo, **kwargs):
        """
        Instantiate a new ReportsHandler
        """
        self._reports_repo = reports_repo

    def get(self, runfolder):
        """
        Will return all reports available for a specific runfolder on the format:
            {
            "links": [
                "http://localhost:9999/reports/foo_runfolder/v1/",
                "http://localhost:9999/reports/foo_runfolder/current/",
                "http://localhost:9999/reports/foo_runfolder/v2/"
                ]
            }
        If there were no reports found for the specific runfolder the status will be 404 (NOT_FOUND).
        """
        try:
            report_versions = self._reports_repo.get_all_report_versions_for_runfolder(runfolder)
            links = []
            for version in report_versions:
                links.append('{}://{}{}'.format(self.request.protocol,
                                                self.request.host,
                                                self.reverse_url('report', '{}/{}'.format(runfolder, version))))
            self.write({'links': links})
        except RunfolderNotFound as exc:
            raise HTTPError(NOT_FOUND) from exc


class ReportFileHandler(StaticFileHandler):
    """
    This handler will return the actual report html file. It will accept requests on two different formats:
    /<api route>/<runfolder_name>/<version, e.g. v1 or v2> or /<api route>/<runfolder_name>/current.
    This first option will return the version of the report specified. The second option will return the
    report which is set as current (most often the most recent one).
    """

    def initialize(self, path, reports_repo, default_filename=None, **kwargs):
        self._reports_repo = reports_repo
        super().initialize(path, default_filename=default_filename)

    def validate_absolute_path(self, root, absolute_path):
        # This regex will match the following type of paths
        # <path_to_root>/reports/foo_runfolder/current
        # <path_to_root>/reports/foo_runfolder/v1
        # if there is a version this will be in the second group,
        # otherwise this will be empty.
        regex = r"^.+/" + re.escape(root) + r"/(\w+)/(v\d+|current)$"
        matches = re.match(regex, absolute_path)

        if not matches:
            raise HTTPError(NOT_FOUND)

        runfolder = matches.group(1)
        version = matches.group(2)

        if not runfolder:
            raise HTTPError(NOT_FOUND)

        try:
            if version:
                report_path = str(self._reports_repo.get_report_with_version(runfolder, version))
            else:
                report_path = str(self._reports_repo.get_current_report_for_runfolder(runfolder))
        except RunfolderNotFound as exc:
            raise HTTPError(NOT_FOUND) from exc

        return report_path
