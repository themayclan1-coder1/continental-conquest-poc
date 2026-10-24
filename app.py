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

# Vehicle Stats (Fuel, Max HP, Troop Capacity, and Damage Roll)
VEHICLE_STATS = {
    "Bike": {"fuel": 1, "hp": 10,  "troops": 1,  "cost": 2500,  "roll": lambda: random.randint(1, 3)},                              # 1d3
    "Car":  {"fuel": 2, "hp": 30,  "troops": 3,  "cost": 7500,  "roll": lambda: sum(random.randint(1, 6) for _ in range(2)) + 1},  # 2d6+1
    "Van":  {"fuel": 3, "hp": 50,  "troops": 7,  "cost": 15000, "roll": lambda: sum(random.randint(1, 6) for _ in range(3)) + 2},  # 3d6+2
    "Bus":  {"fuel": 5, "hp": 75,  "troops": 16, "cost": 25000, "roll": lambda: sum(random.randint(1, 6) for _ in range(4)) + 1},  # 4d6+1
    "Truck":{"fuel": 7, "hp": 150, "troops": 20, "cost": 40000, "roll": lambda: sum(random.randint(1, 6) for _ in range(8)) + 4}   # 8d6+4
}

DIRECTIONS = {
    "N":  (0, -1), "NE": (1, -1), "SE": (1, 0),
    "S":  (0, 1),  "SW": (-1, 1), "NW": (-1, 0)
}

def hex_to_pixel(q, r, size=1.0):
    x = size * (np.sqrt(3) * q + np.sqrt(3)/2 * r)
    y = size * (3/2 * r)
    return x, y

def get_convoy_max_troops(vehicles):
    return sum(VEHICLE_STATS[v]["troops"] * count for v, count in vehicles.items())

def get_convoy_base_fuel(vehicles):
    return sum(VEHICLE_STATS[v]["fuel"] * count for v, count in vehicles.items())

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
            "base": (-2, 0),
            "money": 20000, 
            "food": 150, 
            "fuel": 150, 
            "parts": 100, 
            "vaccine": 10, 
            "troops": 45
        },
        "Clan_B": {
            "name": "Southern Syndicate", 
            "base": (2, 0),
            "money": 20000, 
            "food": 150, 
            "fuel": 150, 
            "parts": 100, 
            "vaccine": 10, 
            "troops": 45
        }
    }

    # Starting Convoys: 1 Bus + 1 Van + 2 Bikes (Starting with real troop capacity)
    convoys = {
        "Convoy_A1": {
            "clan": "Clan_A", 
            "q": -2, "r": 0, 
            "vehicles": {"Bus": 1, "Van": 1, "Bike": 2}, 
            "troops": 25, 
            "mode": "CAPTURE",
            "hidden": False
        },
        "Convoy_B1": {
            "clan": "Clan_B", 
            "q": 2, "r": 0, 
            "vehicles": {"Bus": 1, "Van": 1, "Bike": 2}, 
            "troops": 25, 
            "mode": "CAPTURE",
            "hidden": False
        }
    }

    return {"turn": 1, "grid": grid, "clans": clans, "convoys": convoys, "logs": []}

if "game" not in st.session_state:
    st.session_state.game = init_game()

game = st.session_state.game

def calculate_salvo(convoy):
    damage = 0
    for v_name, count in convoy["vehicles"].items():
        for _ in range(count):
            damage += VEHICLE_STATS[v_name]["roll"]()
    for _ in range(convoy["troops"]):
        if random.random() < 0.5:
            damage += 1
    return damage

