import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import paho.mqtt.client as mqtt
import subprocess
import threading
import os
import sys
import time
from datetime import datetime
import io
import signal

# Fix encoding issues
if sys.stdout.encoding != 'UTF-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'UTF-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

if os.name == 'nt':
    os.system('chcp 65001 > nul')

# ========== CONSTANTS ==========
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
LED_TOPIC = "/home/led"
FAN_TOPIC = "/home/fan"
TEMP_TOPIC = "/home/temp"
HUMIDITY_TOPIC = "/home/humidity"

# Color Scheme
BG_COLOR = "#121212"
FG_COLOR = "#E0E0E0"
ACCENT_COLOR = "#BB86FC"
ENTRY_BG = "#FFFFFF"
ENTRY_FG = "#000000"

# Fonts
TITLE_FONT = ("Segoe UI", 24, "bold")
HEADER_FONT = ("Segoe UI", 16, "bold")
BODY_FONT = ("Segoe UI", 12)
SMALL_FONT = ("Segoe UI", 10)
MONO_FONT = ("Consolas", 10)

# Image Sizes
LED_IMG_SIZE = (60, 60)
FAN_IMG_SIZE = (60, 60)
HOME_IMG_SIZE = (200, 200)

# ========== GLOBALS ==========
# Old (broken):
# client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)

# New (working):
client = mqtt.Client(
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    protocol=mqtt.MQTTv5  # or mqtt.MQTTv311
)

voice_process = None
voice_control_active = False
voice_thread = None
ignore_initial_messages = True
last_update_time = "Never"
fan_slider_moving = False

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def update_timestamp():
    global last_update_time
    last_update_time = datetime.now().strftime("%H:%M:%S")
    status_bar.config(text=f"Last update: {last_update_time} | Connected to {MQTT_BROKER}")

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print("Connected to MQTT broker!")
        client.subscribe([(LED_TOPIC, 0), (FAN_TOPIC, 0), (TEMP_TOPIC, 0), (HUMIDITY_TOPIC, 0)])
        update_timestamp()
    else:
        error_messages = {
            1: "Incorrect protocol version",
            2: "Invalid client identifier",
            3: "Server unavailable",
            4: "Bad username/password",
            5: "Not authorized"
        }
        error_msg = error_messages.get(reason_code, f"Unknown error ({reason_code})")
        print(f"Connection failed: {error_msg}")
        status_bar.config(text=f"Connection failed: {error_msg}")

def on_disconnect(client, userdata, rc, properties=None, reasonCode=None):
    disconnect_reasons = {
        0: "Normal disconnection",
        1: "Broker unavailable",
        2: "Protocol error",
        3: "Client error",
        4: "Transport error"
    }
    reason = disconnect_reasons.get(rc, f"Unknown reason ({rc})")
    print(f"Disconnected: {reason}")
    # Your reconnection logic here
def on_message(client, userdata, msg):
    global ignore_initial_messages
    
    if ignore_initial_messages:
        ignore_initial_messages = False
        return

    print(f"Received on {msg.topic}: {msg.payload.decode()}")
    update_timestamp()

    try:
        if msg.topic == LED_TOPIC:
            handle_led_message(msg.payload.decode())
        elif msg.topic == FAN_TOPIC:
            handle_fan_message(msg.payload.decode())
        elif msg.topic == TEMP_TOPIC:
            handle_temp_message(msg.payload.decode())
        elif msg.topic == HUMIDITY_TOPIC:
            handle_humidity_message(msg.payload.decode())
    except Exception as e:
        print(f"Error processing message: {e}")

def handle_led_message(state):
    if state == "ON":
        led_button.config(image=led_on_photo)
        led_status.config(text="Status: ON")
    else:
        led_button.config(image=led_off_photo)
        led_status.config(text="Status: OFF")

def handle_fan_message(speed):
    global fan_slider_moving
    
    try:
        speed = int(speed)
        if not fan_slider_moving:
            fan_slider.set(speed)
            fan_entry.delete(0, tk.END)
            fan_entry.insert(0, str(speed))
        if speed > 0:
            fan_button.config(image=fan_on_photo)
        else:
            fan_button.config(image=fan_off_photo)
    except ValueError:
        pass

