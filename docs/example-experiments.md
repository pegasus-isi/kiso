# Example Experiments

- [Agentic](https://github.com/pegasus-isi/kiso-agentic-experiment):
  The experiment is a proof-of-concept demonstrating how to run an AI agent workload on provisioned infrastructure using KisoThe experiment provisions a virtual machine (via Vagrant/VirtualBox or optionally FABRIC testbed), installs
  https://ollama.com to serve a local open-source LLM, and then runs a small Python agent using https://ai.pydantic.dev that queries the model for structured output. The agent
  itself is intentionally minimal — it asks where the 2012 Olympics were held and parses the response into a typed CityLocation object — serving as a template for running more
  complex agentic workloads on reproducible, cloud-provisioned infrastructure.

- [Plankifier](https://github.com/pegasus-isi/kiso-plankifier-experiment):
  Plankton are effective indicators of environmental change and ecosystem health in freshwater habitats, but collection of plankton data using manual microscopic methods is extremely labor-intensive and expensive. Automated plankton imaging offers a promising way forward to monitor plankton communities with high frequency and accuracy in real-time. Yet, manual annotation of millions of images proposes a serious challenge to taxonomists. Deep learning classifiers have been successfully applied here to categorize marine plankton images.

- [Orcasound](https://github.com/pegasus-isi/kiso-orcasound-experiment):
  This workflow is based on an open-source software and hardware project that trains itself using the audio files generated via the hydrophone sensors deployed in three locations in the state of Washington (San Juan Island, Point Bush, and Port Townsend) in order to study Orca whales in the Pacific Northwest region. This workflow uses code and ideas available in the Orcasound GitHub actions workflow and the Orca Hello real-time notification system.

- [COLMENA](https://github.com/pegasus-isi/kiso-colmena-experiment):
  COLMENA is an open framework designed to simplify the development, deployment, and operation of hyper-distributed applications across the compute continuum. It enables collections of heterogeneous devices to collaborate as a decentralized swarm of agents, presenting the infrastructure as a single, unified computing platform.
