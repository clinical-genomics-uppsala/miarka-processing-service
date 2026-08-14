# -*- coding: utf-8 -*-
"""
Sets up routes and db for application, and allows it to be started.
"""

import logging
import functools

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from tornado.web import URLSpec as url

from arteria.web.app import AppService

from alembic.config import Config as AlembicConfig
from alembic.command import upgrade as upgrade_db

from miarka_processing_service.handlers.version_handler import VersionHandler
from miarka_processing_service.handlers.job_handler import OneJobHandler, ManyJobHandler, \
    JobStopHandler, JobStartAnalysisHandler, CreateDirectoryHandler, SyncDirectoryHandler
from miarka_processing_service.services.local_runner_service import LocalRunnerService
from miarka_processing_service.repositiories.job_repo import JobRepository
from miarka_processing_service.repositiories.runfolder_repo import RunfolderRepository
from miarka_processing_service.exceptions import ConfigurationError

log = logging.getLogger(__name__)


def routes(**kwargs):
    """
    Setup routes and feed them any kwargs passed, e.g.`routes(config=app_svc.config_svc)`
    Help will be automatically available at /api, and will be based on the
    doc strings of the get/post/put/delete methods
    :param: **kwargs will be passed when initializing the routes.
    """
    return [
        url(r"/api/1.0/version", VersionHandler, name="version", kwargs=kwargs),
        url(r"/api/1.0/jobs/stop/(\d+)$", JobStopHandler, name="job_stop", kwargs=kwargs),
        url(r"/api/1.0/jobs/(\d+)$", OneJobHandler, name="one_job", kwargs=kwargs),
        url(r"/api/1.0/jobs/$", ManyJobHandler, name="many_jobs", kwargs=kwargs),
        # Following endpoints are added by CGU and are in some cases more or less copies
        # of already existing endpoints listed above.
        url(r"/api/1.0/jobs/start_analysis/", JobStartAnalysisHandler, name="job_start_analysis", kwargs=kwargs),
        url(r"/api/1.0/jobs/create_directory/", CreateDirectoryHandler, name="job_create_directory", kwargs=kwargs),
        url(r"/api/1.0/jobs/sync_directory/", SyncDirectoryHandler, name="job_sync_directory", kwargs=kwargs),
    ]


def create_and_migrate_db(db_engine, db_connection_string, logger_config_path, alembic_script_location):
    """
    Configures alembic and runs any none applied migrations found in the
    `scripts_location` folder.
    :param db_engine: engine handle for the database to apply the migrations to
    :param db_connection_string: connection string for db to migrate
    :param logger_config_path path to log config file for alembic
    :param alembic_script_location: path alemtic scripts
    :return: None
    """
    alembic_cfg = AlembicConfig()
    alembic_cfg.set_section_option("alembic", "log_config_file", logger_config_path)
    alembic_cfg.set_section_option("alembic", "sqlalchemy.url", db_connection_string)
    alembic_cfg.set_section_option("alembic", "script_location", alembic_script_location)

    with db_engine.begin() as connection:
        conn_attr = {"connection": connection}
        alembic_cfg.attributes = {**alembic_cfg.attributes, **conn_attr}
        upgrade_db(alembic_cfg, "head")


def get_key_from_config(config, key):
    """
    Get the specific key from the provided config object. Raises a ConfigurationError if the specified key
    does not exist in the configuration.
    :param config: dict-like object containing the config
    :param key: key to look up
    :return: the configuration value
    """
    try:
        return config[key]
    except KeyError as exc:
        raise ConfigurationError("{} not specified in config".format(key)) from exc


def configure_routes(config):
    """
    Configure and return the list of routes for the application
    :param config: a dict-like object containing the app config
    :return: a list of routes for the application
    """

    connection_string = get_key_from_config(config, 'db_connection_string')

    engine = create_engine(connection_string, echo=False)

    # Instantiate db, services, and repos
    log.info("Creating DB migrations")
    alembic_log_config_path = get_key_from_config(config, 'alembic_log_config_path')
    alembic_scripts_path = get_key_from_config(config, 'alembic_scripts')
    create_and_migrate_db(db_engine=engine,
                          db_connection_string=connection_string,
                          logger_config_path=alembic_log_config_path,
                          alembic_script_location=alembic_scripts_path)

    log.info("Setup connection to db")
    session_factory = scoped_session(sessionmaker(expire_on_commit=False))
    session_factory.configure(bind=engine)

    job_repo_factory = functools.partial(JobRepository, session_factory=session_factory)
    local_runner_service = LocalRunnerService(
        job_repo_factory
    )

    monitored_dirs = get_key_from_config(config, 'monitored_directories')
    runfolder_repo = RunfolderRepository(monitored_dirs)

    with job_repo_factory() as job_repo:
        job_repo.clear_out_stale_jobs_at_startup()

    return routes(config=config,
                  runner_service=local_runner_service,
                  runfolder_repo=runfolder_repo)


def start(package=__package__):
    """
    Start the app
    """
    app_svc = AppService.create(package)
    config = app_svc.config_svc
    app_svc.start(configure_routes(config))
