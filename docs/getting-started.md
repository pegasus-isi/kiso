# Getting Started

## Prerequisites

- Python version `3.9` or higher.
- An account on `Chameleon Cloud` and/or `FABRIC`.
- An allocation on `Chameleon Cloud` and/or `FABRIC`.
- `Vagrant` and `VirtualBox`.

```{eval-rst}
.. hint::

    Starting a new experiment? Check out our [template](https://github.com/pegasus-isi/kiso-experiment-template) for a quick start.
```

## Installation

```sh
pip3 install kiso
```

### Vagrant

- Install `Vagrant`.
- Install `VirtualBox`.
- Install `Vagrant` dependencies needed by `Kiso`.

```sh
$ pip3 install kiso[vagrant]
```

### Chameleon Cloud

- An account on `Chameleon Cloud`.
- A project allocation on `Chameleon Cloud`.
- [Create and download](https://chameleoncloud.readthedocs.io/en/latest/technical/gui.html#api-access) application credentials for the desired `Chameleon Cloud` site.
- [Create and download](https://chameleoncloud.readthedocs.io/en/latest/technical/gui.html#api-access), or [Import your SSH key](https://chameleoncloud.readthedocs.io/en/latest/technical/gui.html#api-access) to the desired `Chameleon Cloud` site.
- Install `Chameleon` dependencies needed by `Kiso`.

```sh
$ pip3 install kiso[chameleon]
```

### FABRIC

- An account on `FABRIC`.
- A project on `FABRIC`.
- Getting started with `FABRIC` is [here](https://learn.fabric-testbed.net/article-categories/getting-started/).
- Install `FABRIC` dependencies needed by `Kiso`.

```sh
$ pip3 install kiso[fabric]

# On macOS
$ brew install rsync
```

```{eval-rst}
.. caution::

    Some FABRIC sites assign IPv6 addresses as the management IP. macOS' `rsync` implementation fails connecting to these IPv6 address via jump hosts. To fix this, install `rsync` from Homebrew.
```

## Your First Experiment

The following example uses Vagrant (no cloud account required) to provision a local VM, install Docker, and run a shell experiment that prints "Hello, world!".

**1. Create `experiment.yml`**

```yaml
sites:
  - kind: vagrant
    backend: virtualbox
    box: bento/rockylinux-9
    user: vagrant
    resources:
      machines:
        - labels:
            - submit
          backend: virtualbox
          box: bento/rockylinux-9
          user: vagrant
          flavour: "large"
          number: 1
      networks:
        - labels:
            - net
          cidr: "172.16.42.0/16"

software:
  docker:
    labels:
      - submit

experiments:
  - kind: shell
    name: hello-world
    description: Print a message
    scripts:
      - labels:
          - submit
        script: |
          #!/bin/bash
          echo "Hello, world!" > hello.txt
    outputs:
      - labels:
          - submit
        src: hello.txt
        dst: ./
```

**2. Validate the configuration**

```sh
$ kiso check experiment.yml
```

**3. Provision resources and install software**

```sh
$ kiso up experiment.yml
```

**4. Run the experiment**

```sh
$ kiso run experiment.yml

# View the output
cat hello.txt
```

**5. Tear down resources**

```sh
$ kiso down experiment.yml
```

## CLI Reference

For full details on each command and its options, see the [Command Line Tool](clt.rst) reference.

```sh
$ kiso --help

 Usage: kiso [OPTIONS] COMMAND [ARGS]...

 🏇 Kiso: Edge to Cloud Workflows: Advancing Workflow Management in the Computing Continuum.

╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --debug/--no-debug                                                                                                  │
│ --help  -h    Show this message and exit.                                                                           │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ──────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ check        Check the experiment configuration.                                                                    │
│ down         Destroy the resources provisioned for the experiments.                                                 │
│ run          Run the defined experiments.                                                                           │
│ up           Create the resources needed to run the experiment.                                                     │
│ version      Display the version information.                                                                       │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

 Check our docs at https://kiso.readthedocs.io/en/v0.1.0a10 for more details.

$ kiso check --help
 _   __ _
| | / /(_)
| |/ /  _  ___   ___
|    \ | |/ __| / _ \
| |\  \| |\__ \| (_) |
\_| \_/|_||___/ \___/  v0.1.0a10

 Usage: kiso check [OPTIONS] [EXPERIMENT_CONFIG]

 Check the experiment configuration.

╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help  -h    Show this message and exit.                                                                           │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

 Check our docs at https://kiso.readthedocs.io/en/v0.1.0a10 for more details.

$ kiso up --help
 _   __ _
| | / /(_)
| |/ /  _  ___   ___
|    \ | |/ __| / _ \
| |\  \| |\__ \| (_) |
\_| \_/|_||___/ \___/  v0.1.0a10

 Usage: kiso up [OPTIONS] [EXPERIMENT_CONFIG]

 Create the resources needed to run the experiment.

╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --force   -f                                                                                                        │
│ --output  -o  DIRECTORY  Environment to use for the experiment.                                                     │
│ --help    -h             Show this message and exit.                                                                │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

 Check our docs at https://kiso.readthedocs.io/en/v0.1.0a10 for more details.

$ kiso run --help
 _   __ _
| | / /(_)
| |/ /  _  ___   ___
|    \ | |/ __| / _ \
| |\  \| |\__ \| (_) |
\_| \_/|_||___/ \___/  v0.1.0a10

 Usage: kiso run [OPTIONS] [EXPERIMENT_CONFIG]

 Run the defined experiments.

╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --force   -f                                                                                                        │
│ --output  -o  DIRECTORY  Environment to use for the experiment.                                                     │
│ --help    -h             Show this message and exit.                                                                │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

 Check our docs at https://kiso.readthedocs.io/en/v0.1.0a10 for more details.

$ kiso down --help
 _   __ _
| | / /(_)
| |/ /  _  ___   ___
|    \ | |/ __| / _ \
| |\  \| |\__ \| (_) |
\_| \_/|_||___/ \___/  v0.1.0a10

 Usage: kiso down [OPTIONS] [EXPERIMENT_CONFIG]

 Destroy the resources provisioned for the experiments.

╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --output  -o  DIRECTORY  Environment to use for the experiment.                                                     │
│ --help    -h             Show this message and exit.                                                                │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

 Check our docs at https://kiso.readthedocs.io/en/v0.1.0a10 for more details.

$ kiso version --help

 Usage: kiso version [OPTIONS]

 Display the version information.

╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help  -h  Show this message and exit.                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

 Check our docs at https://kiso.readthedocs.io/en/v0.1.0a10 for more details.
```
