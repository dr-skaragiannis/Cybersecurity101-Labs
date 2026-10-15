# Module 07 — Permissions and Access Control (DAC and MAC)

> **Read this before:** Machines 1, 3, 6, 8, 9, 10, 11 (and any time `ls -l` output
> decides your next move).
> **Why it exists.** Module 05 teaches you to *abuse* `sudo`, SUID and capabilities.
> This module teaches you the system those sit on: how Linux decides who may do
> what — first the ordinary permission model (**DAC**), then the kernel-enforced
> policies that survive a compromised account (**MAC**: SELinux and AppArmor).
> Without this, privilege escalation looks like magic; with it, every finding on
> the machines has a reason.

**Full treatment:** [`docs/CONCEPTS.md`](../docs/CONCEPTS.md) §15.

---

## 1. The two questions access control answers

| Question | Model | Enforced by | Beaten by |
| --- | --- | --- | --- |
| *Who is this process?* | **DAC** — Discretionary Access Control | file owner's `rwx` bits | becoming root, SUID, writable files |
| *Even as root, what may this process do?* | **MAC** — Mandatory Access Control | the kernel (SELinux/AppArmor), a policy you cannot edit as a user | a policy that is *absent*, *permissive*, or *misconfigured* |

DAC is **discretionary**: the owner of a file decides its permissions. MAC is
**mandatory**: a system-wide policy decides, and even root is constrained until it
reloads the policy. Most beginner boxes only need DAC; the moment you meet a CentOS
box or a hardened Ubuntu host, MAC decides whether your exploit works.

---

## 2. DAC, precisely

### 2.1 The nine bits

```text
-rwxr-xr--  1 alice developers  4096 report.txt
 │└┬┘└┬┘└┬┘
 │ │  │  └ others: r-- (read only)
 │ │  └ group:  r-x (read + execute)
 │ └ owner:  rwx (read + write + execute)
 └ type: - file, d dir, l symlink, s socket, c/b device
```

Three classes (**owner, group, others**), three bits each (**read, write, execute**).
Octal is just the decimal value of each triple: `r=4, w=2, x=1`, so `rwxr-xr--` = `754`.

| Octal | Symbolic | Meaning |
| --- | --- | --- |
| `7` | `rwx` | everything |
| `6` | `rw-` | read + write |
| `5` | `r-x` | read + execute |
| `4` | `r--` | read only |
| `0` | `---` | nothing |

### 2.2 What the bits mean for directories

This trips up beginners constantly. On a **directory**, the bits mean something else:

- `r` — you may **list** the names (`ls`).
- `w` — you may **create/delete** entries (this is why a writable directory is so
  dangerous: you can delete and replace files you cannot read).
- `x` — you may **enter/traverse** it (`cd`, or access a file inside by full path).

`--x` on a directory is the classic CTF "you can reach a file you cannot list" case.

### 2.3 `umask` — where default permissions come from

New files are not created `777`; the process's **umask** is subtracted from a base
(`666` for files, `777` for directories):

```bash
umask          # e.g. 0022
touch f; mkdir d
ls -l f d
```

```text
-rw-r--r-- 1 kali kali 0 f     # 666 - 022 = 644
drwxr-xr-x 2 kali kali 4096 d  # 777 - 022 = 755
```

> **Defensive note.** A weak umask (`0000`) is how backups and temp files end up
> world-readable. Look for it in `/etc/profile`, `/etc/login.defs` and a user's
> `.bashrc`.

---

## 3. The three special bits

| Bit | Octal | Shown as | Effect | CTF relevance |
| --- | --- | --- | --- | --- |
| **SUID** | `4000` | `s` in owner-exec | run as the **file's owner** | the #1 privesc (Module 05) |
| **SGID** | `2000` | `s` in group-exec | run as the file's **group**; on a dir, new files inherit the dir's group | shared dirs; group privesc |
| **Sticky** | `1000` | `t` in other-exec | in a dir, only the owner may delete their files | `/tmp` |

