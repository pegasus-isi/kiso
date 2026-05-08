# Run custom setup scripts

This guide covers how to use the `shell` software type to run arbitrary setup scripts on provisioned nodes during `kiso up`.

Use `shell` software when your setup steps do not fit any of the dedicated software plugins — for example, installing a project-specific dependency, writing a config file, or bootstrapping a custom service.

## Prerequisites

- Nodes provisioned via `kiso up`
- Kiso installed with the appropriate testbed extra (e.g. `pip install kiso[vagrant]`)

## Config fields

The `shell` software entry is an **array** — you can run different scripts on different sets of nodes.

```yaml
software:
  shell:
    - labels: [compute]          # Required — labels of nodes to run the script on
      script: |                  # Required — shell script content
        apt-get install -y my-tool
      executable: /bin/bash      # Optional — default: /bin/bash
```

| Field        | Required | Type         | Default     | Description                              |
| ------------ | -------- | ------------ | ----------- | ---------------------------------------- |
| `labels`     | Yes      | list[string] | —           | Labels of nodes the script should run on |
| `script`     | Yes      | string       | —           | Shell script content to execute          |
| `executable` | No       | string       | `/bin/bash` | Shell executable used to run the script  |

Scripts run in the order they appear in the array. Each entry can target a different set of nodes.

## Minimal working example

```yaml
name: custom-setup

sites:
  - kind: vagrant
    resources:
      machines:
        - labels: [compute]
          flavour: small
          number: 1
      networks:
        - labels: [net1]
          cidr: 172.16.42.0/16

software:
  shell:
    - labels: [compute]
      script: |
        echo "Setting up node $(hostname)"
        mkdir -p /data/experiment

experiments:
  - kind: shell
    name: run
    scripts:
      - labels: [compute]
        script: ls /data/experiment
```

## Running different scripts on different node groups

Each array entry runs independently and can target different labels:

```yaml
software:
  shell:
    - labels: [compute]
      script: |
        apt-get update
        apt-get install -y htop
    - labels: [storage]
      script: |
        sudo mkfs.ext4 /dev/sdb
        sudo mount /dev/sdb /mnt/data
```

## See also

- [Use Docker](docker.md) — general-purpose container runtime
- [Use Apptainer](apptainer.md) — rootless container runtime for HPC environments
- [Config file reference](../../reference/config.md) — complete software configuration reference
