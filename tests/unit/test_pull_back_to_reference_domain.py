# Copyright (C) 2015- 2017 by the RBniCS authors
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
import itertools
from numpy import isclose
from dolfin import assemble, Constant, div, Expression, FiniteElement, FunctionSpace, grad, inner, Measure, Mesh, MeshFunction, MixedElement, pi, split, tan, TestFunction, TrialFunction, VectorElement
from rbnics import ShapeParametrization
from rbnics.backends.dolfin.wrapping import ParametrizedExpression, pull_back_forms_to_reference_domain

data_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data", "test_pull_back_to_reference_domain")

# Test forms pull back to reference domain for tutorial 3
def test_pull_back_to_reference_domain_hole():
    # Read the mesh for this problem
    mesh = Mesh(os.path.join(data_dir, "hole.xml"))
    subdomains = MeshFunction("size_t", mesh, os.path.join(data_dir, "hole_physical_region.xml"))
    boundaries = MeshFunction("size_t", mesh, os.path.join(data_dir, "hole_facet_region.xml"))
    
    # Define shape parametrization
    shape_parametrization_expression = [
        ("2 - 2*mu[0] + mu[0]*x[0] + (2 - 2*mu[0])*x[1]", "2 - 2*mu[1] + (2 - mu[1])*x[1]"), # subdomain 1
        ("2*mu[0]- 2 + x[0] + (mu[0] - 1)*x[1]", "2 - 2*mu[1] + (2 - mu[1])*x[1]"), # subdomain 2
        ("2 - 2*mu[0] + (2 - mu[0])*x[0]", "2 - 2*mu[1] + (2- 2*mu[1])*x[0] + mu[1]*x[1]"), # subdomain 3
        ("2 - 2*mu[0] + (2 - mu[0])*x[0]", "2*mu[1] - 2 + (mu[1] - 1)*x[0] + x[1]"), # subdomain 4
        ("2*mu[0] - 2 + (2 - mu[0])*x[0]", "2 - 2*mu[1] + (2*mu[1]- 2)*x[0] + mu[1]*x[1]"), # subdomain 5
        ("2*mu[0] - 2 + (2 - mu[0])*x[0]", "2*mu[1] - 2 + (1 - mu[1])*x[0] + x[1]"), # subdomain 6
        ("2 - 2*mu[0] + mu[0]*x[0] + (2*mu[0] - 2)*x[1]", "2*mu[1] - 2 + (2 - mu[1])*x[1]"), # subdomain 7
        ("2*mu[0] - 2 + x[0] + (1 - mu[0])*x[1]", "2*mu[1] - 2 + (2 - mu[1])*x[1]") # subdomain 8
    ]
    
    # Define function space, test/trial functions, measures
    V = FunctionSpace(mesh, "Lagrange", 1)
    u = TrialFunction(V)
    v = TestFunction(V)
    dx = Measure("dx")(subdomain_data=subdomains)
    ds = Measure("ds")(subdomain_data=boundaries)
    
    # Define base problem
    @ShapeParametrization(*shape_parametrization_expression)
    class Hole(object):
        def __init__(self, V, **kwargs):
            self.V = V
            self.mu = None
            
        def set_mu(self, mu):
            assert len(mu) is 3
            self.mu = mu
            
    # Define problem with forms written on reference domain
    class HoleOnReferenceDomain(Hole):
        def compute_theta(self, term):
            m1 = self.mu[0]
            m2 = self.mu[1]
            m3 = self.mu[2]
            if term == "a":
                # subdomains 1 and 7
                theta_a0 = - (m2 - 2)/m1 - (2*(2*m1 - 2)*(m1 - 1))/(m1*(m2 - 2)) # K11
                theta_a1 = -m1/(m2 - 2) # K22
                theta_a2 = -(2*(m1 - 1))/(m2 - 2) # K12 and K21
                # subdomains 2 and 8
                theta_a3 = 2 - (m1 - 1)*(m1 - 1)/(m2 - 2) - m2
                theta_a4 = -1/(m2 - 2)
                theta_a5 = (m1 - 1)/(m2 - 2)
                # subdomains 3 and 5
                theta_a6 = -m2/(m1 - 2)
                theta_a7 = - (m1 - 2)/m2 - (2*(2*m2 - 2)*(m2 - 1))/(m2*(m1 - 2))
                theta_a8 = -(2*(m2 - 1))/(m1 - 2)
                # subdomains 4 and 6
                theta_a9 = -1/(m1 - 2)
                theta_a10 = 2 - (m2 - 1)*(m2 - 1)/(m1 - 2) - m1
                theta_a11 = (m2 - 1)/(m1 - 2)
                # boundaries 5, 6, 7 and 8
                theta_a12 = m3
                # Return
                return (theta_a0, theta_a1, theta_a2, theta_a3, theta_a4, theta_a5, theta_a6, theta_a7, theta_a8, theta_a9, theta_a10, theta_a11, theta_a12)
            elif term == "f":
                theta_f0 = m1 # boundary 1
                theta_f1 = m2 # boundary 2
                theta_f2 = m1 # boundary 3
                theta_f3 = m2 # boundary 4
                # Return
                return (theta_f0, theta_f1, theta_f2, theta_f3)
            else:
                raise ValueError("Invalid term for compute_theta().")
                
        ## Return forms resulting from the discretization of the affine expansion of the problem operators.
        def assemble_operator(self, term):
            if term == "a":
                # subdomains 1 and 7
                a0 = inner(u.dx(0), v.dx(0))*dx(1) +  inner(u.dx(0), v.dx(0))*dx(7)
                a1 = inner(u.dx(1), v.dx(1))*dx(1) +  inner(u.dx(1), v.dx(1))*dx(7)
                a2 = inner(u.dx(0), v.dx(1))*dx(1) +  inner(u.dx(1), v.dx(0))*dx(1) - (inner(u.dx(0), v.dx(1))*dx(7) +  inner(u.dx(1), v.dx(0))*dx(7))
                # subdomains 2 and 8
                a3 = inner(u.dx(0), v.dx(0))*dx(2) +  inner(u.dx(0), v.dx(0))*dx(8)
                a4 = inner(u.dx(1), v.dx(1))*dx(2) +  inner(u.dx(1), v.dx(1))*dx(8)
                a5 = inner(u.dx(0), v.dx(1))*dx(2) +  inner(u.dx(1), v.dx(0))*dx(2) - (inner(u.dx(0), v.dx(1))*dx(8) +  inner(u.dx(1), v.dx(0))*dx(8))
                # subdomains 3 and 5
                a6 = inner(u.dx(0), v.dx(0))*dx(3) +  inner(u.dx(0), v.dx(0))*dx(5)
                a7 = inner(u.dx(1), v.dx(1))*dx(3) +  inner(u.dx(1), v.dx(1))*dx(5)
                a8 = inner(u.dx(0), v.dx(1))*dx(3) +  inner(u.dx(1), v.dx(0))*dx(3) - (inner(u.dx(0), v.dx(1))*dx(5) +  inner(u.dx(1), v.dx(0))*dx(5))
                # subdomains 4 and 6
                a9 = inner(u.dx(0), v.dx(0))*dx(4) +  inner(u.dx(0), v.dx(0))*dx(6)
                a10 = inner(u.dx(1), v.dx(1))*dx(4) +  inner(u.dx(1), v.dx(1))*dx(6)
                a11 = inner(u.dx(0), v.dx(1))*dx(4) +  inner(u.dx(1), v.dx(0))*dx(4) - (inner(u.dx(0), v.dx(1))*dx(6) +  inner(u.dx(1), v.dx(0))*dx(6))
                # boundaries 5, 6, 7 and 8
                a12 = inner(u,v)*ds(5) + inner(u,v)*ds(6) + inner(u,v)*ds(7) + inner(u,v)*ds(8)
                # Return
                return (a0, a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11, a12)
            elif term == "f":
                f0 = v*ds(1) # boundary 1
                f1 = v*ds(2) # boundary 2
                f2 = v*ds(3) # boundary 3
                f3 = v*ds(4) # boundary 4
                # Return
                return (f0, f1, f2, f3)
            else:
                raise ValueError("Invalid term for assemble_operator().")

    # Define problem with forms pulled back reference domain
    class HolePullBack(Hole):
        def compute_theta(self, term):
            m3 = self.mu[2]
            if term == "a":
                theta_a0 = 1.0
                theta_a1 = m3
                # Return
                return (theta_a0, theta_a1)
            elif term == "f":
                theta_f0 = 1.0
                # Return
                return (theta_f0, )
            else:
                raise ValueError("Invalid term for compute_theta().")
                
        ## Return forms resulting from the discretization of the affine expansion of the problem operators.
        @pull_back_forms_to_reference_domain("a", "f")
        def assemble_operator(self, term):
            if term == "a":
                a0 = inner(grad(u), grad(v))*dx
                a1 = inner(u,v)*ds(5) + inner(u,v)*ds(6) + inner(u,v)*ds(7) + inner(u,v)*ds(8)
                # Return
                return (a0, a1)
            elif term == "f":
                f0 = v*ds(1) + v*ds(2) + v*ds(3) + v*ds(4)
                # Return
                return (f0, )
            else:
                raise ValueError("Invalid term for assemble_operator().")
                    
    # Check forms
    problem_on_reference_domain = HoleOnReferenceDomain(V, subdomains=subdomains, boundaries=boundaries)
    problem_pull_back = HolePullBack(V, subdomains=subdomains, boundaries=boundaries)
    for mu in ((1., 1., 0.), (0.5, 1.5, 0.), (0.5, 0.5, 0.), (0.5, 1.5, 1.)):
        problem_on_reference_domain.set_mu(mu)
        problem_pull_back.set_mu(mu)
        a_1_on_reference_domain = sum([Constant(theta_a)*a for (theta_a, a) in zip(problem_on_reference_domain.compute_theta("a")[:12], problem_on_reference_domain.assemble_operator("a")[:12])])
        a_1_pull_back = sum([Constant(theta_a)*a for (theta_a, a) in zip(problem_pull_back.compute_theta("a")[:1], problem_pull_back.assemble_operator("a")[:1])])
        assert isclose(assemble(a_1_on_reference_domain).norm("frobenius"), assemble(a_1_pull_back).norm("frobenius"))
        a_2_on_reference_domain = sum([Constant(theta_a)*a for (theta_a, a) in zip(problem_on_reference_domain.compute_theta("a")[12:], problem_on_reference_domain.assemble_operator("a")[12:])])
        a_2_pull_back = sum([Constant(theta_a)*a for (theta_a, a) in zip(problem_pull_back.compute_theta("a")[1:], problem_pull_back.assemble_operator("a")[1:])])
        assert isclose(assemble(a_2_on_reference_domain).norm("frobenius"), assemble(a_2_pull_back).norm("frobenius"))
        f_on_reference_domain = sum([Constant(theta_f)*f for (theta_f, f) in zip(problem_on_reference_domain.compute_theta("f"), problem_on_reference_domain.assemble_operator("f"))])
        f_pull_back = sum([Constant(theta_f)*f for (theta_f, f) in zip(problem_pull_back.compute_theta("f"), problem_pull_back.assemble_operator("f"))])
        assert isclose(assemble(f_on_reference_domain).norm("l2"), assemble(f_pull_back).norm("l2"))
    
