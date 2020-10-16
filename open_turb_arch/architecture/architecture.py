from typing import *
import pycycle.api as pyc
import openmdao.api as om
from dataclasses import dataclass, field

__all__ = ['ArchElement', 'TurbofanArchitecture']


@dataclass(frozen=False)
class ArchElement:
    """Base class for an architecture element, should also implement methods to add the element to a pyCycle Cycle
    group."""

    name: str

    def __hash__(self):
        return id(self)

    def add_element(self, cycle: pyc.Cycle, thermo_data, design: bool) -> om.Group:
        """Add the element to the pyCycle cycle object, should also initialize set input defaults"""
        raise NotImplementedError

    def connect(self, cycle: pyc.Cycle):
        """Connect the element to other elements: flow, mechanical, etc"""
        raise NotImplementedError

    def add_cycle_params(self, mp_cycle: pyc.MPCycle):
        """Add cycle parameters for the multi-point cycle."""

    def connect_des_od(self, mp_cycle: pyc.MPCycle):
        """Connect design parameters to off-design (evaluation) parameters"""
        raise NotImplementedError

    def set_problem_values(self, problem: om.Problem, des_con_name: str, eval_con_names: List[str]):
        """Set problem input values after the problem has been configured."""

    def _connect_flow_target(self, cycle: pyc.Cycle, target: 'ArchElement' = None, out_flow='Fl_O', in_flow='Fl_I'):
        if target is not None:
            cycle.pyc_connect_flow('%s.%s' % (self.name, out_flow), '%s.%s' % (target.name, in_flow))


@dataclass(frozen=False)
class TurbofanArchitecture:
    """Describes an instance of a turbofan architecture."""

    elements: List[ArchElement] = field(default_factory=list)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        return id(self)
