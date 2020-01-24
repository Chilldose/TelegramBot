# Michael the TelegramBot

Hi, I am Michael the Botfathers son. I can help you communicate with you and your friends and your own
scripts via the Telegram Messenger. My skillset is comprised with a TCP/IP package communication interface.
With this I can easily communicate with a large variety of different services. As long as they can send json styled packages to me.

## Installation

Currently there is no package list available. But you will need telepot and the yaml python packages.

## Get me working

In the root dir you will find a config.yml file. In there you find the token entry. Here you have to put in the token of your telegram
bot. Without it I cannot send you anything. 

Warning: Never give this token to persons you do not know. With it everyone can hijacks your bot!

For the 'SuperUser' entry please add as FIRST entry your telegram ID. This will make you the owner of this telegram bot instance!
You can add more SuperUsers if you want, they have more or less the same rights as you do but you get more information then the others,
if something happens

The 'User' entry is for all users. Please add yourself there as well. All other users can be added later on through the
internal registration proceedure.

The socket_connection entry is for defining my Server and Clients IP address.
