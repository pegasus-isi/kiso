# COLMENA

**Repo**: [https://github.com/pegasus-isi/kiso-colmena-experiment](https://github.com/pegasus-isi/kiso-colmena-experiment)

**Components**: `FABRIC · Shell`

COLMENA is an open framework for hyper-distributed applications across the compute continuum. It enables collections of heterogeneous devices to collaborate as a decentralised swarm of autonomous agents, each evaluating its capabilities against application requirements to dynamically decide which roles to execute.

This experiment deploys COLMENA across six FABRIC sites to study a power grid monitoring application. The use case simulates the NPCC 140-bus network (a reduced model of the northeastern US and Canadian power grid) using the ANDES simulation library. Three COLMENA roles are deployed: a **SimulationManager** that advances simulation timesteps, a **Monitoring** role that fetches generator frequencies and publishes them as metrics, and an **Optimizer** role that reacts to frequency contingencies, coordinates with peer optimizers via a consensus mechanism, and adjusts simulation parameters.

Connectivity between sites uses FABRIC Layer 2 networking: L2Bridge for nodes within a site and L2STS (Layer 2 Site-to-Site) for connectivity between sites. The experiment scales from 18 to 60 nodes depending on the number of agents per site (3, 5, or 10), and runs in 30 minutes to 1.5 hours per trial. The most advanced example in the gallery — review the multi-testbed tutorial before attempting it.

```sh
git clone https://github.com/pegasus-isi/kiso-colmena-experiment
cd kiso-colmena-experiment
kiso check experiment.yml
kiso up experiment.yml
kiso run experiment.yml
kiso down experiment.yml
```

See the experiment README for prerequisites, testbed credentials, and configuration details.

## See also

- [Experiment gallery](index.md) — all experiments
- [Multi-testbed experiment](../tutorials/multi-testbed.md) — prerequisite reading
- [Run a Shell experiment](../how-to/experiment-types/shell.md)
- [Set up on FABRIC](../how-to/testbeds/fabric.md)
