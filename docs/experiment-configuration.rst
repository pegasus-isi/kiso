Experiment Configuration
========================

Concepts
--------

Sites
~~~~~

In this section, we define the resources to be provisioned on the different sites/testbeds for the experiment.

Software
~~~~~~~~

In this section, we define the software to be installed on the provisioned resources. Currently, we support installing [Docker](https://www.docker.com/) and [Apptainer](https://apptainer.org/).

Deployment
~~~~~~~~~~

In this section, we define the cluster to be deployed on the provisioned resources. Currently, we support deploying [HTCondor](https://htcondor.org/).

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

.. jsonschema:: enoslib.infra.enos_vagrant.schema.SCHEMA

.. jsonschema:: enoslib.infra.enos_chameleonkvm.schema.SCHEMA

.. jsonschema:: enoslib.infra.enos_chameleonedge.schema.SCHEMA

.. .. jsonschema:: enoslib.infra.enos_fabric.schema.SCHEMA

.. jsonschema:: kiso.workflow.__init__.SCHEMA
  :hide_key: /**/variables

.. jsonschema:: kiso.schema.COMMONS_SCHEMA
  :hide_key: /**/variables
