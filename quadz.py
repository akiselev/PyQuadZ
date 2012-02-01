import serial
import re
import gexceptions
from serialqueue import SerialQueue

class QuadZDevice():
    def __init__(self, com_port = 1):
        self.device = serial.Serial(com_port, 19200, \
                                    parity = serial.PARITY_EVEN, \
                                    timeout = 1)
        if not self.device:
            raise gexceptions.DeviceNotFound
        
        self.queue = SerialQueue(self.device)
        self.queue.start()
        
        self.syringe_pumps = {}
        self.syringe_pump_devices = []
        
        self.probe_map = {1: 'a', 2: 'b', 3: 'c', 4: 'd'}
        
        # Positioning constants
        self.base_z = 0
        self.base_tip_height = 10
        self.current_tip_height = 20
        
        # Cached variables
        self.liquid_sensitivity = {}
        self.liquid_detector_status = {}
        self.probe_speed = {}
        self.probe_x_range = {}
        self.xyz_range = {}
        self.home_phase = {}
        self.motor_status = {}
        
        self.time_delay = .05
        
        # Syringe pump data
        """syringe_default = {'device_id': -1,
                           'side': None,
                           'syringe_size': 0,
                           'partner_probe': 0,
                           'status': 'I',
                           'current_volume': 0,
                           'valve_status': 'N',
                           'motor_force': 3,
                           'flow_rate': 10,
                           'next_operation': 0}
        self.syringe = {1: syringe_default, 2: syringe_default,
                        3: syringe_default, 4: syringe_default}"""
        
        self.syringe = {}
        for i in range(4):
            self.syringe[i+1] = {'device_id': -1,
                                   'side': None,
                                   'syringe_size': 0,
                                   'partner_probe': 0,
                                   'status': 'I',
                                   'current_volume': 0,
                                   'valve_status': 'N',
                                   'motor_force': 3,
                                   'flow_rate': 10,
                                   'next_operation': 0}
        self.syringe_devices = []
    
    def initialize_device(self, device_id = 22):
        """
        Initialize device and set up  probe widths, ranges, etc.
        
        Arguments:
        device_id -- Gilson Quad-Z ID (default 22)
        
        Returns:
        True if connected, False if not
        """
        self.device_id = device_id
        if self.queue.register_device(device_id):
            """self.get_liquid_sensitivity()
            self.get_liquid_detector_status()
            self.get_motor_status()
            self.get_home_phase()
            self.get_probe_speed()
            self.get_probe_x_range()
            self.get_travel_range()"""
            return True
        return False

    def sleep(self, seconds, parent = None):
        self.queue.sleep(seconds, parent)
    
    def immediate(self, instruction, device_id = -1):
        """
        Send an immediate command
        
        Arguments:
        instruction -- command to send
        device_id -- device ID to send to. If it's -1, send to liquid handler
        """
        if device_id == -1:
            device_id = self.device_id
        result = self.queue.add_immediate_instruction(device_id, instruction)
        if not result:
            self.queue.log.debug('EXCEPTION ---- ' + str(self.queue.last_exception))
            return False
        return result
    
    def buffered(self, instruction, device_id = -1):
        """
        Send buffered command
        
        Arguments:
        instruction -- command to send
        device_id -- device id to send to. If set to -1, send to liquid handler
        """
        if device_id == -1:
            device_id = self.device_id
        wait = True
        if device_id in self.syringe_devices:
            wait = 'pump'
        # TODO: Add code for checking if it is injection module
        return self.queue.add_buffered_instruction(device_id, instruction,
                                                   wait = wait)
    
    def get_version(self):
        """
        Get liquid handler identifier and software version
        
        Returns:
        version string
        """
        return self.immediate('%')
    
    def reset(self):
        """
        Reset liquid handler
        """
        return self.immediate('$')
    
    def get_home_phase(self):
        """
        Get motor home phase
        
        Returns:
        dict where:
            X - x motor home phase
            Y - y motor home phase
        """
        phase = self.immediate('A')
        phase = phase.split('/')
        return {'X': int(phase[0]), 'Y': int(phase[1])}
    
    def get_last_error(self):
        """
        Get last error to occur
        
        Returns:
        error code of last error
        """
        return int(self.immediate('e'))
    
    def get_liquid_sensitivity(self):
        """
        Get liquid level sensing sensitivity
        
        Returns:
        dict where:
            # - Probe # liquid level sensitivity (where # = 1-4)
        """
        sensitivity = self.immediate('K')
        sensitivity = sensitivity.split(',')
        self.liquid_sensitivity = {1: int(sensitivity[0]),
                                   2: int(sensitivity[1]),
                                   3: int(sensitivity[2]),
                                   4: int(sensitivity[3])}
        return self.liquid_sensitivity
    
    def get_motor_status_2(self):
        """
        Get motor status
        
        Returns:
        dict -- where:
            X - x motor status
            Y - y motor status
            Z - z motor status
            D - dilutor motor status (unuzed on Quad-Z)
        """
        status = self.immediate('M')
        self.motor_status = {'X': status[0], 'Y': status[1], 
                            'Z': status[2], 'D': status[3]}
        return self.motor_status
    
    def get_motor_status(self):
        """
        Get motor status
        
        Returns:
        dict -- where:
            X - x motor status
            Y - y motor status
            Z# - probe # motor statusv (where # = 1-4)
            P - Unused on Quad-Z
        """
        status = self.immediate('m')
        self.motor_status = {'X': status[0], 'Y': status[1], 
                            'Z1': status[2], 'Z2': status[3], 'Z3': status[4], 
                            'Z4': status[5], 'P': status[6]} 
        return self.motor_status
    
    def get_liquid_detector_status(self):
        """
        Get liquid detector status
        
        Returns:
        dict where:
            # - Probe # status (where # = 1-4)
        """
        status = self.immediate('N')
        self.liquid_detector_status = {1: status[0], 2: status[1], 
                                      3: status[2], 4: status[3]} 
        return self.liquid_detector_status
    
    def get_probe_speed(self):
        """
        Get probe speed in micrometers
        
        Returns:
        dict where:
            # - Probe # speed (where # = 1-4)
        """
        speed = self.immediate('O')
        speed = speed.split(',')
        self.probe_speed = {1: int(speed[0]), 2: int(speed[1]),
                            3: int(speed[2]), 4: int(speed[3])}
        return self.probe_speed 
    
    def get_encoder_position(self):
        """
        Get linear encoder position in tenths of millimeters
        
        Returns:
        dict where:
            x - x axis position
            y - y axis position
        """
        position = self.immediate('P')
        position = position.split('/')
        return {'X': position[0], 'Y': position[1]}
    
    def get_probe_x_range(self):
        """
        Get probe x range in tenths of millimeters
        
        Returns:
        dict of tuples (x-min, x-max) where:
            # - Probe # x range (where # = 1-4)
        """
        ranges = {}
        for i in range(4):
            range_ = self.immediate('q')
            range_ = range_.split('=')
            range_nums = range_[1].split('/')
            ranges[range_[0]] = range_nums
        self.probe_x_range = {1: (int(ranges['a'][0]), int(ranges['a'][1])),
                              2: (int(ranges['b'][0]), int(ranges['b'][1])),
                              3: (int(ranges['c'][0]), int(ranges['c'][1])),
                              4: (int(ranges['d'][0]), int(ranges['d'][1]))}
        return self.probe_x_range
    
    def get_travel_range(self):
        """
        Get gantry travel range in tenths of millimeters
        
        Returns:
        dict of tuples (min, max) where:
            X - x axis range
            Y - y axis range
            Z - z axis range
        """
        ranges = {}
        for i in range(3):
            range_ = self.immediate('Q')
            range_ = range_.split('=')
            range_nums = range_[1].split('/')
            ranges[range_[0]] = range_nums
        self.xyz_range = {'X': (int(ranges['X'][0]), int(ranges['X'][1])),
                          'Y': (int(ranges['Y'][0]), int(ranges['Y'][1])),
                          'Z': (int(ranges['Z'][0]), int(ranges['Z'][1]))}
        return self.xyz_range
    
    def get_led_text(self):
        """
        Get LED text
        
        Returns:
        string
        """
        return self.immediate('R')
    
    def get_sync_buffer(self):
        """
        Get synchronous command buffer
        
        Returns:
        string
        """
        return self.immediate('S')
    
    def get_last_probe_z_position(self):
        """
        Get last probe z position in tenths of millimeters
        
        Returns:
        dict where:
            # - Probe # z position (where # = 1-4)
        """
        height = self.immediate('T')
        height = height.split(',')
        return {1: int(height[0]), 2: int(height[1]), 
                3: int(height[2]), 4: int(height[3])}
    
    def get_probe_width(self):
        """
        Get probe spacing in tenths of millimeters
        
        Returns:
        integer
        """
        return int(self.immediate('w'))
    
    def get_x_motor_status(self):
        """
        Get x motor status
        
        Returns:
        "U" for unpowered, "P" for powered, "E" for error
        """
        return self.immediate('x')
    
    def get_y_motor_status(self):
        """
        Get y motor status
        
        Returns:
        "U" for unpowered, "P" for powered, "E" for error
        """
        return self.immediate('y')
    
    def get_z_motor_status(self):
        """
        Get x motor status
        
        Returns:
        "U" for unpowered, "P" for powered, "E" for error
        dict where:
            # - Probe # motor status (where # = 1-4)
        """
        status = self.immediate('z')
        return {1: status[0], 2: status[1], 3: status[2], 4: status[3]}
    
    def get_probe_x_position(self):
        """
        Get probe x position in tenths of millimeters
        
        Returns:
        dict where:
            # - Probe # x position (where # = 1-4)
        """
        position = self.immediate('X')
        position = position.split(',')
        return {1: int(position[0]), 2: int(position[1]),
                3: int(position[2]), 4: int(position[3])}
    
    def get_y_position(self):
        """
        Get y position in tenths of millimeters
        
        Returns:
        integer
        """
        return int(self.immediate('Y'))
    
    def get_probe_z_position(self):
        """
        Get probe z position in tenths of millimeters
        
        Returns:
        dict where:
            # - Probe # z position (where # = 1-4)
        """
        position = self.immediate('Z')
        position = position.split(',')
        return {1: int(position[0]), 2: int(position[1]),
                3: int(position[2]), 4: int(position[3])}
        
    def beep(self, frequency = 2400, duration = 1):
        """
        Activate liquid handler beep
        
        Arguments:
        frequency -- frequency of sound in Hz
        duration -- duration of sound in tenths of seconds
        """
        return self.buffered('SB%i,%i' % (frequency, duration))
    
    def clear_error(self):
        """
        Clear last error
        """
        return self.buffered('Se')
    
    def set_motor_status(self, x, y, z):
        """
        Set motor status (1 for enable motor, 0 for disable)
        Note: enabling the x and y motor after disabling them requires
              an instrument reset
        
        Arguments:
        x -- new x motor status
        y -- new y motor status
        z -- new z motor status
        """
        return self.buffered('SE%i%i%i' % (int(x), int(y), int(z)))
    
    def relax_probe(self, probe):
        """
        Relax probe so that it can be moved manually
        
        Arguments:
        probe -- Probe number to relax (1-4)
        """
        return self.buffered('SF%s' % (self.probe_map[probe]))
    
    def home(self):
        """
        Home the instrument axes
        """
        return self.buffered('SH')
    
    def set_liquid_level_sensitivity(self, probe, sensitivity):
        """
        Set liquid level sensitivity
        
        Arguments:
        probe -- probe number to set sensitivity for
        sensitivity -- desired sensitivity (0-255 where 0 is most sensitive)
        """
        return self.buffered('SK%s%i' % (self.probe_map[probe], sensitivity))
    
    def start_probe_move(self, liquid_level = False):
        """
        Start probe movements without liquid level sensing
        Note: Positions must first be set with set_probe_z_height()
        
        Arguments:
        liquid_level -- If true, use liquid level sensing
        """
        if liquid_level:
            return self.buffered('Sm')
        else:
            return self.buffered('SM')
    
    def set_probe_speed(self):
        pass
    
    def set_probe_z_height(self, a = '', b = '', c = '', d = ''):
        """
        Set probe z position in tenths of millimeters
        Note: If probe position is left blank, it will be ignored
        
        Arguments:
        a -- probe 1 z position
        b -- probe 2 z position
        c -- probe 3 z position
        d -- probe 4 z position
        """
        return self.buffered('ST%s,%s,%s,%s' % (str(a), str(b), str(c), 
                                                str(d)))
    
    def set_lcd_text(self, led_string):
        """
        Set LCD text
        
        Arguments:
        led_string -- text to set the LCD to
        """
        return self.buffered('SW%s' % (led_string))
    
    def set_probe_width(self, width):
        """
        Set probe spacing in tenths of millimeters
        
        Arguments:
        width -- width to set to
        """
        return self.buffered('Sw%i' % (width))
    
    def set_probe_position(self, probe, x, y):
        """
        Move probe to (x, y) position in tenths of millimeters
        
        Arguments:
        probe -- probe number
        x -- desired x position
        y -- desired y position
        """
        return self.buffered('SX%s%i/%i' % (self.probe_map[probe], x, y))
        
    def set_y_position(self, y):
        """
        Move to y position in tenths of millimeters
        
        Arguments:
        y -- y coordinate to move to
        """
        self.buffered('SY%i' % (y))
        
    def set_probe_z(self, probe, z, liquid_level = False):
        """
        Set probe z height in tenths of millimeters
        
        Arguments:
        probe -- probe number
        z -- z position
        liquid_level -- If true, use liquid level sensing
        """
        if liquid_level:
            self.buffered('Sz%s%i' % (self.probe_map[probe], z))
        else:
            self.buffered('SZ%s%i' % (self.probe_map[probe], z))

    def move_to(self, x, y, probe = 1, timeout = 5):
        """
        Move liquid handling arm to (x, y) position in tenths of millimeters
        
        Arguments:
        x -- x position
        y -- y position
        probe -- probe number to use as x coordinate reference
        timeout -- seconds to wait before throwing an error
        """
        
        # Get current position
        position = self.get_encoder_position()
        probe_x = self.get_probe_x_position()
        
        # Move probe
        self.set_probe_position(probe, x, y)
        sleep_counter = 0
        
        # While the positions do not match the target position
        while probe_x[probe] != x and position['Y'] != y:
            # If the timeout has expired
            if sleep_counter > timeout:
                self.sleep(2)
                new_x_position = self.get_probe_x_position()
                new_position = self.get_encoder_position()
                if new_x_position == probe_x and \
                   new_position['Y'] == position['Y']:
                    raise gexceptions.MoveInnacuracyDetected(
                      'Movement to (%i, %i) took %2.2f and stopped at (%i, %i)'
                      % (x, y, sleep_counter, probe_x[probe], position['Y']))
            self.sleep(.05)
            sleep_counter += .05
            position = self.get_encoder_position()
            probe_x = self.get_probe_x_position()
    
    def move_probe(self, z, probes = [1], liquid_sensing = False, timeout = 5):
        # Calculate real Z position
        compensated_z = z + (self.base_z + self.base_tip_height + \
                        self.current_tip_height) * 10
        
        for probe in probes:
            if liquid_sensing:
                self.set_probe_z_with_liquid_sensing(probe, compensated_z)
            else:
                self.set_probe_z(probe, compensated_z)
        if liquid_sensing:
            self.start_probe_move_liquid_sensing()
        else:
            self.start_probe_move()
        
        sleep_counter = 0
        moving = True
        while moving:
            self.sleep(.20)
            sleep_counter += .2
            z_positions = self.get_probe_z_position()
            
            # Cycle through each probe and see if it's still moving
            probes_moving = False
            for probe in probes:
                if z_positions[probe] != compensated_z:
                    probes_moving = True
                    break
            if not probes_moving:
                moving = False
            
            # If the probes are taking too long to move
            if sleep_counter > timeout and moving:
                self.sleep(2)
                sleep_counter += 2
                new_z_positions = self.get_probe_z_position()
                failed = False
                failed_list = []
                failed_string = 'The following probes failed to position: '
                
                # Check if probes are still moving
                for probe in probes:
                    if z_positions[probe] == new_z_positions[probe] and \
                       new_z_positions[probe] != compensated_z:
                        failed_list.append(probe)
                        failed = True
                if failed:
                    for probe in failed_list:
                        failed_string += '%i ' % (probe)
                    raise gexceptions.MoveInnacuracyDetected(failed_string)

    def add_402_syringe_pump(self, device_id, left_probe_num, right_probe_num):
        """
        Register a 402 syringe pump
        
        Arguments:
        device_id -- device id of the syringe pump
        left_probe_num -- probe number to assign to left side pump
        right_probe_num -- probe number to assign to right side pump
        """
        self.queue.register_device(device_id)
        response = self.immediate('%', device_id)
        if response[0:3] != '402':
            raise gexceptions.DeviceException(device_id, 
                              'Specified device is not a 402 syringe pump')
        pr = left_probe_num
        self.syringe[pr]['device_id'] = device_id
        self.syringe[pr]['side'] = 'left'
        self.syringe[pr]['partner_probe'] = right_probe_num
        
        pr = right_probe_num
        self.syringe[pr]['device_id'] = device_id
        self.syringe[pr]['side'] = 'right'
        self.syringe[pr]['partner_probe'] = left_probe_num
        
        self.syringe_devices.append(device_id)
    
    
    def reset_syringe_pump(self, probe_num):
        """
        Reset syringe pump
        
        Arguments:
        probe_num -- assigned probe number of the syringe pump to reset
        
        Returns:
        '$' when pump is reset
        """
        device_id = self.syringe[probe_num]['device_id']
        return self.immediate('$', device_id)
    
    def get_syringe_pump_status(self, probe_num):
        """
        Get individual syringe pump status
        
        Arguments:
        probe_num -- assigned probe number of the syringe pump
        
        Returns:
        str -- syringe status
        int -- syringe size in uL
        """
        device_id = self.syringe[probe_num]['device_id']
        response = self.immediate('M', device_id)
        res = re.match(r"(?P<left>[A-Z])(?P<lvol>[0-9\.]+)" + 
                       r"(?P<right>[A-Z])(?P<rvol>[\.0-9]+)", response)
        
        if self.syringe[probe_num]['side'] is 'right':
            pl = self.syringe[probe_num]['partner_probe']
            pr = probe_num
        else:
            pl = probe_num
            pr = self.syringe[probe_num]['partner_probe']
        self.syringe[pl]['status'] = res.group("left")
        self.syringe[pl]['current_volume'] = res.group("lvol")
        self.syringe[pr]['status'] = res.group("right")
        self.syringe[pr]['current_volume'] = res.group("rvol")
        
        if self.syringe[probe_num]['side'] is 'right':
            return res.group("right"), float(res.group("rvol"))
        return res.group("left"), float(res.group("lvol"))
    
    def get_global_status(self, probe_num):
        """
        Get syringe pump global status
        
        Arguments:
        probe_num -- assigned probe number of the syringe pump
        
        Returns:
        int -- command buffer status
        int -- error flag status
        """
        device_id = self.syringe[probe_num]['device_id']
        resp = self.immediate('S', device_id)
        return int(resp[0]), int(resp[1])
    
    def get_valve_status(self, probe_num):
        """
        Get valve status
        
        Arguments:
        probe_num -- assigned probe number of the syringe pump
        
        Returns:
        str - valve status
        """
        device_id = self.syringe[probe_num]['device_id']
        resp = self.immediate('V', device_id)
        
        if self.syringe[probe_num]['side'] is 'right':
            pl = self.syringe[probe_num]['partner_probe']
            pr = probe_num
        else:
            pl = probe_num
            pr = self.syringe[probe_num]['partner_probe']
        self.syringe[pl]['valve_status'] = resp[0]
        self.syringe[pr]['valve_status'] = resp[1]
        
        offset = 0
        if self.syringe[probe_num]['side'] is 'right':
            offset = 1
        return resp[offset]
    
    def set_aspirate_volume(self, probe_num, volume, block = True):
        """
        Set syringe pump aspiration volume without starting the pump
        
        Arguments:
        probe_num -- assigned probe number of the syringe pump
        volume -- volume to aspirate
        """
        self.wait_for_buffered()
        device_id = self.syringe[probe_num]['device_id']
        probe_letter = "L"
        if self.syringe[probe_num]['side'] is 'right':
            probe_letter = "R"
        suffix = ''
        if not volume % 1 > 0:
            suffix = '.0'
        if (volume % 1) == (self.get_syringe_pump_status(probe_num)[1] % 1):
            return
        self.buffered(('A%s' % (probe_letter)) + str(volume) + suffix, 
                      device_id)
        self.syringe[probe_num]['next_operation'] = -volume
        while self.get_syringe_pump_status(probe_num)[0] != 'H':
            self.sleep(.05, '[aspirate block]')
    
    def set_dispense_volume(self, probe_num, volume):
        """
        Set syringe pump dispense volume without starting the pump
        
        Arguments:
        probe_num -- assigned probe number of the syringe pump
        volume -- volume to dispense
        """
        self.wait_for_buffered()
        device_id = self.syringe[probe_num]['device_id']
        probe_letter = "L"
        if self.syringe[probe_num]['side'] is 'right':
            probe_letter = "R"
        suffix = ''
        if not volume % 1 > 0:
            suffix = '.0' 
        if (volume % 1) == (self.get_syringe_pump_status(probe_num)[1] % 1):
            return
        self.buffered(('D%s' % (probe_letter)) + str(volume) + suffix, 
                      device_id)
        self.syringe[probe_num]['next_operation'] = volume
        while self.get_syringe_pump_status(probe_num)[0] != 'H':
            self.sleep(.05, '[aspirate block]')
    
    def start_syringe_pump(self, probe_num, both = False, block = True):
        """
        Start syringe pump aspirate/dispense
        
        Arguments:
        probe_num -- assigned probe number of the syringe pump
        both -- True to start both syringes, False to move only one
        """
        self.wait_for_buffered()
        device_id = self.syringe[probe_num]['device_id']
        if both:
            syringe = 'B'
        else:
            syringe = 'L'
            if self.syringe[probe_num]['side'] is 'right':
                syringe = 'R'
        self.buffered('B' + syringe, device_id)
        while block:
            status = self.immediate('M', device_id)
            res = re.match(r"(?P<left>[A-Z])(?P<lvol>[0-9\.]+)" +
                           r"(?P<right>[A-Z])(?P<rvol>[\.0-9]+)", status)
            if syringe == 'B' and res.group('left') != 'R' and \
                                        res.group('right') != 'R':
                break
            elif syringe == 'L' and res.group('left') != 'R':
                break
            elif syringe == 'R' and res.group('right') != 'R':
                break
            self.sleep(self.time_delay, parent='start pump delay')
        self.sleep(self.time_delay, parent='pump fin delay')
        return
        
    def set_motor_force(self, probe_num, amplitude):
        """
        Set motor force
        
        Arguments:
        probe_num -- assigned probe number of the syringe pump
        amplitude -- integer value to set amplitude to
        """
        self.wait_for_buffered()
        device_id = self.syringe[probe_num]['device_id']
        syringe = 'L'
        if self.syringe[probe_num]['side'] is 'right':
            syringe = 'R'
        self.buffered('F%s%i' % (syringe, amplitude), device_id)
        self.syringe[probe_num]['motor_force'] = amplitude
        
    def halt_syringe_pump(self, probe_num, both = False):
        """
        Halt syringe pump movement
        
        Arguments:
        probe_num -- assigned probe number of the syringe pump
        both -- True to halt both syringes, False to halt only one
        """
        self.wait_for_buffered()
        device_id = self.syringe[probe_num]['device_id']
        if both:
            syringe = 'B'
        else:
            syringe = 'L'
            if self.syringe[probe_num]['side'] is 'right':
                syringe = 'R'
        self.buffered('N' + syringe, device_id)
        
    def initialize_syringe(self, probe_num, both = False, block = True):
        """
        Initialize syringe pump
        
        Arguments:
        probe_num -- assigned probe number of the syringe pump
        both -- True to initialize both syringes, False to initialize only one
        """
        self.wait_for_buffered()
        device_id = self.syringe[probe_num]['device_id']
        if both:
            syringe = 'B'
        else:
            syringe = 'L'
            if self.syringe[probe_num]['side'] is 'right':
                syringe = 'R'
        self.buffered('O' + syringe, device_id)
        while block:
            self.sleep(self.time_delay)
            status= self.get_syringe_pump_status(probe_num)
            if status[0] is not 'I':
                if both:
                    status = self.get_syringe_pump_status(
                                  self.syringe[probe_num]['partner_probe'])
                    if status[0] is not 'I':
                        return
        
    def set_syringe_size(self, probe_num, volume, both = False):
        """
        Set syringe size
        
        Arguments:
        probe_num -- assigned probe number of the syringe pump
        volume -- syringe volume in uL
        both -- True to set both syringes, False to set only one
        """
        self.wait_for_buffered()
        device_id = self.syringe[probe_num]['device_id']
        if self.syringe[probe_num]['side'] is 'right':
            pl = self.syringe[probe_num]['partner_probe']
            pr = probe_num
        else:
            pl = probe_num
            pr = self.syringe[probe_num]['partner_probe']
        
        if both:
            self.syringe[pl]['syringe_size'] = volume
            self.syringe[pr]['syringe_size'] = volume
            syringe = 'B'
            self.syringe[probe_num]['size'] = volume
            self.syringe[self.syringe[probe_num]['opposite']]['size'] = volume
        else:
            syringe = 'L'
            if self.syringe[probe_num]['side'] is 'right':
                syringe = 'R'
                self.syringe[pr]['syringe_size'] = volume
            else:
                self.syringe[pl]['syringe_size'] = volume
        self.buffered('P%s%i' % (syringe, volume), device_id)
    
    def set_syringe_flow_rate(self, probe_num, flow_rate):
        """
        Set syringe pump flow rate
        
        Arguments:
        probe_num -- assigned probe number of the syringe pump
        flow_rate -- flow rate in mL/min
        """
        self.wait_for_buffered()
        device_id = self.syringe[probe_num]['device_id']
        syringe = 'L'
        if self.syringe[probe_num]['side'] is 'right':
            syringe = 'R'
        self.syringe[probe_num]['flow_rate'] = flow_rate
        self.buffered('S' + syringe + str(flow_rate), device_id)
    
    def synchronize_syringe_pump(self, probe_num):
        """
        Synchronize syringe pump movement
        
        Arguments:
        probe_num -- assigned probe number of the syringe pump
        """
        self.wait_for_buffered()
        device_id = self.syringe[probe_num]['device_id']
        syringe = 'L'
        if self.syringe[probe_num]['side'] is 'right':
            syringe = 'R'
        self.buffered('T' + syringe, device_id)
    
    def set_valve_status(self, probe_num, status, block = True):
        """
        Set valve position
        
        Arguments:
        probe_num -- assigned probe number of the syringe pump
        status -- valve status
                  True or 'N' - needle
                  False or 'R' - reservoir
        """
        self.wait_for_buffered()
        device_id = self.syringe[probe_num]['device_id']
        syringe = 'L'
        if self.syringe[probe_num]['side'] is 'right':
            syringe = 'R'
        valve_status = status
        if status != 'R' and status != 'N':
            valve_status = 'R'
            if status:
                valve_status = 'N'
        self.buffered('V' + syringe + valve_status, device_id)
        while block:
            self.sleep(self.time_delay)
            status = self.get_valve_status(probe_num)
            if status == valve_status:
                return
            
    def set_valves(self, status):
        for i in range(len(status)):
            if status[i] == 'R' or status[i] == 'N':
                self.set_valve_status(i+1, status[i])
        
    def pump(self, volumes):
        """
        Pump probes at the given volumes
        
        Arguments:
        volumes -- list of volumes to pipette from probe 1 to 4
                   Positive values dispense, negative values aspirate
        """
        starting_vol = []
        for i in range(len(volumes)):
            status, vol = self.get_syringe_pump_status(i+1)
            starting_vol.append(vol)
            if volumes[i] > 0:
                if vol < volumes[i]:
                    raise gexceptions.VolumeError('Syringe for probe # ' +
                          str(i+1) + 'does not have enough volume to' +
                           ' dispense ' + str(volumes[i]) + ' uL')
                self.set_dispense_volume(i+1, volumes[i])
                starting_vol[i] -= volumes[i]
            else:
                if vol > -volumes[i]:
                    raise gexceptions.VolumeError('Syringe for probe # ' +
                          str(i+1) + 'does not have enough volume to' +
                          ' aspirate ' + str(volumes[i]) + ' uL')
                self.set_aspirate_volume(i+1, abs(volumes[i]))
                starting_vol[i] -= volumes[i]
        
        for device in self.syringe_devices:
            self.buffered('BB', device)
        
        for i in range(len(volumes)):
            running = False
            while True:
                self.sleep(self.time_delay)
                status, vol = self.get_syringe_pump_status(i+1)
                if status != 'R' and running:
                    if int(vol) != int(starting_vol[i]):
                        raise gexceptions.VolumeError('Probe #' + str(i+1) +
                              ' did not pump desired volume')
                else:
                    if status == 'R':
                        running = True
                if int(vol) == int(starting_vol[i]):
                    break

    def wait_for_buffered(self):
        self.queue.event_buffered.wait()