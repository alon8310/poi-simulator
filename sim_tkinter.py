import tkinter as tk
from tkinter import ttk, messagebox
import threading
import numpy as np
import pandas as pd


# =========================================================
# פונקציות עזר לבניית הממשק
# =========================================================
def create_labeled_entry(parent, label_text, default_val, r, c, width=12):
    lbl = ttk.Label(parent, text=label_text)
    lbl.grid(row=r, column=c * 2, sticky='w', padx=5, pady=5)
    entry = ttk.Entry(parent, width=width)
    entry.insert(0, str(default_val))
    entry.grid(row=r, column=c * 2 + 1, sticky='w', padx=5, pady=5)
    return lbl, entry


def create_labeled_combo(parent, label_text, values, default_idx, r, c, width=12):
    lbl = ttk.Label(parent, text=label_text)
    lbl.grid(row=r, column=c * 2, sticky='w', padx=5, pady=5)
    combo = ttk.Combobox(parent, values=values, width=width, state="readonly")
    combo.current(default_idx)
    combo.grid(row=r, column=c * 2 + 1, sticky='w', padx=5, pady=5)
    return lbl, combo


# =========================================================
# מחלקת האפליקציה הראשית
# =========================================================
class AutoTunerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("✨ Receiver Auto-Tuner (Optimization Engine)")
        self.root.geometry("1000x700")

        self.is_running = False
        self.build_ui()

    def build_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame,
                  text="כלי זה מחשב את זוגות ה-Dwell וה-Revisit האופטימליים כדי להבטיח גילוי (POI) תחת Max Time נתון.",
                  font=('Arial', 10, 'italic')).pack(anchor='w', pady=(0, 10))

        # --- 1. Goals Setup ---
        goals_frame = ttk.LabelFrame(main_frame, text="🎯 1. Threat & Goal Definition", padding=10)
        goals_frame.pack(fill=tk.X, pady=5)

        _, self.target_poi = create_labeled_entry(goals_frame, "Target POI [%]", 99.0, 0, 0)
        _, self.max_time = create_labeled_entry(goals_frame, "Max Time [ms]", 1000.0, 0, 1)
        _, self.age_in = create_labeled_entry(goals_frame, "Age-In (Hits)", 3, 0, 2)
        _, self.age_out = create_labeled_entry(goals_frame, "Age-Out (Miss)", 1, 0, 3)
        _, self.mc_trials = create_labeled_entry(goals_frame, "Trials per Test", 2000, 0, 4)

        # --- 2. Threat Setup ---
        threat_frame = ttk.LabelFrame(main_frame, text="🔥 2. Threat Configuration", padding=10)
        threat_frame.pack(fill=tk.X, pady=5)

        # תיקון: הוספנו את ה-0 (default_idx) לפני ה-Row וה-Col
        self.lbl_ptype, self.pri_type = create_labeled_combo(threat_frame, "PRI Type",
                                                             ["Fixed", "Jittered", "Staggered", "Custom"], 0, 0, 0)
        self.lbl_pw, self.pw = create_labeled_entry(threat_frame, "PW [ms]", 5.0, 0, 1)
        self.lbl_pri, self.pri = create_labeled_entry(threat_frame, "PRI [ms]", 100.0, 0, 2)
        self.lbl_jit, self.jitter = create_labeled_entry(threat_frame, "Jitter [%]", 10, 0, 3)
        self.lbl_stag, self.stagger = create_labeled_entry(threat_frame, "Stagger Seq", "80,120,100", 0, 4, width=15)
        self.lbl_cpri, self.custom_pri = create_labeled_entry(threat_frame, "PW:PRI Pairs", "5:100, 10:150", 0, 5,
                                                              width=15)

        self.lbl_ftype, self.frame_type = create_labeled_combo(threat_frame, "Framing", ["None", "Regular", "Custom"],
                                                               0, 1, 0)
        self.lbl_fon, self.frame_on = create_labeled_entry(threat_frame, "ON [ms]", 50.0, 1, 1)
        self.lbl_foff, self.frame_off = create_labeled_entry(threat_frame, "OFF [ms]", 150.0, 1, 2)
        self.lbl_cfrm, self.custom_frm = create_labeled_entry(threat_frame, "ON:OFF Pairs", "20:180, 30:270", 1, 3,
                                                              width=15)
        self.lbl_sync, self.sync = create_labeled_combo(threat_frame, "Sync", ["Continuous", "Reset"], 0, 1, 4)

        # Bindings for dynamic UI
        self.pri_type.bind("<<ComboboxSelected>>", self.update_visibility)
        self.frame_type.bind("<<ComboboxSelected>>", self.update_visibility)
        self.update_visibility()

        # --- 3. Run & Progress ---
        control_frame = ttk.Frame(main_frame, padding=10)
        control_frame.pack(fill=tk.X)

        self.run_btn = ttk.Button(control_frame, text="🚀 Run Auto-Tuner", command=self.start_optimization)
        self.run_btn.pack(side=tk.LEFT, padx=5)

        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(control_frame, variable=self.progress_var, maximum=100, length=300)
        self.progress.pack(side=tk.LEFT, padx=15, fill=tk.X, expand=True)

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(control_frame, textvariable=self.status_var, font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=15)

        # --- 4. Results Table ---
        results_frame = ttk.LabelFrame(main_frame, text="📊 Optimization Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ("Dwell [ms]", "Max Revisit [ms]", "Duty Cycle [%]", "Achieved POI [%]")
        self.tree = ttk.Treeview(results_frame, columns=columns, show="headings", height=8)

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor="center", width=150)

        # סגנון מיוחד לשורה המנצחת
        self.tree.tag_configure('best', background='#d4edda')  # צבע ירוק בהיר

        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def update_visibility(self, event=None):
        for w in [self.lbl_pri, self.pri, self.lbl_jit, self.jitter, self.lbl_stag, self.stagger, self.lbl_cpri,
                  self.custom_pri]: w.grid_remove()
        ptype = self.pri_type.get()
        if ptype in ["Fixed", "Jittered"]:
            self.lbl_pri.grid();
            self.pri.grid()
            if ptype == "Jittered": self.lbl_jit.grid(); self.jitter.grid()
        elif ptype == "Staggered":
            self.lbl_stag.grid(); self.stagger.grid()
        elif ptype == "Custom":
            self.lbl_cpri.grid(); self.custom_pri.grid()

        for w in [self.lbl_fon, self.frame_on, self.lbl_foff, self.frame_off, self.lbl_cfrm, self.custom_frm,
                  self.lbl_sync, self.sync]: w.grid_remove()
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

    # =========================================================
    # פיזיקה ולוגיקה פנימית
    # =========================================================
    def start_optimization(self):
        if self.is_running: return
        self.is_running = True
        self.run_btn.config(state=tk.DISABLED)
        self.progress_var.set(0)

        # ניקוי טבלה
        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            # איסוף הנתונים מכל התיבות
            t_type = self.pri_type.get()
            t_data = {"type": t_type, "frame_type": self.frame_type.get(), "sync": self.sync.get(),
                      "pw": float(self.pw.get())}

            if t_type in ["Fixed", "Jittered"]:
                t_data["base_pri"] = float(self.pri.get())
                if t_type == "Jittered": t_data["jitter"] = float(self.jitter.get())
            elif t_type == "Staggered":
                t_data["stagger"] = [float(x.strip()) for x in self.stagger.get().split(",")]
            elif t_type == "Custom":
                t_data["custom_seq"] = [(float(p.split(":")[0].strip()), float(p.split(":")[1].strip())) for p in
                                        self.custom_pri.get().split(",")]

            if t_data["frame_type"] == "Regular":
                t_data["frame_on"] = float(self.frame_on.get())
                t_data["frame_off"] = float(self.frame_off.get())
            elif t_data["frame_type"] == "Custom":
                t_data["frame_seq"] = [(float(p.split(":")[0].strip()), float(p.split(":")[1].strip())) for p in
                                       self.custom_frm.get().split(",")]

            self.opt_params = {
                "target_poi": float(self.target_poi.get()),
                "max_time": float(self.max_time.get()),
                "age_in": int(self.age_in.get()),
                "age_out": int(self.age_out.get()),
                "trials": int(self.mc_trials.get()),
                "t_data": t_data
            }
        except Exception as e:
            messagebox.showerror("Input Error", f"Check your inputs:\n{e}")
            self.reset_ui()
            return

        threading.Thread(target=self.run_optimization_thread, daemon=True).start()

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
            p_idx, w_idx = 0, 0
            valid_windows = [w for w in windows if w[1] >= p_t]

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

    def check_lock(self, dwell, revisit):
        p = self.opt_params
        t_data = p["t_data"]
        max_time = p["max_time"]

        if t_data['type'] == "Staggered":
            internal_period = sum(t_data['stagger'])
        elif t_data['type'] == "Custom":
            internal_period = sum(x[1] for x in t_data['custom_seq'])
        else:
            internal_period = t_data['base_pri']

        if t_data['frame_type'] == "Regular":
            f_period = t_data['frame_on'] + t_data['frame_off']
        elif t_data['frame_type'] == "Custom":
            f_period = sum(f[0] + f[1] for f in t_data['frame_seq'])
        else:
            f_period = 0

        offset_frame = np.random.uniform(0, f_period) if f_period > 0 else 0
        offset_internal = np.random.uniform(0, internal_period) if (
                    t_data['sync'] == "Continuous" or t_data['frame_type'] == "None") else 0

        pulses = self.generate_pulses(t_data, max_time + 50, offset_internal, offset_frame)

        t_curr = np.random.uniform(-dwell, revisit - dwell)
        hits, misses = 0, 0

        while t_curr < max_time:
            d_start, d_end = t_curr, t_curr + dwell
            obs_start, obs_end = max(0, d_start), min(max_time, d_end)

            if obs_start < obs_end:
                hit = any((min(obs_end, pulse[1]) - max(obs_start, pulse[0])) > 0 for pulse in pulses)
                if hit:
                    hits += 1
                    misses = 0
                    if hits >= p["age_in"]: return True
                else:
                    misses += 1
                    if misses >= p["age_out"]: hits = 0
            t_curr += revisit
        return False

    def evaluate_poi(self, dwell, revisit, trials):
        success = sum(1 for _ in range(trials) if self.check_lock(dwell, revisit))
        return (success / trials) * 100.0

    def check_physical_limit(self, trials=1000):
        p = self.opt_params
        t_data = p["t_data"]
        max_time = p["max_time"]

        if t_data['type'] == "Staggered":
            internal_period = sum(t_data['stagger'])
        elif t_data['type'] == "Custom":
            internal_period = sum(x[1] for x in t_data['custom_seq'])
        else:
            internal_period = t_data['base_pri']

        if t_data['frame_type'] == "Regular":
            f_period = t_data['frame_on'] + t_data['frame_off']
        elif t_data['frame_type'] == "Custom":
            f_period = sum(f[0] + f[1] for f in t_data['frame_seq'])
        else:
            f_period = 0

        success = 0
        for _ in range(trials):
            offset_frame = np.random.uniform(0, f_period) if f_period > 0 else 0
            offset_internal = np.random.uniform(0, internal_period) if (
                        t_data['sync'] == "Continuous" or t_data['frame_type'] == "None") else 0
            pulses = self.generate_pulses(t_data, max_time, offset_internal, offset_frame)

            valid_pulses = sum(1 for pulse in pulses if pulse[0] < max_time and pulse[1] > 0)
            if valid_pulses >= p["age_in"]:
                success += 1
        return (success / trials) * 100.0

    def update_status(self, text, progress_val=None):
        self.root.after(0, self.status_var.set, text)
        if progress_val is not None:
            self.root.after(0, self.progress_var.set, progress_val)

    def run_optimization_thread(self):
        p = self.opt_params
        t_data = p["t_data"]

        self.update_status("Step 0: Checking physical pulse emission limits...", 5)
        theoretical_max_poi = self.check_physical_limit(trials=1000)

        if theoretical_max_poi < p["target_poi"]:
            err_msg = f"❌ בלתי אפשרי פיזיקלית! האיום מייצר מספיק פולסים בתוך הזמן המוגדר רק ב-{theoretical_max_poi:.1f}% מהמקרים."
            self.root.after(0, lambda: messagebox.showerror("Physical Limit Reached", err_msg))
            self.root.after(0, self.reset_ui)
            return

        if t_data['type'] == "Custom":
            min_pw = min(x[0] for x in t_data['custom_seq'])
        else:
            min_pw = t_data['pw']

        if t_data['type'] == "Staggered":
            avg_pri = sum(t_data['stagger']) / len(t_data['stagger'])
        elif t_data['type'] == "Custom":
            avg_pri = sum(x[1] for x in t_data['custom_seq']) / len(t_data['custom_seq'])
        else:
            avg_pri = t_data['base_pri']

        candidates = [min_pw, min_pw * 2, avg_pri * 0.25, avg_pri * 0.5, avg_pri]
        dwell_candidates = sorted(list(set([round(d, 2) for d in candidates if d >= min_pw])))

        results = []
        upper_rev_bound = (p["max_time"] / p["age_in"])

        for idx, d_cand in enumerate(dwell_candidates):
            self.update_status(f"Scanning Dwell: {d_cand:.1f} ms... ({idx + 1}/{len(dwell_candidates)})",
                               10 + (idx / len(dwell_candidates)) * 80)

            low_r = d_cand + 0.1
            high_r = upper_rev_bound
            best_rev = None

            # Binary Search
            while (high_r - low_r) > 1.0:
                mid_r = (low_r + high_r) / 2.0
                poi = self.evaluate_poi(d_cand, mid_r, int(p["trials"] / 4))

                if poi >= p["target_poi"]:
                    best_rev = mid_r
                    low_r = mid_r
                else:
                    high_r = mid_r

                    # Fine Validation
            if best_rev is not None:
                fine_poi = self.evaluate_poi(d_cand, best_rev, p["trials"])
                if fine_poi >= p["target_poi"]:
                    duty_cycle = (d_cand / best_rev) * 100.0
                    results.append({"Dwell": d_cand, "Rev": best_rev, "Duty": duty_cycle, "POI": fine_poi})
                else:
                    safe_r = best_rev - 2.0
                    if safe_r > d_cand:
                        fine_poi_safe = self.evaluate_poi(d_cand, safe_r, p["trials"])
                        if fine_poi_safe >= p["target_poi"]:
                            duty_cycle_safe = (d_cand / safe_r) * 100.0
                            results.append(
                                {"Dwell": d_cand, "Rev": safe_r, "Duty": duty_cycle_safe, "POI": fine_poi_safe})

        self.root.after(0, self.display_results, results)

    def display_results(self, results):
        self.progress_var.set(100)
        if not results:
            self.status_var.set("⚠️ Optimization Failed - Strict constraints.")
            messagebox.showwarning("No Results",
                                   "המערכת לא הצליחה למצוא זוגות מתאימים. נסה להוריד את דרישות ה-Age Out או להגדיל Max Time.")
            self.reset_ui()
            return

        self.status_var.set("✅ Optimization Complete!")

        df = pd.DataFrame(results).sort_values(by="Duty", ascending=True)

        for i, row in df.iterrows():
            values = (f"{row['Dwell']:.2f}", f"{row['Rev']:.2f}", f"{row['Duty']:.2f}%", f"{row['POI']:.2f}%")
            if i == df.index[0]:
                self.tree.insert("", tk.END, values=values, tags=('best',))
            else:
                self.tree.insert("", tk.END, values=values)

        self.reset_ui(keep_status=True)

    def reset_ui(self, keep_status=False):
        self.is_running = False
        self.run_btn.config(state=tk.NORMAL)
        if not keep_status:
            self.status_var.set("Ready.")
            self.progress_var.set(0)


if __name__ == "__main__":
    root = tk.Tk()
    app = AutoTunerApp(root)
    root.mainloop()