# Glossary

Definitions for terms used in Kiso documentation, including Kiso-specific terms, testbed terminology, and HTCondor terminology.

## Kiso terms

**Component**
One of the four categories of Kiso components: Testbed, Software, Deployment, or Experiment type. Components are combined in a config file to describe an experiment.

**Config file**
A YAML file that describes an experiment completely: resources, software, deployment, and experiment steps. The single source of truth for a Kiso experiment.

**Experiment**
A defined set of steps to execute on provisioned resources. Described in the `experiments` section of the config file.

**Label**
A user-defined string assigned to one or more machines in the `sites` section. Used to target machines in the `software`, `deployment`, and `experiments` sections. The connective tissue between config sections.

**Output directory**
The local directory (default: `output/`) where Kiso writes environment state and experiment results. Specified with `--output`.

**Plugin**
A Python package registered via entry points that adds a new component (software, deployment, or experiment type) to Kiso.

**Site**
An infrastructure provider entry in the `sites` config section. A single experiment can have multiple sites.

**Testbed portability**
Kiso's design goal: the same config file should run on any supported testbed with minimal changes.

## Testbed terms

### FABRIC

**Bastion host**
A gateway node through which users SSH to access FABRIC nodes. FABRIC nodes are not directly accessible from the internet; all connections go through the bastion.

**Fabric token**
A credential token downloaded from the FABRIC portal, used to authenticate API calls for provisioning resources.

**Floating IP**
A public IP address that can be attached to a FABRIC, Chameleon, or Chameleon Edge node, making it reachable from the internet. Required for HTCondor submit/central-manager nodes in multi-testbed deployments.

**Site (FABRIC)**
A FABRIC data centre location. FABRIC has sites at multiple universities and research institutions. Not to be confused with Kiso's `sites` config section.

**Slice**
A FABRIC resource reservation containing nodes, networks, and other components. Kiso creates and manages slices on your behalf.

### Chameleon

**Bare metal**
Physical servers allocated to a single user, providing dedicated hardware resources. Chameleon's primary resource model.

**Chameleon Edge**
A separate Chameleon site (CHI@Edge) that provides IoT and edge hardware (Raspberry Pis, Jetson devices, and others) as container-based resources. Chameleon Edge uses the same Chameleon project allocation as Chameleon Cloud, but requires its own site-specific OpenRC credentials file — a CHI@UC or CHI@TACC credential file will not work with CHI@Edge.

**Lease**
A Chameleon or Chameleon Edge resource reservation. Has a start time, end time (walltime), and specifies which hardware to reserve. Kiso creates leases on your behalf.

**OpenRC file**
A shell script downloaded from the Chameleon dashboard that sets environment variables for OpenStack API authentication. Required by Kiso for Chameleon access.

**Walltime**
The duration of a Chameleon lease. Specified in `HH:MM:SS` format. Resources are released when the walltime expires.

### Vagrant

**Box**
A Vagrant base image (pre-configured OS image). Kiso selects the appropriate box automatically.

**Flavour**
A predefined VM size: `small` (1 vCPU, 1 GB), `medium` (2 vCPU, 2 GB), or `large` (4 vCPU, 4 GB).

**Provider**
The virtualization backend Vagrant uses to create VMs. Kiso uses VirtualBox.

## HTCondor terms

**Central manager**
The HTCondor daemon responsible for matchmaking — tracking which execute nodes are available and which jobs are waiting. Must have a public IP in multi-testbed deployments.

**ClassAd**
A key-value structure used by HTCondor to describe jobs and resources. The matchmaker matches job requirements ClassAds to machine ClassAds.

**Condor pool**
The set of all HTCondor nodes (submit, central manager, and execute) that share a central manager. Kiso creates a pool per experiment.

**Execute node**
A node in the HTCondor pool that runs individual tasks. Can exist on multiple testbeds in a multi-testbed deployment.

**Personal HTCondor**
A single-machine HTCondor setup where one node runs all daemons (central manager, submit, and execute). Used for simple experiments.

**Submit node**
The node from which jobs are submitted to HTCondor. Also called the access point. Must have a public IP in multi-testbed deployments.

**Trust domain**
The security domain for an HTCondor pool. Kiso uses `kiso.scitech.isi.edu` as the trust domain for all pools it creates.

## Workflow and experiment terms

**DAG (Directed Acyclic Graph)**
A workflow structure where tasks are nodes and dependencies are directed edges. Used by Pegasus to represent experiment workflows with task ordering constraints.

**Pegasus**
A workflow management system that maps abstract workflow DAGs to concrete jobs submitted to HTCondor. Used for complex multi-step experiments with task dependencies.

**Provenance**
A record of what was run, with what inputs, on what resources, and when. Pegasus automatically captures provenance for all workflow executions.

**Shell experiment**
A Kiso experiment type that runs shell scripts on targeted nodes. The simplest experiment type.

**Workflow**
In the context of Pegasus: a DAG of computational tasks submitted to HTCondor for execution.

## See also

- [What is Kiso?](../concepts/what-is-kiso.md) — introduction to Kiso concepts
- [Components](../concepts/components.md) — detailed explanation of each component type
- [Config file anatomy](../concepts/config-anatomy.md) — how terms map to config structure
