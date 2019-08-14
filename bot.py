import logging
import os
import socket
from functools import wraps
from typing import Callable, Dict, Iterable, List, Tuple

import paramiko
from telegram import Bot, Update
from telegram.ext import CommandHandler, Filters, MessageHandler, Updater
from tld import get_tld


TOKEN = os.environ['TOKEN']
MIKROTIK_ADDR = os.environ['MIKROTIK_ADDR']
MIKROTIK_USER = os.environ['MIKROTIK_USER']
MIKROTIK_PORT = int(os.environ['MIKROTIK_PORT'])
IP_LIST_NAME = os.environ['IP_LIST_NAME']
LIST_OF_USERS = list(map(int, os.environ['LIST_OF_USERS'].split(',')))


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
LOGGER = logging.getLogger()

HELP_STRING = """
    Commands:
        /unblock domain1 [ url2...] -- Add ip of domain or url to ip-list for static routing to vpn tunnel
        /help -- Get this message
"""


class Host:
    url: str
    ips: List[str]
    hostname: str

    def __init__(self, url: str) -> None:
        self.url = url
        self.fill_hostname()
        self.fill_ips()

    def fill_hostname(self) -> None:
        res = get_tld(self.url, as_object=True, fix_protocol=True)
        self.hostname = res.parsed_url.netloc

    def fill_ips(self) -> None:
        _, _, self.ips = socket.gethostbyname_ex(self.hostname)

    def __str__(self) -> str:
        return "{0}:{1}".format(self.hostname, self.ips)


class Mikrotik:
    addr: str = MIKROTIK_ADDR
    user: str = MIKROTIK_USER
    port: int = MIKROTIK_PORT

    def __init__(self) -> None:
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(self.addr, self.port, self.user)

    def exec_command(self, cmd: str) -> Tuple[int, str, str]:
        LOGGER.info("Executing on Mikrotik: %s", cmd)
        _, stdout, stderr = self.client.exec_command(cmd)
        exit_code = stdout.channel.recv_exit_status()
        stdout, stderr = stdout.read().decode(), stderr.read().decode()
        LOGGER.info("exit_code: %d, stdout: %s; stderr: %s",
                    exit_code, stdout, stderr)
        return exit_code, stdout, stderr

    def add_unblock_rule(self, host: Host) -> Dict[str, str]:
        LOGGER.info("Adding host %s to the unblock list", host)
        responses = dict()
        cmd_template = "/ip firewall address-list add address={0} comment={1} list={2}"
        for ip in host.ips:
            cmd = cmd_template.format(ip, host.hostname, IP_LIST_NAME)
            exit_code, stdout, stderr = self.exec_command(cmd)
            is_error = stdout + stderr != "" or exit_code != 0
            if is_error:
                err_messge = "Ip %s for host %s unblock failed. exit_code: %d, stdout: %s; stderr: %s" % (
                    ip, host.hostname, exit_code, stdout, stderr)
                LOGGER.error(err_messge)
                responses[ip] = "Unblock failed: {0}".format(stdout + stderr)
            else:
                err_messge = "Ip %s for host %s successfully unblocked" % (
                    ip, host.hostname)
                responses[ip] = "Unblocked!"
        return responses


M = Mikrotik()


def unblock_hosts(hosts: Iterable[str]) -> str:
    responses = dict()
    for h in hosts:
        responses[h] = unblock_host(h)
    return "\n".join("{0}: {1}".format(k, v) for k, v in responses.items())


def unblock_host(host: str) -> str:
    message = ""
    try:
        host_ = Host(host)
    except Exception as ex:
        message = "Fail to fill host structure from url %s: %s" % (host, ex)
        LOGGER.error(message)
        return message
    ip_responses = M.add_unblock_rule(host_)
    message = "\n".join("{0}: {1}".format(k, v)
                        for k, v in ip_responses.items())
    return message


def restricted(func: Callable) -> Callable:
    @wraps(func)
    def wrapped(bot: Bot, update: Update, *args, **kwargs):
        message = update.message
        user = message.from_user
        if user.id not in LIST_OF_USERS:
            LOGGER.warning("Unauthorized access denied for %d - %s: %s",
                           user.id, user.username, message.text)
            bot.send_message(chat_id=message.chat_id, text="Unauthorized")
            return
        return func(bot, update, *args, **kwargs)
    return wrapped


def start_handler(bot: Bot, update: Update) -> None:
    message = update.message
    user = message.from_user
    LOGGER.info("Get /start; user = %s; id = %d; chat_id = %d",
                user.username, user.id, message.chat_id)
    bot.send_message(chat_id=message.chat_id, text=HELP_STRING)


@restricted
def unblock_handler(bot: Bot, update: Update, args: Iterable[str]) -> None:
    message = update.message
    user = message.from_user
    LOGGER.info("Get /unblock; args = %s;user = %s; id = %d; chat_id = %d",
                args, user.username, user.id, message.chat_id)
    ret = unblock_hosts(args)
    bot.send_message(chat_id=message.chat_id, text=ret)


def unknown_handler(bot: Bot, update: Update) -> None:
    message = update.message
    user = message.from_user
    LOGGER.warning("Get unknown command %s; user = %s; id = %d; chat_id = %d",
                   message.text, user.username, user.id, message.chat_id)
    bot.send_message(chat_id=update.message.chat_id,
                     text="Sorry, I didn't understand that command.\n" + HELP_STRING)


start_handler_ = CommandHandler('start', start_handler)
help_handler_ = CommandHandler('help', start_handler)
unblock_handler_ = CommandHandler('unblock', unblock_handler, pass_args=True)
unknown_handler_ = MessageHandler(Filters.all, unknown_handler)

updater = Updater(token=TOKEN)
dispatcher = updater.dispatcher

dispatcher.add_handler(start_handler_)
dispatcher.add_handler(help_handler_)
dispatcher.add_handler(unblock_handler_)
dispatcher.add_handler(unknown_handler_)


updater.start_polling()
