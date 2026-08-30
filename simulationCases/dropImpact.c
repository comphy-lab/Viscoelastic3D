/**
# Drop Impact Simulation

This file contains the simulation code for drop impact on a solid surface using 
a Volume of Fluid (VOF) method with viscoelastic fluid modeling capabilities.

The simulation uses an adaptive mesh refinement approach to efficiently resolve 
the interface dynamics during impact. The model can handle both Newtonian and 
viscoelastic fluids through a log-conformation formulation for the polymeric 
stress tensor.

## Physical Model

The simulation solves the Navier-Stokes equations for incompressible flow
coupled with a viscoelastic constitutive equation. The interface between
the two fluids is tracked using a VOF method with surface tension.

### Key dimensionless parameters:

- **Weber number** ($We$): Ratio of inertia to surface tension
- **Ohnesorge number** ($Oh$): Ratio of viscous to inertial and surface tension forces
- **Deborah number** ($De$): Ratio of relaxation time to characteristic flow time
- **Elastocapillary number** ($Ec$): Ratio of elastic to capillary forces

@file dropImpact.c
@author Vatsal Sanjay
@version 0.2
@date Oct 18, 2024
*/

// #include "axi.h"
#include "grid/octree.h"
// #include "grid/quadtree.h"
#include "navier-stokes/centered.h"

#define VANILLA 0
#if VANILLA
#include "log-conform-viscoelastic.h"
#define logFile "logAxi-vanilla.dat"
#else
#if AXI
#include "log-conform-viscoelastic-scalar-2D.h"
#define logFile "logAxi-scalar.dat"
#else
#include "log-conform-viscoelastic-scalar-3D.h"
#define logFile "log3D-scalar.dat"
#endif
#endif

#define FILTERED // Smear density and viscosity jumps
#include "two-phaseVE.h"

#include "navier-stokes/conserving.h"
#include "tension.h"

/**
## Simulation Parameters

### Timing Parameters
- tsnap: Time interval between snapshots (1e-2)
*/
#define tsnap (1e-2)

/**
### Numerical Error Tolerances
- fErr: Error tolerance in VOF function f1 (1e-3)
- KErr: Error tolerance in VOF curvature calculated using height function method (1e-6)
- VelErr: Error tolerances in velocity (1e-2)
  * Use 1e-2 for low Oh and 1e-3 to 5e-3 for high Oh/moderate to high J
*/
#define fErr (1e-3)
#define KErr (1e-6)
#define VelErr (1e-2)

/**
### Domain Configuration
- xDist: Initial horizontal displacement of droplet center from boundary (5e-2)
- R2: Function to calculate squared distance from droplet center
*/
#define xDist (5e-2)
#define R2(x, y, z)  (sq(x - 1. - xDist) + sq(y) + sq(z))

/**
## Boundary Conditions
Dirichlet boundary condition for volume fraction at left boundary.
Note: No-slip boundary conditions are commented out for testing purposes.
*/
// u.t[left] = dirichlet(0.); // todo: later on use no-slip. For testing, free-slip is faster.
// u.r[left] = dirichlet(0.); // todo: later on use no-slip. For testing, free-slip is faster.
f[left] = dirichlet(0.0);

/**
## Global Variables
- MAXlevel: Maximum level of grid refinement
- We: Weber number of the drop
- Oh: Solvent Ohnesorge number
- Oha: Air Ohnesorge number
- De: Deborah number
- Ec: Elasto-capillary number
- tmax: Maximum simulation time
- nameOut: Output filename for snapshots
- dumpFile: Filename for restart dumps
*/
int MAXlevel;
double We, Oh, Oha, De, Ec, tmax;
char nameOut[80], dumpFile[80];

/**
## Main Function
Initializes the simulation parameters and grid, then starts the simulation.

### Parameters
- argc: Command-line argument count
- argv: Command-line argument array

### Return Value
Returns 0 on successful completion
*/
int main(int argc, char const *argv[]) {

  DT = 1e-5;

  L0 = 4.0;
  
  // Values taken from the terminal
  MAXlevel = 6;
  tmax = 3.0;
  We = 5.0;
  Oh = 1e-2;
  Oha = 1e-2 * Oh;
  De = 1.0;
  Ec = 1.0;

  init_grid(1 << 4);

  // Create a folder named intermediate where all the simulation snapshots are stored
  char comm[80];
  sprintf(comm, "mkdir -p intermediate");
  system(comm);
  
  // Name of the restart file
  sprintf(dumpFile, "restart");

  // Set fluid properties for both phases
  rho1 = 1.0, rho2 = 1e-3;
  mu1 = Oh / sqrt(We), mu2 = Oha / sqrt(We);
  G1 = Ec / We, G2 = 0.0;
  lambda1 = De * sqrt(We), lambda2 = 0.0;
  
  f.sigma = 1.0 / We;

  run();
  
  return 0;
}

