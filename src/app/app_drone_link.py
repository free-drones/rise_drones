# #!/usr/bin/env python3

# '''
# APP "app_drone_link"
# This app connects to CRM and receives an app_id.
# '''

# import json
# import logging
# import threading
# import time
# import numpy as np
# import zmq
# import sys
# import traceback
# import argparse
# import queue

# import dss.auxiliaries
# from dss.auxiliaries.config import config
# import dss.client

# #--------------------------------------------------------------------#

# __author__ = 'PUM01 <TDDD96_2023_01@groups.liu.se>'
# __version__ = '0.1.0'
# __copyright__ = 'Copyright (c) 2022, RISE'
# __status__ = 'development'

# #--------------------------------------------------------------------#

# _logger = logging.getLogger('app_drone_link')
# _context = zmq.Context()
# IP = dss.auxiliaries.zmq.get_ip()
# alive_event = threading.Event()
# update_queue = queue.Queue()

# #--------------------------------------------------------------------#

# class Waypoint():
#   '''Class used to store position data'''
#   def __init__(self):
#     self.lat = 0.0
#     self.lon = 0.0
#     self.alt = 0.0

#   def set_lla(self, lat, lon, alt):
#     self.lat = lat
#     self.lon = lon
#     self.alt = alt

#   def copy_lla(self, other_wp):
#     self.lat = other_wp.lat
#     self.lon = other_wp.lon
#     self.alt = other_wp.alt

# def ne_to_ll(loc1, d_northing, d_easting):
#   d_lat = d_northing/(1852*60)
#   d_lon = d_easting/(1852*60*np.cos(loc1.lat/180*np.pi))
#   return (d_lat, d_lon)
# def get_3d_distance(loc1, loc2):
#   dlat = loc2.lat - loc1.lat
#   dlon = loc2.lon - loc1.lon
#   dalt = loc2.alt - loc1.alt

#   # Convert to meters
#   d_northing = dlat * 1852 * 60
#   d_easting = dlon *1852 * 60 * np.cos(loc1.lat/180*np.pi)

#   # Calc distances
#   d_2d = np.sqrt(d_northing**2 + d_easting**2)
#   d_3d = np.sqrt(d_northing**2 + d_easting**2 + dalt**2)

#   # Calc bearing
#   bearing = np.arctan2(d_easting, d_northing)
#   return (d_northing, d_easting, dalt, d_2d, d_3d, bearing)

# class Link():
#     '''This class is used to connect to drones and send missions to them'''
#     def __init__(self):
#         self.drone_dict = {}
#         self.update_queue = update_queue
#         self.drone_id_counter = 0


#         # CRM ip and port
#         self.crm_info = str(config['CRM']['default_crm_ip']) + ":" + str(config['CRM']['default_crm_port'])
#         self.crm = dss.client.CRM(_context, self.crm_info, app_name="app_drone_link", desc='single drone connection', app_id="")
#         self.alive=True
#         self.ip = IP

#         # The application sockets
#         # Use ports depending on subnet used to pass RISE firewall
#         # Rep: ANY -> APP
#         self._app_socket = dss.auxiliaries.zmq.Rep(_context,self.ip, label='link', port=config["app_drone_link"]["default_port_reply"])
#         _ = self.crm.register(self.ip, self._app_socket.port)
#         # Pub socket APP -> ANY
#         self._pub_socket = dss.auxiliaries.zmq.Pub(_context, self.ip, label='link_pub', port=config["app_drone_link"]["default_port_pub"])
#         # Info socket, request info from crm via monitor
#         self._info_socket = dss.auxiliaries.zmq.Req(_context, self.ip, label='req for monitor', port=config["app_drone_link"]["default_port_info"])

#         self._commands = {'connect_to_drone':       {'request': self._request_connect_to_drone},
#                           'get_list_of_drones':     {'request': self._request_get_list_of_drones},
#                           'fly':                    {'request': self._request_fly},
#                           'fly_random_mission':     {'request': self._request_fly_random_mission},
#                           'get_drone_status':       {'request': self._request_get_drone_status},
#                           'get_drone_waypoint':     {'request': self._request_get_drone_waypoint},
#                           'return_to_home':         {'request': self._request_return_to_home},
#                           'get_drone_position':     {'request': self._request_get_drone_position},
#                           'connect_to_all_drones':  {'request': self._request_connect_to_all_drones},
#                           'reset':                  {'request': self._request_reset}}

#         self.main_reply_thread = threading.Thread(target=self._main_rep, daemon = True)
#         self.main_reply_thread.start()

#         self.main_pub_thread = threading.Thread(target=self._main_pub, daemon = True)
#         self.main_pub_thread.start()

#         self.main_info_thread = threading.Thread(target=self._main_req, daemon=True)
#         self.main_info_thread.start()


#     def _main_rep(self):
#       '''Listens for requests from ANY, tries to carry out said requests and replies'''
#       print("i am listening on ip: " ,self._app_socket.ip ," and port: ", self._app_socket.port)
#       _logger.info('Reply socket for link is listening on port: %d', self._app_socket.port)
#       while alive_event.is_set():
#         try:
#           msg = self._app_socket.recv_json()
#           #print(f"received messege: {msg}")
#           _logger.info(f"received messege: {msg}")
#           msg = json.loads(msg)
#           fcn = msg['fcn'] if 'fcn' in msg else ''
#           if fcn in self._commands:
#             request = self._commands[fcn]['request']
#             answer = request(msg)
#             #print(f"answer is : {answer}")
#           else:
#             answer = dss.auxiliaries.zmq.nack(msg['fcn'], 'Request not supported')
#           answer = json.dumps(answer)
#           _logger.info(f"Sending answer: {answer}")
#           #print("sending msg back")
#           self._app_socket.send_json(answer)
#         except zmq.Again:
#           continue
#         except KeyboardInterrupt:
#             _logger.warning('Shutdown due to keyboard interrupt')
#             break
#         except:
#           pass
#       _logger.info("Reply socket closed, thread exit")
#       self._app_socket.close()


