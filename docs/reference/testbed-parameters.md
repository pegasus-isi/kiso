# Testbed parameters

Per-testbed configuration parameters for Vagrant, FABRIC, and Chameleon.

## Vagrant (`kind: vagrant`)

```yaml
sites:
  - kind: vagrant
    backend: libvirt             # Optional — libvirt (default) or virtualbox
    box: generic/debian11        # Optional — base VM image (default: generic/debian11)
    user: root                   # Optional — SSH user (default: root)
    name_prefix: enos            # Optional — prefix for VM names (default: enos)
    config_extra: ""             # Optional — extra Vagrant DSL config for all VMs
    resources:
      machines:
        - labels: [compute]
          flavour: small
          number: 1
          backend: virtualbox    # Optional — per-machine backend override
          box: generic/debian11  # Optional — per-machine box override
          user: root             # Optional — per-machine SSH user override
          name_prefix: myvm      # Optional — per-machine name prefix override
          config_extra_vm: ""    # Optional — extra Vagrant DSL config for this VM only
      networks:
        - cidr: 172.16.42.0/16
          labels: [net1]
```

### Site-level parameters

| Key            | Type   | Required | Default              | Description                                           |
| -------------- | ------ | -------- | -------------------- | ----------------------------------------------------- |
| `backend`      | string | No       | `"libvirt"`          | VM hypervisor: `libvirt` or `virtualbox`              |
| `box`          | string | No       | `"generic/debian11"` | Base Vagrant box (OS image) for all machines          |
| `user`         | string | No       | `"root"`             | SSH user for all machines                             |
| `name_prefix`  | string | No       | `"enos"`             | Prefix applied to all VM names                        |
| `config_extra` | string | No       | —                    | Extra configuration in Vagrant DSL applied to all VMs |

### Machine parameters

| Key               | Type         | Required | Default            | Description                                                                                                                     |
| ----------------- | ------------ | -------- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| `labels`          | list[string] | Yes      | —                  | One or more labels. Must match `[a-zA-Z0-9._-]+`, must not start with `kiso.`                                                   |
| `flavour`         | string       | Yes\*    | —                  | Predefined VM size. See flavour table below. \*Required unless `flavour_desc` is provided.                                      |
| `flavour_desc`    | object       | Yes\*    | —                  | Custom resource profile: `core` (number, required) and `mem` (number in MB, required). \*Required unless `flavour` is provided. |
| `number`          | integer      | No       | `1`                | Number of VMs to provision with these labels                                                                                    |
| `backend`         | string       | No       | site-level default | Per-machine backend override: `libvirt` or `virtualbox`                                                                         |
| `box`             | string       | No       | site-level default | Per-machine Vagrant box override                                                                                                |
| `user`            | string       | No       | site-level default | Per-machine SSH user override                                                                                                   |
| `name_prefix`     | string       | No       | site-level default | Per-machine VM name prefix override                                                                                             |
| `config_extra_vm` | string       | No       | —                  | Extra Vagrant DSL config applied to this VM only                                                                                |

### Vagrant machine flavours

| Flavour       | vCPUs | RAM     |
| ------------- | ----- | ------- |
| `tiny`        | 1     | 512 MB  |
| `small`       | 1     | 1024 MB |
| `medium`      | 2     | 2048 MB |
| `big`         | 3     | 3072 MB |
| `large`       | 4     | 4096 MB |
| `extra-large` | 6     | 6144 MB |

### Network parameters

| Key      | Type         | Required | Description                                     |
| -------- | ------------ | -------- | ----------------------------------------------- |
| `cidr`   | string       | Yes      | Subnet in CIDR notation (e.g. `172.16.42.0/16`) |
| `labels` | list[string] | Yes      | Labels for this network                         |

## FABRIC (`kind: fabric`)

