# Components

Kiso components fall into four categories: Testbeds, Software, Deployments, and Experiment types. Any combination is valid — they are largely independent.

This page explains what each component is, what it does in the context of a Kiso experiment, and when you would choose it. For configuration details, see the how-to guides linked at the end of each section.

## Testbeds

Testbeds are infrastructure providers. The `kind` field in a `sites` entry selects the testbed.

(vagrant)=

### Vagrant

Vagrant manages local virtual machines using VirtualBox or libvirt. It is the **recommended starting point** for developing and testing experiments before running them on a real testbed. Local VMs can be spun up or down quickly, making iteration fast without consuming testbed allocations.

Use Vagrant when you are:

- Writing a new experiment config and want fast iteration without consuming testbed allocations
- Debugging experiment scripts locally
- Running experiments that do not require real network hardware

Vagrant is not a substitute for FABRIC or Chameleon when your experiment requires real physical hardware, specific network topologies, or large-scale resources. It is where you start, not where you finish.

See [Set up on Vagrant](../how-to/testbeds/vagrant.md).

(fabric)=

### FABRIC

FABRIC is a national-scale, programmable research infrastructure spanning 29 sites across the United States, with international presence at Amsterdam, CERN, Bristol, and Tokyo. It supports research in networking, cybersecurity, distributed computing, storage, 5G, machine learning, and data-intensive science. Core capabilities include programmable networking (P4-programmable Tofino switches at selected sites), heterogeneous accelerators (GPUs, FPGAs, and BlueField-3 DPUs), and high-speed optical interconnects between sites.

Use FABRIC when you need:

- Real network hardware (SmartNICs, etc.)
- Large-scale distributed systems experiments across multiple physical sites
- GPU or NVMe storage resources on testbed nodes

See [Set up on FABRIC](../how-to/testbeds/fabric.md).

(chameleon)=

### Chameleon

Chameleon is a large-scale, deeply reconfigurable experimental platform built to support computer science systems research, education, and emerging applications. It provides bare-metal nodes through an OpenStack-based interface at University of Chicago (CHI@UC) and TACC (CHI@TACC). Community projects on Chameleon range from operating systems and virtualization research to software-defined networking, artificial intelligence, and resource management.

Use Chameleon bare metal when you need:

- Bare-metal nodes
- Edge computing resources (Raspberry Pi, NVIDIA Jetson, etc.)

See [Set up on Chameleon](../how-to/testbeds/chameleon.md).

(chameleon-edge)=

### Chameleon Edge

Chameleon Edge (`kind: chameleon-edge`) shares the same Chameleon project allocation as Chameleon Cloud, but uses a **different OpenRC credentials file** specific to the CHI@Edge site. A CHI@UC or CHI@TACC credential file will not work with Chameleon Edge.

Chameleon Edge provisions containers on physical edge devices through CHI@Edge. Resources are containers running on IoT and edge hardware (Raspberry Pis, Jetson devices, and others), not virtual machines or bare-metal servers.

Use Chameleon Edge when you need:

- Edge computing resources (Raspberry Pi, NVIDIA Jetson, etc.)
- Container-based workloads on constrained hardware
- Experiments that span cloud and edge infrastructure

See [Set up on Chameleon Edge](../how-to/testbeds/chameleon-edge.md).

## Software

Software components install runtimes on provisioned nodes. They run during the Configure phase (`kiso up`).

(docker)=

### Docker

Docker is the general-purpose container runtime. Use Docker when your experiment software is packaged as container images and you are running on standard Linux VMs or bare-metal nodes.

Docker is the default choice when you need containers. Choose Apptainer instead when you are in an environment where Docker's daemon model is not permitted, like Chameleon Edge provisioned containers.

See [Use Docker](../how-to/software/docker.md).

(apptainer)=

### Apptainer

Apptainer (formerly Singularity) is a container runtime designed for HPC environments. Unlike Docker, it does not require a root daemon, making it appropriate for shared HPC clusters where Docker is restricted.

Use Apptainer when:

- You need rootless container execution
- You are working with Chameleon Edge containers

See [Use Apptainer](../how-to/software/apptainer.md).

(ollama)=

### Ollama

Ollama runs large language models and AI/ML models as a local service. It is specifically for AI/ML experiments on testbeds — it is **not** a general-purpose container runtime.

Use Ollama when your experiment involves:

- Running LLM inference on testbed nodes
- Evaluating AI models in controlled network environments
- AI/ML workloads that need dedicated GPU resources on testbed hardware