def resolve_convoy_combat(c_atk_id, c_def_id, q, r):
    c_atk = game["convoys"][c_atk_id]
    c_def = game["convoys"][c_def_id]
    clan_atk = game["clans"][c_atk["clan"]]
    clan_def = game["clans"][c_def["clan"]]

    combat_logs = [f"⚔️ BATTLE at ({q}, {r}) between {c_atk_id} and {c_def_id}!"]

    salvo_atk = calculate_salvo(c_atk)
    salvo_def = calculate_salvo(c_def)

    def apply_damage(convoy, clan, incoming_dmg, target_name):
        dmg_rem = incoming_dmg
        troops_lost = 0
        vehicles_lost = []

        v_list = []
        for v_name, count in convoy["vehicles"].items():
            for _ in range(count):
                v_list.append({"type": v_name, "hp": VEHICLE_STATS[v_name]["hp"]})

        while dmg_rem > 0 and (convoy["troops"] > 0 or len(v_list) > 0):
            if convoy["troops"] > 0 and (random.random() < 0.20 or len(v_list) == 0):
                convoy["troops"] -= 1
                troops_lost += 1
                dmg_rem -= 1
            elif len(v_list) > 0:
                hit = min(dmg_rem, random.randint(5, 10))
                idx = random.randint(0, len(v_list) - 1)
                v_list[idx]["hp"] -= hit
                dmg_rem -= hit
                if v_list[idx]["hp"] <= 0:
                    dead_v = v_list.pop(idx)
                    vehicles_lost.append(dead_v["type"])
                    convoy["vehicles"][dead_v["type"]] -= 1
            else:
                break

        parts_cost = int(np.ceil(incoming_dmg / 5))
        if clan["parts"] >= parts_cost:
            clan["parts"] -= parts_cost
        else:
            clan["parts"] = 0

        summary = f"{target_name} took {incoming_dmg} dmg. Lost {troops_lost} troops"
        if vehicles_lost:
            summary += f", lost {', '.join(vehicles_lost)}"
        summary += f". Repaired for {parts_cost} parts."
        return summary

    combat_logs.append(apply_damage(c_def, clan_def, salvo_atk, c_def_id))
    combat_logs.append(apply_damage(c_atk, clan_atk, salvo_def, c_atk_id))

    v_count_atk = sum(c_atk["vehicles"].values())
    v_count_def = sum(c_def["vehicles"].values())

    if v_count_def == 0 or (c_def["troops"] < c_atk["troops"] and v_count_def <= v_count_atk):
        c_def["hidden"] = True
        combat_logs.append(f"🛡️ {c_def_id} fled into HIDING!")
    else:
        c_atk["hidden"] = True
        combat_logs.append(f"🛡️ {c_atk_id} fled into HIDING!")

    return combat_logs

# 3. AI Orders Heuristic
def ai_generate_moves(convoy_id, convoy_data):
    if convoy_data["hidden"]:
        return []

    q, r = convoy_data["q"], convoy_data["r"]
    moves = []
    for _ in range(5):
        valid_neighbors = []
        for d_name, (dq, dr) in DIRECTIONS.items():
            nq, nr = q + dq, r + dr
            if (nq, nr) in game["grid"]:
                target = game["grid"][(nq, nr)]
                score = 1
                if target["owner"] != convoy_data["clan"]:
                    score += 4  # Priority to expand/capture
                valid_neighbors.append((score, nq, nr, d_name))
        
        if valid_neighbors:
            valid_neighbors.sort(key=lambda x: x[0] + random.random(), reverse=True)
            chosen = valid_neighbors[0]
            moves.append((chosen[1], chosen[2], chosen[3]))
            q, r = chosen[1], chosen[2]
            
    return moves

