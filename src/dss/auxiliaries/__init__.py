'''Drone Safety Service'''

from configparser import ConfigParser
from . import (
    config,
    exception,
    git,
    heartbeat,
    kalman,
    logging,
    math_lib,
    spawnDaemon,
    zmq_lib,
)
from .getch import getch
from .task_queue import TaskQueue

__author__ = 'Lennart Ochel <>, Andreas Gising <andreas.gising@ri.se>, Kristoffer Bergman <kristoffer.bergman@ri.se>, Hanna Müller <hanna.muller@ri.se>, Joel Nordahl'
__version__ = '1.1.0'
__copyright__ = 'Copyright (c) 2019-2021, RISE'
__status__ = 'development'

config._init()
