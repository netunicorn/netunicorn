# netunicorn infrastructure module
This module is responsible for connection to deployment systems
via system-specific connectors.

## Installation
```bash
pip install netunicorn-director-infrastructure
```

Then, install all required connectors (specific to your infrastructure)

## Usage
Start the infrastructure module with the following command:
```bash
python -m netunicorn.director.infrastructure -f /path/to/config.yml
```

See confiuration-example.yml for configuration example.