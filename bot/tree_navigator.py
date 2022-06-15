#############################################################################################################################
#                                                                                                                           #
#  This file has been modified since it's previous version on https://github.com/johanmodin/poe-timeless-jewel-multitool    #
#  All changes since that version are covered by the CC BY 4.0 license                                                      #
#  I am not a lawyer, this notice is made in good faith to satisfy 4 (b) of the prior Apache License Version 2.0            #
#                                                                                                                           #
#############################################################################################################################


import logging
import cv2
import numpy as np
import pytesseract
import os
import time
import json
import re

from PIL import Image

from multiprocessing import Pool

#coordinates: 
#absolute tree coordinates, which match the json perfectly. these are prefixed by tree_ (origin center of scion)
#screen coordinates, which describe where on the screen things are
#to convert from tree coordinates to 1080p screen coordinates, multiply by 1080/10000.
#to convert from tree coordinates to 1440p screen coordinates, multiply by 1440/10000.
#done refactoring. Only things that involve moving the mouse and screenshots should be in screen coords, everything else is in tree coords


from .input_handler import InputHandler
from .grabscreen import grab_screen
from .utils import get_config

# This is a position of the inventory as fraction of the resolution
OWN_INVENTORY_ORIGIN = (0.6769531, 0.567361)


# This is the limit on where the center of the screen can be in the passive tree
# We use it to figure out where the screen is (at the begining)
TREE_BOUND_Y = [-9300,9250]
TREE_BOUND_X = [-5525,5525]

#pull node information from the processed tree
f=open("data/name_dict.json", 'r')
name_dict=json.load(f)
f.close()
f=open("data/node_coords.json", 'r')
node_coords=json.load(f)
f.close()
f=open("data/neighbor_nodes.json", 'r')
neighbor_nodes=json.load(f)
f.close()
f=open("data/node_types.json", 'r')
node_types=json.load(f)
f.close()

SOCKET_IDS = [6230, 48768 , 31683 , 
28475, 33631 , 36634 , 41263 , 33989 , 34483 , 
54127, 2491 , 26725 , 55190 , 26196 , 7960 , 61419 , 21984 , 61834 , 32763 , 60735 , 46882
]

SOCKET_TYPE_DICT = {6230 : "normal", 48768 : "normal", 31683 : "normal",
28475 : "normal", 33631 : "normal", 36634 : "normal", 41263 : "normal", 33989 : "normal", 34483 : "normal", 
54127 : "normal", 26725 : "normal", 26196 : "normal", 61419 : "normal", 61834 : "normal", 60735 : "normal", 
2491 : "cluster", 55190 : "cluster", 7960 : "cluster", 21984 : "cluster", 32763 : "cluster", 46882 : "cluster",}

JEWEL_PROCESS_DICT = { 
"Glorious Vanity": {"notable":["name","mods",2], "regular":["name","mods",1]}, 
"Lethal Pride": {"notable":["mods",1]}, 
"Brutal Restraint": {"notable":["mods",1]}, 
"Elegant Hubris": {"notable":["name"]}, 
"Militant Faith": {"notable":["name"]},
}

IMAGE_FOLDER = "data/images/"

OUTPUT_FOLDER = "data/results/"

# We're using template matching and some of the templates are defined here
# with matching thresholds (scores) and sizes per resolution
TEMPLATES = {
    "FreeSpace.png": {
        "1440p_size": (41, 41),
        "1440p_threshold": 0.98,
        "1080p_size": (30, 30),
        "1080p_threshold": 0.98,
    },
    "1080p_cluster_target.png": {
        "1080p_size": (29, 29),
        "1080p_threshold": 0.98,
    },
    "1080p_normal_target.png": {
        "1080p_size": (29, 29),
        "1080p_threshold": 0.98,
    },
    "1440p_cluster_target.png": {
        "1440p_size": (40, 40),
        "1440p_threshold": 0.98,
    },
    "1440p_normal_target.png": {
        "1440p_size": (40, 40),
        "1440p_threshold": 0.98,
    },
}

# Defines the position of the text box which is cropped out and OCR'd per node
TXT_BOX = {"1080p_" : {"x": 32, "y": 0, "w": 900, "h": 320},
"1440p_" : {"x": 40, "y": 0, "w": 1130, "h": 400}}


class NodeData:
    id = 0
    name = []
    mods = []
    name_text = []
    mod_text = []
    img = np.array([0])
    

