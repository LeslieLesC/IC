# -*- coding: utf-8 -*-
"""

"""


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

# duration_sec_acq = duration_sec_send + 0.2 # duracion de la adquisicón de cada paso en segundos

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
lock1 = threading.Lock() # Este lock es para asegurar que la adquisicion este siempre dentro de la señal enviada
lock2 = threading.Lock() # Este lock es para asegurar que no se envie una nueva señal antes de haber adquirido y guardado la anterior
lock1.acquire() # Inicializa el lock, lo pone en cero.

# Defino el thread que envia la señal
data_send = np.zeros([steps,chunk_send],dtype=np.float32)  # aqui guardo la señal enviada
frecs_send = np.zeros(steps)   # aqui guardo las frecuencias

def producer(steps, delta_frec):
    global producer_exit
    samples = (A*np.sin(2*np.pi*np.arange(1*chunk_send)*f/fs)).astype(np.float32)
    samples = np.append(samples, np.zeros(3*chunk_send).astype(np.float32))

        ## Cuadrada
#        samples = A*signal.square(2*np.pi*np.arange(chunk_send)*f/fs).astype(np.float32)
#        samples = np.append(samples, np.zeros(3*chunk_send).astype(np.float32))

        ## Chirp
        #samples = (signal.chirp(np.arange(chunk_send)/fs, frec_ini_hz, duration_sec_send, f, method='linear', phi=0, vertex_zero=True)).astype(np.float32)
        #samples = np.append(samples, np.zeros(3*chunk_send).astype(np.float32))

    data_send[i][:] = samples[0:chunk_send]

    # Se entera que se guardó el paso anterior (lock2), avisa que comienza el nuevo (lock1), y envia la señal
    lock2.acquire()
    lock1.release()
    stream_output.start_stream()
    stream_output.write(samples)
    stream_output.stop_stream()

    producer_exit = True

# Defino el thread que adquiere la señal
data_acq = np.zeros([steps,chunk_acq],dtype=np.int16)  # aqui guardo la señal adquirida

def consumer():
    global consumer_exit
    j = 0
    while(j<steps):

        # Toma el lock, adquiere la señal y la guarda en el array
        lock1.acquire()
        stream_input.start_stream()
        stream_input.read(chunk_delay)
        data_i = stream_input.read(chunk_acq)
        stream_input.stop_stream()

        data_acq[j][:] = np.frombuffer(data_i, dtype=np.int16)

        print ('Termina Consumidor: '+ str(j))
        print ('')
        j = j + 1
        lock2.release() # Avisa al productor que terminó de escribir los datos y puede comenzar con el próximo step

    consumer_exit = True


producer_exit = False
consumer_exit = False

# Inicio los threads
t1 = threading.Thread(target=producer, args=[steps,delta_frec_hz])
t2 = threading.Thread(target=consumer, args=[])
t1.start()
t2.start()


while(not producer_exit or not consumer_exit):
    time.sleep(0.2)



stream_input.close()
stream_output.close()
p.terminate()



#%%

### ANALISIS de la señal adquirida

# Elijo la frecuencia
ind_frec = 5


### Muestra la serie temporal de las señales enviadas y adquiridas
t_send = np.linspace(0,np.size(data_send,1)-1,np.size(data_send,1))/fs
t_adq = np.linspace(0,np.size(data_acq,1)-1,np.size(data_acq,1))/fs

fig = plt.figure(figsize=(14, 7), dpi=250)
ax = fig.add_axes([.15, .15, .75, .8])
ax1 = ax.twinx()
ax.plot(t_send,data_send[ind_frec,:], label=u'Señal enviada: ' + str(frecs_send[ind_frec]) + ' Hz')
ax1.plot(t_adq,data_acq[ind_frec,:],color='red', label=u'Señal adquirida')
ax.set_xlabel('Tiempo [seg]')
ax.set_ylabel('Amplitud [a.u.]')
ax.legend(loc=1)
ax1.legend(loc=4)
plt.show()

### Realiza la FFT de la señal enviada y adquirida
fft_send = abs(fft.fft(data_send[ind_frec,:]))
fft_send = fft_send[0:int(chunk_send/2+1)]
fft_acq = abs(fft.fft(data_acq[ind_frec,:]))
fft_acq = fft_acq[0:int(chunk_acq/2+1)]

frec_send = np.linspace(0,int(chunk_send/2),int(chunk_send/2+1))
frec_send = frec_send/duration_sec_send
frec_acq = np.linspace(0,int(chunk_acq/2),int(chunk_acq/2+1))
frec_acq = frec_acq/duration_sec_acq

fig = plt.figure(figsize=(14, 7), dpi=250)
ax = fig.add_axes([.1, .1, .75, .8])
ax1 = ax.twinx()
ax.plot(frec_send,fft_send, label='Frec enviada: ' + str(frecs_send[ind_frec]) + ' Hz')
ax1.plot(frec_acq,fft_acq,color='red', label=u'Señal adquirida')
ax.set_title(u'FFT de la señal enviada y adquirida')
ax.set_xlabel('Frecuencia [Hz]')
ax.set_ylabel('Amplitud [a.u.]')
ax.legend(loc=1)
ax1.legend(loc=4)
plt.show()

#%%

## Estudo del retardo en caso que delta_frec = 0

i_comp = 10

retardos = np.array([])
for i in range(steps):

    data_acq_i = data_acq[i,:]
    corr = np.correlate(data_acq[i_comp,:] - np.mean(data_acq[i_comp,:]),data_acq_i - np.mean(data_acq_i),mode='full')
    pos_max = np.argmax(corr) - len(data_acq_i)
    retardos = np.append(retardos,pos_max/fs)



fig = plt.figure(figsize=(14, 7), dpi=250)
ax = fig.add_axes([.15, .15, .8, .8])
ax.hist(1000*retardos,bins=1000, rwidth =0.99)
ax.set_xlabel(u'Retardo [ms]')
ax.set_ylabel('Frecuencia [eventos]')
ax.set_title(u'Histograma de retardo respecto a la i = ' + str(i_comp) + ' medición')
ax1.legend(loc=4)
plt.show()


fig = plt.figure(figsize=(14, 7), dpi=250)
ax = fig.add_axes([.15, .15, .8, .8])
ax.hist(retardos*frec_ini_hz,bins=100, rwidth =0.99)
ax.set_xlabel(u'Retardo relativo [periodo]')
ax.set_ylabel('Frecuencia [eventos]')
ax.set_title(u'Histograma de retardo relativo a la duración del período respecto a la i = ' + str(i_comp) + ' medición')
ax1.legend(loc=4)
plt.show()

#%%
plt.plot(np.transpose(data_acq))


plt.plot(np.mean(data_acq[2:,:],axis = 0))



#%%

Is = 1.0*1e-12
Vt = 26.0*1e-3
n = 1.

Vd = np.linspace(-1,1,1000)
Id = Is*(np.exp(Vd/n/Vt)-1)

Rs = 100
Vs = 1
Ir = Vs/Rs - Vd/Rs


plt.plot(Vd,Id)
plt.plot(Vd,Ir)
