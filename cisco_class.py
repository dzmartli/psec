#! /usr/bin/env python3

import re
import time
import logging
import datetime
from service_funcs import end_task
from wrapp_class import Wrapp
from netmiko import ConnectHandler


class BaseCiscoSSH(Wrapp):
    """
    Cisco switch connection class
    """
    def __init__(self, task_params, log_file_name, config, **cisco):
        self.port = task_params['port_num']
        self.date = datetime.datetime.today().strftime('%b %d')
        self.mac = task_params['mac_addr']
        self.config = config
        self.log_file_name = log_file_name
        self.ssh = ConnectHandler(**cisco)
        self.ssh.enable()
        self.logging_mac = self.ssh.send_command('sh logging | include ' + self.date, delay_factor=10)
        self.log = self.ssh.send_command('sh run interface ' + self.port, delay_factor=5)
        self.int_stat = self.ssh.send_command('sh interface ' + self.port, delay_factor=5)
        self.sh_run = self.ssh.send_command('sh run', delay_factor=5)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.ssh.disconnect()

    @Wrapp.next_check
    def completed_task(self):
        """
        Checks if settings have been made before
        """
        if self.mac in self.log:
            logging.info('<<<OK>>> Settings have been made before <<<OK>>>\r\n\r\nTask completed')
            self.ssh.disconnect()
            return True
        else:
            logging.info('!!!OK!!!! Setup required\r\n')
            return False

    @Wrapp.failed_check
    def access(self):
        """
        Checks if it is an access port (in case of an IP or port error)
        """
        if 'switchport mode access' in self.log:
            logging.info('!!!OK!!! Access port\r\n')
            return True
        else:
            self.ssh.disconnect()
            logging.info('!!!NOT OK!!!! Not an access port\r\n\r\nTask failed')
            return False

    @Wrapp.failed_check
    def max(self):
        """
        Checks the allowed number of devices on a port
        """
        if 'maximum' not in self.log:
            logging.info('!!!OK!!! Only one device allowed per port\r\n')
            return True
        else:
            self.ssh.disconnect()
            logging.info('!!!NOT OK!!! Configuring multiple devices per port\r\n\r\nTask failed'')
            return False

    @Wrapp.failed_check
    def port_stat(self):
        """
        Checks port status
        """
        if ' is down' in self.int_stat:
            self.ssh.disconnect()
            logging.info('!!!NOT OK!!! Port status DOWN\r\n\r\nTask failed')
            return False
        else:
            logging.info('!!!OK!!! Port status UP\r\n')
            return True

    @Wrapp.failed_check
    def check_hub(self):
        """
        Checks if the device is connected via a hub
        """
        logging_mac_split = self.logging_mac.split('\n')
        logging_mac_split_all = []
        for line_log in logging_mac_split:
            if all([('%PORT_SECURITY' in line_log), (self.port in line_log)]):
                logging_mac_split_all.append(line_log)
        logging_mac_split_clean = []
        for line_log_ip in logging_mac_split_all:
            if self.mac not in line_log_ip:
                logging_mac_split_clean.append(line_log_ip)
        # If there were PSECURE_VIOLATION on the same port today but with a different MAC
        if len(logging_mac_split_clean) >= 1:
            self.ssh.disconnect()
            logging.info('!!!NOT OK!!! Multiple devices on a port connect through a hub\r\n\r\nTask failed'')
            return False
        else:
            logging.info('!!!OK!!! One MAC per port\r\n')
            return True

    @Wrapp.failed_check
    def mac_on_other_port(self):
        """
        Checks if this MAC is stuck to another port on the same switch
        """
        if self.mac in self.sh_run:
            int_list = re.findall(r'(\S+Ethernet\S+)', self.sh_run)
            for ints in int_list:
                sh_int = self.ssh.send_command('sh run interface ' + ints, delay_factor=10)
                # Clear sticky is not done if this MAC address is stick to the port behind which the hub is located
                if self.mac in sh_int:
                    if 'maximum' in sh_int:
                        self.ssh.disconnect()
                        logging.info('!!!NOT OK!!! MAC on another port ' +
                             ints + ', but a hub is connected there\r\n\r\nTask failed')
                        return False
                    else:
                        self.ssh.send_command('clear port-security sticky interface ' + ints, delay_factor=10)
                        time.sleep(5)
                        logging.info('!!!OK!!! Port sticky reset on other port ' +
                                      ints + '\r\n')
                        return True

    @Wrapp.next_check
    def already_stick(self):
        log = self.ssh.send_command('sh run interface ' + self.port, delay_factor=10)
        if self.mac in log:
            logging.info(log)
            self.ssh.send_command('wr mem', delay_factor=20)
            self.ssh.disconnect()
            logging.info('<<<OK>>> SUCCESSFUL SETUP <<<OK>>>\r\n\r\nTask completed')
            return True
        else:
            logging.info('!!!OK!!! Port sticky reset\r\n')
            return False

    @Wrapp.next_check
    def port_sec_first_try(self):
        """
        Port-security setup
        """
        self.ssh.send_command('clear port-security sticky interface ' + self.port, delay_factor=5)
        time.sleep(30)
        # Update port information
        log = self.ssh.send_command('sh run interface ' + self.port, delay_factor=5)
        if self.mac in log:
            logging.info(log)
            self.ssh.send_command('wr mem', delay_factor=20)
            self.ssh.disconnect()
            logging.info('<<<OK>>> SUCCESSFUL SETUP <<<OK>>>\r\n\r\nTask completed')
            return True
        else:
            logging.info('!!!OK!!! MAC not stick, second try needed\r\n')
            return False

    @Wrapp.pass_check
    def port_sec_second_try(self):
        # If there is not enough time to stick, one more attempt is made
        self.ssh.send_command('clear port-security sticky interface ' + self.port, delay_factor=5)
        time.sleep(240)
        # Update port information
        log = self.ssh.send_command('sh run interface ' + self.port, delay_factor=5)
        if self.mac in log:
            logging.info(log)
            self.ssh.send_command('wr mem', delay_factor=20)
            self.ssh.disconnect()
            logging.info('<<<OK>>> SUCCESSFUL SETUP (second reset) <<<OK>>>\r\n\r\nTask completed')
            return True
        else:
            self.ssh.disconnect()
            logging.info('!!!NOT OK!!! UNABLE TO SET UP, '
                         'MAC DOES NOT STICK TO THE PORT\r\n\r\nTask failed')
            return False