class TreeNavigator:
    def __init__(self, resolution, halt_value):
        self.resolution = resolution
        self.input_handler = InputHandler(self.resolution)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(message)s",
            datefmt="[%H:%M:%S %d-%m-%Y]",
        )
        self.log = logging.getLogger("tree_nav")
        self.t2s_scale = self.resolution[1]/10000.0
        self.config = get_config("tree_nav")
        self.modChars = re.compile("[^a-zA-Z\+0\.123456789% \-',]")
        self.camera_position = (0,0)
        self.px_multiplier = 1
        self.resolution_prefix = str(self.resolution[1]) + "p_"
        self.templates_and_masks = self.load_templates()
        f=open("data/passivesMods.json")
        self.passivesModsData = json.load(f)
        f.close()
        self.halt = halt_value
        self.first_run = True

    def _run(self):
        return not bool(self.halt.value)

    def eval_jewel(self, item_location):

        self.item_name, self.item_desc = self._setup(item_location, copy=True)
        if self.item_name == "":
            return self.item_name, self.item_desc

        # Find the jewel number
        desc_words=self.item_desc.split(" ")
        jewel_number=0
        for word in desc_words:
            if not word.isalpha():
                jewel_number=int(word)
        #check if the jewel has already been evaluated
        if os.path.exists(os.path.join(OUTPUT_FOLDER, str(self.item_name),str(jewel_number) )):
            #put the jewel back
            self._setup(item_location)
            return self.item_name, self.item_desc

        pool = Pool(self.config["ocr_threads"])
        jobs = {}
        
        self.modNames = { "regular" : list(self.passivesModsData[self.item_name]["regular"].keys()), 
                          "notable" : list(self.passivesModsData[self.item_name]["notable"].keys())}

        # if this is the first time this instance has run, we need to move to a known position
        if self.first_run:
        # move all the way bottom right, establish where we are.
            self._locate_screen(3)
            self.first_run = False

        # analyse nodes
        for socket_id in SOCKET_IDS:
            self._move_screen_to_node(socket_id)
            socket_nodes = self._analyze_nodes(socket_id)
            jobs[socket_id] = pool.map_async(OCR.node_to_strings, socket_nodes)
            if not self._run():
                return None, None, None

        # collect ocr'd nodes
        self._setup(item_location)
        self.log.info("Waiting for last OCR to finish")
        item_stats = [
            {
                "socket_id": socket_id,
                "socket_nodes":  jobs[socket_id].get(timeout=300),
            }
            for socket_id in jobs
        ]
        jobs2 = {}

        node_dict={}
        # first pass at interpreting the ocr
        for item_dict in item_stats:
            rerun_nodes=[]
            node_dict[item_dict["socket_id"]]={}
            for a_node in item_dict["socket_nodes"]:
                if "name" in JEWEL_PROCESS_DICT[self.item_name][node_types[str(a_node.id)]]:
                    self._filter_ocr_name(a_node)
                else:
                    a_node.name=["Example Name"]
            for a_node in item_dict["socket_nodes"]:
                if "mods" in JEWEL_PROCESS_DICT[self.item_name][node_types[str(a_node.id)]]:
                    self._filter_ocr_mods(a_node)

            for a_node in item_dict["socket_nodes"]:
#make sure the form matches the desired form based on jewel
#if we wanted a name but didn't get one, try again.
                if "name" in JEWEL_PROCESS_DICT[self.item_name][node_types[str(a_node.id)]] and len(a_node.name) == 0:
                    rerun_nodes.append(a_node)
                    continue
#if we wanted one mod and didn't get it
                if "mods" in JEWEL_PROCESS_DICT[self.item_name][node_types[str(a_node.id)]]:
                    if 1 in JEWEL_PROCESS_DICT[self.item_name][node_types[str(a_node.id)]] and len(a_node.mods) == 0:
                        rerun_nodes.append(a_node)
                        continue
#if we wanted at least two mods and didn't get them
                    if 2 in JEWEL_PROCESS_DICT[self.item_name][node_types[str(a_node.id)]] and len(a_node.mods) < 2:
                        rerun_nodes.append(a_node)
                        continue
# otherwise, add the node to the dictionary
                node_dict[item_dict["socket_id"]][a_node.id]={"name" : a_node.name[0], "mods" : a_node.mods}
            jobs2[item_dict["socket_id"]] = pool.map_async(OCR.node_to_strings2, rerun_nodes)
