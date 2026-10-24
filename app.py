import streamlit as st
import random
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="Continental Conquest", layout="wide")

# 1. Official Terrain Production & Multipliers (Revision 5.0)
TERRAIN_SPECS = {
    "Plains":       {"money": 500,  "food": 11, "fuel": 55,  "parts": 11, "vaccine": 0, "fuel_cost": 1.0},
    "Agricultural": {"money": 500,  "food": 41, "fuel": 0,   "parts": 0,  "vaccine": 0, "fuel_cost": 1.0},
    "Forest":       {"money": 500,  "food": 21, "fuel": 0,   "parts": 0,  "vaccine": 4, "fuel_cost": 1.25},
    "Desert":       {"money": 1500, "food": 0,  "fuel": 155, "parts": 0,  "vaccine": 0, "fuel_cost": 1.25},
    "Mountains":    {"money": 4500, "food": 0,  "fuel": 0,   "parts": 0,  "vaccine": 0, "fuel_cost": 2.0}
}

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

def get_hex_polygon(x, y, radius=0.95):
    angles = np.linspace(0, 2 * np.pi, 7)
    px = x + radius * np.cos(angles)
    py = y + radius * np.sin(angles)
    return px.tolist(), py.tolist()

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
    
    grid[(-2, 0)]["owner"] = "Clan_A"
    grid[(-2, 0)]["city"] = "Fort A"
    grid[(2, 0)]["owner"] = "Clan_B"
    grid[(2, 0)]["city"] = "Fort B"

    clans = {
        "Clan_A": {
            "name": "Northern Coalition (Player)", 
            "base": (-2, 0),
            "money": 20000, 
            "food": 150, 
            "fuel": 150, 
            "parts": 100, 
            "vaccine": 10, 
            "troops": 45
        },
        "Clan_B": {
            "name": "Southern Syndicate (AI)", 
            "base": (2, 0),
            "money": 20000, 
            "food": 150, 
            "fuel": 150, 
            "parts": 100, 
            "vaccine": 10, 
            "troops": 45
        }
    }

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

    return {
        "turn": 1, 
        "state": "ORDERS",  # 'ORDERS' or 'RESULTS'
        "grid": grid, 
        "clans": clans, 
        "convoys": convoys, 
        "latest_logs": [], 
        "all_logs": []
    }

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
                    score += 4
                valid_neighbors.append((score, nq, nr, d_name))
        
        if valid_neighbors:
            valid_neighbors.sort(key=lambda x: x[0] + random.random(), reverse=True)
            chosen = valid_neighbors[0]
            moves.append((chosen[1], chosen[2], chosen[3]))
            q, r = chosen[1], chosen[2]
            
    return moves

