# Changelog

## v0.1.0a10 (2026-03-15)

### Fix

- **chameleon-edge**: chameleon edge moved to using ipv4 shared address space from private ip range
- JSON Schema oneOf won't work with [{type: integer}, {type: number}] as number encompasses integer
- ollama now requires installing the zstd package
- remove the ``args`` argument from Pegasus experiment type config as it use is confusing
- configure condor to enable on IPv4 ot IPv6
- invoke Vagrant and Chameleon related cleanup actions only if those providers are installed

### Refactor

- move public ip assignment to htcondor installer
- move remaining chameleon-edge related functions to edge.py
- add a warning to install rsync package for the FABRIC provider on macOS machines when kiso check is run
- add a warning to install rsync package for the FABRIC provider on macOS machines when kiso up is run
- add variables to shell runner similar to the pegasus runner
- add missing and improve existing code comments

## v0.1.0a9 (2026-01-28)

### Fix

- set timeout to -1 for scripts installing software, deployments, etc
- for chameleon edge just deleting the lease doesn't work. add code to remove the containers beforehand
- treat all sites or fabric as the same
- resolve_labels function failed when only two labels were passed
- add retries and delay to apt command in commons main.yml file
- add retries and delay to apt command in commons main.yml file
- replace \*dst with dst in \_mkdir_remotely method
- close the ProxyCommand in the copy experiment dir action with a single-quote after the endif as it is opended unconditionally
- create HTCondor config, password, and token dir before creating files in them

### Refactor

- replace `-` in HTCondor config with `_`

## v0.1.0a8 (2026-01-07)

### Feat

- multiple changes

### Fix

- use copy instead of manually running rsync as it fails with an IPv6 address
- install acl as a common requirement

### Perf

- use rsync to copy the experiment dir to nodes and undo splitting for nodes into ipv4 and ipv4 address nodes
- use copy for nodes with ipv6 vms and rsync for ipv4 vms to copy the experiment dir to the node

## v0.1.0a7 (2025-12-08)

### Feat

- add support for FABRIC testbed

### Fix

- in kiso down, for vagrant, first remove the private_key from ssh agent, then call destroy, and then remove .vagrant dir and Vagrantfile
- move providers.destroy at the end, otherwise Vagrant remove the ssh key and it can't be removed from tthe ssh-agent
- for console.rule show the rule using the color based on the result of the action

### Refactor

- remove paramiko dependency in kiso and as it is no longer needed
- decorator improvements

## v0.1.0a6 (2025-11-13)

### Feat

- modify the shell runner's output displayed for scripts to show the standard output and error
- generate a /etc/hosts file that maps the machine labels to it IP preferred by Kiso
- cleanup vagrant when running the kiso down command

### Fix

- add a space between -i <private-key> and src in the rsync command
- only check experiments of kind pegasus and not of all kinds
- show all jsonschema errors during schema check instead of just the best match
- ssh opts to the rsync commands based on what ansible vars are set

### Refactor

- add a label/role fabric.<site> to group FABRIC provisioned nodes by the FABRIC site
- move saving of state before determining IP address
- rename pegasus/shell.py to runner.py
- remove unused site object

## v0.1.0a5 (2025-11-05)

### Perf

- use rsync command instead of ansible's copy module to speed up copying of the experiment dir

## v0.1.0a4 (2025-11-05)

### Fix

- use index and hostname as key in status dict to correctly render tables

## v0.1.0a3 (2025-11-03)

### Feat

- add a new experiment type, shell, which can simply runs scripts
- add support for extending software, deployment and add ability to run checks on experiments

### Refactor

- change url of htcondor website

## v0.1.0a2 (2025-11-03)

### Feat

- add support for extending software, deployment and add ability to run checks on experiments

## v0.1.0a1 (2025-09-12)

## v0.1.0a0 (2025-09-10)

### Feat

- change experiment configuration schema
- initial commit
