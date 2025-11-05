# noqa: D100

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

from datetime import datetime

project = "Kiso"
copyright = str(datetime.now().year)
author = "Rajiv Mayani"
release = "0.1.0a4"
repository_url = "https://github.com/pegasus-isi/kiso"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.ifconfig",
    "sphinx.ext.viewcode",
    "sphinx_tabs.tabs",
    "sphinx_click.ext",
    "sphinx-jsonschema",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
# source_suffix = ".rst"
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output
# https://sphinx-book-theme.readthedocs.io/en/stable/reference.html

html_theme = "sphinx_book_theme"
html_logo = "_static/assets/images/logo-kiso.png"
html_favicon = "_static/assets/images/logo-kiso.png"
html_title = "Kiso"
html_static_path = ["_static"]
html_theme_options = {
    "path_to_docs": "docs",
    "repository_url": repository_url,
    "repository_branch": "main",
    "use_edit_page_button": True,
    "use_source_button": True,
    "use_issues_button": True,
    # "use_repository_button": True,
    "use_download_button": True,
    "use_sidenotes": True,
    "show_toc_level": 2,
    # "announcement": "⚠️ Announcement",
    "logo": {
        "image_light": "_static/assets/images/logo-kiso.png",
        # "image_dark": "_static/assets/images/logo-kiso.png",
        "alt_text": "Kiso - Home",
        # "text": html_title,  # Uncomment to try text with logo
    },
    "icon_links": [
        {
            "name": "GitHub",
            "url": repository_url,
            "icon": "fa-brands fa-github",
        },
        {
            "name": "PyPI",
            "url": "https://pypi.org/project/kiso/",
            "icon": "https://img.shields.io/pypi/dw/kiso",
            "type": "url",
        },
    ],
}
html_css_files = [
    "assets/css/custom.css",
]
jsonschema_options = {
    "lift_title": True,
    "lift_description": True,
    "lift_definitions": True,
    "auto_target": True,
    "auto_reference": True,
}
