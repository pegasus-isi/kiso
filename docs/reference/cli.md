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

## `kiso ssh`

SSH into a provisioned node by label or alias.

```
kiso ssh [OPTIONS] NODE_ALIAS [EXTRA_SSH_ARGS]...
```

**Arguments:**

| Argument         | Required | Description                                                                  |
| ---------------- | -------- | ---------------------------------------------------------------------------- |
| `NODE_ALIAS`     | Yes      | Label or node alias to connect to. Accepts `[user@]<label-or-alias>` format. |
| `EXTRA_SSH_ARGS` | No       | Additional arguments passed verbatim to the underlying `ssh` command.        |

**Options:**

| Option               | Default    | Description                                                                                  |
| -------------------- | ---------- | -------------------------------------------------------------------------------------------- |
| `-o, --output PATH`  | `output`   | Directory containing the EnOSlib environment (must match the `--output` used with `kiso up`) |
| `-c, --command TEXT` | —          | Execute a command on the remote node instead of opening an interactive shell                 |
| `-t / -T`            | `-t` (tty) | Allocate (`-t`) or suppress (`-T`) a pseudo-TTY. Suppress when piping output from `-c`       |

**Examples:**

```bash
# Interactive shell on the node with label submit-host
kiso ssh submit-host

# Connect as a specific user
kiso ssh ubuntu@submit-host

# Run a one-off command
kiso ssh -c "hostname" submit-host

# Run a command without TTY (useful for piping output)
kiso ssh -T -c "cat /etc/os-release" submit-host

# Pass extra SSH options (e.g. port forwarding)
kiso ssh submit-host -- -vvv
```

**Notes:**

- Resources must be provisioned (`kiso up`) before connecting.
- `NODE_ALIAS` can be either a **label** defined in the `sites` section of the config or the node's own **alias** assigned by the testbed. Labels that map to more than one node are not usable — use the specific node alias instead.
- The `user@` prefix overrides the default login user for the node. Without it, Kiso uses the user configured by the testbed (e.g. `cc` for Chameleon bare metal, `rocky` for FABRIC Rocky images).
- `EXTRA_SSH_ARGS` are appended after `--` and passed through to `ssh` unchanged.
- Not supported on Chameleon Edge — those resources are containers without SSH access.

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

# 3. (Optional) Inspect a node while resources are up
kiso ssh submit-host

# 4. Run experiments and collect results
kiso run experiment.yml

# 5. Tear down
kiso down experiment.yml
```

## See also

- [Config file reference](config.md) — all supported config keys
- [Collect and export results](../how-to/collect-results.md) — working with the output directory