#            print(len(rerun_nodes), end = ' ')
#        print('')

        second_item_stats = [
            {
                "socket_id": socket_id,
                "socket_nodes":  jobs2[socket_id].get(timeout=300),
            }
            for socket_id in jobs2
        ]

        minor_save_prefix = os.path.join(OUTPUT_FOLDER, str(self.item_name))
        if not os.path.exists(minor_save_prefix):
            os.makedirs(minor_save_prefix)

        # second pass at interpreting the ocr, only the previous failures come through here
        for item_dict in second_item_stats:
            for a_node in item_dict["socket_nodes"]:
                if "name" in JEWEL_PROCESS_DICT[self.item_name][node_types[str(a_node.id)]]:
                    self._filter_ocr_name(a_node)
                else:
                    a_node.name=["Example Name"]
            for a_node in item_dict["socket_nodes"]:
                if "mods" in JEWEL_PROCESS_DICT[self.item_name][node_types[str(a_node.id)]]:
                    self._filter_ocr_mods(a_node)

            save_path = os.path.join(minor_save_prefix, str(jewel_number),str(item_dict["socket_id"])+".json")
            save_prefix = os.path.join(minor_save_prefix, str(jewel_number))
            if not os.path.exists(save_prefix):
                os.makedirs(save_prefix)


            for a_node in item_dict["socket_nodes"]:
                img_save_location = os.path.join(save_prefix, str(item_dict["socket_id"]) +"_"+ str(a_node.id)+".png")
#make sure the form matches the desired form based on jewel
#if we wanted a name but didn't get one, try again.
                if "name" in JEWEL_PROCESS_DICT[self.item_name][node_types[str(a_node.id)]] and len(a_node.name) == 0:
                    img= Image.fromarray(a_node.img)
                    img.save(img_save_location)
                    print("failed to save. name:", a_node.name_text)
                    print("mods:", a_node.mod_text)
                    continue
#if we wanted one mod and didn't get it
                if "mods" in JEWEL_PROCESS_DICT[self.item_name][node_types[str(a_node.id)]]:
                    if 1 in JEWEL_PROCESS_DICT[self.item_name][node_types[str(a_node.id)]] and len(a_node.mods) == 0:
                        img= Image.fromarray(a_node.img)
                        img.save(img_save_location)
                        print("failed to save. name:", a_node.name_text)
                        print("mods:", a_node.mod_text)
                        continue
#if we wanted at least two mods and didn't get them
                    if 2 in JEWEL_PROCESS_DICT[self.item_name][node_types[str(a_node.id)]] and len(a_node.mods) < 2:
                        img= Image.fromarray(a_node.img)
                        img.save(img_save_location)
                        print("failed to save. name:", a_node.name_text)
                        print("mods:", a_node.mod_text)
                        continue

                # finally write this to dictionary if it worked.
                node_dict[item_dict["socket_id"]][a_node.id]={"name" : a_node.name[0], "mods" : a_node.mods}

            if not os.path.exists(save_prefix):
                os.makedirs(save_prefix)

            f=open(save_path, 'w')
            json.dump(node_dict[item_dict["socket_id"]],f)
            f.close()