# 4. Turn Processing Engine
def run_turn():
    logs = []
    logs.append(f"=== RUNNING TURN {game['turn']} ===")

    for cdata in game["convoys"].values():
        cdata["hidden"] = False

    # Phase 1: Income Phase
    for clan_id, clan_data in game["clans"].items():
        income_money = 0
        income_food = 0
        income_fuel = 0
        income_parts = 0
        income_vaccine = 0

        for (q, r), cell in game["grid"].items():
            if cell["owner"] == clan_id:
                specs = TERRAIN_SPECS[cell["terrain"]]
                income_money += specs["money"]
                income_food += specs["food"]
                income_fuel += specs["fuel"]
                income_parts += specs["parts"]
                income_vaccine += specs["vaccine"]

        clan_data["money"] += income_money
        clan_data["food"] += income_food
        clan_data["fuel"] += income_fuel
        clan_data["parts"] += income_parts
        clan_data["vaccine"] += income_vaccine

        logs.append(
            f"Income for {clan_data['name']}: +${income_money}, "
            f"+{income_food} food, +{income_fuel} fuel, +{income_parts} parts"
        )

    # Phase 2: Pre-Turn AI Enlistment & Troop Resupply
    for clan_id, clan_data in game["clans"].items():
        # Enlist troops if reserves are low and clan has money
        if clan_data["troops"] < 20 and clan_data["money"] >= 2000:
            recruits = 20
            clan_data["money"] -= recruits * 100
            clan_data["troops"] += recruits
            logs.append(f"Pre-Turn: {clan_data['name']} enlisted {recruits} fresh troops for ${recruits*100}.")

    # Reinforce Convoys from Reserve Troop Pool
    for cid, cdata in game["convoys"].items():
        clan_data = game["clans"][cdata["clan"]]
        max_capacity = get_convoy_max_troops(cdata["vehicles"])
        needed = max_capacity - cdata["troops"]
        
        # If convoy needs troops and clan has reserves, transfer them
        if needed > 0 and clan_data["troops"] > 0:
            assigned = min(needed, clan_data["troops"])
            cdata["troops"] += assigned
            clan_data["troops"] -= assigned
            logs.append(f"Pre-Turn: {cid} loaded {assigned} troops from reserve (now {cdata['troops']}/{max_capacity}).")

    # Phase 3: Pulse Movement & Combat Resolution
    pulse_moves = {cid: ai_generate_moves(cid, cdata) for cid, cdata in game["convoys"].items()}

    for pulse in range(5):
        for cid, cdata in game["convoys"].items():
            if cdata["hidden"] or pulse >= len(pulse_moves[cid]):
                continue

            clan_data = game["clans"][cdata["clan"]]
            base_fuel_burn = get_convoy_base_fuel(cdata["vehicles"])
            nq, nr, direction = pulse_moves[cid][pulse]
            target_hex = game["grid"][(nq, nr)]
            terrain = target_hex["terrain"]
            multiplier = TERRAIN_SPECS[terrain]["fuel_cost"]
            fuel_needed = int(np.ceil(base_fuel_burn * multiplier))

            if clan_data["fuel"] < fuel_needed:
                logs.append(f"Pulse {pulse+1}: {cid} STALLED out of fuel!")
                continue

            clan_data["fuel"] -= fuel_needed
            cdata["q"], cdata["r"] = nq, nr

            food_needed = max(1, int(cdata["troops"] / 10))
            if clan_data["food"] >= food_needed:
                clan_data["food"] -= food_needed
            else:
                clan_data["food"] = 0
                if random.random() < 0.10 and cdata["troops"] > 0:
                    cdata["troops"] -= 1
                    logs.append(f"Pulse {pulse+1}: {cid} troop deserted due to starvation!")

            # Combat encounter check
            for other_id, other_cdata in game["convoys"].items():
                if other_id != cid and other_cdata["clan"] != cdata["clan"]:
                    if other_cdata["q"] == nq and other_cdata["r"] == nr and not other_cdata["hidden"]:
                        c_logs = resolve_convoy_combat(cid, other_id, nq, nr)
                        logs.extend(c_logs)

            # Hex capture check
            if not cdata["hidden"]:
                if target_hex["owner"] != cdata["clan"]:
                    if cdata["troops"] >= target_hex["defense"]:
                        target_hex["owner"] = cdata["clan"]
                        losses = min(cdata["troops"], target_hex["defense"])
                        cdata["troops"] -= losses
                        logs.append(f"Pulse {pulse+1}: {cid} captured ({nq}, {nr})! Lost {losses} troops.")
                    else:
                        logs.append(f"Pulse {pulse+1}: {cid} repelled at ({nq}, {nr}) (Needs {target_hex['defense']}, has {cdata['troops']})!")
                    
    game["turn"] += 1
    game["logs"] = logs + game["logs"]

