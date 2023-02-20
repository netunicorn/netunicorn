"""
Deployment preprocessors are preprocessors that are applied to a deployment map before actual deployment.
They exist to modify the deployment map in some way
(for example - add a new service to the deployment map, change routing or ACL, etc.)
This module allows to add external preprocessors.
# TODO: allow to add external preprocessors (not implemented yet :D)
"""

from typing import List

from netunicorn.base.experiment import Experiment


class BasePreprocessor:
    def __call__(self, experiment: Experiment) -> Experiment:
        return experiment


experiment_preprocessors: List[BasePreprocessor] = []
