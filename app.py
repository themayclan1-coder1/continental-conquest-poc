import streamlit as st
import random
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

st.set_page_config(page_title="Continental Conquest POC", layout="wide")

# 1. Official Terrain Production & Multipliers (Revision 5.0)
TERRAIN_SPECS = {
    "Plains":       {"money": 500,  "food": 11, "fuel": 55,  "parts": 11, "vaccine": 0, "fuel_cost": 1.0},
    "Agricultural": {"money": 500,  "food": 41, "fuel": 0,   "parts": 0,  "vaccine": 0, "fuel_cost": 1.0},
    "Forest":       {"money": 500,  "food": 21, "fuel": 0,   "parts": 0,  "vaccine": 4, "fuel_cost": 1.25},
    "Desert":       {"money": 1500, "food": 0,  "fuel": 155, "parts": 0,  "vaccine": 0, "fuel_cost": 1.25},
    "Mountains":    {"money": 4500, "food": 0,  "fuel": 0,   "parts": 0,  "vaccine": 0, "fuel_cost": 2.0}
}

# Vehicle Stats (Fuel, Max HP, and Damage Roll Generator)
VEHICLE_STATS = {
    "Car":  {"fuel": 2, "hp": 30, "roll": lambda: sum(random.randint(1, 6) for _ in range(2)) + 1},  # 2d6+1
    "Bike": {"fuel": 1, "hp": 10, "roll": lambda: random.randint(1, 3)},                              # 1d3
    "Van":  {"fuel": 3, "hp": 50, "roll": lambda: sum(random.randint(1, 6) for _ in range(3)) + 2},  # 3d6+2
    "Bus":  {"fuel": 5, "hp": 75, "roll": lambda: sum(random.randint(1, 6) for _ in range(4)) + 1},  # 4d6+1
    "Truck":{"fuel": 7, "hp": 150, "roll": lambda: sum(random.randint(1, 6) for _ in range(8)) + 4}  # 8d6+4
}

DIRECTIONS = {
    "N":  (0, -1), "NE": (1, -1), "SE": (1, 0),
    "S":  (0, 1),  "SW": (-1, 1), "NW": (-1, 0)
}

def hex_to_pixel(q, r, size=1.0):
    x = size * (np.sqrt(3) * q + np.sqrt(3)/2 * r)
    y = size * (3/2 * r)
    return x, y

# 2. Game State Initialization
def init_game():
    grid = {}
    terrain_types = ["Plains", "Plains", "Agricultural", "Forest", "Desert", "Mountains"]
    for q in range(-3, 4):
        for r in range(-3, 4):
            if abs(q + r) <= 3:
                terrain = random.choice(terrain_types)
                grid[(q, r)] = {
                    "terrain": terrain,
                    "owner": None,
                    "defense": random.randint(1, 3),
                    "troops": 0
                }
    
    # Starting bases
    grid[(-2, 0)]["owner"] = "Clan_A"
    grid[(-2, 0)]["city"] = "Fort A"
    grid[(2, 0)]["owner"] = "Clan_B"
    grid[(2, 0)]["city"] = "Fort B"

    # Clan Stockpiles
    clans = {
        "Clan_A": {
            "name": "Northern Coalition", 
            "money": 20000, 
            "food": 120, 
            "fuel": 100, 
            "parts": 100, 
            "vaccine": 10, 
            "troops": 50
        },
        "Clan_B": {
            "name": "Southern Syndicate", 
            "money": 20000, 
            "food": 120, 
            "fuel": 100, 
            "parts": 100, 
            "vaccine": 10, 
            "troops": 50
        }
    }

    # Starting Convoys
    convoys = {
        "Convoy_A1": {
            "clan": "Clan_A", 
            "q": -2, "r": 0, 
            "vehicles": {"Car": 1, "Bike": 2}, 
            "troops": 25, 
            "mode": "CAPTURE",
            "hidden": False
        },
        "Convoy_B1": {
            "clan": "Clan_B", 
            "q": 2, "r": 0, 
            "vehicles": {"Car": 1, "Bike": 2}, 
            "troops": 25, 
            "mode": "CAPTURE",
            "hidden": False
        }
    }

    return {"turn": 1, "grid": grid, "clans": clans, "convoys": convoys, "logs": []}

if "game" not in st.session_state:
    st.session_state.game = init_game()

game = st.session_state.game

def get_convoy_base_fuel(vehicles):
    return sum(VEHICLE_STATS[v]["fuel"] * count for v, count in vehicles.items())

def calculate_salvo(convoy):
    damage = 0
    # Vehicles damage roll
    for v_name, count in convoy["vehicles"].items():
        for _ in range(count):
            damage += VEHICLE_STATS[v_name]["roll"]()
    # Troops fire: 50% chance each to score 1 pt
    for _ in range(convoy["troops"]):
        if random.random() < 0.5:
            damage += 1
    return damage

def resolve_convoy_combat(c_atk_id, c_def_id, q, r):
    """Resolves round of vehicle/troop combat per Continental Conquest rules."""
    c_atk = game["convoys"][c_atk_id]
    c_def = game["convoys"][c_def_id]
    clan_atk = game["clans"][c_atk["clan"]]
    clan_def = game["clans"][c_def["clan"]]

    combat_logs = [f"⚔️ BATTLE at ({q}, {r}) between {c_atk_id} and {c_def_id}!"]

    # Both sides roll salvos
    salvo_atk = calculate_salvo(c_atk)
    salvo_def = calculate_salvo(c_def)

    # Helper function to apply damage
    def apply_damage(convoy, clan, incoming_dmg, target_name):
        dmg_rem = incoming_dmg
        troops_lost = 0
        vehicles_lost = []

        # List all vehicle instances
        v_list = []
        for v_name, count in convoy["vehicles"].items():
            for _ in range(count):
                v_list.append({"type": v_name, "hp": VEHICLE_STATS[v_name]["hp"]})

        while dmg_rem > 0 and (convoy["troops"] > 0 or len(v_list) > 0):
            # 1 in 5 (20%) chance to target troop
            if convoy["troops"] > 0 and (random.random() < 0.20 or len(v_list) == 0):
                convoy["troops"] -= 1
                troops_lost += 1
                dmg_rem -= 1
            elif len(v_list) > 0:
                # Vehicle hit takes 5-10 dmg
                hit = min(dmg_rem, random.randint(5, 10))
                idx = random