# Test shape parametrization gradient computation for tutorial 4
def test_pull_back_to_reference_domain_graetz():
    # Read the mesh for this problem
    mesh = Mesh(os.path.join(data_dir, "graetz.xml"))
    subdomains = MeshFunction("size_t", mesh, os.path.join(data_dir, "graetz_physical_region.xml"))
    boundaries = MeshFunction("size_t", mesh, os.path.join(data_dir, "graetz_facet_region.xml"))
    
    # Define shape parametrization
    shape_parametrization_expression = [
        ("x[0]", "x[1]"), # subdomain 1
        ("mu[0]*(x[0] - 1) + 1", "x[1]") # subdomain 2
    ]
    
    # Define function space, test/trial functions, measures, auxiliary expressions
    V = FunctionSpace(mesh, "Lagrange", 1)
    u = TrialFunction(V)
    v = TestFunction(V)
    dx = Measure("dx")(subdomain_data=subdomains)
    vel = Expression("x[1]*(1-x[1])", element=V.ufl_element())
    ff = Constant(1.)
    
    # Define base problem
    @ShapeParametrization(*shape_parametrization_expression)
    class Graetz(object):
        def __init__(self, V, **kwargs):
            self.V = V
            self.mu = None
            
        def set_mu(self, mu):
            assert len(mu) is 2
            self.mu = mu
            
    # Define problem with forms written on reference domain
    class GraetzOnReferenceDomain(Graetz):
        def compute_theta(self, term):
            mu1 = self.mu[0]
            mu2 = self.mu[1]
            if term == "a":
                theta_a0 = mu2
                theta_a1 = mu2/mu1
                theta_a2 = mu1*mu2
                theta_a3 = 1.0
                return (theta_a0, theta_a1, theta_a2, theta_a3)
            elif term == "f":
                theta_f0 = 1.0
                theta_f1 = mu1
                return (theta_f0, theta_f1)
            else:
                raise ValueError("Invalid term for compute_theta().")
                
        ## Return forms resulting from the discretization of the affine expansion of the problem operators.
        def assemble_operator(self, term):
            if term == "a":
                a0 = inner(grad(u), grad(v))*dx(1)
                a1 = u.dx(0)*v.dx(0)*dx(2)
                a2 = u.dx(1)*v.dx(1)*dx(2)
                a3 = vel*u.dx(0)*v*dx(1) + vel*u.dx(0)*v*dx(2)
                return (a0, a1, a2, a3)
            elif term == "f":
                f0 = ff*v*dx(1)
                f1 = ff*v*dx(2)
                return (f0, f1)
            else:
                raise ValueError("Invalid term for assemble_operator().")
                
    # Define problem with forms pulled back reference domain
    class GraetzPullBack(Graetz):
        def compute_theta(self, term):
            mu2 = self.mu[1]
            if term == "a":
                theta_a0 = mu2
                theta_a1 = 1.0
                return (theta_a0, theta_a1)
            elif term == "f":
                theta_f0 = 1.0
                return (theta_f0, )
            else:
                raise ValueError("Invalid term for compute_theta().")
                
        ## Return forms resulting from the discretization of the affine expansion of the problem operators.
        @pull_back_forms_to_reference_domain("a", "f")
        def assemble_operator(self, term):
            if term == "a":
                a0 = inner(grad(u), grad(v))*dx
                a1 = vel*u.dx(0)*v*dx
                return (a0, a1)
            elif term == "f":
                f0 = ff*v*dx
                return (f0, )
            else:
                raise ValueError("Invalid term for assemble_operator().")
    
    # Check forms
    problem_on_reference_domain = GraetzOnReferenceDomain(V, subdomains=subdomains, boundaries=boundaries)
    problem_pull_back = GraetzPullBack(V, subdomains=subdomains, boundaries=boundaries)
    for mu in ((0.1, 0.1), (10.0, 10.0), (0.1, 10.), (10., 0.1)):
        problem_on_reference_domain.set_mu(mu)
        problem_pull_back.set_mu(mu)
        a_on_reference_domain = sum([Constant(theta_a)*a for (theta_a, a) in zip(problem_on_reference_domain.compute_theta("a"), problem_on_reference_domain.assemble_operator("a"))])
        a_pull_back = sum([Constant(theta_a)*a for (theta_a, a) in zip(problem_pull_back.compute_theta("a"), problem_pull_back.assemble_operator("a"))])
        assert isclose(assemble(a_on_reference_domain).norm("frobenius"), assemble(a_pull_back).norm("frobenius"))
        f_on_reference_domain = sum([Constant(theta_f)*f for (theta_f, f) in zip(problem_on_reference_domain.compute_theta("f"), problem_on_reference_domain.assemble_operator("f"))])
        f_pull_back = sum([Constant(theta_f)*f for (theta_f, f) in zip(problem_pull_back.compute_theta("f"), problem_pull_back.assemble_operator("f"))])
        assert isclose(assemble(f_on_reference_domain).norm("l2"), assemble(f_pull_back).norm("l2"))
        
