from gtts import gTTS
import speech_recognition as sr
import time
import os
import paho.mqtt.client as mqtt
from pydub import AudioSegment
from pydub.playback import play
import arabic_reshaper
from bidi.algorithm import get_display
import pygetwindow as gw
import pyautogui
import cv2
import numpy as np
from PIL import Image
from datetime import datetime
import subprocess  # To run Mosquitto commands
import sys
import io
# Fix encoding issues
if sys.stdout.encoding != 'UTF-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'UTF-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# For Windows specifically
if os.name == 'nt':
    os.system('chcp 65001 > nul')  # Set console to UTF-8 without output



# Global MQTT client (broker)
client = mqtt.Client()
MQTT_BROKER = "broker.emqx.io"  # Global MQTT Broker
MQTT_PORT = 1883  # Default port for EMQX broker
LED_TOPIC = "home/led"
FAN_TOPIC = "home/fan"
TEMP_TOPIC = "home/temp"

def on_connect(client, userdata, flags, rc):
    """Callback when the client connects to the broker."""
    print(f"Connected with result code {rc}")
    # You can subscribe to topics here if needed
    # client.subscribe("home/#")  # Example subscription

def on_message(client, userdata, msg):
    """Callback when a message is received."""
    print(f"Message received: {msg.topic} -> {msg.payload.decode()}")

# Set MQTT callbacks
client.on_connect = on_connect
client.on_message = on_message

# Connect to the global broker
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_start()  # Start the MQTT client loop

