# Deployment interface reference

Complete specification of the interface a deployment plugin must implement.

## Class attributes

| Attribute     | Type | Required | Description                                                                  |
| ------------- | ---- | -------- | ---------------------------------------------------------------------------- |
| `config_type` | type | Yes      | A dataclass (or `list`) that defines the typed configuration for this plugin |
| `schema`      | dict | Yes      | A JSON schema dict for validating the user's config                          |

## Methods

### `__init__(self, config)`

Initialize the installer with a validated configuration instance.

| Parameter | Type                      | Description             |
| --------- | ------------------------- | ----------------------- |
| `config`  | instance of `config_type` | Validated configuration |

### `check(self, label_to_machines)`

Validate that the deployment configuration is consistent with available nodes.

| Parameter           | Type                    | Description                                        |
| ------------------- | ----------------------- | -------------------------------------------------- |
| `label_to_machines` | `enoslib.objects.Roles` | Mapping from label name to list of machine objects |

**Must raise** a descriptive exception if:

- Any label referenced in the config does not exist in `label_to_machines`
- An invalid combination of daemon kinds is configured (e.g. `central-manager` without any `execute` nodes)
- Any other configuration invariant is violated

### `__call__(self, env)`

Install and configure the deployment system on the specified nodes.

| Parameter | Type                       | Description                                                                          |
| --------- | -------------------------- | ------------------------------------------------------------------------------------ |
| `env`     | `enoslib.task.Environment` | EnOSlib environment dict. For e.g., `env["roles"]` maps label → list of host objects |

**Must be idempotent**.

**Must raise** a descriptive exception if the deployment fails to install or configure correctly.

## Configuration dataclass conventions

Deployments typically configure multiple daemon types. Model this as a list of daemon specifications:

```python
@dataclass
class DaemonSpec:
    kind: str  # Daemon type (enum)
    labels: list[str]  # Target nodes
    config_file: Optional[str] = None  # Optional custom config
```

The top-level `config_type` for a deployment is typically a list of daemon specs.

## JSON schema conventions

Deployment schemas are typically arrays:

```python
schema = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["controller", "worker"]},
            "labels": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        },
        "required": ["kind", "labels"],
        "additionalProperties": False,
    },
    "minItems": 1,
}
```

## Error conditions

The `check()` method must handle:

| Condition                              | Action                                 |
| -------------------------------------- | -------------------------------------- |
| Label not found in `label_to_machines` | Raise `ValueError` with label name     |
| Invalid `kind` value                   | Raise `ValueError` with allowed values |
| Incompatible daemon combination        | Raise `ValueError` with explanation    |

## See also

- [Add a deployment](../add-deployment.md) — step-by-step implementation guide
- [How Kiso extensions work](../how-extensions-work.md) — extension model overview