#     def _main_pub(self):
#       '''Publishes status messeges for the connected drones to any who are listening'''
#       print("i am publishing on ip: " ,self._pub_socket.ip ," and port: ", self._pub_socket.port)
#       while alive_event.is_set():
#         try:
#           update = self.update_queue.get(timeout=1)
#           #print(f"got update: {update}")
#           _logger.info(f'received update from queue: {update}')
#           topic, msg = update[0], update [1]
#           #print(f"topic: {topic}, msg: {msg}")
#           _logger.info(f'decoded update for msg: {msg}, topic: {topic}')
#           self._pub_socket.publish(topic, msg)
#         except queue.Empty:
#           continue
#         except KeyboardInterrupt:
#             _logger.warning('Shutdown due to keyboard interrupt')
#             break
#         except:
#           pass
#       _logger.info("Publish socket closed, thread exit")
#       self._pub_socket.close()


#     def _main_req(self):
#       '''Requesting updates on information from the crm'''
#       print('i am requesting msgs on ip: ', self._info_socket.ip, 'and port: ', self._info_socket.port)
#       while alive_event.is_set():
#         try:
#           answer = self.crm.clients('dss')
#           #answer = self._info_socket.send_and_receive({'fcn': 'get_client_list'})
#           client_list = answer['clients']
#           info_dict = self.compare_client_list(client_list)
#           number_gained, lost_drones = info_dict['gained'], info_dict['lost']
#           if number_gained != 0:
#             self.queue_update('gained_drones', {'drones': number_gained})
#           if lost_drones:
#             self.kill_lost_drones(lost_drones)
#             for drone in lost_drones:
#               self.queue_update('lost_drone', {'drone': drone})
#           time.sleep(5)
#         except KeyboardInterrupt:
#           _logger.warning('Shutdown due to keyboard interrupt')
#           break
#         except Exception as e:
#           pass
#       _logger.info("Info socket closed, thread exit")
#       self._info_socket.close()
#          # _logger.warning(f'exception occured in monitor req: {e}')


#     #--------------------------------------------------------------------#
#     # Request handlers

#     def _request_connect_to_all_drones(self, msg):
#       '''Handles connect_to_all_drones request, 
#         sends the number of drones that were connected to as a reply.'''
#       connected_drones = []
#       while True:
#         connected = self.connect_to_drone()
#         if connected:
#           lost_drone = None
#           for drone in self.drone_dict:
#             if not self.drone_dict[drone]:
#               lost_drone = drone
#               break
#           if not lost_drone:
#             connected_drones.append(f'drone{len(self.drone_dict)}')
#         else:
#           break
#       if len(connected_drones) != 0:
#         reply = {'status': 'success',
#             'fcn': 'connect_to_all_drones',
#             'message': f'{len(self.drone_dict)}',
#             'drone_names': f'{connected_drones}'}
#       elif len(self.drone_dict) != 0:
#         reply = {'status': 'denied',
#                 'fcn': 'connect_to_all_drones',
#                 'message': 'Failed to connect to any additional drones'}
#       else:
#         reply = {'status': 'error',
#               'fcn': 'connect_to_all_drones',
#               'message': 'Failed to connect to any drones'}
#       return reply


#     def _request_get_list_of_drones(self, msg):
#       '''Handles get_list_of_drones request, 
#         sends the list of drones as a reply.'''
#       # Call the get_list_of_drones function
#       list_of_drones = self.get_list_of_drones()

#       # Construct the reply
#       reply = {'status': 'success',
#               'fcn': 'get_list_of_drones',
#               'drone_list': list(list_of_drones)} # Convert the keys view object to a list
#       return reply


#     def _request_fly(self, msg):
#       '''Handles the fly request, 
#         starts a new thread that flies the specified mission with the specified drone.'''
#       # Extract the required information from the msg
#       mission = msg['mission']
#       drone_name = msg['drone_name']

#       if mission is None or drone_name is None:
#           reply = {'status': 'error',
#                   'fcn': 'fly',
#                   'message': 'Missing required information (mission or drone_name)'}
#           return reply

#       try:
#           self.fly(mission, drone_name)
#           reply = {'status': 'success',
#                   'fcn': 'fly',
#                   'message': f'Mission started for drone {drone_name}'}
#       except KeyError:
#           reply = {'status': 'error',
#                   'fcn': 'fly',
#                   'message': 'Invalid drone name'}
#       except Exception as e:
#           reply = {'status': 'error',
#                   'fcn': 'fly',
#                   'message': 'something went wrong',
#                   'exception': str(e)}
#       return reply


#     def _request_fly_random_mission(self, msg):
#       '''Handles the fly_random_mission request,
#          starts a new thread that flies the specified mission with the specified drone.'''
#       # Extract the required information from the msg
#       drone_name = msg['drone_name']
#       n_wps = msg['n_wps']

#       if  drone_name is None:
#           reply = {'status': 'error',
#                   'fcn': 'fly_random_mission',
#                   'message': 'Missing required information drone_name'}
#           return reply

#       try:
#           self.fly_random_mission(drone_name, n_wps)
#           reply = {'status': 'success',
#                   'fcn': 'fly_random_mission',
#                   'message': f'Random mission started for drone {drone_name}'}
#       except KeyError:
#           reply = {'status': 'error',
#                   'fcn': 'fly_random_mission',
#                   'message': 'Invalid drone name'}
#       except Exception as e:
#           reply = {'status': 'error',
#                   'fcn': 'get_valid_drone_name',
#                   'message': 'fly_random_mission',
#                   'exception': str(e)}
#       return reply


