#! /usr/bin/env python3
"""
Some unit tests
"""
import datetime
import unittest

from service_funcs import (clearing_message,
                           find_macs_in_mess,
                           create_sql_query)


class ServiceTests(unittest.TestCase):
    """
    Service tests
    """

    def test_clearing_message(self):
        """
        Claering message test
        """
        raw_message_dict = {
            'message': 'pas<First Example 1234 !@#%(*%^$ >sed'
        }
        self.assertEqual(clearing_message(raw_message_dict), {
            'message': 'passed'
        })
        raw_message_dict = {
            'message': 'pas&nbsp;sed'
        }
        self.assertEqual(clearing_message(raw_message_dict), {
            'message': 'passed'
        })
        raw_message_dict = {
            'message': 'pas&quot;sed'
        }
        self.assertEqual(clearing_message(raw_message_dict), {
            'message': 'passed'
        })
        raw_message_dict = {
            'message': 'First Example 1234 !@#%(*%^$;}passed'
        }
        self.assertEqual(clearing_message(raw_message_dict), {
            'message': 'passed'
        })
        raw_message_dict = {
            'message': '\r\n\r\n\r\n\r\n\r\n\r\n\r\npassed'
        }
        self.assertEqual(clearing_message(raw_message_dict), {
            'message': '\r\npassed'
        })

    def test_find_macs_in_mess(self):
        """
        Find MACs in mesage test
        """
        decoded_message = 'Some messsage 0912.AB34.0009 for test'
        self.assertEqual(find_macs_in_mess(decoded_message), '0912ab340009')

        # No MAC
        decoded_message = 'Some messsage for test'
        self.assertEqual(find_macs_in_mess(decoded_message),
                         'No MAC addresses found\r\n\r\nTask failed')

        # Unresolved characters
        decoded_message = 'Some messsage 0912.AG34.0009 for test'
        self.assertEqual(find_macs_in_mess(decoded_message),
                         'No MAC addresses found\r\n\r\nTask failed')

        # To many MACs
        decoded_message = ('Some messsage 0912.AB34.0009 0912.AB34.0009 '
                           '0912.AB34.0009 for test')
        self.assertEqual(find_macs_in_mess(decoded_message),
                         'To many matches\r\n\r\nTask failed')

        # No spaces
        decoded_message = ('Some messsage 0912AB340009 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912ab340009')

        # Two symbols and dots
        decoded_message = ('Some messsage 09.12.AB.34.00.09 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912ab340009')

        # Two symbols and colons
        decoded_message = ('Some messsage 09:12:AB:34:00:09 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912ab340009')

        # Two symbols and dashes
        decoded_message = ('Some messsage 09-12-AB-34-00-09 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912ab340009')

        # Two symbols and spaces
        decoded_message = ('Some messsage 09 12 AB 34 00 09 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912ab340009')

        # Four symbols and dots
        decoded_message = ('Some messsage 0912.AB34.0009 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912ab340009')

        # Four symbols and colons
        decoded_message = ('Some messsage 0912:AB34:0009 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912ab340009')

        # Four symbols and dashes
        decoded_message = ('Some messsage 0912-AB34-0009 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912ab340009')

        # Four symbols and spaces
        decoded_message = ('Some messsage 0912 AB34 0009 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912ab340009')

        # Three symbols and dots
        decoded_message = ('Some messsage 091.2AB.340.009 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912ab340009')

        # Three symbols and colons
        decoded_message = ('Some messsage 091:2AB:340:009 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912ab340009')

        # Three symbols and dashes
        decoded_message = ('Some messsage 091-2AB-340-009 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912ab340009')

        # Three symbols and spaces
        decoded_message = ('Some messsage 091 2AB 340 009 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912ab340009')

        # Replacing cyrillic 'а'
        decoded_message = ('Some messsage 0912аb340009 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912ab340009')

        # Replacing cyrillic 'В'
        decoded_message = ('Some messsage 0912AВ340009 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912ab340009')

        # Replacing cyrillic 'с'
        decoded_message = ('Some messsage 0912aс340009 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912ac340009')

        # Replacing cyrillic 'О'
        decoded_message = ('Some messsage 0912AО340009 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912a0340009')

        # Replacing cyrillic 'Е'
        decoded_message = ('Some messsage 0912AЕ340009 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912ae340009')

        # Replacing 'O'
        decoded_message = ('Some messsage 0912AO340009 for test')
        self.assertEqual(find_macs_in_mess(decoded_message), '0912a0340009')

    def test_create_sql_query(self):
        """
        Generate SQL query test
        """
        mac = '4516ab87ea90'
        date = datetime.datetime.today().strftime('%Y-%m-%d')
        config = {
            'db_user': 'USER',
            'db_pass': 'PASS',
        }
        self.assertEqual(create_sql_query(mac, config), f'''mysql -u USER '''
                         f'''-pPASS -D Syslog -e "SELECT FromHost, Message '''
                         f'''FROM SystemEvents WHERE DeviceReportedTime '''
                         f'''LIKE '%{date}%' AND Message '''
                         f'''REGEXP '.*(4516.ab87.ea90).*' ORDER BY '''
                         f'''ID DESC LIMIT 1;"''')


if __name__ == '__main__':
    unittest.main()
