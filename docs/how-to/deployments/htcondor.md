# Deploy with HTCondor

This guide covers how to configure HTCondor as the deployment for a single-testbed experiment.

For background on HTCondor's role in a Kiso experiment, see [Components — HTCondor](../../concepts/components.md).

## Prerequisites

- HTCondor is configured in the `deployment` section of the config
- For Pegasus experiments: HTCondor is required — Pegasus submits jobs through HTCondor

## Config fields

The `htcondor` deployment entry is an **array** of daemon specifications:

```yaml
deployment:
  htcondor:
    - kind: personal               # personal | central-manager | submit | execute
      labels: [compute]            # Required — labels of target nodes
      config_file: /path/to/config # Optional — custom HTCondor config file to upload
```

| Field         | Required | Type         | Description                                                        |
| ------------- | -------- | ------------ | ------------------------------------------------------------------ |
| `kind`        | Yes      | string       | Daemon type: `personal`, `central-manager`, `submit`, or `execute` |
| `labels`      | Yes      | list[string] | Labels of nodes that should run this daemon                        |
| `config_file` | No       | string       | Path to a local HTCondor config file to upload to the target nodes |

### Daemon kinds

| Kind              | Use case                                                                 |
| ----------------- | ------------------------------------------------------------------------ |
| `personal`        | Single-machine setup: all HTCondor daemons on one node. Simplest option. |
| `central-manager` | Manages the pool. Required for distributed setups.                       |
| `submit`          | Accepts job submissions. Required for distributed setups.                |
| `execute`         | Runs tasks. Use multiple for distributed execution.                      |

For a single-node experiment, use `personal` for simplicity unless you need distributed execution.

(single-node-setup)=

## Single-node setup (personal)

Use `personal` when one node runs the entire HTCondor pool. This is the simplest configuration for Pegasus experiments that do not need to distribute work across multiple nodes.

```yaml
deployment:
  htcondor:
    - kind: personal
      labels: [compute]
```

## Distributed setup (single testbed)

Use separate daemon types to distribute work across multiple nodes on a single testbed:

```yaml
deployment:
  htcondor:
    - kind: central-manager
      labels: [manager]
    - kind: submit
      labels: [submit]
    - kind: execute
      labels: [execute]
```

With matching `sites` config:

```yaml
sites:
  - kind: vagrant
    resources:
      machines:
        - labels: [manager, submit]
          flavour: small
          number: 1
        - labels: [execute]
          flavour: small
          number: 3
      networks:
        - cidr: 172.16.42.0/16
          labels: [net1]
```

The `manager` and `submit` labels can be assigned to the same machine, as shown above.

## Minimal working example (personal + Pegasus)

```{literalinclude} ../../_includes/deploy-htcondor/experiment.yml
:language: yaml
```

## Verifying the HTCondor pool is healthy

After `kiso up`, verify HTCondor is running by checking the pool status in your experiment scripts or via a setup script:

```yaml
experiments:
  - kind: shell
    name: check-condor
    scripts:
      - labels: [compute]
        script: |
          condor_status
          condor_q
```

A healthy pool shows the execute nodes with `Unclaimed` or `Claimed` status in `condor_status`, and an empty or active job queue in `condor_q`.

## Multi-testbed deployments

Kiso's HTCondor deployment plugin automatically detects when a deployment spans multiple testbeds. When it does, it identifies which nodes require publicly accessible IP addresses (the central manager and submit nodes) and automatically handles public IP assignment for those nodes as part of `kiso up`.

### Why public IPs are required (diagram)

Execute nodes on different testbeds live on separate private networks that are not routable to each other. The only address space reachable from both is the public internet. The central manager and submit node must therefore have publicly routable addresses.

```{mermaid}
graph TB
    subgraph fabric ["FABRIC (private: 10.0.x.x)"]
        CM["Central Manager + Submit<br/>★ Public IP required"]
        FE1["Execute node"]
        FE2["Execute node"]
    end

    subgraph chameleon ["Chameleon (private: 10.1.x.x)"]
        CE1["Execute node"]
        CE2["Execute node"]
    end

    FE1 -->|"port 9618<br/>internal"| CM
    FE2 -->|"port 9618<br/>internal"| CM
    CE1 -->|"port 9618<br/>public internet"| CM
    CE2 -->|"port 9618<br/>public internet"| CM
```

## Why public IPs are required

HTCondor daemons communicate over TCP. In a multi-testbed deployment:

- Execute nodes on FABRIC live in a FABRIC private network
- Execute nodes on Chameleon live in a Chameleon private network
- These private networks are not routable to each other

The only address space that nodes on both networks can reach is the public internet. The central manager and submit node must therefore have addresses reachable from the public internet so that execute nodes from both testbeds can register and receive jobs.

## Common failure modes

**No execute nodes in the pool**

If `condor_status` shows no nodes, the execute daemon may not have started or may not have connected to the central manager. Check `/var/log/condor/` on the relevant nodes.

**Jobs stuck in idle state**

Jobs that remain `Idle` in `condor_q` usually indicate no matching execute node. Run `condor_q -better-analyze <job-id>` to see why no node matches.

**HTCondor port blocked**

HTCondor uses port 9618 by default. If a firewall is blocking this port between nodes, the pool will not form. On FABRIC and Chameleon, ensure security group rules allow intra-experiment traffic.

## See also

- [Run a Pegasus workflow](../experiment-types/pegasus.md) — Pegasus requires HTCondor
- [Components — HTCondor](../../concepts/components.md) — architectural overview
