# Add a software runtime

This guide walks through implementing a new software runtime plugin for Kiso (for example, Podman or Singularity).

Read [How Kiso extensions work](how-extensions-work.md) first for background on the extension model. Refer to the [Software interface reference](reference/software-interface.md) for complete method signatures.

## Prerequisites

- Familiarity with Python dataclasses, Ansible, and EnOSlib
- An existing Kiso development setup: `pip install -e ".[all]" && pre-commit install`

## Step 1 — Create the plugin subpackage

Create a directory under `src/kiso/` for your plugin:

```
src/kiso_podman/
  __init__.py
  installer.py
  configuration.py
  schema.py
  main.yml           ← Ansible playbook
```

## Step 2 — Define the configuration dataclass

In `configuration.py`:

```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Podman:
    labels: list[str]
    version: Optional[str] = None
```

The dataclass fields become the config keys users write in their YAML. Field names use snake_case.

## Step 3 — Define the JSON schema

In `schema.py`:

```python
schema = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
        },
        "version": {
            "type": "string",
        },
    },
    "required": ["labels"],
    "additionalProperties": False,
}
```

The schema is used to validate user configs before provisioning starts.

## Step 4 — Write the Ansible playbook

In `main.yml`, write tasks to install the software:

```yaml
- name: Install Podman
  hosts: "{{ labels | join(':') }}"
  become: true
  tasks:
    - name: Install Podman
      ansible.builtin.package:
        name: "podman{% if version is defined %}={{ version }}{% endif %}"
        state: present
```

The playbook receives the `labels` variable as a list of hostnames resolved by EnOSlib.

```{note}
To support Chameleon Edge, the steps to install the software have to be codes as shell commands too.
```

## Step 5 — Implement the installer class

In `installer.py`:

```python
import logging
from pathlib import Path

from kiso import edge, utils

from kiso_podman.configuration import Podman
from kiso_podman.schema import SCHEMA

log = logging.getLogger(__name__)


class PodmanInstaller:
    schema: dict = SCHEMA
    config_type: type = Podman

    def __init__(self, config: Podman):
        self.config = config

    def check(self, label_to_machines: dict) -> None:
        """Validate that all referenced labels exist."""
        for label in self.config.labels:
            if label not in label_to_machines:
                raise ValueError(
                    f"Podman references label '{label}' which does not exist in sites"
                )

    def __call__(self, env) -> None:
        """Install Podman on nodes matching the configured labels."""
        log.info("Installing Podman on labels: %s", self.config.labels)
        labels = env["labels"]
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
                        Path(__file__).parent / "podman.sh",
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

In `pyproject.toml`, add the entry point under `[project.entry-points."kiso.software"]`:

```toml
[project.entry-points."kiso.software"]
podman = "kiso_podman.installer:PodmanInstaller"
```

Reinstall the package so the entry point is registered:

```bash
pip install -e ".[all]"
```

## Step 7 — Verify the plugin loads

```bash
kiso check experiment.yml
```

With a config that uses `software.podman`, the validator should accept it. An invalid config should be rejected.

## Step 8 — Write tests

Add tests in `tests/` following the existing patterns for `docker` and `apptainer`. Run:

```bash
pytest tests/
```

## See also

- [Software interface reference](reference/software-interface.md) — complete method signatures
- [How Kiso extensions work](how-extensions-work.md) — extension model overview
- [Contributing](../about/contributing.md) — submitting your plugin to the project
