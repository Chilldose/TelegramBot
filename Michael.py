#!/usr/bin/env python3

"""This is Michael the Botfahters child. It recieves messages from his father and sends it via TCP to his underlings.
They execute the orders from Botfather and report back to Michael, after that the Botfather gets informed."""

import time, sys, json, os, yaml
import logging
import signal
import re
from forge.socket_connections import Client_, Server_
from forge.utilities import parse_args, LogFile, load_yaml, get_ip
from forge.utilities import getuptime, getDiskSpace, getCPUuse, getRAMinfo, getCPUtemperature
import telepot
from telepot.loop import MessageLoop
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
from threading import Thread


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
        self.all_user_callbacks = ["/status", "/newuser", "/help", "/ping", "/IP"] # Commands every user can call
        self.newUserrequests = [] # Here all new user requests are stored as long as they are not processed
        self.message_types = ["ID", "PLOT", "CALLBACK"]


        #(regex, keyboard, Message, function to call, helptext)
        self.callback_commands = [(re.compile(r"/reboot"), [InlineKeyboardButton(text='No',
                                                                           callback_data='{"name": "do_reboot", "value": "no"}'),
                                                      InlineKeyboardButton(text='Yes',
                                                                           callback_data='{"name": "do_reboot", "value": "yes"}')],
                                   "Do you really want to restart the computer?", None,
                                   "Reboots the computer (only LINUX machines, and you have to be an admin)."),
                                  (re.compile(r"/status"), None, "ComputerStats:", "do_statistics_callback", "Gives you some statistics about the computer (Only works on LINUX)."),
                                  (re.compile(r"/newuser"), None, "A new user wants to join the club: ", "do_newuser_request", "Send this message to be added as a valid user."),
                                  (re.compile(r"/help"), None, "All possible commands:", "do_help", "Shows you all possible commands."),
                                  (re.compile(r"/ping"), None, "The ping yielded:", "do_ping", "Pings the computer the Bot should connect to."),
                                  (re.compile(r"/IP"), None, "The IP is {}:", "do_get_IP",
                                   "Sends you the IP of the machine, the bot is running on.")

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
        self.Server.responder = self.handle_server_requests
        self.Server.start()  # Starts the Server thread
        self.Client = Client_(HOST=config_socket["Client"]["IP"], PORT=config_socket["Client"]["Port"])
        MessageLoop(self.bot, {"chat": self.handle_text,
                               "callback_query": self.handle_callback}).run_as_thread()
        try:
            self._send_telegram_message(self.config["SuperUser"][0], "Micheal just woke up and is ready for commands")
        except:
            self.log.error("You first need to send the bot a message, before he can send you one!")
        while not self.quit:
            try:
                time.sleep(5)
            except KeyboardInterrupt:
                self.quit = True

    def handle_server_requests(self, action, value):
        """handles all request which came from a client"""
        self.log.info("Got server message {}: {}".format(action, value))
        if action == "TelegramBot": # Only accept request for the telegram bot
            # Each value must contain as key the ID to whom I should send something
            if isinstance(value, dict):
                self._process_message({"ID": value}, ID=None) # Never do that with the ID!!! Only if you know what you are doing!!!
            else:
                self.log.critical("Client request was not a dictionary. Type: {}".format(type(value)))
                return "Request value must be a dictionary with keys beeing the ID to send to."
        else:
            self.log.critical("Got a message which was not for me! {}: {}".format(action, value))
            return "Wrong message action header for TelegramBot"


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

    def _send_message_to_underlings(self, message, ID=None):
        """Sends a message via tcp"""
        if isinstance(message, dict):
            msg = message["text"]
            from_ID = message["from"]["id"]
        else:
            msg = str(message)
            from_ID = ID

        try:
            response = self.Client.send_request("TelegramBot", {str(from_ID):"{}".format(msg)})
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

    def do_ping(self, ID, msg):
        """Pings the TCP server and waits for a response"""
        response = self._send_message_to_underlings("PING", ID)
        if response:
            self._send_telegram_message(ID, "Server answered and is ready")
        else:
            self._send_telegram_message(ID, "Server seems to be offline. A reboot can solve this problem.")

    def do_help(self, ID, msg):
        """Generates the help text"""
        text = ""
        for com in self.callback_commands:
            text += "{} - {} \n".format(com[0].pattern, com[4])
        self._send_telegram_message(ID, text)

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
            if content_type != "text":
                self._send_telegram_message(ID, "Sorry, I do not understand {}. I can only cope with text messages".format(content_type))
            # Check if it is a command
            #------------------------------------------------------------------------------------------------------
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
            #------------------------------------------------------------------------------------------------------

            # If its a message to be send to the client
            #------------------------------------------------------------------------------------------------------
            if content_type == "text":
                self.log.info("Text message arrived with content: {}".format(message["text"].strip()))
                response = self._send_message_to_underlings(message)
                if not response:
                    self.log.error("Server did not answer")
                    response = {"result": "The server seems to be offline..."}
                x = Thread(target=self._process_message, args=(self._extract_result(response),ID))
                x.start()



            # ------------------------------------------------------------------------------------------------------

        # If its the start message, just report this to the admin
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

        # If any other message is send and the user is not valid
        else: # If the ID is not recognised
            if ID not in self.blocked_user_ID:
                self.blocked_user_ID.append(ID)
                self.report_to_owner(message)
                self._send_telegram_message(self.config["SuperUser"][0], "I furthermore could not find any reference to this person. I added him "
                                            "to the list of blocked IDs. All further messages will be ignored from this "
                                            "ID.")

    def _process_message(self, response, ID):
        """
        Processes the message obtained by the server. This function should run in a thread. Since data from the
        may not be ready at run time.
        :param response: The response from the server
        :param ID: The ID the query was send from
        :param type: The type of message
        :return: None
        """
        self.log.info("Processing message: {} for userID: {}".format(response, ID))

        if isinstance(response, str): # Handle str messages
            self._send_telegram_message(ID, response)
            return

        # If the response is a dict
        elif isinstance(response, dict):
            message_processes = False
            for key, it in response.items():
                if key.strip().upper() in self.message_types:
                    message_processes = True
                    self._process_special_message(it, ID, type=key)

            if not message_processes:
                self.log.critical("Could not process message: {}. Message type was not recognized".format(response))


        # If it is any other type of message try to convert to str and send
        else:
            try:
                self._send_telegram_message(ID, str(response))
            except:
                self.log.critical("Could not convert response to str for ID: {}".format(ID))
                self._send_telegram_message(ID, "The response for you query returned a non str convertable "
                                                "object. Could not sent response!")

    def _process_special_message(self, message, ID, type):
        """Processes special type messages like Plot messages"""
        admin = self.config["SuperUser"][0]


        # If a picture should be send to the user
        if type.strip().upper() == "PLOT":
            # The value must be a string! And it must be a valid path.
            if isinstance(message, str):
                if os.path.isfile(os.path.normpath(message)):
                    self.bot.sendPhoto(ID, open(message, 'rb'))
                else:
                    self.log.critical("Path {} does not exist or is not accessible. No message sent to {}".format(message, ID))
                    self._send_telegram_message(ID, "Path {} does not exist or is not accessible.".format(message, ID))

        # ID means the subdict is a list
        elif type.strip().upper() == "ID":

            if not isinstance(message, dict):
                self.log.error("'ID' response data error. Data was not a dict! Message: {}".format(message))
                return

            for subID, subitem in message.items():
                try:
                    subID = int(subID)
                except:
                    self.log.critical("Could not convert ID to int conform ID")
                    continue

                if subID in self.config["Users"]: # Only send message to a valid user.
                    self._process_message(subitem, subID) # Reprocess this subitem but with another ID, to whom it should be send

                else:
                    self.log.critical("User {} was not recognised as valid user!")
                    self._send_telegram_message(admin, "Bad user ID encountered in response "
                                                                             "ID: {} not recognised!")
        # Handles callback messages with keyboard things
        elif type.strip().upper() == "CALLBACK":
            # callback_dict: keys= text for button,
            # example: {"info": "A message", "keyboard": {"Chill": Switch Chill, "SuperChill": Switch SuperChill}, "arrangement": ["Chill", "SuperChill"]}
            try:
                keyboard = self.gen_keyboard(message.get("keyboard", {}), message.get("arrangement", {}))
                try: # Todo: this is not very pretty and pythonic. Error if multiline buttons or not occures
                    key = InlineKeyboardMarkup(inline_keyboard=keyboard)
                    self._send_telegram_message(ID, message["info"], reply_markup=key) # For multiline buttons
                except:
                    key = InlineKeyboardMarkup(inline_keyboard=[keyboard])
                    self._send_telegram_message(ID, message["info"], reply_markup=key) # For single line buttons


            except Exception as err:
                self.log.error("Could not generate Keyboard due to an error: {}".format(err))


    def gen_keyboard(self, keyboard_dict, arrangement):
        """Generates a keyboard and returns the final keyboardobject list"""
        keyboard = []
        for arr in arrangement:
            subkey = None
            if isinstance(arr, list) or isinstance(arr, tuple):
                subkey = self.gen_keyboard(keyboard_dict, arr)
            elif isinstance(arr, str):
                subkey = InlineKeyboardButton(text=arr, callback_data='{'+'"name": "do_report_back", "value": "{}"'.format(keyboard_dict[arr]) + '}')

            if subkey:
                keyboard.append(subkey)
            else:
                self.log.error("Could not generate keyboard. Data type error in arrangement: {}".format(arr))
        return keyboard



    def _extract_result(self, response):
        """Each response must be a dictionary with only one entry {'result': whatever}
        Whatever can again be whatever you want --> Dict, str, list etc. This should prevent data mismatch
        And I know this isnt the best way to go. TODO: Make this better"""
        return response.get("result", "Error: Non valid response layout transmitted from server.")

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
                os.system("sudo /sbin/reboot -n&")
                #os.kill(os.getpid(), signal.SIGINT)
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
        self._send_telegram_message(ID, "Your request has been sent to an admin.")

    def do_newuser_callback(self, query_id, chat_id, value, query):
            """Does or does not add the user"""
            self.bot.answerCallbackQuery(query_id)
            newID = int(re.findall(r"ID:\s*(\w*)", query["message"]["text"])[0])

            for i, entry in enumerate(self.newUserrequests):
                if newID == entry[0]:
                    del self.newUserrequests[i]

            if value.lower() == 'no':
                self._send_telegram_message(chat_id, "User {} not added to the family".format(newID))
                self._send_telegram_message(newID, "Your request has been declined by the admin")
            else:
                self.config["Users"].append(newID)
                self.log.info("Try adding user to config file and write to file...")
                try:
                    with open(self.config_path, 'w') as outfile:
                        yaml.dump(self.config, outfile, default_flow_style=False)
                except Exception as err:
                    self.log.warning("Could not save config to file, user not permanently added. Error: {}".format(err))
                    self._send_telegram_message(chat_id, "Could not save config to file, user not permanently added")

                self._send_telegram_message(chat_id, "User {} added to the family".format(newID))
                self._send_telegram_message(newID, "Welcome to the family. Your request has been approved by an admin.")

    def do_report_back_callback(self, query_id, chat_id, value, query):
        """Reports the custom keyboard markup response to the client"""
        self.bot.answerCallbackQuery(query_id)
        response = self._send_message_to_underlings(value, chat_id)
        if response:
            return self._extract_result(response)

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
            response = func(query_id, chat_id, cb_info['value'], query)
            if response:
                self._process_message(response, chat_id)
        else:
            self.log.critical("Unauthorized person tried to make a callback. ID: {}".format(query_id))
            for superU in self.config["SuperUser"]:
                self.report_to_owner(query, send_to=superU)

    def do_get_IP_callback(self, ID, msg):
        """Gets the IP of the machine and sends it to the user."""
        try:
            IP = get_ip()
        except Exception as err:
            IP = "ERROR: Could not obtain IP. ERRORCODE: {}".format(err)
        finally:
            self._send_telegram_message(ID, "The IP is {}:".format(IP))



if __name__ == "__main__":
    path = os.path.dirname(os.path.realpath(__file__))
    bot = Michael(os.path.join(path, "config.yml"))
    bot.run()


