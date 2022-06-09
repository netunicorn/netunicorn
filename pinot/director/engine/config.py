from typing import Literal

from pinot.director.engine.deployer_connectors.salt_connector import SaltConnector
from pinot.director.engine.deployer_connectors.mininet_draft import MininetConnector

environment_type: Literal['shell', 'docker'] = 'shell'
ConnectorClass = MininetConnector

# set deployer connector
deployer_connector = ConnectorClass()