```yaml
sites:
  - kind: fabric
    rc_file: ~/fabric-rc.sh          # Required
    walltime: "24:00:00"             # Optional — HH:MM:SS format
    site: UCSD                       # Optional — default site for all resources
    image: default_rocky_8           # Optional — default OS image
    name_prefix: fabric              # Optional — prefix for resource names
    resources:
      machines:
        - labels: [compute]
          flavour: small
          number: 1
          site: UCSD                 # Optional — per-machine site override
          image: default_rocky_8     # Optional — per-machine image override
      networks:
        - labels: [net1]
          kind: FABNetv4
          site: UCSD
```

### Site-level parameters

| Key           | Type   | Required | Default             | Description                                                       |
| ------------- | ------ | -------- | ------------------- | ----------------------------------------------------------------- |
| `rc_file`     | string | Yes      | —                   | Path to the FABRIC RC credentials file downloaded from the portal |
| `walltime`    | string | No       | `"24:00"`           | Lease duration in `HH:MM` format                                  |
| `site`        | string | No       | `"UCSD"`            | Default FABRIC site for all resources in this site entry          |
| `image`       | string | No       | `"default_rocky_8"` | Default OS image for all machines                                 |
| `name_prefix` | string | No       | `"fabric"`          | Prefix applied to all provisioned resource names                  |

### Machine parameters

| Key            | Type         | Required | Default            | Description                                                                                                                                    |
| -------------- | ------------ | -------- | ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `labels`       | list[string] | Yes      | —                  | One or more labels to assign                                                                                                                   |
| `flavour`      | string       | Yes\*    | —                  | Predefined resource size. See flavour table below. \*Required unless `flavour_desc` is provided.                                               |
| `flavour_desc` | object       | Yes\*    | —                  | Custom resource profile: `core` (int, required), `mem` (int GB, required), `disk` (int GB, optional). \*Required unless `flavour` is provided. |
| `number`       | integer      | No       | `1`                | Number of nodes to provision                                                                                                                   |
| `site`         | string       | No       | site-level default | Per-machine site override                                                                                                                      |
| `image`        | string       | No       | site-level default | Per-machine OS image override                                                                                                                  |
| `gpus`         | list         | No       | —                  | GPU components to attach. Each item: `model` (one of `TeslaT4`, `RTX6000`, `A30`, `A40`)                                                       |
| `storage`      | list         | No       | —                  | Storage components to attach (NVME or NAS)                                                                                                     |

### FABRIC machine flavours

| Flavour       | vCPUs | RAM    |
| ------------- | ----- | ------ |
| `tiny`        | 1     | 0.5 GB |
| `small`       | 1     | 1 GB   |
| `medium`      | 2     | 2 GB   |
| `big`         | 2     | 3 GB   |
| `large`       | 4     | 4 GB   |
| `extra-large` | 6     | 6 GB   |

### Network parameters

All network entries require `labels` and `kind`. Additional required fields depend on the network type.

| Key      | Type         | Required   | Description                                       |
| -------- | ------------ | ---------- | ------------------------------------------------- |
| `labels` | list[string] | Yes        | Labels for this network                           |
| `kind`   | string       | Yes        | Network type. See network types table below.      |
| `site`   | string       | See table  | FABRIC site where the network is created          |
| `site_1` | string       | L2STS only | First site for L2STS spanning network             |
| `site_2` | string       | L2STS only | Second site for L2STS spanning network            |
| `cidr`   | string       | No         | Subnet in CIDR notation (L2Bridge and L2STS only) |

### Network types

| Kind          | Description                                                                  | `site` required | Required permission |
| ------------- | ---------------------------------------------------------------------------- | --------------- | ------------------- |
| `FABNetv4`    | IPv4 network (private)                                                       | Yes             | —                   |
| `FABNetv6`    | IPv6 network (private)                                                       | Yes             | —                   |
| `FABNetv4Ext` | IPv4 network with public internet access                                     | Yes             | `Net.FABNetv4Ext`   |
| `FABNetv6Ext` | IPv6 network with public internet access                                     | Yes             | `Net.FABNetv6Ext`   |
| `L2Bridge`    | Layer 2 bridge network                                                       | Yes             | —                   |
| `L2STS`       | Layer 2 network spanning two sites (`site_1` and `site_2` instead of `site`) | No              | —                   |

