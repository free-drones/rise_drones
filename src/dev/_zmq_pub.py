#!/usr/bin/env python3
'''Minimal running example of a ZMQ PUB socket.
'''

import time
import argparse
import zmq

import dss.auxiliaries


def _print(text):
  print(__file__ + ': ' + str(text))

def _main():
  # parse command-line arguments
  parser = argparse.ArgumentParser(description='_zmq_rep.py', allow_abbrev=False, add_help=False)
  parser.add_argument('-h', '--help', action='help', help=argparse.SUPPRESS)
  parser.add_argument('--port', default=5559, help='port to publish on')
  args = parser.parse_args()

  context = zmq.Context()
  socket = dss.auxiliaries.zmq.Pub(context, ip='*', port=args.port, timeout=1000)
  _print('Local IP:' + dss.auxiliaries.zmq.get_ip_address())
  _print('Publishing messages to all ip (*) at port :' + str(args.port))
  _print('Every second mess with topic \'test_topic\', everysecond with topic \'speed\'')


  while socket:
    try:
      msg1 = {'key': 'value'}
      msg2 = {'speed': 2}
      topic1 = 'test_topic'
      topic2 = 'speed'
      socket.publish(topic=topic1,msg=msg1)
      _print('Published topic and message: ' + dss.auxiliaries.zmq.mogrify(topic1, msg1))
      time.sleep(1)
      socket.publish(topic=topic2,msg=msg2)
      _print('Published topic and message: ' + dss.auxiliaries.zmq.mogrify(topic2, msg2))
      time.sleep(1)
    except KeyboardInterrupt:
      socket.close()
      socket = None

if __name__ == "__main__":
  _main()
