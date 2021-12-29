#! /usr/bin/env python3

import re
import sys
import os
import subprocess
import time
import json
import logging
import smtplib
import datetime
import glob
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication


def log_rotation(config):
    """
    Ротация логов
    """
    if os.path.exists(config['log_dir'] + 'logs/') == False:
        os.mkdir(config['log_dir'] + 'logs/')
    if os.path.exists(config['log_dir'] + 'log_archive/') == False:
        os.mkdir(config['log_dir'] + 'log_archive/')
    if len(glob.glob1(config['log_dir'] + 'log_archive/', '*.txt')) >= 50:
        tar = 'tar czf ' + config['log_dir'] + 'log_archive/log_archive_' + \
              datetime.datetime.today().strftime('%Y-%m-%d') + \
              '.tar.gz ' + config['log_dir'] + 'log_archive/*.txt'
        subprocess.Popen(tar, shell=True, stderr=subprocess.DEVNULL)
        for log in glob.glob(config['log_dir'] + 'log_archive/*.txt'):
            os.remove(log)


def send_report(email, config):
    """
    Отправляет логи текущих заявок
    Выполняется при наличии ключа <REPORT> в тексте сообщения
    """
    files_list = os.listdir(config['log_dir'] + 'logs/')
    # Есть открытые заявки
    if len(files_list) >= 1:
        msg = MIMEMultipart()
        msg['Subject'] = 'Логи текущих заявок во вложении'
        send = smtplib.SMTP(config['mail_server'])
        for f in files_list:
            file_path = os.path.join(config['log_dir'] + 'logs/', f)
            attachment = MIMEApplication(open(file_path, 'rb').read(), _subtype='txt')
            attachment.add_header('Content-Disposition', 'attachment', filename=f)
            msg.attach(attachment)
        msg.attach(MIMEText('Логи текущих заявок во вложении'))
        send.sendmail(config['mail_from'], [email], msg.as_string())
        send.quit()
    # Нет открытых заявок
    else:
        msg = MIMEMultipart()
        msg['Subject'] = 'На данный момент нет заявок в обработке'
        send = smtplib.SMTP(config['mail_server'])
        send.sendmail(config['mail_from'], [email], msg.as_string())
        send.quit()


def send_start(log_file_name, mac, config):
    """
    Отправляет сообщение об открытии заявки с указанием МАС-адреса устройства и трекера заявки
    """
    msg = MIMEMultipart()
    msg['Subject'] = mac + ' принят в обработку'
    send = smtplib.SMTP(config['mail_server'])
    msg.attach(MIMEText(mac + ' принят в обработку, ТРЕКЕР: ' + log_file_name))
    send.sendmail(config['mail_from'], [config['mailbox']], msg.as_string())
    send.quit()


def send_end(log_file_name, mac, task_result, config):
    """
    Отправляет сообщение о закрытии заявки с указанием её статуса и логом её выполнения
    """
    msg = MIMEMultipart()
    msg['Subject'] = task_result + ' ' + mac
    send = smtplib.SMTP(config['mail_server'])
    with open(config['log_dir'] + 'logs/' + log_file_name + '.txt', 'r') as f:
        log = f.read()
    msg.attach(MIMEText(log))
    send.sendmail(config['mail_from'], [config['mailbox']], msg.as_string())
    send.quit()


def send_violation(message_dict, restriction, config):
    """
    Сообщение безопастности
    """
    msg = MIMEMultipart()
    msg['Subject'] = 'Уведомление безопастности. Сообщение от: ' + message_dict['email']
    send = smtplib.SMTP(config['mail_server'])
    msg.attach(MIMEText(restriction +
               '\r\n\r\n----------СООБЩЕНИЕ----------\r\n\r\n' +
               message_dict['message']))
    send.sendmail(config['mail_from'], [config['mailbox']], msg.as_string())
    send.quit()


def send_error(message_dict, error, config):
    """
    Сообщение об ошибке
    Наверно тут стоит задуматься о классе.....
    """
    msg = MIMEMultipart()
    msg['Subject'] = 'Ошибка, такой заявки не существует'
    send = smtplib.SMTP(config['mail_server'])
    msg.attach(MIMEText(error +
               '\r\n\r\n----------СООБЩЕНИЕ----------\r\n\r\n' +
               message_dict['message']))
    send.sendmail(config['mail_from'], message_dict['email'], msg.as_string())
    send.quit()


def kill_in_mess(message_dict, config):
    """
    Принудительно завершает заявку при условии наличия ключа <KILL> в сообщении
    После указанного ключа в сообщении должен быть указан трекер заявки
    """
    try:
        reg_kill = r'(task_\S+)'
        decoded_message = message_dict['message']
        task_match = re.search(reg_kill, decoded_message)
        log_file_name = task_match.groups()[0]
        kill_proc = int(log_file_name.split('_')[1])
        try:
            os.kill(kill_proc, 9)
            mac = log_file_name.split('__')[1].replace('-', '.')
            task_result = log_file_name + ' terminated'
            send_end(log_file_name, mac, task_result, config)
            mv = 'mv ' + config['log_dir'] + 'logs/' + log_file_name + '.txt ' + \
                 config['log_dir'] + 'log_archive/' + log_file_name + '.txt'
            subprocess.Popen(mv, shell=True)
        except Exception as error:
            send_error(message_dict, str(error), config)
    except Exception as error:
        send_error(message_dict, str(error), config)


