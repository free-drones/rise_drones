#!/usr/bin/env python3

'''
APP "app_viser", originates from template photo mission

This app:
- Connects to CRM and receives an app_id
- Requests a spotlight drone
- Sets up position logging
- Enables spotlight blink by toggeling controls
- Downloads all data when control is toggeled post landing
'''

import argparse
import json
import logging
import sys
import threading
import time
import traceback
from datetime import datetime

import zmq

import dss.auxiliaries
import dss.client

#--------------------------------------------------------------------#

__author__ = 'Andreas Gising <andreas.gising@ri.se>, Kristoffer Bergman <kristoffer.bergman@ri.se>, Hanna Müller <hanna.muller@ri.se>, Joel Nordahl'
__version__ = '0.2.0'
__copyright__ = 'Copyright (c) 2022, RISE'
__status__ = 'development'

#--------------------------------------------------------------------#

_logger = logging.getLogger('dss.template')
_context = zmq.Context()

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

class PhotoMission():
  # Init
  def __init__(self, app_ip, app_id, crm):
    # Create Client object, set high timeout since connection is poor and we are handeling pictures
    self.drone = dss.client.Client(timeout=10000, exception_handler=None, context=_context)

    # Create CRM object
    self.crm = dss.client.CRM(_context, crm, app_name='app_viser.py', desc='Viser calibration app', app_id=app_id)

    self._alive = True
    self._dss_data_thread = None
    self._dss_data_thread_active = False
    self._dss_info_thread = None
    self._dss_info_thread_active = False

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
    _logger.info(f'App_viser registered with CRM: {self.crm.app_id}')

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
    if not dss.auxiliaries.zmq_lib.is_ack(answer):
      _logger.error('Unregister failed: {answer}')
    _logger.info("CRM socket closed")

    # Disconnect drone if drone is alive
    if self.drone.alive:
      #wait until other DSS threads finished
      time.sleep(0.5)
      _logger.info("Closing socket to DSS")
      self.drone.close_dss_socket()

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
# Setup the DSS info stream thread
  def setup_dss_info_stream(self, timestamp):
    #Get info port from DSS
    info_port = self.drone.get_port('info_pub_port')
    if info_port:
      self._dss_info_thread = threading.Thread(
        target=self._main_info_dss, args=[self.drone._dss.ip, info_port, timestamp])
      self._dss_info_thread_active = True
      self._dss_info_thread.start()

#--------------------------------------------------------------------#
# Setup the DSS data stream thread
  def setup_dss_data_stream(self):
    #Get data port from DSS
    data_port = self.drone.get_port('data_pub_port')
    if data_port:
      self._dss_data_thread = threading.Thread(
        target=self._main_data_dss, args=[self.drone._dss.ip, data_port])
      self._dss_data_thread_active = True
      self._dss_data_thread.start()

