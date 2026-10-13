# <Machine Name> — VulnHub Walkthrough (Beginner Friendly)

> **Copy this file to `labs/<vm-slug>/README.md` and fill in each section.**
> Replace every `<...>` placeholder. Keep the explanations — they are the point.

| Field | Value |
| --- | --- |
| **Machine** | <name> |
| **Difficulty** | <Easy / Medium / Hard / N/A> |
| **Author** | <author> |
| **Released** | <date> |
| **VulnHub Entry** | <https://vulnhub.com/entry/...> |
| **Download** | <https://vulnhub.com/entry/...#download> |
| **Attacker** | Kali Linux (e.g. 2024.x) on VirtualBox/VMware, host-only network |
| **Target OS** | <Linux / Windows> |

---

## 0. What you will learn

A short bullet list of the concrete skills this box teaches, e.g.:

- How to discover a host and its open ports on a lab network.
- How to enumerate a web server for hidden files and directories.
- How a vulnerable web app leads to a reverse shell.
- How to find and abuse a `sudo`/SUID misconfiguration to become root.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able
to import an OVA.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

```bash
# Identify your own IP + subnet first (the "eth0" adapter is the lab NIC)
ip a
```

```text
<output showing your attacker IP, e.g. 192.168.56.10/24>
```

> **How to read it:** Kali's lab interface usually holds a `192.168.56.x`
> (VirtualBox host-only) or `192.168.19x.x` (VMware) address. The target will
> live on the **same** subnet.

```bash
# ARP-scan the subnet to list live hosts (fast, uses ARP not TCP)
sudo arp-scan --interface=eth0 --localnet
```

```text
<output listing the target IP, e.g. 192.168.56.101>
```

**Target IP:** `192.168.56.<n>`

---

## 2. Enumeration — open ports and services

```bash
# Fast full-TCP port sweep, then service/version detection on open ports
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.<n>
sudo nmap -sC -sV -p <open-ports> -oA scans/services 192.168.56.<n>
```

```text
<full nmap output>
```

> **How to read it:**
> - `-p-` scans all 65,535 TCP ports.
> - `-sV` guesses the **service and version** behind each open port.
> - `-sC` runs Nmap's default scripts (banners, safe checks).
> - Note every open port — each one is an *attack surface*.

![nmap service scan output](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

Explain the exact vulnerability, then exploit it.

### 3.1 Manual exploitation

```bash
<command>
```

```text
<output>
```

> **Why it works:** <explanation>

### 3.2 The reverse shell

```bash
# On Kali: start a listener
nc -lvnp 4444
```

```bash
# On the target / via the exploit: connect back to Kali
<shell command>
```

```text
<shell banner>
```

We now have a shell as `www-data` (or similar). Upgrade it to a full TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# then press Ctrl+Z, run: stty raw -echo; fg  ; and: export TERM=xterm
```

### 3.3 The user flag

```bash
find / -name "user.txt" 2>/dev/null
cat /home/<user>/user.txt
```

```text
<user flag>
```

---

## 4. Privilege escalation — becoming root

Systematically check common privesc vectors and explain each:

```bash
# Sudo rights
sudo -l
# SUID binaries
find / -perm -4000 -type f 2>/dev/null
# Cron jobs
cat /etc/crontab; ls -la /etc/cron*
# Kernel / OS
uname -a; cat /etc/os-release
# Writable files owned by root
find / -writable -user root -type f 2>/dev/null
```

```text
<output>
```

> **Why it works:** <explain the misconfiguration and how it leads to root>

```bash
<privesc command>
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

### The root flag

```bash
cat /root/root.txt
```

```text
<root flag>
```

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | <vuln> | <service/file> | <impact> |
| 2 | <vuln> | <service/file> | <impact> |

## 6. Defensive lessons (blue team)

- <how to configure/patch to prevent step 1>
- <how to prevent step 2>
- <logging/detection opportunities>

---

## 7. References

- VulnHub entry: <link>
- Community writeups consulted:
  - [<title>](<url>)
  - [<title>](<url>)
- Vendor advisories / docs: <links>

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target
- [ ] `images/02-nmap.png` — port/service scan
- [ ] `images/03-enum.png` — the key enumeration finding
- [ ] `images/04-foothold.png` — the initial exploit
- [ ] `images/05-shell.png` — the shell
- [ ] `images/06-user-flag.png` — user flag
- [ ] `images/07-privesc.png` — the privesc finding
- [ ] `images/08-root-flag.png` — root flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