# 4. Turn Processing Engine
def run_turn(player_orders):
    current_turn_logs = []
    current_turn_logs.append(f"=== COMPLETED TURN {game['turn']} ===")

    for cdata in game["convoys"].values():
        cdata["hidden"] = False

    # Income Phase
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

        current_turn_logs.append(
            f"Income for {clan_data['name']}: +${income_money}, "
            f"+{income_food} food, +{income_fuel} fuel, +{income_parts} parts"
        )

    # Pre-Turn Player Orders
    clan_a = game["clans"]["Clan_A"]
    if player_orders["enlist_troops"] > 0:
        cost = player_orders["enlist_troops"] * 100
        if clan_a["money"] >= cost:
            clan_a["money"] -= cost
            clan_a["troops"] += player_orders["enlist_troops"]
            current_turn_logs.append(f"Pre-Turn: You enlisted {player_orders['enlist_troops']} troops for ${cost}.")
        else:
            current_turn_logs.append("Pre-Turn: Enlist order failed: insufficient funds.")

    if player_orders["buy_fuel"] > 0:
        cost = player_orders["buy_fuel"] * 20
        if clan_a["money"] >= cost:
            clan_a["money"] -= cost
            clan_a["fuel"] += player_orders["buy_fuel"]
            current_turn_logs.append(f"Pre-Turn: You purchased {player_orders['buy_fuel']} fuel for ${cost}.")
        else:
            current_turn_logs.append("Pre-Turn: Fuel purchase failed: insufficient funds.")

    # Pre-Turn AI Orders
    clan_b = game["clans"]["Clan_B"]
    if clan_b["troops"] < 20 and clan_b["money"] >= 2000:
        recruits = 20
        clan_b["money"] -= recruits * 100
        clan_b["troops"] += recruits
        current_turn_logs.append(f"Pre-Turn: {clan_b['name']} enlisted {recruits} fresh troops.")

    # Reinforce Convoys from Reserve Troop Pools
    for cid, cdata in game["convoys"].items():
        clan_data = game["clans"][cdata["clan"]]
        max_capacity = get_convoy_max_troops(cdata["vehicles"])
        needed = max_capacity - cdata["troops"]
        if needed > 0 and clan_data["troops"] > 0:
            assigned = min(needed, clan_data["troops"])
            cdata["troops"] += assigned
            clan_data["troops"] -= assigned
            current_turn_logs.append(f"Pre-Turn: {cid} loaded {assigned} troops from reserve (now {cdata['troops']}/{max_capacity}).")

    # Pulse Movements & Encounters
    p_moves = []
    cur_q, cur_r = game["convoys"]["Convoy_A1"]["q"], game["convoys"]["Convoy_A1"]["r"]
    for direction in player_orders["pulses"]:
        if direction in DIRECTIONS:
            dq, dr = DIRECTIONS[direction]
            nxt_q, nxt_r = cur_q + dq, cur_r + dr
            if (nxt_q, nxt_r) in game["grid"]:
                p_moves.append((nxt_q, nxt_r, direction))
                cur_q, cur_r = nxt_q, nxt_r
            else:
                p_moves.append((cur_q, cur_r, "BLOCKED"))
        else:
            p_moves.append((cur_q, cur_r, "PAUSE"))

    ai_moves = ai_generate_moves("Convoy_B1", game["convoys"]["Convoy_B1"])

    pulse_plan = {
        "Convoy_A1": p_moves,
        "Convoy_B1": ai_moves
    }

    for pulse in range(5):
        for cid, cdata in game["convoys"].items():
            if cdata["hidden"] or pulse >= len(pulse_plan[cid]):
                continue

            clan_data = game["clans"][cdata["clan"]]
            base_fuel_burn = get_convoy_base_fuel(cdata["vehicles"])
            nq, nr, direction = pulse_plan[cid][pulse]

            if direction == "PAUSE":
                current_turn_logs.append(f"Pulse {pulse+1}: {cid} PAUSED in hex ({nq}, {nr}).")
                continue
            elif direction == "BLOCKED":
                current_turn_logs.append(f"Pulse {pulse+1}: {cid} order failed: target hex off map!")
                continue

            target_hex = game["grid"][(nq, nr)]
            terrain = target_hex["terrain"]
            multiplier = TERRAIN_SPECS[terrain]["fuel_cost"]
            fuel_needed = int(np.ceil(base_fuel_burn * multiplier))

            if clan_data["fuel"] < fuel_needed:
                current_turn_logs.append(f"Pulse {pulse+1}: {cid} STALLED out of fuel!")
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
                    current_turn_logs.append(f"Pulse {pulse+1}: {cid} troop deserted due to starvation!")

            # Combat encounter check
            for other_id, other_cdata in game["convoys"].items():
                if other_id != cid and other_cdata["clan"] != cdata["clan"]:
                    if other_cdata["q"] == nq and other_cdata["r"] == nr and not other_cdata["hidden"]:
                        c_logs = resolve_convoy_combat(cid, other_id, nq, nr)
                        current_turn_logs.extend(c_logs)

            # Hex capture check
            if not cdata["hidden"]:
                if target_hex["owner"] != cdata["clan"]:
                    if cdata["troops"] >= target_hex["defense"]:
                        target_hex["owner"] = cdata["clan"]
                        losses = min(cdata["troops"], target_hex["defense"])
                        cdata["troops"] -= losses
                        current_turn_logs.append(f"Pulse {pulse+1}: {cid} captured ({nq}, {nr})! Lost {losses} troops.")
                    else:
                        current_turn_logs.append(f"Pulse {pulse+1}: {cid} repelled at ({nq}, {nr}) (Needs {target_hex['defense']}, has {cdata['troops']})!")

    game["latest_logs"] = current_turn_logs
    game["all_logs"] = current_turn_logs + game["all_logs"]
    game["state"] = "RESULTS"  # Switch view state to show results

# 5. UI Layout & Dashboard
st.title("Continental Conquest: Human vs AI")

c1, c2 = st.columns(2)
with c1:
    cA = game["clans"]["Clan_A"]
    hexes_a = sum(1 for c in game["grid"].values() if c["owner"] == "Clan_A")
    convoy_a = game["convoys"]["Convoy_A1"]
    max_a = get_convoy_max_troops(convoy_a["vehicles"])
    v_str_a = ", ".join(f"{count} {v}" for v, count in convoy_a["vehicles"].items() if count > 0) or "None"
    status_a = " [HIDDEN]" if convoy_a["hidden"] else ""
    st.markdown(f"### 🔵 {cA['name']} (Hexes: {hexes_a})")
    st.caption(f"**Convoy A1{status_a}:** {v_str_a} | Troops: **{convoy_a['troops']} / {max_a}** | Hex: `({convoy_a['q']}, {convoy_a['r']})`")
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
    st.caption(f"**Convoy B1{status_b}:** {v_str_b} | Troops: **{convoy_b['troops']} / {max_b}** | Hex: `({convoy_b['q']}, {convoy_b['r']})`")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Treasury", f"${cB['money']:,}")
    m2.metric("Food", f"{cB['food']}")
    m3.metric("Fuel", f"{cB['fuel']}")
    m4.metric("Parts", f"{cB['parts']}")
    m5.metric("Reserve Troops", f"{cB['troops']}")

st.divider()

col_panel, col_map = st.columns([1, 2])

