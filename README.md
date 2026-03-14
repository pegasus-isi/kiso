<p align="center">
    <img width="50%" alt="logo-kiso" src="https://github.com/user-attachments/assets/15e0777c-6305-4783-9a65-cdfabfdd52dc" />
</p>

# Kiso

> Describe your experiment in a YAML file — Kiso handles provisioning, software setup, execution, and result collection.

[![Tests](https://github.com/pegasus-isi/kiso/actions/workflows/tests.yaml/badge.svg)](https://github.com/pegasus-isi/kiso/actions/workflows/tests.yaml)
![License](https://img.shields.io/pypi/l/kiso.svg?logo=apache&color=blue&label=License)
![Latest](https://img.shields.io/pypi/v/kiso.svg?label=Latest)
![Python Versions](https://img.shields.io/pypi/pyversions/kiso.svg?logo=python)
![PyPi Downloads](https://img.shields.io/pypi/dm/kiso?logo=pypi&color=green&label=PyPI%20Downloads)
![Code Style](https://img.shields.io/badge/Code%20Style-black-blue)
![Contributors](https://img.shields.io/github/contributors-anon/pegasus-isi/kiso?color=green&label=Contributors)
[![Documentation](https://readthedocs.org/projects/kiso/badge/?version=latest)](https://kiso.readthedocs.io/en/latest)

## Why Kiso

Setting up experiments across cloud and edge testbeds typically means writing custom provisioning scripts, manually installing software on remote nodes, and stitching together execution logic for each new environment. This work is repetitive, error-prone, and hard to reproduce.

Kiso replaces that with a single declarative configuration file. The same experiment definition runs on Chameleon Cloud, FABRIC, or a local Vagrant VM — no changes to your experiment code required.

## Quick Start

```sh
pip install kiso
kiso check experiment.yml  # validate your config
kiso up experiment.yml     # provision resources and install software
kiso run experiment.yml    # run the experiment
kiso down experiment.yml   # tear down resources
```

See [Getting Started](docs/getting-started.md) for a complete walkthrough, or use the [experiment template](https://github.com/pegasus-isi/kiso-experiment-template) to scaffold a new experiment.

## What's Supported

| Category | Options |
|---|---|
| **Testbeds** | Chameleon Cloud, Chameleon Edge, FABRIC, Vagrant |
| **Software** | Docker, Apptainer, Ollama |
| **Deployment** | HTCondor |
| **Experiments** | Pegasus workflows, Shell scripts |

New testbeds, software, and experiment types can be added as plugins via Python entry points. See [Extending Kiso](docs/extending.rst).

## Documentation

- [Getting Started](docs/getting-started.md) — install Kiso and run your first experiment
- [Concepts](docs/concepts.rst) — understand sites, labels, software, deployments, and experiments
- [Experiment Configuration](docs/experiment-configuration-schema.rst) — full YAML schema reference
- [Example Experiments](docs/example-experiments.md) — real-world experiments built with Kiso
- [Extending Kiso](docs/extending.rst) — add custom testbeds, software, and experiment types
- [Full Documentation](https://kiso.readthedocs.io)

## Contributing

Contributions are welcome. To get started:

```sh
git clone https://github.com/pegasus-isi/kiso.git
cd kiso
pip install -e ".[all]"
pre-commit install
```

Please follow [conventional commits](https://www.conventionalcommits.org/) for commit messages. Open an issue before submitting large changes.

## References

- [Pegasus Workflow Management System](https://pegasus.isi.edu) — scientific workflow engine used to define and execute experiments in Kiso
- [EnOSlib](https://discovery.gitlabpages.inria.fr/enoslib/) — infrastructure management library that Kiso builds on for provisioning and remote execution
- [Chameleon Cloud](https://www.chameleoncloud.org) — NSF-funded cloud testbed supported by Kiso
- [FABRIC](https://portal.fabric-testbed.net) — nationwide programmable research infrastructure supported by Kiso
- [Vagrant](https://www.vagrantup.com/) — tool for managing local VMs; used by Kiso for local development without a cloud account
- [VirtualBox](https://www.virtualbox.org/) — virtualization platform used as the default Vagrant backend

## Funding

Kiso is funded by the National Science Foundation (NSF) under award [2403051](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2403051).

## License

Apache 2.0 © [Pegasus ISI](https://github.com/pegasus-isi)