Use `FABNetv4Ext` or `FABNetv6Ext` for nodes that require public IP addresses (e.g. HTCondor submit and central manager nodes in multi-testbed deployments).

### Permission requirements

Some features require a permission tag to be enabled on your FABRIC project. Kiso checks these during `kiso up`.

| Feature                                 | Required permission             |
| --------------------------------------- | ------------------------------- |
| Machines spanning multiple FABRIC sites | `Slice.Multisite`               |
| `FABNetv4Ext` network                   | `Net.FABNetv4Ext`               |
| `FABNetv6Ext` network                   | `Net.FABNetv6Ext`               |
| GPU components (`gpus` field)           | `Component.GPU`                 |
| NVME storage (P4510 model)              | `Component.NVME_P4510`          |
| NVME storage (other models)             | `Component.NVME`                |
| NAS storage                             | `Component.Storage`             |
| ConnectX-5 SmartNIC                     | `Component.SmartNIC_ConnectX_5` |
| ConnectX-6 SmartNIC                     | `Component.SmartNIC_ConnectX_6` |

## Chameleon

Kiso supports two Chameleon site types: `chameleon` (bare metal) and `chameleon-edge` (edge devices).

### Chameleon bare metal (`kind: chameleon`)

```yaml
sites:
  - kind: chameleon
    rc_file: ~/openrc-chameleon.sh   # Required
    key_name: my-keypair             # Required
    lease_name: my-lease             # Optional (default: enos-lease)
    walltime: "02:00:00"             # Optional (default: 02:00:00)
    image: CC-Ubuntu22.04            # Optional (default: CC-Ubuntu18.04)
    user: cc                         # Optional (default: cc)
    resources:
      machines:
        - labels: [compute]
          flavour: baremetal
          number: 1
          image: CC-Ubuntu22.04      # Optional — per-machine override
          user: cc                   # Optional — per-machine override
      networks:
        - sharednet1
```

**Site-level parameters:**

| Key                 | Type         | Required | Default            | Description                                                 |
| ------------------- | ------------ | -------- | ------------------ | ----------------------------------------------------------- |
| `rc_file`           | string       | Yes      | —                  | Path to OpenRC credentials file (v3)                        |
| `key_name`          | string       | Yes      | —                  | Name of an SSH keypair registered in your Chameleon project |
| `lease_name`        | string       | No       | `"enos-lease"`     | Name for the Chameleon reservation lease                    |
| `walltime`          | string       | No       | `"02:00:00"`       | Lease duration in `HH:MM:SS` format                         |
| `image`             | string       | No       | `"CC-Ubuntu18.04"` | Default OS image for all machines                           |
| `user`              | string       | No       | `"cc"`             | Default SSH user for all machines                           |
| `configure_network` | boolean      | No       | `false`            | Whether to configure networking                             |
| `network.name`      | string       | No       | `"sharednet1"`     | OpenStack network name                                      |
| `subnet.name`       | string       | No       | —                  | OpenStack subnet name                                       |
| `dns_nameservers`   | list[string] | No       | —                  | DNS servers                                                 |
| `gateway`           | boolean      | No       | `false`            | Provision a gateway node                                    |
| `prefix`            | string       | No       | —                  | Prefix for resource names                                   |

**Machine parameters:**

| Key       | Type         | Required | Default      | Description                                                  |
| --------- | ------------ | -------- | ------------ | ------------------------------------------------------------ |
| `labels`  | list[string] | Yes      | —            | Labels to assign                                             |
| `flavour` | string       | Yes      | —            | OpenStack flavour name (e.g. `baremetal`, `compute_skylake`) |
| `number`  | integer      | Yes      | —            | Number of nodes                                              |
| `image`   | string       | No       | site default | Per-machine OS image override                                |
| `user`    | string       | No       | site default | Per-machine SSH user override                                |

