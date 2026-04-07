# What is Kiso?

## The problem Kiso solves

A growing class of computer science research requires realistic edge-to-cloud infrastructure: IoT sensors, edge devices, and cloud resources working together. Testbeds like FABRIC and Chameleon make this hardware accessible, but using them is harder than it should be. Each has its own API, credential system, and resource model. Setting up bare-metal machines, configuring networking between them, and reproducing that setup later requires deep systems knowledge and substantial manual effort — time that researchers would rather spend on the science itself.

A researcher exploring job scheduling strategies or fault tolerance may not have that systems expertise. Even one who does still needs to build layers of custom code for provisioning, configuration, and orchestration before a single experiment can run. This process is error-prone, time-consuming, and produces environments that are difficult to reproduce.

Kiso solves this by making the experiment config file the single source of truth. You describe what you want — resources, software, workflow, results — and Kiso handles the testbed-specific details.

## Core design philosophy

**Config-driven.** Every experiment is fully described in a single YAML file. No ad-hoc shell scripts, no manual SSH sessions, no undocumented steps. If the config file is the same, the experiment is the same.

**Testbed-portable.** The same config file runs on Vagrant locally and on FABRIC or Chameleon with minimal modification — like the `kind` field in the `sites` section. This is not a convenience feature; it is the central design goal. Vagrant is where you develop and test. FABRIC and Chameleon are where you run at scale.

**Composable components.** Testbeds, software runtimes, deployment systems, and experiment types are independent plugins. Any combination is valid. You can run a Shell experiment on Vagrant without Docker, or a Pegasus workflow on Chameleon with HTCondor and Apptainer.

## Design goals

These goals shaped Kiso's architecture from the start:

**Remote launch.** Kiso runs on your laptop or desktop. You install it locally, point it at a testbed, and it provisions and manages remote resources without requiring you to SSH in and run commands manually.

**Automation.** Provisioning, software installation, deployment configuration, and result retrieval are all automated. You should not need to write custom shell scripts to set up the environment — that is Kiso's job.

**Reproducibility.** The experiment config explicitly captures every aspect of the experiment: resource roles, software, workflow structure, and execution parameters. The same config re-run on the same testbed produces the same environment.

**Layered architecture.** Kiso builds on [EnOSlib](https://discovery.gitlabpages.inria.fr/enoslib/) for programmatic access to testbed resources, which in turn uses Ansible for remote execution. Each layer handles a distinct concern.

**Multiple testbed backends.** Kiso supports FABRIC, Chameleon, Chameleon Edge, and Vagrant (for local prototyping). Experiments developed locally on Vagrant can be moved to a real testbed with minimal changes.

**Edge device support.** Kiso can incorporate edge hardware — Raspberry Pis, NVIDIA Jetson devices, and similar IoT nodes — alongside cloud resources in the same experiment. This makes it possible to run realistic edge-to-cloud workflows, not just cloud-only ones.

**Extensibility.** New software runtimes, deployment systems, and experiment types can be added as plugins without modifying Kiso's core.

## Who Kiso is for

Kiso is for researchers who run experiments on academic computing testbeds. It assumes you are technically proficient — you can write shell scripts, understand YAML, and have used SSH — but does not assume familiarity with any particular testbed or experiment framework.

**Kiso is not** a general-purpose cloud orchestrator. It does not manage production infrastructure, handle billing, or replace tools like Terraform or Kubernetes for non-research use cases.

**Kiso is not** a job scheduler. HTCondor, which Kiso can deploy, is the scheduler. Kiso manages the lifecycle around it.

**Kiso is** an experiment framework for academic research on testbeds.

While Kiso was conceived for scientific workflow management — coordinating data-intensive tasks with Pegasus across distributed resources — its modular design makes it equally well-suited for a broader class of experiments. In particular, it provides a natural foundation for deploying and studying **agentic frameworks**, where autonomous AI agents require consistent resource provisioning, cross-site communication, and result collection. Kiso handles all of that automatically, letting researchers focus on the agent behavior rather than the infrastructure beneath it.

## Component categories

Kiso components fall into four categories. Any combination is valid — they are mostly independent of each other.

| Category             | Components                                 | Purpose                                           |
| -------------------- | ------------------------------------------ | ------------------------------------------------- |
| **Testbeds**         | Vagrant, FABRIC, Chameleon, Chameleon Edge | Where resources are provisioned                   |
| **Software**         | Docker, Apptainer, Ollama                  | What runs on the resources                        |
| **Deployments**      | HTCondor                                   | How work is distributed across resources          |
| **Experiment types** | Shell, Pegasus                             | How the experiment itself is defined and executed |

A typical experiment uses one testbed, optionally one or more software runtimes, optionally one deployment, and one or more experiment types.

For a detailed explanation of each component, see [Components](components.md).

## See also

- [The experiment model](experiment-model.md) — the four-phase lifecycle of a Kiso experiment
- [Config file anatomy](config-anatomy.md) — how the config file is structured
- [Your first experiment](../tutorials/first-experiment.md) — a concrete walkthrough
