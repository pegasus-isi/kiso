Experiment Configuration
========================

Concepts
--------

Sites
~~~~~

In this section, we define the resources to be provisioned on the different sites/testbeds for the experiment.

Software
~~~~~~~~

In this section, we define the software to be installed on the provisioned resources. Currently, we support installing `Docker <https://www.docker.com/>`_, `Apptainer <https://apptainer.org/>`_, and `Ollama <http://ollama.com/>`_.

Deployment
~~~~~~~~~~

In this section, we define the cluster to be deployed on the provisioned resources. Currently, we support deploying `HTCondor <https://htcondor.org/>`_.

Experiments
~~~~~~~~~~~

In this section, we define the experiments to be run on the provisioned resources.

Example
-------

.. literalinclude:: _static/examples/kiso-plankifier-experiment.yml
   :language: yaml


Schema
------

.. jsonschema:: kiso.schema.SCHEMA
  :hide_key: /**/variables

.. Supported testbeds

.. jsonschema:: enoslib.infra.enos_vagrant.schema.SCHEMA

.. jsonschema:: enoslib.infra.enos_chameleonkvm.schema.SCHEMA

.. jsonschema:: enoslib.infra.enos_chameleonedge.schema.SCHEMA

.. jsonschema:: enoslib.infra.enos_fabric.schema.SCHEMA

.. Supported software

.. jsonschema:: kiso.apptainer.schema.SCHEMA

.. jsonschema:: kiso.docker.schema.SCHEMA

.. jsonschema:: kiso.ollama.schema.SCHEMA

.. Supported deployments

.. jsonschema:: kiso.htcondor.schema.SCHEMA

.. Supported experiment types

.. jsonschema:: kiso.shell.schema.SCHEMA
  :hide_key: /**/variables, /**/script, /**/location

.. jsonschema:: kiso.pegasus.schema.SCHEMA
  :hide_key: /**/variables, /**/script, /**/location

.. jsonschema:: kiso.schema.COMMONS_SCHEMA
