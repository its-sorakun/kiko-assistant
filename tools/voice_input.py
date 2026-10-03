# source: https://github.com/dscripka/openWakeWord

import pyaudio
import numpy as np
# pyrefly: ignore [missing-import]
import openwakeword
# # pyrefly: ignore [missing-import]
from openwakeword.model import Model
import wave
import sys


CHUNK = 1280
FORMAT = pyaudio.paInt16 #16 bit integer PCM
SAMPLE_RATE = 16000 # 16khz sample rate
p = pyaudio.PyAudio()
# Open stream (2)
stream = p.open(format=FORMAT,
                channels=1,
                rate=SAMPLE_RATE,
                input=True)

# One-time download of all pre-trained models
openwakeword.utils.download_models()

# create the model
# This will automatically load the pre-trained Jarvis model
oww_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

print("   [🎙️ Kiko's ear is active. Listening for 'Hey Jarvis'...] \n")

while True:
    data = stream.read(CHUNK)   
    audio_array = np.frombuffer(data, dtype=np.int16)
    # Print the raw volume of the microphone
    print(np.max(np.abs(audio_array))) 

    # get predictions and check for wakeword
    prediction = oww_model.predict(audio_array)
    
    if "hey_jarvis" in prediction and prediction["hey_jarvis"] > 0.6:
        # Watch the neural net's confidence in real-time!
        print(f"Jarvis Score: {prediction['hey_jarvis']:.4f}")

# Release PortAudio system resources
p.terminate()

# # Instantiate the model(s)
# model = Model(
#     wakeword_models=["path/to/model.tflite"],  # can also leave this argument empty to load all of the included pre-trained models
# )

# # Get audio data containing 16-bit 16khz PCM audio data from a file, microphone, network stream, etc.
# # For the best efficiency and latency, audio frames should be multiples of 80 ms, with longer frames
# # increasing overall efficiency at the cost of detection latency
# frame = my_function_to_get_audio_frame()

# # Get predictions for the frame
# prediction = model.predict(frame)