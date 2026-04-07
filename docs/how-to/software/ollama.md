# Use Ollama

This guide covers how to configure Ollama for AI/ML experiments in Kiso.

Ollama runs large language models as a local service on testbed nodes. It is specifically for AI/ML experiments — not a general-purpose container runtime. For background, see [Components — Ollama](../../concepts/components.md).

## What kinds of experiments Ollama enables

Use Ollama when your experiment involves:

- LLM inference on testbed hardware (including GPU nodes)
- Benchmarking model performance under controlled network conditions
- Evaluating LLM behavior in federated or distributed settings
- Running AI/ML workloads that need dedicated hardware on testbed nodes
- Deploying autonomous AI agents that require a locally running LLM for inference — Ollama is the standard way to provide an LLM backend for agentic experiments in Kiso

## Prerequisites

- Nodes provisioned via `kiso up`
- For GPU-accelerated inference: nodes with NVIDIA GPUs (available on FABRIC and Chameleon)
- Kiso installed with the appropriate testbed extra (e.g. `pip install kiso[fabric]`)

## Config fields

The `ollama` software entry is an **array** — you can configure different models on different sets of nodes.

```yaml
software:
  ollama:
    - labels: [gpu-node]             # Required — labels of nodes to install Ollama on
      models:                        # Required — at least one model name
        - gpt-oss:20b
        - qwen3.5:2b
      environment:                   # Optional — environment variables for the Ollama service
        OLLAMA_NUM_PARALLEL: "4"
        OLLAMA_MAX_LOADED_MODELS: "2"
```

| Field         | Required | Type                 | Description                                                                                                      |
| ------------- | -------- | -------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `labels`      | Yes      | list[string]         | Labels of nodes that should have Ollama installed                                                                |
| `models`      | Yes      | list[string]         | Model names to pull. Must specify at least one. Uses Ollama model names (e.g. `llama3`, `mistral`, `codellama`). |
| `environment` | No       | dict[string, string] | Environment variables passed to the Ollama service                                                               |

## How to specify which model to use

Model names follow Ollama's naming conventions. Use the model name as it appears in the [Ollama model library](https://ollama.com/library):

```yaml
models:
  - codellama:34b       # Code Llama 34B
  - gpt-oss:20b         # Open-source GPT variant, 20B parameters
```

Models are pulled during `kiso up`. Large models may take several minutes to download.

## Minimal working example

```yaml
name: llm-benchmark

sites:
  - kind: vagrant
    backend: virtualbox
    box: bento/rockylinux-9
    resources:
      machines:
        - labels: [compute]
          flavour: large
          number: 1
      networks:
        - labels: [net1]
          cidr: 172.16.42.0/16

software:
  ollama:
    - labels: [compute]
      models:
        - llama3

experiments:
  - kind: shell
    name: run-inference
    scripts:
      - labels: [compute]
        script: |
          /usr/local/bin/ollama run llama3 "Hi"
```

## Calling Ollama from experiment scripts

After `kiso up`, Ollama is running as a service on nodes matching the specified labels. You can interact with it via the CLI or the REST API:

```bash
# CLI
ollama run llama3 "Your prompt here"

# REST API
curl http://localhost:11434/api/generate -d '{
  "model": "llama3",
  "prompt": "Your prompt here",
  "stream": false
}'
```

## See also

- [Use Docker](docker.md) — general-purpose container runtime
- [Components — Ollama](../../concepts/components.md) — when to use Ollama
- [Config file reference](../../reference/config.md) — complete software configuration reference
- [Ollama documentation](https://ollama.com/docs)
