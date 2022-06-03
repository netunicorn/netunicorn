from typing import Literal

from deployer_connectors.salt_connector import SaltLocalConnector

environment_type: Literal['shell', 'docker'] = 'shell'
ConnectorClass = SaltLocalConnector
