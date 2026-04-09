from miarka_processing_service.models.db_models import Job, State


class MockJobRepository():
    def __init__(self, data):
        self._jobs = data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def add_job(self, command_in):
        job = Job(command=command_in['command'],
                  state=State.PENDING,
                  job_id=len(self._jobs) + 1)
        self._jobs.append(job)
        return job

    def get_jobs(self):
        return self._jobs

    def get_jobs_with_state(self, state):
        return [i for i in self._jobs if i.state == state]

    def get_job(self, job_id):
        for job in self._jobs:
            if job.job_id == job_id:
                return job
        return None

    def get_one_pending_job(self):
        potential_job = self.get_jobs_with_state(State.PENDING)
        if potential_job[0]:
            return potential_job[0]

    def expunge_object(self, obj):
        return obj

    def set_state_of_job(self, job_id, state, cmd_log=None):
        job = self.get_job(job_id)
        job.state = state
        if cmd_log:
            job.log = cmd_log
        return job

    def set_pid_of_job(self, job_id, pid):
        job = self.get_job(job_id)
        job.pid = pid
        return Job

    def clear_out_stale_jobs_at_startup(self):
        stale_jobs = self.get_jobs_with_state(State.STARTED)
        for job in stale_jobs:
            self.set_state_of_job(job_id=job.job_id, state=State.CANCELLED)