############################################

        pool.close()
        pool.join()
        return self.item_name, self.item_desc


    def _move_screen_to_node(self, node_id):

        self.log.debug("Moving to node %s" % node_id)

        self._move_to_tree_pos_using_spaces(node_coords[str(node_id)])

        return True



    def _move_to_tree_pos_using_spaces(self, tree_desired_pos, max_position_error=40):

        target = (tree_desired_pos[0],tree_desired_pos[1])
        #we only check the x bound, since all nodes are in bounds in the y direction
        if target[0]<TREE_BOUND_X[0]+400:
            target= (TREE_BOUND_X[0]+400, target[1])
        if target[0]>TREE_BOUND_X[1]-400:
            target= (TREE_BOUND_X[1]-400, target[1])

        dx = target[0] - self.camera_position[0]
        dy = target[1] - self.camera_position[1]
        self.current_error=(0,0)

        while (abs(dx) + abs(dy)) > max_position_error:
            # Choose quadrant to find spaces in based on dx, dy
            right, bottom = dx >= 0, dy >= 0
            if right and not bottom:
                quadrant = 0
            elif not right and not bottom:
                quadrant = 1
            elif not right and bottom:
                quadrant = 2
            elif right and bottom:
                quadrant = 3

            # Find empty spaces that we can drag from
            spaces = self._find_empty_space(quadrant)
            if spaces is None:
                raise ValueError("Could not find an empty space, quitting.")

            # Choose an empty space for random drag
            chosen_space = spaces

            # How far to drag the window to end up in the optimal place
            screen_move_x, screen_move_y = [int(dx*self.t2s_scale), int(dy*self.t2s_scale)]

            # Calculate where our drag should end up to perform the move
            drag_x = int(chosen_space[0]) - screen_move_x
            drag_y = int(chosen_space[1]) - screen_move_y

            # We should only drag within the screen's resolution
            # Additionally, we use 100px margin to not trigger tree scroll
            drag_x = np.clip(drag_x, 100, self.resolution[0] - 100)
            drag_y = np.clip(drag_y, 100, self.resolution[1] - 100)

            # Drag
            self.input_handler.click(
                *chosen_space, *chosen_space, button=None, raw=True, speed_factor=1
            )
            self.input_handler.drag(drag_x, drag_y, speed_factor=1)
            self.input_handler.rnd_sleep(min=200, mean=300, sigma=100)

            # Calculate how far we've actually moved
            effective_move_x = chosen_space[0] - drag_x
            effective_move_y = chosen_space[1] - drag_y
            #self.log.info("I think I've moved %d %d",effective_move_x,effective_move_y)

            # Update our internal tree position
            self.camera_position = [self.camera_position[0]+effective_move_x/self.t2s_scale, self.camera_position[1]+effective_move_y/self.t2s_scale]

            # Update how much we have left to move
            dx = target[0] - self.camera_position[0]
            dy = target[1] - self.camera_position[1]


    def _locate_screen(self, quadrent):
        #move all the way to one direction, and therefore know where you are (default is 3: bottom right corner)
        self.log.info("Moving to corner %d" % quadrent)
        q_signs = {0: (1,-1), 1: (-1,-1) , 2: (-1,1) , 3: (1,1)}
        q_indicator = {0: (0,1), 1: (1,1) , 2: (1,0) , 3: (0,0)}
        for _ in range(3):
            # Find empty spaces that we can drag from
            spaces = self._find_empty_space(quadrent)
            if spaces is None:
                raise ValueError("Could not find an empty space, quitting.")

            # Choose an empty space?
            chosen_space = spaces

            # An arbitrary position in the opposite corner region
            drag_location = (self.resolution[0]*q_indicator[quadrent][0]+200*(q_signs[quadrent][0]),
                             self.resolution[1]*q_indicator[quadrent][1]+200*(q_signs[quadrent][1]),)

            # Drag
            self.input_handler.click(
                *chosen_space, *chosen_space, button=None, raw=True, speed_factor=1
            )
            self.input_handler.drag(drag_location[0], drag_location[1], speed_factor=1)
            self.input_handler.rnd_sleep(min=200, mean=300, sigma=100)

        # Having gotten all the way across the tree, we set our location to the bounded location
        # camera_position always refers to the position in _tree coordinates_ where the center of the screen is.
        self.camera_position=(TREE_BOUND_X[q_signs[quadrent][0]+q_indicator[quadrent][0]],
                              TREE_BOUND_Y[q_signs[quadrent][1]+q_indicator[quadrent][1]])


    def _find_empty_space(self, quadrant):
        # Finds empty spaces that can be used to drag the screen
        # Used to recenter the screen
        # The quadrant argument is an int in [0, 1, 2, 3], corresponding to
        # [top-right, top-left, bottom-left, bottom-right]
        quadrant_translation = {0: [0.5, 0], 1: [0, 0], 2: [0, 0.5], 3: [0.5, 0.5]}
        fractional_lt = quadrant_translation[quadrant]
        lt = [
            int(fractional_lt[0] * self.resolution[0]),
            int(fractional_lt[1] * self.resolution[1]),
        ]
        rb = [int(lt[0] + self.resolution[0] / 2),
              int(lt[1] + self.resolution[1] / 2)]
        searched_area = grab_screen(tuple(lt + rb))
        searched_area = cv2.cvtColor(searched_area, cv2.COLOR_BGR2GRAY)

        locations = np.zeros_like(searched_area)

        centered_coordinates = self._match_image(searched_area, "FreeSpace.png")
        locations[tuple(centered_coordinates)] = 1

        rel_space_pos_yx = np.argwhere(locations == 1)
        rel_space_pos = rel_space_pos_yx.T[::-1].T
        if len(rel_space_pos) == 0:
            self.log.warning("Could not find any free spaces in tree!")
            return None
        screen_space_pos = rel_space_pos + lt

        # remove positions that are close to edges as these trigger scroll or are coverd by UI
        screen_space_pos = screen_space_pos[(screen_space_pos[:, 0] > 200) &
                            (screen_space_pos[:, 1] > 200) &
                            (screen_space_pos[:, 0] < self.resolution[0] - 200) &
                            (screen_space_pos[:, 1] < self.resolution[1] - 200)]
        # find the best choice based on quadrant
        quadrant_directions = {0 : [1,-1], 1: [-1,-1], 2: [-1,1], 3: [1,1]}
        best_value=-1000000
        saved_coords=[0,0]
        for coord in screen_space_pos:
            try_value=quadrant_directions[quadrant][0]*coord[0] + quadrant_directions[quadrant][1]*coord[1]
            if try_value>best_value:
                best_value=try_value
                saved_coords=coord
        return saved_coords



    def _analyze_nodes(self, socket_id, repeated=False):
        self.log.info("Analyzing nodes for socket id %s" % socket_id)
        node_ids = neighbor_nodes[str(socket_id)]
        node_location=node_coords[str(socket_id)]

	#we should be close to the node, we take a screenshot around where we think the node is to get it exactly right, and update our camera position
        thought_offset = [node_location[0] - self.camera_position[0], node_location[1] - self.camera_position[1]]
        #convert this offset to pixels
        screen_offset = [int(thought_offset[0]*self.t2s_scale), int(thought_offset[1]*self.t2s_scale)]
        snapshot_radius = 30
        #larger means less mistakes and slower searching
        lt=[int(self.resolution[0]/2)+screen_offset[0]-snapshot_radius, int(self.resolution[1]/2)+screen_offset[1]-snapshot_radius]
        rb=[int(self.resolution[0]/2)+screen_offset[0]+snapshot_radius, int(self.resolution[1]/2)+screen_offset[1]+snapshot_radius]
        searched_area = grab_screen(tuple(lt + rb))
        searched_area = cv2.cvtColor(searched_area, cv2.COLOR_BGR2GRAY)

	#match it to the saved image of that socket, just to get offset
        offset = self._find_socket_offset(searched_area,socket_id)
        if len(offset) == 0:
            if repeated==True:
                self.log.warning("Could not find the socket! Giving up.")
                return []
            self.log.warning("Could not find the socket! Trying again.")
            self._locate_screen(3)
            self._move_screen_to_node(socket_id)
            return self._analyze_nodes(socket_id,repeated=True)

        #put in the jewel, scan all the nodes
        self._click_socket(node_location,offset)
        nodes =[]
        for node_id in node_ids:
