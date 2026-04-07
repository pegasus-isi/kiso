# The experiment model

A Kiso experiment moves through four phases: **Reserve → Configure → Run → Collect**. Each phase maps to a CLI command. The config file drives all four.

## The four phases

```{mermaid}
flowchart TD
    up["kiso up"]
    run["kiso run"]
    down["kiso down"]

    up --> R["Reserve<br/>Provision nodes"]
    R --> C["Configure<br/>Install software + deployment"]
    C --> run
    run --> E["Run<br/>Execute experiments"]
    E --> down
    down --> D["Collect<br/>Retrieve results + release resources"]
```

### Reserve

`kiso up` provisions the infrastructure described in the `sites` section of the config. For Vagrant, this creates local VMs. For FABRIC, it submits a resource reservation request. For Chameleon, it creates a lease.

At the end of this phase, you have running machines with network connectivity, but no experiment software installed yet.

### Configure

Still part of `kiso up`, after provisioning. Kiso reads the `software` and `deployment` sections of the config and installs what is specified on the nodes that match the given labels. Docker, Apptainer, Ollama, HTCondor — all installed via Ansible.

At the end of this phase, the environment is ready to run the experiment. You can run `kiso up` again with `--force` to tear down and rebuild the environment from scratch.

### Run

`kiso run` executes the experiments described in the `experiments` section. For Shell experiments, it runs the specified scripts on the matching nodes. For Pegasus experiments, it submits the workflow to the HTCondor submit node and polls for completion.

When a Pegasus experiment finishes, Kiso automatically runs two Pegasus tools without any user intervention:

- **`pegasus-statistics`** — computes workflow performance metrics, including wall time (total elapsed time) and cumulative wall time (sum of all individual job runtimes).
- **`pegasus-analyzer`** — determines whether the workflow succeeded. If it failed, the analyzer identifies which jobs failed, captures their standard output and standard error, and highlights relevant Pegasus files for further investigation.

The results of both tools are written into the Pegasus submit directory, which is then collected as part of the output.

### Collect

After `kiso run`, results are in the output directory. The `outputs` field in each experiment specifies which files to retrieve from remote nodes and where to store them locally.

For Pegasus experiments, Kiso also automatically retrieves the Pegasus submit directory from the remote submit node, along with the `pegasus-statistics` and `pegasus-analyzer` output written into it. This happens regardless of whether an `outputs` field is specified.

`kiso down` tears down the provisioned resources. You typically run this after collecting results. Resources are destroyed — make sure you have retrieved everything you need first.

## Monitoring and debugging

All three commands — `kiso up`, `kiso run`, and `kiso down` — accept a `--debug` flag. When set, Kiso captures logs generated at every stage of the experiment, including calls to testbed APIs during provisioning, Ansible output during software installation, and runtime errors during experiment execution. These logs are useful for diagnosing a wide range of issues: intermittent testbed API errors, connectivity problems between nodes, failed package installs due to insufficient disk space, or unreachable external URLs during dependency fetching.

## The config file as single source of truth

The config file is not just input to the CLI. It is the complete, reproducible description of the experiment:

- Which testbed and resources to use
- What software to install
- How to deploy workload management
- What experiment to run and how
- What results to collect

Because all four phases read the same file, the experiment is self-documenting. Share the config file and anyone can reproduce the experiment on any supported testbed.

## Testbed portability

Testbed portability means the config file describes *what* the experiment needs, not *how* a specific testbed provides it.

This is only possible because Kiso abstracts the testbed-specific details:

- Resource provisioning (Vagrant VMs vs FABRIC slices vs Chameleon leases)
- SSH access (local vs credential-based)

The `labels` system is how this abstraction works in practice. A label like `compute` means the same thing regardless of which testbed provides the machine. Software, deployments, and experiments reference labels, not testbed-specific resource identifiers.

## See also

- [Config file anatomy](config-anatomy.md) — the structure of the config file
- [Components](components.md) — what each component does in the context of an experiment
- [CLI reference](../reference/cli.md) — full documentation for all commands
