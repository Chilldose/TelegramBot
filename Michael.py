#!/usr/bin/env python3

"""This is Michael the Botfahters child. It recieves messages from his father and sends it via TCP to his underlings.
They execute the orders from Botfather and report back to Michael, after that the Botfather gets informed."""

import time, sys, json, os, yaml
import logging
import signal
import re
from forge.socket_connections import Client_, Server_
from forge.utilities import parse_args, LogFile, load_yaml
from forge.utilities import getuptime, getDiskSpace, getCPUuse, getRAMinfo, getCPUtemperature
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
        self.log = logging.getLogger("{} notes".format("Bot Logger"))
        self.config = None
        self.args = parse_args()
        self.bot = None
        self.quit = False
        self.intruders = {} # List of all false ID messages
        self.blocked_user_ID = []
        self.Server = None
        self.Client = None
        self.ask_superUser = ["/newuser"] # Command calls, which must be accepted/send by a superuser
        self.all_user_callbacks = ["/status", "/newuser"] # Commands every user can call
        self.newUserrequests = [] # Here all new user requests are stored as long as they are not processed


        #(regex, keyboard, Message, function to call)
        self.callback_commands = [(re.compile(r"/reboot"), [InlineKeyboardButton(text='No',
                                                                           callback_data='{"name": "do_reboot", "value": "no"}'),
                                                      InlineKeyboardButton(text='Yes',
                                                                           callback_data='{"name": "do_reboot", "value": "yes"}')],
                                   "Do you really want to restart the computer?", None
                                   ),
                                  (re.compile(r"/status"), None, "ComputerStats:", "do_statistics_callback"),
                                  (re.compile(r"/newuser"), None, "A new user wants to join the club: ", "do_newuser_request"),

                             ]

        # Do something
        self.log.info("Loading config file...")
        self.load_config()
        self.name = self.config.get("Name", "Michael")
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
            self.config_path = self.args.config
        elif self.config_path:
            self.config = load_yaml(self.config_path)
        else:
            self.log.error("{} cannot work without his cheat sheet. Please add a config file and retry.".format(self.name))

    def _init_connection_to_Bot(self):
        """Takes the information (token) from the config file and connects to the bot"""
        self.bot = telepot.Bot(self.config["token"])

    def _send_telegram_message(self, ID, msg, **kwargs):
        """Sends a telegram message to the father"""
        self.log.info("Sending message '{}' to ID: {}".format(msg, ID))
        if ID:
            self.bot.sendMessage(ID, msg, **kwargs)
        else:
            self.log.warning("No ID passed, no message sent!")

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
        :param ID: checks if the message was send from a specific ID (optional), can be int or list of int
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

    def do_statistics_callback(self, chat_ID, msg=None):
        """Gathers statistics information about the system and writes it on telegram"""
        uptime = "Uptime: {} h\n".format(round(getuptime()/3600,2))
        temp = "CPU Temperature: {} C\n".format(getCPUtemperature())
        CPU = "Uptime: {} %\n".format(getCPUuse())
        RAM = "RAM usage: {} \n".format(getRAMinfo())
        DISK = "Diskspace: {} \n".format(getDiskSpace())

        self._send_telegram_message(chat_ID, "Warning: This statistics apply to UNIX machines only!\n\n {} {} {} {} {}"
                                             "".format(uptime, temp, CPU, RAM, DISK))

    def handle_text(self, message):
        """This function simply handles all text based messages"""
        content_type, chat_type, ID = telepot.glance(message)
        if self.check_user_ID(message) or message["text"].strip() == "/newuser": # Either you know him or the first message is newuser command
            # Check if it is a command
            for val in self.callback_commands:
                # Handle Callbacks, only proceed if you are a superuser or the callback is for all users
                if val[0].match(message["text"]): # Check if callback

                    if val[0].pattern in self.ask_superUser:
                        # If superuser needs to be asked instead. Change the ID the message should get to
                        ID = self.config["SuperUser"][0]

                    if (val[0].pattern in self.all_user_callbacks) or ID in self.config["SuperUser"]:
                        keyboard = InlineKeyboardMarkup(inline_keyboard=[val[1]]) if val[1] else None
                        if keyboard:
                            self._send_telegram_message(ID, val[2], reply_markup=keyboard)
                        else: # If no buttons are there call the callback function
                            try:
                                funct = getattr(self, val[3])
                                funct(ID, msg=message)
                            except Exception as err:
                                self.log.error("Could not execute function {} Error: {}".format(val[3], err))
                        return
                    else:
                        self.report_to_owner(message)

            if content_type == "text":
                response = self._send_message_to_underlings(message)
                self._send_telegram_message(ID, "{}".format(response))

        elif message["text"].strip() == "/start":
            ID = message['from']['id']
            name = message['from'].get('first_name', "None")
            username = message['from'].get('username', "None")
            lastname = message['from'].get('last_name', "None")
            send_to = self.config["SuperUser"][0]
            self._send_telegram_message(send_to, "A new user has started a conversation with me: \n\n" \
                                                 "ID: {} \n" \
                                                 "User Name: {} \n" \
                                                 "First Name: {} \n" \
                                                 "Last Name: {} \n".format(ID, username, name, lastname))

        else: # If the ID is not recognised
            if ID not in self.blocked_user_ID:
                self.blocked_user_ID.append(ID)
                self.report_to_owner(message)
                self._send_telegram_message(self.config["SuperUser"][0], "I furthermore could not find any reference to this person. I added him "
                                            "to the list of blocked IDs. All further messages will be ignored from this "
                                            "ID.")


    def report_to_owner(self, message, send_to=None):
        ID = message['from']['id']
        name = message['from'].get('first_name', "None")
        username = message['from'].get('username', "None")
        lastname = message['from'].get('last_name', "None")
        send_to = send_to if isinstance(send_to, int) else self.config["SuperUser"][0]
        self._send_telegram_message(send_to, "An unauthorized user tried sending me a message: \n\n" \
                                                                 "ID: {} \n" \
                                                                 "User Name: {} \n" \
                                                                 "First Name: {} \n" \
                                                                 "Last Name: {} \n" \
                                                                 "Message: {}".format(ID, username, name, lastname,
                                                                                      message))
        self._send_telegram_message(ID, "You have written {}, but I do not recognise you or you are not authorized to do "
                                        "this action. Your message will be deleted and forgotten. "
                                        "I furthermore have reported this incident "
                                        "to the Botfather. He will decide your fate!".format(self.name))

    def do_reboot_callback(self, query_id, chat_id, value, query):
        """Restarts the respberry"""
        self.bot.answerCallbackQuery(query_id)
        if value.lower() == 'no':
            self._send_telegram_message(chat_id, "Aborted reboot")
        else:
            self._send_telegram_message(chat_id, "Reboot initiated")
            try:
                os.system("sudo /sbin/reboot &")
                os.kill(os.getpid(), signal.SIGINT)
            except:
                self._send_telegram_message(chat_id, "Reboot failed. Only works on LINUX machines")

    def do_newuser_request(self, SuperUser, msg):
        """Adds a new user to the framework. This function gets calles two times. First when the new user sends the
        query. There only an Id will be send"""
        ID = msg['from']['id']
        name = msg['from'].get('first_name', "None")
        username = msg['from'].get('username', "None")
        lastname = msg['from'].get('last_name', "None")
        self.newUserrequests.append((ID, name, lastname, username))
        keyboard = [InlineKeyboardButton(text='Accept',
                                  callback_data='{"name": "do_newuser", "value": "yes"}'),
                        InlineKeyboardButton(text='Reject',
                                  callback_data='{"name": "do_newuser", "value": "no"}')]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[keyboard])
        text = "A user wants to become a member of the Family: \n\n" \
                                                                 "ID: {} \n" \
                                                                 "User Name: {} \n" \
                                                                 "First Name: {} \n" \
                                                                 "Last Name: {}".format(ID, username, name, lastname)
        self._send_telegram_message(SuperUser, text, reply_markup=keyboard)
        self._send_telegram_message(ID, "Your request has been send to an admin.")

    def do_newuser_callback(self, query_id, chat_id, value, query):
            """Does or does not add the user"""
            self.bot.answerCallbackQuery(query_id)
            newID = int(re.findall(r"ID:\s*(\w*)", query["message"]["text"])[0])

            for i, entry in enumerate(self.newUserrequests):
                if newID == entry[0]:
                    del self.newUserrequests[i]

            if value.lower() == 'no':
                self._send_telegram_message(chat_id, "User not added to the family")
                self._send_telegram_message(newID, "Your request has been declined by the admin")
            else:
                self.config["Users"].append(newID)
                with open(self.config_path, 'w') as outfile:
                    yaml.dump(self.config, outfile, default_flow_style=False)
                self._send_telegram_message(chat_id, "User added to the family")
                self._send_telegram_message(newID, "Welcome to the family. Your request has been approved by an admin.")

    def handle_callback(self, query):
        """Handles callbacks from telegram"""
        query_id = query['id']
        chat_id = query['message']['chat']['id']
        callback_data = query['data']
        # Extract data from callback
        cb_info = json.loads(callback_data)

        if self.check_user_ID(query):
            # Funktionsname erstellen (im Attribut "name")
            func_name = "{}_callback".format(cb_info['name'])
            func = getattr(self,func_name)
            # Funktion aufrufen
            func(query_id, chat_id, cb_info['value'], query)
        else:
            self.log.critical("Unauthorized person tried to make a callback. ID: {}".format(query_id))
            for superU in self.config["SuperUser"]:
                self.report_to_owner(query, send_to=superU)


if __name__ == "__main__":
    bot = Michael("config.yml")
    bot.run()


