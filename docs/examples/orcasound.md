# Orcasound

**Repo**: [https://github.com/pegasus-isi/kiso-orcasound-experiment](https://github.com/pegasus-isi/kiso-orcasound-experiment)

**Components**: `Vagrant · Pegasus`

An audio analysis workflow for detecting orca whale vocalisations from hydrophone sensors deployed at three locations in Washington state (San Juan Island, Point Bush, and Port Townsend). The workflow is based on the open-source Orcasound project and the Orca Hello real-time notification system.

The Pegasus workflow ingests hydrophone data in batches per sensor and timestamp, converts it to WAV format, generates spectrogram images, runs inference against the Orcasound model to identify potential orca sounds, and merges predictions into a per-sensor JSON file. A reference example for science workflows that combine external real-world data sources with testbed compute.

```sh
git clone https://github.com/pegasus-isi/kiso-orcasound-experiment
cd kiso-orcasound-experiment
kiso check experiment.yml
kiso up experiment.yml
kiso run experiment.yml
kiso down experiment.yml
```

See the experiment README for prerequisites, data access, and configuration details.

## See also

- [Experiment gallery](index.md) — all experiments
- [Run a Pegasus workflow](../how-to/experiment-types/pegasus.md)
- [Set up on Vagrant](../how-to/testbeds/vagrant.md)
