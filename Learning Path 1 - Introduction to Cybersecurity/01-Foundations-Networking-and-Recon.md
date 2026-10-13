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

_Back to [Learning Path 1](README.md) · previous: [00 — Before You Start](00-Before-You-Start.md) · next: [02 — Web Attacks](02-Web-Attacks.md)._
