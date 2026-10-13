# 04 — Credentials and Cracking

Every machine in this path ends with you holding a credential you should not have.
Most of them *start* that way too. This module covers where credentials come from,
how password storage actually works, and how to attack it.

Full treatment: [`docs/CONCEPTS.md` §7](../docs/CONCEPTS.md#7-what-is-a-wordlist)
(wordlists), [§10](../docs/CONCEPTS.md#10-encoding-vs-hashing-vs-encryption)
(encoding vs hashing vs encryption) and
[§14](../docs/CONCEPTS.md#14-password-cracking) (cracking).

---

## 1. The distinction that decides everything

These three are conflated constantly, and the confusion costs hours:

| | **Encoding** | **Hashing** | **Encryption** |
| --- | --- | --- | --- |
| Purpose | Represent data in another *format* | Prove integrity / store passwords | Provide *confidentiality* |
| Reversible? | **Yes — trivially, no key** | **No** (only guessable) | Yes, **with the key** |
| Key needed? | No | No | **Yes** |
| Examples | base64, hex, URL-encoding, ROT13, brainfuck | MD5, SHA-256, bcrypt, phpass | AES, RSA, ChaCha20 |
| Security value | **Zero** | Depends on the algorithm | Depends on the key |

**Why it matters operationally:** if what you found is *encoded*, you are one
command from the answer. If it is *hashed*, you are starting a guessing game whose
cost depends entirely on the algorithm. If it is *encrypted*, you need the key.

```bash
echo 'YWFydGk6YWFydGlAZ21haWwuY29t' | base64 -d; echo
# aarti:aarti@gmail.com
```

> **Base64 is not a secret.** It exists so binary data survives text-only transport
> — email attachments, HTTP headers, JSON. Seeing it "protecting" a password is a
> *finding*, not a defence. Machine 2 is built entirely on a student making this
> mistake in the other direction.

**Recognise base64 on sight:** the character set is only `A–Z a–z 0–9 + /` with
optional `=` padding, and **the length is a multiple of 4**. **Always check whether
it is nested** — decode, then test whether the result is itself base64 or hex.
Machine 8 uses **brainfuck**, an esoteric programming language, as "encryption";
`bf` and `python3 -c` both decode it, and the point is that *obscurity is not
confidentiality*.

**Identify hashes by prefix or length:**

| Shape | Algorithm | Crackable? |
| --- | --- | --- |
| 32 hex chars | MD5 | Instantly |
| 40 hex chars | SHA-1 | Instantly |
| 64 hex chars | SHA-256 | Instantly |
| `$1$…` | MD5-crypt | Fast |
| `$apr1$…` | Apache `.htpasswd` | Fast |
| `$2b$…` / `$2a$…` | bcrypt | Slow, by design |
| `$5$…` / `$6$…` | SHA-256/512-crypt | Slow |
| `$y$…` | yescrypt (modern Ubuntu) | Slow |
| **`$P$…` / `$H$…`** | **phpass — WordPress, Drupal** | ~5k/sec: 8192 MD5 rounds, deliberately slow |

Machine 7 uses **unsalted MD5** — the weakest thing on this list, and it falls in
seconds. Machine 9 uses **bcrypt**, which is why you attack the *wordlist* rather
than the algorithm.

---

## 2. Wordlists: where they come from

**`rockyou.txt`** is not a theoretical list. In 2009 the social-networking site
RockYou was breached; they had stored **32 million passwords in plaintext** — no
hashing at all. The dump became the most-used password list in security precisely
because it records what real people actually chose. It has 14,344,392 entries,
**ordered by observed frequency**, so the top of the file is disproportionately
valuable. On Kali it ships gzipped:

```bash
sudo gzip -dc /usr/share/wordlists/rockyou.txt.gz > rockyou.txt
wc -l rockyou.txt      # 14344392
```

| List | Size | Use for |
| --- | --- | --- |
| `rockyou.txt` | 14.3 M | Real human password choices |
| `dirb/common.txt` | 4,612 | First web content pass |
| `dirb/big.txt` | 204,669 | Second web pass |
| `fasttrack.txt` | 222 | The most common *service* passwords |
| **SecLists** | huge | Everything else — `sudo apt install seclists` |

### But a generic list fails against a themed box

CTF authors pick passwords that fit their theme and then scatter theme words all
over the website. A targeted list beats `rockyou` completely in that case:

```bash
cewl -d 2 -m 4 --with-numbers -e -w custom.txt http://target/   # crawl the site, harvest ITS words
python3 cupp.py -i                                              # build from a name, birthday, pet, employer
crunch 6 6 -t for%%% -o dict.txt                                # generate from a known pattern
```

| `cewl` flag | Meaning |
| --- | --- |
| `-d 2` | Crawl to depth 2 |
| `-m 4` | Minimum word length 4 |
| `-e` | Include email addresses found |
| `--with-numbers` | Accept words containing digits |
| `-w file` | Write the list out |

**Machine 4 (DC: 2) is the canonical lesson.** Its passwords are drawn from the
site's own content, and the intended solution is `cewl` → `wpscan`/`hydra`. Running
`rockyou.txt` at it will not work in any reasonable time. Machine 7 rewards the same
instinct.

---

## 3. The four attacks — do not confuse them

| Attack | Tries | Cost | Notes |
| --- | --- | --- | --- |
| **Wordlist** | a curated list, many passwords → **one** account | Low | Highest hit rate per attempt |
| **Brute force** | every character combination | Astronomical | Only sane for ≤6 chars or a known pattern |
| **Password spraying** | **one** password → **many** accounts | Low | Stays *under* per-account lockout thresholds |
| **Credential stuffing** | real leaked `user:pass` pairs | Low | Exploits reuse across sites |

Spraying is the professional default against lockout-protected systems: one
attempt per account, across hundreds of accounts, so no single account trips a
threshold. `hydra -L users.txt -p 'Summer2024!'` is a spray; `hydra -l admin -P
rockyou.txt` is not.

### Hydra

```bash
hydra -l admin -P /usr/share/wordlists/rockyou.txt ssh://target -t 4 -f
hydra -L users.txt -P pass.txt http-post-form://target/wp-login.php:"log=^USER^&pwd=^PASS^:F=incorrect"
hydra -l user -p '' ftp://target -e nsr
```

| Flag | Meaning |
| --- | --- |
| `-l USER` / `-L file` | single **l**ogin / a *file* of them |
| `-p PASS` / `-P file` | single **p**assword / a *file* of them |
| `-C file` | colon-separated `user:pass` **pairs** (stuffing) |
| **`-e nsr`** | also try **n**ull password, **s**ame-as-username, **r**eversed username |
| `-f` | stop at the first success |
| `-t N` | threads — higher is faster, noisier, and destabilises old VMs |
| `ssh://`, `ftp://`, `http-post-form://` | the **service module** — picking the wrong one is the most common Hydra mistake |

> **Always include `-e nsr`.** The three cheapest guesses in existence are empty,
> the username, and the reversed username — and they succeed astonishingly often,
> usually in under a second, before the wordlist is even consulted. Machine 1's
> intended path involves a password that *is* the username.

> ⚠️ Pointing Hydra at all 14 million lines of `rockyou` over SSH would take days
> and generate millions of failed logins in `auth.log`. Fine on a VM you own; on a
> real system it is an obvious, logged event. Professionals throttle with `-t 4`,
> use a short targeted list, and spray rather than hammer.

For web forms, `http-post-form` needs three things: the POST path, the body with
`^USER^`/`^PASS^` placeholders, and a **failure string** (`F=…`) or success string
(`S=…`) that distinguishes a bad login from a good one. Find it by logging in
incorrectly in a browser and reading the response.

---

## 4. Cracking offline

Once you have a hash, you never touch the server again:

```bash
john --wordlist=/usr/share/wordlists/rockyou.txt hash.txt
john --show hash.txt                                  # results without re-cracking
john --format=phpass --wordlist=rockyou.txt hash.txt  # force the format
unshadow /etc/passwd /etc/shadow > combined.txt       # prepare Linux hashes
hashcat -m 400 -a 0 hash.txt rockyou.txt              # -m = mode, -a 0 = wordlist
zip2john secret.zip > zip.hash && john --wordlist=rockyou.txt zip.hash
ssh2john id_rsa > key.hash
```

| hashcat `-m` | Algorithm |
| --- | --- |
| `0` | MD5 |
| `100` | SHA-1 |
| `400` | phpass (WordPress/Drupal) |
| `500` | MD5-crypt (`$1$`) |
| `1800` | SHA-512-crypt (`$6$`) |
| `3200` | bcrypt (`$2b$`) |
| `13600` | ZIP |
| `22921` | SSH RSA key |

**Reading John's output:**

```text
Loaded 1 password hash (phpass, MD5 [phpass 2.4.x/2.4.y 4x32])
Will run 8 OpenMP threads
Press 'q' or Ctrl-C to abort, almost any other key for status
letmein          (steven)
1g 0:00:00:14 DONE  3842p/s 71.43g/s
```

`Loaded 1 password hash (phpass, …)` means it auto-detected the format correctly —
if it says `No password hashes loaded`, pass `--format=` explicitly
(`john --list=formats` lists them). `1g 0:00:00:14 DONE` means one guess succeeded
in 14 seconds; `3842p/s` is the candidate rate. **That low rate is the algorithm's
defence working** — for MD5 it would be billions per second.

> ⚠️ **Always single-quote a hash on the command line.** In double quotes or bare,
> the shell expands `$P`, `$1`, `$6` as variables and silently truncates it. This is
> one of the most common reasons a crack "finds nothing".

**If the wordlist fails, add rules before giving up** — automatic mangling that
capitalises, appends digits and applies leetspeak:

```bash
john --wordlist=rockyou.txt --rules hash.txt
hashcat -m 0 -a 0 hash.txt rockyou.txt -r /usr/share/hashcat/rules/best64.rule
```

`best64.rule` applies 64 transformations per word. A list that fails outright very
often succeeds with rules, at 64× the cost.

---

## 5. Credential reuse: the highest-value habit in this module

**Every credential you find, try everywhere.** Against every service on the
machine, and against every username you have enumerated. This is not a tip — it is
the single most productive reflex on beginner boxes, and it is the reason
`hydra -C pairs.txt` exists.

Machines 1, 4, 7, 11 and 12 all hinge on reuse:

- a **database** password reused as the **system** password (Machines 10, 11)
- a **CMS** password reused for **SSH** (Machines 7, 11, 12)
- a **flag or encoded secret** reused as a password (Machine 2)
- one user's password reused by **another user** (Machine 4)

Build the habit mechanically. Keep a `creds.txt` in your notes and append every
`user:pass` you find, then:

```bash
# try every pair against every interesting service
hydra -C creds.txt ssh://target -t 4 -f
hydra -C creds.txt ftp://target
```

**Where credentials hide**, in rough order of how often they pay off:

| Location | Why |
| --- | --- |
| `wp-config.php`, `configuration.php`, `.env`, `web.config`, `settings.py` | A CMS needs DB credentials on *every* request, so they are necessarily plaintext |
| `~/.bash_history`, `~/.mysql_history` | People type passwords on command lines constantly |
| `*.bak`, `*.old`, `*.swp`, `*~` in the web root | Editors leave them; servers serve them as text |
| `/var/backups/`, `/opt/`, `/srv/` | Admin dumps and notes |
| Emails, tickets, README files on an SMB share | Machine 11's entire foothold |
| HTML comments and `robots.txt` | Machines 2, 6, 7, 13 |
| Image metadata and steganography | Machine 7 and others |
| `/etc/passwd` when field 2 holds a real hash instead of `x` | Legacy misconfiguration |

---

## 6. Exercises

1. **Prove one-wayness.** Hash a password with `md5sum`, then try to recover it by
   any method other than guessing. Write down why you cannot.
2. **Encode vs hash.** Take the string `admin:password`, base64-encode it, then
   MD5-hash it. Reverse both. Record which one you reversed without a key.
3. **Build a targeted wordlist.** Point `cewl` at any public site you own or a local
   app, with `-m 4 --with-numbers -e`. How many words? How many look like plausible
   passwords?
4. **Crack a real format.** Create a test user on a Kali VM, `unshadow` the files,
   and crack it with `john`. Then force the wrong `--format=` and observe the error.
5. **Measure algorithm cost.** Crack the same password stored as MD5 and as bcrypt
   with hashcat and compare `H/s`. Explain the difference in one sentence.
6. **Spray, don't hammer.** Against a local DVWA, run a 5-account × 1-password
   spray and then a 1-account × 5-password attack. Note which one a lockout policy
   would stop.

---

## 7. Check yourself

1. You find `cGFzc3dvcmQ=`. Is that a password you need to crack? Justify your answer.
2. Why is the *length* of a base64 string a useful tell, and what length property holds?
3. Which hash prefix indicates WordPress, and roughly how many guesses per second
   can a GPU make against it?
4. What is the difference between password spraying and brute force, and why does
   spraying defeat per-account lockouts?
5. What does `hydra -e nsr` add, and why should it be on every run?
6. Why must a hash be single-quoted on a shell command line?
7. Your wordlist attack fails. Name two things you try before concluding the
   password is strong.
8. Name four places credentials commonly hide on a compromised web server.

---

_Back to [Learning Path 1](README.md) · previous: [03 — Service and Network Attacks](03-Service-and-Network-Attacks.md) · next: [05 — Linux Privilege Escalation](05-Linux-Privilege-Escalation.md)._
