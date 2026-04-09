

import asyncio
import mock
import tempfile
import os
import time
import signal

import pytest

from miarka_processing_service.services.local_runner_service import LocalRunnerService
from miarka_processing_service.models.db_models import Job, State
from miarka_processing_service.exceptions import UnableToStopJob

from tests.test_utils import MockJobRepository


class TestLocalRunnerService(object):
    @pytest.fixture
    def job_repo_factory(self):
        data = []

        def f():
            return MockJobRepository(data)
        return f

    @pytest.mark.asyncio
    async def test_start_process(
            self,
            job_repo_factory,
            ):
        local_runner_service = LocalRunnerService(
            job_repo_factory,
            )

        command_in = {
            "command": ["sleep", "1"],
        }

        with local_runner_service._job_repo_factory() as job_repo:
            job = job_repo.add_job(command_in=command_in)
            job_id = job.job_id
            assert job.state == State.PENDING

            await local_runner_service._start_process(job_id)

            job = job_repo.get_job(job_id)
            assert job.state == State.DONE

    @pytest.mark.asyncio
    async def test_start_process_fail(
            self,
            job_repo_factory,
            ):
        local_runner_service = LocalRunnerService(
            job_repo_factory,
            )

        command_in = {
            "command": ["fakecommand"],
            }

        with local_runner_service._job_repo_factory() as job_repo:
            job = job_repo.add_job(command_in=command_in)
            job_id = job.job_id
            assert job.state == State.PENDING

            await local_runner_service._start_process(job_id)

            job = job_repo.get_job(job_id)
            assert job.state == State.ERROR

    @pytest.mark.asyncio
    async def test_create_directory(self, job_repo_factory):
        local_runner_service = LocalRunnerService(job_repo_factory)

        # Mock the event loop to prevent background tasks from leaking out of the test
        with mock.patch("miarka_processing_service.services.local_runner_service.asyncio.get_event_loop") as mock_loop:
            with tempfile.TemporaryDirectory() as tmp_dir:
                # Create a path for a subdirectory inside the temporary directory
                path = os.path.join(tmp_dir, "test_subdir")
                job_id = local_runner_service.create_directory(path)

                # Verify that the service attempted to schedule the task
                mock_loop.return_value.create_task.assert_called_once()

                # Capture and close the coroutine to prevent RuntimeWarning
                coro = mock_loop.return_value.create_task.call_args[0][0]
                coro.close()

                # We manually await the start_process logic to ensure the shell command finishes
                await local_runner_service._start_process(job_id)

                # Assert the directory was physically created
                assert os.path.exists(path)
                assert os.path.isdir(path)

                with local_runner_service._job_repo_factory() as job_repo:
                    job = job_repo.get_job(job_id)
                    assert job.state == State.DONE

        # After exiting the context manager, the directory should be gone
        assert not os.path.exists(path)

    def test_start_runscript(self, job_repo_factory):
        local_runner_service = LocalRunnerService(job_repo_factory)
        runscript = "/bin/script.sh"
        inbox = "/data/inbox"
        params = ["--fast", "--debug"]
        
        with mock.patch("miarka_processing_service.services.local_runner_service.asyncio.get_event_loop") as mock_loop:
            job_id = local_runner_service.start_runscript(runscript, inbox, params)
            
            # Close coroutine to silence warning
            mock_loop.return_value.create_task.call_args[0][0].close()
            
            with local_runner_service._job_repo_factory() as job_repo:
                job = job_repo.get_job(job_id)
                expected_cmd = ["bash", runscript, "--inbox-path", inbox, "--fast", "--debug"]
                assert job.command == expected_cmd

    def test_stop_pending_job(self, job_repo_factory):
        local_runner_service = LocalRunnerService(job_repo_factory)
        
        with local_runner_service._job_repo_factory() as job_repo:
            job = job_repo.add_job({"command": ["ls"]})
            job_id = job.job_id
        
        stopped_id = local_runner_service.stop(job_id)
        
        assert stopped_id == job_id
        with local_runner_service._job_repo_factory() as job_repo:
            assert job_repo.get_job(job_id).state == State.CANCELLED

    @mock.patch("os.kill")
    def test_stop_started_job(self, mock_kill, job_repo_factory):
        local_runner_service = LocalRunnerService(job_repo_factory)
        test_pid = 1234
        
        with local_runner_service._job_repo_factory() as job_repo:
            job = job_repo.add_job({"command": ["sleep", "100"]})
            job_id = job.job_id
            job_repo.set_state_of_job(job_id, State.STARTED)
            job_repo.set_pid_of_job(job_id, test_pid)
        
        local_runner_service.stop(job_id)
        
        mock_kill.assert_called_once_with(test_pid, signal.SIGTERM)
        with local_runner_service._job_repo_factory() as job_repo:
            assert job_repo.get_job(job_id).state == State.CANCELLED

    def test_stop_job_not_found(self, job_repo_factory):
        local_runner_service = LocalRunnerService(job_repo_factory)
        with pytest.raises(UnableToStopJob):
            local_runner_service.stop(999)

    def test_get_job(self, job_repo_factory):
        local_runner_service = LocalRunnerService(job_repo_factory)
        with local_runner_service._job_repo_factory() as job_repo:
            job = job_repo.add_job({"command": ["test"]})
            job_id = job.job_id
        
        fetched_job = local_runner_service.get_job(job_id)
        assert fetched_job.job_id == job_id

    def test_get_jobs(self, job_repo_factory):
        local_runner_service = LocalRunnerService(job_repo_factory)
        with local_runner_service._job_repo_factory() as job_repo:
            job_repo.add_job({"command": ["cmd1"]})
            job_repo.add_job({"command": ["cmd2"]})
        
        jobs = local_runner_service.get_jobs()
        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_concurrent_jobs(self, job_repo_factory):
        """Verify that multiple jobs can progress independently through PENDING, STARTED, and DONE."""
        local_runner_service = LocalRunnerService(job_repo_factory)
        
        # Resolve the path to the script in miarka_processing_service/scripts/
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        script_path = os.path.join(project_root, "tests", "resources", "scripts", "start_wp1_GMS560.sh")
        inbox_1 = "/data/inbox1"
        inbox_2 = "/data/inbox2"
        command1 = ["bash", script_path, "--inbox-path", inbox_1]
        command2 = ["bash", script_path, "--inbox-path", inbox_2]

        # 1. Add jobs and verify PENDING state
        with local_runner_service._job_repo_factory() as job_repo:
            job1_id = job_repo.add_job({"command": command1}).job_id
            job2_id = job_repo.add_job({"command": command2}).job_id
            
            assert job_repo.get_job(job1_id).state == State.PENDING
            assert job_repo.get_job(job2_id).state == State.PENDING

        # 2. Verify STARTED state
        task1 = asyncio.create_task(local_runner_service._start_process(job1_id))
        task2 = asyncio.create_task(local_runner_service._start_process(job2_id))

        # Yield control so processes can start
        await asyncio.sleep(0.5)
        
        with local_runner_service._job_repo_factory() as job_repo:
            assert job_repo.get_job(job1_id).state == State.STARTED
            assert job_repo.get_job(job2_id).state == State.STARTED

        # 3. Verify DONE state
        await asyncio.gather(task1, task2)

        with local_runner_service._job_repo_factory() as job_repo:
            assert job_repo.get_job(job1_id).state == State.DONE
            assert job_repo.get_job(job2_id).state == State.DONE
        jobs = local_runner_service.get_jobs()
        assert len(jobs) == 2

    @pytest.mark.asyncio
    async def test_start_runscript_fail_empty_inbox(self, job_repo_factory):
        """Verify that an empty inbox-path parameter leads to an ERROR state."""
        local_runner_service = LocalRunnerService(job_repo_factory)
        
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        script_path = os.path.join(project_root, "tests", "resources", "scripts", "start_wp1_GMS560.sh")
        
        with mock.patch("miarka_processing_service.services.local_runner_service.asyncio.get_event_loop") as mock_loop:
            job_id = local_runner_service.start_runscript(script_path, inbox_path="")
            mock_loop.return_value.create_task.call_args[0][0].close()

        # Await the processing logic directly to verify it catches the failure
        await local_runner_service._start_process(job_id)

        with local_runner_service._job_repo_factory() as job_repo:
            job = job_repo.get_job(job_id)
            assert job.state == State.ERROR
