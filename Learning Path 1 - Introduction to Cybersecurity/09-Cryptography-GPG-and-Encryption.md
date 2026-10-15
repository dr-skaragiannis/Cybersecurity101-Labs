# Module 09 — Cryptography in Practice: GPG and File Encryption

> **Read this before:** Machines 2 (encoding vs encryption), and the extended-track
> machines that hide secrets in encrypted form (DC-7, Prime 1).
> **Why it exists.** Module 04 sorted out **encoding vs hashing**. This module adds
> the third leg — **encryption** — and the tool you will actually meet: **GPG**. You
> will generate a key pair, encrypt and sign with it, decrypt a symmetric file, and
> understand why an encrypted backup is only as strong as the place its **passphrase**
> is stored. That last sentence is the whole plot of DC-7.

**Full treatment:** [`docs/CONCEPTS.md`](../docs/CONCEPTS.md) §10 (encoding vs hashing
vs encryption) and §14 (cracking).

---

## 1. The three transformations, one last time

| | **Encoding** | **Hashing** | **Encryption** |
| --- | --- | --- | --- |
| Purpose | represent data (transport) | verify integrity / store a secret **one-way** | **hide** data, **reversibly** |
| Key needed? | no | no (or a salt) | **yes** |
| Reversible? | trivially | no | only with the key |
| Example | `base64`, hex, URL-encoding | `md5sum`, `sha256sum`, `$6$` crypt | GPG, `openssl enc`, LUKS |
| CTF tell | decodes instantly | you *crack* it | you need a key/passphrase |

> **The mistake to kill now:** calling `base64` "encryption". Base64 has **no key**;
> it hides nothing. If you can reverse it with one command, it is encoding.

---

## 2. Symmetric encryption — one key

One secret (a passphrase) both encrypts and decrypts.

### 2.1 GPG symmetric

```bash
gpg --symmetric --cipher-algo AES256 secrets.tar      # writes secrets.tar.gpg
gpg --decrypt secrets.tar.gpg > secrets.tar
```

### 2.2 `openssl enc`

```bash
# encrypt (modern, with a random salt + KDF)
openssl enc -aes-256-cbc -pbkdf2 -salt -in plain.txt -out cipher.bin
# decrypt
openssl enc -d -aes-256-cbc -pbkdf2 -in cipher.bin -out plain.txt
```

> **The classic mistake you will exploit.** Some old scripts use
> `openssl enc -aes-256-ecb -K <hexkey>`: **ECB** mode (no IV, deterministic blocks —
> patterns leak) with a **hardcoded key**. Both are reportable weaknesses. Prime 1
> gives you exactly this, and the key is sitting in the script.

### 2.3 Full-disk / volume encryption

```bash
sudo cryptsetup luksFormat /dev/sdb1          # create a LUKS container
sudo cryptsetup luksOpen  /dev/sdb1 vault      # unlock -> /dev/mapper/vault
sudo cryptsetup luksDump /dev/sdb1            # inspect (no passphrase needed!)
```

`luksDump` leaks the cipher, key-slot count and **iterations** without the
passphrase — useful for a defender's risk assessment and for an attacker's cracking
plan.

---

## 3. Asymmetric encryption — a key pair (this is "GPG key issuance")

Two keys: a **public** key you give away, and a **private** key you never do. What
one locks, only the other opens — which also gives **signatures**.

### 3.1 Generate a key pair

```bash
gpg --full-generate-key
```

```text
Please select what kind of key you want:
   (1) RSA and RSA
   (2) DSA and Elgamal
   ...
   (9) ECC (sign and encrypt) *default*
Your selection? 1
What keysize do you want? 4096
Key is valid for? (0) 2y
Real name: Alice Doe
Email address: alice@example.org
```

You have now performed **key issuance**: a key pair with an identity, an algorithm,
a size and an **expiry**. List and inspect it:

```bash
gpg --list-keys
gpg --list-secret-keys --with-keygrip
```

### 3.2 Export / import — distributing the public key

```bash
gpg --armor --export alice@example.org > alice.pub.asc   # share this
gpg --import alice.pub.asc
gpg --fingerprint alice@example.org                      # the identity you verify
```

> **Verify the fingerprint out of band.** A public key is only trustworthy if the
> fingerprint came from a channel the attacker does not control. This is the entire
> reason **keyservers alone are not enough** and why the Web of Trust exists.

### 3.3 Encrypt, decrypt, sign, verify

```bash
gpg --encrypt --recipient alice@example.org file.txt      # -> file.txt.gpg
gpg --decrypt file.txt.gpg > file.txt                     # needs Alice's PRIVATE key
gpg --clearsign message.txt                               # sign, keep readable
gpg --detach-sign --armor file.txt                        # file.txt.asc signature
gpg --verify file.txt.asc file.txt                        # check signature
```

| Operation | Key used | Proves |
| --- | --- | --- |
| Encrypt | recipient's **public** | only the recipient can read |
| Decrypt | recipient's **private** | you are the recipient |
| Sign | signer's **private** | the signer wrote it |
| Verify | signer's **public** | the message was not altered |

### 3.4 Key management is the real security

```bash
gpg --edit-key alice@example.org      # add UID, change expiry, revoke
gpg --export-secret-keys --armor > backup.asc   # BACK THIS UP, then protect it
```

A private key with **no passphrase**, exported to a world-readable file, is the same
as a plaintext password. Audit `~/.gnupg/` permissions — a `.gnupg` directory you can
read on a target is a finding (Chill Hack, HA: Rudra).

