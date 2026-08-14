"""
Contains classes to run and manage jobs.
"""

import asyncio
import logging
import subprocess
import os
import signal
import shlex
import glob


from miarka_processing_service.models.db_models import State
from miarka_processing_service.exceptions import UnableToStopJob

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

    def __init__(self, job_repo_factory):
        """
        Create a new instance of LocalRunnerService
        :param: job_repo_factory factory method which can produce new JobRepository instances

        """
        self._job_repo_factory = job_repo_factory

    async def _start_process(self, job_id):
        log.debug(f"Attempting to start process for job_id: {job_id}")
        with self._job_repo_factory() as job_repo:
            log.debug(f"Job repository opened for job_id: {job_id}")
            job = job_repo.get_job(job_id)
            if not job:
                log.error(f"Job with id {job_id} not found in repository. Cannot start process.")
                # If the job is truly not found, we can't update its state,
                # but we should log the critical error.
                return
            log.debug(f"Job {job_id} retrieved. Command: {job.command}")

            # Use shlex.join to safely handle arguments with spaces or special characters
            # Redirect stderr to stdout within the shell command to ensure all output
            # (including set -x debug output) is captured by stdout_data.
            # This prevents set -x output from leaking to the service's stderr.
            cmd_to_execute = f"{shlex.join(job.command)} 2>&1"

            try:
                log.debug(f"Executing command: {cmd_to_execute} for job_id: {job_id}")
                process = await asyncio.create_subprocess_shell(
                    cmd=cmd_to_execute,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                job_repo.set_state_of_job(job_id=job.job_id, state=State.STARTED)
                job_repo.set_pid_of_job(job.job_id, process.pid)

                # Refresh job context and check if it was cancelled during execution
                # Capture stdout/stderr and wait for the process to finish
                stdout_data, stderr_data = await process.communicate()
                stdout_str = stdout_data.decode() if stdout_data else ""
                stderr_str = stderr_data.decode() if stderr_data else ""
                cmd_log = f"STDOUT:\n{stdout_str}\nSTDERR:\n{stderr_str}"

                job = job_repo.get_job(job_id)
                if job.state == State.CANCELLED:
                    log.info(f"Job {job_id} was cancelled during execution. Not updating final state.")
                    return

                if process.returncode == 0:
                    log.info("Successfully completed process: %s", job.command)
                    job_repo.set_state_of_job(job_id=job.job_id, state=State.DONE, cmd_log=cmd_log)
                    log.debug(f"Job {job_id} state set to DONE.")
                else:  # Process failed
                    log.error(f"Process for job {job_id} failed with return code {process.returncode}. "
                              "Check job log for details.")
                    # Raise with the command that was executed
                    raise subprocess.CalledProcessError(returncode=process.returncode, cmd=cmd_to_execute)

            except subprocess.CalledProcessError as e:
                job = job_repo.get_job(job_id)
                if job.state == State.CANCELLED:
                    log.info(f"Job {job_id} was cancelled during error handling. Not updating final state.")
                    return

                log.exception(f'Job {job_id} failed with a CalledProcessError:')
                job_repo.set_state_of_job(
                    job_id=job_id,
                    state=State.ERROR,
                    cmd_log=cmd_log if 'cmd_log' in locals() else f"Process failed to start or communicate. Error: {e}"
                )
                log.debug(f"Job {job_id} state set to ERROR.")
            except Exception as e:  # Catch any other unexpected exceptions
                log.exception(f"An unexpected error occurred while processing job {job_id}: {e}")
                job_repo.set_state_of_job(job_id=job_id, state=State.ERROR, cmd_log=f"An unexpected error occurred: {e}")
                log.debug(f"Job {job_id} state set to ERROR due to unexpected exception.")

    def create_directory(self, path):
        with self._job_repo_factory() as job_repo:
            bash_cmd = {"command": ["mkdir", "-p", path]}
            job_id = job_repo.add_job(command_in=bash_cmd).job_id

        log.debug("calling start_process with id %s" % str(job_id))
        loop = asyncio.get_event_loop()
        loop.create_task(self._start_process(job_id))

        return job_id

    def start_runscript(
        self,
        *,
        analysis_path,
        runscript,
        inbox_path,
        pipeline_params=None,
    ):
        """
        Start a new job for the specified runfolder
        :param analysis_path: Path where the runscript will be executed
        :param runscript: Path to pipeline runscript
        :param inbox_path: Path to the runfolder to process
        :param pipeline_params: extra args to append to the pipeline
        :return: the job id of the started job
        """
        if not os.path.exists(analysis_path):
            raise FileNotFoundError(f"Analysis path does not exist: {analysis_path}")
        if not os.path.isfile(runscript):
            raise FileNotFoundError(f"Runscript does not exist or is not a file: {runscript}")
        if not os.path.exists(inbox_path):
            raise FileNotFoundError(f"Inbox path does not exist: {inbox_path}")

        with self._job_repo_factory() as job_repo:
            # Build the command to be executed within the analysis directory
            inner_command = ["bash", runscript, "--inbox-path", inbox_path]
            if pipeline_params:
                # Flatten params if they are provided as a list
                inner_command.extend(pipeline_params if isinstance(pipeline_params, list) else [pipeline_params])

            # Use 'bash -c' to ensure that shell operators like '&&' are correctly interpreted.
            # This prevents shlex.join from escaping them as literal arguments in _start_process.
            full_cmd_str = f"cd {shlex.quote(analysis_path)} && {shlex.join(inner_command)}"
            bash_cmd = {"command": ["bash", "-c", full_cmd_str]}
            job_id = job_repo.add_job(command_in=bash_cmd).job_id

        log.debug("calling start_process with id %s" % str(job_id))
        loop = asyncio.get_event_loop()
        loop.create_task(self._start_process(job_id))
        return job_id

    def sync_directory(self,
                       *,
                       source_path,
                       destination_path,
                       filter,
                       may_exist_filter):

        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source path does not exist: {source_path}")
        if not os.path.exists(destination_path):
            raise FileNotFoundError(f"Destination path does not exist: {destination_path}")

        filter_file = os.path.join(source_path, "files_to_outbox.txt")
        if filter:
            with open(filter_file, "a") as f:
                f.write("\n".join(filter) + "\n")
        if may_exist_filter:
            for pattern in may_exist_filter:
                if glob.glob(os.path.join(source_path, pattern)):
                    with open(filter_file, "a") as f:
                        f.write(pattern + "\n")

        if os.path.exists(filter_file):
            bash_cmd = {"command": ["rsync", "-avP",
                                    "--include-from", filter_file,
                                    "--exclude", "*",
                                    os.path.join(source_path, ""),
                                    os.path.join(destination_path, "")]}
            print(bash_cmd)
        else:
            bash_cmd = {"command": ["rsync", "-avP", os.path.join(source_path, ""), os.path.join(destination_path, "")]}

        with self._job_repo_factory() as job_repo:
            job_id = job_repo.add_job(command_in=bash_cmd).job_id

        log.debug("calling start_process with id %s" % str(job_id))
        loop = asyncio.get_event_loop()
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
            log.debug("Found no job to cancel with job id: %s, or it was not in a cancellable state.", job_id)
            raise UnableToStopJob()

    def get_jobs(self):
        """
        Return all jobs as a list
        :return: list of all jobs
        """
        with self._job_repo_factory() as job_repo:
            jobs = job_repo.get_jobs()
            for job in jobs:
                job_repo.expunge_object(job)
            return jobs

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
