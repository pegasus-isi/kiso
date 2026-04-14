# Multiple Pydantic agents

**Repo**: [https://github.com/pegasus-isi/kiso-multi-agent-experiment](https://github.com/pegasus-isi/kiso-multi-agent-experiment)

**Components**: `FABRIC · Vagrant (optional) · Ollama · Shell`

## Multi-agent Pydantic Experiment

This is a proof-of-concept that provisions two VMs via FABRIC testbed. On the first VM it installs Ollama to serve a local open-source LLM, and locally runs a minimal Python agent using Pydantic AI. The agent asks where the 2012 Olympics were held and parses the response into a typed `CityLocation` object. On the second node, we run a second Pydantic agent which uses the Ollama LLM model installed on the first node. The second agent asks, "List the first five presidents of the United States" and parses the response into a typed `PresidentList` object.

```sh
git clone https://github.com/pegasus-isi/kiso-multi-agent-experiment
cd kiso-multi-agent-experiment
kiso check experiment.yml
kiso up experiment.yml
kiso run experiment.yml
kiso down experiment.yml
```

See the experiment README for prerequisites, model selection, and configuration details.

## See also

- [Experiment gallery](index.md) — all experiments
- [Run AI/ML experiments with Ollama](../how-to/software/ollama.md)
- [Set up on FABRIC](../how-to/testbeds/fabric.md)
