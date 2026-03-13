import streamlit as st
import numpy as np
import plotly.graph_objects as go

# Set up page layout
st.set_page_config(page_title="EW Time-Based POI Validator", layout="wide")

st.title("🧪 Time-Progression POI Validator")
st.markdown(
    "תוכנית זו מציגה את התכנסות הסטטיסטיקה של המקלט לאורך זמן המשימה. ציר ה-X מייצג את הזמן שחולף בקפיצות של מחזורי מקלט (Deadlines). התוכנה בודקת מתי הסטטיסטיקה המצטברת נכנסת לתוך חלון השגיאה המותר שהגדרת.")

# =========================================================
# 1. User Interface (Threat & Receiver Config)
# =========================================================
st.markdown("### ⚙️ Simulation Parameters")

t_col, r_col, m_col = st.columns(3, gap="large")

with t_col:
    st.subheader("🎯 Threat Parameters")
    t_type = st.selectbox("PRI Type", ["Fixed", "Jittered", "Staggered"])

    pw = st.number_input("Pulse Width (PW) [ms]", value=2.0, format="%g")

    # Dynamic PRI inputs based on type
    avg_pri = 10.0  # Default fallback
    if t_type == "Fixed":
        pri = st.number_input("PRI [ms]", value=10.0, format="%g")
        avg_pri = pri
    elif t_type == "Jittered":
        pri = st.number_input("Base PRI [ms]", value=10.0, format="%g")
        jitter = st.slider("Jitter [%]", 0.0, 50.0, 10.0)
        avg_pri = pri
    elif t_type == "Staggered":
        stag_in = st.text_input("Stagger Sequence [ms]", "8, 10, 12")
        try:
            stagger_seq = [float(x.strip()) for x in stag_in.split(",")]
        except:
            stagger_seq = [10.0]
        avg_pri = np.mean(stagger_seq)

    # Threat Framing
    f_type = st.selectbox("Framing", ["None", "Regular"])
    if f_type == "Regular":
        f_on = st.number_input("Frame ON [ms]", value=50.0, format="%g")
        f_off = st.number_input("Frame OFF [ms]", value=50.0, format="%g")
    else:
        f_on, f_off = 1.0, 0.0  # Dummy values for 'None'

with r_col:
    st.subheader("📡 Receiver Parameters")
    # Using Dwell (Active Rx time) and Gap (Off Rx time)
    rx_dwell = st.number_input("Actual Rx Time (Dwell) [ms]", value=1.0, format="%g", min_value=0.001)
    rx_gap = st.number_input("Rx Gap Time [ms]", value=4.0, format="%g", min_value=0.001)

    rx_revisit = rx_dwell + rx_gap  # Total cycle (The "Deadline")
    st.info(f"💡 **Calculated Revisit (Deadline):** {rx_revisit:g} ms")

with m_col:
    st.subheader("🎲 Monte Carlo & Convergence Setup")
    mission_time = st.number_input("Mission Duration [ms]", value=1000.0, format="%g")
    trials = st.number_input("MC Trials", min_value=100, value=2000, step=500)

    # --- הוספת קלט לאחוז השגיאה המותר ---
    error_margin = st.number_input("Allowed Error Margin (±%)", value=2.0, format="%g",
                                   help="השגיאה המוחלטת המותרת סביב אחוז הגילוי התיאורטי. למשל, אם התיאורטי הוא 20% והשגיאה היא 2%, המערכת תחפש מתי הגרף נכנס לטווח שבין 18% ל-22%.")


# =========================================================
# 2. Physics & Simulation Engine
# =========================================================

