from typing import Literal

from pinot.director.engine.deployer_connectors.salt_connector import SaltLocalConnector

environment_type: Literal['shell', 'docker'] = 'shell'
ConnectorClass = SaltLocalConnector

# set deployer connector
deployer_connector = ConnectorClass()
