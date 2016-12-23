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
## @file functions_list.py
#  @brief Type for storing a list of FE functions.
#
#  @author Francesco Ballarin <francesco.ballarin@sissa.it>
#  @author Gianluigi Rozza    <gianluigi.rozza@sissa.it>
#  @author Alberto   Sartori  <alberto.sartori@sissa.it>

from collections import OrderedDict
from dolfin import assign
from RBniCS.backends.fenics.function import Function

def function_extend_or_restrict(function, function_components, V, V_components, weight, copy):
    function_V = function.function_space()
    if function_components is not None:
        assert isinstance(function_components, (int, tuple))
        assert not isinstance(function_components, list), "FEniCS does not handle yet the case of a list of components"
        if isinstance(function_components, int):
            function_V_index = (function_components, )
        else:
            function_V_index = function_components
    else:
        function_V_index = None
    if V_components is not None:
        assert isinstance(V_components, (int, tuple))
        assert not isinstance(V_components, list), "FEniCS does not handle yet the case of a list of components"
        if isinstance(V_components, int):
            V_index = (V_components, )
        else:
            V_index = V_components
    else:
        V_index = None
    
    V_to_function_V_mapping = dict()
    function_V_to_V_mapping = dict()
    
    if _function_spaces_eq(function_V, V, function_V_index, V_index):
        # Then function_V == V: do not need to extend nor restrict input function
        # Example of use case: function is the solution of an elliptic problem, V is the truth space
        if not copy:
            assert function_components is None, "It is not possible to extract function components without copying the vector"
            assert V_components is None, "It is not possible to extract function components without copying the vector"
            assert weight is None, "It is not possible to weigh components without copying the vector"
            return function
        else:
            output = Function(V) # zero by default
            assign(_sub_from_tuple(output, V_index), _sub_from_tuple(function, function_V_index))
            if weight is not None:
                output.vector()[:] *= weight
            return output
    elif _function_spaces_lt(function_V, V, V_to_function_V_mapping, function_V_index, V_index):
        # Then function_V < V: need to extend input function
        # Example of use case: function is the solution of the supremizer problem of a Stokes problem,
        # V is the mixed (velocity, pressure) space, and you are interested in storing a extended function
        # (i.e. extended to zero on pressure DOFs) when defining basis functions for enriched velocity space
        assert copy is True, "It is not possible to extend functions without copying the vector"
        extended_function = Function(V) # zero by default
        for (index_V_as_tuple, index_function_V_as_tuple) in V_to_function_V_mapping.iteritems():
            assign(_sub_from_tuple(extended_function, index_V_as_tuple), _sub_from_tuple(function, index_function_V_as_tuple))
        if weight is not None:
            extended_function.vector()[:] *= weight
        return extended_function
    elif _function_spaces_gt(function_V, V, function_V_to_V_mapping, function_V_index, V_index):
        # Then function_V > V: need to restrict input function
        # Example of use case: function = (y, u, p) is the solution of an elliptic optimal control problem,
        # V is the collapsed state (== adjoint) solution space, and you are
        # interested in storing snapshots of y or p components because of an aggregrated approach
        assert copy is True, "It is not possible to restrict functions without copying the vector"
        restricted_function = Function(V) # zero by default
        for (index_function_V_as_tuple, index_V_as_tuple) in function_V_to_V_mapping.iteritems():
            assign(_sub_from_tuple(restricted_function, index_V_as_tuple), _sub_from_tuple(function, index_function_V_as_tuple))
        if weight is not None:
            restricted_function.vector()[:] *= weight
        return restricted_function
    
def _function_spaces_eq(V, W, index_V, index_W): # V == W
    V = _sub_from_tuple(V, index_V)
    W = _sub_from_tuple(W, index_W)
    # V.sub(component) == W does not work properly
    # We thus resort to:
    assert V.ufl_domain() == W.ufl_domain()
    return V.ufl_element() == W.ufl_element()
    
