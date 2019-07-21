import math
import machine
import neopixel
from utime import ticks_diff, ticks_ms, ticks_add, sleep_ms
#  import http_api_handler
#  import uhttpd
import uasyncio as asyncio
#  from ApiHandler import ApiHandler
from math import sin
#Auge1 0-11 Auge2 12-23 Kiemen1 24-x Kiemen2 x+1-y Inner y+1-max

import socket
import uselect
import network
import sys

MCAST_PORT = 8765
MCAST_GROUP = '224.1.1.1'


PIXEL_COUNT = 60
np = neopixel.NeoPixel(machine.Pin(5), PIXEL_COUNT)
STROBE_INTERVAL = 40
STROBE_TOTAL = 5000
PULSE_DURATION = 100
MAX_PULSE_LIGHT = 150 
CHANGE = False

class Module(object):
    def __init__(self, pixels, color=None, intensity=1.0):
        self.pixels = pixels
        self.color = color
        self.intensity = intensity
        self.mode = None

    def all_pixels(self, onoff=True, color=None):
        global CHANGE
        if onoff:
            color = self._color_intensity(color)
        else:
            color = (0, 0, 0)
        for pixel in self.pixels:
            np[pixel] = color
        CHANGE = True

    def _color_intensity(self, color=None):
        if color is None:
            return tuple(int(self.intensity * self.color[i]) for i in range(3))
        else:
            return tuple(int(self.intensity * color[i]) for i in range(3))


class Qualle(Module):

    def __init__(self, pixels, color, intensity=1):
        super(Qualle, self).__init__(pixels, color, intensity)
        self.all_pixels()
        self.mode = "pulse"
        self.pulse_rise = True
        self.last_tick = ticks_ms()
        self.strobo_on = True
        self.strobo_length = 1000
        self.strobo_start = ticks_ms()
        self.last_mode = "pulse"
        self.blink_tick = ticks_ms()

    def step(self, ticks):
        if abs(ticks_diff(self.blink_tick, ticks)) < 200:
            return

        if self.mode == "pulse":
            if abs(ticks_diff(self.last_tick, ticks)) < PULSE_DURATION:
                return
            self.last_tick = ticks
            if self.pulse_rise:
                if self.color[2] >= MAX_PULSE_LIGHT:
                    self.pulse_rise = False
                else:
                    self.color = (0, max(self.color[1] - 1, 0), self.color[2] + 1)
            else:
                if (self.color[2] <=0):
                    self.pulse_rise = True
                else:
                    self.color = (0, self.color[1] + 1, max(self.color[2] - 1, 0))
            # print(self.color)
            self.all_pixels()

        elif self.mode == "strobo":
            if abs(ticks_diff(self.strobo_start, ticks)) > self.strobo_length:
                self.mode = self.last_mode

            elif abs(ticks_diff(self.last_tick, ticks)) > STROBE_INTERVAL:
                #  print(self.strobo_on)
                if self.strobo_on:
                    self.strobo_on = not self.strobo_on
                    self.all_pixels(True, (250,250,250))
                else:
                    self.strobo_on = not self.strobo_on
                    self.all_pixels(onoff=False)
                self.last_tick = ticks

    def blink(self):
        self.all_pixels(True, (255, 255, 0))
        self.blink_tick = ticks_ms()


    def set_mode(self, mode):
        if(self.mode != "strobo"):
            self.last_mode = self.mode
        self.mode = mode
        if mode == "strobo":
            self.strobo_start = ticks_ms()

def init_modules():
    qualle1 =Qualle(list(range(20)), (0, 0, MAX_PULSE_LIGHT))
    qualle2 = Qualle(list(range(20,40)), (0, 0, MAX_PULSE_LIGHT))
    qualle3 = Qualle(list(range(40,60)), (0, 0, MAX_PULSE_LIGHT))

    return {'1': qualle1, '2': qualle2, '3': qualle3}


SERVER = "192.168.0.101"

