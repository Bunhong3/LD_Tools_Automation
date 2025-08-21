import os
import threading
import tkinter as tk
from tkinter import ttk
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from tkinter.scrolledtext import ScrolledText
from datetime import datetime
import json
import time
import schedule
from pathlib import Path
import subprocess
import shutil
import psutil
import random
import emulator
from emulator import LDPlayer

# Add the parent directory to the Python path
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class ControlEmulator:
    def __init__(self):
        self.ld_dir = r"C:\LDPlayer\LDPlayer9"
        self.ld = emulator.LDPlayer(self.ld_dir)
        self.em = self.ld.emulators
        self.list_thread = self.ld.emulators
        self.fb = "com.facebook.katana"
        self.name_to_serial = {}
        self.boot_delay = 20
        self.task_delay = 10
        self.start_delay = 10
        self.close_delay = 15
        self._build_serial_mapping()

    def _build_serial_mapping(self):
        for emu in self.em.values() if isinstance(self.em, dict) else self.em:
            try:
                index = int(getattr(emu, "index", 0))
                serial = f"emulator-{5554 + (index * 2)}"
                self.name_to_serial[emu.name] = serial
            except Exception as e:
                print(f"Error mapping serial for {emu.name}: {str(e)}")

    def is_ld_running(self, name):
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
            serial = self.name_to_serial.get(name)
            return serial and serial in result.stdout
        except Exception:
            return False

    def _connect_adb(self, serial):
        adb_path = shutil.which("adb")
        if not adb_path:
            possible_paths = [
                r"C:\LDPlayer\LDPlayer4.0\adb.exe",
                r"C:\Program Files\LDPlayer\LDPlayer4.0\adb.exe",
                r"C:\Program Files (x86)\LDPlayer\LDPlayer4.0\adb.exe"
            ]
            adb_path = next((p for p in possible_paths if os.path.exists(p)), None)
        
        if not adb_path:
            raise FileNotFoundError("ADB executable not found. Please install LDPlayer or add adb to PATH.")

        subprocess.run([adb_path, "connect", serial], check=True)

    def start_ld(self, name, delay_between_starts=10):
        try:
            for emu in self.em.values() if isinstance(self.em, dict) else self.em:
                if emu.name == name:
                    emu.start()
                    time.sleep(5)
                    print(f"LD {name} started.")
                    time.sleep(delay_between_starts)
                    
                    # Arrange LD windows in rows after starting
                    self.sort_window_ld()
                    return
            print(f"No LD found with name {name}")
        except Exception as e:
            print(f"Error starting LD {name}: {e}")

    def quit_ld(self, name):
        try:
            for emu in self.em.values() if isinstance(self.em, dict) else self.em:
                if emu.name == name:
                    emu.quit()
                    return
            print(f"No LD found with name {name}")
        except Exception as e:
            print(f"Error quitting LD {name}: {e}")

    def sort_window_ld(self):
        self.ld.sort_window()

    def open_facebook(self, name):
        serial = self.name_to_serial.get(name, name)
        if not serial:
            print(f"No serial found for {name}")
            return

        self._connect_adb(serial)
        subprocess.run(["adb", "-s", serial, "shell", "input", "keyevent", "82"], check=False)

        try:
            subprocess.run([
                "adb", "-s", serial, "shell", "monkey",
                "-p", self.fb,
                "-c", "android.intent.category.LAUNCHER", "1"
            ], check=True)
            print(f"Facebook app launched on LD {name}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to launch Facebook on LD {name}: {e}")
            print(f"Ensure that the emulator with serial {serial} is running and connected to ADB.")

    def scroll_facebook(self, name, duration_sec=900, pause_event=None, running_flag=None):
        serial = self.name_to_serial.get(name, name)
        if not serial:
            print(f"No serial found for {name}")
            return

        self._connect_adb(serial)
        start_time = time.time()
        
        try:
            while time.time() - start_time < duration_sec:
                if running_flag and not running_flag():
                    break
                if pause_event and not pause_event.is_set():
                    time.sleep(0.5)
                    continue
                
                # Adjusted values for smoother scrolling
                scroll_duration = random.uniform(400, 600)  # Swipe duration in ms
                start_y = random.randint(800, 900)         # Start Y-coordinate
                end_y = random.randint(500, 600)           # End Y-coordinate
                
                subprocess.run([
                    "adb", "-s", serial,
                    "shell", "input", "swipe", 
                    "300", str(start_y), 
                    "300", str(end_y), 
                    str(int(scroll_duration))
                ], check=True)
                
                # Shorter and more consistent delay between swipes
                time.sleep(random.uniform(1.5, 2.5))
                
        except Exception as e:
            print(f"Error scrolling on {name}: {str(e)}")

    def is_emulator_connected(self, serial):
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        return serial in result.stdout

    def ld_task(self, name):
        serial = self.name_to_serial.get(name)
        if not self.is_emulator_connected(serial):
            return

