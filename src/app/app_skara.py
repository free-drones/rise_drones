#!/usr/bin/env python3

'''
APP "app_skara"

This app is used to follow a cyclist. It can be configured to use one or two drones. It exposes the "follow me" interface where an application can request to be followed
'''

import argparse
from distutils.log import info
import json
import logging
import sys
import threading
import time
import traceback
import copy

import zmq

import dss.auxiliaries
import dss.client

#--------------------------------------------------------------------#

__author__ = 'Andreas Gising <andreas.gising@ri.se>, Kristoffer Bergman <kristoffer.bergman@ri.se>'
__version__ = '0.2.0'
__copyright__ = 'Copyright (c) 2022, RISE'
__status__ = 'development'

#--------------------------------------------------------------------#

_logger = logging.getLogger('dss.app_skara')
_context = zmq.Context()

#--------------------------------------------------------------------#
# App mission - README.
# This application is used to perform a mission. Input
# parameters are:
# 1. start_wp : Where the drone should start
# 2. mission: The json-file containing the mission
# 3. capabilities: List of capabilities required to perform the mission

#
# The application to connect to crm and allocate a drone
# (if available), it also shows how you can make the drone publish
# information and how to subscribe to it.
# Quit application by calling kill() or Ctrl+C
#
# #--------------------------------------------------------------------#

class AppSkara():
  # Init
  def __init__(self, app_ip, app_id, crm, drone_capabilities, n_drones, owner):
    # Create a dummy drones object
    self.drones = {}
    # Create roles involved depending on number of drones that should be used
    if n_drones == 1:
      self.roles = ["Above"]
    else:
      self.roles = ["East", "West"]
    for role in self.roles:
      self.drones[role] = dss.client.Client(timeout=2000, exception_handler=None, context=_context)

    # Create CRM object
    self.crm = dss.client.CRM(_context, crm, app_name='app_skara.py', desc='SkarApp for following cyclist', app_id=app_id)

    self._alive = True
    self._dss_data_thread = None
    self._dss_data_thread_active = False
    self._dss_info_thread = None
    self._dss_info_thread_active = False

    # Set the owner, it shall be the process who launched the app
    self._owner = owner
    self._app_ip = app_ip
    self.drone_data = {}
    # capabilities required for the allocated drones
    self.drone_capabilities = drone_capabilities

    # The application sockets
    # Use ports depending on subnet used to pass RISE firewall
    # Rep: ANY -> APP
    self._app_socket = dss.auxiliaries.zmq.Rep(_context, label='app', min_port=self.crm.port, max_port=self.crm.port+50)
    # Pub: APP -> ANY
    self._info_socket = dss.auxiliaries.zmq.Pub(_context, label='info', min_port=self.crm.port, max_port=self.crm.port+50)

    # Start the app reply thread
    self._app_reply_thread = threading.Thread(target=self._main_app_reply, daemon=True)
    self._app_reply_thread.start()

    # Register with CRM (self.crm.app_id is first available after the register call)
    answer = self.crm.register(self._app_ip, self._app_socket.port)
    self._app_id = answer['id']

    # All nack reasons raises exception, registration is successful
    _logger.info('App %s listening on %s:%d', self.crm.app_id, self._app_socket.ip, self._app_socket.port)
    _logger.info(f'App_skara registered with CRM: {self.crm.app_id}')

    # Update socket labels with received id
    self._app_socket.add_id_to_label(self.crm.app_id)
    self._info_socket.add_id_to_label(self.crm.app_id)

    #Threads
    self._her_lla_subscriber = None
    self.her_lla_thread = threading.Thread(target=self._her_lla_listener, daemon=True)
    # start task thread
    self._main_task_thread = threading.Thread(target=self._main_task, daemon=True)
    # create initial task
    self._task_msg = {'fcn': ''}
    self._task_event = threading.Event()

    # Supported commands from ANY to APP
    self._commands = {'follow_her':   {'request': self._request_follow_her, 'task': self._follow_her},
                      'get_info':     {'request': self._request_get_info, 'task': None}}

#--------------------------------------------------------------------#
  @property
  def alive(self):
    '''checks if application is alive'''
    return self._alive
  @property
  def app_id(self):
    '''application id'''
    return self._app_id

#--------------------------------------------------------------------#
# This method runs on KeyBoardInterrupt, time to release resources and clean up.
# Disconnect connected drones and unregister from crm, close ports etc..
  def kill(self):
    _logger.info("Closing down...")
    self._alive = False
    # Kill info and data thread
    self._dss_info_thread_active = False
    self._dss_data_thread_active = False
    self._info_socket.close()

    # Unregister APP from CRM
    _logger.info("Unregister from CRM")
    answer = self.crm.unregister()
    if not dss.auxiliaries.zmq.is_ack(answer):
      _logger.error('Unregister failed: {answer}')
    _logger.info("CRM socket closed")

    # Disconnect drone if drone is alive
    for drone in self.drones.values():
      if drone.alive:
        #wait until other DSS threads finished
        time.sleep(0.5)
        _logger.info("Closing socket to DSS")
        drone.close_dss_socket()
    _logger.debug('~ THE END ~')

