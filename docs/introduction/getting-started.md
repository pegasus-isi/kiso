# Getting started

## Prerequisites

- Python version `3.9` or higher.
- Vagrant: `Vagrant` and `VirtualBox`.
- FABRIC: An account and an allocation on `FABRIC`.
- Chameleon: An account and an allocation on `Chameleon Cloud`.

## Installation

Installing `Kiso` varies based on what testbed(s) you want to use. Choose one of the following:

### Vagrant

```sh
pip install kiso[vagrant]
```

See [Set up on Vagrant](../how-to/testbeds/vagrant.md) for more information.

```{hint}
Starting a new experiment? Check out our [Vagrant starter kit](https://github.com/pegasus-isi/kiso-vagrant-starter) for a quick start.
```

### FABRIC

```sh
pip install kiso[fabric]

# On macOS
brew install rsync
```

See [Set up on FABRIC](../how-to/testbeds/fabric.md) for more information.

```{caution}
Some FABRIC sites assign IPv6 addresses as the management IP. macOS' `rsync` implementation fails connecting to these IPv6 address via jump hosts. To fix this, install `rsync` from Homebrew.
```

```{hint}
Starting a new experiment? Check out our [FABRIC starter kit](https://github.com/pegasus-isi/kiso-fabric-starter) for a quick start.
```

### Chameleon Cloud

```sh
pip install kiso[chameleon]
```

See [Set up on Chameleon Cloud](../how-to/testbeds/chameleon.md) for more information.

See [Set up on Chameleon Edge](../how-to/testbeds/chameleon-edge.md) for more information.

```{hint}
Starting a new experiment? Check out our [Chameleon starter kit](https://github.com/pegasus-isi/kiso-chameleon-starter) for a quick start.
```

### Combine multiple testbeds

```sh
pip install kiso[all]
# - OR -
pip install kiso[vagrant,fabric,chameleon]
```

## Next Steps

- [Your first experiment](../tutorials/first-experiment.md) — walkthrough from a fresh installation of Kiso to a working experiment result
- [Concepts](../concepts/what-is-kiso.md) — understand how sites, software, deployments, and experiments fit together
- [Experiment gallery](../examples/index.md) — explore real-world experiments built with Kiso