def generate_threat_pulses(time_limit, offset_internal, offset_frame):
    """Generates an array of physical pulses based on complex threat behavior."""
    windows = []
    if f_type == "None":
        windows.append((-999999, 999999))
    else:
        f_period = f_on + f_off
        t_f = offset_frame - (f_period * 2)
        while t_f < time_limit:
            windows.append((t_f, t_f + f_on))
            t_f += f_period

    pulses = []

    def get_pri(idx):
        if t_type == "Fixed":
            return pri
        elif t_type == "Jittered":
            return pri * np.random.uniform(1 - jitter / 100, 1 + jitter / 100)
        elif t_type == "Staggered":
            return stagger_seq[idx % len(stagger_seq)]

    # Continuous sync simulation
    if t_type == "Staggered":
        int_per = sum(stagger_seq)
    else:
        int_per = avg_pri

    p_t = offset_internal - (int_per * 2)
    p_idx = 0
    valid_windows = [w for w in windows if w[1] >= p_t]
    w_idx = 0

    while p_t < time_limit:
        current_pri = get_pri(p_idx)
        p_end = p_t + pw

        # Check intersection with valid frames
        while w_idx < len(valid_windows) and valid_windows[w_idx][1] < p_t: w_idx += 1
        temp_w = w_idx
        while temp_w < len(valid_windows) and valid_windows[temp_w][0] < p_end:
            w_start, w_end = valid_windows[temp_w]
            o_start, o_end = max(w_start, p_t), min(w_end, p_end)
            if o_start < o_end and o_end >= 0 and o_start < time_limit:
                pulses.append((o_start, o_end))
            temp_w += 1

        p_t += current_pri
        p_idx += 1

    return pulses


# =========================================================
# 3. Execution & Visualization
# =========================================================

