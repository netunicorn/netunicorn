"""
Deployment preprocessors are preprocessors that are applied to a deployment map before actual deployment.
They exist to modify the deployment map in some way
(for example - add a new service to the deployment map, change routing or ACL, etc.)
This module allows to add external preprocessors.

All preprocessors must be placed in the folder specified by the NETUNICORN_PREPROCESSORS_FOLDER environment variable.
Preprocessors must be placed in separate files and must be subclasses of the BasePreprocessor class.
All preprocessor classes would be imported and instantiated in a lexical order of filenames.
"""

import importlib.util
import os
import sys
from typing import List

from netunicorn.director.base.resources import get_logger
from netunicorn.director.base.types import BasePreprocessor

PREPROCESSORS_FOLDER = os.environ.get(
    "NETUNICORN_PREPROCESSORS_FOLDER", "/netunicorn/preprocessors"
)

experiment_preprocessors: List[BasePreprocessor] = []
logger = get_logger("netunicorn.director.mediator")


def import_preprocessors(filename: str, preprocessors: List[BasePreprocessor]) -> None:
    logger.debug(f"Importing preprocessor {filename}")

    file_path = os.path.join(PREPROCESSORS_FOLDER, filename)
    module_name = filename[:-3]
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    for name, obj in module.__dict__.items():
        if (
            isinstance(obj, type)
            and issubclass(obj, BasePreprocessor)
            and obj is not BasePreprocessor
        ):
            logger.debug(f"Found preprocessor {name}")
            preprocessors.append(obj())
            logger.info(f"Preprocessor object {name} imported")

    logger.debug(f"Preprocessor file {filename} imported")


if os.path.exists(PREPROCESSORS_FOLDER):
    preprocessor_files = [
        x for x in os.listdir(PREPROCESSORS_FOLDER) if x.endswith(".py")
    ]
    preprocessor_files.sort()
    for preprocessor_file in preprocessor_files:
        try:
            import_preprocessors(preprocessor_file, experiment_preprocessors)
        except Exception as e:
            logger.error(f"Failed to import preprocessor {preprocessor_file}: {e}")
            continue
else:
    logger.info(
        f"Preprocessors folder {PREPROCESSORS_FOLDER} does not exist, skipping preprocessors initialization"
    )
