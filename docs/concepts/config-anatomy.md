# Config file anatomy

A Kiso config file is a single YAML file that describes an experiment completely. This page explains what each section is and why it exists. For a complete list of every supported key, see the [Config file reference](../reference/config.md).

## Annotated example

```yaml
# The experiment name.
name: my-experiment

# ── SITES ─────────────────────────────────────────────────────────────────────
# One or more infrastructure providers. Each site provisions independent
# resources. Resources from different sites are joined into a single
# addressable pool via the labels system.
sites:
  - kind: vagrant                      # Testbed type: vagrant | fabric | chameleon | chameleon-edge
    resources:
      machines:
        - labels: [compute, submit]    # Labels: arbitrary names you assign
          flavour: small               # Resource size (testbed-specific)
          number: 1                    # How many machines with these labels
      networks:
        - cidr: 172.16.42.0/16
          labels: [net1]

  - kind: chameleon-edge               # Edge devices via CHI@Edge — containers, not VMs
    rc_file: ~/openrc-chi-edge.sh      # Must be a CHI@Edge OpenRC file (not CHI@UC or CHI@TACC)
    resources:
      machines:
        - labels: [edge]               # Edge nodes get their own label
          machine_name: raspberrypi4   # Board type
          count: 1
          container:
            name: edge-container
            image: ubuntu:22.04

# ── SOFTWARE ──────────────────────────────────────────────────────────────────
# What to install on provisioned nodes. Each entry targets nodes via labels.
# Multiple software runtimes can coexist on the same node.
software:
  docker:
    labels: [compute]                  # Install Docker on nodes labelled "compute"
  apptainer:
    labels: [compute]                  # Install Apptainer on nodes labelled "compute"
  ollama:
    labels: [compute]                  # Install Ollama on nodes labelled "compute"

# ── DEPLOYMENT ────────────────────────────────────────────────────────────────
# Optional. Workload management system. HTCondor is the only supported
# deployment. Each item configures one HTCondor daemon type on the
# matching nodes.
deployment:
  htcondor:
    - kind: personal                   # personal | central-manager | submit | execute
      labels: [compute]
      config_file: config/htcondor.conf

# ── EXPERIMENTS ───────────────────────────────────────────────────────────────
# One or more experiments to run, in order.
experiments:
  - kind: shell                        # shell | pegasus
    name: hello
    scripts:
      - labels: [compute]              # Run this script on nodes labelled "compute"
        script: |
          echo "Hello from $(hostname)"
      - labels: [edge]                 # Run this script on edge nodes
        script: |
          echo "Hello from edge device $(hostname)"
```

## The `name` field

A human-readable name for the experiment. Used in output directory paths and log messages. Choose something descriptive.

## The `sites` section

`sites` is a list of infrastructure providers. Each entry has a `kind` field that selects the testbed.

**Why a list?** Multi-testbed experiments need resources from more than one provider. Each site is provisioned independently; resources from all sites are addressable via labels.

**The `resources` block** within each site describes what to provision: machines (VMs or bare metal nodes) and networks. The exact fields differ per testbed — see [Testbed parameters](../reference/testbed-parameters.md).

**Labels** are arbitrary strings you assign to machines. They are the connective tissue between the `sites`, `software`, `deployment`, and `experiments` sections. A label like `compute` means "any machine I tagged with this name". Kiso resolves labels to actual machine addresses at runtime.

Label naming rules: alphanumeric characters, dots (`.`), underscores (`_`), and hyphens (`-`). Labels beginning with `kiso.` are reserved.

## The `software` section

`software` is optional. It describes what to install on provisioned nodes before running experiments.

Each software entry is keyed by the software name (`docker`, `apptainer`, `ollama`) and has at minimum a `labels` field that controls which nodes receive the installation. Software is installed via Ansible; you do not need to write playbooks.

You can install multiple software runtimes on the same node by using the same label in each entry.

## The `deployment` section

`deployment` is optional. It configures a workload management system — currently only HTCondor.

HTCondor is configured as a list of daemon specifications. Each daemon has a `kind` (`personal`, `central-manager`, `submit`, `execute`) and a `labels` field targeting the nodes it should run on. For single-machine experiments, use `kind: personal`. For distributed experiments, use separate `central-manager`, `submit`, and `execute` entries.

## The `experiments` section

`experiments` is a list of experiments to run, executed in order. Each experiment has:

- `kind`: `shell` or `pegasus`
- `name`: used in output paths
- Type-specific fields for scripts, workflow files, resource targeting, etc.

The `labels` field in each experiment step targets specific nodes — the same label system used in `software` and `deployment`.

<!-- TODO(mayani): Uncomment when variables are implemented
## The `variables` section

`variables` is optional. It defines global key-value pairs that can be referenced inside experiment scripts. Variable names must be alphanumeric with underscores. Values can be strings, integers, or floats.

Individual experiments can also define their own `variables` block to override or extend the global values. -->

## How the sections relate

```
sites        → defines what nodes exist and what labels they have
software     → installs runtimes on nodes matching given labels
deployment   → installs HTCondor daemons on nodes matching given labels
experiments  → runs scripts/workflows on nodes matching given labels
```

Labels are the only coupling between sections. Change the testbed `kind` in `sites`, and everything else stays the same — because labels are testbed-agnostic.

```{mermaid}
flowchart TD
    sites["sites<br/>defines labels on machines"]
    L(("label:<br/>compute"))
    software["software<br/>targets labels"]
    deployment["deployment<br/>targets labels"]
    experiments["experiments<br/>targets labels"]

    sites -->|"assigns"| L
    L --> software
    L --> deployment
    L --> experiments
```

## See also

- [Config file reference](../reference/config.md) — every supported key with type, default, and description
- [Testbed parameters](../reference/testbed-parameters.md) — per-testbed resource configuration
- [The experiment model](experiment-model.md) — how the config maps to the four lifecycle phases
