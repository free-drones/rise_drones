.. |DSS| replace:: Drone Safety System
.. |CRM| replace:: Central Resource Manager
.. |SSS| replace:: Sensor Safety System

.. role:: python(code)
  :language: python

.. _sssapi:

|SSS| API
========================

.. index:: SSS, Snesor Safety System

The |SSS| is a middleware that makes it easy to interact with sensors in
differnet ways. A SSS is much like a DSS, it responds to requests, has publish
ports for different streams, has an owner and registers to the |CRM|. The |SSS|
offers applications to connect and control a sensor via an unified API. The
|SSS| currently supports raspberry pi cam.

The |SSS| takes care of the low level functionality. An application software
connects to the |SSS| and requests sensorinformation. Applications can be
written in any language and be hosted anywhere on the network. The communication
library ZeroMQ is used to share information between entities independent on
architecture and code base.

If the application disconnects or loses link, the CRM will take back the
ownership. Some requests requires the requestor to be the owner of the sensor,
refer to API description.

The final component in the figure below is the Central Resource Manager (CRM).
The CRM is mainly responsible for managing the available drone resources to
applications. However, it can also launch a new application to control a drone
or a sensor if the previous application owner for some reason loses connection
to the drone during flight. Nowdays we strive to use the CRM for all
applications and scenarios. It is the default option, however it is still
possible to run applications without the CRM if they are developed to support
it.


.. figure:: images/drone_platform_overview_pilot.png
  :width: 500

  Rise Drones platform architecture overview

Communication
--------------

.. index:: SSS, Communication

The |SSS| offers three external interfaces towards an application. To
support any code base in the application, commands are encoded in
serialised JSON objects and transferred via zeroMQ library.

- DSS Ctrl Reply-socket where the application can call functions and
  receive ack/nack and information

- Info Publish-socket where data streams can be published, e.g.
  autopilot state data

- Data Publish-socket for bigger data structures, e.g. photos

Available commands are described in :ref:`ssscontrolAPI`.

The socket ports for non CRM operations are described below. In CRM
operations the CRM will present the ip and Ctrl-Reply-socket port for
each client, and the publish ports can be requested by directly
connecting to the client of interest and issuing get_info. The sockets
are open for all connecting ip-numbers.

.. code-block:: json
  :caption: Sockets port definition if **NOT** using CRM
  :linenos:

  {
    "Ctrl-Reply-socket": 5557,
    "Info-Publish-Socket": 5558,
    "Data-Publish-Socket": 5559
  }

Each function call must include an application id. This is because
each SSS is owned by someone (application id), and that the owner has
higher level permissions than non-owners. Some commands requires that
the command is sent from the SSS owner in order to be acknowledged by
the SSS, while some commands can be used by everyone. This is
explained in more detail in the Nack reasons for each command in the
API.

In scenarios where CRM is used the application id is distributed by
the CRM in the setup phase. In scenarios without CRM, the application
must use the default application id :python:`"da000"`.

Coordinate system
-----------------

The sensor coordiante system is defined by the camera center line in reference
to the horizontal plane and true north. The center line projected in the
horizontal plane relative true north defines the yaw, the angle between the
horizontal plane and the center line defines the pitch angle and the agnle
between image horizontal axis and the horizon defines roll angle.



.. _ssscontrolAPI:

SSS Ctrl-link API
-----------------

.. index:: SSS; Ctrl-link API

General
~~~~~~~

The ZeroMQ REQ/REP interface takes function calls as JSON objects with
two mandatory keys, :python:`"fcn"` and :python:`"id"`, the string
values are the function name and the application id. Additional keys
are described in this API chapter. Each function call gets confirmed
with an ack or a nack where the key :python:`"call"` holds the name of
the calling function. A generic example follows:

.. code-block:: json
  :caption: Generic function call from application to |SSS|
  :linenos:

  {
    "fcn": "<function name>", "id": "<requestor id>"
  }

Response from |SSS| is an ack or a nack. The key :python:`"call"`
carries the name of the function called. Some functions uses the ack
reply to transfer data, which can be seen in the listings of the API
below. A nack includes the key :python:`"description"` that carries a
nack description string.

.. code-block:: json
  :caption: Generic response: ``ack``
  :linenos:

  {
    "fcn": "ack",
    "call": "<function_name>"
  }

