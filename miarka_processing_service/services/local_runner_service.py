# pylint: disable=W0511,R1732
# W0511-fixme pending DEVELOP-237
# Intentionally disabling R1732 consider-using-with since it is not appropriate for
# open and Popen calls in _start_process
"""
Contains classes to run and manage jobs.
"""

import asyncio
import logging
import subprocess
import os
import signal
import shlex

from tornado.process import Subprocess

from miarka_processing_service.models.db_models import State
from miarka_processing_service.exceptions import UnableToStopJob
from miarka_processing_service.nextflow import nextflow_command

log = logging.getLogger(__name__)


class LocalRunnerService:
    """
    The local runner service will start jobs one by one and attempt to run to
    the command associated with it. In order for jobs to actually be started
    `process_job_queue` must be called. This can e.g. be done periodically from
    the application event loop.

    Please note that while the LocalRunnerService will use Job instances
    returned from the JobRepository, these should not be returned to the called
    of LocalRunnerService. The reason for that is that they will have lost
    their database session, which will cause errors. So in general return the
    job id (or what ever information is useful) of the job if you need to
    process it in some other way downstream rather than returning the job
    instance.
    """

    def __init__(self, job_repo_factory, pipeline_config_dir, nextflow_log_dirs):
        """
        Create a new instance of LocalRunnerService
        :param: job_repo_factory factory method which can produce new JobRepository instances
        :param: pipeline_config_dir directory containing the pipeline configs
        :param: nextflow_log_dirs specifies where nextflow logs should be stored
        """
        self._job_repo_factory = job_repo_factory
        self._pipeline_config_dir = pipeline_config_dir
        self._nextflow_log_dirs = nextflow_log_dirs

    async def _start_process(self, job_id):
        with self._job_repo_factory() as job_repo:
            job = job_repo.get_job(job_id)
            assert job

            working_dir = os.path.join(
                self._nextflow_log_dirs, str(job_id))
            os.mkdir(working_dir)
            nxf_log = os.path.join(working_dir, "nextflow.out")
            sys_env = os.environ.copy() or {}
            job_env = job.environment or {}
            env = {**sys_env, **job_env}
            cmd = shlex.split(shlex.quote(" ".join(job.command)))

            try:
                with open(nxf_log, "w", encoding="utf-8") as nxf_log_fh:
                    log.debug("Will start command %s", cmd)
                    process = Subprocess(
                        cmd,
                        stdout=nxf_log_fh,
                        stderr=nxf_log_fh,
                        env=env,
                        cwd=working_dir,
                        shell=True,
                    )

                    job_repo.set_state_of_job(job_id=job.job_id, state=State.STARTED)
                    job_repo.set_pid_of_job(job.job_id, process.pid)

                    await process.wait_for_exit()

                with open(nxf_log, encoding="utf-8") as log_file:
                    cmd_log = log_file.read()

                log.info("Successfully completed process: %s", job.command)
                job_repo.set_state_of_job(
                    job_id=job.job_id,
                    state=State.DONE,
                    cmd_log=cmd_log,
                )
            except subprocess.CalledProcessError:
                job = job_repo.get_job(job_id)
                if job.state == State.CANCELLED:
                    return

                with open(nxf_log, encoding="utf-8") as log_file:
                    cmd_log = log_file.read()
                log.exception('Job failed with the following error:')
                job_repo.set_state_of_job(
                    job_id=job_id,
                    state=State.ERROR,
                    cmd_log=cmd_log,
                )

    def start(
        self,
        pipeline,
        runfolder_path,
        input_samplesheet_content="",
        ext_args=None,
    ):
        """
        Start a new job for the specified runfolder
        :param pipeline: name of the pipeline to run
        :param runfolder_path: path to the runfolder to process
        :param input_samplesheet_content: content of the input samplesheet
        :param ext_args: extra args to append to the nextflow command
        :return: the job id of the started job
        """
        with self._job_repo_factory() as job_repo:
            nf_cmd = nextflow_command(
                pipeline,
                runfolder_path,
                self._pipeline_config_dir,
                input_samplesheet_content,
                ext_args,
            )
            job_id = job_repo.add_job(command_with_env=nf_cmd).job_id
        log.debug("calling start_process with id %s" % str(job_id))
        loop = asyncio.get_running_loop()
        loop.create_task(self._start_process(job_id))
        return job_id
    
    def start_runscript(
        self,
        runscript,
        inbox_path,
        pipeline_params=None,
    ):
        """
        Start a new job for the specified runfolder
        :param pipeline: name of the pipeline to run
        :param runfolder_path: path to the runfolder to process
        :param input_samplesheet_content: content of the input samplesheet
        :param ext_args: extra args to append to the nextflow command
        :return: the job id of the started job
        """
        with self._job_repo_factory() as job_repo:
            cmd = "bash {} --inbox-path {} {}".format(runscript, 
                                                           inbox_path,
                                                             pipeline_params)
            #No env specified
            env = None
            bash_cmd = {"command": cmd}
            job_id = job_repo.add_job(command_with_env=bash_cmd).job_id
        print(bash_cmd)
        log.debug("calling start_process with id %s" % str(job_id))
        #loop = asyncio.get_running_loop()
        loop = asyncio.new_event_loop()
        loop.create_task(self._start_process(job_id))
        return job_id

    def stop(self, job_id):
        """
        Stop the job with the specified id
        :param job_id:
        :return: the job id of the job that was stopped.
        """
        with self._job_repo_factory() as job_repo:
            job = job_repo.get_job(job_id)
            if job and job.state == State.PENDING:
                log.info("Found pending job: %s. Will set its state to cancelled.", job)
                job_repo.set_state_of_job(job_id, State.CANCELLED)
                return job.job_id
            if job and job.state == State.STARTED:
                log.info("Will stop the currently running job.")
                job_repo.set_state_of_job(job_id, State.CANCELLED)
                os.kill(job.pid, signal.SIGTERM)
                return job.job_id
            log.debug("Found no job to cancel with with job id: {}. Or it was not in a cancellable state.")
            raise UnableToStopJob()

    def get_jobs(self):
        """
        Return all jobs as a list
        :return: list of all jobs
        """
        with self._job_repo_factory() as job_repo:
            for job in job_repo.get_jobs():
                job_repo.expunge_object(job)
            return job_repo.get_jobs()

    def get_job(self, job_id):
        """
        Get the job corresponding to the specific job id
        :param job_id: to fetch job for.
        :return: a Job, or None if there is no job with the specified job id
        """
        with self._job_repo_factory() as job_repo:
            job = job_repo.get_job(job_id)
            job_repo.expunge_object(job)
            return job
