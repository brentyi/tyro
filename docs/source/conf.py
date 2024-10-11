# -*- coding: utf-8 -*-
#
# Configuration file for the Sphinx documentation builder.
#
# This file does only contain a selection of the most common options. For a
# full list see the documentation:
# http://www.sphinx-doc.org/en/stable/config

from typing import Dict, List

import m2r2

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#

# -- Project information -----------------------------------------------------

project = "tyro"
copyright = "2022"
author = "brentyi"

# The short X.Y version
version = ""
# The full version, including alpha/beta/rc tags
release = ""


# -- General configuration ---------------------------------------------------

napoleon_numpy_docstring = False  # Force consistency, leave only Google
napoleon_use_rtype = False  # More legible

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    #  "sphinx.ext.mathjax",
    "sphinx.ext.githubpages",
    "sphinx.ext.napoleon",
    # "sphinx.ext.inheritance_diagram",
    "autoapi.extension",
    "sphinx.ext.viewcode",
    "m2r2",
    "sphinxcontrib.programoutput",
    "sphinxcontrib.ansi",
    "sphinxcontrib.googleanalytics",
]
programoutput_use_ansi = True
html_ansi_stylesheet = "black-on-white.css"
html_static_path = ["_static"]
html_theme_options = {
    "light_css_variables": {
        "color-code-background": "#f4f4f4",
        "color-code-foreground": "#000",
    },
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/brentyi/tyro",
            "html": """
            <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16">
                <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path>
            </svg>
        """,
            "class": "",
        },
    ],
    "light_logo": "logo-light.svg",
    "dark_logo": "logo-dark.svg",
}

# Pull documentation types from hints
autodoc_typehints = "both"

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
source_suffix = [".rst", ".md"]
# source_suffix = ".rst"

# The master toctree document.
master_doc = "index"

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language: str = "en"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path .
exclude_patterns: List[str] = []

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "monokai"


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "furo"
html_title = "tyro"


# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
#
# html_theme_options = {}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# Custom sidebar templates, must be a dictionary that maps document names
# to template names.
#
# The default sidebars (for documents that don't match any pattern) are
# defined by theme itself.  Builtin themes are using these templates by
# default: ``['localtoc.html', 'relations.html', 'sourcelink.html',
# 'searchbox.html']``.
#
# html_sidebars = {}


# -- Options for HTMLHelp output ---------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = "tyro_doc"


# -- Options for Github output ------------------------------------------------

sphinx_to_github = True
sphinx_to_github_verbose = True
sphinx_to_github_encoding = "utf-8"


# -- Options for LaTeX output ------------------------------------------------

latex_elements: Dict[str, str] = {
    # The paper size ('letterpaper' or 'a4paper').
    #
    # 'papersize': 'letterpaper',
    # The font size ('10pt', '11pt' or '12pt').
    #
    # 'pointsize': '10pt',
    # Additional stuff for the LaTeX preamble.
    #
    # 'preamble': '',
    # Latex figure (float) alignment
    #
    # 'figure_align': 'htbp',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    (
        master_doc,
        "tyro.tex",
        "tyro",
        "brentyi",
        "manual",
    ),
]


# -- Options for manual page output ------------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [(master_doc, "tyro", "tyro documentation", [author], 1)]


# -- Options for Texinfo output ----------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    (
        master_doc,
        "tyro",
        "tyro",
        author,
        "tyro",
        "tyro",
        "Miscellaneous",
    ),
]


# -- Extension configuration --------------------------------------------------

# -- Google analytics ID ------------------------------------------------------
googleanalytics_id = "G-624W9VWZWK"

# -- Options for autoapi extension --------------------------------------------
autoapi_dirs = ["../../src/tyro"]
autoapi_root = "api"
autoapi_options = [
    "members",
    "undoc-members",
    "imported-members",
    "show-inheritance",
    # "show-inheritance-diagram",
    "special-members",
    #  "show-module-summary",
]
autoapi_add_toctree_entry = False

