#!/usr/bin/env python3

"""This is Michael the Botfahters child. It recieves messages from his father and sends it via TCP to his underlings.
They execute the orders from Botfather and report back to Michael, after that the Botfather gets informed."""

import time, json, os, yaml
import logging
import re
from forge.socket_connections import Client_, Server_
from forge.utilities import parse_args, LogFile, load_yaml, get_ip
from forge.utilities import getuptime, getDiskSpace, getCPUuse, getRAMinfo, getCPUtemperature

from telegram import Update, ForceReply, InlineKeyboardButton , InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
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
        self.config = {}
        self.args = parse_args()
        self.bot = None
        self.updater = None
        self.dispatcher = None
        self.quit = False
        self.intruders = {} # List of all false ID messages
        self.blocked_user_ID = []
        self.Server = None
        self.Client = None
        self.newUserrequests = {} # Here all new user requests are stored as long as they are not processed


        # Do something
        self.log.info("Loading config file...")
        self._load_config()
        self.SuperUser = self.config["SuperUser"][0]
        self.name = self.config.get("Name", "Michael")
        self.log.info("Connecting to the Bothfather for guidance...")
        self._init_connection_to_Bot()
        self.log.info("Start listening carefully to the Botfather...")

    def run(self):
        # Init the socket connection for data exchange with other programs
        config_socket = self.config["Socket_connection"]
        self.Server = Server_(HOST=config_socket["Host"]["IP"], PORT=config_socket["Host"]["Port"])
        self.Server.responder = self.handle_server_requests
        self.Server.start()  # Starts the Server thread
        self.Client = Client_(HOST=config_socket["Client"]["IP"], PORT=config_socket["Client"]["Port"])

        # All command handlers and callback init
        self._add_telegram_commands()
        self.dispatcher.add_handler(CallbackQueryHandler(self.handle_callback))
        # Handles all text messages except for commands
        self.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, self.handle_text))

        # Start the Bot
        self.updater.start_polling()

        try:
            self._send_telegram_message(self.config["SuperUser"][0], "Michael just woke up and is ready for commands")
        except Exception as err:
            self.log.error("Init message could not be send with error: {}".format(err))

        # Run the bot until you press Ctrl-C or the process receives SIGINT,
        # SIGTERM or SIGABRT. This should be used most of the time, since
        # start_polling() is non-blocking and will stop the bot gracefully.
        self.updater.idle()

    # Bot Command Handlers #############################################################################################
    # All functions that begin with do, are added as command handlers to the bot. Typing the function name as telegram
    # bot command, will call this function --> e.g \newuser at telegram will call do_newuser
    def do_newuser(self, update: Update, context: CallbackContext):
        """Adds a new user to the framework. It will be called by the telegram bot command '\newuser'"""

        ID = update.effective_user.id
        name = update.effective_user.full_name
        is_bot = update.effective_user.is_bot
        username = update.effective_user.name
        SuperUser = self.SuperUser
        if not is_bot:
            self.newUserrequests.update({ID: (name, username)})
            keyboard = [InlineKeyboardButton(text='Accept',
                                             callback_data='{"name": "newuser_callback", "value": "yes/ID:'+str(ID)+'"}'),
                        InlineKeyboardButton(text='Reject',
                                             callback_data='{"name": "newuser_callback", "value": "no/ID:'+str(ID)+'"}')]
            keyboard = InlineKeyboardMarkup([keyboard])
            text = "A user wants to become a member of the Family: \n\n" \
                   "ID: {} \n" \
                   "User Name: {} \n" \
                   "Name: {}".format(ID, username, name)
            self._send_telegram_message(SuperUser, text, reply_markup=keyboard)
            update.message.reply_text("Your request has been sent to an admin.")
        else:
            self._send_telegram_message(SuperUser, "The bot {}, tried to connect with me. I blocked".format(username))

    def do_ping(self, update: Update, context: CallbackContext):
        """Pings the TCP server and waits for a response. Any response from the serves counts as success."""
        ID = update.effective_user.id
        response = self._send_message_to_server("PING", ID)
        if response:
            update.message.reply_text("Server answered and is ready")
        else:
            update.message.reply_text("Server seems to be offline. A reboot can solve this problem.")

    def do_help(self, update: Update, context: CallbackContext):
        """Generates the help text. It takes the doc strings of all possible telegram commands and replies them."""
        text = ""
        for com in self._get_all_telegram_commands():
            text += "{} - {} \n\n".format(com[0].strip(), com[1].strip())
        update.message.reply_text(text)

    def do_info(self, update: Update, context: CallbackContext):
        """Gathers statistics information about the system and writes it on telegram"""
        uptime = "Uptime: {} h\n".format(round(getuptime()/3600,2))
        temp = "CPU Temperature: {} C\n".format(getCPUtemperature())
        CPU = "Uptime: {} %\n".format(getCPUuse())
        RAM = "RAM usage: {} \n".format(getRAMinfo())
        DISK = "Diskspace: {} \n".format(getDiskSpace())

        update.message.reply_text("Warning: This statistics apply to UNIX machines only!\n\n {} {} {} {} {}"
                                             "".format(uptime, temp, CPU, RAM, DISK))

    def do_getIP(self, update: Update, context: CallbackContext):
        """Gets the IP of the machine and sends it to the user."""
        try:
            IP = get_ip()
        except Exception as err:
            IP = "ERROR: Could not obtain IP. ERRORCODE: {}".format(err)
            self.log.error("ERROR: Could not obtain IP. ERRORCODE: {}".format(err))
        finally:
            update.message.reply_text("The IP is {}:".format(IP))

    def do_reboot(self, update: Update, context: CallbackContext):
        """
        Ask if the system should be rebooted or not.
        """
        ID = update.effective_user.id
        is_bot = update.effective_user.is_bot
        username = update.effective_user.name
        SuperUser = self.SuperUser
        if not is_bot:
            keyboard = [InlineKeyboardButton(text='Reboot Now',
                                             callback_data='{"name": "reboot_callback", "value": "yes"}'),
                        InlineKeyboardButton(text='Abort',
                                             callback_data='{"name": "reboot_callback", "value": "no"}')]
            keyboard = InlineKeyboardMarkup([keyboard])
            text = "Do you want to reboot the system?"
            self._send_telegram_message(ID, text, reply_markup=keyboard)
        else:
            self._send_telegram_message(SuperUser, "The bot {}, tried to reboot me. I blocked".format(username))

    def do_start(self, update: Update, context: CallbackContext):
        """
        Reports to the owner if someone is connecting with the bot.
        """
        # If its the start message, just report this to the admin
        ID = update.effective_user.id
        name = update.effective_user.full_name
        is_bot = update.effective_user.is_bot
        lastname = update.effective_user.last_name
        username = update.effective_user.username
        SuperUser = self.SuperUser

        self._send_telegram_message(SuperUser, "A new user has started a conversation with me: \n\n" \
                                             "ID: {} \n" \
                                             "User Name: {} \n" \
                                             "First Name: {} \n" \
                                             "Last Name: {} \n " \
                                             "is Bot: {}".format(ID, username, name, lastname, is_bot))

    # Bot callback functions############################################################################################
    def reboot_callback(self, update, context, value):
        """Restarts the respberry if necessary"""
        if value.lower() == 'no':
            update.message.reply_text("Aborted reboot")
        else:
            update.message.reply_text("Reboot initiated")
            try:
                os.system("sudo /sbin/reboot -n&")
            except:
                update.message.reply_text("Reboot failed. Only works on LINUX machines")

    def newuser_callback(self, update, context, value):
            """
            Does or does not add the user.
            chat_id: The one sending the accept or decline response
            value: the value the admit set for accepting/not accepting
            query: the initial query object from the user asked for entry
            """
            chat_id = update.effective_user.id

            newID = int(value.split("/ID:")[1]) # The user requesting
            value = value.split("/ID:")[0]

            self.newUserrequests.pop(newID)

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

    def report_back_callback(self, query_id, chat_id, value, query):
        """Reports the custom keyboard markup response to the client"""

        response = self._send_message_to_underlings(value, chat_id)
        if response:
            return self._extract_result(response)

    # Telegram Bot handlers ############################################################################################
    def handle_text(self, update: Update, context: CallbackContext):
        """This function simply handles all text based message, entry point for messages comming from telegram"""
        ID = update.effective_user.id
        message = update.message.text

        if self.check_user_ID(update.effective_user):
            self.log.info("Text message arrived with content: '{}' from user {}".format(message.strip(), ID))
            response = self._send_message_to_server(message)
            if not response:
                self.log.error("Server did not answer")
                response = {"result": "The server seems to be offline..."}
            x = Thread(target=self._process_message, args=(self._extract_result(response),ID))
            x.start()

        # If any other message is send and the user is not valid
        else: # If the ID is not recognised
            if ID not in self.blocked_user_ID:
                self.blocked_user_ID.append(ID)
                self.report_to_owner(update, update.message.text)


    def handle_callback(self, update: Update, context: CallbackContext):
        """Handles callbacks from telegram"""
        ID = update.effective_user.id # The ID from the person making the response
        is_bot = update.effective_user.is_bot # Check if it is not a bot

        if is_bot:
            self.report_to_owner(update, update.callback_query.data)

        elif self.check_user_ID(update.effective_user):
            update.callback_query.answer()  # Answer the call so that everything is in order for the other party
            # Extract data from callback
            cb_info = json.loads(update.callback_query.data)
            func_name = cb_info['name']
            try:
                func = getattr(self, func_name)
                # Funktion aufrufen
                response = func(update, context, cb_info['value'])
            except Exception as err:
                self.log.error("Could not run callback function {} with error: {}".format(func_name, err))
                return
            if response:
                self._process_message(response, ID)
        else:
            self.log.critical("Unauthorized person tried to make a callback. ID: {}".format(ID))
            self.report_to_owner(update, update.callback_query.data)


    # Internal Server Handler ##########################################################################################
    def handle_server_requests(self, action, value):
        """Handles all request which came from a client"""
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

    # Private functions ################################################################################################
    def _add_telegram_commands(self):
        """
        Adds all functions starting with 'do_' as handlers to the telegram bot.
        """

        for names in self._get_all_telegram_commands():
            self.log.info("Adding telegram command {} as handler.".format(names))
            try:
                self.dispatcher.add_handler(CommandHandler(names[0], getattr(self, "do_"+names[0])))
            except Exception as err:
                self.log.error("Could not add telegram command handler {} with error {}".format(names, err))


    def _get_all_telegram_commands(self):
        """
        Finds all do_* members the framework and returns them without the do. Furthermore the doc string of all found
        commands will be returned as well. As return value tuples with (name, docstring) in as list will be returned.
        """
        names = []
        for poss in dir(self):
            if "do_" in poss[:3]:
                try:
                    names.append((poss[3:], getattr(self, poss).__doc__))
                except Exception as err:
                    self.log.error("Could not obtain docstring from function {} with error: {}".format(poss, err))
        return names

    def _load_config(self):
        """Loads the config file either from args or passed config file. Args are more important!"""
        if self.args.config:
            self.config = load_yaml(self.args.config)
            self.config_path = self.args.config
        elif self.config_path:
            self.config = load_yaml(self.config_path)
        else:
            self.log.error("{} cannot work without his cheat sheet. Please add a config file and retry.".format(self.name))

    def _init_connection_to_Bot(self):
        """Ta= N the information (token) from the config file and connects to the bot"""
        self.updater = Updater(self.config["token"])
        self.bot = self.updater.bot
        self.dispatcher = self.updater.dispatcher

    def _send_telegram_message(self, ID, msg, **kwargs):
        """Sends a telegram message to the father"""
        self.log.info("Sending message '{}' to ID: {}".format(msg, ID))
        if ID:
            self.bot.send_message(chat_id=ID, text=msg, **kwargs)
        else:
            self.log.warning("No ID passed, no message sent!")

    def _send_message_to_server(self, message, ID=None):
        """Sends a message via tcp to the server.
        :param ID: Sends the ID of the requester as well.
        """
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

    def _extract_result(self, response):
        """Each response must be a dictionary with only one entry {'result': whatever}
        Whatever can again be whatever you want --> Dict, str, list etc. This should prevent data mismatch
        And I know this isnt the best way to go."""
        try:
            return response.get("result", "Error: Non valid response layout transmitted from server.")
        except:
            self.log.error("Could not extract result from server message. Answer from server was {}".format(response))

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
            message_processed = False
            for key, it in response.items():
                if key.strip().upper() in ["ID", "IMAGE", "CALLBACK"]:
                    message_processed = True
                    self._process_special_message(it, ID, type=key)

            if not message_processed:
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
        if type.strip().upper() == "IMAGE":
            # The value must be a string! And it must be a valid path.
            if isinstance(message, str):
                self.log.info("Try sending image {}.".format(message))
                if os.path.isfile(os.path.normpath(message)):
                    self.bot.send_photo(ID, open(message, 'rb'))
                    self.log.debug("Image {} send...".format(message))
                else:
                    self.log.critical("Path {} does not exist or is not accessible. No message sent to {}".format(message, ID))
                    self._send_telegram_message(ID, "Could not send image. Picture not found.".format(message, ID))

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

    # General functions ################################################################################################
    def report_to_owner(self, update, message):
        ID = update.effective_user.id
        name = update.effective_user.full_name
        is_bot = update.effective_user.is_bot
        lastname = update.effective_user.last_name
        username = update.effective_user.username
        self._send_telegram_message(self.SuperUser, "An unauthorized user tried sending me a message: \n\n" \
                                                                 "ID: {} \n" \
                                                                 "User Name: {} \n" \
                                                                 "First Name: {} \n" \
                                                                 "Last Name: {} \n" \
                                                                 "is Bot: {} \n"
                                                                 "Message: {} ".format(ID, username, name, lastname,
                                                                                       is_bot, message))

    def gen_keyboard(self, keyboard_dict, arrangement):
        """Generates a keyboard and returns the final keyboardobject list
        param: keyboard_dict: a dict with the keys from arragement and value the value they should have if clicked.
        param: arrangement: [[button1, button2], button 3], with buttons the keys from keyboard dict
        """
        keyboard = []
        for arr in arrangement:
            subkey = None
            if isinstance(arr, (tuple, list)):
                subkey = self.gen_keyboard(keyboard_dict, arr)
            elif isinstance(arr, str):
                subkey = InlineKeyboardButton(text=arr, callback_data='{'+'"name": "do_report_back", "value": "{}"'.format(keyboard_dict[arr]) + '}')

            if subkey:
                keyboard.append(subkey)
            else:
                self.log.error("Could not generate keyboard. Data type error in arrangement: {}".format(arr))
        return keyboard

    def check_user_ID(self, user, ID=None):
        """
        This function checks if the user who sended the message is a valid user.
        :param message: The telegram message
        :param ID: checks if the message was send from a specific ID (optional), can be int or list of int
        :return: bool
        """
        senderID = user.id
        name = user.first_name
        username = user.username
        lastname = user.last_name

        if isinstance(ID, int):
            ID = [ID]

        self.log.info("Got message from ID: {} with name {} {} and username {}".format(senderID, name, lastname, username))
        if senderID not in (self.config["Users"] if not ID else ID) or not self.SuperUser:
            self.log.critical("User with ID: {} and name {} and username {}, was not recognised as valid user!".format(ID, name, username))
            self.intruders[senderID] = user
            return False
        else:
            return True


if __name__ == "__main__":
    path = os.path.dirname(os.path.realpath(__file__))
    bot = Michael(os.path.join(path, "config.yml"))
    bot.run()


