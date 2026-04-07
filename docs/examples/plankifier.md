# Plankifier

**Repo**: [https://github.com/pegasus-isi/kiso-plankifier-experiment](https://github.com/pegasus-isi/kiso-plankifier-experiment)

**Components**: `Chameleon · Chameleon Edge · Pegasus`

A deep learning classifier for automated plankton image categorization. Plankton are effective indicators of environmental change in freshwater habitats, but manual microscopic annotation of millions of images is labour-intensive. This experiment runs a Pegasus workflow that applies a deep learning model to classify lake zooplankton images at scale.

The experiment provisions a two-node HTCondor cluster: a cloud node acting as central manager, submit node, and execute node, and an edge node acting as an additional execute node. This edge-to-cloud setup demonstrates how Pegasus can dispatch classification tasks across both cloud and edge resources within a single workflow.

```sh
git clone https://github.com/pegasus-isi/kiso-plankifier-experiment
cd kiso-plankifier-experiment
kiso check experiment.yml
kiso up experiment.yml
kiso run experiment.yml
kiso down experiment.yml
```

See the experiment README for prerequisites, dataset setup, and configuration details.

## See also

- [Experiment gallery](index.md) — all experiments
- [Run a Pegasus workflow](../how-to/experiment-types/pegasus.md)
- [Set up on Chameleon](../how-to/testbeds/chameleon.md)
- [Set up on Chameleon Edge](../how-to/testbeds/chameleon-edge.md)
