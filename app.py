#!/usr/bin/env python3

from flask import Flask, render_template, request, Flask, Response
from utils import *     # Plik z funkcjami obslugujacymi kamere i czujniki


"""Glowny plik aplikacji.

    Zawiera funkcje odpowiedzialne za obsluge zapytan HTTP.
"""


app = Flask(__name__)
app.config['SECRET_KEY'] = '6QczXm5JgQq29!'


# Inicjalizacja kamer i czujnikow przed pierwszym zapytaniem HTTP
@app.before_first_request
def on_startup():
    camera_setup()
    sensor_setup()

    
"""Strona glowna aplikacji. Obsluga zapytan HTTP.
   
        GET:
            Zwraca strone glowna aplikacji.
    
        POST:
            Obsluguje zapytania POST z formularza na stronie glownej.
            Zmienia statusy przyciskow i wywoluje odpowiednie funkcje.
            Zwraca strone glowna aplikacji.
    
"""
@app.route('/', methods=["GET", "POST"])
@app.route('/index.html', methods=["GET", "POST"])
def main_page():
    if request.method == "POST":

        # Wlaczanie/wylaczanie podgladu na zywo
        if 'toggleStream' in request.form:
            if video_stream.status:
                video_stream.disable()
            else:
                video_stream.enable()
        
        # Zrobienie zdjecia
        if 'photoButton' in request.form:
            capture_photo()

        # Nagrywanie filmu
        if 'recordButton' in request.form:
            if video_recording.status:
                stop_recording()
                video_recording.disable()
            else:
                start_recording()
                video_recording.enable()

        # Wlaczanie/wylaczanie czujnika przerwania wiazki IR
        if 'barrierButton' in request.form:
            if IR_beam_work.status:
                IR_beam_work.disable()
            else:
                IR_beam_work.enable()

        # Wlaczanie/wylaczanie nagrywania przy wykryciu ruchu przez czujnik PIR
        if 'pirButton' in request.form:
            if PIR_recording.status:
                PIR_recording.disable()
            else:
                if video_recording.status:
                    stop_recording()
                    video_recording.disable()
                PIR_recording.enable()

        return render_template('index.html',
                               stream_status = video_stream.status, streamEnabled=video_stream.button_text, 
                               barrierEnabled=IR_beam_work.button_text, 
                               PIRstatus=PIR_recording.status, PIRenabled=PIR_recording.button_text, 
                               recordingEnabled=video_recording.button_text)

    elif request.method == "GET":
        return render_template('index.html',
                               stream_status = video_stream.status, streamEnabled=video_stream.button_text, 
                               barrierEnabled=IR_beam_work.button_text, 
                               PIRstatus=PIR_recording.status, PIRenabled=PIR_recording.button_text, 
                               recordingEnabled=video_recording.button_text)


# Strona z podgladem wideo na zywo
@app.route('/livestream', methods=["GET"])
def live_stream():
    if video_stream.status:
        return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
    else:
        return "Stream is disabled. Enable it in the menu."


# Strona z logami z czujnika przerwania wiazki IR
@app.route('/beam_log', methods=["GET"])
def beam_log():
    if IR_beam_work.status:
        return Response(beam_sensor(), mimetype="text/plain")
    else:
        return "IR beam sensor is disabled. Enable it in the menu."


# Strona z logami z czujnika ruchu PIR
@app.route('/PIR_log', methods=["GET"])
def PIR_log():
    if PIR_recording.status:
        return Response(PIR_sensor(), mimetype="text/plain")
    else:
        return "PIR sensor is disabled. Enable it in the menu."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000,debug=False,threaded=True)