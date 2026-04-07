# Add an experiment type

This guide walks through implementing a new experiment type plugin for Kiso (for example, a custom workflow engine).

Read [How Kiso extensions work](how-extensions-work.md) first. Refer to the [Experiment type interface reference](reference/experiment-type-interface.md) for complete method signatures.

## Prerequisites

- Familiarity with Python dataclasses and EnOSlib
- An existing Kiso development setup: `pip install -e ".[all]" && pre-commit install`

## Step 1 — Create the plugin subpackage

```
src/kiso_myworkflow/
  __init__.py
  runner.py
  configuration.py
  schema.py
```

## Step 2 — Define the configuration dataclass

```python
# configuration.py
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MyWorkflowConfiguration:
    kind: str = "myworkflow"
    name: str
    main: str  # Script to execute
    submit_node_labels: list[str]
    description: Optional[str] = None
    timeout: int = 600
    variables: dict = field(default_factory=dict)
```

## Step 3 — Define the JSON schema

```python
# schema.py
schema = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "const": "myworkflow"},
        "name": {"type": "string"},
        "main": {"type": "string"},
        "submit_node_labels": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
        },
        "description": {"type": "string"},
        "timeout": {"type": "integer", "minimum": 1},
        "variables": {
            "type": "object",
            "additionalProperties": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "number"},
                ]
            },
        },
    },
    "required": ["kind", "name", "main", "submit_node_labels"],
    "additionalProperties": False,
}
```

## Step 4 — Implement the runner class

```python
# runner.py
import logging
from pathlib import Path

from enoslib.api import run_command

from kiso import constants as const, edge, utils

from kiso_myworkflow.configuration import MyWorkflowConfiguration
from kiso_myworkflow.schema import SCHEMA

log = logging.getLogger(__name__)


class MyWorkflowRunner:
    kind: str = "myworkflow"

    schema: dict = SCHEMA

    config_type: type = MyWorkflowConfiguration

    def __init__(self, config: MyWorkflowConfiguration):
        self.config = config

    def check(self, label_to_machines: dict) -> None:
        """Validate labels and configuration."""
        for label in self.config.submit_node_labels:
            if label not in label_to_machines:
                raise ValueError(
                    f"Experiment '{self.config.name}' references label '{label}' "
                    "which does not exist in sites"
                )

    def __call__(self, env) -> None:
        """Execute the workflow and wait for completion."""
        log.info("Running experiment: %s", self.config.name)

        labels = env["labels"]
        _labels = utils.resolve_labels(labels, self.config.labels)
        vms, containers = utils.split_labels(_labels, labels)
        results = []

        if vms:
            # Steps to run the experiment on VMS
            # Either as an Ansible playbook YAML file or
            # as Python code using utils.actions (wrapper over EnOSlib' actions)
            with utils.actions(
                roles=vms,
                run_as=const.KISO_USER,
                on_error_continue=True,
                strategy="free",
            ) as p:
                p.copy(
                    src=str(src),
                    dest=str(dst),
                    mode="preserve",
                    task_name=f"Copy input file {instance}",
                )
                p.shell(f"rm -rf tempfile", chdir=self.remote_wd)
            results.extend(p.results)

        if containers:
            # Steps to run the experiment on containers
            for container in containers:
                results.append(
                    edge.run_script(
                        container,
                        Path(__file__).parent / "runner.sh",
                        "--no-dry-run",
                        timeout=-1,
                    )
                )

        # Render the results
```

```{seealso}
See [Kiso API reference](../reference/api.md) to reuse code to upload files, download files, andrun commands, request public IPs, etc.
```

## Step 5 — Register the entry point

In `pyproject.toml`:

```toml
[project.entry-points."kiso.experiment"]
myworkflow = "kiso_myworkflow.runner:MyWorkflowRunner"
```

Reinstall:

```bash
pip install -e ".[all]"
```

## Step 7 — Verify the plugin loads

```bash
kiso check experiment.yml
```

With a config that uses `experiments[]` with `kind: myworkflow`, the validator should accept it. An invalid config should be rejected.

## Step 8 — Write tests

Add tests in `tests/` following the existing patterns for `shell`, and `pegasus`. Run:

```bash
pytest tests/
```

## See also

- [Experiment type interface reference](reference/experiment-type-interface.md) — complete method signatures
- [How Kiso extensions work](how-extensions-work.md) — extension model overview
- [Contributing](../about/contributing.md) — submitting your plugin to the project
