#!/usr/bin/env python3
'''Minimal running example of a ZMQ REP socket.

> ./_zmq_req.py & ./_zmq_rep.py
'''

import argparse
import json

import sys
import os
sys.path.insert(0,os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0,os.path.join(os.path.dirname(__file__), '../..'))

import dss.auxiliaries
from dss.auxiliaries.config import config



def _print(text):
  print(__file__ + ': ' + str(text))

def receive_and_reply(socket):
  '''receives a json message and replies with the same message'''
  try:
    msg = socket.recv_json()
  except dss.auxiliaries.exception.Again as error:
    _print(f'{error.fcn} - from socket connected to {error.ip}:{error.port}')
    return

  # answer = msg
  request = json.loads(msg)
  answer = json.dumps(request)

  try:
    socket.send_json(answer)
  except dss.auxiliaries.exception.ZMQError as error:
    _print(f'{error.fcn} - from socket connected to {error.ip}:{error.port}')
  else:
    _print('Replying with:\n' + json.dumps(request, indent = 4))

def _main():
  # parse command-line arguments
  parser = argparse.ArgumentParser(description='_zmq_rep.py', allow_abbrev=False)
  parser.add_argument('--port', default=config["CRM"]["default_crm_port"], help=f'{config["CRM"]["default_crm_port"]}')
  args = parser.parse_args()

  context = dss.auxiliaries.zmq.Context()
  socket = dss.auxiliaries.zmq.Rep(context, port=args.port)
  _print('Local IP:' + dss.auxiliaries.zmq.get_ip_address())
  _print('Listening for incoming messages on port: ' + str(args.port))

  while socket:
    try:
      receive_and_reply(socket)
    except KeyboardInterrupt:
      socket.close()
      socket = None

if __name__ == "__main__":
  _main()
