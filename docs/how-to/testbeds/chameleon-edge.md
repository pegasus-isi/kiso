# Set up on Chameleon Edge

This guide covers how to configure Chameleon Edge (`kind: chameleon-edge`) as the testbed in a Kiso experiment.

> **Chameleon Edge uses a different OpenRC file from Chameleon Cloud.** Both use the same Chameleon project allocation, but CHI@Edge requires its own site-specific OpenRC credentials file. A CHI@UC or CHI@TACC credential file will not work here. If you are looking for Chameleon bare-metal nodes, see [Set up on Chameleon](chameleon.md) instead.

Chameleon Edge provisions containers on edge devices through CHI@Edge. For background on when to use it, see [Components — Chameleon Edge](../../concepts/components.md).

```{tip}
Chameleon Edge containers are not accessible over SSH. Kiso communicates with them through the Chameleon Edge Python API instead. To inspect a running container, open the [CHI@Edge Containers dashboard](https://chi.edge.chameleoncloud.org/project/container/containers): select the container to view its status, access the interactive console, and retrieve stdout/stderr logs.
```

## Prerequisites

1. A Chameleon account at [chameleoncloud.org](https://chameleoncloud.org)
1. [An active Chameleon project allocation](https://chameleoncloud.readthedocs.io/en/latest/user/project.html#creating-a-project) — create a new project or join an existing one; the allocation must include CHI@Edge access
1. [An OpenRC credentials file](https://chameleoncloud.readthedocs.io/en/latest/technical/cli/authentication.html#creating-an-application-credential) downloaded from the **CHI@Edge** site — switch to the CHI@Edge site in the dashboard, then create an application credential under **Identity → Application Credentials**. A CHI@UC or CHI@TACC credential file will not work here.
1. Kiso installed: `pip install kiso[chameleon]`

## Config fields

```yaml
sites:
  - kind: chameleon-edge
    rc_file: ~/openrc-chameleon.sh   # Required — path to OpenRC credentials file
    lease_name: my-edge-lease        # Optional — lease name (default: EnOSlib)
    walltime: "02:00:00"             # Optional — lease duration in HH:MM format (default: 02:00)
    resources:
      machines:
        # Option A: DeviceCluster — select devices by board/model name
        - labels: [edge]             # Required
          machine_name: raspberrypi4 # Required — board type
          count: 2                   # Required — number of devices
          device_model: rpi4b-8gb    # Optional — specific device model
          container:                 # Optional — container to run on each device
            name: my-container       # Required
            image: ubuntu:22.04      # Required
            exposed_ports:           # Optional
              - "8080/tcp"
            start: true              # Optional
            start_timeout: 60        # Optional
            device_profiles:         # Optional
              - pi4

        # Option B: Device — select a specific device by name
        - labels: [specific-device]  # Required
          device_name: iot-jetson04  # Required — specific device hostname
          device_model: jetson-nano  # Optional
          container:
            name: jetson-container
            image: nvcr.io/nvidia/l4t-base:r32.6.1
```

## Machine types

### DeviceCluster

Selects a set of devices by board/machine type. Use this when you need multiple devices of the same kind.

| Field          | Required | Description                                     |
| -------------- | -------- | ----------------------------------------------- |
| `labels`       | Yes      | Labels to assign                                |
| `machine_name` | Yes      | Board/machine type name (e.g. `raspberrypi4`)   |
| `count`        | Yes      | Number of devices to provision                  |
| `device_model` | No       | Specific device model filter (e.g. `rpi4b-8gb`) |
| `container`    | No       | Container to deploy on the devices              |

### Device

Selects a specific named device. Use this when you need a particular piece of hardware.

| Field          | Required | Description                                    |
| -------------- | -------- | ---------------------------------------------- |
| `labels`       | Yes      | Labels to assign                               |
| `device_name`  | Yes      | Specific device hostname (e.g. `iot-jetson04`) |
| `device_model` | No       | Device model                                   |
| `container`    | No       | Container to deploy                            |

## Container fields

| Field             | Required | Description                                              |
| ----------------- | -------- | -------------------------------------------------------- |
| `name`            | Yes      | Container name                                           |
| `image`           | Yes      | Container image                                          |
| `exposed_ports`   | No       | Ports to expose (e.g. `["8080/tcp"]`)                    |
| `start`           | No       | Whether to start the container immediately               |
| `start_timeout`   | No       | Seconds to wait for container to start                   |
| `device_profiles` | No       | Device profiles to apply (e.g. GPU access via `["pi4"]`) |

<!-- TODO(mayani): EnOSlib's Chameleon Edge provider has not implemented networks yet
## Network fields

Networks connect edge containers to each other or to external services.

| Field | Required | Description |
|---|---|---|
| `labels` | Yes | Labels to assign |
| `id` | Yes | Network ID |
| `type` | Yes | Must be `"prod"` |
| `site` | Yes | Chameleon site (e.g. `"CHI@Edge"`) | -->

## Minimal working example

```yaml
name: chameleon-edge-test

sites:
  - kind: chameleon-edge
    rc_file: ~/openrc-chameleon.sh
    lease_name: kiso-edge-test
    resources:
      machines:
        - labels: [edge]
          machine_name: raspberrypi4
          count: 1
          container:
            name: test-container
            image: ubuntu:22.04
            start: true

experiments:
  - kind: shell
    name: check
    scripts:
      - labels: [edge]
        script: hostname && uname -r
```

Source the OpenRC file before running:

```bash
kiso up experiment.yml
kiso run experiment.yml
kiso down experiment.yml
```

## Verifying the setup

After `kiso up`, check the CHI@Edge dashboard:

- Active lease under **Reservations → Leases**
- Running containers under the CHI@Edge **Container → Containers** view

## Common failure modes

**No edge devices available for lease**

Edge devices at CHI@Edge are a shared resource. If none are available for the requested `machine_name`, try a different board type or a shorter `walltime`.

**Missing or invalid RC file**

If `rc_file` points to a file that does not exist or contains invalid credentials, `kiso up` will fail with an authentication error.

```{warning}
In your `rc_file`, do not use `'` to quote the values. For e.g., `export OS_AUTH_TYPE='v3applicationcredential'` is invalid.
```

**Lease expired during experiment**

If the experiment runs longer than `walltime`, Chameleon terminates the lease. Set `walltime` generously. Leases can be extended from the Chameleon dashboard while active.

**Command appears to hang or reports incorrect completion**

The Chameleon Edge API has fixed timeouts that cannot be overridden. If a command takes too long, the API call terminates — but the command continues running on the container. Kiso handles this by polling the container for completion using an exit code file, so the command will eventually be detected as complete. If a script appears to hang, it is likely still running on the container; wait rather than interrupting.

**File transfer times out on large directories**

Chameleon Edge's API compresses a directory before uploading or downloading it. For large directories this can exceed the API timeout. Kiso handles this automatically by falling back to transferring files individually when a bulk transfer times out. Expect slower transfer times for large experiment inputs or outputs on Chameleon Edge compared to other testbeds.

## See also

- [Testbed parameters — Chameleon Edge](../../reference/testbed-parameters.md)
- [Set up on Chameleon bare metal](chameleon.md) — using Chameleon Cloud bare-metal nodes
- [Chameleon documentation](https://chameleoncloud.org/)