#if this jewel doesn't modify this node (in an upredictable way) we don't need to check it.
            if node_types[str(node_id)] not in JEWEL_PROCESS_DICT[self.item_name].keys():
                continue
            if not self._run():
                return
            node_stats = self._get_node_data(node_id,offset)

            node = NodeData()
            node.id=node_id
            node.img=node_stats

            nodes.append(node)
        self._click_socket(node_location,offset, insert=False)

        #fix  the camera position to account for the actual offset
        self.camera_position[0] -= offset[0]/self.t2s_scale
        self.camera_position[1] -= offset[1]/self.t2s_scale
        return nodes


    def _click_socket(self, node_location, offset, insert=True):
        self.log.debug("Clicking socket")
        thought_offset = [node_location[0] - self.camera_position[0], node_location[1] - self.camera_position[1]]
        xy = [int(thought_offset[0]*self.t2s_scale), int(thought_offset[1]*self.t2s_scale)]
        lt = [int(self.resolution[0]/2)+xy[0]+offset[0] - 1, int(self.resolution[1]/2)+xy[1]+offset[1] - 1]
        rb = [int(self.resolution[0]/2)+xy[0]+offset[0] + 1, int(self.resolution[1]/2)+xy[1]+offset[1] + 1]
        if insert:
            self.input_handler.click(*lt, *rb, button="left", raw=True)
        else:
            self.input_handler.click(*lt, *rb, button="right", raw=True)
        self.input_handler.rnd_sleep(min=200, mean=300)

    def _find_socket_offset(self, screen, node_id):
        #look up the filter and the target for the node id
        socket_type=SOCKET_TYPE_DICT[node_id]
        template_name=self.resolution_prefix+socket_type+"_target.png"
        template = self.templates_and_masks[template_name]["image"]
        mask = self.templates_and_masks[template_name]["mask"]
        bw = cv2.inRange(screen, 150, 255)
        res = cv2.matchTemplate(bw, template, cv2.TM_CCORR_NORMED, mask=mask)
        local_shift_array = np.argwhere(np.logical_and(res <1.01,res>0.95))
        if len(local_shift_array)==0:
            return []
        local_shift=local_shift_array[0]

        #adjust for size of screenshot and template
        size = TEMPLATES[template_name][self.resolution_prefix+"size"]
        snap_size = screen.shape
        center=[int(snap_size[0]/2),int(snap_size[1]/2)]
        half_size = [int(size[0]/2),int(size[1]/2)]

        #local shift was transposed, so the order is wrong
        offset=[local_shift[1]+half_size[0]-center[0],local_shift[0]+half_size[1]-center[1]]
        return offset

    def _contains_11(self, img):
        template_name = self.resolution_prefix + "11_target.png"
        template = self.templates_and_masks[template_name]["image"]
        mask = self.templates_and_masks[template_name]["mask"]
        bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        res = cv2.matchTemplate(bgr, template, cv2.TM_CCORR_NORMED, mask=mask)
        cleaned_res = cv2.inRange(res, 0.98, 1.01)
        return (cleaned_res.sum() > 0.9)

    def _match_image(self, screen, template_name):
        template = self.templates_and_masks[template_name]["image"]
        mask = self.templates_and_masks[template_name]["mask"]
        res = cv2.matchTemplate(screen, template, cv2.TM_CCORR_NORMED, mask=mask)
        coordinates = np.where(
            res >= TEMPLATES[template_name][self.resolution_prefix + "threshold"]
        )
        #self.log.info(coordinates)
        icon_size = (
            int(TEMPLATES[template_name][self.resolution_prefix + "size"][0]),
            int(TEMPLATES[template_name][self.resolution_prefix + "size"][1]),
        )
        icon_center_offset = [int(icon_size[0] / 2), int(icon_size[1] / 2)]
        centered_coordinates = [
            coordinates[0] + icon_center_offset[0],
            coordinates[1] + icon_center_offset[1],
        ]

        return centered_coordinates


    def _get_node_data(self, node_id,offset):
        self.log.debug("Getting node stats for node %s" % node_id)
        thought_offset = [node_coords[str(node_id)][0] - self.camera_position[0], node_coords[str(node_id)][1] - self.camera_position[1]]
        location = [int(self.resolution[0]/2)+int(thought_offset[0]*self.t2s_scale)+offset[0], int(self.resolution[1]/2)+int(thought_offset[1]*self.t2s_scale)+offset[1]]
        lt = [
            location[0] - 1,
            location[1] - 1,
        ]
        rb = [
            location[0] + 1,
            location[1] + 1,
        ]
        self.input_handler.click(
            *lt,
            *rb,
            button=None,
            raw=True,
            speed_factor=self.config["node_search_speed_factor"]
        )
        textbox_lt = [location[0] + TXT_BOX[self.resolution_prefix]["x"], location[1] + TXT_BOX[self.resolution_prefix]["y"]]
        textbox_rb = [textbox_lt[0] + int(TXT_BOX[self.resolution_prefix]["w"]),
                      textbox_lt[1] + int(TXT_BOX[self.resolution_prefix]["h"]),
        ]
        # adjust the screengrab if it were to run off the screen
        rb_diff=[min([self.resolution[0]-textbox_rb[0],0]),min([self.resolution[1]-textbox_rb[1],0])]
        textbox_lt = [textbox_lt[0]+rb_diff[0],textbox_lt[1]+rb_diff[1]]
        textbox_rb = [textbox_rb[0]+rb_diff[0],textbox_rb[1]+rb_diff[1]]

        jewel_area_bgr = grab_screen(tuple(np.concatenate([textbox_lt, textbox_rb])))
        bgr = cv2.cvtColor(jewel_area_bgr, cv2.COLOR_BGRA2BGR)
