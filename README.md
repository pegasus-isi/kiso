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

Install Kiso with the extra for your testbed:

```sh
pip install kiso[vagrant]    # local VMs — good for development
pip install kiso[fabric]     # FABRIC testbed
pip install kiso[chameleon]  # Chameleon Cloud and Chameleon Edge (same package, different OpenRC files)
pip install kiso[all]        # all testbeds
```

Then run your experiment:

```sh
# 1. Validate the config
kiso check experiment.yml

# 2. Provision and configure
kiso up experiment.yml

# 3. Run experiments
kiso run experiment.yml

# 4. Collect results, then tear down
kiso down experiment.yml
```

See the [Your first experiment](https://kiso.readthedocs.io/en/latest/tutorials/first-experiment.html) tutorial for a complete walkthrough, or use the [experiment template](https://github.com/pegasus-isi/kiso-experiment-template) to scaffold a new experiment.

## What's Supported

| Category        | Options                                          |
| --------------- | ------------------------------------------------ |
| **Testbeds**    | Vagrant, FABRIC, Chameleon Cloud, Chameleon Edge |
| **Software**    | Docker, Apptainer, Ollama                        |
| **Deployment**  | HTCondor                                         |
| **Experiments** | Pegasus workflows, Shell scripts                 |

New testbeds, software, and experiment types can be added as plugins via Python entry points. See [Extending Kiso](https://kiso.readthedocs.io/en/latest/extending/how-extensions-work.html).

## Documentation

- [Your first experiment](https://kiso.readthedocs.io/en/latest/tutorials/first-experiment.html) — install Kiso and run a working experiment end-to-end
- [Multi-testbed experiment](https://kiso.readthedocs.io/en/latest/tutorials/multi-testbed.html) — span FABRIC and Chameleon simultaneously
- [Concepts](https://kiso.readthedocs.io/en/latest/concepts/what-is-kiso.html) — understand sites, labels, software, deployments, and experiments
- [Config file reference](https://kiso.readthedocs.io/en/latest/reference/config.html) — every supported configuration key
- [Extending Kiso](https://kiso.readthedocs.io/en/latest/extending/how-extensions-work.html) — add custom testbeds, software, and experiment types
- [Full documentation](https://kiso.readthedocs.io)

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
- [Chameleon Cloud](https://www.chameleoncloud.org) — NSF-funded cloud testbed supported by Kiso; includes both bare-metal nodes (CHI@UC, CHI@TACC) and edge devices (CHI@Edge) under the same project allocation, each with its own OpenRC credentials file
- [FABRIC](https://portal.fabric-testbed.net) — nationwide programmable research infrastructure supported by Kiso
- [Vagrant](https://www.vagrantup.com/) — tool for managing local VMs; used by Kiso for local development without a cloud account
- [VirtualBox](https://www.virtualbox.org/) — virtualization platform used as the default Vagrant backend

## Funding

Kiso is funded by the National Science Foundation (NSF) under award [2403051](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2403051).

## License

Apache 2.0 © [Pegasus ISI](https://github.com/pegasus-isi)
