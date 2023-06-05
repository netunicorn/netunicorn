# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys

sys.path.insert(0, os.path.abspath("../../.."))  # Source code dir relative to this file
sys.path.insert(0, os.path.abspath("../../../netunicorn-base/src/netunicorn"))
sys.path.insert(0, os.path.abspath("../../../netunicorn-client/src/netunicorn"))

project = "netunicorn"
copyright = "2023, Roman Beltiukov"
author = "Roman Beltiukov"
release = "0.3"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",  # Core library for html generation from docstrings
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
    "sphinx.ext.autosummary",  # Create neat summary tables
    "sphinx.ext.linkcode",
    "myst_parser",
]

autodoc_default_options = {
    "member-order": "bysource",
}

autosummary_generate = True
html_show_sourcelink = False
autodoc_inherit_docstrings = True
set_type_checking_flag = True
add_module_names = False
toc_object_entries = False
typehints_fully_qualified = False
always_document_param_types = True
typehints_use_rtype = False
typehints_defaults = "comma"


autodoc_mock_imports = ["netunicorn.library", "netunicorn.executor", "typing", "pydantic"]

templates_path = ["_templates"]
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]


def linkcode_resolve(domain, info):
    if domain != 'py':
        return None
    if not info['module']:
        return None
    filename = info['module'].replace('.', '/')
    package = '-'.join(info['module'].split('.')[0:2])
    fullname = info['fullname'].split('.')[-1]
    return f"https://github.com/netunicorn/netunicorn/tree/main/{package}/src/{filename}.py#:~:text={fullname}"


def autodoc_skip_member(app, what, name, obj, skip, options):
    if what == "method" and hasattr(obj, '__objclass__') and obj.__objclass__ == dict:
        return True
    return None


def setup(app):
    app.connect('autodoc-skip-member', autodoc_skip_member)
