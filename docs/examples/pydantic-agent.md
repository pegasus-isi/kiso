# Pydantic agent

**Repo**: [https://github.com/pegasus-isi/kiso-agentic-experiment](https://github.com/pegasus-isi/kiso-agentic-experiment)

**Components**: `FABRIC · Vagrant (optional) · Ollama · Shell`

A proof-of-concept AI agent workload that provisions a FABRIC node, installs Ollama to serve a local LLM, and runs a Python agent using Pydantic to parse structured output. Can also run on Vagrant for local development. Serves as a template for running agentic workloads on reproducible, cloud-provisioned infrastructure.

```sh
git clone https://github.com/pegasus-isi/kiso-agentic-experiment
cd kiso-agentic-experiment
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
