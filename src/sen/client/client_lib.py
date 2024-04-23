'''
Sensor *Client*

This is the sensor object. Commands can be sent and information can be
requested from the sensor. This object provides convience methods to
make communication and implementation easy.

It uses the sen.client.SEN object, which is in charge of the socket
amd the actual API as described in documentation.
'''

import json
import logging
import time

import dss.auxiliaries
import sen.client


__author__ = 'Andreas Gising <andreas.gising@ri.se>, Kristoffer Bergman <kristoffer.bergman@ri.se>, Hanna Müller <hanna.muller@ri.se>, Joel Nordahl'
__version__ = '1.1.0'
__copyright__ = 'Copyright (c) 2019-2021, RISE'
__status__ = 'development'

class Client:
  '''Base class for Sensor applications'''
  def __init__(self, timeout, exception_handler=None, context=None):
    '''
    The timeout defines the interval used to send heartbeats when no
    other command has been send.
    '''
    self._logger = logging.getLogger(__name__)

    self._logger.info(f'SEN client_lib {dss.auxiliaries.git.describe()}')

    self._app_id = 'da000'

    self._alive = False
    self._context = context if context else dss.auxiliaries.zmq_lib.Context()
    self._sen = None
    self._exception_handler = exception_handler
    self._input_handler = None
    self._input_socket = None
    self._task_queue = dss.auxiliaries.TaskQueue(exception_handler=exception_handler)
    self._thread = None
    self._timeout = timeout
    self._in_controls = False
    self._app_abort = False


  @property
  def alive(self):
    '''Checks if the sen client is alive'''
    return self._alive

  @property
  def app_id(self):
    '''Retruns protected _app_id'''
    return self._app_id

  @property
  def app_abort(self):
    '''Returns protected _app_abort flag'''
    return self._app_abort

  @app_abort.setter
  def app_abort(self, value):
    self._app_abort = value

  @property
  def operator(self):
    '''Returns protected _in_controls for backwards compatibility'''
    self._logger.warning("Use of deprecated property 'operator', use in_controls")
    return self._in_controls

  @property
  def in_controls(self):
    '''Retruns protected _in_controls'''
    return self._in_controls

  #@alive.setter
  #def alive(self, value):
  #  self._alive = value

  # *******************
  # Client base methods
  # *******************

  def set_input_handler(self, port, input_handler):
    '''Defines an asynchronous input handler'''
    if self._input_handler:
      raise dss.auxiliaries.exception.Error('An asynchronous input handler is already defined')

    self._input_handler = input_handler
    self._input_socket = dss.auxiliaries.zmq_lib.Rep(self._context, '*', port, label='input-rep', timeout=self._timeout)
    self._logger.info(f"Starting input server on port {port}")

  def raise_if_aborted(self, app_allowed=True):
    # Test if controls where taken
    if self.in_controls and not self.is_who_controls('APPLICATION'):
      # Controls were taken
      self._in_controls = False
      raise dss.auxiliaries.exception.AbortTask("Controls where taken")

    if not self._alive:
      raise dss.auxiliaries.exception.AbortTask()

    if self.app_abort:
      self.app_abort = False
      # Raise error only if application is allowed to cause error
      if app_allowed:
        raise dss.auxiliaries.exception.AbortTask()

  def abort(self, msg=None, rtl=False):
    '''Aborts the mission and stops all threads'''
    if msg:
      self._logger.error(msg)

    self._task_queue.clear()
    self._alive = False
    if rtl:
      pass
      #self.rtl()

  def connect(self, ip, port=None, app_id=None) -> None:
    '''Connects to sensor server
    port=None is used to remain backward compatible'''
    if self._thread:
      raise dss.auxiliaries.exception.Error('SEN client is already running')

    if port:
      sen_address = f'tcp://{ip}:{port}'
    else:
      sen_address = ip
      ip, port = ip.rsplit(':', 1)
      _, ip = ip.rsplit('/', 1)

    if app_id is not None:
      self._app_id = app_id
    else:
      logging.error("Convert your code to send app_id upon connect")

    # Connect to SEN
    self._sen = sen.client.sen_api.SEN(self._context, self._app_id, ip, port, None, timeout=self._timeout)
    self._alive = True

    # Test connection, owner change must have gone through to get ack. Takes some time sometimes
    max_attempt = 20
    for attempt in range(max_attempt):
      try:
        self._sen.heart_beat()
      except dss.auxiliaries.exception.Nack:
        # If the owner change has not gone through, we get nack
        pass
      else:
        # We must have received an ack, correctly connected, break for-loop
        break
      # Give up if no success after maximum number of attempts, raise exception
      if attempt == max_attempt-1:
        self._logger.error('Failed to connect to DSS on %s', sen_address)
        raise dss.auxiliaries.exception.Error(f'Failed to connect to DSS on {sen_address}')
      time.sleep(0.1)

    # SEN class will update sen_id to connected sen when get_info runs.
    try:
      _ = self._sen.get_info()
    except dss.auxiliaries.exception.Nack:
      self._logger.warning('Failed to retreive sen_id from get_info. SEN class might not have a sen_id')

    self._logger.info('Connection to SEN established on %s', sen_address)

  # Connect to a SEN as guest, without beeing the owner
  def connect_as_guest(self, ip, port, app_id) -> None:
    '''Connects to sen server
    port=None is used to remain backward compatible'''
    if self._thread:
      raise dss.auxiliaries.exception.Error('DSS client is already running')

    # Set app id in the Client object
    self._app_id = app_id

    # Connect to DSS
    self._sen = sen.client.sen_api.SEN(self._context, self._app_id, ip, port, None, timeout=self._timeout)
    self._alive = True

    # SEN class will update sen_id to connected sen when get_info runs.
    try:
      _ = self._sen.get_info()
    except:
      self._logger.error(f'Error, could not connect as guest to tcp://{ip}:{port}')

    self._logger.info(f'Connection to SEN established on tcp://{ip}:{port}')

  def sen_disconnect(self) -> None:
    '''Disconnect the SEN'''
    self._sen.disconnect()

  def close_sen_socket(self) -> None:
    '''Close the socket to the SEN'''
    self._alive = False
    self._sen._socket.close()
    self._sen = None

  def run(self):
    '''Executes the mission'''
    self._task_queue.start()

    # Handle external inputs, e.g. mission abort
    try:
      while self._alive:
        if self._input_handler:
          try:
            msg = self._input_socket.recv_json()
          except dss.auxiliaries.exception.Again:
            pass
          else:
            msg = json.loads(msg)
            try:
              self._input_handler(msg)
            except Exception as error:
              if self._exception_handler:
                self._exception_handler(error)
              answer = json.dumps({'fcn': 'nack', 'call': msg['fcn']})
            else:
              answer = json.dumps({'fcn': 'ack', 'call': msg['fcn']})
            self._input_socket.send_json(answer)
        else:
          time.sleep(0.5)

        if self._task_queue.idling:
          self._logger.info('Mission complete')
          self.abort()
    except KeyboardInterrupt:
      self.abort('Shutdown due to keyboard interrupt', rtl=True)

    # stop task queue
    self._task_queue.stop()

    # close zmq connections
    if self._input_handler:
      self._input_socket.close()
    #self._sen._socket.close()

  def add_task(self, task, arg1=None, arg2=None, arg3=None, arg4=None):
    self._task_queue.add(task, arg1, arg2, arg3, arg4)

  # *******************
  # Convenience methods
  # *******************

  # Test get focus
  def test_get_focus(self):
    answer = self._sen.test_get_focus()
    # Return the focus as a number
    return answer['test_get_cam_focus']

  def test_get_name(self):
    answer = self._sen.test_get_name()
    # Return name as a string
    return answer['name']

  # Enable data stream
  def enable_data_stream(self, stream):
    self._sen.data_stream(stream=stream, enable=True)

  # Disable data stream
  def disable_data_stream(self, stream):
    self._sen.data_stream(stream=stream, enable=False)

  # Get info pub port or data pub port of connected SEN
  def get_port(self, port_label) -> int:
    answer = self._sen.get_info()
    return int(answer[port_label])

  def get_id(self) -> str:
    answer = self._sen.get_info()
    return str(answer['id'])

  # Get state message
  def get_state(self) -> dict:
    return self._sen.get_state()

  # Check who controls
  def is_who_controls(self, who) -> bool:
    return self._sen.who_controls() == who
  # Check who owns
  def is_owner(self, owner) -> bool:
    return self._sen.get_owner() == owner

  # Wait until the controls are handed over
  def await_controls(self):
    while not self.is_who_controls('APPLICATION'):
      self._logger.info('APPLICATION waiting for the CONTROLS')
      time.sleep(0.5)
    self._in_controls = True

  # Wait until controls are taken by Pilot
  def await_not_in_controls(self):
    while self.is_who_controls('APPLICATION'):
      self._logger.info('APPLICATION waiting for PILOT to take CONTROLS')
      time.sleep(0.5)
    self._in_controls = False

  # Wait until the sensor is idle
  def await_idling(self, raise_if_aborted = True):
    self._logger.info('Waiting for sen to idle')
    while not self._sen.get_idle():
      if raise_if_aborted:
        self.raise_if_aborted()
      time.sleep(0.5)

  def get_idle(self):
    return self._sen.get_idle()


  def set_init_point(self, heading_ref):
    self._sen.set_init_point(heading_ref)

  def cv_algorithm(self, algorithm, enable):
    _ = self._sen.cv_algorithm(algorithm, enable)


  # Set gimbal
  def set_gimbal(self, roll, pitch, yaw):
    self._sen.set_gimbal(roll, pitch, yaw)

  # *************
  # Photo library
  # *************

  def photo_connect(self, name):
    '''Not documented: keep it or remove it?'''
    raise dss.auxiliaries.exception.NotImplemented()

  def photo_disconnect(self):
    '''Not documented: keep it or remove it?'''
    raise dss.auxiliaries.exception.NotImplemented()

  def get_metadata(self, ref, index) -> dict:
    return self._sen.get_metadata(ref, index)

  # Take a photo
  def photo_take_photo(self):
    self._sen.photo('take_photo')

  # Control continous photo
  def photo_continous_photo(self, enable, period=2, publish="off"):
    self._sen.photo('continous_photo', '', '', enable, period, publish)

  # Photo download
  def photo_download(self, index, resolution):
    self._sen.photo('download', resolution, index)

  # Photo recording
  def photo_rec(self, enable):
    self._sen.photo(cmd='record', enable=enable)
class Remove_me:
  '''Base class for Sensor applications'''
  def __init__(self):
    self.apa = 1
