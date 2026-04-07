# Kiso documentation — guidance for Claude

## Build

```sh
tox -e docs
# Or: cd docs && make html
```

The build must be **warning-free**. Warnings are treated as errors.


## Diataxis framework

Every page belongs to exactly one quadrant. Getting this wrong is the most common docs mistake — if you find yourself writing step-by-step instructions on a concept page, or explaining why something works on a how-to page, stop and split it.

| Quadrant | Question it answers | Tone | What does NOT belong |
|---|---|---|---|
| **Tutorial** | "Can you show me how to do this end-to-end?" | Narrative, you control the path, no branching | Options, alternatives, edge cases |
| **Concept** | "What is this and why does it work this way?" | Explanatory, no instructions | Step-by-step procedures, exhaustive option lists |
| **How-to** | "How do I accomplish this specific goal?" | Goal-oriented, numbered steps, prerequisites listed | Conceptual explanation beyond one linking sentence |
| **Reference** | "What are the exact values/fields/options?" | Precise, terse, tables preferred over prose | Explanations of why, tutorials, procedures |

Two sections sit **outside Diataxis**:
- **Experiment gallery** (`examples/`) — community showcase linking to external repos; never re-explain Kiso, never guess at config details not stated in the experiment description
- **About** (`about/`) — project meta (funding, license, contributing, contact); welcoming and direct tone

### Diataxis rules that apply to every page

1. **One page, one job.** If a page covers X and also Y, split it.
2. **Link instead of re-explain.** A how-to that needs a concept explained writes one sentence and links to the concept page.
3. **Tutorials make decisions for the reader.** No "alternatively you could…", no branching. Defer edge cases to how-to guides.
4. **Concepts have no steps.** If you number something on a concept page, it probably belongs in a how-to.
5. **Reference is look-up-able.** Every entry needs: name, type, default, required/optional, one-line description. No paragraphs.
6. **No orphan pages.** Every page ends with a "See also" or "What's next" block containing at least one link.


## Section order (`index.rst`)

1. Introduction (`introduction/`)
2. Tutorials (`tutorials/`)
3. Concepts (`concepts/`)
4. How-to guides (`how-to/`)
5. Extending Kiso (`extending/`)
6. Experiment gallery (`examples/`) — outside Diataxis
7. Reference (`reference/`)
8. About (`about/`)


## MyST anchor rules

`heading_anchors: 0` is set — headings do **not** auto-generate HTML anchors. Cross-references to specific sections must use `(label)=` syntax placed on the line before the heading. Do **not** use `#fragment` URL syntax in inter-page links — it will produce a `myst.xref_missing` warning.


## Writing rules

- All config examples use fenced code blocks with `yaml` or `bash` language tags
- Sentence case for all headings (`Config file anatomy`, not `Config File Anatomy`)
- Install instructions always use testbed-specific extras: `pip install kiso[vagrant]`, `pip install kiso[fabric]`, `pip install kiso[chameleon]` — never bare `pip install kiso`
- When showing a config example, note which field changes per testbed and which stays the same
- **Never use `---` in markdown files** — it renders as a `<hr>` in HTML. Use headings to separate sections instead.


## Testbed facts (easy to get wrong)

### Chameleon vs Chameleon Edge

- Both use the **same Chameleon project allocation**
- They require **different site-specific OpenRC files**: CHI@UC/CHI@TACC for Chameleon bare metal, CHI@Edge for Chameleon Edge
- A Chameleon Cloud OpenRC file will not authenticate against CHI@Edge and vice versa
- Never say they have "separate project allocations" — they share one
- Never say their credentials are "the same" — the OpenRC files are site-specific
- Documented on separate pages: `how-to/testbeds/chameleon.md` and `how-to/testbeds/chameleon-edge.md`

### Chameleon bare metal networks

Networks are a list of OpenStack network name **strings** (e.g. `["sharednet1"]`), not objects with `cidr`/`labels`. Source: `enoslib/infra/enos_chameleonkvm/schema.py`.

