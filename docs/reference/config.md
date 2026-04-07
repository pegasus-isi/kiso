# Config file reference

Every configuration key Kiso supports, organised by section.

## Complete annotated example

```yaml
name: my-experiment

sites:
  - kind: vagrant
    resources:
      machines:
        - labels: [compute]
          flavour: small
          number: 1
      networks:
        - cidr: 172.16.42.0/16
          labels: [net1]

software:
  docker:
    labels: [compute]
  apptainer:
    labels: [compute]
  ollama:
    - labels: [compute]
      models: [llama3]

deployment:
  htcondor:
    - kind: personal
      labels: [compute]

experiments:
  - kind: shell
    name: my-shell
    scripts:
      - labels: [compute]
        script: echo hello

  - kind: pegasus
    name: my-workflow
    main: workflow.py
    submit_node_labels: [compute]
```

## Top-level keys

| Key           | Type   | Required | Default | Description                                |
| ------------- | ------ | -------- | ------- | ------------------------------------------ |
| `name`        | string | Yes      | —       | Human-readable name for the experiment     |
| `sites`       | list   | Yes      | —       | Infrastructure providers. Minimum 1 item.  |
| `experiments` | list   | Yes      | —       | Experiments to run. Minimum 1 item.        |
| `software`    | object | No       | —       | Software runtimes to install               |
| `deployment`  | object | No       | —       | Workload management system                 |
| `variables`   | object | No       | `{}`    | Global variables accessible in experiments |

## `sites[]` — Vagrant

| Key                                      | Type         | Required | Default              | Description                                                                                                               |
| ---------------------------------------- | ------------ | -------- | -------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `kind`                                   | string       | Yes      | —                    | Must be `"vagrant"`                                                                                                       |
| `backend`                                | string       | No       | `"libvirt"`          | VM hypervisor: `libvirt` or `virtualbox`                                                                                  |
| `box`                                    | string       | No       | `"generic/debian11"` | Base Vagrant box for all machines                                                                                         |
| `user`                                   | string       | No       | `"root"`             | SSH user for all machines                                                                                                 |
| `name_prefix`                            | string       | No       | `"enos"`             | Prefix for VM names                                                                                                       |
| `config_extra`                           | string       | No       | —                    | Extra Vagrant DSL config applied to all VMs                                                                               |
| `resources.machines[].labels`            | list[string] | Yes      | —                    | Labels to assign to these machines                                                                                        |
| `resources.machines[].flavour`           | string       | Yes\*    | —                    | Predefined size: `tiny`, `small`, `medium`, `big`, `large`, `extra-large`. \*One of `flavour` or `flavour_desc` required. |
| `resources.machines[].flavour_desc.core` | number       | Yes\*    | —                    | vCPUs (used with `flavour_desc`)                                                                                          |
| `resources.machines[].flavour_desc.mem`  | number       | Yes\*    | —                    | RAM in MB (used with `flavour_desc`)                                                                                      |
| `resources.machines[].number`            | integer      | No       | `1`                  | Number of VMs to provision                                                                                                |
| `resources.machines[].backend`           | string       | No       | site-level default   | Per-machine backend override                                                                                              |
| `resources.machines[].box`               | string       | No       | site-level default   | Per-machine box override                                                                                                  |
| `resources.machines[].user`              | string       | No       | site-level default   | Per-machine SSH user override                                                                                             |
| `resources.machines[].name_prefix`       | string       | No       | site-level default   | Per-machine VM name prefix                                                                                                |
| `resources.machines[].config_extra_vm`   | string       | No       | —                    | Extra Vagrant DSL config for this VM only                                                                                 |
| `resources.networks[].cidr`              | string       | Yes      | —                    | Network subnet in CIDR notation                                                                                           |
| `resources.networks[].labels`            | list[string] | Yes      | —                    | Labels for this network                                                                                                   |

## `sites[]` — FABRIC

