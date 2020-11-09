"""
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Copyright: (c) 2020, Deutsches Zentrum fuer Luft- und Raumfahrt e.V.
Contact: jasper.bussemaker@dlr.de
"""

from typing import *
from enum import Enum
import openmdao.api as om
import pycycle.api as pyc
from dataclasses import dataclass
import open_turb_arch.evaluation.architecture.units as units
from open_turb_arch.evaluation.architecture.architecture import ArchElement

__all__= ['Compressor', 'CompressorMap', 'Burner', 'FuelType', 'Turbine', 'TurbineMap', 'Shaft']


@dataclass(frozen=False)
class BaseTurboMachinery(ArchElement):

    def __post_init__(self):
        self.__shaft = None

    @property
    def shaft(self):
        return self.__shaft

    @shaft.setter
    def shaft(self, shaft: 'Shaft'):
        self.__shaft = shaft

    def add_element(self, cycle: pyc.Cycle, thermo_data, design: bool) -> om.Group:
        raise NotImplementedError

    def connect(self, cycle: pyc.Cycle):
        raise NotImplementedError

    def connect_des_od(self, mp_cycle: pyc.MPCycle):
        raise NotImplementedError


class CompressorMap(Enum):
    AXI_5 = 'AXI5'
    LPC = 'LPCMap'
    HPC = 'HPCMap'


@dataclass(frozen=False)
class Compressor(BaseTurboMachinery):
    target: ArchElement = None
    map: CompressorMap = CompressorMap.AXI_5
    mach: float = .01  # Reference Mach number for loss calculations
    pr: float = 5.  # Compression pressure ratio
    eff: float = 1.  # Enthalpy rise efficiency (<1 is less efficient)

    def add_element(self, cycle: pyc.Cycle, thermo_data, design: bool) -> om.Group:
        if self.shaft is None:
            raise ValueError('Not connected to shaft: %r' % self)

        map_data = getattr(pyc, self.map.value)
        el = pyc.Compressor(map_data=map_data, design=design, thermo_data=thermo_data, elements=pyc.AIR_MIX)
        cycle.pyc_add_element(self.name, el, promotes_inputs=[('Nmech', self.shaft.name+'_Nmech')])

        if design:
            el.set_input_defaults('MN', self.mach)
        return el

    def connect(self, cycle: pyc.Cycle):
        self._connect_flow_target(cycle, self.target)

    def connect_des_od(self, mp_cycle: pyc.MPCycle):
        for param in ['s_PR', 's_Wc', 's_eff', 's_Nc']:
            mp_cycle.pyc_connect_des_od('%s.%s' % (self.name, param), '%s.%s' % (self.name, param))

        mp_cycle.pyc_connect_des_od(self.name+'.Fl_O:stat:area', self.name+'.area')

    def set_problem_values(self, problem: om.Problem, des_con_name: str, eval_con_names: List[str]):
        problem.set_val('%s.%s.PR' % (des_con_name, self.name), self.pr)
        problem.set_val('%s.%s.eff' % (des_con_name, self.name), self.eff)


class FuelType(Enum):
    JET_A = 'Jet-A(g)'  # Standard jet fuel
    JP_7 = 'JP-7'  # Supersonic


@dataclass(frozen=False)
class Burner(ArchElement):
    target: ArchElement = None
    fuel: FuelType = FuelType.JET_A  # Type of fuel
    mach: float = .01  # Reference Mach number for loss calculations
    p_loss_frac: float = 0.  # Pressure loss as fraction of incoming pressure (dPqP)

    def add_element(self, cycle: pyc.Cycle, thermo_data, design: bool) -> om.Group:
        el = pyc.Combustor(design=design, thermo_data=thermo_data, inflow_elements=pyc.AIR_MIX,
                           air_fuel_elements=pyc.AIR_FUEL_MIX, fuel_type=self.fuel.value)
        cycle.pyc_add_element(self.name, el)

        if design:
            el.set_input_defaults('MN', self.mach)
        return el

    def connect(self, cycle: pyc.Cycle):
        self._connect_flow_target(cycle, self.target)

    def add_cycle_params(self, mp_cycle: pyc.MPCycle):
        mp_cycle.pyc_add_cycle_param(self.name+'.dPqP', self.p_loss_frac)

    def connect_des_od(self, mp_cycle: pyc.MPCycle):
        mp_cycle.pyc_connect_des_od(self.name+'.Fl_O:stat:area', self.name+'.area')


class TurbineMap(Enum):
    LPT_2269 = 'LPT2269'
    LPT = 'LPTMap'
    HPT = 'HPTMap'


@dataclass(frozen=False)
class Turbine(BaseTurboMachinery):
    target: ArchElement = None
    map: TurbineMap = TurbineMap.LPT_2269
    mach: float = .4  # Reference Mach number for loss calculations
    eff: float = 1.  # Enthalpy rise efficiency (<1 is less efficient)

    def add_element(self, cycle: pyc.Cycle, thermo_data, design: bool) -> om.Group:
        if self.shaft is None:
            raise ValueError('Not connected to shaft: %r' % self)

        map_data = getattr(pyc, self.map.value)
        el = pyc.Turbine(map_data=map_data, design=design, thermo_data=thermo_data, elements=pyc.AIR_FUEL_MIX)
        cycle.pyc_add_element(self.name, el, promotes_inputs=[('Nmech', self.shaft.name+'_Nmech')])

        if design:
            el.set_input_defaults('MN', self.mach)
        return el

    def connect(self, cycle: pyc.Cycle):
        self._connect_flow_target(cycle, self.target)

    def connect_des_od(self, mp_cycle: pyc.MPCycle):
        for param in ['s_PR', 's_Wp', 's_eff', 's_Np']:
            mp_cycle.pyc_connect_des_od('%s.%s' % (self.name, param), '%s.%s' % (self.name, param))

        mp_cycle.pyc_connect_des_od(self.name+'.Fl_O:stat:area', self.name+'.area')

    def set_problem_values(self, problem: om.Problem, des_con_name: str, eval_con_names: List[str]):
        problem.set_val('%s.%s.eff' % (des_con_name, self.name), self.eff)


@dataclass(frozen=False)
class Shaft(ArchElement):
    connections: List[BaseTurboMachinery] = None
    rpm_design: float = 10000.  # Design shaft rotation speed [rpm]
    power_loss: float = 0.  # Fraction of power lost

    def __post_init__(self):
        for conn in self.connections:
            if conn.shaft is not None:
                raise ValueError('Shaft already set: %r' % conn)
            conn.shaft = self

    def add_element(self, cycle: pyc.Cycle, thermo_data, design: bool) -> om.Group:
        if self.connections is None or len(self.connections) < 2:
            raise ValueError('Shaft should at least connect two turbomachinery elements!')

        el = pyc.Shaft(num_ports=len(self.connections))
        cycle.pyc_add_element(self.name, el, promotes_inputs=[('Nmech', self.name+'_Nmech')])

        if design:
            cycle.set_input_defaults(self.name +'_Nmech', self.rpm_design, units=units.RPM)
        return el

    def connect(self, cycle: pyc.Cycle):
        for i, element in enumerate(self.connections):
            cycle.connect(element.name+'.trq', '%s.trq_%d' % (self.name, i))

    def add_cycle_params(self, mp_cycle: pyc.MPCycle):
        mp_cycle.pyc_add_cycle_param(self.name+'.fracLoss', self.power_loss)

    def connect_des_od(self, mp_cycle: pyc.MPCycle):
        pass
