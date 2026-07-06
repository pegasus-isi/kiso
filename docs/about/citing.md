# Citing Kiso

If you use Kiso in research that leads to a publication, please cite it.

## BibTeX

```bibtex
@article{kiso,
  author={Mayani, Rajiv  and Vahi, Karan  and Rynge, Mats  and Thareja, Komal  and Casas-Moreno, Xavier  and Jin, Hongwei  and Mandal, Anirban  and Lordan, Francesc  and Raghavan, Krishnan  and Badia, Rosa M.  and Deelman, Ewa },
  title={Kiso: a foundation for complex, agentic, and reproducible experiments},
  journal={Frontiers in Complex Systems},
  volume={Volume 4 - 2026},
  year={2026},
  url={https://www.frontiersin.org/journals/complex-systems/articles/10.3389/fcpxs.2026.1800335},
  doi={10.3389/fcpxs.2026.1800335},
  issn={2813-6187},
  abstract={Experimentation on distributed, heterogeneous computing environments—from edge devices to large-scale cloud platforms—demands orchestration technologies that are both flexible and extensible. Kiso is an open-source framework designed to provision resources and manage complex scientific workflows across the edge-to-cloud continuum. Its architecture unifies infrastructure provisioning, experiment configuration, and reproducible execution, enabling researchers to compose and monitor experiments that span geographically dispersed sites and variable network conditions. Although Kiso was conceived for workflow management—coordinating data-intensive tasks and ensuring reproducibility across dynamic infrastructures—its modular design makes it equally promising for providing reproducible environments for deploying and studying emerging agentic frameworks, where autonomous AI agents require consistent resource provisioning, cross-site communication, and result collection. We describe Kiso’s core capabilities for resource orchestration, experiment lifecycle management, and integration with containerized services, and we outline how these capabilities can support distributed multi-agent systems. In particular, we discuss how its declarative provisioning, extensible task abstractions, and built-in monitoring and output collection provide a natural foundation for experiments in which reasoning agents plan, negotiate, and adapt in real time. This study situates Kiso at the intersection of scientific workflow management and complex, agent-based computing, highlighting its potential to accelerate research on adaptive, self-organizing cyber-physical systems—an emerging frontier in complex systems science.}
}
```

## Plain text (APA style)

Mayani R, Vahi K, Rynge M, Thareja K, Casas-Moreno X, Jin H, Mandal A, Lordan F, Raghavan K, Badia RM and Deelman E (2026) Kiso: a foundation for complex, agentic, and reproducible experiments. Front. Complex Syst. 4:1800335. doi: 10.3389/fcpxs.2026.1800335

## Citing specific integrations

If your experiment used a specific testbed integration, consider citing both Kiso and the testbed:

**FABRIC testbed** (introduced in v0.1.0a7):

> Cite both Kiso and the FABRIC testbed paper. See [learn.fabric-testbed.net](https://learn.fabric-testbed.net) for the recommended FABRIC citation.

**Chameleon testbed**:

> Cite both Kiso and Chameleon. See [chameleoncloud.org](https://chameleoncloud.org/) for the recommended Chameleon citation.

**Pegasus workflow management** (used with `kind: pegasus` experiments):

> If your experiment used Pegasus workflows, cite the Pegasus WMS separately. See [pegasus.isi.edu/documentation](https://pegasus.isi.edu/documentation) for the recommended Pegasus citation.

## See also

- [License](license.md) — usage license for Kiso
- [Funding](funding.md) — grant acknowledgements
- [Contact](contact.md) — questions about citations
