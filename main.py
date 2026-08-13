import streamlit as st
import random
import hashlib
import psycopg2
from datetime import datetime, timedelta
import sqlite3


def get_db_connection():
    return psycopg2.connect(st.secrets["DATABASE_URL"])

try:
    conn = get_db_connection()
    conn.close()
    st.success("✅ PostgreSQL connection successful!")
except Exception as e:
    st.error(f"❌ PostgreSQL connection failed: {e}")

# database_setup.py

# ========================
# CONNECT TO SQLITE
# ========================
conn = sqlite3.connect("pilot_system.db")
conn.execute("PRAGMA foreign_keys = ON")  # enforce relational integrity
c = conn.cursor()

# ========================
# CREATE USERS TABLE
# ========================
c.execute("""
          CREATE TABLE IF NOT EXISTS users
          (
              user_id
              INTEGER
              PRIMARY
              KEY
              AUTOINCREMENT,
              username
              TEXT
              UNIQUE
              NOT
              NULL,
              password
              TEXT
              NOT
              NULL
          )
          """)

# ========================
# CREATE MACHINES TABLE
# ========================
c.execute("""
          CREATE TABLE IF NOT EXISTS machines
          (
              machine_id
              INTEGER
              PRIMARY
              KEY
              AUTOINCREMENT,
              user_id
              INTEGER
              NOT
              NULL,
              name
              TEXT
              NOT
              NULL,
              serial_number
              TEXT,
              model
              TEXT,
              location
              TEXT,
              criticality_level
              TEXT,
              install_date
              TEXT,
              designed_life_years
              INTEGER,
              max_runtime_per_day
              INTEGER,
              warranty_start_date
              TEXT,
              warranty_end_date
              TEXT,
              total_breakdowns
              INTEGER
              DEFAULT
              0,
              environment_condition
              TEXT,
              cost
              REAL,
              downtime_cost_per_hour
              REAL,
              manufacturer
              TEXT,
              FOREIGN
              KEY
          (
              user_id
          ) REFERENCES users
          (
              user_id
          ) ON DELETE CASCADE
              )
          """)

# ========================
# CREATE WORK ORDERS TABLE
# ========================
c.execute("""
          CREATE TABLE IF NOT EXISTS work_orders
          (
              work_order_id
              INTEGER
              PRIMARY
              KEY
              AUTOINCREMENT,
              user_id
              INTEGER
              NOT
              NULL,
              machine_id
              INTEGER
              NOT
              NULL,
              asset_name
              TEXT
              NOT
              NULL,
              location
              TEXT,
              title
              TEXT
              NOT
              NULL,
              description
              TEXT,
              status
              TEXT
              NOT
              NULL,
              priority
              TEXT,
              created_at
              TEXT
              NOT
              NULL,
              due_date
              TEXT,
              completed_at
              TEXT,
              timeline_notes
              TEXT,
              downtime_hours
              REAL
              DEFAULT
              0,
              maintenance_cost
              REAL
              DEFAULT
              0,
              FOREIGN
              KEY
          (
              user_id
          ) REFERENCES users
          (
              user_id
          ) ON DELETE CASCADE,
              FOREIGN KEY
          (
              machine_id
          ) REFERENCES machines
          (
              machine_id
          )
            ON DELETE CASCADE
              )
          """)

c.execute("""
          CREATE TABLE IF NOT EXISTS machine_thresholds
          (
              threshold_id
              INTEGER
              PRIMARY
              KEY
              AUTOINCREMENT,
              user_id
              INTEGER
              NOT
              NULL,
              machine_id
              INTEGER
              NOT
              NULL,
              sensor_type
              TEXT
              NOT
              NULL,
              threshold_value
              REAL
              NOT
              NULL,
              threshold_method
              TEXT, -- 'auto_20_percent', 'manual', etc.
              created_at
              TEXT
              NOT
              NULL,

              FOREIGN
              KEY
          (
              user_id
          ) REFERENCES users
          (
              user_id
          ) ON DELETE CASCADE,
              FOREIGN KEY
          (
              machine_id
          ) REFERENCES machines
          (
              machine_id
          )
            ON DELETE CASCADE,
              UNIQUE
          (
              user_id,
              machine_id,
              sensor_type
          )
              )
          """)

c.execute("""
          CREATE TABLE IF NOT EXISTS sensor_readings
          (
              reading_id
              INTEGER
              PRIMARY
              KEY
              AUTOINCREMENT,
              user_id
              INTEGER
              NOT
              NULL,
              machine_id
              INTEGER
              NOT
              NULL,
              sensor_type
              TEXT
              NOT
              NULL,
              sensor_value
              REAL
              NOT
              NULL,
              threshold_value
              REAL,
              status
              TEXT, -- 'Normal', 'Warning', 'Critical'
              recorded_at
              TEXT
              NOT
              NULL,

              FOREIGN
              KEY
          (
              user_id
          ) REFERENCES users
          (
              user_id
          ) ON DELETE CASCADE,
              FOREIGN KEY
          (
              machine_id
          ) REFERENCES machines
          (
              machine_id
          )
            ON DELETE CASCADE
              )
          """)

# ========================
# COMMIT AND CLOSE
# ========================
conn.commit()
conn.close()

print("✅ Pilot SQLite database and tables created successfully!")

# ======================
# CONFIG - USERS & AI
# ======================
AI_NAME = "Wizzera"

# Fake AI responses for chat fallback
FAKE_AI_RESPONSES = [
    "All assets are operating within normal parameters.",
    "Pump A shows a slight temperature increase.",
    "No critical alerts detected at this time.",
    "Predictive maintenance suggests inspection in 7 days.",
    "Energy consumption is stable across assets.",
    "Vibration levels remain within safe thresholds.",
    "System health score: 92%.",
    "No anomalies detected in sensor data.",
    "Asset efficiency is optimal.",
    "Monitoring continues in real-time",
]

# Assets dictionary
ASSETS = {
    "Compressor": "Block 4 : 104",
    "Conveyor System": "Block 2 : 210",
    "CNC Machine": "Block 1 : 305",
    "Robotic Arm": "Block 3 : 118",
    "Hydraulic Power Unit": "Block 5 : 401",
    "Storage Tank": "Block 6 : 009",
    "Inverters": "Block 2 : 087",
    "Plasma Cutter": "Block 1 : 412",
    "Drilling Machine": "Block 3 : 266",
    "Pump": "Block 4 : 155",
}

# ======================
# SESSION STATE INIT
# ======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "page" not in st.session_state:
    st.session_state.page = "home"
if "chats" not in st.session_state:
    st.session_state.chats = {"Chat 1": []}
if "active_chat" not in st.session_state:
    st.session_state.active_chat = "Chat 1"
if "manual_mode" not in st.session_state:
    st.session_state.manual_mode = "Sensors"

