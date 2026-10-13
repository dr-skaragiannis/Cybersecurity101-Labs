# Cybersecurity101-Labs — VulnHub Walkthroughs

Educational, **beginner-friendly** walkthroughs for the vulnerable virtual machines
(OVAs) published on [VulnHub](https://vulnhub.com/).

Every writeup explains **what** we run, **why** we run it, and **how to read the
output** — starting from the absolute basics. The goal is that a student who has
never opened a terminal can follow along, understand the methodology, and reproduce
the result in their own lab.

> This repository indexes **all 708 VulnHub virtual machines** in
> [`docs/CATALOG.md`](docs/CATALOG.md). Full walkthroughs are being added
> machine-by-machine into [`labs/`](labs/).

---

## Legal & ethical use

VulnHub VMs are **intentionally vulnerable**. They are designed to be attacked,
but **only inside an isolated lab**:

- Run them on a **host-only** or **NAT** virtual network.
- **Never** expose a lab VM to the public internet or a production network.
- Only ever test systems **you own** or have **written authorisation** to test.

Unauthorised access to computer systems is illegal in virtually every country.
Use these skills responsibly.

---

## Repository layout

```text
Cybersecurity101-Labs/
├── README.md               ← you are here
├── TEMPLATE.md             ← the standard writeup template
├── docs/
│   ├── CATALOG.md          ← index of ALL 708 VulnHub VMs
│   ├── PROGRESS.md         ← live list of finished walkthroughs
│   ├── LAB-SETUP.md        ← build your own lab (step by step)
│   ├── BEGINNER-PATH.md    ← suggested order for newcomers
│   └── TOOLS.md            ← the toolkit and what each tool does
├── labs/
│   └── <vm-slug>/
│       ├── README.md       ← the walkthrough for that VM
│       └── images/         ← your screenshots for that VM
└── catalog/
    ├── master-catalog.csv  ← machine-readable catalog
    └── catalog.json        ← slug/URL/metadata map
```

Each VM has its **own folder** named after the VulnHub URL slug
(e.g. `labs/kioptrix-level-1/`). Inside is a `README.md` (the walkthrough) and an
`images/` folder for your screenshots.

---

## Quick start

1. **Build your lab.** Follow [`docs/LAB-SETUP.md`](docs/LAB-SETUP.md)
   (install VirtualBox/VMware, create a host-only network, install Kali).
2. **Pick a target.** New to this? Start with the
   [beginner path](docs/BEGINNER-PATH.md).
3. **Download the OVA** from the VM's VulnHub page (linked in the catalog and in
   each `labs/<vm>/README.md`).
4. **Import it** into your hypervisor and boot it.
5. **Open the walkthrough** and follow along.

---

## The methodology (what every writeup covers)

1. **Reconnaissance** — find the target's IP address and open ports.
2. **Enumeration** — fingerprint services, banners, web apps, SMB shares, users.
3. **Exploitation (foothold)** — turn a finding into the first shell.
4. **Privilege escalation** — go from a normal user to `root`/`Administrator`.
5. **Capture the flags** — read `user.txt` / `root.txt` (or equivalent).
6. **Defensive lessons** — how a defender would have prevented each step.

Each section in a walkup uses three kinds of blocks:

```bash
# The command we run (copy/paste-able)
```

```text
The command's real output (or realistic representative output)
```

> **Why it works / How to read it:** a plain-English explanation of the command
> and its output, aimed at students.

**Screenshots.** The console transcripts above are the primary teaching medium —
they are complete and self-contained, so every walkthrough is fully usable as text.
On top of that, each walkthrough also carries screenshot references using standard
Markdown, plus a **Screenshot checklist** as its final section:

```markdown
![nmap scan showing ports 22 and 80 open](images/01-recon.png)
```

Those `images/NN-*.png` files are **intentionally not committed**. They are
placeholders for *you* to fill in as you work through the machine in your own lab —
capturing your own screenshots is one of the highest-value parts of the exercise,
because it forces you to actually run every command rather than read about it. The
checklist at the end of each walkthrough tells you exactly which shots to take, in
order, and the `alt` text describes what each one should show.

To add them: create `labs/<slug>/images/`, drop in the numbered PNGs, and the
references resolve immediately. Every lab folder already ships an
`images/.gitkeep` so the directory exists.

