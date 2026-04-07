#!/usr/bin/env python3

from pathlib import Path
from Pegasus.api import *

wf = Workflow("multi-testbed-workflow")

# --- Sites ---

sc = SiteCatalog()

WORK_DIR = Path.cwd().resolve()

shared_scratch_dir = str(WORK_DIR / "scratch")
local_storage_dir = str(WORK_DIR / "outputs")

local = Site("local").add_directories(
    Directory(Directory.SHARED_SCRATCH, shared_scratch_dir).add_file_servers(
        FileServer("file://" + shared_scratch_dir, Operation.ALL)
    ),
    Directory(Directory.LOCAL_STORAGE, local_storage_dir).add_file_servers(
        FileServer("file://" + local_storage_dir, Operation.ALL)
    ),
)

condorpool_amd = (
    Site("condorpool_amd", arch=Arch.X86_64)
    .add_pegasus_profile(style="condor")
    .add_pegasus_profile(auxillary_local="true")
    .add_condor_profile(universe="vanilla")
)

condorpool_arm = (
    Site("condorpool_arm", arch=Arch.AARCH64)
    .add_pegasus_profile(style="condor")
    .add_pegasus_profile(auxillary_local="true")
    .add_condor_profile(universe="vanilla")
)

sc.add_sites(local, condorpool_amd, condorpool_arm)

sc.write()

# --- Transformations ---

task_a = Transformation(
    "task-a",
    site="condorpool_amd",
    pfn="/usr/bin/pegasus-keg",
    is_stageable=False,
    arch=Arch.X86_64,
    os_type=OS.LINUX,
)
task_b = Transformation(
    "task-b",
    site="condorpool_arm",
    pfn="/usr/bin/pegasus-keg",
    is_stageable=False,
    arch=Arch.AARCH64,  # Ensure it runs on Chameleon Edge
    os_type=OS.LINUX,
)

tc = TransformationCatalog().add_transformations(task_a, task_b).write()

# --- Jobs ---

# Task A — runs on any execute node
result_a = File("result-a.txt")
task_a = Job(task_a)
task_a.add_args("-o", result_a)
task_a.add_outputs(result_a)

# Task B — depends on Task A
result_b = File("result-b.txt")
task_b = Job(task_b)
task_b.add_args("-i", result_a, "-o", result_b)
task_b.add_inputs(result_a)
task_b.add_outputs(result_b)
task_b.add_condor_profile(
    requirements='TARGET.Arch == "AARCH64"'
)  # → Ensure it runs on Chameleon Edge
wf.add_jobs(task_a, task_b)

wf.write("workflow.yml").plan(sites=["condorpool_amd", "condorpool_arm"], submit=True)
