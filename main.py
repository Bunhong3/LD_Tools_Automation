from src.install import *
import os

class MainWindow():
    def __init__(self, selected_ld_names, running_flag, ld_thread, log_func=print):
        self.em = ControlEmulator()
        all_names = [em.name for em in self.em.list_thread.values()] if isinstance(self.em.list_thread, dict) else [em.name for em in self.em.list_thread]
        self.thread_ld = list(set(name for name in all_names if name in self.em.name_to_serial and name in selected_ld_names))
        self.log = log_func
        self.running_flag = running_flag
        self.ld_thread = ld_thread
        self.scroll_duration = 0

    def ld_task_stage(self, name, stage):
        if stage == "start":
            self.log(f"Starting LD with name: {name}")
            self.em.start_ld(name, delay_between_starts=self.em.boot_delay)  # Pass the delay
            self.em.sort_window_ld()
            time.sleep(self.em.boot_delay)
        elif stage == "facebook":
            self.log(f"Opening Facebook on LD {name}")
            self.em.open_facebook(name)
            time.sleep(self.em.task_delay)
        elif stage == "scroll":
            self.log(f"Scrolling Facebook on LD {name} for {self.scroll_duration // 60} minutes")
            self.em.scroll_facebook(name, duration_sec=self.scroll_duration)
        elif stage == "close":
            self.log(f"Closing LD {name} after {self.em.close_delay}s delay...")
            time.sleep(self.em.close_delay)
            self.em.quit_ld(name)

    def main(self):
        total = len(self.thread_ld)
        self.log(f"Total LDs to process: {total}")

        for batch_start in range(0, total, self.ld_thread):
            if not self.running_flag():
                break

            batch = self.thread_ld[batch_start:batch_start + self.ld_thread]
            batch = list(set(batch))

            for stage in ["start", "facebook", "scroll", "close"]:
                self.log(f"Stage: {stage.capitalize()} for batch {batch}")
                
                if stage == "start":
                    # Sequentially start LDs with delay
                    for name in batch:
                        if not self.running_flag():
                            break
                        self.ld_task_stage(name, stage)
                        time.sleep(self.em.start_delay)  # Delay between starting each LD
                else:
                    # Use threads for other stages
                    threads = []
                    for name in batch:
                        if not self.running_flag():
                            break
                        t = threading.Thread(target=self.ld_task_stage, args=(name, stage))
                        t.start()
                        threads.append(t)
                    for t in threads:
                        t.join()

class LDManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LDPlayer Automation Manager")
        self.root.geometry("800x600")
        self.style = ttkb.Style("cosmo")

        self.emulator = ControlEmulator()

        # LD List Frame
        self.ld_frame = ttkb.LabelFrame(root, text="Available LDs", bootstyle="primary")
        self.ld_frame.pack(fill="x", padx=10, pady=5)

        self.ld_list_frame = ttkb.Frame(self.ld_frame)
        self.ld_list_frame.pack(fill="x", padx=5, pady=5)

        self.ld_list_scrollbar = ttkb.Scrollbar(self.ld_list_frame, orient="vertical")
        self.ld_list_scrollbar.pack(side="right", fill="y")

        self.ld_list = tk.Listbox(
            self.ld_list_frame,
            height=10,
            selectmode="multiple",
            yscrollcommand=self.ld_list_scrollbar.set
        )
        self.ld_list.pack(side="left", fill="x", expand=True)

        self.ld_list_scrollbar.config(command=self.ld_list.yview)
        self.populate_ld_list()

        # Task Settings Frame
        self.settings_frame = ttkb.LabelFrame(root, text="Task Settings", bootstyle="primary")
        self.settings_frame.pack(fill="x", padx=10, pady=5)

        # Row 0: LDs in Parallel, Boot Delay, and Task Delay
        ttkb.Label(self.settings_frame, text="LDs in Parallel:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.parallel_ld = tk.IntVar(value=3)
        ttkb.Entry(self.settings_frame, textvariable=self.parallel_ld, width=5).grid(row=0, column=1, padx=5, pady=5)

        ttkb.Label(self.settings_frame, text="Boot Delay (s):").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.boot_delay = tk.IntVar(value=40)
        ttkb.Entry(self.settings_frame, textvariable=self.boot_delay, width=5).grid(row=0, column=3, padx=5, pady=5)

        ttkb.Label(self.settings_frame, text="Task Delay (s):").grid(row=0, column=4, padx=5, pady=5, sticky="w")
        self.task_delay = tk.IntVar(value=10)
        ttkb.Entry(self.settings_frame, textvariable=self.task_delay, width=5).grid(row=0, column=5, padx=5, pady=5)

        # Row 0: Add Delay Between Starts
        ttkb.Label(self.settings_frame, text="Delay Between Starts (s):").grid(row=0, column=6, padx=5, pady=5, sticky="w")
        self.start_delay = tk.IntVar(value=10)
        ttkb.Entry(self.settings_frame, textvariable=self.start_delay, width=5).grid(row=0, column=7, padx=5, pady=5)

        # Row 1: Close Delay, Scroll Duration, and Progress Bar
        ttkb.Label(self.settings_frame, text="Close Delay (s):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.close_delay = tk.IntVar(value=15)
        ttkb.Entry(self.settings_frame, textvariable=self.close_delay, width=5).grid(row=1, column=1, padx=5, pady=5)

        ttkb.Label(self.settings_frame, text="Scroll Duration (min):").grid(row=1, column=2, padx=5, pady=5, sticky="w")
        self.scroll_duration = tk.IntVar(value=5)
        ttkb.Entry(self.settings_frame, textvariable=self.scroll_duration, width=5).grid(row=1, column=3, padx=5, pady=5)

        self.progress = ttkb.Progressbar(
            self.settings_frame,
            orient="horizontal",
            mode="determinate",
            bootstyle="success-striped"
        )
        self.progress.grid(row=1, column=4, columnspan=2, padx=5, pady=5, sticky="ew")

        # Control Buttons
        self.control_frame = ttkb.Frame(root)
        self.control_frame.pack(fill="x", padx=10, pady=5)

        self.start_button = ttkb.Button(self.control_frame, text="Start Automation", command=self.start_automation, bootstyle="success")
        self.start_button.pack(side="left", padx=5, pady=5)

        self.stop_button = ttkb.Button(self.control_frame, text="Stop Automation", command=self.stop_automation, state="disabled", bootstyle="danger")
        self.stop_button.pack(side="left", padx=5, pady=5)

        # Logs Frame
        self.logs_frame = ttkb.LabelFrame(root, text="Logs", bootstyle="primary")
        self.logs_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.logs_text = ScrolledText(self.logs_frame, state="disabled", wrap="word")
        self.logs_text.pack(fill="both", expand=True, padx=5, pady=5)

        self.automation_thread = None
        self.running = False
        self.load_settings()

    def populate_ld_list(self):
        """Populate the LD list with available LDs."""
        self.ld_list.delete(0, tk.END)
        if not self.emulator.name_to_serial:
            self.log("No available LDs found.")
            return

        for name, serial in self.emulator.name_to_serial.items():
            self.ld_list.insert(tk.END, f"{name} ({serial})")

    def log(self, message):
        """Log a message to the logs text widget."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logs_text.config(state="normal")
        self.logs_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.logs_text.see(tk.END)

        # Limit log entries to the last 100 lines
        lines = self.logs_text.get("1.0", tk.END).splitlines()
        if len(lines) > 100:
            self.logs_text.delete("1.0", f"{len(lines) - 100}.0")

        self.logs_text.config(state="disabled")

    def save_settings(self):
        """Save settings to the config/settings.json file."""
        config_dir = "./src/config"
        os.makedirs(config_dir, exist_ok=True)  # Ensure the config folder exists
        settings_path = os.path.join(config_dir, "settings.json")

        settings = {
            "parallel_ld": self.parallel_ld.get(),
            "boot_delay": self.boot_delay.get(),
            "task_delay": self.task_delay.get(),
            "close_delay": self.close_delay.get(),
            "scroll_duration": self.scroll_duration.get(),
            "start_delay": self.start_delay.get()  # Add start_delay
        }
        with open(settings_path, "w") as f:
            json.dump(settings, f)

    def load_settings(self):
        """Load settings from the config/settings.json file."""
        config_dir = "./src/config"
        settings_path = os.path.join(config_dir, "settings.json")

        try:
            with open(settings_path, "r") as f:
                settings = json.load(f)
                self.parallel_ld.set(settings.get("parallel_ld", 2))
                self.boot_delay.set(settings.get("boot_delay", 5))
                self.task_delay.set(settings.get("task_delay", 5))
                self.close_delay.set(settings.get("close_delay", 5))
                self.scroll_duration.set(settings.get("scroll_duration", 5))
                self.start_delay.set(settings.get("start_delay", 0))  # Load start_delay
        except (FileNotFoundError, json.JSONDecodeError):
            self.log("Settings file not found or corrupted. Using default settings.")
            self.parallel_ld.set(2)
            self.boot_delay.set(5)
            self.task_delay.set(5)
            self.close_delay.set(5)
            self.scroll_duration.set(5)
            self.start_delay.set(0)  # Default value for start_delay

    def start_automation(self):
        """Start the automation process."""
        selected_indices = self.ld_list.curselection()
        selected_ld_names = [self.ld_list.get(i).split(" (")[0] for i in selected_indices]

        if not selected_ld_names:
            Messagebox.show_error("No LDs selected. Please select at least one LD to start automation.", title="Error")
            self.start_button.config(state="normal")  # Re-enable the button
            return

        self.running = True
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.log(f"Starting automation for LDs: {', '.join(selected_ld_names)}")
        self.log(f"Scroll duration set to {self.scroll_duration.get()} minutes.")

        def running_flag():
            return self.running

        self.progress["maximum"] = len(selected_ld_names)
        self.progress["value"] = 0

        self.automation_thread = threading.Thread(
            target=self.run_automation,
            args=(selected_ld_names, running_flag)
        )
        self.automation_thread.start()

    def stop_automation(self):
        if not Messagebox.yesno("Are you sure you want to stop the automation?", title="Confirm"):
            return
        self.running = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.log("Stopping automation...")

    def run_automation(self, selected_ld_names, running_flag):
        """Run the automation process."""
        try:
            main_window = MainWindow(
                selected_ld_names,
                running_flag,
                self.parallel_ld.get(),
                log_func=lambda msg: self.root.after(0, self.log, msg)
            )
            main_window.em.boot_delay = self.boot_delay.get()
            main_window.em.start_delay = self.start_delay.get()  # Pass the delay
            main_window.em.task_delay = self.task_delay.get()
            main_window.em.close_delay = self.close_delay.get()
            main_window.scroll_duration = self.scroll_duration.get() * 60
            main_window.main()
        except Exception as e:
            self.root.after(0, self.log, f"Error: {e}")
        finally:
            self.running = False
            self.root.after(0, self.start_button.config, {"state": "normal"})
            self.root.after(0, self.stop_button.config, {"state": "disabled"})
            self.root.after(0, self.log, "Automation finished.")
            self.root.after(0, self.progress.stop)


class YourClassName:
    def __init__(self, em):
        self.em = em
        self.all_names = []

        # Safely collect all thread names
        if isinstance(self.em.list_thread, dict):
            self.all_names = [thread.name for thread in self.em.list_thread.values()]
        elif isinstance(self.em.list_thread, list):
            self.all_names = [thread.name for thread in self.em.list_thread]

        print("All Thread Names:", self.all_names)

    def setup_ui(self):
        """Placeholder for UI setup."""
        print("Setting up UI...")

    def example_method(self):
        """Example method."""
        print("Example method running...")


# Example usage
if __name__ == "__main__":
    root = ttkb.Window(themename="cosmo")
    app = LDManagerApp(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.save_settings(), root.destroy()))
    root.mainloop()

    # Mock example for testing
    class ThreadMock:
        def __init__(self, name):
            self.name = name

    em_mock = type("EmMock", (), {})()
    em_mock.list_thread = {
        1: ThreadMock("Thread A"),
        2: ThreadMock("Thread B")
    }

    app = YourClassName(em_mock)
