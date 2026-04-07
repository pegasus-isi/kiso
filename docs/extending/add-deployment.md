# Add a deployment

This guide walks through implementing a new deployment plugin for Kiso (for example, Slurm or Kubernetes).

Read [How Kiso extensions work](how-extensions-work.md) first. Refer to the [Deployment interface reference](reference/deployment-interface.md) for complete method signatures.

## Prerequisites

- Familiarity with Python `dataclasses`, `Ansible`, and `EnOSlib`

## Step 1 — Create the plugin subpackage

```
src/kiso_slurm/
  __init__.py
  installer.py
  configuration.py
  schema.py
  main.yml           ← Ansible playbook
```

## Step 2 — Define the configuration dataclass

Deployment configurations are typically arrays of daemon/role specifications. Model this as a list:

```python
# configuration.py
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SlurmDaemon:
    kind: str  # e.g. "controller" | "worker"
    labels: list[str]
    config_file: Optional[str] = None


# The top-level config type is a list of daemon specs
SlurmConfiguration = list[SlurmDaemon]
```

## Step 3 — Define the JSON schema

```python
# schema.py
schema = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["controller", "worker"],
            },
            "labels": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "config_file": {
                "type": "string",
            },
        },
        "required": ["kind", "labels"],
        "additionalProperties": False,
    },
    "minItems": 1,
}
```

## Step 4 — Write the Ansible playbook

In `main.yml`:

```yaml
- name: Install Slurm
  hosts: "{{ labels | join(':') }}"
  become: true
  vars:
    slurm_kind: "{{ kind }}"
  tasks:
    - name: Install Slurm packages
      ansible.builtin.package:
        name:
          - slurm
          - "{% if slurm_kind == 'controller' %}slurmctld{% else %}slurmd{% endif %}"
        state: present
```

```{note}
To support Chameleon Edge, the steps to install the software have to be codes as shell commands too.
```

## Step 5 — Implement the installer class

```python
# installer.py
import logging
from pathlib import Path

from kiso import edge, utils

from kiso_slurm.configuration import SlurmDaemon
from kiso_slurm.schema import SCHEMA

log = logging.getLogger(__name__)


class SlurmInstaller:
    schema: dict = SCHEMA
    config_type: type = list[SlurmDaemon]  # List of SlurmDaemon

    def __init__(self, config: list[SlurmDaemon]):
        self.config = config

    def check(self, label_to_machines: dict) -> None:
        for daemon in self.config:
            for label in daemon.labels:
                if label not in label_to_machines:
                    raise ValueError(
                        f"Slurm daemon '{daemon.kind}' references label '{label}' "
                        "which does not exist in sites"
                    )

    def __call__(self, env) -> None:
        labels = env["labels"]
        for daemon in self.config:
            log.info("Installing Slurm %s on labels: %s", daemon.kind, daemon.labels)
            _labels = utils.resolve_labels(labels, self.config.labels)
            vms, containers = utils.split_labels(_labels, labels)
            results = []

            if vms:
                results.extend(
                    utils.run_ansible([Path(__file__).parent / "main.yml"], roles=vms)
                )

            if containers:
                for container in containers:
                    results.append(
                        edge.run_script(
                            container,
                            Path(__file__).parent / "slurm.sh",
                            "--no-dry-run",
                            timeout=-1,
                        )
                    )

        # Render the results
```

```{seealso}
See [Kiso API reference](../reference/api.md) to reuse code to upload files, download files, and run commands, request public IPs, etc.
```

## Step 6 — Register the entry point

In `pyproject.toml`:

```toml
[project.entry-points."kiso.deployment"]
slurm = "kiso_slurm.installer:SlurmInstaller"
```

Reinstall:

```bash
pip install -e ".[all]"
```

## Step 7 — Verify the plugin loads

```bash
kiso check experiment.yml
```

With a config that uses `deployment.slurm`, the validator should accept it. An invalid config should be rejected.

## Step 8 — Write tests

Add tests in `tests/` following the existing patterns for `htcondor`. Run:

```bash
pytest tests/
```

## See also

- [Deployment interface reference](reference/deployment-interface.md) — complete method signatures
- [How Kiso extensions work](how-extensions-work.md) — extension model overview
- [Contributing](../about/contributing.md) — submitting your plugin to the project
