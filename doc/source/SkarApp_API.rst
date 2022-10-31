.. _skarappapi:

SkarApp API
==========

.. index:: SkarApp

The SkarApp is an application to support a cyclist.
The main function is to have two drones following the
remote that the cyclist carries, Skaramote, providing dynamic spotlights on the road.


Communication
-------------

.. index:: SkarApp, Communication

TYRApp extends the drone application library to support the TYRAmote,
:ref:`appapi`. The extended API is described in this chapter.

.. index:: SkarApp: Ctrl-link API

SkarApp Extension API
---------------------

Information is carried by JSON objects that are sent over the ZeroMQ
REQ/REP interface.

.. _followher:

Fcn: follow_her
~~~~~~~~~~~~~~

The function "follow_her" is called when the user wants to connect drones.

Prior to calling "follow_her" an LLA
stream should be enabled on her dynamic publish-socket.

The flight pattern used is "above", where relative altitude is specified as a parameter in the config file.

The message contains a key "enable" to enable or disable the following
and the key "capabilities" which is a list of capabilities that the drones need to have

.. code-block:: json
  :caption: Request: **follow_her**
  :linenos:

  {
    "fcn": "follow_her",
    "id": "<appliction support id>",
    "enable": "TRUE/FALSE BOOLEAN",
    "target_id": "da001"
    "capabilities": ["SPOTLIGHT"]
  }

**Nack reasons:**
  - requester is not the assigned SkarApp
