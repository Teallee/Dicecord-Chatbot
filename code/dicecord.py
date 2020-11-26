import discord
import time
import asyncio
import datetime
import socket
import traceback
import re
import sys

from utils.tokens import saver, token
from utils import textResponses
from utils.roller import Roller
from utils.messaging import SPLATS
import dbhelpers


class PoolError(Exception):
    def __init__(self, message):
        super().__init__()
        self.message = message


class DicecordBot:
    def __init__(self, token, me):
        self.token = token
        self.me = me

    def startBot(self):
        self.loop = asyncio.new_event_loop()
        self.client = discord.Client(loop=self.loop)

        @self.client.event
        async def on_ready():
            """Print details and update server count when bot comes online."""
            content = 'Logged in as'
            content += f'\n{self.client.user.name}'
            content += f'\n{self.client.user.id}'
            content += f'\n{datetime.datetime.now()}'
            print(content)
            await self.client.change_presence(activity=discord.Game(name='PM "help" for commands'))

        @self.client.event
        async def on_message(message):
            await self.on_message(message)

    async def on_message(self, message):
        # we do not want the bot to reply to itself
        if message.author == self.client.user:
            return

        try:
            await self.checkCommand(message)
        except TypeError:
            tb = traceback.format_exc()
            self.errorText(message, tb)
            return
        except dbhelpers.db.Error:
            tb = traceback.format_exc()
            self.errorText(message, tb)
            print(f'SQL error\n{tb}')
        except:
            tb = traceback.format_exc()
            self.errorText(message, tb)
            self.errorText(message, f'Unknown error\n{tb}')

    async def send(self, content, message, dm=False):
        if dm:
            member = message.author
            channel = await member.create_dm()
        else:
            channel = message.channel
        try:
            await channel.send(content)
        except (discord.Forbidden, UnicodeEncodeError, discord.errors.HTTPException):
            tb = traceback.format_exc()
            self.errorText(message, tb)

    async def checkCommand(self, message):
        if str(message.author) == self.me and "save-cod" in message.content.lower():
            # used to update server count on discord bot list
            await self.send(f'servers:{len(self.client.guilds)}', message)
            # sometimes activity goes away, use this as an opportunity to reset it
            await self.client.change_presence(activity=discord.Game(name='PM "help" for commands'))
            return

        if message.author.bot:
            return

        if not message.guild:  # Private Message - message.guild = None
            await self.pmCommands(message)
            return

        command = self.format_command(message)
        if not command:
            return

        out = None
        if ' roll ' in command:
            out = self.handle_roll(message, command)

        elif ' gangrel ' in command:
            out = self.handle_special_roll(message, command)

        elif ' gan ' in command:
            out = self.handle_special_roll(message, command)

        elif ' splat ' in command:
            out = self.set_splat(message)

        elif ' flavour ' in command:
            out = self.set_flavour(message)

        elif " delete " in command:
            out = self.delete_content(message)

        elif " prefix " in command:
            out = self.set_prefix(message)

        elif command.endswith(' splat'):
            out = self.check_splat(message)

        elif command.endswith(' prefix'):
            out = self.check_prefix(message)

        elif command.endswith(' flavour'):
            out = self.check_flavour(message)

        if out is not None:
            out = out.replace('[userID]', "{0.author.mention}")
            out = out.format(message)
            await self.send(out, message)

    def format_command(self, message):
        command = message.content.lower()
        prefix = None
        if self.client.user in message.mentions:
            # always reply when @mentioned
            return command

        if prefix and command.startswith(prefix + ' '):
            return command.replace(prefix, '', 1)

    def handle_roll(self, message, command):
        """Checks text for type of roll, makes that roll."""
        if 'roll one' in command:
            return Roller.roll_special()
        if ' gangrel ' in command or ' gan ' in command:
            return self.handle_special_roll(message, command)

        character = {'flavour': True, 'splat': 'default'}
        roller = Roller.from_dict(character)
        if "chance" in command:
            results = roller.roll_chance(paradox="paradox" in command)
            results = '\n'.join(results)
            return results

        else:
            results = []
            again = self.get_again_amount(command)
            if '+' in command or '-' in command:
                try:
                    dice_amount, expression = self.get_pool(command)
                    if dice_amount < 1:
                        # roll chance
                        results = [f'Calculated a pool of `{expression}={dice_amount}` dice - chance roll']
                        results += roller.roll_chance(paradox="paradox" in command)
                        results = '\n'.join(results)
                        return results
                    else:
                        results = [f'Calculated a pool of `{expression}={dice_amount}` dice']

                except PoolError as e:
                    return e.message
            else:
                dice_amount = self.getDiceAmount(command)

            if dice_amount is None:
                # stop if no dice number found
                return

            if dice_amount >= 50:
                return "Too many dice. Please roll less than 50."
            else:
                results += roller.roll_set(
                    dice_amount,
                    again=again,
                    rote="rote" in command,
                    paradox="paradox" in command,
                    frenzy="frenzy" in command,
                    sender_nick=message.author.nick.lower()
                )
                results = '\n'.join(results)
                return results

    # 10s don't reroll and 1s subtract from successes
    def handle_special_roll(self, message, command):
        """Checks text for type of roll, makes that roll."""
        if 'roll one' in command:
            return Roller.roll_special()

        character = {'flavour': True, 'splat': 'default'}
        roller = Roller.from_dict(character)
        if "chance" in command:
            results = roller.roll_chance(paradox="paradox" in command)
            results = '\n'.join(results)
            return results

        else:
            results = []
            again = self.get_again_amount(command)
            if '+' in command or '-' in command:
                try:
                    dice_amount, expression = self.get_pool(command)
                    if dice_amount < 1:
                        # roll chance
                        results = [f'Calculated a pool of `{expression}={dice_amount}` dice - chance roll']
                        results += roller.roll_chance(paradox="paradox" in command)
                        results = '\n'.join(results)
                        return results
                    else:
                        results = [f'Calculated a pool of `{expression}={dice_amount}` dice']

                except PoolError as e:
                    return e.message
            else:
                dice_amount = self.getDiceAmount(command)

            if dice_amount is None:
                # stop if no dice number found
                return

            if dice_amount >= 50:
                return "Too many dice. Please roll less than 50."
            else:
                results += roller.special_roll_set(
                    dice_amount,
                    again=11,
                    rote="rote" in command,
                    paradox="paradox" in command,
                    frenzy="frenzy" in command,
                    sender_nick=message.author.nick.lower()
                )
                results = '\n'.join(results)
                return results

    def get_again_amount(self, command):
        again_term = re.search("(8|9|no)again", command)
        if again_term:
            again = again_term.group(0)
            if again == '8again':
                again = 8
            elif again == '9again':
                again = 9
            elif again == 'noagain':
                again = 11
        else:
            again = 10
        return again

    def getDiceAmount(self, messageText):
        """Gets the amount of dice to roll

        Args:
            messageText (str): text of message

        Returns (int or None): amount of dice to roll
        """

        if "roll" in messageText:
            # First check for message of the form roll x
            matched = re.search(r'\broll ([0-9]+\b)', messageText)
            if matched:
                return int(matched.group(1))

        again = re.search("(8|9|no)again", messageText)
        if again:
            again = again.group()
            # Second check for message of the form againTerm x
            matched = re.search(f'(?<=\\b{again} )[0-9]+\\b', messageText)
            if matched:
                return int(matched.group())
            else:
                messageText = messageText.replace(again, '')

        # Check for first number after @mention and then first number in message
        splitMessage = messageText.split(f'{self.client.user.id}')
        for message in splitMessage[::-1]:
            matched = re.search(r'\b\d+\b', message)
            if matched is not None:
                return int(matched.group())

    def get_pool(self, text):
        regex_1 = r'gan|roll|gangrel| \b(-?\d{1,2})'
        regex_2 = r'([+-] ?\d{1,2})'
        numbers = re.findall(f'{regex_1}', text)
        numbers += re.findall(f'{regex_2}', text)
        if len(numbers) > 10:
            raise PoolError(message='Too many values, please only include 10 or fewer terms.')
        if not numbers:
            raise PoolError(message='Pool expression could not be parsed.')
        numbers = ''.join(numbers)
        pool = eval(numbers)
        return pool, numbers.replace(' ', '')

    def set_prefix(self, message):
        new_prefix, server_wide = self.extract_prefix(message)
        if new_prefix:
            if new_prefix == 'reset':
                new_prefix = None
            if server_wide:
                output = f"Server Prefix changed by [userID] to **{new_prefix}** in server {message.guild}"
            else:
                output = f"Prefix changed by [userID] to **{new_prefix}** in server {message.guild} - #{message.channel}"
            return output

    def check_prefix(self, message):
        prefix = None
        if prefix:
            output = f'Current prefix for this channel is `{prefix}`'
        else:
            output = 'There is no custom prefix set for this channel.'
        return output

    def extract_prefix(self, message):
        # command of form 'prefix {new_prefix}'
        text = message.content
        prefix = re.search(r'prefix(?: server)? (\S+)', text)
        if prefix:
            prefix = prefix.group(1)
        return prefix, ' server ' in message.content

    def set_splat(self, message):
        """Allows user to set game type for flavour text."""

        if "check" in message.content.lower():
            return self.check_splat(message)

        else:
            new_splat = self.find_splat(message.content.lower())
            if new_splat:
                return f'Flavour for [userID] changed to {new_splat} in server {message.guild} - #{message.channel}'
            else:
                return 'Unsupported splat selected. Only mage supported at this time.'

    def check_splat(self, message):
        splat = 'default'
        if splat:
            return f"Splat for [userID] is currently set to {splat} in server {message.guild} - #{message.channel}"
        else:
            return f"Splat for [userID] is currently not set in server {str(message.guild)} - {str(message.channel)}"

    def find_splat(self, message):
        for splat in SPLATS:
            if splat in message:
                return splat

    def set_flavour(self, message):
        """Allows user to set existence of flavour text."""
        setting = message.content.lower()
        if 'off' in setting:
            return f"Flavour turned off in server {str(message.guild)} - {str(message.channel)}"

        elif 'on' in setting:
            return f"Flavour turned on in server {str(message.guild)} - {str(message.channel)}"

        elif 'check' in setting:
            return self.check_flavour(message)

    def check_flavour(self, message):
        flavour, _ = False
        if flavour:
            return f"Flavour turned on in server {str(message.guild)} - {str(message.channel)}"
        else:
            return f"Flavour turned off in server {str(message.guild)} - {str(message.channel)}"

    def delete_content(self, message):
        if "user" in message.content:
            scope = 'user'
            output = f"Details for [userID] removed from {str(message.guild)} - {str(message.channel)}"

        elif "channel" in message.content:
            scope = 'channel'
            output = f"All details for channel **{str(message.channel)}** removed from **{str(message.guild)}** by [userID]"

        elif "server" in message.content:
            scope = 'server'
            output = f"All details for all channels removed from **{str(message.guild)}** by [userID]"

        else:
            return

        return output

    def errorText(self, message, error):
        content = f'''Time: {datetime.datetime.now()}
Message: {message.clean_content}
Server: {message.guild}
Channel: {message.channel}
Author: {message.author}
Error:
{error}'''
        print(content)

    async def pmCommands(self, message):
        command = message.content.lower()

        if 'type' in command:
            content = textResponses.typetext

        elif 'flavourhelp' in command:
            content = textResponses.flavText

        elif 'help' in command:
            content = textResponses.helptext

        elif 'info' in command:
            content = textResponses.aboutText

        elif 'prefix' in command:
            content = textResponses.prefixHelp

        else:
            content = "Write 'help' for help, 'info' for bot info, 'type' for list of roll types"

        await self.send(content, message)


def runner(token, me):
    """Helper function to run. Handles connection reset errors by automatically running again."""
    bot = None
    while True:
        try:
            bot = DicecordBot(token, me)
            bot.startBot()
            bot.client.run(bot.token)
        except:
            tb = traceback.format_exc()
            print(f'Potential disconnect\n\n{tb}')
            if bot:
                bot.loop.close()
            checkConnection()
        if bot:
            bot.loop.close()


def checkConnection(host='8.8.8.8', port=53, timeout=53):
    # Try to connect to google
    while True:
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            break
        except:
            print(f"No Connection still at {datetime.datetime.now()}")
            time.sleep(300)
    print("Reconnected")


if __name__ == '__main__':
    runner(token, saver)
