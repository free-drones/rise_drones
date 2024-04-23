#!/usr/bin/env python3

'''
APP "app_test_sensor", originates from app_viser -> template photo mission

This app:
- Connects to CRM and receives an app_id
- Requests a sensor
'''

import argparse
import json
import logging
import threading
import time
import traceback
import sys

import dss.auxiliaries
import sen.client

#--------------------------------------------------------------------#

__author__ = 'Andreas Gising <andreas.gising@ri.se>, Kristoffer Bergman <kristoffer.bergman@ri.se>, Hanna Müller <hanna.muller@ri.se>, Joel Nordahl'
__version__ = '0.2.0'
__copyright__ = 'Copyright (c) 2022, RISE'
__status__ = 'development'

#--------------------------------------------------------------------#

#_logger = logging.getLogger('sen.template')
_logger = logging.getLogger('dev.app_test_sensor')
_logger.setLevel(logging.DEBUG)
_context = dss.auxiliaries.zmq_lib.Context()

#--------------------------------------------------------------------#
# Template application for one drone - README.
# 1. Copy this file to app_myapp_name.py
# 2. Search and replace case sensitive 'template' - 'my_app_name'
# 3. Search and replace case sensitive 'Template' - 'My_app_class'
#
# The template helps you to connect to crm and allocate a drone
# (if available), it also shows how you can make the drone publish
# information and how to subscribe to it.
# Quit application by calling Template.kill() or Ctrl+C
#
# #--------------------------------------------------------------------#

class SensorTest():
  # Init
  def __init__(self, app_ip, app_id, crm):
    # Create Client object, set high timeout since connection is poor and we are handeling pictures
    self.sen = sen.client.client_lib.Client(timeout=2000, exception_handler=None, context=_context)

    # Create CRM object
    self.crm = dss.client.CRM(_context, crm, app_name='app_test_sensor.py', desc='Sensor test app', app_id=app_id)

    self._alive = True
    self._sen_data_thread = None
    self._sen_data_thread_active = False
    self._sen_info_thread = None
    self._sen_info_thread_active = False

    # counter for transferred photos
    self.transferred = 0

    # Find the VPN ip of host machine
    self._app_ip = app_ip
    auto_ip = dss.auxiliaries.zmq_lib.get_ip()
    if auto_ip != app_ip:
      _logger.warning(f'Automatic get ip function and given ip does not agree: {auto_ip} vs {app_ip}')

    # The application sockets
    # Use ports depending on subnet used to pass RISE firewall
    # Rep: ANY -> APP
    self._app_socket = dss.auxiliaries.zmq_lib.Rep(_context, label='app', min_port=self.crm.port, max_port=self.crm.port+50)
    # Pub: APP -> ANY
    self._info_socket = dss.auxiliaries.zmq_lib.Pub(_context, label='info', min_port=self.crm.port, max_port=self.crm.port+50)

    # Start the app reply thread
    self._app_reply_thread = threading.Thread(target=self._main_app_reply, daemon=True)
    self._app_reply_thread.start()

    # Register with CRM (self.crm.app_id is first available after the register call)
    _ = self.crm.register(self._app_ip, self._app_socket.port)

    # All nack reasons raises exception, registreation is successful
    _logger.info(f'App {self.crm.app_id} listening on {self._app_socket.ip}:{self._app_socket.port}')
    _logger.info(f'App_test_sensor registered with CRM: {self.crm.app_id}')

    # Update socket labels with received id
    self._app_socket.add_id_to_label(self.crm.app_id)
    self._info_socket.add_id_to_label(self.crm.app_id)

    # Supported commands from ANY to APP
    self._commands = {'push_dss':     {'request': self._request_push_dss}, # Not implemented
                      'get_info':     {'request': self._request_get_info}}

#--------------------------------------------------------------------#
  @property
  def alive(self):
    '''checks if application is alive'''
    return self._alive