.. code-block:: json
  :caption: Generic response: ``nack``
  :linenos:

  {
    "fcn": "nack",
    "call": "<function name>",
    "description": "<Nack reason>"
  }


Fcn: ``heart_beat``
~~~~~~~~~~~~~~~~~~~

.. compatibility:: badge
  :py-client: verified

The |SSS| tracks the activity from the application to survey if the
application is still alive. Each and every function call from
the application to the |SSS| acts as a heartbeat. If no other messages
are sent from the application to the |SSS|, the application shall call
the ``heart_beat`` function to maintain the link integrity. The link
is considered degraded after 5 seconds and lost after 10 seconds.

The link lost behaviour differs depending on if the |CRM| is used or not as
described below.

|CRM| not used behaviour:
_________________________

The |SSS| will do nothing.

|CRM| is used behaviour:
_________________________

The |SSS| will notify the CRM using the function `app_lost`. If it receives an
ack, the |SSS| will reset the lost link counter. In the meantime the |CRM| will
launch an application that claims ownership of the |SSS| and will send heart
beats and try to land the SSS (heritage from DSS). If the lost link counter
reaches the limit for the second time without receiving any heartbeats in
between the |SSS| will engage the autopilot implementation of RTL (heritage from
DSS).


If it receives a nack (or no response) |SSS| will do nothing.

.. code-block:: json
  :caption: Function call ``heart_beat``
  :linenos:

  {
    "fcn": "heart_beat",
    "id": "<requestor id>"
  }

The SSS responds to the ``heart_beat`` function call with an ack.

.. code-block:: json
  :caption: Response to ``heart_beat``
  :linenos:

  {
    "fcn": "ack",
    "call": "heart_beat"
  }

**Nack reasons:**
  - Requester (``id``) is not the SSS owner

  .. _fcnsssgetinfo:

Fcn: get_info
~~~~~~~~~~~~~


The function ``get_info`` requests connection information from the SSS.
The SSS answers with an ack and the applicable information.

.. code-block:: json
  :caption: Function call: ``get_info``
  :linenos:

  {
    "fcn": "get_info",
    "id": "<requestor id>"
  }

.. code-block:: json
  :caption: Reply: ``get_info``
  :linenos:

  {
    "fcn": "ack",
    "call": "get_info",
    "id": "<replier id>",
    "info_pub_port": 1234,
    "data_pub_port": 5678
  }

**Nack reasons:**
  - None

.. _fcnssswhocontrols:

Fcn: ``who_controls``
~~~~~~~~~~~~~~~~~~~~~

.. compatibility:: badge
  :py-client: verified

The function ``who_controls`` requests who is in control of the sensor, the
"APPLICATION" (sensor application) the "PILOT" (pilot in command) or the "SSS"
itself. While the pilot is in control the |SSS| is not allowed to control the
sensor. This is a safety feature heritage from DSS, it might be used in future
but for now APPLICATION is always in controls.

The response holds the key "in_controls" that carries the string "PILOT",
"APPLICATION" or "SSS". CRM is treated as an application.

.. todo:: Should operator == PILOT be a nack reason for all commands affecting the drone?

.. code-block:: json
  :caption: Function call: ``who_controls``
  :linenos:

  {
    "fcn": "who_controls",
    "id": "<requestor id>",
  }

.. code-block:: json
  :caption: Function response:
  :linenos:

  {
    "fcn": "ack",
    "call": "who_controls",
    "in_controls": "APPLICATION"
  }

**Nack reasons:**
  - None


.. _fcnsssgetowner:

Fcn: ``get_owner``
~~~~~~~~~~~~~~~~~~~~~

.. compatibility:: badge
  :py-client: -

The function ``get_owner`` requests the registered owner of the SSS.

The response holds the key "owner" that carries the string with the
application id of the owner. The default owner is "da000".

.. code-block:: json
  :caption: Function call: ``get_owner``
  :linenos:

  {
    "fcn": "get_owner",
    "id": "<requestor id>",
  }

.. code-block:: json
  :caption: Function response:
  :linenos:

  {
    "fcn": "ack",
    "call": "get_owner",
    "owner": "<owner id>"
  }

**Nack reasons:**
  - None


