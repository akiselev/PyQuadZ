class ResponseSizeError(Exception):
    pass

class BufferedResponseError(Exception):
    pass

class DeviceException(Exception):
    def __init__(self, dev_id, message = ''):
        Exception.__init__(self, message)
        
        self.device_id = dev_id

class DeviceNotRegistered(DeviceException):
    pass

class DeviceNotConnected(DeviceException):
    pass

class DeviceNotResponding(DeviceException):
    pass

class DeviceNotFound(Exception):
    pass

class MoveInnacuracyDetected(Exception):
    pass

class VolumeError(Exception):
    pass