#--------------------------------------------------------------------#
# This method runs on KeyBoardInterrupt, time to release resources and clean up.
# Disconnect connected sensors and unregister from crm, close ports etc..
  def kill(self):
    _logger.info("Closing down...")
    self._alive = False
    # Kill info and data thread
    self._sen_info_thread_active = False
    self._sen_data_thread_active = False
    self._info_socket.close()

    # Unregister APP from CRM
    _logger.info("Unregister from CRM")
    answer = self.crm.unregister()
    if not dss.auxiliaries.zmq_lib.is_ack(answer):
      _logger.error('Unregister failed: {answer}')
    _logger.info("CRM socket closed")

    # Disconnect drone if drone is alive
    if self.sen.alive:
      #wait until other DSS threads finished
      time.sleep(0.5)
      _logger.info("Closing socket to DSS")
      self.sen.close_sen_socket()

    _logger.debug('~ THE END ~')

#--------------------------------------------------------------------#
# Application reply thread
  def _main_app_reply(self):
    _logger.info(f'Reply socket is listening on port: {self._app_socket.port}')
    while self.alive:
      try:
        msg = self._app_socket.recv_json()
        msg = json.loads(msg)
        fcn = msg['fcn'] if 'fcn' in msg else ''

        if fcn in self._commands:
          request = self._commands[fcn]['request']
          answer = request(msg)
        else :
          answer = dss.auxiliaries.zmq_lib.nack(msg['fcn'], 'Request not supported')
        answer = json.dumps(answer)
        self._app_socket.send_json(answer)
      except:
        pass
    self._app_socket.close()
    _logger.info("Reply socket closed, thread exit")

#--------------------------------------------------------------------#
# Application reply: 'push_dss'
  def _request_push_dss(self, msg):
    answer = dss.auxiliaries.zmq_lib.nack(msg['fcn'], 'Not implemented')
    return answer

#--------------------------------------------------------------------#
# Application reply: 'get_info'
  def _request_get_info(self, msg):
    answer = dss.auxiliaries.zmq_lib.ack(msg['fcn'])
    answer['id'] = self.crm.app_id
    answer['info_pub_port'] = self._info_socket.port
    answer['data_pub_port'] = None
    return answer

#--------------------------------------------------------------------#
# Setup the SEN info stream thread
  def setup_sen_info_stream(self, timestamp):
    #Get info port from SEN
    info_port = self.sen.get_port('info_pub_port')
    if info_port:
      self._sen_info_thread = threading.Thread(
        target=self._main_info_sen, args=[self.sen._sen.ip, info_port, timestamp])
      self._sen_info_thread_active = True
      self._sen_info_thread.start()

#--------------------------------------------------------------------#
# Setup the DSS data stream thread
  def setup_sen_data_stream(self):
    #Get data port from SEN
    data_port = self.sen.get_port('data_pub_port')
    if data_port:
      self._sen_data_thread = threading.Thread(
        target=self._main_data_sen, args=[self.sen._sen.ip, data_port])
      self._sen_data_thread_active = True
      self._sen_data_thread.start()

#--------------------------------------------------------------------#
# The main function for subscribing to info messages from the SEN.
  def _main_info_sen(self, ip, port, timestamp):
    # Create info socket and start listening thread
    info_socket = dss.auxiliaries.zmq_lib.Sub(_context, ip, port, "info " + self.crm.app_id)
    while self._sen_info_thread_active:
      try:
        (topic, msg) = info_socket.recv()
        if topic == 'BB':
          print(f'Message received on subscription to topic BB: {msg}')
          _logger.info(msg)
        elif topic == 'OD':
          print(f'Message received on subscription to topic OD: {msg}')
          _logger.info(msg)
        else:
          _logger.info(f'Topic not recognized on info link: {topic}')
      except:
        pass

    # Thread is shutting down
    info_socket.close()
    _logger.info("Stopped thread and closed info socket")

