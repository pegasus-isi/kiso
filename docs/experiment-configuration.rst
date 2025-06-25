Experiment Configuration
========================

Example
-------

.. code-block:: yaml

   name: first-experiment
   condor:
   central-manager:
      roles:
         - master
      config_file: condor_config
   execute:
      roles:
         - execute
      config_file: condor_config
   # execute-1:
   #   roles:
   #     - execute
   #   config_file: condor_config
   submit:
      roles:
         - submit
      config_file: condor_config
   # submit-1:
   #   ...
   minicondor:
      roles:
         - mini
      # config_file: condor_config
   docker:
   roles:
      - mini
   apptainer:
   roles:
      - mini
   sites:
   # - type: fabric
   #   user: root
   #   rc_file: fabric.sh
   #   walltime: "01:10:10"
   #   resources:
   #     machines:
   #       - roles:
   #           - submit
   #         # flavour: "large"
   #         flavour_desc:
   #           core: 2
   #           mem: 4
   #         number: 1
   #     networks:
   #       - roles:
   #           - r1
   #         cidr: "172.16.42.0/16"
   # - type: chameleon-edge
   #   lease_name: mayani-edge
   #   rc_file: edge-app-cred-oac-edge-openrc.sh
   #   resources:
   #     machines:
   #       - roles:
   #         - client
   #         device_name: iot-rpi4-03
   #         container:
   #           name: clicontainer
   #           image: arm64v8/ubuntu
   - type: vagrant
      backend: virtualbox
      box: bento/rockylinux-9
      # box: bento/ubuntu-22.04
      user: vagrant
      config_extra: 'config.vm.synced_folder ".", "/vagrant", disabled: true'
      resources:
         machines:
         - roles:
               - master
            backend: virtualbox
            box: bento/rockylinux-9
            # box: bento/ubuntu-22.04
            user: vagrant
            config_extra_vm: 'my.vm.synced_folder ".", "/vagrant", disabled: true'
            flavour: "large"
            number: 1
         - roles:
               - execute
            flavour: "large"
            number: 1
         - roles:
               - submit
            flavour: "large"
            number: 1
         - roles:
               - mini
            flavour: "large"
            number: 1
         networks:
         - roles:
               - r1
            cidr: "172.16.42.0/16"
   # - type: chameleon
   #   walltime: "01:00:00"
   #   lease_name: lease-name
   #   rc_file: tacc-app-cred-oac-edge-openrc.sh
   #   key_name: mayani-mac-mini
   #   image: CC-Ubuntu18.04
   #   resources:
   #     machines:
   #       - roles:
   #           - submit
   #           - execute
   #         flavour: compute_zen3
   #         number: 1
   #         image: CC-Ubuntu22.04
   #       # - roles:
   #       #     - execute
   #       #   flavour: compute_zen3
   #       #   number: 1
   #         # image: CC-CentOS8
   #     networks:
   #       - sharednet1
   experiments:
   - name: orcasound-experiment
      count: 10
      main: echo
      args:
         - arg-1
         - arg-2
         - arg-3
      submit-node-roles:
         - submit
      setup:
         - roles:
            - submit
         executable: /bin/bash
         script: |
            #!/bin/bash
            echo "Setup script here"
            rm -rf submit-machine
            mkdir submit-machine
         - roles:
            - execute
         script: |
            #!/bin/bash
            echo "Setup script here"
      input_locations:
         - roles:
            - submit
         src: NOTES.md
         dst: submit-machine
      result_locations:
         - roles:
            - submit
         src: /home/vagrant/VBoxGuestAdditions_7.1.6.iso
         dst: local-machine



.. .. literalinclude:: ../experiment.yml
..    :language: yaml

Schema
------

.. jsonschema:: kiso.schema.SCHEMA
