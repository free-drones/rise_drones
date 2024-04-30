import json
import logging
import sys
from pathlib import Path

# --------------------------------------------------------------------#

__author__ = "Lennart Ochel <>, Andreas Gising <andreas.gising@ri.se>, Kristoffer Bergman <kristoffer.bergman@ri.se>, Hanna Müller <hanna.muller@ri.se>, Joel Nordahl"
__version__ = "1.0.0"
__copyright__ = "Copyright (c) 2022, RISE"
__status__ = "development"

# --------------------------------------------------------------------#

_logger = logging.getLogger(__name__)

# --------------------------------------------------------------------#

config = {}


def _init():

    paths = [
        Path.home().joinpath(".rise_drones", ".config"),
        Path.cwd().parent.joinpath(".config"),
        Path.cwd().joinpath(".config"),
    ]
    for path in paths:
        if path.is_file():
            print(f'Configuration file found at "{path}"')
            with open(path) as json_file:
                config.update(json.load(json_file))
                config["config_file_path"] = path
            return

    print(f"No configuration file found at {paths}")
    print("Terminate because no configuration was found")
    sys.exit(0)