#--------------------------------------------------------------------#
# The main function for subscribing to data messages from the SEN.
  def _main_data_sen(self, ip, port):
    # Create data socket and start listening thread
    data_socket = dss.auxiliaries.zmq_lib.Sub(_context, ip, port, "data " + self.crm.app_id)
    while self._sen_data_thread_active:
      try:
        (topic, msg) = data_socket.recv()
        if topic in ('photo', 'photo_low'):
          data = dss.auxiliaries.zmq_lib.string_to_bytes(msg["photo"])
          photo_filename = msg['metadata']['filename']
          dss.auxiliaries.zmq_lib.bytes_to_image(photo_filename, data)
          json_filename = photo_filename[:-4] + ".json"
          dss.auxiliaries.zmq_lib.save_json(json_filename, msg['metadata'])
          _logger.info("Photo saved to " + msg['metadata']['filename']  + "\r")
          _logger.info("Photo metadata saved to " + json_filename + "\r")
          self.transferred += 1
        else:
          _logger.info(f'Topic not recognized on data link: {topic}')
      except:
        pass
    data_socket.close()
    _logger.info('Stopped thread and closed data socket')

  #--------------------------------------------------------------------#
  # Main function
  def main(self):
    # Get a sensor
    answer = self.crm.get_sensor(capabilities=['RPI'])
    if dss.auxiliaries.zmq_lib.is_nack(answer):
      print(f'Did not receive a sensor: {dss.auxiliaries.zmq_lib.get_nack_reason(answer)}, shutting down\n')
      _logger.info(f'Did not receive a sensor: {dss.auxiliaries.zmq_lib.get_nack_reason(answer)}')
      _logger.info('No available RPI sensor')
      return

    # Connect to the sensor, set app_id in socket
    try:
      self.sen.connect(answer['ip'], answer['port'], app_id=self.crm.app_id)
      _logger.info(f"Connected as owner of sensor:") # [{self.sen._sen_id}]")
    except:
      _logger.info("Failed to connect as owner, check crm")
      return

    # Send a command to the connected sensor and print the result
    _logger.info(self.sen._sen.get_info())

    # Request controls from PILOT
    _logger.info("Requesting controls")
    self.sen.await_controls()
    _logger.info("Application is in controls")

    self.sen.set_gimbal(roll=0, pitch=-90, yaw=0)

    focus = self.sen.test_get_focus()
    name = self.sen.test_get_name()
    print(f'Via API libraries, ZMQ and everything else we just figured that the camera name is {name} and its focus setting is {focus}')

    # Connect the subscribe socket
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    self.setup_sen_info_stream(timestamp)

    # Subscribe to objectDetection data
    self.sen.enable_data_stream('OD')

    # Enable cv_algorithm
    self.sen.cv_algorithm('objectDetection', True)
    time.sleep(10)

    _idle = self.sen.get_idle()
    print(_idle)

    # Disable data stream
    self.sen.disable_data_stream('OD')
    time.sleep(1)
    _idle = self.sen.get_idle()
    print(_idle)

    # Enable an other data stream
    self.sen.enable_data_stream('BB')

    # Change cv_algorithm
    self.sen.cv_algorithm('boundingBox', True)
    time.sleep(6)

    # Disable stream and cv_algorithm
    self.sen.disable_data_stream('BB')
    self.sen.cv_algorithm('boundingBox', False)

    time.sleep(10)

    print('Mission complete, BYE')
    # Grafully die
    _logger.info("Good bye")


#--------------------------------------------------------------------#
def _main():
  # parse command-line arguments
  parser = argparse.ArgumentParser(description='APP "app_test_sensor"', allow_abbrev=False, add_help=False)
  parser.add_argument('-h', '--help', action='help', help=argparse.SUPPRESS)
  parser.add_argument('--app_ip', type=str, help='ip of the app', required=True)
  parser.add_argument('--id', type=str, default=None, help='id of this app_test_sensor instance if started by crm')
  parser.add_argument('--crm', type=str, help='<ip>:<port> of crm', required=True)
  parser.add_argument('--log', type=str, default='debug', help='logging threshold')
  parser.add_argument('--owner', type=str, help='id of the instance controlling app_test_sensor - not used in this use case')
  parser.add_argument('--stdout', action='store_true', help='enables logging to stdout')
  args = parser.parse_args()

  # Identify subnet to sort log files in structure
  subnet = dss.auxiliaries.zmq_lib.get_subnet(ip=args.app_ip)
  # Initiate log file
  dss.auxiliaries.logging.configure('app_test_sensor', stdout=args.stdout, rotating=True, loglevel=args.log, subdir=subnet)

  # Create the PhotoMission class
  try:
    app = SensorTest(args.app_ip, args.id, args.crm)
  except dss.auxiliaries.exception.NoAnswer:
    _logger.error('Failed to instantiate application: Probably the CRM couldn\'t be reached')
    sys.exit()
  except:
    _logger.error(f'Failed to instantiate application\n{traceback.format_exc()}')
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
