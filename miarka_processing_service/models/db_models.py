# pylint: disable=C0103

"""
Use this as the base for all database based models. This is used by alembic to
know what the tables should look like in the database, so defining new base
classes elsewhere will mean that they will not be updated properly in the
actual database.
"""
import enum as base_enum

import json

from sqlalchemy import Column, Integer, String, Enum, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

from arteria.web.state import State as ArteriaState

SQLAlchemyBase = declarative_base()


class State(base_enum.Enum):
    """
    Possible states of a job
    """
    # This is an ugly hack since the Arteria state class is not
    # an Enum because the it is not supported in Python2.
    # /JD 2018-11-23
    NONE = ArteriaState.NONE
    PENDING = ArteriaState.PENDING
    READY = ArteriaState.READY
    STARTED = ArteriaState.STARTED
    DONE = ArteriaState.DONE
    ERROR = ArteriaState.ERROR
    CANCELLED = ArteriaState.CANCELLED


class Job(SQLAlchemyBase):
    """
    This table contains information about jobs that we have run.
    """
    __tablename__ = 'jobs'

    job_id = Column(Integer, primary_key=True, autoincrement=True)
    _command = Column(String, nullable=False)
    _environment = Column(String, nullable=True)
    pid = Column(Integer, nullable=True)
    state = Column(Enum(State))
    time_created = Column(DateTime(timezone=True), server_default=func.now())
    time_updated = Column(DateTime(timezone=True), onupdate=func.now())
    log = Column(Text(), nullable=True)

    @property
    def command(self):
        """
        Get value of command
        """
        return self._command.split(';')

    @command.setter
    def command(self, value):
        """
        Set the value of command
        """
        self._command = ';'.join(value)

    @property
    def environment(self):
        """
        Get value of enviroment
        """
        env = self._environment
        if not env:
            return None
        return json.loads(self._environment)

    @environment.setter
    def environment(self, value):
        """
        Set the value of environment
        """
        self._environment = json.dumps(value)

    def __repr__(self):
        return str(self.__dict__)

    def to_dict(self):
        """
        Converts object to dict
        """
        return {'job_id': self.job_id,
                'command': self.command,
                'environment': self.environment,
                'pid': self.pid if self.pid else '',
                'state': self.state.value,
                'created': str(self.time_created),
                'updated': str(self.time_updated),
                'log': str(self.log) if self.log else ''}
