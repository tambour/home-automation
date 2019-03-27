#!/usr/bin/python

'''
Home automation using raspberry pi

Turn on lights:
    sun down and someone comes home

Turn off lights:
    lights on and last person leaves
'''

import os
import sys
import time
import pytz
import datetime
import traceback
import subprocess
import configparser
from astral import Astral

# interval for status print
# -1 for events only
# -2 for silence
PRINT_INTERVAL = 4

# set this to test during the day
ALWAYS_DARK = False

# optional iface for sniffing
INTERFACE = ''

# delay between arrival blinks
BLINK_DELAY = 0.2

class Light():
    NONE         = 0
    PHILLIPS_HUE = 1
    MAGIC_LIGHT  = 2

# switch for choosing the right light cmd
LIGHT_TYPE = Light.PHILLIPS_HUE

# ESP_A06205: 192.168.0.9
# ESP_A06006: 192.168.0.10
# ESP_8D7677: 192.168.0.25
# ESP_E57135: 192.168.0.26
# ESP_8D85BB: 192.168.0.27
# ESP_000000: 192.168.0.28
LIGHTS = ['192.168.0.9', \
          '192.168.0.10', \
          '192.168.0.25', \
          '192.168.0.26', \
          '192.168.0.27', \
          '192.168.0.28']

class Person():
    def __init__(self, name, color, mac, ip):
        self.name = name
        self.color = color
        self.mac  = mac
        self.ip   = ip
        self.home = False
        self.home_time   = time.time()
        self.home_count  = 0
        self.leave_time  = time.time()
        self.leave_count = 0
        self.timestamp   = time.time()

class Status():
    def __init__(self):
        self.sun_down = False
        self.lights_on = False
        self.someone_home = False
        self.everyone_home = False
        self.last_print = -1
        self.update = False


def turn_on_lights():
    '''
    turn on the lights
    '''
    event('[*] Lights on!')
    try:
        cmd = []
        if LIGHT_TYPE == Light.PHILLIPS_HUE:
            cmd = ['hue', 'lights', '1,2,3,5', 'on']

        elif LIGHT_TYPE == Light.MAGIC_LIGHT:
            cmd = ['python', '-m', 'flux_led']
            for light in LIGHTS:
                cmd.append(light)
            cmd.append('--on')

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        out, err = proc.communicate()

    except:
        # wrong lights or not connected
        traceback.print_exc()
        pass

    return


def turn_off_lights():
    '''
    turn off the lights
    '''
    event('[*] Lights off!')
    try:
        cmd = []
        if LIGHT_TYPE == Light.PHILLIPS_HUE:
            cmd = ['hue', 'lights', '1,2,3,5', 'off']

        elif LIGHT_TYPE == Light.MAGIC_LIGHT:
            cmd = ['python', '-m', 'flux_led']
            for light in LIGHTS:
                cmd.append(light)
            cmd.append('--off')

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        out, err = proc.communicate()

    except:
        # wrong lights or not connected
        traceback.print_exc()

    return


def flash_lights(status, member):
    '''
    flash lights to member's color
    '''

    # only flash if lights are already on
    if not status.lights_on:
        return

    for i in range(3):
        try:
            cmd = []
            if LIGHT_TYPE == Light.PHILLIPS_HUE:
                cmd = ['hue', 'lights', '2,3', member.color]
            elif LIGHT_TYPE == Light.MAGIC_LIGHT:
                cmd = ['python', '-m', 'flux_led']
                for light in LIGHTS:
                    cmd.append(light)
                cmd.extend(['-c', member.color])

            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = proc.communicate()

            time.sleep(BLINK_DELAY)

            if LIGHT_TYPE == Light.PHILLIPS_HUE:
                cmd = ['hue', 'lights', '2,3', 'reset']
            elif LIGHT_TYPE == Light.MAGIC_LIGHT:
                cmd = ['python', '-m', 'flux_led']
                for light in LIGHTS:
                    cmd.append(light)
                cmd.extend(['-w', '80'])

            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = proc.communicate()

            time.sleep(BLINK_DELAY)

        except:
            traceback.print_exc()