class MainWindow():
    def __init__(self, selected_ld_names, running_flag, ld_thread, log_func=print, start_same_time=False):
        self.em = ControlEmulator()
        self.thread_ld = [name for name in selected_ld_names if name in self.em.name_to_serial]
        self.log = log_func
        self.running_flag = running_flag
        self.ld_thread = ld_thread
        self.scroll_duration = 0
        self.start_same_time = start_same_time
        self.pause_event = threading.Event()
        self.pause_event.set()  # Start unpaused

    def check_paused(self):
        """Check if operations should be paused - blocks if paused"""
        while not self.pause_event.is_set() and self.running_flag():
            time.sleep(0.5)
        return not self.running_flag()

    def ld_task_stage(self, name, stage):
        if not self.running_flag():
            return
        
        if self.check_paused():
            return
        
        if stage == "start":
            self.log(f"Starting LD: {name}")
            self.em.start_ld(name, delay_between_starts=self.em.boot_delay)
            time.sleep(self.em.boot_delay)
        elif stage == "facebook":
            self.log(f"Opening Facebook on LD: {name}")
            self.em.open_facebook(name)
        elif stage == "scroll":
            self.log(f"Scrolling Facebook on LD: {name} for {self.scroll_duration // 60} minutes")
            self.em.scroll_facebook(name, duration_sec=self.scroll_duration, 
                                   pause_event=self.pause_event, running_flag=self.running_flag)
        elif stage == "close":
            self.log(f"Closing LD: {name}")
            time.sleep(self.em.close_delay)
            self.em.quit_ld(name)

    def main(self):
        total = len(self.thread_ld)
        self.log(f"Total LDs to process: {total}")

        for batch_start in range(0, total, self.ld_thread):
            if not self.running_flag():
                break

            batch = self.thread_ld[batch_start:batch_start + self.ld_thread]
            self.log(f"Processing batch: {batch}")

            for stage in ["start", "facebook", "scroll", "close"]:
                if not self.running_flag():
                    break

                self.log(f"Stage: {stage.capitalize()}")
                
                if stage == "start" and not self.start_same_time:
                    for name in batch:
                        if not self.running_flag():
                            break
                        self.ld_task_stage(name, stage)
                        time.sleep(self.em.start_delay)
                else:
                    threads = []
                    for name in batch:
                        if not self.running_flag():
                            break
                        t = threading.Thread(target=self.ld_task_stage, args=(name, stage))
                        t.daemon = True
                        t.start()
                        threads.append(t)
                    
                    for t in threads:
                        t.join(timeout=300)  # 5 minute timeout

