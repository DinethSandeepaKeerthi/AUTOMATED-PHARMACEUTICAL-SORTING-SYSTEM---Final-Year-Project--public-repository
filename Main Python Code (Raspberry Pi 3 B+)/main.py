import logging
import os
import threading
import time
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from PIL import Image, ImageTk
import pandas as pd
import serial
import serial.tools.list_ports
import ttkbootstrap as tb  # Use ttkbootstrap instead of standard tkinter

# Setup logging
logging.basicConfig(filename="dispensing.log", level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

# File paths and settings
BIN_FILE = "./bins.csv"
PRESCRIPTION_FOLDER = "./prescriptions"
GCODE_FILE = "./gcode_commands.csv"
LOG_FILE = "./GEN_GCODE.gcode"
BAUD_RATE = 115200

# Global control flags
is_running = False
current_thread = None
SERIAL_PORT = None

# Create main window using ttkbootstrap
root = tb.Window(themename="flatly")  # You can try 'superhero', 'cosmo', etc.
root.title("Medicine Dispensing System")
root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}")
root.attributes("-fullscreen", True)

# Load and set background image
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
bg_image_path = "Background.png"
if os.path.exists(bg_image_path):
    bg_image = Image.open(bg_image_path)
    bg_image = bg_image.resize((screen_width, screen_height), Image.Resampling.LANCZOS)
    bg_photo = ImageTk.PhotoImage(bg_image)
else:
    bg_photo = None

canvas = tk.Canvas(root, width=screen_width, height=screen_height, highlightthickness=0)
canvas.pack(fill="both", expand=True)
if bg_photo:
    canvas.create_image(0, 0, image=bg_photo, anchor="nw")

# Overlay card frame
overlay_width = 700
overlay_height = 440
overlay_x = screen_width // 2 - overlay_width // 2
overlay_y = screen_height // 2 - overlay_height // 2

ui_frame = ttk.Frame(root, style='Card.TFrame')
ui_frame.place(x=overlay_x, y=overlay_y, width=overlay_width, height=overlay_height)
# Main Header
main_header = ttk.Label(ui_frame, text="TAB SORT 1.9", font=("Segoe UI", 20, "bold"))
main_header.grid(row=0, column=0, columnspan=3, pady=(20, 5), padx=20, sticky="ew")

# Sub Header
sub_header = ttk.Label(ui_frame, text="Select Prescription", font=("Arial", 15))
sub_header.grid(row=1, column=0, columnspan=3, pady=(0, 20), padx=20, sticky="ew")

# Listbox with scrollbar
listbox_frame = ttk.Frame(ui_frame)
listbox_frame.grid(row=2, column=0, columnspan=3, padx=20, sticky="nsew")
prescription_listbox = tk.Listbox(listbox_frame, width=40, height=8, font=("Arial", 14), relief="solid", bd=1)
prescription_listbox.pack(side="left", fill="both", expand=True)
scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=prescription_listbox.yview)
scrollbar.pack(side="right", fill="y")
prescription_listbox.config(yscrollcommand=scrollbar.set)

# COM Port
com_label = ttk.Label(ui_frame, text="Select COM Port", font=("Arial", 16, "bold"))
com_label.grid(row=3, column=0, padx=20, pady=(20, 10), sticky="w")

comport_var = tk.StringVar()
comport_combobox = ttk.Combobox(ui_frame, textvariable=comport_var, state="readonly", width=18, font=("Arial", 16))
comport_combobox['values'] = ["Select COM Port"]
comport_combobox.current(0)
comport_combobox.grid(row=3, column=1, padx=20, pady=(20, 10), sticky="w")

# Buttons Frame
button_frame = ttk.Frame(ui_frame)
button_frame.grid(row=4, column=0, columnspan=3, pady=(20, 10))

style = tb.Style()
style.configure('Success.Outline.TButton', font=('Arial', 20, 'bold'))
style.configure('Danger.Outline.TButton', font=('Arial', 20, 'bold'))
style.configure('Secondary.Outline.TButton', font=('Arial', 20, 'bold'))

start_btn = tb.Button(button_frame, text="Start", style="success-outline rounded", command=lambda: start_process())
start_btn.grid(row=0, column=0, padx=(0, 20))

terminate_btn = tb.Button(
    button_frame,
    text="Terminate",
    style="danger-outline rounded",
    command=lambda: terminate_process()
)

terminate_btn.grid(row=0, column=1, padx=(0, 20))

exit_btn = tb.Button(button_frame, text="Exit", style='secondary-outline rounded', command=root.quit)
exit_btn.grid(row=0, column=2)