# Test shape parametrization gradient computation for tutorial 17:
def test_pull_back_to_reference_domain_stokes():
    # Read the mesh for this problem
    mesh = Mesh(os.path.join(data_dir, "t_bypass.xml"))
    subdomains = MeshFunction("size_t", mesh, os.path.join(data_dir, "t_bypass_physical_region.xml"))
    boundaries = MeshFunction("size_t", mesh, os.path.join(data_dir, "t_bypass_facet_region.xml"))
    
    # Define shape parametrization
    shape_parametrization_expression = [
        ("mu[4]*x[0] + mu[1] - mu[4]", "tan(mu[5])*x[0] + mu[0]*x[1] + mu[2] - tan(mu[5]) - mu[0]"), # subdomain 1
        ("mu[1]*x[0]", "mu[3]*x[1] + mu[2] + mu[0] - 2*mu[3]"), # subdomain 2
        ("mu[1]*x[0]", "mu[0]*x[1] + mu[2] - mu[0]"), # subdomain 3
        ("mu[1]*x[0]", "mu[2]*x[1]") # subdomain 4
    ]
    
    # Define function space, test/trial functions, measures, auxiliary expressions
    element_u = VectorElement("Lagrange", mesh.ufl_cell(), 2)
    element_p = FiniteElement("Lagrange", mesh.ufl_cell(), 1)
    element = MixedElement(element_u, element_p)
    V = FunctionSpace(mesh, element, components=[["u", "s"], "p"])
    up = TrialFunction(V)
    (u, p) = split(up)
    vq = TestFunction(V)
    (v, q) = split(vq)
    dx = Measure("dx")(subdomain_data=subdomains)
    ds = Measure("ds")(subdomain_data=boundaries)
    
    ff = Constant((0.0, -10.0))
    gg = Constant(1.0)
    nu = Constant(1.0)
    
    @ShapeParametrization(*shape_parametrization_expression)
    class Stokes(object):
        def __init__(self, V, **kwargs):
            self.V = V
            self.mu = None
            
        def set_mu(self, mu):
            assert len(mu) is 6
            self.mu = mu
            
    # Define problem with forms written on reference domain
    class StokesOnReferenceDomain(Stokes):
        def compute_theta(self, term):
            mu = self.mu
            mu1 = mu[0]
            mu2 = mu[1]
            mu3 = mu[2]
            mu4 = mu[3]
            mu5 = mu[4]
            mu6 = mu[5]
            if term == "a":
                theta_a0 = nu*(mu1/mu5)
                theta_a1 = nu*(-tan(mu6)/mu5)
                theta_a2 = nu*((tan(mu6)**2 + mu5**2)/(mu5*mu1))
                theta_a3 = nu*(mu4/mu2)
                theta_a4 = nu*(mu2/mu4)
                theta_a5 = nu*(mu1/mu2)
                theta_a6 = nu*(mu2/mu1)
                theta_a7 = nu*(mu3/mu2)
                theta_a8 = nu*(mu2/mu3)
                return (theta_a0, theta_a1, theta_a2, theta_a3, theta_a4, theta_a5, theta_a6, theta_a7, theta_a8)
            elif term in ("b", "bt"):
                theta_b0 = mu1
                theta_b1 = -tan(mu6)
                theta_b2 = mu5
                theta_b3 = mu4
                theta_b4 = mu2
                theta_b5 = mu1
                theta_b6 = mu2
                theta_b7 = mu3
                theta_b8 = mu2
                return (theta_b0, theta_b1, theta_b2, theta_b3, theta_b4, theta_b5, theta_b6, theta_b7, theta_b8)
            elif term == "f":
                theta_f0 = mu[0]*mu[4]
                theta_f1 = mu[1]*mu[3]
                theta_f2 = mu[0]*mu[1]
                theta_f3 = mu[1]*mu[2]
                return (theta_f0, theta_f1, theta_f2, theta_f3)
            elif term == "g":
                theta_g0 = mu[0]*mu[4]
                theta_g1 = mu[1]*mu[3]
                theta_g2 = mu[0]*mu[1]
                theta_g3 = mu[1]*mu[2]
                return (theta_g0, theta_g1, theta_g2, theta_g3)
            else:
                raise ValueError("Invalid term for compute_theta().")
            
        ## Return forms resulting from the discretization of the affine expansion of the problem operators.
        def assemble_operator(self, term):
            if term == "a":
                a0 = (u[0].dx(0)*v[0].dx(0) + u[1].dx(0)*v[1].dx(0))*dx(1)
                a1 = (u[0].dx(0)*v[0].dx(1) + u[0].dx(1)*v[0].dx(0) + u[1].dx(0)*v[1].dx(1) + u[1].dx(1)*v[1].dx(0))*dx(1)
                a2 = (u[0].dx(1)*v[0].dx(1) + u[1].dx(1)*v[1].dx(1))*dx(1)
                a3 = (u[0].dx(0)*v[0].dx(0) + u[1].dx(0)*v[1].dx(0))*dx(2)
                a4 = (u[0].dx(1)*v[0].dx(1) + u[1].dx(1)*v[1].dx(1))*dx(2)
                a5 = (u[0].dx(0)*v[0].dx(0) + u[1].dx(0)*v[1].dx(0))*dx(3)
                a6 = (u[0].dx(1)*v[0].dx(1) + u[1].dx(1)*v[1].dx(1))*dx(3)
                a7 = (u[0].dx(0)*v[0].dx(0) + u[1].dx(0)*v[1].dx(0))*dx(4)
                a8 = (u[0].dx(1)*v[0].dx(1) + u[1].dx(1)*v[1].dx(1))*dx(4)
                return (a0, a1, a2, a3, a4, a5, a6, a7, a8)
            elif term == "b":
                b0 = - q*u[0].dx(0)*dx(1)
                b1 = - q*u[0].dx(1)*dx(1)
                b2 = - q*u[1].dx(1)*dx(1)
                b3 = - q*u[0].dx(0)*dx(2)
                b4 = - q*u[1].dx(1)*dx(2)
                b5 = - q*u[0].dx(0)*dx(3)
                b6 = - q*u[1].dx(1)*dx(3)
                b7 = - q*u[0].dx(0)*dx(4)
                b8 = - q*u[1].dx(1)*dx(4)
                return (b0, b1, b2, b3, b4, b5, b6, b7, b8)
            elif term == "bt":
                bt0 = - p*v[0].dx(0)*dx(1)
                bt1 = - p*v[0].dx(1)*dx(1)
                bt2 = - p*v[1].dx(1)*dx(1)
                bt3 = - p*v[0].dx(0)*dx(2)
                bt4 = - p*v[1].dx(1)*dx(2)
                bt5 = - p*v[0].dx(0)*dx(3)
                bt6 = - p*v[1].dx(1)*dx(3)
                bt7 = - p*v[0].dx(0)*dx(4)
                bt8 = - p*v[1].dx(1)*dx(4)
                return (bt0, bt1, bt2, bt3, bt4, bt5, bt6, bt7, bt8)
            elif term == "f":
                f0 = inner(ff, v)*dx(1)
                f1 = inner(ff, v)*dx(2)
                f2 = inner(ff, v)*dx(3)
                f3 = inner(ff, v)*dx(4)
                return (f0, f1, f2, f3)
            elif term == "g":
                g0 = gg*q*dx(1)
                g1 = gg*q*dx(2)
                g2 = gg*q*dx(3)
                g3 = gg*q*dx(4)
                return (g0, g1, g2, g3)
            else:
                raise ValueError("Invalid term for assemble_operator().")
    
    # Define problem with forms pulled back reference domain
    class StokesPullBack(Stokes):
        def compute_theta(self, term):
            if term == "a":
                theta_a0 = nu*1.0
                return (theta_a0, )
            elif term in ("b", "bt"):
                theta_b0 = 1.0
                return (theta_b0, )
            elif term == "f":
                theta_f0 = 1.0
                return (theta_f0, )
            elif term == "g":
                theta_g0 = 1.0
                return (theta_g0, )
            else:
                raise ValueError("Invalid term for compute_theta().")
                
        ## Return forms resulting from the discretization of the affine expansion of the problem operators.
        @pull_back_forms_to_reference_domain("a", "b", "bt", "f", "g")
        def assemble_operator(self, term):
            if term == "a":
                a0 = inner(grad(u), grad(v))*dx
                return (a0, )
            elif term == "b":
                b0 = - q*div(u)*dx
                return (b0, )
            elif term == "bt":
                bt0 = - p*div(v)*dx
                return (bt0, )
            elif term == "f":
                f0 = inner(ff, v)*dx
                return (f0, )
            elif term == "g":
                g0 = q*gg*dx
                return (g0, )
            else:
                raise ValueError("Invalid term for assemble_operator().")
    
    # Check forms
    problem_on_reference_domain = StokesOnReferenceDomain(V, subdomains=subdomains, boundaries=boundaries)
    problem_pull_back = StokesPullBack(V, subdomains=subdomains, boundaries=boundaries)
    for mu in itertools.product((0.5, 1.5), (0.5, 1.5), (0.5, 1.5), (0.5, 1.5), (0.5, 1.5), (0.0, pi/6.0)):
        problem_on_reference_domain.set_mu(mu)
        problem_pull_back.set_mu(mu)
        
        a_on_reference_domain = sum([Constant(theta_a)*a for (theta_a, a) in zip(problem_on_reference_domain.compute_theta("a"), problem_on_reference_domain.assemble_operator("a"))])
        a_pull_back = sum([Constant(theta_a)*a for (theta_a, a) in zip(problem_pull_back.compute_theta("a"), problem_pull_back.assemble_operator("a"))])
        assert isclose(assemble(a_on_reference_domain).norm("frobenius"), assemble(a_pull_back).norm("frobenius"))
        
        b_on_reference_domain = sum([Constant(theta_b)*b for (theta_b, b) in zip(problem_on_reference_domain.compute_theta("b"), problem_on_reference_domain.assemble_operator("b"))])
        b_pull_back = sum([Constant(theta_b)*b for (theta_b, b) in zip(problem_pull_back.compute_theta("b"), problem_pull_back.assemble_operator("b"))])
        assert isclose(assemble(b_on_reference_domain).norm("frobenius"), assemble(b_pull_back).norm("frobenius"))
        
        bt_on_reference_domain = sum([Constant(theta_bt)*bt for (theta_bt, bt) in zip(problem_on_reference_domain.compute_theta("bt"), problem_on_reference_domain.assemble_operator("bt"))])
        bt_pull_back = sum([Constant(theta_bt)*bt for (theta_bt, bt) in zip(problem_pull_back.compute_theta("bt"), problem_pull_back.assemble_operator("bt"))])
        assert isclose(assemble(bt_on_reference_domain).norm("frobenius"), assemble(bt_pull_back).norm("frobenius"))
        
        f_on_reference_domain = sum([Constant(theta_f)*f for (theta_f, f) in zip(problem_on_reference_domain.compute_theta("f"), problem_on_reference_domain.assemble_operator("f"))])
        f_pull_back = sum([Constant(theta_f)*f for (theta_f, f) in zip(problem_pull_back.compute_theta("f"), problem_pull_back.assemble_operator("f"))])
        assert isclose(assemble(f_on_reference_domain).norm("l2"), assemble(f_pull_back).norm("l2"))
        
        g_on_reference_domain = sum([Constant(theta_g)*g for (theta_g, g) in zip(problem_on_reference_domain.compute_theta("g"), problem_on_reference_domain.assemble_operator("g"))])
        g_pull_back = sum([Constant(theta_g)*g for (theta_g, g) in zip(problem_pull_back.compute_theta("g"), problem_pull_back.assemble_operator("g"))])
        assert isclose(assemble(g_on_reference_domain).norm("l2"), assemble(g_pull_back).norm("l2"))