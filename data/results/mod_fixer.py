from PIL import Image, ImageTk
import cv2
import tkinter
import json
import os

parent = ".."
mods = "passivesMods.json"
types = "node_types.json"

def str_to_int(in_string):
    newstring=""
    for i in in_string:
        if i in "1234567890":
            newstring=newstring+i
    return newstring

vaal_type_options = [
                "None",
                "X% increased Fire Damage",
                "X% increased Cold Damage",
                "X% increased Lightning Damage",
                "X% increased Physical Damage",
                "X% increased Chaos Damage",
                "Minions deal X% increased Damage",
                "X% increased Attack Damage",
                "X% increased Spell Damage",
                "X% increased Area Damage",
                "X% increased Projectile Damage",
                "X% increased Damage over Time",
                "X% increased Area of Effect",
                "X% increased Projectile Speed",
                "X% increased Critical Strike Chance",
                "+X% to Critical Strike Multiplier",
                "X% increased Attack Speed",
                "X% increased Cast Speed",
                "X% increased Movement Speed",
                "X% chance to Ignite",
                "X% chance to Freeze",
                "X% chance to Shock",
                "X% increased Skill Effect Duration",
                "X% increased maximum Life",
                "X% increased maximum Mana",
                "X% increased Mana Regeneration Rate",
                "X% increased Armour",
                "X% increased Evasion Rating",
                "X% increased maximum Energy Shield",
                "+X% Chance to Block Attack Damage",
                "X% Chance to Block Spell Damage",
                "X% chance to Avoid Elemental Ailments",
                "+X% chance to Suppress Spell Damage",
                "X% increased effect of Non-Curse Auras from your Skills",
                "X% increased Effect of your Curses",
                "+X% to Fire Resistance",
                "+X% to Cold Resistance",
                "+X% to Lightning Resistance",
                "+X% to Chaos Resistance",
]

class GlobalApplication(tkinter.Tk):
    def __init__(self):
        self.fixed_mods = []
        self.root = tkinter.Tk.__init__(self)
        self.name = tkinter.StringVar()
        self.mod1 = tkinter.StringVar()
        self.mod2 = tkinter.StringVar()
        self.mod3 = tkinter.StringVar()
        self.mod4 = tkinter.StringVar()
        self.name_options = ["Name"]
        self.mod1_options = ["Mod1"]
        self.mod2_options = ["Mod2"]
        self.mod3_options = ["Mod3"]
        self.mod4_options = ["Mod4"]
        self.name_menu = tkinter.OptionMenu( self, self.name, *self.name_options )
        self.mod1_menu = tkinter.OptionMenu( self, self.mod1, *self.mod1_options )
        self.mod2_menu = tkinter.OptionMenu( self, self.mod2, *self.mod2_options )
        self.mod3_menu = tkinter.OptionMenu( self, self.mod3, *self.mod3_options )
        self.mod4_menu = tkinter.OptionMenu( self, self.mod4, *self.mod4_options )
        self.mod1_val = tkinter.StringVar()
        self.mod2_val = tkinter.StringVar()
        self.mod3_val = tkinter.StringVar()
        self.mod4_val = tkinter.StringVar()
        self.mod1_val_menu = tkinter.Entry( self, textvariable=self.mod1_val )
        self.mod2_val_menu = tkinter.Entry( self, textvariable=self.mod2_val )
        self.mod3_val_menu = tkinter.Entry( self, textvariable=self.mod3_val )
        self.mod4_val_menu = tkinter.Entry( self, textvariable=self.mod4_val )
        self.name_update_button = tkinter.Button( self, text = "Confirm name" , command =  self.name_update )
#load things
        f=open(os.path.join(parent,mods), 'r')
        self.passiveMods=json.load(f)
        f.close()
        f=open(os.path.join(parent,types), 'r')
        self.node_types=json.load(f)
        f.close()

#find all the images
        self.image_list=[]
        here=os.curdir
        for folder in os.listdir(here):
            if os.path.isdir(folder):
                for im_name in os.listdir(folder):
                    if im_name[-4:] != '.png':
                        continue
                    src = cv2.imread(os.path.join(folder,im_name), 1)
                    img = Image.fromarray(src)
                    #nextim= ImageTk.PhotoImage(img)
                    self.image_list.append({"f" : folder, "n" : im_name, "i" : img })
        self.max_image=len(self.image_list)
        if self.max_image==0:
            print("No errors found, quitting!")
            self.close_app()
            return
        self.curr_image=0
        first_pos=self.image_list[self.curr_image]["n"].index("_")+1
        last_pos=self.image_list[self.curr_image]["n"].index(".")
        self.curr_type = self.node_types[ self.image_list[self.curr_image]["n"][first_pos:last_pos]  ]

