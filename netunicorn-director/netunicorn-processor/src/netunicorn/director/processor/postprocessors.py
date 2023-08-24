"""
Postprocessors are called when an experiment goes to Unknown or Finished states.
They allow to perform some actions after the experiment is finished (e.g., cleanup the external resources).
This module allows to add external postprocessors.

All postprocessors must be placed in the folder specified by the NETUNICORN_POSTPROCESSORS_FOLDER environment variable.
Postprocessors must be placed in separate files and must be subclasses of the BasePostprocessor class.
All postprocessor classes would be imported and instantiated in a lexical order of filenames.
"""

import importlib.util
import os
import sys
from typing import List

from netunicorn.director.base.resources import get_logger
from netunicorn.director.base.types import BasePostprocessor

POSTPROCESSORS_FOLDER = os.environ.get(
    "NETUNICORN_POSTPROCESSORS_FOLDER", "/netunicorn/postprocessors"
)

experiment_postprocessors: List[BasePostprocessor] = []
logger = get_logger("netunicorn.director.processor")


def import_postprocessors(
    filename: str, postprocessors: List[BasePostprocessor]
) -> None:
    logger.debug(f"Importing postprocessor {filename}")

    file_path = os.path.join(POSTPROCESSORS_FOLDER, filename)
    module_name = filename[:-3]
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    for name, obj in module.__dict__.items():
        if (
            isinstance(obj, type)
            and issubclass(obj, BasePostprocessor)
            and obj is not BasePostprocessor
        ):
            logger.debug(f"Found postprocessor {name}")
            postprocessors.append(obj())
            logger.info(f"Postprocessor object {name} imported")

    logger.debug(f"Postprocessor file {filename} imported")


if os.path.exists(POSTPROCESSORS_FOLDER):
    postprocessor_files = [
        x for x in os.listdir(POSTPROCESSORS_FOLDER) if x.endswith(".py")
    ]
    postprocessor_files.sort()
    for postprocessor_file in postprocessor_files:
        try:
            import_postprocessors(postprocessor_file, experiment_postprocessors)
        except Exception as e:
            logger.error(f"Failed to import postprocessor {postprocessor_file}: {e}")
            continue
else:
    logger.info(
        f"Postprocessors folder {POSTPROCESSORS_FOLDER} does not exist, skipping postprocessors initialization"
    )
