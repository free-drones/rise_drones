import uuid
from dataclasses import dataclass
import paho.mqtt.client as paho_mqtt
from dss.auxiliaries.config import config

__author__ = 'Kristoffer Bergman <kristoffer.bergman@ri.se>'
__version__ = '1.0.0'
__status__ = 'development'
'''
This file contains dataclasses that are used by an MQTT agent
'''
@dataclass
class NavData:
  ''' NavData is used to store all data related to the navigation data from the drone'''
  def __init__(self):
    self.lat: float = 0.0
    self.lon: float = 0.0
    self.alt: float = 0.0
    self.heading: float = 0.0
    self.course: float = 0.0
    self.speed: float = 0.0

@dataclass
class Logic:
  ''' The Logic class contains information about the level of autonomy and the different tasks '''
  def __init__(self, name, drone_type, sim_real):
    #Agent variables
    self.name: str = name
    self.type: str = drone_type
    self.description: str = "RISE Drone"
    self.domain: str = "air"
    self.sim_real: str = sim_real # simulation or real
    self.level: list = ["sensor"]
    self.rate: float = 1.0
    self.uuid: str = str(uuid.uuid4())
    self.tasks_available = [] #Only level 1 (sensor) at the moment

    #Task variables
    self.task_running: bool = False
    self.task_start_time: float = None
    self.task_pause_flag: bool = False
    self.task_running_uuid: str = ""
    self.task_paused: bool = False


@dataclass
class MqttClient:
  '''This class is used to connect and handle all information with the MQTT broker'''
  def __init__(self, name, sim_real):
    self.client: paho_mqtt = paho_mqtt.Client()
    self.base_topic: str = f"waraps/unit/air/{sim_real}/{name}"
    self.listen_topic: str = f"waraps/unit/air/{sim_real}/{name}/exec/command"
    self.user: str = config['mqtt']['user']
    self.password: str = config['mqtt']['password']
    self.broker: str = config['mqtt']['broker']
    self.port: int = config['mqtt']['port']
    self.tls_connection: bool = config['mqtt']['tls_connection']
