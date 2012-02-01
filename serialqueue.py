import threading, Queue
import gexceptions
import time
import logging
import traceback

class SerialQueue(threading.Thread):
    """
    SerialQueue is a thread class that runs in the background and manages
    information exchange with the Gilson GSIOC interface.
    
    The class consists of buffered command queue and an immediate command
    function. To send an immediate command use add_immediate_instruction()
    which blocks until receiving a response which it then returns. To send a 
    buffered command, use add_buffered_instruction which will add the command
    to the buffered queue and execute when the command buffer on the instrument
    is clear. For both the liquid handler and the syringe pumps, the command 
    buffer uses the 'S' command to check whether the buffer is ready for 
    another instruction.
    
    DO NOT USE send_immediate_instruction() and send_buffered_instruction! They
    are for use in the thread for handling commands. Instead use the above
    add_* commands.
    """
    max_string_size = 32
    max_null_count = 5
    ACK = chr(int('6', 16))
    LF = chr(int('0A', 16))
    CR = chr(int('0D', 16))
    
    def __init__(self, device):
        # Set up logging
        log_format = '%(asctime)s %(levelname)s: %(message)s'
        log_formatter = logging.Formatter(log_format)
        log_handler = logging.StreamHandler()
        log_handler.setFormatter(log_formatter)
        self.log = logging.getLogger('pygilson')
        self.log.addHandler(log_handler)
        self.log.setLevel(logging.DEBUG)
        
        # Log flags tell the script which categories to log.
        # sleep: used when time.sleep() is called
        # immediate_queue: used in the immediate instruction calls
        # buffered_queue: used in the buffered instruction calsl
        # immediate: logs sent immediate commands
        # buffered: logs send buffered commands
        # worker: used in the main thread function run()
        # devices: used in functions that connect/disconnect with devices
        self.log_flags = {'sleep': False,
                          'immediate_queue': False,
                          'buffered_queue': False,
                          'immediate': False,
                          'buffered': False,
                          'worker': False,
                          'devices': False}
        
        # This is set when there is an instruction to execute
        self.event_instruction = threading.Event()
        
        # Prevents sending of data while the thread is sending data
        self.event_lock = threading.Event()
        self.event_lock.set()
        
        # Prevents thread from attempting to connect to another device while
        # sending data
        self.event_buffer_lock = threading.Event()
        self.event_buffer_lock.set()
        
        # Prevents communication while sending immediate commands
        self.event_buffered = threading.Event()
        self.event_buffered.set()
        
        # Since add_immediate_instruction is usually called in another thread,
        # this event blocks until a response is waiting in the queue
        self.event_immediate_response = threading.Event()
        
        # Buffered instruction queue
        self.queue_instructions = Queue.Queue(0)
        
        # Next immediate command to execute and its response
        self.immediate_instruction = False
        self.immediate_response = False
        
        # Stores last exception in queue thread
        self.last_exception = False
        
        # Serial port
        self.device = device
        
        # Registered device ids
        self.registered_devices = []        
        self.connected_device = None
        
        # Queue timing variables
        # sleep_subtotal allows tracking the timing of arbitrary code
        self.time_delay = .05
        self.sleep_subtotal = 0
        self.sleep_total = 0
        
        threading.Thread.__init__(self)
        
    def run(self):
        # Wait until there is an instruction to send
        # (This is essentially an infinite loop)
        while 1:
            self.event_instruction.wait()
            self.event_buffer_lock.wait()
            self.event_lock.clear()
            
            if self.immediate_instruction != False:
                device_id = self.immediate_instruction[0]
                if self.log_flags['worker']:
                    self.log.debug(' --- Immediate Queue: %25s -> %-25s' %
                                   (self.immediate_instruction[3], 
                                    self.immediate_instruction[1]))
                try:
                    self.establish_connection(device_id)
                except gexceptions.DeviceNotResponding, e:
                    self.immediate_response = False
                    self.event_immediate_response.set()
                    self.immediate_instruction = False
                    self.last_exception = e
                else:
                    try:
                        r = self.send_immediate_instruction(
                                        self.immediate_instruction[1],
                                        parent=self.immediate_instruction[3])
                    except Exception, e:
                        # TODO: Add code to handle common exceptions for serial
                        self.immediate_response = False
                        self.immediate_instruction = False
                        self.last_exception = e
                    else:
                        self.immediate_response = r
                        self.immediate_instruction = False
                    self.event_immediate_response.set()
                # Due to limitations of the Gilson computer, there needs to be
                # a delay before another command is sent
                self.sleep(self.time_delay, parent='[queue_loop_delay]')
            # Buffered commands
            if not self.queue_instructions.empty():
                instruction = self.queue_instructions.get()
                device_id = instruction[0]
                if self.log_flags['worker']:
                    self.log.debug(' ---  Buffered Queue: %25s -> %-25s' %
                                   (instruction[3], instruction[1]))
                try:
                    self.establish_connection(device_id)
                    # This section of code uses proper command to see if 
                    # device queue is empty
                    if instruction[2] == 'handler':
                        while self.send_immediate_instruction('S',
                            parent='[check_quadz_buffer]') != '|':
                            self.sleep(self.time_delay, 'buffer_delay')
                    elif instruction[2] == 'pump':
                        while self.send_immediate_instruction('S',
                            parent='[check_syringe_buffer]')[0] != '0':
                            self.sleep(self.time_delay, 'buffer_delay')
                except gexceptions.DeviceNotResponding, e:
                    # TODO: Add code to handle common exceptions for serial
                    self.queue_instructions.task_done()
                    self.last_exception = e
                else:
                    self.send_buffered_instruction(instruction[1],
                                                   parent=instruction[3])
                    self.queue_instructions.task_done()
            elif self.immediate_instruction == False:
                self.event_instruction.clear()
            self.event_lock.set()
            self.sleep(self.time_delay, parent='[queue_loop_delay]')

    def sleep(self, seconds, parent = None, top_parent = None):
        """
        Wrapper for time.sleep which logs delays
        
        Arguments:
        seconds -- number of seconds to wait
        parent -- name of function that called sleep as a string
        top_parent -- name of function that called above function as a string
        """
        # If seconds = 0, reset the subtotal counter
        if seconds == 0:
            self.sleep_subtotal = 0
            return
        
        self.sleep_total += seconds
        self.sleep_subtotal += seconds
        if self.log_flags['sleep']:
            if parent is not None:
                if top_parent is None:
                    top_parent = traceback.extract_stack(limit=2)[-2][2]
                self.log.debug('%25s -> %-29s Sleep:    %ss (total: %ss)' % 
                               (top_parent, parent, str(seconds),
                                str(self.sleep_subtotal)))
        time.sleep(seconds)
    
    ################################
    ####                        ####
    ####      Serial Methods    ####
    ####                        ####
    ################################
    
    def connect(self, device_id):
        """
        Connect to a device over serial
        
        Arguments:
        device_id -- device id
        """
        if device_id not in self.registered_devices:
            raise gexceptions.DeviceNotRegistered(device_id)
        elif self.connected_device == device_id:
            return True
        device_byte = chr(device_id + 128)
        trace = traceback.extract_stack(limit=3)
        parent = trace[-2][2]
        if parent == 'establish_connection':
            parent = trace[-3][2]
            
        if self.log_flags["devices"]:
            self.log.debug('%25s -> %-25s   Connect:  > %s' % (parent,
                            'connect[%i]' % (device_id), str(device_byte)))
        self.send(device_byte)
        if self.get_byte() != device_byte:
            raise gexceptions.DeviceNotConnected(device_id)
        self.log.debug('%66s - %s' % (' ', str(device_byte)))
        
        self.connected_device = device_id
        if self.log_flags["devices"]:
            self.sleep(.1, parent='connect[%i]' % (device_id),
                       top_parent=parent)
        return True
            
    def disconnect(self):
        """
        Disconnect from current device
        """
        trace = traceback.extract_stack(limit=3)
        parent = trace[-2][2]
        if parent == 'establish_connection':
            parent = trace[-3][2]
        if self.log_flags["devices"]:
            self.log.debug('%25s -> %-25s  DConnect:  > %s' % (parent,
                                                               'disconnect',
                                                               str(chr(255))))
        self.send(chr(255))
        device_id = -1 if self.connected_device == None\
                       else self.connected_device
        self.sleep(.1, parent='disconnect[%i]' % (device_id),
                   top_parent=parent)
        self.connected_device = None
    
    def close(self):
        """
        Close serial port
        """
        self.device.close()
        
    def send(self,char):
        """
        Send a single character
        """
        return self.device.write(char)

    def get_byte(self):
        """
        Get byte from serial port
        """
        return self.device.read(1)
    
    def register_device(self, dev_id):
        """
        Register a device and try to connect to it
        """
        self.event_buffer_lock.clear()
        self.event_lock.wait()
        self.registered_devices.append(dev_id)
        try:
            self.establish_connection(dev_id)
        except gexceptions.DeviceNotResponding:
            self.event_buffer_lock.set()
            return False
        self.event_buffer_lock.set()
        return True
        
    def establish_connection(self, dev_id, max_retries = 10):
        """
        Disconnect from current device and connect to new one
        
        Arguments:
        device_id -- device id to connect to
        max_retries -- number of times to retry connection
        """
        if self.connected_device == dev_id:
            return True
        for i in range(max_retries):
            self.disconnect()
            try:
                if self.connect(dev_id):
                    return True
            except gexceptions.DeviceNotConnected:
                pass
        raise gexceptions.DeviceNotResponding(dev_id)
    
    ################################
    ####                        ####
    ####    Instruction Queue   ####
    ####         Methods        ####
    ####                        ####
    ################################
    
    def add_immediate_instruction(self, device_id, instruction):
        """
        Add immediate instruction to the queue
        
        Arguments:
        device_id -- device to send to
        instruction -- instruction to send
        
        Returns:
        result of immediate command (blocks until there is a response)
        """
        self.event_buffered.clear()
        trace = traceback.extract_stack(limit=4)
        parent_func = trace[-2][2]
        if parent_func == 'immediate':
            parent_func = trace[-3][2]
        
        if self.log_flags['immediate_queue']:
            self.log.debug('%25s -> %-25s     Queue: +I %s' % (parent_func,
                           'add_immediate_cmd', str(instruction)))
        self.immediate_instruction = (device_id, instruction, 0, parent_func)
        self.event_instruction.set()
        self.event_immediate_response.wait()
        response = self.immediate_response
        self.immediate_response = False
        self.event_immediate_response.clear()
        self.event_buffered.set()
        return response
    
    def add_buffered_instruction(self, device_id, instruction, wait='handler'):
        """
        Add buffered instruction to the queue
        
        Arguments:
        device_id -- device to send to
        instruction -- instruction to send
        wait -- string identifying what character represents an empty buffer
                "handler" for Gilson liquid handler (default)
                "pump" for 402 syringe pump
        """
        self.event_buffered.clear()
        trace = traceback.extract_stack(limit=4)
        parent_func = trace[-2][2]
        if parent_func == 'buffered':
            parent_func = trace[-3][2]
            
        if self.log_flags['buffered_queue']:
            self.log.debug('%25s -> %-25s     Queue: +B %s' % (parent_func,
                           'add_buffered_cmd', str(instruction)))
        self.queue_instructions.put((device_id, instruction, wait, parent_func))
        self.event_instruction.set()
    
    def send_buffered_instruction(self, instruction, parent = ''):
        """
        Send buffered instrument
        
        Keyword Arguments:
        instruction -- Instruction to post to send to instrument
        """
        # Buffered commands sent to the instrument are returned byte by byte
        # LF and CR are added to the command when returned
        command = self.LF + instruction + self.CR
        parent_func = traceback.extract_stack(limit=2)[-2][2]
        if self.log_flags["buffered"]:
            self.log.debug('%25s -> %-25s  Buffered:  > %s' % (parent_func,
                                           parent, str(instruction)))
        response = ''
        for char in command:
            self.send(char)
            # If the instrument returns anything but the command sent to
            # it, it means that the call failed
            if self.get_byte() != char:
                self.event_buffered.set()
                raise gexceptions.BufferedResponseError()
            response += char
        response = response.strip()
        if self.log_flags["buffered"]:
            self.log.debug('%66s - %s' % (' ', str(response)))
        self.event_buffered.set()
    
    def send_immediate_instruction(self, instruction, parent = ''):
        """
        Send immediate instruction and return response
        
        Keyword Arguments:
        instruction -- Instruction to send immediately
        """
        count = 0
        null_count = 0
        response = ''
        parent_func = traceback.extract_stack(limit=2)[-2][2]
        if self.log_flags["immediate"]:
            self.log.debug('%25s -> %-25s Immediate:  > %s' % (parent_func,
                                            parent, str(instruction)))
        self.send(instruction)
        while(1):
            # the return string should never be bigger than 32 bytes
            if count > self.max_string_size:
                raise gexceptions.ResponseSizeError('Reponse string ' +
                                                    ' was over 32 characters')
            # If the device sends a string of null characters, call failed
            if null_count > self.max_null_count:
                raise gexceptions.ResponseSizeError('Reponse string' + 
                                                'contained was over 5 nulls')
            # acknowledgement byte is required before device sends more data
            if count > 0:
                self.send(self.ACK)
            
            response_char = self.get_byte()
            if response_char != '':
                # This code checks if the high (#7) bit is set
                # This bit signifies the end of the response
                if (ord(response_char) >> 7) == 1:
                    response_char = chr(ord(response_char) - 128)
                    response += response_char
                    if self.log_flags["immediate"]:
                        self.log.debug('%66s - %s' % (' ', str(response)))
                    return response
                else:
                    response += response_char
            else:
                null_count += 1
            count += 1