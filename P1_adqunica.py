# -*- coding: utf-8 -*-

"""
Descripción:
------------
Este script realiza una adquisición a frecuencia fija utilizando la salida y entrada de audio como emisor-receptor.
Utiliza la libreria pyaudio para generar las señales de salida y la entrada de adquisición.
El script lanza dos thread o hilos que se ejecutan contemporaneamente:
uno para la generación de la señal (producer) y otro para la adquisicón (consumer).
El script está programado para que el hilo productor envie una señal y habilite en ese momento la adquisición del hilo consumidor.
La señal enviada se guarda en el array data_send.
La señal adquirida se guarda en el array data_acq.


Algunas dudas:
--------------
    - El buffer donde se lee la adquisición guarda datos de la adquisicón correspondiente al paso anterior. Para evitar esto se borran
    los primeros datos del buffer, pero no es muy profesional. La cantidad de datos agregados parece ser independiente del tiempo de adquisición
    o la duración de la señal enviada.
    - La señal digital que se envia debe ser cuatro veces mas larga que la que se envía analógicamente. No entiendo porqué.
    - Se puede mejorar la variabilidad en el retardo entre señal enviada y adquirida? Es decir se puede mejorar la sincronización entre los dos procesos?

Falta:
------
    - Mejorar la interrupción del script por el usuario. Por el momento termina únicamente cuando termina la corrida.

Notas:
--------
- Cambio semaforo por lock. Mejora la sincronización en +/- 1 ms.
- Define un chunk_acq_eff que tiene en cuenta el delay inicial
- Cambiar Event por Lock no cambia mucho
- Cuando duration_sec_send > duration_sec_adq la variabilidad del retardo entre los procesos es aprox +/- 1 ms, salvo para la primera medición
- Cuando duration_sec_send < duration_sec_adq la variabilidad del retardo es muchas veces nula, salvo para la primera medición
- Obligo a que la duración de adquisición  > duración de la señal enviada para mejorar la sincronización.


Parametros:
-----------
fs = 44100 # frecuencia de sampleo en Hz
frec_ini_hz = 10 # frecuencia inicial de barrido en Hz
frec_fin_hz = 40000 # frecuencia inicial de barrido en Hz
steps = 50 # cantidad de pasos del barrido
duration_sec_send = 0.3 # duracion de la señal de salida de cada paso en segundos
A = 0.1 # Amplitud de la señal de salida

"""

#%%
import pyaudio
import numpy as np
import matplotlib.pyplot as plt
import threading
import numpy.fft as fft
import datetime
import time
import matplotlib.pylab as pylab
from scipy import signal

params = {'legend.fontsize': 'medium',
     #     'figure.figsize': (15, 5),
         'axes.labelsize': 'medium',
         'axes.titlesize':'medium',
         'xtick.labelsize':'medium',
         'ytick.labelsize':'medium'}
pylab.rcParams.update(params)

# Parametros
fs = 44100 # frecuencia de sampleo en Hz
frec_ini_hz = 440 # frecuencia de barrido en Hz
duration_sec_send = 1 # duracion de la señal de salida en segundos
A = 0.5 # Amplitud de la señal de salida

duration_sec_acq = duration_sec_send + 0.2 # duracion de la adquisicón de cada paso en segundos

# Inicia pyaudio
p = pyaudio.PyAudio()

# Defino los buffers de lectura y escritura
chunk_send = int(fs*duration_sec_send)
chunk_acq = int(fs*duration_sec_acq)

# defino el stream del parlante
stream_output = p.open(format=pyaudio.paFloat32,
                channels = 1,
                rate = fs,
                output = True,
                #input_device_index = 4,
)

# Defino un buffer de lectura efectivo que tiene en cuenta el delay de la medición
chunk_delay = int(fs*stream_output.get_output_latency())
chunk_acq_eff = chunk_acq + chunk_delay
# Defino el stream del microfono
stream_input = p.open(format = pyaudio.paInt16,
                channels = 1,
                rate = fs,
                input = True,
                frames_per_buffer = chunk_acq_eff*p.get_sample_size(pyaudio.paInt16),
)