#make a quit button
        self.quitButton = tkinter.Button(self, width=12, text='Quit', bg='tan',
                    command=self.close_app)
        self.quitButton.grid(row=0, column=0, padx=8, pady=8)

#make a prev button
        self.quitButton = tkinter.Button(self, width=12, text='Prev',
                    command=self.prev)
        self.quitButton.grid(row=0, column=1, padx=8, pady=8)

#make a next button
        self.quitButton = tkinter.Button(self, width=12, text='Next',
                    command=self.next)
        self.quitButton.grid(row=0, column=2, padx=8, pady=8)


        self.name_menu.grid(row=2, column=0, padx=3, pady=3)
        self.name_update_button.grid(row=3, column=0, padx=3, pady=3)

#make a confirm button
        self.confirmButton = tkinter.Button(self, width=12, text='Confirm Stats', bg='green',
                    command=self.confirm)

#build the analyzer
        self.update()


    def close_app(self):
#add all generated dictionary entries to their files
        for a in self.fixed_mods:
            this_dict=a[1]
            this_img=self.image_list[a[0]]
#self.image_list.append({"f" : folder, "n" : im_name, "i" : img })
            pos_under=this_img["n"].find("_")
            pos_pt=this_img["n"].find(".")
            node_number=this_img["n"][pos_under+1:pos_pt]
            json_name = this_img["n"][:pos_under]+".json"
            f=open(os.path.join(this_img["f"],json_name), 'r')
            old_dict=json.load(f)
            f.close()
            old_dict[node_number]=this_dict
            f = open(os.path.join(this_img["f"],json_name), 'w')
            json.dump(old_dict,f)
            f.close()
#remove the image
            os.remove(os.path.join(this_img["f"],this_img["n"]))
        self.destroy()

    def prev(self):
        if self.curr_image>0:
            self.curr_image-=1
        first_pos=self.image_list[self.curr_image]["n"].index("_")+1
        last_pos=self.image_list[self.curr_image]["n"].index(".")
        self.curr_type = self.node_types[ self.image_list[self.curr_image]["n"][first_pos:last_pos]  ]
        self.update()

    def next(self):
        if self.curr_image<self.max_image-1:
            self.curr_image+=1
        first_pos=self.image_list[self.curr_image]["n"].index("_")+1
        last_pos=self.image_list[self.curr_image]["n"].index(".")
        self.curr_type = self.node_types[ self.image_list[self.curr_image]["n"][first_pos:last_pos]  ]
        self.update()


    def update(self):
        self.mod1_val_menu.grid_forget()
        self.mod2_val_menu.grid_forget()
        self.mod3_val_menu.grid_forget()
        self.mod4_val_menu.grid_forget()
        self.im = ImageTk.PhotoImage(self.image_list[self.curr_image]["i"])
        self.image=tkinter.Label(self, image = self.im )
        self.image.grid(row=1, column=0, columnspan=3, padx=3, pady=3)