def ip_list_check(log_file_name, task_params, mac, config):
    """
    Проверяет есть ли хост в списке запрещенных
    """
    if task_params['ip_addr'] not in config['bad_ips']:
        logging.info('!!!OK!!! Хост не в списке исключенных адресов\r\n\r\n')
    else:
        logging.info('!!!NOT OK!!! Хост в списке исключенных адресов\r\n\r\nЗаявка не выполнена')
        task_result = 'Заявка не выполнена'
        end_task(log_file_name, mac, task_result, config)


def sql_answer_check(log_file_name, sql_answer, mac, config):
    """
    Проверяет ответ от БД лог-сервера
    Отправляет сообщение с результатом, завершает процесс заявки
    в случае неудавлетворительного выполнения log_server_check()
    """
    if 'Заявка не выполнена' in sql_answer['answer']:
        logging.info(sql_answer['answer'])
        task_result = 'Заявка не выполнена'
        end_task(log_file_name, mac, task_result, config)
    else:
        logging.info('SQL_ANSWER: ' + sql_answer['answer'] + '\r\n')


def clean_message(raw_message_dict):
    """
    Очистка сообщения
    """
    reg_mess = r'<[\s\S|.]*?>|&nbsp;|&quot;|.*?;}'
    clean_mess = re.sub(reg_mess, '', raw_message_dict['message'])
    reg_line_break = r'(\r\n){5,}'
    clean_mess = re.sub(reg_line_break, '\r\n', clean_mess)
    raw_message_dict.update({'message': clean_mess})
    return raw_message_dict


def find_macs_in_mess(decoded_message):
    """
    Поиск МАС-адреса в сообщении
    """
    reg = re.compile('\s(?P<mac>([0-9A-Fa-fАаВСсЕеOО]{2}[\s:.-]){5}([0-9A-Fa-fАаВСсЕеOО]{2})'
                     '|([0-9A-Fa-fАаВСсЕеOО]{3}[\s:.-]){3}([0-9A-Fa-fАаВСсЕеOО]{3})'
                     '|([([0-9A-Fa-fАаВСсЕеOО]{4}[\s:.-]){2}([0-9A-Fa-fАаВСсЕеOО]{4})'
                     '|([0-9A-Fa-fАаВСсЕеOО]{12}))\s')
    m = reg.finditer(decoded_message)
    matches = []
    for mat in m:
        matches.append(mat.group('mac'))
    format_matches = []
    for match in matches:
        match = match.replace(':', "").replace('-', "").replace('.', "") \
                     .replace(' ', "").replace('\n', "").replace('\t', "")
        match = match.lower()
        # Заменить кириллические символы
        match = match.replace('а', 'a').replace('в', 'b').replace('с', 'c') \
                     .replace('е', 'e').replace('о', '0').replace('o', '0')
        format_matches.append(match)
    if len(format_matches) == 1:
        new_mac = format_matches[0]
        return new_mac
    elif len(format_matches) == 0:
        no_mac = 'В заявке не найдены МАС-адреса\r\n\r\nЗаявка не выполнена'
        return no_mac
    elif len(format_matches) >= 2:
        too_much_mac = 'В заявке слишком много совпадений\r\n\r\nЗаявка не выполнена'
        return too_much_mac


def find_macs_in_mess_check(log_file_name, mac, config):
    """
    Проверяет find_macs_in_mess()
    Отправляет сообщение с результатом, завершает процесс заявки
    в случае неудавлетворительного выполнения find_macs_in_mess()
    """
    # Ничего не найдено
    if 'В заявке не найдены МАС-адреса' in mac:
        logging.info(mac)
        mac = 'В заявке не найдены МАС-адреса'
        task_result = 'Заявка не выполнена'
        end_task(log_file_name, mac, task_result, config)
    # Слишком много матчей
    elif 'В заявке слишком много совпадений' in mac:
        logging.info(mac)
        mac = 'В заявке слишком много совпадений'
        task_result = 'Заявка не выполнена'
        end_task(log_file_name, mac, task_result, config)


def create_sql_query(mac, config):
    """
    Создает SQL запрос с найденным МАС-адресом для лог-сервера
    Событие должно содержать искомый МАС-адрес и иметь ту же дату что и запрос
    """
    mac_cisco = mac[:4] + '.' + mac[4:8]  + '.' + mac[8:12]
    match_sql = ('''mysql -u ''' + config['db_user'] + ''' -p''' + config['db_pass'] +
                 ''' -D Syslog -e "SELECT FromHost, Message FROM SystemEvents WHERE DeviceReportedTime LIKE '%''' +
                 datetime.datetime.today().strftime('%Y-%m-%d') +
                 '''%' AND Message REGEXP '.*(''' + mac_cisco +
                 ''').*' ORDER BY ID DESC LIMIT 1;"''')
    return match_sql


def end_task(log_file_name, mac, task_result, config):
    """
    Завершает заявку (отправляет сообщение с результатом)
    """
    send_end(log_file_name, mac, task_result, config)
    mv = 'mv ' + config['log_dir'] + 'logs/' + log_file_name + '.txt ' + \
         config['log_dir'] + 'log_archive/' + log_file_name + '.txt'
    subprocess.Popen(mv, shell=True)
    sys.exit()