# Defino los semaforos para sincronizar la señal y la adquisicion
# lock1 = threading.Lock() # Este lock es para asegurar que la adquisicion este siempre dentro de la señal enviada
# lock2 = threading.Lock() # Este lock es para asegurar que no se envie una nueva señal antes de haber adquirido y guardado la anterior
# lock1.acquire() # Inicializa el lock, lo pone en cero.

# Defino el thread que envia la señal
f = frec_ini_hz
data_send = np.zeros(chunk_send,dtype=np.float32)  # aqui guardo la señal enviada

def producer():
    global producer_exit
    samples = (A*np.sin(2*np.pi*np.arange(1*chunk_send)*f/fs)).astype(np.float32)
    samples = np.append(samples, np.zeros(3*chunk_send).astype(np.float32))

        ## Cuadrada
#        samples = A*signal.square(2*np.pi*np.arange(chunk_send)*f/fs).astype(np.float32)
#        samples = np.append(samples, np.zeros(3*chunk_send).astype(np.float32))

        ## Chirp
        #samples = (signal.chirp(np.arange(chunk_send)/fs, frec_ini_hz, duration_sec_send, f, method='linear', phi=0, vertex_zero=True)).astype(np.float32)
        #samples = np.append(samples, np.zeros(3*chunk_send).astype(np.float32))

    data_send = samples[0:chunk_send]

    # Se entera que se guardó el paso anterior (lock2), avisa que comienza el nuevo (lock1), y envia la señal
    # lock2.acquire()
    # lock1.release()
    stream_output.start_stream()
    stream_output.write(samples)
    stream_output.stop_stream()

    print ('Termina Productor')
    print (data_send)

    producer_exit = True

# Defino el thread que adquiere la señal
data_acq = np.zeros(chunk_acq,dtype=np.int16)  # aqui guardo la señal adquirida
# print (data_send)
def consumer():
    global consumer_exit
    # Toma el lock, adquiere la señal y la guarda en el array
    # lock1.acquire()

    stream_input.start_stream()
    stream_input.read(chunk_delay)
    data_i = stream_input.read(chunk_acq)

    stream_input.stop_stream()

    data_acq = np.frombuffer(data_i, dtype=np.int16)

    print ('Termina Consumidor')

    # lock2.release() # Avisa al productor que terminó de escribir los datos y puede comenzar con el próximo step

    consumer_exit = True


producer_exit = False
consumer_exit = False

# Inicio los threads
t1 = threading.Thread(target=producer, args=[])
t2 = threading.Thread(target=consumer, args=[])
t1.start()
t2.start()

while(not producer_exit):
    time.sleep(0.2)
    print (data_send)


# while(not producer_exit or not consumer_exit):
#     time.sleep(0.2)



stream_input.close()
stream_output.close()
p.terminate()


#%%
#
### ANALISIS de la señal adquirida

# Elijo la frecuencia
ind_frec = 5


### Muestra la serie temporal de las señales enviadas y adquiridas
t_send = np.linspace(0,np.size(data_send)-1,np.size(data_send))/fs
t_adq = np.linspace(0,np.size(data_acq)-1,np.size(data_acq))/fs
plt.figure()
plt.plot(t_send,data_send, label=u'Señal enviada: %.1f'%(frec_ini_hz)) # + str(frec_ini_hz) + ' Hz')
plt.plot(t_adq,data_acq,color='red', label=u'Señal adquirida')
plt.xlabel('Tiempo [seg]')
plt.ylabel('Amplitud [a.u.]')
plt.legend()
# fig = plt.figure(figsize=(14, 7), dpi=250)
# ax = fig.add_axes([.15, .15, .75, .8])
# ax1 = ax.twinx()
# ax.plot(t_send,data_send, label=u'Señal enviada: ' + str(frec_ini_hz) + ' Hz')
# ax1.plot(t_adq,data_acq,color='red', label=u'Señal adquirida')
# ax.set_xlabel('Tiempo [seg]')
# ax.set_ylabel('Amplitud [a.u.]')
# ax.legend(loc=1)
# ax1.legend(loc=4)
plt.show()
#