#initalize the menus to say what they are
        self.name.set("Name")
        
        self.name_menu.destroy()
        #self.name_options = list(reversed(sorted(list( self.passiveMods["Glorious Vanity"][self.curr_type].keys() ))))
        #self.name_menu = tkinter.Spinbox( self, values=self.name_options, state='readonly')
        self.name_options = sorted(list( self.passiveMods["Glorious Vanity"][self.curr_type].keys() ))
        self.name_menu = tkinter.OptionMenu( self, self.name, *self.name_options )
        self.name_menu.grid(row=2, column=0, padx=3, pady=3)
        self.mod1_menu.grid_forget()
        self.mod2_menu.grid_forget()
        self.mod3_menu.grid_forget()
        self.mod4_menu.grid_forget()
        self.confirmButton.grid_forget()

    def name_update(self):
        self.mod1_val_menu.grid_forget()
        self.mod2_val_menu.grid_forget()
        self.mod3_val_menu.grid_forget()
        self.mod4_val_menu.grid_forget()
        self.mod1_menu.grid_forget()
        self.mod2_menu.grid_forget()
        self.mod3_menu.grid_forget()
        self.mod4_menu.grid_forget()
        self.confirmButton.grid_forget()
        curr_name=self.name.get()
        if self.curr_type=="regular":
            self.mod1_menu.destroy()
            self.mod1_options=self.passiveMods["Glorious Vanity"][self.curr_type][curr_name]
            self.mod1.set("Mod1")
            self.mod1_menu = tkinter.OptionMenu( self, self.mod1, *self.mod1_options )
            self.mod1_menu.grid(row=2, column=1, padx=3, pady=3)
            self.confirmButton.grid(row=2, column=2, padx=3, pady=3)
        else:
            if self.name.get() in ["Might of the Vaal", "Legacy of the Vaal"]:
                self.mod1_menu.destroy()
                self.mod2_menu.destroy()
                self.mod3_menu.destroy()
                self.mod4_menu.destroy()
                self.mod1_options=vaal_type_options
                self.mod2_options=vaal_type_options
                self.mod3_options=vaal_type_options
                self.mod4_options=vaal_type_options
                self.mod1.set("Mod1")
                self.mod2.set("Mod2")
                self.mod3.set("Mod3")
                self.mod4.set("Mod4")
                self.mod1_val.set("")
                self.mod2_val.set("")
                self.mod3_val.set("")
                self.mod4_val.set("")
                self.mod1_menu = tkinter.OptionMenu( self, self.mod1, *self.mod1_options )
                self.mod2_menu = tkinter.OptionMenu( self, self.mod2, *self.mod2_options )
                self.mod3_menu = tkinter.OptionMenu( self, self.mod3, *self.mod3_options )
                self.mod4_menu = tkinter.OptionMenu( self, self.mod4, *self.mod4_options )
                self.mod1_menu.grid(row=2, column=1, padx=3, pady=3)
                self.mod2_menu.grid(row=3, column=1, padx=3, pady=3)
                self.mod3_menu.grid(row=4, column=1, padx=3, pady=3)
                self.mod4_menu.grid(row=5, column=1, padx=3, pady=3)
                self.mod1_val_menu.grid(row=2, column=2, padx=3, pady=3)
                self.mod2_val_menu.grid(row=3, column=2, padx=3, pady=3)
                self.mod3_val_menu.grid(row=4, column=2, padx=3, pady=3)
                self.mod4_val_menu.grid(row=5, column=2, padx=3, pady=3)
                self.confirmButton.grid(row=6, column=2, padx=3, pady=3)
            else:
                self.mod1_menu.destroy()
                self.mod2_menu.destroy()
                self.mod1_options=self.passiveMods["Glorious Vanity"][self.curr_type][curr_name]
                self.mod2_options=self.passiveMods["Glorious Vanity"][self.curr_type][curr_name]
                self.mod1.set("Mod1")
                self.mod2.set("Mod2")
                self.mod1_menu = tkinter.OptionMenu( self, self.mod1, *self.mod1_options )
                self.mod2_menu = tkinter.OptionMenu( self, self.mod2, *self.mod2_options )
                self.mod1_menu.grid(row=2, column=1, padx=3, pady=3)
                self.mod2_menu.grid(row=3, column=1, padx=3, pady=3)
                self.confirmButton.grid(row=2, column=2, padx=3, pady=3)

    def confirm(self):
#generate the mod dictionary entry
#pull the name
        node_name= self.name.get()
        if self.curr_type=="regular":
#pull the mod
            node_mods = [self.mod1.get()]
        else:
            if node_name in ["Might of the Vaal", "Legacy of the Vaal"]:
                node_mod1= self.mod1.get()
                node_mod2= self.mod2.get()
                node_mod3= self.mod3.get()
                node_mod4= self.mod4.get()
                node_mod1_val = str_to_int(self.mod1_val.get())
                node_mod2_val = str_to_int(self.mod2_val.get())
                node_mod3_val = str_to_int(self.mod3_val.get())
                node_mod4_val = str_to_int(self.mod4_val.get())
                if node_mod1 not in ["None", "Mod1"]:
                    pos_X=node_mod1.find("X")
                    real_mod1 = node_mod1[:pos_X]+node_mod1_val+node_mod1[pos_X+1:]
                else:
                    real_mod1 = ""
                if node_mod2 not in ["None", "Mod2"]:
                    pos_X=node_mod2.find("X")
                    real_mod2 = node_mod2[:pos_X]+node_mod2_val+node_mod2[pos_X+1:]
                else:
                    real_mod2 = ""
                if node_mod3 not in ["None", "Mod3"]:
                    pos_X=node_mod3.find("X")
                    real_mod3 = node_mod3[:pos_X]+node_mod3_val+node_mod3[pos_X+1:]
                else:
                    real_mod3 = ""
                if node_mod4 not in ["None", "Mod4"]:
                    pos_X=node_mod4.find("X")
                    real_mod4 = node_mod4[:pos_X]+node_mod4_val+node_mod4[pos_X+1:]
                else:
                    real_mod4 = ""
                node_mods = []
                if real_mod1 != "":
                    node_mods.append(real_mod1)
                if real_mod2 != "":
                    node_mods.append(real_mod2)
                if real_mod3 != "":
                    node_mods.append(real_mod3)
                if real_mod4 != "":
                    node_mods.append(real_mod4)
            else:
                node_mods = [self.mod1.get(),self.mod2.get()]
        self.fixed_mods.append((int(self.curr_image),{"name": str(node_name), "mods": list(node_mods)}))
        
#save the dictionary entry to the list of dictionary entries
        if self.curr_image == self.max_image-1:
            print("Confirmed last image, quitting!")
            self.close_app()
            return
        self.next()




app=GlobalApplication()
app.mainloop()