```bash
find / -perm -4000 -type f 2>/dev/null    # SUID files
find / -perm -2000 -type f 2>/dev/null    # SGID files
find / -perm -1000 -type d 2>/dev/null    # sticky directories
```

Read `-rwsr-xr-x`: the `s` sits where the owner's `x` would be. If the file is
SUID but *not* executable (`-rwSr--r--`), the bit is set but meaningless — a common
false positive.

---

## 4. Beyond the nine bits: ACLs, attributes, capabilities

The nine bits cannot express "user *bob* may read, but not the group". Three
extensions fill the gap — and each is a privesc surface.

### 4.1 POSIX ACLs

```bash
getfacl /etc/shadow
setfacl -m u:bob:r /tmp/notes
```

`getfacl` output ending in a `mask::` and named-user lines means an ACL is in play.
Look for a permissive `mask::rwx` and for the `+` in `ls -l` (`-rw-rw-r--+`).

### 4.2 File attributes (`chattr`)

```bash
lsattr /etc/passwd
chattr +i /etc/passwd     # +i = immutable, even root cannot write
```

`chattr +i` is a real hardening control — and a real trap: if you overwrite
`/etc/passwd` on a box where it is immutable, your write silently fails.

### 4.3 Linux capabilities

Capabilities split root's power into ~40 pieces. `getcap -r /` shows binaries
carrying one — e.g. `cap_dac_read_search` (read anything, bypassing DAC) or
`cap_setuid` (become any user). Machine 8 (`getcap`, `cap_dac_read_search`) is the
worked example; Module 05 §3 has the exploitation.

---

## 5. MAC: SELinux and AppArmor

When DAC is beaten (you are root, or a file is world-writable), **MAC is the last
line of defence**. Both systems ship **default-deny** policies: a program may only
do what its profile allows.

### 5.1 SELinux (Red Hat / CentOS / Fedora)

Every process and file carries a **context**: `user:role:type:level`, e.g.
`system_u:system_r:httpd_t:s0`. Policy rules are written in terms of the **type**
(`httpd_t`, `user_home_t`). Three modes:

| Mode | `getenforce` | Behaviour |
| --- | --- | --- |
| **Enforcing** | `Enforcing` | policy violations are **denied and logged** |
| **Permissive** | `Permissive` | violations are **logged but allowed** — a gold mine for learning |
| **Disabled** | `Disabled` | no MAC at all |

```bash
getenforce
ls -Z /var/www/html          # show security contexts
semanage fcontext -l | grep httpd    # what may httpd touch?
ausearch -m avc -ts recent   # read denials (type=AVC)
```

> **The CTF moment.** On **FristiLeaks 1.3** (CentOS 6, SELinux enforcing), your
> uploaded shell runs in the wrong **type** and is denied — until you notice the
> context and work with it. On **Temple of Doom** the shell is `unconfined_t`, so
> SELinux does not block you at all. *Same kernel feature, opposite outcome, decided
> entirely by policy.*

### 5.2 AppArmor (Ubuntu / Debian / SUSE)

Path-based instead of label-based: a profile lists the **files** a program may
touch. Profiles live in `/etc/apparmor.d/`.

```bash
sudo aa-status                 # which profiles are loaded/enforced
cat /etc/apparmor.d/usr.sbin.apache2
sudo aa-complain /usr/sbin/apache2   # switch a profile to "log only"
sudo aa-genprof /usr/bin/foo         # generate a profile by watching a program
```

Apache on Ubuntu ships an AppArmor profile. **If it is not in enforce mode, a
compromised `www-data` reads far more of the filesystem** — exactly the defensive
note on the Photographer and Basic Pentesting walkthroughs.

> **Why MAC matters to a defender.** DAC says "the file is world-readable, so
> anyone may read it." MAC says "even if it is world-readable, *this program* may
> not." That is the difference between a single misconfiguration and a full
> compromise.

---

