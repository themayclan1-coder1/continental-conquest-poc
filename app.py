import streamlit as st
import random
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

st.set_page_config(page_title="Continental Conquest POC", layout="wide")

# 1. Official Terrain Production Table (Revision 5.0)
# (Money in thousands, Food, Fuel, Parts, Vaccine)
TERRAIN_SPECS = {
    "Plains":       {"money": 500,  "food": 11, "fuel": 55,  "parts": 11, "vaccine": 0, "fuel_cost": 1.0},
    "Agricultural": {"money": 500,  "food": 41, "fuel": 0,   "parts": 0,  "vaccine": 0, "fuel_cost": 1.0},
    "Forest":       {"money": 500,  "food": 21, "fuel": 0,   "parts": 0,  "vaccine": 4, "fuel_cost": 1.25},
    "Desert":       {"money": 1500, "food": 0,  "fuel": 155, "parts": 0,  "vaccine": 0, "fuel_cost": 1.25},
    "Mountains":    {"money": 4500, "food": 0,  "fuel": 0,   "parts": 0,  "vaccine": 0, "fuel_cost": 2.0}
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

    # Clan Stockpiles (Starting baseline)
    clans = {
        "Clan_A": {
            "name": "Northern Coalition", 
            "money": 20000, 
            "food": 250, 
            "fuel": 300, 
            "parts": 100, 
            "vaccine": 10, 
            "troops": 50
        },
        "Clan_B": {
            "name": "Southern Syndicate", 
            "money": 20000, 
            "food": 250, 
            "fuel": 300, 
            "parts": 100, 
            "vaccine": 10, 
            "troops": 50
        }
    }

    convoys = {
        "Convoy_A1": {"clan": "Clan_A", "q": -2, "r": 0, "troops": 25, "fuel": 100, "mode": "CAPTURE"},
        "Convoy_B1": {"clan": "Clan_B", "q": 2, "r": 0, "troops": 25, "fuel": 100, "mode": "CAPTURE"}
    }

    return {"turn": 1, "grid": grid, "clans": clans, "convoys": convoys, "logs": []}

if "game" not in st.session_state:
    st.session_state.game = init_game()

game = st.session_state.game

# 3. AI Orders Heuristic
def ai_generate_moves(convoy_id, convoy_data):
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
                    score += 3
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

    # Phase 1: Income Phase (Hexes produce resources)
    for clan_id, clan_data in game["clans"].items():
        income_money = 0
        income_food = 0
        income_fuel = 0
        income_parts = 0
        income_vaccine = 0

        # Scan controlled hexes
        for (q, r), cell in game["grid"].items():
            if cell["owner"] == clan_id:
                specs = TERRAIN_SPECS[cell["terrain"]]
                income_money += specs["money"]
                income_food += specs["food"]
                income_fuel += specs["fuel"]
                income_parts += specs["parts"]
                income_vaccine += specs["vaccine"]

        # Deposit into Clan stockpile
        clan_data["money"] += income_money
        clan_data["food"] += income_food
        clan_data["fuel"] += income_fuel
        clan_data["parts"] += income_parts
        clan_data["vaccine"] += income_vaccine

        logs.append(
            f"Income for {clan_data['name']}: +${income_money}, "
            f"+{income_food} food, +{income_fuel} fuel, +{income_parts} parts, +{income_vaccine} vaccine"
        )

    # Phase 2: Convoy Movement Pulses
    for cid, cdata in game["convoys"].items():
        moves = ai_generate_moves(cid, cdata)
        for step, (nq, nr, direction) in enumerate(moves, 1):
            cdata["q"], cdata["r"] = nq, nr
            target_hex = game["grid"][(nq, nr)]
            
            # Capture check
            if target_hex["owner"] != cdata["clan"]:
                if cdata["troops"] >= target_hex["defense"]:
                    target_hex["owner"] = cdata["clan"]
                    losses = min(cdata["troops"], target_hex["defense"])
                    cdata["troops"] -= losses
                    logs.append(f"Pulse {step}: {cid} ({cdata['clan']}) captured ({nq}, {nr})! Lost {losses} troops.")
                else:
                    logs.append(f"Pulse {step}: {cid} repelled at ({nq}, {nr})!")
                    
    game["turn"] += 1
    game["logs"] = logs + game["logs"]

# 5. UI Layout & Dashboard
st.title("Continental Conquest: 2-AI Proof of Concept")

# Resource Metrics Top Bar
c1, c2 = st.columns(2)
with c1:
    cA = game["clans"]["Clan_A"]
    hexes_a = sum(1 for c in game["grid"].values() if c["owner"] == "Clan_A")
    st.markdown(f"### 🔵 {cA['name']} (Hexes: {hexes_a})")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Treasury", f"${cA['money']:,}")
    m2.metric("Food", f"{cA['food']}")
    m3.metric("Fuel", f"{cA['fuel']}")
    m4.metric("Parts", f"{cA['parts']}")
    m5.metric("Troops", f"{cA['troops']}")

with c2:
    cB = game["clans"]["Clan_B"]
    hexes_b = sum(1 for c in game["grid"].values() if c["owner"] == "Clan_B")
    st.markdown(f"### 🔴 {cB['name']} (Hexes: {hexes_b})")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Treasury", f"${cB['money']:,}")
    m2.metric("Food", f"{cB['food']}")
    m3.metric("Fuel", f"{cB['fuel']}")
    m4.metric("Parts", f"{cB['parts']}")
    m5.metric("Troops", f"{cB['troops']}")

st.divider()

# Controls, Logs, and Map
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

    # Draw hex grid
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
        
        # Display axial coords and abbreviated terrain
        ax.text(x, y, f"{q},{r}\n{cell['terrain'][:3]}", ha='center', va='center', fontsize=7)

    # Plot convoys
    for cid, cdata in game["convoys"].items():
        x, y = hex_to_pixel(cdata["q"], cdata["r"])
        marker_color = "darkblue" if cdata["clan"] == "Clan_A" else "darkred"
        ax.plot(x, y, marker='*', markersize=14, color=marker_color)

    st.pyplot(fig)
