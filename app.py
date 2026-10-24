import streamlit as st
import random
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

st.set_page_config(page_title="Continental Conquest POC", layout="wide")

# 1. Coordinate / Hex Helpers (Axial coordinates)
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
    # Generate a 7x7 hex map
    for q in range(-3, 4):
        for r in range(-3, 4):
            if abs(q + r) <= 3:
                terrain = random.choice(["Plains", "Plains", "Forest", "Desert", "Mountains"])
                grid[(q, r)] = {
                    "terrain": terrain,
                    "owner": None,
                    "defense": random.randint(1, 3),
                    "troops": 0
                }
    
    # Starting setup for 2 Clans
    grid[(-2, 0)]["owner"] = "Clan_A"
    grid[(-2, 0)]["city"] = "Fort A"
    grid[(2, 0)]["owner"] = "Clan_B"
    grid[(2, 0)]["city"] = "Fort B"

    clans = {
        "Clan_A": {"name": "Northern Coalition", "money": 20000, "food": 500, "fuel": 500, "troops": 50},
        "Clan_B": {"name": "Southern Syndicate", "money": 20000, "food": 500, "fuel": 500, "troops": 50}
    }

    convoys = {
        "Convoy_A1": {"clan": "Clan_A", "q": -2, "r": 0, "troops": 20, "fuel": 100, "mode": "CAPTURE"},
        "Convoy_B1": {"clan": "Clan_B", "q": 2, "r": 0, "troops": 20, "fuel": 100, "mode": "CAPTURE"}
    }

    return {"turn": 1, "grid": grid, "clans": clans, "convoys": convoys, "logs": []}

if "game" not in st.session_state:
    st.session_state.game = init_game()

game = st.session_state.game

# 3. Simple Heuristic AI Logic
def ai_generate_moves(convoy_id, convoy_data):
    """Simple AI: pick an adjacent legal hex, preferring uncaptured/enemy hexes."""
    q, r = convoy_data["q"], convoy_data["r"]
    moves = []
    
    for _ in range(5):  # 5 movement pulses per turn for POC
        valid_neighbors = []
        for d_name, (dq, dr) in DIRECTIONS.items():
            nq, nr = q + dq, r + dr
            if (nq, nr) in game["grid"]:
                target = game["grid"][(nq, nr)]
                score = 1
                if target["owner"] != convoy_data["clan"]:
                    score += 3  # Priority to expand/capture
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
    logs.append(f"--- RUNNING TURN {game['turn']} ---")
    
    # Convoy Movement & Resolution
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

# 5. UI & Map Rendering
st.title("Continental Conquest: 2-AI Proof of Concept")

col_ctrl, col_map = st.columns([1, 2])

with col_ctrl:
    st.subheader(f"Game Status (Turn {game['turn']})")
    if st.button("Run Next Turn (Simulate AI vs AI)", type="primary"):
        run_turn()
        st.rerun()

    if st.button("Reset Game"):
        st.session_state.game = init_game()
        st.rerun()

    st.write("### Turn Logs")
    for msg in game["logs"][:12]:
        st.caption(msg)

with col_map:
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.set_aspect('equal')
    ax.axis('off')

    # Draw hex grid
    for (q, r), cell in game["grid"].items():
        x, y = hex_to_pixel(q, r)
        color = "#e0e0e0"  # Unowned
        if cell["owner"] == "Clan_A":
            color = "#6baed6"  # Blue
        elif cell["owner"] == "Clan_B":
            color = "#fb6a4a"  # Red
            
        hex_patch = patches.RegularPolygon((x, y), numVertices=6, radius=0.95, 
                                           orientation=0, facecolor=color, edgecolor="#333333", alpha=0.8)
        ax.add_patch(hex_patch)
        ax.text(x, y, f"{q},{r}\n{cell['terrain'][:3]}", ha='center', va='center', fontsize=7)

    # Plot convoys
    for cid, cdata in game["convoys"].items():
        x, y = hex_to_pixel(cdata["q"], cdata["r"])
        marker_color = "darkblue" if cdata["clan"] == "Clan_A" else "darkred"
        ax.plot(x, y, marker='*', markersize=14, color=marker_color)

    st.pyplot(fig)
