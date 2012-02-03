import traceback

class ProbeList():
    def __init__(self, quadz, syringes, mask):
        self.quadz = quadz
        self.syringes = syringes
        self.mask = mask
        self.probe_map = {1: 'a', 2: 'b', 3: 'c', 4: 'd'}
        self.e = "{0}() with mask {1} takes exactly " +\
                 str(len(self.mask)) + " arguments ({2} given)"
        
        self.both = {}
        for probe in mask:
            if probe in self.both:
                continue
            if self.syringes[probe]['partner_probe'] in self.mask:
                self.both[self.syringes[probe]['partner_probe']] = probe
        
    def relax(self):
        for probe in self.mask:
            self.quadz.relax_probe(probe)
    
    def form_args(self, argv):
        ct = len(argv)
        if ct == 0:
            return False
        elif ct == 1:
            arg_ret = []
            for i in self.mask:
                arg_ret.append(argv[0])
                i = i
            return arg_ret
        else:
            if len(self.mask) != ct:
                if len(self.mask) == 1:
                    mask = "[%i]" % (self.mask[0])
                else:
                    mask = self.mask
                func = traceback.extract_stack(limit=2)[-2][2]
                raise TypeError(self.e.format(func, mask, ct))
            else:
                arg_ret = []
                for i in argv:
                    arg_ret.append(i)
                return arg_ret
    
    def skeleton(self, *argv):
        args = self.form_args(argv)
        if not args:
            return
        for key, probe in enumerate(self.mask):
            self.quadz.f(probe, args[key])
    
    def sensitivity(self, *argv):
        args = self.form_args(argv)
        if not args:
            return self.quadz.get_liquid_sensitivity()
        for key, probe in enumerate(self.mask):
            self.quadz.set_liquid_level_sensitivity(probe, args[key])
    
    def height(self, *argv):
        args = self.form_args(argv)
        if not args:
            return self.quadz.get_probe_z_position()
        height = {'a': '', 'b': '', 'c': '', 'd': ''}
        for key, probe in enumerate(self.mask):
            height[self.probe_map[probe]] = args[key]
        self.quadz.set_probe_z_height(**height)
        self.quadz.start_probe_move(liquid_level=False)
        
    def speed(self, *args):
        args = self.form_args(args)
        if not args:
            return
        speed = {'a': '', 'b': '', 'c': '', 'd': ''}
        for key, probe in enumerate(self.mask):
            speed[self.probe_map[probe]] = args[key]
        self.quadz.set_probe_speed(**speed)
        
    def width(self, width = -1):
        if width == -1:
            return self.quadz.get_probe_width()
        if 180 < int(width) < 90:
            raise Exception("Probe width must be between 90 and 180")
        self.quadz.set_probe_width(int(width))
    
    def move(self, x, y):
        self.quadz.move_to(x, y, probe=self.mask[0])