### double check that we _actually_ got the node
### look for the exact mod color: 135, 135, 254
### the screengrab is bgr though, so look for 254, 135, 135
### need at least 400 to have a good mod
        pix_count = (bgr == (254,135,135)).sum()
        if pix_count < 400:
            print("Didn't find the node!!!", node_id, "scanning to try and find it.")
            self.log.debug("Failed to find node %s" % node_id)
            # try again, this time scan a 5x5 pixel area until you find it.
            for dx,dy in [(x,y) for x in range(5) for y in range(5)]:
                lt = [
                    location[0] - 2 + dx,
                    location[1] - 2 + dy,
                ]
                rb = [
                    location[0] - 2 + dx,
                    location[1] - 2 + dy,
                ]
                self.input_handler.click(
                    *lt,
                    *rb,
                    button=None,
                    raw=True,
                    speed_factor=self.config["node_search_speed_factor"]
                )

                jewel_area_bgr = grab_screen(tuple(np.concatenate([textbox_lt, textbox_rb])))
                bgr = cv2.cvtColor(jewel_area_bgr, cv2.COLOR_BGRA2BGR)
                pix_count = (bgr == (254,135,135)).sum()
                if pix_count > 400:
                    print("found it with offset", dx, dy)
                    break
                    

        return jewel_area_bgr