class CheckboxTreeview(ttk.Treeview):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.checkboxes = {}
        self.tag_configure("checked", background="#e1f5fe")
        self.tag_configure("unchecked", background="white")
        self.tag_configure("active", foreground="green")
        self.tag_configure("inactive", foreground="red")
        self.tag_configure("paused", foreground="orange")
        self.tag_configure("scheduled", foreground="blue")
        self.bind("<Double-1>", self._on_double_click)
        
    def insert(self, parent, index, iid=None, **kwargs):
        item = super().insert(parent, index, iid, **kwargs)
        self.checkboxes[item] = False
        values = kwargs.get('values', [])
        status = values[2] if len(values) > 2 else "Inactive"
        tags = ("unchecked", "active") if status == "Active" else ("unchecked", "inactive")
        self.item(item, tags=tags)
        return item
        
    def _on_double_click(self, event):
        item = self.identify_row(event.y)
        if item:
            self.toggle_checkbox(item)
            
    def toggle_checkbox(self, item):
        self.checkboxes[item] = not self.checkboxes[item]
        current_tags = list(self.item(item, "tags"))
        new_tags = [t for t in current_tags if t not in ("checked", "unchecked")]
        new_tags.append("checked" if self.checkboxes[item] else "unchecked")
        self.item(item, tags=new_tags)
            
    def get_checked_items(self):
        return [item for item, checked in self.checkboxes.items() if checked]

class LDManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LDPlayer Automation Manager")
        self.root.geometry("1100x750")
        self.style = ttkb.Style("cosmo")
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        self.emulator = ControlEmulator()
        self.running_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()  # Start unpaused
        self.schedule_thread = None
        self.schedule_running = False
        self.schedule_settings_file = Path("./config/setting_schedule.json")
        
        # Initialize settings variables
        self.parallel_ld = ttkb.IntVar(value=3)
        self.boot_delay = ttkb.IntVar(value=40)
        self.task_delay = ttkb.IntVar(value=10)
        self.start_delay = ttkb.IntVar(value=10)
        self.close_delay = ttkb.IntVar(value=15)
        self.scroll_duration = ttkb.IntVar(value=5)
        self.schedule_time = ttkb.StringVar(value="09:00")
        self.schedule_daily = ttkb.BooleanVar(value=True)
        self.start_same_time = ttkb.BooleanVar(value=False)
        
        self.setup_ui()
        self.load_settings()
        self.load_schedule_settings()
        self.populate_ld_table()
        self.start_status_refresh()

    def setup_ui(self):
        self.main_container = ttkb.Frame(self.root)
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # Left panel
        self.left_panel = ttkb.Frame(self.main_container)
        self.left_panel.pack(side="left", fill="both", expand=False, padx=5, pady=5)

        self.ld_frame = ttkb.LabelFrame(self.left_panel, text="Available LD Players", bootstyle="primary", padding=10)
        self.ld_frame.pack(fill="both", expand=True)

        self.ld_controls = ttkb.Frame(self.ld_frame)
        self.ld_controls.pack(fill="x", pady=(0, 10))

        self.refresh_btn = ttkb.Button(self.ld_controls, text="Refresh", command=self.refresh_all, bootstyle="info", width=12)
        self.refresh_btn.pack(side="left", padx=2)

        # Update "Select All" button
        self.select_all_btn = ttkb.Button(
            self.ld_controls, 
            text="Select All", 
            command=self.select_all, 
            bootstyle="primary",  # Change to blue
            width=12
        )
        self.select_all_btn.pack(side="left", padx=2)

        self.deselect_all_btn = ttkb.Button(self.ld_controls, text="Deselect All", command=self.deselect_all, bootstyle="danger", width=12)
        self.deselect_all_btn.pack(side="left", padx=2)

        # Table with status column
        self.table_frame = ttkb.Frame(self.ld_frame, bootstyle="light")
        self.table_frame.pack(fill="both", expand=True)

        columns = ("name", "serial", "status")
        self.ld_table = CheckboxTreeview(self.table_frame, columns=columns, show="headings", selectmode="none", height=15)
        
        # Configure columns
        self.ld_table.heading("name", text="LD Name", anchor="w")
        self.ld_table.column("name", width=150, anchor="w")
        
        self.ld_table.heading("serial", text="ADB Serial", anchor="w")
        self.ld_table.column("serial", width=120, anchor="w")
        
        self.ld_table.heading("status", text="Status", anchor="w")
        self.ld_table.column("status", width=80, anchor="w")

        scrollbar = ttkb.Scrollbar(self.table_frame, orient="vertical", command=self.ld_table.yview)
        scrollbar.pack(side="right", fill="y")
        self.ld_table.configure(yscrollcommand=scrollbar.set)
        self.ld_table.pack(fill="both", expand=True, padx=1, pady=1)

        # Right panel
        self.right_panel = ttkb.Frame(self.main_container)
        self.right_panel.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        # Batch operations frame
        self.batch_frame = ttkb.LabelFrame(self.right_panel, text="Batch Operations", bootstyle="primary", padding=10)
        self.batch_frame.pack(fill="x", pady=(0, 10))
        
        batch_btn_frame = ttkb.Frame(self.batch_frame)
        batch_btn_frame.pack(fill="x", padx=5, pady=5)
        
        # Update "Start LDs" button
        self.batch_start_btn = ttkb.Button(
            batch_btn_frame, 
            text="Start LDs", 
            command=self.batch_start, 
            bootstyle="primary",  # Change to blue
            width=15
        )
        self.batch_start_btn.pack(side="left", padx=5)
        
        self.batch_stop_btn = ttkb.Button(batch_btn_frame, text="Stop LDs", command=self.batch_stop, bootstyle="danger", width=15)
        self.batch_stop_btn.pack(side="left", padx=5)

        # Settings frame
        self.settings_frame = ttkb.LabelFrame(self.right_panel, text="Task Settings", bootstyle="primary", padding=10)
        self.settings_frame.pack(fill="x", pady=(0, 10))

        settings_grid = ttkb.Frame(self.settings_frame)
        settings_grid.pack(fill="x", padx=5, pady=5)

        ttkb.Label(settings_grid, text="LDs in Parallel:", bootstyle="dark").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttkb.Entry(settings_grid, textvariable=self.parallel_ld, width=5).grid(row=0, column=1, padx=5, pady=5, sticky="w")

        ttkb.Label(settings_grid, text="Boot Delay (s):", bootstyle="dark").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ttkb.Entry(settings_grid, textvariable=self.boot_delay, width=5).grid(row=0, column=3, padx=5, pady=5, sticky="w")

        ttkb.Label(settings_grid, text="Task Delay (s):", bootstyle="dark").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttkb.Entry(settings_grid, textvariable=self.task_delay, width=5).grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttkb.Label(settings_grid, text="Start Delay (s):", bootstyle="dark").grid(row=1, column=2, padx=5, pady=5, sticky="w")
        ttkb.Entry(settings_grid, textvariable=self.start_delay, width=5).grid(row=1, column=3, padx=5, pady=5, sticky="w")

        ttkb.Label(settings_grid, text="Close Delay (s):", bootstyle="dark").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        ttkb.Entry(settings_grid, textvariable=self.close_delay, width=5).grid(row=2, column=1, padx=5, pady=5, sticky="w")

        ttkb.Label(settings_grid, text="Scroll Duration (min):", bootstyle="dark").grid(row=2, column=2, padx=5, pady=5, sticky="w")
        ttkb.Entry(settings_grid, textvariable=self.scroll_duration, width=5).grid(row=2, column=3, padx=5, pady=5, sticky="w")

        ttkb.Label(settings_grid, text="Start LDs Simultaneously:", bootstyle="dark").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        ttkb.Checkbutton(settings_grid, variable=self.start_same_time, bootstyle="round-toggle").grid(row=3, column=1, padx=5, pady=5, sticky="w")

        self.progress = ttkb.Progressbar(settings_grid, orient="horizontal", mode="determinate", bootstyle="success-striped", length=400)
        self.progress.grid(row=4, column=0, columnspan=4, sticky="ew", padx=5, pady=10)

        # Schedule frame
        self.schedule_frame = ttkb.LabelFrame(self.right_panel, text="Task Scheduling", bootstyle="primary", padding=10)
        self.schedule_frame.pack(fill="x", pady=(0, 10))
        
        schedule_grid = ttkb.Frame(self.schedule_frame)
        schedule_grid.pack(fill="x", padx=5, pady=5)
        
        ttkb.Label(schedule_grid, text="Schedule Time:", bootstyle="dark").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttkb.Entry(schedule_grid, textvariable=self.schedule_time, width=10).grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        ttkb.Checkbutton(schedule_grid, text="Daily", variable=self.schedule_daily, bootstyle="round-toggle").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        
        self.schedule_enable_btn = ttkb.Button(schedule_grid, text="Enable Schedule", command=self.toggle_schedule, bootstyle="info", width=15)
        self.schedule_enable_btn.grid(row=0, column=3, padx=5, pady=5, sticky="e")

        # Control buttons
        self.control_frame = ttkb.Frame(self.right_panel)
        self.control_frame.pack(fill="x", pady=(0, 10))

        self.start_button = ttkb.Button(self.control_frame, text="Start Automation", command=self.start_automation, bootstyle="success", width=15)
        self.start_button.pack(side="left", padx=5)

        self.pause_button = ttkb.Button(self.control_frame, text="Pause", command=self.toggle_pause, bootstyle="warning", width=15, state="disabled")
        self.pause_button.pack(side="left", padx=5)

        self.stop_button = ttkb.Button(self.control_frame, text="Stop Automation", command=self.stop_automation, state="disabled", bootstyle="danger", width=15)
        self.stop_button.pack(side="left", padx=5)

        # Logs
        self.logs_frame = ttkb.LabelFrame(self.right_panel, text="Activity Log", bootstyle="primary", padding=10)
        self.logs_frame.pack(fill="both", expand=True)

        self.logs_text = ScrolledText(self.logs_frame, state="disabled", wrap="word", height=10, font=('Consolas', 10), padx=10, pady=10)
        self.logs_text.pack(fill="both", expand=True)

        # Status bar
        self.status_bar = ttkb.Label(self.root, text="Ready", bootstyle="inverse-dark", padding=(10, 5))
        self.status_bar.pack(fill="x", side="bottom", padx=10, pady=(0, 10))

    def toggle_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_button.config(text="Resume", bootstyle="info")
            self.log("Automation paused")
            
            # Update table to show paused status
            for item in self.ld_table.get_children():
                if self.ld_table.checkboxes[item]:
                    tags = list(self.ld_table.item(item, "tags"))
                    if "paused" not in tags:
                        tags.append("paused")
                    self.ld_table.item(item, tags=tags)
        else:
            self.pause_event.set()
            self.pause_button.config(text="Pause", bootstyle="warning")
            self.log("Automation resumed")
            
            # Remove paused status from table
            for item in self.ld_table.get_children():
                tags = [t for t in self.ld_table.item(item, "tags") if t != "paused"]
                self.ld_table.item(item, tags=tags)

    def refresh_all(self):
        """Refresh both the LD list and their statuses"""
        self.emulator = ControlEmulator()
        self.populate_ld_table()
        self.log("Refreshed LD player list")

    def populate_ld_table(self):
        self.ld_table.delete(*self.ld_table.get_children())
        if not self.emulator.name_to_serial:
            self.log("No available LDs found.")
            return
            
        for name, serial in self.emulator.name_to_serial.items():
            status = "Active" if self.emulator.is_ld_running(name) else "Inactive"
            self.ld_table.insert("", "end", values=(name, serial, status))

    def start_status_refresh(self):
        """Start periodic status refresh every 5 seconds"""
        self.refresh_status()
        self.root.after(5000, self.start_status_refresh)

    def refresh_status(self):
        """Update the status of all LDs in the table"""
        for item in self.ld_table.get_children():
            name = self.ld_table.item(item)["values"][0]
            new_status = "Active" if self.emulator.is_ld_running(name) else "Inactive"

            current_values = list(self.ld_table.item(item)["values"])
            if current_values[2] != new_status:
                current_values[2] = new_status
                self.ld_table.item(item, values=current_values)
                
                current_tags = list(self.ld_table.item(item, "tags"))
                if new_status == "Active":
                    if "inactive" in current_tags:
                        current_tags.remove("inactive")
                    if "active" not in current_tags:
                        current_tags.append("active")
                else:
                    if "active" in current_tags:
                        current_tags.remove("active")
                    if "inactive" not in current_tags:
                        current_tags.append("inactive")
                
                self.ld_table.item(item, tags=current_tags)

    def select_all(self):
        for item in self.ld_table.get_children():
            if not self.ld_table.checkboxes[item]:
                self.ld_table.toggle_checkbox(item)
        self.log("Selected all LD players")

    def deselect_all(self):
        for item in self.ld_table.get_children():
            if self.ld_table.checkboxes[item]:
                self.ld_table.toggle_checkbox(item)
        self.log("Deselected all LD players")

    def log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logs_text.config(state="normal")
        self.logs_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.logs_text.see(tk.END)
        # Limit log size to 100 lines
        lines = self.logs_text.get("1.0", tk.END).count('\n')
        if lines > 100:
            self.logs_text.delete("1.0", f"{lines - 100}.0")
        self.logs_text.config(state="disabled")
        # Update status bar with truncated message if needed
        status_msg = message[:100] + "..." if len(message) > 100 else message
        self.status_bar.config(text=status_msg)

    def save_settings(self):
        config_dir = "./config"
        os.makedirs(config_dir, exist_ok=True)
        settings_path = os.path.join(config_dir, "settings.json")
        settings = {
            "parallel_ld": self.parallel_ld.get(),
            "boot_delay": self.boot_delay.get(),
            "task_delay": self.task_delay.get(),
            "close_delay": self.close_delay.get(),
            "scroll_duration": self.scroll_duration.get(),
            "start_delay": self.start_delay.get(),
            "schedule_time": self.schedule_time.get(),
            "schedule_daily": self.schedule_daily.get(),
            "start_same_time": self.start_same_time.get()
        }
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)

    def load_settings(self):
        config_dir = "./config"
        settings_path = os.path.join(config_dir, "settings.json")
        try:
            if os.path.exists(settings_path):
                with open(settings_path, "r") as f:
                    settings = json.load(f)
                    self.parallel_ld.set(settings.get("parallel_ld", 3))
                    self.boot_delay.set(settings.get("boot_delay", 40))
                    self.task_delay.set(settings.get("task_delay", 10))
                    self.close_delay.set(settings.get("close_delay", 15))
                    self.scroll_duration.set(settings.get("scroll_duration", 5))
                    self.start_delay.set(settings.get("start_delay", 10))
                    self.schedule_time.set(settings.get("schedule_time", "09:00"))
                    self.schedule_daily.set(settings.get("schedule_daily", True))
                    self.start_same_time.set(settings.get("start_same_time", False))
        except (FileNotFoundError, json.JSONDecodeError):
            self.log("Using default settings")

    def load_schedule_settings(self):
        """Load schedule settings from JSON file"""
        try:
            if self.schedule_settings_file.exists():
                with open(self.schedule_settings_file, 'r') as f:
                    settings = json.load(f)
                    self.schedule_time.set(settings.get('time', "09:00"))
                    self.schedule_daily.set(settings.get('daily', True))
                    
                    saved_selected = settings.get('selected_lds', [])
                    for item in self.ld_table.get_children():
                        ld_name = self.ld_table.item(item)['values'][0]
                        if ld_name in saved_selected and not self.ld_table.checkboxes[item]:
                            self.ld_table.toggle_checkbox(item)
                            
        except Exception as e:
            self.log(f"Error loading schedule settings: {str(e)}")

    def save_schedule_settings(self):
        """Save current schedule settings to JSON file"""
        try:
            self.schedule_settings_file.parent.mkdir(parents=True, exist_ok=True)
            selected_lds = [
                self.ld_table.item(item)['values'][0] 
                for item in self.ld_table.get_checked_items()
            ]
            
            settings = {
                'time': self.schedule_time.get(),
                'daily': self.schedule_daily.get(),
                'selected_lds': selected_lds,
                'last_saved': datetime.now().isoformat()
            }
            
            with open(self.schedule_settings_file, 'w') as f:
                json.dump(settings, f, indent=2)
                
        except Exception as e:
            self.log(f"Error saving schedule settings: {str(e)}")

    def start_automation(self):
        selected_items = self.ld_table.get_checked_items()
        selected_ld_names = [self.ld_table.item(item)["values"][0] for item in selected_items]
        if not selected_ld_names:
            Messagebox.show_error("No LDs selected. Please select at least one LD to start automation.", title="Error")
            return

        self.running_event.set()
        self.pause_event.set()  # Ensure unpaused when starting
        self.start_button.config(state="disabled")
        self.pause_button.config(state="normal")
        self.stop_button.config(state="normal")
        self.log(f"Starting automation for {len(selected_ld_names)} LDs")
        self.log(f"Scroll duration set to {self.scroll_duration.get()} minutes.")

        self.progress["maximum"] = len(selected_ld_names)
        self.progress["value"] = 0
        self.opened_ld_names = selected_ld_names

        threading.Thread(target=self.run_automation, args=(selected_ld_names,), daemon=True).start()

    def stop_automation(self):
        if not self.running_event.is_set():
            return
            
        confirm_stop = Messagebox.yesno("Are you sure you want to stop the automation?", title="Confirm")
        if confirm_stop == "No":
            self.log("Stop automation canceled by user.")
            return

        self.running_event.clear()
        self.pause_event.set()  # Ensure unpaused when stopping
        self.start_button.config(state="normal")
        self.pause_button.config(state="disabled")
        self.stop_button.config(state="disabled")
        self.log("Stopping automation...")

        def close_ld_with_delay():
            for name in getattr(self, "opened_ld_names", []):
                self.log(f"Closing LD {name}...")
                self.emulator.quit_ld(name)
                time.sleep(2)
            self.root.after(0, self.log, "Automation stopped by user.")
            self.root.after(0, lambda: self.progress.config(value=0))

        threading.Thread(target=close_ld_with_delay, daemon=True).start()

    def run_automation(self, selected_ld_names):
        try:
            main_window = MainWindow(
                selected_ld_names,
                running_flag=lambda: self.running_event.is_set(),
                ld_thread=self.parallel_ld.get(),
                log_func=lambda msg: self.root.after(0, self.log, msg),
                start_same_time=self.start_same_time.get()
            )
            # Share both pause and running events
            main_window.pause_event = self.pause_event
            main_window.em.boot_delay = self.boot_delay.get()
            main_window.em.start_delay = self.start_delay.get()
            main_window.em.task_delay = self.task_delay.get()
            main_window.em.close_delay = self.close_delay.get()
            main_window.scroll_duration = self.scroll_duration.get() * 60
            main_window.main()
        except Exception as e:
            self.root.after(0, self.log, f"Error: {str(e)}")
        finally:
            self.running_event.clear()
            self.root.after(0, self.start_button.config, {"state": "normal"})
            self.root.after(0, self.pause_button.config, {"state": "disabled"})
            self.root.after(0, self.stop_button.config, {"state": "disabled"})
            self.root.after(0, self.log, "Automation task completed.")

    def batch_start(self):
        selected_items = self.ld_table.get_checked_items()
        if not selected_items:
            Messagebox.show_error("No LDs selected for batch start.", title="Error")
            return
            
        selected_ld_names = [self.ld_table.item(item)["values"][0] for item in selected_items]
        self.log(f"Starting {len(selected_ld_names)} LDs in batch...")
        
        def start_lds():
            if self.start_same_time.get():
                threads = []
                for name in selected_ld_names:
                    try:
                        t = threading.Thread(target=self.emulator.start_ld, args=(name, 0))
                        t.daemon = True
                        t.start()
                        threads.append(t)
                        self.log(f"Starting LD: {name} (simultaneously)")
                    except Exception as e:
                        self.log(f"Error starting LD {name}: {str(e)}")
                
                for t in threads:
                    t.join(timeout=60)
            else:
                for name in selected_ld_names:
                    try:
                        success = self.emulator.start_ld(name, delay_between_starts=self.boot_delay.get())
                        if success:
                            self.log(f"Started LD: {name} (with delay)")
                        else:
                            self.log(f"Failed to start LD: {name}")
                    except Exception as e:
                        self.log(f"Error starting LD {name}: {str(e)}")
                    time.sleep(self.boot_delay.get())
                
        threading.Thread(target=start_lds, daemon=True).start()

    def batch_stop(self):
        selected_items = self.ld_table.get_checked_items()
        if not selected_items:
            Messagebox.show_error("No LDs selected for batch stop.", title="Error")
            return
            
        selected_ld_names = [self.ld_table.item(item)["values"][0] for item in selected_items]
        self.log(f"Stopping {len(selected_ld_names)} LDs in batch...")
        
        def stop_lds():
            if self.start_same_time.get():
                threads = []
                for name in selected_ld_names:
                    try:
                        t = threading.Thread(target=self.emulator.quit_ld, args=(name,))
                        t.daemon = True
                        t.start()
                        threads.append(t)
                        self.log(f"Stopping LD: {name} (simultaneously)")
                    except Exception as e:
                        self.log(f"Error stopping LD {name}: {str(e)}")
                
                for t in threads:
                    t.join(timeout=30)
            else:
                for name in selected_ld_names:
                    try:
                        success = self.emulator.quit_ld(name)
                        if success:
                            self.log(f"Stopped LD: {name}")
                        else:
                            self.log(f"Failed to stop LD: {name}")
                    except Exception as e:
                        self.log(f"Error stopping LD {name}: {str(e)}")
                    time.sleep(2)
                    
        threading.Thread(target=stop_lds, daemon=True).start()

    def toggle_schedule(self):
        if self.schedule_running:
            self.stop_schedule()
        else:
            self.start_schedule()

    def start_schedule(self):
        try:
            datetime.strptime(self.schedule_time.get(), "%H:%M")
        except ValueError:
            Messagebox.show_error("Invalid time format. Please use HH:MM.", title="Error")
            return
            
        selected_items = self.ld_table.get_checked_items()
        if not selected_items:
            Messagebox.show_error(
                "Please select at least one LD Player before scheduling.\n\n"
                "Tip: Double-click LD names to select them.",
                title="No LDs Selected"
            )
            return
            
        self.save_schedule_settings()
        schedule.clear()
        
        schedule_time = self.schedule_time.get()
        if self.schedule_daily.get():
            schedule.every().day.at(schedule_time).do(self.run_scheduled_task)
            self.log(f"Daily schedule set for {schedule_time} (Selected LDs: {len(selected_items)})")
        else:
            schedule.every().day.at(schedule_time).do(self.run_scheduled_task).tag('one_time')
            self.log(f"One-time schedule set for {schedule_time} (Selected LDs: {len(selected_items)})")
            
        self.schedule_running = True
        self.schedule_enable_btn.config(
            text="Disable Schedule", 
            bootstyle="danger",
            command=self.stop_schedule
        )
        
        for item in self.ld_table.get_children():
            tags = list(self.ld_table.item(item, "tags"))
            if self.ld_table.checkboxes[item]:
                if "scheduled" not in tags:
                    tags.append("scheduled")
            self.ld_table.item(item, tags=tags)
        
        if not self.schedule_thread or not self.schedule_thread.is_alive():
            self.schedule_thread = threading.Thread(target=self.run_scheduler, daemon=True)
            self.schedule_thread.start()

    def stop_schedule(self):
        schedule.clear()
        self.schedule_running = False
        self.schedule_enable_btn.config(
            text="Enable Schedule", 
            bootstyle="info",
            command=self.start_schedule
        )
        self.log("Scheduling disabled")
        
        for item in self.ld_table.get_children():
            tags = [t for t in self.ld_table.item(item, "tags") if t != "scheduled"]
            self.ld_table.item(item, tags=tags)

    def run_scheduler(self):
        while self.schedule_running:
            schedule.run_pending()
            time.sleep(1)

    def run_scheduled_task(self):
        if not self.schedule_running:
            return
            
        self.log("Running scheduled task...")
        selected_items = self.ld_table.get_checked_items()
        if not selected_items:
            self.log("No LDs selected for scheduled task.")
            return
            
        selected_ld_names = [self.ld_table.item(item)["values"][0] for item in selected_items]
        self.root.after(0, self.start_automation)
        
        if not self.schedule_daily.get():
            self.root.after(0, self.stop_schedule)

if __name__ == "__main__":
    root = ttkb.Window(themename="cosmo")
    app = LDManagerApp(root)
    
    def on_closing():
        app.save_settings()
        app.running_event.clear()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()