.. _fcnssssetowner:

Fcn: ``set_owner``
~~~~~~~~~~~~~~~~~~~~~

.. compatibility:: badge
  :py-client: -

The function ``set_owner`` sets the SSS owner. The function call holds
the key "owner" with a string with the new owners id. The reply holds
an ack or a nack.

.. code-block:: json
  :caption: Function call: ``set_owner``
  :linenos:

  {
    "fcn": "set_owner",
    "id": "<requestor id>",
    "owner": "<the new owner>"
  }


**Nack reasons:**
  - Requestor is not CRM




.. _fcnsssgetidle:

Fcn: ``get_idle``
~~~~~~~~~~~~~~~~~

.. compatibility:: badge
  :py-client: -

The function ``get_idle`` reports false if task is running, i.e. cv_algorithm is
running or media is beeing streamed for example, otherwise true.

.. code-block:: json
  :caption: Function call: ``get_idle``
  :linenos:

  {
    "fcn": "get_idle",
    "id": "<requestor id>"
  }

.. code-block:: json
  :caption: Function response:
  :linenos:

  {
    "fcn": "ack",
    "idle": true
  }

**Nack reasons:**
  - None


.. _fcnsssgetpose:

Fcn: ``get_pose``
~~~~~~~~~~~~~~~~~~
.. compatibility:: badge
  :py-client: -

The function ``get_pose`` acquires the camera pose of the sensor.

Lat, long [Decimal degrees]; Alt [m AMSL]; Heading [degrees relative true
north]; Agl [m] above ground, -1 if not valid; roll, pitch [degrees relative
horizon]; yaw [degrees relative true north], status is a string describing a
running task.


.. code-block:: json
  :caption: Function call: ``get_pose``
  :linenos:

  {
    "fcn": "get_pose",
    "id": "<requestor id>"
  }


.. code-block:: json
  :caption: Function response: ``get_pose``
  :linenos:


  {
    "fcn": "ack",
    "lat": -0.0018926148768514395,
    "long": 0.0014366497052833438,
    "alt": 28.3,
    "roll": 2,
    "pitch": 45,
    "yaw": 259,
    "status": "describing string"
  }

**Nack reasons:**
  - None


.. _fcnssssetpose:

Fcn: ``set_pose``
~~~~~~~~~~~~~~~~~~~~~~~~

.. compatibility:: badge
  :py-client: -

The function ``set_pose`` set the current pose of the sensor.

Lat, long [Decimal degrees]; Alt [m AMSL]; Agl [m] above ground, -1 if not
valid; roll, pitch [degrees relative horizon]; yaw [degrees relative true
north].

.. code-block:: json
  :caption: Function call: ``set_pose``
  :linenos:

  {
    "fcn": "set_pose",
    "id": "<requestor id>",
    "lat": -0.0018926148768514395,
    "long": 0.0014366497052833438,
    "alt": 28.3,
    "roll": 2,
    "pitch": 45,
    "yaw": 259
  }

**Nack reasons:**
  - None


.. _fcnssssetgimbal:

Fcn: ``set_gimbal``
~~~~~~~~~~~~~~~~~~~

.. compatibility:: badge
  :py-client: -

The function ``set_gimbal`` commands the gimbal to rotate to the
``roll``, ``pitch`` and ``yaw`` angles provided [deg]. Positive roll
is leaning right, positive pitch angles points nose up and increasing
yaw angles rotates the gimbal clockwise. Parameters not supported by
the gimbal in use will just be ignored.

.. code-block:: json
  :caption: Function call: ``set_gimbal``
  :linenos:

  {
    "fcn": "set_gimbal",
    "id": "<requestor id>",
    "roll": 0,
    "pitch": -90,
    "yaw": 0
  }

**Nack reasons:**
  - Requester is not the SSS owner
  - Application is not in controls
  - Roll, pitch or yaw is out of range for the gimbal


.. _fcncvalgorithm:

Fcn: ``cv_algorithm``
~~~~~~~~~~~~~~~~~~~~~

.. compatibility:: badge
  :py-client: -

The function ``cv_algorithm`` enables or disables computer vision algorithm task
on the sensor. The task will run until disabled or when other high priority task
is enabled.

The key ``algorithm`` is used to specify the algorithm, 'boundingBox' and
'objectDetection' are available.