#     def _request_get_drone_status(self, msg):
#       '''Handles the get_drone_status request,
#          returns the mission status of the specified drone.'''
#       # Extract the required information from the msg
#       drone_name = msg.get('drone_name')

#       if drone_name is None:
#           reply = {'status': 'error',
#               'fcn': 'get_drone_status',
#               'message': 'Missing required information (drone_name)'}
#           return reply
#       try:
#           mission_status = self.get_drone_status(drone_name)
#           reply = {'status': 'success',
#               'fcn': 'get_drone_status',
#               'drone_name': drone_name,
#               'mission_status': mission_status}
#       except KeyError:
#           reply = {'status': 'error',
#               'fcn': 'get_drone_status',
#               'message': 'Invalid drone name'}
#       except Exception as e:
#           reply = {'status': 'error',
#                   'fcn': 'get_drone_status',
#                   'message': 'something went wrong',
#                   'exception': str(e)}
#       return reply


#     def _request_connect_to_drone(self, msg):
#       '''Handles the connect_to_drone request and creates a new drone object, 
#         adding it to the drone dictionary.'''
#       drone_name = None
#       for drone in self.drone_dict:
#         if not self.drone_dict[drone]:
#           drone_name = drone
#           break
#       if not drone_name:
#           drone_name = 'drone' + str(len(self.drone_dict))
#       connected = self.connect_to_drone()
#       if connected:
#           reply = {'status': 'success',
#               'fcn': 'connect_to_drone',
#               'message': 'Drone connected successfully',
#               'drone_name': drone_name}
#       elif len(self.drone_dict) != 0:
#         reply = {'status': 'denied',
#                 'fcn': 'connect_to_drone',
#                 'message': 'Failed to connect to another drone'}
#       else:
#           reply = {'status': 'error',
#               'fcn': 'connect_to_drone',
#               'message': 'Failed to connect to drone'}
#       return reply


#     def _request_get_drone_waypoint(self, msg):
#       '''Handles the get_drone_waypoint request, 
#         returns the current waypoint of the specified drone.'''
#       # Extract the required information from the msg
#       drone_name = msg.get('drone_name')

#       if drone_name is None:
#           reply = {'status': 'error',
#                   'fcn': 'get_drone_waypoint',
#                   'message': 'Missing required information (drone_name)'}
#           return reply

#       try:
#           waypoint = self.get_drone_waypoint(drone_name)
#           reply = {'status': 'success',
#                   'fcn': 'get_drone_waypoint',
#                   'drone_name': drone_name,
#                   'drone_waypoint': waypoint}
#       except KeyError:
#           reply = {'status': 'error',
#                   'fcn': 'get_drone_waypoint',
#                   'message': 'Invalid drone name'}
#       except Exception as e:
#           reply = {'status': 'error',
#                   'fcn': 'get_drone_waypoint',
#                   'message': 'something went wrong',
#                   'exception': str(e)}
#       return reply


#     def _request_return_to_home(self, msg):
#       '''Handles the return_to_home request, 
#         returns the specified drone to its launch location.'''
#       # Extract the required information from the msg
#       drone_name = msg.get('drone_name')

#       if drone_name is None:
#           reply = {'status': 'error',
#                   'fcn': 'return_to_home',
#                   'message': 'Missing required information (drone_name)'}
#           return reply

#       try:
#           self.return_to_home(drone_name)
#           reply = {'status': 'success',
#                   'fcn': 'return_to_home',
#                   'message': f'Drone {drone_name} returning to home'}
#       except KeyError:
#           reply = {'status': 'error',
#               'fcn': 'return_to_home',
#               'message': 'Invalid drone name'}
#       except Exception as e:
#           reply = {'status': 'error',
#                   'fcn': 'return_to_home',
#                   'message': 'something went wrong',
#                   'exception': str(e)}
#       return reply


#     def _request_get_drone_position(self, msg):
#       '''Handles the get_drone_position request,
#         returns the current state of the specified drone.'''
#       # Extract the required information from the msg
#       drone_name = msg.get('drone_name')

#       if drone_name is None:
#           reply = {'status': 'error',
#                   'fcn': 'get_drone_position',
#                   'message': 'Missing required information (drone_name)'}
#           return reply

#       try:
#           drone_position = self.get_drone_position(drone_name)
#           reply = {'status': 'success',
#                   'fcn': 'get_drone_position',
#                   'drone_name': drone_name,
#                   'drone_position': drone_position}
#       except KeyError:
#           reply = {'status': 'error',
#                   'fcn': 'get_drone_position',
#                   'message': 'Invalid drone name'}
#       except Exception as e:
#           reply = {'status': 'error',
#                   'fcn': 'get_drone_position',
#                   'message': 'something went wrong',
#                   'exception': str(e)}
#       return reply


#     def _request_get_drone_battery(self, msg):
#       '''Handles the get_drone_battery request,
#         returns the current level of charge for the battery'''
#       drone_name = msg.get('drone_name')

#       if drone_name is None:
#           reply = {'status': 'error',
#                   'fcn': 'get_drone_battery',
#                   'message': 'Missing required information (drone_name)'}
#           return reply
#       try:
#           drone_battery = self.get_drone_battery(drone_name)
#           reply = {'status': 'success',
#                   'fcn': 'get_drone_battery',
#                   'drone_name': drone_name,
#                   'battery': drone_battery}
#       except KeyError:
#           reply = {'status': 'error',
#                   'fcn': 'get_drone_battery',
#                   'message': 'Invalid drone name'}
#       except Exception as e:
#           reply = {'status': 'error',
#                   'fcn': 'get_drone_battery',
#                   'message': 'something went wrong',
#                   'exception': str(e)}
#       return reply


#     def _request_get_valid_drone_name(self, msg):
#       '''Handles the get_valid_drone_name request,
#         returns if the drone name is valid'''
#       drone_name = msg.get('drone_name')

