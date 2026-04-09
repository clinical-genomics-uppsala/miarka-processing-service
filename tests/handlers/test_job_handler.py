
import json
from pathlib import Path


from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application

import mock

from miarka_processing_service.app import routes
from miarka_processing_service.services.local_runner_service import LocalRunnerService
from miarka_processing_service.repositiories.runfolder_repo import RunfolderRepository
from miarka_processing_service.models.db_models import Job, State
import importlib.metadata

version = importlib.metadata.version("miarka-processing-service")


class TestJobHandler(AsyncHTTPTestCase):
    def get_app(self):

        mock_runner_service = mock.create_autospec(LocalRunnerService)
        job = Job(job_id=1, command=['foo'], state=State.PENDING)
        mock_runner_service.get_jobs = mock.MagicMock(return_value=[job])
        mock_runner_service.get_job = mock.MagicMock(return_value=job)
        mock_runner_service.start_runscript = mock.MagicMock(return_value=job.job_id)
        mock_runner_service.create_directory = mock.MagicMock(return_value=job.job_id)
        mock_runner_service.stop = mock.MagicMock(return_value=job)

        mock_runfolder_repo = mock.create_autospec(RunfolderRepository)
        mock_runfolder_repo.get_runfolder = mock.MagicMock(return_value=mock)

        return Application(routes(runner_service=mock_runner_service,
                                  runfolder_repo=mock_runfolder_repo))

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
        response = self.fetch('/api/1.0/jobs/start_analysis/', method='POST', body=json.dumps({}))
        self.assertEqual(response.code, 202)
        self.assertDictEqual(
            json.loads(response.body),
            {
                'link': self.get_url('/api/1.0/jobs/1'),
                'version': version,
            }
        )

    def test_create_directory(self):
        response = self.fetch('/api/1.0/jobs/create_directory/', method='POST', body=json.dumps({}))
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
