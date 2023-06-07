Documentation for netunicorn
======================================

Welcome to the documentation for netunicorn. This documentation is
divided into two parts: user documentation and system design.

-----------------------
User documentation
-----------------------
User documentation provides information on public netunicorn API (i.e., classes and functions),
such as tasks, environment definitions, pipelines, experiments, nodes, etc.

.. autosummary::
   :caption: User Documentation
   :toctree: _autosummary
   :template: custom-module-template.rst
   :recursive:

   netunicorn.base
   netunicorn.client


-----------------------
Design documentation
-----------------------

Design documentation describes the internal structure and ideas behind architecture of the system.

See the sidebar for the full documentation.


.. toctree::
   :caption: Design Documentation
   :hidden:
   :maxdepth: 1

   design_docs/index
   design_docs/director/index
   design_docs/frontend/index
   design_docs/target/index

