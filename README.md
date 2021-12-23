**Psec** – прототип системы, позволяющей автоматизировать организацию безопасного доступа новых устройств к сети посредством технологии port-security.
Данный прототип не рекомендуется к использованию и разрабатывался в учебных целях.
Техническое задание для разработки данного прототипа было сформулировано на базе некоторой вымышленной модели компании с определенными допущениями и удовлетворяющей следующим требованиям:  
1.	Отсутствие у компании системы для автоматизации процессов службы поддержки и управления ИТ-услугами (вместо этого используется электронная почта).
2.	Служба информационной безопасности компании должна согласовать данное ПО к использованию.
3.	Использование оборудования Cisco для доступа сотрудников к сети компании.  
Как видно из условий, данный прототип является «сферическим конем в вакууме». Первое и третье условия, как правило, противоречат друг другу на практике. Небольшим компаниям обычно не по карману использование оборудования Cisco (как и наличие отдела информационной безопасности), а те компании, которые используют оборудование этого вендора для доступа пользователей к сети, обычно располагают системами для автоматизации процессов службы поддержки и управления ИТ-услугами. В данном случае, оборудование Cisco было выбрано, как наиболее распространенное к эмуляции для использования в рамках лабораторных стендов (к примеру, GNS3).  
В основе технического задания к данному прототипу лежит производственный процесс выглядящий следующим образом:
1.	Пользователь хочет подключить новое устройство к сети компании.
2.	Системный администратор в неустановленной форме согласует новое подключение (с указанием МАК-адреса нового устройства) с отделом информационной безопасности.
3.	Сотрудник информационной безопасности уведомляет администратора сети о том, что согласовано новое устройство для подключения. Данное уведомление отправляется администратору сети с почтового ящика сотрудника информационной безопасности и содержит информацию о подтверждении и МАК-адрес нового устройства.
4.	Администратор сети получает данное сообщение и выполняет настройки на оборудовании доступа.  
В качестве основного технического условия требуется наличие лог-сервера (Linux), как отдельной виртуальной машины или аппаратного сервера. Обработка syslog сообщений от устройств  должна производиться при помощи утилиты Rsyslog и передаваться для дальнейшего хранения СУБД MySQL.  
Для работы данного прототипа потребуется отдельный почтовый ящик. Так же необходимо настроить правило переадресации на почтовом ящике администратора сети, для дублирования сообщений с заявками на ящик системы.  
**Стек:**
- Python 3.6.9
- Netmiko 3.3.3  
# Принцип работы
Диаграмма последовательности 
Прототип представляет из себя демонизированный python скрипт, проверяющий несколько раз в минуту выделенный почтовый ящик на наличие новых сообщений (через POP3, как наиболее универсальный и простой способ). Полученное сообщение обрабатывается и проверяется на соответствие исходящего адресата (список сотрудников ИБ). Если в полученном сообщении присутствует МАК-адрес, создается отдельный процесс для выполнения запроса и на почтовый адрес администратора сети приходит сообщение с указанием МАК-адреса устройства, и трек-идентификатором запроса. Если в сообщении по каким-то причинам не находится ни одного МАК-адреса, либо их находится более одного, администратору приходит сообщение о том, что запрос в обработку не принят. В течение рабочего дня скрипт подключается к лог-серверу и периодически проверяет наличие в базе журналов события с искомым устройством. Когда событие найдено, скрипт подключается к коммутатору доступа (на основе полученных из записи журнала данных) и выполняет настройки. Для подключения к лог-серверу и коммутаторам доступа используется модуль Netmiko. В процессе обработки одного запроса, а так же настройки оборудования формируется отдельный лог файл, который по завершении работы запроса отправляется на почтовый ящик администратора сети.  
Для более удобной работы с системой предусмотрены несколько простых инструментов администрирования. Если по каким-то причинам требуется отменить выполнение заявки, нужно отправить на почтовый ящик системы сообщение, начинающееся с “KILL ” и далее содержащее трек-идентификатор запроса. В случае если требуется уточнить статусы всех текущих запросов, нужно отправить сообщение, содержащее “REPORT” в теле письма. В этом случае, на почтовый адрес администратора сети поступит сообщение с лог-файлами всех текущих заявок во вложении.  
В качестве примера демонизации скрипта (systemd) в репозитории есть файл `psec.service`. В файле `conf.json` содержится основная конфигурация, файлы `cisco_params.json`, `sql_params.json` включают параметры подключения к сетевому оборудованию и лог-серверу (netmiko). Конфигурация системы содержится в файлах `conf.json`, `cisco_params.json`, `sql_params.json`.  
Описание параметров в `conf.json`:
`proj_dir` – директория проекта  
`log_dir` – директория для хранения логов  
`mail_server` – адрес почтового сервера  
`mailbox` - почтовый ящик администратора сети  
`mail_from` - почтовый ящик для работы системы  
`mail_pass` – пароль для почтового ящика системы  
`db_user` – имя пользователя СУБД  
`db_pass` – пароль для пользователя СУБД  
`bad_ips` – список исключенных адресов устройств  
`infsec_emails` – почтовые ящики сотрудников информационной безопасности  