#--------------------------------------------------------------------#
# The main function for subscribing to info messages from the DSS.
  def _main_info_dss(self, ip, port, timestamp):
    # Create a logfile of STATE data and the metadata.
    # A text file will be built up, missing the trailing curly bracket to be resilient to early exits.
    # Once logging compleete, the final curly bracket will be added and converted to JSON.
    # Generate filenames
    log_items_filename = '{}_{}'.format(timestamp, 'viser-log-items.txt')
    log_filename = '{}_{}'.format(timestamp, 'viser-log.json')
    log_items = 'log/' + log_items_filename
    log_file = 'log/' + log_filename

    # Init log items
    k = 0
    with open(log_items, 'w', encoding="utf-8") as outfile:
      # Manually add the initial key with empty string value
      first_key_value = f'{{ "{k}": ""'
      outfile.write(first_key_value)


    # Enable LLA stream
    # self.drone._dss.data_stream('LLA', True)
    # Enable STATE stream
    self.drone.enable_data_stream('STATE')
    self.drone.enable_data_stream('photo_LLA')
    # Create info socket and start listening thread
    info_socket = dss.auxiliaries.zmq_lib.Sub(_context, ip, port, "info " + self.crm.app_id)
    while self._dss_info_thread_active:
      try:
        (topic, msg) = info_socket.recv()
        if topic == 'STATE':
          _logger.info(msg)
          # Save STATE information and leave out final curly bracket
          k += 1
          # Save the log_item under a new key in the log file built line by line
          with open(log_items, 'a', encoding="utf-8") as outfile:
            # Build up string to print to file
            # Test both time formats
            _time = datetime.now()
            time_stamp ={}
            time_stamp["hour"] = _time.strftime("%H")
            time_stamp["minute"] = _time.strftime("%M")
            time_stamp["second"] = _time.strftime("%S")
            time_stamp["microsecond"] = _time.strftime("%f")
            time_stamp["string"] = _time.strftime("%H:%M:%S.%f")
            # Create a log string: ' , "k": {"time": {time_stamp}, "state": {state}}
            log_string = f',"{k}":'
            log_string += f'{{'
            log_string += f'"time": {json.dumps(time_stamp)}'
            log_string += f','
            log_string += f'"state": {json.dumps(msg)}'
            log_string += f'}}'
            # write the log_item as a string under the newly added key
            outfile.write(log_string)

        elif topic == 'battery':
          _logger.info('Remaning battery time: '+ msg['remaining_time'] +  ' seconds')
        elif topic == 'currentWP':
          if int(msg["currentWP"]) == -1:
            _logger.info('Mission is completed')
          else:
            _logger.info(f'Going to wp {msg["currentWP"]}, final wp is msg["finalWP"]')
        elif topic == 'photo_LLA':
          _logger.info(f' Photo LLA metadata: {msg}')
        else:
          _logger.info(f'Topic not recognized on info link: {topic}')
      except:
        pass

    # Thread is shutting down
    # Add the final curly bracket to log items
    with open(log_items, 'a', encoding="utf-8") as outfile:
      outfile.write('}')

    # Open the log items file and save it in log file with pretty print
    with open(log_items, 'r', encoding="utf-8") as infile:
      big_json = json.load(infile)
      with open(log_file, 'w', encoding="utf-8") as outfile:
        log_str = json.dumps(big_json, indent=4)
        outfile.write(log_str)

    info_socket.close()
    _logger.info("Stopped thread and closed info socket")

