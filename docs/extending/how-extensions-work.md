# How Kiso extensions work

This page explains the extension model — what Kiso expects from any new component, and how the plugin system works.

For step-by-step guides to implementing specific extension types, see:

- [Add a software runtime](add-software.md)
- [Add a deployment](add-deployment.md)
- [Add an experiment type](add-experiment-type.md)

## How the plugin system works

```{mermaid}
flowchart TD
    subgraph load ["At import time"]
        EP["pyproject.toml<br/>entry_points"]
        PD["Plugin discovery<br/>(kiso.software / .deployment / .experiment)"]
        SC["Compose global JSON schema<br/>from all plugin schemas"]
        EP --> PD --> SC
    end

    subgraph runtime ["kiso check / up / run / down"]
        V["Validate YAML<br/>against composed schema"]
        DC["dacite.from_dict()<br/>into typed dataclasses"]
        CH["plugin.check()<br/>validate labels + resources"]
        EX["plugin.\_\_call\_\_()<br/>execute (Ansible / orchestration)"]
        SC --> V --> DC --> CH --> EX
    end
```

## The extension model

Kiso uses Python entry points for plugin discovery. There are three plugin groups:

| Group             | Purpose                                         |
| ----------------- | ----------------------------------------------- |
| `kiso.software`   | Software installers (Docker, Apptainer, Ollama) |
| `kiso.deployment` | Deployment systems (HTCondor)                   |
| `kiso.experiment` | Experiment runners (Pegasus, Shell)             |

Plugins are Python packages registered in `pyproject.toml`. At startup, Kiso queries all registered entry points in each group and loads the plugins dynamically. The config schema and configuration dataclasses are assembled from all registered plugins — adding a plugin automatically adds its config keys to the schema validator.

## What each extension type must implement

Every plugin exports a **runner/installer class** with three methods:

```python
class MyPlugin:
    config_type: type  # A dataclass for typed configuration
    schema: dict  # A JSON schema dict for config validation

    def __init__(self, config):
        """Initialize with a validated config instance."""

    def check(self, label_to_machines: dict) -> None:
        """Validate that the config makes sense given the available nodes.
        Raise an exception if the config is invalid."""

    def __call__(self, env) -> None:
        """Execute the plugin (install software, run experiment, etc.)."""
```

Each plugin subpackage also provides:

- `configuration.py` — the dataclass for typed config (`config_type`)
- `schema.py` — the JSON schema dict (`schema`)

Software and deployment plugins install via Ansible. The `__call__` method typically invokes an Ansible playbook (`main.yml`) via EnOSlib.

## Contracts by extension type

### Software installer contract

- Must install the software on all nodes matching the specified `labels`
- Must be idempotent (running twice produces the same result as running once)
- Must not interfere with other software installers running on the same nodes
- Must handle the case where the software is already installed

### Deployment contract

- Must configure the deployment system on nodes matching the specified `labels`
- Must be idempotent
- The `check` method must validate label references and daemon kind combinations

### Experiment runner contract

- Must execute the experiment and wait for completion
- Must provide a way to retrieve results. WHat results are returned can be user-defined or determined by the runner.
- Must respect the `timeout` parameter (if applicable)
- Must exit cleanly and allow `kiso down` to proceed regardless of experiment outcome

## Config key naming conventions

Config keys use snake_case. They must be valid YAML/TOML identifiers. Examples: `labels`, `version`, `config_file`, `submit_node_labels`.

Reserved prefix: `kiso.*` — do not use this for your own keys.

## Error handling and logging

- Raise informative exceptions from `check()` to surface config errors before provisioning starts
- Use Python's standard `logging` module for all log output
- Use `logger.debug()` for verbose output, `logger.info()` for progress, `logger.error()` for failures
- Do not use `print` to output to stdout, use `rich.console.Console` instead.

## See also

- [Add a software runtime](add-software.md) — implementing a new software installer
- [Add a deployment](add-deployment.md) — implementing a new deployment
- [Add an experiment type](add-experiment-type.md) — implementing a new experiment runner
- [Software interface reference](reference/software-interface.md) — complete method signatures
- [Deployment interface reference](reference/deployment-interface.md)
- [Experiment type interface reference](reference/experiment-type-interface.md)