def handle_temp_message(temp):
    try:
        temp = float(temp)
        temp_gauge.config(text=f"{temp}°C")
    except ValueError:
        pass

def handle_humidity_message(humidity):
    try:
        humidity = float(humidity)
        humidity_gauge.config(text=f"{humidity}%")
    except ValueError:
        pass

def connect_to_mqtt():
    try:
        client.will_set(FAN_TOPIC, "0", qos=1, retain=True)
        client.will_set(LED_TOPIC, "OFF", qos=1, retain=True)
        
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect
        
        # Add clean_start parameter for MQTTv5
        client.connect(
            MQTT_BROKER, 
            MQTT_PORT, 
            keepalive=60,
            clean_start=True  # False if you want persistent session
        )
        client.loop_start()
    except Exception as e:
        print(f"MQTT error: {e}")
        status_bar.config(text=f"Connection error: {str(e)}")
    
def toggle_led():
    current_state = led_status.cget("text").split(": ")[1]
    if current_state == "OFF":
        client.publish(LED_TOPIC, "ON", qos=1)
    else:
        client.publish(LED_TOPIC, "OFF", qos=1)

def set_fan_speed(value=None):
    if value is None:
        try:
            value = int(fan_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Please enter a number between 0-255")
            return
    
    if 0 <= value <= 255:
        client.publish(FAN_TOPIC, str(value), qos=1)
        if value > 0:
            fan_button.config(image=fan_on_photo)
        else:
            fan_button.config(image=fan_off_photo)

def on_slider_change(event):
    global fan_slider_moving
    fan_slider_moving = True
    value = fan_slider.get()
    fan_entry.delete(0, tk.END)
    fan_entry.insert(0, str(int(value)))
    if abs(value - int(value)) < 0.1:
        set_fan_speed(int(value))
    fan_slider_moving = False

def on_entry_change(event):
    try:
        value = int(fan_entry.get())
        if 0 <= value <= 255:
            fan_slider.set(value)
            set_fan_speed(value)
    except ValueError:
        pass

def launch_voice_control():
    global voice_process, voice_control_active, voice_thread
    
    if not voice_control_active:
        try:
            script_path = resource_path("VoiceControlForHome.py")
            if not os.path.exists(script_path):
                script_path = "C:\\codes\\IOT\\VoiceControlForHome.py"
                if not os.path.exists(script_path):
                    raise FileNotFoundError("VoiceControlForHome.py not found")

            output_text.delete(1.0, tk.END)
            output_text.insert(tk.END, "Starting voice control...\n")
            output_text.see(tk.END)
            
            voice_btn.config(text="Stop Voice Control", style='Accent.TButton')
            voice_control_active = True
            
            voice_process = subprocess.Popen(
                [sys.executable, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
                shell=True
            )
            
            voice_thread = threading.Thread(
                target=monitor_voice_output,
                daemon=True
            )
            voice_thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch voice control:\n{str(e)}")
            voice_control_active = False
            voice_btn.config(text="Start Voice Control", style='TButton')
    else:
        stop_voice_control()
        voice_btn.config(text="Start Voice Control", style='TButton')
        output_text.insert(tk.END, "Voice control stopped\n")
        output_text.see(tk.END)

def monitor_voice_output():
    global voice_process, voice_control_active
    
    while voice_control_active and voice_process:
        output = voice_process.stdout.readline()
        if output:
            output_text.insert(tk.END, output)
            output_text.see(tk.END)
        
        err = voice_process.stderr.readline()
        if err:
            output_text.insert(tk.END, f"ERROR: {err}")
            output_text.see(tk.END)
        
        if voice_process.poll() is not None:
            output_text.insert(tk.END, "\nVoice control process ended\n")
            output_text.see(tk.END)
            voice_control_active = False
            voice_btn.config(text="Start Voice Control", style='TButton')
            break
        
        time.sleep(0.1)

def stop_voice_control():
    global voice_process, voice_control_active
    
    if voice_process:
        try:
            if os.name == 'nt':
                os.system(f'taskkill /F /PID {voice_process.pid}')
            else:
                voice_process.send_signal(signal.SIGINT)
                try:
                    voice_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    voice_process.kill()
        except Exception as e:
            print(f"Error stopping process: {e}")
        finally:
            voice_process = None
            voice_control_active = False

# ========== GUI SETUP ==========
root = tk.Tk()
root.title("Smart Home Control Panel")
root.geometry("950x850")
root.minsize(850, 750)
root.configure(bg=BG_COLOR)
root.iconbitmap('smart_home_icon.ico')


style = ttk.Style()
style.theme_use('clam')

# Configure styles
style.configure('.', background=BG_COLOR, foreground=FG_COLOR)
style.configure('TFrame', background=BG_COLOR)
style.configure('TLabel', background=BG_COLOR, foreground=FG_COLOR, font=BODY_FONT)
style.configure('TButton', background=BG_COLOR, foreground=FG_COLOR, font=BODY_FONT)
style.configure('Title.TLabel', font=TITLE_FONT)
style.configure('Header.TLabel', font=HEADER_FONT)
style.configure('Gauge.TLabel', font=("Segoe UI", 24, "bold"))
style.configure('TLabelframe', background=BG_COLOR, foreground=FG_COLOR)
style.configure('TLabelframe.Label', background=BG_COLOR, foreground=FG_COLOR)
style.configure('TScale', background=BG_COLOR)
style.configure('Black.TEntry', fieldbackground=ENTRY_BG, foreground=ENTRY_FG, insertcolor=ENTRY_FG)
style.configure('Accent.TButton', background=ACCENT_COLOR, foreground=BG_COLOR)

main_frame = ttk.Frame(root, padding=15)
main_frame.pack(fill=tk.BOTH, expand=True)

# Header
header_frame = ttk.Frame(main_frame)
header_frame.pack(fill=tk.X, pady=(0, 15))
title_label = ttk.Label(header_frame, text="Smart Home Dashboard", style='Title.TLabel')
title_label.pack(side=tk.LEFT)

# Top Section - Home Image and Output Console
top_section = ttk.Frame(main_frame)
top_section.pack(fill=tk.X, pady=10)

# Home Image (Left)
home_frame = ttk.Frame(top_section)
home_frame.pack(side=tk.LEFT, padx=10)
try:
    home_img = Image.open(resource_path("home_image.png")).resize(HOME_IMG_SIZE)
    home_photo = ImageTk.PhotoImage(home_img)
    ttk.Label(home_frame, image=home_photo).pack()
except Exception as e:
    print(f"Error loading home image: {e}")
    ttk.Label(home_frame, text="Home Image", width=25, height=10).pack()

# Output Console (Right)
output_frame = ttk.LabelFrame(top_section, text="Voice Control Output", padding=10)
output_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
output_text = tk.Text(
    output_frame,
    height=10,
    bg=BG_COLOR,
    fg=FG_COLOR,
    font=MONO_FONT,
    wrap=tk.WORD
)
output_text.pack(fill=tk.BOTH, expand=True)
scrollbar = ttk.Scrollbar(output_frame, command=output_text.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
output_text.config(yscrollcommand=scrollbar.set)

# Control Section - LED and Voice Control
control_section = ttk.Frame(main_frame)
control_section.pack(fill=tk.X, pady=10)

# LED Control
led_frame = ttk.LabelFrame(control_section, text="LED Control", padding=10)
led_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

led_btn_frame = ttk.Frame(led_frame)
led_btn_frame.pack()

try:
    led_on_img = Image.open(resource_path("led_on.png")).resize(LED_IMG_SIZE)
    led_off_img = Image.open(resource_path("led_off.png")).resize(LED_IMG_SIZE)
    led_on_photo = ImageTk.PhotoImage(led_on_img)
    led_off_photo = ImageTk.PhotoImage(led_off_img)
    led_button = ttk.Button(led_btn_frame, image=led_off_photo, command=toggle_led)
    led_button.pack(side=tk.LEFT, padx=10)
    led_status = ttk.Label(led_btn_frame, text="Status: OFF", font=HEADER_FONT)
    led_status.pack(side=tk.LEFT, padx=15)
except Exception as e:
    print(f"Error loading LED images: {e}")
    led_button = ttk.Button(led_btn_frame, text="LED", command=toggle_led)
    led_button.pack(side=tk.LEFT, padx=10)
    led_status = ttk.Label(led_btn_frame, text="Status: OFF", font=HEADER_FONT)
    led_status.pack(side=tk.LEFT, padx=15)

# Voice Control
voice_frame = ttk.LabelFrame(control_section, text="Voice Control", padding=10)
voice_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
voice_btn = ttk.Button(
    voice_frame, 
    text="Start Voice Control", 
    command=launch_voice_control,
    width=20
)
voice_btn.pack(expand=True, pady=10, padx=10)

# Fan Control Section
fan_frame = ttk.LabelFrame(main_frame, text="Fan Control", padding=10)
fan_frame.pack(fill=tk.X, pady=10)

fan_control_frame = ttk.Frame(fan_frame)
fan_control_frame.pack(fill=tk.X)

try:
    fan_on_img = Image.open(resource_path("fan_on.png")).resize(FAN_IMG_SIZE)
    fan_off_img = Image.open(resource_path("fan_off.png")).resize(FAN_IMG_SIZE)
    fan_on_photo = ImageTk.PhotoImage(fan_on_img)
    fan_off_photo = ImageTk.PhotoImage(fan_off_img)
    fan_button = ttk.Label(fan_control_frame, image=fan_off_photo)
    fan_button.pack(side=tk.LEFT, padx=10)
except Exception as e:
    print(f"Error loading fan images: {e}")
    fan_button = ttk.Label(fan_control_frame, text="FAN")
    fan_button.pack(side=tk.LEFT, padx=10)

fan_slider = ttk.Scale(
    fan_control_frame, 
    from_=0, 
    to=255, 
    command=on_slider_change,
    orient=tk.HORIZONTAL,
    length=200
)
fan_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

fan_entry_frame = ttk.Frame(fan_control_frame)
fan_entry_frame.pack(side=tk.LEFT, padx=10)
fan_entry = ttk.Entry(fan_entry_frame, width=5, font=BODY_FONT, style='Black.TEntry')
fan_entry.pack(side=tk.LEFT)
fan_entry.insert(0, "0")
fan_entry.bind("<KeyRelease>", on_entry_change)
set_button = ttk.Button(fan_entry_frame, text="Set", command=lambda: set_fan_speed())
set_button.pack(side=tk.LEFT, padx=5)

# Environment Section
env_frame = ttk.Frame(main_frame)
env_frame.pack(fill=tk.X, pady=15)

temp_frame = ttk.LabelFrame(env_frame, text="Temperature", padding=10)
temp_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
ttk.Label(temp_frame, text="Current:", font=BODY_FONT).pack()
temp_gauge = ttk.Label(temp_frame, text="--°C", style='Gauge.TLabel')
temp_gauge.pack()

humidity_frame = ttk.LabelFrame(env_frame, text="Humidity", padding=10)
humidity_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
ttk.Label(humidity_frame, text="Current:", font=BODY_FONT).pack()
humidity_gauge = ttk.Label(humidity_frame, text="--%", style='Gauge.TLabel')
humidity_gauge.pack()

# Status Bar
status_bar = ttk.Label(root, text="Connecting to MQTT broker...", relief=tk.SUNKEN, 
                      anchor=tk.W, padding=5, font=SMALL_FONT)
status_bar.pack(side=tk.BOTTOM, fill=tk.X)

# ========== START APPLICATION ==========
mqtt_thread = threading.Thread(target=connect_to_mqtt, daemon=True)
mqtt_thread.start()

def on_closing():
    stop_voice_control()
    client.disconnect()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)
root.mainloop()