async def tcp_receiver(modules):
    sta_if = network.WLAN(network.STA_IF)
    ap_if = network.WLAN(network.AP_IF)
    if not sta_if.isconnected():
        print('connecting to network...')
        sta_if.active(True)
        #sta_if.connect('Incubator', 'Fl4mongo')
        sta_if.connect('Fischnetz', 'incubator')
        while not sta_if.isconnected():
            await asyncio.sleep_ms(10)
    ap_if.active(False)

    print('network config sta_if:', sta_if.active())
    print('network config ap_if:', ap_if.active())
    print('network config:', sta_if.ifconfig())

    poller = uselect.poll()
    sock = None

    is_connected = False
    while not is_connected:
        try:
            print("trying to connect to server")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((SERVER, 7654))
            is_connected = True
        except Exception as e:
            print(str(e))
        await asyncio.sleep_ms(1000)
    poller.register(sock, uselect.POLLIN)

    while True:
        ret = poller.poll(0)

        if not ret:
            await asyncio.sleep_ms(1)
            continue

        #  print(str(ret))

        obj, event = ret[0]
        #  print(str(obj))
        #  print(str(event))
        if event == uselect.POLLHUP:
            print("POLLHUP")
            print(uselect.POLLHUP)
        elif event == uselect.POLLERR:
            print("POLLERR")
            print(uselect.POLLERR)
        else:
            s = obj
            data = s.readline()
            print(str(data))

            if len(data) == 0:
                poller.unregister(s)
                is_connected = False
                while not is_connected:
                    try:
                        print("trying to connect to server")
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.connect((SERVER, 7654))
                        is_connected = True
                    except Exception as e:
                        print(str(e))
                    await asyncio.sleep_ms(1000)
                poller.register(sock, uselect.POLLIN)

            if data.startswith(b'flash'):
                #  print("BLINK")
                try:
                    id = int(data[6:8])
                    if(id == 0):
                        for module in modules.values():
                            module.blink()
                    elif(str(id) in modules.keys()):
                        modules[str(id)].blink()
                    np.write()
                except Exception as e:
                    print(e)

                #  blink_tick = ticks_ms()

            elif data.startswith(b'set max_brightness'):
                brightness = int(data[19:22])
                print(str(brightness))
                print("set max_brightness")
                intensity = brightness / 255.0
                for module in modules.values():
                    module.intensity = intensity

            elif data.startswith(b'kill'):
                sys.exit(0)

            elif data.startswith(b'set strobo_duration'):
                duration = int(data[20:23])
                print("Strobo duration set to", str(duration))
                for module in modules.values():
                    module.strobo_length = duration*1000

            elif data.startswith(b'strobo'):
                print("Strobo")
                for module in modules.values():
                    module.set_mode("strobo")

        await asyncio.sleep_ms(1)
    sock.close()

async def udp_receiver(modules):
    global intensity

    sta_if = network.WLAN(network.STA_IF)
    ap_if = network.WLAN(network.AP_IF)
    if not sta_if.isconnected():
        print('connecting to network...')
        sta_if.active(True)
        #sta_if.connect('Incubator', 'Fl4mongo')
        sta_if.connect('Fischnetz', 'incubator')
        while not sta_if.isconnected():
            await asyncio.sleep_ms(10)
    ap_if.active(False)

    print('network config sta_if:', sta_if.active())
    print('network config ap_if:', ap_if.active())
    print('network config:', sta_if.ifconfig())

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(False)
    addr = socket.getaddrinfo("0.0.0.0", MCAST_PORT)[0][-1]
    sock.bind(addr)
    opt = bytes([224, 1, 1, 1]) + bytes([0, 0, 0, 0])
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, opt)

    poller = uselect.poll()
    poller.register(sock, uselect.POLLIN)

    while True:
        res = poller.poll(-1)  # time in milliseconds
        if not res is None:
            print(str(res))
            s = res[0][0]
            (data, _address) = s.recvfrom(1024)
            print(str(data))
            if data.startswith(b'flash'):
                print("BLINK")
                id = int(data[6:8])
                if(id == 0):
                    for module in modules.values():
                        module.blink()
                elif(str(id) in modules.keys()):
                    modules[str(id)].blink()
                np.write()

            elif data.startswith(b'set max_brightness'):
                brightness = int(data[19:22])
                print(str(brightness))
                print("set max_brightness")
                intensity = brightness / 255.0
                for module in modules.values():
                    module.intensity = intensity
            elif data.startswith(b'set strobo_duration'):
                duration = int(data[20:23])
                print("Strobo duration set to", str(duration))
                for module in modules.values():
                    module.strobo_length = duration*1000
            elif data.startswith(b'strobo'):
                print("Strobo")
                for module in modules.values():
                    module.set_mode("strobo")
        await asyncio.sleep_ms(1)
        #  try:
            #  (data, _address) = sock.recvfrom(1024)
            #  print(str(data))
            #  if data.startswith(b'flash'):
                #  print("BLINK")
                #  id = int(data[6:8])
                #  blink_tick = ticks_ms()
                #  if(id == 0):
                    #  for module in modules.values():
                        #  module.blink()
                #  elif(str(id) in modules.keys()):
                    #  modules[str(id)].blink()
                #  np.write()

            #  elif data.startswith(b'set max_brightness'):
                #  brightness = int(data[19:22])
                #  print(str(brightness))
                #  print("set max_brightness")
                #  intensity = brightness / 255.0
                #  for module in modules.values():
                    #  module.intensity = intensity
            #  elif data.startswith(b'set strobo_duration'):
                #  duration = int(data[20:23])
                #  print("Strobo duration set to", str(duration))
                #  for module in modules.values():
                    #  module.strobo_length = duration*1000
            #  elif data.startswith(b'strobo'):
                #  print("Strobo")
                #  for module in modules.values():
                    #  module.set_mode("strobo")
        #  except OSError:
            #  pass
        #  await asyncio.sleep_ms(1)



async def real_main(modules):
    global CHANGE
    while True:
        ticks = ticks_ms()

        for module in modules.values():
            module.step(ticks)

        if CHANGE:
            np.write()
            CHANGE = False
        #sleep_ms(20)
        await asyncio.sleep_ms(1)

def main():
    modules = init_modules()
    #main(modules)
    #api_handler = http_api_handler.Handler([([''], ApiHandler(modules))])
    loop = asyncio.get_event_loop()
    loop.create_task(real_main(modules))
    loop.create_task(tcp_receiver(modules))
    loop.run_forever()
    #server = uhttpd.Server([('/api', api_handler)])
    #server.run()

if __name__ == "__main__":
    main()
