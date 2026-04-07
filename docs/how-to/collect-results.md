# Collect and export results

This guide covers how to retrieve experiment results after a Kiso run.

This page is testbed-agnostic — the same process applies regardless of whether you ran on Vagrant, FABRIC, or Chameleon.

## Where results are stored

After `kiso run`, results are written to the output directory (default: `output/`, configurable with `--output`). The outputs are stored in the `output/` directory or to a destination specified in the experiment config.

### Shell experiment output structure

```
output/
  env                       ← Kiso environment state
  <files-or-directories>    ← Files or directories specified in the `outputs` section of the `shell` experiment config.
  ...
```

### Pegasus workflow output structure

```
output/
  env                       ← Kiso environment state
  <files-or-directories>    ← Files or directories specified in the `outputs` section of the `pegasus` experiment config.
  <experiment-name>/
    <instance-0>/
      <submit-dir>/
        statistics/
          summary.txt       ← wall time and cumulative wall time
          breakdown.txt     ← transformation breakdown, like minimum, maximum, and average runtimes etc.
          integrity.txt     ← file integrity information, like number of files for whom checksums were computed or checked
          jobs.txt          ← job instance information, like number of retries, runtimes, etc.
          time.txt          ← contains job and invocation times grouped by day/hour
          workflow.txt      ← contains information about each workflow run, like number of retries, etc.
        analyzer.log        ← success/failure analysis
        other pegasus files
    <instance-1>/
      ...
```

The Pegasus submit directory is retrieved automatically — you do not need to specify it in `outputs`. Before downloading, Kiso automatically runs two analysis tools and writes their output into the submit directory:

- **`pegasus-statistics`** — computes workflow performance metrics: the wall time (total elapsed time as observed by the user), cumulative wall time (sum of individual job run times), etc.
- **`pegasus-analyzer`** — determines the outcome of the workflow execution. If the workflow succeeded, it confirms completion. If the workflow failed, it identifies which jobs failed, captures their standard output and standard error, and highlights relevant Pegasus files for investigation

### Collected output files

Files specified in the `outputs` section of an experiment are downloaded from nodes and placed in the local path specified by `dst`:

```yaml
experiments:
  - kind: shell
    name: my-experiment
    outputs:
      - labels: [compute]
        src: /remote/results/data.csv
        dst: local-results/
```

After `kiso run`, `local-results/data.csv` will contain the downloaded file.

## Supported output formats

The `outputs` mechanism transfers arbitrary files. Kiso does not impose a format on experiment results — use whatever format your experiment produces (CSV, JSON, HDF5, etc.).

See [Output formats](../reference/output-formats.md) for the schema of Kiso's own output files (environment state, run metadata).

## Changing the output directory

By default, Kiso uses `output/` in the current directory. To use a different directory:

```bash
kiso run --output /path/to/results experiment.yml
```

Use the same `--output` path for all four commands (`check`, `up`, `run`, `down`) for a given experiment:

```bash
kiso up --output /data/exp1 experiment.yml
kiso run --output /data/exp1 experiment.yml
kiso down --output /data/exp1 experiment.yml
```

## Re-running experiments

If you want to run the experiment again without reprovisioning the infrastructure, use `kiso run --force`:

```bash
kiso run --force experiment.yml
```

`--force` disregards previous run results and reruns the experiment on the already-provisioned nodes.

## See also

- [Output formats](../reference/output-formats.md) — schemas for Kiso's output files
- [Run a Shell experiment](experiment-types/shell.md) — configuring `inputs` and `outputs`
- [Run a Pegasus workflow](experiment-types/pegasus.md) — collecting Pegasus workflow outputs
- [CLI reference](../reference/cli.md) — `--output` flag and other options
