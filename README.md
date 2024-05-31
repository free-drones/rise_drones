# RISE drone system
Hi there, we are happy that you are here!✨ <br />
In this document you'll find brief information about RISE drone system, after which we help you get started. In order to grow and get better we greatly appreciate your feedback, feel free to contribute by following the contribution guidelines. In the last section you can find information about licensing and how you can utilize our system.

## What is RISE drone system?
The platform is built to simplify the process of developing applications for autonomous systems and to make it easy to get a sensor in the air or lay out search patterns.

There are three basic building blocks of the software platform:

**Application:** <br />
Utilizes one or several drones to execute missions defined in the application. This software is typically built from a python template. The application code decides what control commands that should be sent to the drone and when, such as take-off, goto waypoint, take photo etc. The application code can utilize the handy DSS-library or just implement the commands as they are described in the API. The application can run anywhere on the network; on the drone, on the server or as a mobile app.

**DSS:** <br />
Drone Safety Service (DSS) acts as a bridge between applications and the autopilot. The DSS receives commands from applications or other modules if necessary, it interprets them and tries to execute them through the autopilot. Currently there are two DSS versions, one for Ardupilot and one for DJI. Both DSS offer the same API resulting in identical code on application level.

**CRM:**<br />
Central Resource Manager (CRM) is a resource manager that runs in the network. The main responsibility for the CRM is to manage ownership of available resources and supply connection information. An application can request a specific drone or a drone per capability, if there are any suitable drone available in the pool of drones, the CRM will assign it and supply connection information. A simple scenario would be that the application connects directly to the DSS, this requires knowledge about IP and ports. Now imagine managing several applications and drones (i.e several DSS's) manually, the task quickly becomes cumbersome managing different ip numbers and ports. Using the CRM makes the task of dealing with several applications and drones more manageable. Every application and DSS shall register to the CRM and supply their connection information. The CRM then automatically becomes the owner of the drone resources and assigns resources and connection information when requested. In this setup the only knowledge required is the IP and port for the CRM.

## Getting started

1. Install necessary dependencies

> pip install -r requirements.txt

2. Add src directory to pythonpath

> cd src
> export PYTHONPATH=`pwd` 

3. Install SITL - ardupilot

> git clone git@github.com:ArduPilot/ardupilot.git <br/>
> git submodule update --init --recursive <br/>
> python3 -m venv .ardupilot <br/>
> pip3 install -r requirements.txt <br/>
> Modify ardupilot/Tools/autotest/locations.txt <br/>

It is recommended to put a configfile in ~/.rise_drones/.config. but it can also be put in rise_drones/src or from where script is called.
```javascript
{
  "zeroMQ": {
    "subnets" : {
      "vpn161": {
        "ip": "10.44.161.",
        "crm_ip": "10.44.160.10",
        "crm_port": 16100,
        "min_port": 16100,
        "max_port": 16199
      },
      "home": {
        "ip": "192.168.1.",
      	"crm_ip": "192.168.1.196",
        "crm_port": 10000,
        "min_port": 10000,
        "max_port": 10099
      }
    }
  },
  "CRM" : {
    "default_crm_ip": "127.0.0.1",
    "default_crm_port": 12700,
    "SITL": {
      "pythonPATH": "/home/pi/.venv/venv-ardupilot/bin/python3",
      "mavproxyPATH": "/home/pi/.venv/venv-ardupilot/bin/mavproxy.py",
      "ardupilot_dir": "/home/pi/ardupilot/",
      "drone_1": {
          "lat": 58.408868,
          "lon": 15.659205,
          "alt": 30.5,
          "heading": 45
        },
        "drone_2": {
          "lat": 58.38825737644909,
          "lon": 13.481121210496298,
          "alt": 130.6,
          "heading": 45
        },
        "drone_3": {
          "lat": 58.3884,
          "lon": 13.4844,
          "alt": 130.6,
          "heading": 45
        },
        "drone_4": {
          "lat": 58.38825737644909,
          "lon": 13.481121210496298,
          "alt": 130.6,
          "heading": 45
        },
        "_airport": {
          "lat": 58.408871,
          "lon": 15.659212,
          "alt": 30.5,
          "heading": 45
        },
        "_kolbyttemon": {
          "lat": 58.327740,
          "lon": 15.634766,
          "alt": 35,
          "heading": 45
        },
        "_skara": {
         "lat": 58.38825737644909,
         "lon": 13.481121210496298,
         "alt": 130.6,
         "heading" : 45
        }
      }
  },
  "DSS": {
    "HeartbeatAttempts":     3,
    "HeartbeatClientSocket": "tcp://192.168.1.4:5560",
    "PhotoClient":           "tcp://192.168.1.3:5556",
    "ServSocket":            "tcp://*:5557",
    "GlanaClientSocket":     "tcp://192.168.1.3:5562",
    "VEL": {
      "vel_lim_enable": 0,
      "vel_x_max": 5,
      "vel_x_min": -3,
      "vel_y_max": 3,
      "vel_y_min": -3,
      "vel_z_max": 1,
      "vel_z_min": -1.5,
      "max_yaw_rate": 15,
      "min_yaw_rate": -15
    },
    "ACC": {
      "acc_lim_enable": 1,
      "acc_x_max": 0.8,
      "acc_x_min": 0.8,
      "acc_y_max": 0.8,
      "acc_y_min": 0.8,
      "acc_z_max": 0.5,
      "acc_z_min": 0.5,
      "yaw_turd_max": 10,
      "yaw_turd_min": 10
    },
    "POS": {
      "pos_ned_n_max": 200,
      "pos_ned_n_min":-200,
      "pos_ned_e_max": 200,
      "pos_ned_e_min": -200,
      "pos_ned_d_max": 0,
      "pos_ned_d_min": -80
    },
    "WP": {
      "max_wp_distance": 25
    }
  },
  "mqtt" : {
    "user": "user" ,
    "password": "password",
    "broker": "broker-url",
    "port": 5555,
    "tls_connection": true
  },
  "app_ussp_mission" :{
    "ussp_ip": "localhost",
    "ussp_req_port": 5555,
    "ussp_pub_port": 5556,
    "ussp_sub_port": 5557,
    "operator_id": "SWE33DummyOperatorID",
    "delta_r_max": 2000.0,
    "height_max": 120.0,
    "height_min": 8.0
  }
}

```

## Contributing
If you would want to contribute to RISE drone system please take a look at [the guide for contributing](contributing.md) to find out more about the guidelines on how to proceed.

## License
RISE drone system is realeased under the [BSD 3-Clause License](https://opensource.org/licenses/BSD-3-Clause)

## Documentation
See Readme in doc folder for documentation.
