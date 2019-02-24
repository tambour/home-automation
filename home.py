#!/usr/bin/python

'''
Home automation using raspberry pi

Turn on lights:
    sun has set and first person home
    [anyone home and sun sets]?

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
from astral import Astral

# interval for status print
# -1 for events only
# -2 for silence
PRINT_INTERVAL = 4

COAL_MAC   = 'a0:c9:a0:96:63:26'
OAT_MAC    = '44:91:60:61:a4:94'
WALDO_MAC  = '70:ef:00:4a:cf:1f'
ZIPPER_MAC = '04:4b:ed:56:e4:f3'

COAL_IP   = '10.0.0.20'
OAT_IP    = '10.0.0.10'
WALDO_IP  = '10.0.0.5'
ZIPPER_IP = '10.0.0.8'

INTERFACE = ''
TIMEOUT = 10

class Person():
    def __init__(self, name, mac, ip):
        self.name = name
        self.mac  = mac
        self.ip   = ip
        self.home = False
        self.home_time   = time.time()
        self.home_count  = 0
        self.leave_time  = time.time()
        self.leave_count = 0
        self.timestamp   = time.time()
        self.longest_idle = -1

class Status():
    def __init__(self):
        self.sun_down = False
        self.lights_on = False
        self.someone_home = False
        self.everyone_home = False
        self.last_print = -1
        self.update = False

def turn_on_lights(status):
    '''
    turn on the lights
    '''
    event('[*] Lights on!')
    status.lights_on = True

    try:
        proc = subprocess.Popen(['hue', 'lights', '3', 'on'], stdout=subprocess.PIPE)
        out, err = proc.communicate()
    except:
        # wrong lights or not connected
        pass

    return

def turn_off_lights(status):
    '''
    turn off the lights
    '''
    event('[*] Lights off!')
    status.lights_on = False
    try:
        proc = subprocess.Popen(['hue', 'lights', '3', 'off'], stdout=subprocess.PIPE)
        out, err = proc.communicate()
    except:
        # wrong lights or not connected
        pass

    return

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

    # get arp table
    proc = subprocess.Popen(['arp', '-n'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()

    # check if member in arp
    for member in members:
        if not member.home:
            if member.mac.lower() in out:
                # member in arp table!!
                member.home = True
                member.home_count += 1
                member.timestamp = time.time()
                member.home_time = time.time()
                event('[*] {} is home!'.format(member.name))
                update(status, members)

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

    proc = subprocess.Popen(['arp', '-n'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    for member in members:
        if member.home:
            if member.mac.lower() not in out: #and (time.time() - member.timestamp > TIMEOUT):
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

    # always dark
    #return True

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

    # print('today:\nsunrise: {}\nsunset: {}\n'.format(sunrise_today, sunset_today))
    # print('tomorrow:\nsunrise: {}\nsunset: {}\n'.format(sunrise_tomorrow, sunset_tomorrow))
    # print('current: {}'.format(current_time))

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
            if (time.time() - member.timestamp) > member.longest_idle:
                member.longest_idle = round(time.time() - member.timestamp, 2)

            if member.home:
                debug('[*] {} [{}]:\n    home:     {}\n    count:    {}\n    duration: {}\n    ping:     {}\n'\
                    .format(member.name, member.ip, member.home, member.home_count, \
                        round(time.time() - member.home_time, 2), round(time.time() - member.timestamp, 2)))
            else:
                debug('[*] {} [{}]:\n    home:     {}\n    count:    {}\n    duration: {}\n    ping:     {}\n'\
                    .format(member.name, member.ip, member.home, member.leave_count, \
                        round(time.time() - member.leave_time, 2), round(time.time() - member.timestamp, 2)))

def main():
    '''
    main state machine
    '''

    # change interface to monitor mode
    if INTERFACE != '':
        try:
            os.system('sudo ifconfig {} down'.format(INTERFACE))
            os.system('sudo iwconfig {} mode monitor'.format(INTERFACE))
            os.system('sudo ifconfig {} up'.format(INTERFACE))
        except:
            pass

    # instantiate member list
    members = [Person('Coal',   COAL_MAC,   COAL_IP), \
               Person('Oat',    OAT_MAC,    OAT_IP), \
               Person('Waldo',  WALDO_MAC,  WALDO_IP), \
               Person('Zipper', ZIPPER_MAC, ZIPPER_IP)]

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
                    turn_off_lights(status)

                # check for someone to arrive
                detect_newcomers(status, members)

            # someone / everyone home
            else:

                # turn on lights if they're off and it's dark
                if status.sun_down and not status.lights_on:
                    turn_on_lights(status)

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

            # prevent stack trace tight loop
            time.sleep(0.5)

        except KeyboardInterrupt:
            print_status(status, members)
            debug('[*] Sun down:  {}'.format(status.sun_down))
            debug('[*] Lights on: {}'.format(status.lights_on))
            debug('\n')
            sys.exit(0)

        except:
            traceback.print_exc()


if __name__ == '__main__':
    main()
