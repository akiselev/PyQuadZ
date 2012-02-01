import time
from quadz import QuadZDevice

# QuadZDevice([serial port number] - 1)
# e.g. COM3 = QuadZDevice(2)
q = QuadZDevice(2)

# QuadZDevice.initialize_device([device id])
# Device ID is usually 22 for the liquid handler
q.initialize_device(22)

# QuadZDevice.move_to(x, y)
# This moves probe #1 to (x,y)
# The probes are numbered left to right starting with 1
q.move_to(100,2000)

# QuadZDevice.set_probe_z_height(probe1, probe2, probe3, probe4)
# At z=2000, the probes are fully up
q.set_probe_z_height(2000,2000,2000,2000)

# QuadZDevice.start_probe_move()
# The previous command sets the z height, this commands starts the motion
q.start_probe_move()

# QuadZDevice.add_402_syringe_pump([device id], [left probe], [right probe])
# Connects to 402 syringe pump with device id and sets up the probe
# [left probe] is the number of the probe that is connected to the left syringe
# [right probe] is the probe connected to the right syringe
# Check the manual for how to set syringe pump device ID, 0 and 1 are defaults
q.add_402_syringe_pump(0, 1, 2)
q.add_402_syringe_pump(1, 3, 4)

# QuadZDevice.set_syringe_size([probe], [size])
# [probe] is the probe number (1-4, numbered left to right)
# [size] is the size in microliters
q.set_syringe_size(1, 250)
q.set_syringe_size(2, 250)
q.set_syringe_size(3, 250)
q.set_syringe_size(4, 250)

# NOTE: some commands like set_syringe_size have an optional argument [both]
# if [both] is True, the function applies to the syringe pump for the specified 
# probe, as well as it's partner syringe (since there are two syringes in each 
# 402 pump). Refer to the definition of the function to see if it has [both]
# For example, instead of the above code you can do:
q.set_syringe_size(1, 250, both=True)
q.set_syringe_size(3, 250, both=True)

# QuadZDevice.set_syringe_flow_rate([probe], [flow rate])
# [flow rate] in ml/min
# (set_syringe_flow_rate does not have a [both] argument)
q.set_syringe_flow_rate(1, 10)
q.set_syringe_flow_rate(2, 10)
q.set_syringe_flow_rate(3, 10)
q.set_syringe_flow_rate(4, 10)

# QuadZDevice.initialize_syringe()
# Initializes syringe pump
# Some commands also have an optional [block] argument. If true, the function
# does not return until the action has been completed. In the case of 
# initializing a syringe pump, it checks until the status is no longer 'I'
q.initialize_syringe(1, both=True)
q.initialize_syringe(3, both=True, block=True)

# In the above code, we don't wait for syringes 1 and 2 to initialize, instead
# waiting for 3 and 4, which means they will intialize simultaneously.
# However, here we still need to check that the syringe pump has loaded
while True:
    status1, volume1 = q.get_syringe_pump_status(1)
    status2, volume2 = q.get_syringe_pump_status(2)
    if status1 != 'I' and status2 != 'I':
        break
    # It's best to wait a little before each status update
    time.sleep(.1)

# The below for loop is an example of aspirate from the system fluid
# and dispensing to the probe
for i in range(5):
    # QuadZDevice.set_valve_status([probe], [status])
    # [status] is the position to set the valve to
    # 'R' for system fluid reservoir, 'N' for probe
    q.set_valve_status(1, 'R')
    
    # QuadZDevice.set_aspirate_volume([probe], [volume])
    # Sets the volume that you want to aspirate but does not start syringe
    # [volume] is in microliters
    q.set_aspirate_volume(1, 150)
    
    # QuadZDevice.start_syringe_pump([probe])
    # Starts the syringe pump with previous set volume
    # Does nothing if there is no previous volume to pipette
    q.start_syringe_pump(1)
    
    q.set_valve(1, 'N')
    # QuadZDevice.set_dispense_volume([probe], [volume])
    # same as set_aspirate_volume
    q.set_dispense_volume(1, 150)
    q.start_syringe_pump(1)

# Since the above code can be annoying to type for 4 syringe pumps there are
# simpler alternatives to the above code:
for i in range(5):
    # QuadZDevice.set_valves([[probe1], [probe2], [probe3], [probe4]])
    # sets valve status for all valves
    q.set_valves(['N', 'N', 'N', 'N'])
    
    # QuadZDevice.pump([[probe1], [probe2], [probe3], [probe4]])
    # Sets pipetting volumes and starts syringe pumps
    # negative volumes aspirate, positive dispense
    # Note: Yes this is stupid and will probably change in future versions to
    # positive = aspirate and negative = dispense
    q.pump([-150, -150, -150, -150])
    
    q.set_valves(['R', 'R', 'R', 'R'])
    q.pump([150, 150, 150, 150])

# Read the code for further documentation