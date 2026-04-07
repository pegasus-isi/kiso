# Your first experiment

This tutorial walks you from a fresh installation of Kiso to a working experiment result. You will run a simple shell experiment locally using Vagrant, then run the **same config** on FABRIC — demonstrating testbed portability in practice.

## What you will build

You will run a shell experiment that provisions a local Vagrant VM, installs Docker on it, runs a container that prints the VM hostname, and retrieves the output back to your machine. The experiment itself is intentionally trivial — the goal is to understand how Kiso's config file, labels, and four-phase lifecycle fit together before working with real testbed infrastructure.

At the end of the tutorial you will make a single one-line change to the same config to run it on FABRIC, demonstrating testbed portability.

## Prerequisites

- Python 3.9 or later
- [VirtualBox](https://www.virtualbox.org/wiki/Downloads) installed and working
- [Vagrant](https://developer.hashicorp.com/vagrant/install) installed

## Step 1 — Install Kiso

```bash
pip install kiso[vagrant]
```

To run on other testbeds later, install the matching extra: `kiso[fabric]` or `kiso[chameleon]`.

Verify the installation:

```bash
kiso version
```

## Step 2 — Write the config file

Create a file called `experiment.yml` in a new directory:

```yaml
name: hello-kiso

sites:
  - kind: vagrant
    backend: virtualbox
    box: bento/rockylinux-9
    resources:
      machines:
        - labels:
            - compute
          flavour: small
          number: 1
      networks:
        - labels:
            - r1
          cidr: 172.16.42.0/16

software:
  docker:
    labels:
      - compute

experiments:
  - kind: shell
    name: shell-experiment
    description: An experiment to print a message
    scripts:
      - labels:
          - compute
        script: |
          #!/bin/bash
          docker run --rm alpine echo "Hello, world!" | tee hello.txt
    outputs:
      - labels:
          - compute
        src: hello.txt
        dst: output
```

This config does three things:

- Provisions one small Vagrant VM labelled `compute`
- Installs Docker on that VM
- Runs a single shell experiment that pulls and runs the Docker `alpine` image, prints `Hello, world!`, and downloads the output to `output/` directory

The `labels` field is how Kiso connects resources to software and experiments — everything targeting `compute` runs on the same machine.

## Step 3 — Run the experiment locally on Vagrant

**Validate the config:** (optional but recommended):

```bash
kiso check experiment.yml
```

**Provision the VM and install software:**

```bash
kiso up experiment.yml
```

Kiso creates the Vagrant VM and installs Docker on it. This may take a few minutes the first time.

**Run the experiment:**

```bash
kiso run experiment.yml
```

You will see the hostname of the Vagrant VM printed by the `alpine` container.

**Check the output:**

```bash
ls -l output/hello.txt
```

Experiment output(s) are stored in the `output/` directory (the default; change it with `--output`).

**Tear down when done:**

```bash
kiso down experiment.yml
```

## Step 4 — Collect and view results

After `kiso run`, results are written to the output directory:

```
output/
  hello.txt
```

View the output:

```bash
cat output/hello.txt
```

## Step 5 — Run the same config on FABRIC

This is the payoff. Change a few lines in `experiment.yml` and get it running on FABRIC:

```yaml
sites:
  - kind: fabric
    rc_file: secrets/fabric_rc
    walltime: "02:00:00"
    resources:
      machines:
        - labels:
            - submit
          site: FIU
          flavour: small
          number: 1
      networks:
        - labels:
            - v4
          kind: FABNetv4
          site: FIU
          nic:
            kind: SharedNIC
            model: ConnectX-6
```

<!-- TODO(mayani): Remove the nic from networks section as this is the default and not required after EnOSlib accepts MR #273 and it released
          nic:
            kind: SharedNIC
            model: ConnectX-6
-->

Everything else — the software block, the experiment block, the labels — stays identical.

Before running on FABRIC you need credentials. See [Set up on FABRIC](../how-to/testbeds/fabric.md) for how to configure them.

Once credentials are in place:

```bash
kiso up experiment.yml
kiso run experiment.yml
kiso down experiment.yml
```

The experiment runs on FABRIC infrastructure using the modified experiment file.

## What you have accomplished

🎉 Congratulations — you have run a complete Kiso experiment end to end. That is no small thing. Specifically, you have:

- ✅ Written a config file that fully describes an experiment — resources, software, and what to run
- ✅ Used `kiso up` to provision a VM and install Docker on it automatically, without touching a shell on the remote machine
- ✅ Used `kiso run` to execute a script on that VM and retrieve the output to your local machine
- ✅ Moved the same experiment from a local Vagrant VM to real FABRIC infrastructure

That last point is worth pausing on. Most researchers spend days porting an experiment from one environment to another. You just did it in few lines. 🚀 The config file you wrote is a fully reproducible experiment description — anyone with Kiso and the same config can reproduce exactly what you ran, on any supported testbed. That is the core idea behind everything else Kiso does, and you have already seen it work.

## What's next

- **Tutorial 2**: [Multi-testbed experiment](multi-testbed.md) — span FABRIC and Chameleon simultaneously
- **Concepts**: [The experiment model](../concepts/experiment-model.md) — understand the four-phase lifecycle
- **Concepts**: [Config file anatomy](../concepts/config-anatomy.md) — understand every section of the config
