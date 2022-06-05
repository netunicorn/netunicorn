from typing import Literal

from pinot.director.engine.deployer_connectors.salt_connector import SaltConnector

environment_type: Literal['shell', 'docker'] = 'shell'
ConnectorClass = SaltConnector

# set deployer connector
deployer_connector = ConnectorClass()
