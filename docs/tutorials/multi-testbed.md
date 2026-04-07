# Multi-testbed experiment

> **Prerequisite**: Complete [Your first experiment](first-experiment.md) before starting this tutorial.

This tutorial walks through running a Pegasus workflow experiment that spans FABRIC and Chameleon Edge simultaneously, with HTCondor as the deployment layer.

## What you will build

You will run a two-task Pegasus workflow distributed across execute nodes on two separate testbeds — FABRIC and Chameleon Edge — within a single HTCondor pool. One FABRIC node acts as the HTCondor submit node, execute node, and central manager, FABRIC and Chameleon Edge each contribute execute nodes, and HTCondor schedules tasks across all of them transparently.

The workflow itself is minimal: Task A produces an output file, Task B consumes it. The point is not the computation but the infrastructure — by the end you will have provisioned nodes on two different testbeds, configured them into a single HTCondor pool, submitted a Pegasus workflow, and collected results, all from one config file and three commands.

## Prerequisites

Before you begin, confirm all of the following:

1. You have completed Tutorial 1 and are comfortable with the basic `kiso up / run / down` workflow.
1. You have a FABRIC account with an active project allocation. See [Set up on FABRIC](../how-to/testbeds/fabric.md).
1. You have a Chameleon account with an active project allocation. See [Set up on Chameleon Edge](../how-to/testbeds/chameleon-edge.md).
1. **Public IP addresses are available on both testbeds for the HTCondor submit and central manager nodes.** This is a hard requirement for multi-testbed HTCondor, not a configuration preference. See [Components — HTCondor](../concepts/components.md) for why this is necessary.

## Step 1 — Configure the experiment for two testbeds

Create `experiment.yml`:

```{literalinclude} ../_includes/multi-testbed-experiment/experiment.yml
:language: yaml
```

Notice that the `execute` label appears on nodes from **both** testbeds. HTCondor treats them as a single pool regardless of where they physically run.

## Step 2 — Write the Pegasus workflow script

Create `workflow.py` alongside `experiment.yml`:

```{literalinclude} ../_includes/multi-testbed-experiment/workflow.py
:language: python
```

This workflow has two dependent tasks. HTCondor schedules them across the available execute nodes on FABRIC and Chameleon Edge.

## Step 3 — Run the Pegasus workflow

**Provision all resources and install HTCondor on all nodes:**

```bash
kiso up experiment.yml
```

Kiso provisions nodes on both FABRIC and Chameleon Edge, installs HTCondor, and configures the pool so all execute nodes (from both testbeds) register with the central manager.

**Run the Pegasus workflow:**

```bash
kiso run experiment.yml
```

Kiso submits the Pegasus workflow to the HTCondor submit node. Pegasus schedules individual tasks to execute nodes — Kiso and HTCondor handle the cross-testbed routing transparently.

## Step 4 — Collect results and view them

```bash
ls -l output/

# Workflow outputs
cat output/result-a.txt
cat output/result-b.txt

# Pegasus workflow statistics
cat output/distributed-workflow/instance-0/run0001/statistics/summary.txt
```

All results are collected into the same output directory structure. See [Collect and export results](../how-to/collect-results.md) for details on the output format and how to export results.

**Tear down all resources:**

```bash
kiso down experiment.yml
```

This destroys resources on both FABRIC and Chameleon.

## What you have accomplished

🎉 Congratulations — what you just did is genuinely impressive. You have run a Pegasus workflow across two separate testbeds from a single Kiso config file. Specifically, you have:

- ✅ Provisioned nodes on FABRIC and Chameleon simultaneously with `kiso up`
- ✅ Configured all those nodes into a single HTCondor pool spanning two different network domains
- ✅ Submitted a Pegasus workflow that scheduled tasks across execute nodes on both testbeds
- ✅ Collected results into a single output directory

This is a non-trivial distributed systems achievement. 🏆 Doing it manually — provisioning two testbeds, installing and configuring HTCondor on each, establishing cross-testbed connectivity, submitting a workflow, and retrieving outputs — would require hours of careful work and deep familiarity with both testbed APIs. You did it with a config file and three commands. 🚀 That is exactly what Kiso is designed to make possible, and you have now seen it work at scale.

## What's next

- [Run a Pegasus workflow](../how-to/experiment-types/pegasus.md) — Pegasus configuration options in detail
- [How Kiso extensions work](../extending/how-extensions-work.md) — add new testbeds, software runtimes, or experiment types