#--------------------------------------------------------------------#
# The main function for subscribing to data messages from the DSS.
  def _main_data_dss(self, ip, port):
    # Create data socket and start listening thread
    data_socket = dss.auxiliaries.zmq_lib.Sub(_context, ip, port, "data " + self.crm.app_id)
    while self._dss_data_thread_active:
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
    # Get a drone
    answer = self.crm.get_drone(capabilities=['SPOTLIGHT'])
    if dss.auxiliaries.zmq_lib.is_nack(answer):
      _logger.error(f'Did not receive a drone: {dss.auxiliaries.zmq_lib.get_nack_reason(answer)}')
      _logger.info('No available drone')
      return

    # Connect to the drone, set app_id in socket
    try:
      self.drone.connect(answer['ip'], answer['port'], app_id=self.crm.app_id)
      _logger.info(f"Connected as owner of drone: [{self.drone._dss.dss_id}]")
    except:
      _logger.info("Failed to connect as owner, check crm")
      return

    # Setup info and data stream to DSS
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    self.setup_dss_info_stream(timestamp)
    self.setup_dss_data_stream()

    # Send a command to the connected drone and print the result
    _logger.info(self.drone._dss.get_info())

    # Request controls from PILOT
    _logger.info("Requesting controls")
    self.drone.await_controls()
    _logger.info("Application is in controls")

    # Set init point with camera as heading reference
    self.drone.try_set_init_point('camera')

    # Take-off and set gimbal
    _logger.info("Take off")
    self.drone.arm_and_takeoff(5)
    self.drone.set_gimbal(roll=0, pitch=-90, yaw=0)
    print('Take-off complete, fly to calibration point and hand over')

    # Wait for Pilot to take controls, just send velo_BODY in the mean time.
    self.drone.await_not_in_controls()

    # Wait for controls, Pilot will hand over controls when in position.
    self.drone.await_controls()
    # Set gimbal down in case pilot took control during take-off
    self.drone.set_gimbal(roll=0, pitch=-90, yaw=0)

    # While we are still flying, take photo and blink spotlight each time controls are handed over
    while self.drone.get_flight_state() != 'landed':
      print('Will take photo and blink spotlight')
      self.drone.photo_take_photo()
      time.sleep(1)
      # Blink the spotlight
      try:
        self.drone.enable_spotlight(brightness=100)
        time.sleep(1)
        self.drone.disable_spotlight()
        _logger.info('Download latest low res photo to update metadata with filenames')
        time.sleep(1)
        self.drone.photo_download('latest', 'low')
        _logger.info('Download low res photo')

        time.sleep(2)
      except:
        pass

      print('Fly to next calibration point or land, then hand over controls')
      # Wait for pilot to controls
      self.drone.await_not_in_controls()

      # Wait for controls, Pilot will hand over controls when in position or landed.
      self.drone.await_controls()

    # Landed and in controls
    # Stop STATE stream, it will just flood the log
    self.drone.disable_data_stream('STATE')

    print('Data download will start, be patient..')
    # Download all photos high res and metadata.
    # Save metadata to file
    json_metadata = self.drone.get_metadata(ref='LLA', index='all')

    metadata_filename = '{}_{}'.format(timestamp, 'viser-metadata.json')
    metadata_file = 'log/' + metadata_filename
    with open(metadata_file, "w") as fh:
      fh.write(json.dumps(json_metadata, indent=4))
      _logger.info('Metadata saved to log/timestamp_viser-metadata.json')

    # For convinence print photo metadata to log. Whole json cannot be printed to log, its truncated.
    for item in json_metadata:
      _logger.info(f'Metadata index {json.dumps(item)}: {json.dumps(json_metadata[item])}')

    # Download all photos one by one
    n_photos = len(json_metadata)
    index = 1
    downloaded_to_phone = 0
    self.transferred = 0

    _logger.info(f'Download all photos {n_photos} in sequence, this might take a while. Consider downloading from SD-card.')

    while index < n_photos + 1:
      print('Downloading and transfering..')
      while True:
        try:
          # If camera is busy downloading an exception is thrown
          self.drone.photo_download(index, 'high')
          _logger.info(f'Download index: {index}')
          downloaded_to_phone += 1
          # Wait for the file to be transferred before asking for next. Buffer no more than one photo
          seconds = 0
          while downloaded_to_phone > self.transferred + 1:
            _logger.info(f'Transfer index {self.transferred + 1} of {n_photos} to app.. elapsed time: {seconds}')
            time.sleep(1)
            seconds += 1
          # A photo has been transferred
          _logger.info(f'Downloaded to phone: {downloaded_to_phone},  transferred to application: {self.transferred}')
        except dss.auxiliaries.exception.Nack as nack:
          _logger.warning(nack.msg)
          if nack.msg == 'Requester is not the DSS owner':
            _logger.info("PILOT took the controls, await controls")
            self.drone.await_controls()
          if nack.msg == 'Camera resource is busy':
            time.sleep(1)
        except:
          # unknown exception, try again
          time.sleep(1)
        else:
          break
      index += 1

    # Wait for the last photo to be downloaded
    print('Transferring last photo.. almost there')
    while downloaded_to_phone != self.transferred:
      _logger.info(f'Transfer final index {self.transferred + 1}')
      time.sleep(0.5)

    print('Mission complete, BYE')
    # Grafully die
    _logger.info(f'Downloaded to phone: {downloaded_to_phone},  transferred to application: {self.transferred}')
    _logger.info("All photos and metadata downloaded. Good bye")


#--------------------------------------------------------------------#
def _main():
  # parse command-line arguments
  parser = argparse.ArgumentParser(description='APP "app_viser"', allow_abbrev=False, add_help=False)
  parser.add_argument('-h', '--help', action='help', help=argparse.SUPPRESS)
  parser.add_argument('--app_ip', type=str, help='ip of the app', required=True)
  parser.add_argument('--id', type=str, default=None, help='id of this app_viser instance if started by crm')
  parser.add_argument('--crm', type=str, help='<ip>:<port> of crm', required=True)
  parser.add_argument('--log', type=str, default='debug', help='logging threshold')
  parser.add_argument('--owner', type=str, help='id of the instance controlling app_viser - not used in this use case')
  parser.add_argument('--stdout', action='store_true', help='enables logging to stdout')
  args = parser.parse_args()

  # Identify subnet to sort log files in structure
  subnet = dss.auxiliaries.zmq_lib.get_subnet(ip=args.app_ip)
  # Initiate log file
  dss.auxiliaries.logging.configure('app_viser', stdout=args.stdout, rotating=True, loglevel=args.log, subdir=subnet)

  # Create the PhotoMission class
  try:
    app = PhotoMission(args.app_ip, args.id, args.crm)
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

  # Temporary notes. await controls to be taken
  # while True:
      #       try:
      #         self.drone.set_vel_BODY(0,0,0,0)
      #         time.sleep(1)
      #       except dss.auxiliaries.exception.Nack as nack:
      #         if nack.msg == 'Application is not in controls':
      #           # Pilot took controls
      #           break