# 5. UI Layout & Dashboard
st.title("Continental Conquest: 2-AI Proof of Concept")

c1, c2 = st.columns(2)
with c1:
    cA = game["clans"]["Clan_A"]
    hexes_a = sum(1 for c in game["grid"].values() if c["owner"] == "Clan_A")
    convoy_a = game["convoys"]["Convoy_A1"]
    max_a = get_convoy_max_troops(convoy_a["vehicles"])
    v_str_a = ", ".join(f"{count} {v}" for v, count in convoy_a["vehicles"].items() if count > 0) or "None"
    status_a = " [HIDDEN]" if convoy_a["hidden"] else ""
    st.markdown(f"### 🔵 {cA['name']} (Hexes: {hexes_a})")
    st.caption(f"**Convoy A1{status_a}:** {v_str_a} | Troops: **{convoy_a['troops']} / {max_a}**")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Treasury", f"${cA['money']:,}")
    m2.metric("Food", f"{cA['food']}")
    m3.metric("Fuel", f"{cA['fuel']}")
    m4.metric("Parts", f"{cA['parts']}")
    m5.metric("Reserve Troops", f"{cA['troops']}")

with c2:
    cB = game["clans"]["Clan_B"]
    hexes_b = sum(1 for c in game["grid"].values() if c["owner"] == "Clan_B")
    convoy_b = game["convoys"]["Convoy_B1"]
    max_b = get_convoy_max_troops(convoy_b["vehicles"])
    v_str_b = ", ".join(f"{count} {v}" for v, count in convoy_b["vehicles"].items() if count > 0) or "None"
    status_b = " [HIDDEN]" if convoy_b["hidden"] else ""
    st.markdown(f"### 🔴 {cB['name']} (Hexes: {hexes_b})")
    st.caption(f"**Convoy B1{status_b}:** {v_str_b} | Troops: **{convoy_b['troops']} / {max_b}**")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Treasury", f"${cB['money']:,}")
    m2.metric("Food", f"{cB['food']}")
    m3.metric("Fuel", f"{cB['fuel']}")
    m4.metric("Parts", f"{cB['parts']}")
    m5.metric("Reserve Troops", f"{cB['troops']}")

st.divider()

col_ctrl, col_map = st.columns([1, 2])

with col_ctrl:
    st.subheader(f"Turn Control (Turn {game['turn']})")
    if st.button("Run Next Turn (Simulate AI vs AI)", type="primary"):
        run_turn()
        st.rerun()

    if st.button("Reset Game"):
        st.session_state.game = init_game()
        st.rerun()

    st.write("### Turn Logs")
    for msg in game["logs"][:15]:
        st.caption(msg)

with col_map:
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.set_aspect('equal')
    ax.axis('off')

    for (q, r), cell in game["grid"].items():
        x, y = hex_to_pixel(q, r)
        color = "#e0e0e0"
        if cell["owner"] == "Clan_A":
            color = "#6baed6"  # Blue
        elif cell["owner"] == "Clan_B":
            color = "#fb6a4a"  # Red
            
        hex_patch = patches.RegularPolygon(
            (x, y), numVertices=6, radius=0.95, 
            orientation=0, facecolor=color, edgecolor="#333333", alpha=0.8
        )
        ax.add_patch(hex_patch)
        ax.text(x, y, f"{q},{r}\n{cell['terrain'][:3]}", ha='center', va='center', fontsize=7)

    for cid, cdata in game["convoys"].items():
        x, y = hex_to_pixel(cdata["q"], cdata["r"])
        marker_color = "darkblue" if cdata["clan"] == "Clan_A" else "darkred"
        marker_style = 'X' if cdata["hidden"] else '*'
        ax.plot(x, y, marker=marker_style, markersize=14, color=marker_color)

    st.pyplot(fig)