#       if drone_name is None:
#           reply = {'status': 'error',
#                   'fcn': 'get_valid_drone_name',
#                   'message': 'Missing required information (drone_name)'}
#           return reply
#       try:
#           validity = self.valid_drone_name(drone_name)
#           reply = {'status': 'success',
#                   'fcn': 'get_valid_drone_name',
#                   'drone_name': drone_name,
#                   'valid': validity}
#       except Exception as e:
#           reply = {'status': 'error',
#                   'fcn': 'get_valid_drone_name',
#                   'message': 'something went wrong',
#                   'exception': str(e)}
#       return reply


#     def _request_reset(self, msg):
#       '''Handles the reset request,
#         disconnects all drones and returns true or false'''
#       try:
#         if self.reset():
#           reply = {'status': 'success',
#                   'fcn': 'reset',
#                   'message': 'link application reset'}
#         else:
#           reply = {'status': 'error',
#                   'fcn': 'reset',
#                   'message': 'something went wrong, reset encountered an exception check drone app logs'}
#       except Exception as e:
#         reply = {'status': 'error',
#                   'fcn': 'reset',
#                   'message': f"reset encountered an exception: {e}"}


#     #--------------------------------------------------------------------#
#     # Public functions

#     def connect_to_drone(self):
#       '''Creates a new drone object and adds it to the drone dictionary'''
#       drone_name = 'drone' + str(self.drone_id_counter + 1)
#       new_drone = Drone(self.ip, drone_name, self.crm_info)
#       if new_drone.drone_connected:
#           self.drone_id_counter += 1
#           self.drone_dict[drone_name] = new_drone
#           return True
#       else:
#           # Kill any threads that were created
#           new_drone.kill()
#           return False


#     def get_list_of_drones(self):
#         '''Returns a list of all drones'''
#         return self.drone_dict.keys()


#     def kill(self):
#         '''Kills all drones and clears the drone dictionary'''
#         _logger.info("Closing app")
#         try:
#           if not self.drone_dict == {}:
#               for drone in self.drone_dict.values():
#                   drone.kill()
#           self.drone_dict = {}
#           alive_event.clear()
#           time.sleep(1)
#           _logger.info("Closing app")
#           return True
#         except Exception as e:
#           _logger.error(f"Tried to kill but didn't work: {e}")
#           return False


#     def reset(self):
#       '''Disconnects from all drones'''
#       try:
#         if not self.drone_dict == {}:
#               for drone in self.drone_dict.values():
#                 drone.kill()
#               self.drone_dict = {}
#               _logger.info("Disconnected drones and reset app")
#               return True
#       except Exception as e:
#         _logger.error(f"Tried to disconnect drones but failed due to: {e}")
#         return False


#     def fly(self, mission, drone_name):
#         '''Starts a new thread that flies the specified mission with the specified drone'''
#         if not self.valid_drone_name(drone_name):
#             raise KeyError('Invalid drone name')
#         if self.drone_dict[drone_name].valid_mission(mission):
#             fly_thread = threading.Thread(target=self.drone_dict[drone_name].fly_mission(mission), daemon=True)
#             fly_thread.start()
#         else:
#             raise Exception('Mission denied: invalid mission')


#     def fly_random_mission(self, drone_name, n_wps = 10):
#         '''Starts a new thread that flies a random mission with the specified drone'''
#         if not self.valid_drone_name(drone_name):
#             raise KeyError('Invalid drone name')
#         fly_thread = threading.Thread(target=self.drone_dict[drone_name].execute_random_mission(n_wps), daemon=True)
#         fly_thread.start()


#     def get_drone_status(self, drone_name):
#         '''Returns the status of the mission, 'flying' = mission is in progress, 
#         'waiting' = flying and waiting for a new mission, 'idle' = not flying and idle, 
#         'landed' = on the ground, 'denied' = mission was denied'''
#         if not self.valid_drone_name(drone_name):
#             raise KeyError('Invalid drone name')
#         with self.drone_dict[drone_name].mission_status_lock:
#             return self.drone_dict[drone_name].mission_status


#     def return_to_home(self, drone_name):
#         '''Returns the drone to its launch location'''
#         if not self.valid_drone_name(drone_name):
#             raise KeyError('Invalid drone name')
#         with self.drone_dict[drone_name].mission_status_lock:
#             self.drone_dict[drone_name].mission_status = 'flying'
#         home_thread = threading.Thread(self.drone_dict[drone_name].return_to_home(), daemon=True)
#         home_thread.start()


#     def get_drone_position(self, drone_name):
#         '''Returns the current state of the drone in the form of a dictionary 
#           {Lat: Decimal degrees , Lon: Decimal degrees , 
#            Alt: AMSL , Heading: degrees relative true north}'''
#         if not self.valid_drone_name(drone_name):
#             raise KeyError('Invalid drone name')
#         return self.drone_dict[drone_name].get_drone_state()


#     def get_drone_waypoint(self, drone_name):
#         '''Returns the current waypoint of the drone, 
#           {"lat" : lat , "lon": lon , "alt": new_alt, "alt_type": "amsl", 
#           "heading": degrees relative true north,  "speed": speed}'''
#         if not self.valid_drone_name(drone_name):
#             raise KeyError('Invalid drone name')
#         return self.drone_dict[drone_name].get_current_waypoint()


#     def get_drone_battery(self, drone_name):
#       if not self.valid_drone_name(drone_name):
#         raise KeyError('invalid drone name')
#       return self.drone_dict[drone_name].battery_level


#     def valid_drone_name(self, drone_name):
#         '''Returns true if the drone name is valid'''
#         if drone_name in self.drone_dict:
#             return True
#         else:
#             return False


#     def queue_update(self, string, data_dict):
#       '''Takes a string and a dictionary and puts them in the queue to publish'''
#       topic = str(string)
#       self.update_queue.put((topic, data_dict))


