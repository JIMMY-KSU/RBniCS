# Copyright (C) 2015-2018 by the RBniCS authors
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

from dolfin import *
from rbnics import *

class UnsteadyThermalBlock(ParabolicCoerciveProblem):
    
    # Default initialization of members
    def __init__(self, V, **kwargs):
        # Call the standard initialization
        ParabolicCoerciveProblem.__init__(self, V, **kwargs)
        # ... and also store FEniCS data structures for assembly
        assert "subdomains" in kwargs
        assert "boundaries" in kwargs
        self.subdomains, self.boundaries = kwargs["subdomains"], kwargs["boundaries"]
        self.u = TrialFunction(V)
        self.v = TestFunction(V)
        self.dx = Measure("dx")(subdomain_data=self.subdomains)
        self.ds = Measure("ds")(subdomain_data=self.boundaries)
        # Store the initial condition expression
        self.ic = Expression("1-x[1]", element=self.V.ufl_element())
        
    # Return custom problem name
    def name(self):
        return "UnsteadyThermalBlock2RB"
        
    # Return the alpha_lower bound.
    def get_stability_factor(self):
        return min(self.compute_theta("a"))
    
    # Return theta multiplicative terms of the affine expansion of the problem.
    def compute_theta(self, term):
        mu = self.mu
        if term == "m":
            theta_m0 = 1.
            return (theta_m0, )
        elif term == "a":
            theta_a0 = mu[0]
            theta_a1 = 1.
            return (theta_a0, theta_a1)
        elif term == "f":
            theta_f0 = mu[1]
            return (theta_f0,)
        elif term == "initial_condition":
            theta_ic0 = - mu[1]
            return (theta_ic0,)
        else:
            raise ValueError("Invalid term for compute_theta().")
                
    # Return forms resulting from the discretization of the affine expansion of the problem operators.
    def assemble_operator(self, term):
        v = self.v
        dx = self.dx
        if term == "m":
            u = self.u
            m0 = u*v*dx
            return (m0, )
        elif term == "a":
            u = self.u
            a0 = inner(grad(u), grad(v))*dx(1)
            a1 = inner(grad(u), grad(v))*dx(2)
            return (a0, a1)
        elif term == "f":
            ds = self.ds
            f0 = v*ds(1)
            return (f0,)
        elif term == "dirichlet_bc":
            bc0 = [DirichletBC(self.V, Constant(0.0), self.boundaries, 3)]
            return (bc0,)
        elif term == "initial_condition":
            ic0 = project(self.ic, self.V)
            return (ic0,)
        elif term == "inner_product":
            u = self.u
            x0 = inner(grad(u), grad(v))*dx
            return (x0,)
        elif term == "projection_inner_product":
            u = self.u
            x0 = u*v*dx
            return (x0,)
        else:
            raise ValueError("Invalid term for assemble_operator().")
        
# 1. Read the mesh for this problem
mesh = Mesh("data/thermal_block.xml")
subdomains = MeshFunction("size_t", mesh, "data/thermal_block_physical_region.xml")
boundaries = MeshFunction("size_t", mesh, "data/thermal_block_facet_region.xml")

# 2. Create Finite Element space (Lagrange P1, two components)
V = FunctionSpace(mesh, "Lagrange", 1)

# 3. Allocate an object of the UnsteadyThermalBlock class
unsteady_thermal_block_problem = UnsteadyThermalBlock(V, subdomains=subdomains, boundaries=boundaries)
mu_range = [(0.1, 10.0), (-1.0, 1.0)]
unsteady_thermal_block_problem.set_mu_range(mu_range)
unsteady_thermal_block_problem.set_time_step_size(0.05)
unsteady_thermal_block_problem.set_final_time(3)

# 4. Prepare reduction with a reduced basis method
reduced_basis_method = ReducedBasis(unsteady_thermal_block_problem)
reduced_basis_method.set_Nmax(20, POD_Greedy=4)
reduced_basis_method.set_tolerance(1e-5, POD_Greedy=1e-2)

# 5. Perform the offline phase
first_mu = (0.5, 1.0)
unsteady_thermal_block_problem.set_mu(first_mu)
reduced_basis_method.initialize_training_set(100)
reduced_unsteady_thermal_block_problem = reduced_basis_method.offline()

# 6. Perform an online solve
online_mu = (8.0, -1.0)
reduced_unsteady_thermal_block_problem.set_mu(online_mu)
reduced_unsteady_thermal_block_problem.solve()
reduced_unsteady_thermal_block_problem.export_solution(filename="online_solution")

# 7. Perform an error analysis
reduced_basis_method.initialize_testing_set(10)
reduced_basis_method.error_analysis()

# 8. Perform a speedup analysis
reduced_basis_method.speedup_analysis()
