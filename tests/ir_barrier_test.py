from gpiozero import LineSensor
import time


"""Kod testowy do czujnika przerwania wiazki IR by sprawdzic czy dziala poprawnie."""

ir_barrier = LineSensor(17)

while True:
    ir_barrier.wait_for_active()
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\tWykryto wiazke")
    ir_barrier.wait_for_inactive()
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\tWiazka przerwana")