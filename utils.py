import io 
import os
import time
import logging 
from picamera2 import Picamera2 # Oficjalna biblioteka do obslugi kamery Raspberry Pi
from picamera2.encoders import JpegEncoder, H264Encoder
from picamera2.outputs import FileOutput
from gpiozero import LineSensor, MotionSensor   # Oficjalna biblioteka do obslugi GPIO Raspberry Pi
from threading import Condition, Lock   # Biblioteka do obslugi watkow


"""Ten plik zawiera funkcje i klasy pomocnicze, ktore sa wykorzystywane w glownym programie."""

"""Poniewaz kamera jest zmienna globalna, do ktorej maja dostep rozne funkcje,
    potrzebujemy zabezpieczyc sie przed sytuacja, w ktorej dwie funkcje probuja
    jednoczesnie uzyskac dostep do kamery. W tym celu tworzymy obiekt typu Lock,
    ktory zapewnia wzajemne wykluczanie sie funkcji.
"""
mutex = Lock()

camera_initialised = False


# Inicjalizacja kamery
def camera_setup():
    global camera, camera_initialised # Kamera musi byc zmienna globalna, aby moc nagrywac oraz robic zdjecia podczas podgladu na zywo
    if not camera_initialised:
        try:
            tuning = Picamera2.load_tuning_file("ov5647.json")
            camera = Picamera2(tuning=tuning)

            global streaming_config # Konfiguracja strumienia wideo jest domyslna konfiguracja kamery
            streaming_config = camera.create_video_configuration(main={"size": (640, 480)})
            camera.configure(streaming_config)

            camera_initialised = True
            print("Camera initialised.")
        except Exception as e:
            print(f"Error: {e}")
            camera_initialised = False
    else:
        pass


# Inicjalizacja czujnikow
def sensor_setup():
    global IR_beam, PIR_sensor  
    IR_beam = LineSensor(17)        # Czujnik przerwania wiazki podlaczony do GPIO17
    PIR_sensor = MotionSensor(4)    # Czujnik ruchu PIR podlaczony do GPIO4
    print("Sensors initialised.")


"""Prosta klasa, ktora przechowuje aktualny status narzedzi takich jak czujnik IR,
czy nagrywanie przy wykryciu ruchu oraz obsluguje zmiane tekstu przyciskow.

    Argumenty:
        init_stat (bool): Poczatkowy status narzedzia.
        true_string (str): Tekst przycisku, ktory zmienia status narzedzia na True.
        false_string (str): Tekst przycisku, ktory zmienia status narzedzia na False.

    Atrybuty:
        status (bool): Aktualny status narzedzia.
        make_true (str): Tekst przycisku, ktory zmienia status narzedzia na True.
        make_false (str): Tekst przycisku, ktory zmienia status narzedzia na False.
        button_text (str): Zmiana domyslnego tekstu przycisku.

    Metody:
        enable(): Ustawia status narzedzia na True.
        disable(): Ustawia status narzedzia na False.
"""
class UtilityStatus():
    def __init__(self, init_stat=True, true_string='Enable', false_string='Disable'):
        self.status = init_stat
        self.make_true = true_string
        self.make_false = false_string
        if self.status:
            self.button_text = self.make_false
        else:
            self.button_text = self.make_true
    
    def enable(self):
        self.status = True
        self.button_text = self.make_false

    def disable(self):
        self.status = False
        self.button_text = self.make_true


"""Zmienne globalne, ktore przechowuja aktualny status czujnikow i funkcji kamery.
Zmienne musza byc globalne, aby byly dostepne dla roznych funkcji.
"""
video_stream = UtilityStatus()  # Status podgladu na zywo
IR_beam_work = UtilityStatus()  # Status czujnika przerwania wiazki IR
PIR_recording = UtilityStatus(init_stat=False)  # Status nagrywania przy wykryciu ruchu przez czujnik PIR
video_recording = UtilityStatus(init_stat=False, true_string='Start', false_string='Stop')  # Status nagrywania filmu



"""Twozenie obiektu typu StreamingOutput, ktory przechowuje w pamieci klatki z kamery,
bez zapisywania ich do pliku. Obiekt ten jest wykorzystywany do wyswietlania podgladu na zywo.

    Na podstawie przykladu z oficjalnego repozytorium biblioteki picamera2 na githubie.
    Zrodlo: https://github.com/raspberrypi/picamera2/blob/main/examples/mjpeg_server.py
    Licencja: BSD 2-Clause License

"""
class StreamingOutput(io.BufferedIOBase): 
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def write(self, buf):
        with self.condition:
            self.frame = buf
            self.condition.notify_all()