###the input to below in "nodes_lines"
###pool.map_async(OCR.node_to_strings, socket_nodes):
###        return {"id": node["id"], "name" : [], "mods": [], "name_text": name_text, "mod_text": mod_text, "img": img}


    def _filter_ocr_name(self, node):
        node_type = node_types[str(node.id)]
        node.name=[]
        local_valid_names=self.modNames[node_type]+[name_dict[str(node.id)]]
        for line in node.name_text:
            filtered_name = self._filter_nonalpha(line)
            if len(filtered_name)<4:
                continue
            if filtered_name in local_valid_names:
                node.name.append(filtered_name)
            if filtered_name[2:] in local_valid_names:
                node.name.append(filtered_name[2:])
            if filtered_name[:-2] in local_valid_names:
                node.name.append(filtered_name[:-2])

        if len(node.name)!=1:
            #found the wrong number of names, give up on processing
            node.name=[]

    def _filter_ocr_mods(self, node):
        if len(node.name)==0:
            return
        node_type = node_types[str(node.id)]
        node.mods=[]
        for line in node.mod_text:
            filtered_line = self._filter_nonalpha(line)
            if len(filtered_line) < 4 or filtered_line == "Unallocated":
                continue
            if filtered_line in self.passivesModsData[self.item_name][node_type][node.name[0]]:
                node.mods.append(filtered_line)
            elif filtered_line[2:] in self.passivesModsData[self.item_name][node_type][node.name[0]]:
                node.mods.append(filtered_line[2:])
            elif filtered_line[:-2] in self.passivesModsData[self.item_name][node_type][node.name[0]]:
                node.mods.append(filtered_line[:-2])
            else:
                if self._contains_11(node.img):
                    if "1%" in filtered_line:
                        insert_location = filtered_line.find("1%")
                        fixed_filtered_line=filtered_line[:insert_location]+"11%"+filtered_line[insert_location+2:]
                        if fixed_filtered_line in self.passivesModsData[self.item_name][node_type][node.name[0]]:
                            node.mods.append(fixed_filtered_line)
                    elif "n%" in filtered_line:
                        insert_location = filtered_line.find("n%")
                        fixed_filtered_line=filtered_line[:insert_location]+"11%"+filtered_line[insert_location+2:]
                        if fixed_filtered_line in self.passivesModsData[self.item_name][node_type][node.name[0]]:
                            node.mods.append(fixed_filtered_line)



    def _setup(self, item_location, copy=False):
        item_desc = None
        item_name = None
        self.input_handler.click_hotkey("p")
        self.input_handler.rnd_sleep(min=150, mean=200, sigma=100)
        self.input_handler.click_hotkey("i")
        if copy:
            self.input_handler.rnd_sleep(min=150, mean=200, sigma=100)
            item = self.input_handler.inventory_copy(
                *item_location, OWN_INVENTORY_ORIGIN, speed_factor=2
            )
            #if we have an empty slot, don't fail
            if len(item.split("\n"))<3:
                item_desc = ""
                item_name = ""
            else:
                if "(implicit)" in item.split("\n")[10]:
                    if "(implicit)" in item.split("\n")[11]:
                        item_desc = item.split("\n")[13].strip()
                    else:
                        item_desc = item.split("\n")[12].strip()
                else:
                    item_desc = item.split("\n")[10].strip()
                item_name = item.split("\n")[2].strip()
        self.input_handler.rnd_sleep(min=150, mean=200, sigma=100)
        self.input_handler.inventory_click(*item_location, OWN_INVENTORY_ORIGIN)
        self.input_handler.rnd_sleep(min=150, mean=200, sigma=100)
        self.input_handler.click_hotkey("i")
        self.input_handler.rnd_sleep(min=150, mean=200, sigma=100)
        return item_name, item_desc

    def load_templates(self, threshold=128):
        templates_and_masks = {}
        for template_name in ["FreeSpace.png"]:
            template_path = os.path.join(IMAGE_FOLDER, template_name)
            img = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
            size = TEMPLATES[template_name][self.resolution_prefix + "size"]
            channels = cv2.split(img)
            mask = None
            if len(channels) > 3:
                mask = np.array(channels[3])
                mask[mask <= threshold] = 0
                mask[mask > threshold] = 255
                # mask = cv2.resize(mask, size)

            img = cv2.imread(template_path, 0)
            # img = cv2.resize(img, size)
            templates_and_masks[template_name] = {"image": img, "mask": mask}
        for type in ["cluster","normal"]:
            target_name = self.resolution_prefix + type + "_target.png"
            mask_name = self.resolution_prefix + type + "_filter.png"
            target_path = os.path.join(IMAGE_FOLDER, target_name)
            mask_path = os.path.join(IMAGE_FOLDER, mask_name)
            img = cv2.imread(target_path, 0)
            mask = cv2.imread(mask_path, 0)
            templates_and_masks[target_name] = {"image": img, "mask": mask}

        target_name = self.resolution_prefix + "11_target.png"
        mask_name = self.resolution_prefix + "11_filter.png"
        target_path = os.path.join(IMAGE_FOLDER, target_name)
        mask_path = os.path.join(IMAGE_FOLDER, mask_name)
        img = cv2.imread(target_path, 1)
        mask = cv2.imread(mask_path, 0)
        templates_and_masks[target_name] = {"image": img, "mask": mask}
            
        return templates_and_masks

    def _filter_nonalpha(self, value):
        small_filter = re.sub(self.modChars, "", value)
        if len(small_filter)==0:
            return small_filter
        while small_filter[-1]==' ':
            small_filter=small_filter[:-1]
            if len(small_filter)==0:
                return small_filter
        return small_filter


