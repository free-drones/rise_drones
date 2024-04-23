#!/usr/bin/env python3
'''This runs the sensor server.'''


import argparse
import logging
import time
import traceback
import sys
import os

sys.path.insert(0,os.path.join(os.path.dirname(__file__), '..'))

import dss.auxiliaries
import sen.server.sen


__author__ = 'Andreas Gising <andreas.gising@ri.se>, Kristoffer Bergman <kristoffer.bergman@ri.se>, Hanna Müller <hanna.muller@ri.se>, Joel Nordahl'
__version__ = '1.2.0'
__copyright__ = 'Copyright (c) 2019-2023, RISE'
__status__ = 'development'

def _main():
  # parse command-line arguments
  parser = argparse.ArgumentParser(description='SEN Server', allow_abbrev=False, add_help=False)
  parser.add_argument('-h', '--help', action='help', help=argparse.SUPPRESS)
  parser.add_argument('--crm', type=str, help='<ip>:<port> of crm', required=True)
  parser.add_argument('--capabilities', type=str, default=None, nargs='*', required=False)
  parser.add_argument('--sen_ip', type=str,help='ip of the crm_sen', required = True)
  #parser.add_argument('--owner', type=str, help='id of the connected TYRAmote instance', required=True)
  parser.add_argument('--sen_id', type=str, default='', help='id of the sen instance', required=False)
  parser.add_argument('--descr', type=str, default='crm_sen', help='description for register command', required=False)
  parser.add_argument('--log', type=str, default='debug', help='logging threshold', required=False)
  parser.add_argument('--stdout', action='store_true', help='enables logging to stdout', required=False)
  parser.add_argument('--virgin', action='store_true', help='defines if to start from a backup or not', required=False)
  parser.set_defaults(feature=True)

  args = parser.parse_args()

  # Find correct subnet
  sen_ip = args.sen_ip
  subnet = dss.auxiliaries.zmq_lib.get_subnet(ip=sen_ip)
  dss.auxiliaries.logging.configure(f'crm_sen.log', stdout=args.stdout, rotating=True, loglevel=args.log, subdir=subnet)

  # start sen
  try:
    server = sen.server.sen.Server(sen_ip=args.sen_ip, sen_id=args.sen_id, crm=args.crm, capabilities=args.capabilities, description=args.descr, die_gracefully=True, camera='picam')
  except dss.auxiliaries.exception.Error as error:
    logging.critical(str(error))
    sys.exit()
  except:
    logging.critical(traceback.format_exc())
    sys.exit()

  # run sen
  try:
    while server.alive:
      time.sleep(3.0)
  except KeyboardInterrupt:
    logging.warning('Shutdown due to keyboard interrupt')
    server.alive = False
  #Let the process die gracefully
  time.sleep(2.0)

if __name__ == '__main__':
  _main()