#     def compare_client_list(self, client_list):
#       '''Compares the list of registered drones with the application
#          to the list of current clients given by app_monitor'''
#       try:
#         dss_clients = len(client_list)
#         lost_drones = []
#         gained_drones = []
#         dss_list = []
#         for drone in self.drone_dict:
#           if (self.drone_dict[drone].drone != None) and (self.drone_dict[drone].drone._dss != None):
#             dss = self.drone_dict[drone].drone._dss.dss_id
#             dss_list.append(dss)
#             if dss not in client_list:
#               lost_drones.append(drone)
#           else:
#             lost_drones.append(drone)
#         for client in client_list:
#           if client not in dss_list and client['owner'] == 'crm':
#             gained_drones.append(client)
#         return {'gained': len(gained_drones), 'lost': lost_drones}
#       except Exception as e:
#         _logger.warning(f'exception occurred in compare_client_list: {e}')
#       return None, None


#     def kill_lost_drones(self, drones):
#       '''Handles the removal of drone objects that have lost connection'''
#       for drone in drones:
#         try:
#           self.drone_dict[drone].kill()
#         except Exception as e:
#           _logger.warning(f'tried to kill the lost drone but didnt work IN KILL_LOST: {e}')
#         try:
#           self.drone_dict.pop(drone)
#         except Exception as e:
#           _logger.warning(f'tried to pop the lost drone but didnt work IN KILL_LOST: {e}')


# class Drone():
#   # Init
#   def __init__(self, app_ip, app_id, crm, _context=_context):
#     # Create Client object
#     self.drone_name = app_id
#     self.drone = dss.client.Client(timeout=2000, exception_handler=None, context=_context)
#     self.mission = {}
#     self.mission_status = 'idle'
#     self.drone_connected = False
#     self.drone_mission = None
#     self.fly_var = False
#     self.update_queue = update_queue
#     self.drone_info_timeout = 0

#     # threading events for thread control
#     self.stop_threads = threading.Event()

#     # Create CRM object
#     self.crm = dss.client.CRM(_context, crm, app_name=app_id, desc='single drone connection', app_id="")

#     # initialize variables
#     self._alive = True
#     self._dss_data_thread = None
#     self._dss_data_thread_active = False
#     self._dss_info_thread = None
#     self._dss_info_thread_active = False

#     # locks for objects that can be accessed by multiple threads
#     self.general_lock = threading.Lock()
#     self.drone_mission_lock = threading.Lock()
#     self.mission_status_lock = threading.Lock()
#     self.fly_mission_lock = threading.Lock()
#     self.mission_lock = threading.Lock()

#     # Find the VPN ip of host machine
#     auto_ip = dss.auxiliaries.zmq.get_ip()
#     if auto_ip != app_ip:
#       _logger.warning("Automatic get ip function and given ip does not agree: %s vs %s", auto_ip, app_ip)

#     # The application sockets
#     # Use ports depending on subnet used to pass RISE firewall
#     # Rep: ANY -> APP
#     self._app_socket = dss.auxiliaries.zmq.Rep(_context, label='app', min_port=self.crm.port, max_port=self.crm.port+50)
#     # Pub: APP -> ANY
#     self._info_socket = dss.auxiliaries.zmq.Pub(_context, label='info', min_port=self.crm.port, max_port=self.crm.port+50)

#     # Start the app reply thread
#     self._app_reply_thread = threading.Thread(target=self._main_app_reply, daemon=True)
#     self._app_reply_thread.start()

#     # Register with CRM (self.crm.app_id is first available after the register call)
#     _ = self.crm.register(app_ip, self._app_socket.port)

#     # All nack reasons raises exception, registreation is successful
#     _logger.info('App %s listening on %s:%s', self.crm.app_id, self._app_socket.ip, self._app_socket.port)
#     _logger.info(f'App_template_photo_mission registered with CRM: {self.crm.app_id}')

#     # drone position tracking
#     self.start_pos_received = False
#     self.start_pos = Waypoint() # Start position of the drone
#     self.drone_pos = Waypoint() # Current position of the drone

#     # Update socket labels with received id
#     self._app_socket.add_id_to_label(self.crm.app_id)
#     self._info_socket.add_id_to_label(self.crm.app_id)

#     # Supported commands from ANY to APP
#     self._commands = {'push_dss':     {'request': self._request_push_dss}, # Not implemented
#                       'get_info':     {'request': self._request_get_info}}

#     # Start class specific threads
#     self.connect_to_drone()
#     if self.drone_connected:
#       self.setup_dss_info_stream()

#     #self.setup_dss_data_stream() # Not implemented
#         #App-specific parameters

#     # Cheat battery level because it is not implemented in DSS
#     self.battery_level = 100.0 

#     #Parameters for generate_random_mission()
#     self.default_speed = 5.0
#     #distance between waypoints
#     self.wp_dist = 20.0
#     #geofence parameters
#     self.delta_r_max = 50.0
#     self.height_max = 30.0
#     self.height_min = 14.0
#     #maximum total time (seconds)
#     self.t_max = 240.0
#     #take-off height
#     self.takeoff_height = 15.0

#   @property
#   def alive(self):
#     '''checks if application is alive'''
#     return self._alive

#   #---------------------------Networking functions------------------------
#   #_______________________________________________________________________
#   def _main_app_reply(self):
#     '''Listens for requests from ANY, tries to carry out said requests and replies'''
#     _logger.info('Reply socket is listening on port: %d', self._app_socket.port)
#     while self.alive:
#       try:
#         msg = self._app_socket.recv_json()
#         msg = json.loads(msg)
#         fcn = msg['fcn'] if 'fcn' in msg else ''
#         if fcn in self._commands:
#           request = self._commands[fcn]['request']
#           answer = request(msg)
#         else :
#           answer = dss.auxiliaries.zmq.nack(msg['fcn'], 'Request not supported')
#         answer = json.dumps(answer)
#         self._app_socket.send_json(answer)
#       except:
#         pass
#     self._app_socket.close()
#     _logger.info("Reply socket closed, thread exit")


