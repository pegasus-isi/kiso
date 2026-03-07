Concepts
========

Sites
-----

In this section, we define the resources to be provisioned on the different sites/testbeds for the experiment. Currently we support the following testbeds.

FABRIC
~~~~~~

.. note::

  pip install kiso[fabric] # Install Kiso with FABRIC

Example
'''''''

.. code-block:: yaml

  sites:
    - kind: fabric
      rc_file: secrets/fabric_rc
      walltime: "02:00:00"
      resources:
        machines:
          - labels:
              - submit
            site: FIU
            image: default_rocky_8
            flavour: big
            number: 1
            gpus:
              - model: TeslaT4
            storage:
              - kind: NVME
                model: P4510
                mount_point: /mnt/nvme
              - kind: Storage
                model: NAS
                name: kiso-fabric-integration
                auto_mount: true
        networks:
          - labels:
              - v4
            kind: FABNetv4
            site: FIU
            nic:
              kind: SharedNIC
              model: ConnectX-6

.. hint::

   For a complete schema reference see :ref:`fabric-schema`

Vagrant
~~~~~~~

.. note::

  pip install kiso[vagrant] # Install Kiso with Vagrant

Example
'''''''

.. code-block:: yaml

  sites:
    - kind: vagrant
      backend: virtualbox
      box: bento/rockylinux-9
      user: vagrant
      config_extra: 'config.vm.synced_folder ".", "/vagrant", disabled: true'
      resources:
        machines:
          - labels:
              - execute
            backend: virtualbox
            box: bento/rockylinux-9
            user: vagrant
            flavour: "large"
            number: 2
        networks:
          - labels:
              - r1
            cidr: "172.16.42.0/16"

.. hint::

   For a complete schema reference see :ref:`vagrant-schema`

Chameleon
~~~~~~~~~

.. note::

  pip install kiso[chameleon] # Install Kiso with Chameleon

Example
'''''''

.. code-block:: yaml

  sites:
    - kind: chameleon
      walltime: "04:00:00"
      lease_name: tacc-lease
      rc_file: secrets/chi-tacc-app-cred-openrc.sh
      key_name: mayani-mac-mini
      image: CC-Ubuntu18.04
      resources:
        machines:
          - labels:
              - submit
            flavour: compute_zen3
            number: 2
            image: CC-Ubuntu22.04
        networks:
          - sharednet1

.. hint::

   For a complete schema reference see :ref:`chameleonkvm-schema`

Chameleon Edge
~~~~~~~~~~~~~~

.. note::

  pip install kiso[chameleon] # Install Kiso with Chameleon

Example
'''''''

.. code-block:: yaml

  sites:
    - kind: chameleon-edge
      walltime: "04:00:00"
      lease_name: edge-lease
      rc_file: secrets/chi-edge-app-credopenrc.sh
      resources:
        machines:
          - labels:
              - central-manager
            machine_name: raspberrypi4-64
            count: 1
            container:
              name: execute
              image: rockylinux:8

.. hint::

   For a complete schema reference see :ref:`chameleonedge-schema`

Software
--------

In this section, we define the software to be installed on the provisioned resources. Currently, we support installing `Docker <https://www.docker.com/>`_, `Apptainer <https://apptainer.org/>`_, and `Ollama <http://ollama.com/>`_.

Apptainer
~~~~~~~~~

Example
'''''''

.. code-block:: yaml

  software:
    apptainer:
      labels:
        - submit


.. hint::

   For a complete schema reference see :ref:`apptainer-schema`

Docker
~~~~~~

Example
'''''''

.. code-block:: yaml

  software:
    docker:
      labels:
        - submit

.. hint::

   For a complete schema reference see :ref:`docker-schema`

Ollama
~~~~~~

Example
'''''''

.. code-block:: yaml

  software:
    ollama:
      - labels:
          - large-model
        models:
          - gpt-oss:20b
        variables:
          - OLLAMA_MAX_QUEUE: 512

      - labels:
          - small-model
        models:
          - qwen3.5:2b
        variables:
          - OLLAMA_CONTEXT_LENGTH: 8192

.. hint::

   For a complete schema reference see :ref:`ollama-schema`

Deployment
----------

In this section, we define the cluster to be deployed on the provisioned resources. Currently, we support deploying `HTCondor <https://htcondor.org/>`_.

HTCondor
~~~~~~~~

Example
'''''''

.. code-block:: yaml

  deployment:
    htcondor:
      - kind: central-manager
        labels:
          - central-manager
        # Optionally, define a custom Condor configuration file
        # config_file: config/cm-condor_config

      # Optionally, define on or more execute nodes configurations
      - kind: execute
        labels:
          - execute
        # Optionally, define a custom Condor configuration file
        # config_file: config/exec-condor_config

      # Optionally, define on or more execute nodes configurations
      - kind: submit
        labels:
          - submit
        # Optionally, define a custom Condor configuration file
        # config_file: config/submit-condor_config

      # Optionally, define one or more personal HTCondor nodes configurations
      - kind: personal
        labels:
          - edge-1
      #   Optionally, define a custom Condor configuration file
      #   config_file: config/personal-condor_config

.. hint::

   For a complete schema reference see :ref:`htcondor-schema`

Experiments
-----------

In this section, we define the experiments to be run on the provisioned resources. Currently we support the following experiment types.

Shell
~~~~~

Example
'''''''

.. code-block:: yaml

  experiments:
    - kind: shell
      name: shell-experiment
      description: An experiment to print a message
      # Optionally, specify output files and on which node to copy them from after the experiment
      inputs:
        - labels:
            - submit
          src: name.txt
          dst: ~kiso

      # Specify what scripts to run and on which node to run them on
      scripts:
        - labels:
            - submit
          script: |
            #!/bin/bash
            echo "Hello, world!" | tee hello.txt

      # Optionally, specify output files and on which node to copy them from after the experiment
      outputs:
        - labels:
            - submit
          src: hello.txt
          dst: output

.. hint::

   For a complete schema reference see :ref:`shell-schema`

Pegasus
~~~~~~~

Example
'''''''

.. code-block:: yaml

  experiments:
    - kind: pegasus
        name: process-experiment
        description: A Pegasus workflow
        # Number of time to run the experiment
        count: 1
        # Script to run the Pegasus workflow
        main: bin/main.sh
        # The node from which the workflow will be submitted
        submit_node_labels:
          - submit

        # Optionally, specify input files and on which node to copy them on to setup the environment
        # By default, the directory containing the experiment.yml file will be copied to all provisioned nodes
        inputs:
          - labels:
              - execute
            src: README.md
            dst: ~kiso/kiso-process-experiment

        # Optionally, specify what scripts to run and on which node to run them on to setup the environment
        setup:
          - labels:
              - submit
            executable: /bin/bash
            script: |
              #!/bin/bash
              echo "Setup script here"

        # Optionally, specify what scripts to run and on which node to run them on after the environment
        post_scripts:
          - labels:
              - submit
            executable: /bin/bash
            script: |
              #!/bin/bash
              echo "Post script here"

        # Optionally, specify output files and on which node to copy them from after the experiment
        # By default, the Pegasus workflow submit directory will be copied to the local machine
        outputs:
          - labels:
              - submit
            src: ~kiso/kiso-process-experiment
            dst: local-machine

.. hint::

   For a complete schema reference see :ref:`pegasus-schema`

Advanced Multi-Site Experiment
------------------------------

.. literalinclude:: _static/examples/kiso-plankifier-experiment.yml
   :language: yaml
