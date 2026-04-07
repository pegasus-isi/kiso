# Output formats

The structure and formats for experiment results and Kiso's own output files.

## Output directory structure

Kiso writes all output to the directory specified by `--output` (default: `output/`).

```
output/
  env                       ← EnOSlib environment state (used by kiso up, kiso run, and kiso down)
  <files-or-directories>    ← Files or directories specified in the `outputs` section of the `shell` experiment config.
```

<!-- TODO(mayani): Uncomment when shell output is improved
## `stdout` and `stderr`

The captured standard output and standard error from experiment scripts are shown on the console using Python's `logging` module.

**Example `stdout`:**

```
Running on compute-01.example.fabric-testbed.net
Hello from the experiment
```

**Example `stderr`:**

```
+ echo 'Running on compute-01...'
+ hostname
``` -->

## Pegasus workflow output

For Pegasus experiments, the output structure includes the Pegasus execution directory:

```
output/
  <experiment-name>/
    <instance-0>/
      <submit-dir>/
        statistics/
        analyzer.log        ← success/failure analysis
        other pegasus files ← Pegasus execution directory contents
```

The Pegasus execution directory contains Pegasus-native files: `braindump.yml` (workflow metadata), `monitord.log`, individual job logs etc.

## File transfer outputs

Files specified in the `outputs` section of an experiment are downloaded to the local path specified by `dst`. There is no imposed format — files are transferred as-is from the remote node.

**Config example:**

```yaml
outputs:
  - labels: [compute]
    src: /scratch/results/data.csv
    dst: local-results/
```

**Result:**

```
local-results/
  data.csv
```

<!-- TODO(mayani):
If multiple nodes match the labels, files from each node are placed in subdirectories named by hostname:

```
local-results/
  compute-01.example.com/
    data.csv
  compute-02.example.com/
    data.csv
``` -->

## Environment state file (`env`)

The `env` file is a pickled Python object containing EnOSlib environment state. It is used internally by `kiso up`, `kiso run`, and `kiso down` to reconnect to provisioned resources.

This file is not intended for direct use. Do not modify it. It is specific to the provisioned resource set and becomes invalid after `kiso down`.

## See also

- [Collect and export results](../how-to/collect-results.md) — how to retrieve and work with results
- [CLI reference](cli.md) — `--output` flag
