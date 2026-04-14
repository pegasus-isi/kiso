# Network Measurement Experiment

**Repo**: [https://github.com/pegasus-isi/kiso-network-experiment](https://github.com/pegasus-isi/kiso-network-experiment)

**Components**: `FABRIC · Docker · Shell`

A Kiso experiment that tests bandwidth between two nodes on two different sites. The experiment runs `iperf3` server on one node and the `iperf3` client on the other node.

```sh
git clone https://github.com/pegasus-isi/kiso-network-experiment
cd kiso-network-experiment
kiso check experiment.yml
kiso up experiment.yml
kiso run experiment.yml
kiso down experiment.yml
```

See the experiment README for prerequisites, model selection, and configuration details.

## See also

- [Experiment gallery](index.md) — all experiments
- [Use Docker](../how-to/software/docker.md)
- [Set up on FABRIC](../how-to/testbeds/fabric.md)
