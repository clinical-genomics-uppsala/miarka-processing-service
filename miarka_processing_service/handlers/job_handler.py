# pylint: disable=W0223,W0221,W0511,W0201
# W0201 needs to be disabled because this is the way that tornado demands that handlers
#       are setup
# TODO: remove these exceptions, see DEVELOP-440
"""
Handlers start, stop and check jobs.
"""

from tornado.web import HTTPError

from arteria.web.handlers import BaseRestHandler

from miarka_processing_service.handlers import ACCEPTED, NOT_FOUND, FORBIDDEN
from miarka_processing_service.exceptions import UnableToStopJob, RunfolderNotFound
from miarka_processing_service import __version__ as version


class OneJobHandler(BaseRestHandler):
    """
    Handle checking state of a single job.
    """

    def initialize(self, runner_service, **kwargs):
        """
        Initalize a new instance of OneJobHandler.
        """
        self.runner_service = runner_service

    def get(self, job_id):
        """
        Will return the job object corresponding to a specific job id. It will
        return or the form:
        {
            "job_id": 1,
            "command": "nextflow run socks --style emoji",
            "environment": "NXF_TEMP=/tmp",
            "pid": 3837,
            "state": "done",
            "created": "2018-11-27 12:06:26",
            "updated": "2018-11-27 12:06:44",
            "log": "",
        }
        """
        job = self.runner_service.get_job(job_id)
        if job:
            job_as_dicts = job.to_dict()
            job_as_dicts["version"] = version
            self.write_object(job_as_dicts)
        else:
            raise HTTPError(NOT_FOUND)


class ManyJobHandler(BaseRestHandler):
    """
    Handles checking the state of all jobs
    """

    def initialize(self, runner_service, **kwargs):
        """
        Initalize a new instance of ManyJobHandler.
        """
        self.runner_service = runner_service

    def get(self):
        """
        Will return the status of all jobs (or fewer depending on filter). The
        return json has the format:

        {
        "jobs": [
            {
                "job_id": 1,
                "command": "nextflow run socks --style emoji",
                "environment": "NXF_TEMP=/tmp",
                "pid": 3837,
                "state": "done",
                "created": "2018-11-27 12:06:26",
                "updated": "2018-11-27 12:06:44",
                "log": "",
            },
            {
                "job_id": 2,
                "command": "nextflow run socks --style ascii",
                "environment": "NXF_TEMP=/tmp",
                "pid": 4394,
                "state": "done",
                "created": "2018-11-27 12:09:59",
                "updated": "2018-11-27 12:11:11"
                "log": "",
            }
            ]
        }
        """
        jobs = self.runner_service.get_jobs()
        jobs_as_dicts = list(map(lambda job: job.to_dict(), jobs))
        self.write_object({"jobs": jobs_as_dicts, "version": version})


class JobStartHandler(BaseRestHandler):
    """
    Handle starting jobs.
    """

    def initialize(self, runner_service, runfolder_repo, **kwargs):
        """
        Initalize a new instance of JobStartHandler.
        """
        self.runner_service = runner_service
        self.runfolder_repo = runfolder_repo

    def post(self, pipeline, runfolder):
        """
        Posting to this endpoint will start a job for the provided pipeline on
        the provided runfolder, e.g.:
            curl -X POST -w'\n' localhost:9999/api/1.0/jobs/start/socks/foo_runfolder
        The endpoint will then return a link where the run can be monitored:
            {"link": "http://localhost:9999/api/1.0/jobs/130"}

        This endpoint also support the following parameters:
            - `input_samplesheet_content`: content of the nf-core input samplesheet to
            input to the pipeline
            - `ext_args`: extra arguments to pass to the pipeline
        """
        try:
            request_data = self.body_as_object()
            runfolder_path = self.runfolder_repo.get_runfolder(runfolder)

            job_id = self.runner_service.start(
                    pipeline,
                    runfolder_path=runfolder_path,
                    input_samplesheet_content=request_data.get("input_samplesheet_content", ""),
                    ext_args=request_data.get("ext_args", "").split(" "),
                    )
            self.set_status(status_code=ACCEPTED)
            self.write_object(
                {
                    "link":
                        f"{self.request.protocol}://"
                        f"{self.request.host}"
                        f"{self.reverse_url('one_job', job_id)}",
                    'version': version,
                }
            )
        except (RunfolderNotFound, FileNotFoundError) as exc:
            raise HTTPError(
                status_code=NOT_FOUND,
                log_message=str(exc)
            ) from exc