/**
## Initialization Event
Sets up the initial condition for the droplet and velocity field.

The event initializes a spherical droplet using the VOF method and sets
an initial horizontal velocity. If a restart file exists, the simulation
state is restored from it instead.

@param t Time (set to 0 for initialization)
*/
event init(t = 0) {
  if (!restore(file = dumpFile)) {
    refine(R2(x, y, z) < (1.1) && R2(x, y, z) > (0.9) && level < MAXlevel);
    fraction(f, (1 - R2(x, y, z)));
    foreach() {
      u.x[] = -f[] * 1.0;
    }
  }
}

/**
## Adaptive Mesh Refinement
Refines the computational mesh based on wavelet error estimates for the
tracked fields to efficiently allocate computational resources.

The refinement criteria track errors in:
- Volume fraction field (f)
- Velocity components (u.x, u.y, u.z)

@param i Current iteration number
*/
event adapt(i++) {
  adapt_wavelet((scalar *){f, u.x, u.y, u.z},
      (double[]){fErr, VelErr, VelErr, VelErr},
      MAXlevel, 4);
}

/**
## Snapshot Writing
Creates periodic dumps of the simulation state for visualization and restarts.

@param t Current simulation time
@param tsnap Time interval between snapshots
@param tmax Maximum simulation time
*/
event writingFiles(t = 0; t += tsnap; t <= tmax) {
  dump(file = dumpFile);
  sprintf(nameOut, "intermediate/snapshot-%5.4f", t);
  dump(file = nameOut);
}

/**
## Simulation Termination
Outputs final simulation parameters to standard error when the simulation ends.

@param t End time
*/
event end(t = end) {
  if (pid() == 0)
    fprintf(ferr, "Level %d, Oh %2.1e, We %2.1e, Oha %2.1e, De %2.1e, Ec %2.1e\n", 
            MAXlevel, Oh, We, Oha, De, Ec);
}

/**
## Simulation Logging
Records simulation progress and checks for numerical stability.

This event:
1. Calculates the total kinetic energy of the system
2. Writes simulation data to the log file
3. Checks for numerical stability based on kinetic energy values
4. Terminates the simulation if energy values indicate instability

@param i Current iteration number
@return Returns 1 (terminating the simulation) if instability is detected
*/
event logWriting(i++) {

  // Calculate kinetic energy
  double ke = 0.;
  foreach(reduction(+:ke)) {
    ke += (2 * pi * y) * (0.5 * rho(f[]) * (sq(u.x[]) + sq(u.y[]))) * sq(Delta);
  }

  static FILE *fp;
  if (pid() == 0) {
    const char *mode = (i == 0) ? "w" : "a";
    fp = fopen(logFile, mode);
    if (fp == NULL) {
      fprintf(ferr, "Error opening log file\n");
      return 1;
    }

    if (i == 0) {
      fprintf(ferr, "Level %d, Oh %2.1e, We %2.1e, Oha %2.1e, De %2.1e, Ec %2.1e\n", 
              MAXlevel, Oh, We, Oha, De, Ec);
      fprintf(ferr, "i dt t ke\n");
      fprintf(fp, "Level %d, Oh %2.1e, We %2.1e, Oha %2.1e, De %2.1e, Ec %2.1e\n", 
              MAXlevel, Oh, We, Oha, De, Ec);
      fprintf(fp, "i dt t ke rM\n");
    }

    fprintf(fp, "%d %g %g %g\n", i, dt, t, ke);
    fprintf(ferr, "%d %g %g %g\n", i, dt, t, ke);

    fflush(fp);
    fclose(fp);
  }

  assert(ke > -1e-10);

  // Stability check based on kinetic energy
  if (i > 1e1 && pid() == 0) {
    if (ke > 1e2 || ke < 1e-8) {
      const char *message = (ke > 1e2) ? 
        "The kinetic energy blew up. Stopping simulation\n" : 
        "Kinetic energy too small now! Stopping!\n";
      
      fprintf(ferr, "%s", message);
      
      fp = fopen("log", "a");
      fprintf(fp, "%s", message);
      fflush(fp);
      fclose(fp);
      
      dump(file = dumpFile);
      return 1;
    }
  }

}