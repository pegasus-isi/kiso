# Experiment type interface reference

Complete specification of the interface an experiment type plugin must implement.

## Class attributes

| Attribute     | Type | Required | Description                                                               |
| ------------- | ---- | -------- | ------------------------------------------------------------------------- |
| `config_type` | type | Yes      | A dataclass that defines the typed configuration for this experiment type |
| `schema`      | dict | Yes      | A JSON schema dict for validating the user's config                       |

## Methods

### `__init__(self, config, index, variables)`

Initialize the runner with a validated configuration instance.

| Parameter   | Type                                     | Description                                      |
| ----------- | ---------------------------------------- | ------------------------------------------------ |
| `config`    | `Kiso`                                   | Validated configuration                          |
| `index`     | `int`                                    | Index of this experiment in the experiments list |
| `variables` | `dict[str, str \| int \| float] \| None` | Variable overrides                               |

### `check(self, label_to_machines)`

Validate that the experiment configuration is consistent with available nodes.

| Parameter           | Type                    | Description                                        |
| ------------------- | ----------------------- | -------------------------------------------------- |
| `label_to_machines` | `enoslib.objects.Roles` | Mapping from label name to list of machine objects |

**Must raise** a descriptive exception if:

- Any label referenced in the config does not exist in `label_to_machines`
- Required dependencies (e.g. HTCondor) are not configured
- Any other pre-flight validation fails

### `__call__(self, env)`

Execute the experiment and wait for completion.

| Parameter   | Type                       | Description                                                                           |
| ----------- | -------------------------- | ------------------------------------------------------------------------------------- |
| `wd`        | `str`                      | Local experiment working directory                                                    |
| `remote_wd` | `str`                      | Remote working directory on provisioned resources                                     |
| `resultdir` | `str`                      | Result directory                                                                      |
| `labels`    | `enoslib.objects.Roles`    | Maps label → list of host objects. `env["output"]` is the output directory path.      |
| `env`       | `enoslib.task.Environment` | EnOSlib environment dict. For e.g., `env["roles"]` maps label → list of host objects. |

**Must** render status on the console using `rich.console.Console`.

**Must** write experiment outputs to `resultdir`.

**Must** wait for the experiment to complete before returning.

**Must** respect the configured `timeout` (if applicable) and raise a `KisoTimeoutError` or similar if the experiment exceeds it.

**Must raise** a descriptive exception if the experiment fails. This causes `kiso run` to report failure while still allowing `kiso down` to run.

## Configuration dataclass conventions

Every experiment type configuration must include:

| Field         | Type | Required | Notes                                             |
| ------------- | ---- | -------- | ------------------------------------------------- |
| `name`        | str  | Yes      | Used in output paths and log messages             |
| `kind`        | str  | Yes      | Must match the entry point key (e.g. `"pegasus"`) |
| `description` | str  | No       | Human-readable description                        |
| `variables`   | dict | No       | Per-experiment variable overrides                 |

Additional fields are experiment-type-specific.

## JSON schema conventions

The schema must include `"kind"` as a required field with a `const` value matching the entry point name. This is how Kiso dispatches configs to the correct runner:

```python
schema = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "const": "myworkflow"},
        "name": {"type": "string"},
        # ... other fields
    },
    "required": ["kind", "name"],
    "additionalProperties": False,
}
```

## Output directory conventions

Write experiment outputs to the path `resultdir`.

Standard files:

- `stdout` — standard output from the experiment
- `stderr` — standard error from the experiment

Additional files (workflow outputs, result files, etc.) may be placed in subdirectories.

## Error conditions

The `__call__` method must handle:

| Condition                        | Action                        |
| -------------------------------- | ----------------------------- |
| Experiment script exits non-zero | Raise `RuntimeError`          |
| Workflow timeout exceeded        | Raise `KisoTimeoutError`      |
| Node unreachable during run      | Raise descriptive exception   |
| Output file collection fails     | Log warning; optionally raise |

## See also

- [Add an experiment type](../add-experiment-type.md) — step-by-step implementation guide
- [How Kiso extensions work](../how-extensions-work.md) — extension model overview