### Chameleon Edge machine types

Two types: `deviceCluster` (select by board type: `machine_name` + `count`) and `device` (select by name: `device_name`). Container config is nested inside the machine entry. Source: `enoslib/infra/enos_chameleonedge/schema.py`.

### Chameleon Edge — no Docker

Docker is **not supported** on Chameleon Edge containers. Always use an `{warning}` admonition to state this — never just a prose bullet. Apptainer is the container runtime of choice for Chameleon Edge.

### Chameleon Edge — known failure modes

Two documented failure modes (paper Section 3.4):

1. **Command execution timeouts** — Kiso polls for completion via an exit code file on the container filesystem; scripts that take longer than expected may appear to hang until the polling detects the file
2. **File transfer timeouts** — Kiso uses a per-file fallback strategy; individual transfers that time out are retried rather than failing the whole transfer step

### Vagrant defaults

Default backend is `libvirt` (not VirtualBox). Flavours: `tiny`, `small`, `medium`, `big`, `large`, `extra-large`.

### FABRIC networks

Must use typed network objects (`kind: FABNetv4`, `FABNetv4Ext`, etc.) — not a bare `cidr` field. Use `FABNetv4Ext`/`FABNetv6Ext` for public IPs (required for HTCondor submit/central-manager nodes in multi-testbed deployments).

### FABRIC permissions

Some features require project permission tags. Kiso's `check()` validates these at `kiso up` time. Source: `enoslib/infra/enos_fabric/provider.py` + `constants.py`.

| Feature | Required permission |
|---|---|
| Machines spanning multiple sites | `Slice.Multisite` |
| `FABNetv4Ext` network | `Net.FABNetv4Ext` |
| `FABNetv6Ext` network | `Net.FABNetv6Ext` |
| GPU components | `Component.GPU` |
| NVME storage (P4510 model) | `Component.NVME_P4510` |
| NVME storage (other models) | `Component.NVME` |
| NAS storage | `Component.Storage` |
| ConnectX-5 SmartNIC | `Component.SmartNIC_ConnectX_5` |
| ConnectX-6 SmartNIC | `Component.SmartNIC_ConnectX_6` |


## HTCondor multi-testbed requirement

Submit and central manager nodes **must have public IP addresses** when HTCondor spans multiple testbeds. This is a hard architectural requirement — daemons must be reachable across testbed network boundaries. Surface this prominently on every page that touches multi-testbed HTCondor. Never put it in a footnote.

Multi-testbed deployments are not limited to two testbeds — any number of supported testbeds can be combined (e.g., Chameleon + Vagrant + Chameleon Edge). The only constraint is that the central manager and submit nodes have public IPs.


## Pegasus auto-artifacts

For Pegasus experiments, Kiso automatically (without any `outputs` config):

1. Copies the Pegasus submit directory from the submit node to `output/run/<experiment-name>/<submit-node>/pegasus-run/<workflow-run-id>/`
2. Runs `pegasus-statistics` — wall time and cumulative wall time — and writes output into the submit directory
3. Runs `pegasus-analyzer` — success/failure analysis, failed job stdout/stderr — and writes output into the submit directory

Both tool outputs are included in the submit directory download. Users do **not** need to call these tools themselves or specify the submit directory in `outputs`.


## Tutorial page structure

Tutorial pages should follow this structure:
1. Intro paragraph (one sentence: what the tutorial does)
2. **"What you will build"** section — describes the end state before listing prerequisites; helps readers decide whether to continue
3. **Prerequisites** section — numbered list with links to install/download pages (not home pages)
4. Body (numbered steps)
5. **"What you have accomplished"** section at the end — celebrates success with bullet points, encouraging tone, emojis welcome

Prerequisites links must point to **install or download pages**, not home pages or general docs. Examples: `virtualbox.org/wiki/Downloads` not `virtualbox.org`; `developer.hashicorp.com/vagrant/install` not `developer.hashicorp.com/vagrant/docs`.
