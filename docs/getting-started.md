# Getting Started

## Pre requisites

- Python version `3.9` or higher.
- An account on `Chameleon Cloud` or `FABRIC`.
- An allocation on `Chameleon Cloud` or `FABRIC`.
- `Vagrant` and `VirtualBox`.

### Vagrant

- Install `Vagrant`.
- Install `VirtualBox`.
- Install `Vagrant` dependencies needed by `Kiso`.

```sh
$ pip3 install kiso[vagrant]
```

### Chameleon Cloud

- An account on `Chameleon Cloud` or `FABRIC`.
- A project allocation on `Chameleon Cloud` or `FABRIC`.
- [Create and download](https://chameleoncloud.readthedocs.io/en/latest/technical/gui.html#api-access) application credentials for the desired `Chameleon Cloud` site.
- [Create and download](https://chameleoncloud.readthedocs.io/en/latest/technical/gui.html#api-access), or [Import your SSH key](https://chameleoncloud.readthedocs.io/en/latest/technical/gui.html#api-access) to the desired `Chameleon Cloud` site.
- Install `Chameleon` dependencies needed by `Kiso`.

```sh
$ pip3 install kiso[chameleon]
```

### FABRIC

- An account on `FABRIC`.
- A project on `FABRIC`.
- Install `Chameleon` dependencies needed by `Kiso`.

```sh
$ pip3 install kiso[fabric]
```

Not yet implemented.

## Installation

```sh
pip3 install kiso
```

### Usage

```sh
$ kiso --help

 Usage: kiso [OPTIONS] COMMAND [ARGS]...

 🏇 Kiso: Edge to Cloud Workflows: Advancing Workflow Management in the Computing Continuum.

╭─ Options ────────────────────────────────────────────────────────────────────────────────╮
│ --help  -h    Show this message and exit.                                                │
╰──────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────────╮
│ check        Check the experiment configuration.                                         │
│ up           Create the resources needed to run the experiment.                          │
│ down         Destroy the resources provisioned for the experiments.                      │
│ run          Run the defined experiments.                                                │
╰──────────────────────────────────────────────────────────────────────────────────────────╯

 Check out our docs at https://readthedocs.org for more details.

$ kiso check --help
 _   __ _
| | / /(_)
| |/ /  _  ___   ___
|    \ | |/ __| / _ \
| |\  \| |\__ \| (_) |
\_| \_/|_||___/ \___/  0.0.0



 Usage: kiso check [OPTIONS] EXPERIMENT_CONFIG

 Check the experiment configuration.

╭─ Options ────────────────────────────────────────────────────────────────────────────────╮
│ --help  -h    Show this message and exit.                                                │
╰──────────────────────────────────────────────────────────────────────────────────────────╯

 Check out our docs at https://readthedocs.org for more details.

$ kiso create --help
 _   __ _
| | / /(_)
| |/ /  _  ___   ___
|    \ | |/ __| / _ \
| |\  \| |\__ \| (_) |
\_| \_/|_||___/ \___/  0.0.0



 Usage: kiso up [OPTIONS] EXPERIMENT_CONFIG

 Create the resources needed to run the experiment.

╭─ Options ────────────────────────────────────────────────────────────────────────────────╮
│ --help  -h    Show this message and exit.                                                │
╰──────────────────────────────────────────────────────────────────────────────────────────╯

 Check out our docs at https://readthedocs.org for more details.

$ kiso run --help
 _   __ _
| | / /(_)
| |/ /  _  ___   ___
|    \ | |/ __| / _ \
| |\  \| |\__ \| (_) |
\_| \_/|_||___/ \___/  0.0.0



 Usage: kiso run [OPTIONS] EXPERIMENT_CONFIG

 Run the defined experiments.

╭─ Options ────────────────────────────────────────────────────────────────────────────────╮
│ --help  -h    Show this message and exit.                                                │
╰──────────────────────────────────────────────────────────────────────────────────────────╯

 Check out our docs at https://readthedocs.org for more details.

$ kiso destroy --help
 _   __ _
| | / /(_)
| |/ /  _  ___   ___
|    \ | |/ __| / _ \
| |\  \| |\__ \| (_) |
\_| \_/|_||___/ \___/  0.0.0



 Usage: kiso down [OPTIONS] EXPERIMENT_CONFIG

 Destroy the resources provisioned for the experiments.

╭─ Options ────────────────────────────────────────────────────────────────────────────────╮
│ --help  -h    Show this message and exit.                                                │
╰──────────────────────────────────────────────────────────────────────────────────────────╯

 Check out our docs at https://readthedocs.org for more details.
```