if st.button("🚀 Run Time-Based Validation", type="primary"):

    # Calculate how many "Deadlines" (Revisits) fit in the mission time
    num_steps = int(mission_time / rx_revisit)
    if num_steps < 1:
        st.error("❌ Mission Duration is shorter than a single Receiver Revisit (Deadline)!")
        st.stop()

    # --- Theoretical Calculation ---
    base_prob = min(1.0, (pw + rx_dwell) / avg_pri)
    frame_prob = 1.0 if f_type == "None" else (f_on / (f_on + f_off))
    prob_theory = base_prob * frame_prob * 100.0

    # Array to accumulate total hits across ALL trials, step by step
    global_cumulative_hits = np.zeros(num_steps)

    progress_bar = st.progress(0.0)

    for i in range(trials):
        # 1. Randomize offsets for a completely new phase environment
        offset_frame = np.random.uniform(0, f_on + f_off) if f_type != "None" else 0
        offset_internal = np.random.uniform(0, avg_pri * 5)

        # Initial phase offset for the receiver inside the very first Deadline window
        curr_t = np.random.uniform(0, rx_revisit)

        # 2. Generate Threat Environment (pad with rx_revisit to ensure full coverage)
        threat_pulses = generate_threat_pulses(mission_time + rx_revisit, offset_internal, offset_frame)

        # Array to record if a hit occurred at each specific Deadline step in THIS trial
        trial_hits = np.zeros(num_steps)

        # 3. Step through the mission by Deadlines
        for step in range(num_steps):
            d_start = curr_t
            d_end = curr_t + rx_dwell

            # Check if this specific dwell hit ANY pulse
            hit = any((min(d_end, p[1]) - max(d_start, p[0])) > 0 for p in threat_pulses)
            if hit:
                trial_hits[step] = 1

            curr_t += rx_revisit  # Move to the next Deadline window

        # Calculate cumulative hits for this trial over time, and add to the global pool
        global_cumulative_hits += np.cumsum(trial_hits)

        if i % 100 == 0:
            progress_bar.progress(i / trials)

    progress_bar.progress(1.0)

    # --- Time Axis & Final Math ---
    step_numbers = np.arange(1, num_steps + 1)
    time_axis_ms = step_numbers * rx_revisit  # The X-Axis values: [Deadline 1, Deadline 2, ...]

    total_attempts_per_step = step_numbers * trials
    cumulative_hit_ratio = (global_cumulative_hits / total_attempts_per_step) * 100.0
    final_mc_ratio = cumulative_hit_ratio[-1]

    # --- Convergence Analysis (מציאת נקודת החיתוך הראשונה עם השגיאה המותרת) ---
    upper_bound = prob_theory + error_margin
    lower_bound = prob_theory - error_margin

    # מחפש את כל האינדקסים שבהם הגרף נמצא בתוך גבולות השגיאה
    converged_indices = np.where((cumulative_hit_ratio >= lower_bound) & (cumulative_hit_ratio <= upper_bound))[0]

    if len(converged_indices) > 0:
        first_convergence_idx = converged_indices[0]
        convergence_time_ms = time_axis_ms[first_convergence_idx]
        convergence_deadline = first_convergence_idx + 1
        conv_text = f"{convergence_time_ms:g} ms"
        conv_sub = f"At Deadline #{convergence_deadline}"
    else:
        conv_text = "Not Converged"
        conv_sub = "Increase Mission Time"

    # --- Results Display ---
    st.divider()
    st.subheader("📊 Convergence Results Over Mission Time")

    # יצירת 4 עמודות כדי להכניס את מדד ההתכנסות החדש בולט לעין
    rc1, rc2, rc3, rc4 = st.columns(4)
    rc1.metric("Theoretical Expected ON", f"{prob_theory:.2f}%")
    rc2.metric(f"MC Achieved ON (at {time_axis_ms[-1]:g} ms)", f"{final_mc_ratio:.2f}%",
               delta=f"{final_mc_ratio - prob_theory:.3f}%", delta_color="off")
    rc3.metric("Total Hits / Analyzed Dwells", f"{int(global_cumulative_hits[-1]):,} / {total_attempts_per_step[-1]:,}")
    rc4.metric(f"Time to Converge (±{error_margin}%)", conv_text, conv_sub, delta_color="off")

    # --- Plotly Graph ---
    fig = go.Figure()

    # רצועת השגיאה المותרת (Shaded Area) סביב הקו התיאורטי
    fig.add_hrect(
        y0=lower_bound, y1=upper_bound,
        line_width=0, fillcolor="rgba(255, 51, 102, 0.1)",
        annotation_text=f"±{error_margin}% Tolerance Band",
        annotation_position="top left"
    )

    # Simulated Line (Time-based X-Axis)
    fig.add_trace(go.Scatter(
        x=time_axis_ms,
        y=cumulative_hit_ratio,
        name="Average Simulated Hit Ratio",
        mode="lines+markers",
        line=dict(color='#00CC96', width=2),
        marker=dict(size=4)
    ))

    # Theoretical Line
    fig.add_trace(go.Scatter(
        x=[time_axis_ms[0], time_axis_ms[-1]],
        y=[prob_theory, prob_theory],
        name="Theoretical Truth",
        mode="lines",
        line=dict(color='#FF3366', width=3, dash='dash')
    ))

    # אם הייתה התכנסות, הוספת סמן (נקודה בולטת) על הגרף בנקודת ההתכנסות
    if len(converged_indices) > 0:
        fig.add_trace(go.Scatter(
            x=[convergence_time_ms],
            y=[cumulative_hit_ratio[first_convergence_idx]],
            mode="markers",
            marker=dict(color="yellow", size=12, line=dict(color="black", width=2)),
            name=f"Reached Target (±{error_margin}%)"
        ))

    fig.update_layout(
        title="Hit Ratio (ON Duty Cycle) Convergence Across Mission Time",
        xaxis_title="Mission Progression Time [ms] (Steps = Rx Deadlines)",
        yaxis_title="Cumulative Hit Ratio up to this time [%]",
        yaxis_range=[max(0, prob_theory - (error_margin * 3)), min(100, prob_theory + (error_margin * 3))],
        hovermode="x unified"
    )

    # Setting explicitly to show tick marks exactly at Deadlines
    if num_steps <= 20:
        fig.update_xaxes(tickvals=time_axis_ms)

    st.plotly_chart(fig, use_container_width=True)