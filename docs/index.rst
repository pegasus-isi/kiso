Kiso documentation
==================

Kiso is a config-driven experiment management platform that helps researchers
run reproducible experiments across academic testbeds (Vagrant, FABRIC,
Chameleon). The same config file runs locally and on real testbeds with minimal changes.

.. toctree::
   :maxdepth: 1
   :caption: Introduction

   introduction/introduction.md
   introduction/getting-started.md

.. toctree::
   :maxdepth: 2
   :caption: Tutorials

   tutorials/first-experiment
   tutorials/multi-testbed

.. toctree::
   :maxdepth: 2
   :caption: Concepts

   concepts/what-is-kiso
   concepts/experiment-model
   concepts/config-anatomy
   concepts/components

.. toctree::
   :maxdepth: 2
   :caption: How-to guides

   how-to/testbeds/fabric
   how-to/testbeds/vagrant
   how-to/testbeds/chameleon
   how-to/testbeds/chameleon-edge
   how-to/software/docker
   how-to/software/apptainer
   how-to/software/ollama
   how-to/deployments/htcondor
   how-to/experiment-types/shell
   how-to/experiment-types/pegasus
   how-to/collect-results

.. toctree::
   :maxdepth: 2
   :caption: Extending Kiso

   extending/how-extensions-work
   extending/add-software
   extending/add-deployment
   extending/add-experiment-type
   extending/reference/software-interface
   extending/reference/deployment-interface
   extending/reference/experiment-type-interface

.. toctree::
   :maxdepth: 1
   :caption: Experiment gallery

   examples/index
   examples/pydantic-agent
   examples/plankifier
   examples/orcasound
   examples/colmena

.. toctree::
   :maxdepth: 2
   :caption: Reference

   reference/config
   reference/cli
   reference/testbed-parameters
   reference/output-formats
   reference/api
   reference/glossary
   reference/changelog

.. toctree::
   :maxdepth: 1
   :caption: About

   about/contributing
   about/contact
   about/funding
   about/license
   about/citing
   about/external-links