See [Run AI/ML experiments with Ollama](../how-to/software/ollama.md).

## Deployments

Deployments install and configure workload management systems across provisioned nodes.

(htcondor)=

### HTCondor

HTCondor is a distributed job scheduling system. In a Kiso experiment, HTCondor manages how individual experiment tasks are distributed across available execute nodes.

HTCondor is a natural fit for edge-to-cloud experiments for two reasons that distinguish it from traditional HPC schedulers like SLURM: it does not require a shared filesystem, and it is designed to tolerate resource and job failures, network latency, and intermittent connectivity. These properties are essential when execute nodes span geographically dispersed testbeds with heterogeneous network conditions.

HTCondor in Kiso supports four daemon types:

| Daemon kind       | Role                                                                        |
| ----------------- | --------------------------------------------------------------------------- |
| `personal`        | Single-machine setup — all daemons on one node. Use for simple experiments. |
| `central-manager` | Manages the pool — tracks which execute nodes are available                 |
| `submit`          | Accepts job submissions and routes them to execute nodes                    |
| `execute`         | Runs individual tasks                                                       |

HTCondor is currently the only supported deployment. Kiso's deployment abstraction is designed to support additional workload management systems in the future.

**Multi-testbed deployments — public IP requirement**

When HTCondor spans multiple testbeds, the submit and central manager daemons **must have public IP addresses**. This is a hard architectural requirement, not a configuration preference.

The reason: HTCondor daemons communicate over TCP. Execute nodes from FABRIC and execute nodes from Chameleon each live behind their testbed's private network. The only way for nodes on both networks to reach a shared central manager and submit node is if those nodes have addresses reachable from the public internet. Private addresses on one testbed are not routable from the other.

**Port 9618 requirement**

Port 9618 is the TCP port HTCondor uses for all inter-daemon communication — the Collector, Negotiator, Schedd, and Startd daemons all accept connections on it. Every node in an HTCondor pool must be able to reach the central manager on port 9618, and execute nodes must be reachable on port 9618 from the submit node for job dispatching to work.

<!-- On most testbeds (FABRIC, Chameleon bare metal, Vagrant), firewall rules are either absent or configurable at the network level, so port 9618 is typically reachable without special handling. Chameleon Edge is the exception: containers provisioned through CHI@Edge do not expose any ports by default, and there is no SSH access through which Ansible could configure the firewall after the fact. -->

Containers provisioned through CHI@Edge do not expose any ports by default, and there is no SSH access through which Ansible could configure the firewall after the fact. Kiso handles this automatically. When a machine with an HTCondor daemon role is provisioned on Chameleon Edge, Kiso declares port 9618 in the container port mapping at provisioning time, before the container starts. No manual firewall configuration is needed. This is transparent — the same experiment config works whether the execute nodes are Vagrant VMs, FABRIC slices, or Chameleon Edge containers.

## Experiment types

Experiment types define how the experiment itself runs.

### Shell

Shell runs one or more shell scripts on targeted nodes. It is the simplest experiment type — no workflow engine, no job scheduler, just scripts.

Use Shell when:

- Your experiment is a single command or a short script
- You do not need task dependencies or parallel job scheduling
- You are prototyping before moving to a more complex setup

See [Run a Shell experiment](../how-to/experiment-types/shell.md).

### Pegasus

Pegasus is a workflow management system for large-scale scientific workflows. Users describe their workflows using a high-level, resource-agnostic workflow description; Pegasus maps this to the available execution environment during a planning phase, discovering input data, executables, and site layout to produce an executable workflow. This separation between workflow description and execution site means the same workflow can run on Vagrant locally or on a distributed HTCondor pool across multiple testbeds without modification.

Pegasus builds on HTCondor DAGMan to manage workflow execution. It generates a Directed Acyclic Graph (DAG) of tasks, submits them to an HTCondor pool, and handles automatic retry of failed tasks and provenance tracking of results.

Use Pegasus when:

- Your experiment has multiple steps that depend on each other
- You need automatic retry of failed tasks
- You need to distribute tasks across many nodes
- You need provenance tracking of experiment results

Pegasus requires HTCondor in the `deployment` section.

See [Run a Pegasus workflow](../how-to/experiment-types/pegasus.md).

## See also

- [The experiment model](experiment-model.md) — how components fit into the four lifecycle phases
- [Config file anatomy](config-anatomy.md) — how to reference components in the config file
- [Config file reference](../reference/config.md) — all configuration keys for each component