| Key                                      | Type         | Required | Default             | Description                                                                                                               |
| ---------------------------------------- | ------------ | -------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `kind`                                   | string       | Yes      | —                   | Must be `"fabric"`                                                                                                        |
| `rc_file`                                | string       | Yes      | —                   | Path to the FABRIC RC credentials file                                                                                    |
| `walltime`                               | string       | No       | `"24:00:00"`        | Lease duration in `HH:MM` format                                                                                          |
| `site`                                   | string       | No       | `"UCSD"`            | Default FABRIC site for all resources                                                                                     |
| `image`                                  | string       | No       | `"default_rocky_8"` | Default OS image for all machines                                                                                         |
| `name_prefix`                            | string       | No       | `"fabric"`          | Prefix for provisioned resource names                                                                                     |
| `resources.machines[].labels`            | list[string] | Yes      | —                   | Labels to assign                                                                                                          |
| `resources.machines[].flavour`           | string       | Yes\*    | —                   | Predefined size: `tiny`, `small`, `medium`, `big`, `large`, `extra-large`. \*One of `flavour` or `flavour_desc` required. |
| `resources.machines[].flavour_desc.core` | integer      | Yes\*    | —                   | Number of cores (used with `flavour_desc`)                                                                                |
| `resources.machines[].flavour_desc.mem`  | integer      | Yes\*    | —                   | RAM in GB (used with `flavour_desc`)                                                                                      |
| `resources.machines[].flavour_desc.disk` | integer      | No       | —                   | Disk in GB (used with `flavour_desc`)                                                                                     |
| `resources.machines[].number`            | integer      | No       | `1`                 | Number of machines                                                                                                        |
| `resources.machines[].site`              | string       | No       | site-level default  | Per-machine site override                                                                                                 |
| `resources.machines[].image`             | string       | No       | site-level default  | Per-machine OS image override                                                                                             |
| `resources.networks[].labels`            | list[string] | Yes      | —                   | Labels for this network                                                                                                   |
| `resources.networks[].kind`              | string       | Yes      | —                   | Network type: `FABNetv4`, `FABNetv6`, `FABNetv4Ext`, `FABNetv6Ext`, `L2Bridge`, `L2STS`                                   |
| `resources.networks[].site`              | string       | Yes\*    | —                   | FABRIC site. Required for all types except `L2STS`.                                                                       |
| `resources.networks[].site_1`            | string       | Yes\*    | —                   | First site. `L2STS` only.                                                                                                 |
| `resources.networks[].site_2`            | string       | Yes\*    | —                   | Second site. `L2STS` only.                                                                                                |
| `resources.networks[].cidr`              | string       | No       | —                   | Subnet in CIDR notation. `L2Bridge` and `L2STS` only.                                                                     |

## `sites[]` — Chameleon bare metal

| Key                            | Type         | Required | Default            | Description                                                  |
| ------------------------------ | ------------ | -------- | ------------------ | ------------------------------------------------------------ |
| `kind`                         | string       | Yes      | —                  | Must be `"chameleon"`                                        |
| `rc_file`                      | string       | Yes      | —                  | Path to OpenRC credentials file                              |
| `key_name`                     | string       | Yes      | —                  | Name of SSH keypair registered in Chameleon                  |
| `lease_name`                   | string       | No       | `"enos-lease"`     | Name for the Chameleon lease                                 |
| `walltime`                     | string       | No       | `"02:00:00"`       | Lease duration in `HH:MM:SS` format                          |
| `image`                        | string       | No       | `"CC-Ubuntu18.04"` | Default OS image for all machines                            |
| `user`                         | string       | No       | `"cc"`             | Default SSH user                                             |
| `configure_network`            | boolean      | No       | `false`            | Whether to configure networking                              |
| `network.name`                 | string       | No       | `"sharednet1"`     | OpenStack network name                                       |
| `resources.machines[].labels`  | list[string] | Yes      | —                  | Labels to assign                                             |
| `resources.machines[].flavour` | string       | Yes      | —                  | OpenStack flavour name (e.g. `baremetal`, `compute_skylake`) |
| `resources.machines[].number`  | integer      | Yes      | —                  | Number of machines                                           |
| `resources.machines[].image`   | string       | No       | site default       | Per-machine OS image override                                |
| `resources.machines[].user`    | string       | No       | site default       | Per-machine SSH user override                                |
| `resources.networks`           | list[string] | No       | —                  | List of OpenStack network name strings                       |

