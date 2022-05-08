import json
import os

parent = ".."
neighbors = "neighbor_nodes.json"

f = open(os.path.join(parent,neighbors), 'r')
neighbor_dict = json.load(f)
f.close()
 
socket_names = {
"6230": "Life-Mana Scion",
"48768": "Spell-Attack Scion",
"31683": "Proj-Res Scion",
"28475": "Dualist-Marauder",
"33631": "Marauder-Templar",
"36634": "Templar-Witch",
"41263": "Witch-Shadow",
"33989": "Shadow-Ranger",
"34483": "Ranger-Dualist",
"54127": "Endurance-Frenzy",
"2491": "Melee Cluster",
"26725": "Endurance Charge",
"55190": "Armour Cluster",
"26196": "Power-Endurance",
"7960": "Elemental Damage Cluster",
"61419": "Power Charge",
"21984": "Mana Cluster",
"61834": "Frenzy-Power",
"32763": "Projectile Cluster",
"60735": "Frenzy Charge",
"46882": "Evasion Cluster"
}

desired_mods=[
                "X% increased effect of Non-Curse Auras from your Skills",
]

threshholds=[
37,
]

all_mod_options = [
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
          #      "X% increased Skill Effect Duration",#curse
          #      "X% increased maximum Life",#minion
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
                "+X% to maximum Lightning Resistance",
                "+X% to maximum Fire Resistance",
                "+X% to maximum Cold Resistance",
                "+X% to maximum Chaos Resistance",
                "Damage Penetrates X% Fire Resistance",
                "Damage Penetrates X% Cold Resistance",
                "Damage Penetrates X% Lightning Resistance",
                "X% chance to inflict Withered for 2 seconds on Hit",
                "X% chance to deal Double Damage",
                "Regenerate X% of Life per second",
                "X% of Chaos Damage Leeched as Life",
                "X% of Cold Damage Leeched as Life",
                "X% of Fire Damage Leeched as Life",
                "X% of Lightning Damage Leeched as Life",
                "X% of Physical Damage Leeched as Life",
                "X% of Physical Damage Converted to Fire Damage",
                "X% of Physical Damage Converted to Cold Damage",
                "X% of Physical Damage Converted to Lightning Damage",
                "+X Life gained when you Block",
                "Bleeding you inflict deals Damage X% faster",
                "Curse Skills have X% increased Skill Effect Duration",
                "X% of Spell Damage Leeched as Energy Shield",
                "X% of Attack Damage Leeched as Life",
                "Minions have X% increased maximum Life",
                "X% chance to Avoid being Stunned",
                "+X% to all Elemental Resistances",
                "X% increased Defences from Equipped Shield",
                "X% increased Critical Strike Chance for Spells",
                "X% increased Energy Shield Recharge Rate",
                "X% chance to Blind Enemies on Hit",
                "X% additional Physical Damage Reduction",
                "X% increased Area of Effect of Aura Skills",
]

desired_mod_prefixes= [mod[:mod.index('X')] for mod in desired_mods]
desired_mod_suffixes= [mod[mod.index('X')+1:] for mod in desired_mods]
num_mod_options=len(desired_mods)

#all_mod_prefixes= [mod[:mod.index('X')] for mod in all_mod_options]
#all_mod_suffixes= [mod[mod.index('X')+1:] for mod in all_mod_options]
#num_mod_options=len(all_mod_options)


here=os.curdir
for folder in os.listdir(here):
    if os.path.isdir(folder):
        for json_name in os.listdir(folder):
            mod_totals=[0 for _ in desired_mods]
            if json_name[-5:] != '.json':
#            if json_name != '61419.json':
                continue
            f = open(os.path.join(folder,json_name), 'r')
            socket_mods=json.load(f)
            f.close()
            socket_id=json_name[:-5]
            node_list = neighbor_dict [socket_id]
            for node_id in node_list:
                if str(node_id) not in socket_mods.keys():
                    a=0
                    #print("Jewel number" +folder+ "is missing node"+str(node_id)+ "in socket"+socket_id)
                else:
                    mods = socket_mods[str(node_id)]["mods"]
                    for mod in mods:
                        for i in range(num_mod_options):
                            #if all_mod_suffixes[i] in mod and all_mod_prefixes[i] in mod:
                            if desired_mod_suffixes[i] in mod and desired_mod_prefixes[i] in mod:
                                pre_numb = mod.index(desired_mod_prefixes[i])
                                suf_numb = mod.index(desired_mod_suffixes[i])
                                mod_numb = float(mod[pre_numb+len(desired_mod_prefixes[i]):suf_numb])
                                mod_totals[i] =mod_totals[i]+mod_numb
            satisfying_thresholds=True
            for i in range(num_mod_options):
                if mod_totals[i]<threshholds[i]:
                    satisfying_thresholds=False
            if satisfying_thresholds:
                print("Jewel number: "+folder)
                print("Socket location: "+socket_names[socket_id])
                for i in range(num_mod_options):
                    print(mod_totals[i],desired_mods[i])
                     
                        
                    
