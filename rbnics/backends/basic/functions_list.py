# Copyright (C) 2015-2017 by the RBniCS authors
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

import os
from numbers import Number
from rbnics.backends.abstract import FunctionsList as AbstractFunctionsList
from rbnics.utils.decorators import dict_of, list_of, overload, ThetaType, tuple_of
from rbnics.utils.mpi import is_io_process

# Type for storing a list of functions. From the user point of view this is
# the same as a matrix. Indeed, given a Matrix A, a Vector F
# and a FunctionsList Z, overriding __mul__ and __rmul__ operators
# allows to write expressions like transpose(Z)*A*Z and transpose(Z)*F
def FunctionsList(backend, wrapping, online_backend, online_wrapping, AdditionalIsFunction=None, ConvertAdditionalFunctionTypes=None):
    if AdditionalIsFunction is None:
        def _AdditionalIsFunction(arg):
            return False
        AdditionalIsFunction = _AdditionalIsFunction
    if ConvertAdditionalFunctionTypes is None:
        def _ConvertAdditionalFunctionTypes(arg):
            raise NotImplementedError("Please implement conversion of additional function types")
        ConvertAdditionalFunctionTypes = _ConvertAdditionalFunctionTypes
                
    class _FunctionsList(AbstractFunctionsList):
        def __init__(self, V_or_Z, component):
            if component is None:
                self.V_or_Z = V_or_Z
            else:
                self.V_or_Z = wrapping.get_function_subspace(V_or_Z, component)
            self.mpi_comm = wrapping.get_mpi_comm(V_or_Z)
            self._list = list() # of functions
            self._precomputed_slices = dict() # from tuple to FunctionsList
        
        def enrich(self, functions, component=None, weights=None, copy=True):
            # Append to storage
            self._enrich(functions, component, weights, copy)
            # Reset precomputed slices
            self._precomputed_slices = dict()
            # Prepare trivial precomputed slice
            self._precomputed_slices[len(self._list)] = self
        
        @overload(backend.Function.Type(), (None, str, dict_of(str, str)), (None, Number), bool)
        def _enrich(self, function, component, weight, copy):
            self._add_to_list(function, component, weight, copy)
        
        @overload((lambda cls: cls, list_of(backend.Function.Type()), tuple_of(backend.Function.Type())), (None, str, dict_of(str, str)), (None, list_of(Number)), bool)
        def _enrich(self, functions, component, weights, copy):
            if weights is not None:
                assert len(weights) == len(functions)
                for (index, function) in enumerate(functions):
                    self._add_to_list(function, component, weights[index], copy)
            else:
                for function in functions:
                    self._add_to_list(function, component, None, copy)
        
        @overload(object, (None, str, dict_of(str, str)), (None, Number, list_of(Number)), bool)
        def _enrich(self, function, component, weight, copy):
            if AdditionalIsFunction(function):
                function = ConvertAdditionalFunctionTypes(function)
                assert weight is None or isinstance(weight, Number)
                self._add_to_list(function, component, weight, copy)
            elif isinstance(function, list):
                converted_function = list()
                for function_i in function:
                    if AdditionalIsFunction(function_i):
                        converted_function.append(ConvertAdditionalFunctionTypes(function_i))
                    else:
                        raise RuntimeError("Invalid function provided to FunctionsList.enrich()")
                assert weight is None or isinstance(weight, list)
                self._enrich(converted_function, component, weight, copy)
            else:
                raise RuntimeError("Invalid function provided to FunctionsList.enrich()")
                
        @overload(backend.Function.Type(), (None, str), (None, Number), bool)
        def _add_to_list(self, function, component, weight, copy):
            self._list.append(wrapping.function_extend_or_restrict(function, component, self.V_or_Z, component, weight, copy))
            
        @overload(backend.Function.Type(), dict_of(str, str), (None, Number), bool)
        def _add_to_list(self, function, component, weight, copy):
            assert len(component) == 1
            for (component_from, component_to) in component.items():
                break
            self._list.append(wrapping.function_extend_or_restrict(function, component_from, self.V_or_Z, component_to, weight, copy))
            
        def clear(self):
            self._list = list()
            # Reset precomputed slices
            self._precomputed_slices = dict()
            
        def save(self, directory, filename):
            self._save_Nmax(directory, filename)
            for (index, function) in enumerate(self._list):
                wrapping.function_save(function, directory, filename + "_" + str(index))
                    
        def _save_Nmax(self, directory, filename):
            if is_io_process(self.mpi_comm):
                with open(os.path.join(str(directory), filename + ".length"), "w") as length:
                    length.write(str(len(self._list)))
            
        def load(self, directory, filename):
            if len(self._list) > 0: # avoid loading multiple times
                return False
            Nmax = self._load_Nmax(directory, filename)
            for index in range(Nmax):
                function = backend.Function(self.V_or_Z)
                loaded = wrapping.function_load(function, directory, filename + "_" + str(index))
                assert loaded
                self.enrich(function)
            return True
            
        def _load_Nmax(self, directory, filename):
            Nmax = None
            if is_io_process(self.mpi_comm):
                with open(os.path.join(str(directory), filename + ".length"), "r") as length:
                    Nmax = int(length.readline())
            Nmax = self.mpi_comm.bcast(Nmax, root=is_io_process.root)
            return Nmax
        
        @overload(online_backend.OnlineMatrix.Type(), )
        def __mul__(self, other):
            return wrapping.functions_list_mul_online_matrix(self, other, type(self))
        
        @overload((online_backend.OnlineVector.Type(), ThetaType), )
        def __mul__(self, other):
            return wrapping.functions_list_mul_online_vector(self, other)
            
        @overload(online_backend.OnlineFunction.Type(), )
        def __mul__(self, other):
            return wrapping.functions_list_mul_online_vector(self, online_wrapping.function_to_vector(other))
        
        def __len__(self):
            return len(self._list)

        @overload(int)
        def __getitem__(self, key):
            return self._list[key]
        
        @overload(slice) # e.g. key = :N, return the first N functions
        def __getitem__(self, key):
            assert key.start is None
            assert key.step is None
            assert key.stop <= len(self._list)
            
            if key.stop in self._precomputed_slices:
                return self._precomputed_slices[key.stop]
            else:
                output = _FunctionsList.__new__(type(self), self.V_or_Z)
                output.__init__(self.V_or_Z)
                output._list = self._list[key]
                self._precomputed_slices[key.stop] = output
                return output
                
        @overload(int, backend.Function.Type())
        def __setitem__(self, key, item):
            self._list[key] = item
            
        @overload(int, object)
        def __setitem__(self, key, item):
            if AdditionalIsFunction(item):
                item = ConvertAdditionalFunctionTypes(item)
                self._list[key] = item
            else:
                raise RuntimeError("Invalid function provided to FunctionsList.__setitem__()")
                
        def __iter__(self):
            return self._list.__iter__()
    return _FunctionsList