#   def setup_dss_info_stream(self):
#     '''Setup the DSS info stream thread'''
#     #Get info port from DSS
#     info_port = self.drone.get_port('info_pub_port')
#     if info_port:
#       self._dss_info_thread = threading.Thread(
#         target=self._main_info_dss, args=[self.drone._dss.ip, info_port])
#       self._dss_info_thread_active = True
#       self._dss_info_thread.start()


#   def setup_dss_data_stream(self):
#     '''Setup the DSS data stream thread (Not implemented)'''
#     #Get data port from DSS
#     data_port = self.drone.get_port('data_pub_port')
#     if data_port:
#       self._dss_data_thread = threading.Thread(
#         target=self._main_data_dss, args=[self.drone._dss.ip, data_port])
#       self._dss_data_thread_active = True
#       self._dss_data_thread.start()


#   def _main_info_dss(self, ip, port):
#     '''The main function for subscribing to info messages from the DSS.'''
#     # Enable LLA stream
#     self.drone._dss.data_stream('LLA', True)
#     self.drone._dss.data_stream('battery', True)
#     # Create info socket and start listening thread
#     info_socket = dss.auxiliaries.zmq.Sub(_context, ip, port, "info " + self.crm.app_id)
#     #print(self._dss_data_thread_active)
#     while self._dss_info_thread_active:
#       try:
#         (topic, msg) = info_socket.recv()
#         if topic == "LLA":
#           self.drone_pos.lat = msg['lat']
#           self.drone_pos.lon = msg['lon']
#           self.drone_pos.alt = msg['alt']
#           self.drone_info_timeout += 1
#           if self.drone_info_timeout >= 2:
#             self.queue_update('drone_position', {'drone':self.drone_name, 'lat': self.drone_pos.lat,
#                                                 'lon': self.drone_pos.lon, 'alt': self.drone_pos.alt})
#             self.drone_info_timeout = 0
#           if not self.start_pos_received:
#               self.start_pos.lat = msg['lat']
#               self.start_pos.lon = msg['lon']
#               pos_d = self.drone._dss.get_posD()
#               if pos_d <= -1:
#                 self.start_pos.alt = msg['alt'] + pos_d
#               else:
#                 self.start_pos.alt = msg['alt']
#               self.start_pos_received = True
#         elif topic == 'battery':
#           _logger.debug("Not implemented yet...")
#           #Not supported yet in the DSS
#           #self._battery_level = msg['battery status']
#           #if self._battery_level < self._battery_threshold:
#           # self.keep_flying = False
#           #set keep_flying flag to false when battery lower than threshold
#         else:
#           _logger.warning("Topic not recognized on info link: %s", topic)
#       except:
#         pass
#     info_socket.close()
#     _logger.info("Stopped thread and closed info socket")


#   def _main_data_dss(self, ip, port):
#     '''The main function for subscribing to data messages from the DSS.)'''
#     # Create data socket and start listening thread
#     data_socket = dss.auxiliaries.zmq.Sub(_context, ip, port, "data " + self.crm.app_id)
#     while self._dss_data_thread_active:
#       try:
#         (topic, msg) = data_socket.recv()
#         if topic in ('photo', 'photo_low'):
#           data = dss.auxiliaries.zmq.string_to_bytes(msg["photo"])
#           photo_filename = msg['metadata']['filename']
#           dss.auxiliaries.zmq.bytes_to_image(photo_filename, data)
#           json_filename = photo_filename[:-4] + ".json"
#           dss.auxiliaries.zmq.save_json(json_filename, msg['metadata'])
#           _logger.info("Photo saved to " + msg['metadata']['filename']  + "\r")
#           _logger.info("Photo metadata saved to " + json_filename + "\r")
#           self.transferred += 1
#         else:
#           _logger.info("Topic not recognized on data link: %s", topic)
#       except:
#         pass
#     data_socket.close()
#     _logger.info("Stopped thread and closed data socket")


#   def connect_to_drone(self, capabilities=config['app_drone_link']['capabilities']):
#     '''Ask the CRM for a drone with specified capabilities 
#       (default simulated ['SIM']) and connect to it'''
#     answer = self.crm.get_drone(capabilities)
#     if dss.auxiliaries.zmq.is_nack(answer):
#       _logger.error(f'Did not receive a drone: {dss.auxiliaries.zmq.get_nack_reason(answer)}')
#       _logger.info('No available drone')
#       self.drone_connected = False
#       return

#     # Connect to the drone, set app_id in socket
#     try:
#       self.drone.connect(answer['ip'], answer['port'], app_id=self.crm.app_id)
#       _logger.info(f"Connected as owner of drone: [{self.drone._dss.dss_id}]")
#       self.drone_connected = True
#     except:
#       _logger.info("Failed to connect as owner, check crm")
#       self.drone_connected = False
#       return

#     #------------------------------Requests---------------------------------
#     #_______________________________________________________________________
#   def _request_push_dss(self, msg):
#     '''Not implemented'''
#     answer = dss.auxiliaries.zmq.nack(msg['fcn'], 'Not implemented')
#     return answer


#   def _request_get_info(self, msg):
#     '''Returns info about the application, specifically the app_id
#        and the ports for info/data streams'''
#     answer = dss.auxiliaries.zmq.ack(msg['fcn'])
#     answer['id'] = self.crm.app_id
#     answer['info_pub_port'] = self._info_socket.port
#     answer['data_pub_port'] = None
#     return answer