# ======================
# CUSTOM PAGE STYLING
# ======================
st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(to top, white 0%, black 100%); color: white; }
    .stTextInput>div>div>input { color: black; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ======================
# LOGIN LOGIC
# ======================

# Hash password
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# Safe user creation
def create_user(username, password, role="client"):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id FROM users WHERE username = %s",
        (username,)
    )
    existing = cursor.fetchone()

    if existing:
        print(f"[INFO] User '{username}' already exists. Skipping creation. (User ID: {existing[0]})")
        user_id = existing[0]
    else:
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s) RETURNING user_id",
            (username, hash_password(password))
        )
        user_id = cursor.fetchone()[0]
        conn.commit()
        print(f"[SUCCESS] User '{username}' created successfully. (User ID: {user_id})")

    conn.close()
    return user_id


# return user_id for linking machines/work orders


# Example usage
create_user("Raza0421", "sxb123456")

# Example usage
create_user("Raza0421", "sxb123456")


# ======================
# VERIFY USER FUNCTION
# ======================
def verify_user(username, password):
    hashed = hash_password(password)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE username=%s AND password=%s", (username, hashed))
    user = c.fetchone()
    conn.close()  # close AFTER fetching
    if user:
        return True, user[0]  # return True + user_id
    return False, None


# ======================
# LOGIN PAGE
# ======================
def login_page():
    st.title("Asset Management System: WIZZERA.")
    st.subheader("Owner Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        success, user_id = verify_user(username, password)
        if success:
            # ✅ Store user info in session_state
            st.session_state.logged_in = True
            st.session_state.page = "home"
            st.session_state.current_user_id = user_id  # unique key for dashboard
            st.session_state.current_username = username
            st.success(f"Logged in as {username} (User ID: {user_id})")
            st.rerun()  # Refresh the app to load dashboard
        else:
            st.error("Invalid username or password")


# ======================
# HOME PAGE
# ======================
def home_page():
    st.title("Dashboard")
    st.write("Choose a control mode")
    col1, col2 = st.columns(2)

    # AI Assistant Panel
    with col1:
        st.markdown(
            """
            <div style="border:1px solid #ccc;padding:40px;border-radius:10px; text-align:center;background-color:#222;">
            <h2>AI Assistant</h2>
            <p>Chat with Wizzera</p>
            </div>
            """, unsafe_allow_html=True
        )
        if st.button("Open AI Assistant"):
            st.session_state.page = "ai"
            st.rerun()

    # Manual Control Panel
    with col2:
        st.markdown(
            """
            <div style="border:1px solid #ccc;padding:40px;border-radius:10px; text-align:center;background-color:#222;">
            <h2>Manual Control</h2>
            <p>Direct asset control</p>
            </div>
            """, unsafe_allow_html=True
        )
        if st.button("Open Manual Control"):
            st.session_state.page = "manual"
            st.rerun()

    st.divider()
    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.page = "home"
        st.rerun()


# ======================
# AI ASSISTANT
# ======================
# Simulated plant state
def generate_plant_state():
    total_assets = len(ASSETS)
    assets_down = random.randint(0, 2)
    assets_under_maintenance = random.randint(1, 3)
    assets_operational = total_assets - assets_down
    work_orders = {
        "approval": random.randint(0, 3),
        "ongoing": random.randint(1, 4),
        "completed": random.randint(2, 6),
    }
    sensors_faulty = random.choice([0, 1])
    predicted_failures = random.choice(["None", "Pump", "Compressor"])
    active_team_members = random.randint(4, 12)
    return {
        "total_assets": total_assets,
        "assets_down": assets_down,
        "assets_under_maintenance": assets_under_maintenance,
        "assets_operational": assets_operational,
        "work_orders": work_orders,
        "sensors_faulty": sensors_faulty,
        "predicted_failures": predicted_failures,
        "active_team_members": active_team_members
    }


# Sensor definitions
SENSOR_RULES = {
    "temperature": {"unit": "°C", "range": (60, 120), "generator": lambda: random.randint(50, 150)},
    "pressure": {"unit": "PSI", "range": (180, 300), "generator": lambda: random.randint(150, 330)},
    "vibration": {"unit": "Hz", "range": (400, 850), "generator": lambda: random.randint(350, 1000)},
    "speed": {"unit": "RPM", "range": (800, 1500), "generator": lambda: random.randint(700, 1700)},
    "position": {
        "generator": lambda: {"x": random.randint(1, 5), "y": random.randint(1, 5), "z": random.randint(1, 5)}},
}


# AI rule engine
def rule_engine(text: str, state):
    text = text.lower().strip()
    total_assets = state["total_assets"]
    assets_operational = state["assets_operational"]
    assets_under_maintenance = state["assets_under_maintenance"]
    assets_down = state["assets_down"]
    work_orders = state["work_orders"]
    sensors_faulty = state["sensors_faulty"]
    predicted_failures = state["predicted_failures"]
    active_team_members = state["active_team_members"]

    # Greeting
    if text in ["hi", "hello", "hey"]:
        return f"Hello 👋 I’m {AI_NAME}.\nI can give you plant status, asset health, work orders, or live sensor readings."

    # Plant status
    if "plant" in text and ("working" in text or "status" in text):
        percent = int((assets_operational / total_assets) * 100)
        return f"🏭 **Plant Status Overview**\n\n• Operational Capacity: **{percent}%**\n• Assets under maintenance: **{assets_under_maintenance}**\n• Production is **not stopped** — load has been shifted to healthy assets."

    # Assets down
    if "assets down" in text or "how many assets are down" in text:
        return f"🔧 **Assets Down:** {assets_down}\nMaintenance teams are assigned and production impact is minimized."

    # Work orders
    if "work order" in text or "workorder" in text:
        return f"🗂 **Work Order Status**\n\n• Approval Required: **{work_orders['approval']}**\n• Ongoing: **{work_orders['ongoing']}**\n• Completed: **{work_orders['completed']}**"

    # Sensor health
    if "sensors" in text and ("working" in text or "status" in text):
        if sensors_faulty == 0:
            return "📡 All sensors are operational and reporting normally."
        return "⚠ One sensor has intermittent readings. Calibration recommended."

    # Failure prediction
    if "failure" in text or "predict" in text:
        if predicted_failures == "None":
            return "✅ No imminent asset failure predicted at this time."
        return f"⚠ **Potential Failure Predicted**\nAsset: **{predicted_failures}**\nRecommendation: Schedule inspection within 48 hours."

    # Team status
    if "team" in text or "technicians" in text:
        return f"👷 **Active Team Members:** {active_team_members}\nAll teams are currently assigned to operational or maintenance tasks."

    # Assign work
    if "assign" in text and "work" in text:
        return "✅ Work order has been assigned successfully.\nMaintenance team has been notified and execution is scheduled."

    # Sensor + asset queries
    asset_found = None
    for asset in ASSETS:
        if asset.lower() in text:
            asset_found = asset
            break
    sensor_found = None
    for sensor in SENSOR_RULES:
        if sensor in text:
            sensor_found = sensor
            break

    if sensor_found and not asset_found:
        return f"Please specify the asset name for {sensor_found} reading."

    if sensor_found and asset_found:
        meta = SENSOR_RULES[sensor_found]
        value = meta["generator"]()
        if sensor_found == "position":
            x, y, z = value["x"], value["y"], value["z"]
            reading = f"{x}D-{y}D-{z}D"
            status = "⚠ Minor offset detected" if max(x, y, z) > 4 else "✅ Normal"
            return f"📍 **Position of {asset_found}:** {reading}\nStatus: {status}"
        low, high = meta["range"]
        unit = meta["unit"]
        status = "⚠ Attention Required" if value < low or value > high else "✅ Normal"
        return f"📡 **{sensor_found.capitalize()} of {asset_found}:** {value}{unit}\nStatus: {status}"

    # Default fallback
    return random.choice(FAKE_AI_RESPONSES)


# ======================
# AI ASSISTANT PAGE
# ======================
import re

AI_NAME = "Wizzera"


def ai_page():

    st.title(f"{AI_NAME} — AI Assistant")

    # ==========================
    # SESSION INIT
    # ==========================
    if "chats" not in st.session_state:
        st.session_state.chats = {"Chat 1": []}
        st.session_state.active_chat = "Chat 1"

    if "processing_message" not in st.session_state:
        st.session_state.processing_message = False

    if "last_machine" not in st.session_state:
        st.session_state.last_machine = None

    # ==========================
    # SIDEBAR
    # ==========================
    with st.sidebar:
        st.header("💬 Recent Chats")

        for chat_name in st.session_state.chats:
            if st.button(chat_name):
                st.session_state.active_chat = chat_name
                st.rerun()

        if st.button("➕ New Chat"):
            name = f"Chat {len(st.session_state.chats)+1}"
            st.session_state.chats[name] = []
            st.session_state.active_chat = name
            st.rerun()

        st.divider()

        if st.button("⬅ Back to Dashboard"):
            st.session_state.page = "home"
            st.rerun()

    chat = st.session_state.chats[st.session_state.active_chat]

    # ==========================
    # DISPLAY HISTORY
    # ==========================
    for sender, message in chat:
        with st.chat_message(sender):
            st.markdown(message)

    # ==========================
    # INPUT
    # ==========================
    user_input = st.chat_input("Ask Wizzera about your plant...")

    # 🚨 MESSAGE LOCK (MAIN FIX)
    if st.session_state.processing_message:
        return

    if not user_input:
        return

    # Activate lock immediately
    st.session_state.processing_message = True

    chat.append(("user", user_input))

    # ==========================
    # CLEAN TEXT
    # ==========================
    clean_text = re.sub(r"[^\w\s]", "", user_input.lower())
    clean_text = clean_text.replace(" ", "")

    user_id = st.session_state.get("current_user_id")

    if not user_id:
        chat.append(("assistant",
                     "Session expired. Please login again."))
        st.session_state.processing_message = False
        return

    conn = get_db_connection()
    c = conn.cursor()

    # ==========================
    # INTENTS
    # ==========================
    intents = {
        "risk": ["risk", "failure", "breakdown", "critical"],
        "work": ["workorder", "maintenance", "task"],
        "health": ["health", "condition"],
        "why": ["why", "reason", "cause"],
        "summary": ["status", "overview"]
    }

    detected_intent = "summary"

    for intent, words in intents.items():
        if any(w in clean_text for w in words):
            detected_intent = intent
            break

    greetings = ["hi", "hello", "hey"]

    # ==========================
    # GREETING
    # ==========================
    if clean_text in greetings:

        response = (
            "Hello 👋 I'm Wizzera.\n\n"
            "I'm monitoring your assets and helping prevent failures."
        )

    # ==========================
    # RISK
    # ==========================
    elif detected_intent == "risk":

        c.execute("""
        SELECT name,total_breakdowns,max_runtime_per_day
        FROM machines WHERE user_id=%s
        """, (user_id,))

        machines = c.fetchall()

        risky = []

        for name, breaks, runtime in machines:
            risk = min(100, breaks * 15 + (runtime or 0))
            if risk >= 60:
                risky.append(name)

        if risky:
            st.session_state.last_machine = risky[0]
            response = (
                f"⚠ Elevated failure probability detected in "
                f"**{', '.join(risky)}**.\n"
                "Preventive inspection recommended."
            )
        else:
            response = "All machines operating normally ✅"

    # ==========================
    # WHY
    # ==========================
    elif detected_intent == "why" and st.session_state.last_machine:

        machine = st.session_state.last_machine

        c.execute("""
        SELECT total_breakdowns,max_runtime_per_day
        FROM machines
        WHERE user_id=%s AND name=%s
        """, (user_id, machine))

        row = c.fetchone()

        if row:
            breaks, runtime = row
            response = (
                f"{machine} risk increased due to "
                f"{breaks} historical breakdowns."
            )

    # ==========================
    # WORK ORDERS
    # ==========================
    elif detected_intent == "work":

        c.execute("""
        SELECT status,COUNT(*)
        FROM work_orders
        WHERE user_id=%s
        GROUP BY status
        """, (user_id,))

        rows = c.fetchall()

        if rows:
            response = "Maintenance workload:\n\n"
            for status, count in rows:
                response += f"• {count} are **{status}**\n"
        else:
            response = "No work orders found."

    # ==========================
    # HEALTH
    # ==========================
    elif detected_intent == "health":

        c.execute("""
        SELECT name,total_breakdowns
        FROM machines WHERE user_id=%s
        """, (user_id,))

        rows = c.fetchall()

        response = "Asset health:\n\n"

        for name, breaks in rows:
            health = max(0, 100 - breaks * 10)
            response += f"• {name}: **{health}%**\n"

    # ==========================
    # DEFAULT
    # ==========================
    else:

        c.execute("SELECT COUNT(*) FROM machines WHERE user_id=%s",
                  (user_id,))
        total = c.fetchone()[0]

        response = (
            f"You have **{total} monitored assets**.\n"
            "Ask about risks, health or maintenance."
        )

    conn.close()

    chat.append(("assistant", response))
    st.session_state.chats[st.session_state.active_chat] = chat

    # ✅ RELEASE LOCK (CRITICAL)
    st.session_state.processing_message = False

    st.rerun()


def manual_page():
    st.title("Manual Control")

    with st.sidebar:
        st.header("Manual Functions")

        if st.button("Predictive Maintenance Detector"):
            st.session_state.manual_mode = "Predictive"
            st.rerun()

        if st.button("Real-Time Asset Monitoring"):
            st.session_state.manual_mode = "Real-Time"
            st.rerun()

        if st.button("Workflow Management"):
            st.session_state.manual_mode = "Workflow"
            st.rerun()

        if st.button("Sensors"):
            st.session_state.manual_mode = "Sensors"
            st.rerun()

        if st.button("Add Asset"):
            st.session_state.manual_mode = "Add_Asset"
            st.rerun()

        if st.button("Add-Workorder"):
            st.session_state.manual_mode = "Add-Workorder"
            st.rerun()

        if st.button("Sensor Data"):
            st.session_state.manual_mode = "Sensor Data"
            st.rerun()

        if st.button("Threshold Configuration"):
            st.session_state.manual_mode = "Threshold Configuration"
            st.rerun()

        st.divider()

        if st.button("⬅ Back to Dashboard"):
            st.session_state.page = "home"
            st.rerun()

    mode = st.session_state.manual_mode

    # ======================
    # PREDICTIVE
    # ======================

    if mode == "Predictive":

        st.subheader("🧠 Predictive Maintenance Detection")

        def safe_percent(value):
            try:
                value = float(value)
            except:
                value = 0
            return max(0, min(100, round(value, 1)))

        user_id = st.session_state.get("current_user_id")
        if not user_id:
            st.error("User session not found. Please login first.")
            st.stop()

        conn = get_db_connection()
        c = conn.cursor()

        # Fetch all machines for user
        c.execute("""
                  SELECT machine_id,
                         name,
                         location,
                         serial_number,
                         model,
                         criticality_level,
                         install_date,
                         designed_life_years,
                         total_breakdowns,
                         max_runtime_per_day
                  FROM machines
                  WHERE user_id = %s
                  """, (user_id,))
        machines = c.fetchall()

        if not machines:
            st.warning("No machines registered for this user.")
            st.stop()

        today = datetime.now()
        FAILURE_THRESHOLDS = {
            "Vibration": 100,
            "Temperature": 80
        }

        for row in machines:
            machine_id, name, location, serial, model, criticality, install_date, life_years, total_breakdowns, max_runtime = row

            # ======================
            # Fetch latest sensor reading per type
            # ======================
            c.execute("""
                      SELECT sensor_type, sensor_value
                      FROM sensor_readings
                      WHERE user_id = %s
                        AND machine_id = %s
                      ORDER BY recorded_at DESC
                      """, (user_id, machine_id))
            sensor_rows = c.fetchall()

            # Map latest reading per sensor type
            sensor_map = {}
            for s_type, value in sensor_rows:
                if s_type not in sensor_map:
                    sensor_map[s_type] = float(value)  # latest first

            # Determine if we have sensor data
            use_sensor_logic = bool(sensor_map)

            # ======================
            # SENSOR-BASED RISK ONLY
            # ======================
            final_probability = 0
            reason = None

            if use_sensor_logic:
                for sensor_type, threshold in FAILURE_THRESHOLDS.items():
                    if sensor_type not in sensor_map:
                        continue

                    latest = sensor_map[sensor_type]

                    # Threshold logic
                    if latest >= threshold:
                        # Above threshold → high probability
                        final_probability = safe_percent(60 + (latest - threshold) / threshold * 40)
                        reason = f"{sensor_type} exceeded safe threshold ({latest})"
                    elif latest >= threshold * 0.8:
                        # Near threshold → warning
                        final_probability = safe_percent((latest / threshold) * 50)
                        reason = f"{sensor_type} near threshold ({latest})"
                    else:
                        # Below threshold → low
                        final_probability = safe_percent((latest / threshold) * 20)
                        reason = f"{sensor_type} within safe range ({latest})"

            # ======================
            # LIFECYCLE-BASED RISK (fallback if no sensor)
            # ======================
            if not use_sensor_logic:
                if install_date and life_years:
                    install_dt = datetime.strptime(install_date, "%Y-%m-%d")
                    days_used = (today - install_dt).days
                    total_days = life_years * 365
                    life_used_percent = safe_percent((days_used / total_days) * 100)
                else:
                    life_used_percent = 0

                breakdown_risk = safe_percent(total_breakdowns * 10)
                runtime_risk = safe_percent((max_runtime / 24) * 100) if max_runtime else 0

                final_probability = safe_percent(
                    life_used_percent * 0.5 +
                    breakdown_risk * 0.3 +
                    runtime_risk * 0.2
                )
                reason = "Using lifecycle data (no sensors)"

            # ======================
            # RISK LEVEL
            # ======================
            if final_probability >= 60:
                risk_level = "High"
                risk_color = "#dc3545"
            elif final_probability >= 20:
                risk_level = "Warning"
                risk_color = "#ffcc00"
            else:
                risk_level = "Normal"
                risk_color = "#17a2b8"

            # ======================
            # Additional reasons
            # ======================
            reasons = []
            if reason:
                reasons.append(reason)
            if not use_sensor_logic and install_date and life_used_percent > 75:
                reasons.append("Asset near end of life")
            if total_breakdowns > 0:
                reasons.append(f"{total_breakdowns} historical breakdown(s)")
            if max_runtime and max_runtime > 16:
                reasons.append("High runtime stress")
            reason_text = "\n".join(reasons) if reasons else "No significant risk"

            # ======================
            # Display
            # ======================
            st.markdown(
                f"""
                <div style="
                    background:#2b2b2b;
                    padding:18px;
                    border-radius:14px;
                    margin-bottom:16px;
                    border-left:6px solid {risk_color};
                ">
                    <h4>🛠 {name}</h4>
                    <p><b>📍 Location:</b> {location}</p>
                    <p><b>Serial No:</b> {serial}</p>
                    <p><b>Model:</b> {model}</p>
                    <p><b>Criticality Level:</b> {criticality}</p>
                    <p><b>Failure Probability:</b> {final_probability}%</p>
                    <p><b>Risk Level:</b> {risk_level}</p>
                    <p style="white-space:pre-line;"><b>Primary Risk Drivers:</b>\n{reason_text}</p>
                </div>
                """,
                unsafe_allow_html=True
            )

            col1, col2 = st.columns(2)
            with col1:
                st.button(f"📄 View Report — {name}")
            with col2:
                st.button(f"🛠 Schedule Maintenance — {name}")

        conn.close()

    # ======================
    # SENSORS
    # ======================

    elif mode == "Sensors":
        st.subheader("📡 Sensor Inventory")

        asset = st.selectbox("Select Asset", list(ASSETS.keys()))
        location = ASSETS[asset]

        st.markdown(f"### 🏭 **Asset:** {asset}")
        st.markdown(f"📍 **Location:** {location}")

        SENSOR_TYPES = [
            "🌡 Temperature Sensor",
            "📍 Position Sensor",
            "🚀 Speed Sensor",
            "📳 Vibration Sensor",
            "🔊 Ultrasonic Sensor",
        ]

        MANUFACTURERS = [
            "XBD High-End Sensors",
            "Shenchon Sensors",
            "Singhai Sensors",
            "Industrial Pro Sensors",
        ]

        st.divider()

        for sensor in SENSOR_TYPES:
            manufacturer = random.choice(MANUFACTURERS)
            model = (
                    random.choice(["X", "S", "P", "Q"])
                    + str(random.randint(100, 999))
                    + random.choice(["A", "B", "Z"])
            )
            install_year = random.randint(2005, 2026)
            expiry_year = random.randint(2030, 2040)

            col1, col2, col3 = st.columns([3, 2, 2])

            with col1:
                st.markdown(f"### **{sensor}**")
                st.markdown(f"🏭 **Manufacturer:** {manufacturer}")
                st.markdown(f"🆔 **Model Number:** {model}")

            with col2:
                st.markdown(f"📅 **Installed Year:** {install_year}")
                st.markdown(f"⏳ **Expiry Year:** {expiry_year}")

            with col3:
                st.success("🟢 **Sensor Status: Operational**")
                st.markdown("✅ **Condition: New / Healthy**")

            st.divider()

        if st.button("📡 **Show Live Data**"):
            st.info("🔄 Switching to Real-Time Monitoring View…")

    # ======================
    # REAL TIME
    # ======================

    elif mode == "Real-Time":

        st.subheader("Real-Time Asset Monitoring")

        # ==========================
        # SAFE PERCENT FUNCTION
        # ==========================
        def safe_percent(value):
            try:
                value = float(value)
            except:
                value = 0
            return max(0, min(100, int(value)))

        # ==========================
        # GET LOGGED-IN USER
        # ==========================
        user_id = st.session_state.get("current_user_id")
        if not user_id:
            st.error("User session not found. Please login first.")
            st.stop()

        conn = get_db_connection()
        c = conn.cursor()
        # ==========================
        # FETCH MACHINES
        # ==========================
        c.execute("""
                  SELECT machine_id,
                         name,
                         serial_number,
                         model,
                         location,
                         criticality_level,
                         install_date,
                         designed_life_years,
                         max_runtime_per_day,
                         warranty_start_date,
                         warranty_end_date,
                         total_breakdowns,
                         environment_condition,
                         manufacturer,
                         cost
                  FROM machines
                  WHERE user_id = %s
                  """, (user_id,))
        machines = c.fetchall()

        if not machines:
            st.warning("No machines registered for this user.")
            st.stop()

        machine_dict = {
            row[1]: {
                "machine_id": row[0],
                "serial_number": row[2],
                "model": row[3],
                "location": row[4],
                "criticality_level": row[5],
                "install_date": row[6],
                "life_years": row[7],
                "max_runtime": row[8],
                "warranty_start": row[9],
                "warranty_end": row[10],
                "total_breakdowns": row[11],
                "environment_condition": row[12],
                "manufacturer": row[13],
                "cost": row[14]
            }
            for row in machines
        }

        asset = st.selectbox("Select Asset", list(machine_dict.keys()))
        data = machine_dict[asset]
        machine_id = data["machine_id"]

        today = datetime.now()

        # ==========================
        # LIFE CALCULATION
        # ==========================
        life_remaining = 100
        if data["install_date"] and data["life_years"]:
            install = datetime.strptime(data["install_date"], "%Y-%m-%d")
            total_days = data["life_years"] * 365
            used_days = (today - install).days
            life_remaining = safe_percent((1 - used_days / total_days) * 100)

        maintenance_requirement = safe_percent(100 - life_remaining)

        # ==========================
        # WARRANTY CALCULATION + COUNTDOWN
        # ==========================
        warranty_remaining = 100
        warranty_days_left = 0

        if data["warranty_start"] and data["warranty_end"]:
            start = datetime.strptime(data["warranty_start"], "%Y-%m-%d")
            end = datetime.strptime(data["warranty_end"], "%Y-%m-%d")

            total_warranty_days = (end - start).days
            used_warranty_days = (today - start).days

            warranty_remaining = safe_percent((1 - used_warranty_days / total_warranty_days) * 100)

            days_left = (end - today).days
            warranty_days_left = max(0, days_left)

        # ==========================
        # WORK ORDERS
        # ==========================
        c.execute("""
                  SELECT COUNT(*)
                  FROM work_orders
                  WHERE user_id = %s
                    AND machine_id = %s
                  """, (user_id, machine_id))
        total_workorders = c.fetchone()[0]

        c.execute("""
                  SELECT COUNT(*)
                  FROM work_orders
                  WHERE user_id = %s
                    AND machine_id = %s
                    AND status = 'Completed'
                  """, (user_id, machine_id))
        completed_workorders = c.fetchone()[0]

        workorder_completed_percent = safe_percent(
            (completed_workorders / total_workorders) * 100
            if total_workorders > 0 else 0
        )

        # TOTAL MAINTENANCE COST
        c.execute("""
                  SELECT SUM(maintenance_cost)
                  FROM work_orders
                  WHERE user_id = %s
                    AND machine_id = %s
                  """, (user_id, machine_id))
        total_maintenance_cost = c.fetchone()[0] or 0

        # BREAKDOWNS
        total_breakdowns = data["total_breakdowns"] or 0
        breakdown_scaled = safe_percent(total_breakdowns * 10)

        conn.close()

        # ==========================
        # HEALTH SCORE
        # ==========================
        health_score = safe_percent(
            (life_remaining * 0.35) +
            (warranty_remaining * 0.15) +
            ((100 - breakdown_scaled) * 0.25) +
            (workorder_completed_percent * 0.25)
        )

        # ==========================
        # SMART RISK ENGINE
        # ==========================
        risk_score = 0

        if health_score < 50:
            risk_score += 2
        elif health_score < 70:
            risk_score += 1

        if total_breakdowns >= 3:
            risk_score += 1

        if maintenance_requirement > 60:
            risk_score += 1

        if warranty_days_left == 0:
            risk_score += 1

        if risk_score >= 3:
            risk_level = "HIGH RISK"
            risk_color = "red"
        elif risk_score == 2:
            risk_level = "MEDIUM RISK"
            risk_color = "orange"
        else:
            risk_level = "LOW RISK"
            risk_color = "green"

        # ==========================
        # ASSET AGE
        # ==========================
        asset_age_years = 0
        if data["install_date"]:
            install = datetime.strptime(data["install_date"], "%Y-%m-%d")
            asset_age_years = (today - install).days // 365 

        # ==========================
        # HEADER SECTION
        # ==========================
        colA, colB = st.columns(2)

        colA.markdown(f"### 🏭 {asset}")
        colA.markdown(f"**Serial No:** {data['serial_number']}")
        colA.markdown(f"**Model:** {data['model']}")
        colA.markdown(f"**Location:** {data['location']}")
        colA.markdown(f"**Criticality Level:** {data['criticality_level']}")
        colA.markdown(f"**Max Runtime:** {data['max_runtime']} hrs/day")
        colA.markdown(f"**Environment Condition:** {data['environment_condition']}")
        colA.markdown(f"**Manufacturer:** {data['manufacturer']}")
        colA.markdown(f"**Cost:** ${data['cost']}")

        colB.metric("Overall Health Score", f"{health_score}%")
        colB.metric("Asset Age (Years)", asset_age_years)
        colB.metric("Warranty Days Remaining", warranty_days_left)
        colB.metric("Total Maintenance Cost ($)", f"{total_maintenance_cost:.2f}")

        # ==========================
        # VISUAL RISK DISPLAY
        # ==========================
        st.markdown("### 🚨 Risk Assessment")

        if risk_color == "red":
            st.error(f"{risk_level} — Immediate Attention Required")
        elif risk_color == "orange":
            st.warning(f"{risk_level} — Monitor Closely")
        else:
            st.success(f"{risk_level} — Asset Operating Normally")

        st.divider()

        # ==========================
        # STATUS BARS (COLOR LOGIC)
        # ==========================
        st.markdown("### 📊 Asset Status Overview")

        st.progress(life_remaining)
        st.write(f"Life Remaining: {life_remaining}%")

        st.progress(warranty_remaining)
        st.write(f"Warranty Remaining: {warranty_remaining}%")

        st.progress(maintenance_requirement)
        st.write(f"Maintenance Requirement: {maintenance_requirement}%")

        st.progress(workorder_completed_percent)
        st.write(f"Work Orders Completed: {workorder_completed_percent}%")

        st.progress(breakdown_scaled)
        st.write(f"Total Breakdowns (Scaled): {breakdown_scaled}%")

        st.divider()

        # ==========================
        # SENSOR SECTION
        # ==========================
        st.markdown("### 📟 Current Sensor Readings")

        conn = get_db_connection()
        c = conn.cursor()

        yesterday = datetime.now() - timedelta(days=1)

        c.execute("""
                  SELECT sensor_type, sensor_value
                  FROM sensor_readings
                  WHERE user_id = %s
                    AND machine_id = %s
                    AND recorded_at >= %s
                  ORDER BY recorded_at DESC
                  """, (user_id, machine_id, yesterday.strftime("%Y-%m-%d %H:%M:%S")))

        rows = c.fetchall()
        conn.close()

        simulated = False
        sensor_data = {}

        if not rows:
            simulated = True
            sensor_data = {
                "Temperature": random.randint(80, 150),
                "Pressure": random.randint(150, 300),
                "Vibration": random.randint(300, 800),
                "Speed": random.randint(60, 120),
                "Runtime": random.randint(1000, 4000),
            }
        else:
            for sensor_type, value in rows:
                if sensor_type not in sensor_data:
                    sensor_data[sensor_type] = value

        if simulated:
            st.info("⚠ Simulated sensor readings (no live upload in last 24h)")

        col1, col2, col3 = st.columns(3)

        col1.metric("Temperature (°C)", sensor_data.get("Temperature", 0))
        col2.metric("Pressure (PSI)", sensor_data.get("Pressure", 0))
        col3.metric("Vibration (Hz)", sensor_data.get("Vibration", 0))

        col1.metric("Speed (RPM)", sensor_data.get("Speed", 0))
        col2.metric("Run Time (hrs)", sensor_data.get("Runtime", 0))
        col3.metric("Data Source", "Simulated" if simulated else "Live Upload")

    # ======================
    # WORKFLOW MANAGEMENT (STREAMLIT ONLY)
    # ======================

    if mode == "Workflow":

        st.subheader("🗂 Workflow Management")

        # ======================
        # GET LOGGED-IN USER
        # ======================
        user_id = st.session_state.get("current_user_id")
        if not user_id:
            st.error("User session not found. Please login first.")
            st.stop()

        conn = get_db_connection()
        c = conn.cursor()

        # ======================
        # FETCH ALL WORK ORDERS
        # ======================
        c.execute("""
                  SELECT work_order_id,
                         asset_name,
                         location,
                         title,
                         description,
                         status,
                         priority,
                         created_at,
                         due_date,
                         completed_at,
                         timeline_notes
                  FROM work_orders
                  WHERE user_id = %s
                  ORDER BY created_at DESC
                  """, (user_id,))
        work_orders = c.fetchall()

        if not work_orders:
            st.info("No work orders found for your account.")
            conn.close()
            st.stop()

        today = datetime.now()

        # ======================
        # DISPLAY WORK ORDERS
        # ======================
        for wo in work_orders:
            (work_order_id, asset_name, location, title, description, status,
             priority, created_at, due_date, completed_at, timeline_notes) = wo

            # ======================
            # Check due date
            # ======================
            if due_date:
                due_dt = datetime.strptime(due_date, "%Y-%m-%d")
                if today > due_dt:
                    # Delete expired work order
                    c.execute("DELETE FROM work_orders WHERE work_order_id=%s", (work_order_id,))
                    conn.commit()
                    continue  # skip display
            else:
                due_dt = None

            # ======================
            # Only “Requested Approval” shown
            # ======================
            status_text = "Awaiting Admin Approval"
            badge = "Approval Required"
            timeline = timeline_notes or "Not started"

            # ======================
            # DISPLAY CARD
            # ======================
            with st.container():
                st.markdown("---")
                col1, col2 = st.columns([3, 1])

                with col1:
                    st.markdown(f"### {asset_name}")
                    st.write(f"📍 **Location:** {location}")
                    st.write(f"📌 **Status:** {status_text}")
                    st.write(f"📝 **Title:** {title}")
                    st.write(f"📝 **Description:** {description}")
                    if timeline:
                        st.write(f"⏱ **Timeline:** {timeline}")
                    if priority:
                        st.write(f"⚡ **Priority:** {priority}")
                    if due_dt:
                        st.write(f"📅 **Due Date:** {due_dt.strftime('%Y-%m-%d')}")

                with col2:
                    st.info(badge)

                # ======================
                # ACTION BUTTONS
                # ======================
                b1, b2 = st.columns(2)
                with b1:
                    st.button(f"📄 View Details — {asset_name}", key=f"view_{work_order_id}")
                with b2:
                    st.button(f"✅ Approve Work — {asset_name}", key=f"approve_{work_order_id}")

        conn.close()

    if mode == "Add_Asset":
        st.subheader("➕ Add New Asset")

        # Get current logged-in user ID
        user_id = st.session_state.current_user_id

        min_date = datetime(1900, 1, 1)

        # ========================
        # MACHINE INPUT FORM
        # ========================
        with st.form("add_machine_form"):
            name = st.text_input("Machine Name")
            serial_number = st.text_input("Serial Number")
            model = st.text_input("Model")
            location = st.text_input("Location")
            criticality_level = st.selectbox(
                "Criticality Level", ["Low", "Medium", "High"]
            )

            install_date = st.date_input(
                "Installation Date",
                value=datetime.today(),
                min_value=min_date
            )

            designed_life_years = st.number_input(
                "Designed Life (years)", min_value=1, max_value=100, value=10
            )

            max_runtime_per_day = st.number_input(
                "Max Runtime per Day (hours)", min_value=1, max_value=24, value=8
            )

            warranty_start_date = st.date_input(
                "Warranty Start Date",
                value=datetime.today(),
                min_value=min_date
            )

            warranty_end_date = st.date_input(
                "Warranty End Date",
                value=datetime.today(),
                min_value=min_date
            )

            total_breakdowns = st.number_input(
                "Total Breakdowns", min_value=0, value=0
            )

            environment_condition = st.text_input("Environment Condition")

            cost = st.number_input(
                "Machine Cost ($)", min_value=0.0, value=0.0
            )

            downtime_cost_per_hour = st.number_input(
                "Downtime Cost per Hour ($)", min_value=0.0, value=0.0
            )

            manufacturer = st.text_input("Manufacturer")

            submitted = st.form_submit_button("Add Machine")

        # ========================
        # INSERT INTO DATABASE
        # ========================
        if submitted:
            try:
                conn = get_db_connection()
                c = conn.cursor()

                c.execute(
                    """
                    INSERT INTO machines (user_id, name, serial_number, model, location, criticality_level,
                                          install_date, designed_life_years, max_runtime_per_day,
                                          warranty_start_date, warranty_end_date, total_breakdowns,
                                          environment_condition, cost, downtime_cost_per_hour, manufacturer)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        name,
                        serial_number,
                        model,
                        location,
                        criticality_level,
                        install_date.strftime("%Y-%m-%d"),
                        designed_life_years,
                        max_runtime_per_day,
                        warranty_start_date.strftime("%Y-%m-%d"),
                        warranty_end_date.strftime("%Y-%m-%d"),
                        total_breakdowns,
                        environment_condition,
                        cost,
                        downtime_cost_per_hour,
                        manufacturer,
                    ),
                )

                conn.commit()
                st.success(f"✅ Machine '{name}' added successfully for User ID {user_id}")
                print(f"[DEBUG] Machine added for user_id={user_id}: {name}")

            except Exception as e:
                st.error(f"❌ Error adding machine: {e}")
                print(f"[ERROR] Failed to add machine for user_id={user_id}: {e}")

            finally:
                conn.close()

    elif mode == "Add-Workorder":
        st.subheader("📝 Add New Work Order")

        # Get logged-in user ID
        user_id = st.session_state.current_user_id

        # ========================
        # FETCH MACHINES FOR THIS USER
        # ========================
        conn = get_db_connection()
        c = conn.cursor()

        c.execute(
            "SELECT machine_id, name, location FROM machines WHERE user_id = %s",
            (user_id,)
        )
        machines = c.fetchall()
        conn.close()

        if not machines:
            st.warning("⚠ No machines found for your account. Please add an asset first.")
            st.stop()

        machine_options = {
            f"{m[1]} (ID: {m[0]})": (m[0], m[1], m[2])
            for m in machines
        }

        # ========================
        # WORK ORDER FORM
        # ========================
        with st.form("add_work_order_form"):
            selected_machine_label = st.selectbox(
                "Select Machine",
                list(machine_options.keys())
            )

            machine_id, asset_name, location = machine_options[selected_machine_label]

            title = st.text_input("Work Order Title")
            description = st.text_area("Description")

            status = st.selectbox(
                "Status",
                ["Open", "In Progress", "On Hold", "Completed"]
            )

            priority = st.selectbox(
                "Priority",
                ["Low", "Medium", "High", "Critical"]
            )

            created_at = st.date_input("Created At", datetime.today())
            due_date = st.date_input("Due Date", datetime.today())

            timeline_notes = st.text_area("Timeline Notes")

            downtime_hours = st.number_input(
                "Downtime Hours",
                min_value=0.0,
                value=0.0
            )

            maintenance_cost = st.number_input(
                "Maintenance Cost ($)",
                min_value=0.0,
                value=0.0
            )

            submitted = st.form_submit_button("Create Work Order")

        # ========================
        # INSERT INTO DATABASE
        # ========================
        if submitted:
            try:
                conn = get_db_connection()
                c = conn.cursor()

                c.execute(
                    """
                    INSERT INTO work_orders (user_id,
                                             machine_id,
                                             asset_name,
                                             location,
                                             title,
                                             description,
                                             status,
                                             priority,
                                             created_at,
                                             due_date,
                                             completed_at,
                                             timeline_notes,
                                             downtime_hours,
                                             maintenance_cost)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        machine_id,
                        asset_name,
                        location,
                        title,
                        description,
                        status,
                        priority,
                        created_at.strftime("%Y-%m-%d"),
                        due_date.strftime("%Y-%m-%d"),
                        None,  # completed_at (only set when status = Completed)
                        timeline_notes,
                        downtime_hours,
                        maintenance_cost
                    ),
                )

                conn.commit()
                st.success(f"✅ Work Order '{title}' created successfully for User ID {user_id}")
                print(f"[DEBUG] Work order created for user_id={user_id}, machine_id={machine_id}, title={title}")

            except Exception as e:
                st.error(f"❌ Error creating work order: {e}")
                print("[ERROR]", e)

            finally:
                conn.close()

    elif mode == "Threshold Configuration":

        st.subheader("⚙ Threshold Configuration")

        st.markdown("""
        ### 📘 Instructions:
        1. Select your machine.
        2. Choose sensor type.
        3. Either:
            - Upload 30 days CSV to auto-calculate threshold (+20%), OR
            - Enter threshold manually.
        4. Click Save Threshold.
        """)

        user_id = st.session_state.current_user_id

        # ===============================
        # FETCH USER MACHINES
        # ===============================
        conn = get_db_connection()
        c = conn.cursor()

        c.execute(
            "SELECT machine_id, name FROM machines WHERE user_id = %s",
            (user_id,)
        )
        machines = c.fetchall()
        conn.close()

        if not machines:
            st.warning("⚠ No machines found. Please add an asset first.")
            st.stop()

        machine_options = {
            f"{m[1]} (ID: {m[0]})": m[0]
            for m in machines
        }

        # ===============================
        # FORM START
        # ===============================
        with st.form("threshold_form"):

            selected_machine_label = st.selectbox(
                "Select Machine",
                list(machine_options.keys())
            )

            machine_id = machine_options[selected_machine_label]

            sensor_type = st.selectbox(
                "Select Sensor Type",
                ["Temperature", "Pressure", "Vibration", "Speed"]
            )

            method = st.radio(
                "Threshold Method",
                ["Auto Calculate (Upload CSV)", "Manual Entry"]
            )

            threshold_value = None

            # Manual input always visible
            manual_input = st.number_input(
                "Enter Threshold Value (Manual)",
                min_value=0.0,
                step=0.1
            )

            # CSV uploader only shows for auto
            uploaded_file = None
            if method == "Auto Calculate (Upload CSV)":
                uploaded_file = st.file_uploader(
                    "Upload 30 Days Sensor CSV",
                    type=["csv"]
                )
                if uploaded_file:
                    import pandas as pd
                    df = pd.read_csv(uploaded_file)
                    if sensor_type not in df.columns:
                        st.error(f"❌ CSV must contain column: {sensor_type}")
                    else:
                        average = df[sensor_type].mean()
                        threshold_value = average * 1.2
                        st.info(f"Suggested Threshold (+20%): {round(threshold_value, 2)}")

            # Use manual input if manual selected
            if method == "Manual Entry":
                threshold_value = manual_input

            # ===============================
            # FORM SUBMISSION
            # ===============================
            submitted = st.form_submit_button("Save Threshold")

            if submitted:

                if threshold_value is None:
                    st.error("❌ Please provide threshold value.")
                else:
                    try:
                        conn = get_db_connection()
                        c = conn.cursor()

                        c.execute(
                            """
                            INSERT INTO machine_thresholds
                            (
                                user_id,
                                machine_id,
                                sensor_type,
                                threshold_value,
                                threshold_method,
                                created_at
                            )
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (user_id, machine_id, sensor_type)
                            DO UPDATE SET
                                threshold_value = EXCLUDED.threshold_value,
                                threshold_method = EXCLUDED.threshold_method,
                                created_at = EXCLUDED.created_at
                            """,
                            (
                                user_id,
                                machine_id,
                                sensor_type,
                                float(threshold_value),
                                "auto_20_percent" if method.startswith("Auto") else "manual",
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            )
                        )

                        conn.commit()
                        conn.close()

                        st.success("✅ Threshold Saved Successfully")

                        # Debug Print
                        print("===================================")
                        print("THRESHOLD SAVED")
                        print(f"User ID: {user_id}")
                        print(f"Machine ID: {machine_id}")
                        print(f"Sensor: {sensor_type}")
                        print(f"Threshold: {threshold_value}")
                        print("Method: " + ("Auto" if method.startswith("Auto") else "Manual"))
                        print("===================================")

                    except Exception as e:
                        st.error(f"❌ Error saving threshold: {e}")
                        print("[ERROR]", e)

    elif mode == "Sensor Data":

        st.subheader("📊 Sensor Data Upload / Manual Entry")

        st.markdown("""
        ### 📘 Instructions:
        1. Select your machine.
        2. Choose the sensor type.
        3. Either:
            - Upload CSV of readings (multiple entries), OR
            - Enter a single reading manually (always visible).
        4. System will compare against threshold and save status.
        """)

        user_id = st.session_state.current_user_id

        # ===============================
        # FETCH USER MACHINES
        # ===============================
        conn = get_db_connection()
        c = conn.cursor()

        c.execute(
            "SELECT machine_id, name FROM machines WHERE user_id = %s",
            (user_id,)
        )
        machines = c.fetchall()
        conn.close()

        if not machines:
            st.warning("⚠ No machines found. Please add an asset first.")
            st.stop()

        machine_options = {f"{m[1]} (ID: {m[0]})": m[0] for m in machines}

        # ===============================
        # FORM START
        # ===============================
        with st.form("sensor_data_form"):

            selected_machine_label = st.selectbox(
                "Select Machine",
                list(machine_options.keys())
            )
            machine_id = machine_options[selected_machine_label]

            sensor_type = st.selectbox(
                "Select Sensor Type",
                ["Temperature", "Pressure", "Vibration", "Speed"]
            )

            # Always show manual input
            manual_value = st.number_input(
                "Enter Sensor Reading (Manual)",
                min_value=0.0,
                step=0.1
            )

            # CSV upload optional
            uploaded_file = st.file_uploader(
                "Upload CSV for multiple readings (optional)",
                type=["csv"]
            )

            submitted = st.form_submit_button("Save Sensor Data")

        # ===============================
        # PROCESS AND SAVE READINGS
        # ===============================
        if submitted:
            readings = []

            # Add manual input first
            readings.append(manual_value)

            # Add CSV readings if uploaded
            if uploaded_file:
                import pandas as pd
                df = pd.read_csv(uploaded_file)
                if sensor_type not in df.columns:
                    st.error(f"❌ CSV must contain column: {sensor_type}")
                else:
                    csv_values = df[sensor_type].tolist()
                    readings.extend(csv_values)
                    st.info(f"{len(csv_values)} readings loaded from CSV")

            if not readings:
                st.error("❌ No readings to save.")
            else:
                try:
                    conn = get_db_connection()
                    c = conn.cursor()

                    # Fetch threshold for this machine & sensor
                    c.execute(
                        """
                        SELECT threshold_value
                        FROM machine_thresholds
                        WHERE user_id = %s
                          AND machine_id = %s
                          AND sensor_type = %s
                        """,
                        (user_id, machine_id, sensor_type)
                    )
                    result = c.fetchone()
                    threshold_value = result[0] if result else None

                    for value in readings:
                        # Determine status based on threshold
                        if threshold_value is None:
                            status = "Unknown"
                        elif value > threshold_value:
                            status = "Critical"
                        elif value > 0.8 * threshold_value:  # 80% warning rule
                            status = "Warning"
                        else:
                            status = "Normal"

                        c.execute(
                            """
                            INSERT INTO sensor_readings
                            (user_id, machine_id, sensor_type, sensor_value, threshold_value, status, recorded_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                user_id,
                                machine_id,
                                sensor_type,
                                float(value),
                                threshold_value,
                                status,
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            )
                        )

                    conn.commit()
                    conn.close()

                    st.success(f"✅ {len(readings)} readings saved successfully!")

                    # Debug print
                    print("===================================")
                    print("SENSOR DATA SAVED")
                    print(f"User ID: {user_id}")
                    print(f"Machine ID: {machine_id}")
                    print(f"Sensor: {sensor_type}")
                    print(f"Threshold: {threshold_value}")
                    print(f"Values: {readings}")
                    print("===================================")

                except Exception as e:
                    st.error(f"❌ Error saving sensor data: {e}")
                    print("[ERROR]", e)


# ======================
# APP FLOW
# ======================

if not st.session_state.logged_in:
    login_page()
else:
    if st.session_state.page == "home":
        home_page()
    elif st.session_state.page == "ai":
        ai_page()
    elif st.session_state.page == "manual":
        manual_page()
