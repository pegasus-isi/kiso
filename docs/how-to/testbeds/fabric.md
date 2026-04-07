# Set up on FABRIC

This guide covers how to configure FABRIC as the testbed in a Kiso experiment.

For background on what FABRIC is and when to use it, see [Components — FABRIC](../../concepts/components.md).

## Prerequisites

1. A FABRIC account — sign up at [portal.fabric-testbed.net](https://portal.fabric-testbed.net)
1. [An active FABRIC project allocation](https://learn.fabric-testbed.net/knowledge-base/creating-or-joining-a-project/) — create a new project or join an existing one
1. [SSH keys generated and configured](https://learn.fabric-testbed.net/knowledge-base/generating-ssh-configuration-and-ssh-keys/) — required for Kiso to connect to provisioned nodes over SSH
1. [A FABRIC API token generated](https://learn.fabric-testbed.net/knowledge-base/obtaining-and-using-fabric-api-tokens/) — required for the RC file
1. A FABRIC RC file (used as `rc_file` in the config)

```bash
export FABRIC_BASTION_HOST=bastion.fabric-testbed.net
export FABRIC_PROJECT_ID=<fabric-project-id>
export FABRIC_BASTION_USERNAME=<fabric-bastion-username>
export FABRIC_BASTION_KEY_LOCATION=<path-to-fabric-bastion-key>
export FABRIC_SLICE_PRIVATE_KEY_FILE=<path-to-fabric-sliver-key>
export FABRIC_SLICE_PUBLIC_KEY_FILE=<path-to-fabric-bastion-public-key>
export FABRIC_LOG_LEVEL=INFO
export FABRIC_LOG_FILE=/tmp/fablib/fablib.log
export FABRIC_TOKEN_LOCATION=<path-to-fabric-token>
```

6. [Permissions requested](https://learn.fabric-testbed.net/knowledge-base/fabric-user-roles-and-project-permissions/) for any resources your experiment requires (GPUs, public IPs, NVMe storage, etc.) — see the permissions table below

1. Kiso installed: `pip install kiso[fabric]`

1. **(macOS only, optional)** `rsync` from Homebrew: some FABRIC sites assign IPv6 addresses as the management IP, and macOS's built-in `rsync` fails to connect to IPv6 addresses via jump hosts. Install the Homebrew version to fix this:

   ```bash
   brew install rsync
   ```

## FABRIC-specific config fields

```yaml
sites:
  - kind: fabric
    rc_file: ~/fabric-rc.sh          # Required — path to FABRIC RC credentials file
    walltime: "24:00:00"             # Optional — lease duration in HH:MM format (default: 24:00)
    site: UCSD                       # Optional — default FABRIC site for all resources (default: UCSD)
    image: default_rocky_8           # Optional — default OS image for all machines (default: default_rocky_8)
    name_prefix: fabric              # Optional — prefix for resource names (default: fabric)
    resources:
      machines:
        - labels: [compute]          # Required — one or more labels
          flavour: small             # Required — see flavour table below (or use flavour_desc)
          number: 1                  # Optional — number of machines (default: 1)
          site: UCSD                 # Optional — per-machine site override
          image: default_rocky_8     # Optional — per-machine image override
          gpus:                      # Optional — attach GPU components (requires Component.GPU permission)
            - model: TeslaT4
          storage:                   # Optional — attach storage components
            - kind: NVME             # NVME or Storage
              model: P4510           # Required for NVME (requires Component.NVME_P4510 permission)
              mountpoint: /mnt/nvme  # Optional — auto-mount path
            - kind: Storage          # NAS persistent storage
              model: NAS
              name: my-storage       # Required — persistent storage name
              auto_mount: true       # Optional — mount automatically
      networks:
        - labels: [net1]             # Required — one or more labels
          kind: FABNetv4             # Required — network type (see network types below)
          site: UCSD                 # Required for most network types
          nic:                       # Optional — specify the NIC for network attachment
            kind: SharedNIC          # SharedNIC or SmartNIC
            model: ConnectX-6        # NIC model (e.g. ConnectX-5, ConnectX-6)
```

### Machine flavours

| Flavour       | vCPUs | RAM    |
| ------------- | ----- | ------ |
| `tiny`        | 1     | 0.5 GB |
| `small`       | 1     | 1 GB   |
| `medium`      | 2     | 2 GB   |
| `big`         | 2     | 3 GB   |
| `large`       | 4     | 4 GB   |
| `extra-large` | 6     | 6 GB   |

Alternatively, use `flavour_desc` to specify a custom resource profile:

```yaml
machines:
  - labels: [compute]
    flavour_desc:
      core: 8      # Required — number of cores
      mem: 16      # Required — RAM in GB
      disk: 100    # Optional — disk in GB
```

### Network types

| Kind          | Description                              | Required fields    |
| ------------- | ---------------------------------------- | ------------------ |
| `FABNetv4`    | IPv4 network (private)                   | `site`             |
| `FABNetv6`    | IPv6 network (private)                   | `site`             |
| `FABNetv4Ext` | IPv4 network with public internet access | `site`             |
| `FABNetv6Ext` | IPv6 network with public internet access | `site`             |
| `L2Bridge`    | Layer 2 bridge network                   | `site`             |
| `L2STS`       | Layer 2 network spanning two sites       | `site_1`, `site_2` |

Use `FABNetv4Ext` or `FABNetv6Ext` when nodes need public IP addresses (e.g. HTCondor submit and central manager nodes in a multi-testbed deployment).

## FABRIC project permissions

Some features require additional permissions to be enabled on your FABRIC project. Kiso validates these during `kiso up` and raises an error if a required permission is missing.

Request permissions from the FABRIC portal under **Experiments → Projects and Slices → [Your Project] → Request Permissions**.

| Feature                                 | Required permission             |
| --------------------------------------- | ------------------------------- |
| Machines spanning multiple FABRIC sites | `Slice.Multisite`               |
| `FABNetv4Ext` network (public IPv4)     | `Net.FABNetv4Ext`               |
| `FABNetv6Ext` network (public IPv6)     | `Net.FABNetv6Ext`               |
| GPU components (`gpus` field)           | `Component.GPU`                 |
| NVME storage (P4510 model)              | `Component.NVME_P4510`          |
| NVME storage (other models)             | `Component.NVME`                |
| NAS storage                             | `Component.Storage`             |
| ConnectX-5 SmartNIC                     | `Component.SmartNIC_ConnectX_5` |
| ConnectX-6 SmartNIC                     | `Component.SmartNIC_ConnectX_6` |

## Minimal working example

```yaml
name: fabric-test

sites:
  - kind: fabric
    rc_file: ~/fabric-rc.sh
    resources:
      machines:
        - labels: [compute]
          flavour: small
          number: 1
      networks:
        - labels: [net1]
          kind: FABNetv4
          site: UCSD
          nic:
            kind: SharedNIC
            model: ConnectX-6

experiments:
  - kind: shell
    name: check
    scripts:
      - labels: [compute]
        script: hostname && uname -r
```

Run it:

```bash
kiso up experiment.yml
kiso run experiment.yml
kiso down experiment.yml
```

## Example with public IP (for multi-testbed HTCondor)

To give a node a publicly routable IP address, attach a `FABNetv4Ext` network:

```yaml
sites:
  - kind: fabric
    rc_file: ~/fabric-rc.sh
    resources:
      machines:
        - labels: [submit, central-manager]
          flavour: small
          number: 1
        - labels: [execute]
          flavour: small
          number: 2
      networks:
        - labels: [internal]
          kind: FABNetv4
          site: UCSD
          nic:
            kind: SharedNIC
            model: ConnectX-6
        - labels: [public]
          kind: FABNetv4Ext
          site: UCSD
          nic:
            kind: SharedNIC
            model: ConnectX-6
```

## Verifying the setup

After `kiso up`, check the FABRIC dashboard:

- Active slice under **Experiments → MY SLICES**

## Common failure modes

**Missing or invalid RC file**

If `rc_file` points to a file that does not exist or contains invalid credentials, `kiso up` will fail with an authentication error. Re-download the RC file from the FABRIC portal.

```{warning}
In your `rc_file`, do not use `'` to quote the values. For e.g., `export FABRIC_BASTION_KEY_LOCATION='~/.ssh/bastion.key'` is invalid.
```

**Token expired**

FABRIC tokens expire. If `kiso up` fails with an authentication error, refresh your token from the FABRIC portal and update your RC file.

**Lease expired during experiment**

If the experiment runs longer than `walltime`, FABRIC terminates the slice. Set `walltime` generously. Leases can be extended from the FABRIC portal while active.

**Project allocation exhausted**

If your project has no remaining compute allocation, FABRIC will reject the reservation request. Check your allocation at the FABRIC portal.

**SSH connectivity issues**

If `kiso up` succeeds (resources provisioned) but subsequent steps fail with SSH errors, verify that your bastion key is correctly configured. FABRIC nodes are accessed through a bastion host.

**Resource unavailability**

FABRIC resources are not always available at all sites. If a specific site or flavour is unavailable, `kiso up` will fail. Try a different FABRIC site or adjust the resource request.

## See also

- [Your first experiment](../../tutorials/first-experiment.md) — demonstrates switching from Vagrant to FABRIC
- [Testbed parameters](../../reference/testbed-parameters.md) — complete FABRIC parameter reference
- [FABRIC documentation](https://learn.fabric-testbed.net)