# Adapted from https://github.com/klayveR/python-poe-timeless-jewel
class OCR:
    @staticmethod
    def node_to_strings(node):
        name_filt, mod_filt = OCR.getFilteredImage(node.img)
        node.name_text = OCR.imageToStringArray(name_filt)
        node.mod_text = OCR.imageToStringArray(mod_filt)
        return node

    @staticmethod
    def node_to_strings2(node):
        name_filt, mod_filt = OCR.getFilteredImage(node.img,True)
        node.name_text = OCR.imageToStringArray(name_filt)
        node.mod_text = OCR.imageToStringArray(mod_filt)
        return node

    @staticmethod
    def getFilteredImage(src,second_try=False):

        srcH, srcW = src.shape[:2]
        # HSV to find the text
        rgb = cv2.cvtColor(src, cv2.COLOR_BGRA2BGR)
        hsv = cv2.cvtColor(rgb.copy(), cv2.COLOR_BGR2HSV)
        # the text is very specific colors, so pick those colors.
        # some sorcery to try and reduce the failures. The first try be very strict about what is included
        # the second try, include more junk, but filter the dust.
        # mask1 for blue affix text
        lower_blue = np.array([119, 100, 40])
        if second_try:
            upper_blue = np.array([126, 140, 255])
        else:
            upper_blue = np.array([121, 140, 255])
        # mask2 for yellow passive node name
        lower_yellow = np.array([16, 45, 130])
        upper_yellow = np.array([20, 55, 255])
        dark_mod = cv2.inRange(hsv, lower_blue, upper_blue)
        dark_name = cv2.inRange(hsv, lower_yellow, upper_yellow)
        mod = cv2.bitwise_not(dark_mod)
        name = cv2.bitwise_not(dark_name)
#because we're very close, we're going to clean up the visual "dirt"
#put a 5x5 box around any black pixel. If the sum of black pixels in this region is 4 or less, fill the box with white
        if second_try:
            for i in range(2,srcH-2):
                for j in range(2,srcW-2):
                    if mod[i,j] == 0:
                        zeros=0
                        for dx in range(5):
                            for dy in range(5):
                                if mod[i-2+dx,j-2+dy] == 0:
                                    zeros+=1
                        if zeros<5: 
                            for dx in range(5):
                                for dy in range(5):
                                    mod[i-2+dx,j-2+dy] = 255
                    if name[i,j] == 0:
                        zeros=0
                        for dx in range(5):
                            for dy in range(5):
                                if name[i-2+dx,j-2+dy] == 0:
                                    zeros+=1
                        if zeros<5: 
                            for dx in range(5):
                                for dy in range(5):
                                    name[i-2+dx,j-2+dy] = 255
            name = cv2.resize(name, (int(srcW * 2), int(srcH * 2)))
            mod = cv2.resize(mod, (int(srcW * 2), int(srcH * 2)))
        return name, mod

    @staticmethod
    def imageToStringArray(img):
        t = pytesseract.image_to_string(img, lang="eng", config="--oem 3 --psm 12 poe")
        t = t.replace("\n\n", "\n")
        lines = t.split("\n")
        return lines
