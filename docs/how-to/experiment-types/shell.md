# Run a Shell experiment

This guide covers how to configure and run a Shell experiment type in Kiso.

## When Shell is the right choice

Use Shell when:

- Your experiment is a command or a short script
- You do not need task dependencies, retries, or distributed scheduling
- You are prototyping before building a more complex Pegasus workflow

If your experiment has multiple dependent steps, parallel tasks, or needs automatic retry, use [Pegasus](pegasus.md) instead.

## Config fields

```yaml
experiments:
  - kind: shell
    name: my-experiment             # Required — used in output paths
    description: "Optional note"    # Optional
    inputs:                         # Optional — files to upload before running
      - labels: [compute]
        src: local/path/file.txt
        dst: /remote/path/
    scripts:                        # Required — at least one script
      - labels: [compute]           # Required — target nodes
        script: |                   # Required — shell script content
          echo "Running on $(hostname)"
        executable: /bin/bash       # Optional — default: /bin/bash
    outputs:                        # Optional — files to download after running
      - labels: [compute]
        src: /remote/path/result.txt
        dst: local/output/
```

### `scripts` array

Each entry in `scripts` runs on all nodes matching the given `labels`.

| Field        | Required | Type         | Default     | Description                   |
| ------------ | -------- | ------------ | ----------- | ----------------------------- |
| `labels`     | Yes      | list[string] | —           | Target nodes                  |
| `script`     | Yes      | string       | —           | Shell script content (inline) |
| `executable` | No       | string       | `/bin/bash` | Shell to use (shebang)        |

### `inputs` and `outputs`

Use `inputs` to upload files to nodes before the script runs. Use `outputs` to download files after the script completes.

| Field    | Required | Type         | Description           |
| -------- | -------- | ------------ | --------------------- |
| `labels` | Yes      | list[string] | Target nodes          |
| `src`    | Yes      | string       | Source path           |
| `dst`    | Yes      | string       | Destination directory |

### Exit codes

If a script exits with a non-zero exit code, Kiso marks the experiment as failed.

```yaml
experiments:
  - kind: shell
    name: process-data
    scripts:
      - labels: [compute]
        script: |
          echo "Hello, world!" > hello.txt
```

## Minimal working example

```yaml
name: hello-shell

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

experiments:
  - kind: shell
    name: hello
    scripts:
      - labels: [compute]
        script: |
          echo "Hello from $(hostname)"
```

This runs the script on the node labelled `compute`.

## Setup then run

A common pattern is to use two sequential scripts in one experiment: a setup script that installs dependencies, followed by a run script that executes the experiment. Scripts in a single experiment run sequentially in the order listed.

```yaml
experiments:
  - kind: shell
    name: agent-experiment
    scripts:
      - labels: [agent]
        script: |
          sudo dnf -y install python3.13 python3.13-pip python3.13-setuptools
          sudo pip3.13 install pydantic-ai
      - labels: [agent]
        script: |
          echo "Running agent"
          python3.13 bin/agent.py > agent-output.txt
    outputs:
      - labels: [agent]
        src: agent-output.txt
        dst: ./
```

The `dst: ./` shorthand copies output files into the current working directory on your local machine.

## Running scripts on multiple node groups

You can also have multiple `scripts` entries targeting different sets of nodes:

```yaml
experiments:
  - kind: shell
    name: multi-node
    scripts:
      - labels: [storage]
        script: |
          tar -czf /data/archive.tar.gz /data/results/
      - labels: [compute]
        script: |
          process.py --input /data/input.csv > /data/output.txt
```

Scripts in a single experiment run sequentially in the order listed.

## See also

- [Run a Pegasus workflow](pegasus.md) — for experiments with task dependencies
- [Collect and export results](../collect-results.md) — how to retrieve experiment output
- [Config file reference](../../reference/config.md) — complete Shell experiment configuration reference