#   #------------------------------GETTERS----------------------------------
#   #_______________________________________________________________________
#   def get_drone_state(self):
#     '''Get drone state, this will be a dictionary with the following keys:
#       Lat, Lon, ALT, Agl, vel_n, vel_e, vel_d, gnss_state[0-6] 
#       (global navigation satellite system), flight_state'''
#     return self.drone.get_state()


#   def get_current_waypoint(self):
#     '''Get current waypoint in lon, lat, alt'''
#     return self.drone.get_currentWP()


#   #----------------------------Utility Functions--------------------------
#   #_______________________________________________________________________
#   def queue_update(self, string, data_dict):
#     '''Takes a string and a dictionary and puts them in the queue to publish'''
#     topic = str(string)
#     self.update_queue.put((topic, data_dict))


#   def valid_mission(self, mission):
#     '''Check if all the required keys for a mission are present'''
#     for wp_id in range(0, len(mission)):
#       for key in ['lat', 'lon', 'alt', 'alt_type', 'heading']:
#         id_str = "id%d" % wp_id
#         if key not in mission[id_str]:
#           return False
#     return True


#   def task_await_init_point(self):
#     '''Wait for start position from drone'''
#     # Wait until info stream up and running
#     while self.alive and not self.start_pos_received:
#       _logger.debug("Waiting for start position from drone...")
#       time.sleep(1.0)


#   def kill(self):
#     '''This method runs on KeyBoardInterrupt, time to release resources and clean up.
#        Disconnect connected drones and unregister from crm, close ports etc..'''
#     _logger.info("Closing down...")
#     self._alive = False
#     self.stop_threads.set()
#     # Kill info and data thread
#     self._dss_info_thread_active = False
#     self._dss_data_thread_active = False
#     self._info_socket.close()
#     # stop all other threads
#     with self.drone_mission_lock:
#       if self.drone_mission is not None:
#         self.mission_status = 'idle'
#         self.drone_mission = None

#     # Unregister APP from CRM
#     _logger.info("Unregister from CRM")
#     answer = self.crm.unregister()
#     if not dss.auxiliaries.zmq.is_ack(answer):
#       _logger.error('Unregister failed: {answer}')
#     _logger.info("CRM socket closed")

#     # Disconnect drone if drone is alive
#     if self.drone.alive:
#       #wait until other DSS threads finished
#       time.sleep(0.5)
#       _logger.info("Closing socket to DSS")
#       self.drone.close_dss_socket()

#     _logger.debug('~ THE END ~')


#   #------------------------Mission Related Functions----------------------
#   #_______________________________________________________________________
#   def task_launch_drone(self, height):
#     '''Go through the launch procedure for the drone'''
#     #Initialize drone
#     self.drone.try_set_init_point()
#     self.drone.set_geofence(config['app_drone_link']['geofence_height_min'], 
#                             config['app_drone_link']['geofence_height_max'], 
#                             config['app_drone_link']['geofence_radius'])
#     self.drone.await_controls()
#     self.drone.arm_and_takeoff(height)
#     self.drone.reset_dss_srtl()


#   def return_to_home(self):
#     '''Start a thread that returns the drone to launch position'''
#     with self.mission_status_lock:
#       self.mission_status = 'returning'
#       self.queue_update('drone_status', {'drone': self.drone_name, 'drone_status': self.mission_status})
#     mission_rtl = threading.Thread(target=self.fly_rtl, args=(), daemon=True)
#     mission_rtl.start()
#     _logger.info("Flying home")

#   def mission_alt_fix(self, mission):
#     try:
#       altered_mission = mission
#       for key in altered_mission:
#         altered_mission[key]['alt'] += self.start_pos.alt
#       return altered_mission
#     except Exception as e:
#       _logger.debug(f"Excepton occurred in alt fix: {e}")


#   def fly_rtl(self):
#     '''Fly the drone to the launch position and set the mission status to landed'''
#     self.drone.rtl()
#     while not self.stop_threads:
#       if not self.drone._dss.get_armed():
#         with self.mission_status_lock:
#           self.mission_status = 'landed'
#           self.queue_update('drone_status', {'drone': self.drone_name, 'drone_status': self.mission_status})


#   def generate_random_mission(self, n_wps):
#     '''Function to construct a new mission based on current position and a
#     given area '''
#     #Compute distance from start position
#     mission = {}
#     current_wp = Waypoint()
#     current_wp.copy_lla(self.drone_pos)
#     for wp_id in range(0, n_wps):
#       (_, _, _, d_start, _, bearing) = get_3d_distance(self.start_pos, current_wp)
#       if d_start <= self.delta_r_max - self.wp_dist:
#         #Safe to generate a random point (meter)
#         delta_dir = np.random.uniform(-np.pi, np.pi)
#       else:
#         #move back towards start pos
#         delta_dir = (bearing + 2*np.pi) % (2 * np.pi) - np.pi
#       #Compute new lat lon
#       d_northing = self.wp_dist*np.cos(delta_dir)
#       d_easting = self.wp_dist*np.sin(delta_dir)
#       (d_lat, d_lon) = ne_to_ll(current_wp, d_northing, d_easting)
#       new_lat = current_wp.lat + d_lat
#       new_lon = current_wp.lon + d_lon
#       # Compute new altitude
#       new_height = current_wp.alt - self.start_pos.alt + np.random.uniform(-2.0, 2.0)
#       new_alt = self.start_pos.alt + min(self.height_max, max(self.height_min, new_height))
#       current_wp.set_lla(new_lat, new_lon, new_alt)

#       id_str = "id%d" % wp_id
#       mission[id_str] = {
#         "lat" : new_lat, "lon": new_lon, "alt": new_alt, "alt_type": "amsl", 
#         "heading": "course", "speed": self.default_speed
#       }
#     # Add start position as final wp
#     id_str = "id%d" % n_wps
#     mission[id_str] = {
#         "lat" : self.start_pos.lat, "lon": self.start_pos.lon,
#         "alt": new_alt, "alt_type": "amsl", "heading": "course", 
#         "speed": self.default_speed
#     }
#     return mission


