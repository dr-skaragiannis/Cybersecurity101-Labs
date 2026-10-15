# Module 08 — Identity, Authentication and PAM

> **Read this before:** Machines 1, 4, 7, 9, 10, 11, 12 (every box where you become
> another user).
> **Why it exists.** Module 04 taught you to *crack* credentials. This module teaches
> you the machinery that *checks* them: where accounts live, how `su` and `sudo`
> really work, how **PAM** chains authentication modules together, and how SSH trusts
> a key. When a login behaves oddly — a lockout, a silent `su` failure, a password
> that works over SSH but not `su` — the answer is here.

**Full treatment:** [`docs/CONCEPTS.md`](../docs/CONCEPTS.md) §15.

---

## 1. Where identity lives: the four files

| File | Holds | Readable by |
| --- | --- | --- |
| `/etc/passwd` | usernames, UID, GID, home, shell (**no passwords**) | everyone |
| `/etc/shadow` | password **hashes** + ageing + lock state | root only |
| `/etc/group` | group name → GID → members | everyone |
| `/etc/gshadow` | group passwords/admins | root only |

### 1.1 `/etc/passwd` — seven fields

```text
alice:x:1000:1000:Alice Doe,,,:/home/alice:/bin/bash
  │   │  │    │        │         │            └ login shell
  │   │  │    │        │         └ home directory
  │   │  │    │        └ GECOS (comments)
  │   │  │    └ primary GID
  │   │  └ UID
  │   └ password placeholder ("x" = see /etc/shadow)
  └ username
```

**UID ranges matter:** `0` = root; `1–999` = system/service accounts (no login);
`1000+` = real humans. `grep -E ':(1000|1001):' /etc/passwd` lists the real users on
almost any box.

### 1.2 `/etc/shadow` — nine fields, the ones that matter

```text
alice:$6$Xy…:19000:0:99999:7:::
       │      │     │   │    │└ account disabled (days since epoch, empty = never)
       │      │     │   │    └ warn days
       │      │     │   └ max days
       │      │     └ min days
       │      └ last change (days since 1970-01-01)
       └ password hash  ($6$ = SHA-512-crypt, $y$ = yescrypt, $2b$ = bcrypt)
```

A leading `!` or `*` means **locked** (no password login possible). That is why
`su` sometimes refuses even when you have the right password.

> **Read a hash before you crack it.** `$1$`=MD5-crypt, `$5$`=SHA-256-crypt,
> `$6$`=SHA-512-crypt, `$2y$`=bcrypt. The prefix tells you the `hashcat`/`john`
> format *and* how slow cracking will be.

---

## 2. `su` vs `sudo` — different questions

| | `su` | `sudo` |
| --- | --- | --- |
| Asks for | the **target** user's password | **your** password (usually) |
| Grants | a whole new session | one command, from a policy |
| Configured in | `/etc/pam.d/su` | `/etc/sudoers` (edit with `visudo`) |
| CTF relevance | "reuse the DB password as the OS password" | "one NOPASSWD line = root" |

```bash
su alice                 # become alice (needs alice's password)
sudo -i                  # an interactive root login
sudo -u alice whoami     # run one command as alice
sudo -l                  # WHAT MAY I RUN? — always the first privesc command
```

A `sudoers` rule looks like:

```text
alice ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart apache2
```

