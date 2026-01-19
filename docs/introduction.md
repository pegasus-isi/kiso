# Introduction

<center><iframe width="560" height="315" src="https://www.youtube.com/embed/2L5kSMh25tc?si=2CqNOefwcDi5NDX8" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe></center>
<p></p>

Kiso is a framework that helps researchers run and reproduce experiments across edge, cloud, and testbed environments with minimal effort. Instead of writing custom scripts to provision resources, install software, and manage execution, users describe their experiments declaratively using simple configuration files. Kiso then handles resource provisioning, software setup, experiment execution, and result collection, allowing researchers to focus on designing and evaluating their experiments rather than managing infrastructure.

## What does Kiso do?

- Kiso provides a structured way to manage the full lifecycle of an experiment:
- Provision resources across one or more supported testbeds (e.g., cloud, edge, or local environments)
- Install and configure software stacks and workload management systems
- Deploy execution environments, such as workflow engines or agent runtimes
- Run experiments in a controlled and repeatable manner
- Collect results from distributed resources back to a central location

All of this is described using a YAML-based experiment specification, which captures what should be run, where, and how, without requiring users to write custom orchestration code.