#   def fly_mission(self, mission):
#     '''Start a thread that flies the given mission'''
#     mission = self.mission_alt_fix(mission)
#     with self.general_lock:
#       if not self.drone._dss.get_armed():
#         with self.mission_status_lock:
#           self.mission_status = 'launching'
#           self.queue_update('drone_status', {'drone': self.drone_name, 'drone_status': self.mission_status})
#         self.task_launch_drone(self.takeoff_height)
#     self.task_await_init_point()
#     with self.mission_lock:
#       self.mission = mission
#     with self.fly_mission_lock:
#       self.fly_var = True
#     with self.drone_mission_lock:
#       # Stops current mission
#       self.stop_threads.set()
#       time.sleep(1)
#       # Allows for next mission to be flown
#       self.stop_threads.clear()
#       self.drone_mission = threading.Thread(target=self.task_execute_mission, args=(mission,), daemon=True)
#       self.drone_mission.start()


#   def execute_random_mission(self, n_wps = 5):
#     '''Start a thread that flies a random mission of default length 5 waypoints'''
#     with self.general_lock:
#       if not self.drone._dss.get_armed():
#         with self.mission_status_lock:
#           self.mission_status = 'launching'
#           self.queue_update('drone_status', {'drone': self.drone_name, 'drone_status': self.mission_status})
#         self.task_launch_drone(self.takeoff_height)
#     self.task_await_init_point()
#     mission = self.generate_random_mission(n_wps)
#     with self.mission_lock:
#       self.mission = mission
#     with self.fly_mission_lock:
#       self.fly_var = True
#     with self.drone_mission_lock:
#       # Stop the current mission
#       self.stop_threads.set()
#       time.sleep(1)
#       # Allows for next mission to be flown
#       self.stop_threads.clear()
#       self.drone_mission = threading.Thread(target=self.task_execute_mission, args=(mission,), daemon=True)
#       self.drone_mission.start()


#   def task_execute_mission(self, mission, raise_if_aborted = True):
#     '''Flies a mission and updates the mission status accordingly'''
#     self.drone.upload_mission_LLA(mission)
#     time.sleep(0.5)
#     # Fly waypoints, allow PILOT intervention.
#     last_answer = 1
#     with self.mission_status_lock:
#           self.mission_status = 'flying'
#           self.queue_update('drone_status', {'drone': self.drone_name, 'drone_status': self.mission_status})
#     self.drone._dss.gogo(last_answer)
#     while not self.stop_threads.is_set() and self.drone._dss.get_armed():  
#       # Essentially just fly_waypoints but we can cancel it with stop_threads, don't have to deal with nested while loop  
#       try:
#         time.sleep(1.0)
#         if raise_if_aborted:
#           self.drone.raise_if_aborted()
#         currentWP, _ = self.drone._dss.get_currentWP()
#         if currentWP != last_answer:
#           last_answer = currentWP
#           if last_answer == -1:
#             break
#       except dss.auxiliaries.exception.Nack as nack:
#         if nack.msg == 'Not flying':
#           _logger.info("Pilot has landed")
#           with self.mission_status_lock:
#             self.mission_status = 'landed'
#             self.queue_update('drone_status', {'drone': self.drone_name, 'drone_status': self.mission_status})
#         else:
#           _logger.info("Fly mission was nacked %s", nack.msg)
#           with self.mission_status_lock:
#             self.mission_status = 'denied'
#             self.queue_update('drone_status', {'drone': self.drone_name, 'drone_status': self.mission_status})
#         self.stop_threads.set()
#         break
#       except dss.auxiliaries.exception.AbortTask:

#         # PILOT took controls
#         (current_wp, _) = self.drone.get_currentWP()
#         _logger.info("Pilot took controls, awaiting PILOT action")
#         self.drone.await_controls()
#         _logger.info("PILOT gave back controls")
#         # Try to continue mission
#         self.drone._dss.gogo(current_wp)
#         continue
#     with self.mission_status_lock:
#       self.mission_status = 'waiting'
#       self.queue_update('drone_status', {'drone': self.drone_name, 'drone_status': self.mission_status})

# #--------------------------MAIN LOOP START------------------------------
# #_______________________________________________________________________

#   def main(self):
#     '''Main loop for the Drone class'''
#     while alive_event.is_set():
#       time.sleep(1)


# def _main_loop():
#   '''Main loop for the main application'''
#   while alive_event.is_set():
#         time.sleep(1)


# def _main(app_ip= None, crm = '10.44.170.10:17700', app_id = "app_drone_link"):

#   subnet = dss.auxiliaries.zmq.get_subnet(ip=IP)

#   dss.auxiliaries.logging.configure('app_drone_link', stdout=False, rotating=True, loglevel='debug', subdir=subnet)
#   alive_event.set()

#   try:
#     app = Link()
#   except dss.auxiliaries.exception.NoAnswer:
#     _logger.error('Failed to instantiate application: Probably the CRM couldn\'t be reached')
#     sys.exit()
#   except:
#     _logger.error('Failed to instantiate application\n%s', traceback.format_exc())
#     sys.exit()

#   # Try to setup objects and initial sockets
#   try:
#     # Try to run main
#     _main_loop()

#   except KeyboardInterrupt:
#     _logger.warning('Shutdown due to keyboard interrupt')
#     app.kill()
#   except Exception as e:
#     _logger.warning(f'Exception while running main_loop: {e}')
#     pass
#   try:
#     app.kill()
#   except:
#     _logger.error(f'unexpected exception\n{traceback.format_exc()}')


# #--------------------------------------------------------------------#
# if __name__ == '__main__':
#   _main()
