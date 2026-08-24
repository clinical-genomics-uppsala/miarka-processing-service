# pylint: disable=W0223,W0221,W0511,W0201
# W0201 needs to be disabled because this is the way that tornado demands that handlers
#       are setup
# TODO: remove these exceptions
"""
Handlers start, stop and check jobs.
"""

import os

from tornado.web import HTTPError

from arteria.web.handlers import BaseRestHandler

from miarka_processing_service.handlers import ACCEPTED, BAD_REQUEST, NOT_FOUND, FORBIDDEN
from miarka_processing_service.exceptions import UnableToStopJob
from miarka_processing_service import __version__ as version


def _parse_request_body(handler):
    """
    Return the JSON body of the request as an object, or raise a 400 if it cannot be parsed.

    arteria's body_as_object() lets json.JSONDecodeError (a ValueError) escape, which would
    otherwise surface as a 500 for what is a malformed request.
    """
    try:
        return handler.body_as_object()
    except ValueError as exc:
        raise HTTPError(BAD_REQUEST, "request body is not valid JSON: %s", str(exc)) from exc


def _required_string(request_data, field):
    """
    Return a required, non-empty string field from the request body, or raise a 400.

    Note that arteria's body_as_object(required_members=...) cannot be used for this: it
    raises HTTPError with the status code as a string, which makes tornado fail to write
    any response at all.
    """
    value = request_data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise HTTPError(BAD_REQUEST, 'missing or empty required field "%s"', field)
    return value


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
            "command": "bash /script/to/exec.sh",
            "environment": "",
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
                "command": "bash /script/to/exec.sh",
                "environment": "",
                "pid": 3837,
                "state": "done",
                "created": "2018-11-27 12:06:26",
                "updated": "2018-11-27 12:06:44",
                "log": "",
            },
            {
                "job_id": 2,
                "command": "mkdir -p /dir/to/create",
                "environment": "",
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

    TODO:
    Information from workflow variables that has to be sent to processing-service
    to be able to start an analysis.

    run_analysis_miarka:
        action: ductus.run_analysis_miarka_action
        input:
            runfolder: <% ctx(runfolder) %>
            experiment_name: <% ctx(experiment_name) %>
            workpackage: <% ctx(workpackage) %>
            analysis: <% ctx(analysis) %>
            process_settings: <% ctx(process_settings) %>
            mail_bioinfo: <% ctx(mail_bioinfo) %>

    curl -X POST -w '\n' --data '{
        "runscript": "<% ctx(process_settings).get(ctx(workpackage)).get(ctx(analysis)).get('run_script') %>",
        "inbox_path": "<% ctx(runfolder) %>",
        "parameters": "<% ctx(process_settings).get(ctx(workpackage)).get(ctx(analysis)).get('parameters') %>" }' \
        http://localhost:11010/api/1.0/jobs/start_analysis/

    """
    def initialize(self, runner_service, **kwargs):
        """
        Initalize a new instance of JobStartHandler.
        """
        self.runner_service = runner_service

    def post(self):
        """
        Posting to this endpoint will start a job for the provided runscript on
        the provided runfolder, e.g.:
            curl -X POST -w'\n' localhost:9999/api/1.0/jobs/start/socks/foo_runfolder
        The endpoint will then return a link where the run can be monitored:
            {"link": "http://localhost:9999/api/1.0/jobs/130"}

        This endpoint also support the following parameters:
        TODO:
        """
        request_data = _parse_request_body(self)

        analysis_path = _required_string(request_data, "analysis_path")
        runscript = _required_string(request_data, "runscript")
        inbox_path = _required_string(request_data, "inbox_path")

        params = request_data.get("parameters", "")
        if isinstance(params, str):
            # split() rather than split(" "), so that a stray leading, trailing or doubled
            # space does not turn into an empty argument on the pipeline command line
            params = params.split()
        elif not isinstance(params, list):
            raise HTTPError(BAD_REQUEST, 'field "parameters" must be a string or a list')

        try:
            job_id = self.runner_service.start_runscript(
                analysis_path=analysis_path,
                runscript=runscript,
                inbox_path=inbox_path,
                pipeline_params=params)
        except FileNotFoundError as exc:
            raise HTTPError(NOT_FOUND, "%s", str(exc)) from exc

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


class CreateDirectoryHandler(BaseRestHandler):
    "Class to handle creation of directories associated with analysis on miarka."

    def initialize(self, runner_service, **kwargs):
        """
        Initalize a new instance of JobStartHandler.
        """
        self.runner_service = runner_service

    def post(self):
        """
        curl -X POST -w '\n' --data '{"path": "<% ctx(analysis_folder_path) %>" }' \
        http://localhost:11010/api/1.0/jobs/create_directory/
        """
        request_data = _parse_request_body(self)

        path = _required_string(request_data, "path")
        if not os.path.isabs(path):
            # A relative path would be created relative to the service's working directory
            raise HTTPError(BAD_REQUEST, 'field "path" must be an absolute path, got: %s', path)

        # create_directory only queues the job; a failing mkdir is reported through the
        # job's state and log, not as an exception here.
        job_id = self.runner_service.create_directory(path=path)

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


class SyncDirectoryHandler(BaseRestHandler):
    "Class to handle rsync of directories between analysis-dir and outbox-dir on miarka."

    def initialize(self, runner_service, **kwargs):
        """
        Initalize a new instance of JobStartHandler.
        """
        self.runner_service = runner_service

    def post(self):
        """
        Posting to this endpoint will start a job for the provided runscript on
        the provided runfolder, e.g.:
        curl -X POST -w'\n' --data '{"source_directory": "<% ctx(analysis_folder_path) %>" \
        "destination_directory": "<% ctx(outbox_folder_path) %>" \
        "filter": "<% ctx(process_settings).get(ctx(workpackage)).get(ctx(analysis)).get('outbox_files_and_folders', []) %>"}' \
        "may_exist_filter": <% ctx(process_settings).get(ctx(workpackage)).get(ctx(analysis)) \
        .get('outbox_files_and_folders_that_may_exist', []) %>" \
        http://localhost:9999/api/1.0/jobs/sync_directory/
        The endpoint will return a link where the run can be monitored:
            {"link": "http://localhost:9999/api/1.0/jobs/130"}

        sync_data_to_outbox:
            with:
                items: <% ctx(process_settings).get(ctx(workpackage)).get(ctx(analysis)).get('outbox_files_and_folders', []) %>
                concurrency: 2
            action: core.local
            input:
                cwd: <% ctx(analysis_folder_path) %>
                cmd: cp -r <% item() %> <% ctx(outbox_folder) %>/

        gms560:
            run_script: "/projects/bin/pipeline_start_scripts/marvin/start_wp1_gms560.sh"
            parameters: ""
            outbox_files_and_folders:
                - "results"
                - "bam_*"
                - "samples.tsv"
                - "units.tsv"
                - "samples_and_settings.json"
            outbox_files_and_folders_that_may_exist:
                - "gvcf_*"

        This endpoint also support the following parameters:
        TODO:
        """
        request_data = _parse_request_body(self)

        source_path = _required_string(request_data, "source_directory")
        destination_path = _required_string(request_data, "destination_directory")

        for field in ("filter", "may_exist_filter"):
            # A string here would be iterated character by character when building the
            # rsync filter file, which silently produces a nonsensical filter.
            if not isinstance(request_data.get(field, []), list):
                raise HTTPError(BAD_REQUEST, 'field "%s" must be a list', field)

        try:
            job_id = self.runner_service.sync_directory(
                source_path=source_path,
                destination_path=destination_path,
                filter=request_data.get("filter", []),
                may_exist_filter=request_data.get("may_exist_filter", [])
            )
        except FileNotFoundError as exc:
            raise HTTPError(NOT_FOUND, "%s", str(exc)) from exc

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
