# REST API connector
TODO: documentation

This connector is used to connect to other netunicorn connectors that are hosted as a default REST API service.

This allows you to deploy a netunicorn connector on a separate host to increase security or provide additional capabilities.

## Configuration
You are required to specify a valid configuration string during connector initialization.  
A valid string is a JSON-serialized object with the following structure:
```json
{
  "url": "https://connector.url/",
  "api_key": "preshared_api_key (usually NETUNICORN_API_KEY on the other side)",
  "init_params": {
    "netunicorn_gateway": "netunicorn_gateway address",
    "param1": "value1",
    "param2": "value2",
    "these params": "would be passed to the remote connector during initialization"
  }
}

```