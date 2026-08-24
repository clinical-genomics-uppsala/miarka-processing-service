
import json
from pathlib import Path


from tornado.testing import AsyncHTTPTestCase, ExpectLog
from tornado.web import Application

import mock

from miarka_processing_service.app import routes
from miarka_processing_service.services.local_runner_service import LocalRunnerService
from miarka_processing_service.models.db_models import Job, State
import importlib.metadata

version = importlib.metadata.version("miarka-processing-service")


class TestJobHandler(AsyncHTTPTestCase):
    START_ANALYSIS_BODY = json.dumps({"analysis_path": "/analysis/ABC-123",
                                      "runscript": "/scripts/start_wp1_GMS560.sh",
                                      "inbox_path": "/inbox/ABC-123"})
    CREATE_DIRECTORY_BODY = json.dumps({"path": "/analysis/ABC-123"})
    SYNC_DIRECTORY_BODY = json.dumps({"source_directory": "/analysis/ABC-123",
                                      "destination_directory": "/outbox/ABC-123"})

    def get_app(self):

        mock_runner_service = mock.create_autospec(LocalRunnerService)
        job = Job(job_id=1, command=['foo'], state=State.PENDING)
        mock_runner_service.get_jobs = mock.MagicMock(return_value=[job])
        mock_runner_service.get_job = mock.MagicMock(return_value=job)
        mock_runner_service.start_runscript = mock.MagicMock(return_value=job.job_id)
        mock_runner_service.create_directory = mock.MagicMock(return_value=job.job_id)
        mock_runner_service.sync_directory = mock.MagicMock(return_value=job.job_id)
        mock_runner_service.stop = mock.MagicMock(return_value=job)

        # Kept so that individual tests can make the service layer fail on demand
        self.mock_runner_service = mock_runner_service

        return Application(routes(runner_service=mock_runner_service))

    def test_get_jobs(self):
        response = self.fetch('/api/1.0/jobs/')
        self.assertEqual(response.code, 200)
        resp_dict = json.loads(response.body)

        self.assertEqual(resp_dict['version'], version)

        jobs_dict = resp_dict['jobs'][0]
        self.assertEqual(jobs_dict['command'], ['foo'])
        self.assertEqual(jobs_dict['job_id'], 1)
        self.assertEqual(jobs_dict['state'], 'pending')

    def test_get_job(self):
        response = self.fetch('/api/1.0/jobs/1')
        self.assertEqual(response.code, 200)
        resp_dict = json.loads(response.body)
        self.assertEqual(resp_dict['command'], ['foo'])
        self.assertEqual(resp_dict['job_id'], 1)
        self.assertEqual(resp_dict['state'], 'pending')
        self.assertEqual(resp_dict['version'], version)

    def test_start_analysis(self):
        response = self.fetch('/api/1.0/jobs/start_analysis/', method='POST', body=self.START_ANALYSIS_BODY)
        self.assertEqual(response.code, 202)
        self.assertDictEqual(
            json.loads(response.body),
            {
                'link': self.get_url('/api/1.0/jobs/1'),
                'version': version,
            }
        )

    def test_create_directory(self):
        response = self.fetch('/api/1.0/jobs/create_directory/', method='POST', body=self.CREATE_DIRECTORY_BODY)
        self.assertEqual(response.code, 202)
        self.assertDictEqual(
            json.loads(response.body),
            {
                'link': self.get_url('/api/1.0/jobs/1'),
                'version': version,
            }
        )

    def test_stop_job(self):
        response = self.fetch('/api/1.0/jobs/stop/1', method='POST', body=json.dumps({}))
        self.assertEqual(response.code, 202)
        self.assertDictEqual(
            json.loads(response.body),
            {
                'link': self.get_url('/api/1.0/jobs/1'),
                'version': version,
            }
        )

    def test_sync_directory(self):
        response = self.fetch('/api/1.0/jobs/sync_directory/', method='POST', body=self.SYNC_DIRECTORY_BODY)
        self.assertEqual(response.code, 202)
        self.assertDictEqual(
            json.loads(response.body),
            {
                'link': self.get_url('/api/1.0/jobs/1'),
                'version': version,
            }
        )

    def test_start_analysis_missing_required_field(self):
        body = json.dumps({"runscript": "/scripts/start_wp1_GMS560.sh", "inbox_path": "/inbox/ABC-123"})
        with ExpectLog("tornado.general", '400 POST .*missing or empty required field "analysis_path"'):
            response = self.fetch('/api/1.0/jobs/start_analysis/', method='POST', body=body)
        self.assertEqual(response.code, 400)
        self.mock_runner_service.start_runscript.assert_not_called()

    def test_start_analysis_invalid_json(self):
        with ExpectLog("tornado.general", '400 POST .*not valid JSON'):
            response = self.fetch('/api/1.0/jobs/start_analysis/', method='POST', body='not json')
        self.assertEqual(response.code, 400)
        self.mock_runner_service.start_runscript.assert_not_called()

    def test_start_analysis_path_missing_on_disk(self):
        """A path the service cannot find is a 404."""
        self.mock_runner_service.start_runscript.side_effect = FileNotFoundError(
            "Analysis path does not exist: /analysis/ABC-123")
        with ExpectLog("tornado.general", '404 POST .*Analysis path does not exist'):
            response = self.fetch('/api/1.0/jobs/start_analysis/', method='POST', body=self.START_ANALYSIS_BODY)
        self.assertEqual(response.code, 404)

    def test_start_analysis_unexpected_error_is_not_masked_as_404(self):
        """A bug in the service layer must surface as a 500 with a traceback, not as a 404."""
        self.mock_runner_service.start_runscript.side_effect = TypeError("simulated bug: 100% broken")
        with ExpectLog("tornado.application", "Uncaught exception"):
            response = self.fetch('/api/1.0/jobs/start_analysis/', method='POST', body=self.START_ANALYSIS_BODY)
        self.assertEqual(response.code, 500)

    def test_create_directory_missing_path(self):
        with ExpectLog("tornado.general", '400 POST .*missing or empty required field "path"'):
            response = self.fetch('/api/1.0/jobs/create_directory/', method='POST', body=json.dumps({}))
        self.assertEqual(response.code, 400)
        self.mock_runner_service.create_directory.assert_not_called()

    def test_create_directory_relative_path(self):
        body = json.dumps({"path": "analysis/ABC-123"})
        with ExpectLog("tornado.general", '400 POST .*must be an absolute path'):
            response = self.fetch('/api/1.0/jobs/create_directory/', method='POST', body=body)
        self.assertEqual(response.code, 400)
        self.mock_runner_service.create_directory.assert_not_called()

    def test_sync_directory_missing_destination(self):
        body = json.dumps({"source_directory": "/analysis/ABC-123"})
        with ExpectLog("tornado.general", '400 POST .*missing or empty required field "destination_directory"'):
            response = self.fetch('/api/1.0/jobs/sync_directory/', method='POST', body=body)
        self.assertEqual(response.code, 400)
        self.mock_runner_service.sync_directory.assert_not_called()

    def test_sync_directory_filter_is_not_a_list(self):
        """A bare string would be iterated character by character when building the filter file."""
        body = json.dumps({"source_directory": "/analysis/ABC-123",
                           "destination_directory": "/outbox/ABC-123",
                           "filter": "results"})
        with ExpectLog("tornado.general", '400 POST .*"filter" must be a list'):
            response = self.fetch('/api/1.0/jobs/sync_directory/', method='POST', body=body)
        self.assertEqual(response.code, 400)
        self.mock_runner_service.sync_directory.assert_not_called()

    def test_sync_directory_error_message_containing_percent_sign(self):
        """log_message must be a format string plus args; a pre-interpolated '%' breaks logging."""
        self.mock_runner_service.sync_directory.side_effect = FileNotFoundError(
            "Source path does not exist: /analysis/100%_done")
        with ExpectLog("tornado.general", '404 POST .*100%_done'):
            response = self.fetch('/api/1.0/jobs/sync_directory/', method='POST', body=self.SYNC_DIRECTORY_BODY)
        self.assertEqual(response.code, 404)

    def test_start_analysis_parameters_with_stray_whitespace(self):
        """Leading, trailing and doubled spaces must not become empty pipeline arguments."""
        body = json.dumps({"analysis_path": "/analysis/ABC-123",
                           "runscript": "/scripts/start_wp1_GMS560.sh",
                           "inbox_path": "/inbox/ABC-123",
                           "parameters": " --profile  marvin --threads=4 "})
        response = self.fetch('/api/1.0/jobs/start_analysis/', method='POST', body=body)
        self.assertEqual(response.code, 202)
        self.mock_runner_service.start_runscript.assert_called_once_with(
            analysis_path="/analysis/ABC-123",
            runscript="/scripts/start_wp1_GMS560.sh",
            inbox_path="/inbox/ABC-123",
            pipeline_params=["--profile", "marvin", "--threads=4"])