## `sites[]` — Chameleon Edge

| Key                                              | Type         | Required | Default     | Description                                                                 |
| ------------------------------------------------ | ------------ | -------- | ----------- | --------------------------------------------------------------------------- |
| `kind`                                           | string       | Yes      | —           | Must be `"chameleon-edge"`                                                  |
| `rc_file`                                        | string       | Yes      | —           | Path to OpenRC credentials file                                             |
| `lease_name`                                     | string       | No       | `"EnOSlib"` | Name for the edge lease                                                     |
| `walltime`                                       | string       | No       | `"02:00"`   | Lease duration in `HH:MM` format                                            |
| `resources.machines[].labels`                    | list[string] | Yes      | —           | Labels to assign                                                            |
| `resources.machines[].machine_name`              | string       | Yes\*    | —           | Board/machine type (DeviceCluster). \*Required unless `device_name` is set. |
| `resources.machines[].count`                     | integer      | Yes\*    | —           | Number of devices (DeviceCluster). \*Required unless `device_name` is set.  |
| `resources.machines[].device_name`               | string       | Yes\*    | —           | Specific device hostname (Device). \*Required unless `machine_name` is set. |
| `resources.machines[].device_model`              | string       | No       | —           | Device model filter                                                         |
| `resources.machines[].container.name`            | string       | No       | —           | Container name                                                              |
| `resources.machines[].container.image`           | string       | No       | —           | Container image                                                             |
| `resources.machines[].container.exposed_ports`   | list[string] | No       | —           | Ports to expose (e.g. `["8080/tcp"]`)                                       |
| `resources.machines[].container.start`           | boolean      | No       | —           | Start container immediately                                                 |
| `resources.machines[].container.start_timeout`   | integer      | No       | —           | Seconds to wait for container to start                                      |
| `resources.machines[].container.device_profiles` | list[string] | No       | —           | Device profiles (e.g. GPU access)                                           |
| `resources.networks[].labels`                    | list[string] | Yes      | —           | Labels for this network                                                     |
| `resources.networks[].id`                        | string       | Yes      | —           | Network ID                                                                  |
| `resources.networks[].type`                      | string       | Yes      | —           | Must be `"prod"`                                                            |
| `resources.networks[].site`                      | string       | Yes      | —           | Chameleon site (e.g. `"CHI@Edge"`)                                          |

## `software.docker`

| Key       | Type         | Required | Default | Description                          |
| --------- | ------------ | -------- | ------- | ------------------------------------ |
| `labels`  | list[string] | Yes      | —       | Labels of nodes to install Docker on |
| `version` | string       | No       | latest  | Docker version to install            |

## `software.apptainer`

| Key       | Type         | Required | Default | Description                             |
| --------- | ------------ | -------- | ------- | --------------------------------------- |
| `labels`  | list[string] | Yes      | —       | Labels of nodes to install Apptainer on |
| `version` | string       | No       | latest  | Apptainer version to install            |

## `software.ollama[]`

Array of objects. Each object:

| Key           | Type         | Required | Default | Description                                  |
| ------------- | ------------ | -------- | ------- | -------------------------------------------- |
| `labels`      | list[string] | Yes      | —       | Labels of nodes to install Ollama on         |
| `models`      | list[string] | Yes      | —       | Model names to pull. Minimum 1.              |
| `environment` | object       | No       | `{}`    | Environment variables for the Ollama service |

## `deployment.htcondor[]`

Array of objects. Each object:

| Key           | Type         | Required | Default | Description                                                        |
| ------------- | ------------ | -------- | ------- | ------------------------------------------------------------------ |
| `kind`        | string       | Yes      | —       | Daemon type: `personal`, `central-manager`, `submit`, or `execute` |
| `labels`      | list[string] | Yes      | —       | Labels of nodes to configure as this daemon                        |
| `config_file` | string       | No       | —       | Path to a local HTCondor config file to upload                     |

## `experiments[]` — Shell

| Key                    | Type         | Required | Default     | Description                           |
| ---------------------- | ------------ | -------- | ----------- | ------------------------------------- |
| `kind`                 | string       | Yes      | —           | Must be `"shell"`                     |
| `name`                 | string       | Yes      | —           | Experiment name, used in output paths |
| `description`          | string       | No       | —           | Human-readable description            |
| `variables`            | object       | No       | `{}`        | Per-experiment variable overrides     |
| `inputs[].labels`      | list[string] | No       | —           | Nodes to upload the file to           |
| `inputs[].src`         | string       | No       | —           | Local source path                     |
| `inputs[].dst`         | string       | No       | —           | Remote destination directory          |
| `scripts[].labels`     | list[string] | Yes      | —           | Target nodes                          |
| `scripts[].script`     | string       | Yes      | —           | Shell script content                  |
| `scripts[].executable` | string       | No       | `/bin/bash` | Shell executable                      |
| `outputs[].labels`     | list[string] | No       | —           | Nodes to download from                |
| `outputs[].src`        | string       | No       | —           | Remote source path                    |
| `outputs[].dst`        | string       | No       | —           | Local destination directory           |

## `experiments[]` — Pegasus

| Key                         | Type         | Required | Default     | Description                                 |
| --------------------------- | ------------ | -------- | ----------- | ------------------------------------------- |
| `kind`                      | string       | Yes      | —           | Must be `"pegasus"`                         |
| `name`                      | string       | Yes      | —           | Experiment name, used in output paths       |
| `main`                      | string       | Yes      | —           | Local path to the workflow script           |
| `submit_node_labels`        | list[string] | Yes      | —           | Labels of nodes to submit the workflow from |
| `description`               | string       | No       | —           | Human-readable description                  |
| `count`                     | integer      | No       | `1`         | Number of times to run the workflow         |
| `poll_interval`             | integer      | No       | `3`         | Status check interval (seconds)             |
| `timeout`                   | integer      | No       | `600`       | Maximum wait time (seconds)                 |
| `variables`                 | object       | No       | `{}`        | Per-experiment variable overrides           |
| `inputs[].labels`           | list[string] | No       | —           | Nodes to upload files to                    |
| `inputs[].src`              | string       | No       | —           | Local source path                           |
| `inputs[].dst`              | string       | No       | —           | Remote destination directory                |
| `setup[].labels`            | list[string] | No       | —           | Nodes to run setup script on                |
| `setup[].script`            | string       | No       | —           | Setup script content                        |
| `setup[].executable`        | string       | No       | `/bin/bash` | Shell executable                            |
| `outputs[].labels`          | list[string] | No       | —           | Nodes to download from                      |
| `outputs[].src`             | string       | No       | —           | Remote source path                          |
| `outputs[].dst`             | string       | No       | —           | Local destination directory                 |
| `post_scripts[].labels`     | list[string] | No       | —           | Nodes to run post-script on                 |
| `post_scripts[].script`     | string       | No       | —           | Post-run script content                     |
| `post_scripts[].executable` | string       | No       | `/bin/bash` | Shell executable                            |

## `variables`

| Key      | Type                      | Required | Default | Description                                                                                                       |
| -------- | ------------------------- | -------- | ------- | ----------------------------------------------------------------------------------------------------------------- |
| `<name>` | string, integer, or float | No       | —       | Variable name: alphanumeric + underscore only. Value accessible in experiment scripts as an environment variable. |

## See also

- [Config file anatomy](../concepts/config-anatomy.md) — explanation of the config structure
- [Testbed parameters](testbed-parameters.md) — per-testbed parameter details
- [CLI reference](cli.md) — command-line options