serial_monitor_btn = tb.Button(
    button_frame,
    text="Serial Monitor",
    style="secondary-outline rounded",
    command=lambda: open_serial_monitor()
)

serial_monitor_btn.grid(row=1, column=1, pady=(10, 0))

# Status Label and Progress Bar
status_label = ttk.Label(ui_frame, text="Waiting for prescriptions...", font=("Arial", 16))
status_label.grid(row=5, column=0, columnspan=3, pady=(20, 10))

progress_var = tk.DoubleVar()
progress_bar = ttk.Progressbar(ui_frame, orient="horizontal", mode="determinate", variable=progress_var)
progress_bar.grid(row=6, column=0, columnspan=3, padx=20, pady=(0, 20), sticky="ew")

ui_frame.columnconfigure((0, 1, 2), weight=1)
ui_frame.rowconfigure(1, weight=1)


# Serial Monitor Support
def open_serial_monitor():
    port = comport_combobox.get()
    if port == "Select COM Port":
        messagebox.showwarning("Warning", "Please select a valid COM port before opening Serial Monitor.")
        return
    SerialMonitorWindow(root, port)


class SerialMonitorWindow(tk.Toplevel):
    def __init__(self, master, port):
        super().__init__(master)
        self.title("Serial Monitor")
        self.geometry("600x400")
        self.resizable(False, False)
        self.port = port
        self.ser = None
        self.monitor_running = False

        self.protocol("WM_DELETE_WINDOW", self.close_monitor)

        self.text_area = ScrolledText(self, wrap=tk.WORD, font=("Courier", 12), state="disabled")
        self.text_area.pack(expand=True, fill="both", padx=10, pady=10)

        self.btn_frame = ttk.Frame(self)
        self.btn_frame.pack(pady=(0, 10))

        self.start_btn = tb.Button(self.btn_frame, text="Start", style="success-outline", command=self.start_monitor)
        self.start_btn.grid(row=0, column=0, padx=5)

        self.stop_btn = tb.Button(self.btn_frame, text="Stop", style="danger-outline", command=self.stop_monitor)
        self.stop_btn.grid(row=0, column=1, padx=5)

    def start_monitor(self):
        if not self.monitor_running:
            try:
                self.ser = serial.Serial(self.port, BAUD_RATE, timeout=1)
                self.monitor_running = True
                self.thread = threading.Thread(target=self.read_serial)
                self.thread.daemon = True
                self.thread.start()
                self.write_text(f"Monitoring started on {self.port}\n")
            except Exception as e:
                messagebox.showerror("Serial Error", f"Failed to open serial port: {e}")

    def stop_monitor(self):
        self.monitor_running = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.write_text(f"Monitoring stopped.\n")

    def close_monitor(self):
        self.stop_monitor()
        self.destroy()

    def read_serial(self):
        while self.monitor_running:
            if self.ser.in_waiting:
                try:
                    line = self.ser.readline().decode().strip()
                    self.write_text(line + "\n")
                except Exception as e:
                    self.write_text(f"[Error] {e}\n")
            time.sleep(0.1)

    def write_text(self, text):
        self.text_area.configure(state="normal")
        self.text_area.insert(tk.END, text)
        self.text_area.see(tk.END)
        self.text_area.configure(state="disabled")


# Helper Functions
def update_prescription_list():
    prescription_listbox.delete(0, tk.END)
    if not os.path.exists(PRESCRIPTION_FOLDER):
        os.makedirs(PRESCRIPTION_FOLDER)
    for file in os.listdir(PRESCRIPTION_FOLDER):
        if file.endswith(".txt"):
            prescription_listbox.insert(tk.END, file)


# FOR THE US IN WINDOWS
#def refresh_com_ports():
    #ports = serial.tools.list_ports.comports()
    #port_list = [port.device for port in ports]
    #dummy_ports = ["COM1", "COM2", "COM3", "COM4"]
    #port_list.extend(dummy_ports)
    #comport_combobox['values'] = ["Select COM Port"] + port_list
    #comport_combobox.current(0)


# FOR THE US IN RASPBIAN
def refresh_com_ports():
    ports = serial.tools.list_ports.comports()
    port_list = [port.device for port in ports]
    # Remove dummy ports like "COM1", "COM2" for Raspberry Pi
    comport_combobox['values'] = ["Select COM Port"] + port_list
    comport_combobox.current(0)