Read the tokens in Module 05 §1. The rule that matters: a program that can execute
another program, granted without argument restrictions, is a root shell in disguise
(use [GTFOBins](https://gtfobins.github.io/)).

---

## 3. PAM — the authentication framework

**PAM** (*Pluggable Authentication Modules*) is the layer **between** a program and
the password database. `su`, `sudo`, `sshd`, `login`, `passwd`, `screen` — all of
them ask PAM, and PAM runs a stack of modules for them.

### 3.1 How a service's stack looks

```text
/etc/pam.d/su
#%PAM-1.0
auth       sufficient pam_rootok.so
auth       required   pam_unix.so
account    required   pam_unix.so
session    required   pam_env.so
```

Each line is **type · control · module · args**:

| Field | Values | Meaning |
| --- | --- | --- |
| **type** | `auth` | is this really you? |
| | `account` | may this account log in now (not locked/expired)? |
| | `password` | how a password is changed |
| | `session` | what to set up/take down for the session |
| **control** | `required` | must pass; keep checking, fail at end |
| | `requisite` | must pass; **fail immediately** if it fails |
| | `sufficient` | if it passes, stop and succeed (unless a later `required` fails) |
| | `optional` | only matters if no other module decides |
| **module** | `pam_unix.so` | the classic shadow-file check |
| | `pam_rootok.so` | succeeds if you are already root |
| | `pam_faillock.so` / `pam_tally2.so` | count failures, **lock the account** |
| | `pam_pwquality.so` | password strength policy |
| | `pam_pwhistory.so` | remember old passwords |

> **The `sufficient pam_rootok.so` line is why root never needs a password for `su`.**
> And a mis-set `sufficient`/`optional` is a classic authentication bypass: a stack
> that "succeeds early" can accept you without the check you expected.

### 3.2 Reading a lockout

```bash
faillock --user alice          # recent failed logins
sudo pam_tally2 --user alice   # older systems
lastb | head                   # failed logins from the wtmp/btmp records
```

If `su` fails with the *right* password, check for a `!` in `/etc/shadow` or a
`pam_faillock` lock — not for a wrong password.

### 3.3 Where PAM shows up on the labs

- **Corrosion: 1** and **Raven: 1** use `su`/`sudo` flows whose failures are PAM
  decisions (locked account, `pam_unix` vs a custom module).
- **HA: Narak** and **W1R3S** touch `/etc/pam.d` while hunting misconfigurations.
- The general lesson: **the password is only one input to the decision.** PAM can
  also consult a time window, a lock counter, a group, a fingerprint, or an LDAP
  server — and any of those can be the reason a login is refused.

---

## 4. SSH authentication: keys, not passwords

```bash
ssh-keygen -t ed25519 -C "kali"
cat ~/.ssh/id_ed25519.pub            # the PUBLIC key you distribute
ssh-copy-id alice@target             # appends it to alice's authorized_keys
ssh -i ~/.ssh/id_ed25519 alice@target
```

| Server file | Purpose |
| --- | --- |
| `/etc/ssh/sshd_config` | `PasswordAuthentication`, `PubkeyAuthentication`, `AllowUsers`, `PermitRootLogin` |
| `~/.ssh/authorized_keys` | public keys allowed to log in **as that user** |
| `/etc/ssh/ssh_host_*_key` | the server's own identity (what `known_hosts` pins) |

> **Why this is a privesc path.** If you can write to *any* user's
> `authorized_keys` (Module 05: writable files), you get a stable login as them
> **without a password** — the trick used on Chill Hack and several band-4 boxes.
> `authorized_keys` is therefore a high-value file to audit for permissions.

---

## 5. Where you practise this

| Machine | What it teaches here |
| --- | --- |
| [`2-001-basic-pentesting-1`](../labs/2-001-basic-pentesting-1/README.md) | reading `/etc/passwd`; replacing a hash to become root |
| [`3-019-corrosion-1`](../labs/3-019-corrosion-1/README.md) | `su`/`sudo` behaviour and PAM-configured services |
| [`3-059-raven-1`](../labs/3-059-raven-1/README.md) | multi-user enumeration; authentication surfaces |
| [`4-082-ha-narak`](../labs/4-082-ha-narak/README.md) | `/etc/pam.d`, MOTD and login-flow misconfiguration |
| [`3-068-w1r3s-101`](../labs/3-068-w1r3s-101/README.md) | world-readable `/etc/shadow` → `unshadow` → John |

---

## 6. Exercises

1. List the real (UID ≥ 1000) users on your Kali box in one command.
2. Create a user, lock it with `passwd -l`, and prove `su` fails; then explain which
   `/etc/shadow` field changed.
3. Add a temporary `sudoers.d` rule granting yourself one binary with `NOPASSWD`,
   validate it with `visudo -c`, then remove it.
4. Read `/etc/pam.d/sshd` and identify every `auth` line; state the order they run in.
5. Generate an SSH key, install the public half for a user, and log in with no
   password; then find and explain the file that made it work.

## 7. Check yourself

1. Which file holds the password hash, and why is it not `/etc/passwd`?
2. What do `!` and `*` mean at the start of a `/etc/shadow` hash?
3. Give the four PAM **types** and the four **control** flags.
4. Why does root not need a password for `su`, in PAM terms?
5. Name two reasons `su` can fail even with the correct password.

---

## 8. Annotated command reference

### 8.1 `id` and `getent`

```bash
id
getent passwd alice
getent group docker sudo lxd
```

`getent` asks the **NSS** stack — the same source the system uses — so it also
resolves LDAP/NIS accounts that never appear in the local files.

### 8.2 `passwd` state

```bash
sudo passwd -S alice
```

```text
alice P 05/11/2024 0 99999 7 -1
```

`P` = usable password, `L` = locked, `NP` = no password. The first field is the
whole story.

### 8.3 `sudo -l` and `visudo`

```bash
sudo -l
sudo visudo -c
```

`visudo -c` checks syntax. **Never edit `/etc/sudoers` directly** — one typo locks
everyone out of sudo. Use a drop-in file in `/etc/sudoers.d/` instead.

### 8.4 PAM inspection

```bash
ls /etc/pam.d/
cat /etc/pam.d/su
faillock --user "$USER"
```

### 8.5 SSH keys

```bash
ssh-keygen -t ed25519
ls -l ~/.ssh
ssh -v alice@target 2>&1 | grep -i 'authentications that can continue'
```

`ssh -v` prints exactly which authentication methods the server offers and which
one succeeded — the fastest way to debug a key login.

---

_Back to [Learning Path 1](README.md) · previous: [07 — Permissions and Access Control](07-Permissions-and-Access-Control.md) · next: [09 — Cryptography in Practice: GPG and File Encryption](09-Cryptography-GPG-and-Encryption.md)._