#--------------------------------------------------------------------#
# Ack nack helper
	# Is message from owner?
  def from_owner(self, msg) -> bool:
    return msg['id'] == self._owner

#--------------------------------------------------------------------#
# Application reply thread
  def _main_app_reply(self):
    _logger.info('Reply socket is listening on: %d', self._app_socket.port)
    while self.alive:
      try:
        msg = self._app_socket.recv_json()
        msg = json.loads(msg)
        fcn = msg['fcn'] if 'fcn' in msg else ''

        if fcn in self._commands:
          request = self._commands[fcn]['request']
          answer = request(msg)
        else:
          answer = dss.auxiliaries.zmq.nack(msg['fcn'], 'Request not supported')
        is_ack = dss.auxiliaries.zmq.is_ack(answer)
        answer = json.dumps(answer)
        self._app_socket.send_json(answer)
        if is_ack:
          self._task_msg = msg
          self._task_event.set()
      except:
        pass
    self._app_socket.close()
    _logger.info("Reply socket closed, thread exit")

  def _get_info_port(self, req_socket:dss.auxiliaries.zmq.Req):
    call = 'get_info'
    # build message
    msg = {'fcn': call, 'id': self.app_id}
    # send and receive message
    answer = req_socket.send_and_receive(msg)
    # handle nack
    if not dss.auxiliaries.zmq.is_ack(answer, call):
      raise dss.auxiliaries.exception.Nack(dss.auxiliaries.zmq.get_nack_reason(answer), fcn=call)
    if not 'info_pub_port' in msg:
      raise dss.auxiliaries.exception.Error('info pub port not provided')
    return answer['info_pub_port']

  def setup_her_lla_subscriber(self):
    if 'dss' in self.her['id']:
      drone = dss.client.Client(timeout=2000, exception_handler=None, context=_context)
      drone.connect_as_guest(self.her['ip'], self.her['port'], app_id=self.app_id)
      drone.enable_data_stream('LLA')
      info_pub_port = drone.get_port('info_pub_port')
    else:
      #Request socket to another application
      req_socket = dss.auxiliaries.zmq.Req(_context, self.her['ip'], self.her['port'], label='her-req', timeout=2000)
      info_pub_port = self._get_info_port(req_socket)
    self._her_lla_subscriber = dss.auxiliaries.zmq.Sub(_context,self.her['ip'], info_pub_port, "info-her" + self.app_id)
    self._her_lla_subscriber_active = True

  def _her_lla_listener(self):
    while self.alive:
      if self._her_lla_subscriber_active:
        try:
          (topic, msg) = self._her_lla_subscriber.recv()
          if topic == "LLA":
            self._her_lla_data = msg
        except:
          pass

  def _her_lla_publisher(self, role, pub_socket:dss.auxiliaries.zmq.Pub):
    while self.alive:
      topic = 'LLA'
      msg = None
      if role == 'Above':
        msg = copy.deepcopy(self._her_lla_data)
      if msg is not None:
        pub_socket.publish(topic, msg)
      time.sleep(0.1)

#--------------------------------------------------------------------#
# Application reply: 'follow_her'
  def _request_follow_her(self, msg):
    fcn = dss.auxiliaries.zmq.get_fcn(msg)
    # Check nack reasons
    if not self.from_owner(msg) and msg['id'] != "GUI":
      descr = 'Requester ({}) is not the APP owner'.format(msg['id'])
      answer = dss.auxiliaries.zmq.nack(fcn, descr)
    elif not 'target_id' in msg:
      descr = 'missing target_id'
      answer = dss.auxiliaries.zmq.nack(fcn, descr)
    # Accept if target id in list from CRM
    else:
      answer = self.crm.clients(filter=msg['target_id'])
      if len(answer['clients']) > 0:
        self.her = answer['clients'][0]
        answer = dss.auxiliaries.zmq.ack(fcn)
      else:
        descr = 'target_id not found'
        answer = dss.auxiliaries.zmq.nack(fcn, descr)
    return answer

