import tkinter as tk
from tkinter import ttk, messagebox
import threading
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


# =========================================================
# פונקציות עזר לבניית הממשק (מחזירות גם את התווית להסתרה)
# =========================================================
def create_labeled_entry(parent, label_text, default_val, r, c, width=10):
    lbl = ttk.Label(parent, text=label_text)
    lbl.grid(row=r, column=c * 2, sticky='w', padx=2, pady=5)
    entry = ttk.Entry(parent, width=width)
    entry.insert(0, str(default_val))
    entry.grid(row=r, column=c * 2 + 1, sticky='w', padx=5, pady=5)
    return lbl, entry


def create_labeled_combo(parent, label_text, values, default_idx, r, c, width=12):
    lbl = ttk.Label(parent, text=label_text)
    lbl.grid(row=r, column=c * 2, sticky='w', padx=2, pady=5)
    combo = ttk.Combobox(parent, values=values, width=width, state="readonly")
    combo.current(default_idx)
    combo.grid(row=r, column=c * 2 + 1, sticky='w', padx=5, pady=5)
    return lbl, combo


# =========================================================
# מחלקת איום (UI ונתונים) - עכשיו עם UI דינאמי
# =========================================================
class ThreatTab:
    def __init__(self, parent_notebook, threat_id):
        self.id = threat_id
        self.frame = ttk.Frame(parent_notebook, padding=10)
        parent_notebook.add(self.frame, text=f"🔥 Threat #{threat_id}")

        # שורה 1: PRI Setup
        self.lbl_ptype, self.pri_type = create_labeled_combo(self.frame, "PRI Type",
                                                             ["Fixed", "Jittered", "Staggered", "Custom"], 0, 0, 0)
        self.lbl_pw, self.pw = create_labeled_entry(self.frame, "PW [ms]", 5.0, 0, 1)

        self.lbl_pri, self.pri = create_labeled_entry(self.frame, "PRI / Base [ms]", 100.0, 0, 2)  # תוקן ל-100 קבוע
        self.lbl_jit, self.jitter = create_labeled_entry(self.frame, "Jitter [%]", 10, 0, 3)
        self.lbl_stag, self.stagger = create_labeled_entry(self.frame, "Stagger Seq", "80,120,100", 0, 4)
        self.lbl_cpri, self.custom_pri = create_labeled_entry(self.frame, "PW:PRI Pairs", "5:100, 10:150", 0, 5, 15)

        # שורה 2: Framing Setup
        self.lbl_ftype, self.frame_type = create_labeled_combo(self.frame, "Framing", ["None", "Regular", "Custom"], 0,
                                                               1, 0)

        self.lbl_fon, self.frame_on = create_labeled_entry(self.frame, "ON [ms]", 50.0, 1, 1)
        self.lbl_foff, self.frame_off = create_labeled_entry(self.frame, "OFF [ms]", 150.0, 1, 2)
        self.lbl_cfrm, self.custom_frm = create_labeled_entry(self.frame, "ON:OFF Pairs", "20:180, 30:270", 1, 3, 15)
        self.lbl_sync, self.sync = create_labeled_combo(self.frame, "Sync", ["Continuous", "Reset"], 0, 1, 4)

        # אירועי שינוי ערך להסתרת שדות
        self.pri_type.bind("<<ComboboxSelected>>", self.update_visibility)
        self.frame_type.bind("<<ComboboxSelected>>", self.update_visibility)

        # הפעלה ראשונית כדי להסתיר את מה שלא צריך
        self.update_visibility()

    def update_visibility(self, event=None):
        # איפוס הסתרה ל-PRI
        for w in [self.lbl_pri, self.pri, self.lbl_jit, self.jitter, self.lbl_stag, self.stagger, self.lbl_cpri,
                  self.custom_pri]:
            w.grid_remove()

        ptype = self.pri_type.get()
        if ptype in ["Fixed", "Jittered"]:
            self.lbl_pri.grid();
            self.pri.grid()
            if ptype == "Jittered":
                self.lbl_jit.grid();
                self.jitter.grid()
        elif ptype == "Staggered":
            self.lbl_stag.grid();
            self.stagger.grid()
        elif ptype == "Custom":
            self.lbl_cpri.grid();
            self.custom_pri.grid()

        # איפוס הסתרה למסגרות
        for w in [self.lbl_fon, self.frame_on, self.lbl_foff, self.frame_off, self.lbl_cfrm, self.custom_frm,
                  self.lbl_sync, self.sync]:
            w.grid_remove()

        ftype = self.frame_type.get()
        if ftype == "Regular":
            self.lbl_fon.grid();
            self.frame_on.grid()
            self.lbl_foff.grid();
            self.frame_off.grid()
            self.lbl_sync.grid();
            self.sync.grid()
        elif ftype == "Custom":
            self.lbl_cfrm.grid();
            self.custom_frm.grid()
            self.lbl_sync.grid();
            self.sync.grid()

    def get_data(self):
        t_type = self.pri_type.get()
        f_type = self.frame_type.get()
        data = {"id": self.id, "type": t_type, "frame_type": f_type, "sync": self.sync.get()}
        data["pw"] = float(self.pw.get())
        if t_type in ["Fixed", "Jittered"]:
            data["base_pri"] = float(self.pri.get())
            if t_type == "Jittered": data["jitter"] = float(self.jitter.get())
        elif t_type == "Staggered":
            data["stagger"] = [float(x.strip()) for x in self.stagger.get().split(",")]
        elif t_type == "Custom":
            data["custom_seq"] = [(float(p.split(":")[0]), float(p.split(":")[1])) for p in
                                  self.custom_pri.get().split(",")]
        if f_type == "Regular":
            data["frame_on"] = float(self.frame_on.get())
            data["frame_off"] = float(self.frame_off.get())
        elif f_type == "Custom":
            data["frame_seq"] = [(float(p.split(":")[0]), float(p.split(":")[1])) for p in
                                 self.custom_frm.get().split(",")]
        return data


