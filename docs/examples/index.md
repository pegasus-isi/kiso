# Experiment gallery

These are experiments, built with Kiso and published as open repositories. Each has its own README with experiment-specific prerequisites, data, and instructions.

Every experiment follows the standard Kiso workflow:

```sh
git clone <experiment-repo-url>
cd <experiment-directory>
kiso check experiment.yml
kiso up experiment.yml
kiso run experiment.yml
kiso down experiment.yml
```

| Experiment                                                          | Components                             | Description                                                                                                                                                                    |
| ------------------------------------------------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [Pydantic agent](pydantic-agent.md)                                 | `FABRIC · Ollama · Shell`              | AI agent workload running a local LLM with Pydantic-structured output                                                                                                          |
| [Multiple Pydantic agents](multi-pydantic-agents.md)                | `FABRIC · Ollama · Shell`              | Multiple AI agents on two nodes, one with local LLM and a local Agent, and another running an agent using the LLM on the first node. Both returning Pydantic-structured output |
| [Plankifier](plankifier.md)                                         | `Chameleon · Chameleon Edge · Pegasus` | Deep learning classifier for automated plankton image categorisation                                                                                                           |
| [Orcasound](orcasound.md)                                           | `Vagrant · Pegasus`                    | Audio analysis workflow for detecting orca whale vocalisations                                                                                                                 |
| [COLMENA](colmena.md)                                               | `FABRIC · Shell`                       | Hyper-distributed swarm framework across multiple testbeds                                                                                                                     |
| [Network Measurement Experiment](network-measurement-experiment.md) | `FABRIC · Docker · Shell`              | A Kiso experiment that tests bandwidth between two nodes on two different sites. The experiment runs `iperf3` server on one node and the `iperf3` client on the other node     |

## Submit your experiment

This list is meant to grow. If you have built an experiment with Kiso and want to share it with the community, open an issue on the [https://github.com/pegasus-isi/kiso/issues](https://github.com/pegasus-isi/kiso/issues) or follow the process on the [Contributing](../about/contributing.md) page.
