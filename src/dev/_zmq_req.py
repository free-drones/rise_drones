#!/usr/bin/env python3
'''Minimal running example of a ZMQ REQ socket.

> ./_zmq_req.py & ./_zmq_rep.py
'''
import argparse
import json

import zmq

import dss.auxiliaries
from dss.auxiliaries.config import config


def _print(text):
  print(__file__ + ': ' + str(text))

def _main():
  # parse command-line arguments
  parser = argparse.ArgumentParser(description='_zmq_req.py', allow_abbrev=False)
  parser.add_argument('--ip', default='127.0.0.1', help='ip to send req to')
  parser.add_argument('--port', default=config["CRM"]["default_crm_port"], help=f'{config["CRM"]["default_crm_port"]}')
  parser.add_argument('--id', default=config["CRM"]["default_id"], help=config["CRM"]["default_id"])
  args = parser.parse_args()

  socket = dss.auxiliaries.zmq.Req(zmq.Context(), args.ip, args.port)
  _print('Local IP: ' + dss.auxiliaries.zmq.get_ip_address())

  msg = {'id':args.id, 'fcn': 'clients'}
  _print('Sending message: \n' + json.dumps(msg, indent = 4))
  _print('Sending to ' + args.ip + ':' + str(args.port))

  try:
    answer = socket.send_and_receive(msg)
    _print("Recceived massage: \n" + json.dumps(answer, indent = 4))
  except dss.auxiliaries.exception.Nack as error:
    _print(f'Nacked when sending {error.fcn}, received error: {error.msg}')
  except dss.auxiliaries.exception.NoAnswer as error:
    _print(f'NoAnswer when sending: {error.fcn} to {error.ip}:{error.port}')
    _print('Double check receiving end and ip+port')

  socket.close()
  socket = None


if __name__ == "__main__":
  _main()