## 6. Where you practise this

| Machine | What it teaches here |
| --- | --- |
| [`2-001-basic-pentesting-1`](../labs/2-001-basic-pentesting-1/README.md) | world-writable `/etc/passwd`; AppArmor as the missing defence |
| [`3-068-w1r3s-101`](../labs/3-068-w1r3s-101/README.md) | **world-writable `/etc/shadow`**, `unshadow` + John |
| [`3-031-fristileaks-13`](../labs/3-031-fristileaks-13/README.md) | **SELinux** contexts (`httpd_t`), enforcing mode changing the outcome |
| [`3-028-empire-breakout`](../labs/3-028-empire-breakout/README.md) | **file capabilities** (`cap_dac_read_search`) |
| [`3-055-photographer-1`](../labs/3-055-photographer-1/README.md) | no enforced AppArmor profile → `www-data` reads broadly |
| [`4-091-temple-of-doom-1`](../labs/4-091-temple-of-doom-1/README.md) | `unconfined_t` — SELinux present but not protecting |

---

## 7. Exercises

1. On your Kali box, create `a.txt` and `b/`, run `umask 0077`, recreate both, and
   explain every character of the resulting `ls -l`.
2. Make a directory `--x` for others and prove you can read a known file inside it
   by full path but cannot `ls` it.
3. Find one SUID binary that is *not* exploitable and explain why the bit is harmless.
4. On any Ubuntu VM, run `sudo aa-status`; find one profile that is **not** in enforce
   mode and state what that means for an attacker who compromises that program.
5. On a CentOS VM, switch SELinux to **Permissive**, trigger a denial, read it with
   `ausearch`, then re-enable **Enforcing**.

## 8. Check yourself

1. In `-rwxr-sr-x`, which special bit is set and what does it do?
2. Why is a **writable directory** dangerous even when the files inside are not writable?
3. State the difference between DAC and MAC in one sentence each.
4. What does SELinux *Permissive* mode do that *Enforcing* does not, and why is that
   useful to an attacker **and** a defender?
5. Where does a capability sit relative to SUID in terms of granularity?

---

## 9. Annotated command reference

### 9.1 `ls -l` / `ls -la`

```bash
ls -la /etc/passwd /tmp
```

```text
-rw-r--r--  1 root root   2871 May 11 09:41 /etc/passwd
drwxrwxrwt 12 root root   4096 May 11 09:41 /tmp
```

The `t` on `/tmp` is the **sticky bit**; the `+` would signal an ACL.

### 9.2 `getfacl` / `setfacl`

```bash
getfacl /tmp/shared
setfacl -m u:alice:rw /tmp/shared
getfacl /tmp/shared | grep -E 'user:|mask:'
```

`mask::` caps the effective rights of every named user and the group.

### 9.3 `lsattr` / `chattr`

```bash
lsattr /etc/passwd
sudo chattr +i /etc/passwd
echo x | sudo tee -a /etc/passwd     # fails: Operation not permitted
```

### 9.4 SELinux

```bash
getenforce
ls -Z /var/www/html | head
ausearch -m avc -ts recent 2>/dev/null | tail
```

Read `ausearch` output as: `avc: denied { read } for pid=… comm="httpd" path="…"`.
That single line tells you *what* was blocked, *which program* asked, and *which file*
it wanted — the whole story of a MAC denial.

### 9.5 AppArmor

```bash
sudo aa-status
sudo aa-complain /usr/sbin/apache2     # log-only
sudo aa-enforce  /usr/sbin/apache2     # re-enforce
```

`aa-status` prints three counts: **profiles loaded**, **in enforce mode**, and
**in complain mode**. A program missing from the enforce list is unprotected.

---

_Back to [Learning Path 1](README.md) · previous: [06 — Shells, Persistence and Escapes](06-Shells-Persistence-and-Escapes.md) · next: [08 — Identity, Authentication and PAM](08-Identity-Authentication-and-PAM.md)._
