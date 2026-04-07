# Run a Pegasus workflow

This guide covers how to configure and run a Pegasus workflow experiment type in Kiso.

## Execution flow

```{mermaid}
sequenceDiagram
    actor User
    participant Kiso
    participant Submit as Submit node
    participant HTCondor
    participant Execute as Execute nodes

    User->>Kiso: kiso run
    Kiso->>Submit: Upload inputs + workflow script
    Kiso->>Submit: Execute main script
    Submit->>HTCondor: pegasus-plan + submit DAG
    loop Every poll_interval seconds
        Kiso->>HTCondor: Check workflow status
    end
    HTCondor->>Execute: Schedule jobs
    Execute-->>HTCondor: Job results
    HTCondor-->>Kiso: Workflow complete
    Kiso->>Submit: Run pegasus-statistics
    Kiso->>Submit: Run pegasus-analyzer
    Kiso->>User: Download submit directory
```

## When Pegasus is the right choice

Use Pegasus when:

- Your experiment has multiple steps with dependencies between them (Task B must run after Task A)
- You want automatic retry of failed tasks
- You need to distribute tasks across many nodes
- You need provenance tracking (record of what ran, where, and with what inputs)

For simple single-step experiments, use [Shell](shell.md) instead.

Pegasus requires HTCondor in the `deployment` section. See [Deploy with HTCondor](../deployments/htcondor.md).

## Prerequisites

- HTCondor installed and the pool is healthy (verify with `condor_status`)
- Pegasus workflow management system on the submit node (installed by Kiso)
- Python on the submit node (for writing the workflow script)

## Config fields

```yaml
experiments:
  - kind: pegasus
    name: my-workflow               # Required — used in output paths
    main: ./workflow.py             # Required — script that generates/submits the workflow
    submit_node_labels: [submit]    # Required — which node(s) to run the workflow from
    description: "Optional note"    # Optional
    count: 1                        # Optional — number of times to run (default: 1)
    poll_interval: 3                # Optional — status check interval in seconds (default: 3)
    timeout: 600                    # Optional — workflow timeout in seconds (default: 600)
    inputs:                         # Optional — files to upload before running
      - labels: [submit]
        src: local/data.txt
        dst: /remote/input/
    setup:                          # Optional — scripts to run before the workflow
      - labels: [submit]
        script: |
          mkdir -p /scratch/work
    outputs:                        # Optional — files to download after running
      - labels: [submit]
        src: /scratch/results/
        dst: local/output/
    post_scripts:                   # Optional — scripts to run after the workflow
      - labels: [submit]
        script: |
          cleanup.sh
```

### Key fields

| Field                | Required | Type         | Default | Description                                                                                                                                                                               |
| -------------------- | -------- | ------------ | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`               | Yes      | string       | —       | Experiment name, used in output paths                                                                                                                                                     |
| `main`               | Yes      | string       | —       | Path to a local script that generates and submits the Pegasus workflow. Can be a Python script or a shell script.                                                                         |
| `submit_node_labels` | Yes      | list[string] | —       | Labels of nodes where the workflow should be submitted. The referenced nodes must run an HTCondor `submit` or `personal` daemon — see [Deploy with HTCondor](../deployments/htcondor.md). |
| `count`              | No       | integer      | `1`     | How many times to run the workflow. Use this to collect performance or variability metrics across repeated trials.                                                                        |
| `poll_interval`      | No       | integer      | `3`     | How often (in seconds) to check workflow status                                                                                                                                           |
| `timeout`            | No       | integer      | `600`   | Maximum time (in seconds) to wait for the workflow to complete                                                                                                                            |

### Default file transfer behavior

**Inputs**: By default, the experiment directory (the directory containing the Kiso config file) is copied to all provisioned nodes before the workflow runs. Use `inputs` to transfer additional files.

**Outputs**: By default, the Pegasus workflow submit directory is automatically retrieved from the submit node after the workflow completes — you do not need to specify it in `outputs`. Kiso also automatically runs `pegasus-statistics` (wall time metrics) and `pegasus-analyzer` (success/failure analysis) and includes their output in the submit directory before downloading it. Use `outputs` to retrieve additional files beyond the submit directory.

## Writing the workflow script (`main`)

The `main` field is a script (shell) that Kiso uploads to the submit node and executes. The script is responsible for constructing the workflow and invoking the Pegasus planner. A Python script uses the Pegasus Python API directly; a shell script typically calls a Python workflow generator.

**Minimal example with two dependent tasks:**

```python
# workflow.py
from Pegasus.api import *

# Define transformations (executables)
tc = TransformationCatalog()
process = Transformation(
    "process", site="condorpool", pfn="/usr/bin/python3", is_stageable=False
)
analyze = Transformation(
    "analyze", site="condorpool", pfn="/usr/bin/python3", is_stageable=False
)
tc.add_transformations(process, analyze)

# Define the workflow DAG
wf = Workflow("my-workflow")

# Task A — produces an output file
task_a = Job(process)
task_a.add_args("process.py", "--input", "data.txt", "--output", "intermediate.txt")
task_a.add_inputs(File("data.txt"))
task_a.add_outputs(File("intermediate.txt"))

# Task B — depends on Task A's output
task_b = Job(analyze)
task_b.add_args("analyze.py", "--input", "intermediate.txt", "--output", "result.txt")
task_b.add_inputs(File("intermediate.txt"))
task_b.add_outputs(File("result.txt"), stage_out=True)

wf.add_jobs(task_a, task_b)
wf.add_transformation_catalog(tc)

# Submit the workflow
wf.plan(submit=True, output_sites=["local"])
```

Kiso monitors the submitted workflow and waits for completion (up to `timeout` seconds). On completion it automatically runs `pegasus-statistics` and `pegasus-analyzer` — you do not need to call these yourself.

## Using `setup`, `post_scripts`, and `outputs` together

A common pattern is to use `setup` to install dependencies, `post_scripts` to package results, and `outputs` to retrieve the package:

```yaml
experiments:
  - kind: pegasus
    name: my-workflow
    count: 2                           # Run twice to collect variability metrics
    main: bin/main.sh
    submit_node_labels: [submit]
    setup:
      - labels: [submit]
        script: pip install pyyaml GitPython
    inputs:
      - labels: [submit]
        src: README.md
        dst: ~kiso/
    post_scripts:
      - labels: [submit]
        script: tar zcvf outputs.tgz ~kiso/
    outputs:
      - labels: [submit]
        src: ~kiso/outputs.tgz
        dst: ./
```

## Minimal working example

```yaml
name: pegasus-workflow

sites:
  - kind: vagrant
    resources:
      machines:
        - labels: [submit]
          flavour: medium
          number: 1
        - labels: [execute]
          flavour: small
          number: 2
      networks:
        - cidr: 172.16.42.0/16
          labels: [net1]

deployment:
  htcondor:
    - kind: central-manager
      labels: [submit]
    - kind: submit
      labels: [submit]
    - kind: execute
      labels: [execute]

experiments:
  - kind: pegasus
    name: two-task-workflow
    main: workflow.py
    submit_node_labels: [submit]
    timeout: 1800
```

## See also

- [Run a Shell experiment](shell.md) — for simpler, single-step experiments
- [Deploy with HTCondor](../deployments/htcondor.md) — required for Pegasus
- [Collect and export results](../collect-results.md) — retrieving workflow outputs
- [Config file reference](../../reference/config.md) — complete Pegasus experiment configuration reference
- [Pegasus documentation](https://pegasus.isi.edu/documentation)