#--------------------------------------------------------------------#
# Application reply: 'get_info'
  def _request_get_info(self, msg):
    answer = dss.auxiliaries.zmq.ack(msg['fcn'])
    answer['id'] = self.crm.app_id
    answer['info_pub_port'] = self._info_socket.port
    answer['data_pub_port'] = None
    return answer

  def _follow_her(self, msg):
    if not msg['enable']:
      self._her_subscriber_lla_active = False
      for drone in self.drones.values():
        drone.disable_follow_stream()
        drone.abort()
        self.alive = False
    else:
      #Setup LLA listener to her
      self.setup_her_lla_subscriber()
      for role, drone in self.drones.items():
        #Obtain a drone with correct capabilities
        drone_received = False
        while not drone_received:
          answer = self.crm.get_drone(capabilities=self.drone_capabilities)
          if dss.auxiliaries.zmq.is_ack(answer):
            _logger.warning('No drone with correct capabilities available.. Sleeping for 2 seconds')
            time.sleep(2.0)
        drone.connect(answer['ip'], answer['port'], app_id=self.app_id)
        #Setup a "modified" LLA-stream thread based on the role of the drone
        lla_publisher = dss.auxiliaries.zmq.Pub(_context, label='info', min_port=self.crm.port, max_port=self.crm.port+50)
        lla_pub_thread = threading.Thread(self._her_lla_publisher, args=[role, lla_publisher])
        lla_pub_thread.start()
        #Enable follow stream
        drone.enable_follow_stream(self._app_ip, lla_publisher.port)


#--------------------------------------------------------------------#
  def _main_task(self):
    '''Executes the current task'''
    while self.alive:
      fcn = self._task_msg['fcn']
      if fcn:
        try:
          task = self._commands[fcn]['task']
          task(self._task_msg)
        except dss.auxiliaries.exception.AbortTask:
          _logger.warning('abort current task')
        except dss.auxiliaries.exception.Error:
          _logger.error(traceback.format_exc())

      if self.alive:
        self._task_event.clear()
        self._task_event.wait()


  #--------------------------------------------------------------------#
  def main(self):
    self._main_task_thread.start()
    cursor = ['  |o....|','  |.o...|', '  |..o..|', '  |...o.|','  |....o|', '  |...o.|', '  |..o..|', '  |.o...|']
    cursor_index = 7
    while self.alive:
      time.sleep(1)
      cursor_index += 1
      if cursor_index >= len(cursor):
        cursor_index = 0
      print(cursor[cursor_index], end = '\r', flush=True)

#--------------------------------------------------------------------#
def _main():
  # parse command-line arguments
  parser = argparse.ArgumentParser(description='APP "app skara"', allow_abbrev=False, add_help=False)
  parser.add_argument('-h', '--help', action='help', help=argparse.SUPPRESS)
  parser.add_argument('--app_ip', type=str, help='ip of the app', required=True)
  parser.add_argument('--capabilities', type=str, default=None, nargs='*', help='If any specific capability is required')
  parser.add_argument('--n_drones', type=int, default=1, help='Number of drones used to track the cyclist')
  parser.add_argument('--id', type=str, default=None, help='id of this instance if started by crm')
  parser.add_argument('--crm', type=str, help='<ip>:<port> of crm', required=True)
  parser.add_argument('--log', type=str, default='debug', help='logging threshold')
  parser.add_argument('--owner', type=str, help='id of the instance controlling the app')
  parser.add_argument('--stdout', action='store_true', help='enables logging to stdout')
  args = parser.parse_args()

  # Identify subnet to sort log files in structure
  subnet = dss.auxiliaries.zmq.get_subnet(ip=args.app_ip)
  # Initiate log file
  dss.auxiliaries.logging.configure('app_skara', stdout=args.stdout, rotating=True, loglevel=args.log, subdir=subnet)

  # Create the PhotoMission class
  try:
    app = AppSkara(args.app_ip, args.id, args.crm, args.capabilities, args.n_drones, args.owner)
  except dss.auxiliaries.exception.NoAnswer:
    _logger.error('Failed to instantiate application: Probably the CRM couldn\'t be reached')
    sys.exit()
  except:
    _logger.error('Failed to instantiate application\n%s', traceback.format_exc())
    sys.exit()

  # Try to setup objects and initial sockets
  try:
    # Try to run main
    app.main()
  except KeyboardInterrupt:
    print('', end='\r')
    _logger.warning('Shutdown due to keyboard interrupt')
  except dss.auxiliaries.exception.Nack as error:
    _logger.error(f'Nacked when sending {error.fcn}, received error: {error.msg}')
  except dss.auxiliaries.exception.NoAnswer as error:
    _logger.error(f'NoAnswer when sending: {error.fcn} to {error.ip}:{error.port}')
  except:
    _logger.error(f'unexpected exception\n{traceback.format_exc()}')

  try:
    app.kill()
  except:
    _logger.error(f'unexpected exception\n{traceback.format_exc()}')


#--------------------------------------------------------------------#
if __name__ == '__main__':
  _main()
