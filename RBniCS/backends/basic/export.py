# Copyright (C) 2015-2016 by the RBniCS authors
#
# This file is part of RBniCS.
#
# RBniCS is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# RBniCS is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with RBniCS. If not, see <http://www.gnu.org/licenses/>.
#
## @file
#  @brief
#
#  @author Francesco Ballarin <francesco.ballarin@sissa.it>
#  @author Gianluigi Rozza    <gianluigi.rozza@sissa.it>
#  @author Alberto   Sartori  <alberto.sartori@sissa.it>

def export(solution, directory, filename, suffix, component, backend, wrapping):
    assert isinstance(solution, (backend.Function.Type(), backend.Matrix.Type(), backend.Vector.Type()))
    if isinstance(solution, backend.Function.Type()):
        if component is None:
            wrapping.function_save(solution, directory, filename, suffix=suffix)
        else:
            restricted_solution = wrapping.function_extend_or_restrict(solution, component, wrapping.get_function_subspace(solution.function_space(), component), None, weight=None, copy=True)
            wrapping.function_save(restricted_solution, directory, filename, suffix=suffix)
    elif isinstance(solution, (backend.Matrix.Type(), backend.Vector.Type())):
        assert component is None
        assert suffix is None
        wrapping.tensor_save(solution, directory, filename)
    else: # impossible to arrive here anyway, thanks to the assert
        raise AssertionError("Invalid arguments in export.")
        
