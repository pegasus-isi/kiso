# API reference

Python API for plugin authors and advanced users. All symbols are importable from the modules listed below.

(api-utils)=

## `kiso.utils`

### Ansible helpers

#### `run_ansible`

```python
def run_ansible(playbooks, roles=None, extra_vars=None, ...) -> None
```

Run one or more Ansible playbooks against provisioned roles. Wraps `enoslib.run_ansible` with `on_error_continue=True` — task errors are logged but do not abort execution.

See the [EnOSlib `run_ansible` docs](https://discovery.gitlabpages.inria.fr/enoslib/apidoc/global_api.html#enoslib.api.run_ansible) for the full parameter list.

#### `actions`

```python
def actions(roles=None, ...) -> contextmanager
```

Context manager that builds and runs a sequence of Ansible tasks against provisioned roles. Wraps `enoslib.actions` with `on_error_continue=True` — task errors are logged but do not abort execution.

See the [EnOSlib `actions` docs](https://discovery.gitlabpages.inria.fr/enoslib/apidoc/global_api.html#enoslib.api.actions) for the full parameter list.

### Role and label helpers

#### `resolve_labels`

```python
def resolve_labels(labels: Roles, label_names: list[str]) -> Roles
```

| Parameter     | Type        | Description                                                                |
| ------------- | ----------- | -------------------------------------------------------------------------- |
| `labels`      | `Roles`     | Collection of labels to resolve from                                       |
| `label_names` | `list[str]` | Label names to filter or combine; empty list returns the original `labels` |

Returns a `Roles` object. Multiple names are merged with a logical OR.

#### `split_labels`

```python
def split_labels(split: Roles, labels: Roles) -> tuple[Roles, Roles]
```

Splits `split` into `(non-edge VMs, edge containers)` using `labels["chameleon-edge"]` as the separator.

| Parameter | Type    | Description                                               |
| --------- | ------- | --------------------------------------------------------- |
| `split`   | `Roles` | Complete label set to split                               |
| `labels`  | `Roles` | Reference label set containing the `chameleon-edge` label |

Returns `(vms, containers)`.

### IP helpers

#### `get_ips`

```python
def get_ips(machine: Host | ChameleonDevice) -> list[tuple[IPv4Address | IPv6Address, int]]
```

Returns all non-loopback, non-link-local IP addresses for a machine, sorted by priority.

| Priority | Address type |
| -------- | ------------ |
| `0`      | Public IPv4  |
| `1`      | Public IPv6  |
| `2`      | Private IPv4 |
| `3`      | Private IPv6 |

Floating IPs stored in `machine.extra["floating-ips"]` are included.

(api-schema)=

## `kiso.schema`

JSON schema objects used for experiment config validation. Schemas are assembled at import time from all registered plugins.

| Name             | Description                                                       |
| ---------------- | ----------------------------------------------------------------- |
| `COMMONS_SCHEMA` | Reusable sub-schemas: `labels`, `variables`, `script`, `location` |

Use `$ref` to pull individual `COMMONS_SCHEMA` definitions into a plugin schema:

```python
MY_SCHEMA = {
    "type": "object",
    "properties": {
        "labels": {"$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/labels"},
        "variables": {"$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/variables"},
        "script": {"$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/script"},
        "location": {"$ref": "py-obj:kiso.schema.COMMONS_SCHEMA#/$defs/location"},
    },
}
```

(api-objects)=

## `kiso.objects`

Shared dataclass types used across multiple modules.

### `Script`

```python
@dataclass
class Script:
    labels: list[str]
    script: str
    executable: str = "/bin/bash"
```

| Field        | Type        | Required | Default     | Description                             |
| ------------ | ----------- | -------- | ----------- | --------------------------------------- |
| `labels`     | `list[str]` | Yes      | —           | Labels identifying the target resources |
| `script`     | `str`       | Yes      | —           | Script content to execute               |
| `executable` | `str`       | No       | `/bin/bash` | Interpreter used to run the script      |

### `Location`

```python
@dataclass
class Location:
    labels: list[str]
    src: str
    dst: str
```

| Field    | Type        | Required | Default | Description                             |
| -------- | ----------- | -------- | ------- | --------------------------------------- |
| `labels` | `list[str]` | Yes      | —       | Labels identifying the target resources |
| `src`    | `str`       | Yes      | —       | Source file path                        |
| `dst`    | `str`       | Yes      | —       | Destination directory path              |

(api-edge)=

## `kiso.edge`

Helpers for interacting with Chameleon Edge (`ChameleonDevice`) containers. All functions require the `kiso[chameleon]` extra.

### `upload`

```python
def upload(
    container: ChameleonDevice,
    src: Path | str,
    dst: Path | str,
    user: str | None = None,
) -> CommandResult
```

Upload a file or directory to a Chameleon Edge container. Directories are uploaded file-by-file to work around API timeout limits.

| Parameter   | Type              | Default | Description                                       |
| ----------- | ----------------- | ------- | ------------------------------------------------- |
| `container` | `ChameleonDevice` | —       | Target container                                  |
| `src`       | `Path \| str`     | —       | Local source path                                 |
| `dst`       | `Path \| str`     | —       | Remote destination directory                      |
| `user`      | `str \| None`     | `None`  | Set as owner of uploaded files (defaults to root) |

Raises `ValueError` if `src` does not exist or `dst` is not an accessible directory.

### `download`

```python
def download(
    container: ChameleonDevice,
    src: Path | str,
    dst: Path | str,
) -> CommandResult
```

Download a file or directory from a Chameleon Edge container. Directories are downloaded file-by-file to work around API timeout limits.

| Parameter   | Type              | Description                 |
| ----------- | ----------------- | --------------------------- |
| `container` | `ChameleonDevice` | Source container            |
| `src`       | `Path \| str`     | Remote source path          |
| `dst`       | `Path \| str`     | Local destination directory |

Raises `ValueError` if `dst` is not an accessible local directory.

### `execute`

```python
def execute(
    container: ChameleonDevice,
    command: Path | str,
    *args: str,
    workdir: Path | str | None = None,
    timeout: int = 180,
    poll_interval: int = 1,
    user: str | None = None,
) -> CommandResult
```

Execute a command on a Chameleon Edge container. The command is wrapped so that stdout, stderr, and the exit code are captured via temporary files. Kiso polls for completion rather than blocking.

| Parameter       | Type                  | Default | Description                                        |
| --------------- | --------------------- | ------- | -------------------------------------------------- |
| `container`     | `ChameleonDevice`     | —       | Target container                                   |
| `command`       | `Path \| str`         | —       | Command to execute                                 |
| `*args`         | `str`                 | —       | Additional arguments passed to the command         |
| `workdir`       | `Path \| str \| None` | `/tmp`  | Working directory                                  |
| `timeout`       | `int`                 | `180`   | Maximum seconds to wait; `-1` to wait indefinitely |
| `poll_interval` | `int`                 | `1`     | Seconds between completion checks                  |
| `user`          | `str \| None`         | `None`  | Run command as this user (defaults to root)        |

Returns a `CommandResult`. `result.rc` is `-1` and `result.status` is `STATUS_TIMEOUT` when the command does not finish within `timeout`.

### `run_script`

```python
def run_script(
    container: ChameleonDevice,
    script: Path,
    *args: str,
    workdir: str | None = None,
    user: str | None = None,
    timeout: int = 180,
    poll_interval: int = 1,
    task_name: str | None = None,
) -> CommandResult
```

Upload a script to a container, make it executable, run it, and remove it.

| Parameter       | Type              | Default | Description                                    |
| --------------- | ----------------- | ------- | ---------------------------------------------- |
| `container`     | `ChameleonDevice` | —       | Target container                               |
| `script`        | `Path`            | —       | Local path to the script file                  |
| `*args`         | `str`             | —       | Arguments passed to the script                 |
| `workdir`       | `str \| None`     | `/tmp`  | Working directory on the container             |
| `user`          | `str \| None`     | `None`  | Run script as this user                        |
| `timeout`       | `int`             | `180`   | Maximum seconds to wait                        |
| `poll_interval` | `int`             | `1`     | Seconds between completion checks              |
| `task_name`     | `str \| None`     | `None`  | Label included in the returned `CommandResult` |

### `expanduser`

```python
def expanduser(container: ChameleonDevice, path: str | Path) -> str | Path
```

Expand a `~`-prefixed path to an absolute path by querying the container shell. Paths that do not start with `~` are returned unchanged. The return type matches the input type.

| Parameter   | Type              | Description        |
| ----------- | ----------------- | ------------------ |
| `container` | `ChameleonDevice` | Container to query |
| `path`      | `str \| Path`     | Path to expand     |

### `command_result`

```python
def command_result(
    container: ChameleonDevice,
    status: dict[str, Any],
    task_name: str | None,
) -> CommandResult
```

Convert a raw Zun API response dict into an EnOSlib `CommandResult`.

| Key in `status` | Description                                                    |
| --------------- | -------------------------------------------------------------- |
| `exit_code`     | Integer exit code, or `None` if the container is still running |
| `output`        | Combined stdout text from the container                        |

(api-ip)=

## `kiso.ip`

Functions for associating public IP addresses with nodes across testbeds.

### `associate_floating_ip`

```python
def associate_floating_ip(node: Host | ChameleonDevice) -> IPv4Address | IPv6Address
```

Attach a public IP address to a node. The strategy is determined by `node.extra["kind"]`.

| `kind` value     | Strategy                                                                                  |
| ---------------- | ----------------------------------------------------------------------------------------- |
| `chameleon`      | Reuses an existing floating IP or creates a new one via the OpenStack CLI                 |
| `chameleon-edge` | Reads `/etc/floating-ip` on the container or calls the Chameleon Edge API                 |
| `fabric`         | Creates an `IPv4Ext` L3 network and NIC, routes the IP, persists it to `/etc/floating-ip` |
| `vagrant`        | Always raises `KisoError` — public IPs are not supported for Vagrant VMs                  |

The acquired IP is appended to `node.extra["floating-ips"]`.

Raises `ValueError` for an unknown `kind` or a provider-level error. Raises `KisoError` for Vagrant nodes.

<!-- TODO(mayani): Refine the display API and then add to the docs
(api-display)=
## `kiso.display`


### `commons`

```python
def _render(console: Console, results: list[CommandResult]) -> None
```

Print a per-host status table to a Rich `Console`.

| Parameter | Type | Description |
|---|---|---|
| `console` | `Console` | Rich console to print to |
| `results` | `list[CommandResult]` | Results returned by an Ansible or command run |

Each host appears once. The final status is `STATUS_FAILED` if any result for that host failed; skipped tasks (`conditional result was false`) do not override the accumulated status. -->

(api-errors)=

## `kiso.errors`

Exception hierarchy raised by Kiso.

| Class              | Base        | Description                                  |
| ------------------ | ----------- | -------------------------------------------- |
| `KisoError`        | `Exception` | Base class for all Kiso exceptions           |
| `KisoValueError`   | `KisoError` | Invalid value in configuration or execution  |
| `KisoTimeoutError` | `KisoError` | An operation exceeded its allowed time limit |

## See also

- [How extensions work](../extending/how-extensions-work.md) — how to write plugins that use these APIs
- [CLI reference](cli.md) — command-line interface
- [Config file reference](config.md) — all supported config keys
