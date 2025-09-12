# Getting Started

## Prerequisites

- Python version `3.9` or higher.
- An account on `Chameleon Cloud` and/or `FABRIC`.
- An allocation on `Chameleon Cloud` and/or `FABRIC`.
- `Vagrant` and `VirtualBox`.

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
- Install `FABRIC` dependencies needed by `Kiso`.

```sh
$ pip3 install kiso[fabric]
```

Not yet implemented.

### Usage

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
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

 Check out our docs at https://kiso.readthedocs.io/en/v0.1.0a1/ for more details.

$ kiso check --help
 _   __ _
| | / /(_)
| |/ /  _  ___   ___
|    \ | |/ __| / _ \
| |\  \| |\__ \| (_) |
\_| \_/|_||___/ \___/  v0.1.0a1


 Usage: kiso check [OPTIONS] [EXPERIMENT_CONFIG]

 Check the experiment configuration.

╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --help  -h    Show this message and exit.                                                                           │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

 Check out our docs at https://kiso.readthedocs.io/en/v0.1.0a1/ for more details.

$ kiso up --help
 _   __ _
| | / /(_)
| |/ /  _  ___   ___
|    \ | |/ __| / _ \
| |\  \| |\__ \| (_) |
\_| \_/|_||___/ \___/  v0.1.0a1


 Usage: kiso up [OPTIONS] [EXPERIMENT_CONFIG]

 Create the resources needed to run the experiment.

╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --force   -f                                                                                                        │
│ --output  -o  DIRECTORY  Environment to use for the experiment.                                                     │
│ --help    -h             Show this message and exit.                                                                │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

 Check out our docs at hhttps://kiso.readthedocs.io/en/v0.1.0a1/ for more details.

$ kiso run --help
 _   __ _
| | / /(_)
| |/ /  _  ___   ___
|    \ | |/ __| / _ \
| |\  \| |\__ \| (_) |
\_| \_/|_||___/ \___/  v0.1.0a1


 Usage: kiso run [OPTIONS] [EXPERIMENT_CONFIG]

 Run the defined experiments.

╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --force   -f                                                                                                        │
│ --output  -o  DIRECTORY  Environment to use for the experiment.                                                     │
│ --help    -h             Show this message and exit.                                                                │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

 Check out our docs at https://kiso.readthedocs.io/en/v0.1.0a1/ for more details.

$ kiso down --help
 _   __ _
| | / /(_)
| |/ /  _  ___   ___
|    \ | |/ __| / _ \
| |\  \| |\__ \| (_) |
\_| \_/|_||___/ \___/  v0.1.0a1


 Usage: kiso down [OPTIONS] [EXPERIMENT_CONFIG]

 Destroy the resources provisioned for the experiments.

╭─ Options ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --output  -o  DIRECTORY  Environment to use for the experiment.                                                     │
│ --help    -h             Show this message and exit.                                                                │
╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

 Check out our docs at https://kiso.readthedocs.io/en/v0.1.0a1/ for more details.
```
