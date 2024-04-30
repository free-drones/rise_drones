'''
USSP CLIENT *API*

This class handles the communication with the USSP, according to the API described in
the repository https://github.com/RISE-drones/ussp-api
'''

import logging

import dss.auxiliaries

__author__ = 'Lennart Ochel <>, Andreas Gising <andreas.gising@ri.se>, Kristoffer Bergman <kristoffer.bergman@ri.se>, Hanna Müller <hanna.muller@ri.se>'
__version__ = '1.0.0'
__copyright__ = 'Copyright (c) 2021, RISE'
__status__ = 'development'

class UsspClientApi:
  def __init__(self, context, app_id, ussp_ip, req_port, pub_port, sub_port, timeout=1000):
    self._logger = logging.getLogger(__name__)
    self._logger.info('USSP Client API')

    self._context = context

    self._req_socket = dss.auxiliaries.zmq_lib.Req(context, ussp_ip, req_port, label="USSP-API-REQ", timeout=timeout, self_id=app_id)
    self._pub_socket = dss.auxiliaries.zmq_lib.Pub(context, ussp_ip, pub_port, label="USSP-API-PUB", self_id=app_id, bind=False)
    self._sub_socket = dss.auxiliaries.zmq_lib.Sub(context, ussp_ip, sub_port, timeout=int(1e8), label="USSP-API-SUB", self_id=app_id, subscribe_all=False)

  def __del__(self):
    self._req_socket.close()
    self._pub_socket.close()
    self._sub_socket.close()

  def subscribe_to_topic(self, topic):
    self._sub_socket.subscribe(topic)

  def receive_subscribe_data(self):
    topic, msg = self._sub_socket.recv()
    return topic, msg

  def query_ground_height(self, lat, lon, epsg=4979):
    call = 'query ground height'
    # build message
    msg = {'request': call, 'EPSG': epsg, 'at': [lon, lat]}
    # send and receive message
    answer = self._req_socket.send_and_receive_string(msg)
    return answer

  def request_plan(self, msg):
    call = 'request plan'
    msg['request'] = call
    answer = self._req_socket.send_and_receive_string(msg)
    return answer

  def get_plan(self, plan_id):
    call = 'get plan'
    # build message
    msg = {'request': call, 'plan ID': plan_id}
    # send and receive message
    answer = self._req_socket.send_and_receive_string(msg)
    return answer

  def accept_plan(self, plan_id):
    call = 'accept plan'
    # build message
    msg = {'request': call, 'plan ID': plan_id}
    # send and receive message
    answer = self._req_socket.send_and_receive_string(msg)
    return answer

  def activate_plan(self, plan_id, time_until_withdrawn):
    call = 'activate plan'
    # build message
    msg = {'request': call, 'plan ID': plan_id}
    #Debug parameter used to trigger a plan withdrawn msg from the USSP
    if time_until_withdrawn :
      msg["withdraw plan"] = time_until_withdrawn
    # send and receive message
    answer = self._req_socket.send_and_receive_string(msg)
    return answer

  def cancel_plan(self, plan_id):
    call = 'cancel plan'
    # build message
    msg = {'request': call, 'plan ID': plan_id}
    # send and receive message
    answer = self._req_socket.send_and_receive_string(msg)
    return answer

  def end_plan(self, plan_id):
    call = 'end plan'
    # build message
    msg = {'request': call, 'plan ID': plan_id}
    # send and receive message
    answer = self._req_socket.send_and_receive_string(msg)
    return answer

  def publish_nrid(self, msg):
    topic = 'nrid'
    self._pub_socket.publish(topic, msg)
