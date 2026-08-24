# pylint: disable=W0223,W0221,W0511,W0201,W0107
# W0201 needs to be disabled because this is the way that tornado demands that handlers
#       are setup
# TODO: remove these exceptions
"""
Get the version of the service
"""
from arteria.web.handlers import BaseRestHandler

from miarka_processing_service import __version__ as version


class VersionHandler(BaseRestHandler):
    """
    Get the version of the service
    """

    def initialize(self, **kwargs):
        """
        Initialize new VersionHandler
        """
        pass

    def get(self):
        """
        Returns the version of the checksum-service as json. Format looks as follows:
        {
           "version": "1.0.0"
        }
        """
        self.write_object({"version": version})
