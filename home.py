#!/usr/bin/python

'''
Home automation using raspberry pi
'''
import os
import sys
import time
import pytz
import datetime
import traceback
import subprocess
from astral import Astral

PRINT_INTERVAL = 10

COAL_MAC   = '00:00:00:00:00:00'
OAT_MAC    = '44:91:60:61:a4:94'
WALDO_MAC  = '70:ef:00:4a:cf:1f'
ZIPPER_MAC = '04:4B:ED:56:E4:F3'

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
        self.dark = False
        self.lights_on = False
        self.someone_home = False
        self.everyone_home = False
        self.last_print = -100
        self.update = False

def turn_on_lights(status):
    '''
    turn on the lights
    '''
    event('[*] lights on!')
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
    event('[*] lights off!')
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
                event('[*] {} is home!\tcount: {}, duration: {}'.format(member.name, member.home_count, round(member.home_time - member.leave_time, 2)))
                update(status, members)

    # ping all members
    for member in members:
        if not member.home:
            proc = subprocess.Popen(['ping', member.ip, '-c', '1', '-w', '1'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            out, err = proc.communicate()
            if '0 received' not in out:
                # member responded to ping!
                member.home = True
                member.home_count += 1
                member.timestamp = time.time()
                member.home_time = time.time()
                event('[*] {} is home!\tcount: {}, duration: {}'.format(member.name, member.home_count, round(member.home_time - member.leave_time, 2)))

def detect_absence(status, members):
    '''
    check for member to leave
    '''
    # ping all present members
    for member in members:
        if member.home:
            proc = subprocess.Popen(['ping', member.ip, '-c', '1', '-w', '1'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
                event('[*] {} has left! count: {}, duration: {}'.format(member.name, member.leave_count, round(member.leave_time - member.home_time, 2)))
                update(status, members)
            else:
                member.timestamp = time.time()

def darkness_comes():
    '''
    return true if the sun has set
    '''
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

    #print('today:\nsunrise: {}\nsunset: {}\n'.format(sunrise_today, sunset_today))
    #print('tomorrow:\nsunrise: {}\nsunset: {}\n'.format(sunrise_tomorrow, sunset_tomorrow))
    #print('current: {}'.format(current_time))

    if (current_time < sunrise_today) or (current_time > sunset_today and current_time < sunrise_tomorrow):
        # it's dark!
        return True
    else:
        # it's light!
        return False

def debug(print_str):
    print(print_str)
    f = open('./out.txt', 'a')
    f.write(print_str+'\n')
    f.close()

def event(event_str):
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
    print member status
    '''
    debug('\n')
    for member in members:
        if member.home_count > 0:
            if (time.time() - member.timestamp) > member.longest_idle:
                member.longest_idle = round(time.time() - member.timestamp, 2)
            if member.home:
                debug('{} [{}]:\n  home:     {}\n  count:    {}\n  duration: {}\n  ping:     {}\n'\
                    .format(member.name, member.ip, member.home, member.home_count, \
                        round(time.time() - member.home_time, 2), round(time.time() - member.timestamp, 2)))
            else:
                debug('{} [{}]:\n  home:     {}\n  count:    {}\n  duration: {}\n  ping:     {}\n'\
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

    members = [Person('Waldo', WALDO_MAC, WALDO_IP), \
               Person('COAL', COAL_MAC, COAL_IP), \
               Person('Oat', OAT_MAC, OAT_IP), \
               Person('Zipper', ZIPPER_MAC, ZIPPER_IP)]

    status = Status()
    status.dark = darkness_comes()
    debug('\n[*] Sun Down: {}'.format(status.dark))

    while True:
        try:

            # print status
            if (time.time() - status.last_print > PRINT_INTERVAL) or status.update:
                status.last_print = time.time()
                status.update = False
                print_status(status, members)

            # check for darkness
            status.dark = darkness_comes()

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
                if status.dark and not status.lights_on:
                    turn_on_lights(status)

                # check for someone to leave
                detect_absence(status, members)

                if not status.everyone_home:
                    # check for someone to arrive
                    detect_newcomers(status, members)

            # prevent tight loop
            time.sleep(0.1)

        except KeyboardInterrupt:
            print_status(status, members)
            debug('[*] Sun down:  {}'.format(status.dark))
            debug('[*] Lights on: {}'.format(status.lights_on))
            debug('\n')
            sys.exit(0)

        except:
            traceback.print_exc()


if __name__ == '__main__':
    main()