# Left Column: Switches dynamically between ORDERS and RESULTS
with col_panel:
    if game["state"] == "ORDERS":
        st.subheader(f"Clan Orders Sheet (Turn {game['turn']})")
        
        with st.expander("Pre-Turn Procurement", expanded=True):
            enlist_val = st.number_input("Enlist Troops ($100 each)", min_value=0, max_value=50, value=0, step=5)
            fuel_val = st.number_input("Buy Fuel ($20 each)", min_value=0, max_value=500, value=0, step=50)

        st.markdown("**Convoy A1 Pulse Moves (5 Pulses)**")
        dir_options = ["N", "NE", "SE", "S", "SW", "NW", "PAUSE"]

        p_cols = st.columns(5)
        pulses = []
        default_dirs = ["SE", "NE", "SE", "S", "PAUSE"]
        for i in range(5):
            with p_cols[i]:
                d = st.selectbox(f"P{i+1}", dir_options, index=dir_options.index(default_dirs[i]), key=f"pulse_{i}_{game['turn']}")
                pulses.append(d)

        if st.button("Submit Orders & Process Turn", type="primary"):
            player_orders = {
                "enlist_troops": enlist_val,
                "buy_fuel": fuel_val,
                "pulses": pulses
            }
            run_turn(player_orders)
            st.rerun()

        if st.button("Reset Game"):
            st.session_state.game = init_game()
            st.rerun()

    elif game["state"] == "RESULTS":
        st.subheader(f"Turn {game['turn']} Results & Intelligence")
        st.success(f"Turn {game['turn']} executed successfully!")

        if st.button(f"Proceed to Turn {game['turn'] + 1} Orders ➔", type="primary"):
            game["turn"] += 1
            game["state"] = "ORDERS"
            st.rerun()

        st.write("### Turn Activity Report")
        for msg in game["latest_logs"]:
            if "BATTLE" in msg:
                st.error(msg)
            elif "captured" in msg:
                st.success(msg)
            elif "STALLED" in msg or "deserted" in msg:
                st.warning(msg)
            else:
                st.caption(msg)

        if st.button("Reset Game", key="reset_results"):
            st.session_state.game = init_game()
            st.rerun()

# Right Column: Map remains always visible
with col_map:
    fig = go.Figure()

    for (q, r), cell in game["grid"].items():
        x, y = hex_to_pixel(q, r)
        px, py = get_hex_polygon(x, y)
        
        fill_color = "rgba(220, 220, 220, 0.75)"
        border_color = "#555555"
        owner_name = "Neutral / Unclaimed"
        
        if cell["owner"] == "Clan_A":
            fill_color = "rgba(107, 174, 214, 0.85)"
            owner_name = "Northern Coalition (You)"
        elif cell["owner"] == "Clan_B":
            fill_color = "rgba(251, 106, 74, 0.85)"
            owner_name = "Southern Syndicate (AI)"

        specs = TERRAIN_SPECS[cell["terrain"]]
        hover_text = (
            f"<b>Hex ({q}, {r})</b><br>"
            f"Terrain: {cell['terrain']}<br>"
            f"Owner: {owner_name}<br>"
            f"Defense Level: {cell['defense']}<br>"
            f"<b>Per Turn Yield:</b><br>"
            f"• Money: ${specs['money']:,}<br>"
            f"• Food: {specs['food']}<br>"
            f"• Fuel: {specs['fuel']}<br>"
            f"• Parts: {specs['parts']}<br>"
            f"• Vaccine: {specs['vaccine']}"
        )

        fig.add_trace(go.Scatter(
            x=px, y=py,
            fill="toself",
            fillcolor=fill_color,
            line=dict(color=border_color, width=1.5),
            hoverinfo="text",
            hovertext=hover_text,
            mode="lines",
            showlegend=False
        ))

        label_text = f"{q},{r}<br>{cell['terrain'][:3]}"
        fig.add_trace(go.Scatter(
            x=[x], y=[y],
            mode="text",
            text=[label_text],
            textfont=dict(size=9, color="#111111"),
            hoverinfo="none",
            showlegend=False
        ))

    for cid, cdata in game["convoys"].items():
        cx, cy = hex_to_pixel(cdata["q"], cdata["r"])
        marker_color = "#084594" if cdata["clan"] == "Clan_A" else "#990000"
        marker_symbol = "x" if cdata["hidden"] else "star"
        max_cap = get_convoy_max_troops(cdata["vehicles"])
        v_list = ", ".join(f"{c} {v}" for v, c in cdata["vehicles"].items())

        convoy_hover = (
            f"<b>{cid}</b> ({'You' if cdata['clan'] == 'Clan_A' else 'AI'})<br>"
            f"Vehicles: {v_list}<br>"
            f"Troops: {cdata['troops']}/{max_cap}<br>"
            f"Status: {'HIDDEN' if cdata['hidden'] else 'ACTIVE'}"
        )

        fig.add_trace(go.Scatter(
            x=[cx], y=[cy],
            mode="markers",
            marker=dict(symbol=marker_symbol, size=18, color=marker_color, line=dict(width=1.5, color="white")),
            hoverinfo="text",
            hovertext=convoy_hover,
            name=cid,
            showlegend=False
        ))

    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False, scaleanchor="x", scaleratio=1),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=580,
        dragmode="pan"
    )

    st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True})
