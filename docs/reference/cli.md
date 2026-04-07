# CLI reference

Every Kiso CLI command and flag.

## Global options

```
kiso [OPTIONS] COMMAND [ARGS]...
```

| Option                 | Default      | Description                |
| ---------------------- | ------------ | -------------------------- |
| `--debug / --no-debug` | `--no-debug` | Enable debug-level logging |
| `--help`               | —            | Show help and exit         |

## `kiso check`

Check the experiment configuration.

```
kiso check [OPTIONS] [EXPERIMENT_CONFIG]
```

**Arguments:**

| Argument            | Required | Default          | Description                                                   |
| ------------------- | -------- | ---------------- | ------------------------------------------------------------- |
| `EXPERIMENT_CONFIG` | No       | `experiment.yml` | Path to the experiment YAML file. Must exist and be readable. |

**Example:**

```bash
kiso check experiment.yml
```

**Exit codes:**

| Code | Meaning                                                |
| ---- | ------------------------------------------------------ |
| `0`  | Config is valid                                        |
| `1`  | Config is invalid (validation error printed to stderr) |

## `kiso up`

Create the resources needed to run the experiment.

```
kiso up [OPTIONS] [EXPERIMENT_CONFIG]
```

**Arguments:**

| Argument            | Required | Default          | Description                      |
| ------------------- | -------- | ---------------- | -------------------------------- |
| `EXPERIMENT_CONFIG` | No       | `experiment.yml` | Path to the experiment YAML file |

**Options:**

| Option                 | Default      | Description                                                 |
| ---------------------- | ------------ | ----------------------------------------------------------- |
| `--force / --no-force` | `--no-force` | Tear down existing resources and recreate them from scratch |
| `-o, --output PATH`    | `output`     | Directory to store the EnOSlib environment and run state    |

**Examples:**

```bash
# Basic provisioning
kiso up experiment.yml

# Force rebuild of existing resources
kiso up --force experiment.yml

# Use a custom output directory
kiso up --output /data/exp1 experiment.yml
```

## `kiso run`

Run the defined experiments.

```
kiso run [OPTIONS] [EXPERIMENT_CONFIG]
```

**Arguments:**

| Argument            | Required | Default          | Description                      |
| ------------------- | -------- | ---------------- | -------------------------------- |
| `EXPERIMENT_CONFIG` | No       | `experiment.yml` | Path to the experiment YAML file |

**Options:**

| Option                 | Default      | Description                                                                                  |
| ---------------------- | ------------ | -------------------------------------------------------------------------------------------- |
| `--force / --no-force` | `--no-force` | Disregard previous run results and rerun the experiment                                      |
| `-o, --output PATH`    | `output`     | Directory containing the EnOSlib environment (must match the `--output` used with `kiso up`) |

**Examples:**

```bash
# Run the experiment
kiso run experiment.yml

# Re-run, discarding previous results
kiso run --force experiment.yml

# Use a custom output directory
kiso run --output /data/exp1 experiment.yml
```

**Notes:**

- Resources must be provisioned (`kiso up`) before running
- Results are written to `<output>/run/<experiment-name>/`

## `kiso down`

Destroy the resources provisioned for the experiments.

```
kiso down [OPTIONS] [EXPERIMENT_CONFIG]
```

**Arguments:**

| Argument            | Required | Default          | Description                      |
| ------------------- | -------- | ---------------- | -------------------------------- |
| `EXPERIMENT_CONFIG` | No       | `experiment.yml` | Path to the experiment YAML file |

**Options:**

| Option              | Default  | Description                                  |
| ------------------- | -------- | -------------------------------------------- |
| `-o, --output PATH` | `output` | Directory containing the EnOSlib environment |

**Examples:**

```bash
kiso down experiment.yml
kiso down --output /data/exp1 experiment.yml
```

**Notes:**

- Destroys all provisioned resources. This action is irreversible.
- Collect all results before running `kiso down`.

## `kiso version`

Display the version information.

```
kiso version
```

**Examples:**

```bash
kiso version
```

## Typical workflow

```bash
# 1. Validate the config
kiso check experiment.yml

# 2. Provision and configure
kiso up experiment.yml

# 3. Run experiments and collect results
kiso run experiment.yml

# 4. Tear down
kiso down experiment.yml
```

## See also

- [Config file reference](config.md) — all supported config keys
- [Collect and export results](../how-to/collect-results.md) — working with the output directory
