# Psec 
**Psec** is a prototype of a system that automates the secure access of new devices to the network using port-security technology.  
This prototype was developed for educational purposes based on a fictitious specification for a non-existent enterprise. Cisco devices (available in GNS3) are used as an example of access equipment.  

**Dependencies:**
- Python 3.6.9
- Netmiko 3.3.3

## How it works
**[PUML sequence diagram](https://raw.githubusercontent.com/5lunk/psec/main/psec.svg)**  

Description of parameters in the `conf.json` configuration file:
`proj_dir` – project directory
`log_dir` – logs directory
`mail_server` – mail server address
`mailbox` – network admin mailbox
`mail_from` – Psec mailbox
`mail_pass` – Psec mailbox password
`db_user` – DB username 
`db_pass` – DB password
`bad_ips` – list of excluded device addresses
`infsec_emails` – information security engineers mailbox list