class ArabicSpeechProcessor:
    def __init__(self):
        """Initialize the speech processor."""
        self.recognizer = sr.Recognizer()
        self.running = True  # Flag to control the main loop
        self.voiceover_enabled = True  # Voiceover enabled by default
        self.greetings = ["مرحبا", "السلام عليكم", "اهلا", "صباح الخير", "مساء الخير"]  # List of greetings
        self.window_name = "Smart Home Dashboard"  # The window name to focus on
        self.captured_image = None

    def listen_and_process(self):
        """Listen for speech, recognize it, and execute commands."""
        try:
            with sr.Microphone() as source:
                self._print_arabic("جاري الاستماع... قل شيئًا!")  # "Listening... Say something!"
                self.recognizer.adjust_for_ambient_noise(source, duration=1)  # Adjust for ambient noise
                audio = self.recognizer.listen(source)  # Capture the audio
                self._print_arabic("تم تسجيل الصوت.")  # "Audio captured."

            # Recognize the speech using Google's API
            self._print_arabic("جاري التعرف على الكلام...")  # "Recognizing speech..."
            recognized_text = self.recognizer.recognize_google(audio, language='ar-AR')
            self._print_arabic(f"تم التعرف على النص: {recognized_text}")  # "Recognized text:"

            # Check if the recognized text contains a greeting
            if self._is_greeting(recognized_text):
                self._respond_to_greeting()
            else:
                # Execute commands based on recognized text
                self._execute_command(recognized_text)

            # Small delay before listening again
            self._print_arabic("جاهز للاستماع إلى المدخل التالي...\n")  # "Ready for the next input..."
            time.sleep(1)  # Add a delay to prevent rapid repeated calls

        except sr.UnknownValueError:
            self._print_arabic("خطأ: لا يمكن فهم الصوت.")  # "Error: Could not understand the audio."
            time.sleep(1)  # Small delay before retrying
        except sr.RequestError as e:
            self._print_arabic(f"خطأ في طلب النتائج من جوجل: {e}")  # "Error with the request to the API."
        except KeyboardInterrupt:
            self._print_arabic("\nتم إنهاء البرنامج...")  # "Exiting the program..."
            self.running = False
        except Exception as e:
            self._print_arabic(f"حدث خطأ غير متوقع: {e}")  # "Unexpected error occurred."
            self.running = False

    def _is_greeting(self, text):
        """Check if the recognized text contains a greeting."""
        for greeting in self.greetings:
            if greeting in text:
                return True
        return False

    def _respond_to_greeting(self):
        """Respond to a greeting with a friendly message."""
        response = "مرحبًا! كيف يمكنني مساعدتك؟"  # "Hello! How can I help you?"
        self._print_arabic(response)
        if self.voiceover_enabled:
            audio_file = self._text_to_speech(response)
            if audio_file:
                self._play_audio(audio_file)

    def _execute_command(self, text):
        """Execute commands based on recognized text."""
        stop_commands = ["توقف", "خروج", "إغلاق", "إنهاء"]
        if any(command in text for command in stop_commands):  # Check if any stop command is in the text
            self._print_arabic("تم استلام أمر التوقف.")  # "Stop command received."
            self.running = False
        elif "تشغيل الاضواء" in text:  # LED ON command
            self.control_led_on()
        elif "فصل الاضواء" in text:    # LED OFF command
            self.control_led_off()
        elif "تشغيل المروحه" in text:  # Fan ON command
            self.control_fan_on()
        elif "إيقاف المروحة" in text:  # Fan OFF command
            self.control_fan_off()
        elif "درجة الحراره" in text:  # Temperature reading command
            self.get_temperature()

        else:
            # Save recognized text to a file and convert to speech if voiceover is enabled
            self._save_text_to_file(text)
            if self.voiceover_enabled:
                audio_file = self._text_to_speech(text)
                if audio_file:
                    self._play_audio(audio_file)

    def control_led_on(self):
        """Control LEDs (on)."""
        self._print_arabic("تم تشغيل الأضواء.")
        client.publish(LED_TOPIC, "ON")

    def control_led_off(self):
        """Control LEDs (off)."""
        self._print_arabic("تم إيقاف الأضواء.")
        client.publish(LED_TOPIC, "OFF")

    def control_fan_on(self):
        """Control Fan (on)."""
        self._print_arabic("تم تشغيل المروحة.")
        client.publish(FAN_TOPIC, "1024")

    def control_fan_off(self):
        """Control Fan (off)."""
        self._print_arabic("تم إيقاف المروحة.")
        client.publish(FAN_TOPIC, "OFF")

    def get_temperature(self):
        """Fetch temperature."""
        # For now, let's simulate a static temperature reading (you can integrate real sensor here).
        temperature = 22.5  # Example temperature
        self._print_arabic(f"درجة الحرارة الحالية هي {temperature} درجة مئوية.")  # "Current temperature is..."
        client.publish(TEMP_TOPIC, str(temperature))

    def _save_text_to_file(self, text):
        """Save recognized text to a file."""
        with open('text.txt', 'a', encoding='utf-8') as f:
            f.writelines(text + '\n')
        self._print_arabic("تم حفظ النص في الملف.")  # "Text saved to file."

    def _print_arabic(self, text):
        """Print Arabic text with error handling for TTS."""
        try:
            reshaped_text = arabic_reshaper.reshape(text)  # Reshape the Arabic text
            bidi_text = get_display(reshaped_text)  # Correct the bidirectional display of Arabic text
            
            # Print the reshaped and bidi-corrected text to the console
            print(bidi_text)
            
            # Only convert to speech and play the audio if it's enabled and hasn't been done before
            #if self.voiceover_enabled:
            #    audio_file = self._text_to_speech(text)  # Convert to speech
            #    if audio_file:
            #        self._play_audio(audio_file)  # Play the audio file
        except Exception as e:
            print(f"خطأ في طباعة النص العربي: {e}")  # Print an error message in Arabic if something goes wrong


    def _text_to_speech(self, text):
        """Convert text to speech and save it as an MP3 file."""
        try:
            audio_filename = 'greeting.mp3' if text == "مرحبًا! كيف يمكنني مساعدتك؟" else 'text.mp3'
            
            # Generate the speech using gTTS
            tts = gTTS(text=text, lang='ar', slow=False)
            tts.save(audio_filename)  # Save the speech as an MP3 file
            self._print_arabic(f"تم تحويل النص إلى كلام وحفظه كملف MP3: {audio_filename}")  # Confirm MP3 creation
            return audio_filename
        except Exception as e:
            print(f"خطأ في تحويل النص إلى كلام: {e}")  # Print any error in Arabic
            return None  # Return None if there's an error


    def _play_audio(self, file_path):
        """Play audio using pydub and simpleaudio."""
        try:
            audio = AudioSegment.from_mp3(file_path)  # Load the MP3 file
            play(audio)  # Play the audio
        except Exception as e:
            print(f"حدث خطأ أثناء تشغيل الصوت: {e}")  # Print error if something goes wrong with playback

# Main program
if __name__ == "__main__":
    processor = ArabicSpeechProcessor()
    processor._respond_to_greeting()
    processor._print_arabic("بدء معالجة الكلام باللغة العربية...")  # "Starting Arabic speech processing..."
    
    while processor.running:
        processor.listen_and_process()
    
    processor._print_arabic("تم إنهاء البرنامج بنجاح.")  # "Program terminated successfully."