def send_gcode_from_file():
    global SERIAL_PORT, is_running
    SERIAL_PORT = comport_var.get()
    if SERIAL_PORT == "Select COM Port" or SERIAL_PORT == "":
        messagebox.showwarning("Warning", "Please select a valid COM port before sending G-code.")
        logging.warning("No COM port selected. Cannot send G-code.")
        return False

    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2) as ser:
            time.sleep(2)  # Allow GRBL to initialize
            ser.reset_input_buffer()

            # Wake up GRBL
            ser.write(b"\n")
            time.sleep(0.5)
            welcome = ser.readline().decode().strip()
            logging.info(f"[GRBL] Welcome: {welcome}")

            ser.write(b"$X\n")
            time.sleep(0.5)
            response = ser.readline().decode().strip()
            logging.info(f"[Unlock Response] {response}")

            with open(LOG_FILE, "r") as log_file:
                for line in log_file:
                    if not is_running:
                        logging.info("Dispensing process terminated by user.")
                        return False

                    line = line.strip()
                    if not line:
                        continue

                    ser.write((line + "\n").encode())
                    logging.info(f"[Sent] {line}")

                    ok_received = False
                    timeout_seconds = 750
                    start_time = time.time()

                    while (time.time() - start_time) < timeout_seconds:
                        if not is_running:
                            logging.info("Dispensing process interrupted during G-code transmission.")
                            return False

                        response = ser.readline().decode().strip()
                        if response:
                            logging.info(f"[Received] {response}")
                        if response.lower() == "ok":
                            ok_received = True
                            break
                        elif response.lower().startswith("error"):
                            logging.error(f"GRBL returned error: {response}")
                            messagebox.showerror("GRBL Error",
                                                 f"GRBL returned an error: {response}\nProcess will be terminated.")
                            terminate_process()
                            return False

                        time.sleep(0.1)

                    if not ok_received:
                        logging.error("GRBL did not respond with 'ok' within 10 seconds.")
                        messagebox.showwarning(
                            "GRBL Not Responding",
                            "GRBL did not respond within 10 seconds.\nDispensing process will be terminated."
                        )
                        terminate_process()
                        return False

        messagebox.showinfo("Success", "G-code successfully sent.")
        return True

    except Exception as e:
        logging.error(f"Error communicating with Arduino: {e}")
        messagebox.showerror("Communication Error", f"Error communicating with Arduino: {e}")
        terminate_process()
        return False

def save_gcode_to_log(gcode_sequence):
    try:
        with open(LOG_FILE, "w") as log_file:
            log_file.write("\n".join(gcode_sequence))
    except Exception as e:
        logging.error(f"Error writing to log file: {e}")


def load_fixed_gcodes(quan, angle_index=0):
    try:
        gcode_df = pd.read_csv(GCODE_FILE)
        gcode_list = []

        angles = [1, 249, 449, 748]  # Define your angle steps here
        angle_to_use = angles[angle_index % len(angles)]  # Cycle through angles

        for idx, row in gcode_df.iterrows():
            cmd = str(row["command"]).strip()
            func = str(row["function"]).strip() if "function" in row else ""

            # Replace M211 P000 with M211 P<quan>
            if cmd.startswith("M211 P"):
                if quan is not None:
                    cmd = f"M211 P{quan}"
                    logging.info(f"Replaced M211 command with: {cmd} ({func})")
                else:
                    logging.warning("Quantity not provided. M211 command left unchanged.")

            # Replace M3 with M3 S<angle>
            if cmd.startswith("M3 S"):
                cmd = f"M3 S{angle_to_use}"
                logging.info(f"Replaced M3 command with: {cmd} ({func})")

            gcode_list.append((cmd, func))

        return gcode_list

    except Exception as e:
        messagebox.showinfo("Info", f"Error reading gcode_commands.csv:\n{e}")
        logging.error(f"Error reading gcode_commands.csv: {e}")
        return []


def generate_gcode_sequence(g_code, quantity, angle_index):
    gcode_sequence = ["G0G21G90X0Y0Z0F1000", g_code]  # Initial G-code setup
    fixed_gcodes = load_fixed_gcodes(quantity, angle_index)
    gcode_commands_only = [cmd for cmd, func in fixed_gcodes]
    gcode_sequence.extend(gcode_commands_only)
    return gcode_sequence


def get_medicine_gcode(medicine_id):
    try:
        bins_df = pd.read_csv(BIN_FILE)
        row = bins_df[bins_df["Medicine_ID"] == medicine_id]
        if not row.empty:
            return row.iloc[0]["GCODE"]  # Change from X, Y to GCODE
    except Exception as e:
        logging.error(f"Error reading bins.csv: {e}")
    return None


