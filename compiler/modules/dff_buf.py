# See LICENSE for licensing information.
#
#Copyright (c) 2016-2019 Regents of the University of California and The Board
#of Regents for the Oklahoma Agricultural and Mechanical College
#(acting for and on behalf of Oklahoma State University)
#All rights reserved.
#
import debug
import design
from tech import drc,parameter
from math import log
from vector import vector
from globals import OPTS
from sram_factory import factory

class dff_buf(design.design):
    """
    This is a simple buffered DFF. The output is buffered
    with two inverters, of variable size, to provide q
    and qbar. This is to enable driving large fanout loads.
    """
    unique_id = 1
    
    def __init__(self, inv1_size=2, inv2_size=4, name=""):

        if name=="":
            name = "dff_buf_{0}".format(dff_buf.unique_id)
            dff_buf.unique_id += 1
        design.design.__init__(self, name)
        debug.info(1, "Creating {}".format(self.name))
        self.add_comment("inv1: {0} inv2: {1}".format(inv1_size, inv2_size))
        
        # This is specifically for SCMOS where the DFF vdd/gnd rails are more than min width.
        # This causes a DRC in the pinv which assumes min width rails. This ensures the output
        # contact does not violate spacing to the rail in the NMOS.
        debug.check(inv1_size>=2, "Inverter must be greater than two for rail spacing DRC rules.")
        debug.check(inv2_size>=2, "Inverter must be greater than two for rail spacing DRC rules.")        

        self.inv1_size=inv1_size
        self.inv2_size=inv2_size
        
        self.create_netlist()
        if not OPTS.netlist_only:
            self.create_layout()

    def create_netlist(self):
        self.add_modules()
        self.add_pins()
        self.create_instances()

    def create_layout(self):
        self.width = self.dff.width + self.inv1.width + self.inv2.width
        self.height = self.dff.height
        
        self.place_instances()
        self.route_wires()
        self.add_layout_pins()
        self.DRC_LVS()

    def add_modules(self):
        self.dff = factory.create(module_type="dff")
        self.add_mod(self.dff)

        self.inv1 = factory.create(module_type="pinv",
                                   size=self.inv1_size,
                                   height=self.dff.height)
        self.add_mod(self.inv1)

        self.inv2 = factory.create(module_type="pinv",
                                   size=self.inv2_size,
                                   height=self.dff.height)
        self.add_mod(self.inv2)

        
        
    def add_pins(self):
        self.add_pin("D")
        self.add_pin("Q")
        self.add_pin("Qb")
        self.add_pin("clk")
        self.add_pin("vdd")
        self.add_pin("gnd")

    def create_instances(self):
        self.dff_inst=self.add_inst(name="dff_buf_dff",
                                    mod=self.dff)
        self.connect_inst(["D", "qint", "clk", "vdd", "gnd"])

        self.inv1_inst=self.add_inst(name="dff_buf_inv1",
                                     mod=self.inv1)
        self.connect_inst(["qint", "Qb",  "vdd", "gnd"])
        
        self.inv2_inst=self.add_inst(name="dff_buf_inv2",
                                     mod=self.inv2)
        self.connect_inst(["Qb", "Q",  "vdd", "gnd"])

    def place_instances(self):
        # Add the DFF
        self.dff_inst.place(vector(0,0))

        # Add INV1 to the right
        self.inv1_inst.place(vector(self.dff_inst.rx(),0))
        
        # Add INV2 to the right
        self.inv2_inst.place(vector(self.inv1_inst.rx(),0))
        
    def route_wires(self):
        # Route dff q to inv1 a
        q_pin = self.dff_inst.get_pin("Q")
        a1_pin = self.inv1_inst.get_pin("A")
        mid_x_offset = 0.5*(a1_pin.cx() + q_pin.cx())
        mid1 = vector(mid_x_offset, q_pin.cy())
        mid2 = vector(mid_x_offset, a1_pin.cy())
        self.add_path("metal3", [q_pin.center(), mid1, mid2, a1_pin.center()])
        self.add_via_center(layers=("metal2","via2","metal3"),
                            offset=q_pin.center())
        self.add_via_center(layers=("metal2","via2","metal3"),
                            offset=a1_pin.center())
        self.add_via_center(layers=("metal1","via1","metal2"),
                            offset=a1_pin.center())

        # Route inv1 z to inv2 a
        z1_pin = self.inv1_inst.get_pin("Z")
        a2_pin = self.inv2_inst.get_pin("A")
        mid_x_offset = 0.5*(z1_pin.cx() + a2_pin.cx())
        self.mid_qb_pos = vector(mid_x_offset, z1_pin.cy())
        mid2 = vector(mid_x_offset, a2_pin.cy())
        self.add_path("metal1", [z1_pin.center(), self.mid_qb_pos, mid2, a2_pin.center()])
        
    def add_layout_pins(self):

        # Continous vdd rail along with label.
        vdd_pin=self.dff_inst.get_pin("vdd")
        self.add_layout_pin(text="vdd",
                            layer="metal1",
                            offset=vdd_pin.ll(),
                            width=self.width,
                            height=vdd_pin.height())

        # Continous gnd rail along with label.
        gnd_pin=self.dff_inst.get_pin("gnd")
        self.add_layout_pin(text="gnd",
                            layer="metal1",
                            offset=gnd_pin.ll(),
                            width=self.width,
                            height=vdd_pin.height())
            
        clk_pin = self.dff_inst.get_pin("clk")
        self.add_layout_pin(text="clk",
                            layer=clk_pin.layer,
                            offset=clk_pin.ll(),
                            width=clk_pin.width(),
                            height=clk_pin.height())

        din_pin = self.dff_inst.get_pin("D")
        self.add_layout_pin(text="D",
                            layer=din_pin.layer,
                            offset=din_pin.ll(),
                            width=din_pin.width(),
                            height=din_pin.height())

        dout_pin = self.inv2_inst.get_pin("Z")
        mid_pos = dout_pin.center() + vector(self.m1_pitch,0)
        q_pos = mid_pos - vector(0,self.m2_pitch)
        self.add_layout_pin_rect_center(text="Q",
                                        layer="metal2",
                                        offset=q_pos)
        self.add_path("metal1", [dout_pin.center(), mid_pos, q_pos])
        self.add_via_center(layers=("metal1","via1","metal2"),
                            offset=q_pos)

        qb_pos = self.mid_qb_pos + vector(0,self.m2_pitch)
        self.add_layout_pin_rect_center(text="Qb",
                                        layer="metal2",
                                        offset=qb_pos)
        self.add_path("metal1", [self.mid_qb_pos, qb_pos])
        self.add_via_center(layers=("metal1","via1","metal2"),
                            offset=qb_pos)
        
        

    def analytical_delay(self, corner, slew, load=0.0):
        """ Calculate the analytical delay of DFF-> INV -> INV """
        dff_delay=self.dff.analytical_delay(corner, slew=slew, load=self.inv1.input_load())
        inv1_delay = self.inv1.analytical_delay(corner, slew=dff_delay.slew, load=self.inv2.input_load()) 
        inv2_delay = self.inv2.analytical_delay(corner, slew=inv1_delay.slew, load=load)
        return dff_delay + inv1_delay + inv2_delay
            
    def get_clk_cin(self):
        """Return the total capacitance (in relative units) that the clock is loaded by in the dff"""
        #This is a handmade cell so the value must be entered in the tech.py file or estimated.
        #Calculated in the tech file by summing the widths of all the gates and dividing by the minimum width.
        #FIXME: Dff changed in a past commit. The parameter need to be updated.
        return parameter["dff_clk_cin"]