def detect_newcomers(status, members):
    '''
    ping devices and update member status
    '''

    if INTERFACE != '':
        packets = sniff(timeout=2, iface=INTERFACE)

        # check for MAC
        for packet in packets:
            for member in members:
                if (not member.home) and (member.mac in packet.summary()):
                    # someone is home!
                    debug('{} is home!'.format(member.name))
                    member.timestamp = time.time()
                    member.home = True
                    return member


    # ping all members (populates arp table)
    for member in members:
        if not member.home:
            proc = subprocess.Popen(['ping', member.ip, '-w', '2'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = proc.communicate()
            if '0 received' not in out:
                # member responded to ping!
                member.home = True
                member.home_count += 1
                member.timestamp = time.time()
                member.home_time = time.time()
                event('[*] {} is home!'.format(member.name))
                update(status, members)
                flash_lights(status, member)

    # get arp table
    proc = subprocess.Popen(['/usr/sbin/arp', '-n'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()

    # check if member in arp
    for member in members:
        if not member.home:
            if out and member.mac.lower() in out:
                # member in arp table!!
                member.home = True
                member.home_count += 1
                member.timestamp = time.time()
                member.home_time = time.time()
                event('[*] {} is home!'.format(member.name))
                update(status, members)
                flash_lights(status, member)


def detect_absence(status, members):
    '''
    check for member to leave
    '''
    # ping all present members
    for member in members:
        if member.home:
            proc = subprocess.Popen(['ping', member.ip, '-w', '2'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = proc.communicate()
            if '0 received' not in out:
                member.timestamp = time.time()

    proc = subprocess.Popen(['/usr/sbin/arp', '-n'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    for member in members:
        if member.home:
            if member.mac.lower() not in out:
                # member left
                member.home = False
                member.leave_count += 1
                member.leave_time = time.time()
                event('[*] {} has left!'.format(member.name))
                update(status, members)
            else:
                member.timestamp = time.time()


def darkness_comes():
    '''
    return true if the sun has set in Columbus
    '''

    if ALWAYS_DARK:
        return True

    city_name = 'Columbus'
    a = Astral()
    a.solar_depression = 'civil'
    city = a[city_name]
    timezone = city.timezone

    sun_today = city.sun(date=datetime.datetime.now(), local=True)
    sunrise_today = sun_today['sunrise']
    sunset_today = sun_today['sunset']

    sun_tomorrow = city.sun(date=datetime.datetime.today() + datetime.timedelta(days=1), local=True)
    sunrise_tomorrow = sun_tomorrow['sunrise']
    sunset_tomorrow = sun_tomorrow['sunset']

    current_time = datetime.datetime.now(pytz.timezone('America/New_York'))

    # dark means it's earlier than sunrise or later than sunset
    if (current_time < sunrise_today) or (current_time > sunset_today and current_time < sunrise_tomorrow):
        # sun is down!
        return True
    else:
        # sun is up!
        return False


def debug(print_str):
    if PRINT_INTERVAL != -1:
        print(print_str)
    f = open('./out.txt', 'a')
    f.write(print_str+'\n')
    f.close()

def event(event_str):
    if PRINT_INTERVAL != -2:
        print(event_str)
    f = open('./event.txt', 'a')
    f.write('[{}]: {}\n'.format(datetime.datetime.now(), event_str))
    f.close()

def update(status, members):
    '''
    check member status to set program state
    '''
    status.someone_home = False
    for member in members:
        if member.home:
            status.someone_home = True

    status.everyone_home = True
    for member in members:
        if not member.home:
            status.everyone_home = False

    # flag that there is an updated status available
    status.update = True


def print_status(status, members):
    '''
    print status
    '''
    debug('\n')
    debug('[*] Sun Down:  {}'.format(status.sun_down))
    debug('[*] Lights on: {}\n'.format(status.lights_on))
    for member in members:
        if member.home_count > 0: # only print for members who have been home
            if member.home:
                debug('[*] {} [{}]:\n    home:     {}\n    count:    {}\n    duration: {}\n    ping:     {}\n'\
                    .format(member.name, member.ip, member.home, member.home_count, \
                        round(time.time() - member.home_time, 2), round(time.time() - member.timestamp, 2)))
            else:
                debug('[*] {} [{}]:\n    home:     {}\n    count:    {}\n    duration: {}\n    ping:     {}\n'\
                    .format(member.name, member.ip, member.home, member.leave_count, \
                        round(time.time() - member.leave_time, 2), round(time.time() - member.timestamp, 2)))


def main():

    # change interface to monitor mode
    if INTERFACE != '':
        try:
            os.system('sudo ifconfig {} down'.format(INTERFACE))
            os.system('sudo iwconfig {} mode monitor'.format(INTERFACE))
            os.system('sudo ifconfig {} up'.format(INTERFACE))
        except:
            pass


    # read in config file
    config = configparser.ConfigParser()
    config.read('conf.ini')

    members = []
    for person in config.sections():
        members.append(\
            Person(person, \
                config[person]['Color'], \
                config[person]['MAC'], \
                config[person]['IP']))


    # set initial status
    status = Status()

    # loop forever
    while True:
        try:

            # check for darkness
            if not status.sun_down and darkness_comes():
                # only set sun_down when no one is home
                # prevents lights from turning on right at sunset
                if not status.someone_home:
                    event('[*] Darkness comes!')
                    status.sun_down = True
            elif status.sun_down and not darkness_comes():
                event('[*] Sun has risen!')
                status.sun_down = False

            # no one home
            if not status.someone_home:

                # turn off lights if they're on
                if status.lights_on:
                    turn_off_lights()
                    status.lights_on = False

                # check for someone to arrive
                detect_newcomers(status, members)

            # someone / everyone home
            else:

                # turn on lights if they're off and it's dark
                if status.sun_down: #and not status.lights_on:
                    turn_on_lights()
                    status.lights_on = True

                # check for someone to leave
                detect_absence(status, members)

                if not status.everyone_home:
                    # check for someone to arrive
                    detect_newcomers(status, members)

            # print status
            if ((time.time() - status.last_print > PRINT_INTERVAL) or status.update) \
                and PRINT_INTERVAL > -1:
                status.last_print = time.time()
                status.update = False
                print_status(status, members)

            time.sleep(1)

        except KeyboardInterrupt:
            print_status(status, members)
            debug('\n')
            sys.exit(0)

        except:
            traceback.print_exc()
            time.sleep(1)


if __name__ == '__main__':
    main()
