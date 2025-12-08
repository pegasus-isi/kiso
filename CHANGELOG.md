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