The key ``enable`` takes a bool to enable or disable the algorithm.

.. code-block:: json
  :caption: Function call: ``cv_algorithm``
  :linenos:

  {
    "fcn": "cv_algorithm",
    "id": "<requestor id>",
    "algorithm": "boundingBox",
    "enable": false
  }

**Nack reasons:**
  - Requester is not the SSS owner
  - Cannot disable algorithm not running
  - Algorithm not supported, <stream>



.. .. _fcnphoto:

.. Fcn: ``photo``
.. ~~~~~~~~~~~~~~

.. .. compatibility:: badge
..   :ardupilot: -
..   :dji: verified
..   :py-client: verified

.. The function ``photo`` controls the photo sub-module. The key ``"cmd"`` can be
.. set to ``"take_photo"``, , ``"record"``, ``"continous_photo"`` or ``"download"``.
.. Take photo triggers the camera to take a photo with current settings, Record
.. enables or disables video recording, Continous photo enables or disables a
.. continous photo session and Download triggers the |DSS| to publish the photo(s)
.. on the DATA-socket.

.. **Take photo**

.. No extra keys.

.. .. code-block:: json
..   :caption: Function call: ``photo, take_photo``
..   :linenos:

..   {
..     "fcn": "photo",
..     "id": "<requestor id>",
..     "cmd": "take_photo"
..   }

.. .. code-block:: json
..   :caption: Function response:
..   :linenos:

..   {
..     "fcn": "ack",
..     "call": "photo",
..     "description": "take_photo"
..   }

.. **Nack reasons:**
..   - Requester is not the DSS owner
..   - Application is not in controls
..   - Camera resource is busy
..   - Cmd faulty

.. **Record**

.. The record command has one extra key, ``"enable"``. Enable is a bool to
.. enable or disable the recording.

.. .. code-block:: json
..   :caption: Function call: ``photo, record``
..   :linenos:

..   {
..     "fcn": "photo",
..     "id": "<requestor id>",
..     "cmd": "record",
..     "enable":  true
..   }

.. .. code-block:: json
..   :caption: Function response:
..   :linenos:

..   {
..     "fcn": "ack",
..     "call": "photo",
..     "description": "record - enabled/disabled"
..   }


.. **Nack reasons:**
..   - Requester is not the DSS owner
..   - Application is not in controls
..   - Camera resource is busy
..   - Cmd faulty

.. **Continous photo**

.. The continous photo command has three extra keys, ``"enable"``,
.. ``"period"`` and ``"publish"``. Enable is a bool to enable or disable
.. the contionous photo. Period is a double for setting the desired photo
.. period in seconds (seconds between photos). Publish is a flag to
.. trigger the DSS to publish each photo, it can be set to "off", "low"
.. or "high" where low and high detemines high or low resolution. If the
.. period is set lower than the hardware allows for, photos will be taken
.. as often as possible.

.. .. code-block:: json
..   :caption: Function call: ``photo, continous_photo``
..   :linenos:

..   {
..     "fcn": "photo",
..     "id": "<requestor id>",
..     "cmd": "continous_photo",
..     "enable":  true,
..     "publish": "low",
..     "period": 2.5
..   }

.. .. code-block:: json
..   :caption: Function response:
..   :linenos:

..   {
..     "fcn": "ack",
..     "call": "photo",
..     "description": "continous_photo - enabled/disabled"
..   }


.. **Nack reasons:**
..   - Requester is not the DSS owner
..   - Application is not in controls
..   - Camera resource is busy
..   - Cmd faulty


.. **Download**

.. The download command has two extra keys, ``"index"`` and the optional
.. key ``"resolution"`` The key ``"index"`` can be set to an integer for
.. a specific photo index, "latest" or "all" for all indexes of the
.. current session. Index relates to an increasing index from that
.. session and can be identified via function :ref:`fcngetmetadata`. The
.. index is included in the response as a string.

.. The optional key ``resolution`` can be set to ``"high"`` or ``"low"``,
.. high is the default value.

.. The response is a description string with command and index when
.. applicable.

.. The requested file(s) are published on the DATA-socket, refer to
.. :ref:`photodownload`

.. .. code-block:: json
..   :caption: Function call: ``photo, download``
..   :linenos:

..   {
..     "fcn": "photo",
..     "id": "<requestor id>",
..     "cmd": "download",
..     "resolution": "low",
..     "index": "all"
..   }

.. .. code-block:: json
..   :caption: Function response:
..   :linenos:

..   {
..     "fcn": "ack",
..     "call": "photo",
..     "description": "download <index>"
..   }

.. **Nack reasons:**
..   - Requester is not the DSS owner
..   - Application is not in controls
..   - Camera resource is busy
..   - Index out of range, <index>
..   - Index string faulty, <index>
..   - Cmd faulty

.. .. _fcngetmetadata:

.. Fcn: ``get_metadata``
.. ~~~~~~~~~~~~~~~~~~~~~

.. .. compatibility:: badge
..   :ardupilot: -
..   :dji: verified
..   :py-client: verified

.. The function ``get_metadata`` requests metadata from the photos of the
.. current session.

.. The key ``index`` can be set to a integer for a specific index or the
.. string ``"all"`` for all metadata or the string ``"latest"`` for the
.. latest metadata.

.. The key ``reference`` specifies what coordinate system the metadata
.. shall be given in, ``"LLA"``, ``"NED"`` or ``"XYZ"``.

.. The response format is the same as described in the
.. :ref:`dssinfolinkapi` with the additional keys "index", "filename" and
.. "pitch for gimbal pitch" as shown below.

.. .. code-block:: json
..   :caption: Function call: ``get_metadata``
..   :linenos:

..   {
..     "fcn": "get_metadata",
..     "id": "<requestor id>",
..     "ref": "XYZ",
..     "index": "latest"
..   }

.. **Nack reasons:**
..   - Reference faulty, <ref>
..   - Index out of range, <index>
..   - Index string faulty, <index>

.. .. code-block:: json
..   :caption: Function response:
..   :linenos:

..   {
..     "fcn": "ack",
..     "call": "get_metadata",
..     "metadata": {
..       "0": {
..         "index": 0,
..         "filename": "the_filename.file_type",
..         "x": 1,
..         "y": 4,
..         "z": -15,
..         "agl": -1,
..         "heading": 10,
..         "pitch": -45
..       },
..       "1": {
..         "...":"..."
..       }
..     }
..   }



.. .. _fcndisconnect:

.. Fcn: ``disconnect``
.. ~~~~~~~~~~~~~~~~~~~

.. .. compatibility:: badge
..   :ardupilot: -
..   :dji: verified
..   :py-client: verified

.. The function ``disconnect`` informs the |DSS| that application will
.. disconnect. |DSS| will enter a hover, honor the heartbeat
.. functionality, but immediately call the CRM :ref:`fcnapplost` if CRM
.. is in use.

.. .. code-block:: json
..   :caption: Function call: ``disconnect``
..   :linenos:

..   {
..     "fcn": "disconnect",
..     "id": "<requestor id>"
..   }

.. **Nack reasons:**
..   - Requester is not the DSS owner


.. _fcnsssdatastream:

Fcn: ``data_stream``
~~~~~~~~~~~~~~~~~~~~

.. compatibility:: badge
  :py-client: verified

The function ``data_stream`` enables or disables a data stream on the
INFO-socket.

The key ``stream`` is used to specify the wanted stream.

The key ``enable`` that takes a bool to enable or disable the stream.

Available stream values are:

=========  =========================
Stream     Description
=========  =========================
BB         Bounding box
OD         Object detection
=========  =========================

SSS will publish data as soon as new data is available. The format
of the published data is described in the :ref:`sssinfolinkapi`.

.. code-block:: json
  :caption: Function call: ``data_stream``
  :linenos:

  {
    "fcn": "data_stream",
    "id": "<requestor id>",
    "stream": "BB",
    "enable": true
  }

**Nack reasons:**
  - Stream faulty, <stream>

.. code-block:: json
  :caption: Function response:
  :linenos:

  {
    "fcn": "ack",
    "call": "data_stream"
  }


.. _sssinfolinkapi:

SSS Info-link API
-----------------

Streams of information can be controlled using the function
:ref:`fcnsssdatastream`. The information is published on the Info-socket
together with the corresponding attribute as topic. The format for each
attribute is described in the following sections.