# =========================================================
# האפליקציה הראשית (עם UI דינאמי למקלט)
# =========================================================
class POISimulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🛡️ Desktop EW Simulator – Phase Uncertain POI")
        self.root.geometry("1300x850")
        self.threat_tabs = []
        self.is_running = False
        self.build_ui()

    def build_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Receiver Setup ---
        rx_frame = ttk.LabelFrame(main_frame, text="⚙️ Receiver Setup", padding=10)
        rx_frame.pack(fill=tk.X, pady=5)

        self.lbl_rxtype, self.rx_type = create_labeled_combo(rx_frame, "Rx Pattern", ["Fixed", "Custom"], 0, 0, 0)

        self.lbl_rxdwell, self.rx_dwell = create_labeled_entry(rx_frame, "Dwell [ms]", 5.0, 0, 1)
        self.lbl_rxrev, self.rx_rev = create_labeled_entry(rx_frame, "Rev [ms]", 100.0, 0, 2)
        self.lbl_rxcust, self.rx_cust = create_labeled_entry(rx_frame, "Dwell:Rev", "5:100", 0, 3, 12)
        self.lbl_rxdev, self.rx_dev = create_labeled_entry(rx_frame, "Dev [%]", 0.0, 0, 4)

        self.lbl_ovr, self.overlap = create_labeled_entry(rx_frame, "Overlap [ms]", 0.0, 0, 5)
        self.lbl_agin, self.age_in = create_labeled_entry(rx_frame, "Age-In", 1, 0, 6)
        self.lbl_agout, self.age_out = create_labeled_entry(rx_frame, "Age-Out", 1, 0, 7)
        self.lbl_maxt, self.max_time = create_labeled_entry(rx_frame, "Max Time", 1000.0, 0, 8)

        self.lbl_rxfrmtype, self.rx_frm_type = create_labeled_combo(rx_frame, "Rx Framing",
                                                                    ["None", "Regular", "Custom"], 0, 1, 0)

        self.lbl_rxfon, self.rx_fon = create_labeled_entry(rx_frame, "Rx ON [ms]", 50.0, 1, 1)
        self.lbl_rxfoff, self.rx_foff = create_labeled_entry(rx_frame, "Rx OFF [ms]", 150.0, 1, 2)
        self.lbl_rxcustfrm, self.rx_cust_frm = create_labeled_entry(rx_frame, "Rx ON:OFF", "50:150", 1, 3, 12)
        self.lbl_rxsync, self.rx_sync = create_labeled_combo(rx_frame, "Rx Sync", ["Continuous", "Reset"], 0, 1, 4)

        self.lbl_trials, self.mc_trials = create_labeled_entry(rx_frame, "MC Trials", 10000, 1, 6)
        self.lbl_numt, self.num_threats = create_labeled_entry(rx_frame, "Threats", 1, 1, 7)

        ttk.Button(rx_frame, text="Update Threats", command=self.update_threats).grid(row=1, column=16, padx=10)

        # Bindings למקלט
        self.rx_type.bind("<<ComboboxSelected>>", self.update_rx_visibility)
        self.rx_frm_type.bind("<<ComboboxSelected>>", self.update_rx_visibility)
        self.update_rx_visibility()

        # --- Threats Setup ---
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.X, pady=10)
        self.update_threats()

        # --- Run Button & Progress ---
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=5)

        self.run_btn = ttk.Button(control_frame, text="🚀 Run Simulation", command=self.start_simulation)
        self.run_btn.pack(side=tk.LEFT, padx=5)

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(control_frame, textvariable=self.status_var, font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=15)

        # --- Matplotlib Graph ---
        self.fig, self.ax = plt.subplots(figsize=(10, 4))
        self.canvas = FigureCanvasTkAgg(self.fig, master=main_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def update_rx_visibility(self, event=None):
        # טיפול בדפוס בסיס של המקלט
        for w in [self.lbl_rxdwell, self.rx_dwell, self.lbl_rxrev, self.rx_rev, self.lbl_rxcust, self.rx_cust]:
            w.grid_remove()

        if self.rx_type.get() == "Fixed":
            self.lbl_rxdwell.grid();
            self.rx_dwell.grid()
            self.lbl_rxrev.grid();
            self.rx_rev.grid()
        else:
            self.lbl_rxcust.grid();
            self.rx_cust.grid()

        # טיפול במסגרות המקלט
        for w in [self.lbl_rxfon, self.rx_fon, self.lbl_rxfoff, self.rx_foff, self.lbl_rxcustfrm, self.rx_cust_frm,
                  self.lbl_rxsync, self.rx_sync]:
            w.grid_remove()

        ftype = self.rx_frm_type.get()
        if ftype == "Regular":
            self.lbl_rxfon.grid();
            self.rx_fon.grid()
            self.lbl_rxfoff.grid();
            self.rx_foff.grid()
            self.lbl_rxsync.grid();
            self.rx_sync.grid()
        elif ftype == "Custom":
            self.lbl_rxcustfrm.grid();
            self.rx_cust_frm.grid()
            self.lbl_rxsync.grid();
            self.rx_sync.grid()

    def update_threats(self):
        try:
            count = int(self.num_threats.get())
        except:
            return
        for tab in self.threat_tabs: tab.frame.destroy()
        self.threat_tabs.clear()
        for i in range(count): self.threat_tabs.append(ThreatTab(self.notebook, i + 1))

    # =========================================================
    # ליבת הסימולציה (ללא שינוי, זהה לאלגוריתם הקיים)
    # =========================================================
    def start_simulation(self):
        if self.is_running: return
        self.is_running = True
        self.run_btn.config(state=tk.DISABLED)
        self.status_var.set("Simulating... Please wait.")
        try:
            self.sim_params = {
                "rx_type": self.rx_type.get(),
                "rx_dwell": float(self.rx_dwell.get()),
                "rx_rev": float(self.rx_rev.get()),
                "rx_cust": [(float(p.split(":")[0]), float(p.split(":")[1])) for p in self.rx_cust.get().split(",")],
                "rx_dev": float(self.rx_dev.get()),
                "overlap": float(self.overlap.get()),
                "age_in": int(self.age_in.get()),
                "age_out": int(self.age_out.get()),
                "max_time": float(self.max_time.get()),
                "rx_frm_type": self.rx_frm_type.get(),
                "rx_fon": float(self.rx_fon.get()),
                "rx_foff": float(self.rx_foff.get()),
                "rx_cust_frm": [(float(p.split(":")[0]), float(p.split(":")[1])) for p in
                                self.rx_cust_frm.get().split(",")],
                "rx_sync": self.rx_sync.get(),
                "trials": int(self.mc_trials.get()),
                "threats_data": [tab.get_data() for tab in self.threat_tabs]
            }
        except Exception as e:
            messagebox.showerror("Input Error", f"Check your inputs:\n{e}")
            self.is_running = False
            self.run_btn.config(state=tk.NORMAL)
            self.status_var.set("Ready.")
            return

        threading.Thread(target=self.run_monte_carlo, daemon=True).start()

    def generate_pulses(self, th, time_limit, offset_internal, offset_frame):
        windows = []
        if th['frame_type'] == "None":
            windows.append((-999999, 999999))
        else:
            f_seq = [(th['frame_on'], th['frame_off'])] if th['frame_type'] == "Regular" else th['frame_seq']
            f_period = sum(f[0] + f[1] for f in f_seq)
            t_f = offset_frame - (f_period * 2)
            f_idx = 0
            while t_f < time_limit:
                on_t, off_t = f_seq[f_idx]
                windows.append((t_f, t_f + on_t))
                t_f += (on_t + off_t)
                f_idx = (f_idx + 1) % len(f_seq)

        pulses = []

        def get_pw_pri(idx):
            if th['type'] == "Fixed":
                return th['pw'], th['base_pri']
            elif th['type'] == "Jittered":
                return th['pw'], th['base_pri'] * np.random.uniform(1 - th['jitter'] / 100, 1 + th['jitter'] / 100)
            elif th['type'] == "Staggered":
                return th['pw'], th['stagger'][idx % len(th['stagger'])]
            elif th['type'] == "Custom":
                return th['custom_seq'][idx % len(th['custom_seq'])]

        if th['frame_type'] != "None" and th['sync'] == "Reset":
            for w_start, w_end in windows:
                if w_end < 0: continue
                p_t, p_idx = w_start, 0
                while p_t < w_end:
                    pw, pri = get_pw_pri(p_idx)
                    p_end = p_t + pw
                    o_start, o_end = max(w_start, p_t), min(w_end, p_end)
                    if o_start < o_end and o_end >= 0 and o_start < time_limit: pulses.append((o_start, o_end))
                    p_t += pri
                    p_idx += 1
        else:
            if th['type'] == "Staggered":
                int_per = sum(th['stagger'])
            elif th['type'] == "Custom":
                int_per = sum(p[1] for p in th['custom_seq'])
            else:
                int_per = th['base_pri']

            p_t = offset_internal - (int_per * 2)
            p_idx = 0
            valid_windows = [w for w in windows if w[1] >= p_t]
            w_idx = 0

            while p_t < time_limit:
                pw, pri = get_pw_pri(p_idx)
                p_end = p_t + pw
                while w_idx < len(valid_windows) and valid_windows[w_idx][1] < p_t: w_idx += 1
                temp_w = w_idx
                while temp_w < len(valid_windows) and valid_windows[temp_w][0] < p_end:
                    w_start, w_end = valid_windows[temp_w]
                    o_start, o_end = max(w_start, p_t), min(w_end, p_end)
                    if o_start < o_end and o_end >= 0 and o_start < time_limit: pulses.append((o_start, o_end))
                    temp_w += 1
                p_t += pri
                p_idx += 1
        return pulses

    def run_monte_carlo(self):
        p = self.sim_params
        all_trials_results = []
        limit_t = p["max_time"]
        rx_seq = [(p["rx_dwell"], p["rx_rev"])] if p["rx_type"] == "Fixed" else p["rx_cust"]

        for _ in range(p["trials"]):
            all_threats_pulses = []
            for th in p["threats_data"]:
                if th['type'] == "Staggered":
                    int_per = sum(th['stagger'])
                elif th['type'] == "Custom":
                    int_per = sum(x[1] for x in th['custom_seq'])
                else:
                    int_per = th['base_pri']

                if th['frame_type'] == "Regular":
                    f_per = th['frame_on'] + th['frame_off']
                elif th['frame_type'] == "Custom":
                    f_per = sum(f[0] + f[1] for f in th['frame_seq'])
                else:
                    f_per = 0

                off_f = np.random.uniform(0, f_per) if f_per > 0 else 0
                off_i = np.random.uniform(0, int_per) if (
                            th['sync'] == "Continuous" or th['frame_type'] == "None") else 0
                all_threats_pulses.append(self.generate_pulses(th, limit_t + 100, off_i, off_f))

            rx_windows = []
            if p["rx_frm_type"] == "None":
                rx_windows.append((-999999, 999999))
            else:
                rx_f_seq = [(p["rx_fon"], p["rx_foff"])] if p["rx_frm_type"] == "Regular" else p["rx_cust_frm"]
                rx_f_period = sum(f[0] + f[1] for f in rx_f_seq)
                rx_offset_frame = np.random.uniform(0, rx_f_period) if rx_f_period > 0 else 0
                t_f = rx_offset_frame - (rx_f_period * 2)
                f_idx = 0
                while t_f < limit_t:
                    on_t, off_t = rx_f_seq[f_idx]
                    rx_windows.append((t_f, t_f + on_t))
                    t_f += (on_t + off_t)
                    f_idx = (f_idx + 1) % len(rx_f_seq)

            rx_dwells = []

            def get_rx_params(idx):
                d, r = rx_seq[idx % len(rx_seq)]
                if p["rx_dev"] > 0: r = r * np.random.uniform(1 - p["rx_dev"] / 100.0, 1 + p["rx_dev"] / 100.0)
                return d, r

            if p["rx_frm_type"] != "None" and p["rx_sync"] == "Reset":
                for w_start, w_end in rx_windows:
                    if w_end < 0: continue
                    p_t, p_idx = w_start, 0
                    while p_t < w_end:
                        d_val, r_val = get_rx_params(p_idx)
                        d_end_time = p_t + d_val
                        o_start, o_end = max(w_start, p_t), min(w_end, d_end_time)
                        if o_start < o_end and o_end >= 0 and o_start < limit_t: rx_dwells.append((o_start, o_end))
                        p_t += r_val
                        p_idx += 1
            else:
                int_per = sum(x[1] for x in rx_seq)
                p_t = np.random.uniform(0, int_per) - (int_per * 2)
                p_idx = 0
                valid_windows = [w for w in rx_windows if w[1] >= p_t]
                w_idx = 0
                while p_t < limit_t:
                    d_val, r_val = get_rx_params(p_idx)
                    d_end_time = p_t + d_val
                    while w_idx < len(valid_windows) and valid_windows[w_idx][1] < p_t: w_idx += 1
                    temp_w = w_idx
                    while temp_w < len(valid_windows) and valid_windows[temp_w][0] < d_end_time:
                        w_start, w_end = valid_windows[temp_w]
                        o_start, o_end = max(w_start, p_t), min(w_end, d_end_time)
                        if o_start < o_end and o_end >= 0 and o_start < limit_t: rx_dwells.append((o_start, o_end))
                        temp_w += 1
                    p_t += r_val
                    p_idx += 1

            hits = [0] * len(p["threats_data"])
            misses = [0] * len(p["threats_data"])
            is_locked = [False] * len(p["threats_data"])
            lock_times = [None] * len(p["threats_data"])

            for d_start, d_end in rx_dwells:
                obs_start, obs_end = max(0, d_start), min(limit_t, d_end)
                if obs_start >= obs_end: continue

                for i in range(len(p["threats_data"])):
                    if lock_times[i] is not None: continue
                    hit = any((min(obs_end, pulse[1]) - max(obs_start, pulse[0])) >= p["overlap"] for pulse in
                              all_threats_pulses[i])

                    if hit:
                        hits[i] += 1
                        misses[i] = 0
                        if hits[i] >= p["age_in"]:
                            is_locked[i] = True
                            lock_times[i] = obs_end
                    else:
                        if is_locked[i]:
                            misses[i] += 1
                            if misses[i] >= p["age_out"]:
                                is_locked[i] = False
                                hits[i] = 0
                        else:
                            hits[i] = max(0, hits[i] - 1)

                if all(lt is not None for lt in lock_times): break

            all_trials_results.append(lock_times)

        self.root.after(0, self.update_graph, all_trials_results, p["max_time"], p["threats_data"])

    def update_graph(self, all_trials_results, max_analysis_t, threats_data):
        trials = len(all_trials_results)
        time_axis = np.linspace(0, max_analysis_t, 50)
        self.ax.clear()

        combined_lock_times = [min(t for t in res if t is not None) for res in all_trials_results if
                               any(t is not None for t in res)]
        combined_poi_curve = [(sum(1 for ct in combined_lock_times if ct <= t_pt) / trials) * 100 for t_pt in time_axis]
        final_comb_poi = (len(combined_lock_times) / trials) * 100

        self.ax.plot(time_axis, combined_poi_curve, label=f"Combined POI ({final_comb_poi:.1f}%)", color='green',
                     linewidth=3, linestyle='--')

        for i, th in enumerate(threats_data):
            t_times = [res[i] for res in all_trials_results if res[i] is not None]
            final_poi = (len(t_times) / trials) * 100
            poi_curve = [(sum(1 for ct in t_times if ct <= t_pt) / trials) * 100 for t_pt in time_axis]
            self.ax.plot(time_axis, poi_curve, label=f"Threat #{th['id']} ({final_poi:.1f}%)")

        self.ax.set_title(f"Cumulative POI over Time ({trials:,} Trials)")
        self.ax.set_xlabel("Time [ms]")
        self.ax.set_ylabel("POI (%)")
        self.ax.set_ylim(-2, 105)
        self.ax.grid(True, linestyle=':', alpha=0.7)
        self.ax.legend()
        self.canvas.draw()

        self.is_running = False
        self.run_btn.config(state=tk.NORMAL)
        self.status_var.set("✅ Simulation Complete.")


if __name__ == "__main__":
    root = tk.Tk()
    app = POISimulatorApp(root)
    root.mainloop()