---

## Writeup progress

| Batch | Machines | Status |
| --- | --- | --- |
| Master catalog (all VMs indexed) | 708 | ✅ Done |
| Lab setup / tools / beginner path docs | — | ✅ Done |
| Full beginner walkthroughs | **82** written | 🚧 In progress |
| Remaining machines | 626 | 🚧 Planned (metadata stubs in place) |

See the live list of finished walkthroughs in
[`docs/PROGRESS.md`](docs/PROGRESS.md).

The [catalog](docs/CATALOG.md) is the single source of truth for **every** VM:
name, difficulty (where stated), description, author, release date, the
VulnHub link, and whether a local walkthrough exists yet. Use it to find
machines by name or date.

### Newest walkthroughs

A batch of long-requested VulnHub classics, each with a full beginner-oriented
guide:

| Machine | Headline techniques | Walkthrough |
| --- | --- | --- |
| Kioptrix: 2014 (#5) | FreeBSD, LFI via pChart, User-Agent access-control bypass, PhpTax RCE, SYSRET kernel exploit | [`labs/kioptrix-2014-5/`](labs/kioptrix-2014-5/README.md) |
| Basic Pentesting: 1 | ProFTPD 1.3.3c backdoor, WordPress `admin:admin`, writable `/etc/passwd` | [`labs/basic-pentesting-1/`](labs/basic-pentesting-1/README.md) |
| Basic Pentesting: 2 | SMB/`enum4linux`, Hydra, SSH-key cracking, Struts2 CVE-2017-9805 | [`labs/basic-pentesting-2/`](labs/basic-pentesting-2/README.md) |
| Lord Of The Root: 1.0.1 | Port knocking, nested base64, SQLi, overlayfs, MySQL UDF, **hand-written buffer overflow** | [`labs/lord-of-the-root-101/`](labs/lord-of-the-root-101/README.md) |
| FristiLeaks: 1.3 | Base64 image in HTML, file-upload filter bypass, insecure cron, SUID via `sudo -u` | [`labs/fristileaks-13/`](labs/fristileaks-13/README.md) |
| HackLAB: Vulnix | `finger`/SMTP enumeration, NFS `root_squash`, UID impersonation, `sudoedit /etc/exports` | [`labs/hacklab-vulnix/`](labs/hacklab-vulnix/README.md) |
| VulnOS: 2 | OpenDocMan SQLi (CVE-2014-1945), Drupalgeddon2, overlayfs | [`labs/vulnos-2/`](labs/vulnos-2/README.md) |
| SickOs: 1.2 | WebDAV `PUT` upload, HTTP 417 gotcha, egress firewall, chkrootkit CVE-2014-0476 | [`labs/sickos-12/`](labs/sickos-12/README.md) |
| Tr0ll: 2 | Image metadata forensics, ZIP cracking, Shellshock over SSH, manual 32-bit buffer overflow | [`labs/tr0ll-2/`](labs/tr0ll-2/README.md) |
| zico2: 1 | LFI, phpLiteAdmin CVE-2012-4162, LFI→RCE chaining, Dirty COW | [`labs/zico2-1/`](labs/zico2-1/README.md) |
| Bulldog: 1 | SHA-1 hashes in HTML comments, Django admin, web-shell filter bypass, `strings` on an ELF | [`labs/bulldog-1/`](labs/bulldog-1/README.md) |
| Chill Hack: 1 | Anonymous FTP, command-injection filter bypass, SSH port forwarding, steganography, Docker→root | [`labs/chill-hack-1/`](labs/chill-hack-1/README.md) |

---

## Contributing a walkthrough

1. Copy [`TEMPLATE.md`](TEMPLATE.md) into `labs/<vm-slug>/README.md`.
2. Fill in every section. Explain the *basics* — assume the reader is new.
3. Put screenshots in `labs/<vm-slug>/images/` and reference them relatively.
4. Link the community writeups you used in the **References** section.
5. Keep commands copy/paste-able and outputs accurate.

---

## Credits

- All vulnerable machines are the work of their **authors** and are hosted by
  **[VulnHub](https://vulnhub.com/)**. Full credit and download links are in the
  [catalog](docs/CATALOG.md).
- This repository only provides **educational walkthroughs** that link back to
  the original sources.
