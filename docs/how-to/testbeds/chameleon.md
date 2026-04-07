# Set up on Chameleon

This guide covers how to configure Chameleon bare metal (`kind: chameleon`) as the testbed in a Kiso experiment.

For Chameleon Edge (containers on edge devices), see [Set up on Chameleon Edge](chameleon-edge.md).

For background on what Chameleon is and when to use it, see [Components — Chameleon](../../concepts/components.md).

## Prerequisites

1. A Chameleon account at [chameleoncloud.org](https://chameleoncloud.org)
1. [An active Chameleon project allocation](https://chameleoncloud.readthedocs.io/en/latest/user/project.html#creating-a-project) — create a new project or join an existing one
1. [An OpenRC credentials file](https://chameleoncloud.readthedocs.io/en/latest/technical/cli/authentication.html#creating-an-application-credential) — create an application credential and download the OpenRC v3 file from the Chameleon dashboard under **Identity → Application Credentials**
1. [An SSH keypair registered in your Chameleon project](https://chameleoncloud.readthedocs.io/en/latest/technical/gui/navigation.html#key-pairs) — used as the `key_name` field in the config
1. Kiso installed: `pip install kiso[chameleon]`

## Chameleon bare metal (`kind: chameleon`)

### Config fields

```yaml
sites:
  - kind: chameleon
    rc_file: ~/openrc-chameleon.sh   # Required — path to OpenRC credentials file
    key_name: my-keypair             # Required — SSH keypair registered in Chameleon
    lease_name: my-lease             # Optional — name for the Chameleon lease (default: enos-lease)
    walltime: "02:00:00"             # Optional — lease duration in HH:MM:SS format (default: 02:00:00)
    image: CC-Ubuntu22.04            # Optional — OS image for all machines (default: CC-Ubuntu18.04)
    user: cc                         # Optional — SSH user (default: cc)
    configure_network: false         # Optional — whether to configure networking (default: false)
    network:                         # Optional — OpenStack network to use
      name: sharednet1               # default: sharednet1
    subnet:                          # Optional — OpenStack subnet
      name: sharednet1-subnet
    dns_nameservers:                 # Optional — DNS servers
      - 130.202.101.6
      - 130.202.101.37
    gateway: false                   # Optional — provision a gateway node (default: false)
    prefix: myexp                    # Optional — prefix for resource names
    resources:
      machines:
        - labels: [compute]          # Required — one or more labels
          flavour: baremetal         # Required — OpenStack flavour name
          number: 1                  # Required — number of nodes
          image: CC-Ubuntu22.04      # Optional — per-machine image override
          user: cc                   # Optional — per-machine SSH user override
      networks:
        - sharednet1                 # Required — list of OpenStack network names
```

### Key fields

| Field               | Required | Default            | Description                                                 |
| ------------------- | -------- | ------------------ | ----------------------------------------------------------- |
| `rc_file`           | Yes      | —                  | Path to the OpenRC credentials file                         |
| `key_name`          | Yes      | —                  | Name of an SSH keypair registered in your Chameleon project |
| `lease_name`        | No       | `"enos-lease"`     | Name of the Chameleon bare-metal lease to create            |
| `walltime`          | No       | `"02:00:00"`       | Lease duration in `HH:MM:SS` format                         |
| `image`             | No       | `"CC-Ubuntu18.04"` | Default OS image for all machines                           |
| `user`              | No       | `"cc"`             | Default SSH user                                            |
| `configure_network` | No       | `false`            | Whether to configure networking                             |
| `network.name`      | No       | `"sharednet1"`     | OpenStack network to attach instances to                    |

### Machine fields

| Field     | Required | Description                                                                                                                                                                                      |
| --------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `labels`  | Yes      | Labels to assign                                                                                                                                                                                 |
| `flavour` | Yes      | OpenStack flavour name (e.g. `baremetal`, `compute_skylake`, `compute_zen3`). Available flavours depend on the Chameleon site — check the dashboard at CHI@UC or CHI@TACC for what is available. |
| `number`  | Yes      | Number of nodes to provision                                                                                                                                                                     |
| `image`   | No       | Per-machine OS image override                                                                                                                                                                    |
| `user`    | No       | Per-machine SSH user override                                                                                                                                                                    |

### Networks

Networks are specified as a list of OpenStack network name strings:

```yaml
networks:
  - sharednet1
```

### Minimal working example

```yaml
name: chameleon-test

sites:
  - kind: chameleon
    rc_file: ~/openrc-chameleon.sh
    key_name: my-keypair
    lease_name: kiso-test
    resources:
      machines:
        - labels: [compute]
          flavour: baremetal
          number: 1
      networks:
        - sharednet1

experiments:
  - kind: shell
    name: check
    scripts:
      - labels: [compute]
        script: hostname && uname -r
```

Source the OpenRC file before running:

```bash
kiso up experiment.yml
kiso run experiment.yml
kiso down experiment.yml
```

## Verifying the setup

After `kiso up`, check the Chameleon dashboard:

- Active lease under **Reservations → Leases**
- Instances under **Compute → Instances**

You can also connect to a node directly using `kiso ssh` with the label assigned to it in your config:

```bash
kiso ssh <your-node-label>
```

## Common failure modes

**No nodes available for lease**

Chameleon bare-metal resources are shared. If no nodes are available: try a different Chameleon site (UC vs TACC), a different flavour, or a shorter walltime.

**Missing or invalid RC file**

If `rc_file` points to a file that does not exist or contains invalid credentials, `kiso up` will fail with an authentication error.

```{warning}
In your `rc_file`, do not use `'` to quote the values. For e.g., `export OS_AUTH_TYPE='v3applicationcredential'` is invalid.
```

**Lease expired during experiment**

If the experiment runs longer than `walltime`, Chameleon terminates the lease. Set `walltime` generously. Leases can be extended from the Chameleon dashboard while active.

**SSH key not found**

If `key_name` is not registered in your project, provisioning will fail. Register it at **Compute → Key Pairs** in the Chameleon dashboard.

## See also

- [Testbed parameters](../../reference/testbed-parameters.md) — complete Chameleon parameter reference
- [Set up on Chameleon Edge](chameleon-edge.md) — containers on edge devices
- [Chameleon documentation](https://chameleoncloud.org/)
