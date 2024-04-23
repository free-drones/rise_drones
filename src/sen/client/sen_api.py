'''
Sensor *API*

This class is in charge of the socket and the actual API as described
in documentation.
'''

import logging
#import typing

import dss.auxiliaries

__author__ = 'Andreas Gising <andreas.gising@ri.se>, Kristoffer Bergman <kristoffer.bergman@ri.se>, Hanna Müller <hanna.muller@ri.se>, Joel Nordahl'
__version__ = '1.0.0'
__copyright__ = 'Copyright (c) 2023, RISE'
__status__ = 'development'

class SEN:
  def __init__(self, context, app_id, ip, port, sen_id, timeout=1000):
    self._logger = logging.getLogger(__name__)
    self._logger.info(f'DSS dss_api {dss.auxiliaries.git.describe()}')

    self._context = context
    self._app_id = app_id
    self._ip = ip
    self._port = port
    self._sen_id = sen_id

    self._socket = dss.auxiliaries.zmq_lib.Req(context, ip, port, label=sen_id, timeout=timeout, self_id=app_id)
    self._socket.start_heartbeat(app_id)

  def __del__(self):
    self._socket.close()

  @property
  def app_id(self):
    return self._app_id

  @property
  def port(self):
    return self._port

  @property
  def sen_id(self):
    return self._sen_id

  @property
  def ip(self):
    return self._ip

  def heart_beat(self) -> None:
    call = 'heart_beat'
    # build message
    msg = {'fcn': call, 'id': self._app_id}
    # send and receive message
    answer = self._socket.send_and_receive(msg)
    # handle nack
    if not dss.auxiliaries.zmq_lib.is_ack(answer, call):
      raise dss.auxiliaries.exception.Nack(dss.auxiliaries.zmq_lib.get_nack_reason(answer), fcn=call)
    # return
    return

  # Thest method for test only, Reomve later
  def test_get_focus(self) -> dict:
    call = 'test_get_focus'
    # build message
    msg = {'fcn': call, 'id': self._app_id}
    # send and receive message
    answer = self._socket.send_and_receive(msg)
    # handle nack
    if not dss.auxiliaries.zmq_lib.is_ack(answer, call):
      raise dss.auxiliaries.exception.Nack(dss.auxiliaries.zmq_lib.get_nack_reason(answer), fcn=call)
    # return
    return answer

  def test_get_name(self) -> dict:
    call = 'test_get_name'
    # build message
    msg = {'fcn': call, 'id': self._app_id}
    # send and receive message
    answer = self._socket.send_and_receive(msg)
    # handle nack
    if not dss.auxiliaries.zmq_lib.is_ack(answer, call):
      raise dss.auxiliaries.exception.Nack(dss.auxiliaries.zmq_lib.get_nack_reason(answer), fcn=call)
    # return
    return answer


  def get_info(self) -> dict:
    call = 'get_info'
    # build message
    msg = {'fcn': call, 'id': self._app_id}
    # send and receive message
    answer = self._socket.send_and_receive(msg)
    # handle nack
    if not dss.auxiliaries.zmq_lib.is_ack(answer, call):
      raise dss.auxiliaries.exception.Nack(dss.auxiliaries.zmq_lib.get_nack_reason(answer), fcn=call)
    # Take the returned id and store it in the class
    if answer['id'] != self._sen_id:
      self._sen_id = answer['id']
    # return
    return answer

  def who_controls(self) -> str:
    call = 'who_controls'
    # build message
    msg = {'fcn': call, 'id': self._app_id}
    # send and receive message
    answer = self._socket.send_and_receive(msg)
    # handle nack
    if not dss.auxiliaries.zmq_lib.is_ack(answer, call):
      raise dss.auxiliaries.exception.Nack(dss.auxiliaries.zmq_lib.get_nack_reason(answer), fcn=call)
    # return
    return answer['in_controls']

  def get_owner(self) -> str:
    call = 'get_owner'
    # build message
    msg = {'fcn': call, 'id': self._app_id}
    # send and receive message
    answer = self._socket.send_and_receive(msg)
    # handle nack
    if not dss.auxiliaries.zmq_lib.is_ack(answer, call):
      raise dss.auxiliaries.exception.Nack(dss.auxiliaries.zmq_lib.get_nack_reason(answer), fcn=call)
    # return
    return answer['owner']

  def set_owner(self) -> None:
    call = 'set_owner'
    # build message
    msg = {'fcn': call, 'id': self._app_id}
    # send and receive message
    answer = self._socket.send_and_receive(msg)
    # handle nack
    if not dss.auxiliaries.zmq_lib.is_ack(answer, call):
      raise dss.auxiliaries.exception.Nack(dss.auxiliaries.zmq_lib.get_nack_reason(answer), fcn=call)
    # return
    return

  def cv_algorithm(self, algorithm, enable) -> dict:
    call = 'cv_algorithm'
    # build message
    msg = {'fcn': call, 'id': self._app_id, 'algorithm': algorithm, 'enable': enable}
    # send and receive message
    answer = self._socket.send_and_receive(msg)
    # handle nack
    if not dss.auxiliaries.zmq_lib.is_ack(answer, call):
      raise dss.auxiliaries.exception.Nack(dss.auxiliaries.zmq_lib.get_nack_reason(answer), fcn=call)
    # return
    return answer

  def get_idle(self) -> bool:
    call = 'get_idle'
    # build message
    msg = {'fcn': call, 'id': self._app_id}
    # send and receive message
    answer = self._socket.send_and_receive(msg)
    # handle nack
    if not dss.auxiliaries.zmq_lib.is_ack(answer, call):
      raise dss.auxiliaries.exception.Nack(dss.auxiliaries.zmq_lib.get_nack_reason(answer), fcn=call)
    # return
    return answer['idle']

  def get_state(self) -> dict:
    call = 'get_state'
    # build message
    msg = {'fcn': call, 'id': self._app_id}
    # send and receive message
    answer = self._socket.send_and_receive(msg)
    # handle nack
    if not dss.auxiliaries.zmq_lib.is_ack(answer, call):
      raise dss.auxiliaries.exception.Nack(dss.auxiliaries.zmq_lib.get_nack_reason(answer), fcn=call)
    # return
    return answer


  def set_init_point(self, heading_ref) -> None:
    call = 'set_init_point'
    # build message
    msg = {'fcn': call, 'id': self._app_id}
    msg['heading_ref'] = heading_ref
    # send and receive message
    answer = self._socket.send_and_receive(msg)
    # handle nack
    if not dss.auxiliaries.zmq_lib.is_ack(answer, call):
      raise dss.auxiliaries.exception.Nack(dss.auxiliaries.zmq_lib.get_nack_reason(answer), fcn=call)
    # return
    return


  def set_gimbal(self, roll, pitch, yaw) -> None:
    call = 'set_gimbal'
    # build message
    msg = {'fcn': call, 'id': self._app_id}
    msg['roll'] = roll
    msg['pitch'] = pitch
    msg['yaw'] = yaw
    # send and receive message
    answer = self._socket.send_and_receive(msg)
    # handle nack
    if not dss.auxiliaries.zmq_lib.is_ack(answer, call):
      raise dss.auxiliaries.exception.Nack(dss.auxiliaries.zmq_lib.get_nack_reason(answer), fcn=call)
    # return
    return

  def photo(self, cmd, resolution='low', index='latest', enable=False, period=10, publish="low") -> None:
    call = 'photo'
    # build message
    msg = {'fcn': call, 'id': self._app_id}
    msg['cmd'] = cmd
    # Download and continous photo have more args
    if cmd == 'download':
      msg['resolution'] = resolution
      msg['index'] = index
    elif cmd == 'continous_photo':
      msg['enable'] = enable
      msg['publish'] = publish
      msg['period'] = period
    elif cmd == 'record':
      msg['enable'] = enable
    # send and receive message
    answer = self._socket.send_and_receive(msg)
    # handle nack
    if not dss.auxiliaries.zmq_lib.is_ack(answer, call):
      raise dss.auxiliaries.exception.Nack(dss.auxiliaries.zmq_lib.get_nack_reason(answer), fcn=call)
    # return
    return


  def get_metadata(self, ref, index) -> dict:
    call = 'get_metadata'
    # build message
    msg = {'fcn': call, 'id': self._app_id}
    msg['ref'] = ref
    msg['index'] = index
    # send and receive message
    answer = self._socket.send_and_receive(msg)
    # handle nack
    if not dss.auxiliaries.zmq_lib.is_ack(answer, call):
      raise dss.auxiliaries.exception.Nack(dss.auxiliaries.zmq_lib.get_nack_reason(answer), fcn=call)
    # return
    return answer['metadata']


  def disconnect(self) -> None:
    call = 'disconnect'
    # build message
    msg = {'fcn': call, 'id': self._app_id}
    # send and receive message
    answer = self._socket.send_and_receive(msg)
    # handle nack
    if not dss.auxiliaries.zmq_lib.is_ack(answer, call):
      raise dss.auxiliaries.exception.Nack(dss.auxiliaries.zmq_lib.get_nack_reason(answer), fcn=call)
    # return
    return

  def data_stream(self, stream: str, enable: bool) -> None:
    call = 'data_stream'
    # build message
    msg = {'fcn': call, 'id': self._app_id}
    msg['stream'] = stream
    msg['enable'] = enable
    # send and receive message
    answer = self._socket.send_and_receive(msg)
    # handle nack
    if not dss.auxiliaries.zmq_lib.is_ack(answer, call):
      raise dss.auxiliaries.exception.Nack(dss.auxiliaries.zmq_lib.get_nack_reason(answer), fcn=call)
    # return
    return