**Network parameters:**

Networks are specified as a list of OpenStack network name strings:

```yaml
networks:
  - sharednet1
```

### Chameleon Edge (`kind: chameleon-edge`)

```yaml
sites:
  - kind: chameleon-edge
    rc_file: ~/openrc-chameleon.sh   # Required
    lease_name: my-edge-lease        # Optional (default: EnOSlib)
    walltime: "02:00"                # Optional (default: 02:00)
    resources:
      machines:
        # DeviceCluster — select devices by board/model name
        - labels: [edge]
          machine_name: raspberrypi4
          count: 2
          device_model: rpi4b-8gb    # Optional
          container:
            name: my-container
            image: ubuntu:22.04

        # Device — select a specific device by name
        - labels: [specific-device]
          device_name: iot-jetson04
          container:
            name: jetson-container
            image: nvcr.io/nvidia/l4t-base:r32.6.1

      networks:
        - labels: [net1]
          id: containernet1
          type: prod
          site: CHI@Edge
```

**Site-level parameters:**

| Key          | Type   | Required | Default     | Description                      |
| ------------ | ------ | -------- | ----------- | -------------------------------- |
| `rc_file`    | string | Yes      | —           | Path to OpenRC credentials file  |
| `lease_name` | string | No       | `"EnOSlib"` | Name for the edge lease          |
| `walltime`   | string | No       | `"02:00"`   | Lease duration in `HH:MM` format |

**Machine types:**

*DeviceCluster* — selects devices by board type:

| Key            | Type         | Required | Description                        |
| -------------- | ------------ | -------- | ---------------------------------- |
| `labels`       | list[string] | Yes      | Labels to assign                   |
| `machine_name` | string       | Yes      | Board/machine type name            |
| `count`        | integer      | Yes      | Number of devices to provision     |
| `device_model` | string       | No       | Specific device model filter       |
| `container`    | object       | No       | Container to deploy on the devices |

*Device* — selects a specific named device:

| Key            | Type         | Required | Description                                    |
| -------------- | ------------ | -------- | ---------------------------------------------- |
| `labels`       | list[string] | Yes      | Labels to assign                               |
| `device_name`  | string       | Yes      | Specific device hostname (e.g. `iot-jetson04`) |
| `device_model` | string       | No       | Device model                                   |
| `container`    | object       | No       | Container to deploy                            |

**Container parameters:**

| Key               | Type         | Required | Description                                |
| ----------------- | ------------ | -------- | ------------------------------------------ |
| `name`            | string       | Yes      | Container name                             |
| `image`           | string       | Yes      | Container image                            |
| `exposed_ports`   | list[string] | No       | Ports to expose (e.g. `["8080/tcp"]`)      |
| `start`           | boolean      | No       | Whether to start the container immediately |
| `start_timeout`   | integer      | No       | Seconds to wait for container to start     |
| `device_profiles` | list[string] | No       | Device profiles to apply (e.g. GPU access) |

<!-- TODO(mayani): EnOSlib's Chameleon Edge provider has not implemented networks yet
**Network parameters:**

| Key | Type | Required | Description |
|---|---|---|---|
| `labels` | list[string] | Yes | Labels for this network |
| `id` | string | Yes | Network ID |
| `type` | string | Yes | Must be `"prod"` |
| `site` | string | Yes | Chameleon site (e.g. `"CHI@Edge"`) | -->

## Label naming rules

Applies to all testbeds:

- Allowed characters: `a-z`, `A-Z`, `0-9`, `.`, `_`, `-`
- Must not start with `kiso.` (reserved prefix)
- Labels are case-sensitive
- A machine can have multiple labels

## See also

- [Config file reference](config.md) — all configuration keys
- [Set up on Vagrant](../how-to/testbeds/vagrant.md)
- [Set up on FABRIC](../how-to/testbeds/fabric.md)
- [Set up on Chameleon](../how-to/testbeds/chameleon.md)