def get_medicine_name(medicine_id):
    try:
        bins_df = pd.read_csv(BIN_FILE)
        row = bins_df[bins_df["Medicine_ID"] == medicine_id]
        if not row.empty:
            return row.iloc[0]["Medicine_Name"]  # Change from X, Y to GCODE
    except Exception as e:
        logging.error(f"Error reading bins.csv: {e}")
    return None


def display_summary(summary):
    messagebox.showinfo("Dispensing Summary", "\n".join(summary) if summary else "No medicines dispensed.")
    status_label.config(text="Done")


def load_final_gcodes():
    final_gcodes = []
    final_gcode_path = "final_gcode.csv"
    if not os.path.exists(final_gcode_path):
        logging.warning(f"{final_gcode_path} not found. Skipping final G-code append.")
        return final_gcodes
    try:
        final_df = pd.read_csv(final_gcode_path)
        for idx, row in final_df.iterrows():
            cmd = str(row["command"]).strip()
            if cmd:
                final_gcodes.append(cmd)
    except Exception as e:
        logging.error(f"Error reading {final_gcode_path}: {e}")
    return final_gcodes


def process_prescription(file_path):
    global is_running
    summary = []
    gcode_sequence = []
    angle_index = 0
    try:
        with open(file_path, "r") as file:
            lines = file.readlines()
            total_lines = len(lines)
            for idx, line in enumerate(lines):
                if not is_running:
                    break
                parts = line.strip().split(",")
                if len(parts) == 2:
                    medicine_id, quantity = parts
                    g_code = get_medicine_gcode(medicine_id)
                    if g_code is not None:
                        gcode_sequence.extend(generate_gcode_sequence(g_code, quantity, angle_index))
                        medicine_name = get_medicine_name(medicine_id)
                        summary.append(f"Dispensed {quantity} of {medicine_name} (ID: {medicine_id})")
                        angle_index += 1  # Increment for next tablet set
                progress = ((idx + 1) / total_lines) * 100
                progress_var.set(progress)
    except Exception as e:
        logging.error(f"Error processing prescription: {e}")
        terminate_process()
        return

    if is_running:
        # Append final gcode commands before saving
        final_gcodes = load_final_gcodes()
        gcode_sequence.extend(final_gcodes)

        save_gcode_to_log(gcode_sequence)

        success = send_gcode_from_file()
        if success:
            display_summary(summary)
        else:
            root.after(0, lambda: status_label.config(text="Dispensing aborted or failed."))

    else:
        root.after(0, lambda: status_label.config(text="Dispensing aborted or terminated by user."))

    is_running = False
    update_prescription_list()
    prescription_listbox.selection_clear(0, tk.END)
    progress_var.set(0)


def start_process():
    global is_running, current_thread
    selected = prescription_listbox.get(tk.ACTIVE)
    port = comport_combobox.get()
    if not selected or port == "Select COM Port":
        messagebox.showwarning("Warning", "Please select a prescription and a COM port before starting.")
        return

    if is_running:
        messagebox.showinfo("Info", "Process already running.")
        return

    file_path = os.path.join(PRESCRIPTION_FOLDER, selected)
    if not os.path.isfile(file_path):
        messagebox.showerror("Error", f"Prescription file not found: {selected}")
        return

    is_running = True
    status_label.config(text=f"Processing prescription: {selected}")
    logging.info(f"Starting dispensing process for {selected}")

    current_thread = threading.Thread(target=process_prescription, args=(file_path,))
    current_thread.daemon = True
    current_thread.start()


def terminate_process():
    global is_running
    if not is_running:
        messagebox.showinfo("Info", "No dispensing process running.")
        return

    if messagebox.askyesno("Confirm Termination", "Are you sure you want to terminate the dispensing process?"):
        is_running = False
        status_label.config(text="Dispensing terminated.")
        progress_var.set(0)
        logging.info("User terminated the dispensing process.")
    else:
        status_label.config(text="Termination canceled.")


def on_exit():
    global is_running, current_thread
    if is_running:
        if messagebox.askyesno("Exit", "Dispensing is in progress. Do you want to terminate and exit?"):
            is_running = False
            if current_thread is not None:
                if current_thread.is_alive():
                    current_thread.join()
            root.destroy()
    else:
        root.destroy()


# Update the root window protocol to call `on_exit` on window close
root.protocol("WM_DELETE_WINDOW", on_exit)


# Refresh listbox and COM ports before GUI launches
update_prescription_list()
refresh_com_ports()


# Run the application
root.mainloop()