---

## 4. Encrypted archives and the modern alternative

```bash
zip -e archive.zip secret.txt          # password-protected zip
7z a -p -mhe=on archive.7z secret.txt  # AES-256, encrypts filenames too
age -r <public-key> -o out.age in.txt  # simple, modern file encryption
age -d -i key.txt -o in.txt out.age
```

`zip2john` / `7z2john` / `pdf2john` turn these into crackable hashes (Module 04 §8.6).
A weak archive passphrase falls to `rockyou.txt` in seconds.

---

## 5. Where encryption breaks — the DC-7 lesson

On **DC: 7**, the intended path is *not* "break AES". It is:

1. A root cron job runs a **GPG-encrypted** website backup.
2. The job emails its output — and the **passphrase is embedded in the script**, then
   leaks into root's `mbox` (`/var/mail/…`).
3. You read the mail, get the passphrase, and run
   `gpg --decrypt website.sql.gpg` yourself.

> **The principle, stated once:** *encryption protects data **at rest** and **in
> transit**; it does not protect against a key that is stored next to the ciphertext.*
> Cryptography was never the weak point — key management was. Every "encrypted"
> finding on these boxes is really a key-management finding.

---

## 6. Where you practise this

| Machine | What it teaches here |
| --- | --- |
| [`2-002-cybersploit-1`](../labs/2-002-cybersploit-1/README.md) | **encoding vs encryption** — decode, do not "crack" |
| [`4-073-dc-7`](../labs/4-073-dc-7/README.md) | GPG symmetric backup + **passphrase leaked in cron mail** |
| [`3-056-prime-1`](../labs/3-056-prime-1/README.md) | `openssl enc` with a **hardcoded key** and ECB mode |
| [`4-072-chill-hack-1`](../labs/4-072-chill-hack-1/README.md) | `.gnupg` on a target; encrypted archive (`zip2john`) |
| [`5-095-ha-rudra`](../labs/5-095-ha-rudra/README.md) | a readable `.gnupg` directory as a finding |

---

## 7. Exercises

1. `gpg --symmetric` a file, then decrypt it. Delete the plaintext first and prove
   the ciphertext alone is useless without the passphrase.
2. Generate a 4096-bit RSA key pair with a 1-year expiry, export only the **public**
   key, and encrypt a message to yourself from a *different* keyring.
3. Sign a file, edit one byte, and show `gpg --verify` fails.
4. Encrypt with `openssl enc -aes-256-cbc -pbkdf2` and again with `-aes-256-ecb`;
   encrypt the *same* plaintext twice under each and explain which output is
   deterministic and why that is a weakness.
5. Run `cryptsetup luksDump` on a LUKS volume and list everything it reveals without
   the passphrase.

## 8. Check yourself

1. Give one command that reverses each of: base64, SHA-256, GPG symmetric. What does
   each result prove?
2. In `gpg --encrypt -r bob`, whose key is used, and whose key decrypts?
3. What does a **detached signature** prove that a checksum does not?
4. Why is ECB mode weaker than CBC even with the same key?
5. State DC-7's weakness in one sentence — and name the control that would have fixed it.

---

## 9. Annotated command reference

### 9.1 `gpg --full-generate-key` and `--list-keys`

```bash
gpg --full-generate-key
gpg --list-keys --keyid-format long
```

```text
pub   rsa4096/3A5B7C9D2E1F0A4B 2024-05-11 [SC] [expires: 2026-05-11]
      8F2C 1D44 9A03 7B6E 5C10  3A5B 7C9D 2E1F 0A4B 6E77
uid                 [ultimate] Alice Doe <alice@example.org>
sub   rsa4096/1F0A4B6E77C9D2E1 2024-05-11 [E]
```

`pub` = public, `sub` = encryption subkey, `[SC]` = can **S**ign and **C**ertify,
`[E]` = can **E**ncrypt. The 40-hex-digit **fingerprint** is the identity you verify.

### 9.2 Symmetric round-trip

```bash
echo 'flag{test}' > p.txt
gpg -c --cipher-algo AES256 p.txt
file p.txt.gpg
gpg -d p.txt.gpg
```

`file` reports `GPG symmetrically encrypted data (AES256 cipher)` — note it names the
cipher without the passphrase, just like `luksDump`.

### 9.3 `openssl enc` weak vs strong

```bash
openssl enc -aes-256-cbc -pbkdf2 -salt -in p.txt -out strong.bin
openssl enc -aes-256-ecb -K 00112233445566778899aabbccddeeff -in p.txt -out weak.bin
openssl enc -d -aes-256-ecb -K 00112233445566778899aabbccddeeff -in weak.bin
```

The `-K` key is visible in the command/script — a hardcoded secret is not a secret.

### 9.4 Verify a signature

```bash
gpg --detach-sign --armor p.txt
gpg --verify p.txt.asc p.txt
```

```text
gpg: Good signature from "Alice Doe <alice@example.org>" [ultimate]
```

`Good signature` = the message is unaltered **and** signed by that key. It does *not*
say the key belongs to who it claims — that is the fingerprint-verification step.

---

_Back to [Learning Path 1](README.md) · previous: [08 — Identity, Authentication and PAM](08-Identity-Authentication-and-PAM.md) · next: [10 — Firewalls and Sandboxing](10-Firewalls-and-Sandboxing.md)._
