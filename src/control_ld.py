import sys
import os
import time
import subprocess

# Ensure we can import emulator from your src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.install import *  # Assumes this imports `emulator`

class ControlEmulator:
    def __init__(self):
        self.ld_dir = r"C:\LDPlayer\LDPlayer9"
        self.ld = emulator.LDPlayer(self.ld_dir)
        self.em = self.ld.emulators
        self.list_thread = self.ld.emulators  # Might be dict or list
        self.fb = "com.facebook.katana"
        self.name_to_serial = {}

        # Build a mapping from LD name to ADB serial/device
        for emu in self.em.values() if isinstance(self.em, dict) else self.em:
            # LDPlayer ADB serials are typically in the format 127.0.0.1:5555
            try:
                index = int(getattr(emu, "index", None))  # Get the emulator index
                serial = f"emulator-{5554 + (index * 2)}"  # Map index to ADB serial
                self.name_to_serial[emu.name] = serial
            except (TypeError, ValueError):
                print(f"Warning: No valid index found for LD {emu.name}")
        print("LD name to serial mapping:", self.name_to_serial)

    def _connect_adb(self, serial):
        """Ensure ADB is connected to this serial."""
        result = subprocess.run(["adb", "connect", serial], capture_output=True, text=True)
        if "unable to connect" in result.stdout.lower():
            print(f"Failed to connect to {serial}: {result.stdout}")

    def start_ld(self, name):
        """Start the LD emulator by name."""
        try:
            for emu in self.em.values() if isinstance(self.em, dict) else self.em:
                if emu.name == name:
                    emu.start()
                    time.sleep(5)  # Wait for the emulator to start
                    return
            print(f"No LD found with name {name}")
        except Exception as e:
            print(f"Error starting LD {name}: {e}")

    def quit_ld(self, name):
        """Quit the LD emulator by name."""
        try:
            for emu in self.em.values() if isinstance(self.em, dict) else self.em:
                if emu.name == name:
                    emu.quit()
                    return
            print(f"No LD found with name {name}")
        except Exception as e:
            print(f"Error quitting LD {name}: {e}")

    def sort_window_ld(self):
        """Arrange LD windows."""
        self.ld.sort_window()

    def open_facebook(self, name):
        """Open the Facebook app on the specified LD."""
        serial = self.name_to_serial.get(name, name)
        if not serial:
            print(f"No serial found for {name}")
            return

        self._connect_adb(serial)
        # Unlock screen
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

    def scroll_facebook(self, name, duration_sec=900):
        """Simulate smoother scrolling on Facebook for the specified duration."""
        serial = self.name_to_serial.get(name, name)
        if not serial:
            print(f"No serial found for {name}")
            return

        self._connect_adb(serial)
        start_time = time.time()
        try:
            while time.time() - start_time < duration_sec:
                # Perform a smooth swipe gesture
                subprocess.run([
                    "adb", "-s", serial,
                    "shell", "input", "swipe", "300", "1000", "300", "500", "500"  # Adjusted swipe duration
                ], check=True)
                print(f"Smoothly scrolled Facebook on LD {name}")
                time.sleep(2)  # Slight delay between swipes for smoother experience
        except subprocess.CalledProcessError as e:
            print(f"Failed to scroll on LD {name}: {e}")
        except Exception as e:
            print(f"Unexpected error while scrolling on LD {name}: {e}")

    def is_emulator_connected(self, serial):
        """Check if the emulator with the given serial is connected."""
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        return serial in result.stdout

    def ld_task(self, name):
        serial = self.em.name_to_serial.get(name)
        if not self.is_emulator_connected(serial):
            return