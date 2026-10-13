# Setting Up Your Lab (Step by Step)

This guide builds a **safe, isolated** lab where you can legally attack VulnHub
machines. Follow it once, then reuse it for every machine in this repository.

> ⚠️ **Safety first.** The target VMs are *deliberately* vulnerable. Keep them on
> an **isolated virtual network**. Never bridge a lab VM to your home/office
> LAN, and never port-forward it to the internet.

---

## 1. What you need

| Component | Purpose | Suggested |
| --- | --- | --- |
| **Hypervisor** | Runs the virtual machines | VirtualBox (free) or VMware Workstation Player |
| **Attacker VM** | Your "hacking" machine | Kali Linux (VirtualBox/VMware image from kali.org) |
| **Target VM** | The VulnHub OVA you download | One per walkthrough |
| **Disk space** | ~40 GB+ free | Targets are often 1–2 GB each |
| **RAM** | Run 2 VMs at once | 8 GB comfortable, 16 GB ideal |

VulnHub machines are usually distributed as **`.ova` / `.ovf`** files. Some older
ones are `.vmdk` + `.ovf`, or even ISOs.

---

## 2. Install the hypervisor

### VirtualBox (recommended for beginners)

1. Download from <https://www.virtualbox.org/wiki/Downloads> and install.
2. Also install the **VirtualBox Extension Pack** (same page) for USB/extra
   device support.

### VMware Workstation Player

1. Download **VMware Workstation Player** from <https://www.vmware.com/products/workstation-player.html>.
2. Install it with default options.

> You only need **one** hypervisor. VirtualBox is used in the examples below.

---

## 3. Install Kali (your attacker)

1. Download the **Kali Linux VirtualBox/VMware image**: <https://www.kali.org/get-kali/#kali-virtual-machines>.
2. Import it: **File → Import Appliance…** (VirtualBox) and select the `.ova`.
3. Give it **at least 2 CPUs and 4 GB RAM** if you can.
4. Default credentials on the Kali image are `kali` / `kali`.
5. Update it once: `sudo apt update && sudo apt full-upgrade -y`.

---

## 4. Create an isolated network

You want Kali and the targets on a private network that has **no route** to the
internet.

### Option A [Proposed for both isoaltion and Internet Connection] — VirtualBox "NAT Network"

1. **Tools → Network → NAT Networks → Create**, e.g. `LabNet`, `10.0.2.0/24`.
2. Set each VM's adapter to **NAT Network → LabNet**.

### Option B — VirtualBox "Host-Only" adapter (recommended)

1. VirtualBox → **Tools → Network → Host-only Networks → Create**.
2. Note the range, e.g. `192.168.56.1/24` (the host gets `.1`).
3. Give **Kali** a second adapter set to **Host-only Adapter**.
4. Give **every target** one adapter set to **Host-only Adapter** (same network).

### Option C — VMware host-only

1. **Edit → Virtual Network Editor** → use the pre-made `VMnet1` (Host-only).
2. Set each VM's network adapter to **Host-only**.

> **DHCP note:** most VulnHub VMs get an IP automatically. If a target boots and
> shows no IP, log into its console and run `dhclient` / `ip a`.

---

## 5. Import a target OVA

**VirtualBox:** `File → Import Appliance… → choose the .ova → Import`.
**VMware:** `File → Open… → choose the .ova/.ovf`.

The first boot may take a few minutes. Once it reaches a login screen, note the
IP if it is displayed (many VulnHub VMs print it on the console).

---

## 6. Find the target's IP from Kali

```bash
ip a                          # show Kali's own addresses
sudo arp-scan -l              # ARP-scan the local subnet for live hosts
```

Or with netdiscover:

```bash
sudo netdiscover -r 192.168.56.0/24
```

Isolate the target by scanning it:

```bash
sudo nmap -sn 192.168.56.0/24
```

> **Checkpoint:** you now know the target IP. Every walkthrough starts here.

---

## 7. Take snapshots (so you can retry safely)

Before attacking, in VirtualBox: select the VM → **Snapshots → Take**. Name it
`clean`. If you break the box, restore the snapshot instead of re-downloading.

---

## 8. Common problems

| Symptom | Likely cause / fix |
| --- | --- |
| Target has no IP | Adapter is wrong, or DHCP didn't run — check adapter type, try `dhclient` in the VM console |
| Can't ping the target | `arp-scan` first (some hosts drop ICMP); verify both VMs use the **same** host-only network |
| Kali has no internet | Add a **second** adapter set to NAT alongside the host-only one |
| OVA import fails | Enable virtualisation (VT-x/AMD-V) in your BIOS; try VMware if VirtualBox complains |
| Very slow VM | Give it more RAM/CPU; enable nested virtualisation if supported |

---

## 9. Lab hygiene rules

1. Targets **never** touch the internet.
2. Take a snapshot before every attack session.
3. Expect to reboot targets often (some crashes are part of the box).
4. Only test machines you downloaded for your own learning.

---

_Next: [The toolkit](TOOLS.md) · [Beginner path](BEGINNER-PATH.md) · [Catalog](CATALOG.md)._