"""Funkcja, ktora generuje i zwraca klatki z kamery w formacie MJPEG.

    Na podstawie artykulow z bloga Miguela Grinberga i jego repozytorium na githubie.
    Zrodla: https://blog.miguelgrinberg.com/post/video-streaming-with-flask
            https://blog.miguelgrinberg.com/post/flask-video-streaming-revisited
            https://github.com/miguelgrinberg/flask-video-streaming/tree/master            
    Licencja: MIT License
"""
def gen_frames():
    buffer = StreamingOutput()      # Obiekt ktory przechowuje w pamieci klatki z kamery
    stream_encoder = JpegEncoder()  # Osobny enkoder dla strumienia wideo, aby nie zaklocac transmisji na zywo
    camera.start_recording(stream_encoder, FileOutput(buffer))

    while True:
        with buffer.condition:
            buffer.condition.wait()
            frame = buffer.frame
        yield (b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        

"""Funkcja do robienia zdjecia i zapisywania go do pliku.
Zmienia konfiguracje kamery na czas robienia zdjecia, a nastepnie przywraca ja do 
poprzedniej. Zdjecia nie zajmuja duzo pamieci, wiec zmiana konfiguracji odbywa sie, 
by przechwycic je w lepszej rozdzielczosci.

    Na podstawie przykladu z oficjalnego repozytorium biblioteki picamera2 na githubie.
    Zrodlo: https://github.com/raspberrypi/picamera2/blob/main/examples/capture_image_full_res.py
    Licencja: BSD 2-Clause License
"""
def capture_photo():
    size = camera.sensor_resolution
    # GPU nie przetworzy zdjecia szerszego niz 4096 pikseli na Raspberry Pi 4B
    # nie chcemy zdjec wiekszych niz 2592x1944, aby nie przeciazyc sieci, procesora i pamieci
    if size[0] > 2592:
        height = size[1] * 2592 // size[0]
        height -= height % 2
        size = (2592, height)
    
    camera.still_configuration.size = size  # Zmiana rozdzielczosci na czas robienia zdjecia

    # Tworzenie folderu na zdjecia, jesli nie istnieje
    photo_path = f"{os.getcwd()}/captured/photos"
    if not os.path.exists(photo_path):
        os.makedirs(photo_path)
    photo_name = time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime())

    """Wedlug dokumentacji biblioteki picamera2, funkcja switch_mode_and_capture_file()
    powinna byc wywolywana w sposob nieblokujacy, aby nie zaklocac transmisji na zywo.
    W tym celu wykorzystujemy obiekt typu Lock. 

    Zmiana konfiguracji kamery odbywa sie jedynie na czas robienia zdjecia, a nastepnie
    przywracana jest poprzednia konfiguracja.
    """    
    with mutex:
        camera.switch_mode_and_capture_file("still", f"{photo_path}/{photo_name}.jpg")


"""Funkcja, ktora obsluguje petle, ktora sprawdza, czy czujnik przerwania wiazki IR
wykryl przerwanie wiazki i zapisuje czasy przerwania do pliku .log.
"""
def beam_sensor():
    # Stworzenie loggera
    beam_logger = logging.getLogger('IR_beam_logger')
    beam_logger.setLevel(logging.INFO)

    # Stworzenie pliku log
    # Kazde uruchomienie programu tworzy nowy plik log
    beam_log_path = f"{os.getcwd()}/captured/logs/IR_beam"
    if not os.path.exists(beam_log_path):
        os.makedirs(beam_log_path)

    # Plik log ma nazwe w formacie: <data_i_czas>_IR_beam.log
    beam_log_file = f"{beam_log_path}/{time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime())}_IR_beam.log"
    beam_handler = logging.FileHandler(beam_log_file)
    beam_handler.setLevel(logging.INFO)
    beam_handler.setFormatter(logging.Formatter('%(asctime)s\t%(message)s', datefmt="%Y-%m-%d %H:%M:%S"))
    beam_logger.addHandler(beam_handler)

    beam_logger.info("IR beam sensor enabled. Logging started.")

    # Petla, ktora sprawdza, czy czujnik przerwania wiazki IR wykryl przerwanie wiazki
    # i loguje to do pliku .log oraz zwraca ostatni log do wyswietlenia na stronie internetowej
    while True:
        IR_beam.wait_for_active()
        beam_logger.info("Beam detected!")
        yield f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\tBeam detected!\n"

        IR_beam.wait_for_inactive()
        beam_logger.info("Beam broken!")
        yield f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\tBeam broken!\n"


