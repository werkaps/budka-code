from gpiozero import MotionSensor
from picamera2 import Picamera2, Preview
from libcamera import Transform
import time


"""Kod testowy do czujnika ruchu PIR by sprawdzic czy dziala poprawnie 
i czy mozna go wykorzystac do nagrywania filmow przy wykryciu ruchu.
"""

pir  = MotionSensor(4)

picam2 = Picamera2()
picam2.start_preview()

config = picam2.create_preview_configuration()
picam2.configure(config)

picam2.start()
picam2.stop_preview()

while True:
    pir.wait_for_active()
    print("Motion detected!")
    # picam2.start_preview(True, transform=Transform(hflip=1, vflip=1))
    picam2.start_preview(Preview.QTGL, transform=Transform(hflip=1, vflip=1))
    pir.wait_for_inactive()
    picam2.stop_preview()
    