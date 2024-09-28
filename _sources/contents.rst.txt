.. toctree::
    :caption: General Info
    :hidden:
    :maxdepth: 1

    Home<index.md>
    examples.md
    UI.md

.. autosummary::
    :caption: User Documentation
    :toctree: _autosummary
    :template: custom-module-template.rst
    :recursive:

    netunicorn.base
    netunicorn.client

.. toctree::
    :caption: Administrator Documentation
    :hidden:
    :maxdepth: 1

    administrator_docs/deployment
    administrator_docs/connectors
    administrator_docs/users
    administrator_docs/database

.. toctree::
    :caption: Design Documentation
    :hidden:
    :maxdepth: 1

    design_docs/index
    design_docs/director/index
    design_docs/frontend/index
    design_docs/target/index