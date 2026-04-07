# Use Apptainer

This guide covers how to configure Apptainer as the software runtime in a Kiso experiment.

For background on when to prefer Apptainer over Docker, see [Components — Apptainer](../../concepts/components.md).

## When to prefer Apptainer over Docker

Choose Apptainer when:

- You need rootless container execution
- You are working with HPC workflows or schedulers that expect Apptainer/Singularity images

For general-purpose container workloads on Vagrant, FABRIC, or Chameleon, Docker is simpler. Apptainer is the right choice specifically when the environment restricts Docker.

## Prerequisites

- Nodes provisioned via `kiso up` (Apptainer is installed during provisioning)
- Apptainer is supported on Vagrant, FABRIC, Chameleon bare-metal, and Chameleon Edge testbeds

```{note}
Unlike Docker, Apptainer can also be installed on Chameleon Edge containers. Since edge containers do not run a Docker daemon, Apptainer is the container runtime of choice when your experiment requires containerized workloads on Chameleon Edge hardware.
```

## Config fields

```yaml
software:
  apptainer:
    labels: [compute]          # Required — labels of nodes to install Apptainer on
```

| Field    | Required | Type         | Description                                          |
| -------- | -------- | ------------ | ---------------------------------------------------- |
| `labels` | Yes      | list[string] | Labels of nodes that should have Apptainer installed |

<!-- TODO(mayani): Uncomment when version specific installation is implemented
| `version` | No | string | Apptainer version to install. Omit to install the latest stable version. | -->

## Minimal working example

```yaml
name: apptainer-experiment

sites:
  - kind: vagrant
    backend: virtualbox
    box: bento/rockylinux-9
    resources:
      machines:
        - labels: [compute]
          flavour: small
          number: 1
      networks:
        - labels: [net1]
          cidr: 172.16.42.0/16

software:
  apptainer:
    labels: [compute]

experiments:
  - kind: shell
    name: run-container
    scripts:
      - labels: [compute]
        script: |
          apptainer exec docker://ubuntu:22.04 echo "Apptainer works"
```

Run:

```bash
kiso up experiment.yml
kiso run experiment.yml
kiso down experiment.yml
```

## Using Apptainer in experiment scripts

After `kiso up`, Apptainer is installed on all nodes matching the specified labels. Your experiment scripts can use `apptainer` directly:

```bash
# Run a container from Docker Hub
apptainer exec docker://python:3.11 python3 analysis.py

# Run from a local SIF image
apptainer exec myimage.sif ./run_experiment.sh

# Run with a bind mount
apptainer exec --bind /data:/data myimage.sif process.sh
```

## See also

- [Use Docker](docker.md) — simpler alternative for environments where Docker is permitted
- [Components — Apptainer](../../concepts/components.md) — when to choose Apptainer
- [Config file reference](../../reference/config.md) — complete software configuration reference
