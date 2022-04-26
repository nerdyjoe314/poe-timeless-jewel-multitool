import logging
import time
import sys
import numpy as np
import re
import time
import keyboard

from multiprocessing import Value, Process
from queue import Queue
from bson.objectid import ObjectId
from datetime import datetime

from .trader import Trader
from .tree_navigator import TreeNavigator
from .utils import get_config, filter_mod
from .input_handler import InputHandler


class Bot:
    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(message)s",
            datefmt="[%H:%M:%S %d-%m-%Y]",
            filename="jewels.log",
            encoding='utf-8',
        )
        self.log = logging.getLogger("bot")
        self.config = get_config("bot")
        self.resolution = self.split_res(self.config["resolution"])
        self.nonalpha_re = re.compile("[^a-zA-Z]")

        self.trader = Trader(self.resolution, self.config["accept_trades"])
        self.input_handler = InputHandler(self.resolution)
        self.halt = Value("i", False)
        self.hotkey_killer = Process(
            target=hotkey_killer, args=(self.halt, self.config["exit_hotkey"])
        )
        self.hotkey_killer.daemon = True
        self.hotkey_killer.start()

    def loop(self):
#        self.log.info(
        print(
            "Quit the application by pressing %s" % self.config["exit_hotkey"]
        )
#        self.log.info(
        print(
            "Bot starts in %s seconds. Please tab into the game client."
            % self.config["initial_sleep"]
        )
        time.sleep(int(self.config["initial_sleep"]))
        while True:
            if self.config["accept_trades"]:
                empty = self.trader.verify_empty_inventory()
                if not empty:
                    self.trader.stash_items()
                username = self.trader.wait_for_trade()
                successfully_received = self.trader.get_items(username)
                if not successfully_received:
                    continue
            else:
                username = "nerdyjoe314"
            jewel_locations, descriptions = self.trader.get_jewel_locations()
            self.log.info("Got %s new jewels" % len(jewel_locations))
            long_break_at_idx = np.random.choice(
                60, self.config["breaks_per_full_inventory"]
            )
            for idx, jewel_location in enumerate(jewel_locations):
                if not self._run():
                    self.log.info("Exiting.")
                    return
                self.log.info(
                    "Analyzing jewel (%s/%s) with description: %s"
                    % (idx, len(jewel_locations), descriptions[idx])
                )
                if idx in long_break_at_idx:
                    self.log.info("Taking a break of around 5 minutes.")
                    self.input_handler.rnd_sleep(mean=300000, sigma=100000, min=120000)

                self.tree_nav = TreeNavigator(self.resolution, self.halt)
                analysis_time = datetime.utcnow()
                name, description, socket_instances = self.tree_nav.eval_jewel(
                    jewel_location
                )
                if socket_instances is None:
                    self.log.info("No socket instances returned. Exiting.")
                    return
                print(
                    "Jewel evaluation took %s seconds"
                    % (datetime.utcnow() - analysis_time).seconds
                )
                self.log.info(
                    "Jewel evaluation took %s seconds"
                    % (datetime.utcnow() - analysis_time).seconds
                )
                for socket in socket_instances:
                    socket["description"] = description
                    socket["name"] = name
                    socket["created"] = analysis_time
                    socket["reporter"] = username

#                self.store_items(socket_instances)

            if self.config["accept_trades"]:
                self.trader.return_items(username, jewel_locations)
            else:
                self.log.info("Inventory analysis complete!")
                break

#    def store_items(self, socket_instances):
#        # Add some filtered summed values for easier querying
#        for jewel_inst in socket_instances:
#            jewel_inst["summed_mods"] = {}
#            for node in jewel_inst["socket_nodes"]:
#                for mod in node["mods"]:
#                    filt_mod, value = filter_mod(mod, regex=self.nonalpha_re)
#                    if filt_mod in jewel_inst["summed_mods"]:
#                        jewel_inst["summed_mods"][filt_mod] += value
#                    else:
#                        jewel_inst["summed_mods"][filt_mod] = value

        #return result

    def split_res(self, resolution):
        resolution = [int(n) for n in resolution.split("x")]
        return resolution

    def _run(self):
        halt = bool(self.halt.value)
        if halt:
            self.hotkey_killer.join()
        return not halt


def hotkey_killer(halt_value, hotkey):
    while True:
        if keyboard.is_pressed(hotkey):
            halt_value.value += 1
            return
        time.sleep(0.1)
