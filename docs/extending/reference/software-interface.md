# Software interface reference

Complete specification of the interface a software runtime plugin must implement.

## Class attributes

| Attribute     | Type | Required | Description                                                                                                      |
| ------------- | ---- | -------- | ---------------------------------------------------------------------------------------------------------------- |
| `config_type` | type | Yes      | A dataclass that defines the typed configuration for this plugin. Used by Kiso to parse and validate the config. |
| `schema`      | dict | Yes      | A JSON schema dict that Kiso uses to validate the user's config before calling `__init__`.                       |

## Methods

### `__init__(self, config)`

Initialize the installer with a validated configuration instance.

| Parameter | Type                      | Description                                                  |
| --------- | ------------------------- | ------------------------------------------------------------ |
| `config`  | instance of `config_type` | Validated configuration, already parsed from the user's YAML |

Called once per experiment run, after config validation passes.

### `check(self, label_to_machines)`

Validate that the configuration is consistent with the available nodes.

| Parameter           | Type                    | Description                                        |
| ------------------- | ----------------------- | -------------------------------------------------- |
| `label_to_machines` | `enoslib.objects.Roles` | Mapping from label name to list of machine objects |

**Must raise** a descriptive exception if any label in the config does not exist in `label_to_machines`, or if any other configuration invariant is violated.

Called during `kiso check` and at the start of `kiso up`, before any provisioning occurs.

### `__call__(self, env)`

Install the software on the nodes specified in the configuration.

| Parameter | Type                       | Description                                                                           |
| --------- | -------------------------- | ------------------------------------------------------------------------------------- |
| `env`     | `enoslib.task.Environment` | EnOSlib environment dict. For e.g., `env["roles"]` maps label → list of host objects. |

**Must be idempotent**: calling this method twice on already-provisioned nodes must produce the same result as calling it once.

**Must not** raise an exception if the software is already installed and at the correct version.

**Must raise** a descriptive exception if installation fails.

## Configuration dataclass conventions

The `config_type` dataclass fields become the config keys users write in YAML. Follow these conventions:

| Convention                            | Example                               |
| ------------------------------------- | ------------------------------------- |
| Field names use snake_case            | `labels`, `config_file`, `model_name` |
| Required fields have no default       | `labels: list[str]`                   |
| Optional fields have a default        | `version: Optional[str] = None`       |
| Lists use `list[str]` not `List[str]` | `labels: list[str]`                   |

## JSON schema conventions

| Convention                                     | Example                  |
| ---------------------------------------------- | ------------------------ |
| Top-level is `"type": "object"`                | —                        |
| `required` lists all required fields           | `"required": ["labels"]` |
| `"additionalProperties": false`                | Prevents unknown keys    |
| `labels` is always an array with `minItems: 1` | —                        |

## Example: minimal software plugin

```python
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
from enoslib.api import run_ansible


@dataclass
class MyRuntimeConfig:
    labels: list[str]
    version: Optional[str] = None


class MyRuntimeInstaller:
    config_type = MyRuntimeConfig
    schema = {
        "type": "object",
        "properties": {
            "labels": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "version": {"type": "string"},
        },
        "required": ["labels"],
        "additionalProperties": False,
    }

    def __init__(self, config: MyRuntimeConfig):
        self.config = config

    def check(self, label_to_machines: dict) -> None:
        for label in self.config.labels:
            if label not in label_to_machines:
                raise ValueError(f"Unknown label: {label!r}")

    def __call__(self, env) -> None:
        playbook = Path(__file__).parent / "main.yml"
        run_ansible(
            [str(playbook)],
            roles=env["roles"],
            extra_vars={"labels": self.config.labels},
        )
```

## See also

- [Add a software runtime](../add-software.md) — step-by-step implementation guide
- [How Kiso extensions work](../how-extensions-work.md) — extension model overview
