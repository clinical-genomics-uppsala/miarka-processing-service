"""
This module contains repository classes related to managing job objects.
"""

import logging

#from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from miarka_processing_service.models.db_models import Job, State

log = logging.getLogger(__name__)


class JobRepository:
    """
    The JobRepository manages job objects. In this cases these are stored in the a database, but in principle
    they could be anywhere. It should be used as a context handler, i.e.:

        with JobRepository(db_session_factory) as job_repo:
            job_repo.add_job('foo_folder')

    This makes sure that the connection is closed correctly once the job_repo is no longer used.

    """

    def __init__(self, session_factory):
        """
        Create a new job repository
        :param session_factory: scoped_session object from sqlalchemy.
        """
        self.session_factory = session_factory

    def __enter__(self):
        """
        Handles setting up the context manager
        :return:
        """
        self.session = self.session_factory()
        return self

    def __exit__(self, *args):
        """
        Handlers shutting down the context manager
        :param args:
        :return:
        """
        self.session_factory.remove()

    def add_job(self, command_in):
        """
        Add a new job for the specified runfolder. The state of the job will be set as pending.
        :param command: to start job with
        :return: the created Job
        """
        job = Job(command=command_in["command"],
                  state=State.PENDING,
                  )
        self.session.add(job)
        self.session.commit()
        log.debug("Added job with command: %s", command_in["command"])
        return job

    def get_jobs(self):
        """
        Get all jobs
        :return: all the Jobs in the database, None if none found
        """
        return self.session.query(Job).all()

    def get_jobs_with_state(self, state):
        """
        Get all jobs with specified state
        :param state:
        :return: all the jobs, or None
        """
        return self.session.query(Job).filter(Job.state == state).all()

    def get_job(self, job_id):
        """
        Get the job with the specified job_id
        :param job_id:
        :return: a Job, or None if it does not exist
        """
        return self.session.query(Job).get(job_id)

    def get_one_pending_job(self):
        """
        Get the first available pending Job
        :return: A pending job or none.
        """
        return self.session.query(Job).filter(Job.state == State.PENDING).first()

    def expunge_object(self, obj):
        """
        This will remove the object from the current session. This is necessary if you
        want to pass the object on. However, please note that after this point no
        changes made to the object will be persisted.
        :param obj: to remove from current session.
        :return: None
        """
        if obj:
            self.session.expunge(obj)

    def set_state_of_job(self, job_id, state, cmd_log=None):
        """
        Set the state of the of the specified job to the specified state
        :param job_id: of Job to change
        :param state: Instance of sequencing_report_models.db_models.State
        :param cmd_log: Optionally add log for the job
        :return: The job which state was changed, or none if no (or multiple) jobs with id were found.
        """
        job = self.session.query(Job).get(job_id)

        if not job:
            log.error("Found no job with id: %s.", job_id)
            return None

        job.state = state
        if cmd_log:
            job.log = cmd_log

        self.session.commit()
        return job

    def set_pid_of_job(self, job_id, pid):
        """
        Sets the process id associated with a specific job
        :param job_id: to change pid of
        :param pid: to set
        :return: the Job changed or None if no job was found
        """
        job = self.session.query(Job).get(job_id)

        if not job:
            log.error("Found no job with id: %s.", job_id)
            return None

        job.pid = pid

        self.session.commit()
        return job

    def clear_out_stale_jobs_at_startup(self):
        """
        This method will set all jobs which have state started, i.e. jobs which
        should be running, but are not when the service is started. Should only be
        called once at the start up of the application
        :param job_repo_factory
        :return:
        """
        stale_jobs = self.get_jobs_with_state(State.STARTED)
        for job in stale_jobs:
            log.info("Setting state of job with id=%s, to %s because it was stale.", job.job_id, State.CANCELLED)
            self.set_state_of_job(job_id=job.job_id, state=State.CANCELLED)