def _function_spaces_lt(V, W, W_to_V_mapping, index_V, index_W): # V < W
    assert V.ufl_domain() == W.ufl_domain()
    assert len(W_to_V_mapping) == 0
    V_sub_elements = _get_sub_elements(V, index_V)
    W_sub_elements = _get_sub_elements(W, index_W)
    W_sub_elements_used = dict.fromkeys(W_sub_elements.keys(), False)
    should_return_False = False
    for (index_V, element_V) in V_sub_elements.iteritems():
        for (index_W, element_W) in W_sub_elements.iteritems():
            if (
                element_W == element_V 
                    and
                not W_sub_elements_used[index_W]
            ):
                assert index_W not in W_to_V_mapping
                W_to_V_mapping[index_W] = index_V
                W_sub_elements_used[index_W] = True
                break
        else: # for loop was not broken
            # There is an element in V which cannot be mapped to W, thus
            # V is larger than W
            should_return_False = True
            # Do not return immediately so that the map W_to_V_mapping
            # is filled in as best as possible
            
    if should_return_False:
        return False
            
    assert len(W_to_V_mapping) == len(V_sub_elements) # all elements were found
    
    # Avoid ambiguity that may arise if there were sub elements of W that were not used but had 
    # the same element type of used elements
    for (index_W_used, element_W_was_used) in W_sub_elements_used.iteritems():
        if element_W_was_used:
            for (index_W, element_W) in W_sub_elements.iteritems():
                if (
                    len(index_W_used) == len(index_W)
                        and
                    element_W == W_sub_elements[index_W_used]
                        and
                    not W_sub_elements_used[index_W]
                ):
                    raise RuntimeError("Ambiguity when querying _function_spaces_lt")
        
    return True
    
def _function_spaces_gt(V, W, V_to_W_mapping, index_V, index_W): # V > W
    return _function_spaces_lt(W, V, V_to_W_mapping, index_W, index_V)

def _get_sub_elements(V, index_V):
    sub_elements = _get_sub_elements__recursive(V, index_V)
    # Re-order sub elements for increasing tuple length to help
    # avoiding ambiguities
    sub_elements__sorted_by_index_length = dict()
    for (index, element) in sub_elements.iteritems():
        index_length = len(index)
        if index_length not in sub_elements__sorted_by_index_length:
            sub_elements__sorted_by_index_length[index_length] = OrderedDict()
        assert index not in sub_elements__sorted_by_index_length[index_length]
        sub_elements__sorted_by_index_length[index_length][index] = element
    assert min(sub_elements__sorted_by_index_length.keys()) == 1
    assert max(sub_elements__sorted_by_index_length.keys()) == len(sub_elements__sorted_by_index_length)
    output = OrderedDict()
    for index_length in range(1, len(sub_elements__sorted_by_index_length) + 1):
        output.update(sub_elements__sorted_by_index_length[index_length])
    return output
        
def _get_sub_elements__recursive(V, index_V):
    sub_elements = OrderedDict()
    if V.num_sub_spaces() == 0:
        if index_V is None:
            index_V = (None, )
        sub_elements[tuple(index_V)] = V.ufl_element()
        return sub_elements
    else:
        for i in range(V.num_sub_spaces()):
            index_V_comma_i = list()
            if index_V is not None:
                index_V_comma_i.extend(index_V)
            index_V_comma_i.append(i)
            sub_elements_i = _get_sub_elements__recursive(V.sub(i), index_V_comma_i)
            sub_elements.update(sub_elements_i)
        return sub_elements
        
def _sub_from_tuple(input_, index_as_tuple):
    if index_as_tuple is None:
        index_as_tuple = (None, )
    assert isinstance(index_as_tuple, tuple)
    assert len(index_as_tuple) > 0
    if len(index_as_tuple) == 1 and index_as_tuple[0] is None:
        return input_
    else:
        for i in index_as_tuple:
            input_ = input_.sub(i)
        return input_
        