"""Funkcja, ktora obsluguje petle, ktora sprawdza, czy czujnik PIR wykryl ruch
i zapisuje czasy wykrycia ruchu do pliku .log oraz uruchamia nagrywanie filmu.
Gdy czujnik nie wykryje ruchu przez 15 sekund, zatrzymuje nagrywanie i zapisuje
czas zatrzymania nagrywania do pliku .log.
"""
def PIR_sensor():
    # Stworzenie loggera
    PIR_logger = logging.getLogger('PIR_logger')
    PIR_logger.setLevel(logging.INFO)

    # Stworzenie pliku log
    # Kazde uruchomienie programu tworzy nowy plik log
    PIR_log_path = f"{os.getcwd()}/captured/logs/PIR_recording"
    if not os.path.exists(PIR_log_path):
        os.makedirs(PIR_log_path)
    
    # Plik log ma nazwe w formacie: <data_i_czas>_PIR_recording.log
    PIR_log_file = f"{PIR_log_path}/{time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime())}_PIR_recording.log"
    PIR_handler = logging.FileHandler(PIR_log_file)
    PIR_handler.setLevel(logging.INFO)
    PIR_handler.setFormatter(logging.Formatter('%(asctime)s\t%(message)s', datefmt="%Y-%m-%d %H:%M:%S"))
    PIR_logger.addHandler(PIR_handler)

    # Stworzenie enkodera do nagrywania filmu
    # Osobny enkoder do nagrywania filmu, aby nie zaklocac transmisji na zywo
    motion_encoder = H264Encoder(iperiod=30)

    # Tworzenie folderu na nagrania, jesli nie istnieje
    video_path = f"{os.getcwd()}/captured/videos"
    if not os.path.exists(video_path):
        os.makedirs(video_path)

    PIR_logger.info("PIR motion recording enabled. Logging started.")

    # Petla, ktora sprawdza, czy czujnik PIR wykryl ruch i uruchamia nagrywanie filmu,
    # loguje to do pliku .log oraz zwraca ostatni log do wyswietlenia na stronie internetowej
    while True:
        PIR_sensor.wait_for_active()
        PIR_logger.info("Motion detected!")
        yield f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\tMotion detected!\n"
        
        # Plik nagrania ma nazwe w formacie: <data_i_czas>_PIR_recording.h264
        camera.start_encoder(motion_encoder, FileOutput(f"{video_path}/{time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime())}_PIR_recording.h264"))
        PIR_logger.info("Recording started!")
        yield f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\tRecording started!\n"

        time.sleep(15)  # Opoznienie 15 sekund, aby nagrywanie nie zostalo zatrzymane od razu po wykryciu ruchu

        PIR_sensor.wait_for_inactive()
        PIR_logger.info("No motion detected!")
        yield f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\tNo motion detected!\n"

        camera.stop_encoder(motion_encoder)
        PIR_logger.info("Recording stopped!")
        yield f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\tRecording stopped!\n"


"""Globalna zmienna, ktore przechowuje osobny enkoder do nagrywania filmu przez
uzytkownika. Osobny enkoder, aby nie zaklocac transmisji na zywo."""
recording_encoder = H264Encoder(iperiod=30)

# Rozpoczecie nagrywania filmu
def start_recording():
    # Tworzenie folderu na nagrania, jesli nie istnieje
    video_path = f"{os.getcwd()}/captured/videos"
    if not os.path.exists(video_path):
        os.makedirs(video_path)
    
    # Plik nagrania ma nazwe w formacie: <data_i_czas>_recording.h264
    start_time = time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime())
    camera.start_encoder(recording_encoder, FileOutput(f"{video_path}/{start_time}_recording.h264"))

# Zakonczenie nagrywania filmu
def stop_recording():
    camera.stop_encoder(recording_encoder)
    





    
