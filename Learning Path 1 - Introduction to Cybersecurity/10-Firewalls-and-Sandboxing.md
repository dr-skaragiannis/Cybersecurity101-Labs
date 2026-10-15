# Module 10 — Firewalls and Sandboxing

> **Read this before:** Machines 5, 8 (network-facing services) and the extended-track
> machines where the network itself fights back (SickOs 1.2, Lord of the Root).
> **Why it exists.** Recon (Module 01) assumes ports answer and your reverse shell
> gets out. Two controls break that assumption: a **firewall** decides which packets
> may pass, and a **sandbox** decides what a compromised program may do once it is
> running. Both show up on the machines, and both are what a defender reaches for
> first.

**Full treatment:** [`docs/CONCEPTS.md`](../docs/CONCEPTS.md) §2 and §15.

---

## 1. What a firewall is, in one idea

A firewall is a **rule list applied to packets**, in order, first match wins. Rules
match on protocol, source/destination address, port, and **state** (new vs.
established), then take an action: **ACCEPT**, **DROP** (silent), **REJECT** (with an
error). Understanding three things makes every firewall observable:

1. **Direction** — `INPUT` (to this host), `OUTPUT` (from this host), `FORWARD`
   (through this host).
2. **Default policy** — the rule that applies when nothing matches. A sane host is
   `DROP` by default on `INPUT`.
3. **State** — most rules allow `ESTABLISHED,RELATED`, which is why a **reverse**
   shell (outbound) often works where a **bind** shell (inbound) does not.

> **This is the packet-level reason reverse shells beat bind shells** — now you can
> see it in a ruleset instead of taking it on faith.

---

## 2. The Linux implementations

| Tool | Layer | You will see it |
| --- | --- | --- |
| **iptables** | legacy netfilter CLI | most VulnHub boxes |
| **nftables** (`nft`) | modern netfilter | newer distros |
| **ufw** | friendly front-end to iptables | Ubuntu |
| **firewalld** | zone-based front-end | CentOS/RHEL |

### 2.1 iptables

```bash
sudo iptables -L -n -v --line-numbers     # list rules with counters
sudo iptables -S                          # machine-readable form
sudo iptables-save > rules.v4             # the whole ruleset
```

