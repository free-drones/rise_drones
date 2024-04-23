'''Sensor Server'''

import json
import logging
import threading
import time
import traceback

import dss.auxiliaries
import sen.server.picam


from dss.auxiliaries.config import config


__author__ = 'Andreas Gising <andreas.gising@ri.se>, Kristoffer Bergman <kristoffer.bergman@ri.se>, Hanna Müller <hanna.muller@ri.se>, Joel Nordahl'
__version__ = '1.1.0'
__copyright__ = 'Copyright (c) 2019-2023, RISE'
__status__ = 'development'

MAX_PRIORITY = 10

class Server:
  '''Sensor Server'''

  def __init__(self, sen_ip, sen_id='', camera='', crm: str='', capabilities=None, description='Sensor_server', die_gracefully: bool=False):
    # TODO, have to configure log level specifically for this logger, why? The logger seem to have level EROOR, should have DEBUG?
    self._logger = logging.getLogger(__name__)
    self._logger.setLevel(logging.DEBUG)
    self._logger.info(f'Sensor Server version: {dss.__version__}, git describe: {dss.auxiliaries.git.describe()}')

    if die_gracefully:
      # source: https://stackoverflow.com/a/31464349
      import signal
      signal.signal(signal.SIGINT, self.exit_gracefully)
      signal.signal(signal.SIGTERM, self.exit_gracefully)

    # create all objects that are used in the destructor
    self._cam = None
    self._sen_id = sen_id
    self._sen_ip = sen_ip

    self._owner = 'da000'

    self._zmq_context = dss.auxiliaries.zmq_lib.Context()

    # This attribute is true if there is a connection to a sensor client
    # application
    self._connected = False

    # Split crm connection string"
    if crm:
      (_, crm_port) = crm.split(':')
      crm_port = int(crm_port)

    # zmq sockets
    app_port = None

    # We will connect to crm, set random ports within range.
    self._serv_socket = dss.auxiliaries.zmq_lib.Rep(self._zmq_context, port=app_port, label='sen', min_port=crm_port+1, max_port=crm_port+49)
    self._pub_socket = dss.auxiliaries.zmq_lib.Pub(self._zmq_context, port=None, min_port=crm_port+1, max_port=crm_port+50, label='info')
    self._logger.info('Starting pub server on %d... done', self._pub_socket.port)

    if camera == 'picam':
      self._cam =  sen.server.picam.PiCam(publish_method = self._pub_socket.publish)
      self._logger.info('Initiating PiCam..')

    # Publish attributes
    self._pub_attributes = {'BB':                   {'enabled': False, 'name': 'boundingBox'},
                            'OD':                   {'enabled': False, 'name': 'objectDetection'}}

    # _commands is a lookup table for all the sen commands
    # 'request' points to the synchronous request call-back
    # 'task' points to an optional asynchronous task call-back

    # Functions in same order as documentation
    self._commands = {'heart_beat':         {'request': self._request_heart_beat,         'task': None},
                      'get_info':           {'request': self._request_get_info,           'task': None},
                      'who_controls':       {'request': self._request_who_controls,       'task': None},
                      'get_owner':          {'request': self._request_get_owner,          'task': None},
                      'set_owner':          {'request': self._request_set_owner,          'task': None},
                      'get_idle':           {'request': self._request_get_idle,           'task': None},
                      'get_pose':           {'request': self._request_get_pose,           'task': None},
                      'set_pose':           {'request': self._request_set_pose,           'task': None},
                      'set_gimbal':         {'request': self._request_set_gimbal,         'task': None},
                      'cv_algorithm':       {'request': self._request_cv_argorithm,       'task': self._task_cv_algorithm, 'priority': 1},
                      'test_get_focus':     {'request': self._request_test_get_focus,     'task': None},
                      'test_get_name':      {'request': self._request_test_get_name,      'task': None},
                      'data_stream':        {'request': self._request_data_stream,        'task': None},#self._task_data_stream,'priority': MAX_PRIORITY},
                      # 'disconnect':         {'request': self._request_disconnect,         'task': self._task_disconnect, 'priority': 1},
                      # 'dss_srtl':           {'request': self._request_dss_srtl,           'task': self._task_dss_srtl, 'priority': MAX_PRIORITY},
                      # 'get_state':          {'request': self._request_get_state,          'task': None},
                      # 'get_metadata':       {'request': self._request_get_metadata,       'task': None}, # Not implemented

                      'photo':              {'request': self._request_photo,              'task': None}, # Not implemented
                     }

    # create initial task
    self._task = {'fcn': ''}
    self._task_event = threading.Event()
    self._task_priority = 0

    self._alive = True
    self._in_controls = 'APPLICATION'  # How to use this for sensors?
    self._gcs_heartbeat = None         # No need for gcs

    # start main thread
    main_thread = threading.Thread(target=self._main, daemon=False)
    main_thread.start()

    # start task thread
    task_thread = threading.Thread(target=self._main_task, daemon=True)
    task_thread.start()

    # register sen
    self._capabilities = capabilities
    self._crm = dss.client.CRM(self._zmq_context, crm, app_name='sen.py', desc=description, app_id=self._sen_id)
    # register and start sending heartbeat to the CRM
    self._logger.info(f"registering to CRM with capabilities: {self._capabilities}")
    answer = self._crm.register(self._sen_ip, self._serv_socket.port, type='sen', capabilities=self._capabilities)
    if dss.auxiliaries.zmq_lib.is_ack(answer):
      self._sen_id = answer['id']
      self._logger.info(f"Regitered to CRM, received id {answer['id']}")
    else:
      self._logger.error(f'register failed: {answer}')
      self.alive = False

  def lost_link_to_gcs(self):
    '''returns true if the connection to the gcs has been lost'''
    if self._gcs_heartbeat:
      return not self._gcs_heartbeat.vital
    return False

  def exit_gracefully(self, *args):
    self._logger.warning('Shutdown due to interrupt')
    self.alive = False

  @property
  def alive(self):
    '''Checks if the dss server is alive'''
    return self._alive

  @alive.setter
  def alive(self, value):
    self._alive = value

	# Ack nack helpers
	# Is message from owner?
  def from_owner(self, msg)->bool:
    return msg['id'] == self._owner

  #############################################################################
  # REQUESTS
  #############################################################################


  ######
  # Dummy methods for test
  def _request_test_get_focus(self,msg):
    fcn = dss.auxiliaries.zmq_lib.get_fcn(msg)
    # No nack reasons, accept
    print(f'This is the _request_test_me function called on request test_me. Arguments are {msg}')
    answer = dss.auxiliaries.zmq_lib.ack(fcn, {'test_get_cam_focus': self._cam.test_cam_get_focus()})
    return answer

  def _request_test_get_name(self,msg):
    fcn = dss.auxiliaries.zmq_lib.get_fcn(msg)
    # No nack reasons, accept
    answer = dss.auxiliaries.zmq_lib.ack(fcn, {'name': self._cam._name})
    return answer
  #######

  def _request_heart_beat(self, msg) -> dict:
    fcn = dss.auxiliaries.zmq_lib.get_fcn(msg)
    # Test nack reasons
    if not self.from_owner(msg):
      descr = 'Requester ({}) is not the DSS owner'.format(msg['id'])
      answer = dss.auxiliaries.zmq_lib.nack(fcn, descr)
    # Accept
    else:
      answer = dss.auxiliaries.zmq_lib.ack(fcn)
    return answer

  def _request_get_info(self, msg) -> dict:
    fcn = dss.auxiliaries.zmq_lib.get_fcn(msg)
    # No nack reasons, accept
    answer = dss.auxiliaries.zmq_lib.ack(fcn, {'info_pub_port': self._pub_socket.port, 'data_pub_port': '', 'id': self._sen_id})
    return answer

  def _request_who_controls(self, msg) -> dict:
    fcn = dss.auxiliaries.zmq_lib.get_fcn(msg)
    # No nack reasons, accept
    answer = dss.auxiliaries.zmq_lib.ack(fcn, {'in_controls': self._in_controls})
    return answer

  def _request_get_owner(self, msg) -> dict:
    fcn = dss.auxiliaries.zmq_lib.get_fcn(msg)
    # No nack reasons, accept
    answer = dss.auxiliaries.zmq_lib.ack(fcn)
    answer['owner'] = self._owner
    return answer

  def _request_set_owner(self, msg) -> dict:
    fcn = dss.auxiliaries.zmq_lib.get_fcn(msg)
    # Test nack reasons
    if not msg['id'] == 'crm':
      answer = dss.auxiliaries.zmq_lib.nack(fcn, 'Requestor is not CRM')
    # Accept
    else:
      new_owner = msg['owner']
      self._owner = new_owner
      # New owner -> reset connected flag
      self._connected = False
      answer = dss.auxiliaries.zmq_lib.ack(fcn)
    return answer


  def _request_get_idle(self, msg) -> dict:
    fcn = dss.auxiliaries.zmq_lib.get_fcn(msg)
    # No nack reasons, accept
    answer = dss.auxiliaries.zmq_lib.ack(fcn, {'idle': self._task_event.is_set()})
    return answer

  def _request_get_pose(self, msg):
    fcn = dss.auxiliaries.zmq_lib.get_fcn(msg)
    # No nack reasons, accept
    answer = dss.auxiliaries.zmq_lib.ack(fcn, {'idle': self._task_event.is_set()})
    # But not implementede so nack
    answer = dss.auxiliaries.zmq_lib.nack(fcn, desc="Not implemented")
    return answer

  def _request_set_pose(self, msg):
    fcn = dss.auxiliaries.zmq_lib.get_fcn(msg)
    # No nack reasons, accept
    answer = dss.auxiliaries.zmq_lib.ack(fcn, {'idle': self._task_event.is_set()})
    # But not implementede so nack
    answer = dss.auxiliaries.zmq_lib.nack(fcn, desc="Not implemented")
    return answer

  def _request_set_gimbal(self, msg) -> dict:
    fcn = dss.auxiliaries.zmq_lib.get_fcn(msg)
    # Parse
    roll = msg['roll']
    pitch = msg['pitch']
    yaw = msg['yaw']
    # Test nack reasons
    if not self.from_owner(msg):
      descr = 'Requester ({}) is not the DSS owner'.format(msg['id'])
      answer = dss.auxiliaries.zmq_lib.nack(fcn, descr)

    elif self._in_controls != 'APPLICATION':
      answer = dss.auxiliaries.zmq_lib.nack(fcn, 'Application is not in controls')

    elif False: # TODO, roll pitch yaw is out of range
      answer = dss.auxiliaries.zmq_lib.nack(fcn, 'Roll, pitch or yaw is out of range fo the gimbal')
    # Accept
    else:
      answer = dss.auxiliaries.zmq_lib.ack(fcn)
      #self._hexa.set_gimbal(msg['roll'], msg['pitch'], msg['yaw'])
    return answer


  def _request_photo(self, msg) -> dict:
    fcn = dss.auxiliaries.zmq_lib.get_fcn(msg)
    # Parse
    cmd = msg['cmd']
    # Test nack reasons
    if not self.from_owner(msg):
      descr = 'Requester ({}) is not the DSS owner'.format(msg['id'])
      answer = dss.auxiliaries.zmq_lib.nack(fcn, descr)
    elif self._in_controls != 'APPLICATION':
      answer = dss.auxiliaries.zmq_lib.nack(fcn, 'Application is not in controls')
    elif False: # TODO, Camera resource busy
      answer = dss.auxiliaries.zmq_lib.nack(fcn, 'Camera resource is busy')
    elif not cmd in ('take_photo', 'continous_photo', 'download'):
      answer = dss.auxiliaries.zmq_lib.nack(fcn, 'Cmd faulty')
    # Accept
    else:
      if cmd == 'take_photo':
        answer = dss.auxiliaries.zmq_lib.ack(fcn)
        answer['description'] = 'take_photo'
        # TODO, take_photo
        answer = dss.auxiliaries.zmq_lib.nack(fcn, 'Take photo not implemented')
      elif cmd == 'continous_photo':
        enable = msg['enable']
        publish = msg['publish'] #'off', 'low' or 'high'
        period = msg['period']
        answer = dss.auxiliaries.zmq_lib.ack(fcn)
        if enable:
          descr = 'continous_photo enabled'
        else:
          descr = 'continous_photo disabled'
        answer['description'] = descr
        # TODO, enable/disable continous photo
        answer = dss.auxiliaries.zmq_lib.nack(fcn, 'Continous photo not implemented')
      elif cmd == 'download':
        resolution = msg['resolution']
        index = msg['index']
        # Test more nack reasons
        if False:
          anser = dss.auxiliaries.zmq_lib.nack(fcn, 'Index out of range' + index)
        elif False:
          anser = dss.auxiliaries.zmq_lib.nack(fcn, 'Index string faulty' + index)
        # Accept
        else:
          answer = dss.auxiliaries.zmq_lib.ack(fcn)
          answer['description'] = 'download ' + 'index'
          # TODO, download photo
          answer = dss.auxiliaries.zmq_lib.nack(fcn, 'Download photo not implemented')
    return answer

  def _request_data_stream(self, msg) -> dict:
    fcn = dss.auxiliaries.zmq_lib.get_fcn(msg)
    # Parse
    stream = msg['stream']
    enable = msg['enable']
    # Test nack reasons
    if stream not in self._pub_attributes:
      descr = 'Stream faulty, ' + stream
      answer = dss.auxiliaries.zmq_lib.nack(fcn, descr)
    # Accept
    else:
      answer = dss.auxiliaries.zmq_lib.ack(fcn)
      # Update publish attributes dict
      self._pub_attributes[stream]['enabled'] = enable
      # Activate publish of stream
      if stream == 'STATE':
        # STATE requires pos attribute listener. Make sure there is one enabled.
        if not self._pub_attributes['LLA']['enabled']:
          msg_mod = msg
          msg_mod['stream'] = 'LLA'
          return self._request_data_stream(msg_mod)
      if enable:
        pass

      if stream == 'BB':
        self._pub_attributes[stream]['enable'] = enable
        self._cam._publish_cv_BB = enable

      if stream == 'OD':
        self._pub_attributes[stream]['enable'] = enable
        self._cam._publish_cv_OD = enable


      #   self._logger.info("Global listener removed: %s", stream)
    return answer

  def _request_cv_argorithm(self, msg):
    fcn = dss.auxiliaries.zmq_lib.get_fcn(msg)
    # parse
    cv_algorithm = msg['algorithm']
    enable = msg['enable']
    # Test nack reasons
    # Test from owner
    if not self.from_owner(msg):
      descr = 'Requester ({}) is not the DSS owner'.format(msg['id'])
      answer = dss.auxiliaries.zmq_lib.nack(fcn, descr)
    # Test in controls
    elif self._in_controls != 'APPLICATION':
      answer = dss.auxiliaries.zmq_lib.nack(fcn, 'Application is not in controls')
    # Test if disabled algorithm is the running task
    elif not enable and self._cam._status_msg == cv_algorithm:
      answer = dss.auxiliaries.zmq_lib.nack(fcn, 'Cannot disable algorithm not running')
    elif cv_algorithm not in self._cam._cv_algorithms:
      answer = dss.auxiliaries.zmq_lib.nack(fcn, f'Algorithm not supported, {cv_algorithm}')
    # Accept
    else:
      self._cam.cv_algorithm = cv_algorithm
      answer = dss.auxiliaries.zmq_lib.ack(fcn)
    return answer


  def _publisher_callback(self, topic, msg):
    self._pub_socket.publish(topic, msg)

  # Function to handle if the link to the application is lost
  def _is_link_lost(self):
    link_lost = False
    if self._connected:
      curr_time = time.time()
      t_link_lost = 10.0
      t_diff = curr_time - self._t_last_owner_msg
      if 0.5*t_link_lost < t_diff < t_link_lost:
        self._logger.warning("Application link degraded")
      elif t_diff >= t_link_lost:
        self._logger.error("Application is disconnected")
        link_lost = True
        self._connected = False
        if self._crm :
          _ = self._crm.app_lost()
        if self._in_controls == 'APPLICATION':
          self._logger.error('Lost link to the dss client; DSS took the CONTROLS')
          self._in_controls = 'DSS'
        else:
          self._logger.error('Lost link to the dss client')
    return link_lost


  #############################################################################
  # TASKS
  #############################################################################
  # Task computer vision algorithm
  def _task_cv_algorithm(self, msg):
    algortihm = msg['algorithm']
    enable = msg['enable']
    if enable:
      # method task_cv_algorithm runs a loop until abort task
      self._cam.task_cv_algorithm(algortihm)
    else:
      # The task is the running task since the request is acked. Abort task
      self._cam._abort_task = True




  #############################################################################
  # CALLBACKS
  #############################################################################



  #############################################################################
  # THREAD *TASKS*
  #############################################################################

  def _main_task(self):
    '''Executes the current task'''
    while self.alive:
      fcn = self._task['fcn']

      if fcn:
        try:
          task = self._commands[fcn]['task']
          # Run task until AbortTask exception is thrown
          task(self._task)
        except dss.auxiliaries.exception.AbortTask:
          logging.warning('abort current task')
          self._cam.abort_task = False
        except dss.auxiliaries.exception.Error:
          logging.critical(traceback.format_exc())

      if self.alive:
        self._task_event.clear()
        self._task_event.wait()

  #############################################################################
  # THREAD *MAIN*
  #############################################################################

  def _main(self):
    '''Listening for new requests and gcs heartbeats'''
    attempts = 0

    while self.alive:

      #################################
      ## In controls state machine
      #################################

      # Monitor gcs heartbeats
      ########################
      if self._in_controls == 'APPLICATION' and self.lost_link_to_gcs():
        self._logger.error('Lost link to the gcs heartbeats; DSS taking the CONTROLS')
        self._in_controls = 'DSS'
        continue

      # APPLICATION is in controls
      ############################
      if self._task_event.is_set():
        print('\033[K', end='\r') # clear to the end of line
        #print('[%s has the CONTROLS] %s' % (self._in_controls), end='\r')
      else:
        print('\033[K', end='\r') # clear to the end of line
        print('[%s has the CONTROLS] idle' % self._in_controls, end='\r')

      # ZMQ
      #####
      try:
        msg = self._serv_socket.recv_json()
        msg = json.loads(msg)
        if self.from_owner(msg):
          self._t_last_owner_msg = time.time()
      except dss.auxiliaries.exception.Again:
        _ = self._is_link_lost()
        continue

      if not self._connected and self.from_owner(msg) and msg['id'] != 'crm':
        self._connected = True
        self._logger.info('Application is connected')

      fcn = msg['fcn'] if 'fcn' in msg else ''

      if fcn != 'heart_beat':
        self._logger.info('Received request: %s', str(msg))

      if fcn in self._commands:
        request = self._commands[fcn]['request']
        task = self._commands[fcn]['task']

        #we need to try the request prior to executing the task. All nack reasons are handled in the requests
        start_task = False
        if task:
          priority = self._commands[fcn]['priority']
          # Nack reasons for all tasks with low priority
          if self._task_event.is_set() and (self._task_priority == MAX_PRIORITY or priority < self._task_priority):
              answer = {'fcn': 'nack', 'call': fcn, 'description': 'Task not prioritized'}
          # Accept task
          else:
            # Test request
            answer = request(msg)
            if dss.auxiliaries.zmq_lib.is_ack(answer):
              start_task = True
        else:
          # simple requests are always allowed
          answer = request(msg)
      else:
        start_task = False
        print("request not supported")
        print(fcn, msg)
        answer = {'fcn': 'nack', 'arg': msg['fcn'], 'arg2': 'request not supported'}

      answer = json.dumps(answer)
      self._serv_socket.send_json(answer)
      if start_task:
        if self._task_event.is_set():
          self._cam.abort_task = True
          # Wait until task is aborted, if task does not abort in time, new task will not run
          max_wait = 0.5
          _timer = 0
          loop_time = 0.01
          while self._cam.abort_task and _timer < max_wait:
            _timer += loop_time
            time.sleep(loop_time)
        self._task = msg
        self._task_priority = priority
        self._task_event.set()

      if fcn != 'heart_beat':
        self._logger.info("Replied: %s", answer)

    #Unregister from CRM
    if self._crm:
      self._crm.unregister()
    self._logger.info('SEN Server exited correctly. Have a nice day!')