# # Generate name aliases
# def _gen_name_aliases():
#     """Generate a name alias dictionary, which maps private names to ones in the public
#     API. A little bit hardcoded/hacky."""
#
#     name_alias = {}
#
#     def recurse(module, prefixes):
#         if hasattr(module, "__name__") and module.__name__.startswith("tyro"):
#             MAX_DEPTH = 5
#             if len(prefixes) > MAX_DEPTH:
#                 # Prevent infinite loops from cyclic imports
#                 return
#         else:
#             return
#
#         for member_name in dir(module):
#             if member_name == "tyro":
#                 continue
#
#             member = getattr(module, member_name)
#             if callable(member):
#                 full_name = ".".join(["tyro"] + prefixes + [member_name])
#
#                 shortened_name = "tyro"
#                 current = tyro
#                 success = True
#                 for p in prefixes + [member_name]:
#                     if p.startswith("_"):
#                         continue
#                     if not hasattr(current, p):
#                         success = False
#                         break
#                     current = getattr(current, p)
#                     shortened_name += "." + p
#
#                 if success and shortened_name != full_name:
#                     if full_name in name_alias:
#                         assert full_name == name_alias[shortened_name], full_name
#                     else:
#                         name_alias[full_name] = shortened_name
#             elif not member_name.startswith("__"):
#                 recurse(member, prefixes + [member_name])
#
#     import tyro
#
#     recurse(tyro, prefixes=[])
#     return name_alias
#
#
# _name_aliases = _gen_name_aliases()
#
# # Set inheritance_alias setting for inheritance diagrams
# inheritance_alias = _name_aliases
#
#
# def _apply_name_aliases(name: Optional[str]) -> Optional[str]:
#     if name is None:
#         return None
#
#     name = name.strip()
#
#     if "[" in name:
#         # Generics.
#         name, _, suffix = name.partition("[")
#         assert suffix[-1] == "]"
#         suffix = suffix[:-1]
#         if "," in suffix:
#             suffix = ", ".join(_apply_name_aliases(x) for x in suffix.split(","))  # type: ignore
#         else:
#             suffix = _apply_name_aliases(suffix)  # type: ignore
#         suffix = "[" + suffix + "]"
#     else:
#         suffix = ""
#
#     if name in _name_aliases:
#         name = _name_aliases[name]
#
#     return name + suffix  # type: ignore
#
#
# # Apply our inheritance alias to autoapi base classes
# def _override_class_documenter():
#     import autoapi
#
#     orig_init = autoapi.mappers.python.PythonClass.__init__
#
#     def __init__(self, obj, **kwargs):
#         bases = obj["bases"]
#         for i in range(len(bases)):
#             bases[i] = _apply_name_aliases(bases[i])
#
#         args = obj["args"]
#         if args is not None:
#             for i in range(len(args)):
#                 assert isinstance(args[i], tuple) and len(args[i]) == 4
#                 args[i] = (
#                     args[i][0],
#                     args[i][1],
#                     _apply_name_aliases(args[i][2]),
#                     args[i][3],
#                 )
#         orig_init(self, obj, **kwargs)
#
#     autoapi.mappers.python.PythonClass.__init__ = __init__
#
#
# _override_class_documenter()
#
#
# # Apply our inheritance alias to autoapi type annotations
# def _override_function_documenter():
#     import autoapi
#
#     orig_init = autoapi.mappers.python.PythonFunction.__init__
#
#     def __init__(self, obj, **kwargs):
#         args = obj["args"]
#         if args is not None:
#             for i in range(len(args)):
#                 assert isinstance(args[i], tuple) and len(args[i]) == 4
#                 args[i] = (
#                     args[i][0],
#                     args[i][1],
#                     _apply_name_aliases(args[i][2]),
#                     args[i][3],
#                 )
#
#         obj["return_annotation"] = _apply_name_aliases(obj["return_annotation"])
#         orig_init(self, obj, **kwargs)
#
#     autoapi.mappers.python.PythonFunction.__init__ = __init__
#
#
# _override_function_documenter()
#
# # Apply our inheritance alias to autoapi attribute annotations
# def _override_attribute_documenter():
#     import autoapi
#
#     orig_init = autoapi.mappers.python.PythonAttribute.__init__
#
#     def __init__(self, obj, **kwargs):
#         obj["annotation"] = _apply_name_aliases(obj["annotation"])
#         orig_init(self, obj, **kwargs)
#
#     autoapi.mappers.python.PythonAttribute.__init__ = __init__
#
#
# _override_attribute_documenter()


# -- Options for todo extension ----------------------------------------------

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True

# -- Enable Markdown -> RST conversion ----------------------------------------


def docstring(app, what, name, obj, options, lines):
    md = "\n".join(lines)
    rst = m2r2.convert(md)
    lines.clear()
    lines += rst.splitlines()  # type: ignore


def setup(app):
    app.connect("autodoc-process-docstring", docstring)
    app.add_css_file("css/compact_table_header.css")