A ruleset that blocks egress except a couple of ports looks like this (from
SickOs 1.2's `/root/newRule`):

```text
*filter
:INPUT DROP [0:0]
:OUTPUT DROP [0:0]
-A INPUT  -p tcp -m tcp --dport 22  -j ACCEPT
-A INPUT  -p tcp -m tcp --dport 80  -j ACCEPT
-A OUTPUT -p tcp -m tcp --sport 22  -j ACCEPT
-A OUTPUT -p tcp -m tcp --sport 80  -j ACCEPT
-A OUTPUT -p tcp -m tcp --dport 8080 -j ACCEPT
-A OUTPUT -p tcp -m tcp --dport 443  -j ACCEPT
COMMIT
```

**Read it as an attacker:** inbound web/SSH are open, but **outbound is DROP by
default** — so your reverse shell on port 4444 will never connect. The allowed
outbound ports are `8080` and `443`. That single observation is why the SickOs 1.2
walkthrough lands its shell on **443**. A firewall rulebook is a map of the only
doors you can use.

### 2.2 nftables, ufw, firewalld

```bash
sudo nft list ruleset
sudo ufw status verbose
sudo firewall-cmd --list-all
```

### 2.3 NAT and redirection

```bash
sudo iptables -t nat -L -n -v
```

`nat` rewrites addresses/ports — how a VM reaches the internet through VirtualBox NAT,
and how port-forwarding exposes a lab service on the host. If a target is reachable
on a port it "should not" be, look for a NAT rule.

---

## 3. Firewalls as a *puzzle*: port knocking and filtering

Some boxes hide services behind a firewall that only opens after a secret **sequence
of connection attempts** — **port knocking**. On **Lord of the Root 1.0.1**, the SSH
port stays filtered until you send the right knock:

```bash
for p in 1 2 3; do nc -z TARGET $p; sleep 1; done   # illustrative knock
knock TARGET 1234 5678 9999                          # the `knock` tool
```

The defensive idea is real: **"security by obscurity" adds friction, not protection.**
A knock sequence is not a secret in the cryptographic sense — capture the traffic and
you have it.

Also expect the classic nmap states:

| nmap state | Meaning at the packet level |
| --- | --- |
| `open` | SYN-ACK — something is listening |
| `closed` | RST — host up, nothing there |
| `filtered` | nothing back — a firewall dropped it |
| `open\|filtered` | no reply, and nmap cannot tell why (common for UDP) |

---

## 4. Sandboxing: limiting what code may do after it runs

A firewall constrains **network** reach. A **sandbox** constrains a **process**.
Four layers, from coarse to fine:

| Layer | Mechanism | Limits |
| --- | --- | --- |
| **chroot / container** | namespace + changed root | what the process *sees* of the filesystem |
| **systemd sandboxing** | unit directives | filesystem, network, syscalls per service |
| **MAC (SELinux / AppArmor)** | kernel policy | which files/resources a program may touch (Module 07) |
| **seccomp** | syscall filter | which **system calls** a process may make |

### 4.1 systemd sandboxing (defender's toolkit)

```ini
# /etc/systemd/system/myapp.service
[Service]
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
RestrictAddressFamilies=AF_UNIX
SystemCallFilter=@system-service
```

Each line removes an attacker's options. `NoNewPrivileges` alone blocks the SUID
escalation from Module 05 for that service.

### 4.2 seccomp

```bash
grep Seccomp /proc/self/status        # Seccomp: 0 = off, 2 = filter mode
```

Docker applies a default seccomp profile that blocks ~44 syscalls; a container escape
often starts by finding a syscall the profile forgot (HackInOS 1, Module 06).

### 4.3 AppArmor / SELinux recap

The MAC systems from Module 07 are the sandbox most services actually run under on
Ubuntu/CentOS. **A service with no enforced profile is unsandboxed** — the finding on
the Photographer and Basic Pentesting boxes.

> **The defender's ordering.** *Least privilege* first (Module 07/08), then *network
> segmentation* (firewall), then *confinement* (sandbox). Each layer assumes the
> previous one failed.

---

## 5. Where you practise this

| Machine | What it teaches here |
| --- | --- |
| [`4-086-sickos-12`](../labs/4-086-sickos-12/README.md) | **egress firewall** — only 443/8080 out; the `/root/newRule` reveal |
| [`6-098-lord-of-the-root-101`](../labs/6-098-lord-of-the-root-101/README.md) | **port knocking** to open SSH |
| [`4-082-ha-narak`](../labs/4-082-ha-narak/README.md) | filtered services and where they hide |
| [`3-049-kioptrix-level-13-4`](../labs/3-049-kioptrix-level-13-4/README.md) | firewall rules shaping which exploit path works |
| [`5-093-djinn-1`](../labs/5-093-djinn-1/README.md) | ports and filtering on an unusual service |

---

## 6. Exercises

1. On Kali, `sudo iptables -L -n -v`, then add a rule dropping inbound `INPUT` from
   one IP and confirm with `nmap` from that IP that the port is now `filtered`.
2. Write (do not run) a ruleset that allows web+SSH and **only** outbound 443; explain
   which reverse-shell ports will fail.
3. Compare `nmap` against a `DROP` port vs a `REJECT` port and explain the difference
   in the reported state.
4. Set `NoNewPrivileges=true` on a test service and demonstrate that a SUID binary no
   longer elevates.
5. Run `grep Seccomp /proc/self/status` inside and outside a Docker container.

## 7. Check yourself

1. Why does a reverse shell often succeed where a bind shell fails, in firewall terms?
2. What is the difference between `DROP` and `REJECT` from the scanner's point of view?
3. On SickOs 1.2, which two outbound ports were allowed, and how did you find out?
4. Name the four sandbox layers from coarsest to finest.
5. Why is port knocking *obscurity* rather than *security*?

---

## 8. Annotated command reference

### 8.1 Reading a ruleset

```bash
sudo iptables -S
```

```text
-P INPUT DROP
-A INPUT -p tcp --dport 22 -j ACCEPT
-A OUTPUT -p tcp --dport 443 -j ACCEPT
```

`-P` = the chain's **policy** (default action). Every `-A` appends a rule; the first
match wins, so order matters.

### 8.2 Discovering egress restrictions from a shell

```bash
ss -tnp                                   # current connections
for p in 22 80 443 4444; do timeout 2 bash -c "echo > /dev/tcp/ATTACKER/$p" && echo "$p open" || echo "$p blocked"; done
```

This is the empirical version of reading the ruleset: try each port outbound and see
which one a listener on Kali receives.

### 8.3 Port knocking

```bash
knock TARGET 1234 5678 9999
nmap -p 22 TARGET          # now open
```

### 8.4 systemd and seccomp

```bash
systemctl show myapp -p NoNewPrivileges -p ProtectSystem
grep Seccomp /proc/self/status
```

### 8.5 nmap states

```bash
sudo nmap -Pn -p 22,80,4444 TARGET
```

Read each line: `open`, `closed`, `filtered` or `open|filtered` — the packet-level
answer, not a guess.

---

_Back to [Learning Path 1](README.md) · previous: [09 — Cryptography in Practice](09-Cryptography-GPG-and-Encryption.md) · next: [11 — Malware Analysis and YARA](11-Malware-Analysis-and-YARA.md)._
