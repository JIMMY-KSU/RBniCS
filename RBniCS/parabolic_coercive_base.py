# Copyright (C) 2015 SISSA mathLab
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
## @file elliptic_coercive_base.py
#  @brief Implementation of projection based reduced order models for parabolic coervice problems: base class
#
#  @author Francesco Ballarin <francesco.ballarin@sissa.it>
#  @author Gianluigi Rozza    <gianluigi.rozza@sissa.it>
#  @author Alberto   Sartori  <alberto.sartori@sissa.it>

from elliptic_coercive_base import *
import os
import shutil

#~~~~~~~~~~~~~~~~~~~~~~~~~     PARABOLIC COERCIVE BASE CLASS     ~~~~~~~~~~~~~~~~~~~~~~~~~# 
## @class ParablicCoerciveBase
#
# Base class containing the interface of a projection based ROM
# for parabolic coercive problems
class ParabolicCoerciveBase(EllipticCoerciveBase):

    ###########################     CONSTRUCTORS     ########################### 
    ## @defgroup Constructors Methods related to the construction of the POD-Galerkin ROM object
    #  @{
    
    ## Default initialization of members
    def __init__(self, V, bc_list):
        # Call the parent initialization
        EllipticCoerciveBase.__init__(self, V, bc_list)
        
        # $$ PROBLEM SPECIFIC $$ #
        # Time step
        self.dt = 0.01
        # Final time
        self.T = 1.
        # All times
        self.all_times = np.linspace(0., self.T, num = 1 + np.ceil(self.T/self.dt))
        # Current time
        self.t = 0.

        # $$ ONLINE DATA STRUCTURES $$ #
        # 3a. Number of terms in the affine expansion
        self.Qm = 1
        # 3b. Theta multiplicative factors of the affine expansion
        self.theta_m = (1., )
        # 3c. Reduced order matrices/vectors
        self.red_M = []
        # 4. Online solution
        self.all_uN = np.array([]) # array (size of T/dt + 1) of vectors of dimension N storing the reduced order solution
        
        # $$ OFFLINE DATA STRUCTURES $$ #
        # 3c. Matrices/vectors resulting from the truth discretization
        u = self.u
        v = self.v
        truth_m = inner(u,v)*dx
        self.truth_M = (assemble(truth_m), )
        # 4. Auxiliary functions
        self.all_snap = np.array([]) # array (size of T/dt + 1) of vectors for storage of a truth solution
        self.all_red = np.array([]) # array (size of T/dt + 1) of vectors for storage of the FE reconstruction of the reduced solution
        self.all_er = np.array([]) # array (size of T/dt + 1) of vectors for storage of the error
        
    #  @}
    ########################### end - CONSTRUCTORS - end ########################### 
    def set_dt(self,dt):
        self.dt = dt
        self.all_times = np.linspace(0., self.T, num = 1 + np.ceil(self.T/self.dt))
    def set_final_t(self, T):
        self.T = T
        self.all_times = np.linspace(0., self.T, num = 1 + np.ceil(self.T/self.dt))
    
    ###########################     ONLINE STAGE     ########################### 
    ## @defgroup OnlineStage Methods related to the online stage
    #  @{
    
    # Perform an online solve. self.N will be used as matrix dimension if the default value is provided for N.
    def online_solve(self, N=None, with_plot=False):
        self.load_red_matrices()
        if N is None:
            N = self.N
        self.all_uN = (self.red_F[0]*0.0).reshape(-1,1)
        self.uN = (self.red_F[0]*0.0).reshape(-1,1)
        
        # Set the initial condition
        self.t = 0.
        sol = self.Z[:, 0]*self.all_uN[0, 0]*0.0
        self.all_red = sol
        
        # Iterate in time
        for t in self.all_times[1:]:
            self.t = t
       #     print "t = " + str(self.t)
            self.red_solve(N)
            self.all_red = np.hstack((self.all_red, self.get_fe_functions_at_time(t)))

        # Now obtain the FE function corresponding to the reduced order solutions
        if with_plot == True:
            func = Function(self.V)
            func.vector()[:] = self.get_fe_functions_at_time(t)
            plot(func, title = "Reduced solution. mu = " + str(self.mu) + ", t = " + str(t*self.dt), interactive = True)
    
    def get_fe_functions_at_time(self,tt):
        sol = self.Z[:, 0]*self.all_uN[0,tt]
        i = 1
        for un in self.all_uN[1:,tt]:
            sol += self.Z[:,i]*np.float(un)
            i += 1
        func = Function(self.V)
        func.vector()[:] = sol
        return sol

    # Perform an online solve (internal)
    def red_solve(self, N):
        dt = self.dt
        # Need to possibly re-evaluate theta, since they may be time dependent
        self.theta_a = self.compute_theta_a()
        self.theta_f = self.compute_theta_f()
        assembled_red_M = self.aff_assemble_red_matrix(self.red_M, self.theta_m, N, N)
        assembled_red_A = self.aff_assemble_red_matrix(self.red_A, self.theta_a, N, N)
        assembled_red_F = self.aff_assemble_red_vector(self.red_F, self.theta_f, N)
        assembled_red_lhs = 1./dt*assembled_red_M + assembled_red_A
        assembled_red_rhs = 1./dt*assembled_red_M*np.matrix(self.uN) + assembled_red_F.reshape(-1,1) # uN -> solution at previous time
        if (self.N == 1):
            self.uN = assembled_red_rhs/assembled_red_lhs
        else:
            self.uN = np.linalg.solve(assembled_red_lhs, assembled_red_rhs)
        self.all_uN = np.hstack((self.all_uN, self.uN)) # add new solutions as column vectors
    
    #  @}
    ########################### end - ONLINE STAGE - end ########################### 
    
    ###########################     OFFLINE STAGE     ########################### 
    ## @defgroup OfflineStage Methods related to the offline stage
    #  @{

    def offline(self):
        print "=============================================================="
        print "=             Offline phase begins                           ="
        print "=============================================================="
        print ""
        if os.path.exists(self.pp_folder):
            shutil.rmtree(self.pp_folder)
        folders = (self.snap_folder, self.basis_folder, self.dual_folder, self.red_matrices_folder, self.pp_folder)
        for f in folders:
            if not os.path.exists(f):
                os.makedirs(f)
        
        self.truth_A = self.assemble_truth_a()
        self.apply_bc_to_matrix_expansion(self.truth_A)
        #self.truth_M = self.assemble_truth_M()
        self.apply_bc_to_matrix_expansion(self.truth_M)
        [bc.zero(self.truth_M[0]) for bc in self.bc_list]
        self.truth_F = self.assemble_truth_f()
        self.apply_bc_to_vector_expansion(self.truth_F)
        self.Qa = len(self.truth_A)
        self.Qm = len(self.truth_M)
        self.Qf = len(self.truth_F)

        while self.N < self.Nmax:
            print "############################## N = ", self.N, " ######################################"
            
            print "truth solve for mu = ", self.mu
            self.truth_solve()
            
            print "update basis matrix" 
            self.update_basis_matrix()
            
            print "build reduced matrices"
            self.build_red_matrices()
            self.build_red_vectors()
            
            print "solve rb"
            ParabolicCoerciveBase.online_solve(self,self.N,False)
            
            print "build matrices for error estimation (it may take a while)"
            self.compute_dual_terms()
            
            if self.N < self.Nmax:
                print "find next mu"
                self.greedy()
            else:
                self.greedy()

            print ""
            
        print "=============================================================="
        print "=             Offline phase ends                             ="
        print "=============================================================="
        print ""
    ## Perform a truth solve
    def truth_solve(self):
        # Set the initial condition
        dt = self.dt
        self.t = 0.
        self.snap = interpolate(Constant(0.0),self.V)
        self.all_snap = np.array(self.snap.vector()).reshape(-1, 1) # as column vector
        
        # Iterate in time
        for k in range(1,len(self.all_times)):
            self.t = self.all_times[k]
            sys.stdout.write('\rT = ' + str(self.t)+ '     ')
            sys.stdout.flush()
            # Need to possibly re-evaluate theta, since they may be time dependent
            self.theta_a = self.compute_theta_a()
            self.theta_f = self.compute_theta_f()
            assembled_truth_M = self.aff_assemble_truth_matrix(self.truth_M, self.theta_m)
            assembled_truth_A = self.aff_assemble_truth_matrix(self.truth_A, self.theta_a)
            assembled_truth_F = self.aff_assemble_truth_vector(self.truth_F, self.theta_f)
            assembled_truth_lhs = 1./dt*assembled_truth_M + assembled_truth_A
            assembled_truth_rhs = 1./dt*assembled_truth_M*self.snap.vector() + assembled_truth_F  # snap -> solution at previous time
            solve(assembled_truth_lhs, self.snap.vector(), assembled_truth_rhs)
            self.all_snap = np.hstack((self.all_snap, self.snap.vector())) # add new solutions as column vectors
        print ""
        
    ## Assemble the reduced order affine expansion (matrix)
    def build_red_matrices(self):
        # Assemble the reduced matrix A, as in parent
        EllipticCoerciveBase.build_red_matrices(self)
        # Moreover, assemble also the reduced matrix M
        red_M = ()
        i = 0
        for M in self.truth_M:
            M = as_backend_type(M)
            dim = M.size(0) # = M.size(1)
            if self.N == 1:
                red_M += (np.dot(self.Z.T,M.mat().getValues(range(dim),range(dim)).dot(self.Z)),)
            else:
                red = np.matrix(np.dot(self.Z.T,np.matrix(np.dot(M.mat().getValues(range(dim),range(dim)),self.Z))))
                red_M += (red,)
                i += 1
        self.red_M = red_M
        np.save(self.red_matrices_folder + "red_M", self.red_M)
    
    #  @}
    ########################### end - OFFLINE STAGE - end ########################### 
    
    ###########################     ERROR ANALYSIS     ########################### 
    ## @defgroup ErrorAnalysis Error analysis
    #  @{
    
    # Compute the error of the reduced order approximation with respect to the full order one
    # for the current value of mu
    def compute_error(self, N=None, skip_truth_solve=False):
        if not skip_truth_solve:
            self.truth_solve()
        self.online_solve(N, False)
        self.er = np.array([])
        error = 0.
        for k in range(len(self.all_times)):
            current_er.vector()[:] = self.all_snap[:, k].vector()[:] - self.all_red[:, k].vector()[:] # error as a function
            self.t = self.all_times[k] # needed by the next line, since theta_a ...
            print "t = " + str(self.t)
            self.theta_a = self.compute_theta_a() # ... may depend on time
            assembled_truth_A_sym = self.aff_assemble_truth_sym_matrix(self.truth_A, self.theta_a)
            error += 1./self.dt * self.compute_scalar(current_er, current_er, assembled_truth_A_sym) # norm of the error
        return np.sqrt(error)
        
    #  @}
    ########################### end - ERROR ANALYSIS - end ########################### 
    
    ###########################     I/O     ########################### 
    ## @defgroup IO Input/output methods
    #  @{
    
    ## Load reduced order data structures
    def load_red_matrices(self):
        # Read in data structures as in parent
        EllipticCoerciveBase.load_red_matrices(self)
        # Moreover, read in also the reduced matrix M
        if not self.red_M: # avoid loading multiple times
            self.red_M = tuple(np.load(self.red_matrices_folder + "red_M.npy"))
        # TODO ne serviranno altre?
        
    ## Export snapshot in VTK format
    def export_solution(self, solution, filename):
        file = File(filename + ".pvd", "compressed")
        for k in range(len(self.all_times)):
            self.t = self.all_times[k]
            file << (solution[:, k], self.t)
            
    # Note that there is no need to override the export basis method. Basis are steady!
    
    #  @}
    ########################### end - I/O - end ########################### 