.. _boundingbox:

boundingBox - boundingBox - what?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. compatibility:: badge
  :py-client: -

The sensor has detected a target within a bounding box. The message contains the
key "x" for first x pixel, "y" for first y pixel, "width" for width and "height"
for height.

.. code-block:: json
  :caption: Info-socket: Topic ``BB``
  :linenos:

  {
    "x": 340,
    "y": 80,
    "width": 40,
    "height": 23
  }


.. _objectdetection:

objectdetection - objectdetection - what?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. compatibility:: badge
  :py-client: -

The sensor has detected a target within a bounding box. The message contains the
key "x" for first x pixel, "y" for first y pixel, "width" for width and "height"
for height.

.. code-block:: json
  :caption: Info-socket: Topic ``OD``
  :linenos:

  {
    "x": 340,
    "y": 80,
    "width": 40,
    "height": 23
  }


.. .. _photoLLA:

.. Photo LLA - photo available with Metadata
.. ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. .. compatibility:: badge
..   :ardupilot: -
..   :dji: verified
..   :py-client: verified

.. Metadata for a photo given in the LLA frame published with topic
.. photo_LLA. Filename is not available until photo is downloaded. The
.. message contains the key "index" for photo index, "filename" for photo
.. filename if available and keys described in :ref:`LLA`.

.. .. code-block:: json
..   :caption: Info-socket: Topic ``photo_LLA``
..   :linenos:

..   {
..     "index": 1,
..     "filename": "the_filename.file_type",
..     "lat": 58.3254094,
..     "lon": 15.6324897,
..     "alt": 114.1
..     "agl": 8,
..     "heading": 10
..   }


.. .. _photoXYZ:

.. Photo XYZ - new photo metadata
.. ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. .. compatibility:: badge
..   :ardupilot: -
..   :dji: verified
..   :py-client: verified

.. Metadata for a photo given in the XYZ frame published with topic
.. photo_XYZ. Filename is not available until photo is downloaded. The
.. message contains the key "index" for photo index, "filename" for photo
.. filename if available and keys described in :ref:`XYZ`.

.. .. code-block:: json
..   :caption: Info-socket: Topic ``photo_XYZ``
..   :linenos:

..   {
..     "index": 1,
..     "filename": "the_filename.file_type",
..     "x": 1,
..     "y": 4,
..     "z": -15
..     "agl": -1
..     "heading": 10
..   }


.. .. _currentWP:

.. Current WP - Mission progress
.. ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. .. compatibility:: badge
..   :ardupilot: -
..   :dji: verified
..   :py-client: verified

.. Mission progress data is sent every time the |DSS| tracks a waypoint.
.. The message contains the key "currentWP" for the waypoint |DSS| is
.. flying towards  and "finalWP" for the final wp number in the active
.. mission. When the final wp is reached -1 is sent as currentWP.

.. .. code-block:: json
..   :caption: Info-socket: Topic ``currentWP``
..   :linenos:

..   {
..     "currentWP": 2,
..     "finalWP": 5
..   }


.. .. _sssdatalinkapi:

.. SSS Data-link API
.. -----------------

.. When data is requested from the |DSS|, it publishes the data on the Data-socket
.. together with the corresponding attribute as topic. Format for each
.. attribute is described in the following sections.

.. .. _photodownload:

.. Photo download
.. ~~~~~~~~~~~~~~

.. .. compatibility:: badge
..   :ardupilot: -
..   :dji: verified
..   :py-client: verified

.. Photos are requested using the function :ref:`fcnphoto`. Requested
.. photos will be published on the Data-socket with the topic photo or
.. photo_low depending on the resolution. The message contains the key
.. "photo" with a base64 encoded photo string, "metadata" with json with
.. the corresponding metadata specified in the photo request. Meta data
.. keys are described in :ref:`photoLLA` and :ref:`photoXYZ`.

.. .. code-block:: json
..   :caption: Data-socket: Topic ``photo`` or topic ``photo_low``
..   :linenos:

..   {
..     "photo": "<base64 encoded photo string>",
..     "metadata": {
..       "index": 1,
..       "filename": "the_filename.file_type",
..       "x": 1,
..       "y": 4,
..       "z": -15,
..       "agl": -1,
..       "heading": 10
..     }
..   }