class JobStopHandler(BaseRestHandler):
    """
    Handle stopping jobs. This will stops jobs which are eligible for stopping,
    i.e. jobs which have pending or started as their state.
    """

    def initialize(self, **kwargs):
        """
        Initalize a new instance of JobStartHandler.
        """
        self.runner_service = kwargs['runner_service']

    def post(self, job_id):
        """
        curl -X POST -w'\n' localhost:9999/api/1.0/jobs/stop/1
        Will return an endpoint at which the state of the job can be checked on
        the format:
            {"link": "http://localhost:9999/api/1.0/jobs/1"}
        If it was possible to stop the job the status code will be 202
        (ACCEPTED), and if it was not possible to stop the job it will be 403
        (FORBIDDEN). If there was no corresponding job_id, the status code will
        be 404 (NOT_FOUND)
        """
        if not self.runner_service.get_job(job_id):
            raise HTTPError(NOT_FOUND)

        try:
            self.runner_service.stop(job_id)
            self.set_status(status_code=ACCEPTED)
        except UnableToStopJob:
            self.set_status(status_code=FORBIDDEN)

        self.write_object({
            "link":
                f"{self.request.protocol}://"
                f"{self.request.host}"
                f"{self.reverse_url('one_job', job_id)}",
            'version': version,
        })


class JobStartAnalysisHandler(BaseRestHandler):
    """
            Posting to this endpoint will start a job for the provided pipeline on
        the provided runfolder, e.g.:
            curl -X POST -w'\n' localhost:9999/api/1.0/jobs/start/socks/foo_runfolder
        The endpoint will then return a link where the run can be monitored:
            {"link": "http://localhost:9999/api/1.0/jobs/130"}

        This endpoint also support the following parameters:
            - `input_samplesheet_content`: content of the nf-core input samplesheet to
            input to the pipeline
            - `ext_args`: extra arguments to pass to the pipeline
    """
    def initialize(self, runner_service, **kwargs):
        """
        Initalize a new instance of JobStartHandler.
        """
        self.runner_service = runner_service

    def post(self):
        """
        Posting to this endpoint will start a job for the provided pipeline on
        the provided runfolder, e.g.:
            curl -X POST -w'\n' localhost:9999/api/1.0/jobs/start/socks/foo_runfolder
        The endpoint will then return a link where the run can be monitored:
            {"link": "http://localhost:9999/api/1.0/jobs/130"}

        This endpoint also support the following parameters:
            - `input_samplesheet_content`: content of the nf-core input samplesheet to
            input to the pipeline
            - `ext_args`: extra arguments to pass to the pipeline
        """
        try:
            request_data = self.body_as_object()

            params=request_data.get("parameters", "")

            if params != "":
                params=request_data.get("parameters").split(" ")

            job_id = self.runner_service.start_runscript(
                    runscript=request_data.get("runscript", ""),
                    inbox_path=request_data.get("inbox_path", ""),
                    pipeline_params=params)
            self.set_status(status_code=ACCEPTED)
            self.write_object(
                {
                    "link":
                        f"{self.request.protocol}://"
                        f"{self.request.host}"
                        f"{self.reverse_url('one_job', job_id)}",
                    'version': version,
                }
            )
        except (RunfolderNotFound, FileNotFoundError) as exc:
            raise HTTPError(
                status_code=NOT_FOUND,
                log_message=str(exc)
            ) from exc