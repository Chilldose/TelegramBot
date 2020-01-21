#!/usr/bin/env python3

"""This is Michael the Botfahters child. It recieves messages from his father and sends it via TCP to his underlings.
They execute the orders from Botfather and report back to Michael, after that the Botfather gets informed."""

import time, sys, json, os
import logging
import pprint
import signal
import re
from forge.socket_connections import Client_, Server_
from forge.utilities import parse_args, LogFile, load_yaml
from forrge.utilities import getuptime, getDiskSpace, getCPUuse, getRAMinfo, getCPUtemperature
import telepot
from telepot.loop import MessageLoop
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton


class Michael:
    """This is the working environment of Michael. Here he directs everything"""

    def __init__(self, config=None):
        """
        :param config: The path to the config file of Michael, must be a JSON or YML
        """
        # Initialize Logger
        LogFile("loggerConfig.yml")
        self.start_time = time.time()
        self.processed_messages = 0
        self.config_path = config
        self.config = None
        self.log = logging.getLogger("Michaels notes")
        self.args = parse_args()
        self.bot = None
        self.quit = False
        self.intruders = {} # List of all false ID messages
        self.blocked_user_ID = []
        self.Server = None
        self.Client = None

        #(regex, keyboard, Message, function to call)
        self.callback_commands = [(re.compile(r"/reboot"), [InlineKeyboardButton(text='No',
                                                                           callback_data='{"name": "do_reboot", "wert": "no"}'),
                                                      InlineKeyboardButton(text='Yes',
                                                                           callback_data='{"name": "do_reboot", "wert": "yes"}')],
                                   "Do you really want to restart the computer?", None
                                   ),
                                  (re.compile(r"/status"), None, "ComputerStats:", "do_statistics_callback"),

                             ]

        # Do something
        self.log.info("Loading config file...")
        self.load_config()
        self.log.info("Connecting to the Bothfather for guidance...")
        self._init_connection_to_Bot()
        self.log.info("Start listening carefully to the Botfather...")

    def run(self):
        config_socket = self.config["Socket_connection"]
        self.Server = Server_(HOST=config_socket["Host"]["IP"], PORT=config_socket["Host"]["Port"])
        self.Server.start()  # Starts the Server thread
        self.Client = Client_(HOST=config_socket["Client"]["IP"], PORT=config_socket["Client"]["Port"])
        MessageLoop(self.bot, {"chat": self.handle_text,
                               "callback_query": self.handle_callback}).run_as_thread()
        self._send_telegram_message(self.config["SuperUser"][0], "Micheal just woke up and is ready for commands")
        while not self.quit:
            try:
                time.sleep(5)
            except KeyboardInterrupt:
                self.quit = True

    def load_config(self):
        """Loads the config file either from args or passed config file. Args are more important!"""
        if self.args.config:
            self.config = load_yaml(self.args.config)
        elif self.config_path:
            self.config = load_yaml(self.config_path)
        else:
            self.log.error("Michael cannot work without his cheat sheet. Please add a config file and retry.")

    def _init_connection_to_Bot(self):
        """Takes the information (token) from the config file and connects to the bot"""
        self.bot = telepot.Bot(self.config["token"])

    def _send_telegram_message(self, ID, msg, **kwargs):
        """Sends a telegram message to the father"""
        self.log.info("Sending message '{}' to ID: {}".format(msg, ID))
        self.bot.sendMessage(ID, msg, **kwargs)

    def _send_message_to_underlings(self, message):
        """Sends a message via tcp"""
        try:
            response = self.Client.send_request("TelegramBot", {str(message["from"]["id"]):"{}".format(message["text"])})
        except Exception as err:
            self.log.info("Server Error {}".format(err))
            return err
        self.log.info("Server responded with {}".format(response))
        return response

    def check_user_ID(self, message, ID=None):
        """
        This function checks if the user who sendet the message is a valid user.
        :param message: The telegram message
        :param ID: checks if the message was send from a specific ID (optional)
        :return: bool
        """
        senderID = message['from']['id']
        name = message['from'].get('first_name', "None")
        username = message['from'].get('username', "None")
        lastname = message['from'].get('last_name', "None")

        if isinstance(ID, int):
            ID = [ID]

        self.log.info("Got message from ID: {} with name {} {} and username {}".format(senderID, name, lastname, username))
        if senderID not in (self.config["Users"] if not ID else ID):
            self.log.critical("User with ID: {} and name {} and username {}, was not recognised as valid user!".format(ID, name, username))
            self.intruders[senderID] = message
            return False
        else:
            return True

    def do_statistics_callback(self, chat_ID):
        """Gathers statistics information about the system and writes it on telegram"""
        uptime = getuptime
        temp = getCPUtemperature
        CPU = getCPUuse
        RAM = getRAMinfo
        DISK = getDiskSpace

    def handle_text(self, message):
        """This function simply handles all text based messages"""
        content_type, chat_type, ID = telepot.glance(message)
        if self.check_user_ID(message):
            # Check if it is a command
            for val in self.callback_commands:
                if val[0].match(message["text"]):
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[val[1]]) if val[1] else None
                    if keyboard:
                        self._send_telegram_message(ID, val[2], reply_markup=keyboard)
                    else: # If no buttons are there call the callback function
                        try:
                            funct = getattr(self, val[3])
                            funct(chat_id)# Only one parameter because there is no more information
                        except Exception as err:
                            self.log.error("Could not execute function {} Error: {}".format(val[3], err))
                    return

            if content_type == "text":
                response = self._send_message_to_underlings(message)
                self._send_telegram_message(ID, "{}".format(response))

        else: # If the ID is not recognised
            if ID not in self.blocked_user_ID:
                self.blocked_user_ID.append(ID)
                name = message['from'].get('first_name', "None")
                username = message['from'].get('username', "None")
                lastname = message['from'].get('last_name', "None")
                self._send_telegram_message(self.config["SuperUser"], "An unauthorized user tried sending me a message: \n\n"\
                                                                      "ID: {} \n"\
                                                                      "User Name: {} \n"\
                                                                      "First Name: {} \n"\
                                                                      "Last Name: {} \n"\
                                                                      "Message: {}".format(ID, username, name, lastname, message["text"]))
                self._send_telegram_message(ID, "You have written Michael, but Michael does not recognise you. Your message"
                                                "will be deleted and forgotten. I furthermore have reported this incident"
                                                "to the Botfather. He will decide your fate!")

    def do_reboot_callback(self, query_id, chat_id, value):
        """Restarts the respberry"""
        self.bot.answerCallbackQuery(query_id)
        if value.lower() == 'no':
            self._send_telegram_message(chat_id, "Aborted reboot")
        else:
            self._send_telegram_message(chat_id, "Reboot initiated")
            os.system("sudo /sbin/reboot &")
            os.kill(os.getpid(), signal.SIGINT)

    def handle_callback(self, query):
        """Handles callbacks from telegram"""
        query_id = query['id']
        chat_id = query['message']['chat']['id']
        callback_data = query['data']
        # Extract data from callback
        cb_info = json.loads(callback_data)

        if self.check_user_ID(query, ID=self.config["SuperUser"]):
            # Funktionsname erstellen (im Attribut "name")
            func_name = "{}_callback".format(cb_info['name'])
            func = getattr(self,func_name)
            # Funktion aufrufen
            func(query_id, chat_id, cb_info['wert'])
        else:
            self.log.critical("Unauthorized person tried to make a callback. ID: {}".format(query_id))
            name = query['from'].get('first_name', "None")
            username = query['from'].get('username', "None")
            lastname = query['from'].get('last_name', "None")
            self._send_telegram_message(self.config["SuperUser"],
                                        "Unauthorized person tried to make a callback: \n\n" \
                                        "ID: {} \n" \
                                        "User Name: {} \n" \
                                        "First Name: {} \n" \
                                        "Last Name: {} \n" \
                                        "Query: {}".format(query_id, username, name, lastname, cb_info))


if __name__ == "__main__":
    bot = Michael("config.yml")
    bot.run()


