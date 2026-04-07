# Set up on Vagrant

This guide covers how to configure Vagrant as the testbed in a Kiso experiment.

Vagrant is the local development testbed. Use it to develop and test experiments before running them on FABRIC or Chameleon. See [Components — Vagrant](../../concepts/components.md) for context on when to use Vagrant.

## Prerequisites

- [Vagrant](https://developer.hashicorp.com/vagrant/install) installed (version 2.3 or later)
- A supported VM backend:
  - **VirtualBox** — install [VirtualBox](https://www.virtualbox.org/wiki/Downloads) and set `backend: virtualbox` in the config
  - **libvirt** (default) — install `libvirt` and the `vagrant-libvirt` plugin
- Kiso installed: `pip install kiso[vagrant]`

Verify Vagrant is working:

```bash
vagrant --version
```

## Vagrant-specific config fields

```yaml
sites:
  - kind: vagrant
    backend: virtualbox           # Optional — libvirt (default) or virtualbox
    box: generic/debian11         # Optional — base VM image (default: generic/debian11)
    user: root                    # Optional — SSH user (default: root)
    name_prefix: enos             # Optional — prefix for VM names (default: enos)
    config_extra: |               # Optional — extra Vagrant DSL config applied to all VMs
      config.vm.boot_timeout = 600
    resources:
      machines:
        - labels: [compute]       # Required — one or more labels
          flavour: small          # Required — see flavour table below (or use flavour_desc)
          number: 1               # Optional — number of VMs (default: 1)
          backend: virtualbox     # Optional — per-machine backend override
          box: bento/rockylinux-9 # Optional — per-machine box override
          user: root              # Optional — per-machine SSH user override
          name_prefix: myvm       # Optional — per-machine name prefix override
          config_extra_vm: |      # Optional — extra Vagrant DSL config for this VM only
            vb.memory = 2048
      networks:
        - cidr: 172.16.42.0/16    # Required
          labels: [net1]          # Required
```

### Machine flavours

| Flavour       | vCPUs | RAM     |
| ------------- | ----- | ------- |
| `tiny`        | 1     | 512 MB  |
| `small`       | 1     | 1024 MB |
| `medium`      | 2     | 2048 MB |
| `big`         | 3     | 3072 MB |
| `large`       | 4     | 4096 MB |
| `extra-large` | 6     | 6144 MB |

Alternatively, use `flavour_desc` to specify a custom resource profile:

```yaml
machines:
  - labels: [compute]
    flavour_desc:
      core: 2    # Required — number of vCPUs
      mem: 4096  # Required — RAM in MB
```

## Minimal working example

```yaml
name: vagrant-test

sites:
  - kind: vagrant
    resources:
      machines:
        - labels: [compute]
          flavour: small
          number: 1
      networks:
        - cidr: 172.16.42.0/16
          labels: [net1]

experiments:
  - kind: shell
    name: check
    scripts:
      - labels: [compute]
        script: hostname
```

Run it:

```bash
kiso up experiment.yml
kiso run experiment.yml
kiso down experiment.yml
```

## Verifying the setup

After `kiso up`, verify the VM is running:

```bash
vagrant status
```

You should see the provisioned VM(s) in the `running` state.

## Common failure modes

**Invalid VM architecture**

You are using a Box that is not built to support that architecture of the machine running Kiso.

```
Stderr: VBoxManage: error: Cannot run the machine because its platform architecture x86 is not supported on ARM
```

<!-- TODO(mayani): Test with libvirt
**libvirt not installed or not running**

The default backend is `libvirt`. If it is not installed or the daemon is not running:

```bash
# Start the libvirt daemon (Linux)
sudo systemctl start libvirtd

# Or switch to VirtualBox
```

```yaml
sites:
  - kind: vagrant
    backend: virtualbox
    ...
```

**VirtualBox not found / driver not loaded**

If using `backend: virtualbox`, VirtualBox must be installed and its kernel module loaded:

```bash
# On Linux, reload the VirtualBox kernel module
sudo modprobe vboxdrv
```
 -->

**Port conflicts**

If another Vagrant VM is running on the same host using the same private network CIDR, `kiso up` may fail. Stop other VMs first or use a different CIDR.

**VM stuck in "waiting for SSH"**

This usually means the VM backend is not starting the VM correctly. Increasing the flavour (`medium` or `large`) can help if the VM is resource-starved.

**`kiso up` fails partway through**

Run `kiso up --force experiment.yml` to tear down and recreate resources from scratch.

## See also

- [Your first experiment](../../tutorials/first-experiment.md) — a full walkthrough using Vagrant
- [Set up on FABRIC](fabric.md) — run the same experiment on FABRIC
- [Testbed parameters](../../reference/testbed-parameters.md) — complete Vagrant parameter reference
