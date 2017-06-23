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

from __future__ import print_function
from rbnics.problems.base import LinearTimeDependentProblem
from rbnics.problems.stokes import StokesProblem
from rbnics.backends import product, sum
from rbnics.utils.decorators import Extends, override
from rbnics.utils.mpi import log, print, PROGRESS

StokesUnsteadyProblem_Base = LinearTimeDependentProblem(StokesProblem)

# Base class containing the definition of saddle point problems
@Extends(StokesUnsteadyProblem_Base)
class StokesUnsteadyProblem(StokesUnsteadyProblem_Base):
    
    ## Default initialization of members
    @override
    def __init__(self, V, **kwargs):
        # Call to parent
        StokesUnsteadyProblem_Base.__init__(self, V, **kwargs)
        
        # Form names for saddle point problems
        self.terms.append("m")
        self.terms_order.update({"m": 2})
        
        # Auxiliary storage for supremizer enrichment, using a subspace of V
        self._supremizer_over_time = list() # of Functions
        
    class ProblemSolver(StokesUnsteadyProblem_Base.ProblemSolver):
        def residual_eval(self, t, solution, solution_dot):
            problem = self.problem
            problem.set_time(t)
            assembled_operator = dict()
            for term in ("m", "a", "b", "bt", "f", "g"):
                assembled_operator[term] = sum(product(problem.compute_theta(term), problem.operator[term]))
            return (
                  assembled_operator["m"]*solution_dot
                + assembled_operator["a"]*solution
                + assembled_operator["b"]*solution
                + assembled_operator["bt"]*solution
                - assembled_operator["f"]
                - assembled_operator["g"]        
            )
            
        def jacobian_eval(self, t, solution, solution_dot, solution_dot_coefficient):
            problem = self.problem
            problem.set_time(t)
            assembled_operator = dict()
            for term in ("m", "a", "b", "bt"):
                assembled_operator[term] = sum(product(problem.compute_theta(term), problem.operator[term]))
            return (
                  assembled_operator["m"]*solution_dot_coefficient
                + assembled_operator["a"]
                + assembled_operator["b"]
                + assembled_operator["bt"]
            )
    
    def _solve_supremizer(self, solution):
        print("# t =", self.t)
        StokesUnsteadyProblem_Base._solve_supremizer(self, solution)
    
    def _supremizer_cache_key_and_file(self):
        (cache_key, cache_file) = StokesUnsteadyProblem_Base._supremizer_cache_key_and_file(self)
        cache_key += (int(round(self.t/self.dt)), )
        return (cache_key, cache_file)
        
    def export_supremizer(self, folder, filename, supremizer=None, component=None, suffix=None):
        assert suffix is None
        StokesUnsteadyProblem_Base.export_supremizer(self, folder, filename, supremizer=supremizer, component=component, suffix=int(round(self.t/self.dt)))
        
    def import_supremizer(self, folder, filename, supremizer=None, component=None, suffix=None):
        assert suffix is None
        return StokesUnsteadyProblem_Base.import_supremizer(self, folder, filename, supremizer=supremizer, component=component, suffix=int(round(self.t/self.dt)))

    @override
    def export_solution(self, folder, filename, solution_over_time=None, solution_dot_over_time=None, component=None, suffix=None):
        if component is None:
            component = ["u", "p"] # but not "s"
        StokesUnsteadyProblem_Base.export_solution(self, folder, filename, solution_over_time, solution_dot_over_time, component, suffix)
        
    @override
    def import_solution(self, folder, filename, solution_over_time=None, solution_dot_over_time=None, component=None, suffix=None):
        if component is None:
            component = ["u", "p"] # but not "s"
        return StokesUnsteadyProblem_Base.import_solution(self, folder, filename, solution_over_time, solution_dot_over_time, component, suffix)
        