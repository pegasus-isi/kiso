# Use Docker

This guide covers how to configure Docker as the software runtime in a Kiso experiment.

For background on when to use Docker vs Apptainer, see [Components — Docker](../../concepts/components.md).

## Prerequisites

- Nodes provisioned via `kiso up` (Docker is installed during provisioning)
- Docker is supported on Vagrant, FABRIC, and Chameleon bare-metal testbeds

```{warning}
Docker is not supported on Chameleon Edge. Edge containers are managed directly by the CHI@Edge API and do not run a Docker daemon. Use the `container` field in the Chameleon Edge site config to specify the container image instead.
```

## Config fields

```yaml
software:
  docker:
    labels: [compute]          # Required — labels of nodes to install Docker on
```

| Field    | Required | Type         | Description                                       |
| -------- | -------- | ------------ | ------------------------------------------------- |
| `labels` | Yes      | list[string] | Labels of nodes that should have Docker installed |

<!-- TODO(mayani): Uncomment when version specific installation is implemented
| `version` | No | string | Docker version to install. Omit to install the latest stable version. | -->

## Minimal working example

```yaml
name: docker-experiment

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
  docker:
    labels: [compute]

experiments:
  - kind: shell
    name: run-container
    scripts:
      - labels: [compute]
        script: |
          docker run --rm ubuntu:22.04 echo "Container works"
```

Run:

```bash
kiso up experiment.yml
kiso run experiment.yml
kiso down experiment.yml
```

## Using Docker in experiment scripts

After `kiso up`, Docker is installed and the Docker daemon is running on all nodes matching the specified labels. Your experiment scripts can use `docker` directly:

```bash
# Pull and run an image
docker run --rm myimage:latest ./run_experiment.sh

# Run with a bind mount
docker run --rm -v /data:/data myimage:latest process.sh

# Run a GPU workload (if the node has a GPU)
docker run --rm --gpus all myimage:latest gpu_experiment.sh
```

Your container images do not need HTCondor, Pegasus, or any other Kiso dependencies pre-installed. Kiso installs those separately on the provisioned nodes. Keep your images focused on your experiment's workload — this makes them smaller and reusable across different Kiso configurations.

## See also

- [Use Apptainer](apptainer.md) — alternative container runtime for HPC environments
- [Components — Docker](../../concepts/components.md) — when to choose Docker
- [Config file reference](../../reference/config.md) — complete software configuration reference
